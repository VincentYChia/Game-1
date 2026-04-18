# Faction System — Comprehensive Handoff Document

**Date**: April 18, 2026  
**Status**: Phase 2 Complete, Phase 3 Ready to Begin  
**Audience**: Next developer, project lead, or future continuation

---

## Executive Summary

The faction system is a **parallel recording and retrieval layer** for NPC/player affinity. It:
- Records affinity changes from game events (quests, combat)
- Supplies context for NPC dialogue generation (real-time LLM)
- Feeds affinity changes to an independent **consolidator tool** (separate LLM)
- Publishes events to GameEventBus (WMS integration optional)

**Phase 2** (Complete): Database, data models, singleton manager, comprehensive testing.  
**Phase 3** (Ready): NPC dialogue integration, quest tool, affinity consolidator.  
**Phase 4+** (Designed): Location affinity generation, NPC creation, dialogue pre-caching.

---

## Part 1: Current State (Phase 2 Complete)

### 1.1 What's Implemented

**Database Layer** (`schema.py` — 224 lines):
- 8 SQLite tables with proper constraints
- Sparse storage (only non-zero values)
- 3 indexes for query performance
- Bootstrap location affinity defaults (hardcoded, to be LLM-generated)

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `npc_profiles` | NPC core data | npc_id, narrative, created_at, last_updated |
| `npc_belonging_tags` | NPC's faction memberships | npc_id, tag, significance (0-1), role, narrative_hooks, since_game_time |
| `npc_affinity` | NPC's feelings about tags; personal opinion of player stored under reserved tag `_player` | npc_id, tag, affinity_value (-100 to 100), last_updated |
| `player_affinity` | Player's standing with tags | player_id, tag, affinity_value (-100 to 100), last_updated |
| `location_affinity_defaults` | Cultural defaults for locations | address_tier, location_id, tag, affinity_value (-100 to 100) |
| `faction_schema_version` | Schema versioning | version, updated_at |

**Data Models** (`models.py` — 119 lines):
- `FactionTag`: Single tag with significance, role, narrative hooks
- `NPCProfile`: Complete NPC (narrative, belonging_tags, affinity)
- `PlayerProfile`: Player's affinities with all tags
- `LocationAffinityDefault`: Cultural baseline for location/tag
- `NPCAffinityTowardPlayer`: Per-NPC personal opinion

**Manager** (`faction_system.py` — 330 lines):
- Singleton pattern with initialization
- 17 CRUD methods covering all operations
- NPC management (add, get, update tags)
- Player affinity (set, adjust, get, get all)
- NPC affinity (set, get)
- NPC opinion of player (set, adjust, get)
- Location defaults (get single, compute inherited with summing)
- Save/load for game state persistence

**Testing** (`test_faction_phase2plus.py` — 267 lines):
- 4 test classes with 11 test methods
- NPC profile CRUD, player affinity operations, location inheritance
- Integration workflow (quest → deltas → affinity)
- All tests passing (use `pytest` if available)

**Documentation** (NEW):
- `PHASE_2_ARCHITECTURE.md` — Design overview, significance buckets, WMS integration
- `INFORMATION_FLOW.md` — Clear data flow explanation (read this first)
- `LLM_INTEGRATION.md` — Prompts, payloads, integration patterns
- `IMPLEMENTATION_STATUS.md` — Phase 2 checklist + Phase 3 roadmap

### 1.2 What's NOT Implemented

❌ NPC dialogue integration (Phase 3)  
❌ Quest tool definition (Phase 3)  
❌ Affinity consolidator (Phase 3)  
❌ Location affinity LLM generation (Phase 4)  
❌ NPC creation pipeline (Phase 4)  
❌ Dialogue pre-caching (Phase 4+)  
❌ WMS FactionReputationEvaluator wiring (WMS responsibility)  

### 1.3 Code Organization

