#!/usr/bin/env python3
"""World System sidecar — Godot (C#) shells out to this helper to run the WES
content-generation pipeline (planner -> hub -> tool -> supervisor -> commit ->
reload) on the real LLM tiers. It reuses ``tools/world_system_driver`` VERBATIM
(the same real-tier orchestrator, canonical-id coordination, tag governance and
prune that the 2D headless driver uses), so 3D content generation is the same
pipeline that is unit-tested and live-Claude-verified.

Protocol: newline-delimited JSON on stdin -> one JSON reply line on stdout.
  {"op":"ping"}
      -> {"ok":true, "ready":bool, "api_key_present":bool, "error":str?}
  {"op":"run_wes", "directive":"...", "address":"region:...", "layer":4,
       "tier":4, "summary":"..."}
      -> {"ok":true, "status":"committed|abandoned|rolled_back|...",
          "committed":{"materials":[id...], ...},   # the reload signal for Godot
          "files":[path...], "plan_id":str, "verification":bool}
  {"op":"shutdown"} -> {"ok":true}
On any failure: {"ok":false, "error":"..."}.

The bundle is the ONLY input (WES never live-queries), so Godot just sends a
directive + firing address/tier. Committed content lands as ``*-generated-*``
JSON under the game-root; ``committed``/``files`` tell Godot which content to
load into its own C# databases. Requires the 2D game's Python env + a working
ANTHROPIC_API_KEY (or a reachable local Ollama).
"""
import glob
import json
import os
import sys
import traceback

# The imported modules print banners / DB-load logs to stdout. Keep STDOUT pure
# for JSON replies by routing library prints to stderr; reply on the saved handle.
_OUT = sys.stdout
sys.stdout = sys.stderr

_HERE = os.path.dirname(os.path.abspath(__file__))          # <repo>/Game-1-Godot/sidecar
REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))         # <repo>
MODULAR = os.path.join(REPO_ROOT, "Game-1-modular")
if MODULAR not in sys.path:
    sys.path.insert(0, MODULAR)
try:
    os.chdir(MODULAR)  # game databases load content by paths relative to here
except OSError:
    pass

# Force the real LLM tiers before BackendManager is imported (via the driver).
os.environ.setdefault("WES_DISABLE_FIXTURES", "1")
os.environ.setdefault("WES_REQUIRE_REAL_LLM", "1")

_state = {"init": False, "orch": None, "registry": None,
          "error": None, "game_root": None}


def _ensure_init():
    if _state["init"]:
        return _state["error"] is None
    _state["init"] = True
    try:
        from tools.world_system_driver import build_real_orchestrator
        # Generated content lands under game_root. Default to a sidecar-owned dir
        # so real content dirs aren't polluted; Godot points WES_GAME_ROOT at
        # wherever it reads generated content, and WES_SAVE_DIR at the SQLite dir.
        game_root = os.environ.get("WES_GAME_ROOT") or os.path.join(
            MODULAR, "saves", "wes_sidecar")
        save_dir = os.environ.get("WES_SAVE_DIR") or game_root
        os.makedirs(game_root, exist_ok=True)
        os.makedirs(save_dir, exist_ok=True)
        orch, registry, _reg = build_real_orchestrator(save_dir, game_root)
        _state.update(orch=orch, registry=registry, game_root=game_root)
        return True
    except Exception as e:  # noqa: BLE001 — surface any boot failure to the client
        _state["error"] = f"{type(e).__name__}: {e}"
        return False


def _api_key_present():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    for candidate in ("Game-1-modular/.env", ".env"):
        path = os.path.join(os.getcwd(), candidate)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("ANTHROPIC_API_KEY="):
                            return True
            except Exception:
                pass
    return False


def _op_ping(_req):
    ready = _ensure_init()
    return {"ok": True, "ready": ready,
            "api_key_present": _api_key_present(), "error": _state["error"]}


def _op_run_wes(req):
    if not _ensure_init():
        return {"ok": False, "error": _state["error"] or "sidecar init failed"}
    from tools.world_system_driver import make_bundle, run_bundle
    layer = int(req.get("layer", 4))
    bundle = make_bundle(
        address=req.get("address", "region:ashfall_moors"),
        layer=layer,
        directive_text=req.get("directive", ""),
        firing_tier=int(req.get("tier", layer)),
        summary=req.get("summary", ""),
    )
    result = run_bundle(_state["orch"], bundle)
    status = result.get("status")
    committed = {}
    if status == "committed":
        try:
            committed = dict(
                result.get("dispatch", {}).get("staged_content_ids", {}) or {})
        except Exception:
            committed = {}
    files = []
    if status == "committed" and _state["game_root"]:
        files = [os.path.relpath(p, _state["game_root"]) for p in glob.glob(
            os.path.join(_state["game_root"], "**", "*generated*.*"),
            recursive=True) if p.lower().endswith(".json")]
    return {
        "ok": True,
        "status": status,
        "committed": committed,          # {tool: [content_id...]} — reload signal
        "files": files,
        "plan_id": result.get("plan_id"),
        "bundle_id": result.get("bundle_id"),
        "verification": (result.get("verification") or {}).get("passed"),
    }


def _op_shutdown(_req):
    return {"ok": True, "shutdown": True}


_OPS = {"ping": _op_ping, "run_wes": _op_run_wes, "shutdown": _op_shutdown}


def main():
    for line in sys.stdin:
        line = line.strip().lstrip("﻿").strip()  # tolerate a leading BOM
        if not line:
            continue
        stop = False
        try:
            req = json.loads(line)
            op = req.get("op")
            handler = _OPS.get(op)
            reply = handler(req) if handler else {
                "ok": False, "error": f"unknown op: {op}"}
            stop = op == "shutdown"
        except Exception as e:  # noqa: BLE001
            reply = {"ok": False, "error": f"{type(e).__name__}: {e}",
                     "trace": traceback.format_exc()}
        _OUT.write(json.dumps(reply, default=str) + "\n")
        _OUT.flush()
        if stop:
            break


if __name__ == "__main__":
    main()
