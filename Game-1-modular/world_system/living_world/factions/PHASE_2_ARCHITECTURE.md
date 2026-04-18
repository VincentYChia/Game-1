# Faction System Phase 2+ Architecture

**Status**: Implemented (Phase 2-3 complete, Phase 4-6 designed)  
**Date**: 2026-04-18  
**Model**: Recording + Inheritance (not multi-axis, not decay, not ripples)

## Core Principles

This is a **recording system parallel to WMS**, not a behavior simulator.

- **Recording layer**: Events → affinity deltas → tables (primary direction)
- **Retrieval layer**: NPC affinity + location defaults → dialogue context (rare, high-level)
- **Sparse storage**: Only non-zero values stored; defaults inherited hierarchically
- **Single affinity**: One float per tag (-100 to 100), not multi-axis
- **No decay, no ripples, no milestones**: These emerge from WMS consolidation

## Data Model

### NPC Profile
```
npc_profiles:
  npc_id (PK)
  narrative (TEXT)
  created_at, last_updated (REAL)

npc_belonging_tags:
  npc_id, tag (PK)
  significance (0-1) — structural weight
  role (TEXT, optional) — "master", "member", etc.
  narrative_hooks (JSON) — specific facts for LLM
  since_game_time (REAL)

npc_affinity:
  npc_id, tag (PK)
  affinity_value (-100 to 100) — how NPC feels about tag
  last_updated (REAL)
```

**Key**: NPC has two affinity-like concepts:
- **Belonging tags**: what defines them (0-1 significance)
- **Personal affinity**: how they feel about other tags (-100 to 100)

### Player Profile
```
player_affinity:
  player_id, tag (PK)
  affinity_value (-100 to 100) — player's standing with tag
  last_updated (REAL)
```

Sparse: only non-zero values stored. Default is 0.

### Location Affinity Defaults (Cultural Defaults)
```
location_affinity_defaults:
  address_tier, location_id, tag (PK)
  significance (0-1) — cultural default for tag at this location

address_tier ∈ {"world", "nation", "region", "province", "district", "locality"}
location_id = NULL for world tier, else actual location ID
```

**Inheritance**: When querying, walk hierarchy and sum all matching defaults.
- Locality defaults override district
- District defaults override region
- Etc.

## Information Flow

**See INFORMATION_FLOW.md for detailed, simplified explanation.**

### Recording (Primary)
```
Game Event (Quest Completion, Combat, etc.)
    ↓
Quest/Combat System provides affinity deltas directly
    ↓
FactionSystem.adjust_player_affinity(player_id, tag, delta)
    ↓
Database updated (sparse: only non-zero)
    ↓
FACTION_REP_CHANGED event published
    ↓
WMS FactionReputationEvaluator listens, produces InterpretedEvent
```

### Retrieval (For Dialogue)
```
NPC dialogue requested
    ↓
NPC Agent gathers context:
  - get_npc_profile(npc_id) → narrative + belonging_tags
  - get_all_player_affinities(player_id) → player standing with tags
  - get_npc_affinity_toward_player(npc_id) → NPC's personal opinion
  - compute_inherited_affinity(hierarchy) → location cultural baseline
    ↓
Assemble context dict
    ↓
Pass to BackendManager.generate_dialogue()
    ↓
Dialogue returned to game (tone modulated by affinity)
```

## Significance Buckets (0-1 Scale)

Ten-point log scale, scale-agnostic (works for kingdom, guild, village):

| Value | Term | Meaning |
|-------|------|---------|
| 1.0 | Nucleus | Center; group forms around them |
| 0.9 | Inner Circle | Innermost; group built around them |
| 0.8 | Pillar | Principal upholder |
| 0.7 | Fixture | Permanent, reliable presence |
| 0.6 | Devoted | Chosen deep commitment |
| 0.5 | Active | Regularly participating |
| 0.4 | Involved | Present, taking part |
| 0.3 | Member | Baseline belonging |
| 0.2 | Affiliate | Loose tie |
| 0.1 | Nominal | In name only |

## Reputation Delta Estimation

**Removed**: ReputationRulesEngine class (no longer needed)

**New Pattern**:
- Quest system directly provides affinity delta estimates when quest completes
- Example: `quest.get_affinity_deltas()` → `{"guild:smiths": +10, "profession:blacksmith": +5}`
- FactionSystem records these deltas immediately

**Affinity Consolidation** (WMS Layer 2):
- WMS evaluator refines delta estimates with context factors:
  - Time elapsed since quest completion
  - Quality of work (if relevant)
  - Player's past behavior with that faction
