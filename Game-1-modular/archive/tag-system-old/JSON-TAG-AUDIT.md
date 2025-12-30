# JSON Tag Field Audit & Implementation Plan

**Version:** 1.0
**Date:** 2025-12-17
**Purpose:** Comprehensive catalog of ALL tag fields across the codebase with implementation status and plans

---

## Executive Summary

This document catalogs every JSON file with tag fields, classifies their purpose, documents current implementation status, and provides actionable plans for full tag integration.

### Tag Philosophy Recap

Tags represent **conceptual descriptors** that different systems interpret differently:

- **Metadata Tags**: Describe WHAT something IS (for filtering, UI, categorization)
- **Effect Tags**: Describe WHAT something DOES (for effect executor, combat mechanics)
- **Hybrid**: Some systems use BOTH types (e.g., skills have both `tags` and `combatTags`)

---

## 1. JSON Files WITH Tag Fields

### 1.1 Chunks (`Definitions.JSON/Chunk-templates-1.JSON`)

**Field:** `metadata.tags`
**Tag Type:** Metadata (Descriptive)
**Example Tags:** `["forest", "safe", "wood-rich", "starter"]`

**Current Usage:**
```json
{
  "metadata": {
    "tags": ["forest", "safe", "wood-rich", "starter"]
  },
  "chunkType": "peaceful_forest",
  "resourceDensity": { ... },
  "enemySpawns": { ... }
}
```

**Tag Semantics:**
- Position 0: **Biome/Theme** (`forest`, `quarry`, `cave`) - Visual theme and resource types
- Position 1: **Difficulty** (`safe`, `combat`, `rare`) - Enemy density and aggression
- Position 2: **Resource Focus** (`wood-rich`, `ore-quality`, `mixed`) - Primary resource type
- Position 3: **Progression Tier** (`starter`, `mid-game`, `end-game`) - When player should encounter

**Implementation Status:** ❌ NOT IMPLEMENTED

**Implementation Plan:**
1. **Chunk Generation System** - Use tags to:
   - Filter chunk templates based on player progression level
   - Determine adjacency preferences (similar tags spawn near each other)
   - Weight spawn probabilities (more `starter` chunks near spawn)

2. **Spawn Filtering** - Use `starter`/`mid-game`/`end-game` tags:
   - Player level 1-10: Prefer `starter` chunks
   - Player level 11-25: Prefer `mid-game` chunks
   - Player level 26+: Allow `end-game` chunks

3. **Resource Density Modifiers** - Use `wood-rich`/`ore-quality` tags:
   - Apply bonus multipliers to matching resource types
   - Affect drop quality based on tag tier

**Priority:** LOW (world generation is currently static, chunk tags are cosmetic)

---

### 1.2 Materials (`items.JSON/items-materials-1.JSON`)

**Field:** `metadata.tags`
**Tag Type:** Metadata (Descriptive)
**Example Tags:** `["basic", "metal", "starter"]`, `["refined", "wood", "legendary"]`

**Current Usage:**
```json
{
  "metadata": {
    "tags": ["basic", "metal", "starter"]
  },
  "materialId": "copper_ore",
  "category": "metal",
  "tier": 1
}
```

**Tag Semantics:**
- Position 0: **Processing State** (`basic`, `refined`) - Raw ore vs processed ingot
- Position 1: **Category** (`metal`, `wood`, `stone`, `elemental`, `monster`) - Material type
- Position 2: **Quality/Tier** (`starter`, `standard`, `legendary`, `mythical`) - Progression tier
- Position 3+: **Special Properties** (`temporal`, `living`, `void`) - Unique characteristics

**Implementation Status:** ❌ NOT IMPLEMENTED

**Implementation Plan:**
1. **Inventory Filtering** - Use tags for:
   - Quick filter buttons in UI ("Show only metals", "Show refined only")
   - Search functionality (search by tag)
   - Auto-sorting by tag category

