#!/usr/bin/env python3
"""World System real-tier driver (Phase 1 of WORLD_SYSTEM_COMPLETION_PLAN).

Runs a WESContextBundle through the **real** LLM tiers end to end —
planner -> hub -> tool -> supervisor -> ContentRegistry.commit -> DB reload —
headless, with no game loop. This is:

  1. the verification substrate for every World-System fix (assert on real,
     committed content instead of fixtures), and
  2. the seed of the Godot World-System sidecar (Phase 4): the same
     build_real_orchestrator() + run_bundle() functions get wrapped in an
     NDJSON stdin/stdout loop later.

Forces real LLMs (no fixtures, no mock) via WES_DISABLE_FIXTURES=1 +
WES_REQUIRE_REAL_LLM=1 unless --allow-fixtures is passed. Defaults to a throwaway
temp dir so it never pollutes the sacred content directories; pass
--game-root <dir> to actually land generated JSON somewhere real.

Usage:
  python tools/world_system_driver.py                    # moors copper demo, real Claude
  python tools/world_system_driver.py --json             # machine-readable result
  python tools/world_system_driver.py --allow-fixtures   # offline stub/fixture path
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile
import time
import uuid

# Windows consoles default to cp1252; the game databases print unicode (⚠)
# during load and crash-on-print when stdout is piped, which would leave the
# sacred-content index empty. Match main.py's stdio reconfigure.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_THIS = os.path.dirname(os.path.abspath(__file__))
_MODULAR = os.path.dirname(_THIS)
if _MODULAR not in sys.path:
    sys.path.insert(0, _MODULAR)


def set_real_llm_gates(allow_fixtures: bool) -> None:
    """Set the backend gates BEFORE BackendManager is imported/used.

    The gates are read per-call, but setting them up front keeps the whole
    process honest. --allow-fixtures leaves them unset (offline path).
    """
    if not allow_fixtures:
        os.environ["WES_DISABLE_FIXTURES"] = "1"
        os.environ["WES_REQUIRE_REAL_LLM"] = "1"


def build_real_orchestrator(save_dir: str, game_root: str):
    """Wire the REAL LLM tiers into a fresh WESOrchestrator.

    This is the exact wiring the game orchestrator is missing today
    (game_engine.py:5178 passes no tiers -> stubs). Mirrors the proven
    pattern in test_e2e_pipeline.py::TestLLMTierPipeline.
    """
    from world_system.living_world.backends.backend_manager import BackendManager
    from world_system.content_registry.content_registry import ContentRegistry
    from world_system.wes.tool_registry import WESToolRegistry
    from world_system.wes.wes_orchestrator import WESOrchestrator

    ContentRegistry.reset()
    registry = ContentRegistry.get_instance()
    registry.initialize(save_dir=save_dir, game_root=game_root)

    BackendManager.reset()
    BackendManager.get_instance().initialize()

    WESToolRegistry.reset()
    reg = WESToolRegistry.get_instance(use_stubs=False)
    reg.initialize()

    WESOrchestrator.reset()
    orch = WESOrchestrator.get_instance()
    orch.initialize(
        planner=reg.get_planner(),
        hubs={n: reg.get_hub(n) for n in reg.tool_names()},
        tools={n: reg.get_tool(n) for n in reg.tool_names()},
        supervisor=reg.get_supervisor(),
        registry=registry,
        subscribe_to_bus=False,
    )
    return orch, registry, reg


def make_bundle(address: str, layer: int, directive_text: str,
                firing_tier: int, summary: str):
    from world_system.living_world.infra.context_bundle import (
        NarrativeContextSlice,
        NarrativeDelta,
        WESContextBundle,
        WNSDirective,
    )
    return WESContextBundle(
        bundle_id=f"driver_{uuid.uuid4().hex[:8]}",
        created_at=time.time(),
        delta=NarrativeDelta(
            address=address, layer=layer, start_time=0.0, end_time=100.0,
        ),
        narrative_context=NarrativeContextSlice(firing_layer_summary=summary),
        directive=WNSDirective(directive_text=directive_text,
                               firing_tier=firing_tier),
    )


def run_bundle(orch, bundle) -> dict:
    """Run one bundle through the orchestrator and return the status dict."""
    return orch.run_plan(bundle)


def _collect_generated(game_root: str) -> list:
    """Find every *-generated-* JSON the commit wrote under game_root."""
    out = []
    for path in glob.glob(os.path.join(game_root, "**", "*generated*.*"),
                          recursive=True):
        if path.lower().endswith((".json",)):
            try:
                with open(path, encoding="utf-8") as f:
                    out.append((os.path.relpath(path, game_root), f.read()))
            except Exception as e:  # pragma: no cover
                out.append((path, f"<unreadable: {e}>"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="World System real-tier driver")
    ap.add_argument("--address", default="region:ashfall_moors")
    ap.add_argument("--layer", type=int, default=4)
    ap.add_argument("--tier", type=int, default=4)
    ap.add_argument("--summary",
                    default="The moors restructure around copper.")
    ap.add_argument("--directive", default=(
        "Generate content responding to the moors' economic realignment: "
        "a new material and a new hostile raiding the copper trade."))
    ap.add_argument("--game-root", default=None,
                    help="Where generated JSON lands (default: throwaway temp).")
    ap.add_argument("--allow-fixtures", action="store_true",
                    help="Do NOT force real LLMs (offline stub/fixture path).")
    ap.add_argument("--json", action="store_true",
                    help="Emit the raw result dict as JSON only.")
    args = ap.parse_args()

    set_real_llm_gates(args.allow_fixtures)

    tmp = None
    if args.game_root:
        game_root = save_dir = args.game_root
    else:
        tmp = tempfile.mkdtemp(prefix="wes_driver_")
        game_root = save_dir = tmp

    t0 = time.time()
    orch, registry, reg = build_real_orchestrator(save_dir, game_root)

    if not args.json:
        print("=" * 66)
        print("WORLD SYSTEM DRIVER — real tiers:",
              "OFF (fixtures)" if args.allow_fixtures else "ON (Claude/local)")
        print(f"  planner : {type(orch._planner).__name__}")
        print(f"  supervis: {type(orch._supervisor).__name__}")
        print(f"  tools   : {len(orch._tools)}  hubs: {len(orch._hubs)}")
        print(f"  game_root: {game_root}")
        print("=" * 66)

    bundle = make_bundle(args.address, args.layer, args.directive,
                         args.tier, args.summary)
    result = run_bundle(orch, bundle)
    elapsed = time.time() - t0

    if args.json:
        print(json.dumps({"result": result, "elapsed_s": elapsed},
                         default=str, indent=2))
        return 0 if result.get("status") == "committed" else 1

    print(f"\nSTATUS: {result.get('status')}   ({elapsed:.1f}s)")
    print("-" * 66)
    # Surface the interesting bits of the status dict without dumping everything.
    for k in ("plan_id", "bundle_id", "verification", "dispatch",
              "supervisor_verdict", "reason", "error"):
        if k in result:
            v = result[k]
            s = json.dumps(v, default=str)
            print(f"  {k}: {s[:400]}{'...' if len(s) > 400 else ''}")

    generated = _collect_generated(game_root)
    print("-" * 66)
    print(f"GENERATED FILES: {len(generated)}")
    for rel, content in generated:
        print(f"\n--- {rel} ---")
        print(content[:1600] + ("..." if len(content) > 1600 else ""))

    if tmp:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    return 0 if result.get("status") == "committed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
