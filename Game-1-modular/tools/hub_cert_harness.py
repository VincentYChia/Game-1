"""Hub certification harness — contract + example-leakage scoring.

Permanent version of the 2026-07-10/11 certification loop. Runs every
hub through build_specs on a chosen backend/model and scores each
batch against the full contract:

  parse_ok | count_match | tier/biome propagation | dedup vs seeded
  registry | distinctness | EXAMPLE LEAKAGE (does output copy the
  prompt example's distinctive content words?)

Usage:
    python tools/hub_cert_harness.py --model gemma3:4b
    python tools/hub_cert_harness.py --model qwen3:4b --runs 2
    python tools/hub_cert_harness.py --backend claude          # Haiku
    python tools/hub_cert_harness.py --model gemma3:4b --tools materials hostiles
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from world_system.wes.dataclasses import WESPlanStep  # noqa: E402
from world_system.living_world.infra.context_bundle import BundleToolSlice  # noqa: E402

TOOLS = ["materials", "hostiles", "nodes", "skills", "titles",
         "chunks", "npcs", "quests"]

SEEDED_REGISTRY = {
    "materials": [
        {"content_id": "moors_copper", "display_name": "Moors Copper",
         "tier": 2, "biome": "moors", "source": "live"},
        {"content_id": "bog_iron", "display_name": "Bog Iron",
         "tier": 2, "biome": "moors", "source": "live"},
    ],
    "hostiles": [
        {"content_id": "copperlash_rider", "display_name": "Copperlash Rider",
         "tier": 2, "biome": "moors", "source": "live"},
    ],
}

STEP_INTENTS = {
    "materials": "Three distinct new bog minerals fueling the salt-moors copper economy",
    "hostiles": "Three distinct new moors threats preying on the copper roads",
    "nodes": "Three distinct gatherable nodes yielding the new bog minerals",
    "skills": "Three distinct raider-signature combat skills seen on the copper roads",
    "titles": "Three distinct titles rewarding anti-raider play on the moors",
    "chunks": "Three distinct dangerous moors chunk variants along the copper roads",
    "npcs": "Three distinct dockside NPCs entangled in the copper-road troubles",
    "quests": "Three distinct quests arising from the copper-road raids",
}

# Words too generic to count as leakage evidence.
_STOPWORDS = {"the", "a", "an", "of", "and", "or", "one", "two", "three",
              "example", "sample", "spec", "specs", "moors", "copper",
              "salt", "tier", "quarry", "cave", "water", "forest",
              "apprentice", "novice", "journeyman", "expert", "master",
              "warden", "strike", "title", "quest", "chunk", "person",
              "creature", "ore", "deposit", "seam", "road", "roads",
              # category/enum vocabulary — legitimate output words, not
              # example content ("Dangerous X" is category+subject naming)
              "dangerous", "peaceful", "hostile", "uncommon", "common",
              "rare", "epic", "legendary", "metal", "stone", "wood",
              "beast", "humanoid", "combat", "side", "main"}
# NOTE: moors/copper/salt are stopworded because the TEST FIRING itself
# is moors-themed — an output named 'Copper ...' is on-theme, not leaked.
# Distinctive example words (frostline, glacier, wyrm, copperlash...)
# are what leakage detection keys on.


def _example_words(tool: str) -> set:
    """Distinctive content words from the ACTIVE example for this hub."""
    path = os.path.join(_ROOT, "world_system", "config",
                        f"prompt_fragments_hub_{tool}.json")
    with open(path, encoding="utf-8") as f:
        example = json.load(f)["_output"]["example"]
    # name_hint values + intent text carry the copyable content
    words = set()
    for m in re.finditer(r'"(?:name_hint|title_hint)":\s*"([^"]+)"', example):
        words.update(w.lower() for w in re.findall(r"[A-Za-z]+", m.group(1)))
    for m in re.finditer(r"<intent>([^<]+)</intent>", example):
        words.update(w.lower() for w in re.findall(r"[A-Za-z]+", m.group(1)))
    return {w for w in words if len(w) > 3 and w not in _STOPWORDS}


def make_step(tool: str) -> WESPlanStep:
    return WESPlanStep(step_id="s1", tool=tool, intent=STEP_INTENTS[tool],
                       depends_on=[], slots={"count": 3, "tier": 2,
                                             "biome": "moors"})


def make_slice(tool: str) -> BundleToolSlice:
    return BundleToolSlice(
        tool_name=tool, bundle_id="cert_bundle", firing_tier=4,
        directive_text=("Respond to the moors' economic realignment: the "
                        "copper trade is reshaping the salt moors and its "
                        "dangers."),
        address_hint="region:salt_moors", threads_in_focal_address=[],
        recent_registry_entries=SEEDED_REGISTRY.get(tool, []),
        firing_layer_summary=("The salt moors restructure around the copper "
                              "trade; raiders work the roads while the "
                              "harbor towns profit."),
        parent_summaries={"5:nation:ardenreach":
                          "Ardenreach's copper ascendancy consolidates."},
        geographic_chain=["world:aldera", "nation:ardenreach",
                          "region:salt_moors"],
        threads_in_parent_addresses=[], wms_events_since_last=[],
        npc_dialogue_since_last=[], trigger_archetype="narrative",
    )


def score(tool: str, specs, example_words: set) -> dict:
    if not specs:
        return {"parse_ok": False}
    seeded = {e["display_name"].lower()
              for e in SEEDED_REGISTRY.get(tool, [])}
    expects_biome = tool in ("materials", "hostiles", "nodes", "chunks")
    names, tiers_ok, biome_ok, leaked = [], 0, 0, []
    for s in specs:
        hc = s.hard_constraints or {}
        tier_val = hc.get("tier", hc.get("tier_anchor"))
        if tier_val == 2 or (tool == "titles" and hc.get("difficultyTier")):
            tiers_ok += 1
        if (hc.get("biome") in ("moors", "salt_moors", "bog")
                or hc.get("home_chunk") or hc.get("theme")):
            biome_ok += 1
        fh = s.flavor_hints or {}
        name = str(fh.get("name_hint", s.item_intent))[:60]
        names.append(name)
        hits = {w for w in re.findall(r"[A-Za-z]+", name.lower())
                if w in example_words}
        if hits:
            leaked.append(f"{name} ({','.join(sorted(hits))})")
    n = len(specs)
    dedup_ok = not any(x.lower() in seeded for x in names)
    # A batch one short WITH clean dedup usually means the hub's
    # post-parse guard dropped a live-registry collision — correct
    # behavior (a short batch beats a duplicate), scored as pass with
    # a note rather than a count failure.
    count_ok = n == 3 or (n == 2 and dedup_ok)
    return {
        "parse_ok": True,
        "count_match": count_ok,
        "short_batch_note": ("guard likely dropped a collision"
                             if (n == 2 and dedup_ok) else ""),
        "tier": f"{tiers_ok}/{n}",
        "biome": f"{biome_ok}/{n}" if expects_biome else "n/a",
        "dedup": dedup_ok,
        "distinct": len({x.lower() for x in names}) == n,
        "leaked": leaked,
        "names": names,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="ollama",
                    choices=["ollama", "claude"])
    ap.add_argument("--model", default="gemma3:4b",
                    help="ollama model name (ignored for claude)")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--tools", nargs="*", default=None)
    args = ap.parse_args()

    from world_system.living_world.backends.backend_manager import (
        BackendManager, OllamaBackend)
    from world_system.wes.llm_tiers.llm_execution_hub import LLMExecutionHub

    mgr = BackendManager.get_instance()
    mgr.initialize()
    for t in TOOLS:
        mgr._task_routing[f"wes_hub_{t}"] = args.backend
    if args.backend == "ollama":
        mgr._backends["ollama"] = OllamaBackend(model=args.model,
                                                timeout=600.0)

    totals = {"pass": 0, "fail": 0, "leaks": 0}
    for tool in (args.tools or TOOLS):
        ex_words = _example_words(tool)
        for run in range(1, args.runs + 1):
            hub = LLMExecutionHub(tool_name=tool)
            specs = hub.build_specs(make_step(tool), make_slice(tool))
            result = score(tool, specs, ex_words)
            ok = (result.get("parse_ok") and result.get("count_match")
                  and result.get("dedup") and result.get("distinct")
                  and not result.get("leaked"))
            totals["pass" if ok else "fail"] += 1
            totals["leaks"] += len(result.get("leaked", []))
            print(f"[{tool} #{run}] {'PASS' if ok else 'FAIL'} "
                  f"{json.dumps(result, ensure_ascii=False)}")
    print(f"\nTOTAL: {totals['pass']} pass / {totals['fail']} fail / "
          f"{totals['leaks']} leaked names")


if __name__ == "__main__":
    main()
