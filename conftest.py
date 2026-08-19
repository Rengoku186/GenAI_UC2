"""Pytest root configuration: sets up python path and test environment."""

import sys
from pathlib import Path

# Ensure workspace root is always at the top of sys.path for test runs
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
