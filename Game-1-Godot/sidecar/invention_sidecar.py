#!/usr/bin/env python3
"""
Crafting INVENTION sidecar — the Godot (C#) game shells out to this helper for the
one part of crafting it cannot do in-process: run the trained CNN / LightGBM placement
classifiers and the Claude item generator. It imports the 2D game's
`systems.crafting_classifier` and `systems.llm_item_generator` VERBATIM (same models,
same feature encoders, same few-shot prompts) so discovery in 3D is bit-for-bit the 2D
invention pipeline.

Protocol: newline-delimited JSON on stdin → one JSON reply line on stdout.
  {"op":"ping"}                         -> {"ok":true, "ready":bool, "backend":"anthropic|mock", "error":str?}
  {"op":"validate","signature":{...}}   -> {"ok":true, "valid":bool, "confidence":float, "probability":float}
  {"op":"invent","signature":{...},
       "narrative":"..."}               -> {"ok":true, "valid":bool, "item":{...}?, "itemId":str,
                                            "itemName":str, "recipeInputs":[...], "stationTier":int,
                                            "fromCache":bool}
On any failure: {"ok":false, "error":"..."}.

`signature` is exactly what a Godot PlacementBoard.Signature() emits — a discipline-tagged
snapshot mirroring placements.JSON (grid / core+surrounding / ingredients / slots /
shapes+vertices). We rebuild a tiny shim object exposing the attributes the 2D
classifier + generator read off an InteractiveXUI, then call the real code.

Nothing here is imported by the game at build time; it is a standalone process. Requires
the 2D game's Python env (numpy + tensorflow + lightgbm for the classifiers; anthropic +
ANTHROPIC_API_KEY for real LLM generation — without a key the generator falls back to a
placeholder item, reported as backend="mock").
"""
import os
import sys
import json
import traceback

# The imported 2D modules print banners / load logs to stdout (pygame, PathManager,
# CraftingClassifierManager, material loads). Keep STDOUT pure for JSON replies by
# routing every library print to stderr; we write replies to the saved handle.
_OUT = sys.stdout
sys.stdout = sys.stderr

# --- locate the repo + the 2D game package -------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))              # <repo>/Game-1-Godot/sidecar
REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))             # <repo>
MODULAR = os.path.join(REPO_ROOT, "Game-1-modular")
if MODULAR not in sys.path:
    sys.path.insert(0, MODULAR)
# The 2D MaterialDatabase loads item JSONs by paths relative to the modular root.
try:
    os.chdir(MODULAR)
except OSError:
    pass

# Grid dimension per station tier (smithing NxN).
_SMITH_N = {1: 3, 2: 5, 3: 7, 4: 9}
_ALCHEMY_SLOTS = {1: 2, 2: 3, 3: 4, 4: 6}
_ADORN_GRID = {1: 8, 2: 10, 3: 12, 4: 14}

# Lazily-initialised singletons (heavy imports deferred to first real request).
_state = {"init": False, "mgr": None, "gen": None, "backend": "unknown", "error": None}


class _PM:
    """A stand-in for the 2D PlacedMaterial (only .item_id / .quantity are read)."""
    __slots__ = ("item_id", "quantity", "crafted_stats", "rarity")

    def __init__(self, item_id, quantity=1):
        self.item_id = item_id
        self.quantity = int(quantity)
        self.crafted_stats = None
        self.rarity = "common"


class _UI:
    """A stand-in for an InteractiveXUI carrying just the attributes the classifier +
    generator read. Populated per discipline from a board Signature()."""


def _ensure_init():
    if _state["init"]:
        return _state["error"] is None
    _state["init"] = True
    try:
        from pathlib import Path
        from data.databases.material_db import MaterialDatabase
        from systems.crafting_classifier import init_classifier_manager
        from systems.llm_item_generator import LLMItemGenerator

        mat_db = MaterialDatabase.get_instance()
        _state["mgr"] = init_classifier_manager(Path(REPO_ROOT), mat_db)
        _state["gen"] = LLMItemGenerator(Path(REPO_ROOT), mat_db)
        # Report which LLM backend resolved (anthropic vs mock placeholder).
        try:
            be = _state["gen"].backend
            _state["backend"] = type(be).__name__.replace("Backend", "").lower()
        except Exception:
            _state["backend"] = "mock"
        return True
    except Exception as e:  # noqa: BLE001 — surface any boot failure to the client
        _state["error"] = f"{type(e).__name__}: {e}"
        return False


