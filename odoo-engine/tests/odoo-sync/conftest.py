import sys
from pathlib import Path

# Add the project's src directory to sys.path for imports
ROOT = Path(__file__).resolve().parents[2]  # Points to odoo-engine/
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
