"""Canonical path resolution shared by the CLI and MCP server."""

from __future__ import annotations

import os

_HERE = os.path.dirname(os.path.abspath(__file__))        # <repo>/Game-1-modular/tools/concern_mcp
SCAN_ROOT = os.path.dirname(os.path.dirname(_HERE))       # <repo>/Game-1-modular  (what we index)
REPO_ROOT = os.path.dirname(SCAN_ROOT)                    # <repo>  (relpath base for openable links)
DEFAULT_DB = os.environ.get("CONCERN_MCP_DB") or os.path.join(_HERE, ".index", "concern.db")