```
Game-1-modular/world_system/living_world/factions/
├── schema.py                           # Database schema + bootstrap
├── models.py                           # Python dataclasses
├── faction_system.py                   # Singleton manager (CORE)
├── __init__.py                         # Initialization functions
├── test_faction_phase2plus.py          # Test suite
├── PHASE_2_ARCHITECTURE.md             # Design overview
├── INFORMATION_FLOW.md                 # Data flow explanation (START HERE)
├── LLM_INTEGRATION.md                  # Prompts and integration
├── IMPLEMENTATION_STATUS.md            # Phase checklist
└── HANDOFF.md                          # This file
```

---

## Part 2: Design Philosophy

### 2.1 Core Principles

**Parallel Recording System**: FactionSystem is **NOT** part of WMS pipeline. It's a sibling system that:
- Listens to GameEventBus (same as WMS)
- Records to its own SQLite database (faction.db, separate from WMS)
- Publishes events (optional WMS consumption in future)

**Affinity as -100 to 100 Scale**: All affinity values use same range:
- Player affinity with tags (global standing)
- NPC affinity with tags (how NPC feels)
- NPC affinity toward player (per-NPC personal opinion)
- Location affinity defaults (cultural baseline)

**Only significance (belonging tags) uses 0-1 scale** — how central is NPC to a faction.

**Sparse Storage**: Only non-zero affinities written to database. Default is 0 (neutral).

**Hierarchical Inheritance**: Location affinity cascades from world → nation → region → province → district → locality, with summing:
```python
hierarchy = [
    ("locality", "village_westhollow"),
    ("district", "grain_fields"),
    ("nation", "nation:stormguard"),
    ("world", None)
]
accumulated = faction_sys.compute_inherited_affinity(hierarchy)
# Returns: {tag: sum of affinities across all tiers}
```

### 2.2 LLM Integration Philosophy

**Three separate LLM tools** (not one unified system):

1. **NPC Dialogue Generation** (Real-time, BackendManager)
   - Input: NPC profile + player affinity + location defaults
   - Output: Dialogue text (50-200 words)
   - No affinity changes (read-only)

2. **Quest Tool** (Tool-calling LLM, called by dialogue agent)
   - Input: NPC context + player context + location + world
   - Output: Quest JSON with difficulty, tag relevance, narrative hints
   - Does NOT estimate affinity deltas

3. **Affinity Consolidator** (Tool-calling LLM, post-quest)
   - Input: Dialogue transcript + quest + completion data + profiles
   - Output: Affinity changes + narrative
   - Authority on affinity deltas (not quest system)
   - Uses log-scale difficulty: harder quests = bigger impacts
   - Applies diminishing returns (harder to change high affinities)

**Critical constraint**: Consolidator is SEPARATE from WMS consolidation. It's a tool that the faction system calls, not part of WMS Layer 2+.

### 2.3 Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| Separate from WMS | Faction is parallel recording, not behavior simulator. No consolidation hierarchy. |
| Sparse storage | Reduces DB size, simplifies queries. Defaults to 0 (neutral). |
| Hierarchical defaults | Locations inherit cultural attitudes from parent tiers. Enables rich world-building. |
| Three opinion tracks | Player, NPC, NPC→player are orthogonal concerns. |
| No rules engine | Quest system provides metadata; consolidator decides impacts. More flexible. |
| Consolidator separate | Affinity assignment is complex (difficulty × relevance × quality × diminishing). Deserves own LLM tool. |
| Event-driven | Changes publish to GameEventBus; WMS/other systems can subscribe. |
| Log-scale affects | Difficulty scales non-linearly; harder quests have bigger reputation impact. |

---

## Part 3: Key Integration Points

### 3.1 External System Dependencies

**BackendManager** (`world_system/living_world/backends/backend_manager.py`):
- Exists ✓ (supports Ollama, Claude, Mock)
- Used by: NPC dialogue generation, quest tool, consolidator
- Methods to add: `generate_dialogue()`, `generate_quest()`, `consolidate_affinity()`
- No changes to FactionSystem needed; it just calls BackendManager

