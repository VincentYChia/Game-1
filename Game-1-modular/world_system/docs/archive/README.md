# World System

**Created**: 2026-03-24
**Scope**: Everything that makes the world feel alive — memory, AI agents, data collection, narrative

## Document Map

| Document | Purpose |
|----------|---------|
| **README.md** (this file) | Overview — data layers, agents, worked example |
| [LAYER_ARCHITECTURE.md](LAYER_ARCHITECTURE.md) | **7-layer hierarchy** — triggers, geographic scale, compression principle |
| [EVALUATOR_DESIGN.md](EVALUATOR_DESIGN.md) | Layer 3+4 evaluators — what they see, dual coverage, cross-domain |
| [STORAGE_SCHEMA.md](STORAGE_SCHEMA.md) | Every SQL table — Layers 2-7, data flow diagram |
| [RETRIEVAL_DESIGN.md](RETRIEVAL_DESIGN.md) | How data is queried — entity-first, tag scoring, distance filtering, gossip |
| [LIVING_WORLD_AI.md](LIVING_WORLD_AI.md) | Living world agents — backends, NPC, factions, ecosystem |
| [AI_TOUCHPOINT_MAP.md](AI_TOUCHPOINT_MAP.md) | Every place AI inference or interpretation fires |

---

## The 7-Layer Architecture (Summary)

Data compresses upward. Each layer condenses the one below into better information transfer. A consumer at Layer 5 never needs to read Layer 2 — the summaries encode everything relevant at that scale.

| Layer | Name | Scale | What it stores |
|:---:|-------|-------|---------------|
| 1 | Numerical Stats | Global | 850+ cumulative counters (stat_tracker.py) |
| 2 | Structured Events | Chunk/Locality | Timestamped facts in SQLite — WHO/WHAT/WHERE/WHEN |
| 3 | Simple Interpretations | Locality/District | One-sentence narratives from 9 evaluators |
| 4 | Connected Interpretations | District/Province | Cross-domain and cross-region pattern detection |
| 5 | Principality Summaries | Province | Gross summaries of provincial state |
| 6 | Regional/National State | Realm | Faction landscapes, economic state, player reputation |
| 7 | World State | World | Narrative threads, world identity, themes, history |

**Trigger cadence**: `1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000`
The biggest leaps happen at **1, 10, 100, 1000**. Triggers are opportunities to evaluate, not mandates to produce output.

**Full design**: [LAYER_ARCHITECTURE.md](LAYER_ARCHITECTURE.md)

---

## All Data the World System Stores

Seven layers, each serving a different purpose.

### Layer 1 — StatTracker (cumulative counters, pre-existing)

**File**: `entities/components/stat_tracker.py` (~1,756 lines, 850+ stats)

The game already tracks *everything* the player does as aggregate counters. These are **totals** — no timestamps, no location, no sequence. Good for unlocks and UI. Useless for narrative.

| Category | Example stats | Count |
|----------|-------------|:---:|
| **Gathering** | `total_ores_mined`, per-resource counts, `tier_3_resources_gathered`, `axe_swings`, `longest_gather_streak` | ~50 |
| **Crafting** | Per-recipe `CraftingEntry` (attempts, successes, quality, timing), per-discipline breakdowns, `legendary_crafts`, `best_minigame_score` | ~80 |
| **Combat** | Damage dealt/taken by element (8 types), `total_kills`, tier breakdowns, `critical_hits`, `longest_killstreak`, per-status-effect counts | ~120 |
| **Items** | Per-item collection counts, `rare_drops_total`, `potions_consumed_in_combat`, `equipment_swaps` | ~30 |
| **Skills** | Per-skill `SkillStatEntry` (uses, damage, mana), `total_mana_spent`, skill unlock sources | ~30 |
| **Exploration** | `unique_chunks_visited`, distance by biome, `furthest_from_spawn`, `npcs_met` | ~20 |
| **Economy** | `gold_earned/spent` by source, `trades_made`, `items_bought/sold` | ~15 |
| **Progression** | EXP by source, `titles_earned` by tier, `class_changes`, `stat_points_allocated` | ~20 |
| **Time** | `total_playtime`, per-activity time, session tracking | ~15 |
| **Records** | `highest_damage_single_hit`, `fastest_boss_kill`, `best_exp_per_hour` | ~20 |
| **Social** | `npc_dialogues_completed`, quests started/completed/failed by type | ~15 |
| **Dungeons** | Entered/completed/abandoned by rarity, `fastest_clear`, `waves_completed` | ~25 |

