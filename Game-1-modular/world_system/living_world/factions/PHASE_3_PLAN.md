# Faction System — Phase 3 Implementation Plan

**Status**: Phase 2+ complete. Phase 3 ready to build.  
**Date**: 2026-04-19  
**Target**: NPC Dialogue Integration, Quest Tool, Affinity Consolidator

---

## Current State (Phase 2+ Complete)

### SQLite Schema (Sparse Storage)
- `npc_profiles`: NPC narrative, timestamps
- `npc_belonging_tags`: NPC → tag + significance + role + narrative_hooks
- `npc_affinity`: NPC → tag → affinity_value (-100..100); reserved tag `_player` for NPC opinion of player
- `player_affinity`: Player → tag → affinity_value (-100..100)
- `location_affinity_defaults`: Tier + location_id → tag → affinity_value
- `faction_schema_version`: Version tracking

### FactionSystem API (19 Public Methods)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `get_instance()` | `→ FactionSystem` | Singleton access |
| `initialize()` | `→ None` | Create DB, bootstrap defaults |
| `add_npc()` | `(npc_id, narrative, game_time=0) → None` | Add NPC |
| `get_npc_profile()` | `(npc_id) → NPCProfile \| None` | Full NPC data + tags + affinity |
| `add_npc_belonging_tag()` | `(npc_id, tag, significance, role, hooks, game_time) → None` | Tag NPC |
| `get_npc_belonging_tags()` | `(npc_id) → List[FactionTag]` | All tags for NPC |
| `get_all_npcs_with_tag()` | `(tag) → List[str]` | NPC IDs having tag |
| `set_player_affinity()` | `(player_id, tag, value, game_time) → float` | Set & clamp; publish event |
| `adjust_player_affinity()` | `(player_id, tag, delta, game_time) → float` | Adjust & clamp; publish event |
| `get_player_affinity()` | `(player_id, tag) → float` | Single affinity |
| `get_all_player_affinities()` | `(player_id) → Dict[tag, float]` | All tags for player |
| `set_npc_affinity()` | `(npc_id, tag, value, game_time) → float` | Set NPC → tag affinity |
| `adjust_npc_affinity()` | `(npc_id, tag, delta, game_time) → float` | Adjust NPC → tag affinity |
| `get_npc_affinity()` | `(npc_id, tag) → float` | Single NPC → tag affinity |
| `set_npc_affinity_toward_player()` | `(npc_id, value, game_time) → float` | Set NPC → player opinion |
| `adjust_npc_affinity_toward_player()` | `(npc_id, delta, game_time) → float` | Adjust NPC → player opinion |
| `get_npc_affinity_toward_player()` | `(npc_id) → float` | NPC's opinion of player |
| `get_location_affinity_defaults()` | `(tier, location_id) → Dict[tag, float]` | Single location defaults |
| `compute_inherited_affinity()` | `(hierarchy) → Dict[tag, float]` | Sum location hierarchy |

### Event Contract

```python
FACTION_AFFINITY_CHANGED = "FACTION_AFFINITY_CHANGED"
data = {
    "player_id": str,
    "tag": str,
    "delta": float,          # actual clamped change
    "new_value": float,      # -100..100
    "source": str,           # "set" | "adjust"
}
```

**Consumer**: `world_system/world_memory/evaluators/faction_reputation.py` (WMS Layer 2 — already listening)

### Key Design Rules
- NPC affinity toward player = reserved tag `_player` in `npc_affinity` table (not separate table)
- All affinity values: -100..100 (clamped)
- All belonging significance: 0.0..1.0 (role weight)
- Sparse storage: only non-zero affinities stored
- Location hierarchy sum + clamp (world → nation → district → locality)

---

## Phase 3A: NPC Dialogue Integration

### Goal
Wire `FactionSystem` → `BackendManager` → `npc_agent.py` to generate contextual dialogue using affinity context.

### Files to Modify/Create

