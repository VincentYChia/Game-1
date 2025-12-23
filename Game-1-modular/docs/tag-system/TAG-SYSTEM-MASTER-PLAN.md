# Tag System Master Plan & Analysis
**Comprehensive analysis of tag-driven architecture for Game-1**

Last Updated: 2025-12-17
Status: Phase 3 - Week 4 Complete, Planning Remaining Work

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Tag Philosophy](#tag-philosophy)
3. [Current Tag Usage Analysis](#current-tag-usage-analysis)
4. [Tag-to-Effects System](#tag-to-effects-system)
5. [Implementation Status](#implementation-status)
6. [Remaining Work](#remaining-work)
7. [Full Integration Plan](#full-integration-plan)

---

## Executive Summary

The tag system in Game-1 serves two distinct but complementary purposes:

1. **Metadata Tags**: Descriptive tags in JSON files that describe WHAT something is
2. **Effect Tags**: Functional tags that tell the effect executor HOW to process combat/effects

**Key Principle**: Tags represent the same CONCEPT but are interpreted differently depending on the system context.

**Current Status**:
- ✅ Tag-to-Effects Core System (100%)
- ✅ Turret Integration (100%)
- ✅ Training Dummy & Testing (100%)
- ✅ Skill System Integration (100%)
- ✅ Combat System Integration (100%)
- 🔲 Enemy Attack Integration (0%)
- 🔲 Weapon/Item Tag Integration (0%)
- 🔲 Chunk Tag Utilization (0%)
- 🔲 Full Tag-Driven Architecture (30%)

---

## Tag Philosophy

### The Core Concept

Tags are **conceptual descriptors** that different systems interpret according to their needs:

```
Concept: "fire"

- In Items: Describes what the item relates to ("fire-based device")
- In Skills: Describes the skill's theme ("fire magic")
- In Enemies: Describes the enemy's nature ("fire elemental")
- In Effects: Tells executor to apply fire damage + burn status
- In Chunks: Describes environmental hazard ("fire region")
```

### Two Tag Types

#### 1. Metadata Tags (Descriptive)
**Purpose**: Categorize, filter, and describe entities
**Location**: `metadata.tags` field in JSONs
**Used By**: Spawn systems, UI filters, narrative generation, LLMs
**Examples**:
- Skills: `["damage_boost", "gathering", "basic"]`
- Items: `["device", "turret", "fire", "elemental"]`
- Enemies: `["wolf", "uncommon", "aggressive", "mid-game"]`
- Chunks: `["forest", "safe", "wood-rich", "starter"]`

#### 2. Effect Tags (Functional)
**Purpose**: Drive combat mechanics and effect execution
**Location**: Separate fields (`combatTags`, `tags` in turret defs, etc.)
**Used By**: Effect executor, damage calculator, status manager
**Examples**:
- Combat: `["fire", "circle", "burn"]`
- Geometry: `["single_target"]`, `["chain"]`, `["cone"]`
- Status: `["freeze"]`, `["shock"]`, `["bleed"]`
- Damage: `["physical"]`, `["lightning"]`, `["holy"]`

**Critical**: These two tag types COEXIST and serve different purposes!

---

## Current Tag Usage Analysis

### Skills (`Skills/skills-skills-1.JSON`)

**Current Structure**:
```json
{
  "skillId": "miners_fury",
  "name": "Miner's Fury",
  "tags": ["damage_boost", "gathering", "basic"],  // METADATA
  "effect": {
    "type": "empower",
    "category": "mining"
  }
}
```

**What Tags Mean**:
- `damage_boost`: This skill boosts damage output
- `gathering`: Related to gathering activities
- `basic`: Simple/starter skill

**Usage**:
- Skill filtering/sorting in UI
- Narrative/tooltip generation
- Learning requirements
- LLM skill recommendations

**For Combat Skills** (NEW):
```json
{
  "skillId": "fireball",
  "tags": ["damage", "aoe", "combat", "fire"],  // METADATA (unchanged)
  "combatTags": ["fire", "circle", "burn"],     // EFFECT TAGS (new field)
  "combatParams": {
    "baseDamage": 80,
    "circle_radius": 4.0,
    "burn_duration": 5.0
  }
}
```

**Current Status**: ✅ Implemented (combatTags/combatParams fields added)

---

### Items/Materials (`items.JSON/items-engineering-1.JSON`)

**Current Structure**:
```json
{
  "itemId": "fire_arrow_turret",
  "metadata": {
    "tags": ["device", "turret", "fire", "elemental"]  // METADATA
  },
  "category": "device",
  "type": "turret",
  "effect": "Fires flaming arrows, 35 damage + burn, 7 unit range"
}
```

**What Tags Mean**:
- `device`: It's a placeable device
- `turret`: Specific device type
- `fire`: Fire-themed/fire damage
- `elemental`: Elemental damage type

**Usage**:
- Crafting recipe filtering
- Inventory categorization
- Material requirements
- Rarity/tier indicators

**For Turrets** (Already has effect tags):
```json
{
  "itemId": "fire_arrow_turret",
  "metadata": {
    "tags": ["device", "turret", "fire", "elemental"]  // METADATA (descriptive)
  },
  "tags": ["fire", "single_target", "burn"],         // EFFECT TAGS (for turret system)
  "effectParams": {
    "baseDamage": 35,
    "burn_duration": 4.0,
    "burn_damage_per_second": 8.0
  }
}
```

**Current Status**: ✅ Implemented (turrets use effect tags)

**For Weapons** (NEEDS IMPLEMENTATION):
```json
{
  "itemId": "flaming_sword",
  "metadata": {
    "tags": ["weapon", "sword", "fire", "melee"]  // METADATA
  },
  "weaponTags": ["fire", "single_target", "burn"],  // EFFECT TAGS (not yet implemented)
  "weaponParams": {
    "burn_duration": 3.0,
    "burn_damage_per_second": 5.0
  }
}
```

**Current Status**: 🔲 Not implemented (weapons don't use effect tags yet)

---

### Hostiles/Enemies (`Definitions.JSON/hostiles-1.JSON`)

**Current Structure**:
```json
{
  "enemyId": "wolf_dire",
  "metadata": {
    "tags": ["wolf", "uncommon", "aggressive", "mid-game"]  // METADATA
  },
  "tier": 2,
  "category": "beast",
  "behavior": "aggressive_pack"
}
```

**What Tags Mean**:
- `wolf`: Enemy type/species
- `uncommon`: Spawn rarity
- `aggressive`: Behavior pattern
- `mid-game`: Appropriate player progression level

**Usage**:
- Spawn filtering by chunk type
- AI behavior selection
- Loot table determination
- Difficulty scaling

**For Special Attacks** (NEEDS IMPLEMENTATION):
```json
{
  "enemyId": "fire_mage",
  "metadata": {
    "tags": ["mage", "rare", "caster", "mid-game"]  // METADATA
  },
  "specialAbility": {
    "abilityId": "fireball",
    "cooldown": 8.0,
    "tags": ["fire", "circle", "burn"],  // EFFECT TAGS
    "params": {
      "baseDamage": 60,
      "circle_radius": 3.0,
      "burn_duration": 4.0
    }
  }
}
```

**Current Status**: 🔲 Not implemented (enemies can't use tag-based attacks yet)

---

### Chunks (In Code - `systems/chunk.py`)

**Current Concept** (Not explicitly tagged in JSONs):
```python
# Chunks have ChunkType enum but could benefit from tags
{
  "chunkType": "forest_safe",
  "tags": ["forest", "safe", "wood-rich", "starter"]  // Conceptual
}
```

**What Tags Would Mean**:
- `forest`: Biome type
- `safe`: Low enemy spawn rate
- `wood-rich`: High wood node density
- `starter`: Near spawn, low tier enemies

**Potential Usage**:
- Dynamic spawn filtering
- Resource node generation
- Weather/ambient effects
- Navigation/map legend

**Current Status**: 🔲 Not implemented (chunks use enums, not tags)

---

## Tag-to-Effects System

### Overview

The effect executor processes **effect tags** to create dynamic, composable combat mechanics.

**Architecture**:
```
Effect Tags → Tag Registry → Geometry + Damage + Status → Target Calculation → Apply Effects
```

**Effect Tag Categories**:

1. **Geometry Tags** (How targets are selected):
   - `single_target`: Hit one enemy
   - `circle`: AOE around point
   - `chain`: Jump between targets
   - `cone`: Angular spread
   - `beam`: Line from source
   - `pierce`: Line through targets

2. **Damage Type Tags** (What damage is dealt):
   - `physical`: Physical damage
   - `fire`: Fire damage + heat
   - `frost`: Frost damage + cold
   - `lightning`: Lightning damage + shock
   - `holy`: Holy damage (heal allies/damage undead)
   - `poison`: Poison damage + toxin
   - `shadow`: Shadow damage + dark

3. **Status Effect Tags** (What conditions apply):
   - `burn`: Fire DoT
   - `freeze`: Immobilize
   - `shock`: Stun
   - `slow`: Reduce speed
   - `bleed`: Physical DoT
   - `poison_status`: Poison DoT
   - `regeneration`: Heal over time
   - `shield`: Damage absorption
   - `haste`: Increase speed

4. **Special Tags** (Unique mechanics):
   - `ally`: Target allies instead of enemies
   - `lifesteal`: Heal based on damage
   - `knockback`: Push targets away
   - `vampiric`: Alias for lifesteal

### Effect Tag Synergies

Some tag combinations create special effects:

```json
{
  "tags": ["lightning", "chain"],
  "synergy": "+20% chain range"
},
{
  "tags": ["fire", "circle"],
  "synergy": "+15% radius"
},
{
  "tags": ["frost", "slow"],
  "synergy": "+30% slow duration"
}
```

**Current Status**: ✅ Fully implemented in `core/tag_registry.py`

---

## Implementation Status

### ✅ Completed Systems

#### 1. Tag-to-Effects Core (Week 1-3)
**Files**:
- `core/tag_registry.py` - Tag definitions and lookup
- `core/tag_parser.py` - Tag combination parsing
- `core/effect_executor.py` - Effect execution engine
- `core/geometry.py` - Target selection algorithms
- `core/status_effects.py` - Status effect manager
- `core/tag_debug.py` - Debug logging

**Features**:
- 80+ functional tags
- 13 status effects
- 6 geometry types
- Tag synergies
- Context-aware behavior (holy vs undead)
- Performance optimized (<1ms per effect)

**Lines of Code**: ~3,640

---

#### 2. Turret Integration (Week 4 Part 1)
**Files**:
- `systems/turret_system.py` - Tag-based turret attacks
- `docs/tag-system/TURRET-TAG-GUIDE.md` - Documentation

**Features**:
- Turrets use effect tags from item definitions
- All geometries supported (single, chain, cone, etc.)
- Status effects apply correctly
- Auto-targeting and cooldowns

**Example Turrets**:
- Basic Arrow: `["physical", "single_target"]`
- Fire Arrow: `["fire", "single_target", "burn"]`
- Lightning Cannon: `["lightning", "chain", "shock"]`
- Frost Beam: `["frost", "beam", "freeze", "slow"]`

---

#### 3. Training Dummy & Testing (Week 4 Part 2)
**Files**:
- `systems/training_dummy.py` - High-HP testing entity
- `docs/tag-system/TESTING-GUIDE.md` - Test scenarios
- Renderer updates - Visual HP bar and label

**Features**:
- 10,000 HP (doesn't die easily)
- Detailed damage reporting
- Status effect tracking
- Auto-reset at 10% HP
- Spawns at (60, 50) near player start

---

#### 4. Skill System Integration (Week 4 Part 3)
**Files**:
- `data/models/skills.py` - Added combatTags/combatParams
- `data/databases/skill_db.py` - Load combat tags
- `entities/components/skill_manager.py` - Tag execution
- `docs/tag-system/SKILL-TAG-GUIDE.md` - Documentation

**Features**:
- Skills have BOTH metadata tags AND combat tags
- `use_skill_in_combat()` method with enemy targeting
- Level scaling (+10% per level)
- Backward compatibility with buff-based skills

**Example**:
```json
{
  "skillId": "fireball",
  "tags": ["damage", "aoe", "combat", "fire"],    // Metadata
  "combatTags": ["fire", "circle", "burn"],       // Effect tags
  "combatParams": {
    "baseDamage": 80,
    "circle_radius": 4.0
  }
}
```

---

#### 5. Combat System Integration (Week 4 Part 4)
**Files**:
- `Combat/combat_manager.py` - Added player_attack_enemy_with_tags()

**Features**:
- Tag-based player attacks
- Full stat bonus integration (STR, titles, buffs)
- AOE geometry support
- Auto-loot and EXP
- Backward compatibility

**Usage**:
```python
combat_manager.player_attack_enemy_with_tags(
    enemy=target,
    tags=["fire", "circle", "burn"],
    params={"baseDamage": 50, "circle_radius": 4.0}
)
```

---

### 🔲 Incomplete Systems

#### 1. Enemy Tag-Based Attacks (NOT STARTED)
**Goal**: Enemies can use special attacks with effect tags

**Needs**:
- Extend enemy definitions with optional `specialAbility` field
- Add `enemy_attack_with_tags()` method in Enemy class
- Inherit from player/turret tag attack systems
- AI trigger for special attacks (cooldown, health threshold, etc.)

**Example**:
```json
{
  "enemyId": "fire_mage",
  "specialAbility": {
    "abilityId": "fireball",
    "cooldown": 8.0,
    "healthThreshold": 0.5,  // Use when below 50% HP
    "tags": ["fire", "circle", "burn"],
    "params": {
      "baseDamage": 60,
      "circle_radius": 3.0
    }
  }
}
```

**Implementation Complexity**: Medium (inherit from existing systems)

---

#### 2. Weapon Tag Integration (NOT STARTED)
**Goal**: Equipped weapons add effect tags to player attacks

**Needs**:
- Add `weaponTags`/`weaponParams` fields to weapon definitions
- Modify `player_attack_enemy()` to merge weapon tags
- Handle enchantments that modify tags
- UI display of weapon effect tags

**Example**:
```json
{
  "itemId": "flaming_sword",
  "weaponTags": ["fire", "single_target", "burn"],
  "weaponParams": {
    "burn_duration": 3.0,
    "burn_damage_per_second": 5.0
  }
}
```

**Implementation Complexity**: Medium (extend combat system)

---

#### 3. Chunk Tag-Driven Spawning (NOT STARTED)
**Goal**: Use chunk tags to filter enemy spawns and resources

**Needs**:
- Add `tags` field to chunk generation
- Filter enemy spawns by matching tags
- Adjust resource nodes by chunk tags
- Dynamic difficulty based on tags

**Example**:
```python
# Chunk tags affect spawn filtering
chunk.tags = ["forest", "safe", "starter"]
# Only spawn enemies with matching tags
allowed_enemies = filter_by_tags(enemies, ["passive", "starter", "low-tier"])
```

**Implementation Complexity**: Low (spawn system already exists)

---

#### 4. Item Tag Filtering/Crafting (PARTIAL)
**Goal**: Use metadata tags for crafting, filtering, UI

**Current**: Tags exist in JSONs but not heavily used
**Needs**:
- Crafting recipes filter by tags
- Inventory sorting by tags
- Material requirement tag matching
- LLM-driven crafting suggestions

**Implementation Complexity**: Low (mostly UI/UX work)

---

## Remaining Work

### Phase 1: Enemy Attack Integration (Priority: HIGH)
**Estimated Time**: 2-3 hours
**Files to Modify**:
- `Combat/enemy.py` - Add attack_with_tags() method
- `Combat/combat_manager.py` - Add enemy special attack handling
- `Definitions.JSON/hostiles-1.JSON` - Add specialAbility fields

**Steps**:
1. Extend Enemy class with tag-based attack method (inherit from player system)
2. Add AI logic to trigger special attacks
3. Test with fire mage, lightning shaman, ice golem examples
4. Document in ENEMY-ABILITIES-GUIDE.md

---

### Phase 2: Weapon Tag Integration (Priority: MEDIUM)
**Estimated Time**: 3-4 hours
**Files to Modify**:
- Item JSONs - Add weaponTags/weaponParams
- `Combat/combat_manager.py` - Merge weapon tags into attacks
- `entities/character.py` - Get weapon tags from equipped item

**Steps**:
1. Add weaponTags/weaponParams to weapon definitions
2. Modify player_attack_enemy() to include weapon tags
3. Handle tag merging (weapon + skill tags)
4. Test with various weapon combinations
5. Document in WEAPON-TAG-GUIDE.md

---

### Phase 3: Chunk Tag Utilization (Priority: LOW)
**Estimated Time**: 1-2 hours
**Files to Modify**:
- `systems/chunk.py` - Add tags field
- `Combat/combat_manager.py` - Filter spawns by chunk tags

**Steps**:
1. Add tags to Chunk class
2. Generate tags based on ChunkType
3. Filter enemy spawns by tag matching
4. Test spawn distribution
5. Document in CHUNK-TAG-GUIDE.md

---

### Phase 4: Documentation Consolidation (Priority: HIGH)
**Estimated Time**: 1-2 hours
**Files to Create/Update**:
- This file (TAG-SYSTEM-MASTER-PLAN.md) ✅
- Update IMPLEMENTATION-STATUS.md
- Fix SKILL-TAG-GUIDE.md (clarify combatTags vs tags)
- Create TAG-PHILOSOPHY.md (conceptual guide)

**Steps**:
1. Fix all incorrect documentation references
2. Create clear examples for each tag type
3. Add migration guides
4. Add troubleshooting section

---

## Full Integration Plan

### Stage 1: Core Completion (CURRENT)
- ✅ Tag-to-effects system
- ✅ Turret integration
- ✅ Skill integration
- ✅ Combat integration
- ✅ Training dummy
- 🔲 Enemy attacks ← NEXT
- 🔲 Documentation fixes

**Goal**: All combat entities can use tag-based attacks

---

### Stage 2: Item/Weapon Integration
- 🔲 Weapon tags
- 🔲 Enchantment tags
- 🔲 Consumable effect tags
- 🔲 Tool effect tags

**Goal**: All items contribute tags to gameplay

---

### Stage 3: World Integration
- 🔲 Chunk tags affect spawning
- 🔲 Biome tags affect resources
- 🔲 Weather/ambient tags
- 🔲 Dynamic events by tags

**Goal**: World generation is tag-driven

---

### Stage 4: Meta Integration
- 🔲 Crafting recipe tag matching
- 🔲 Quest generation by tags
- 🔲 Narrative generation by tags
- 🔲 Achievement tracking by tags

**Goal**: Full tag-driven gameplay loop

---

## Tag-Driven Architecture Vision

### The Ultimate Goal

Every system in Game-1 should:
1. **Define** itself with metadata tags (what it IS)
2. **Interact** with others using effect tags (what it DOES)
3. **Filter/Select** using tag matching (what it WORKS WITH)

### Example: Complete Tag Flow

**Player Scenario**: Attacks enemy with flaming sword while Fireball skill is active

```
1. Player Equipment:
   - Weapon: Flaming Sword
     - metadata.tags: ["weapon", "sword", "fire", "melee"]
     - weaponTags: ["fire", "single_target", "burn"]
     - weaponParams: {burn_duration: 3.0}

2. Active Skill:
   - Skill: Fireball (active buff)
     - tags: ["damage", "aoe", "combat", "fire"]  // Metadata
     - Buff: +50% fire damage

3. Target Enemy:
   - Enemy: Ice Elemental
     - metadata.tags: ["elemental", "rare", "frost", "resistant"]
     - vulnerabilities: ["fire"]  // 2x damage from fire

4. Combat Execution:
   - Merge tags: ["fire", "single_target", "burn"]  // From weapon
   - Apply buffs: +50% damage  // From skill
   - Check context: enemy.vulnerabilities includes "fire" → 2x multiplier
   - Execute:
     - Base: 50 damage
     - With buffs: 75 damage
     - With vulnerability: 150 damage
     - Apply burn: 5 DPS for 3 seconds = 15 damage
     - Total: 165 damage

5. Result:
   - Enemy takes 165 total damage
   - Burn status applied (3 seconds)
   - Player activity.tags gains ["combat", "fire", "elemental_slayer"]
   - Potential drop: check enemy.drops for tags["fire", "rare"]
```

**This is the vision**: Every interaction is tag-driven, composable, and emergent.

---

## Next Steps

### Immediate (This Session):
1. ✅ Create this master plan document
2. 🔄 Fix SKILL-TAG-GUIDE.md (clarify combatTags vs metadata tags)
3. 🔄 Update IMPLEMENTATION-STATUS.md with accurate info
4. ⏭️ Implement enemy tag-based attacks
5. ⏭️ Add enemy special abilities to hostiles JSON

### Short-term (Next Session):
1. Weapon tag integration
2. Chunk tag-driven spawning
3. Visual debugging tools
4. Performance optimization

### Long-term (Future):
1. Full item tag integration
2. Tag-based crafting system
3. Dynamic quest generation
4. Narrative system integration

---

**END OF MASTER PLAN**

Total Implementation Progress: ~35% (Core systems done, integration ongoing)