**NPC Agent System** (`world_system/living_world/npc/npc_agent.py`):
- Exists ✓ (has `generate_dialogue()` method)
- Will integrate: Gathers faction context before calling BackendManager
- Will call: Quest tool when player requests quest
- Will call: Consolidator when quest completes
- Expected changes: Add faction context assembly, add tool calls

**GameEventBus** (`events/event_bus.py`):
- Exists ✓ (pub/sub system)
- FactionSystem already publishes: `FACTION_AFFINITY_CHANGED` (on affinity changes)
- New event: `FACTION_AFFINITY_CONSOLIDATED` (after consolidator runs)
- No changes to FactionSystem; just documentation

**WMS (Optional)** (`world_system/world_memory/`):
- Exists ✓ (Layers 1-7 complete)
- **NOT integrated** by design (see HANDOFF_STATUS.md)
- Future: FactionReputationEvaluator can listen to `FACTION_AFFINITY_CHANGED` if desired
- No blocking dependency; faction works standalone

### 3.2 Data Flow Through System

```
Timeline:

T0: Player asks NPC for quest
    NPC Agent → Gathers faction context (4 FactionSystem calls)
    NPC Agent → Calls BackendManager.generate_dialogue()
    LLM generates dialogue (affinity-aware tone)
    Player sees dialogue (read-only)

T1: Player accepts quest
    Dialogue Agent → Calls Quest Tool (tool-calling)
    Quest Tool → Gathers context, calls BackendManager.generate_quest()
    LLM generates quest JSON (difficulty, tags, narrative hints)
    Quest returned to player

T2: Player completes quest
    Game captures completion metrics (time, quality, success)

T3: Quest completion triggered
    Quest System/Dialogue Agent → Calls Consolidator Tool (tool-calling)
    Consolidator Tool → Gathers all context, calls BackendManager.consolidate_affinity()
    LLM processes:
      - Quest relevance to NPC's tags
      - Difficulty impact (log scale)
      - Player quality of completion
      - Existing affinity (diminishing returns)
    Returns: Affinity changes + narrative

T4: Consolidation output applied
    FactionSystem.adjust_player_affinity() for each tag delta
    FactionSystem.adjust_npc_affinity_toward_player() if needed
    Database updated (sparse: only non-zero)

T5: Event published
    GameEventBus.publish("FACTION_AFFINITY_CONSOLIDATED", {...})
    (Optional) WMS evaluator can listen

T6: Next dialogue reflects new affinity
    Player talks to NPC again
    New affinity values passed to dialogue generation
    LLM generates different tone (warmer/colder)
```

### 3.3 Critical Methods (FactionSystem API)

**For NPC Dialogue Context**:
```python
npc = faction_sys.get_npc_profile(npc_id)
player_aff = faction_sys.get_all_player_affinities(player_id)
npc_opinion = faction_sys.get_npc_affinity_toward_player(npc_id)
location_aff = faction_sys.compute_inherited_affinity(hierarchy)
```

**For Consolidator to Write Results**:
```python
faction_sys.adjust_player_affinity(player_id, tag, delta)
faction_sys.adjust_npc_affinity_toward_player(npc_id, delta)
```

**For Quest System** (indirect, via consolidator):
```python
# No direct integration; quest system provides metadata only
# Consolidator reads NPC/player profiles and writes results
```

---

## Part 4: Implementation Roadmap (Phase 3)

### Phase 3A: NPC Dialogue Integration (Week 1)

**Files to Modify**:
1. `world_system/living_world/npc/npc_agent.py`
   - Import FactionSystem
   - Add method: `_assemble_faction_context(npc_id, player_id, location_hierarchy)`
   - In `generate_dialogue()`: Gather faction context, pass to BackendManager
   - Update system/user prompts with affinity-aware instructions

2. `world_system/living_world/backends/backend_manager.py`
   - Add method: `generate_dialogue(system_prompt, user_prompt, temperature, max_tokens)`
   - (Wrapper around existing `generate()` method)

3. `world_system/living_world/factions/faction_system.py`
   - Add helper: `assemble_dialogue_context(npc_id, player_id, location_hierarchy)`
   - Returns formatted dict ready for LLM (npc, player, location sections)

