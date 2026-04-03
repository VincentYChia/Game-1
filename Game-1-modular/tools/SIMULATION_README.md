# World Memory System — Simulation Database

## What This Is

`simulate_world_memory.py` creates a standalone SQLite database (`wms_simulation.db`) populated with synthetic data from a simulated 2-hour play session. It demonstrates how data flows through all 7 layers of the World Memory System.

The database uses the **production SQL schemas** from `event_store.py` and `stat_store.py`. It does NOT use `layer_store.py` schemas (see "Schema Note" below).

---

## How To Run

```bash
cd Game-1-modular
python tools/simulate_world_memory.py --dump    # Build database + print summary
python tools/simulate_world_memory.py           # Build silently
sqlite3 tools/wms_simulation.db                 # Inspect directly
```

---

## What's In The Database

### Layer 1: `stats` table — 500 rows

The same schema as `stat_store.py`. Hierarchical text keys with count/total/max_value.

Simulated player state: Level 9 warrior, ~2 hours played.

| Category | Sample Keys | Sample Values |
|----------|------------|---------------|
| Combat | `combat.kills` = 120, `combat.kills.species.wolf_grey` = 18, `combat.damage_dealt` = 15,234 | 120 kills across 9 enemy types, 850 attacks, 85 crits |
| Gathering | `gathering.collected` = 300, `gathering.collected.resource.iron_ore` = 32 | 300 resources from 15 types, 22 nodes depleted |
| Crafting | `crafting.attempts` = 50, `crafting.success` = 38 | 5 disciplines, 2 inventions |
| Progression | `progression.level_ups` = 8, `progression.current_level` max=9 | 6 skills learned, 2 titles, warrior class |
| Exploration | `exploration.unique_chunks` = 35, `exploration.distance` = 8,500 | 4 biome types visited |
| Dungeons | `dungeon.entered` = 3, `dungeon.completed` = 2 | 28 dungeon kills, 1 death |
| Social | `social.npc_interactions` = 15, `social.quests.completed` = 2 | 3 NPCs, 3 quests |

**Example queries:**
```sql
SELECT key, count, total FROM stats WHERE key LIKE 'combat.kills%' ORDER BY count DESC LIMIT 10;
SELECT key, total FROM stats WHERE key LIKE 'gathering.collected.resource%' ORDER BY total DESC;
```

### Raw Event Pipeline: `events` + `event_tags` — 176 events

The same schema as `event_store.py`. Each event has full geographic context (locality, district, province, biome), position, game_time, magnitude, result, tier.

**Play session narrative** (5 phases):

| Phase | Game Time | Location | Events | What Happens |
|-------|-----------|----------|--------|-------------|
| 1. Spawn | 0-600 | spawn_crossroads | ~25 | Gather T1 resources, kill T1 enemies, talk to tutorial NPC, accept quest |
| 2. Forest | 600-1800 | south_clearing, elder_grove | ~35 | Explore woods, fight T1-T2 enemies, gather T2 resources, level to 5, learn fireball |
| 3. Mining | 1800-3600 | traders_corner, east_path | ~65 | Heavy iron mining (35 gathers), deplete 2 nodes, fight T1-T2, craft 12 items, level to 8, earn title |
| 4. Dungeon | 3600-5400 | deep_caverns | ~30 | Fight T2-T4 enemies, die once, dodge, use skills |
| 5. Late | 5400-7200 | traders_corner, east_path | ~20 | Talk to trader, accept quest, level to 9, choose warrior class, gather T2 |

Tags per event (~5-6 each): `domain:combat`, `event:enemy_killed`, `species:wolf_grey`, `tier:1`, `biome:peaceful_forest`, `location:spawn_crossroads`

**Example queries:**
```sql
SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY COUNT(*) DESC;
SELECT e.event_type, e.event_subtype, e.locality_id, e.magnitude
  FROM events e WHERE e.event_type = 'enemy_killed' ORDER BY e.game_time;
SELECT tag, COUNT(*) FROM event_tags GROUP BY tag ORDER BY COUNT(*) DESC LIMIT 20;
```

### Threshold Tracking: `occurrence_counts` + `regional_counters`

**Track 1** (individual streams): 62 counters keyed by `(actor_id, event_type, event_subtype)`.

Example: `("player", "enemy_killed", "enemy.wolf_grey", "spawn_crossroads")` → count=8

**Track 2** (regional accumulators): 22 counters keyed by `(region_id, event_category)`.

Example: `("traders_corner", "gathering")` → count=37

Thresholds: `1, 3, 5, 10, 25, 50, 100, 250, 500, 1000`

When a counter hits a threshold value → evaluators are triggered → Layer 2 output.

### Layer 2: `interpretations` + `interpretation_tags` — ~94 entries

Evaluator outputs. Each has: narrative (one sentence), category, severity, trigger event, cause chain, affected localities/districts, tags.

| Category | Count | Sample Narrative |
|----------|-------|-----------------|
| population_change | ~39 | "Significant hunting pressure in traders_corner. 25 creatures killed — population may be affected." |
| ecosystem_pressure | ~36 | "Critical harvesting pressure in traders_corner. 50 resources — deposits becoming strained." |
| player_milestones | ~8 | "Reached a new level in elder_grove." / "Earned a new title in traders_corner." |
| resource_pressure | ~5 | "Under resource pressure: traders_corner. 25 gathering events — supply strained." |
| area_danger | ~2 | "Heavy combat zone: deep_caverns. 25 combat events — area is dangerous." |
| combat_proficiency | ~1 | "Fell in combat in deep_caverns. Area may be dangerous." |
| crafting_mastery | ~2 | "Crafting hub emerging at traders_corner. 5 crafting events." |

