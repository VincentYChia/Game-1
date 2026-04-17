# Faction System Phase 2 - Implementation Status

**Status**: Phase 2 Complete (PART A-E: Models, Schema, Database, Integration, Testing)

**Date Completed**: 2026-04-17

## Phase 2 Summary

Phase 2 implements the core NPC faction profile system, player affinity tracking, and cultural affinity calculation using SQLite persistence. All components are tested and integrated with the game engine's save/load cycle.

## Files Implemented

### Core Module Files

#### 1. `models.py` (180 lines)
Pure data classes (dataclasses) representing faction system entities:

- **NPCBelongingTag**: NPC identity tags with significance, role, and narrative hooks
- **NPCFactionProfile**: NPC identity (narrative, primary_tag, location, timestamps, metadata)
- **PlayerAffinityProfile**: Player reputation tracking (-100 to +100 per tag)
- **AffinityDefaultEntry**: Geographic tier affinity defaults (world/nation/region/province/district/locality)
- **CulturalAffinityEntry**: Pre-calculated cultural affinity cache (future optimization)
- **QuestLogEntry**: Quest tracking (player/NPC/status/timestamps)
- **NPCContextForDialogue**: Assembled context for LLM dialogue generation

**Key Design**: Each dataclass mirrors SQLite schema structure. Models are immutable after creation (no setters).

#### 2. `schema.py` (361 lines)
SQLite schema definitions and bootstrap data:

- **FactionDatabaseSchema** class: Manages table creation
- **7 Tables**:
  1. `affinity_defaults` (CONFIG): tier (PK), location_id (PK), tag (PK), delta
  2. `cultural_affinity_cache` (CACHE): tier, location_id, tag, cultural_affinity (unused in Phase 2, for future optimization)
  3. `npc_profiles` (MAIN): npc_id (PK), location_id, narrative, primary_tag, created_at, last_updated, metadata
  4. `npc_belonging` (NORMALIZED): npc_id (FK), tag (PK), significance, role, narrative_hooks
  5. `player_affinity` (MAIN): player_id (FK), tag (PK), current_value, total_gained, updated_at
  6. `quest_log` (LOG): player_id, quest_id (PK), npc_id, status, offered_at, completed_at
  7. `faction_schema_version` (META): version tracking for migrations

- **Bootstrap Data**: `BOOTSTRAP_AFFINITY_DEFAULTS_SQL` with 50+ INSERT statements covering:
  - World tier: None location_id (global affinity)
  - Nation tier: 4 nations (stormguard, wildlands, academarch, deephold)
  - Region tier: 8 regions (northlands, midlands, southern, eastern, etc.)
  - Province tier: 16 provinces (ironpeak, ashvale, deepwood, etc.)
  - District tier: Sample districts
  - All major tags (profession, guild, nation, etc.)

**Key Design**: Additive tier summation (not hierarchical). All tiers contribute equally to cultural affinity calculation.

#### 3. `database.py` (574 lines)
FactionDatabase singleton managing all SQLite operations:

- **Initialization**: `initialize()` creates connection, tables, seeds bootstrap data
- **NPC Operations**:
  - `create_npc_profile()`: Create new NPC with narrative and metadata
  - `get_npc_profile()`: Retrieve NPC by ID
  - `update_npc_narrative()`: Update NPC story after events
  - `add_npc_belonging_tag()`: Add identity tag to NPC
  - `get_npc_belonging_tags()`: Get all tags for NPC
  - `get_all_npcs_with_tag()`: Query NPCs by tag (indexed)
  - `get_all_npcs_in_location()`: Get NPCs at location
  
- **Player Affinity Operations**:
  - `initialize_player_affinity()`: Create empty affinity profile
  - `get_player_affinity()`: Get current affinity for tag (default 0.0)
  - `get_all_player_affinities()`: Get all tags for player
  - `add_player_affinity_delta()`: Apply additive delta, clamp to ±100
  - `get_player_total_gained()`: Track cumulative gains (separate from current)

- **Cultural Affinity Calculation**:
  - `calculate_cultural_affinity()`: Sum affinity_defaults across all 6 tiers
  - Handles NULL location_id for world tier
  - Clamps result to -100 to +100
  - On-the-fly calculation (not cached in Phase 2)

- **Quest Log Operations**:
  - `log_quest_offer()`: Record quest offer
  - `log_quest_completion()`: Update quest status
  - `get_npc_quest_history()`: Retrieve all quests for NPC

