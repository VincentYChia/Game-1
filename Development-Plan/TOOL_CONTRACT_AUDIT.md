# Tool Contract Audit

**Date**: 2026-04-24
**Purpose**: Authoritative reference for authoring WES tool prompts. Every claim is traced to code with file + line refs. Use this doc to understand exactly what each tool can emit.
**Scope**: 8 tool domains — Materials, Nodes, Hostiles, Skills, Titles, Chunks, NPCs, Quests. NPCs + Quests require schema overhaul before tool work (see memory files `npc_schema_overhaul_v3.md`, `quest_lifecycle_design.md`), so they are not exhaustively documented here.

**Companion**: `PLACEHOLDER_FURNISHING_WORKSHEET.md` is the action list. This doc is the *how* / *reality*.

---

## 0. Summary of Most Load-Bearing Findings

1. **Three distinct tag systems** exist — functional combat tags, descriptive content tags, and WMS narrative tags. They live in different files, are validated differently, and have different growth rules.
2. **ChunkType enum is code-locked** (`data/models/world.py:230-268`, 21 values). A new chunkType in JSON is stored but never matched at runtime — silently dead.
3. **ResourceType enum is code-locked** (`data/models/world.py:68-136`, 38 values). A new resourceId in JSON will crash `Chunk.spawn_resources` with `ValueError`.
4. **Materials `metadata.tags` silently ignored** by the standard `MaterialDatabase.load_from_file()`. Stored on disk but never read into the live dataclass.
5. **Title bonus casing bug**: `title_db._map_title_bonuses()` normalizes camelCase JSON → snake_case internal; but `TitleSystem.get_total_bonus()` does a literal dict-key match with no normalization. Most camelCase `get_total_bonus('attackSpeed')` calls silently return 0.
6. **Most enums are free-form strings**. Only ResourceType, ChunkType, AIState, SkillDatabase.durations enforce vocabulary in code.
7. **All cross-references are silent-skip**. Missing materialId in a drop list is not a load error — it becomes an inventory entry with no material definition.

---

## 1. The Three Tag Systems

### 1a. Functional Combat Tags — `Definitions.JSON/tag-definitions.JSON`

- **Purpose**: drive `effect_executor.py` dispatch. Combat abilities, skill effects, enchantments.
- **Registry class**: `core/tag_system.py` → `TagRegistry` singleton.
- **11 categories**, each with a locked value set:
  - `equipment`: `1H, 2H, versatile`
  - `geometry`: `single_target, chain, cone, circle, beam, projectile, pierce, splash`
  - `damage_type`: `physical, slashing, piercing, crushing, fire, frost, lightning, poison, holy, shadow, arcane, chaos, energy`
  - `status_debuff`: `burn, freeze, chill, slow, stun, root, bleed, poison_status, shock, weaken`
  - `status_buff`: `haste, quicken, empower, fortify, regeneration, shield, barrier, invisible`
  - `special`: `lifesteal, vampiric, reflect, thorns, knockback, pull, teleport, summon, dash, charge, phase, execute, critical`
  - `trigger`: `on_hit, on_kill, on_damage, on_crit, on_contact, on_proximity, passive, active, instant`
  - `context`: `self, ally, friendly, enemy, hostile, all, player, turret, device, construct, undead, mechanical`
  - `class`: `warrior, ranger, scholar, artisan, scavenger, adventurer`
  - `playstyle`: `melee, ranged, magic, crafting, gathering, balanced, tanky, agile, caster`
  - `armor_type`: `heavy, medium, light, robes`
- **Per-tag fields**: category, description, priority, default_params, conflicts_with, aliases, synergies, context_behavior (holy+undead×1.5, etc.)
- **Load path**: `effect_executor.execute_effect(source, target, tags, params)` → `tag_parser.parse(tags, params)` → `EffectConfig` → damage/status/geometry dispatch.
- **Unknown tag behavior**: warning logged (`tag_parser.py:61`), tag ignored, execution continues.
- **Tool implication**: **Skills' functional `tags` and Enemy abilities' `tags` MUST be drawn from this registry.** Descriptive categorization tags go elsewhere.

### 1b. Descriptive Tags — Scattered `metadata.tags` in content JSONs

- **Purpose**: categorize content for UI/search, CNN training input, stat_tracker filtering, narrative relevance.
- **No central registry**. Tags live in the JSONs themselves.
- **Current inventory** (scraped via `tools/tag_collector.py`, 235 unique tags across 626 files):
  - Materials: 53 tags (see §2.2.1)
  - Nodes: 50 tags
  - Hostiles: 41 tags (mix of descriptive + functional — some combat tags leak in)
  - Skills: 65 tags (same mix)
  - Recipes: 136 tags
  - Chunks: 36 tags
  - NPCs: 8 tags
  - Quests: 7 tags
  - Classes: 30 tags
  - Stations: 17 tags
