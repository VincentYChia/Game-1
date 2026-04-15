# World Memory System — Tag Library Design

**Created**: 2026-03-26
**Status**: Design — Pending procedural assignment implementation
**Location**: `world_system/docs/TAG_LIBRARY.md`

---

## Design Principles

### 1. Tags Describe Events, Not Regions
Every tag answers "what is this EVENT about?" — never "what is this PLACE like?"
- GOOD: `living_impact:dire` (this event has a dire impact on living conditions)
- BAD: `economy:prosperous` (this describes a region, not an event)

### 2. Tags Are Not Simply Accumulated
Higher layers OVERRIDE and UPDATE tags from below. Two mechanisms:
- **Significance is RECREATED** at each layer. Each layer makes its own judgment.
- **Key tags are UPDATED** (scope, urgency, address). Higher layers have broader context.

### 3. 65 Categories, 5-10 Tags Per Item
- Layer 1: 30 categories (factual dimensions)
- Layers 2-7: 5-9 new categories each (progressive unlock, including per-layer significance)
- Each stat/event carries 5-10 tags from available categories
- Tags are the PRIMARY retrieval/indexing mechanism

### 4. Format
All tags use `category:value` format. Stored as arrays of strings.

---

## Layer 1: Numerical Data (30 categories)

Factual dimensions of raw stats. Derived from stat keys and record_* parameters.

### Identity (5)
| # | Category | Values |
|---|----------|--------|
| 1 | `domain` | combat, gathering, crafting, exploration, social, economy, progression, dungeon, items, skills |
| 2 | `action` | kill, damage_deal, damage_take, gather, deplete, craft, invent, discover, equip, unequip, trade, buy, sell, quest_accept, quest_complete, quest_fail, level_up, learn, die, dodge, block, heal, repair, move, fish, enchant, place, use, consume, swing |
| 3 | `metric` | count, total, maximum, rate, streak, duration, percentage, current |
| 4 | `actor` | player, enemy, npc, world, system |
| 5 | `target` | player, enemy, npc, resource, item, node, station |

### Entity (7)
| # | Category | Values |
|---|----------|--------|
| 6 | `species` | wolf, goblin, slime, beetle, golem, dragon, skeleton... *(dynamic)* |
| 7 | `resource` | iron, oak, copper, mithril, herbs, limestone, granite... *(dynamic)* |
| 8 | `item` | iron_sword, health_potion, mithril_armor... *(dynamic)* |
| 9 | `skill` | fireball, heal, dash, shield_bash... *(dynamic)* |
| 10 | `recipe` | iron_sword_001, health_potion_basic... *(dynamic)* |
| 11 | `npc` | tutorial_guide, mysterious_trader, combat_trainer... *(dynamic)* |
| 12 | `quest` | main_quest_1, gather_herbs... *(dynamic)* |

### Classification (8)
| # | Category | Values |
|---|----------|--------|
| 13 | `tier` | 1, 2, 3, 4 |
| 14 | `element` | physical, fire, ice, lightning, poison, arcane, shadow, holy |
| 15 | `quality` | normal, fine, superior, masterwork, legendary |
| 16 | `rarity` | common, uncommon, rare, epic, legendary |
| 17 | `discipline` | smithing, alchemy, refining, engineering, enchanting |
| 18 | `material_category` | ore, tree, stone, plant, fish, gem |
| 19 | `item_category` | material, equipment, consumable, weapon, armor, tool, device, potion |
| 20 | `rank` | normal, elite, boss, dragon, unique |

### Combat (4)
| # | Category | Values |
|---|----------|--------|
| 21 | `attack_type` | melee, ranged, magic |
| 22 | `weapon_type` | sword, axe, bow, staff, dagger, hammer, spear |
| 23 | `status_effect` | burn, bleed, poison, freeze, stun, root, slow, shock, chill |
| 24 | `slot` | head, chest, legs, feet, main_hand, off_hand, accessory, ring |

