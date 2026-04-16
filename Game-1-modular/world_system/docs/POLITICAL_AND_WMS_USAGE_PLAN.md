# Political Systems & WMS Usage — Implementation Handoff

**Date**: 2026-04-16
**Branch**: `claude/implement-layer-7-aggregation-mn87h`
**Prerequisite reading**: `HANDOFF_STATUS.md` (WMS state), `PART_2_LIVING_WORLD.md` (design plan)

---

## Bottom Line Up Front

Three systems are **scaffolded but not wired in**:

| System | Code exists | Initialized in game? | Used anywhere? |
|--------|------------|----------------------|----------------|
| `FactionSystem` | ✅ `living_world/factions/faction_system.py` | ❌ never called | ❌ |
| `NPCAgentSystem` | ✅ `living_world/npc/npc_agent.py` | ❌ never called | ❌ |
| `WorldQuery` | ✅ `world_memory/query.py` | ✅ initialized in WMS | ❌ nothing queries it |

The WMS pipeline (Layers 1-7, 36 evaluators) records everything. Nothing reads it.
`FactionSystem` can react to bus events but never starts. This document defines what
to build and in what order.

---

## What Must NOT Change

Before starting, read `HANDOFF_STATUS.md §Single Sources of Truth`. Specifically:

- **Do not add `FACTION_REP_CHANGED` to WMS Layer pipeline yet.** It is deliberately
  excluded until FactionSystem is real (see `ARCHITECTURAL_DECISIONS.md §§2-5`).
  A faction *evaluator* (Layer 2) will be added, but only after the faction data
  is real and the system is initialized in game.
- **Do not modify `faction-definitions.json` incrementally.** It is explicitly
  a placeholder — see the `_status` key at line 1. The whole file gets redesigned.
- **Do not touch any content JSON** (`items.JSON/`, `recipes.JSON/`, `Skills/`, etc.).
- **Do not modify `combat_manager.py`** — integrate faction effects via event bus only.

---

## Dependency Chain

```
Step 1: Design + populate real faction data (JSON)
    ↓
Step 2: Wire FactionSystem into game_engine._init_world_memory()
    ↓
Step 3: Connect NPC IDs → faction membership (JSON + npc_system.py lookup)
    ↓
Step 4: Add FACTION_REP_CHANGED evaluator to WMS Layer 2
    ↓
Step 5: Wire NPCAgentSystem + WorldQuery into game_engine
    ↓
Step 6: Integrate WMS context into NPC dialogue (the actual "living world" moment)
    ↓
Step 7 (optional, long-term): World Chronicle UI
```

Steps 1-3 are **political system setup**.
Steps 4-6 are **WMS consumption**.
Step 7 is **player-facing UI**.

Do not start Step 4 before Step 2. Do not start Step 6 before Step 5.

---

## Step 1: Design Real Faction Data

### Problem
`faction-definitions.json` has 4 placeholder factions with empty `member_npc_ids`
and territory IDs that don't match the actual `geographic-map.json` hierarchy.

The game's actual geographic districts (from `geographic-map.json`):
- `whispering_woods` — forest, low danger, northwest
- `iron_hills` — mining, quarry, northeast  
- `deep_caverns` — cave, dangerous, south
- `traders_corner` — settlement, central
- `elder_grove` — forest, mystical
- `spawn_crossroads` — starting area
- (+ more districts defined in geographic-map.json)

The game's 3 NPCs (from `progression/npcs-1.JSON`): `combat_trainer`, `mysterious_trader`, `tutorial_guide`.

### What to do

1. **Read** `world_system/config/geographic-map.json` (all districts/provinces) and
   `Game-1-modular/progression/npcs-1.JSON` (all NPC IDs) before redesigning factions.

2. **Redesign `faction-definitions.json`** to:
   - Reference real district/province IDs from `geographic-map.json`
   - Assign real NPC IDs to factions (at minimum: trainer→village_guard, trader→merchants)
   - Add `reputation_events` blocks mapping bus event types to rep deltas:
     ```json
     "reputation_events": {
       "ENEMY_KILLED": {
         "wolf": { "forest_wardens": -0.02, "village_guard": 0.01 },
         "default": { "village_guard": 0.005 }
       },
       "RESOURCE_GATHERED": {
         "default": { "forest_wardens": -0.01 }
       }
     }
     ```
   - Keep existing 4 faction structure unless there's a design reason to change

3. **Add a `faction_territories` mapping** in the JSON that maps faction_id → list of
   `region_id` values from geographic-map.json (not invented names). This is used to:
   - Determine which faction "cares" about an event by location
   - Determine which faction's territory a WMS Layer 2 event occurred in

