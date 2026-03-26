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

### 3. ~60 Categories, 5-10 Tags Per Item
- Layer 1: 30 categories (factual dimensions)
- Layers 2-7: ~5 new categories each (progressive unlock)
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

## Layer 2: Simple Text Events — 6 new (36 total)

Geographic address system and initial event assessment. Evaluators produce these.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 31 | `locality` | elder_grove, traders_corner... | Precise geographic address |
| 32 | `district` | spawn_crossroads, whispering_woods... | District-level address |
| 33 | `province` | northwestern_reaches, northeastern_highlands... | Province-level address |
| 34 | `biome` | peaceful_forest, dangerous_quarry, water_lake... | Chunk biome type |
| 35 | `scope` | chunk, local, district, regional, global | **KEY TAG — updated at higher layers** |
| 36 | `significance` | minor, moderate, significant, major, critical | **RECREATED at every layer** |

---

## Layer 3: Municipality/Local — 8 new (44 total)

Consolidation of Layer 2 events. Interpretation begins. Can OVERRIDE Layer 2 tags.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 37 | `sentiment` | positive, negative, neutral, dangerous, fortunate, prosperous, declining, hopeful, grim | Emotional read of the consolidated event |
| 38 | `alignment` | good, evil, just, unjust, chaotic, orderly, natural, unnatural, merciful, cruel | Moral/ethical dimension of the event |
| 39 | `trend` | increasing, decreasing, stable, volatile, emerging, dying, cyclical, accelerating | Directional pattern over time |
| 40 | `intensity` | light, moderate, heavy, extreme | Magnitude judgment — needs multi-event context |
| 41 | `setting` | village, settlement, wilderness, dungeon, underground, ruins, crossroads, market, camp | Environmental context of event |
| 42 | `terrain` | forest, hills, cave, clearing, path, rocky, dense, water, plains, swamp | Physical terrain where event occurred |
| 43 | `population_status` | thriving, declining, extinct, migrating, stable, recovering | Creature population state from event patterns |
| 44 | `resource_status` | abundant, steady, scarce, critical, depleted, recovering | Resource availability from event patterns |

**Override behavior:** Layer 3 UPDATES these from Layer 2:
- `significance` → recreated with local consolidation context
- `scope` → updated (may expand if event spans multiple localities)
- `locality`, `district`, `province` → updated if event scope changed

---

## Layer 4: Smaller Region — 4 new (48 total)

District-level cross-domain patterns. Tags describe event characteristics.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 45 | `faction` | village_guard, crafters_guild, forest_wardens, miners_collective | Which faction this event touches |
| 46 | `urgency_level` | none, low, moderate, high, critical, emergency | **KEY TAG — updated at higher layers.** Broader than danger — any event type |
| 47 | `event_status` | emerging, developing, ongoing, resolving, resolved, recurring, escalating | Lifecycle status of the event pattern |
| 48 | `player_impact` | player_driven, partially_player, world_driven, mixed | Proportion of player vs world causation |

**Override behavior:** Layer 4 UPDATES:
- `significance` → recreated at district level
- `scope` → updated (likely `district` or broader)
- `urgency_level` → set here, updated at higher layers
- Address tags → updated if event spans multiple localities

---

## Layer 5: Larger Region / Country — 4 new (52 total)

Province-level event interpretation. How events interact with political/living conditions.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 49 | `political` | stabilizing, destabilizing, neutral, provocative, unifying, divisive | Political dimension of the event |
| 50 | `military` | peaceful, escalating, defensive, offensive, deterrent, provocative | Military dimension of the event |
| 51 | `living_impact` | minimal, noticeable, significant, dire, nightmarish, beneficial, transformative | Impact on quality of life |
| 52 | `migration` | causing_inflow, causing_outflow, displacement, attraction, neutral | Whether event drives population movement |

**Override behavior:** Layer 5 UPDATES:
- `significance` → recreated at province level
- `scope` → updated (likely `regional`)
- `urgency_level` → refined with province-wide context
- Address tags → updated to province level

---

## Layer 6: Intercountry — 4 new (56 total)

