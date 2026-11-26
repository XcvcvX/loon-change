"""Repository test suite with access to the project tooling modules."""

import sys
from pathlib import Path

TOOLS_DIR = str(Path(__file__).resolve().parents[1] / "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