- **Growth rule** (user directive): don't invent. If a tool emits a novel tag, log it as flagged for designer review. Do not auto-accept.
- **Known hazard**: **Materials' `metadata.tags` is IGNORED by the standard loader.** See §2.2.

### 1c. WMS Narrative/Structural Tags — `world_system/world_memory/tag_library.py`

- **Purpose**: World Memory System event indexing and narrative weaving.
- **Format**: `namespace:value` (e.g., `domain:combat`, `species:wolf`, `tier:1`, `locality:whispering_woods`).
- **65 categories**, 7 layers. Key-tags updated; significance recreated at every layer.
- **Out of scope** for the tool prompts (this is for WNS, not WES tools), but NPCs and Quests will carry these alongside the content tags.

---

## 2. Per-Domain Reference

### 2.1 Shared behaviors across domains

- **Loader silent-fails**: No domain validates cross-references at load time. A hostile dropping a non-existent material loads cleanly; the material is never found at runtime and silently produces no item.
- **Tier is convention**: tiers 1-4 are an honored convention but no loader enforces `1 <= tier <= 4`.
- **Icon paths auto-generated**: most loaders synthesize `iconPath` from the ID if missing (e.g., `materials/{id}.png`). Tool prompts should not emit `iconPath`.

---

### 2.2 Materials — `items.JSON/items-materials-*.JSON`

**Loader**: `data/databases/material_db.py` → `MaterialDatabase` singleton.
**Model**: `data/models/materials.py` → `MaterialDefinition` dataclass.

#### 2.2.1 Fields parsed by the loader

| Field | JSON key | Type | Default | Source |
|---|---|---|---|---|
| material_id | materialId | str | (required) | `material_db.py:27` |
| name | name | str | `''` | `material_db.py:28` |
| tier | tier | int | 1 | `material_db.py:29` |
| category | category | str | 'unknown' | `material_db.py:30` |
| rarity | rarity | str | 'common' | `material_db.py:50` |
| description | description | str | `''` | `material_db.py:35` |
| max_stack | maxStack | int | 99 | `material_db.py:52` |
| icon_path | iconPath | str | auto | `material_db.py:31-42` |
| placeable | flags.placeable | bool | False | `material_db.py:55` |
| item_type | type | str | `''` | `material_db.py:56` |
| item_subtype | subtype | str | `''` | `material_db.py:57` |
| effect | effect | str | `''` | `material_db.py:58` |
| effect_tags | effectTags | list | [] | `material_db.py:59` |
| effect_params | effectParams | dict | {} | `material_db.py:60` |
| properties | properties | dict | {} | `material_db.py:53` (never read by consumers — **dead**) |

#### 2.2.2 **KNOWN BUG — metadata.tags silently dropped**

The standard loader (`load_from_file`) does **not** read `metadata.narrative` or `metadata.tags` from materials JSONs (verified: no reference in material_db.py primary load path). Two sub-loaders (`load_refining_items`, `load_stackable_items`) DO read `metadata.narrative` into `description` (lines 115, 183) but STILL ignore `metadata.tags`.

Current material JSONs contain 53 unique tags via `metadata.tags`, all of which are invisible at runtime.

**Tool-author options**:
1. Fix the loader to read `metadata.tags` into `MaterialDefinition` (preferred — preserves existing JSON shape). ~3-line edit.
2. Have the tool emit tags at top level (`"tags": [...]`) instead of `metadata.tags`. Breaks symmetry with existing data.

**Decision**: FIX the loader. See §5 for patch location.

#### 2.2.3 Enum vocabularies

| Field | Code-enforced? | Observed values |
|---|---|---|
| category | NO (free-form) | `elemental, metal, monster_drop, stone, wood` |
| rarity | NO (free-form) | `common, uncommon, rare, epic, legendary` (no `mythic`, no `unique` in current data) |
| tier | NO | 1-4 (convention) |

#### 2.2.4 Descriptive tag library (current)

From 57 materials:

```
advanced, air, ancient, basic, blood, carapace, chaos, common, crafting, dark,
durable, earth, elemental, essence, fang, fine, fire, fishing, flexible, gel,
ice, impossible, layered, leather, legendary, light, lightning, living, magical,
memory, metal, metallic, monster, mythical, precious, quality, quantum, radiant,
rare, refined, scales, sharp, spectral, standard, starter, stone, strong,
temporal, uncommon, versatile, void, water, wood
```

#### 2.2.5 Cross-reference surface

- **Missing materialId is silent everywhere** — inventory stacks, recipe outputs, enemy drops all handle `None` from `MaterialDatabase.get_material()` gracefully. Item shows as raw string ID with no icon; recipes complete but consume/produce invalid IDs.

#### 2.2.6 Minimal valid output (for tool prompt)