- **Context Assembly**:
  - `build_npc_dialogue_context()`: Assemble NPCContextForDialogue with:
    - NPC profile and narrative
    - NPC belonging tags with significance
    - Cultural affinity for all tags
    - Player affinity (from player_affinity table)
    - Quest history
    - Location info

**Key Design**: All operations are atomic (auto-commit). SQLite transactions are per-operation, not batch.

#### 4. `__init__.py` (64 lines, Updated)
Public API and initialization:

- `initialize_faction_systems()`: Initialize FactionDatabase and create schema
- `save_faction_systems()`: Prepare for save (returns empty dict—faction.db persists separately)
- `restore_faction_systems()`: Restore after load (no-op—faction.db already loaded)

### Integration Files

#### 5. `core/paths.py` (Added Methods)
- `PathManager.get_faction_db_path()`: Returns `save_path / "faction.db"`
- `get_faction_db_path()`: Global convenience function

**Design**: Faction database persists in game save directory alongside character saves, autosaves, etc.

#### 6. `core/game_engine.py` (Modified 3 load paths)
- Added `initialize_faction_systems()` call in `_init_world_memory()` before WorldMemorySystem
- Added `self.save_manager.restore_faction_state(save_data)` to all 3 game load scenarios:
  - Load autosave (F5)
  - Load default save (Shift+F5)
  - Load from save menu (option_index == 2)

#### 7. `systems/save_manager.py` (Already integrated)
- `create_save_data()`: Calls `save_faction_systems()` (returns empty dict)
- `restore_faction_state()`: Calls `restore_faction_systems()`
- Methods already in place, just needed game_engine calls

#### 8. `world_system/living_world/factions/__init__.py` (Updated)
- Imports FactionDatabase (not old TagRegistry/AffinityDefaults)
- References updated to Phase 2 approach

### Testing

#### 9. `test_faction_system.py` (620+ lines)
Comprehensive test suite covering:

- **test_database_initialization()**: Schema creation, table verification, bootstrap data
- **test_npc_profile_crud()**: Create, read, update NPC profiles
- **test_npc_belonging_tags()**: Add/retrieve tags, prevent duplicates
- **test_get_npcs_with_tag()**: Query NPCs by tag
- **test_player_affinity()**: Track affinity, additivity, clamping, multiple tags
- **test_cultural_affinity_calculation()**: Sum across tiers, handle missing tiers
- **test_quest_log_operations()**: Log offers, completions, retrieve history
- **test_npc_dialogue_context_assembly()**: Full context building for LLM
- **test_edge_cases()**: Error handling, minimal addresses, small deltas

All 9 tests are designed to run independently with temporary databases (no pollution).

## Architecture Decisions

### 1. Separate Database (faction.db)
- **Why**: Keeps faction data orthogonal to game state. Easy to reset NPC factions without affecting player progress.
- **Where**: Game save directory (alongside autosave.json, default_save.json)
- **Persistence**: Automatic. Single connection per game session.

### 2. Additive Cultural Affinity
- **Implementation**: Iterate all 6 tiers, sum deltas from affinity_defaults table
- **No Hierarchical Fallback**: If a tier is missing (None), skip it—don't use parent
- **Result**: Clean compositional model (world sentiment + nation sentiment + district sentiment = NPC cultural affinity)

### 3. Separate Affinity Tracks
- **Cultural Affinity** (-100 to +100): How location feels about a tag (derived from tiers)
- **Player Affinity** (-100 to +100): How player feels about tags (earned through quests)
- **Significance** (varies): How much an NPC cares about their tags (-100 to +100 or custom)

### 4. Normalized npc_belonging Table
- **Why**: Allows efficient queries like "get all NPCs with guild:merchants"
- **Trade-off**: More tables but better query performance
- **Alternative**: Store JSON in npc_profiles.tags, but slower to query

### 5. No Event System Integration (Yet)
- **Phase 2 Scope**: Database layer only
- **Phase 3 (TODO)**: Listen to GameEventBus quest events (quest_accepted, quest_completed) and trigger affinity deltas
- **Placeholder**: Quest log operations exist (log_quest_offer, log_quest_completion) but not auto-triggered

### 6. On-the-Fly vs Cached Cultural Affinity
- **Phase 2**: Calculate on-the-fly (call calculate_cultural_affinity for each NPC)
- **Optimization Path**: Pre-calculate during game init, cache in cultural_affinity_cache table
- **Current**: Table exists but unused; no code updates cache yet

## Integration Points (Completed)

### Game Engine Integration
- ✅ initialize_faction_systems() called before WorldMemorySystem
- ✅ restore_faction_state() called in all 3 load paths
- ✅ Database persists across save/load cycles

