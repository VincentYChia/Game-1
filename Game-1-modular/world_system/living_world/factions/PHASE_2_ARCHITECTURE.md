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

### Recording (Primary)
```
Game Event (QUEST_COMPLETED, ENEMY_KILLED, etc.)
    ↓
Quest/Combat System publishes to GameEventBus
    ↓
ReputationRulesEngine.apply_rules(event_type, npc_tags)
    ↓
Returns: tag → delta map
    ↓
FactionSystem.adjust_player_affinity(player_id, tag, delta)
    ↓
Database updated; FACTION_REP_CHANGED event published
    ↓
WMS FactionReputationEvaluator listens, consolidates into narrative
```

### Retrieval (For Dialogue)
```
NPC dialogue requested
    ↓
FactionSystem.get_npc_profile(npc_id)
    ↓ (returns: narrative + belonging_tags + npc_affinity)
NPC Dialogue Context built:
  - NPC narrative + tags
  - Player affinity with NPC's tags
  - Location affinity defaults (inherited from address hierarchy)
    ↓
Passed to LLM (Claude via BackendManager) for dialogue generation
    ↓
Dialogue tone modulated by affinity (high affinity = friendly, etc.)
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

## Reputation Rules Engine

Simple rule matching: when event E occurs with NPC having tag pattern T, apply delta D.

**Example rules**:
- QUEST_COMPLETED, target_tag=*, → +10 to all NPC's belonging tags
- ENEMY_KILLED, target_tag=allegiance:*, → -5 to member's allegiance
- ITEM_CRAFTED, target_tag=guild:*, → +2 to guild:crafters

Rules are:
- Event-type driven (QUEST_COMPLETED, ENEMY_KILLED, ITEM_CRAFTED, etc.)
- Pattern-matched on NPC's belonging tags
- Produce tag → delta map

Currently hardcoded; will load from JSON later.

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
- `schema.py` — SQLite table definitions
- `models.py` — Python dataclasses (NPCProfile, PlayerProfile, FactionTag, LocationAffinityDefault)

**Core Logic**:
- `faction_system.py` — FactionSystem singleton, all CRUD operations
- `reputation_rules.py` — ReputationRulesEngine, event → delta mapping

**Integration**:
- `__init__.py` — Initialization functions
- `test_faction_phase2plus.py` — Comprehensive test suite

**Config**:
- `tag-registry.json` (Phase 1) — All valid tags
- `faction-archetypes.json` (Phase 1) — NPC creation seeds
- `location-affinity-defaults` (hardcoded in schema.py bootstrap, to be LLM-generated)

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

1. **Hardcoded rules**: Reputation rules are hardcoded; should load from JSON
2. **No multi-character support**: Using "player" as placeholder; should be character save slot ID
3. **Location defaults bootstrap**: Hardcoded in schema.py; should be generated by LLM or loaded from config
4. **No NPC generation**: NPC creation still manual; future: LLM-driven with narrative → tags