**Modify**: `world_system/living_world/npc/npc_agent.py`
- Add import: `from world_system.living_world.factions import FactionSystem`
- Add import: `from world_system.living_world.backends import BackendManager`
- In dialogue generation method, assemble context from FactionSystem
- Call `BackendManager.generate_dialogue()` with formatted context

**Create**: `world_system/living_world/factions/dialogue_helper.py` (20 lines)
```python
"""Helper to assemble dialogue context from FactionSystem."""

def assemble_dialogue_context(npc_id: str, player_id: str, location_hierarchy: List[Tuple[str, Optional[str]]]):
    """Return dict ready for BackendManager.generate_dialogue()."""
    from . import FactionSystem
    fs = FactionSystem.get_instance()
    
    npc = fs.get_npc_profile(npc_id)
    player_aff = fs.get_all_player_affinities(player_id)
    npc_opinion = fs.get_npc_affinity_toward_player(npc_id)
    location = fs.compute_inherited_affinity(location_hierarchy)
    
    return {
        "npc": npc,
        "player": {"id": player_id, "affinity_with_tags": player_aff},
        "npc_opinion": npc_opinion,
        "location": location,
    }
```

### Integration Pattern

```python
# In npc_agent.py
context = assemble_dialogue_context(
    npc_id="smith_1",
    player_id="player_1",
    location_hierarchy=[
        ("locality", "westhollow"),
        ("district", "iron_hills"),
        ("nation", "nation:stormguard"),
        ("world", None),
    ]
)

backend = BackendManager.get_instance()
dialogue = backend.generate_dialogue(
    model_type="dialogue_npc",
    system_prompt=DIALOGUE_SYSTEM_PROMPT,  # from LLM_INTEGRATION.md
    user_prompt=format_dialogue_prompt(context),
    temperature=0.7,
    max_tokens=200,
)
```

### Test Checklist
- [ ] `npc_agent.py` imports FactionSystem and BackendManager without errors
- [ ] `dialogue_helper.assemble_dialogue_context()` returns all required keys
- [ ] `BackendManager.generate_dialogue()` accepts context dict and returns string
- [ ] Dialogue generation runs without breaking NPC system
- [ ] Affinity values influence dialogue tone (manual inspection)

---

## Phase 3B: Quest Tool Integration

### Goal
Create LLM tool for quest system to apply affinity deltas based on player choices.

### Files to Create

**Create**: `world_system/living_world/factions/quest_tool.py` (60 lines)
```python
"""Quest tool for affinity changes."""

from . import FactionSystem

class QuestGenerator:
    @staticmethod
    def get_affinity_deltas(quest_id: str, choice_outcome: str) -> Dict[str, float]:
        """Return tag → delta map for a quest choice outcome.
        
        Query logic (placeholder):
        - Load quest definition from world system
        - Map outcome to affinity changes
        - Return dict of {tag: delta_value}
        """
        # TODO: Load quest_affinity_schema from JSON or quests table
        # For now, return hardcoded example
        if quest_id == "smith_contract" and choice_outcome == "complete_honestly":
            return {
                "guild:smiths": +15.0,
                "nation:stormguard": +10.0,
                "profession:blacksmith": +8.0,
            }
        return {}
    
    @staticmethod
    def apply_quest_deltas(player_id: str, deltas: Dict[str, float]) -> None:
        """Apply all deltas to player affinity."""
        fs = FactionSystem.get_instance()
        for tag, delta in deltas.items():
            fs.adjust_player_affinity(player_id, tag, delta)
```

**Modify**: Quest system integration point
- On quest completion, call `QuestGenerator.apply_quest_deltas(player_id, deltas)`
- Deltas publish `FACTION_AFFINITY_CHANGED` automatically via `adjust_player_affinity()`

### Integration Pattern

```python
# In quest_system.py or wherever quests complete
from world_system.living_world.factions.quest_tool import QuestGenerator

deltas = QuestGenerator.get_affinity_deltas(quest_id, choice_outcome)
QuestGenerator.apply_quest_deltas(player_id, deltas)
```

