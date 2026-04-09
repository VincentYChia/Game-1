# World Memory System — Layer 1-2 Redesign Decisions

**Date**: 2026-04-09  
**Status**: Design finalized, implementation pending  
**Scope**: Layer 1 schema (DONE), prompt system (designed), temporal store (designing)

---

## 1A. Fact Recording Criteria (RESOLVED)

### What Gets Recorded in the Fact Store

The system uses a **two-tier filter** on GameEventBus events:

**Tier 1 — Skip visual-only events** (5 events dropped):
`SCREEN_SHAKE`, `PARTICLE_BURST`, `FLASH_ENTITY`, `ATTACK_PHASE`, `ATTACK_STARTED`

**Tier 2 — Only mapped events recorded** (28 bus events → 16 memory types):

| Bus Event | Memory Type | Frequency |
|-----------|------------|-----------|
| DAMAGE_DEALT | attack_performed | High (combat) |
| PLAYER_HIT | damage_taken | High (combat) |
| ENEMY_KILLED | enemy_killed | Medium |
| PLAYER_DIED | player_death | Rare |
| DODGE_PERFORMED | dodge_performed | Medium (combat) |
| STATUS_APPLIED | status_applied | Medium (combat) |
| RESOURCE_GATHERED | resource_gathered | Medium |
| NODE_DEPLETED | node_depleted | Low |
| ITEM_CRAFTED | craft_attempted | Low |
| ITEM_INVENTED | item_invented | Rare |
| RECIPE_DISCOVERED | recipe_discovered | Rare |
| ITEM_ACQUIRED | item_acquired | Medium |
| EQUIPMENT_CHANGED / ITEM_EQUIPPED | item_equipped | Low |
| REPAIR_PERFORMED | repair_performed | Low |
| LEVEL_UP | level_up | Rare |
| SKILL_LEARNED | skill_learned | Rare |
| SKILL_ACTIVATED | skill_used | High (combat) |
| TITLE_EARNED | title_earned | Rare |
| CLASS_CHANGED | class_changed | Rare |
| CHUNK_ENTERED | chunk_entered | Medium (exploration) |
| AREA_DISCOVERED | area_discovered | Rare |
| NPC_INTERACTION | npc_interaction | Low |
| QUEST_ACCEPTED | quest_accepted | Low |
| QUEST_COMPLETED | quest_completed | Low |
| QUEST_FAILED | quest_failed | Rare |
| WORLD_EVENT | world_event | Rare |
| POSITION_SAMPLE | position_sample | Every ~10 real seconds |

### What is NOT Recorded

- **Individual player steps/tile movement**: No `PLAYER_MOVED` event exists. Movement is tracked as:
  - `CHUNK_ENTERED` — fires at 16×16 chunk boundaries (~every 2-3 seconds while exploring)
  - `POSITION_SAMPLE` — periodic breadcrumb every ~10 real seconds
  - `StatTracker.record_movement()` — accumulates `exploration.distance` in StatStore (aggregate only)
- **Menu clicks, camera, UI interactions**: No bus events exist for these
- **Individual attack frames/animations**: Filtered by SKIP_BUS_EVENTS
- **Any event not in BUS_TO_MEMORY_TYPE mapping**: Silently dropped

### Performance Impact

At peak gameplay (active combat): ~10 events/minute  
At exploration: ~2-3 events/minute  
At idle/menu: ~0.1 events/minute (position samples only)  
Average mixed play: ~5 events/minute  

Each event = ~18 SQL operations across StatStore + Fact Store.  
SQLite WAL mode capacity: 10,000+ ops/sec.  
**Actual usage: <2% of SQLite capacity. Not a bottleneck.**

### Source of Truth References

- Filter logic: `world_system/world_memory/event_schema.py` (BUS_TO_MEMORY_TYPE, SKIP_BUS_EVENTS)
- Recording pipeline: `world_system/world_memory/event_recorder.py` (_on_bus_event method)
- Bus subscription: Priority -10 (runs before all other handlers)

---

## 1B. Tag-Based Prompt Fragment System

### Purpose

Layer 2 evaluators will call an LLM (Claude as stopgap, local model as target) to produce
one-sentence factual narrations. The LLM needs enough context to narrate accurately without
misinterpreting the data. The prompt system provides this context via **modular fragments
selected by tags**.

### Architecture

```
ASSEMBLED PROMPT = core_context          (always included)
                 + domain_fragment       (one per trigger, selected by domain: tag)
                 + entity_fragments      (0-3, selected by species:/resource:/discipline: etc.)
                 + data_block            (dynamic, assembled from StatStore + temporal data)
                 + output_instruction    (always included)
```

### Fragment Categories and Counts

| Category | Tag Pattern | Count | Purpose |
|----------|-----------|-------|---------|
| Core | `_core` | 1 | Game description, tier system, world basics |
| Output | `_output` | 1 | Format instructions for the LLM |
| Domain | `domain:*` | 10 | Evaluator lens (combat, gathering, crafting, etc.) |
| Species | `species:*` | 13 | Enemy descriptions (tier, biome, behavior) |
| Material Category | `material_category:*` | 5 | Resource type context (ore, tree, stone, plant, fish) |
| Discipline | `discipline:*` | 6 | Craft discipline mechanics |
| Tier | `tier:*` | 4 | Significance scaling context |
| Element | `element:*` | 8 | Damage type implications |
| Rank | `rank:*` | 3 | Enemy rank significance (normal, boss, unique) |
| Status Effect | `status_effect:*` | 13 | Effect type context (DoT, CC, buff) |
| **Total** | | **64** | |