Tags: `domain:combat`, `location:traders_corner`, `district:iron_hills`, `province:northeastern_highlands`, `biome:peaceful_quarry`, `scope:local`, `significance:significant`, `category:population_change`

**Example queries:**
```sql
SELECT narrative, severity, category FROM interpretations ORDER BY created_at DESC LIMIT 10;
SELECT category, COUNT(*) FROM interpretations GROUP BY category;
SELECT DISTINCT tag FROM interpretation_tags WHERE tag LIKE 'location:%';
```

### Layer 3: `connected_interpretations` — 6 entries

Cross-domain patterns. Triggers when a locality has 3+ Layer 2 interpretations OR 2+ from different categories.

| Locality | Domains | Sample Narrative |
|----------|---------|-----------------|
| spawn_crossroads | 4 | "Correlated activity across 4 domains: ecosystem_pressure, player_milestones, population_change, resource_pressure." |
| traders_corner | 5 | "Correlated activity across 5 domains: crafting_mastery, ecosystem_pressure, player_milestones, population_change, resource_pressure." |
| deep_caverns | 3 | "Correlated activity across 3 domains: area_danger, combat_proficiency, population_change." |

Tags: Layer 2 tags inherited + `scope:district`, `trend:accelerating`/`emerging`, `intensity:heavy`/`moderate`

### Layer 4: `province_summaries` — 2 entries

| Province | Threat | Summary |
|----------|--------|---------|
| northwestern_reaches | moderate | 3 notable regional patterns. Dominant: combat, gathering, crafting. |
| northeastern_highlands | moderate | 3 notable regional patterns. Dominant: combat, gathering, crafting. |

### Layer 5: `realm_state` — 1 entry

| Field | Value |
|-------|-------|
| realm_id | known_lands |
| faction_standings | village_guard: 0.3, crafters_guild: 0.5 |
| economic_summary | Active resource extraction and crafting economy. Gold flow from quests. |
| player_reputation | Rising adventurer with combat and crafting focus. Level 9, warrior class. |

### Layers 6-7: `world_narrative` + `narrative_threads` — 2 entries

**Thread**: "Iron deposits in the Iron Hills are being heavily mined. Local supply is strained and node depletion events are increasing."
- Status: developing
- Significance: 0.6
- Origin: iron_hills
- Canonical facts: ["Player mined 50+ iron ore", "2 iron nodes fully depleted", "Gathering rate exceeds regeneration"]

**World State**: Epoch = early_exploration, Themes = [discovery, growth, conflict]

---

## The Cascade Filter Effect

```
176 raw events
 → 94 Layer 2 interpretations (evaluator outputs from threshold hits)
  → 6 Layer 3 consolidated patterns (cross-domain per locality)
   → 2 Layer 4 province summaries
    → 1 Layer 5 realm state
     → 1 Layer 6-7 narrative thread
```

Each layer compresses the one below by 5-15x.

---

## Schema Note: Two Database Systems

The production WMS uses **two separate SQLite databases**:

### 1. `world_memory.db` (from `event_store.py` + `stat_store.py`)

This is what the simulation builds. Contains:
- `stats` — Layer 1 flat key-value counters
- `events` + `event_tags` — Raw Event Pipeline
- `interpretations` + `interpretation_tags` — Layer 2 (flat tag strings)
- `connected_interpretations` + tags — Layer 3
- `province_summaries` — Layer 4
- `realm_state` — Layer 5
- `world_narrative` + `narrative_threads` — Layers 6-7
- Consumer tables: `npc_memory`, `faction_state`, `faction_reputation_history`, `biome_resource_state`, `entity_state`, `region_state`
- Tracking: `occurrence_counts`, `regional_counters`, `interpretation_counters`, `daily_ledgers`, `meta_daily_stats`
- System: `event_triggers`, `pacing_state`

Total: **20 tables**

### 2. `layer_store.db` (from `layer_store.py`)

**NOT in the simulation yet.** This is the tag-indexed retrieval database with structured `(tag_category, tag_value)` pairs instead of flat tag strings. Contains:
- `layer1_stats` + `layer1_tags` — Stats mirrored with tag junction table
- `layer2_events` + `layer2_tags` — Layer 2 with structured tags
- `layer3_events` + `layer3_tags` through `layer7_events` + `layer7_tags`

Total: **14 tables** (7 event tables + 7 tag tables)

The tag tables use `(tag_category TEXT, tag_value TEXT)` columns instead of a single `tag TEXT` column. This enables queries like:
```sql
SELECT e.* FROM layer2_events e
JOIN layer2_tags t ON t.event_id = e.id
WHERE t.tag_category = 'species' AND t.tag_value = 'wolf_grey';
```

### Why Two Databases?

`world_memory.db` is the **write-path** database (optimized for recording events and running evaluators). `layer_store.db` is the **read-path** database (optimized for tag-intersection retrieval by NPC agents, quest generators, and other consumers).

---

## Simulation Limitations

1. **No real LLM calls** — Layer 2 narratives use templates (matching design doc §2.5: "templates first, LLM when needed")
2. **No layer_store.db** — Only builds the event_store schema, not the tag-indexed retrieval tables
3. **Simplified evaluator logic** — Uses threshold→template mapping instead of the 33 real evaluators
4. **Static geographic data** — Uses 6 hardcoded localities instead of the full procedural world
5. **No retention pruning** — All events kept (real system prunes per §5.4 rules)
6. **No daily ledger** — Time tracking simplified
7. **Consumer tables empty** — npc_memory, faction_state, biome_resource_state not populated