2. **Crafting Station Validation** - Use tags to:
   - Verify material suitability (e.g., T3 forge requires refined metals)
   - Highlight valid materials based on recipe requirements

3. **Recipe Discovery Hints** - Use tags to:
   - Suggest compatible materials for experimentation
   - Tag-based recipe recommendations

**Priority:** LOW (QoL feature, not critical for gameplay)

---

### 1.3 Weapons (`items.JSON/items-smithing-2.JSON`)

**Field:** `metadata.tags`
**Tag Type:** Metadata (Descriptive) + Potential Combat Modifiers
**Example Tags:** `["melee", "sword", "versatile", "starter"]`, `["melee", "mace", "2H", "crushing", "armor_breaker"]`

**Current Usage:**
```json
{
  "metadata": {
    "tags": ["melee", "dagger", "1H", "fast", "precision"]
  },
  "itemId": "copper_dagger",
  "statMultipliers": {
    "damage": 0.9,
    "attackSpeed": 1.3
  }
}
```

**Tag Semantics:**
- Position 0: **Range Type** (`melee`, `ranged`) - Attack range category
- Position 1: **Weapon Type** (`sword`, `dagger`, `bow`, `staff`) - Weapon archetype
- Position 2: **Hand Requirement** (`1H`, `2H`, `versatile`) - Equipment slot usage
- Position 3+: **Combat Properties** (`fast`, `precision`, `crushing`, `armor_breaker`, `reach`) - Special behaviors

**Implementation Status:** ⚠️ PARTIALLY IMPLEMENTED
- Weapons exist and have tags
- Tags are NOT used for combat mechanics currently
- `statMultipliers` define behavior, not tags

**Implementation Plan:**

**MEDIUM Priority** - Weapon tags should affect combat:

1. **Hand Requirement Tags** (`1H`, `2H`, `versatile`):
   - `1H`: Can equip shield in off-hand
   - `2H`: Requires both hands, +20% damage multiplier
   - `versatile`: Can use 1H or 2H, bonus damage if 2H

2. **Combat Property Tags**:
   - `fast`: +15% attack speed
   - `precision`: +10% critical hit chance
   - `crushing`: +20% damage vs armored enemies
   - `armor_breaker`: Ignore 25% of enemy defense
   - `reach`: +1 unit attack range
   - `cleaving`: Hits adjacent enemies for 50% damage

3. **Implementation Location:**
   - Modify `Character.calculate_weapon_stats()` to apply tag-based modifiers
   - Check for tags in `metadata.tags` field
   - Apply bonuses additively with `statMultipliers`

**Code Example:**
```python
def calculate_weapon_stats(self, weapon: ItemDefinition):
    base_damage = weapon.statMultipliers.get("damage", 1.0)

    # Apply tag-based modifiers
    weapon_tags = weapon.metadata.get("tags", [])

    if "2H" in weapon_tags:
        base_damage *= 1.2  # Two-handed damage bonus
    if "fast" in weapon_tags:
        attack_speed *= 1.15
    if "precision" in weapon_tags:
        crit_chance += 0.10

    # Continue with existing logic...
```

---

### 1.4 Devices (`items.JSON/items-engineering-1.JSON`)

**Field:** `metadata.tags`
**Tag Type:** Metadata (Descriptive) + Effect Tags (for turrets)
**Example Tags:** `["device", "turret", "fire", "elemental"]`

**Current Usage:**
```json
{
  "metadata": {
    "tags": ["device", "turret", "lightning", "advanced"]
  },
  "itemId": "lightning_cannon",
  "type": "turret"
}
```

**Tag Semantics:**
- Position 0: **Category** (`device`) - Item type
- Position 1: **Device Type** (`turret`, `bomb`, `trap`, `utility`) - Subcategory
- Position 2: **Element/Effect** (`fire`, `lightning`, `frost`, `physical`) - Damage type
- Position 3: **Tier/Role** (`basic`, `advanced`, `area`, `precision`) - Capability level

