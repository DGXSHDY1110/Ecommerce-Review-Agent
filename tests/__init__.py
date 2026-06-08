"""Conftest for pytest — shared fixtures and configuration."""

import sys
import os

# Add src to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