**Testing**:
- Unit: Faction context assembly with mock data
- Integration: Full dialogue generation with faction context
- Manual: Verify affinity values modulate dialogue tone

### Phase 3B: Quest Tool Integration (Week 1-2)

**Files to Create**:
1. `world_system/living_world/backends/quest_tool.py` (NEW)
   - Class: `QuestGenerator`
   - Method: `generate_quest(npc_context, player_context, location_context, world_context)`
   - Calls BackendManager with tool-calling schema
   - Returns: Quest JSON (name, description, objectives, difficulty, tag_relevance, narrative_hooks, rewards)

**Files to Modify**:
1. `world_system/living_world/npc/npc_agent.py`
   - When player requests quest: Call `QuestGenerator.generate_quest()`
   - Store quest metadata for consolidator
   - Return quest to player

2. `world_system/living_world/backends/backend_manager.py`
   - Add method: `generate_quest(context_dict, temperature=0.5, max_tokens=1000)`
   - Tool-calling with quest JSON schema

**Testing**:
- Unit: Quest generation with various contexts
- Verify difficulty numbers (5-50 point range)
- Verify tag_relevance makes sense

### Phase 3C: Affinity Consolidator (Week 2-3)

**Files to Create**:
1. `world_system/living_world/factions/consolidator.py` (NEW)
   - Class: `AffinityConsolidator`
   - Method: `consolidate_quest_completion(dialogue, quest, npc, player, completion_data)`
   - Calls BackendManager with consolidator schema
   - Returns: `ConsolidatedEvent` (narrative, affinity_changes, npc_opinion_change)

2. `world_system/living_world/factions/consolidated_event.py` (NEW)
   - Dataclass: `ConsolidatedEvent`
   - Fields: narrative (str), player_affinity_changes (Dict[tag, delta]), npc_affinity_toward_player_change (float), npc_tag_changes (List[tag])

**Files to Modify**:
1. `world_system/living_world/npc/npc_agent.py` (or quest completion handler)
   - When quest completes: Call `AffinityConsolidator.consolidate_quest_completion()`
   - Apply changes: `faction_sys.adjust_player_affinity()`, etc.
   - Publish event: `GameEventBus.publish("FACTION_AFFINITY_CONSOLIDATED", {...})`

2. `world_system/living_world/backends/backend_manager.py`
   - Add method: `consolidate_affinity(context_dict, temperature=0.4, max_tokens=1000)`
   - Tool-calling with consolidator JSON schema

3. `events/event_bus.py` (or game_engine.py)
   - Add event type: `FACTION_AFFINITY_CONSOLIDATED` (if not exists)
   - Document structure

**Testing**:
- Unit: Consolidation with various difficulties/qualities
- Verify log-scale calculations
- Verify diminishing returns at high affinities
- Integration: Full quest → consolidation → database flow

### Phase 3D: Prompts & Fine-tuning (Week 3)

**Files to Create**:
1. `world_system/living_world/backends/prompt_templates.py` (NEW)
   - Centralized prompts for:
     - NPC dialogue (affinity-aware)
     - Quest generation (difficulty-calibrated)
     - Affinity consolidation (log-scale aware)
   - Each as format template with clear placeholders

**Iterate Based On**:
- Sample dialogue/quest/consolidation generation
- Verify quality, consistency, affinity influence
- Adjust temperatures (dialogue 0.7, quest 0.5, consolidation 0.4)

### Phase 3E: Integration Testing (Week 4)

**Test Scenario**:
1. Player talks to NPC (dialogue)
2. Receives quest (quest tool)
3. Completes quest (metrics gathered)
4. Affinity calculated (consolidator)
5. Verify database updated
6. Next dialogue reflects new affinity

**Files to Create/Modify**:
- Add comprehensive integration test
- Document usage patterns

---

## Part 5: Testing & Validation

### 5.1 Unit Tests (Already Written - Phase 2)

