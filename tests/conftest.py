"""Pytest conftest — ensures mock mode for all tests.

V2-M1: Sets USE_MOCK_LLM=true and LLM_MOCK_MODE=true at pytest configure time,
BEFORE any test modules import config.py. This prevents accidental real
DeepSeek API calls during test runs.

The values are set using direct os.environ assignment (not setdefault) so they
take precedence over anything in .env, which will be loaded later by config.py
via load_dotenv(override=False).
"""

import os


def pytest_configure(config) -> None:
    """Set mock mode env vars before any test module is imported."""
    os.environ["USE_MOCK_LLM"] = "true"
    os.environ["LLM_MOCK_MODE"] = "true"