### Context (6)
| # | Category | Values |
|---|----------|--------|
| 25 | `result` | success, failure, critical, perfect, first_try, miss, block, dodge |
| 26 | `source` | quest, enemy, vendor, level_up, book, crafting, gathering, fishing, dungeon, trade, loot |
| 27 | `tool` | axe, pickaxe, fishing_rod, hammer |
| 28 | `class` | warrior, mage, ranger, healer, rogue, paladin |
| 29 | `title_tier` | novice, intermediate, advanced, master |
| 30 | `location` | whispering_woods, iron_hills, deep_caverns... *(dynamic)* |

---

## Layer 2: Simple Text Events — 9 new (39 total)

Geographic address system and initial event assessment. Evaluators produce these.
The six address tags map 1:1 to the game's geographic hierarchy
(`World → Nation → Region → Province → District → Locality`) and are assigned
**at L2 capture time** from the chunk position via
`GeographicRegistry.get_full_address()`. They are FACTS — no higher layer and
no LLM prompt is permitted to create, rewrite, or drop them. See
`ARCHITECTURAL_DECISIONS.md` §6.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 31 | `locality` | elder_grove, traders_corner... | Sparse 6th tier — only present when the chunk has a POI |
| 32 | `district` | spawn_crossroads, whispering_woods... | District-level address (always present) |
| 33 | `province` | northwestern_reaches, northeastern_highlands... | Province-level address |
| 34 | `region` | shattered_coast, emberveil... | Region-level address |
| 35 | `nation` | varethkar, sylvandor... | Nation-level address |
| 36 | `world` | terra | World-level address (constant for a save) |
| 37 | `biome` | peaceful_forest, dangerous_quarry, water_lake... | Chunk biome type |
| 38 | `scope` | chunk, local, district, province, region, nation, global | **KEY TAG — updated at higher layers** |
| 39 | `significance` | minor, moderate, significant, major, critical | **RECREATED at every layer** |

**Sparse locality rule:** If the chunk has no POI, `locality:` is omitted
and the finest address tag on the event is `district:`. This is the only
optional tier — the other five address tiers are always present on any L2
event carrying a position.

---

## Layer 3: District-level — 9 new (48 total)

Consolidation of Layer 2 events into game-District-scoped narratives. One
tier per layer: L3 aggregates across all localities inside one district, so
**it drops the `locality:` address tag** on its output and retains
`district:/province:/region:/nation:/world:`. Interpretation begins here.
Content tags can be overridden/refined. Address tags are propagated unchanged
and never LLM-rewritten.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 37 | `significance` | minor, moderate, significant, major, critical | **RECREATED at this layer.** Layer 3 makes its own judgment with local consolidation context. |
| 38 | `sentiment` | positive, negative, neutral, dangerous, fortunate, prosperous, declining, hopeful, grim | Emotional read of the consolidated event |
| 39 | `alignment` | good, evil, just, unjust, chaotic, orderly, natural, unnatural, merciful, cruel | Moral/ethical dimension of the event |
| 40 | `trend` | increasing, decreasing, stable, volatile, emerging, dying, cyclical, accelerating | Directional pattern over time |
| 41 | `intensity` | light, moderate, heavy, extreme | Magnitude judgment — needs multi-event context |
| 42 | `setting` | village, settlement, wilderness, dungeon, underground, ruins, crossroads, market, camp | Environmental context of event |
| 43 | `terrain` | forest, hills, cave, clearing, path, rocky, dense, water, plains, swamp | Physical terrain where event occurred |
| 44 | `population_status` | thriving, declining, extinct, migrating, stable, recovering | Creature population state from event patterns |
| 45 | `resource_status` | abundant, steady, scarce, critical, depleted, recovering | Resource availability from event patterns |

**Override behavior:** Layer 3 UPDATES these content tags from Layer 2:
- `significance` → recreated with district consolidation context
- `scope` → updated (likely `district`)

