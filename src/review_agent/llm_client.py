"""LLM client interface for calling DeepSeek API.

Supports:
- Real API calls via OpenAI-compatible Chat Completions endpoint
- Mock mode for testing without API key
- JSON parse retry with safe fallback
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

import requests

from .config import Settings, get_settings
from .schemas import ReviewInput, ReviewAnalysis

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
        """
        rating = review.rating
        text_lower = review.review_text.lower()

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

        return ReviewAnalysis(
            review_id=review.review_id,
            sentiment=sentiment,
            issue_category=issue_category,
            priority=priority,
            responsible_team=responsible_team,
            summary_zh=f"Mock分析：用户评分{rating}，检测到关键词匹配类别{issue_category}。",
            suggested_action_zh=f"Mock建议：请人工复核{issue_category}相关评论。",
            confidence=0.5,
            needs_human_review=True,
        )

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
        """Call the DeepSeek API, retrying on JSON parse failure."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return self._call_api_once(review)
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "LLM JSON parse failed (attempt %d/%d): %s",
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                )
            except requests.RequestException as exc:
                last_error = exc
                logger.error("LLM API request failed (attempt %d/%d): %s",
                             attempt + 1, self.max_retries + 1, exc)

        # All retries exhausted — return safe fallback
        logger.error("All LLM attempts failed, returning safe fallback for %s", review.review_id)
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
        """Extract a JSON object from LLM output (may contain markdown fences)."""
        text = text.strip()

        # Remove ```json / ``` fences if present
        if text.startswith("```"):
            # Remove opening fence line
            text = re.sub(r"^```\w*\s*\n?", "", text)
            # Remove closing fence
            text = re.sub(r"\n?```\s*$", "", text)

        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected a JSON object, got {type(parsed).__name__}")
        return parsed

    # ── Safe fallback ──────────────────────────────────────────────────────

    def _safe_fallback(self, review: ReviewInput) -> ReviewAnalysis:
        """Return a safe fallback classification when LLM fails."""
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
            summary_zh="模型输出解析失败，需要人工复核。",
            suggested_action_zh="请人工查看该评论并确认分类结果。",
            confidence=0.0,
            needs_human_review=True,
        )


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