Also: `ActivityTracker` — 8 simple counters (mining, forestry, smithing, refining, alchemy, engineering, enchanting, combat) used for title/skill unlock gates.

### Layer 2 — EventStore (timestamped facts, new)

**File**: `world_memory/event_store.py` — SQLite database per save slot

Every game action recorded as a structured row with WHO, WHAT, WHERE, WHEN:

```
events table:
  event_id, event_type, event_subtype,
  actor_id, actor_type, target_id, target_type,
  position_x, position_y, chunk_x, chunk_y,
  locality_id, district_id, province_id, biome,
  game_time, real_time, session_id,
  magnitude, result, quality, tier,
  context_json, tags[]
```

**What this adds over StatTracker**: Sequence, location, time, relationships. "Player killed 50 wolves" (StatTracker) vs "Player killed 12 wolves in Old Forest in the last 5 minutes, then moved to Iron Hills" (EventStore).

**Event types recorded** (28 mapped from GameEventBus):
```
Combat:    DAMAGE_DEALT, PLAYER_HIT, ENEMY_KILLED, PLAYER_DIED, DODGE_PERFORMED, STATUS_APPLIED
Skills:    SKILL_ACTIVATED
Resources: RESOURCE_GATHERED, NODE_DEPLETED
Crafting:  ITEM_CRAFTED, ITEM_INVENTED, RECIPE_DISCOVERED
Items:     ITEM_ACQUIRED, ITEM_EQUIPPED, EQUIPMENT_CHANGED, REPAIR_PERFORMED
Progress:  LEVEL_UP, SKILL_LEARNED, TITLE_EARNED, CLASS_CHANGED
World:     CHUNK_ENTERED, AREA_DISCOVERED, POSITION_SAMPLE
Social:    NPC_INTERACTION, QUEST_ACCEPTED, QUEST_COMPLETED, QUEST_FAILED
Meta:      WORLD_EVENT
```

**Not recorded** (filtered as visual noise): SCREEN_SHAKE, PARTICLE_BURST, FLASH_ENTITY, ATTACK_PHASE, ATTACK_STARTED

### Layer 3 — Simple Interpretations

**Files**: `world_memory/evaluators/*.py` — 9 evaluators (expanded from 5)

When occurrence counts hit milestone thresholds (1, 3, 5, 10, 25, 50, 100...), evaluators scan recent Layer 2 data and Layer 1 stats to produce one-sentence narratives.

| Evaluator | Question it answers | Example output |
|-----------|-------------------|----------------|
| Population Dynamics | What's happening to creature populations? | "Wolf population declining in Old Forest. 23 killed." |
| Ecosystem Pressure | Are resources being sustainably harvested? | "Iron ore nearly exhausted in Eastern Caves. 95% depleted." |
| Combat Proficiency | How capable is the player in combat? | "Flawless victory against T2 pack — no damage taken." |
| Crafting Mastery | What is the player's crafting identity? | "Dual specialty: smithing and enchanting both at 30+ crafts." |
| Player Milestones | Has the player achieved something notable? | "Level 10 reached. A significant milestone." |
| Exploration & Discovery | How is the player engaging geographically? | "25 unique areas explored. Well-traveled." |
| Social & Reputation | How is the player interacting with NPCs/factions? | "Village Guard: Recognized (0.28). Guards warming up." |
| Economy & Items | What is the player's economic behavior? | "Heavy potion usage — 8 consumed in recent fights." |
| Dungeon Progress | How is dungeon content going? | "3 rare dungeons completed. Taking on serious challenges." |

**Dual coverage is expected**: killing wolves triggers both Population ("wolves are dying") and Combat ("player is becoming a skilled hunter"). These serve different consumers.

**Full evaluator design**: [EVALUATOR_DESIGN.md](EVALUATOR_DESIGN.md)

### Layers 4-7 — Higher Interpretation Layers

| Layer | What it produces | Example |
|-------|-----------------|---------|
| 4 — Connected | Cross-domain patterns | "Player is plundering Iron Hills — both wildlife and resources under pressure." |
| 5 — Principality | Province-wide summaries | "Northern province largely cleared of wildlife. Heavy resource extraction." |
| 6 — National | Realm-wide state | Faction power balances, global resource scarcity, player reputation |
| 7 — World | Narrative threads, world identity | Active wars, plagues, discoveries. World themes and tone. |