File: `test_faction_phase2plus.py`

Test classes:
- `TestNPCProfiles` (3 tests): Add NPC, retrieve, get by tag
- `TestPlayerAffinity` (4 tests): Set, adjust, get, get all, clamping
- `TestLocationAffinity` (2 tests): Get defaults, compute inheritance
- `TestIntegration` (1 test): Quest → affinity flow

**Run tests**:
```bash
cd Game-1-modular
python -m pytest world_system/living_world/factions/test_faction_phase2plus.py -v
```

### 5.2 New Tests (Phase 3)

**NPC Dialogue Context**:
- Verify context assembly returns correct structure
- Mock NPC/player/location data
- Verify affinity values included

**Quest Tool**:
- Generate quest with various contexts
- Verify JSON schema valid
- Verify difficulty in expected range

**Consolidator**:
- Consolidation with known inputs → expected outputs
- Verify log-scale calculations
- Verify clamping to -100/100
- Verify diminishing returns

**Integration**:
- Full flow: dialogue → quest → consolidation → affinity
- Verify database written
- Verify events published
- Verify next dialogue reflects new affinity

### 5.3 Manual Testing Checklist

- [ ] NPC dialogue generates in real-time (not blocking)
- [ ] Dialogue tone differs with affinity (high vs low)
- [ ] Quest tool generates valid quests
- [ ] Quest difficulty values reasonable
- [ ] Consolidator calculates affinities
- [ ] Affinity changes written to database
- [ ] Events published to GameEventBus
- [ ] Multiple NPC interactions work
- [ ] Affinity values never exceed ±100
- [ ] Location hierarchy inheritance works

---

## Part 6: Critical Files & Line Counts

| File | Lines | Purpose |
|------|-------|---------|
| `faction_system.py` | 330 | Core manager - CRITICAL |
| `schema.py` | 224 | Database definitions |
| `models.py` | 119 | Python dataclasses |
| `__init__.py` | 40 | Initialization |
| `test_faction_phase2plus.py` | 267 | Test suite |
| `PHASE_2_ARCHITECTURE.md` | 207 | Design overview |
| `INFORMATION_FLOW.md` | 420 | Data flow (READ FIRST) |
| `LLM_INTEGRATION.md` | 850 | Prompts & integration |
| `IMPLEMENTATION_STATUS.md` | 183 | Phase checklist |
| **Total** | **2,640** | |

---

## Part 7: Known Gaps & Future Work

### Immediate (Phase 3 - Next Priority)

- [ ] NPC dialogue integration with faction context
- [ ] Quest tool definition and integration
- [ ] Affinity consolidator tool
- [ ] Full end-to-end testing
- [ ] Prompt fine-tuning

### Medium-Term (Phase 4)

- [ ] Location affinity generation (LLM)
- [ ] NPC creation pipeline (LLM generates narrative + tags)
- [ ] Dialogue pre-caching system
- [ ] Async player option generation
- [ ] Personality test onboarding

### Long-Term (Phase 5+)

- [ ] Multi-character support (currently "player_1" placeholder)
- [ ] Dialogue-choice → affinity feedback (after personality profiling)
- [ ] NPC faction dynamics (rival factions, alliances)
- [ ] Quest generation from faction events
- [ ] WMS FactionReputationEvaluator full integration

### Known Limitations

1. **Hardcoded location defaults**: BOOTSTRAP_LOCATION_AFFINITY_DEFAULTS in schema.py (15 entries). Should be LLM-generated for full world.
2. **Single player placeholder**: Using "player_1"; should be character save slot ID.
3. **No faction dynamics**: Factions don't influence each other (by design for Phase 2).
4. **Consolidator separate from WMS**: Intentional design decision; faction is parallel system.

---

## Part 8: Quick-Start Guide for Next Developer

### To understand the system (read in this order):

1. **This file** (HANDOFF.md) — Overview
2. **INFORMATION_FLOW.md** — Data flow explanation
3. **faction_system.py** — Read the method signatures and docstrings (not all implementation)
4. **schema.py** — Understand database structure
5. **models.py** — Review dataclasses
6. **PHASE_2_ARCHITECTURE.md** — Design principles
7. **LLM_INTEGRATION.md** — Prompt design and tool definitions