Cross-province event effects. How events ripple between regions.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 53 | `relation_effect` | hostility, alliance, friendship, hatred, war, trade_disruption, cooperation, indifference | What the event triggers between provinces/factions |
| 54 | `diplomacy` | treaty, embargo, negotiation, escalation, de_escalation, neutral | Diplomatic consequence of the event |
| 55 | `regional_effect` | unifying, fragmenting, isolating, connecting, destabilizing, strengthening | How event affects regional cohesion |
| 56 | `regional_significance` | negligible, minor, notable, major, defining | **NEW significance at cross-regional scope** |

**Override behavior:** Layer 6 UPDATES:
- `significance` → recreated at intercountry level
- `scope` → updated (`widespread`, `cross_regional`)
- `urgency_level` → updated with multi-province context

---

## Layer 7: World Level — 4 new (60 total)

World-level event interpretation. How events shape the world narrative.

| # | Category | Values | Notes |
|---|----------|--------|-------|
| 57 | `world_significance` | negligible, passing, notable, historic, epochal | Fresh significance at world scale. Most events are negligible or passing here. A Layer 4 `critical` event may be `passing` at world scale. |
| 58 | `narrative_role` | catalyst, turning_point, escalation, resolution, echo, origin, consequence, climax | What role this event plays in the world story. Not what the world is — what this event DOES to the story. |
| 59 | `era_effect` | no_effect, era_continuing, era_shifting, era_defining, era_ending, era_beginning | Does this event mark or affect a world epoch? Most are `no_effect`. Only world-shaping events are `era_defining`. |
| 60 | `world_theme` | conflict, discovery, decline, growth, balance, chaos, order, renewal, stagnation | What thematic thread this event reinforces or introduces. |

**Override behavior:** Layer 7 UPDATES:
- `significance` → recreated at world level
- `scope` → `global` or `world`
- `urgency_level` → final assessment
- Address tags → may be stripped or generalized (world level doesn't need locality precision)

---

## Tag Update Mechanism

### Key Tags (updated at each layer, not just inherited)

| Tag | Behavior | Why |
|-----|----------|-----|
| `significance` | **Recreated fresh** at every layer | Each layer judges significance with its own scope. Layer 2's `major` might be Layer 5's `minor`. |
| `scope` | **Updated** (generally broadens) | `local` → `district` → `regional` → `global` as event consolidates upward |
| `urgency_level` | **Updated** (from Layer 4+) | Refined with each layer's broader context. Can escalate OR de-escalate. |
| Address (`locality`, `district`, `province`) | **Updated** (can expand or generalize) | Event may span larger area at higher layers. World-level may drop locality entirely. |

### All Other Tags

- **Inherited by default** from the layer below
- **Can be overridden** by the processing layer (add, remove, or change)
- **NOT a simple union** of all involved lower-layer events' tags
- At higher layers, LLM will likely handle tag selection/override
- Each item carries 5-10 tags from its available categories

### Significance Per Layer

Each layer creates its own significance column:
- Layer 2: `significance` (evaluator-assessed)
- Layer 3: `significance` (recreated with local context)
- Layer 4: `significance` (recreated with district context)
- Layer 5: `significance` (recreated with province context)
- Layer 6: `significance` + `regional_significance` (new scope-specific)
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

| Layer | New Categories | Total | Focus |
|-------|---------------|-------|-------|
| 1 | 30 | 30 | Factual dimensions of numerical data |
| 2 | 6 | 36 | Geographic address + initial assessment |
| 3 | 8 | 44 | Local interpretation, sentiment, alignment |
| 4 | 4 | 48 | District cross-domain, urgency, factions |
| 5 | 4 | 52 | Province political/military/living impact |
| 6 | 4 | 56 | Cross-province effects and relations |
| 7 | 4 | 60 | World narrative, era, theme |

---

## Implementation Notes

- Procedural tag assignment (how tags are automatically derived) is designed separately after this library is finalized.
- LLM will likely handle tag updates at Layers 4+ where judgment and context are needed.
- Tag library is defined as a JSON config for easy modification.
- The existing `affects_tags` field on evaluator output maps to Layer 2 tags.
- Existing `tag_relevance.py` category:value parsing already supports this format.
