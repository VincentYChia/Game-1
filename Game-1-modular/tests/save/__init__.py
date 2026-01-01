"""Save system tests"""

import sys
from pathlib import Path

# Add Game-1-modular to path
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