**Address tag behavior (facts, never rewritten):**
- `locality:` → **dropped** (L3 aggregates across all localities in a district)
- `district:/province:/region:/nation:/world:` → propagated unchanged

---

## Layer 4: Province-level — 5 new (53 total)

Province-scoped consolidation of L3 district events. L4 aggregates across
all districts inside one province, so it **drops the `district:` address
tag** and retains `province:/region:/nation:/world:`. LLM-driven narrative
upgrade may rewrite content tags but never touches address tags.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 49 | `significance` | minor, moderate, significant, major, critical | **RECREATED at this layer.** Province-level judgment — a district-level major event may be minor at province scale. |
| 50 | `faction` | village_guard, crafters_guild, forest_wardens, miners_collective | Which faction this event touches |
| 51 | `urgency_level` | none, low, moderate, high, critical, emergency | **KEY TAG — updated at higher layers.** Broader than danger — any event type |
| 52 | `event_status` | emerging, developing, ongoing, resolving, resolved, recurring, escalating | Lifecycle status of the event pattern |
| 53 | `player_impact` | player_driven, partially_player, world_driven, mixed | Proportion of player vs world causation |

**Override behavior (content tags only — LLM may rewrite):**
- `significance` → recreated at province level
- `scope` → updated (likely `province`)
- `urgency_level` → set here, updated at higher layers

**Address tag behavior (facts, never rewritten):**
- `district:` → **dropped** (L4 aggregates across all districts in a province)
- `province:/region:/nation:/world:` → propagated unchanged. The layer code
  partitions `summary.tags` into address/content halves before calling the
  LLM and re-attaches the address half after the rewrite returns.

---

## Layer 5: Region-level — 5 new (58 total)

Region-scoped consolidation of L4 province events. L5 aggregates across all
provinces inside one game Region (one tier up from Layer 4), so it **drops
the `province:` address tag** and retains `region:/nation:/world:`. L5
events are produced as `RegionSummaryEvent` (previously named
`RealmSummaryEvent` and retargeted from world-aggregation to
region-aggregation in the 2026-04-16 hierarchy alignment). The LLM is given
only content tags for rewrite; address tags are re-attached by layer code.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 54 | `significance` | minor, moderate, significant, major, critical | **RECREATED at this layer.** Region-level judgment with full region context. |
| 55 | `political` | stabilizing, destabilizing, neutral, provocative, unifying, divisive | Political dimension of the event |
| 56 | `military` | peaceful, escalating, defensive, offensive, deterrent, provocative | Military dimension of the event |
| 57 | `living_impact` | minimal, noticeable, significant, dire, nightmarish, beneficial, transformative | Impact on quality of life |
| 58 | `migration` | causing_inflow, causing_outflow, displacement, attraction, neutral | Whether event drives population movement |

**Override behavior (content tags only — LLM may rewrite):**
- `significance` → recreated at region level
- `scope` → updated (likely `region`)
- `urgency_level` → refined with region-wide context

**Address tag behavior (facts, never rewritten):**
- `province:` → **dropped** (L5 aggregates across all provinces in a region)
- `region:/nation:/world:` → propagated unchanged

---

## Layer 6: Nation-level — 5 new (63 total)  *(future)*

Nation-scoped consolidation of L5 region events. L6 aggregates across all
regions inside one nation, so it **drops the `region:` address tag** and
retains `nation:/world:`. Layer 6 is a future trivial copy of Layer 5's
pattern at nation scope — it does not exist in code yet.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 59 | `significance` | minor, moderate, significant, major, critical | **RECREATED at this layer.** Nation-level judgment. |
| 60 | `relation_effect` | hostility, alliance, friendship, hatred, war, trade_disruption, cooperation, indifference | What the event triggers between regions/factions |
| 61 | `diplomacy` | treaty, embargo, negotiation, escalation, de_escalation, neutral | Diplomatic consequence of the event |
| 62 | `nation_effect` | unifying, fragmenting, isolating, connecting, destabilizing, strengthening | How event affects national cohesion |
| 63 | `nation_significance` | negligible, minor, notable, major, defining | **NEW significance at nation scope** (separate from per-layer `significance`) |