### Key file
`world_system/config/faction-definitions.json` — rewrite from scratch with real data.

---

## Step 2: Wire FactionSystem into game_engine

### Problem
`game_engine._init_world_memory()` initializes `WorldMemorySystem` but never
initializes `FactionSystem`, `NPCAgentSystem`, or `EcosystemAgent`.

### What to do

In `core/game_engine.py`, extend `_init_world_memory()` (around line 4460):

```python
# After WorldMemorySystem initialization...

# Initialize FactionSystem
try:
    from world_system.living_world.factions.faction_system import FactionSystem
    self.faction_system = FactionSystem.get_instance()
    self.faction_system.initialize()
    print(f"[GameEngine] FactionSystem initialized")
except Exception as e:
    self.faction_system = None
    print(f"[GameEngine] FactionSystem init failed (non-fatal): {e}")
```

FactionSystem already subscribes to `ENEMY_KILLED`, `ITEM_CRAFTED`,
`RESOURCE_GATHERED`, `LEVEL_UP` in its `_connect_bus()` method — it will
self-wire to the event bus on `initialize()`. No other changes needed.

**Also**: Persist faction state on save/load. `FactionSystem` has player reputation
as a `Dict[str, float]` in `self._player_reputation`. Wire into
`systems/save_manager.py` — add `"faction_reputation"` to the save dict and
call `faction_system.load_reputation(data)` on load.

### Where to look
- `core/game_engine.py:4451` — `_init_world_memory()`
- `world_system/living_world/factions/faction_system.py:91` — `initialize()`
- `systems/save_manager.py` — save/load extension point

---

## Step 3: NPC → Faction Membership

### Problem
NPCs have no faction. The 3 game NPCs (`combat_trainer`, `mysterious_trader`,
`tutorial_guide`) are defined in `progression/npcs-1.JSON`. The faction JSON's
`member_npc_ids` arrays are empty.

### What to do

1. Populate `member_npc_ids` in `faction-definitions.json` with real NPC IDs.
2. The `FactionSystem._npc_faction_map` is built from `member_npc_ids` at init —
   no code change needed, just JSON data.
3. Extend `get_npc_disposition(npc_id)` (already implemented in faction_system.py)
   to return a usable disposition label that NPC dialogue code can consume.

Test: after init, `faction_system.get_npc_disposition("combat_trainer")` should
return `"neutral"`, `"friendly"`, or `"hostile"` based on player reputation.

---

## Step 4: Faction Evaluator for WMS Layer 2

### Problem
`FACTION_REP_CHANGED` is published by FactionSystem but excluded from
`BUS_TO_MEMORY_TYPE`. The WMS pipeline never sees faction changes.

### What to do

Follow the **New-Evaluator Checklist** in `HANDOFF_STATUS.md §New-Evaluator Checklist`
to add a faction evaluator. Key design decisions:

**EventType**: `FACTION_REP_CHANGED = "faction_rep_changed"`

**Payload** (already published by FactionSystem):
```python
get_event_bus().publish("FACTION_REP_CHANGED", {
    "faction_id": faction_id,
    "faction_name": faction.name,
    "delta": delta,
    "new_score": new_score,
    "reason": reason,
    "is_ripple": is_ripple,
    "position_x": ...,  # ADD THIS — FactionSystem doesn't include it yet
    "position_y": ...,  # ADD THIS
})
```

> **Note**: FactionSystem currently doesn't include position in its payload.
> This is a gap — before writing the evaluator, ensure position is included
> so `EventRecorder._enrich_geographic` can assign locality/district IDs.

**Evaluator design** (`evaluators/faction_reputation.py`):
- `RELEVANT_TYPES = {"faction_rep_changed"}`
- Severity based on magnitude of change and direction:
  - `|delta| < 0.05` → minor
  - Crossing a milestone threshold (0.25, 0.5, -0.5) → significant or major
- Tags: `domain:faction`, `faction:{faction_id}`, `relationship:{hostile|neutral|friendly|allied}`
- Narrative: "Player's standing with the {faction_name} has {improved/worsened}."

**Prompt fragment to add** (`prompt_fragments.json`):
- `"domain:faction"`: "This is a faction reputation event. Factions are groups of NPCs with shared interests. Player reputation affects NPC dialogue, content access, and faction behavior."
- `"action:faction_rep_changed"`: "Faction reputation changed. Positive changes reflect helpful actions; negative changes reflect harmful ones. Milestone crossings unlock or lock content."

