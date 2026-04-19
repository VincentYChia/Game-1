# Faction System

**Status**: Phase 2+ complete. Phase 3 ready to start.
**Date**: 2026-04-18

Parallel recording & retrieval layer for NPC/player affinity. Records affinity
changes from game events, supplies context to NPC dialogue generation, and
publishes `FACTION_AFFINITY_CHANGED` events for WMS consolidation.

---

## Files

```
factions/
├── README.md                      ← you are here (navigation)
├── PHASE_3_PLAN.md                ← what to build next (READ THIS)
├── LLM_INTEGRATION.md             ← prompts, payload schemas (reference)
├── schema.py         (221 lines)  SQLite tables, bootstrap defaults
├── models.py          (99 lines)  Dataclasses (FactionTag, NPCProfile, ...)
├── faction_system.py (455 lines)  FactionSystem singleton — 19 public methods
├── __init__.py        (58 lines)  initialize/save/restore entry points
└── test_faction_phase2plus.py    21 tests, all passing
```

---

## Quick reference

```python
from world_system.living_world.factions import FactionSystem

fs = FactionSystem.get_instance()
fs.initialize()

# Recording
fs.adjust_player_affinity("player_1", "guild:smiths", +10.0)
# → persists to SQLite + publishes FACTION_AFFINITY_CHANGED

# Retrieval (for dialogue context)
npc     = fs.get_npc_profile("smith_1")             # NPCProfile or None
player  = fs.get_all_player_affinities("player_1")  # Dict[tag, -100..100]
opinion = fs.get_npc_affinity_toward_player("smith_1")   # float -100..100
locale  = fs.compute_inherited_affinity([
    ("locality", "village_westhollow"),
    ("district", "district:iron_hills"),
    ("nation",   "nation:stormguard"),
    ("world",    None),
])                                                   # Dict[tag, -100..100]
```

## Event contract

```python
# Published on every real affinity change:
event_type = "FACTION_AFFINITY_CHANGED"
data = {
    "player_id": str,
    "tag":       str,
    "delta":     float,   # actual change after clamping
    "new_value": float,   # -100..100
    "source":    str,     # "set" | "adjust"
}
```

Consumer: `world_system/world_memory/evaluators/faction_reputation.py`
(WMS Layer 2 evaluator — already wired, already listening).

## Tests

```bash
cd Game-1-modular
python -m pytest world_system/living_world/factions/test_faction_phase2plus.py -v
```

Expected: **21 passed**.