### Test Checklist
- [ ] `QuestGenerator.get_affinity_deltas()` returns dict
- [ ] `apply_quest_deltas()` calls `FactionSystem.adjust_player_affinity()` for each tag
- [ ] Events publish for each adjusted tag
- [ ] WMS evaluator receives all published events

---

## Phase 3C: Affinity Consolidator (Optional)

### Goal
Create new event type `FACTION_AFFINITY_CONSOLIDATED` to track rolled-up affinity changes across NPC/location aggregations.

### Files to Create

**Create**: `world_system/living_world/factions/consolidator.py` (80 lines)
```python
"""Consolidate affinity changes into narrative-friendly summaries."""

FACTION_AFFINITY_CONSOLIDATED = "FACTION_AFFINITY_CONSOLIDATED"

class AffinityConsolidator:
    @staticmethod
    def consolidate_player_standing(player_id: str) -> Dict[str, float]:
        """Return top 5 tags by affinity for player (for WMS narrative)."""
        from . import FactionSystem
        fs = FactionSystem.get_instance()
        aff = fs.get_all_player_affinities(player_id)
        # Sort by value, take top 5, return
        return dict(sorted(aff.items(), key=lambda x: x[1], reverse=True)[:5])
    
    @staticmethod
    def publish_consolidated_event(player_id: str, summary: Dict[str, float]) -> None:
        """Publish consolidated summary to GameEventBus."""
        from events.event_bus import get_event_bus
        try:
            get_event_bus().publish(
                FACTION_AFFINITY_CONSOLIDATED,
                {"player_id": player_id, "top_affinities": summary},
                source="FactionConsolidator"
            )
        except Exception as e:
            print(f"[Consolidator] Publish failed: {e}")
```

**Modify**: `__init__.py`
- Export: `FACTION_AFFINITY_CONSOLIDATED`, `AffinityConsolidator`

### Integration Pattern
- On game tick or milestone, call `consolidate_player_standing()` and `publish_consolidated_event()`
- WMS Layer 3-4 evaluators can consume consolidated events for high-level narratives

### Test Checklist
- [ ] Consolidator returns top 5 affinities sorted by value
- [ ] Event publishes without breaking other systems
- [ ] WMS can subscribe to `FACTION_AFFINITY_CONSOLIDATED`

---

## Phase 3D: Prompts & Fine-tuning

### Location
All prompts centralized in `world_system/living_world/factions/LLM_INTEGRATION.md` (already done).

### Candidates for Tuning
1. **NPC Dialogue** (Section 1)
   - Current: 0.7 temperature (creative)
   - Test: 0.5-0.8 range for personality vs consistency
   
2. **Location Affinities** (Section 2)
   - Current: 0.5 temperature (consistent)
   - Status: Matches design spec

3. **NPC Creation** (Section 3)
   - Current: Placeholder
   - Future: Implement as Phase 4

### Reference
- See `LLM_INTEGRATION.md` Sections 1-3 for system + user prompts
- See `LLM_INTEGRATION.md` Section 4 for BackendManager pattern
- See `world_system/living_world/backends/README.md` for model selection

---

## Code Patterns to Follow

### Event Publishing (Best-Effort)
```python
try:
    get_event_bus().publish(EVENT_TYPE, data, source="YourSystem")
except Exception as e:
    print(f"[System] Publish failed: {e}; continuing")
```

### FactionSystem Access
```python
from world_system.living_world.factions import FactionSystem
fs = FactionSystem.get_instance()
fs.initialize()  # Safe to call multiple times
```

### BackendManager Access
```python
from world_system.living_world.backends import BackendManager
backend = BackendManager.get_instance()
response = backend.generate_dialogue(
    model_type="dialogue_npc",
    system_prompt="...",
    user_prompt="...",
    temperature=0.7,
    max_tokens=200,
)
```

### Location Hierarchy
```python
hierarchy = [
    ("locality", location_name or None),
    ("district", district_name or None),
    ("nation", nation_name or None),
    ("world", None),
]
affinities = fs.compute_inherited_affinity(hierarchy)
```