```json
{
  "materialId": "sand_dust",
  "name": "Sand Dust",
  "tier": 1,
  "rarity": "common",
  "category": "stone",
  "metadata": {
    "narrative": "Fine granular silica from wind-blasted dunes.",
    "tags": ["stone", "basic", "starter"]
  }
}
```

Required for tool correctness: `materialId, name, tier, category, rarity, metadata.narrative, metadata.tags` (tags require the loader fix above).

---

### 2.3 Nodes — `Definitions.JSON/resource-node-1.JSON`

**Loader**: `data/databases/resource_node_db.py` → `ResourceNodeDatabase`.
**Consumer**: `systems/chunk.py:spawn_resources` (line 274-339), `systems/natural_resource.py`.

#### 2.3.1 **ARCHITECTURAL BLOCKER — ResourceType is a Python enum**

`data/models/world.py:68-136` declares `class ResourceType(Enum)` with 38 members: 8 trees + 8 ores + 12 stones + 13 fishing spots + 1 generic fallback.

- **`Chunk.spawn_resources` calls `ResourceType(node_def.resource_id)` at `systems/chunk.py:333`.** If `resource_id` isn't in the enum, it raises `ValueError` and is caught by a bare `except ValueError: continue` — meaning the node silently fails to spawn.
- **`RESOURCE_TIERS` dict** (`data/models/world.py:158-217`) also must have an entry for every ResourceType or fallback spawning fails.

**Implication**: A tool that emits genuinely new node types cannot commit via JSON alone. For v4, the Nodes tool must pick from the existing 38 ResourceType values (then vary name/tier/drops/narrative/tags around that skeleton), OR we refactor ResourceType to string IDs.

**Recommendation**: v4 ships the tool with a locked node-type allow-list pointing at the 38 existing values. Post-release: refactor to data-driven.

#### 2.3.2 Node fields parsed

| Field | JSON key | Type | Notes |
|---|---|---|---|
| resourceId | resourceId | str | **Must be in ResourceType enum** |
| name | name | str | |
| category | category | str | |
| tier | tier | int | |
| requiredTool | requiredTool | str | |
| baseHealth | baseHealth | int | T1=100, T2=200, T3=400, T4=800 (convention) |
| drops | drops | list | Each drop: `{materialId, quantity, chance}` |
| respawnTime | respawnTime | str/null | |
| metadata.narrative | | str | |
| metadata.tags | | list | **Read here (unlike materials)** |

#### 2.3.3 Enum vocabularies

| Field | Locked? | Valid values | Fallback |
|---|---|---|---|
| category | NO | `tree, ore, stone, fishing` (observed) | Used for chunk filtering — unknowns silently skipped |
| requiredTool | NO | `axe, pickaxe, fishing_rod` | No validation |
| respawnTime | Map in code | `fast, normal, slow, very_slow, null` → 30/60/120/300 seconds | Unknown → 60s |
| drops[].quantity | Map in code | `few, several, many, abundant` → (1,2), (2,4), (3,5), (4,8) | Unknown → (1,3) |
| drops[].chance | Map in code | `guaranteed, high, moderate, low, rare, improbable` → 1.0/0.8/0.5/0.25/0.1/0.05 | Unknown → 1.0 |
| ResourceType | **YES — Python enum** | 38 values (see §2.3.1) | ValueError on unknown |

Source mappings: `data/models/resources.py:14-22` (quantity), `:24-34` (chance), `:51-61` (respawnTime).

Current data also has `respawnTime: "quick"` appearing — which is **NOT in the mapping**. Verify against the current code whether this is an alias or a silent fallback. (Collector reported: `['fast', 'normal', 'quick', 'slow', 'very_slow']`.)

#### 2.3.4 Chunk-template cross-ref

A node only spawns if at least one Chunk-template's `resourceDensity` dict has the node's `resourceId` as a key. A node not referenced by any template is **dead** — won't spawn anywhere.

#### 2.3.5 Descriptive tag library (current)

From 36 nodes + fishing spots:

```
advanced, ancient, carp, chaos, common, crystal, durable, fine, fire, fishing,
flexible, frostback, ice, impossible, layered, legendary, leviathan, light,
lighteye, lightning, living, magical, memory, metal, metallic, minnow, mythical,
ore, phoenixkoi, precious, quality, quantum, radiant, rare, shadow, shadowgill,
sharp, standard, starter, stone, stormfin, sunfish, tempesteel, temporal, tree,
void, voidswimmer, volcanic, water, wood
```

---

### 2.4 Hostiles — `Definitions.JSON/hostiles-*.JSON`

**Loader**: `Combat/enemy.py` → `EnemyDatabase` (note: in `Combat/`, not `data/databases/`).
**Model**: `Combat/enemy.py:93-122` (EnemyDefinition), `:44-60` (SpecialAbility).
**Consumer**: `Combat/combat_manager.py` (damage pipeline, ability dispatch).

