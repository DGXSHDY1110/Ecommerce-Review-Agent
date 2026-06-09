"""LLM client interface for calling DeepSeek API.

Supports:
- Real API calls via OpenAI-compatible Chat Completions endpoint
- Mock mode for testing without API key
- JSON parse retry with safe fallback
- Error-case logging for observability
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

import requests

from .config import Settings, get_settings
from .schemas import ReviewInput, ReviewAnalysis
from .utils import log_error_case

logger = logging.getLogger(__name__)


# ── Prompt loading ────────────────────────────────────────────────────────────

def _load_system_prompt() -> str:
    """Extract the system prompt from prompts/review_classification_prompt.md.

    Returns the text inside the first fenced code block (``` ... ```) that
    follows the "System Prompt" heading.
    """
    prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "review_classification_prompt.md"
    if not prompt_path.exists():
        # Fallback minimal prompt if file is missing
        return (
            "You are a cross-border e-commerce review classifier. "
            "Output ONLY valid JSON with: sentiment, issue_category, priority, "
            "responsible_team, summary_zh, suggested_action_zh, confidence, needs_human_review. "
            "No explanation."
        )

    content = prompt_path.read_text(encoding="utf-8")

    # Find the first fenced code block after "System Prompt"
    match = re.search(r"```\n(.*?)\n```", content, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: return whole file content stripped of markdown headings
    return (
        "You are a cross-border e-commerce review classifier. "
        "Output ONLY valid JSON. No explanation."
    )


SYSTEM_PROMPT = _load_system_prompt()


# ── LLM Client ────────────────────────────────────────────────────────────────

class LLMClient:
    """Client for calling DeepSeek OpenAI-compatible Chat Completions API."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.api_key = self.settings.deepseek_api_key
        self.base_url = self.settings.deepseek_base_url
        self.model = self.settings.deepseek_model
        self.timeout = self.settings.llm_timeout_seconds
        self.max_retries = self.settings.llm_max_retries
        self.mock_mode = self.settings.llm_mock_mode

    # ── Public API ─────────────────────────────────────────────────────────

    def analyze_review(self, review: ReviewInput) -> ReviewAnalysis:
        """Analyze a single review. Delegates to mock or real API."""
        if self.mock_mode:
            return self._mock_analyze(review)

        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not set — falling back to mock mode")
            return self._mock_analyze(review)

        return self._call_api_with_retry(review)

    # ── Mock implementation ─────────────────────────────────────────────────

    def _mock_analyze(self, review: ReviewInput) -> ReviewAnalysis:
        """Return a rule-based classification without calling any API.

        Used when LLM_MOCK_MODE=true or when DEEPSEEK_API_KEY is missing.

        Mock strategy:
        - Clear reviews with explicit category keywords get confidence 0.85
        - Moderate reviews get confidence 0.80
        - Vague, short, or unclassifiable reviews get confidence 0.50
        - This produces a realistic mix: some auto-pass, some need human review
        """
        rating = review.rating
        text_lower = review.review_text.lower()
        text_len = len(review.review_text.strip())

        # Determine sentiment from rating
        if rating <= 2:
            sentiment = "negative"
        elif rating == 3:
            sentiment = "neutral"
        else:
            sentiment = "positive"

        # Determine issue category from keywords
        issue_category = self._classify_category(text_lower)
        priority = self._classify_priority(rating, issue_category)
        responsible_team = self._classify_team(issue_category)

        # ── Compute mock confidence ────────────────────────────────────
        confidence = self._compute_mock_confidence(
            text_lower, text_len, issue_category, rating, sentiment
        )

        # ── Determine initial needs_human_review ────────────────────────
        # Low confidence → always flag
        # High confidence → let guardrails catch any remaining issues
        needs_review = confidence < 0.6

        # Category-specific summaries (in Chinese)
        category_summaries: dict[str, str] = {
            "battery": f"用户反馈电池相关问题，评分{rating}。",
            "image_quality": f"用户反馈图像/摄像头质量问题，评分{rating}。",
            "logistics": f"用户反馈物流配送问题，评分{rating}。",
            "customer_service": f"用户反馈客服/售后问题，评分{rating}。",
            "price": f"用户反馈价格/性价比问题，评分{rating}。",
            "description_mismatch": f"用户反馈产品与描述不符，评分{rating}。",
            "product_quality": f"用户反馈产品质量问题，评分{rating}。",
            "other": f"用户反馈无法明确归类，评分{rating}。",
        }

        return ReviewAnalysis(
            review_id=review.review_id,
            sentiment=sentiment,
            issue_category=issue_category,
            priority=priority,
            responsible_team=responsible_team,
            summary_zh=category_summaries.get(
                issue_category,
                f"Mock分析：用户评分{rating}，类别{issue_category}。",
            ),
            suggested_action_zh=f"建议{responsible_team}团队查看该评论，确认是否需要跟进处理。",
            confidence=confidence,
            needs_human_review=needs_review,
        )

    @staticmethod
    def _compute_mock_confidence(
        text_lower: str,
        text_len: int,
        category: str,
        rating: int,
        sentiment: str,
    ) -> float:
        """Compute a mock confidence score based on review clarity.

        Rules (priority order):
        1. Short or vague text → 0.50 (need human review)
        2. Category is "other" → 0.50 (can't classify)
        3. Rating/sentiment mismatch → 0.50 (uncertain)
        4. Clear category + long descriptive text → 0.85
        5. Clear category + reasonable text → 0.80
        """
        # Very short reviews are inherently uncertain
        if text_len < 30:
            return 0.50

        # "other" category means we couldn't match any keyword
        if category == "other":
            return 0.50

        # Rating sent strong signal but model sentiment disagrees
        if rating <= 2 and sentiment != "negative":
            return 0.50
        if rating >= 4 and sentiment != "positive":
            return 0.50

        # Clear category + detailed review → high confidence
        if text_len >= 60:
            return 0.85

        # Reasonable review with a matched category
        return 0.80

    def _classify_category(self, text_lower: str) -> str:
        """Simple keyword-based category classification for mock mode."""
        if any(kw in text_lower for kw in ["battery", "charge", "charging", "drain", "power"]):
            return "battery"
        if any(kw in text_lower for kw in ["blurry", "night vision", "camera", "image", "photo", "video", "resolution"]):
            return "image_quality"
        if any(kw in text_lower for kw in ["shipping", "delivery", "package", "arrived", "tracking"]):
            return "logistics"
        if any(kw in text_lower for kw in ["customer service", "support", "refund", "return", "email", "contact"]):
            return "customer_service"
        if any(kw in text_lower for kw in ["price", "expensive", "cheap", "worth", "value", "cost"]):
            return "price"
        if any(kw in text_lower for kw in ["description", "match", "misalign", "wrong", "different", "not as"]):
            return "description_mismatch"
        if any(kw in text_lower for kw in ["quality", "build", "broke", "defect", "stop", "fail", "issue", "problem"]):
            return "product_quality"
        return "other"

    def _classify_priority(self, rating: int, category: str) -> str:
        if rating <= 2:
            return "high"
        elif rating == 3:
            return "medium"
        else:
            return "low"

    def _classify_team(self, category: str) -> str:
        mapping = {
            "logistics": "operations",
            "product_quality": "product",
            "battery": "product",
            "image_quality": "product",
            "customer_service": "customer_service",
            "price": "marketing",
            "description_mismatch": "supply_chain",
        }
        return mapping.get(category, "unknown")

    # ── Real API call ───────────────────────────────────────────────────────

    def _call_api_with_retry(self, review: ReviewInput) -> ReviewAnalysis:
        """Call the DeepSeek API, retrying on transient failures.

        Retry strategy:
        - JSON parse / validation errors → retry (the model might fix itself)
        - Network / timeout errors → retry
        - Non-2xx HTTP responses → retry (except 4xx client errors)
        - After all retries exhausted → safe fallback + error log
        """
        last_error: Optional[Exception] = None
        max_attempts = self.settings.retry_max_attempts

        for attempt in range(max_attempts):
            try:
                result = self._call_api_once(review)
                # Success — if we previously had errors, log a recovery note
                if attempt > 0:
                    logger.info(
                        "LLM call succeeded on attempt %d for review %s",
                        attempt + 1, review.review_id,
                    )
                return result

            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "LLM JSON parse failed (attempt %d/%d) for review %s",
                    attempt + 1, max_attempts, review.review_id,
                )

            except requests.Timeout as exc:
                last_error = exc
                logger.warning(
                    "LLM API timeout (attempt %d/%d) for review %s after %ds",
                    attempt + 1, max_attempts, review.review_id, self.timeout,
                )

            except requests.HTTPError as exc:
                last_error = exc
                status = exc.response.status_code if exc.response is not None else "?"
                # Do not retry on 4xx client errors (bad request, unauthorized, etc.)
                if isinstance(status, int) and 400 <= status < 500:
                    logger.error(
                        "LLM API client error HTTP %s for review %s — not retrying",
                        status, review.review_id,
                    )
                    break
                logger.warning(
                    "LLM API server error HTTP %s (attempt %d/%d) for review %s",
                    status, attempt + 1, max_attempts, review.review_id,
                )

            except requests.RequestException as exc:
                last_error = exc
                logger.warning(
                    "LLM API request failed (attempt %d/%d) for review %s: %s",
                    attempt + 1, max_attempts, review.review_id,
                    _safe_error_message(exc),
                )

        # ── All retries exhausted — return safe fallback ──────────────────
        error_type = _classify_error(last_error)
        error_msg = _safe_error_message(last_error) if last_error else "unknown"

        logger.error(
            "All %d LLM attempts failed for review %s (%s) — using safe fallback",
            max_attempts, review.review_id, error_type,
        )

        log_error_case(
            review_id=review.review_id,
            error_type=error_type,
            error_message=error_msg,
            fallback_used=True,
            needs_human_review=True,
        )

        return self._safe_fallback(review)

    def _call_api_once(self, review: ReviewInput) -> ReviewAnalysis:
        """Make a single API call and parse the response."""
        user_message = self._build_user_message(review)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Extract JSON from the response (may be wrapped in ```json fences)
        parsed = self._extract_json(content)
        return ReviewAnalysis(**parsed)

    def _build_user_message(self, review: ReviewInput) -> str:
        """Build the user message from a ReviewInput."""
        return json.dumps(
            {
                "review_id": review.review_id,
                "platform": review.platform,
                "product_name": review.product_name,
                "rating": review.rating,
                "review_text": review.review_text,
                "country": review.country,
                "created_at": review.created_at,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract a JSON object from LLM output.

        Handles several common malformations:
        - `` ```json ... ``` `` fenced blocks
        - `` ``` ... ``` `` untyped fenced blocks
        - Leading/trailing whitespace and stray newlines
        - Text **before** or **after** the JSON object
        - Multiple consecutive code blocks (takes the first one)
        """
        text = text.strip()

        # ── Strategy 1: extract content from markdown code fences ─────────
        # Look for the pattern: ```json\n{...}\n``` or ```\n{...}\n```
        fence_match = re.search(
            r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL
        )
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass  # fall through to next strategy

        # ── Strategy 2: find the outermost { ... } pair ───────────────────
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            candidate = text[brace_start:brace_end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass  # fall through to next strategy

        # ── Strategy 3: try parsing the whole text as-is ──────────────────
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed

        raise ValueError(f"Expected a JSON object, got {type(parsed).__name__}")

    # ── Safe fallback ──────────────────────────────────────────────────────

    def _safe_fallback(self, review: ReviewInput) -> ReviewAnalysis:
        """Return a safe fallback classification when LLM fails.

        Uses simple rating-based heuristics for sentiment and priority,
        and defaults *everything else* to conservative values so that
        the downstream workflow always has a valid result to work with.
        """
        rating = review.rating
        if rating <= 2:
            sentiment = "negative"
            priority = "high"
        elif rating == 3:
            sentiment = "neutral"
            priority = "medium"
        else:
            sentiment = "positive"
            priority = "low"

        return ReviewAnalysis(
            review_id=review.review_id,
            sentiment=sentiment,
            issue_category="other",
            priority=priority,
            responsible_team="unknown",
            summary_zh="（AI 解析失败，已使用安全兜底结果）",
            suggested_action_zh="请人工查看该评论原文并手动完成分类。",
            confidence=0.0,
            needs_human_review=True,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _classify_error(exc: Optional[Exception]) -> str:
    """Map an exception to a short error-type tag for logging."""
    if exc is None:
        return "UNKNOWN"
    if isinstance(exc, json.JSONDecodeError):
        return "JSON_PARSE_FAILED"
    if isinstance(exc, ValueError):
        return "VALIDATION_FAILED"
    if isinstance(exc, requests.Timeout):
        return "API_TIMEOUT"
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else 0
        if 400 <= status < 500:
            return f"API_CLIENT_ERROR_{status}"
        return f"API_SERVER_ERROR_{status}"
    if isinstance(exc, requests.ConnectionError):
        return "API_CONNECTION_ERROR"
    if isinstance(exc, requests.RequestException):
        return "API_REQUEST_FAILED"
    return type(exc).__name__.upper()


def _safe_error_message(exc: Exception) -> str:
    """Return a user-safe error message that never leaks API keys or headers."""
    msg = str(exc)

    # If the exception message looks like it might contain a URL with a key,
    # or request headers, truncate to a generic message.
    if len(msg) > 500:
        msg = msg[:500] + "…"

    # Redact any obvious "Authorization: Bearer sk-…" patterns
    msg = re.sub(r"Bearer\s+[\w\-\.]+", "Bearer ***REDACTED***", msg, flags=re.IGNORECASE)
    # Redact any "key=" or "api_key=" patterns
    msg = re.sub(r"(?:api[_-]?key|apikey|secret|token)=[\w\-\.]+", r"\1=***REDACTED***", msg, flags=re.IGNORECASE)

    return msg


# ── Module-level convenience ──────────────────────────────────────────────────

_default_client: Optional[LLMClient] = None


def get_client(settings: Optional[Settings] = None) -> LLMClient:
    """Return a shared LLMClient instance, creating one if needed."""
    global _default_client
    if settings is not None:
        return LLMClient(settings)
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