---

## Testing Checklist (Per Phase)

### Phase 3A: Dialogue Integration
- [ ] Unit test: `assemble_dialogue_context()` with known NPC/player returns correct keys
- [ ] Integration test: NPC dialogue generation runs without errors
- [ ] Manual test: Dialogue tone changes with affinity level (positive/negative)
- [ ] Manual test: Dialogue references location culture from affinity defaults
- [ ] All 21 existing faction tests still pass

### Phase 3B: Quest Tool
- [ ] Unit test: `get_affinity_deltas()` returns expected dict for known quest
- [ ] Unit test: `apply_quest_deltas()` calls `adjust_player_affinity()` for each tag
- [ ] Integration test: Quest completion publishes `FACTION_AFFINITY_CHANGED` events
- [ ] Integration test: WMS evaluator receives events
- [ ] All 21 existing faction tests still pass

### Phase 3C: Consolidator (Optional)
- [ ] Unit test: `consolidate_player_standing()` returns top 5 by affinity
- [ ] Unit test: `publish_consolidated_event()` publishes without raising
- [ ] Integration test: WMS can subscribe to consolidated events
- [ ] All 21 existing faction tests still pass

### Final
- [ ] All 21 existing faction tests pass
- [ ] No stale imports or broken references
- [ ] No new database migrations needed (Phase 2 schema sufficient)
- [ ] LLM calls tested with BackendManager in mock mode

---

## Key Constraints

### DO NOT CHANGE
- SQLite schema (Phase 2+ is final)
- `FACTION_AFFINITY_CHANGED` event name/contract
- Affinity ranges (-100..100)
- Significance ranges (0.0..1.0)
- Reserved tag `_player` for NPC → player affinity

### DO EXTEND
- New event types (e.g., `FACTION_AFFINITY_CONSOLIDATED`)
- New helper modules (dialogue_helper.py, quest_tool.py, consolidator.py)
- New config in LLM_INTEGRATION.md (prompts, examples)

### DATABASE IS AUTHORITATIVE
- SQLite file persists independently from save/load system
- No migrations needed for Phase 3 (schema complete)
- Location defaults preloaded in bootstrap

---

## Handoff Notes for Smaller Model

### What Exists (Don't Reimplement)
1. **FactionSystem** — 19 methods, fully tested, ready to call
2. **GameEventBus** — pub/sub system, ready to publish to
3. **BackendManager** — LLM abstraction, ready to call
4. **Bootstrap defaults** — 15 location/faction defaults already in DB
5. **21 passing tests** — Phase 2+ complete and verified

### What to Build (Phase 3)
1. **dialogue_helper.py** — ~20 lines, assemble context dict
2. **Modify npc_agent.py** — ~10 lines, call BackendManager
3. **quest_tool.py** — ~60 lines, map quest → affinity deltas
4. **consolidator.py** — ~80 lines, roll up affinities for narratives
5. **Tests** — 3-5 new tests per phase

### Integration Points
- `npc_agent.py` (dialogue generation)
- Quest system (on quest completion)
- WMS evaluators (consume `FACTION_AFFINITY_CHANGED`)
- Game tick (consolidator milestone checks)

### Reference Docs
- **LLM_INTEGRATION.md** — Prompts, payloads, examples
- **schema.py** — Database schema + constants
- **faction_system.py** — API surface (19 methods)
- **test_faction_phase2plus.py** — Pattern for new tests (21 existing)

### CLI Quick Reference
```bash
cd /home/user/Game-1/Game-1-modular
python -m pytest world_system/living_world/factions/test_faction_phase2plus.py -v
# Expected: 21 passed
```

---

**Next Action**: Build Phase 3A (dialogue integration) first. It unblocks quest tool and consolidator.

**Estimated Size**: 200-300 lines of new code across 4 files.

**Confidence**: High (Phase 2 complete and verified; Phase 3 is integration only).