**Config block** (`memory-config.json`):
```json
"faction_reputation": {
  "enabled": true,
  "lookback_time": 200.0,
  "expiration_offset": 300.0,
  "thresholds": { "minor_max": 0.05, "significant_min": 0.15, "major_min": 0.30 },
  "milestone_thresholds": [0.25, 0.5, 0.75, -0.25, -0.5],
  "narrative_templates": {
    "improved": "Player's standing with {faction} has improved to {score:.2f}.",
    "worsened": "Player's standing with {faction} has worsened to {score:.2f}.",
    "milestone": "Player has reached {label} status with {faction}."
  }
}
```

---

## Step 5: Wire NPCAgentSystem and WorldQuery into game_engine

### Problem
`NPCAgentSystem` exists but `game_engine.py` never initializes it. NPC dialogue
in `game_engine._handle_npc_interaction()` calls static JSON cycling, not the agent.

### What to do

**Part A: Initialize NPCAgentSystem**

In `game_engine._init_world_memory()`, after WMS init:

```python
try:
    from world_system.living_world.npc.npc_agent import NPCAgentSystem
    from world_system.living_world.backends.backend_manager import BackendManager
    from world_system.living_world.npc.npc_memory import NPCMemoryManager

    backend = BackendManager.get_instance()
    backend.initialize()

    memory_manager = NPCMemoryManager.get_instance()
    npc_memory_path = os.path.join(save_dir, "npc_memories.json")
    memory_manager.load(npc_memory_path)

    self.npc_agent_system = NPCAgentSystem.get_instance()
    self.npc_agent_system.initialize(
        config=None,  # loads from npc-personalities.json
        npc_memory_manager=memory_manager,
        world_query=self.world_memory.world_query,
    )
except Exception as e:
    self.npc_agent_system = None
    print(f"[GameEngine] NPCAgentSystem init failed (non-fatal): {e}")
```

**Part B: Wire WorldQuery**

`WorldMemorySystem.initialize()` already creates `world_query` at line ~220 but
only if the query module loads. Verify it's accessible:
```python
self.world_memory.world_query  # Should not be None after WMS init
```

If it's None, trace the init chain in `world_memory_system.py` around the
`WorldQuery` initialization.

**Part C: Save/load NPC memories**

On game save: `memory_manager.save(npc_memory_path)`
On game load: `memory_manager.load(npc_memory_path)` (already in init above)

### Where to look
- `world_system/living_world/npc/npc_agent.py:54` — NPCAgentSystem
- `world_system/living_world/npc/npc_memory.py` — NPCMemoryManager
- `world_system/living_world/backends/backend_manager.py` — BackendManager
- `world_system/world_memory/query.py:62` — WorldQuery

---

## Step 6: Integrate WMS Context into NPC Dialogue

This is the **living world moment** — NPCs respond to what actually happened.

### Problem
`game_engine._handle_npc_interaction()` (find via Grep for `NPC_INTERACTION`) uses
cycling static dialogue. The `NPCAgentSystem.generate_dialogue()` method exists
but is never called.

### What to do

1. **Find the NPC interaction handler** in `game_engine.py`. It currently calls
   something like `npc.get_dialogue()` or cycles through `npc.dialogue_lines`.

2. **Add an LLM dialogue path** (guarded by `npc_agent_system` availability):

```python
if self.npc_agent_system and self.npc_agent_system._initialized:
    result = self.npc_agent_system.generate_dialogue(
        npc_id=npc.npc_id,
        player_input="",   # or player-typed text if UI supports it
        character=self.character,
    )
    if result.success:
        dialogue_text = result.text
        # Optional: apply relationship delta
        # faction_system.modify_reputation(npc_faction, result.relationship_delta, "dialogue")
    else:
        dialogue_text = self._get_static_dialogue(npc)  # fallback
else:
    dialogue_text = self._get_static_dialogue(npc)
```

3. **NPC context building** (`NPCAgentSystem.build_context()`) should call:
   ```python
   world_query_result = self._world_query.for_npc(npc_id)
   # world_query_result.nearby_relevant_events → recent events near NPC
   # world_query_result.ongoing_conditions → active L2 interpretations
   # world_query_result.regional_context → L3/L4 summaries for NPC's region
   ```
   This is already plumbed in `NPCAgentSystem` (it has `self._world_query`) but
   `build_context()` must be verified/extended to actually call it.

4. **BackendManager generates dialogue** via configured LLM (Ollama or Claude).
   The MockBackend returns template responses when no real LLM is available —
   so development/testing doesn't require an API key.

### What NPCs will know about