Each layer can see two layers down. Layer 4 sees Layer 3 (full) and Layer 2 (limited). This prevents upper layers from needing raw event streams while still grounding them in reality.

### SQL Tables

| Table | Layer | Purpose |
|-------|:---:|---------|
| `events` + `event_tags` | 2 | Every game action as structured fact |
| `occurrence_counts` | 2 | Milestone trigger tracking |
| `interpretations` + `interpretation_tags` | 3 | One-sentence evaluator narratives |
| `connected_interpretations` | 4 | Cross-domain pattern narratives |
| `province_summaries` | 5 | Province-level state snapshots |
| `realm_state` | 6 | Realm-wide political/economic state |
| `world_narrative` + `narrative_threads` | 7 | World identity and active story threads |
| `npc_memory` | — | Per-NPC relationship, knowledge, conversation |
| `faction_state` + `faction_reputation_history` | — | Faction reputation audit trail |
| `biome_resource_state` | — | Ecosystem depletion tracking |
| `region_state` | — | Per-region active conditions |
| `entity_state` | — | Per-entity tag and activity persistence |

**Full schema**: [STORAGE_SCHEMA.md](STORAGE_SCHEMA.md)

---

## The AI Agents — What Each Does and How They Talk

Five systems subscribe to the GameEventBus. None import each other directly.

```
     GameEventBus
     ┌────┼────┬────────┬────────────┐
     │    │    │        │            │
   VFX  Faction Ecosystem EventRecorder
  (p10)  (p5)   (p5)     (p-10)
     │    │    │        │
     │    │    │    ┌───┴───┐
     │    │    │  SQLite  Interpreter
     │    │    │           │
     │    │    │   L3: 9 Evaluators
     │    │    │           │
     │    │    │   L4: 4 Connected
     │    │    │           │
     │    │    │     Region states
     │    │    │           │
     │    └────┼───────────┤
     │         │           │
     │    NPC Agent   WorldQuery
     │    (on demand)  (assembles
     │                  context)
     │         │
     │    BackendManager
     │    ollama→claude→mock
     │         │
     └─── Player sees dialogue
```

### Agent 1: EventRecorder — the journalist

Subscribes to every event (wildcard `"*"`, priority -10 = runs last). Converts bus events to structured WorldMemoryEvents with geographic context. Writes to SQLite. Triggers evaluators at milestone thresholds.

**Example**: Player gathers iron ore →
- EventRecorder stamps it with chunk (2,4), locality "iron_hills", biome "mountain"
- Increments occurrence count for (player, resource_gathered, gathered_iron_ore) → count=10
- 10 is a milestone threshold → triggers 9 Layer 3 evaluators
- EcosystemPressure evaluator checks depletion state → "Iron ore under heavy pressure in Iron Hills"
- Combat evaluator: not relevant, skips
- Narrative stored as InterpretedEvent, propagated to region state

**Trigger cadence**: `1, 3, 5, 10, 25, 50, 100, 250, 500, 1000...` — logarithmic spacing. First occurrence always evaluated. Major evaluation leaps at 1, 10, 100, 1000. A trigger is an *opportunity* — evaluators may find nothing notable and produce no output.

### Agent 2: FactionSystem — reputation tracker

Subscribes to ENEMY_KILLED, ITEM_CRAFTED, RESOURCE_GATHERED, LEVEL_UP (priority 5). Adjusts player reputation with 4 factions based on configured deltas. Large changes ripple to allied/hostile factions.

**Example**: Player kills enemy → Village Guard +0.02, Forest Wardens -0.01. If the Guard change pushes past 0.25 → milestone "Recognized" fires, publishes FACTION_MILESTONE_REACHED event.

**What the agent communicates**: Publishes `FACTION_REP_CHANGED` and `FACTION_MILESTONE_REACHED` events to the bus. These get recorded by EventRecorder into the memory layer. NPC agents can query faction state when building dialogue context.

**Missing**: Milestones produce no narrative text. The guard captain should say something when you become "Recognized" but currently nothing happens. **My proposal**: Start with template strings per milestone, generate LLM flavor text later. Happens ~12 times per playthrough — low frequency, high impact.

