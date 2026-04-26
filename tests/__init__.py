import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
SRC_STR = str(SRC_DIR)
if SRC_STR not in sys.path:
    sys.path.insert(0, SRC_STR)
