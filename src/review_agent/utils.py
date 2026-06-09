"""Utility functions for error logging, directory management, and helpers.

Designed to support production-style observability without introducing
heavy frameworks.  All write operations are best-effort — they must not
cause the main workflow to crash.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Path resolution ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ERROR_LOG_PATH = PROJECT_ROOT / "outputs" / "results" / "error_cases.jsonl"

# Fields that MUST NOT appear in error logs (case-insensitive partial match)
_SENSITIVE_KEY_SUBSTRINGS = (
    "api_key", "apikey", "api-key",
    "secret", "token", "password", "passwd",
    "authorization", "credential", "private",
)


# ── Error-case logging ─────────────────────────────────────────────────────────

def log_error_case(
    review_id: str,
    error_type: str,
    error_message: str,
    raw_output: Optional[str] = None,
    fallback_used: bool = True,
    needs_human_review: bool = True,
) -> None:
    """Write a structured error entry to ``outputs/results/error_cases.jsonl``.

    This function is designed to be called from any layer that detects a
    failure (LLM parse error, schema validation failure, guardrail
    contradiction, network timeout, …).  It is entirely best-effort: if the
    write fails (e.g. disk full, permission error), the exception is caught
    and logged — it is **never** re-raised, so the main workflow continues.

    Args:
        review_id:         The review that triggered the error.
        error_type:        Short tag, e.g. ``JSON_PARSE_FAILED``,
                           ``API_TIMEOUT``, ``GUARDRAIL_TRIGGERED``.
        error_message:     Human-readable description (no API keys).
        raw_output:        Optional raw LLM output that caused the error.
                           Truncated to 1000 chars and sanitised.
        fallback_used:     Whether a safe fallback result was substituted.
        needs_human_review: Whether this case requires human review.
    """
    try:
        # Ensure the output directory tree exists
        ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "review_id": review_id,
            "error_type": error_type,
            "error_message": error_message,
            "fallback_used": fallback_used,
            "needs_human_review": needs_human_review,
        }

        if raw_output:
            # Truncate long outputs and strip any obviously sensitive patterns
            sanitised = _sanitise_output(str(raw_output))
            entry["raw_output"] = sanitised[:1000]

        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info("Error case logged: review=%s type=%s", review_id, error_type)

    except Exception:
        logger.warning(
            "Failed to write error log for review=%s — continuing anyway",
            review_id,
            exc_info=True,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def ensure_output_dir(path: str) -> None:
    """Create the parent directories for *path* if they don't exist."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _sanitise_output(text: str) -> str:
    """Remove obviously sensitive key-value pairs from a JSON-ish string.

    This is a best-effort scrubber — it looks for ``"key": "value"``
    patterns where *key* matches a known sensitive name and replaces the
    value with ``***REDACTED***``.  It is NOT a cryptographic guarantee;
    it simply reduces the blast radius of accidental logging.
    """
    import re

    # Build a regex that matches any of the sensitive key names (case-insensitive)
    pattern_parts = "|".join(re.escape(k) for k in _SENSITIVE_KEY_SUBSTRINGS)
    # Match: "key": "value"  (handles escaped quotes in value simply)
    sensitive_re = re.compile(
        rf'"([^"]*\b(?:{pattern_parts})\b[^"]*)"\s*:\s*"[^"]*"',
        re.IGNORECASE,
    )
    return sensitive_re.sub(r'"\1": "***REDACTED***"', text)