### To run tests:

```bash
cd Game-1-modular
python -m pytest world_system/living_world/factions/test_faction_phase2plus.py -v
```

### To start Phase 3A (NPC Dialogue):

1. Read `LLM_INTEGRATION.md` § 1 (NPC Dialogue)
2. Examine `npc_agent.py` and `backend_manager.py` (existing code)
3. Implement `_assemble_faction_context()` in npc_agent.py
4. Add `generate_dialogue()` method to BackendManager
5. Test with mock faction data
6. Refine prompts based on dialogue quality

### To debug:

```python
# Check FactionSystem state
from world_system.living_world.factions import FactionSystem

faction_sys = FactionSystem.get_instance()
faction_sys.initialize()

# Get NPC profile
npc = faction_sys.get_npc_profile("npc_id")
print(f"NPC: {npc.narrative}")
print(f"Tags: {npc.belonging_tags}")
print(f"Affinity toward player: {faction_sys.get_npc_affinity_toward_player('npc_id')}")

# Get player affinities
affinities = faction_sys.get_all_player_affinities("player_1")
print(f"Player affinities: {affinities}")

# Get location defaults
inherited = faction_sys.compute_inherited_affinity([
    ("locality", "village"),
    ("district", "district_id"),
    ("nation", "nation_id"),
    ("world", None)
])
print(f"Inherited defaults: {inherited}")
```

### Common Pitfalls

⚠️ **Affinity not changing**: Check that consolidator is calling `adjust_player_affinity()` (not just returning values).

⚠️ **Database not updating**: Verify FactionSystem.initialize() was called. Check db_path in config.

⚠️ **Dialogue ignoring affinity**: Check that affinity values are passed to LLM in prompt. Verify system prompt includes affinity-tone mapping.

⚠️ **Log-scale calculations**: Difficulty 15 should result in ~12-15 affinity delta (not 150). If too high, check LLM is understanding "log scale" correctly.

⚠️ **Consolidator over-writing**: Ensure Quest Tool does NOT provide affinity deltas; consolidator is the authority.

---

## Part 9: Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FACTION SYSTEM (PHASE 2-3)                      │
└─────────────────────────────────────────────────────────────────────────┘

                          ┌──────────────────────────────────┐
                          │   NPC Dialogue (Phase 3A)        │
                          │   Real-time LLM via             │
                          │   BackendManager.                │
                          │   generate_dialogue()            │
                          └────────────┬─────────────────────┘
                                       │
                        ┌──────────────▼────────────────────┐
                        │ FactionSystem.                    │
                        │ assemble_dialogue_context()       │
                        │ Returns: npc + player + location  │
                        └────────────┬─────────────────────┘
                                     │
                    ┌────────────────▼─────────────────┐
                    │ LLM Generates Dialogue           │
                    │ (Affinity-aware tone)            │
                    └────────────┬──────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │ Quest Tool (Phase 3B)           │
                    │ Tool-calling LLM                │
                    │ Returns: Quest JSON             │
                    └────────────┬──────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │ Affinity Consolidator (3C)      │
                    │ Tool-calling LLM                │
                    │ Input: dialogue + quest +       │
                    │        completion data          │
                    │ Output: affinity changes        │
                    └────────────┬──────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │ FactionSystem.                  │
                    │ adjust_player_affinity()        │
                    │ adjust_npc_affinity_toward_     │
                    │ player()                        │
                    │ → Database Updated              │
                    └────────────┬──────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │ GameEventBus.publish()          │
                    │ FACTION_AFFINITY_CONSOLIDATED   │
                    └────────────┬──────────────────────┘
                                 │
              ┌──────────────────┴──────────────────────┐
              │                                         │
        ┌─────▼──────┐                    ┌────────────▼─────┐
        │ Next        │                    │ (Future) WMS      │
        │ Dialogue    │                    │ Integration       │
        │ Reflects    │                    │ (FactionRepEval)  │
        │ New         │                    │                   │
        │ Affinity    │                    │                   │
        └─────────────┘                    └───────────────────┘