#### 2.4.1 Load order is significant

File is processed in one pass:
1. `abilities` array parsed first → `ability_map: Dict[str, SpecialAbility]` (`enemy.py:200-217`).
2. `enemies` array parsed second; `aiPattern.specialAbilities` validated against `ability_map` (`enemy.py:254`).
3. Missing ability → warning logged (`:257`), ability skipped from enemy, load continues.

**Tool implication**: for atomic co-generation of a new enemy + new ability, the tool output MUST place abilities BEFORE enemies in the emitted JSON, and both must live in the same file.

#### 2.4.2 Enemy fields

| Field | JSON key | Type | Notes |
|---|---|---|---|
| enemy_id | enemyId | str | |
| name | name | str | |
| tier | tier | int | Convention, not enforced |
| category | category | str | See §2.4.3 |
| behavior | behavior | str | Free-form |
| stats | stats | dict | `{health, damage[min,max], defense, speed, aggroRange, attackSpeed}` |
| drops | drops | list | Each: `{materialId, quantity[min,max], chance: str→float}` |
| aiPattern | aiPattern | dict | See §2.4.4 |
| metadata | metadata | dict | `{narrative, tags}` |

Drop `chance` mapping: `guaranteed=1.0, high=0.75, moderate=0.5, low=0.25` (`enemy.py:177-184`).

Derived at load time, not from JSON: `visual_size`, `hurtbox_radius` (from category+tier, `:150-162`); `attacks` (from `attack_profile_generator`, `:293-294`).

#### 2.4.3 Category enum

**Soft-enforced** via `_CATEGORY_BASE_SIZE` dict at `enemy.py:129-139`:

```
beast, ooze, insect, construct, undead, elemental, aberration, humanoid, dragon
```

Defaults to `beast` if missing. Unknown categories load but get default size scaling.

#### 2.4.4 AIPattern structure

Fields within `aiPattern`:
- `defaultState` — **Hard-enum** via `AIState`: `idle, wander, patrol, guard` (4 mappable values). Unknown defaults to `IDLE`.
- `aggroOnDamage` — bool
- `aggroOnProximity` — bool
- `fleeAtHealth` — float 0-1
- `callForHelpRadius` — float
- `packCoordination` — bool
- `specialAbilities` — list of ability_id strings

Other AIState values (`CHASE, ATTACK, FLEE, DEAD, CORPSE`) are entered dynamically at runtime; JSON cannot set these.

#### 2.4.5 Behavior — free-form (soft convention)

Observed values: `passive_patrol, aggressive_pack, boss_encounter, stationary, aggressive_swarm, docile_wander, territorial, aggressive_phase`.

Only `"boss" in behavior.lower()` check drives runtime branch (`enemy.py:476`). Everything else is display/convention.

#### 2.4.6 Tier stat bands (observed, NOT enforced)

Use these as guidance in the tool prompt:

| Tier | Health | Damage min-max | Defense | Speed | AggroRange | AttackSpeed |
|---|---|---|---|---|---|---|
| T1 | 50-100 | 5-12 | 2-12 | 0.5-1.2 | 3-5 | 0.8-1.0 |
| T2 | 120-250 | 15-30 | 8-25 | 0.7-1.4 | 6-8 | 0.8-1.2 |
| T3 | 500-800 | 40-80 | 25-40 | 0.5-1.6 | 10-12 | 0.6-1.5 |
| T4 | 400-2000 | 60-180 | 15-60 | 0.6-1.5 | 12-20 | 0.7-1.3 |

Bosses intentionally break T4 ranges upward.

#### 2.4.7 Ability library (21 entries in `hostiles-1.JSON`)

Full list (abilityId → tags):

| abilityId | tags |
|---|---|
| howl_buff | circle, ally, empower, haste |
| leap_attack | physical, single, bleed, player |
| acid_damage_over_time | poison, circle, poison_status, player |
| split_on_damage | summon, self |
| elemental_burst | arcane, circle, knockback, player |
| charge_attack | physical, beam, stun, player |
| earthquake_stomp | physical, circle, stun, player |
| shell_shield | self, shield, fortify |
| rampage | self, haste, empower, enrage |
| ground_slam | physical, cone, knockback, player |
| stone_armor | self, fortify, slow |
| crystal_beam | arcane, beam, pierce, player |
| refraction_shield | self, shield, reflect |
| summon_shards | summon, circle |
| phase_shift | self, teleport, invisible |
| life_drain | shadow, cone, lifesteal, player |
| teleport | self, teleport |
| reality_warp | chaos, circle, confuse, vulnerable |
| void_rift | shadow, circle, pull |
| temporal_distortion | arcane, circle, slow, silence |
| chaos_burst | chaos, chain, random |