**Override behavior (content tags only):**
- `significance` → recreated at nation level
- `scope` → updated (`nation`, `cross_regional`)
- `urgency_level` → updated with multi-region context

**Address tag behavior (facts, never rewritten):**
- `region:` → **dropped** (L6 aggregates across all regions in a nation)
- `nation:/world:` → propagated unchanged

---

## Layer 7: World-level — 5 new (68 total)  *(future)*

World-scoped consolidation of L6 nation events. L7 aggregates across all
nations inside the world, so it **drops the `nation:` address tag** and
retains only `world:`. Layer 7 is a future trivial copy of Layer 5's
pattern at world scope — it does not exist in code yet.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 64 | `significance` | minor, moderate, significant, major, critical | **RECREATED at this layer.** World-level judgment — most events are minor at world scale. |
| 65 | `world_significance` | negligible, passing, notable, historic, epochal | **Scope-specific significance.** A Layer 4 `critical` event may be `world_significance:passing`. |
| 66 | `narrative_role` | catalyst, turning_point, escalation, resolution, echo, origin, consequence, climax | What role this event plays in the world story. |
| 67 | `era_effect` | no_effect, era_continuing, era_shifting, era_defining, era_ending, era_beginning | Does this event mark or affect a world epoch? |
| 68 | `world_theme` | conflict, discovery, decline, growth, balance, chaos, order, renewal, stagnation | What thematic thread this event reinforces. |

**Override behavior (content tags only):**
- `significance` → recreated at world level
- `scope` → `global` or `world`
- `urgency_level` → final assessment

**Address tag behavior (facts, never rewritten):**
- `nation:` → **dropped** (L7 aggregates across all nations in the world)
- `world:` → propagated unchanged (the only address tag remaining)

---

## Tag Update Mechanism

### Key Tags (updated at each layer, not just inherited)

| Tag | Behavior | Why |
|-----|----------|-----|
| `significance` | **Recreated fresh** at every layer | Each layer judges significance with its own scope. Layer 2's `major` might be Layer 5's `minor`. |
| `scope` | **Updated** (generally broadens) | `local` → `district` → `province` → `region` → `nation` → `global` as event consolidates upward |
| `urgency_level` | **Updated** (from Layer 4+) | Refined with each layer's broader context. Can escalate OR de-escalate. |
| Address (`world`, `nation`, `region`, `province`, `district`, `locality`) | **Propagated unchanged, with one dropped per layer** | See §6 of `ARCHITECTURAL_DECISIONS.md`. Addresses are facts assigned at L2 capture from chunk position. Each layer drops exactly the finest address tag (the tier it aggregates across). No LLM may ever create, rewrite, or remove an address tag. |

### All Other Tags (content tags)

- **Inherited by default** from the layer below
- **Can be overridden** by the processing layer (add, remove, or change)
- **NOT a simple union** of all involved lower-layer events' tags
- At higher layers, LLM handles content-tag selection/override. The layer
  code partitions `summary.tags` into address/content halves before
  calling the LLM and re-attaches the address half after. Any address
  tag the LLM emits in its output is discarded.
- Each item carries 5-10 tags from its available categories

### Significance Per Layer

Each layer creates its own significance column:
- Layer 2: `significance` (evaluator-assessed, capture-scope)
- Layer 3: `significance` (recreated with district context)
- Layer 4: `significance` (recreated with province context)
- Layer 5: `significance` (recreated with region context)
- Layer 6: `significance` + `nation_significance` (new scope-specific)
- Layer 7: `significance` + `world_significance` (new scope-specific)