DATABASE LAYER (Phase 2):
┌──────────────────────────────────────────────────────────────┐
│ SQLite (faction.db)                                          │
├──────────────────────────────────────────────────────────────┤
│ npc_profiles                                                 │
│ npc_belonging_tags                                           │
│ npc_affinity  (includes reserved tag `_player` row per NPC)  │
│ player_affinity                                              │
│ location_affinity_defaults                                   │
│ faction_schema_version                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## Part 10: Success Criteria

Phase 3 is complete when:

- ✅ NPC dialogue generates with affinity-aware tone
- ✅ Quest tool produces valid quests (difficulty, tags, metadata)
- ✅ Quest completion triggers consolidator
- ✅ Consolidator calculates affinities (log scale, diminishing returns applied)
- ✅ Affinity changes written to database
- ✅ Next dialogue reflects new affinity
- ✅ Events published to GameEventBus (`FACTION_AFFINITY_CONSOLIDATED`)
- ✅ Full integration test passes: dialogue → quest → consolidation → affinity
- ✅ Manual testing: Multiple NPC interactions, verify tone shifts with affinity
- ✅ Code comments explain design (especially log-scale, consolidator role, affinity tracks)
- ✅ No breaking changes to existing systems (NPC agent, BackendManager)

---

## Part 11: Contact & Questions

If continuing this work:

1. **Understand affinity scales first**: Player, NPC-toward-tags, NPC-toward-player are orthogonal (-100 to 100). Significance (belonging) is 0-1.

2. **Consolidator is the authority**: Never estimate affinity in quest system; let consolidator calculate based on difficulty × relevance × quality.

3. **Dialogue is read-only**: No affinity changes from dialogue choices (Phase 3). Player personality test comes first (Phase 4+).

4. **Log-scale thinking**: Difficulty 15 → ~12-15 affinity change. Difficulty 30 → ~25-30. Not linear.

5. **Sparse storage wins**: Only non-zero values in database. Reduces size, simplifies queries. Default is 0 (neutral).

---

**Prepared**: April 18, 2026  
**Next Action**: Begin Phase 3A (NPC Dialogue Integration)  
**Estimated Duration**: 4 weeks (A: 1 week, B: 1.5 weeks, C: 1 week, D: 0.5 week, E: 1 week)

---

## Appendix: File Reference

### Core Files

**faction_system.py**
- `FactionSystem.get_instance()` — Singleton accessor
- `FactionSystem.initialize()` — Create DB, bootstrap defaults
- `get_npc_profile(npc_id)` — Retrieve NPC with tags + affinity
- `adjust_player_affinity(player_id, tag, delta)` — Write affinity change
- `get_npc_affinity_toward_player(npc_id)` — Get NPC's personal opinion
- `compute_inherited_affinity(hierarchy)` — Sum location defaults

**schema.py**
- `FactionDatabaseSchema.create_all_tables(connection)` — Initialize DB
- `BOOTSTRAP_LOCATION_AFFINITY_DEFAULTS` — Hardcoded defaults (to be LLM)

**models.py**
- `FactionTag` — Belongs tag definition
- `NPCProfile` — Complete NPC with tags + affinity
- `PlayerProfile` — Player's faction affinities
- `LocationAffinityDefault` — Location cultural baseline
- `NPCAffinityTowardPlayer` — NPC's personal opinion

### Documentation

- **INFORMATION_FLOW.md** — Start here for understanding data flow
- **LLM_INTEGRATION.md** — Prompt design and tool definitions
- **PHASE_2_ARCHITECTURE.md** — Design principles and constraints
- **IMPLEMENTATION_STATUS.md** — Phase checklist and roadmap

### Testing

- **test_faction_phase2plus.py** — All unit and integration tests

---

**END OF HANDOFF DOCUMENT**