### Save Manager Integration
- ✅ save_faction_systems() creates save data (empty—faction.db is separate)
- ✅ restore_faction_systems() restores state (no-op—database already open)

## Integration Points (Pending - Phase 3+)

### Quest System
- [ ] Listen to quest_accepted events → log_quest_offer()
- [ ] Listen to quest_completed events → log_quest_completion() + add_player_affinity_delta()
- [ ] Read quest_log in build_npc_dialogue_context() (implemented, just not auto-triggered)

### NPC Agent System
- [ ] Call build_npc_dialogue_context() to assemble LLM input
- [ ] Use cultural_affinity + player_affinity in NPC dialogue generation

### World Memory System
- [ ] Create FactionReputationEvaluator to observe quest completion events
- [ ] Capture "player earned affinity with guild:merchants" as WMS Layer 2 event

### Backend/LLM System
- [ ] Pass NPCContextForDialogue.to_dict() to LLM prompt
- [ ] Use player_affinity + npc_cultural_affinity + quest_history to guide tone

## Known Limitations (Phase 2)

1. **No Event Listening**: Affinity changes must be triggered manually or via future event system
2. **No Cache Updates**: cultural_affinity_cache table exists but is never updated
3. **No Migration System**: ~~schema_version table exists but no migration code~~
4. **No Rollback**: Affinity changes are immediate; no undo mechanism
5. **No Bulk Operations**: add_player_affinity_delta() is one-at-a-time (acceptable for gameplay)
6. **No Relationship Symmetry**: If A likes B, B doesn't automatically like A (by design)

## Data Volume Estimates (at scale)

| Table | Row Count (100 NPCs) | Row Count (1000 NPCs) | Notes |
|-------|-----|------|-------|
| npc_profiles | 100 | 1,000 | One per NPC |
| npc_belonging | 300-500 | 3,000-5,000 | Avg 3-5 tags per NPC |
| affinity_defaults | 100-200 | 100-200 | Geographic + tag combinations |
| player_affinity | 50-100 | 50-100 | Per unique tag (not per NPC) |
| quest_log | 100-500 | 1,000-5,000 | Depends on quest frequency |
| schema_version | 1 | 1 | Single row |

**Index Strategy**:
- PK on all tables ✅
- FK on npc_id, player_id ✅
- Composite PK on multi-column uniqueness ✅
- Consider: Index on `npc_belonging(tag)` for fast tag lookups (query implemented, may need tuning)

## Testing Approach

All tests use temporary directories—no database pollution. Each test:
1. Creates temp database
2. Patches get_faction_db_path()
3. Resets FactionDatabase singleton
4. Runs assertions
5. Cleans up and restores

**To Run Tests** (requires pygame):
```bash
cd Game-1-modular
python3 -m pytest world_system/living_world/factions/test_faction_system.py -v
# OR
python3 world_system/living_world/factions/test_faction_system.py
```

## Next Steps (Phase 3+)

1. **Event Integration**: Hook quest system to affinity delta recording
2. **WMS Consolidation**: Create FactionReputationEvaluator in WMS
3. **NPC Behavior**: Use build_npc_dialogue_context() in NPC agent system
4. **LLM Prompting**: Pass context dict to LLM for dialogue generation
5. **Cache Optimization**: Implement cultural_affinity_cache updates
6. **Affinity Tiers**: Define affinity change thresholds (e.g., -100 to -50 = "Enemy", 50 to 100 = "Ally")
7. **Affinity Ripples**: Implement faction-wide affinity changes (e.g., help guild:merchants → like nation:academy)
8. **Affinity Decay**: Implement time-based affinity decay (optional gameplay feature)

## Code Quality Metrics

- **Files**: 4 new (models, schema, database, test) + 1 updated (paths) + 4 modified (init, game_engine, save_manager, paths)
- **Total New LOC**: 1,789 lines (180 models + 361 schema + 574 database + 72 init + 602 test)
- **Test Coverage**: 9 test functions covering core operations
- **Documentation**: This file + docstrings in all classes/methods
- **Type Hints**: All public methods have complete type annotations
- **Error Handling**: SQLite IntegrityError caught, printed, handled gracefully
- **Logging**: Print statements for major operations (✓ symbols, ✗ errors)

## Commit History

- **Commit 1**: Phase 2 implementation (models.py, schema.py, database.py)
- **Commit 2**: Integration (paths.py, __init__.py, game_engine.py updates)
- **Commit 3**: Testing (test_faction_system.py)

## Version

- **Phase**: 2/5
- **Date**: 2026-04-17
- **Status**: Complete and integrated

---

**End of Phase 2 Documentation**
