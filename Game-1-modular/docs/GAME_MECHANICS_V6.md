# GAME MECHANICS V6 - IMPLEMENTATION REALITY
**Version:** 6.0
**Last Updated:** 2025-12-30
**Status:** Living Document - Reflects ACTUAL Coded Implementation

> **IMPORTANT:** This document describes what is ACTUALLY IMPLEMENTED in code, not design aspirations.
> Values and mechanics documented here are verified from source code analysis.

---

## QUICK NAVIGATION

| Part | Contents |
|------|----------|
| [Part I](#part-i-core-systems) | Character Stats, Leveling, Classes |
| [Part II](#part-ii-combat-equipment) | Combat, Equipment, Enchantments |
| [Part III](#part-iii-skills-progression) | Skills, Titles, Status Effects |
| [Part IV](#part-iv-crafting) | 5 Crafting Disciplines |
| [Part V](#part-v-world-systems) | World, Gathering, NPCs, Quests |
| [Part VI](#part-vi-technical) | Save System, Tag System |

---

# PART I: CORE SYSTEMS

## Character Stats

### The 6 Core Stats
All stats start at 0. Players gain 1 stat point per level (30 total at max level).

| Stat | Effect Per Point | Implementation |
|------|-----------------|----------------|
| **Strength (STR)** | +5% melee damage | `character.py:recalculate_stats()` |
| **Defense (DEF)** | +2% damage reduction | `combat_manager.py` defense calc |
| **Vitality (VIT)** | +15 Max HP | `character.py:max_health` |
| **Luck (LCK)** | +2% crit chance | `combat_manager.py:630` |
| **Agility (AGI)** | +5% gathering efficiency, +2% movement speed | `character.py:582` |
| **Intelligence (INT)** | +20 Max Mana | `character.py:recalculate_stats()` |

### Stat Bonuses Applied
```python
# From stats.py - how bonuses are calculated
def get_bonus(stat_name: str) -> float:
    return getattr(stats, stat_name) * multiplier
    # STR/AGI: 0.05 (5%)
    # DEF: 0.02 (2%)
    # LCK: 0.02 (2%)
```

### Flat Bonuses
- **Max Health:** Base 100 + (VIT × 15) + class bonus + equipment
- **Max Mana:** Base 100 + (INT × 20) + class bonus + equipment
- **Carry Capacity:** Base inventory + STR bonus (not currently active)

---

## Level System

### Progression
- **Max Level:** 30
- **Stat Points:** 1 per level = 30 total
- **EXP Formula:** `200 * (1.75 ** (level - 1))`

### Level Requirements
| Level | EXP Required | Cumulative |
|-------|--------------|------------|
| 1→2 | 200 | 200 |
| 2→3 | 350 | 550 |
| 5→6 | ~1,100 | ~3,000 |
| 10→11 | ~3,500 | ~15,000 |
| 20→21 | ~35,000 | ~100,000 |
| 29→30 | ~175,000 | ~500,000 |

### EXP Sources
| Source | Base EXP | Notes |
|--------|----------|-------|
| T1 Gather | 10 | Per resource |
| T2 Gather | 40 | 4x multiplier |
| T3 Gather | 160 | 4x multiplier |
| T4 Gather | 640 | 4x multiplier |
| T1 Enemy | 100 | Per kill |
| T2 Enemy | 400 | 4x multiplier |
| T3 Enemy | 1,600 | 4x multiplier |
| T4 Enemy | 6,400 | 4x multiplier |
| Boss | 10x | Multiplied from tier |
| Quest | Variable | Defined per quest |

---

## Class System

### Implementation Status: FULLY WORKING
Files: `systems/class_system.py`, `data/models/classes.py`

### 6 Starting Classes

| Class | Tags | Preferred Damage | Armor | Tool Bonus |
|-------|------|------------------|-------|------------|
| **Warrior** | warrior, melee, physical, tanky, frontline | physical, slashing, crushing | heavy | +10% tool damage |
| **Ranger** | ranger, ranged, agile, nature, mobile | physical, piercing, poison | light | +15% axe efficiency |
| **Scholar** | scholar, magic, alchemy, arcane, caster | arcane, fire, frost, lightning | robes | - |
| **Artisan** | artisan, crafting, smithing, engineering, utility | physical | medium | - |
| **Scavenger** | scavenger, luck, gathering, treasure, explorer | physical | light | +15% pickaxe efficiency |
| **Adventurer** | adventurer, balanced, versatile, generalist, adaptive | physical, arcane | medium | - |

### Class Bonuses (Defined in classes-1.JSON)
Each class has stat bonuses applied via `class_system.get_bonus()`:
- Max health bonus
- Max mana bonus
- Movement speed bonus
- Crit chance bonus
- Resource quality bonus

### Skill Affinity System
When using skills, matching tags between class and skill grant bonuses:
- 1 tag match: +5% effectiveness
- 2 tags: +10%
- 3 tags: +15%
- 4+ tags: +20% (capped)

**Implementation:** `skill_manager.py:_apply_combat_skill_with_context()`

### Tool Efficiency Bonus
Applied when class is selected via callback system:
```python
# class_system.py
if 'nature' in tags: bonus += 0.10  # Rangers
if 'gathering' in tags: bonus += 0.05/0.10  # Axe/Pickaxe
if 'explorer' in tags: bonus += 0.05  # Pickaxe
```

---

# PART II: COMBAT & EQUIPMENT

## Combat System

### Implementation Status: FULLY WORKING
File: `Combat/combat_manager.py` (1,377 lines)

### Damage Calculation Pipeline
```
Base Damage (weapon or tool)
  × Hand Type Bonus (+10-20% for proper grip)
  × Strength Multiplier (1.0 + STR × 0.05)
  × Skill Buff Bonus (empower: +50% to +400%)
  × Title Bonus (activity-based combat titles)
  × Weapon Tag Bonuses (precision, crushing, armor_breaker)
  × Critical Hit (2x if triggered)
  - Enemy Defense (1% reduction per DEF, max 75%)
  = Final Damage
```

### Critical Hits
- Base chance: Luck × 2%
- Pierce buff adds crit chance
- Precision weapon tag adds crit chance
- Critical damage: 2x multiplier

### Weapon Tag Effects
| Tag | Effect | Implementation |
|-----|--------|----------------|
| `precision` | +10% crit chance | Line 640 |
| `armor_breaker` | Ignores 25% armor | Line 575 |
| `crushing` | +25% vs armored (DEF>10) | Line 611 |
| `reach` | +1 attack range | Equipment stat |

### Hand Type Bonuses
| Hand Type | Mainhand | Offhand | Bonus |
|-----------|----------|---------|-------|
| 1H | Yes | Yes | Normal |
| 2H | Yes | Blocks | +20% damage |
| Versatile | Yes | Yes | +10% mainhand |

### Dual Wielding
- Both mainhand and offhand weapons deal damage
- Separate cooldowns for each hand
- Total damage = mainhand + offhand (each calculated separately)

---

## Equipment System

### Implementation Status: FULLY WORKING
Files: `entities/components/equipment_manager.py`, `data/models/equipment.py`

### Equipment Slots (10 Total)
| Slot | Type | Notes |
|------|------|-------|
| mainHand | Weapon | Primary damage source |
| offHand | Weapon/Shield | Secondary damage or defense |
| helmet | Armor | Defense |
| chestplate | Armor | Defense (highest) |
| leggings | Armor | Defense |
| boots | Armor | Defense, movement |
| gauntlets | Armor | Defense |
| axe | Tool | Forestry gathering |
| pickaxe | Tool | Mining gathering |
| accessory | Accessory | Bonus stats |

### Equipment Stats
| Stat | Description | Application |
|------|-------------|-------------|
| damage | Base weapon damage | Combat calculation |
| defense | Damage reduction | Stacks from all armor |
| durability_current | Current condition | 0 = broken |
| durability_max | Max condition | For repair % |
| attack_speed | Speed multiplier | Cooldown modifier |
| range | Attack distance | Collision detection |
| weight | Item weight | (Future: encumbrance) |

### Durability System
- Weapons: -1 durability per proper use
- Tools in combat: -2 durability (improper use penalty)
- Effectiveness: Scales 0.5x to 1.0x based on durability %
  - ≥50% = 1.0x
  - <50% = Linear decrease to 0.5x at 0%

---

## Enchantment System

### Implementation Status: FULLY WORKING
Files: `Crafting-subdisciplines/enchanting.py`, `combat_manager.py`

### Working Enchantments
| Enchantment | Effect | Trigger | Location |
|-------------|--------|---------|----------|
| **Sharpness** | +X% damage | Passive | equipment.py |
| **Protection** | +X% defense | Passive | combat_manager.py:1188 |
| **Efficiency** | +X% gather speed | Passive | character.py:793 |
| **Fortune** | +X% bonus yield | On gather | character.py:847 |
| **Unbreaking** | +X% durability | On use | character.py:818 |
| **Fire Aspect** | Apply burn | On hit | combat_manager.py:780 |
| **Poison** | Apply poison | On hit | combat_manager.py:780 |
| **Swiftness** | +X% move speed | Passive | character.py:601 |
| **Thorns** | Reflect damage | On hit received | combat_manager.py:1221 |
| **Lifesteal** | Heal % of damage | On hit | combat_manager.py:673 |
| **Knockback** | Push enemy | On hit | combat_manager.py:802 |
| **Frost Touch** | Apply slow | On hit | combat_manager.py:812 |
| **Chain Damage** | Hit nearby enemies | On hit | combat_manager.py:683 |

### Enchantment Triggers
- **Passive:** Always active when equipped
- **On Hit:** Triggers when dealing damage
- **On Crit:** Triggers on critical hits only
- **On Kill:** Triggers when killing enemy

---

# PART III: SKILLS & PROGRESSION

## Skill System

### Implementation Status: WORKING (Buff skills fully, Combat skills partial)
File: `entities/components/skill_manager.py` (709 lines)

### Skill Hotbar
- 5 slots available (keys 1-5)
- Cooldown system per skill
- Mana cost system
- Level requirement checking

### Buff-Based Skills (FULLY WORKING)
| Effect Type | Description | Magnitude Range |
|-------------|-------------|-----------------|
| **Empower** | +damage% | +50% to +400% |
| **Quicken** | +speed% | +30% to +100% |
| **Fortify** | Flat damage reduction | +10 to +80 |
| **Pierce** | +crit chance% | +10% to +40% |
| **Restore** | Instant heal | 50-400 HP/Mana |
| **Enrich** | Bonus gathering | Extra items |
| **Elevate** | Rarity upgrade | % chance |
| **Regenerate** | Heal over time | 5-20 HP/s |
| **Devastate** | AoE damage/gather | Radius effect |
| **Transcend** | Tier bypass | Access higher tier |

### Skill Leveling
- Skills gain EXP from use (100 EXP per use)
- Higher levels = +10% effectiveness per level
- Max skill level tracks independently

### Combat Skills (Tag-Based)
- Use `combat_tags` for damage/effect types
- Execute through `effect_executor` when enemies present
- Level scaling and class affinity applied

---

## Title System

### Implementation Status: FULLY WORKING
Files: `systems/title_system.py`, `data/databases/title_db.py`

### Title Acquisition
| Method | Description |
|--------|-------------|
| **Guaranteed** | Reach activity milestone (e.g., Mine 1000 ore) |
| **Random** | Tier-based chance on activity (20%/10%/5%/2%) |
| **Hidden** | Auto-granted when conditions met |
| **Prerequisites** | Require other titles first |

### Title Tiers
| Tier | Drop Rate | Typical Bonus |
|------|-----------|---------------|
| Novice | 20% | +5% |
| Apprentice | 10% | +10% |
| Journeyman | 5% | +15% |
| Expert | 2% | +20% |
| Master | 1% | +25-30% |

### Title Bonus Types
- Mining/Forestry damage and speed
- Combat damage multiplier
- Crit chance bonus
- Crafting quality/speed
- Material yield bonus
- Durability bonus
- Rare drop rate

---

## Status Effects

### Implementation Status: FULLY WORKING
File: `entities/status_effect.py` (827 lines)

### Damage Over Time (DoT)
| Status | Damage Type | Stack Limit | Special |
|--------|-------------|-------------|---------|
| Burn | Fire | 3 | - |
| Bleed | Physical | 5 | - |
| Poison | Nature | ∞ | 1.2x power per stack |
| Shock | Lightning | - | Tick rate varies |

### Crowd Control
| Status | Effect | Duration | Notes |
|--------|--------|----------|-------|
| Freeze | Complete stop | Short | Breaks on damage |
| Slow | -30% speed | Medium | Stores original speed |
| Stun | No actions | Short | Full incapacitation |
| Root | No movement | Medium | Can still attack |

### Buffs
| Status | Effect | Duration |
|--------|--------|----------|
| Regeneration | +HP/s | Medium |
| Shield | Absorb damage | Until depleted |
| Haste | +30% speed | Medium |
| Empower | +25% damage | Medium |
| Fortify | +20% defense | Medium |

### Debuffs
| Status | Effect |
|--------|--------|
| Weaken | -25% damage dealt |
| Vulnerable | +25% damage taken |

### Special
| Status | Effect |
|--------|--------|
| Phase | Intangible, immune to damage |
| Invisible | Stealth mode |

---

# PART IV: CRAFTING

## Overview

### Implementation Status: FULLY WORKING
Directory: `Crafting-subdisciplines/` (9,159 lines total)

### 5 Crafting Disciplines
| Discipline | Minigame | Station | Lines of Code |
|------------|----------|---------|---------------|
| Smithing | Temperature + Hammering | Forge | 622 |
| Refining | Cylinder Alignment | Refinery | 669 |
| Alchemy | Reaction Chain | Alchemy Table | 695 |
| Engineering | Cognitive Puzzle | Engineering Bench | 890 |
| Enchanting | Pattern Creation | Enchanting Table | 1,265 |

### Rarity System
| Rarity | Color | Stat Modifier |
|--------|-------|---------------|
| Common | White | 1.0x |
| Uncommon | Green | 1.15x |
| Rare | Blue | 1.35x |
| Legendary | Gold | 1.6x |

### Crafting Flow
1. Select recipe at station
2. Place required materials
3. Complete minigame
4. Quality determined by performance
5. Item created with stats

---

## Smithing
**File:** `Crafting-subdisciplines/smithing.py`

### Minigame Mechanics
- **Temperature Control:** Maintain optimal heat zone
- **Hammer Timing:** Hit at the right moment
- **Quality:** Based on precision of both

### Outputs
- Weapons (swords, axes, maces, etc.)
- Armor pieces
- Tools

---

## Refining
**File:** `Crafting-subdisciplines/refining.py`

### Minigame Mechanics
- **Cylinder Alignment:** Rotate rings to align gaps
- **Multiple Rings:** More rings = harder
- **Time Pressure:** Must complete before timeout

### Outputs
- Refined materials (bars from ore)
- Alloys (combining metals)
- Elemental materials

---

## Alchemy
**File:** `Crafting-subdisciplines/alchemy.py`

### Minigame Mechanics
- **Reaction Chain:** Manage ingredient interactions
- **Order Matters:** Sequential ingredient addition
- **Gradient Success:** Partial success possible

### Outputs
- Health potions
- Mana potions
- Buff potions
- Transmuted materials

---

## Engineering
**File:** `Crafting-subdisciplines/engineering.py`

### Minigame Mechanics
- **Cognitive Puzzle:** Pattern/logic based
- **Device Assembly:** Slot-type component placement
- **Complex Builds:** Multiple steps

### Outputs
- Turrets (auto-attack)
- Traps (proximity trigger)
- Bombs (timed/triggered)
- Utility devices

---

## Enchanting
**File:** `Crafting-subdisciplines/enchanting.py` (1,265 lines)

### Minigame Mechanics
- **Freeform Pattern:** Create rune patterns
- **Pattern Recognition:** Match target patterns
- **Precision:** Quality based on accuracy

### Outputs
- Enchanted equipment
- Upgrade existing items
- Apply special effects

---

# PART V: WORLD SYSTEMS

## World Generation

### Implementation Status: FULLY WORKING
Files: `systems/world_system.py`, `systems/chunk.py`

### World Size
- Default: 100×100 tiles
- Chunk size: 16×16 tiles
- Configurable in Config

### Chunk Danger Levels
| Level | Enemies | Resources | Description |
|-------|---------|-----------|-------------|
| Peaceful | None | T1-T2 | Safe gathering |
| Normal | T1-T2 | T1-T3 | Standard gameplay |
| Dangerous | T2-T3 | T2-T4 | Challenge areas |
| Rare | T3-T4 | T3-T4 | Boss spawns |

### Terrain Types
- Grass (walkable)
- Water (blocked)
- Forest (resources)
- Mountain (blocked)

---

## Gathering System

### Implementation Status: FULLY WORKING
Files: `systems/natural_resource.py`, `character.py:harvest_resource()`

### Resource Types
| Type | Tool | Tiers | Respawn |
|------|------|-------|---------|
| Trees | Axe | T1-T4 | 60 seconds |
| Ore | Pickaxe | T1-T4 | Never |
| Stone | Pickaxe | T1-T4 | Never |

### Resource HP by Tier
| Tier | Base HP | Damage to Destroy |
|------|---------|-------------------|
| T1 | 100 | 5-10 hits |
| T2 | 200 | 8-15 hits |
| T3 | 400 | 12-20 hits |
| T4 | 800 | 18-30 hits |

### Gathering Buffs
- **Devastate:** AoE gathering (Chain Harvest skill)
- **Enrich:** Bonus item drops
- **Elevate:** Rarity upgrade chance

---

## NPC & Quest System

### Implementation Status: WORKING (Basic)
Files: `systems/npc_system.py`, `systems/quest_system.py`

### NPC Features
- Spawn in world at defined positions
- Dialogue cycling
- Quest availability checking
- Interaction radius

### Quest Types
| Type | Objective | Example |
|------|-----------|---------|
| Gather | Collect items | "Bring 10 Iron Ore" |
| Combat | Defeat enemies | "Kill 5 Goblins" |

### Quest Rewards
- Experience points
- Item rewards
- Skill unlocks
- Stat points
- Gold (if implemented)

### Quest Tracking
- Progress tracked per objective
- Only counts items gathered AFTER quest start
- Items consumed on turn-in

---

# PART VI: TECHNICAL SYSTEMS

## Save System

### Implementation Status: FULLY WORKING
File: `systems/save_manager.py`

### Saved Data
| Category | Data Preserved |
|----------|----------------|
| Character | Position, facing, stats, level, EXP |
| Resources | Health/mana with proportional scaling |
| Equipment | All slots, durability, enchantments |
| Inventory | Items, stacks, equipment metadata |
| Skills | Known skills, levels, equipped slots |
| Titles | All earned titles |
| Activities | Activity counts for title tracking |
| Class | Selected class |
| Quests | Active, completed, progress |
| World | Placed entities, modified resources |

### Save Features
- Version tracking (v2.0)
- Timestamps
- Multiple save slots
- Full state restoration

---

## Tag System

### Implementation Status: FULLY WORKING
Files: `core/effect_executor.py`, `core/tag_parser.py`

### Tag Categories
| Category | Examples | Purpose |
|----------|----------|---------|
| Geometry | single_target, chain, circle, cone, line | Area targeting |
| Damage | physical, fire, ice, lightning, poison, arcane | Damage type |
| Status | burn, bleed, poison, freeze, slow, stun | Effect application |
| Context | enemy, ally, self | Valid targets |
| Trigger | on_hit, on_kill, on_crit | When to activate |

### Tag Resolution
1. Parse tags from skill/equipment
2. Determine geometry type
3. Select valid targets
4. Apply damage with modifiers
5. Apply status effects
6. Handle falloff for AoE

---

## NOT IMPLEMENTED (Future)

The following systems are documented in older docs but NOT in code:

| System | Status | Notes |
|--------|--------|-------|
| Block/Parry | Not Implemented | Tracked in MASTER_ISSUE_TRACKER |
| Summon | Not Implemented | Tracked in MASTER_ISSUE_TRACKER |
| Weight/Encumbrance | Not Implemented | Weight stat exists but unused |
| Repair System | Not Implemented | Equipment breaks, can't repair |
| Weather | Not Implemented | No weather effects |
| Dungeons | Not Implemented | No instanced areas |
| Set Bonuses | Not Implemented | No equipment sets |
| Skill Trees | Not Implemented | No branching paths |

---

## FILE REFERENCE

### Core Systems
| System | Primary File | Lines |
|--------|--------------|-------|
| Character | `entities/character.py` | ~1,100 |
| Combat | `Combat/combat_manager.py` | 1,377 |
| Skills | `entities/components/skill_manager.py` | 709 |
| Equipment | `entities/components/equipment_manager.py` | ~300 |
| Status | `entities/status_effect.py` | 827 |

### Crafting
| Discipline | File | Lines |
|------------|------|-------|
| Smithing | `Crafting-subdisciplines/smithing.py` | 622 |
| Refining | `Crafting-subdisciplines/refining.py` | 669 |
| Alchemy | `Crafting-subdisciplines/alchemy.py` | 695 |
| Engineering | `Crafting-subdisciplines/engineering.py` | 890 |
| Enchanting | `Crafting-subdisciplines/enchanting.py` | 1,265 |

### Data
| Type | Location |
|------|----------|
| Classes | `progression/classes-1.JSON` |
| Skills | `Skills/skills-*.JSON` |
| Recipes | `recipes.JSON/recipes-*.JSON` |
| Items | `items.JSON/items-*.JSON` |
| Enemies | `Enemies.JSON` |
| Titles | `progression/titles-1.JSON` |

---

**Document Maintained By:** Auto-generated from code audit
**Next Review:** After major feature additions