Note some tags here (`enrage, confuse, random, silence, single`) are NOT in `tag-definitions.JSON` — they're currently descriptive-only in this context.

#### 2.4.8 Descriptive tag library (current, 41 from enemies)

```
aggressive, arcane, beam, beetle, boss, burn, chain, circle, common, cone,
construct, docile, end-game, entity, epic, fire, golem, knockback, lightning,
mid-game, mythical, passive, phase, physical, pierce, player, pull, rare,
reality-bender, shadow, shock, slime, slow, starter, stun, territorial,
uncommon, vulnerable, weaken, wolf, wraith
```

---

### 2.5 Skills — `Skills/skills-*.JSON`

**Loader**: `data/databases/skill_db.py` → `SkillDatabase`.
**Model**: `data/models/skills.py`.
**Effect metadata**: `Skills/skills-base-effects-1.JSON` (magnitude → numeric multiplier map).
**Consumer**: `entities/components/skill_manager.py`, `core/effect_executor.py`.

#### 2.5.1 Fields parsed

- Top-level: `skillId, name, tier, rarity, categories, description, narrative, tags, combatTags, combatParams, iconPath`
- `effect`: `{type, category, magnitude, target, duration, additionalEffects}`
- `cost`: `{mana, cooldown}`
- `evolution`: `{canEvolve, nextSkillId, requirement}` (optional)
- `requirements`: `{characterLevel, stats: {STR, DEF, VIT, LCK, AGI, INT}, titles: [title_id]}`

#### 2.5.2 Effect type enum (10 values, from `skills-base-effects-1.JSON`)

`empower, quicken, fortify, enrich, pierce, restore, regenerate, elevate, devastate, transcend`

**Effect type → valid categories** (observed in skills-1.JSON + base-effects file):

| Effect type | Categories |
|---|---|
| empower | damage, smithing, alchemy, engineering, refining, enchanting, mining, forestry |
| quicken | combat, movement, smithing, alchemy, engineering, refining, mining, forestry |
| fortify | defense, durability |
| restore | defense, durability |
| enrich | mining, forestry |
| elevate | mining, refining, enchanting, smithing |
| pierce | damage, enchanting, combat |
| regenerate | defense |
| devastate | damage, mining, combat |
| transcend | mining, smithing, alchemy, engineering |

**Enforcement note**: Category is NOT validated in effect_executor code. The matrix is convention observed in base-effects file; tool should enforce it.

#### 2.5.3 Magnitude → multiplier (enum-locked by file)

| magnitude | empower | quicken | fortify | pierce | enrich | restore | regenerate | elevate | devastate | transcend |
|---|---|---|---|---|---|---|---|---|---|---|
| minor | 0.5 | 0.3 | 10 | 0.1 | 1 | 50 | 3 | 0.15 | 3 | 1 |
| moderate | 1.0 | 0.5 | 20 | 0.15 | 3 | 100 | 5 | 0.25 | 5 | 2 |
| major | 2.0 | 0.75 | 40 | 0.25 | 6 | 200 | 10 | 0.4 | 7 | 3 |
| extreme | 4.0 | 1.0 | 80 | 0.4 | 12 | 400 | 20 | 0.6 | 10 | 4 |

Source: `Skills/skills-base-effects-1.JSON` + `skill_manager.py:24-46` (fallback hardcode).

#### 2.5.4 Duration → seconds (hard-enum in code)

`skill_db.py:17`:

`instant=0, brief=15, moderate=30, long=60, extended=120`

Unknown → 0.

#### 2.5.5 Target enum (convention only)

`self, enemy, resource_node, area` — no code validation.

#### 2.5.6 Cost

- **mana**: accepts string enums `low=30, moderate=60, high=100, extreme=150` OR direct int.
- **cooldown**: accepts string enums `short=120, moderate=300, long=600, extreme=1200` OR direct int (seconds).
- **No tier band enforcement**. The user's draft tier bands (T1: 20-70, etc.) are convention.

#### 2.5.7 Requirements enforcement

Checked ONLY at learn-time in `skill_manager.can_learn_skill()`, NOT at activation:
- `characterLevel` → `character.leveling.level` (`:64-65`)
- `stats` → 6 attribute map (STR→strength, etc.) minimum values (`:68-81`)
- `titles` → earned-title membership (`:84-89`)

#### 2.5.8 Tag fields — TWO tag systems

- **`tags`** (descriptive): free-form, NOT used by effect_executor. Example: `["damage_boost", "combat", "basic"]`.
- **`combatTags`** (functional): resolved via tag registry. Must be in `tag-definitions.JSON` — unknown tags produce warnings but do not block.

Most current skill JSONs use `tags` only (no `combatTags`), which means their combat behavior comes from `effect.type` + params, not from the tag registry.

---

### 2.6 Titles — `progression/titles-*.JSON`