### Agent 3: EcosystemAgent — resource accountant

Subscribes to RESOURCE_GATHERED (priority 5). Tracks per-biome, per-resource depletion pools. When depletion crosses 70% → scarce flag. 90% → critical. Resources regenerate over time (quick=120s, normal=300s, slow=600s, very_slow=1200s).

**Example**: Player gathers 180 of 250 iron ore in mountain biome (72% depleted) → scarce flag set → publishes RESOURCE_SCARCITY event. After player leaves, iron regenerates at 1 unit per 600 seconds.

**What the agent communicates**: Publishes `RESOURCE_SCARCITY` and `RESOURCE_RECOVERED` to the bus. **Problem**: nobody listens. EventRecorder doesn't map these event types yet. NPCs don't hear about scarcity.

**Missing bridge** (10 lines): Subscribe to RESOURCE_SCARCITY → compose summary → call `NPCAgentSystem.propagate_gossip()`. Also: add these to `BUS_TO_MEMORY_TYPE` in event_schema.py. Wire this in WorldMemorySystem.initialize() as a lightweight subscriber.

### Agent 4: NPC Agent System — personality + memory + dialogue

Only fires on demand (player talks to NPC). Assembles context from NPCMemory + personality template, sends to BackendManager for LLM generation, parses response, updates memory.

**Example conversation context**:
```
SYSTEM: "You are Thorin, a gruff blacksmith.
  Emotion: impressed. Relationship: friendly (0.35).
  You know: [wolf pack killed, iron scarce, player crafted longsword]
  Past talks: Discussed swords."

USER: "Player says: 'Got any weapons?'
  Level 12 Warrior. World: wolf attacks increasing."
```

**What it knows**: NPC personality, relationship history, 10 most recent knowledge items, rolling conversation summary, player level/class/title, 3 global world conditions.

**What it should know but doesn't**:

| Missing | Source | Impact |
|---------|--------|--------|
| Faction reputation with NPC's faction | `FactionSystem.get_reputation()` | High — should change tone/access |
| This NPC's local events | `WorldQuery.query_entity(npc_id)` | Medium — grounds dialogue in location |
| Resource scarcity NPC cares about | `EcosystemAgent.get_scarcity_report()` | Medium — blacksmith should mention iron |
| Gossip freshness | Timestamp on knowledge items | Low — "I just heard" vs stale facts |

**My proposal**: Don't dump everything in. Score available context by NPC's personality tags, pick the 3-5 most relevant items. Keep the prompt under ~500 tokens of context. Small models (Ollama 8B) degrade fast with long prompts.

### Agent 5: BackendManager — the LLM router

Not an autonomous agent — a service layer. Routes `generate(task, system, user)` calls to the best available backend with fallback: ollama → claude → mock.

**Current consumers**: Only NPC dialogue (Touchpoint 6). LLM item generation (Touchpoint 9) uses its own separate backend.

**Future consumers**: Quest generation, faction milestone narratives, ecosystem crisis descriptions. Each would be a new `task` type routed through the same manager.

**Mock backend** always succeeds with keyword-matched templates. This means every AI feature works offline — just with less variety.

---

## How Agents Would Interact — Worked Example

**Scenario**: Player over-harvests iron ore in the mountains, triggering a chain of agent responses.

