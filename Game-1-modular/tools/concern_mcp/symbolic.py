"""Phase 5 -- symbolic call-spine composition hook (graceful degradation).

The concern registry covers the STRING web + the output_contract field layer. The pure
SYMBOLIC call spine (who calls TagParser.parse, references to EffectConfig the type) is the
one class an off-the-shelf LSP MCP does best. This module composes such a provider if one is
configured, and degrades to a useful pointer set otherwise -- so a structural/parser refactor
is never silently under-served.

Wire a provider by setting CONCERN_SYMBOLIC_CMD to a command that receives the concept as its
last argv and prints JSON: [{"file": "...", "line": N, "role": "..."}]. Any LSP-backed tool
(Serena, jedi, pyright + a shim) can satisfy this.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any, Dict

# Curated find-references anchors for the tag pipeline (what to run find-refs on for a
# structural refactor). These are the symbolic couplings the string index deliberately skips.
SYMBOL_ANCHORS = {
    "TagParser.parse": "Game-1-modular/core/tag_parser.py -- all call-sites of parse()",
    "get_tag_parser": "Game-1-modular/core/tag_parser.py -- singleton accessor",
    "get_tag_registry": "Game-1-modular/core/tag_system.py -- registry accessor",
    "EffectConfig": "Game-1-modular/core/effect_context.py -- type references (see output_contract group)",
    "EffectContext": "Game-1-modular/core/effect_context.py -- wraps EffectConfig, passed through the executor",
}

_NOTE = ("Symbolic call-graph provider not configured (CONCERN_SYMBOLIC_CMD unset). For a "
         "STRUCTURAL/parser refactor, drive it with an LSP MCP (e.g. Serena) or your editor's "
         "find-references on the anchors below; the concern registry complements that with the "
         "string web + the output_contract field layer a call-graph under-weights.")


def symbolic_refs(concept: str, repo_root: str) -> Dict[str, Any]:
    cmd = os.environ.get("CONCERN_SYMBOLIC_CMD")
    if not cmd:
        return {"available": False, "note": _NOTE, "anchors": SYMBOL_ANCHORS}
    try:
        out = subprocess.run(shlex.split(cmd) + [concept], cwd=repo_root,
                             capture_output=True, text=True, timeout=20)
        if out.returncode != 0:
            return {"available": False, "error": out.stderr.strip()[:200],
                    "note": _NOTE, "anchors": SYMBOL_ANCHORS}
        refs = json.loads(out.stdout or "[]")
        return {"available": True, "provider": cmd, "refs": refs}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": f"{type(e).__name__}: {e}",
                "note": _NOTE, "anchors": SYMBOL_ANCHORS}