**Loader**: `data/databases/title_db.py` → `TitleDatabase`.
**Model**: `data/models/titles.py` → `TitleDefinition`.
**Consumer**: `systems/title_system.py` → `TitleSystem.get_total_bonus(key)`.

#### 2.6.1 **KNOWN BUG — camelCase/snake_case mismatch**

`title_db._map_title_bonuses()` (`:98-120`) normalizes camelCase JSON bonus keys → snake_case internal keys (e.g., `miningDamage → mining_damage`). Some keys also rename (`smithingTime → smithing_speed`, `refiningPrecision → refining_speed`, `criticalChance → crit_chance`).

`TitleSystem.get_total_bonus(bonus_type)` does a **literal** dict lookup on the normalized store (`title_system.py:88-93`). No alias or case normalization.

**Consumer call pattern inventory** (what the code actually queries, grouped by casing):

| CamelCase queries (mostly broken — won't match snake_case stored) | Snake_case queries (working) |
|---|---|
| `alchemyQuality` (game_engine) | `fishing_accuracy` (fishing.py) |
| `alchemyTime` | `fishing_speed` |
| `alloyQuality` | `fishing_yield` |
| `attackSpeed` (character.py) | `luck_stat` (fishing.py) |
| `counterChance` (combat_manager) | `rare_fish_chance` |
| `criticalChance` (combat_manager) | |
| `durabilityBonus` | |
| `enchantingQuality/Time` | |
| `engineeringQuality/Time` | |
| `firstTryBonus` | |
| `legendaryDropRate` | |
| `luckStat` | |
| `meleeDamage` (combat_manager, 3 calls) | |
| `rareDropRate` | |
| `refiningPrecision` | |
| `smithingQuality/Time` | |

**Implication**: Most title bonuses in game are silently ineffective right now. Only fishing bonuses work end-to-end.

**For the Titles tool prompt**: emit bonuses using the exact casing the **consumer code queries** (see table above). When in doubt, verify by grepping `get_total_bonus('<your_name>')`. OR propose a fix to `get_total_bonus()` that does case-normalization and alias resolution.

#### 2.6.2 Bonus field names in current JSONs (30 total)

```
alloyQuality, attackSpeed, combatSkillExp, counterChance, criticalChance,
dragonDamage, durabilityBonus, elementalAfinity (TYPO — should be elementalAffinity),
fireOreChance, fireResistance, firstTryBonus, fishingAccuracy, fishingSpeed,
fishingYield, forestryDamage, forestrySpeed, legendaryChance, legendaryDropRate,
luckStat, materialYield, meleeDamage, miningDamage, miningSpeed, rareDropRate,
rareFishChance, rareOreChance, rareWoodChance, refiningPrecision, smithingQuality,
smithingTime
```

Of these, only ~12 have any consumer in the game code (see §2.6.1). The rest are purely cosmetic.

#### 2.6.3 Enum vocabularies

| Field | Locked? | Valid values |
|---|---|---|
| titleType | NO (convention) | `combat, crafting, gathering, utility` |
| difficultyTier | NO (convention) | `novice, apprentice, journeyman, expert, master, special` |
| acquisitionMethod | NO (convention) | `guaranteed_milestone, event_based_rng, special_achievement, hidden_discovery` |

#### 2.6.4 Prerequisites — `UnlockCondition` taxonomy

`data/models/unlock_conditions.py` + `ConditionFactory.create_from_json()` accepts these `type` values:

| type | Required fields | Semantics |
|---|---|---|
| `level` | `min_level` | character.leveling.level >= min_level |
| `stat` | `requirements: {stat: value}` OR `stat_name, min_value` | Attribute minimums |
| `activity` | `activity, min_count` | legacy — character.activities.get_count |
| `stat_tracker` | `stat_path, min_value` | navigates `character.stat_tracker` via dotted attr path |
| `title` | `required_titles: [ids]` OR `required_title: id` | earned-title membership |
| `skill` | `required_skills: [ids]` | known-skill membership |
| `quest` | `required_quests: [ids]` | completed-quest membership |
| `class` | `required_class: id` | current class match |

Composed via `UnlockRequirements` (AND logic across conditions).

#### 2.6.5 Stat paths used today

Current titles use **17 legacy-style stat paths** (`gathering_totals.*, combat_kills.*`, etc.) which may or may not match actual stat_tracker attribute names. This is another known-bug surface area — verify each path against `stat_tracker.py` attribute tree before emitting.

For the tool prompt, conservatively use only paths that are verified-live. Recommend starting with the stat paths that existing novice titles use (they presumably work):
- `gathering_totals.total_ores_mined`
- `gathering_totals.total_trees_chopped`
- `crafting_by_discipline.smithing.total_crafts`
- `combat_kills.total_kills`

Verify these exist before commit.

#### 2.6.6 `stat_tracker.py` — 74 `record_*` methods (event emission side)

See the live inventory via `tools/tag_collector.py` run artefact, or grep `record_` in `entities/components/stat_tracker.py`. Categories represented: combat, crafting, gathering, exploration, dungeon, economy, encyclopedia, fishing, barriers.

**The stat_tracker attribute-navigation tree** (what `StatTrackerCondition.stat_path` traverses) is separate from the `record_*` method names and needs a deeper trace. Flag for targeted investigation before the Titles prompt ships.

---

### 2.7 Chunks (biome templates) — `Definitions.JSON/Chunk-templates-*.JSON`

**Loader**: `Combat/combat_manager.py:208-228` (`_load_chunk_templates`).
**Model**: no dataclass — raw dict stored.
**Consumer**: `Combat/combat_manager.py:265-269` (`_get_chunk_template`), `systems/chunk.py`, `systems/biome_generator.py`.

#### 2.7.1 **ARCHITECTURAL BLOCKER — ChunkType is a Python enum**

`data/models/world.py:230-268` declares `class ChunkType(Enum)` with **21 values**:

**Legacy (12)**: `PEACEFUL_FOREST, PEACEFUL_QUARRY, PEACEFUL_CAVE, DANGEROUS_FOREST, DANGEROUS_QUARRY, DANGEROUS_CAVE, RARE_HIDDEN_FOREST, RARE_ANCIENT_QUARRY, RARE_DEEP_CAVE, WATER_LAKE, WATER_RIVER, WATER_CURSED_SWAMP`

**Geographic (9)**: `DENSE_FOREST, ROCKY_FOREST, DEEP_CAVE, FLOODED_CAVE, CRYSTAL_CAVE, ROCKY_HIGHLANDS, OVERGROWN_RUINS, BARREN_WASTE, WETLAND`

**Behavior on unknown chunkType string in JSON**:
- Template is stored in `self.chunk_templates[<string>]` (line 214)
- Runtime lookup at `:265-269` uses `chunk.chunk_type.value` (an enum instance's string value)
- If the JSON string isn't in the enum, no chunk will ever have `chunk_type.value == <string>` → template is unreachable → **dead biome**.

**Implication**: Same as ResourceType. v4 Chunks tool must pick from the existing 21 chunkType values. Post-release: refactor to data-driven.

#### 2.7.2 Template fields parsed (all raw dict)

- `chunkType` — **must match ChunkType enum value**
- `name, category, theme` — metadata
- `resourceDensity` — `{resourceId: {density, tierBias}}` (resourceId must be in ResourceType OR silently skipped)
- `enemySpawns` — `{enemyId: {density, tier}}` (enemyId must be in EnemyDatabase OR silently skipped)
- `generationRules` — `{rollWeight, spawnAreaAllowed, adjacencyPreference}`
- `tilePattern` — `{waterCoverage, hasIslands, isToxic}` for water chunks
- `metadata` — `{narrative, tags}`

#### 2.7.3 Enum vocabularies

| Field | Locked? | Valid values |
|---|---|---|
| chunkType | **YES — Python enum** | 21 values above |
| category | NO (convention) | `peaceful, dangerous, rare, water, rare_water` |
| theme | NO (convention) | `forest, quarry, cave, water` |
| density | Map in code | `very_low=0.5x, low=0.75x, moderate=1x, high=2x, very_high=3x` |
| tierBias | NO (convention) | `low, mid, high, legendary` |

Density map: `Combat/combat_manager.py:39-45` (`CombatConfig.density_weights`).

#### 2.7.4 Dead decoration fields

- `generationRules.spawnAreaAllowed` — **never checked in code**
- `generationRules.adjacencyPreference` — **never used in code**

Tool can emit these for documentation, but they have no runtime effect.

#### 2.7.5 Cross-reference behaviors

- **Missing resourceId in resourceDensity**: silently skipped during spawn (chunk.py, resource_node_db iteration).
- **Missing enemyId in enemySpawns**: silently skipped (combat_manager.py:327-329).
- **Invalid density/tierBias value**: silently defaulted to neutral weighting.

---

### 2.8 NPCs and Quests

**Out of scope for this audit.** Schema overhauls required before tool prompts. See:
- Memory: `npc_schema_overhaul_v3.md` — static-narrative + dynamic-context split
- Memory: `quest_lifecycle_design.md` — in-progress prose-reward + archived structured metadata

When those schemas are designed, audit their loaders and consumers the same way.

---

## 3. Cross-Cutting Implications for Tool Prompts

### 3.1 What the prompts MUST constrain

1. **Every tool prompt ships with the current tag library** for its domain as a locked allow-list. New tags flagged for review.
2. **Skills' functional `combatTags`** must be drawn from `tag-definitions.JSON`. Descriptive `tags` are free-form.
3. **Hostiles' ability tags** must either compose from `tag-definitions.JSON` or be explicitly flagged as new descriptive-only tags.
4. **Hostile ability IDs** (used in `aiPattern.specialAbilities`) must resolve to abilities emitted in the same output batch or existing in registry.
5. **Drops' materialIds, enemySpawns' enemyIds, resourceDensity's resourceIds** — must resolve via registry OR be co-emitted atomically.
6. **Nodes' `resourceId` must be in ResourceType enum** (v4 constraint) — tool picks from the 38 existing values.
7. **Chunks' `chunkType` must be in ChunkType enum** (v4 constraint) — tool picks from the 21 existing values.

### 3.2 What the prompts must TOLERATE

1. Magnitude/duration/target: use the enum-locked words, not numeric values, where possible.
2. Tier conventions (T1=100hp for hostiles, etc.): emit close to the observed band; validator can tighten.
3. Emit iconPath? NO. The loaders auto-generate from ID.

### 3.3 Content Registry validation burden

The `content_registry` should validate the following at commit:

- [ ] **Strict**: materialId/resourceId/enemyId/chunkType references resolve
- [ ] **Strict**: combatTags on skills and abilities are all in tag-definitions.JSON
- [ ] **Strict**: `effect.type` is one of the 10 values; `effect.magnitude` is one of 4; `effect.duration` is one of 5
- [ ] **Strict**: resourceId is in ResourceType enum (until refactored)
- [ ] **Strict**: chunkType is in ChunkType enum (until refactored)
- [ ] **Warning**: new descriptive tag appeared (log to `new_tags_flagged.json`)
- [ ] **Warning**: title bonus field not in consumer-verified list (see §2.6.1)

---

## 4. Known Bugs Surfaced During Audit (Not My Problem To Fix, But Document)

1. **Materials' `metadata.tags` silently dropped by standard loader** — §2.2.2. Fix = 2-3 line edit to `material_db.py` at line ~50.
2. **Title bonus camelCase/snake_case mismatch** — §2.6.1. Fix = case-normalization + alias table in `TitleSystem.get_total_bonus`.
3. **`elementalAfinity` typo in titles-1.JSON** — should be `elementalAffinity`. Data-side fix.
4. **`respawnTime: "quick"` used in nodes but not in mapping** — §2.3.3. Either add to mapping or migrate data.
5. **ResourceType and ChunkType are code-locked** — §2.3.1, §2.7.1. Refactor to data-driven is the real fix; v4 lives with the constraint.

Flag these as separate tickets. Do NOT mix with the tool prompt work unless explicitly instructed.

---

## 5. Recommended Loader Patch for Materials `metadata.tags`

**File**: `Game-1-modular/data/databases/material_db.py`

Around line 50 (inside `_load_standard_materials` or equivalent standard load path), add:

```python
# Read descriptive tags from metadata (was silently dropped)
metadata = item_data.get('metadata', {})
tags = metadata.get('tags', [])
narrative = metadata.get('narrative', '')
```

Then pass `tags` into `MaterialDefinition(...)` as a new `descriptive_tags: List[str] = field(default_factory=list)` field (add to `data/models/materials.py:MaterialDefinition`).

Trivial edit, but **needed before Materials tool commits** or all generated material tags will be invisible.

---

## 6. Tool Build Order Revisited

Given the audit findings, the recommended build order (unchanged from prior plan, but now with specific prereqs):

1. **Materials** — but patch the `metadata.tags` loader bug first.
2. **Titles** — either fix `get_total_bonus` casing OR carefully constrain to consumer-verified bonus names.
3. **Nodes** — constrain to 38 existing ResourceType values.
4. **Skills** — enforce effect type/category/magnitude/duration enums.
5. **Hostiles** — atomic abilities-then-enemies output; constrain ability tags to tag-definitions.JSON.
6. **Chunks** — constrain to 21 existing ChunkType values; cross-check all resourceDensity/enemySpawns refs.

NPCs (Step 7) pauses for schema overhaul with user.

---

## Appendix A: Tag Registry File Map

| Purpose | File | Who reads it |
|---|---|---|
| Functional combat tags (SSOT) | `Definitions.JSON/tag-definitions.JSON` | `core/tag_system.py → TagRegistry` |
| Descriptive tags per domain | scattered `metadata.tags` | Mostly nobody (see §2.2.2) |
| WMS narrative tags (SSOT) | `world_system/world_memory/tag_library.py` (Python, not JSON) | WMS event indexing |
| Faction tags (durable registry) | `world_system/config/tag-registry.json` | FactionSystem |
| Narrative tag taxonomy (WNS, draft) | missing — `narrative-tag-definitions.JSON` was flagged in prior session as NOT actually committed | placeholder still open |

---

**End of audit.**

This document is the authoritative reference for tool prompt authoring as of 2026-04-24. Subsequent audits should append sections, not overwrite, so the history of what-was-true-when is preserved.
