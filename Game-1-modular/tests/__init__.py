"""
Game-1 Test Suite

This package contains all tests for the Game-1 modular codebase.

Structure:
- tests/          - Root-level game system tests
- tests/crafting/ - Crafting subsystem tests
- tests/save/     - Save system tests

To run tests:
    cd Game-1-modular
    python -m pytest tests/

Or run individual tests:
    python tests/test_class_tags.py
"""

import sys
from pathlib import Path

# Add Game-1-modular to path so tests can import game modules
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