**Implementation Status:** ✅ PARTIALLY IMPLEMENTED
- Turrets use tags for combat (effect tags in turret placement logic)
- Metadata tags NOT used for device behavior

**Implementation Plan:**

**LOW Priority** - Metadata tags could enable:

1. **Inventory Filtering:**
   - Filter by device type (`turret`, `bomb`, `trap`)
   - Filter by element (`fire`, `lightning`, `frost`)

2. **Placement Validation:**
   - Check tags to determine placement rules
   - Restrict turret placement near other turrets (tag-based)

3. **Visual Effects:**
   - Use element tags to determine particle effects
   - `fire` = red/orange particles, `lightning` = blue sparks, etc.

---

### 1.5 Recipes (`recipes.JSON/recipes-smithing-3.JSON`)

**Field:** `metadata.tags`
**Tag Type:** Metadata (Descriptive)
**Example Tags:** `["weapon", "sword", "starter"]`, `["tool", "pickaxe", "starter"]`

**Current Usage:**
```json
{
  "metadata": {
    "tags": ["weapon", "sword", "starter"]
  },
  "recipeId": "smithing_iron_shortsword",
  "outputId": "iron_shortsword"
}
```

**Tag Semantics:**
- Position 0: **Output Category** (`weapon`, `tool`, `armor`, `accessory`, `station`) - What it crafts
- Position 1: **Output Type** (`sword`, `pickaxe`, `chestplate`, `ring`) - Specific type
- Position 2: **Tier** (`starter`, `standard`, `advanced`, `master`) - Difficulty level

**Implementation Status:** ❌ NOT IMPLEMENTED

**Implementation Plan:**

**LOW Priority** - Recipe tags could enable:

1. **Recipe Discovery System:**
   - Show hints based on owned materials' tags
   - "You have fire crystals - try fire-related recipes"

2. **Recipe Filtering:**
   - UI filter by category (`weapon`, `tool`, `armor`)
   - Filter by tier (`starter` recipes shown first)

3. **Crafting Achievements:**
   - Track recipes crafted by tag category
   - Title: "Crafted 100 weapon recipes"

---

### 1.6 Skills (`Skills/skills-skills-1.JSON`)

**Field:** `tags` (Metadata) + `combatTags` (Effect Tags)
**Tag Type:** HYBRID - Both metadata and effect tags
**Example Tags:**
- Metadata: `["damage_boost", "gathering", "basic"]`
- Combat: `["fire", "circle", "burn"]` (when applicable)

**Current Usage:**
```json
{
  "skillId": "miners_fury",
  "tags": ["damage_boost", "gathering", "basic"],
  "effect": {
    "type": "empower",
    "category": "mining"
  }
  // Combat skills ALSO have:
  // "combatTags": ["fire", "circle", "burn"],
  // "combatParams": { "baseDamage": 80, "circle_radius": 4.0 }
}
```

**Tag Semantics (Metadata `tags`):**
- Describe skill purpose and category
- Used for: Filtering, UI organization, skill discovery
- Examples: `damage_boost`, `defense`, `gathering`, `movement`, `combat`

**Tag Semantics (Effect `combatTags`):**
- Tell effect executor HOW to execute skill
- Geometry tags: `single_target`, `circle`, `cone`, `chain`, `line`
- Damage tags: `fire`, `ice`, `lightning`, `physical`, `poison`
- Status tags: `burn`, `freeze`, `stun`, `slow`

**Implementation Status:** ✅ FULLY IMPLEMENTED
- Metadata tags: Used for skill categorization
- Combat tags: Fully integrated with effect executor
- Skills with `combatTags` use tag-based combat system

**No Further Action Needed** - Skills are the GOLD STANDARD for tag usage

---

### 1.7 Enemies (`Definitions.JSON/hostiles-1.JSON`)

**Field:** `metadata.tags`
**Tag Type:** Metadata (Descriptive) + Combat Behavior Hints
**Example Tags:** `["wolf", "common", "passive", "starter"]`, `["beetle", "uncommon", "territorial", "mid-game"]`