- Produces consolidated narrative for higher WMS layers

## WMS Integration (Layer 2)

FactionReputationEvaluator:
- Listens to FACTION_REP_CHANGED events (published when affinity changes)
- Produces InterpretedEvent with rich tags:
  - domain:faction
  - faction:{tag}
  - rep_direction:{improved|worsened}
  - rep_magnitude:{minor|moderate|major}
  - source_event_id (link back to original event)

Example narrative:
> "The player's standing with guild:smiths has improved."

Feeds into WMS Layer 3-7 consolidation pipeline.

## What's NOT Here (Deferred)

- **Multi-axis reputation** (trust, respect, fear): Single affinity per tag
- **Affinity decay**: Time-based degradation (designed in Phase 6, deferred)
- **Ripple effects**: When affinity with A changes, B changes proportionally (designed in Phase 6, deferred)
- **Milestones**: Special events at thresholds (designed in Phase 6, deferred)
- **Affinity tiers**: Unlocking quests/interactions at thresholds (designed in Phase 6, deferred)

These emerge naturally from WMS consolidation + dialogue + quest generation logic. Don't hardcode them in faction system.

## Files (Phase 2-3)

**Schema & Data**:
- `schema.py` — SQLite table definitions (8 tables + indexes)
- `models.py` — Python dataclasses (FactionTag, NPCProfile, PlayerProfile, LocationAffinityDefault, NPCAffinityTowardPlayer)

**Core Logic**:
- `faction_system.py` — FactionSystem singleton, all CRUD operations (17 methods)
- `__init__.py` — Initialization and save/restore functions

**Testing**:
- `test_faction_phase2plus.py` — Comprehensive test suite (4 test classes, 11 test methods)

**Documentation** (NEW):
- `PHASE_2_ARCHITECTURE.md` — This file, high-level design (you are here)
- `INFORMATION_FLOW.md` — Detailed data flow explanation (READ FIRST for understanding)
- `LLM_INTEGRATION.md` — LLM prompts, payloads, integration patterns

**Config** (Phase 1, external):
- `tag-registry.json` — All valid tags
- `faction-archetypes.json` — NPC creation seeds
- `location-affinity-defaults` — Bootstrapped in schema.py, to be LLM-generated

## Pending (Phase 4-6)

**Phase 4**: NPC dialogue integration (existing `faction_dialogue_generator.py` needs refactor)
**Phase 5**: LLM integration via BackendManager (already exists, needs wiring)
**Phase 6**: Advanced features (tiers, ripples, decay, milestones) — deferred by design

## Testing

Test suite covers:
- NPC profile CRUD (add, retrieve, update tags)
- Player affinity operations (set, adjust, get all)
- Location affinity defaults and inheritance
- Reputation rules engine
- Integration workflow (quest → NPC tags → deltas → affinity)

Run with:
```bash
python -m pytest world_system/living_world/factions/test_faction_phase2plus.py -v
```

## Known Limitations

1. **Location affinity defaults**: Hardcoded in schema.py BOOTSTRAP_LOCATION_AFFINITY_DEFAULTS; future: LLM-generated via LLM_INTEGRATION.md § 2
2. **NPC dialogue not yet wired**: Faction context available, but not yet integrated into NPC agent dialogue generation
3. **NPC creation**: Still manual; future: LLM-driven via LLM_INTEGRATION.md § 3
4. **No multi-character support**: Using "player_1" as placeholder; should be character save slot ID
5. **Location affinity refinement**: Quest/combat systems need to call adjust_player_affinity(); WMS consolidator will refine values

## What's Ready (Phase 2 Complete)

- ✅ Complete database schema (8 tables)
- ✅ All data models (5 dataclasses)
- ✅ FactionSystem CRUD (17 methods covering all operations)
- ✅ Sparse storage (only non-zero values)
- ✅ Hierarchical location affinity (compute_inherited_affinity with summing)
- ✅ NPC affinity toward player (separate per-NPC opinion track)
- ✅ Test suite (4 test classes, 11 test methods)
- ✅ Information flow documentation (clear, simplified)
- ✅ LLM integration documentation (prompts, payloads, patterns)

## What's Needed (Phase 3+)

- [ ] Wire quest system to call adjust_player_affinity()
- [ ] Wire NPC agent to gather context and call BackendManager for dialogue
- [ ] Implement location affinity generation (LLM § 2)
- [ ] Implement NPC creation pipeline (LLM § 3)