Once wired, NPCs will have access to:
- Recent events near their location (from WorldQuery.for_npc)
- Ongoing L2 narratives in their district ("high combat activity in Whispering Woods")
- Regional L3 context summaries
- Faction reputation (from FactionSystem.get_npc_disposition)
- Their own memory (past interactions, emotional state)

This creates dialogue like: "I heard you've been busy hunting in the woods. The forest wardens
won't be pleased if you keep that up."

---

## Step 7 (Long-term): World Chronicle UI

A player-facing panel displaying the WMS narrative state. Low priority — build after
Steps 1-6 are functional.

### API needed first

`WorldMemorySystem` needs query methods that don't yet exist:

```python
def get_world_summary(self, world_id: str = "world_0") -> Optional[WorldSummaryEvent]:
    """Return the latest L7 world summary."""
    if not self.layer_store:
        return None
    events = self.layer_store.get_layer_events("layer7_events", limit=1)
    return events[0] if events else None

def get_nation_summaries(self, world_id: str = "world_0") -> List[NationSummaryEvent]:
    """Return latest L6 per-nation summaries."""
    ...

def get_region_summaries(self, nation_id: str) -> List[RegionSummaryEvent]:
    """Return latest L5 per-region summaries."""
    ...
```

These query methods are the prerequisite for any Chronicle UI. Add them to
`world_memory_system.py` as a clean API surface, tested with simple unit tests.

### UI integration
- New key binding (e.g., `J` for "Journal" or `W` for "World") opens Chronicle panel
- Panel shows: World Summary → expandable Nation summaries → expandable Region summaries
- Rendered in `rendering/renderer.py` (follows existing overlay panel pattern)
- Source data: the LayerStore tables `layer7_events`, `layer6_events`, `layer5_events`

---

## File Map: What to Touch

| Step | Files to MODIFY | Files to CREATE |
|------|----------------|-----------------|
| 1 | `world_system/config/faction-definitions.json` (rewrite) | — |
| 2 | `core/game_engine.py`, `systems/save_manager.py` | — |
| 3 | `world_system/config/faction-definitions.json` | — |
| 4 | `world_system/world_memory/event_schema.py`, `event_recorder.py`, `interpreter.py`, `memory-config.json`, `prompt_fragments.json` | `evaluators/faction_reputation.py`, test cases |
| 5 | `core/game_engine.py`, `systems/save_manager.py` | — |
| 6 | `core/game_engine.py`, `world_system/living_world/npc/npc_agent.py` | — |
| 7 | `core/game_engine.py`, `rendering/renderer.py`, `world_system/world_memory/world_memory_system.py` | query methods |

---

## Current State Verification

Run before starting any work:

```bash
cd Game-1-modular

# 1. All 246 tests pass
python -m unittest discover -s world_system/tests -p "test_*.py"

# 2. FactionSystem is NOT called from game_engine
grep -n "FactionSystem\|NPCAgentSystem" core/game_engine.py
# → should return 0 matches

# 3. WorldQuery exists but is unqueried
grep -rn "world_query\." core/ systems/ entities/ --include="*.py"
# → should return 0 matches (only world_memory_system.py creates it)

# 4. FactionSystem bus events ARE published (once integrated)
grep -n "FACTION_REP_CHANGED" world_system/living_world/factions/faction_system.py
```

---

## Critical Design Notes

### Faction territory must match WMS geography

`faction-definitions.json`'s `territory_regions` must use the same IDs as
`geographic-map.json`. The geographic hierarchy has these levels:
`world → province → district → locality`. Factions should map to **districts**
(e.g., `whispering_woods`, `iron_hills`) — the finest tier with named areas.

This matters because: when a WMS Layer 2 event fires in `district_id=whispering_woods`,
the faction evaluator can check which faction's territory that falls in and tag
the interpretation with `faction:forest_wardens`.

### FactionSystem is a SIBLING to WMS, not inside it

`FactionSystem` subscribes to the **bus** independently. It does not read from
or write to `EventStore` or `LayerStore`. The WMS pipeline reads `FACTION_REP_CHANGED`
events from the bus (via `BUS_TO_MEMORY_TYPE`) and creates Layer 2 narratives —
this is the only connection. See `ARCHITECTURAL_DECISIONS.md §§2-5`.

### NPCAgentSystem gracefully degrades

If BackendManager has no real LLM (no Ollama, no API key), MockBackend returns
plausible template text. The game should be fully playable with mock responses —
the LLM enrichment is additive, not critical path.

### Save file compatibility

When adding faction state and NPC memories to saves, follow the existing pattern
in `save_manager.py`: version-gate new fields with `.get("faction_reputation", {})`
defaults so old save files load cleanly.
