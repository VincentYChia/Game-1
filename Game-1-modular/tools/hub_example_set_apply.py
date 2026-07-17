"""Apply a hub-example content set to the 8 hub prompt files.

The example teaches the XML SHAPE; its CONTENT leaks into small-model
output (2026-07-11 hub certification: gemma3:4b copied the moors
examples' names in 3/8 hubs). Sets live in
world_system/config/hub_example_sets.json — every set keeps identical
shape and per-tool constraint keys; only the illustrative content
differs.

Usage:
    python tools/hub_example_set_apply.py --list
    python tools/hub_example_set_apply.py --current
    python tools/hub_example_set_apply.py --set frostpeak
    python tools/hub_example_set_apply.py --set schematic
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

SETS_PATH = os.path.join(_ROOT, "world_system", "config",
                         "hub_example_sets.json")
HUB_PATH = os.path.join(_ROOT, "world_system", "config",
                        "prompt_fragments_hub_{tool}.json")
TOOLS = ["materials", "hostiles", "nodes", "skills", "titles",
         "chunks", "npcs", "quests"]


def load_sets() -> dict:
    with open(SETS_PATH, encoding="utf-8") as f:
        return json.load(f)


def detect_current(sets: dict) -> str:
    """Best-effort: which set do the live hub files match?"""
    with open(HUB_PATH.format(tool="materials"), encoding="utf-8") as f:
        live = json.load(f)["_output"]["example"]
    for name, examples in sets.items():
        if name.startswith("_"):
            continue
        if examples.get("materials", "").strip() == live.strip():
            return name
    return "(custom / original moors)"


def apply_set(name: str) -> None:
    sets = load_sets()
    if name not in sets or name.startswith("_"):
        raise SystemExit(f"unknown set {name!r} — try --list")
    examples = sets[name]
    # Round-trip check BEFORE touching any file: every example must parse.
    from world_system.wes.xml_batch_parser import parse_xml_batch
    for tool in TOOLS:
        specs = parse_xml_batch(examples[tool], default_plan_step_id="sX")
        assert specs, f"set {name}: {tool} example does not parse"
    for tool in TOOLS:
        path = HUB_PATH.format(tool=tool)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        d["_output"]["example"] = examples[tool]
        d["_output"]["_active_set"] = name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
        print(f"applied {name} -> hub_{tool}")
    print(f"\nActive example set: {name}. Re-certify with:\n"
          f"  python tools/hub_cert_harness.py --model gemma3:4b")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--current", action="store_true")
    ap.add_argument("--set", dest="set_name")
    args = ap.parse_args()
    sets = load_sets()
    if args.list:
        for name, desc in sets["_meta"]["sets"].items():
            print(f"  {name}: {desc}")
        return
    if args.current:
        print("active set:", detect_current(sets))
        return
    if args.set_name:
        apply_set(args.set_name)
        return
    ap.print_help()


if __name__ == "__main__":
    main()