def _build_ui(sig):
    """Rebuild an interactive-UI shim from a Godot board Signature()."""
    disc = sig.get("discipline", "")
    tier = int(sig.get("stationTier", 1))
    ui = _UI()
    ui.station_tier = tier
    ui.station_type = disc

    if disc == "smithing":
        ui.grid_size = _SMITH_N.get(tier, 3)
        ui.grid = {}
        for key, mat in (sig.get("grid") or {}).items():
            r, c = (int(p) for p in key.split(","))
            ui.grid[(c - 1, r - 1)] = _PM(mat)          # (x=col, y=row), 0-indexed

    elif disc == "refining":
        ui.core_slots = [_PM(o["materialId"], o.get("quantity", 1)) for o in sig.get("coreInputs", [])]
        ui.surrounding_slots = [_PM(o["materialId"], o.get("quantity", 1)) for o in sig.get("surroundingInputs", [])]

    elif disc == "alchemy":
        n = _ALCHEMY_SLOTS.get(tier, 2)
        ui.slots = [None] * n
        for o in sig.get("ingredients", []):
            idx = int(o.get("slot", 1)) - 1
            if 0 <= idx < n:
                ui.slots[idx] = _PM(o["materialId"], o.get("quantity", 1))

    elif disc == "engineering":
        lanes = {}
        for o in sig.get("slots", []):
            lanes.setdefault(o.get("type", ""), []).append(_PM(o["materialId"], o.get("quantity", 1)))
        ui.slots = lanes

    elif disc == "adornments":
        ui.grid_size = _ADORN_GRID.get(tier, 8)
        ui.coordinate_range = 7
        ui.vertices = {k: _PM(v.get("materialId") or v.get("itemId"))
                       for k, v in (sig.get("vertices") or {}).items()
                       if (v.get("materialId") or v.get("itemId"))}
        ui.shapes = [{"type": s.get("type", ""),
                      "vertices": list(s.get("vertices", [])),
                      "rotation": int(s.get("rotation", 0))}
                     for s in sig.get("shapes", [])]
    else:
        raise ValueError(f"unknown discipline: {disc}")

    return disc, tier, ui


def _op_ping(_req):
    ready = _ensure_init()
    return {"ok": True, "ready": ready, "backend": _state["backend"], "error": _state["error"]}


def _op_validate(req):
    if not _ensure_init():
        return {"ok": False, "error": _state["error"] or "sidecar init failed"}
    disc, _tier, ui = _build_ui(req["signature"])
    res = _state["mgr"].validate(disc, ui)
    if res.error:
        return {"ok": False, "error": res.error}
    return {"ok": True, "valid": bool(res.valid),
            "confidence": float(res.confidence), "probability": float(res.probability)}


def _op_invent(req):
    if not _ensure_init():
        return {"ok": False, "error": _state["error"] or "sidecar init failed"}
    disc, tier, ui = _build_ui(req["signature"])

    res = _state["mgr"].validate(disc, ui)
    if res.error:
        return {"ok": False, "error": res.error}
    if not res.valid:
        return {"ok": True, "valid": False, "probability": float(res.probability)}

    gen = _state["gen"].generate(disc, ui, narrative=req.get("narrative", ""))
    if not gen.success:
        return {"ok": False, "error": gen.error or "generation failed"}
    return {
        "ok": True,
        "valid": True,
        "backend": _state["backend"],
        "fromCache": bool(getattr(gen, "from_cache", False)),
        "item": gen.item_data,
        "itemId": gen.item_id,
        "itemName": gen.item_name,
        "recipeInputs": gen.recipe_inputs or [],
        "stationTier": int(getattr(gen, "station_tier", tier)),
    }


_OPS = {"ping": _op_ping, "validate": _op_validate, "invent": _op_invent}


def main():
    # Unbuffered line protocol.
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            handler = _OPS.get(req.get("op"))
            reply = handler(req) if handler else {"ok": False, "error": f"unknown op: {req.get('op')}"}
        except Exception as e:  # noqa: BLE001
            reply = {"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()}
        _OUT.write(json.dumps(reply) + "\n")
        _OUT.flush()


if __name__ == "__main__":
    main()