**Current Usage:**
```json
{
  "metadata": {
    "tags": ["wolf", "uncommon", "aggressive", "mid-game"]
  },
  "enemyId": "wolf_dire",
  "behavior": "aggressive_pack",
  "aiPattern": { ... }
}
```

**Tag Semantics:**
- Position 0: **Enemy Type** (`wolf`, `slime`, `beetle`, `golem`) - Species/category
- Position 1: **Rarity** (`common`, `uncommon`, `rare`, `boss`) - Spawn frequency
- Position 2: **Behavior Hint** (`passive`, `aggressive`, `territorial`, `boss`) - AI behavior
- Position 3: **Progression Tier** (`starter`, `mid-game`, `end-game`) - Power level

**Implementation Status:** ✅ COMBAT TAGS IMPLEMENTED
- Enemies can use tag-based attacks via `specialAbilities` field
- Metadata tags NOT used for AI behavior (behavior is hardcoded in `aiPattern`)

**Implementation Plan:**

**LOW Priority** - Metadata tags could enhance AI:

1. **Dynamic AI Behavior:**
   - Use `passive`/`aggressive`/`territorial` tags to modify aggro range
   - `passive`: Reduce aggro range by 50%
   - `aggressive`: Increase aggro range by 50%
   - `territorial`: Only aggro within defined territory

2. **Spawn Filtering:**
   - Match enemy tags with chunk tags
   - `starter` chunks spawn `starter` enemies
   - `end-game` chunks spawn `end-game` enemies

3. **Damage Modifiers:**
   - Enemy type tags affect damage taken
   - `beetle` tag: -20% damage from 1H weapons, +30% from 2H weapons
   - `wolf` tag: +10% damage from fire, -10% from ice

---

### 1.8 Titles (`progression/titles-1.JSON`)

**Field:** ❌ NO TAG FIELD
**Tag Type:** N/A

**Implementation Status:** N/A - Titles don't use tags

**Recommendation:** Titles are fine without tags. They use `titleType` and `difficultyTier` for categorization, which is sufficient.

---

### 1.9 Classes (`progression/classes-1.JSON`)

**Field:** ❌ NO TAG FIELD
**Tag Type:** N/A

**Implementation Status:** N/A - Classes don't use tags

**Recommendation:** Classes are fine without tags. They use `classId` and `thematicIdentity` for categorization.

---

### 1.10 Quests (`progression/quests-1.JSON`)

**Field:** ❌ NO TAG FIELD
**Tag Type:** N/A

**Implementation Status:** N/A - Quests don't use tags

**Recommendation:** Consider adding tags for quest filtering:
- Example tags: `["combat", "gathering", "tutorial", "optional"]`
- Use case: Quest journal filtering, quest recommendations
- **Priority: VERY LOW** - Not critical for MVP

---

### 1.11 NPCs (`progression/npcs-1.JSON`)

**Field:** ❌ NO TAG FIELD
**Tag Type:** N/A

**Implementation Status:** N/A - NPCs don't use tags

**Recommendation:** NPCs are fine without tags. They use `npc_id` and quest associations for behavior.

---

### 1.12 Placements (`placements.JSON/placements-engineering-1.JSON`)

**Field:** ❌ NO TAG FIELD
**Tag Type:** N/A

**Implementation Status:** N/A - Placement recipes don't use tags

**Recommendation:** Placements inherit tags from their output items. No additional tags needed.

---

## 2. Implementation Priority Matrix

