"""LLM client interface for calling DeepSeek API.

Supports:
- Real API calls via OpenAI-compatible Chat Completions endpoint (DEFAULT)
- Mock mode for testing / offline demo (requires explicit --mock or USE_MOCK_LLM=true)
- JSON parse retry with safe fallback
- Pydantic validation retry
- Error-case logging for observability

V2-M2: No silent mock fallback. Real mode is the default. Missing API key
in real mode raises a clear error instead of switching to mock.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import requests
from pydantic import ValidationError

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
        return (
            "You are a cross-border e-commerce review classifier. "
            "Output ONLY valid JSON with: sentiment, issue_category, priority, "
            "responsible_team, summary_zh, suggested_action_zh, confidence, "
            "needs_human_review, evidence. No explanation."
        )

    content = prompt_path.read_text(encoding="utf-8")

    # Find the first fenced code block after "System Prompt"
    match = re.search(r"```\n(.*?)\n```", content, re.DOTALL)
    if match:
        return match.group(1).strip()

    return (
        "You are a cross-border e-commerce review classifier. "
        "Output ONLY valid JSON. No explanation."
    )


SYSTEM_PROMPT = _load_system_prompt()


# ── LLM Client ────────────────────────────────────────────────────────────────

class LLMClient:
    """Client for calling DeepSeek OpenAI-compatible Chat Completions API.

    V2-M2 behaviour:
    - Default: real LLM (USE_MOCK_LLM=false).
    - Mock only when USE_MOCK_LLM=true or --mock flag.
    - Missing API key in real mode → ValueError (no silent fallback).
    """

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
        """Analyze a single review. Mock or real based on config.

        V2-M2: NO silent fallback. If real mode and no API key, raises ValueError.
        """
        if self.mock_mode:
            return self._mock_analyze(review)

        # ── Real mode ──────────────────────────────────────────────────────
        if not self.api_key:
            msg = (
                "DEEPSEEK_API_KEY is not set but USE_MOCK_LLM is false. "
                "Set DEEPSEEK_API_KEY in .env for real LLM mode, "
                "or use USE_MOCK_LLM=true / --mock for explicit mock mode."
            )
            logger.error(msg)
            log_error_case(
                review_id=review.review_id,
                error_type="MISSING_API_KEY",
                error_message=msg,
                fallback_used=True,
                needs_human_review=True,
            )
            raise ValueError(msg)

        return self._call_api_with_retry(review)

    # ── Mock implementation ─────────────────────────────────────────────────

    def _mock_analyze(self, review: ReviewInput) -> ReviewAnalysis:
        """Return a rule-based classification without calling any API.

        Used ONLY when USE_MOCK_LLM=true or --mock flag.

        V2-M2 improvements:
        - Natural Chinese summaries (no more "评分X" templates).
        - "unknown" team → suggested_action_zh uses generic human-review wording.
        - Evidence extracted from review text via keyword matching.
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

        # Compute mock confidence
        confidence = self._compute_mock_confidence(
            text_lower, text_len, issue_category, rating, sentiment
        )

        needs_review = confidence < 0.6

        # ── V2-M2: Natural Chinese summaries (no "评分X") ─────────────────
        summary_zh = self._build_mock_summary(
            rating, issue_category, responsible_team, text_len
        )

        # ── V2-M2: No "建议unknown团队" ────────────────────────────────────
        suggested_action_zh = self._build_mock_action(issue_category, responsible_team)

        # ── Extract evidence from review text ──────────────────────────────
        evidence = self._extract_mock_evidence(text_lower, issue_category)

        return ReviewAnalysis(
            review_id=review.review_id,
            sentiment=sentiment,
            issue_category=issue_category,
            priority=priority,
            responsible_team=responsible_team,
            summary_zh=summary_zh,
            suggested_action_zh=suggested_action_zh,
            confidence=confidence,
            needs_human_review=needs_review,
            evidence=evidence,
            llm_mode="mock",
            is_mock=True,
            model="mock-rule-engine",
        )

    @staticmethod
    def _build_mock_summary(
        rating: int, category: str, team: str, text_len: int
    ) -> str:
        """Build a natural-sounding Chinese summary for mock mode.

        V2-M2: No more "用户反馈XX问题，评分X" templates.
        """
        category_cn: dict[str, str] = {
            "battery": "电池续航或充电",
            "image_quality": "图像/摄像头质量",
            "logistics": "物流配送",
            "customer_service": "客服或售后",
            "price": "价格或性价比",
            "description_mismatch": "产品与描述一致",
            "product_quality": "产品质量",
            "other": "无法明确归类",
        }

        text_hint = "内容简短" if text_len < 30 else "有较详细描述"

        cat_name = category_cn.get(category, "未知")
        if rating <= 2:
            return f"客户对{cat_name}不满意（{text_hint}），给出{rating}星低分。"
        elif rating == 3:
            return f"客户对产品的评价中性，主要关注{cat_name}方面。"
        else:
            return f"客户对产品整体满意，但提到{cat_name}方面有改进空间。"

    @staticmethod
    def _build_mock_action(category: str, team: str) -> str:
        """Build mock suggested_action_zh. V2-M2: no 'unknown' team exposure."""
        if team == "unknown":
            return "建议运营同学人工复核该评论，确认问题类别并协调相应责任团队跟进。"
        team_cn: dict[str, str] = {
            "operations": "运营",
            "product": "产品",
            "supply_chain": "供应链",
            "customer_service": "客服",
            "marketing": "市场",
        }
        team_name = team_cn.get(team, "相关")
        return f"建议{team_name}团队查看该评论详情，评估是否需要跟进处理或联系客户。"

    @staticmethod
    def _compute_mock_confidence(
        text_lower: str,
        text_len: int,
        category: str,
        rating: int,
        sentiment: str,
    ) -> float:
        """Compute a mock confidence score based on review clarity."""
        if text_len < 30:
            return 0.50
        if category == "other":
            return 0.50
        if rating <= 2 and sentiment != "negative":
            return 0.50
        if rating >= 4 and sentiment != "positive":
            return 0.50
        if text_len >= 60:
            return 0.85
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

    @staticmethod
    def _extract_mock_evidence(text_lower: str, category: str) -> list[str]:
        """Extract evidence-like fragments from review text for mock mode."""
        keyword_map: dict[str, list[str]] = {
            "battery": ["battery", "charge", "charging", "drain", "power"],
            "image_quality": ["blurry", "night vision", "camera", "image", "photo", "video", "resolution"],
            "logistics": ["shipping", "delivery", "package", "arrived", "tracking"],
            "customer_service": ["customer service", "support", "refund", "return", "contact"],
            "price": ["price", "expensive", "cheap", "worth", "value", "cost"],
            "description_mismatch": ["description", "match", "wrong", "different", "not as"],
            "product_quality": ["quality", "build", "broke", "defect", "stop", "fail", "issue", "problem"],
        }

        keywords = keyword_map.get(category, [])
        if not keywords:
            return []

        evidence: list[str] = []
        for kw in keywords:
            if kw in text_lower:
                idx = text_lower.find(kw)
                start = max(0, idx - 15)
                end = min(len(text_lower), idx + len(kw) + 45)
                fragment = text_lower[start:end].strip()
                if start > 0:
                    space_idx = fragment.find(" ")
                    if space_idx != -1 and space_idx < 20:
                        fragment = fragment[space_idx:].strip()
                if fragment and fragment not in evidence:
                    evidence.append(fragment)
                if len(evidence) >= 2:
                    break

        return evidence

    # ── Real API call ───────────────────────────────────────────────────────

    def _call_api_with_retry(self, review: ReviewInput) -> ReviewAnalysis:
        """Call the DeepSeek API, retrying on transient failures.

        Retry strategy:
        - JSON parse / Pydantic validation errors → retry (model might fix itself)
        - Network / timeout errors → retry
        - Non-2xx HTTP responses → retry (except 4xx client errors)
        - After all retries exhausted → safe fallback + error log
        """
        last_error: Optional[Exception] = None
        # total attempts = 1 (initial) + max_retries
        max_attempts = 1 + self.max_retries

        for attempt in range(max_attempts):
            try:
                result = self._call_api_once(review)
                if attempt > 0:
                    logger.info(
                        "LLM call succeeded on attempt %d for review %s",
                        attempt + 1, review.review_id,
                    )
                return result

            except ValidationError as exc:
                last_error = exc
                logger.warning(
                    "Pydantic validation failed (attempt %d/%d) for review %s: %s",
                    attempt + 1, max_attempts, review.review_id,
                    _safe_error_message(exc),
                )

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

                # ── V2-M2: model_not_found hint ────────────────────────────
                if status == 404:
                    logger.error(
                        "LLM API 404 for review %s — model '%s' may not exist. "
                        "Check DEEPSEEK_MODEL in .env (current: %s).",
                        review.review_id, self.model, self.model,
                    )

                # Do not retry on 4xx client errors
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

        # ── All retries exhausted — safe fallback ──────────────────────────
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
        """Make a single API call, extract JSON, validate with Pydantic.

        Returns ReviewAnalysis on success.
        Raises ValidationError, JSONDecodeError, ValueError, or requests exceptions.
        """
        start_time = time.time()
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

        # ── Extract JSON from the response ─────────────────────────────────
        parsed = self._extract_json(content)

        # V2-M1/2: Inject code-populated fields
        parsed.setdefault("evidence", [])
        parsed["llm_mode"] = "real"
        parsed["is_mock"] = False
        parsed["model"] = self.model

        # ── Pydantic validation (raises ValidationError on failure) ────────
        result = ReviewAnalysis(**parsed)

        # Set processing time
        elapsed_ms = (time.time() - start_time) * 1000.0
        result.processing_time_ms = round(elapsed_ms, 2)

        return result

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

        Handles:
        - `` ```json ... ``` `` fenced blocks
        - `` ``` ... ``` `` untyped fenced blocks
        - Leading/trailing whitespace and stray newlines
        - Text before or after the JSON object
        - Multiple consecutive code blocks (takes the first one)
        """
        text = text.strip()

        # Strategy 1: extract from markdown code fences
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
                pass

        # Strategy 2: find the outermost { ... } pair
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            candidate = text[brace_start:brace_end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Strategy 3: try parsing the whole text as-is
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed

        raise ValueError(f"Expected a JSON object, got {type(parsed).__name__}")

    # ── Safe fallback ──────────────────────────────────────────────────────

    def _safe_fallback(self, review: ReviewInput) -> ReviewAnalysis:
        """Return a safe fallback classification when LLM fails.

        V2-M2: Updated summary_zh to use the new wording.
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
            summary_zh="模型调用或解析失败，需要人工复核。",
            suggested_action_zh="请人工查看该评论，并根据原始评论内容确认分类结果。",
            confidence=0.0,
            needs_human_review=True,
            evidence=[],
            llm_mode="real",
            is_mock=False,
            model=self.model,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _classify_error(exc: Optional[Exception]) -> str:
    """Map an exception to a short error-type tag for logging."""
    if exc is None:
        return "UNKNOWN"
    if isinstance(exc, json.JSONDecodeError):
        return "JSON_PARSE_FAILED"
    if isinstance(exc, ValidationError):
        return "VALIDATION_FAILED"
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

    if len(msg) > 500:
        msg = msg[:500] + "…"

    # Redact Bearer tokens
    msg = re.sub(r"Bearer\s+[\w\-\.]+", "Bearer ***REDACTED***", msg, flags=re.IGNORECASE)
    # Redact key/secret/token params (capture key name, replace value)
    msg = re.sub(
        r"((?:api[_-]?key|apikey|secret|token))=[\w\-\.]+",
        r"\1=***REDACTED***",
        msg,
        flags=re.IGNORECASE,
    )

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