---

## Storage Schema (Per Layer)

Each layer has its own SQL table with an ID column.

```sql
-- Layer 1
CREATE TABLE layer1_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    count INTEGER DEFAULT 0,
    total REAL DEFAULT 0.0,
    max_value REAL DEFAULT 0.0,
    tags TEXT DEFAULT '[]',
    updated_at REAL DEFAULT 0.0
);

-- Layer 2
CREATE TABLE layer2_events (
    id TEXT PRIMARY KEY,
    narrative TEXT NOT NULL,
    origin_stat_key TEXT NOT NULL,
    game_time REAL NOT NULL,
    real_time REAL NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    tags TEXT DEFAULT '[]',
    evaluator_id TEXT
);

-- Layer 3
CREATE TABLE layer3_events (
    id TEXT PRIMARY KEY,
    narrative TEXT NOT NULL,
    origin_layer2_ids TEXT NOT NULL,
    game_time REAL NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    tags TEXT DEFAULT '[]'
);

-- Layers 4-7: Same pattern
-- origin_layer{N-1}_ids references the layer below
-- Each has its own tags column (with that layer's tag updates applied)
```

Junction tables for tag-based retrieval:
```sql
CREATE TABLE layer{N}_tags (
    event_id TEXT NOT NULL,
    tag_category TEXT NOT NULL,
    tag_value TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES layer{N}_events(id)
);
CREATE INDEX idx_layer{N}_tags_cat_val ON layer{N}_tags(tag_category, tag_value);
```

---

## Summary

| Layer | Aggregation tier | New Categories | Total | Focus |
|-------|-----|---------------|-------|-------|
| 1 | — | 30 | 30 | Factual dimensions of numerical data |
| 2 | capture | 9 | 39 | Full 6-tier address (world/nation/region/province/district/locality) + biome + scope + significance |
| 3 | game District | 9 (incl. significance) | 48 | District consolidation — sentiment, alignment, trend, setting, terrain. Drops `locality:` address tag. |
| 4 | game Province | 5 (incl. significance) | 53 | Province cross-domain — urgency, factions, event status. Drops `district:` address tag. |
| 5 | game Region | 5 (incl. significance) | 58 | Region political/military/living impact. Drops `province:` address tag. |
| 6 | game Nation *(future)* | 5 (incl. significance) | 63 | Cross-region effects and relations. Drops `region:` address tag. |
| 7 | game World *(future)* | 5 (incl. significance) | 68 | World narrative, era, theme. Drops `nation:` address tag. |

---

## Implementation Notes

- Procedural tag assignment (how tags are automatically derived) is designed separately after this library is finalized.
- LLM handles **content**-tag rewriting at Layers 4 and 5. It never sees address tags. The layer code partitions `summary.tags` into address/content halves before calling the LLM and re-attaches the address half after. See `ARCHITECTURAL_DECISIONS.md` §6.
- Tag library is defined as a JSON config for easy modification.
- The existing `affects_tags` field on evaluator output maps to Layer 2 tags.
- Existing `tag_relevance.py` category:value parsing already supports this format.

---

## Document History

- **2026-04-16**: Hierarchy-alignment migration. The WMS `RegionLevel`
  enum was expanded from 5 shifted labels to 6 game-aligned values
  (`WORLD/NATION/REGION/PROVINCE/DISTRICT/LOCALITY`). Layer 2 now
  carries all six address tags (was locality/district/province only).
  Layers 3-7 re-pinned to their correct aggregation tiers — each layer
  now drops exactly the finest address tag (one tier per layer). Layer
  5 retargeted from "realm" (world-scope) to game-Region scope; L6/L7
  remapped to nation/world. Address tags formalized as facts (assigned
  at L2 capture from chunk position, never LLM-synthesized). See
  `ARCHITECTURAL_DECISIONS.md` §6.
- **2026-03-26**: Initial creation.
