# World System

**Created**: 2026-03-24
**Scope**: Everything that makes the world feel alive — memory, AI agents, data collection, narrative

See also:
- [LIVING_WORLD_AI.md](LIVING_WORLD_AI.md) — Architecture diagrams and per-system deep dives
- [AI_TOUCHPOINT_MAP.md](AI_TOUCHPOINT_MAP.md) — Every place AI inference or interpretation fires

---

## All Data the World System Can See

Three layers of data exist. Each serves a different purpose.

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

**File**: `ai/memory/event_store.py` — SQLite database per save slot

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

### Layer 3 — Interpretations (narrative summaries, new)

**Files**: `ai/memory/evaluators/*.py` — 5 pattern evaluators

When event occurrence counts hit prime numbers (1, 2, 3, 5, 7, 11, 13...), evaluators scan recent Layer 2 data and produce one-sentence narratives:

| Evaluator | Watches | Example output |
|-----------|---------|----------------|
| Population | enemy kills per region | "The wolf population has been devastated in Old Forest. 47 killed." |
| Resources | gathers per region | "Iron Ore deposits are critically strained in Iron Hills." |
| Milestones | kills, levels, crafts, titles | "The adventurer has reached level 10. A major milestone." |
| Danger | damage taken, deaths | "Old Forest is extremely dangerous. 3 deaths recorded." |
| Crafting | discipline specialization | "The adventurer is becoming a master smithing crafter." |

These propagate to region states (locality → district → province based on severity) and are queryable by NPC agents.

### New SQL Tables (Phase 2.2–2.5)

| Table | What it stores |
|-------|---------------|
| `npc_memory` | Per-NPC: relationship score, emotion, knowledge[], conversation summary, reputation tags, quest state |
| `faction_state` | Per-faction: player reputation score, crossed milestones, last change |
| `faction_reputation_history` | Audit trail: delta, reason, game_time, is_ripple |
| `biome_resource_state` | Per-biome per-resource: initial pool, current, gathered, regen rate, scarce/critical flags |
| `event_triggers` | Future: world event cooldown tracking |
| `pacing_state` | Future: tension/reward cadence tracking |

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
     │    │    │     5 Evaluators
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

Subscribes to every event (wildcard `"*"`, priority -10 = runs last). Converts bus events to structured WorldMemoryEvents with geographic context. Writes to SQLite. Triggers the interpreter on prime-number occurrence counts.

**Example**: Player gathers iron ore →
- EventRecorder stamps it with chunk (2,4), locality "iron_hills", biome "mountain"
- Increments occurrence count for (player, resource_gathered, gathered_iron_ore) → count=7
- 7 is prime → triggers WorldInterpreter
- ResourcePressureEvaluator counts 25 recent gathers → "Notable iron ore harvesting in Iron Hills"
- Narrative stored as InterpretedEvent, propagated to region state

**My thinking**: This is the most important system. It's the bridge between raw gameplay and everything downstream. The prime-number trigger is clever — it naturally samples more densely early (1,2,3,5,7) and logarithmically later (97,101,103), so the first wolf kill always gets interpreted but the 500th only gets interpreted at prime checkpoints. This keeps SQLite small without losing narrative coverage.

### Agent 2: FactionSystem — reputation tracker

Subscribes to ENEMY_KILLED, ITEM_CRAFTED, RESOURCE_GATHERED, LEVEL_UP (priority 5). Adjusts player reputation with 4 factions based on configured deltas. Large changes ripple to allied/hostile factions.

**Example**: Player kills enemy → Village Guard +0.02, Forest Wardens -0.01. If the Guard change pushes past 0.25 → milestone "Recognized" fires, publishes FACTION_MILESTONE_REACHED event.

**What the agent communicates**: Publishes `FACTION_REP_CHANGED` and `FACTION_MILESTONE_REACHED` events to the bus. These get recorded by EventRecorder into the memory layer. NPC agents can query faction state when building dialogue context.

**Missing**: Milestones produce no narrative text. The guard captain should say something when you become "Recognized" but currently nothing happens. **My proposal**: Start with template strings per milestone, generate LLM flavor text later. Happens ~12 times per playthrough — low frequency, high impact.

### Agent 3: EcosystemAgent — resource accountant

Subscribes to RESOURCE_GATHERED (priority 5). Tracks per-biome, per-resource depletion pools. When depletion crosses 70% → scarce flag. 90% → critical. Resources regenerate over time (quick=120s, normal=300s, slow=600s, very_slow=1200s).

**Example**: Player gathers 180 of 250 iron ore in mountain biome (72% depleted) → scarce flag set → publishes RESOURCE_SCARCITY event. After player leaves, iron regenerates at 1 unit per 600 seconds.

**What the agent communicates**: Publishes `RESOURCE_SCARCITY` and `RESOURCE_RECOVERED` to the bus. **Problem**: nobody listens. EventRecorder doesn't map these event types yet. NPCs don't hear about scarcity.

**Missing bridge** (10 lines): Subscribe to RESOURCE_SCARCITY → compose summary → call `NPCAgentSystem.propagate_gossip()`. Also: add these to `BUS_TO_MEMORY_TYPE` in event_schema.py. **My proposal**: Wire this in WorldMemorySystem.initialize() as a lightweight subscriber.

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
   └─ 50 is not prime → no interpreter trigger

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
| Quest generation | Needs all agents integrated first — quests should be grounded in faction rep + scarcity + NPC personality |
| World events (invasions, migrations) | Needs quest system + pacing model. Tables exist in schema. |
| NPC schedules/movement | Blocked by animation system (Phase 1) |
| BalanceValidator | Spec only, no code. Gates AI-generated content with tier-based stat ranges |
| Player behavior classification | Phase 3. Requires enough stat history to classify playstyle |

---

## File Map

```
ai/
├── backends/
│   └── backend_manager.py          # LLM router: ollama→claude→mock
├── npc/
│   ├── npc_memory.py               # Per-NPC persistent state
│   └── npc_agent.py                # Dialogue generation + gossip
├── factions/
│   └── faction_system.py           # Reputation + ripple + milestones
├── ecosystem/
│   └── ecosystem_agent.py          # Biome resource tracking + scarcity
├── memory/
│   ├── event_store.py              # SQLite (13 tables)
│   ├── event_recorder.py           # Bus→SQLite bridge
│   ├── event_schema.py             # Event types + dataclasses
│   ├── interpreter.py              # Evaluator orchestrator
│   ├── evaluators/                 # 5 pattern evaluators
│   ├── geographic_registry.py      # Region hierarchy
│   ├── entity_registry.py          # NPC/player/region entities
│   ├── query.py                    # WorldQuery context assembly
│   ├── config_loader.py            # JSON config loader
│   ├── retention.py                # Event pruning
│   ├── position_sampler.py         # Player breadcrumbs
│   └── world_memory_system.py      # Facade/singleton
└── tests/
    └── test_phase2_systems.py      # 32 tests

AI-Config.JSON/
├── memory-config.json              # Evaluator thresholds, query windows
├── geographic-map.json             # Region hierarchy definitions
├── backend-config.json             # LLM routing, rate limits
├── npc-personalities.json          # 6 NPC archetypes
├── faction-definitions.json        # 4 factions + relationships
└── ecosystem-config.json           # Biome resource pools + regen rates

World System/
├── README.md                       # This file
├── LIVING_WORLD_AI.md              # Architecture deep dives
└── AI_TOUCHPOINT_MAP.md            # Every inference/interpretation point
```