```
1. Player gathers iron_ore (50th time in mountain biome)
   └─ GameEventBus: RESOURCE_GATHERED

2. EcosystemAgent hears it (p5)
   └─ mountain iron_ore: 200/250 gathered → 80% depleted → SCARCE
   └─ Publishes: RESOURCE_SCARCITY {biome: mountain, resource: iron_ore, severity: scarce}

3. FactionSystem hears RESOURCE_GATHERED (p5)
   └─ Miners Collective: +0.005 (they respect gatherers)
   └─ Forest Wardens: -0.005 (they worry about over-harvesting)

4. EventRecorder hears RESOURCE_GATHERED (p-10)
   └─ Writes WorldMemoryEvent to SQLite
   └─ Occurrence count for (player, resource_gathered, gathered_iron_ore) = 50
   └─ 50 is a milestone threshold → triggers Layer 3 evaluators
   └─ EcosystemPressure: depletion at 80%, already flagged → updates existing interpretation
   └─ CombatProficiency: not relevant, skips
   └─ Layer 4 check: 3+ ecosystem interpretations in this district → triggers connected evaluator
   └─ Connected: "Heavy resource extraction in Iron Hills district"

5. [PROPOSED] Scarcity bridge hears RESOURCE_SCARCITY
   └─ Composes: "Iron ore is becoming scarce in the mountains"
   └─ Calls NPCAgentSystem.propagate_gossip(significance=0.7)
   └─ Schedules delivery: blacksmith (60s delay), merchant (180s), all NPCs (420s)

6. 60 game-seconds later: NPCAgentSystem.update()
   └─ Delivers gossip to blacksmith NPC memory
   └─ blacksmith.knowledge += "Iron ore is becoming scarce in the mountains"

7. Player talks to blacksmith
   └─ NPCAgentSystem.generate_dialogue()
   └─ System prompt includes: "You know: Iron ore is becoming scarce..."
   └─ [PROPOSED] Also includes: "Miners Collective considers player: recognized (0.28)"
   └─ BackendManager → Ollama → "Iron's getting hard to come by. If you find any,
      bring it here — I'll make it worth your while."
   └─ Player experiences: NPC awareness of their impact on the world
```

**What this requires that doesn't exist yet**:
- Step 5: ~10 lines subscribing to RESOURCE_SCARCITY
- Step 7: ~3 lines injecting faction context into prompt

---

## What's NOT Here (and shouldn't be yet)

| System | Why not yet |
|--------|-----------|
| Quest generation | Needs all layers integrated first — quests should be grounded in Layer 4+ patterns |
| World events (invasions, migrations) | Needs quest system + pacing model. Layer 7 tables designed for this. |
| NPC schedules/movement | Blocked by animation system (Phase 1) |
| BalanceValidator | Spec only, no code. Gates AI-generated content with tier-based stat ranges |
| Player behavior classification | Phase 3. Layer 4's Player Identity Consolidator is the foundation for this. |
| Narrative threads | Layer 7 concept. Designed (see Scratchpad). Needs Layers 3-5 stable first. |
| Multiplayer sub-layer | Would be ~Layer 3.5 — per-player connected interpretations before merging into shared Layer 4+. |

---

## File Map

```
world_system/                               # "World System" — top-level package
│
├── world_memory/                           # Event capture, interpretation, queries
│   ├── event_store.py                      # SQLite (13 tables)
│   ├── event_recorder.py                   # Bus→SQLite bridge
│   ├── event_schema.py                     # Event types + dataclasses
│   ├── interpreter.py                      # Evaluator orchestrator
│   ├── evaluators/                         # 5 pattern evaluators
│   ├── geographic_registry.py              # Region hierarchy
│   ├── entity_registry.py                  # NPC/player/region entities
│   ├── query.py                            # WorldQuery context assembly
│   ├── config_loader.py                    # JSON config loader
│   ├── retention.py                        # Event pruning
│   ├── position_sampler.py                 # Player breadcrumbs
│   └── world_memory_system.py              # Facade/singleton
│
├── living_world/                           # Autonomous agents that make the world feel alive
│   ├── backends/
│   │   └── backend_manager.py              # LLM router: ollama→claude→mock
│   ├── npc/
│   │   ├── npc_memory.py                   # Per-NPC persistent state
│   │   └── npc_agent.py                    # Dialogue generation + gossip
│   ├── factions/
│   │   └── faction_system.py               # Reputation + ripple + milestones
│   └── ecosystem/
│       └── ecosystem_agent.py              # Biome resource tracking + scarcity
│
├── config/                                 # All JSON configuration
│   ├── memory-config.json                  # Evaluator thresholds, query windows
│   ├── geographic-map.json                 # Region hierarchy definitions
│   ├── backend-config.json                 # LLM routing, rate limits
│   ├── npc-personalities.json              # 6 NPC archetypes
│   ├── faction-definitions.json            # 4 factions + relationships
│   └── ecosystem-config.json              # Biome resource pools + regen rates
│
├── docs/                                   # Documentation
│   ├── README.md                           # This file
│   ├── LIVING_WORLD_AI.md                  # Architecture deep dives
│   └── AI_TOUCHPOINT_MAP.md               # Every inference/interpretation point
│
└── tests/
    └── test_phase2_systems.py              # 32 tests
```