| JSON Type | Has Tags? | Implemented? | Priority | Effort | Impact |
|-----------|-----------|--------------|----------|--------|--------|
| Skills | ✅ | ✅ FULL | N/A | N/A | ✅ Complete |
| Enemies (Combat) | ✅ | ✅ COMBAT | N/A | N/A | ✅ Complete |
| **Weapons** | ✅ | ❌ NONE | **MEDIUM** | **Medium** | **High** |
| Chunks | ✅ | ❌ NONE | LOW | High | Medium |
| Materials | ✅ | ❌ NONE | LOW | Low | Low |
| Devices | ✅ | ⚠️ PARTIAL | LOW | Low | Low |
| Recipes | ✅ | ❌ NONE | LOW | Low | Low |
| Enemies (AI) | ✅ | ❌ NONE | LOW | Medium | Medium |
| Quests | ❌ | N/A | VERY LOW | Low | Low |
| NPCs | ❌ | N/A | N/A | N/A | N/A |
| Classes | ❌ | N/A | N/A | N/A | N/A |
| Titles | ❌ | N/A | N/A | N/A | N/A |
| Placements | ❌ | N/A | N/A | N/A | N/A |

---

## 3. Recommended Implementation Order

### Phase 1: Combat Enhancement (IMMEDIATE)
**Focus:** Weapon Tag Integration
**Why:** Direct gameplay impact, medium effort, high value

**Tasks:**
1. ✅ Modify `Character.calculate_weapon_stats()` to read weapon metadata tags
2. ✅ Apply tag-based modifiers:
   - `2H` → +20% damage
   - `fast` → +15% attack speed
   - `precision` → +10% crit chance
   - `reach` → +1 attack range
   - `crushing` → +20% vs armored
   - `armor_breaker` → Ignore 25% defense
   - `cleaving` → Hit adjacent enemies for 50%
3. ✅ Test with existing weapons (iron_warhammer, copper_dagger, etc.)
4. ✅ Document weapon tag effects in combat documentation

**Estimated Time:** 2-3 hours

---

### Phase 2: Quality of Life (LATER)
**Focus:** Inventory/UI Improvements
**Why:** Low effort, improves UX

**Tasks:**
1. Material filtering by tags
2. Recipe filtering by tags
3. Device type filtering
4. Search by tag functionality

**Estimated Time:** 3-4 hours

---

### Phase 3: World Generation (FUTURE)
**Focus:** Chunk Tag-Based Spawning
**Why:** High effort, requires world generation refactor

**Tasks:**
1. Tag-based chunk filtering by player level
2. Enemy spawn matching (chunk tags ↔ enemy tags)
3. Resource density modifiers based on tags
4. Adjacency preferences for similar chunks

**Estimated Time:** 8-12 hours

---

## 4. Summary

**Total JSON Files Analyzed:** 13
**Files WITH Tags:** 8
**Files WITHOUT Tags:** 5

**Implementation Status:**
- ✅ **Fully Implemented:** Skills (both metadata and combat tags), Enemy combat tags
- ⚠️ **Partially Implemented:** Devices (combat only), Enemies (combat only, not AI)
- ❌ **Not Implemented:** Weapons (PRIORITY), Chunks, Materials, Recipes

**Next Steps:**
1. ✅ Implement weapon tag-based combat modifiers (MEDIUM priority, high impact)
2. ⏸️ Consider inventory filtering for materials/recipes (LOW priority, QoL)
3. ⏸️ Defer chunk tag implementation until world generation refactor (FUTURE)

---

## 5. Confident Implementation Candidates

Based on "act if you are confident in the theme":

### ✅ **WEAPON TAG INTEGRATION** - Ready to implement NOW
- Clear semantics (`2H`, `fast`, `precision`, `reach`, etc.)
- Direct gameplay impact
- Medium effort, high value
- Minimal risk of breaking existing systems

### ⏸️ **MATERIAL/RECIPE FILTERING** - Could implement, but low value
- Clear use case (UI filtering)
- Low effort
- But: Low impact on core gameplay

### ❌ **CHUNK TAG SPAWNING** - NOT confident yet
- Requires world generation refactor
- High complexity
- Needs more design work on spawn algorithms

---

**Recommendation:** Proceed with **Weapon Tag Integration** immediately. It's the highest value, clearest implementation path, and most impactful tag usage we can add right now.