Each fragment is 1-3 sentences (~10-40 tokens). A typical assembled prompt uses 4-5 fragments
totaling ~180-250 system tokens + ~100-150 data block tokens = **~300-400 tokens input**.

### Fragment Selection Logic

```python
FRAGMENT_CATEGORIES = {"species", "material_category", "discipline", 
                       "tier", "element", "rank", "status_effect"}

def select_fragments(trigger_tags, fragment_library):
    selected = [fragment_library["_core"]]
    
    # Domain (required — exactly one)
    for tag in trigger_tags:
        if tag.startswith("domain:") and tag in fragment_library:
            selected.append(fragment_library[tag])
            break
    
    # Entity/context (optional — add all matching)
    for tag in trigger_tags:
        cat = tag.split(":")[0]
        if cat in FRAGMENT_CATEGORIES and tag in fragment_library:
            selected.append(fragment_library[tag])
    
    selected.append(fragment_library["_output"])
    return [f for f in selected if f]
```

### Fallback Chain

When a tag has no matching fragment:
1. `species:new_enemy` → not found → fall back to `tier:N` (from enemy data)
2. `resource:new_material` → not found → fall back to `material_category:X`
3. `discipline:new_craft` → not found → fall back to `domain:crafting`
4. If all fail → domain fragment alone provides sufficient context

### Auto-Expansion (Future Feature)

When the game encounters an entity with no matching fragment:

1. System detects missing fragment for tag `species:void_horror`
2. Reads the entity's game data from JSON definitions (tier, biome, attack types, description)
3. Calls BackendManager with a meta-prompt containing:
   - Full game context (the `_core` fragment)
   - The entity's game data
   - Examples of existing fragments for similar entities
   - Instruction: "Write a 1-2 sentence fragment describing this entity for narration context"
4. Stores the generated fragment in `prompt_fragments.json` indexed by `species:void_horror`
5. All future evaluator triggers for this entity use the generated fragment

**Key requirement**: The meta-prompt must include comprehensive game context so the generated
fragment is accurate. The `_core` fragment + relevant domain fragment + entity game data
provides this. The LLM generating the fragment should be the most capable available model
(Claude), not the fast local model, since fragment generation is rare (once per new entity)
and accuracy matters more than speed.

**Indexing**: Fragments are always indexed by a single tag string (`species:X`, `tier:N`, etc.).
This means any game system that produces tagged data automatically integrates with the prompt
system. No manual wiring needed — the tag IS the index.

### Storage

File: `world_system/config/prompt_fragments.json`

Structure:
```json
{
  "_meta": {
    "version": "1.0",
    "total_fragments": 64,
    "auto_generation": {
      "enabled": false,
      "meta_prompt_includes": ["_core", "relevant domain fragment", "entity game data"],
      "preferred_model": "claude (high accuracy, infrequent calls)",
      "index_by": "tag string"
    }
  },
  "_core": "...",
  "_output": "...",
  "domain:combat": "...",
  "species:wolf_grey": "...",
  "tier:1": "..."
}
```

### Integration Points

- **StatStore** provides the data block (tag-based queries for relevant stats)
- **Temporal store** provides trend/recency data (today, week average, trend)
- **BackendManager** routes LLM calls (Claude → Ollama → Mock fallback)
- **Evaluator infrastructure** decides WHEN to call (threshold triggers)
- **Fragment library** decides WHAT context to include (tag matching)

---

## Section 3 Decisions (Resolved)

### Counters — REMOVED

The following tables are confirmed redundant and will be removed:

| Table | Why Redundant |
|-------|--------------|
| `occurrence_counts` | StatStore has same data (e.g., `combat.kills.species.wolf = 47`). TriggerManager does its own in-memory counting. This table is written to but read by nobody. |
| `regional_counters` | Never written to by any code. Dead table. |
| `interpretation_counters` | Never written to by any code. Dead table. |

### Consumer/State Tables — MOVED TO CONSUMERS

| Table | New Home |
|-------|---------|
| `npc_memory` | NPCMemoryManager (already manages this data in-memory) |
| `faction_state`, `faction_reputation_history` | FactionSystem (already manages this) |
| `biome_resource_state` | EcosystemAgent (already manages this) |
| `entity_state` | EntityRegistry (in-memory) |
| `region_state` | GeographicRegistry (in-memory) |

### Trigger Tables — REMOVED

| Table | Why |
|-------|-----|
| `event_triggers` | Never written to. Dead code. |
| `pacing_state` | Never written to. Dead code. |

### Layer 2+ Tables — MOVED TO LAYERSTORE

| Table | Already Exists In LayerStore |
|-------|-----|
| `interpretations`, `interpretation_tags` | `layer2_events`, `layer2_tags` |
| `connected_interpretations`, `connected_interpretation_tags` | `layer3_events`, `layer3_tags` |
| `province_summaries` | `layer4_events` |
| `realm_state` | `layer5_events` |
| `world_narrative`, `narrative_threads` | `layer7_events` |

### What Remains — Temporal Fact Store (designing)

See "Temporal Calculations" section below (in progress).
