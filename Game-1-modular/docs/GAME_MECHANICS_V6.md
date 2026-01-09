# GAME MECHANICS V6 - MASTER DEVELOPER DOCUMENT

**Version:** 6.0
**Last Updated:** December 31, 2025
**Status:** Living Document - Implementation Reality + Design Aspirations

**IMPORTANT:** See `NAMING_CONVENTIONS.md` for API standards and naming patterns to prevent bugs.

---

## Implementation Status Legend

Throughout this document, the following markers indicate implementation status:

| Marker | Meaning |
|--------|---------|
| ✅ IMPLEMENTED | Verified working in code |
| ⏳ PARTIAL | Some aspects implemented |
| 🔮 PLANNED | Design only, not yet coded |

---

## Latest Updates (v5 → v6)

### New Implemented Features (v6)
- ✅ **Tag-Driven Class System** - Classes now have tags that drive gameplay bonuses
- ✅ **Skill Affinity System** - Matching class/skill tags grant up to +20% effectiveness
- ✅ **Class Selection Tooltips** - UI shows tag effects and class bonuses
- ✅ **Tool Slot Tooltips** - Hovering tools shows tier, damage, durability, class bonuses
- ✅ **Tool Efficiency Bonuses** - Rangers +15% axe, Scavengers +15% pickaxe
- ✅ **Enchantment Combat Integration** - 12+ enchantments active in combat
- ✅ **Full Save/Load System** - Complete state preservation and restoration
- ✅ **Status Effect System** - DoTs, CC, buffs, debuffs all working
- ✅ **Combat Tag System** - Geometry, damage types, triggers all functional

### Implemented JSON Files
**Recipe Files (Complete):**
- ✅ `recipes-smithing-3.json` - Most up to date smithing recipes
- ✅ `recipes-alchemy-1.json` - Alchemy consumables and transmutations
- ✅ `recipes-refining-1.json` - Material processing and alloy creation
- ✅ `recipes-engineering-1.json` - Turrets, bombs, traps, and devices
- ✅ `recipes-adornments-1.json` - Enchanting gems and equipment enhancements

**Placement Files (Complete):**
- ✅ `placements-smithing-1.JSON` - Grid layouts for smithing recipes
- ✅ `placements-adornments-1.JSON` - Pattern layouts for enchanting
- ✅ `placements-engineering-1.JSON` - Slot-type layouts for engineering
- ✅ `placements-refining-1.JSON` - Hub-spoke patterns for refining
- ✅ `placements-alchemy-1.JSON` - Sequential order layouts for alchemy

**Material Files:**
- ✅ `items-materials-1.JSON` - 57 materials with properties and tiers (3 T4 monster drops pending)

**Skill Files:**
- ✅ `skills-skills-1.JSON` - 100+ skill definitions
- ✅ `skills-translation-table.JSON` - Skill progression curves and unlocks

**Class Files:**
- ✅ `classes-1.JSON` - 6 classes with tags, bonuses, preferred types

**Title Files:**
- ✅ `titles-1.JSON` - Title definitions with bonuses and prerequisites

**Template Files:**
- ✅ `templates-crafting-1.JSON` - Item template definitions for procedural generation

### System Implementation Status
- ✅ **Combat System:** Full damage pipeline, enchantments, dual wielding (1,377 lines)
- ✅ **Skill System:** Buff skills, combat skills, affinity bonuses (709 lines)
- ✅ **Crafting System:** All 5 disciplines with minigames (9,159 lines total)
- ✅ **Status Effects:** DoT, CC, buffs, debuffs (827 lines)
- ✅ **Save/Load:** Full state preservation
- ⏳ **World Generation:** Basic chunks, detailed templates pending
- ⏳ **NPC/Quest System:** Basic functionality, needs expansion
- 🔮 **LLM Integration:** Designed but not implemented
- 🔮 **Block/Parry:** Designed but not implemented
- 🔮 **Summon Mechanics:** Designed but not implemented

### Critical Notes
- All numerical values remain **PLACEHOLDERS** unless explicitly approved through playtesting
- Structure is final, numbers are flexible
- This document serves as master reference for developers
- JSON files contain actual content definitions
- Implementation status markers show what's coded vs. planned

---

# PART IV: PROGRESSION & SYSTEMS

## Progression Systems ✅ IMPLEMENTED

### Overview

**Implementation Status:** ✅ Core systems working, ⏳ some values hardcoded

**Code References:**
- `entities/character.py` - Character stats, leveling, EXP (1,100+ lines)
- `systems/title_system.py` - Title acquisition and bonuses
- `entities/components/skill_manager.py` - Skill system (709 lines)
- `systems/class_system.py` - Class bonuses and tag system

**Current Implementation:**
- ✅ Title definitions in `titles-1.JSON` (all title data including bonuses, prerequisites)
- ✅ Skill definitions in `skills-skills-1.JSON` (100+ skill definitions)
- ⏳ Progression curves currently hardcoded as placeholder
- 🔮 **Future:** Progression curves will become JSON/dynamic when LLM personalizes advancement rates

**Must Be JSON (Even If Using Placeholder Values):**
- ✅ `titles-1.JSON` - Title definitions AND progression thresholds
- ✅ `skills-skills-1.JSON` - Skill definitions AND progression curves
- 🔮 `exp_curves.json` - Character leveling, skill leveling curves (not yet created)
- 🔮 `title_progression.json` - Acquisition thresholds, RNG chances (not yet created)
- 🔮 `class_switching.json` - Cost tables by level (not yet created)

---

## Character Stats ✅ IMPLEMENTED

### Core Design

**Code Reference:** `entities/character.py:recalculate_stats()`
**Formula Source:** `Definitions.JSON/stats-calculations.JSON` (369 lines)

- **30 Total Stat Points** (earned through leveling, 1 point per level)
- **Multiplicative Scaling** (stats × titles × equipment)
- **No Hard Caps** (balance through careful tuning)
- **Activity-Specific Bonuses** (each stat has clear purposes)

### Hierarchical Stat Formula System ✅ IMPLEMENTED

From `stats-calculations.JSON`:

**Master Formula:**
```
FinalStat = globalBase × tierMultiplier × categoryMultiplier × typeMultiplier × subtypeMultiplier × itemMultiplier
```

**Global Bases:**
| Stat | Base Value |
|------|------------|
| Weapon Damage | 10 |
| Armor Defense | 10 |
| Tool Gathering | 10 |
| Durability | 500 |
| Weight | 1.0 |
| Attack Speed | 1.0 |

**Tier Multipliers:**
| Tier | Multiplier |
|------|------------|
| T1 | 1.0x |
| T2 | 2.0x |
| T3 | 4.0x |
| T4 | 8.0x |

### The 6 Core Stats (All Start at 0)

#### 1. Strength (STR)
- **Mining Efficiency:** +5% damage to ore/stone nodes per point
- **Melee Damage:** +5% physical weapon damage per point
- **Carry Capacity:** +10 inventory slots per point
- **Tool Power:** +2% base tool effectiveness per point
- **Identity:** Raw physical power, heavy combat, mining specialist

#### 2. Defense (DEF)
- **Damage Reduction:** +2% incoming damage reduction per point
- **Armor Effectiveness:** +3% bonus from equipped armor per point
- **Durability Bonus:** Equipped gear loses durability 2% slower per point
- **Stability:** +1% resistance to knockback/stuns per point
- **Identity:** Tank, survivability, gear preservation

#### 3. Vitality (VIT)
- **Max Health:** +15 HP per point (base 100 HP)
- **Health Regeneration:** +1% passive regen per point (base 1 HP/10s)
- **Tool Durability:** -1% consumption per point (stacks with DEF)
- **Stamina Pool:** +10 stamina per point (if stamina system added)
- **Identity:** Endurance, longevity, sustain

#### 4. Luck (LCK)
- **Critical Hit Chance:** +2% chance per point (2x damage on crit)
- **Resource Quality:** +2% better yields per point (RNG shifts toward max)
- **Rare Drop Chance:** +3% rare material spawn/drop per point
- **First-Try Bonus:** +3% chance per point for unique crafting attributes
- **RNG Blessing:** +1% to ALL random outcomes per point
- **Identity:** Fortune, discovery, RNG manipulation

#### 5. Agility (AGI)
- **Forestry Efficiency:** +5% damage to tree/plant nodes per point
- **Attack Speed:** +3% faster attacks per point
- **Crafting Precision:** +2% mini-game time for Smithing/Engineering per point
- **Dodge Chance:** +1% evasion per point
- **Movement Speed:** +2% faster movement per point
- **Identity:** Speed, precision, forestry specialist, nimble combat

#### 6. Intelligence (INT)
- **Alchemy/Enchanting Efficiency:** +2% mini-game time per point
- **Recipe Discovery:** +4% chance to discover recipes per point
- **Mana Pool:** +20 mana per point (base 100, for skills)
- **Skill EXP:** +2% faster skill leveling per point
- **Elemental Damage:** +5% fire/ice/lightning damage per point
- **Identity:** Magic, knowledge, crafting mastery, learning

### Stat Allocation

- All stats start at 0
- Gain 1 stat point per character level (max 30 points at Level 30)
- Can allocate freely at any time
- Respec available with cooldown (no material cost)

---

## Level and Experience

### Character Levels (VERY SLOW - 20 Hours Total)

**Max Level:** 30 (1 stat point per level = 30 total stat points)

**Exponential EXP Requirements:**
```
Level 1 → 2:      200 EXP
Level 2 → 3:      350 EXP
Level 3 → 4:      550 EXP
Level 4 → 5:      800 EXP
Level 5 → 6:    1,100 EXP
...
Level 10 → 11:  3,500 EXP
...
Level 20 → 21: 12,000 EXP
...
Level 29 → 30: 35,000 EXP

Total for Level 30: ~250,000 EXP
Average: ~12,500 EXP per hour
```

### EXP Sources (Exponential by Tier, 4x Multiplier)

**Gathering:**
```
T1 Resource:    10 EXP base
T2 Resource:    40 EXP base (4x)
T3 Resource:   160 EXP base (4x)
T4 Resource:   640 EXP base (4x)

Size Modifiers:
- Small:  0.8x
- Normal: 1.0x
- Large:  1.5x
- Huge:   2.5x

Example: Huge T2 Tree = 40 × 2.5 = 100 EXP per gather
```

**Crafting (Mini-Game ONLY - Instant Craft = 0 EXP):**
```
T1 Recipe:    50 EXP base
T2 Recipe:   200 EXP base (4x)
T3 Recipe:   800 EXP base (4x)
T4 Recipe: 3,200 EXP base (4x)

Performance Multipliers:
- Perfect craft: 2.0x EXP
- First-Try Bonus achieved: 3.0x EXP

Example: Perfect T3 craft = 800 × 2.0 = 1,600 EXP
```

**Discovery:**
```
T1 Recipe Discovery:   100 EXP
T2 Recipe Discovery:   400 EXP
T3 Recipe Discovery: 1,600 EXP
T4 Recipe Discovery: 6,400 EXP

New Material Found: Tier × 100 EXP
New Area Explored: Tier × 200 EXP
Failed Experiment: 10 EXP (encourages trying)
```

**Combat (Placeholder):**
```
T1 Enemy:   100 EXP
T2 Enemy:   400 EXP
T3 Enemy: 1,600 EXP
T4 Enemy: 6,400 EXP

Boss: 10x multiplier
```

**Quests:**
```
Tutorial Quests:   200 EXP
Main Quest T1:     500 EXP
Main Quest T2:   2,000 EXP
Main Quest T3:   8,000 EXP
Side Quests: 50% of main quest value
```

### Auto-Save System

- Game auto-saves character build snapshot at every level
- Snapshots show progression (stats, skills, titles earned)
- Reference only (cannot load old snapshots except pre-class-switch saves)
- Used for LLM analysis and player progression tracking

---

## Skill System ✅ IMPLEMENTED

**Implementation Status:** ✅ Core system working
**Source Files:**
- `Definitions.JSON/skills-translation-table.JSON` (235 lines) - Translation tables
- `skills.JSON/skills-skills-1.JSON` - 100+ skill definitions
- `entities/components/skill_manager.py` (709 lines) - Skill logic

### Core Design

- **Skills are activated effects** (NOT passive bonuses - titles give passives)
- **Frenzy/Burst mechanics** (temporary powerful boosts)
- **Cooldown-based** (can't spam, strategic usage)
- **Consume Mana** (INT-based resource pool)
- **Progress slowly** (late-game EXP sink, slower than character levels)

### Skill Progression ✅ IMPLEMENTED

From `skills-translation-table.JSON`:

| Level | EXP Required | Cumulative EXP |
|-------|--------------|----------------|
| 1 | 1,000 | 1,000 |
| 2 | 2,000 | 3,000 |
| 3 | 4,000 | 7,000 |
| 4 | 8,000 | 15,000 |
| 5 | 16,000 | 31,000 |
| 6 | 32,000 | 63,000 |
| 7 | 64,000 | 127,000 |
| 8 | 128,000 | 255,000 |
| 9 | 256,000 | 511,000 |
| 10 | 512,000 | 1,022,000 |

**Level Scaling Formula:** `effectValue × (1 + (currentLevel - 1) × 0.1)`
- Level 1: 1.0x base effectiveness
- Level 5: 1.4x base effectiveness
- Level 10: 1.9x base effectiveness (max bonus: +90%)

### Skill EXP Sources ✅ IMPLEMENTED

| Source | EXP Gained |
|--------|------------|
| Using the skill | 100 |
| T1 activity while active | 20 |
| T2 activity while active | 80 |
| T3 activity while active | 320 |
| T4 activity while active | 1,280 |

### Duration Translations ✅ IMPLEMENTED

Text-based duration values translate to actual seconds:

| Descriptor | Seconds | Description |
|------------|---------|-------------|
| `instant` | 0 | No duration - effect applies once immediately |
| `brief` | 15 | Short burst - quick tactical advantage |
| `moderate` | 30 | Standard duration - sustained effect |
| `long` | 60 | Extended duration - strategic advantage |
| `extended` | 120 | Very long duration - prolonged power |

### Mana Cost Translations ✅ IMPLEMENTED

| Descriptor | Cost | Description |
|------------|------|-------------|
| `low` | 30 | Minimal mana - frequent use |
| `moderate` | 60 | Standard mana - tactical use |
| `high` | 100 | Significant mana - powerful effects |
| `extreme` | 150 | Massive mana - ultimate abilities |

### Cooldown Translations ✅ IMPLEMENTED

| Descriptor | Seconds | Description |
|------------|---------|-------------|
| `short` | 120 | 2 minutes - frequent use |
| `moderate` | 300 | 5 minutes - tactical use |
| `long` | 600 | 10 minutes - strategic use |
| `extreme` | 1200 | 20 minutes - ultimate abilities |

### Skill Categories ✅ IMPLEMENTED

Skills apply to specific activity types with compatible effects:

| Category | Applies To | Compatible Effects |
|----------|------------|-------------------|
| `mining` | resource_nodes, mining_damage, ore_yield | empower, quicken, enrich, pierce, devastate |
| `forestry` | tree_nodes, forestry_damage, wood_yield | empower, quicken, enrich, pierce, devastate |
| `fishing` | fishing_nodes, catch_rate, fish_quality | empower, quicken, enrich, pierce |
| `combat` | weapon_damage, attack_speed, critical_chance | empower, quicken, fortify, pierce, restore, regenerate, devastate |
| `smithing` | item_stats, mini_game_time, rarity_chance, first_try_bonus | empower, quicken, pierce, elevate |
| `refining` | material_quality, mini_game_time, rarity_chance | empower, quicken, pierce, elevate |
| `alchemy` | potion_quality, mini_game_time, effect_strength | empower, quicken, pierce, elevate |
| `engineering` | device_stats, mini_game_time, success_rate | empower, quicken, pierce, elevate |
| `enchanting` | enchantment_power, pattern_accuracy, success_rate | empower, quicken, pierce, elevate |
| `movement` | move_speed, dash_distance | quicken |
| `defense` | damage_reduction, armor_effectiveness | fortify, restore, regenerate |
| `damage` | physical_damage, elemental_damage, critical_damage | empower, pierce, devastate |
| `durability` | durability_consumption, repair_rate | fortify, restore, regenerate |

### Effect Types & Formulas ✅ IMPLEMENTED

All 10 effect types use this formula:
```
FinalValue = baseValue × rarityMultiplier × magnitudeMultiplier × levelScaling
```

| Effect | Description | Example Calculation |
|--------|-------------|---------------------|
| **empower** | Increases damage/power | major (rare, lvl 5) = 100% × 1.35 × 2.0 × 1.4 = 378% damage |
| **quicken** | Increases speed | moderate (epic, lvl 10) = 50% × 1.6 × 0.5 × 1.9 = 76% speed |
| **fortify** | Flat damage reduction | major (legendary, lvl 7) = 20 × 2.0 × 40 × 1.6 = 2560 reduction |
| **enrich** | Extra item drops | moderate (uncommon, lvl 3) = 3 × 1.15 × 3 × 1.2 = 12 items |
| **pierce** | Critical hit chance | major (mythic, lvl 10) = 15% × 2.5 × 0.25 × 1.9 = 17.8% crit |
| **restore** | Instant HP/mana/durability | major (epic, lvl 6) = 100 × 1.6 × 200 × 1.5 = 48000 restored |
| **regenerate** | HP/mana per second | moderate (rare, lvl 8) = 5 × 1.35 × 5 × 1.7 = 57.4/sec |
| **elevate** | Rarity upgrade chance | major (legendary, lvl 10) = 25% × 2.0 × 0.4 × 1.9 = 38% chance |
| **devastate** | AoE tile radius | moderate (uncommon, lvl 4) = 5 × 1.15 × 5 × 1.3 = 37 tiles |
| **transcend** | Tier bypass | moderate (mythic, lvl 10) = 1 × 2.5 × 2 × 1.9 = 9 tiers |

### Target Types ✅ IMPLEMENTED

| Target | Description | Radius |
|--------|-------------|--------|
| `self` | Affects only the player character | 0 |
| `enemy` | Affects a single targeted enemy | 0 |
| `resource_node` | Affects the resource being gathered | 0 |
| `area` | Affects all targets in radius | 5 (modified by magnitude) |

### Mana System

```
Mana Pool:
- Base: 100 mana
- Per INT Point: +20 mana
- Per Character Level: +10 mana

Example (15 INT, Level 20):
100 + (15 × 20) + (20 × 10) = 600 mana

Mana Regeneration:
- Base: 10 mana/minute
- Per INT Point: +2 mana/minute

Example (15 INT):
10 + (15 × 2) = 40 mana/minute
```

### Placeholder Skills (Proof of Concept - Full Library Needs Development)

**NOTE:** These are placeholder examples. The full skill library (100+ skills) will be developed later, similar to how recipes will be developed.

1. **Mining Frenzy** [NEEDS DEVELOPMENT]
   - Effect: +100% mining damage for 30 seconds
   - Cooldown: 5 minutes
   - Mana Cost: 50
   - Level Scaling: +10% duration per level (Level 10 = 60s)

2. **Forestry Frenzy** [NEEDS DEVELOPMENT]
   - Effect: +100% forestry damage for 30 seconds
   - Cooldown: 5 minutes
   - Mana Cost: 50

3. **Smithing Focus** [NEEDS DEVELOPMENT]
   - Effect: +50% mini-game time for 1 craft
   - Cooldown: 10 minutes
   - Mana Cost: 80

4. **Forging Precision** [NEEDS DEVELOPMENT]
   - Effect: +100% timing window for 1 refinement
   - Cooldown: 10 minutes
   - Mana Cost: 80

5. **Alchemist's Touch** [NEEDS DEVELOPMENT]
   - Effect: +50% progress bar for 1 brew
   - Cooldown: 10 minutes
   - Mana Cost: 80

6. **Engineering Insight** [NEEDS DEVELOPMENT]
   - Effect: Reveals optimal puzzle solution for 1 device
   - Cooldown: 20 minutes
   - Mana Cost: 100

7. **Enchanter's Vision** [NEEDS DEVELOPMENT]
   - Effect: Shows perfect pattern overlay for 1 enchantment
   - Cooldown: 20 minutes
   - Mana Cost: 100

8. **Battle Rage** [NEEDS DEVELOPMENT]
   - Effect: +50% all damage for 20 seconds
   - Cooldown: 3 minutes
   - Mana Cost: 60

9. **Iron Skin** [NEEDS DEVELOPMENT]
   - Effect: +50% damage reduction for 15 seconds
   - Cooldown: 5 minutes
   - Mana Cost: 70

10. **Treasure Hunter's Luck** [NEEDS DEVELOPMENT]
    - Effect: Next 10 gathers have 3x rare drop chance
    - Cooldown: 15 minutes
    - Mana Cost: 100

### Skill Evolution System

```
Trigger: NPC interaction, special area, major event/milestone
(NOT player-initiated, happens through gameplay)

When Skill Reaches Level 10:
→ Game creates opportunity for evolution
→ Visit specific NPC / Enter special area / Complete event
→ Skill evolves: Resets to Level 0 with enhanced effect

Evolution Chain Example:
Mining Frenzy (Level 10: +100% damage, 60s)
  ↓ (NPC/Event triggers evolution)
Advanced Mining Frenzy (Level 0 → 10: +150% damage, 80s)
  ↓ (NPC/Event triggers evolution)
Expert Mining Frenzy (Level 0 → 10: +200% damage, 100s)
  ↓ (NPC/Event triggers evolution)
Master Mining Frenzy (Level 0 → 10: +300% damage, 120s)
  ↓ (LLM generates unique evolution)
[Custom Skill] - Personalized to player's style
```

**CRITICAL:** Evolution is NOT automatic at level 10. It's triggered by gameplay analysis at major milestones.

**ALL skills can evolve until reaching maximum rarity (legendary)**

### Skill Unlocking

- **Class:** Starts with 1 skill (Level 1)
- **NPCs:** Teach 3-4 skills through quests (guided-play)
- **Discovery:** Find skill books (rare world drops)
- **Achievements:** Some Master titles grant unique skills
- **LLM:** Generate personalized skills (post-guided-play)

### Max Skills

- **Known:** Unlimited (can learn all skills eventually)
- **Equipped:** 6 active at once (hotbar, keyboard 1-6)

---

## Title System

### Core Design

- **Titles give PERMANENT passive bonuses** (always active, never removed)
- **LLM-Generated** (except starter Novice titles which are hardcoded)
- **Progression tiers:** Novice → Apprentice → Journeyman → Expert → Master
- **Prerequisite chains** (mostly, but can skip with extraordinary feats)
- **Hidden titles** (discovery-based, no shown requirements)
- **RARE acquisition** (milestone/event-based with generation chance)

### Title Tiers & Bonuses

#### Novice (Hardcoded - Starter Set)

```
Guaranteed on specific milestones:

• 100 ores mined → "Novice Miner" (+10% mining damage)
• 100 trees chopped → "Novice Lumberjack" (+10% forestry damage)
• 50 T1 items smithed → "Novice Smith" (+10% smithing time)
• 50 materials refined → "Novice Refiner" (+10% forging precision)
• 50 potions brewed → "Novice Alchemist" (+10% alchemy progress)
• 20 devices crafted → "Novice Engineer" (+10% engineering tolerance)
• 20 items enchanted → "Novice Enchanter" (+10% enchanting precision)
• 50 enemies defeated → "Novice Warrior" (+10% melee damage)
• First rare material → "Novice Explorer" (+10% discovery chance)

Purpose: Establish baseline progression paths
```

#### Apprentice (LLM-Generated)

```
Bonus: +25% efficiency in activity
Acquisition: Milestone events with 20% generation chance

Example Generation:
Player Activity:
- 1,000 ores mined
- 80% fire-based ores
- Uses fire weapons primarily
- Has Novice Miner title

LLM Generates: "Apprentice Flame Miner"
- Bonus: +25% mining damage
- Special: +15% fire ore discovery chance
- Prerequisite: Novice Miner (required)
- Unique to player's specialization pattern
```

#### Journeyman (LLM-Generated)

```
Bonus: +50% efficiency + minor unique perk
Acquisition: Milestone events with 10% generation chance
Prerequisite: Usually requires Apprentice tier
```

#### Expert (LLM-Generated)

```
Bonus: +100% efficiency + moderate unique perk
Acquisition: Milestone events with 5% generation chance
Prerequisite: Usually requires Journeyman tier
```

#### Master (LLM-Generated)

```
Bonus: +200% efficiency + major unique perk
Acquisition: Milestone events with 2% generation chance OR special achievement
Prerequisite: Usually requires Expert tier

Example: "Master Smith"
- +200% smithing mini-game time
- All crafts have +10% first-try bonus chance
- May grant unique skill unlock
```

### Title Acquisition Methods

**Primary: Milestone/Event-Based with Generation Chance**
```
Examples of Title Triggers:

Milestone Event: Gather 1,000th ore
→ 20% chance to generate "Apprentice Miner" title

Special Event: Defeat first boss
→ 50% chance to generate "Apprentice Warrior" title

Discovery Event: Find rare material for first time
→ 30% chance to generate title related to discovery

Quest Event: Complete NPC master quest
→ 100% chance to generate specific title
```

**Fallback: Activity Count Guarantees**
```
If RNG hasn't granted title by threshold:

Novice:       1,000 activities (guaranteed if not obtained)
Apprentice:   5,000 activities (guaranteed)
Journeyman:  20,000 activities (guaranteed)
Expert:     100,000 activities (guaranteed)
Master:     500,000 activities OR special achievement (guaranteed)
```

### Title Prerequisite System

```
Standard Chain (Enforced):
Novice Miner (hardcoded)
  ↓ (requires Novice)
Apprentice Miner (LLM, needs Novice)
  ↓ (requires Apprentice)
Journeyman Miner (LLM, needs Apprentice)
  ↓ (requires Journeyman)
Expert Miner (LLM, needs Journeyman)
  ↓ (requires Expert)
Master Miner (LLM, needs Expert)

Skip Conditions (Extraordinary Feats):
IF player does something exceptional:
- Mine 10,000 T4 ores before getting any titles → Skip to Expert
- Discover new mining technique → Skip to Journeyman
- Complete impossible mining challenge → Skip to Master
- LLM evaluates if feat warrants skip

Multiple Paths (Branching):
Novice Miner
  ↓
Apprentice Fire Miner ← Focus fire ores
Apprentice Ice Miner ← Focus ice ores
Apprentice Speed Miner ← Mine super fast
Apprentice Deep Miner ← Mine only T3-T4

Each branch has own progression path
Can pursue multiple branches simultaneously
```

### Hidden Titles (Discovery-Based)

```
No requirements shown
No hints given
Discovered through unique actions

Examples:
• "Dragon's Bane" - Defeat dragon boss with fire weapon
• "Eternal Smith" - Craft 100 items in single session
• "Lucky Bastard" - Get 10 first-try bonuses in a row
• "Material Hoarder" - Store 10,000 unique materials
• "The Undying" - Survive 100 near-death experiences

LLM generates: Title name, bonus, discovery condition
Player discovers through experimentation and play
```

### Title Permanence

```
All Titles are PERMANENT:
- Once earned, ALWAYS active
- Cannot be removed or unequipped
- Bonuses stack infinitely
- No limit to number of titles

Example Character Progression:
Level 5:  "Novice Miner" (+10% mining)
Level 10: "Novice Smith" (+10% smithing)
Level 15: "Apprentice Miner" (+25% mining)
          → Total Mining: +10% + 25% = +35%
Level 20: "Apprentice Warrior" (+25% melee)
Level 30: "Expert Miner" (+100% mining + rare ore bonus)
          → Total Mining: +10% + 25% + 100% = +135%
```

### Title Categories

- **Gathering:** Miner, Lumberjack
- **Crafting:** Smith, Refiner, Alchemist, Engineer, Enchanter
- **Combat:** Warrior, Defender
- **Utility:** Explorer, Survivalist

---

## Class System ✅ IMPLEMENTED

**Code References:**
- `systems/class_system.py` - Class bonuses, tag system, tool efficiency
- `data/models/classes.py` - ClassDefinition model with tags
- `progression/classes-1.JSON` - Class definitions data
- `rendering/renderer.py` - Class selection tooltips

### Hierarchy

```
World/Save File
  └─ Character 1 (Class: Warrior)
  └─ Character 2 (Class: Scholar)
  └─ Character 3 (Class: Ranger)
  └─ etc.

One World → Multiple Characters
One Character → One Class (switchable with cost)
```

### Starting Classes (Character Creation)

Each class provides:
- ✅ Starting stat bonuses (permanent)
- ✅ Starting skill unlocked (Level 1)
- ✅ **Tags** (NEW in V6 - drive skill affinity and tool bonuses)
- ✅ **Preferred damage/armor types** (NEW in V6)
- Recommended stat allocation
- Thematic identity

**6 Base Classes (from classes-1.JSON):**

| Class | Tags | Preferred Damage | Armor Type |
|-------|------|------------------|------------|
| **Warrior** | warrior, melee, physical, tanky, frontline | physical, slashing, crushing | heavy |
| **Ranger** | ranger, ranged, agile, nature, mobile | physical, piercing, poison | light |
| **Scholar** | scholar, magic, alchemy, arcane, caster | arcane, fire, frost, lightning | robes |
| **Artisan** | artisan, crafting, smithing, engineering, utility | physical | medium |
| **Scavenger** | scavenger, luck, gathering, treasure, explorer | physical | light |
| **Adventurer** | adventurer, balanced, versatile, generalist, adaptive | physical, arcane | medium |

1. **Warrior**
   - Bonuses: +30 HP, +10% melee damage, +20 inventory slots
   - Starting Skill: Battle Rage (Level 1)
   - Tags: `warrior, melee, physical, tanky, frontline`
   - Tool Bonus: +10% tool damage (from physical/melee tags)
   - Recommended: STR, VIT, DEF

2. **Ranger**
   - Bonuses: +15% movement speed, +10% crit chance, +10% forestry
   - Starting Skill: Forestry Frenzy (Level 1)
   - Tags: `ranger, ranged, agile, nature, mobile`
   - Tool Bonus: +15% axe efficiency (from nature/gathering affinity)
   - Recommended: AGI, LCK, VIT

3. **Scholar**
   - Bonuses: +100 mana, +10% recipe discovery, +5% skill EXP
   - Starting Skill: Alchemist's Touch (Level 1)
   - Tags: `scholar, magic, alchemy, arcane, caster`
   - Recommended: INT, LCK, AGI

4. **Artisan**
   - Bonuses: +10% all crafting time, +10% first-try bonus, +5% durability
   - Starting Skill: Smithing Focus (Level 1)
   - Tags: `artisan, crafting, smithing, engineering, utility`
   - Recommended: AGI, INT, LCK

5. **Scavenger**
   - Bonuses: +20% rare drops, +10% resource quality, +100 carry capacity
   - Starting Skill: Treasure Hunter's Luck (Level 1)
   - Tags: `scavenger, luck, gathering, treasure, explorer`
   - Tool Bonus: +15% pickaxe efficiency (from gathering/explorer tags)
   - Recommended: LCK, STR, VIT

6. **Adventurer**
   - Bonuses: +5% all gathering, +5% all crafting, +50 HP, +50 mana
   - Starting Skill: Choice of any 1 skill (Level 1)
   - Tags: `adventurer, balanced, versatile, generalist, adaptive`
   - Recommended: Balanced spread

### Skill Affinity System ✅ IMPLEMENTED (NEW in V6)

**Code Reference:** `skill_manager.py:_apply_combat_skill_with_context()`, `_apply_skill_effect()`

When using skills, matching tags between the player's class and the skill grant effectiveness bonuses:

```
Tag Matching Formula:
matching_tags = intersection(class.tags, skill.tags)
bonus = min(len(matching_tags) * 5%, 20%)  # Capped at 20%

Examples:
- Warrior (melee, physical) using "Power Strike" (melee, physical): +10%
- Scholar (magic, arcane, fire) using "Fireball" (magic, fire): +10%
- Ranger (nature, agile) using "Evasion" (agile): +5%
- Any class using skill with 4+ matching tags: +20% (max)
```

**Implementation Details:**
```python
# From ClassDefinition.get_skill_affinity_bonus()
def get_skill_affinity_bonus(self, skill_tags: List[str]) -> float:
    if not self.tags or not skill_tags:
        return 0.0
    class_tags = set(t.lower() for t in self.tags)
    skill_tags_set = set(t.lower() for t in skill_tags)
    matching = len(class_tags.intersection(skill_tags_set))
    return min(matching * 0.05, 0.20)  # 5% per match, max 20%
```

### Tool Efficiency Bonuses ✅ IMPLEMENTED (NEW in V6)

**Code Reference:** `class_system.py:get_tool_efficiency_bonus()`

Class tags provide bonuses to tool efficiency:

| Tag Combination | Tool | Bonus |
|-----------------|------|-------|
| `nature` | Axe | +10% |
| `gathering` | Axe | +5% |
| `gathering` | Pickaxe | +10% |
| `explorer` | Pickaxe | +5% |
| `physical` | All tools | +5% damage |
| `melee` | All tools | +5% damage |

**Examples:**
- **Ranger** (nature + mobile): +10% axe efficiency
- **Scavenger** (gathering + explorer): +15% pickaxe efficiency
- **Warrior** (physical + melee): +10% tool damage

### Class Switching (Simple Cost-Based)

**What Switching Means:**
```
Switching class = Changing active class bonuses

KEPT:
• All character progression (stats, level, EXP)
• All skill levels and EXP
• All titles earned
• All equipped gear
• All inventory items
• All stored materials

CHANGED:
• Class bonuses (old class → new class)
• Starting skill (if applicable)
```

**Switching Cost:**
```
Fixed Cost (Regardless of Level):
- Cost: 1,000 gold
- Purpose: Small gate to prevent constant switching
- Can switch at any time after paying cost
- No cooldown between switches
```

**Simple Confirmation:**
```
Player initiates class switch:

╔═══════════════════════════════════════╗
║  CLASS CHANGE                          ║
╠═══════════════════════════════════════╣
║ Switching from WARRIOR to SCHOLAR     ║
║                                        ║
║ New Bonuses:                           ║
║ • +100 mana (was +30 HP)              ║
║ • +10% recipe discovery (was +10% melee) ║
║ • +5% skill EXP (was none)            ║
║                                        ║
║ Starting Skill Changed:                ║
║ • Battle Rage → Alchemist's Touch     ║
║                                        ║
║ Everything else remains the same.     ║
║                                        ║
║ COST: 1,000 gold                      ║
║                                        ║
║ [CANCEL]  [CONFIRM SWITCH]            ║
╚═══════════════════════════════════════╝
```

**Design Intent:**
- Allow flexible playstyle experimentation
- Minimal cost prevents spam-switching
- No harsh penalties - encourage trying different classes
- Supports build variety and respecialization

---

---

## Equipment Progression

### Tier System

- T1 → T2 → T3 → T4 based on material tier + recipe complexity
- Higher tier materials + larger recipes = more powerful items
- T1 maxed (high rarity + mini-game perfection) can compete with basic T2

### Equipment Types

- **Armor:** Helmet, Chestplate, Leggings, Boots, Gauntlets (5 slots)
- **Weapons:** Main Hand, Off Hand
- **Accessories:** 1 slot (rings/amulets/charms from Enchanting)
- **Tools:** Pickaxe slot, Axe slot (quick-swap, not counted in combat slots)

### Upgrade vs Replace

- **Enchanting** upgrades existing gear (adds bonuses, can fail at high tier)
- **Crafting new** replaces old gear (better base stats)
- Both paths viable

---

# PART V: GAMEPLAY SYSTEMS

## Combat System ✅ IMPLEMENTED

**Code Reference:** `Combat/combat_manager.py` (1,377 lines)

### Basic Combat Loop

```
1. Move within 3 unit radius of enemy (WASD)
2. Click enemy to attack
3. Auto-attack until defeated or player moves away
4. Attack speed based on AGI (+3% per point)
5. Damage based on weapon + STR (+5% per point)
6. Enemy counter-attacks
7. Player takes damage (reduced by DEF + armor)
8. Enemy defeated → corpse appears
9. Click corpse to loot
```

### Damage Calculation Pipeline ✅ IMPLEMENTED

**Code Reference:** `combat_manager.py:calculate_damage()`

```
Full Damage Formula:
Base Damage (weapon or tool)
  × Hand Type Bonus (+10-20% for proper grip)
  × Strength Multiplier (1.0 + STR × 0.05)
  × Skill Buff Bonus (empower: +50% to +400%)
  × Class Affinity Bonus (up to +20% from matching tags)
  × Title Bonus (activity-based combat titles)
  × Weapon Tag Bonuses (precision, crushing, armor_breaker)
  × Critical Hit (2x if triggered)
  - Enemy Defense (1% reduction per DEF, max 75%)
  = Final Damage
```

### Weapon Tag Effects ✅ IMPLEMENTED

| Tag | Effect | Code Location |
|-----|--------|---------------|
| `precision` | +10% crit chance | Line 640 |
| `armor_breaker` | Ignores 25% armor | Line 575 |
| `crushing` | +25% vs armored (DEF>10) | Line 611 |
| `reach` | +1 attack range | Equipment stat |

### Hand Type System ✅ IMPLEMENTED

| Hand Type | Mainhand | Offhand | Bonus |
|-----------|----------|---------|-------|
| 1H (One-Handed) | Yes | Yes | Normal |
| 2H (Two-Handed) | Yes | Blocks offhand | +20% damage |
| Versatile | Yes | Optional | +10% if mainhand only |

### Dual Wielding ✅ IMPLEMENTED
- Both mainhand and offhand weapons deal damage
- Separate cooldowns for each hand
- Total damage = mainhand + offhand (each calculated separately)

### Enchantment Combat Integration ✅ IMPLEMENTED (NEW in V6)

**Code Reference:** `combat_manager.py:780-850`

| Enchantment | Effect | Trigger | Code Line |
|-------------|--------|---------|-----------|
| **Sharpness** | +X% damage | Passive | equipment.py |
| **Protection** | +X% defense | Passive | Line 1188 |
| **Fire Aspect** | Apply burn DoT | On hit | Line 780 |
| **Poison** | Apply poison DoT | On hit | Line 780 |
| **Lifesteal** | Heal % of damage | On hit | Line 673 |
| **Knockback** | Push enemy back | On hit | Line 802 |
| **Frost Touch** | Apply slow | On hit | Line 812 |
| **Chain Damage** | Hit nearby enemies | On hit | Line 683 |
| **Thorns** | Reflect damage | On hit received | Line 1221 |

### Critical Hits ✅ IMPLEMENTED

```
Crit Chance = (LCK × 2%) + Pierce Buff + Precision Tag
Crit Damage = 2x multiplier

Example: 15 LCK + Pierce (+10%) + Precision weapon (+10%)
= 30% + 10% + 10% = 50% crit chance
```

### T1 Enemies

**Wolves:**
- HP: 50 | Damage: 5 | Attack Speed: 2s
- Behavior: Patrol, aggro 5 unit radius
- Loot: Wolf Pelt (1-2, 100% drop rate)
- Spawns: Grassland (2-3), Forest (4-6), Mob chunks (6-10)

**Slimes:**
- HP: 30 | Damage: 3 | Attack Speed: 3s
- Behavior: Slow movement, aggro 2 unit radius
- Loot: Slime Gel (2-4, 100% drop rate)
- Spawns: Grassland (1-2), Stone chunks (2-3), Mob chunks (4-8)

**Giant Beetles:**
- HP: 70 | Damage: 8 | Attack Speed: 2.5s
- Behavior: Near resource nodes, aggro when node attacked (4 unit radius)
- Loot: Chitinous Shell (1-3, 100% drop rate)
- Spawns: Grassland (1-2), Stone chunks (3-5), Mob chunks (3-6)

### Combat Formulas

```
Player Damage:
Weapon Base × (1 + STR×0.05) × Skill × Title × Equipment × Affinity

Enemy Damage to Player:
Enemy Base × (1 - [DEF×0.02 + Armor])  (max 75% reduction)

Player Health:
Base 100 + VIT×15 + Class Bonus + Title Bonuses

Health Regen:
(1 HP/10s) × (1 + VIT×0.01) when out of combat

Death:
Respawn at spawn point (50, 50)
Keep all items and equipment (no death penalty for now)
```

### Enemy AI ⏳ PARTIAL

- ✅ **Patrol:** Random movement within chunk
- ✅ **Aggro:** Chase player in range
- ✅ **Combat:** Simple auto-attack
- ✅ **Return:** Go back to patrol area if player leaves chunk
- 🔮 **Advanced behaviors:** Not yet implemented

### Not Yet Implemented 🔮 PLANNED

| Feature | Status | Notes |
|---------|--------|-------|
| Block/Parry | 🔮 PLANNED | Tracked in MASTER_ISSUE_TRACKER |
| Summon Mechanics | 🔮 PLANNED | Tracked in MASTER_ISSUE_TRACKER |
| Combo System | 🔮 PLANNED | Sequential attack bonuses |
| Stamina System | 🔮 PLANNED | VIT-based resource for actions |

---

## NPC Quest System

**[NEEDS FULL DEVELOPMENT]**

### NPC 1: The Mentor (35, 40)

**Role:** Tutorial guide, basic crafting

**Quest 1 - "Gather the Basics":**
- Collect 20 Oak Logs + 10 Limestone
- Reward: 200 EXP, T1 Forge recipe

**Quest 2 - "Craft Your First Station":**
- Craft T1 Forge (10 Limestone, 8 Oak, 5 Iron Ore)
- Reward: 300 EXP, unlocks Smithing discipline

**Quest 3 - "Tools of the Trade":**
- Craft 3 T1 items with mini-game
- Reward: 500 EXP, T2 Forge recipe, reveals NPC 2 location

### NPC 2: The Artisan (20, 50)

**Role:** Forging/Refining specialist

**Quest 1 - "The Art of Refinement":**
- Craft T1 Refinery, refine 20 Iron Ore → Ingots
- Reward: 800 EXP, Alloy recipes

**Quest 2 - "Elemental Discovery":**
- Create any elemental material (Fire Steel, Ice Copper, etc.)
- Reward: 1,200 EXP, More elemental recipes

**Quest 3 - "Master the Forge":**
- Craft T2 Refinery, create 5 T2 alloys
- Reward: 2,000 EXP, T3 Forge recipe, reveals NPC 3 location

### NPC 3: The Wanderer (25, 25)

**Role:** 3rd discipline choice, advanced training

**Quest 1 - "Choose Your Path":**
- Select Alchemy, Engineering, OR Enchanting
- Receive corresponding T1 station + 5 starter recipes
- Reward: 1,500 EXP

**Quest 2 - "Prove Your Mastery":**
- Craft 10 items in chosen discipline, reach T2
- Reward: 3,000 EXP, Advanced recipes

**Quest 3 - "The World Awaits":**
- Craft T3 stations in all disciplines, reach Level 15
- Reward: 5,000 EXP, Guided-play complete message, LLM activation

---

## Inventory UI

### Inventory System

```
Capacity:
- Base: 20 slots
- STR Bonus: +10 slots per point
- Example: 15 STR = 20 + 150 = 170 slots total

Stack Limits:
- Materials: 256 per slot
- Consumables: 99 per slot
- Equipment/Tools: 1 per slot (no stacking)

Categories (Filtering):
- All Items
- Materials (wood, ore, stone, elementals, monster drops)
- Equipment (armor, weapons, accessories)
- Consumables (potions, food, temporary buffs)
- Tools (pickaxes, axes)
- Recipes (recipe book tab)
```

### UI Layout

**Screen Layout (Placeholder - Subject to UX Design):**
```
Top:
- Health bar (left)
- Mana bar (right)
- Character level and EXP progress

Center:
- Game world (main viewport)
- Resource node health bars (above targeted nodes)
- Enemy health bars (above enemies)
- Damage numbers (floating text)

Bottom:
- Skill hotbar (center, keys 1-6)
- Inventory quick-access (?)

Right Side:
- Quest tracker (toggleable)
- Active buffs/debuffs display

Left Side:
- [Reserved for future features]

No Minimap: Map system not implemented yet
```

---

## Technical Architecture

### Position System (3D-Ready)

```javascript
Position {
  x: float,
  y: float,
  z: float  // Currently 0 for 2D, ready for 3D
}

distance(pos1, pos2) = √[(x₁-x₂)² + (y₁-y₂)² + (z₁-z₂)²]

Current 2D usage: z=0 for both positions
```

### Renderer Abstraction

```javascript
interface IRenderer {
  renderWorld(worldSystem: WorldSystem): void
  renderCharacter(character: Character): void
  renderUI(uiData: any): void
  handleResize(width, height): void
}

// Current: Canvas2DRenderer implements IRenderer
// Future: WebGL3DRenderer implements IRenderer (drop-in replacement)
```

### Asset Management

```javascript
AssetDefinition {
  id: string,
  name: string,
  sprite2D: "path.png",      // Current
  model3D: "path.gltf",      // Future
  color: "#hex",             // Fallback
  scale: number              // 3D scaling
}
```

### Input System

- Mouse → world coordinates via viewport.screenToWorld()
- WASD movement (updates character position)
- Hotkeys 1-6 for skills
- Ready for 3D ray casting (future)

### Save/Load (Placeholder - Needs Implementation)

```
Auto-save triggers:
- Every 5 minutes (background)
- On exit (player quits)
- Before class switch (safety save)
- Every character level (progression snapshot)

Save data includes:
- World state (all tiles, resources, placed objects)
- Player state (position, stats, level, EXP)
- Inventory (all items, quantities)
- Equipment (what's equipped)
- Progression (skills, titles, quest progress)
- Playtime tracking

Format: JSON or binary (TBD based on size/performance)
```

---

# PART VI: DEVELOPMENT REFERENCE

## JSON Schemas

**⚠️ CRITICAL DISCLAIMER: ALL NUMERICAL VALUES IN THESE TEMPLATES ARE PLACEHOLDERS. THEY HAVE NOT BEEN APPROVED OR BALANCED. DO NOT USE THESE NUMBERS IN PRODUCTION. THEY ARE FOR STRUCTURAL REFERENCE ONLY.**

### Items

**Key Specifications:**
- **Range Field:** Physical attack/interaction range (e.g., bow = 10 units, sword = 1 unit), NOT stat ranges
- **Slots/Behavior:** Derived from type/subtype, hardcoded in game logic
- **Crafting Stations:** Just placeable items, no special JSON structure needed
- **Requirements:** Can include level, stats, and titles. Stats/titles requirements should be RARE (most items use level only)
- **Unified Damage Stat:** Tools use same damage field as weapons (mining pickaxe has damage value, not separate mining stat)
- **Narrative First:** Narrative field at top of JSON so LLM processes story/context before mechanics
- **Tradeable:** Everything is tradeable by default, no flag needed
- **Rarity Tiers:** common → uncommon → rare → epic → mythic → legendary → unique
  - **Unique rarity:** Virtually impossible to obtain, devoted players might have 2-3 after a year

**Template:**
```json
{
  "metadata": {
    "narrative": "A simple iron blade with a wooden handle. Every warrior's first step on the path to mastery. The weight feels right in your hand - not perfect, but yours.",
    "tags": ["melee", "starter", "one-handed"]
  },
  
  "itemId": "iron_shortsword",
  "name": "Iron Shortsword",
  "category": "equipment",
  "type": "weapon",
  "subtype": "sword",
  "tier": 1,
  "rarity": "common",
  "range": 1,
  
  "stats": {
    "damage": [15, 20],
    "attackSpeed": 1.2,
    "durability": [500, 500],
    "weight": 3.5,
    "defense": null,
    "mining": null,
    "forestry": null
  },
  
  "attributes": [
    {
      "element": "physical",
      "damageValue": [15, 20]
    }
  ],
  
  "requirements": {
    "level": 1,
    "stats": {"STR": 5},
    "titles": []
  },
  
  "flags": {
    "stackable": false,
    "consumable": false,
    "placeable": false,
    "equippable": true,
    "repairable": true
  }
}
```

### Materials

**Key Specifications:**
- **Simplified:** Only essential data, narrative hints at uses
- **Fields:** materialId, name, tier, rarity, category, narrative, tags
- **Removed:** properties object (described in narrative), subCategory, weight, stackSize (hardcoded by category), processingType (all materials refinable if recipe exists), sources (determined by world gen), uses (redundant with narrative)
- **Properties in Narrative:** Material characteristics described naturally ("highly conductive", "extremely brittle", "combustible") rather than as boolean flags

**Template:**
```json
{
  "metadata": {
    "narrative": "Sturdy grey metal from common deposits. Moderately conductive, somewhat malleable when heated. The workhorse of civilization - reliable, abundant, essential for weapons, tools, and armor.",
    "tags": ["basic", "metal", "refined"]
  },
  
  "materialId": "iron_ingot",
  "name": "Iron Ingot",
  "tier": 1,
  "rarity": "common",
  "category": "metal"
}
```

### Recipes

**Key Specifications:**
- **Discipline Separation:** Recipes MUST be separated by crafting discipline (smithing, forging, alchemy, engineering, enchanting)
- **Base Craft vs Mini-Game:** Same recipe supports both. Base craft = instant, no bonuses. Mini-game = randomness + bonuses
- **Mini-Game Recording:** Item metadata records if mini-game was used (greyed out text), not recipe definition
- **Material Matching:** Recipes handle material filtering directly via materialRules (no separate category JSON)
  - Example: `"materialRules": {"slot_1": {"category": "wood", "tier": 1}}` dynamically matches all T1 wood materials

**Template:**
```json
{
  "metadata": {
    "narrative": "The foundational smithing technique - blade, tang, handle. Simple in concept, demanding in execution. Every smith remembers their first sword.",
    "tags": ["weapon", "sword", "starter"]
  },
  
  "recipeId": "smithing_iron_shortsword_001",
  "outputId": "iron_shortsword",
  "outputQty": 1,
  "stationTier": 1,
  "gridSize": "3x3",
  
  "pattern": [
    [null, "iron_ingot", null],
    [null, "iron_ingot", null],
    [null, "t1_wood", null]
  ],
  
  "materialRules": {
    "t1_wood": {
      "type": "category",
      "alternatives": ["oak_log", "pine_log", "ash_log", "oak_plank", "pine_plank", "ash_plank"]
    }
  },
  
  "miniGame": {
    "type": "smithing",
    "difficulty": "easy",
    "baseTime": 30,
    "params": {
      "temperatureZones": 3,
      "hammeringSp# Game Mechanics - Master Reference Document

## Document Purpose & Status

**Version:** 5.1 MASTER (Updated with Template-Based Chunk System)  
**Last Updated:** 2025-01-XX  
**Status:** Comprehensive Developer Reference

This document serves as the complete design specification for a narrative-driven, LLM-adaptive crafting RPG. It establishes the boundary between hardcoded systems and JSON content, defines all data structures, provides comprehensive guidance for content creation, and details the complete 100×100 development world with all materials, systems, and mechanics.

**Latest Update:** Replaced random chunk generation with 9 predefined chunk templates (Peaceful/Dangerous/Rare variants of Forest/Quarry/Cave themes). Every chunk now has clear narrative identity and purpose.

**Critical Note:** This is a LIVING DOCUMENT. All numerical values are PLACEHOLDERS unless explicitly approved. The structure is final, the numbers are flexible.

---

## Table of Contents

### PART I: ARCHITECTURAL FOUNDATION
1. [Core Design Principles](#core-design-principles)
2. [Hardcode vs JSON Philosophy](#hardcode-vs-json-philosophy)
3. [Element Template System](#element-template-system)
4. [Text-Based Value System](#text-based-value-system)
5. [System Clarifications](#system-clarifications)

### PART II: GAME WORLD & CONTENT
6. [Vision & Philosophy](#vision-and-philosophy)
7. [World Structure (100×100)](#world-structure)
8. [Material System (60 Materials)](#material-system)
9. [Gathering System](#gathering-system)
10. [Resource Nodes](#resource-nodes)

### PART III: CRAFTING SYSTEMS
11. [Crafting Overview](#crafting-overview)
12. [Smithing (Weapons/Tools/Armor)](#smithing)
13. [Forging/Refining (Material Processing)](#forging-refining)
14. [Alchemy (Potions/Transmutation)](#alchemy)
15. [Engineering (Turrets/Bombs/Traps)](#engineering)
16. [Adornment/Enchanting (Enhancement)](#enchanting)
17. [Cross-Crafting Systems](#cross-crafting-systems)

### PART IV: PROGRESSION & SYSTEMS
18. [Progression Systems](#progression-systems)
19. [Character Stats](#character-stats)
20. [Level & Experience](#level-and-experience)
21. [Skill System](#skill-system)
22. [Title System](#title-system)
23. [Class System](#class-system)
24. [Equipment Progression](#equipment-progression)

### PART V: GAMEPLAY SYSTEMS
25. [Combat System](#combat-system)
26. [NPC & Quest System](#npc-quest-system)
27. [Inventory & UI](#inventory-ui)
28. [Technical Architecture](#technical-architecture)

### PART VI: DEVELOPMENT REFERENCE
29. [JSON Schema Specifications](#json-schemas)
30. [Complete Reference Tables](#reference-tables)
31. [LLM Integration Guidelines](#llm-integration)
32. [Development Roadmap](#development-roadmap)
33. [Outstanding Questions](#outstanding-questions)

---

# PART I: ARCHITECTURAL FOUNDATION

## Core Design Principles

### The Golden Rule

**"Hardcode the invariant mechanics, JSON the variable content and values."**

### Hardcode vs JSON Philosophy

**What Gets Hardcoded:**
- System mechanics (HOW things work)
- Formula SHAPES (multiplication order, calculation structure)
- Lookup hierarchy logic (override → tier/category → fallback)
- Core game loops (gathering, crafting, combat)
- Element behavior boundaries (fire never slows, ice can slow AND damage)
- Yield inversion principle (T1 = high yields, T4 = low yields)
- Tool efficiency tables (100%/50%/10% for tier matching)
- Size multiplier tables (0.8x/1.0x/1.5x/2.5x)
- Stat bonus percentages (STR = 5% per point)
- Mini-game mechanics and scoring
- Position/distance calculations
- Grid rendering system
- Equipment slot architecture

**What Goes in JSON:**
- All content definitions (items, materials, recipes, enemies)
- All numerical values (even "foundational" ones like EXP curves)
- Specific multiplier values in formulas
- Exact yield numbers per tier/category
- Material-specific overrides for special cases
- Progression curves (character levels, skill levels, title thresholds)
- Balance values and tuning parameters
- Anything that will become LLM-dynamic (even if hardcoded placeholder now)

**Key Insight:** If a "system rule" contains specific numbers/values that might change or become personalized, it should be JSON even if it feels foundational.

### Design Principles Summary

1. **Simple Rules, Infinite Complexity** - Basic mechanics scale infinitely through data and algorithms
2. **No Hard Caps** - Balance through careful tuning, not artificial limits (except max level 30 for stats)
3. **Player Agency** - Everything optional (mini-games skippable, class switching allowed, skills evolved via gameplay)
4. **3D-Ready Architecture** - All systems support seamless 2D→3D transition
5. **LLM-Enhanced Longevity** - Guided-play establishes patterns, LLM generates infinite personalized content
6. **Specialization Rewards** - Deep focus yields unique personalized content
7. **No Breaking** - Durability declines but never destroys (0% = 50% effectiveness forever)
8. **Multiplicative Scaling** - Stats × Titles × Equipment = exponential power growth
9. **EXP = Engagement** - Only mini-games grant crafting EXP (encourages skilled play)
10. **Placeholder Philosophy** - All numerical values subject to refinement during balance testing

---

## Element Template System

### The Core Principle

**CRITICAL: LLM chooses element → receives that element's template → fills it out.**

Elements are NOT free-form. Each element has a pre-defined template with specific fields. This prevents invalid combinations (fire with slowPercent field doesn't exist) and ensures predictable, balanced gameplay.

### Element Behavior Rules (Hardcoded)

**What Each Element CAN and CANNOT Do:**
- **Fire:** NEVER slows. Can burn (DoT), ignite, spread
- **Ice:** CAN slow AND damage. Can freeze, chill, shatter
- **Lightning:** Can stun and chain. Never slows or burns
- **Void:** Erases but doesn't linger. No DoT, pure instant effect
- **Holy:** Can heal and smite. Light-based, purification
- **Poison:** Can damage over time AND slow. Gradual corruption
- **Vampiric:** ONLY lifesteal element. Drains health, sustains wielder

### Element Templates (Hardcoded Structures)

```javascript
ELEMENT_TEMPLATES = {
  physical: {
    fields: ["damageValue"]
  },
  
  fire: {
    fields: ["damageValue", "damageOverTime", "duration", "chance"]
  },
  
  ice: {
    fields: ["damageValue", "damageOverTime", "slowPercent", "duration", "chance"]
  },
  
  lightning: {
    fields: ["damageValue", "stunDuration", "chance", "chainTargets"]
  },
  
  void: {
    fields: ["damageValue", "erasureChance"]
  },
  
  holy: {
    fields: ["damageValue", "healValue", "smiteDamageBonus", "duration", "chance"]
  },
  
  poison: {
    fields: ["damageValue", "damageOverTime", "slowPercent", "duration", "chance"]
  },
  
  vampiric: {
    fields: ["damageValue", "lifesteelPercent", "drainPerTick", "duration", "chance"]
  }
}
```

### LLM Generation Process

**Step-by-Step:**
1. LLM decides: "This sword should have fire properties"
2. System provides fire template: `{damageValue, damageOverTime, duration, chance}`
3. LLM fills in values: `{damageValue: [25,40], damageOverTime: [8,12], duration: 10, chance: 0.30}`
4. Result: Valid fire attribute with only fire-appropriate fields

### Example Attributes

**Fire Attribute:**
```json
{
  "element": "fire",
  "damageValue": [25, 40],
  "damageOverTime": [8, 12],
  "duration": 10,
  "chance": 0.30
}
```

**Ice Attribute:**
```json
{
  "element": "ice",
  "damageValue": [15, 25],
  "damageOverTime": [3, 6],
  "slowPercent": 0.40,
  "duration": 8,
  "chance": 0.25
}
```

**Vampiric Attribute:**
```json
{
  "element": "vampiric",
  "damageValue": [20, 30],
  "lifesteelPercent": 0.12,
  "drainPerTick": 0.03,
  "duration": 12,
  "chance": 0.15
}
```

### Benefits

✅ LLM can't create invalid combinations  
✅ Each element has exactly the fields it needs  
✅ Code knows exactly what to expect per element  
✅ Clean, predictable structure  
✅ Future expansion supported (add new elements with their own templates)

---

## Text-Based Value System ✅ IMPLEMENTED

**Implementation Status:** ✅ Fully implemented
**Source File:** `Definitions.JSON/value-translation-table-1.JSON` (237 lines)

### The Philosophy

**CRITICAL: All JSON quantity/rate fields use TEXT, not numbers. Lookup tables translate to actual values.**

This allows:
- Natural language for LLM ("many logs" not "[8,12]")
- Precise tuning for important materials (ironwood, voidsteel)
- Consistent defaults for standard materials (oak, iron)
- Easy global balance adjustments (change one table, affects all materials)
- Rarity scales naturally (T1 common = high yields, T4 legendary = low yields)

### Implemented Translation Tables

The following tables are fully implemented in `value-translation-table-1.JSON`:

#### Yield Translations
Converts text descriptors to min/max item counts:

| Descriptor | Min | Max | Description |
|------------|-----|-----|-------------|
| `few` | 1 | 2 | Minimal yield, barely worth gathering |
| `several` | 3 | 5 | Standard low yield |
| `many` | 6 | 9 | Good yield, efficient gathering |
| `abundant` | 10 | 15 | High yield, very efficient |
| `plentiful` | 16 | 25 | Exceptional yield, rare occurrence |

#### Respawn Translations
Converts text descriptors to seconds until resource respawns:

| Descriptor | Seconds | Description |
|------------|---------|-------------|
| `null` | - | Does not respawn (finite resource) |
| `quick` | 120 | 2 minutes - fast renewable |
| `normal` | 300 | 5 minutes - standard renewable |
| `slow` | 600 | 10 minutes - slow renewable |
| `very_slow` | 1200 | 20 minutes - very slow renewable |

#### Chance Translations
Converts text descriptors to drop probabilities:

| Descriptor | Probability | Percentage | Description |
|------------|-------------|------------|-------------|
| `guaranteed` | 1.0 | 100% | Always drops |
| `high` | 0.75 | 75% | Very likely to drop |
| `moderate` | 0.5 | 50% | 50/50 chance |
| `low` | 0.25 | 25% | Unlikely but possible |
| `rare` | 0.1 | 10% | Rare drop |
| `improbable` | 0.03 | 3% | Very rare drop |

#### Density Translations
Converts text descriptors to spawn counts per chunk:

| Descriptor | Count Range | Description |
|------------|-------------|-------------|
| `none` | [0, 0] | Does not spawn in this chunk type |
| `very_low` | [1, 2] | Scarce presence |
| `low` | [3, 5] | Light presence |
| `moderate` | [6, 10] | Standard presence |
| `high` | [11, 16] | Common presence |
| `very_high` | [17, 24] | Abundant presence |

#### Tier Bias Translations
Tier distribution weights for resource spawning:

| Bias Level | T1 Weight | T2 Weight | T3 Weight | T4 Weight | Description |
|------------|-----------|-----------|-----------|-----------|-------------|
| `low` | 70% | 25% | 5% | 0% | Heavily favors T1 resources |
| `mid` | 30% | 50% | 18% | 2% | Favors T2 resources |
| `high` | 10% | 30% | 50% | 10% | Favors T3 resources |
| `legendary` | 0% | 10% | 40% | 50% | Favors T4 resources |

#### Size Multipliers
Resource node size affects HP and yield:

| Size | Multiplier | HP Modifier | Yield Modifier | Description |
|------|------------|-------------|----------------|-------------|
| `small` | 0.8 | 0.7 | 0.6 | Smaller node, less HP and yield |
| `normal` | 1.0 | 1.0 | 1.0 | Standard size baseline |
| `large` | 1.5 | 1.5 | 1.4 | Larger node, more HP and yield |
| `huge` | 2.5 | 2.5 | 2.0 | Massive node, significantly more HP and yield |

#### Tool Efficiency
Effectiveness based on tool tier vs resource tier:

| Scenario | Multiplier | Description |
|----------|------------|-------------|
| `sameTier` | 1.0 | 100% efficiency - optimal |
| `oneTierHigher` | 0.5 | 50% efficiency - slow but viable |
| `twoTiersHigher` | 0.1 | 10% efficiency - impractical |
| `lowerTier` | 1.5 | 150% efficiency - overkill |

#### Resource Health by Tier
Base HP for resource nodes:

| Tier | Base HP | Description |
|------|---------|-------------|
| Tier 1 | 100 | T1 baseline health |
| Tier 2 | 200 | T2 doubled health |
| Tier 3 | 400 | T3 quadrupled health |
| Tier 4 | 800 | T4 octupled health |

#### Tool Damage by Tier
Tool stats progression:

| Tier | Base Damage | Durability | Description |
|------|-------------|------------|-------------|
| Tier 1 | 10 | 500 | T1 tool baseline |
| Tier 2 | 20 | 1000 | T2 tool doubled |
| Tier 3 | 40 | 2000 | T3 tool quadrupled |
| Tier 4 | 80 | 4000 | T4 tool octupled |

### Three-Tier Lookup Hierarchy

```
1. Material-Specific Override (hand-crafted materials like ironwood, voidsteel)
   ↓ Not found?
2. Tier + Category Default (T3 woods, T2 ores, etc.)
   ↓ Not found?
3. Global Fallback (error state, shouldn't happen)
```

### The Yield Inversion Principle

**CRITICAL BALANCE MECHANIC:**

Higher tier materials are MORE VALUABLE but LESS ABUNDANT. Combined with resource HP scaling:

| Tier | Yield Range | Resource HP | Tool Damage | Hits to Harvest |
|------|-------------|-------------|-------------|-----------------|
| T1 | plentiful (16-25) | 100 | 10 | 10 hits |
| T2 | many (6-9) | 200 | 20 | 10 hits |
| T3 | several (3-5) | 400 | 40 | 10 hits |
| T4 | few (1-2) | 800 | 80 | 10 hits |

**Note:** Matching tool tier to resource tier maintains consistent harvest time (10 hits). Using lower-tier tools increases time significantly.

### Example Calculations

**T2 Tool on T3 Resource (One Tier Higher):**
- Resource HP: 400
- Tool Damage: 20 × 0.5 efficiency = 10 effective damage
- Hits needed: 400 / 10 = 40 hits (4x longer than optimal)

**T3 Tool on T1 Resource (Lower Tier - Overkill):**
- Resource HP: 100
- Tool Damage: 40 × 1.5 efficiency = 60 effective damage
- Hits needed: 100 / 60 = 2 hits (5x faster than T1 tool)

### System Benefits

✅ Precise tuning for important materials (ironwood, voidsteel, legendary items)
✅ Consistent defaults for standard materials (oak, iron use tier/category)
✅ Easy global balance adjustments (change tier tables, affects all non-override materials)
✅ Outlier support (voidsteel can be even rarer than T4 defaults)
✅ Natural language for LLM ("many logs" not "[8,12]")
✅ Rarity scales naturally (T1 common = high yields, T4 legendary = low yields)

---

## System Clarifications

### Title System Structure

**Current Implementation:**
- Title definitions are in `titles.json` (all title data including bonuses, prerequisites)
- Progression curves (Novice = 1000 activities, Apprentice = 5000, etc.) currently hardcoded as placeholder
- **Future:** Even progression curves will become JSON/dynamic when LLM personalizes advancement rates
- **Grouping:** Titles grouped by `titleType` (gathering, crafting, combat) and `difficultyTier` (novice, apprentice, journeyman, expert, master)
- **Balance:** Hardcoded titleType and difficultyTier structures maintain balance across title system

### Skill System Structure

**Current Implementation:**
- Skill definitions are in `skills.json` (all 100+ skill definitions)
- Progression curves (Level 1 = 1000 exp, Level 2 = 2000 exp) currently hardcoded as placeholder
- **Future:** Progression curves will become JSON/dynamic for personalized advancement

**Evolution System:**
- Skill evolution is NOT automatic at level 10
- Skills CAN evolve when they reach level 10, but it's not automatic
- Evolution triggered by: NPC interaction, special area visit, major milestone/event
- Player doesn't initiate - happens through gameplay
- Level 10 is prerequisite, not trigger
- **ALL skills can evolve until reaching maximum rarity (legendary)**
- Evolution path determined by gameplay analysis, not pre-defined in skill JSON

### Progression System

**Currently Hardcoded (Placeholder Values):**
- Character level EXP curve (max 1,000,000 EXP for endgame)
- Skill level EXP curve (rarity-based exponential scaling)
- Title acquisition thresholds
- Class switching costs by level

**Future (Will become JSON/Dynamic):**
- LLM may personalize EXP curves per player
- Skill progression might vary by playstyle
- Title thresholds could adapt to player pace
- Class switching costs might become dynamic

**Therefore:** These should be JSON NOW, even though they use static placeholder values during guided-play.

**Must Be JSON (Even If Using Placeholder Values):**
- `titles.json` - Title definitions AND progression thresholds
- `skills.json` - Skill definitions AND progression curves
- `exp_curves.json` - Character leveling, skill leveling curves
- `title_progression.json` - Acquisition thresholds, RNG chances
- `class_switching.json` - Cost tables by level

---

# PART II: GAME WORLD & CONTENT

## Vision and Philosophy

### Mission: The Infinite Adaptive World

**Our Vision:** Create a 2D sandbox game that becomes a unique, infinite world for each player - one that understands how they think and adapts accordingly. Whether someone is an analytical optimizer who loves efficiency systems, a creative explorer who seeks discovery, or a social builder who enjoys collaboration, the game should recognize their cognitive style and procedurally generate content that resonates with how their mind works.

### The Infinite Promise

- **Infinite Resources** through procedural material generation
- **Infinite Recipes** via algorithmic combination systems
- **Infinite Territory** through modular world building blocks
- **Infinite Progression** where mastery opens new systems
- **Infinite Personalization** where the game learns player preferences

**Technical Philosophy:** Start with rock-solid, simple foundations (place tiles, craft items, automate systems) but architect every system to scale infinitely through data and algorithms, not code rewrites. Like Minecraft's blocks or No Man's Sky's planets - simple rules creating infinite emergent complexity.

**The Developer Challenge:** Build systems so robust and extensible that in 5 years, players could still be discovering new combinations, new territories, and new possibilities that surprise even us as the creators.

### Development Approach

**Current Phase:** Guided-play prototype (100×100 world, T1-T3 content, hand-crafted recipes establishing baseline patterns)

**Guided-Play Style:** BOTW/Minecraft approach - hints and info bubbles, but complete freedom from the start. No forced tutorial sequences. Easy start with core mechanics, gradually opens to full freedom after 3 NPCs.

**Future Phase:** LLM-driven infinite content generation begins post-guided-play, creating personalized progression, emergent specializations, and unique discoveries based on player behavior patterns.

---

## World Structure

### Development World (100×100 Units)

**Total Playable Area:** 100×100 units
- **Purpose:** Guided-play development region (prototype for larger world)
- **Grid System:** Continuous float positions with snap-to-unit for collision detection
- **3D-Ready Architecture:** All positions use {x, y, z} format where z=0 for 2D (ready for 3D conversion)
- **Future Expansion:** Post-guided-play opens to infinite procedural world generation
- **Boundaries:** None for now (players can walk to edges, system will expand later)

**Why 100×100:**
- Large enough for ~20 hours of guided-play content
- Small enough for performance testing and iteration
- Provides baseline data for LLM training
- Easy to expand without rewriting core systems

### Chunk-Based Generation System

**Chunk Structure:**
- **Chunk Size:** 16×16 units each
- **Total Chunks:** 6×6 grid = 36 chunks (with 4 unit border/padding for roads and transitions)
- **Generation Method:** Template-based with predefined themes (NOT fully random)
- **Seed-Based:** Reproducible world generation using seed values (for save/load consistency)

**Chunk Type Distribution:**

Roll d10 for each chunk during world generation:
```
1-5 = PEACEFUL VARIANTS (50% chance - safe gathering zones)
  Roll d3: 1=Forest, 2=Quarry, 3=Cave
  
6-8 = DANGEROUS VARIANTS (30% chance - high risk/reward)
  Roll d3: 1=Forest, 2=Quarry, 3=Cave
  
9-10 = RARE VARIANTS (20% chance - special themed areas)
  Roll d3: 1=Hidden Forest, 2=Ancient Quarry, 3=Deep Cave

Result: Mix of safe zones, dangerous areas, and special discoveries
```

**Design Rationale:**
- Every chunk has a clear theme and narrative identity
- Peaceful chunks provide safe baseline gathering (50% of world)
- Dangerous chunks reward risk with better nodes and higher tier materials (30%)
- Rare chunks are special discoveries with guaranteed T3 spawns (20%)
- No random mess - each chunk tells a story

---

### Chunk Content Specifications

**PEACEFUL FOREST (Safe Tree Gathering):**

```
Theme: Sunlit groves where ancient oaks stand patient. Safe haven for woodcutters.

Tree Nodes (Very High Density - Primary Resource):
- Oak Trees: 18-24 nodes per chunk (abundant, safe farming)
- Pine Trees: 15-20 nodes per chunk (abundant, alternative)
- Ash Trees: 8-12 nodes per chunk (common here)
- Birch Trees (T2): 4-6 nodes per chunk (uncommon but accessible)
- Maple Trees (T2): 2-4 nodes per chunk (rare T2 access)

Size Distribution:
- Small: 20%
- Normal: 50%
- Large: 25%
- Huge: 5%

Stone/Metal Nodes (Minimal - Not Primary Purpose):
- Limestone: 2-4 nodes per chunk
- Copper Ore: 1-2 nodes per chunk
- Purpose: Token amounts, not efficient

Enemy Spawns (Very Low Density - Safe Zone):
- Wolves: 1-2 active spawns (easily avoidable)
- Giant Beetles: 0-1 active spawns
- Purpose: Minimal threat, focus on gathering

Narrative: "Peaceful woodland where birds sing and danger is distant. The trees here grow thick and safe, perfect for beginners learning the woodcutter's craft."
```

**PEACEFUL QUARRY (Safe Stone Gathering):**

```
Theme: Open stone fields where miners work without fear. Solid, reliable deposits.

Stone Nodes (Very High Density - Primary Resource):
- Limestone: 18-24 nodes per chunk (abundant, safe farming)
- Sandstone: 15-20 nodes per chunk (abundant)
- Slate: 10-14 nodes per chunk (common here)
- Granite (T2): 4-6 nodes per chunk (uncommon but accessible)
- Marble (T2): 2-4 nodes per chunk (rare T2 access)

Size Distribution:
- Small: 20%
- Normal: 50%
- Large: 25%
- Huge: 5%

Tree/Metal Nodes (Minimal):
- Oak Trees: 2-4 nodes per chunk
- Copper Ore: 2-3 nodes per chunk

Enemy Spawns (Very Low Density):
- Giant Beetles: 1-2 active spawns (sluggish, avoidable)
- Slimes: 0-1 active spawns
- Purpose: Minimal threat, focus on gathering

Elemental Drops: Standard rates (15% Fire Crystal, 10% Storm Essence)

Narrative: "Exposed stone formations under open sky. Peaceful but exposed. The stones here are solid and plentiful, perfect for learning the mason's trade."
```

**PEACEFUL CAVE (Safe Metal Gathering):**

```
Theme: Shallow cave systems with good light. Safe ore veins for novice miners.

Metal Ore Nodes (Very High Density - Primary Resource):
- Copper Ore: 18-24 nodes per chunk (abundant, safe farming)
- Iron Ore: 15-20 nodes per chunk (abundant)
- Tin Ore: 10-14 nodes per chunk (common here)
- Steel Ore (T2): 4-6 nodes per chunk (uncommon but accessible)
- Silver Ore (T2): 2-4 nodes per chunk (rare T2 access)

Size Distribution:
- Small: 20%
- Normal: 50%
- Large: 25%
- Huge: 5%

Tree/Stone Nodes (Minimal):
- Pine Trees: 2-4 nodes per chunk
- Limestone: 3-5 nodes per chunk

Enemy Spawns (Very Low Density):
- Giant Beetles: 1-2 active spawns (guarding ore)
- Slimes: 0-1 active spawns
- Purpose: Minimal threat, focus on gathering

Narrative: "Well-lit cave entrance where sunlight still reaches. The ores here are close to the surface and easy to extract. A miner's training ground."
```

---

**DANGEROUS FOREST (High Risk Tree Gathering):**

```
Theme: Deep woods where wolves hunt in packs. Trees grow larger, stronger, more valuable.

Tree Nodes (High Density + Better Quality):
- Oak Trees: 12-16 nodes per chunk (fewer but BIGGER)
- Pine Trees: 10-14 nodes per chunk
- Ash Trees: 6-10 nodes per chunk
- Birch Trees (T2): 8-12 nodes per chunk (common here vs rare elsewhere)
- Maple Trees (T2): 6-10 nodes per chunk (common here)
- Ironwood Trees (T3): 2-3 nodes per chunk (5% chance, guaranteed if rolled)

Size Distribution (Shifted toward larger):
- Small: 5%
- Normal: 30%
- Large: 40%
- Huge: 25% (5x more huge nodes than peaceful)

Stone/Metal Nodes (Sparse):
- Limestone: 1-2 nodes per chunk
- Copper Ore: 0-1 nodes per chunk

Enemy Spawns (High Density - Dangerous):
- Wolves: 6-10 active spawns (pack hunters, coordinated)
- Giant Beetles: 2-4 active spawns
- Purpose: Serious threat, must fight or evade constantly

Narrative: "The forest deepens here. Ancient trees loom overhead, their trunks thick as houses. Wolves howl in the distance. Risk and reward walk hand in hand."
```

**DANGEROUS QUARRY (High Risk Stone Gathering):**

```
Theme: Unstable rock formations where danger lurks. Rare stones and elemental concentrations.

Stone Nodes (High Density + Better Quality):
- Limestone: 12-16 nodes per chunk (fewer but BIGGER)
- Sandstone: 10-14 nodes per chunk
- Slate: 8-12 nodes per chunk
- Granite (T2): 8-12 nodes per chunk (common here)
- Basalt (T2): 6-10 nodes per chunk (common here)
- Obsidian (T3): 2-3 nodes per chunk (5% chance, guaranteed if rolled)

Size Distribution (Shifted toward larger):
- Small: 5%
- Normal: 30%
- Large: 40%
- Huge: 25%

Tree/Metal Nodes (Sparse):
- Oak Trees: 1-2 nodes per chunk
- Copper Ore: 1-2 nodes per chunk

Enemy Spawns (High Density):
- Giant Beetles: 5-8 active spawns (aggressive defenders)
- Slimes: 3-5 active spawns
- Purpose: Constant combat, beetles defend nodes aggressively

Elemental Drops: Enhanced rates (25% Fire Crystal, 20% Storm Essence, 18% Frost Shard)

Narrative: "Jagged stone spires jut from cracked earth. The air crackles with trapped elemental energy. Beetles the size of dogs guard the richest veins."
```

**DANGEROUS CAVE (High Risk Metal Gathering):**

```
Theme: Deep tunnels where light fails. Rich ore deposits in perilous darkness.

Metal Ore Nodes (High Density + Better Quality):
- Copper Ore: 12-16 nodes per chunk (fewer but BIGGER)
- Iron Ore: 10-14 nodes per chunk
- Tin Ore: 8-12 nodes per chunk
- Steel Ore (T2): 8-12 nodes per chunk (common here)
- Silver Ore (T2): 6-10 nodes per chunk (common here)
- Mithril Ore (T3): 2-3 nodes per chunk (5% chance, guaranteed if rolled)

Size Distribution (Shifted toward larger):
- Small: 5%
- Normal: 30%
- Large: 40%
- Huge: 25%

Tree/Stone Nodes (Sparse):
- Pine Trees: 1-2 nodes per chunk
- Limestone: 2-3 nodes per chunk

Enemy Spawns (High Density):
- Giant Beetles: 5-8 active spawns (nest defenders)
- Slimes: 3-5 active spawns (cave dwellers)
- Purpose: Dangerous environment, must fight through

Narrative: "Darkness presses close. Your torch barely holds it back. But here, where few dare venture, the richest ore veins glitter in the stone."
```

---

**HIDDEN FOREST (Rare Special Discovery):**

```
Theme: Secret grove untouched by civilization. Ancient trees and mystical energy.

Tree Nodes (Maximum Density + Guaranteed Rares):
- Oak Trees: 20-28 nodes per chunk (ancient specimens)
- Pine Trees: 18-24 nodes per chunk
- Ash Trees: 12-18 nodes per chunk
- Birch Trees (T2): 15-20 nodes per chunk (abundant)
- Maple Trees (T2): 12-18 nodes per chunk (abundant)
- Ancient Oak (T3): 1 GUARANTEED huge node (1000 HP, 25-35 logs)
- Ironwood Trees (T3): 3-5 nodes per chunk (GUARANTEED, not RNG)

Size Distribution (Heavily toward larger):
- Small: 0%
- Normal: 20%
- Large: 50%
- Huge: 30% (6x more huge nodes)

Stone/Metal Nodes (Minimal):
- Limestone: 2-3 nodes per chunk
- Copper Ore: 1-2 nodes per chunk

Enemy Spawns (Moderate - Guardians):
- Wolves: 4-6 active spawns (territorial, but not aggressive)
- Purpose: Present but not overwhelming, respects sacred space

Special Feature: All trees have +20% yield bonus (passive buff for entire chunk)

Narrative: "You stumble through dense undergrowth and find... this. An ancient grove where trees grow to impossible size. The air hums with something you can't name. Sacred ground."
```

**ANCIENT QUARRY (Rare Special Discovery):**

```
Theme: Ruins of old civilization. Stone quarried by forgotten hands, elemental convergence.

Stone Nodes (Maximum Density + Guaranteed Rares):
- Limestone: 20-28 nodes per chunk
- Sandstone: 18-24 nodes per chunk
- Slate: 15-20 nodes per chunk
- Granite (T2): 15-20 nodes per chunk (abundant)
- Marble (T2): 12-18 nodes per chunk (abundant)
- Crystal Quartz (T3): 3-5 nodes per chunk (GUARANTEED)
- Obsidian (T3): 2-4 nodes per chunk (GUARANTEED)

Size Distribution (Heavily toward larger):
- Small: 0%
- Normal: 20%
- Large: 50%
- Huge: 30%

Tree/Metal Nodes (Minimal):
- Oak Trees: 2-3 nodes per chunk
- Copper Ore: 2-3 nodes per chunk

Enemy Spawns (Moderate):
- Giant Beetles: 4-6 active spawns (ancient guardians)
- Slimes: 2-4 active spawns
- Purpose: Present but manageable with preparation

Elemental Drops: Maximum rates (40% Fire Crystal, 35% Storm Essence, 30% Frost Shard, 25% Inferno Core)

Special Feature: All stones have +30% elemental drop chance (passive buff)

Narrative: "Carved pillars still stand after centuries. The ancients knew this place held power. Now you understand why. Every stone thrums with elemental potential."
```

**DEEP CAVE (Rare Special Discovery):**

```
Theme: Depths where few have ventured. Untapped ore veins of legendary quality.

Metal Ore Nodes (Maximum Density + Guaranteed Rares):
- Copper Ore: 20-28 nodes per chunk
- Iron Ore: 18-24 nodes per chunk
- Tin Ore: 15-20 nodes per chunk
- Steel Ore (T2): 15-20 nodes per chunk (abundant)
- Silver Ore (T2): 12-18 nodes per chunk (abundant)
- Mithril Ore (T3): 3-5 nodes per chunk (GUARANTEED)
- Adamantine Ore (T3): 2-4 nodes per chunk (GUARANTEED)

Size Distribution (Heavily toward larger):
- Small: 0%
- Normal: 20%
- Large: 50%
- Huge: 30%

Tree/Stone Nodes (Minimal):
- Pine Trees: 1-2 nodes per chunk
- Limestone: 3-5 nodes per chunk

Enemy Spawns (Moderate):
- Giant Beetles: 4-6 active spawns (nest colony)
- Slimes: 3-5 active spawns
- Purpose: Present but manageable with preparation

Special Feature: All ores have +20% rarity chance (Uncommon → Rare upgrade more likely)

Narrative: "Descend the winding passage. The air grows thick and hot. This far down, the earth's bones are exposed. Metals no smith has seen in a generation wait in the dark."
```

---

### Chunk Generation Rules

**World Generation Process:**
1. For each of 36 chunks, roll d10 to determine category
2. If Peaceful (1-5): Roll d3 for variant (Forest/Quarry/Cave)
3. If Dangerous (6-8): Roll d3 for variant (Forest/Quarry/Cave)
4. If Rare (9-10): Roll d3 for variant (Hidden Forest/Ancient Quarry/Deep Cave)
5. Place spawn area override (center 3×3 chunks forced to Peaceful variants)
6. Generate road connecting spawn to 3 NPC locations
7. Populate each chunk using its template specifications

**Spawn Area Exception:**
- Center 3×3 chunks (9 chunks total) MUST be Peaceful variants
- Mix of Peaceful Forest, Peaceful Quarry, Peaceful Cave
- Ensures new players have safe starting area
- +50% resource density in spawn chunks (tutorial safety)

**Expected World Composition (36 chunks):**
- Spawn Safe Zone: 9 chunks (forced Peaceful)
- Peaceful Variants: ~9 chunks (50% of remaining 27)
- Dangerous Variants: ~8 chunks (30% of remaining 27)
- Rare Variants: ~10 chunks (20% of remaining 27, includes spawn)
- Road: Connects through 3-4 chunks

### The 9 Chunk Templates

**Peaceful Variants (50% of world - Safe gathering zones):**
1. **Peaceful Forest** - Safe tree gathering, low enemy density, abundant Oak/Pine/Ash
2. **Peaceful Quarry** - Safe stone gathering, low enemy density, abundant Limestone/Sandstone/Slate
3. **Peaceful Cave** - Safe metal gathering, low enemy density, abundant Copper/Iron/Tin

**Dangerous Variants (30% of world - High risk/reward):**
4. **Dangerous Forest** - High-tier trees common, high enemy density, larger nodes (25% huge vs 5%)
5. **Dangerous Quarry** - High-tier stones common, aggressive beetles, enhanced elemental drops
6. **Dangerous Cave** - High-tier ores common, high enemy density, larger nodes

**Rare Variants (20% of world - Special discoveries):**
7. **Hidden Forest** - Maximum tree density, guaranteed Ancient Oak (T3), +20% yield buff
8. **Ancient Quarry** - Maximum stone density, guaranteed Crystal Quartz + Obsidian (T3), +30% elemental drops
9. **Deep Cave** - Maximum ore density, guaranteed Mithril + Adamantine (T3), +20% rarity upgrade chance

**World Composition (36 total chunks):**
- Spawn Safe Zone: 9 chunks (forced Peaceful variants)
- Peaceful Zones: ~9 additional chunks
- Dangerous Zones: ~11 chunks  
- Rare Zones: ~7 chunks
- Roads: 3-4 chunks

This creates a world with: safe starting area → challenging exploration → legendary discoveries.

---

### Spawn Area & Road System

**Player Spawn Point:** Center of world at coordinates (50, 50)

**Spawn Area (Center 3×3 Chunks = 48×48 Unit Safe Zone):**
```
Guaranteed Resource Distribution:
- All chunks within 24 units of spawn guaranteed to be GRASSLAND type
- Higher than normal density of starter materials:
  - Oak Trees: +50% spawn rate (12-18 per chunk instead of 8-12)
  - Pine Trees: +50% spawn rate
  - Limestone: +50% spawn rate
  - Copper Ore: +50% spawn rate
  - Iron Ore: +50% spawn rate

Lower Enemy Density:
- Wolves: 1-2 per chunk (instead of 2-3)
- Slimes: 0-1 per chunk (instead of 1-2)
- Giant Beetles: 0-1 per chunk (instead of 1-2)

Purpose:
- Safe learning environment
- Immediate access to all T1 material types
- Tutorial quests completable without leaving spawn area
- No frustrating deaths during first 30 minutes
```

**Road System (Clear Path to NPCs):**

```
Road Path (Winding, No Resource Spawns):

Start: (50, 50) - Player spawn point
  ↓ (curves northwest, approximately 20 units)
NPC 1: (35, 40) - The Mentor (Tutorial Guide)
  ↓ (curves west, approximately 15 units)
NPC 2: (20, 50) - The Artisan (Forging/Refining Teacher)
  ↓ (curves north, approximately 25 units)
NPC 3: (25, 25) - The Wanderer (Advanced Specialization)

Total Path Length: ~60 units of connected road
```

**Road Properties:**
```
Visual Appearance:
- Width: 2-3 units (wide enough to be obvious)
- Texture: Distinct from surrounding terrain (packed dirt, cobblestone, etc.)
- Color: Lighter/darker than grass to stand out

Mechanical Properties:
- No resource node spawning on road tiles
- Movement speed bonus: +20% when on road (optional quality-of-life)
- Cannot place structures on road (reserved for navigation)
- NPCs always visible from road (no hidden behind trees)

Purpose:
- Clear navigation for new players
- Prevents disorientation in early game
- Natural progression path (spawn → NPC 1 → NPC 2 → NPC 3)
- Road branches can extend to future content areas
```

### Chunk JSON Template

**Template:**
```json
{
  "metadata": {
    "narrative": "Peaceful woodland where birds sing and danger is distant. The trees here grow thick and safe, perfect for beginners learning the woodcutter's craft."
  },
  
  "chunkType": "peaceful_forest",
  "name": "Peaceful Forest",
  "category": "peaceful",
  "theme": "forest",
  
  "resourceDensity": {
    "oak_tree": {
      "density": "very_high",
      "count": [18, 24],
      "tierBias": "low"
    },
    "pine_tree": {
      "density": "very_high", 
      "count": [15, 20],
      "tierBias": "low"
    },
    "birch_tree": {
      "density": "moderate",
      "count": [4, 6],
      "tierBias": "mid"
    }
  },
  
  "sizeDistribution": {
    "small": 0.20,
    "normal": 0.50,
    "large": 0.25,
    "huge": 0.05
  },
  
  "enemySpawns": {
    "wolf_grey": {
      "density": "very_low",
      "count": [1, 2],
      "behavior": "passive_patrol"
    }
  },
  
  "specialFeatures": [],
  
  "generationRules": {
    "rollWeight": 5,
    "adjacencyPreference": ["peaceful_forest", "peaceful_quarry"],
    "spawnAreaAllowed": true
  }
}
```

---

## Material System

**CRITICAL NOTE: All 57 materials listed below are PLACEHOLDERS for guided-play development. (3 T4 monster drops pending implementation.) Names, descriptions, properties, and balance are subject to change during playtesting and narrative refinement. These establish baseline patterns for LLM generation post-guided-play.**

### Material System Structure

**5 Material Categories:**
1. **Metals** - Ores and ingots for weapons, armor, tools (15 materials total)
2. **Woods** - Lumber for handles, structures, fuel (12 materials total)
3. **Stones** - Building materials, refinement bases, elemental sources (12 materials total)
4. **Elemental Materials** - Crystals and essences for magical properties (12 materials total)
5. **Monster Drops** - Organic materials from creatures (12 materials total - NOTE: 3 materials missing from T4, needs completion)

**Total Materials:** 57 materials CURRENTLY DEFINED (3 T4 monster drops missing - see note below)

**Material Acquisition Summary:**
- **Metals:** Gathered from Metal Ore Chunks using Pickaxe, MUST be refined to ingots before use
- **Woods:** Gathered from Tree Nodes using Axe, can be used raw or refined to planks
- **Stones:** Gathered from Stone Nodes using Pickaxe, used directly (no processing)
- **Elementals:** Bonus drops from Stone Nodes (RNG-based, higher tier stones = higher drop chance)
- **Monster Drops:** Looted from defeated enemies (click corpse after combat)

### 🔩 METALS (15 Total)

**Processing Rule:** Type A (Required Refinement) - All metal ores CANNOT be used in recipes directly. Must refine Ore → Ingot at T1+ Refinery before crafting.

#### Tier 1 Metals (Starter/Common)

**Copper Ore → Copper Ingot**
- *"A soft, reddish metal found in shallow veins near the surface. Easy to work with basic tools but lacks the durability needed for serious combat. The foundation of all smithing - every blacksmith's first lesson."*
- **Source:** Metal ore chunks (Grassland common, Ore chunks abundant)
- **Spawn Rate:** Common (4-8 in grassland, 10-15 in ore chunks)
- **Tool Required:** T1 Pickaxe
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, no material loss)
- **Yield:** several
- **Uses:** Basic tools (low durability), early weapons (low damage), binding components, alloy base (Bronze), decorative items, cheap repairs
- **Notable Property:** Malleable - easy to work with, forgiving for beginner crafters, accepts enchantments readily

**Iron Ore → Iron Ingot**
- *"Sturdy grey metal from common deposits throughout the land. The workhorse of civilization - reliable, abundant, and strong enough for most purposes. If copper is a blacksmith's first lesson, iron is their bread and butter."*
- **Source:** Metal ore chunks (Grassland common, Ore chunks abundant)
- **Spawn Rate:** Common (3-6 in grassland, 8-12 in ore chunks)
- **Tool Required:** T1 Pickaxe
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, no material loss)
- **Yield:** several
- **Uses:** Standard tools (moderate durability), weapons and armor (reliable stats), construction components, majority of T1 recipes, general-purpose crafting
- **Notable Property:** Balanced - no major strengths or weaknesses, versatile across all crafting types, industry standard for T1

**Tin Ore → Tin Ingot**
- *"A silvery metal with a subtle sheen, softer than iron but resistant to corrosion. Rarely used alone, but when combined with copper through careful forging, creates bronze - an alloy stronger than either parent metal."*
- **Source:** Metal ore chunks (Grassland uncommon, Ore chunks common)
- **Spawn Rate:** Uncommon (1-3 in grassland, 4-8 in ore chunks)
- **Tool Required:** T1 Pickaxe
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, no material loss)
- **Yield:** few
- **Uses:** Alloy creation (primary use: Copper + Tin = Bronze), protective coatings, corrosion-resistant components, specialized crafting recipes, waterproofing materials
- **Notable Property:** Alloy Catalyst - essential for Bronze creation, teaches players multi-material forging, gateway to understanding advanced metallurgy

#### Tier 2 Metals (Intermediate/Quality)

**Steel Ore → Steel Ingot**
- *"Dense, carbon-rich iron deposits from deeper veins where ancient fires left their mark. The metal holds an edge far better than common iron and weathers harsh conditions without complaint. A warrior's metal."*
- **Source:** Metal ore chunks (Ore chunks common, rare in grassland)
- **Spawn Rate:** Uncommon (10% chance in grassland, 3-6 in ore chunks)
- **Tool Required:** T2 Pickaxe (or T1 at 50% efficiency - takes 4x longer)
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, no material loss)
- **Yield:** several
- **Uses:** Quality weapons (excellent edge retention), durable armor (resists wear), refined tools (longer lifespan), upgrade component for T1 items, professional-grade equipment
- **Notable Property:** Edge Retention - weapons stay sharp longer, tools last longer, durability 25% higher than iron equivalents

**Silver Ore → Silver Ingot**
- *"Gleaming white metal with mysterious properties that seem to resonate with the unseen. Conducts magical energies as readily as it conducts heat, making it invaluable for enchantments and elemental crafting. Alchemists prize it above gold."*
- **Source:** Metal ore chunks (Ore chunks uncommon, rare in forest/quarry)
- **Spawn Rate:** Rare (10% chance in grassland, 2-4 in ore chunks)
- **Tool Required:** T2 Pickaxe
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, no material loss)
- **Yield:** few
- **Uses:** Enchantment bases (magical conductivity), elemental weapons (fire/ice channeling), magical accessories (amplifies effects), alchemical catalysts, high-tier enchanting components
- **Notable Property:** Magical Conductivity - +50% effectiveness of elemental/magic properties, required for many enchanting recipes, synergizes with Elemental Materials

**Bronze Alloy** (Refined from Copper Ore + Tin Ore)
- *"The first true alloy discovered by ancient metallurgists - harder than copper, more workable than raw iron. The perfect balance between strength and flexibility. A smith's reliable companion when iron is too rigid and copper too weak."*
- **Source:** Crafted at T1+ Refinery (NOT found in world)
- **Refining Recipe:** 1 Copper Ore + 1 Tin Ore → 1 Bronze Alloy
- **Tool Required:** N/A (created through forging, not gathered)
- **Yield:** N/A (crafted material)
- **Uses:** Balanced weapons (compromise between damage and speed), early armor (good protection without weight penalty), decorative items (polishes beautifully), stepping stone between T1 and T2 gear
- **Notable Property:** Balanced Stats - sits between Copper and Iron in all properties, teaches alloy creation concept, demonstrates material fusion

#### Tier 3 Metals (Rare/Legendary)

**Mithril Ore → Mithril Ingot**
- *"Impossibly light, impossibly strong. This silvery-blue metal seems to defy the natural laws of the physical world - a feather-light helmet that stops a warhammer, a blade that never dulls yet weighs less than a wooden stick. Legends claim it fell from the stars themselves."*
- **Source:** Metal ore chunks (Rare spawns in ore chunks 5%, very rare in deep areas)
- **Spawn Rate:** Very Rare (5% chance in ore chunks for 1-2 spawns)
- **Tool Required:** T3 Pickaxe (or T2 at 50% efficiency)
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, but ore is precious)
- **Yield:** few
- **Uses:** Legendary weapons (high damage, low weight), elite armor (maximum protection, minimal encumbrance), advanced mechanisms (flying machines, intricate clockwork), prestige items for masters
- **Notable Property:** Weightless Strength - 50% lighter than steel with 200% durability, allows heavy armor without movement penalty, signature legendary material

**Adamantine Ore → Adamantine Ingot**
- *"Black as a moonless night, heavy as original sin, and harder than any metal known to civilization. This material refuses to yield to lesser tools and laughs at the concept of 'damage.' Forged in the deepest, hottest places where the earth's heart beats molten."*
- **Source:** Metal ore chunks (Rare spawns in ore/volcanic chunks 5%, deep earth)
- **Spawn Rate:** Very Rare (5% chance in ore chunks for 1 spawn)
- **Tool Required:** T3 Pickaxe (T2 barely scratches it)
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, but requires high heat)
- **Yield:** few
- **Uses:** Impenetrable armor (maximum defense, heavy), unbreakable weapons (never loses durability), fortress construction (permanent structures), vault doors, legendary shields
- **Notable Property:** Indestructible - durability never decreases below 90%, highest defense values in game, extremely heavy (movement penalty without high VIT)

**Orichalcum Ore → Orichalcum Ingot**
- *"Golden-green metal that hums with barely contained elemental forces. Touch it and you can feel the vibrations of fire, ice, lightning coursing through the crystalline structure. Ancient texts claim this was the gods' preferred material when they walked among mortals."*
- **Source:** Metal ore chunks (Rare spawns in ancient ruins, deep caves, ore chunks 5%)
- **Spawn Rate:** Very Rare (5% chance in ore chunks for 1 spawn, guaranteed in ruins)
- **Tool Required:** T3 Pickaxe
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, resonates during refinement)
- **Yield:** few
- **Uses:** Elemental weapons (maximum element damage channeling), high-tier enchanting bases (amplifies magic), magical amplification devices, elemental armor (resists all elements), conduits for powerful magic
- **Notable Property:** Elemental Resonance - doubles the effectiveness of any elemental material combined with it, creates most powerful elemental weapons, synergy king

#### Tier 4 Metals (Mythic/Reality-Breaking)

**Voidsteel Ore → Voidsteel Ingot**
- *"Metal that seems to absorb light itself, creating a disconcerting void in space where it exists. Cold to touch yet never freezes, heavy yet seems to have no weight. Found only in places where reality grows thin - cracks between dimensions, rifts in the world's fabric. To hold it is to hold concentrated absence."*
- **Source:** Metal ore chunks (Extremely rare, void rifts, corrupted reality zones)
- **Spawn Rate:** Extremely Rare (1-2 in entire 100×100 world, guaranteed in void zones)
- **Tool Required:** T4 Pickaxe (lower tiers pass through it like smoke)
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, refinement opens small tears in reality)
- **Yield:** few (override: [1,2] even for "many")
- **Uses:** Reality-bending weapons (phase through armor, cut space itself), dimensional anchors (stabilize reality rifts), void magic items, anti-magic armor (absorbs spells), portal components
- **Notable Property:** Void Affinity - ignores physical armor, can cut through anything, absorbs magic, extremely dangerous to craft with, can create instabilities

**Celestium Ore → Celestium Ingot**
- *"Radiant metal that glows with perpetual inner light, warm to the touch and impossibly weightless - less than air, less than thought. Appears only in places touched by cosmic forces - meteor impact sites, celestial shrines where stars have kissed the earth. To work with it is to work with solidified starlight."*
- **Source:** Metal ore chunks (Extremely rare, meteor sites, celestial convergences)
- **Spawn Rate:** Extremely Rare (1-2 in entire 100×100 world, guaranteed at impact sites)
- **Tool Required:** T4 Pickaxe (glows when near celestium)
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, releases light during process)
- **Yield:** few
- **Uses:** Divine weapons (holy damage, evil-slaying), holy armor (demon protection), light-based technology (permanent illumination), angelic constructs, healing items
- **Notable Property:** Holy Light - deals bonus damage to dark creatures, provides healing aura, never rusts or tarnishes, weightless, shines in darkness

**Eternium Ore → Eternium Ingot**
- *"Crystalline metal that exists in multiple temporal states simultaneously. Scholars argue endlessly whether it's matter or energy, present or future, real or probability. The truth? It is all of these and none - a material that has transcended the concept of 'being' to become 'becoming.'"*
- **Source:** Metal ore chunks (Legendary rarity, time-distorted zones, ancient forges, temporal anomalies)
- **Spawn Rate:** Legendary (0-1 in entire 100×100 world, maybe)
- **Tool Required:** T4 Pickaxe (appears in different states each hit)
- **Refining Ratio:** 1 Ore → 1 Ingot (1:1, but exists in flux during process)
- **Yield:** few
- **Uses:** Timeless equipment (durability frozen in time, never degrades), perpetual machines (motion without energy), reality anchors (prevent time alteration), paradox weapons (strike before swung), chronomancer items
- **Notable Property:** Temporal Flux - item durability frozen at creation value, effects can occur before cause, enables time manipulation, breaks conventional physics

### 🌲 WOODS (12 Total)

**Processing Rule:** Type B (Optional Refinement) - All wood materials can be used RAW (logs) in recipes directly. Optionally refine Log → Plank at any Refinery for improved stats (+durability, +quality). Player choice: quick crafting with raw logs vs better items with refined planks.

#### Tier 1 Woods (Common/Starter)

**Oak Logs → Oak Planks**
- *"Reliable, sturdy timber from the ancient oaks that dot the landscape like patient guardians. Dense grain, strong fibers, and a warm golden-brown hue that darkens with age. This is the standard by which all other woods are measured - if your tool holds true with oak, it's properly made."*
- **Source:** Oak trees (Grassland very common, Forest abundant)
- **Spawn Rate:** Very Common (8-12 in grassland, 15-20 in forest)
- **Tool Required:** T1 Axe
- **Processing:** Optional - Oak Logs (usable raw) → Oak Planks (+15% durability, +10% quality)
- **Yield:** Normal oak tree (100 HP) drops several logs
- **Uses:** Tool handles (standard), weapon grips (comfortable), basic structures (houses, walls), fuel (long-burning), general crafting (most T1 recipes accept oak), furniture, shields
- **Notable Property:** Versatile Standard - accepted in 90% of wood-requiring recipes, reliable baseline stats, teaches basic crafting, abundant everywhere

**Pine Logs → Pine Planks**
- *"Light, flexible wood harvested from tall conifers, carrying the sharp, clean scent of mountain air. Works easily under a blade, bends without breaking, but lacks the crushing strength of hardwoods. Perfect for when you need reach over raw power."*
- **Source:** Pine trees (Grassland common, Forest abundant)
- **Spawn Rate:** Common (6-10 in grassland, 12-18 in forest)
- **Tool Required:** T1 Axe
- **Processing:** Optional - Pine Logs (usable raw) → Pine Planks (+10% durability, +15% flexibility)
- **Yield:** Normal pine tree (100 HP) drops several logs
- **Uses:** Lightweight handles (reduced weight penalty), arrow shafts (straight grain), bows (natural flex), kindling (ignites easily), temporary structures (quick construction), ladders, poles
- **Notable Property:** Lightweight Flex - items 20% lighter than oak equivalents, provides flexibility bonus, best for ranged weapons and tools requiring reach

**Ash Logs → Ash Planks**
- *"Dense, shock-resistant timber favored by master craftsmen who know the difference between 'good enough' and 'perfect.' The pale wood absorbs impacts like a clenched fist absorbing a punch - flexing just enough to distribute force, then springing back untouched. Warriors know: the best spear shaft is always ash."*
- **Source:** Ash trees (Grassland uncommon, Forest common)
- **Spawn Rate:** Uncommon (2-4 in grassland, 6-10 in forest)
- **Tool Required:** T1 Axe
- **Processing:** Optional - Ash Logs (usable raw) → Ash Planks (+20% durability, +5% impact resistance)
- **Yield:** Normal ash tree (100 HP) drops several logs
- **Uses:** Premium tool handles (shock absorption), weapon shafts (spears, staves, hammers), durable construction (load-bearing), practice weapons (won't splinter), siege equipment
- **Notable Property:** Impact Resistance - reduces durability loss by 15% when used for handles, weapons with ash components lose less durability on heavy impacts, premium T1 material

#### Tier 2 Woods (Quality/Specialized)

**Birch Logs → Birch Planks**
- *"Pale wood with grain so fine you could read text through a thin shaving. Lightweight yet surprisingly resilient, wrapping strength in elegance. The distinctive white bark peels like ancient parchment - some cultures use it for writing, but craftsmen know its true value lies in the timber beneath."*
- **Source:** Birch trees (Forest zones common, rare in grassland)
- **Spawn Rate:** Uncommon (10% in grassland, 5-8 in forest)
- **Tool Required:** T2 Axe (T1 axe at 50% efficiency)
- **Processing:** Optional - Birch Logs → Birch Planks (+18% durability, +12% precision)
- **Yield:** Normal birch tree (200 HP) drops several logs
- **Uses:** Quality bows (superior flex and snap-back), refined furniture (beautiful grain), precision tools (fine control), musical instruments (resonance), scrollwork, high-end construction
- **Notable Property:** Precision Crafting - items have tighter tolerances, +5% accuracy on ranged weapons, beautiful aesthetic for decorative items

**Maple Logs → Maple Planks**
- *"Hard, dense timber with grain patterns that seem to flow like water frozen in time. Takes a polish so deep you can see your reflection, holds details so fine they look carved by divine hands. If oak is the craftsman's standard, maple is the artist's dream."*
- **Source:** Maple trees (Forest zones common)
- **Spawn Rate:** Uncommon (rare in grassland, 4-6 in forest)
- **Tool Required:** T2 Axe
- **Processing:** Optional - Maple Logs → Maple Planks (+22% durability, +15% finish quality)
- **Yield:** Normal maple tree (200 HP) drops several logs
- **Uses:** Superior weapon components (high-end grips, pommels), fine crafting (detailed work), decorative items (polishes beautifully), prestige furniture (noble houses), musical instruments, display pieces
- **Notable Property:** Fine Detail - accepts intricate carving, holds polish indefinitely, increases item quality tier when used in recipes, aesthetic perfection

**Cedar Logs → Cedar Planks**
- *"Aromatic red wood that fills the air with a scent insects despise and humans find calming. Naturally resistant to rot, weathering, and the passage of time itself. Legends say cedar chests can preserve cloth for centuries - the legends don't exaggerate."*
- **Source:** Cedar trees (Forest uncommon, rare elsewhere)
- **Spawn Rate:** Rare (rare in grassland, 2-4 in forest)
- **Tool Required:** T2 Axe
- **Processing:** Optional - Cedar Logs → Cedar Planks (+15% durability, +25% decay resistance)
- **Yield:** Normal cedar tree (200 HP) drops several logs
- **Uses:** Preservation (storage chests, food containers), weather-resistant construction (outdoor structures, boats), aromatic items (wardrobes, incense), rot-proof materials, long-term storage, naval construction
- **Notable Property:** Decay Resistance - items lose durability 30% slower in wet/outdoor conditions, natural pest resistance, aromatic bonus (items smell pleasant)

#### Tier 3 Woods (Rare/Exceptional)

**Ironwood Logs → Ironwood Planks**
- *"So dense it sinks in water like a stone. So hard that careless strokes with lesser tools leave the blade damaged and the wood untouched. This timber earned its name not through metaphor but through sheer, stubborn defiance of what wood should be capable of achieving."*
- **Source:** Ironwood trees (Deep forest rare spawns, ancient groves)
- **Spawn Rate:** Very Rare (5% in forest chunks, 1 tree)
- **Tool Required:** T3 Axe (T2 at 50% efficiency, damages T1 axes)
- **Processing:** Optional - Ironwood Logs → Ironwood Planks (+30% durability, +20% density)
- **Yield:** Normal ironwood tree (400 HP) drops few logs (override: [4,7])
- **Uses:** Heavy weapon cores (warhammer hafts, quarterstaff), armor reinforcement (wooden plate equivalents), unbreakable structures (fortress gates), siege-resistant construction, permanent outdoor structures
- **Notable Property:** Extreme Density - durability rivals T2 metals, can be used for armor components, weighs 3x normal wood (heavy but indestructible), defeats conventional wisdom about wood limitations

**Ebony Logs → Ebony Planks**
- *"Black as a starless midnight, smooth as polished glass, cold to the touch yet somehow radiating power. This rare timber seems to drink in light, creating an absence more profound than mere shadow. Valued equally for its unearthly beauty and its mysterious affinity for dark enchantments."*
- **Source:** Ebony trees (Ancient forests, cursed groves, shadow zones - rare)
- **Spawn Rate:** Very Rare (rare in forest chunks, special spawn locations)
- **Tool Required:** T3 Axe
- **Processing:** Optional - Ebony Logs → Ebony Planks (+25% durability, +30% magic affinity)
- **Yield:** Normal ebony tree (400 HP) drops few logs
- **Uses:** Legendary weapon crafting (dark aesthetic, magic channeling), dark enchantments (necromancy, shadow magic), prestige items (noble status symbol), magical staves (best conductor for certain schools), cursed items (if that becomes a thing)
- **Notable Property:** Shadow Affinity - enhances dark/void magic by 50%, aesthetic perfection (pure black mirror finish), increases rarity tier of crafted items, mysterious supernatural properties

**Ancient Oak Logs → Ancient Oak Planks**
- *"Timber from trees that have stood sentinel for centuries, watching empires rise and fall, soaking in the ambient magic that permeates the world. The wood itself hums with accumulated energy - place your palm against it and feel the thrum of stored seasons, absorbed moonlight, witnessed history."*
- **Source:** Very old oak trees (Rare special spawns, sacred groves, historical sites)
- **Spawn Rate:** Very Rare (special spawn conditions, 1-2 in world)
- **Tool Required:** T3 Axe
- **Processing:** Optional - Ancient Oak Logs → Ancient Oak Planks (+28% durability, +40% magic potential)
- **Yield:** Huge ancient oak tree (1000 HP) drops plentiful logs (25-35 logs - worth the effort)
- **Uses:** Magical staffs (wizard/druid weapons), enchantment bases (high receptivity), living constructs (animated furniture, golems), druidic items, magical focuses, heirloom items
- **Notable Property:** Magical Saturation - pre-loaded with ambient magic, +50% effectiveness for nature/growth magic, living wood (can regrow in specific circumstances), historical significance

#### Tier 4 Woods (Mythic/Impossible)

**World Tree Branch → World Tree Lumber**
- *"A fragment torn from the mythical World Tree whose roots touch every realm, every plane, every possibility. The timber hums with the resonance of universal connection - hold it to your ear and you might hear echoes of distant worlds, or the breathing of reality itself."*
- **Source:** World Tree manifestations (Extremely rare, dimensional boundaries, cosmic convergence)
- **Spawn Rate:** Extremely Rare (0-1 in world, mythic quest reward, legendary discovery)
- **Tool Required:** T4 Axe (anything less can't perceive it)
- **Processing:** Optional - World Tree Branch → World Tree Lumber (+50% durability, +60% dimensional resonance)
- **Yield:** Each branch (800 HP) drops many lumber pieces (15-25 lumber pieces)
- **Uses:** Reality-bending staves (planeswalker weapons), dimensional gates (portals between locations), cosmic crafting (items that work across dimensions), universal keys (unlock anything), multiversal anchors
- **Notable Property:** Universal Resonance - works in any dimension/plane, can create portals, consciousness can perceive other realities through items made from it, ultimate rare material

**Petrified Heartwood → Petrified Planks**
- *"Wood so ancient it has transcended its original state and become stone, yet somehow retains the grain, the rings, the very soul of the living tree. It exists in a paradox state - neither wood nor stone, neither living nor dead, frozen at the exact moment of transformation."*
- **Source:** Petrified forests (Extremely rare, time-frozen zones, ancient fossil beds)
- **Spawn Rate:** Extremely Rare (special zones, 0-2 in world)
- **Tool Required:** T4 Axe (T3 treats it as stone)
- **Processing:** Optional - Petrified Heartwood → Petrified Planks (+45% durability, stone-like properties)
- **Yield:** Petrified tree (800 HP) drops many heartwood pieces (15-25 heartwood pieces)
- **Uses:** Eternal construction (never decays), time-locked items (frozen in perfect state), paradox weapons (wood-damage with stone-hardness), permanent monuments, fossilized enchantments
- **Notable Property:** Temporal Stasis - immune to decay/aging/weathering, combines properties of wood AND stone simultaneously, preserves enchantments indefinitely, philosophical conundrum made material

**Starfall Timber → Starfall Planks**
- *"Wood from trees that caught falling stars in their branches and absorbed cosmic fire into their very being. The timber burns with perpetual cold flames that provide light without heat, illumination without consumption. To work with it is to shape captured starlight."*
- **Source:** Celestial impact sites (Legendary rarity, meteor strikes, stellar conjunction zones)
- **Spawn Rate:** Legendary (0-1 in world, maybe none)
- **Tool Required:** T4 Axe (glows blue when near starfall timber)
- **Processing:** Optional - Starfall Timber → Starfall Planks (+40% durability, perpetual luminescence)
- **Yield:** Starfall tree (800 HP, glowing) drops many timber pieces (15-25 timber pieces)
- **Uses:** Celestial weapons (star-blessed damage), eternal lights (never dim), cosmic tools (work with celestial materials), star-blessed equipment (holy properties), beacon construction
- **Notable Property:** Cold Fire - provides light without heat, eternal luminescence (never fades), holy damage bonus, beautiful aesthetic (shimmers with inner starlight), cosmos-touched

### 🪨 STONES (12 Total)

**Processing Rule:** Direct Use - Stone materials do NOT require processing. Use them directly in recipes as-is. Primary purpose: construction, forge bases, and SOURCE OF ELEMENTAL MATERIALS (stones drop elementals when broken - see "Elemental Bonus" for each stone type).

#### Tier 1 Stones (Common/Foundational)

**Limestone**
- *"Pale, soft sedimentary stone that crumbles more easily than it cuts, forming the bedrock of most civilized regions. Essential for mortar, foundations, and basic construction - the building block of society, literal and metaphorical. Burns hot enough to occasionally release trapped fire crystals from ancient volcanic intrusions."*
- **Source:** Stone nodes (Grassland very common, Stone chunks abundant)
- **Spawn Rate:** Very Common (6-10 in grassland, 12-18 in stone chunks)
- **Tool Required:** T1 Pickaxe
- **Yield:** Normal limestone node (100 HP) drops several stones
- **Uses:** Building blocks (walls, structures), refinement base (forge construction), mortar components (binding agent), basic construction (everywhere), cheap repairs
- **Elemental Bonus:** 15% chance to drop 1 Fire Crystal when broken (ancient heat trapped in stone)
- **Notable Property:** Ubiquitous Foundation - accepted in all basic construction recipes, cheap and abundant, teaches stone gathering

**Sandstone**
- *"Gritty, layered sedimentary stone formed from compressed ancient riverbeds and desert dunes. Easy to cut and shape but prone to weathering - builders use it knowing it won't outlast empires, but it'll outlast them. Contains pockets of volatile minerals that sometimes manifest as fire crystals."*
- **Source:** Stone nodes (Grassland common, Stone chunks common)
- **Spawn Rate:** Common (4-6 in grassland, 8-12 in stone chunks)
- **Tool Required:** T1 Pickaxe
- **Yield:** Normal sandstone node (100 HP) drops several stones
- **Uses:** Basic construction (simple buildings), grinding components (abrasive), casting molds (heat-resistant), decorative blocks (tan/red colors), temporary structures
- **Elemental Bonus:** 12% chance to drop 1 Fire Crystal when broken (desert heat absorbed over eons)
- **Notable Property:** Workable - easiest stone to shape and cut, faster crafting with sandstone components, aesthetic variety (color options)

**Slate**
- *"Layered metamorphic stone that splits cleanly into flat sheets along natural fault lines. Waterproof, durable, and blessed with the odd property of holding faint electrical charges in its crystalline structure. Miners report tingling sensations and occasional sparks when breaking large deposits."*
- **Source:** Stone nodes (Grassland less common, Stone chunks common)
- **Spawn Rate:** Uncommon (2-4 in grassland, 6-10 in stone chunks)
- **Tool Required:** T1 Pickaxe
- **Yield:** Normal slate node (100 HP) drops several stones
- **Uses:** Roofing (splits into tiles), flat surfaces (floors, tables), inscribable tablets (holds etchings), waterproofing (natural sealant), electrical components
- **Elemental Bonus:** 10% chance to drop 1 Storm Essence when broken (electrical properties of metamorphic formation)
- **Notable Property:** Layered Structure - splits into thin sheets naturally, waterproof quality, mild electrical conductivity

#### Tier 2 Stones (Quality/Durable)

**Granite**
- *"Speckled igneous stone born in volcanic fury, incredibly hard and weather-resistant. The foundation of mountains, the bones of the earth. Each piece is a frozen moment of the planet's creation - cooled magma crystals locked in eternal embrace. Cold to touch, sometimes releasing frost shards from microscopic ice pockets."*
- **Source:** Stone nodes (Stone chunks common, rare in grassland)
- **Spawn Rate:** Uncommon (10% in grassland, 4-6 in stone chunks)
- **Tool Required:** T2 Pickaxe (T1 at 50% efficiency, very slow)
- **Yield:** Normal granite node (200 HP) drops several stones
- **Uses:** Durable structures (fortresses, permanent buildings), crushing tools (mortars, mills), fortifications (walls that last centuries), monuments (eternal remembrance), heavy foundations
- **Elemental Bonus:** 18% chance to drop 1 Frost Shard when broken (crystalline structure traps cold)
- **Notable Property:** Extreme Durability - structures last 200% longer, weather-resistant, extremely heavy (permanent placement)

**Marble**
- *"Smooth metamorphic limestone transformed by eons of heat and pressure into something transcendent. Swirls of color flow through the stone like frozen rivers of cream and honey. Takes a polish so perfect you can see your soul reflected back. Some blocks contain frost shards where ancient ice sheets compressed the stone."*
- **Source:** Stone nodes (Stone chunks uncommon, special formations)
- **Spawn Rate:** Rare (rare in grassland, 2-4 in stone chunks)
- **Tool Required:** T2 Pickaxe
- **Yield:** Normal marble node (200 HP) drops several stones
- **Uses:** Decorative construction (palaces, temples), enchanting platforms (magical conductivity), prestigious items (status symbols), sculpture (artistic medium), polished surfaces (mirrors, floors)
- **Elemental Bonus:** 15% chance to drop 1 Frost Shard when broken (cold pressure created it)
- **Notable Property:** Aesthetic Perfection - items gain prestige/value bonus, accepts enchantments readily, beautiful finish increases item quality tier

**Basalt**
- *"Dense volcanic stone, dark and hexagonal, formed when lava met ocean in explosive fury and cooled into geometric perfection. Each column a natural testament to the mathematics underlying reality. Still radiates faint heat from its birth - smiths prize it for forge construction."*
- **Source:** Stone nodes (Stone chunks uncommon, volcanic areas)
- **Spawn Rate:** Rare (rare in grassland, 2-4 in stone chunks)
- **Tool Required:** T2 Pickaxe
- **Yield:** Normal basalt node (200 HP) drops several stones
- **Uses:** Heat-resistant construction (forges, kilns), forge components (retains heat), heavy foundations (extreme weight), geometric construction (natural hexagons), volcanic resistance
- **Elemental Bonus:** 20% chance to drop 1 Inferno Core when broken (volcanic origin, eternal heat)
- **Notable Property:** Heat Retention - naturally warm, perfect for forge construction, resists fire damage, heavy and permanent

#### Tier 3 Stones (Rare/Powerful)

**Obsidian**
- *"Volcanic glass born in the instant when molten earth met frozen ice, cooling too fast for crystals to form. Sharp enough to split atoms and cut light itself. Black and gleaming like a window into the void, each fracture revealing edges that shame the finest steel blade. Within its depths, phoenix ash sometimes crystallizes."*
- **Source:** Stone nodes (Volcanic areas rare, stone chunks 5% rare spawn)
- **Spawn Rate:** Very Rare (5% in stone chunks for 1-2 nodes)
- **Tool Required:** T3 Pickaxe (T2 at 50%, T1 shatters)
- **Yield:** Normal obsidian node (400 HP) drops few stones
- **Uses:** Cutting edges (surgical precision), dark magic focuses, precision instruments (scientific tools), scrying surfaces (divination), ceremonial blades
- **Elemental Bonus:** 35% chance to drop 1 Phoenix Ash when broken (rebirth from fire/ice meeting)
- **Notable Property:** Razor Edge - sharpest material in game, can cut anything, fragile but deadly, dark aesthetic

**Crystal Quartz**
- *"Pure crystalline stone that grew one molecule at a time over millennia in hidden geodes. Focuses light and energy with supernatural precision - a natural amplifier of any force passed through it. Perfectly clear specimens seem to contain captured rainbows, and their resonant frequencies can shatter lesser gems."*
- **Source:** Stone nodes (Crystal caves, geodes, stone chunks 5% rare spawn)
- **Spawn Rate:** Very Rare (5% in stone chunks for 1 node)
- **Tool Required:** T3 Pickaxe
- **Yield:** Normal quartz node (400 HP) drops few crystals
- **Uses:** Magical lenses (focus/amplify), energy conductors (channel power), enchantment amplifiers (boost magic), precision optics (telescopes, scopes), resonance chambers
- **Elemental Bonus:** 40% chance to drop 1 Prismatic Gem when broken (pure light focus)
- **Notable Property:** Universal Amplifier - increases effectiveness of any magic/element by 30%, perfect clarity, scientific applications

**Void Stone**
- *"Stone that seems to exist partially outside conventional reality. Cool to touch yet never cold, absorbs sound and light creating a sphere of absolute silence around large deposits. Looking at it too long creates vertigo as your consciousness tries to comprehend matter that shouldn't exist in three dimensions."*
- **Source:** Stone nodes (Reality rifts, corrupted areas, dimensional tears - very rare)
- **Spawn Rate:** Very Rare (special spawn conditions, 1-3 in world)
- **Tool Required:** T3 Pickaxe (lower tiers phase through it)
- **Yield:** Void node (400 HP) drops few stones
- **Uses:** Dimensional anchors (stabilize reality), void magic focuses, silence fields (sound absorption), anti-magic zones, reality manipulation tools
- **Elemental Bonus:** 45% chance to drop 1 Void Essence when broken (concentrated absence)
- **Notable Property:** Reality Distortion - exists between dimensions, absorbs magic and sound, disturbing to hold, enables void/dimension magic

#### Tier 4 Stones (Mythic/Cosmic)

**Star Crystal**
- *"Crystallized starlight in solid mineral form, torn from the cosmos and embedded in earth by meteor impact. Glows eternally with inner radiance that provides light without heat, warmth without consumption. Each facet contains captured images of distant galaxies - you can see infinity if you look deep enough."*
- **Source:** Stone nodes (Meteor impact sites, celestial convergences - extremely rare)
- **Spawn Rate:** Extremely Rare (1-2 guaranteed at impact sites, 0 elsewhere)
- **Tool Required:** T4 Pickaxe (glows when near star crystal)
- **Yield:** Star crystal node (800 HP) drops few crystals
- **Uses:** Divine construction (holy structures), eternal lights (never dim), cosmic anchors (connect to stars), celestial weapons (star damage), immortal monuments
- **Elemental Bonus:** 100% guaranteed to drop 1-2 Eternal Flame when broken (star cores contain primordial fire)
- **Notable Property:** Eternal Luminescence - provides light forever, holy/cosmic damage, warm despite being stone, infinite power source

**Primordial Stone**
- *"Mineral from the literal beginning of time, containing echoes of creation itself. Impossibly dense - a fist-sized chunk weighs more than a grown man. Touch it and feel the vibrations of the universe's first moments, hear the echoes of the cosmic birth cry, sense the weight of eternity compressed into physical form."*
- **Source:** Stone nodes (Ancient ruins, world cores, creation sites - extremely rare)
- **Spawn Rate:** Extremely Rare (0-1 in world, mythic quest reward)
- **Tool Required:** T4 Pickaxe (anything less cannot scratch it)
- **Yield:** Primordial node (800 HP) drops few stones
- **Uses:** Foundation of reality (base for world anchors), time manipulation (access temporal flows), creation magic (forge something from nothing), immortal construction, reality anchors
- **Elemental Bonus:** 100% guaranteed to drop 1-2 Living Light when broken (conscious creation energy)
- **Notable Property:** Temporal Weight - contains echo of creation, extremely heavy, enables time manipulation, philosophical significance

**Living Gem**
- *"Crystalline growth that breathes and grows, neither truly alive nor truly dead. Responds to conscious thought with faint pulses of bioluminescence. Scientists claim it's a mineral. Mystics claim it's aware. The truth? Both are right. It is stone that has achieved consciousness, thought made solid."*
- **Source:** Stone nodes (Deep earth, consciousness nexuses, thought convergences - legendary)
- **Spawn Rate:** Legendary (0-1 in world, maybe none, ultimate discovery)
- **Tool Required:** T4 Pickaxe (must respect the gem's autonomy)
- **Yield:** Living gem node (800 HP) drops few gems (harvesting doesn't harm)
- **Uses:** Sentient constructs (animated items), living weapons (respond to wielder), thought amplifiers (enhance consciousness), AI cores, communication tools
- **Elemental Bonus:** 100% guaranteed to drop 1-2 Absolute Zero when broken (consciousness creating perfect stillness)
- **Notable Property:** Conscious Material - aware and responsive, can communicate (vaguely), grows over time, ultimate mystery

### ✨ ELEMENTAL MATERIALS (12 Total)

**Acquisition Method:** Elemental materials are NOT gathered directly as nodes. They drop as BONUS MATERIALS when breaking Stone Nodes (see "Elemental Bonus" percentages on each stone type above). Higher tier stones have higher drop chances. Think of it as extracting the elemental energy trapped within the stone during geological formation.

**Processing Rule:** Direct use - elemental materials require no processing, ready to use immediately in crafting.

#### Tier 1 Elemental (Common/Basic)

**Fire Crystal**
- *"Warm red crystal that never cools, crackling with inner heat like a captured ember. Common near volcanic activity where ancient fires left their signature in the stone. Hold it and feel perpetual warmth - never hot enough to burn, but hot enough to boil water."*
- **Source:** Stone node bonus drops (Limestone 15%, Sandstone 12%)
- **Drop Chance:** Common (break 10 limestone = ~1-2 fire crystals)
- **Tool Required:** Any T1 tool (dropped when stone breaks)
- **Uses:** Fire weapons (burning swords, flame arrows), heat sources (forges, cooking), elemental forging (Fire Steel, Fire Copper), warmth items (never-cold cloaks), ignition sources
- **Notable Property:** Perpetual Heat - never cools, perfect fuel source, fire element basis, can ignite flammable materials

**Frost Shard**
- *"Perpetually frozen crystal that chills the air around it in a sphere of condensation. Never melts even in furnace heat, never warms even in desert sun. Contains absolute cold - the concept of 'frozen' given physical form."*
- **Source:** Stone node bonus drops (Granite 18%, Marble 15%)
- **Drop Chance:** Uncommon (break 10 granite = ~1-2 frost shards)
- **Tool Required:** Any T1 tool (dropped when stone breaks)
- **Uses:** Ice weapons (freezing swords, frost magic), preservation (food storage, body preservation), cold resistance (gear for hot climates), elemental forging (Ice Copper, Frost Steel), freezing tools
- **Notable Property:** Absolute Cold - never melts, preserves anything nearby, ice element basis, creates frost aura

**Storm Essence**
- *"Bottled lightning crystallized into mineral form. Hums with electrical potential even in stillness - bring it near metal and watch sparks dance. Handle with care unless you enjoy the tingling sensation of controlled electrocution."*
- **Source:** Stone node bonus drops (Slate 10%, Basalt minor chance)
- **Drop Chance:** Uncommon (break 10 slate = ~1 storm essence)
- **Tool Required:** Any T1 tool (dropped when stone breaks)
- **Uses:** Lightning weapons (shock swords, electric magic), energy storage (batteries, capacitors), shock effects (stunning, paralysis), elemental forging (Storm Copper, Lightning Steel), electrical systems
- **Notable Property:** Electric Charge - generates small current, lightning element basis, dangerous when wet, creates static field

#### Tier 2 Elemental (Advanced/Concentrated)

**Inferno Core**
- *"Concentrated fire essence from the heart of ancient volcanoes, born where the earth bleeds molten stone. Burns without consuming, glows without producing heat - pure fire energy separated from its destructive aspect. What remains is fire's essence: transformation, energy, light."*
- **Source:** Stone node bonus drops (Basalt 20%, other volcanic stones)
- **Drop Chance:** Rare (break 10 basalt = ~2 inferno cores, lucky)
- **Tool Required:** Any T2 tool (dropped when stone breaks)
- **Uses:** Advanced fire weapons (plasma blades), forge enhancement (hotter fires), eternal flames (never extinguish), fire constructs (animated fire), advanced elemental forging
- **Notable Property:** Pure Flame - hotter than fire crystals, enables advanced fire recipes, essential for T2+ fire items

**Glacier Heart**
- *"Core of ancient ice compressed over millennia into crystalline perfection. Contains absolute zero made tangible - the theoretical temperature where molecular motion ceases, made real through geological miracles. Touch it and feel warmth flee."*
- **Source:** Stone node bonus drops (Granite higher chance at T2, Marble)
- **Drop Chance:** Rare (break 10 T2 granite = ~2 glacier hearts)
- **Tool Required:** Any T2 tool (dropped when stone breaks)
- **Uses:** Freezing weapons (absolute zero attacks), ice constructs (animated ice), thermal manipulation (heat extraction), advanced preservation (stasis chambers), T2+ cold recipes
- **Notable Property:** Absolute Zero - colder than frost shards, enables advanced ice magic, can freeze anything

**Tempest Orb**
- *"Captured hurricane compressed into a sphere the size of a fist. Swirls with visible wind currents trapped inside like a snow globe of pure chaos. Shake it and hear thunder. Break it and... well, don't break it."*
- **Source:** Stone node bonus drops (Higher tier stones, storm areas)
- **Drop Chance:** Rare (special weather conditions increase chance)
- **Tool Required:** Any T2 tool (dropped when stone breaks)
- **Uses:** Wind weapons (cutting gales), flight items (levitation, gliding), weather control (storm summoning), air constructs, advanced lightning recipes
- **Notable Property:** Contained Storm - releases energy when used, wind element basis, dangerous if mishandled

#### Tier 3 Elemental (Rare/Powerful)

**Phoenix Ash**
- *"Ash from a phoenix's moment of rebirth, still warm, shimmering with resurrection energy like heat waves above desert sand. Regenerates slowly over time if kept warm - a single grain can return from nothing given patience. Life and death made tangible, the moment between states crystallized."*
- **Source:** Stone node bonus drops (Obsidian 35%, phoenix encounters)
- **Drop Chance:** Very Rare (break obsidian or defeat phoenix enemies)
- **Tool Required:** Any T3 tool (dropped when stone breaks)
- **Uses:** Life weapons (healing/resurrection), resurrection items (revive fallen), renewal magic (restore/repair), regeneration effects, life constructs
- **Elemental Bonus:** Can be used to craft items that slowly regenerate durability
- **Notable Property:** Self-Regenerating - regrows over time, life element basis, resurrection magic enabler

**Void Essence**
- *"Concentrated absence given semi-physical form. Not darkness (which is merely lack of light) but the space between existence, the gaps in reality made tangible. Disturbing to hold - your mind struggles with the concept of touching nothing."*
- **Source:** Stone node bonus drops (Void Stone 45%, void creatures, reality rifts)
- **Drop Chance:** Very Rare (void stone or dimensional anomalies)
- **Tool Required:** Any T3 tool (dropped when stone breaks)
- **Uses:** Void magic (erasure, dimensional), dimensional weapons (phase through armor), erasure effects (delete from reality), anti-magic items, space manipulation
- **Notable Property:** Reality Gap - occupies space without existing, void element basis, extremely dangerous

**Prismatic Gem**
- *"Contains all elements in perfect harmonic balance - fire, ice, lightning, earth, wind, light, darkness, all singing in cosmic unity. Shifts colors continuously like an oil slick made of pure energy. Hums with universal harmony when brought near other elemental materials."*
- **Source:** Stone node bonus drops (Crystal Quartz 40%, elemental convergences)
- **Drop Chance:** Very Rare (crystal quartz or special locations)
- **Tool Required:** Any T3 tool (dropped when stone breaks)
- **Uses:** Omni-elemental items (all elements simultaneously), balance magic (harmony effects), spectrum weapons (rainbow damage), elemental amplifiers, universal conductors
- **Notable Property:** Elemental Harmony - works with ALL element types, enables multi-element recipes, perfect balance

#### Tier 4 Elemental (Mythic/Conceptual)

**Eternal Flame**
- *"Fire that existed before creation and will burn after entropy claims the last star. Not hot, not cold, but absolute in its nature - the platonic ideal of 'flame' separated from temperature, light separated from heat. This is not fire as we know it. This is the concept of fire made real."*
- **Source:** Stone node bonus drops (Star Crystal 100% guaranteed 1-2)
- **Drop Chance:** Guaranteed from star crystal, otherwise impossible
- **Tool Required:** Any T4 tool (dropped when stone breaks)
- **Uses:** Genesis weapons (creation fire), eternal forges (never extinguish), concept manipulation (work with ideas), primordial crafting, reality-level fire magic
- **Notable Property:** Conceptual Fire - exists beyond physics, burns without consuming, creation element, philosophical weapon

**Absolute Zero**
- *"The end of all motion, all energy, all heat. Crystallized impossibility - the theoretical minimum temperature where quantum mechanics says motion must cease, made solid. To touch it is to touch entropy's heart, to hold the heat death of the universe in your palm."*
- **Source:** Stone node bonus drops (Living Gem 100% guaranteed 1-2)
- **Drop Chance:** Guaranteed from living gem, otherwise impossible
- **Tool Required:** Any T4 tool (dropped when stone breaks)
- **Uses:** Entropy weapons (stop all motion), heat death magic (end energy), motion cessation (freeze time/space), ultimate cold, stasis fields
- **Notable Property:** Conceptual Cold - beyond freezing, stops molecular motion, entropy made solid, ultimate ice element

**Living Light**
- *"Sentient radiance that thinks and feels, consciousness given luminous form. Warm but not hot, bright but doesn't blind, aware but not speaking. Existence itself made visible - the light that was there before the universe said 'let there be light.' It predates creation. It IS creation."*
- **Source:** Stone node bonus drops (Primordial Stone 100% guaranteed 1-2)
- **Drop Chance:** Guaranteed from primordial stone, otherwise impossible
- **Tool Required:** Any T4 tool (dropped when stone breaks)
- **Uses:** Sentient light weapons (respond to wielder thoughts), conscious magic (aware spells), illuminated thought (telepathy), creation light, reality construction
- **Notable Property:** Conscious Energy - aware and responsive, light element personified, can communicate, ultimate mystery

### 🦴 MONSTER DROPS (12 Total - NOTE: Missing 3 T4 materials, needs completion)

**Acquisition Method:** Monster drops are obtained by defeating enemies and looting their corpses. After an enemy is defeated, a corpse entity appears that can be clicked to loot materials. Drops are immediate (no processing needed).

**Processing Rule:** Direct use - monster drops require no processing, ready to craft immediately.

#### Tier 1 Monster Drops (Common Enemies)

**Wolf Pelt**
- *"Thick fur harvested from forest wolves, warm and water-resistant, still carrying the scent of pine needles and predatory musk. The hide beneath is tough leather suitable for padding. Hunters know: a good wolf pelt can mean the difference between frostbite and comfort on a winter hunt."*
- **Source:** Wolves (common enemy in all chunk types)
- **Drop Rate:** 100% (1-2 per wolf)
- **Spawn Locations:** Grassland (2-3 wolves), Forest (4-6 wolves), Mob chunks (6-10 wolves)
- **Uses:** Basic armor padding (cold resistance), leather alternatives (flexible armor), cold resistance gear (winter clothing), fur linings (warmth), decorative items (pelts, rugs)
- **Notable Property:** Natural Warmth - provides cold resistance, lightweight armor component, versatile material

**Slime Gel**
- *"Viscous substance extracted from defeated slimes - adhesive, flexible, and remarkably versatile. Hardens when exposed to air into a rubber-like consistency but can be re-softened with gentle heat. Alchemists prize it, engineers use it for seals, and everyone underestimates it until they try removing it from their clothes."*
- **Source:** Slimes (common enemy, often near water/damp areas)
- **Drop Rate:** 100% (2-4 per slime, they're gooey)
- **Spawn Locations:** Grassland (1-2), Stone chunks (2-3), Mob chunks (4-8)
- **Uses:** Binding agent (glue for crafting), waterproofing (seals, coatings), sticky traps (area denial), alchemy ingredient (potions), flexible seals (moving parts)
- **Notable Property:** Adhesive Flex - sticks to everything, waterproof when set, can be resoftened, annoying to clean

**Chitinous Shell**
- *"Hard carapace harvested from giant insects, lightweight yet surprisingly durable due to natural composite structure. Each piece is a natural armor plate, evolved over millions of years to protect against predators. Nature's engineering at its finest."*
- **Source:** Giant Beetles (common enemy near resources)
- **Drop Rate:** 100% (1-3 per beetle)
- **Spawn Locations:** Grassland (1-2), Stone chunks (3-5), Mob chunks (3-6)
- **Uses:** Armor plates (lightweight protection), shield components (blocking), protective gear (helmets, bracers), natural armor (carapace suits), construction material (light, strong)
- **Notable Property:** Natural Composite - strong yet light, layered structure provides flexibility, insect aesthetic

#### Tier 2 Monster Drops (Uncommon Enemies - Placeholder, enemies not yet defined)

**Troll Blood**
- *"Thick, viscous blood that clots almost instantly when exposed to air, regenerating tissue at visible speeds even after extraction from the host. Healing properties persist in the separated fluid - alchemists have built careers studying why it works, healers just know it does."*
- **Source:** Trolls (uncommon enemy, needs full definition)
- **Drop Rate:** Placeholder - needs enemy design
- **Spawn Locations:** TBD - depends on troll implementation
- **Uses:** Healing potions (powerful regeneration), regenerative items (self-repair), life magic (restoration), medical applications, alchemy ingredient
- **Notable Property:** Regenerative - accelerates healing, clots instantly, medical miracle, expensive ingredient

**Drake Scale**
- *"Iridescent scale from lesser dragons, smaller cousins of true dragons but no less magnificent. Heat-resistant and naturally conductive to magical energies - each scale is a miniature fortress that also happens to channel fire like copper channels electricity. A dragon's armor in portable form."*
- **Source:** Drakes (uncommon enemy, flying lesser dragons - needs full definition)
- **Drop Rate:** Placeholder - needs enemy design
- **Spawn Locations:** TBD - volcanic areas, mountain regions
- **Uses:** Heat-resistant armor (fire immunity), magical conductors (channel magic), dragon-aspected items (fire bonus), decorative (prestige), elemental crafting
- **Notable Property:** Dragon Heritage - fire resistant, magic conductive, beautiful, prestige material

**Wraith Essence**
- *"Ectoplasmic residue from defeated spirits, intangible yet somehow collectible in special vials. Whispers faintly in a language that predates words. Cold to the touch, passes through solid matter, and gives observers the unshakeable feeling of being watched by something that no longer has eyes."*
- **Source:** Wraiths (uncommon enemy, undead/spirits - needs full definition)
- **Drop Rate:** Placeholder - needs enemy design
- **Spawn Locations:** TBD - cursed areas, graveyards, haunted zones
- **Uses:** Ghost-touched weapons (phase through armor), phase items (intangibility), spirit magic (necromancy), undead control, ethereal crafting
- **Notable Property:** Intangible - passes through matter, enables phasing, undead affinity, creepy

#### Tier 3 Monster Drops (Rare Boss Enemies - Placeholder, bosses not yet designed)

**Dragon Scale**
- *"True dragon scale, not from a lesser drake but from an actual legend made flesh. Harder than steel yet lighter than silk, shimmering with ancient power accumulated over centuries of life. Each scale is a treasure - kingdoms have gone to war over a single shed scale from an elder wyrm."*
- **Source:** Dragons (rare boss encounters - needs full definition)
- **Drop Rate:** Guaranteed from dragon bosses (3-8 per defeat)
- **Spawn Locations:** TBD - dragon lairs, mountain peaks, volcanic zones
- **Uses:** Legendary armor (ultimate protection), dragon weapons (massive power), ultimate protection (best defense), prestige items (nobles pay fortunes), magical focuses
- **Notable Property:** Ultimate Defense - highest defense values, fire immunity, magic resistance, legendary quality

**Demon Horn**
- *"Curved horn torn from defeated demons, radiating malevolent power that makes the air shimmer with heat distortion. Handle with caution and conviction - the horn remembers its previous owner and doesn't appreciate the separation. Excellent for channeling dark magic, terrible for peace of mind."*
- **Source:** Demons (rare boss, infernal creatures - needs full definition)
- **Drop Rate:** Guaranteed from demon bosses (2-5 per defeat)
- **Spawn Locations:** TBD - hell rifts, corrupted zones, summoning sites
- **Uses:** Dark weapons (unholy damage), forbidden magic (demonic spells), corruption resistance (ironic protection), dark rituals, infernal crafting
- **Notable Property:** Corrupting - dark magic bonus, may influence wielder, powerful but dangerous, moral ambiguity

**Angel Feather**
- *"Pure white plumage from celestial beings, glowing faintly with holy light that never fades. Weightless and indestructible - you can't damage it even if you try. Some claim the feathers sing hymns too quiet for mortal ears. Others claim that's just tinnitus. The faithful know better."*
- **Source:** Angels (rare boss, celestial beings - needs full definition)
- **Drop Rate:** Guaranteed from angel encounters (1-3 per encounter)
- **Spawn Locations:** TBD - holy sites, celestial convergences, temples
- **Uses:** Holy weapons (smite evil), divine magic (healing, protection), purification items (cleanse corruption), resurrection materials, celestial crafting
- **Notable Property:** Holy - bonus vs evil/undead, purifies corruption, weightless, eternal light, beautiful

#### Tier 4 Monster Drops (Legendary Mythic Bosses - Placeholder, no designs exist yet)

**Titan's Heart (PLACEHOLDER - needs design)**
- *"Still-beating heart from a fallen titan, pumping primordial energy instead of blood. Each pulse contains the power of tectonic shifts. Legend says the heart beats once per century. Legend is wrong - it beats once per thought, and titans think slowly."*
- **Source:** Titans (legendary boss - NEEDS FULL DESIGN)
- **Drop Rate:** Guaranteed from titan boss (1 per defeat, unique)
- **Spawn Locations:** TBD - world-level boss design needed
- **Uses:** Ultimate life items, creation magic, world-shaping tools (Placeholder uses)

**Void Dragon Soul (PLACEHOLDER - needs design)**
- *"Captured essence of reality-devouring dragons. Existence compressed into crystalline nightmare. Handle at existential risk."*
- **Source:** Void Dragons (legendary boss - NEEDS FULL DESIGN)
- **Drop Rate:** Guaranteed (1 per defeat)
- **Uses:** Reality-breaking weapons, void mastery, dimension control (Placeholder uses)

**God Fragment (PLACEHOLDER - needs design)**
- *"Shard of divine being, containing infinite possibilities. Warm with creative potential. Literally contains a fraction of divinity."*
- **Source:** Fallen Gods (mythic boss - NEEDS FULL DESIGN)
- **Drop Rate:** Guaranteed (1 per defeat, game-ending material)
- **Uses:** Godly weapons, creation itself, rewriting reality (Placeholder uses)

**NOTE: T4 monster drops are INCOMPLETE. These are placeholder concepts that need full boss design, encounter mechanics, and balanced implementation. Current game focus is T1-T3 content.**

---

## Gathering System ✅ IMPLEMENTED

**Implementation Status:** ✅ Core mechanics working
**Source Files:**
- `Definitions.JSON/value-translation-table-1.JSON` - Tool efficiency, resource HP, tool damage values
- `systems/resource_system.py` - Resource gathering logic

### Core Interaction Loop

**Player → Resource Node Interaction Flow:**
```
1. Player moves near resource node using WASD controls
2. System checks distance: Within 3 unit interaction radius?
3. Player clicks on resource node (mouse click on sprite/hitbox)
4. System validates:
   - Does player have correct tool type equipped? (Axe for trees, Pickaxe for ore/stone)
   - Is tool tier sufficient? (T1 tool can mine T1, struggles with T2+)
5. If valid: Tool "hits" resource
   - Visual: Resource node shakes/vibrates
   - Audio: Impact sound (wood thunk, stone crack, metal clang)
   - Particles: Material-specific particles spawn (wood chips, stone dust, ore sparkles)
   - Damage: Resource health bar depletes based on effective damage calculation
6. Repeat: Player clicks again for next hit (or holds mouse for continuous hitting)
7. Resource health reaches 0:
   - Node destruction animation plays (tree falls, stone crumbles, ore shatters)
   - Materials drop (RNG quantity based on resource size and tier)
   - Materials scatter on ground in 2-3 unit radius around node
   - Materials glow/shimmer for visibility
8. Collection: Player clicks scattered materials (1 unit pickup radius)
   - Materials automatically add to inventory (if space available)
   - Collection sound plays (satisfying chime/pickup noise)
   - Quantity notification appears briefly ("+5 Oak Logs")
9. Node disappears: Resource entity removed from world (no respawn for now)
10. Player continues: Find next resource, repeat loop
```

**Design Philosophy:**
- Click-to-gather feels rewarding (each hit is player action)
- Health bars provide clear progress feedback
- Visual/audio feedback makes gathering satisfying
- Material drop creates micro-moment of "loot collection" excitement
- No respawn creates sense of world impact (you're actually consuming resources)

### Tool Tier Efficiency System

**The Core Formula:**
```
Effective Damage = Base Tool Damage × Tool Tier Efficiency × Stat Multiplier × Title Multiplier × Equipment Multiplier

Where:
- Base Tool Damage: Tier-based flat value (T1 = 10, T2 = 20, T3 = 40, T4 = 80)
- Tool Tier Efficiency: Multiplicative modifier based on resource tier vs tool tier
- Stat Multiplier: 1 + (relevant stat points × stat bonus %)
- Title Multiplier: Cumulative from all earned titles
- Equipment Multiplier: Product of all equipment bonuses
```

**Tool Tier Efficiency Rules:**
```
Gathering SAME Tier Resource (Optimal):
- Efficiency: 100% (no modifier)
- Example: T2 Axe (20 base) vs T2 Tree (200 HP)
  - Effective Damage: 20 × 1.0 = 20 damage/hit
  - Hits to Deplete: 200 HP ÷ 20 = 10 hits
  - Result: Fast, efficient, feels good

Gathering ONE TIER HIGHER Resource (+1, Slow but Viable):
- Efficiency: 50% (half damage)
- Example: T1 Axe (10 base) vs T2 Tree (200 HP)
  - Effective Damage: 10 × 0.5 = 5 damage/hit
  - Hits to Deplete: 200 HP ÷ 5 = 40 hits  
  - Result: 4x slower, significant time investment, but POSSIBLE
  - Design: Allows progression without hard gates, rewards upgrading tools

Gathering TWO+ TIERS HIGHER Resource (+2+, Not Practical):
- Efficiency: 10% (one-tenth damage)
- Example: T1 Axe (10 base) vs T3 Tree (400 HP)
  - Effective Damage: 10 × 0.1 = 1 damage/hit
  - Hits to Deplete: 400 HP ÷ 1 = 400 hits
  - Result: Absurdly slow, not worth attempting
  - Design: Soft blocks progression (technically possible, practically insane)

Gathering LOWER Tier Resources (Efficient Farming):
- Efficiency: 150%+ (bonus damage, overkill)
- Example: T3 Axe (40 base) vs T1 Tree (100 HP)
  - Effective Damage: 40 × 1.5 = 60 damage/hit
  - Hits to Deplete: 100 HP ÷ 60 = 1.67 hits (basically 2 hits)
  - Result: 5x faster than same-tier, trivializes low-tier gathering
  - Design: Returning to starter areas for materials doesn't feel tedious
```

**Why This System Works:**
- **Natural Progression:** Players can attempt higher tiers but it's painful
- **Meaningful Upgrades:** New tools make dramatic difference (10 hits → 2 hits)
- **No Hard Walls:** Can't be permanently stuck (just slow progression)
- **Backtracking Reward:** High-tier tools make low-tier gathering trivial
- **Clear Feedback:** Players FEEL the difference between tier matches

### Resource Health Scaling

**Base Health by Tier (Doubling Pattern):**
```
T1 Resources: 100 HP base
- Oak Tree, Pine Tree, Limestone, Copper Ore, etc.
- Rationale: 10 hits with T1 tool (10 damage × 10 hits = 100 HP)

T2 Resources: 200 HP base (2x)
- Birch Tree, Maple Tree, Granite, Steel Ore, etc.
- Rationale: 10 hits with T2 tool (20 damage × 10 hits = 200 HP)

T3 Resources: 400 HP base (2x)
- Ironwood Tree, Obsidian, Mithril Ore, etc.
- Rationale: 10 hits with T3 tool (40 damage × 10 hits = 400 HP)

T4 Resources: 800 HP base (2x)
- World Tree, Star Crystal, Eternium Ore, etc.
- Rationale: 10 hits with T4 tool (80 damage × 10 hits = 800 HP)
```

**Design Goal:** Same-tier gathering always takes approximately 10 hits (consistent feedback)

### Size Variance ✅ IMPLEMENTED

From `value-translation-table-1.JSON` - **sizeMultipliers**:

| Size | Multiplier | HP Modifier | Yield Modifier | Description |
|------|------------|-------------|----------------|-------------|
| `small` | 0.8x | 0.7x | 0.6x | Smaller node, less HP and yield |
| `normal` | 1.0x | 1.0x | 1.0x | Standard size baseline |
| `large` | 1.5x | 1.5x | 1.4x | Larger node, more HP and yield |
| `huge` | 2.5x | 2.5x | 2.0x | Massive node, significantly more HP and yield |

**Example Application (T1 Oak Tree, base HP 100, base yield "several" = 3-5):**
```
SMALL Oak (70 HP, 0.6× yield):
- Hits: 7 hits with T1 tool
- Yield: 2-3 logs (60% of base)
- Efficiency: Worse HP per log, but faster

NORMAL Oak (100 HP, 1.0× yield):
- Hits: 10 hits with T1 tool
- Yield: 3-5 logs (baseline)
- Efficiency: Standard

LARGE Oak (150 HP, 1.4× yield):
- Hits: 15 hits with T1 tool
- Yield: 4-7 logs (140% of base)
- Efficiency: Slightly better HP per log

HUGE Oak (250 HP, 2.0× yield):
- Hits: 25 hits with T1 tool
- Yield: 6-10 logs (200% of base)
- Efficiency: BEST efficiency - 2.5x time for 2x reward
```

**Design Intent:**
- Small nodes: Quick emergency resources but inefficient
- Normal nodes: Balanced, most common
- Large nodes: Worth targeting (better efficiency, more total)
- Huge nodes: BEST efficiency, reward exploration and observation
- Visual feedback: Can identify valuable nodes from distance

### Tool Damage Scaling ✅ IMPLEMENTED

From `value-translation-table-1.JSON` - **toolDamageByTier**:

```
T1 Tools: 10 damage per hit
- Example: T1 Pickaxe, T1 Axe
- Result: 10 hits to deplete T1 resource (100 HP ÷ 10 = 10)

T2 Tools: 20 damage per hit (2x)
- Example: T2 Pickaxe, T2 Axe
- Result: 10 hits to deplete T2 resource (200 HP ÷ 20 = 10)

T3 Tools: 40 damage per hit (2x)
- Example: T3 Pickaxe, T3 Axe
- Result: 10 hits to deplete T3 resource (400 HP ÷ 40 = 10)

T4 Tools: 80 damage per hit (2x)
- Example: T4 Pickaxe, T4 Axe
- Result: 10 hits to deplete T4 resource (800 HP ÷ 80 = 10)
```

**Perfect Symmetry:** Tool damage doubles when health doubles, maintaining 10-hit baseline across all tiers.

### Material Yield System ✅ IMPLEMENTED

**Text-Based Yields** from `value-translation-table-1.JSON`:

| Descriptor | Min | Max | Description |
|------------|-----|-----|-------------|
| `few` | 1 | 2 | Minimal yield |
| `several` | 3 | 5 | Standard low yield |
| `many` | 6 | 9 | Good yield |
| `abundant` | 10 | 15 | High yield |
| `plentiful` | 16 | 25 | Exceptional yield |

**Combined with Size Modifiers:**
```
Example: Resource with "several" (3-5) base yield
- Small (0.6x): 2-3 materials
- Normal (1.0x): 3-5 materials
- Large (1.4x): 4-7 materials
- Huge (2.0x): 6-10 materials
```

**Yield Inversion Principle:**
Higher tier materials use lower yield descriptors:
- T1 Resources: Often use "abundant" or "plentiful"
- T2 Resources: Often use "many" or "abundant"
- T3 Resources: Often use "several" or "many"
- T4 Resources: Often use "few" or "several"

**Luck Stat Influence:**
```
Base RNG: Random(min, max) using uniform distribution
Luck Effect: Shifts distribution toward maximum value

Formula: 
final_yield = min + (max - min) × (base_random + LCK_bonus)
where LCK_bonus = LCK_stat × 0.02

Example: Normal T2 Tree (5-7 logs), Player has 15 LCK
- Base roll: Random(0.0 to 1.0) = 0.5
- LCK Bonus: 15 × 0.02 = 0.30
- Adjusted: 0.5 + 0.30 = 0.80 (capped at 1.0)
- Result: 5 + (7-5) × 0.80 = 5 + 1.6 = 6.6 logs → 7 logs (rounded up)

Zero Luck (0 LCK):
- Uniform distribution, equal chance of any value in range
- Average yield over time

High Luck (20+ LCK):
- Heavily biased toward maximum values
- Almost always get max or near-max yields
- Dramatic difference in material accumulation over time
```

**Design Philosophy:**
- Base RNG prevents predictability (keeps gathering interesting)
- Luck stat rewards builds focused on resource acquisition
- High luck builds become "farmer" specialists (gather more per node)
- Still random (never guaranteed), just statistically better

### Complete Gathering Example (With All Multipliers)

**Scenario: Player gathering Huge T2 Birch Tree (500 HP)**

**Player Build:**
- Tool: T2 Axe (20 base damage)
- Stats: 12 AGI (forestry bonus +5% per point)
- Title: Apprentice Lumberjack (+25% forestry)
- Equipment: Forestry Gloves (+10%), no other bonuses
- LCK: 8 (affects yield)

**Damage Calculation:**
```
Base Tool Damage: 20 (T2 Axe)

Tool Tier Efficiency: 1.0 (T2 tool vs T2 resource, perfect match)

Stat Multiplier:
- AGI: 12 points × 5% = +60%
- Multiplier: 1.60

Title Multiplier:
- Apprentice Lumberjack: +25%
- Multiplier: 1.25

Equipment Multiplier:
- Forestry Gloves: +10%
- Multiplier: 1.10

Total Effective Damage:
20 × 1.0 × 1.60 × 1.25 × 1.10 = 44 damage per hit
```

**Hits Required:**
```
Resource HP: 500 (Huge T2 tree = 200 base × 2.5 size)
Damage per Hit: 44
Hits Needed: 500 ÷ 44 = 11.36 hits → 12 hits

Compare to Base (no bonuses):
- Base damage: 20
- Hits needed: 500 ÷ 20 = 25 hits
- Specialized build is MORE THAN 2x faster (12 vs 25 hits)
```

**Yield Calculation:**
```
Huge T2 Tree Base Range: 15-22 logs

Luck Influence (8 LCK):
- LCK Bonus: 8 × 0.02 = 0.16
- Base Roll: Random(0-1) = 0.60 (example)
- Adjusted: 0.60 + 0.16 = 0.76
- Yield: 15 + (22-15) × 0.76 = 15 + 5.32 = 20.32 → 20 logs

Compare to No Luck:
- Average yield: (15+22)/2 = 18.5 logs
- With 8 LCK: Averaging ~19-20 logs (noticeable improvement)
```

**Total Result:**
- Hits: 12 (vs 25 base, 52% faster)
- Yield: 20 logs (vs 18.5 average, 8% more)
- Time Saved: If each hit takes 0.5 seconds, saves 6.5 seconds per tree
- Over 100 trees: Saves 650 seconds (10+ minutes of clicking)

**Design Validation:**
- Specialization feels VERY rewarding (dramatic time savings)
- Stats, titles, equipment all stack multiplicatively (big numbers)
- Luck provides consistent edge (not random spikes, steady improvement)
- High-investment builds pay off clearly

### Visual & Audio Feedback

**During Gathering (Per Hit):**
```
Visual Feedback:
- Resource node shakes/vibrates (0.2 second duration)
- Particle effects spawn at impact point:
  - Trees: Wood chips (brown/tan particles, scatter outward)
  - Stone: Dust clouds (gray/white particles, puff upward)
  - Ore: Sparkles (metallic glints, shimmer effect)
- Health bar appears above node:
  - Red bar depleting left to right
  - Current HP / Max HP displayed numerically
  - Bar color changes based on % (green > yellow > orange > red)
- Critical Hit (if triggered):
  - Larger particle burst
  - Screen shake (subtle, 1 pixel)
  - "CRIT!" text popup with damage number
  - Different impact sound (deeper/louder)

Audio Feedback:
- Impact sound varies by material:
  - Wood: Solid "thunk" (satisfying chop)
  - Stone: Sharp "crack" (brittle break)
  - Ore: Metallic "clang" (mining ring)
- Volume scales with damage dealt (higher damage = louder)
- Critical hits play enhanced sound effect
- Pitch variation (slight random pitch shift prevents monotony)
```

**On Resource Depletion (Node Destroyed):**
```
Visual Feedback:
- Destruction animation:
  - Trees: Fall in random direction, fade out during fall
  - Stone: Crumble into pieces, pieces sink into ground
  - Ore: Shatter with sparkle burst, fragments disappear
- Materials drop:
  - Items spawn at node position
  - Scatter in 2-3 unit radius (random positions)
  - Items appear with "pop-in" animation (scale from 0 to 1)
  - Glow effect around items (make them obvious)
  - Shimmer particles above items (draw attention)
- Experience gain notification:
  - "+10 EXP" floats upward from node position
  - Fades out while floating (3 second duration)

Audio Feedback:
- Destruction sound:
  - Trees: Timber creak → crash (satisfying fall)
  - Stone: Heavy crumble (boulder break)
  - Ore: Crystal shatter (high-pitch tinkle)
- Material drop sound: Soft "plink" as items hit ground
- Experience chime: Pleasant notification tone
```

**Material Collection (Pickup):**
```
Visual Feedback:
- Item highlights when mouse hover (outline glow)
- On click: Item flies toward player character
  - Parabolic arc animation (looks natural)
  - Scales down during flight (perspective)
  - Disappears when reaching player
- Inventory slot briefly highlights (item added)
- If inventory full: Red "X" appears, item stays on ground

Audio Feedback:
- Collection chime: Pleasant "ding" or "pop" sound
- Different pitch per material type (wood lower, ore higher)
- If inventory full: Error "bonk" sound

Text Feedback:
- Quantity notification appears briefly:
  - "+5 Oak Logs" (material name + quantity)
  - Position: Above player character or bottom-center screen
  - Duration: 2 seconds, fades out
  - Stacks if collecting multiple materials quickly
```

**Critical Hit System (Luck-Based):**
```
Trigger Chance:
- Base: 5% chance per hit
- LCK Bonus: +2% per LCK point
- Example: 15 LCK = 5% + 30% = 35% crit chance

Critical Effect:
- Damage: 2x normal damage (before multipliers)
- Visual: Enhanced particle burst, screen shake
- Audio: Deeper/louder impact sound
- Text: "CRIT!" popup with yellow damage number

Design Purpose:
- Adds excitement to repetitive clicking
- Rewards LCK builds (high crit chance)
- Occasional fast node depletion (satisfying surprise)
- Makes gathering feel less monotonous
```

### Interaction Range & Position System

**Position Architecture (3D-Ready):**
```javascript
Position Object Structure:
{
  x: float  // World X coordinate (continuous, sub-unit precision)
  y: float  // World Y coordinate (continuous)
  z: float  // World Z coordinate (currently 0 for 2D, ready for 3D)
}

Distance Calculation (3D formula, works in 2D when z=0):
distance(pos1, pos2) = √[(x₁-x₂)² + (y₁-y₂)² + (z₁-z₂)²]

Current 2D Usage:
distance(pos1, pos2) = √[(x₁-x₂)² + (y₁-y₂)²]
(z components ignored since z=0 for both)
```

**Interaction System:**
```
Player Position: Continuous float coordinates
- Example: Player at (47.3, 52.8, 0)
- Moves smoothly between units
- WASD controls update position in small increments (0.1 units per frame)

Resource Node Position: Snap-to-grid integer coordinates
- Example: Tree at (48, 53, 0)
- Always positioned on whole number coordinates
- Makes pathfinding and collision simpler

Interaction Range Check:
IF distance(player_pos, node_pos) <= 3.0 THEN
  node is interactable (highlight, can click)
ELSE
  node not interactable (grayed out, cannot click)

Visual Feedback:
- Nodes within range: Full color, outline glow on hover
- Nodes out of range: Slightly dimmed, no interaction possible
- Range indicator: Optional circle around player (3 unit radius, toggle in settings)
```

**Snap-to-Grid for Collision:**
```
Movement Collision Detection:
1. Player tries to move from (47.3, 52.8) to (47.4, 52.8)
2. System checks "snap position": floor(47.4, 52.8) = (47, 52)
3. Check if tile (47, 52) is solid/occupied
4. If clear: Allow movement to (47.4, 52.8)
5. If blocked: Prevent movement, player stays at (47.3, 52.8)

Design Rationale:
- Continuous float positions = smooth movement
- Snap-to-grid collision = simple, predictable physics
- Resources on grid = easy pathfinding
- Ready for 3D (just add z-axis checks)
```

**Visual Range Indicator:**
```
Optional UI Element (can be toggled):
- Circle drawn around player (3 unit radius)
- Shows exact interaction range
- Helps new players understand mechanics
- Can be disabled in settings for cleaner visuals
```

### Tool Durability Consumption

**Simple 1:1 System:**
```
Each resource hit = 1 durability consumed

Example:
T2 Tree (200 HP) with T2 Axe (20 damage):
- Requires 10 hits to deplete
- Consumes 10 durability

Result: Predictable, easy to understand
```

**Durability Ranges by Tier:**
```
T1 Tools: 500 durability
- Can harvest ~50 same-tier resources
- Breaking should be rare for new players

T2 Tools: 1,000 durability  
- Can harvest ~50 same-tier resources
- Higher tier = more durable

T3 Tools: 2,000 durability
- Can harvest ~50 same-tier resources
- Very durable, long-lasting

T4 Tools: 4,000 durability
- Can harvest ~50 same-tier resources
- Extremely rare to break
```

**Wrong Tool Penalty:**
```
Using pickaxe in combat = 2x durability drain
Using sword to mine = 5x durability drain (or impossible)

Design: Encourages using right tool for job
```

**0% Durability Behavior:**
```
Tool never breaks completely
At 0% durability: Functions at 50% effectiveness
- T2 Axe at 0%: 10 damage instead of 20 damage
- Still usable, just slower
- Can repair at any time

Philosophy: No punishment for running out, just inefficiency
```

**Repair System:**
```
Where: Workstations only (appropriate discipline)
Cost: 20% of original crafting materials
Preserves: All mini-game bonuses and attributes
Time: Instant (no mini-game for repairs)

Example:
T2 Iron Pickaxe repair from 0% to 100%:
- Original cost: 5 Iron Ingots, 2 Oak Planks
- Repair cost: 1 Iron Ingot, 1 Oak Plank (20%)
- Keeps: +15% mining speed from mini-game craft
```

---

## Resource Nodes

### Node Definition Structure

**Key Specifications:**
- **Qualitative Descriptors:** Use words not numbers
  - Yields: "few", "several", "many", "abundant", "plentiful"
  - Respawn: "quick", "normal", "slow", "very_slow", null
  - Chance: "guaranteed", "high", "moderate", "low", "rare", "improbable"
- **Hardcoded Lookup:** Numbers determined by hardcoded tables based on qualitative descriptors
- **Size Variation:** resourceId defines base type, size (small/normal/large/huge) rolled at spawn time
- **LLM Materials:** Only hand-crafted materials get resource nodes; LLM materials obtained through crafting/drops/quests

### Example Resource Node

**Oak Tree Node:**
```json
{
  "metadata": {
    "narrative": "Ancient oak standing patient as centuries pass. Dense, reliable wood - the foundation of countless structures.",
    "tags": ["tree", "wood", "common"]
  },
  
  "resourceId": "oak_tree",
  "name": "Oak Tree",
  "category": "tree",
  "tier": 1,
  
  "visual": {
    "baseSprite": "oak_tree_base",
    "sizeVariants": ["small", "normal", "large", "huge"]
  },
  
  "harvesting": {
    "toolRequired": "axe",
    "harvestTime": "normal",
    "respawnTime": "normal",
    "respawnConditions": []
  },
  
  "sizeVariation": {
    "possible": ["small", "normal", "large", "huge"],
    "distribution": "normal"
  },
  
  "yields": {
    "materialId": "oak_log",
    "baseYield": "several",
    "scalesWithSize": true
  },
  
  "bonusDrops": [],
  
  "interaction": {
    "destructible": true,
    "leavesRemnant": true,
    "remnantSprite": "tree_stump"
  }
}
```

---

# PART III: CRAFTING SYSTEMS

## Crafting Overview ✅ IMPLEMENTED

**Implementation Status:** All 5 disciplines working with minigames

**Code References:**
- `Crafting-subdisciplines/smithing.py` (622 lines)
- `Crafting-subdisciplines/refining.py` (669 lines)
- `Crafting-subdisciplines/alchemy.py` (695 lines)
- `Crafting-subdisciplines/engineering.py` (890 lines)
- `Crafting-subdisciplines/enchanting.py` (1,265 lines)
- **Total:** 9,159 lines of crafting code

### General Overview

1. **Core Concept:** ✅ Material-driven mini-games where recipe complexity and material value determines challenge difficulty and potential rewards. Specializations emerge from material usage patterns (e.g., using many fire materials adds fire modifiers to mini-games, enabling fire-focused sub-specializations).

2. **LLM Role:** Generates new recipes and materials for ANY TIER as long as recipe is unknown to player. T4 is maximum tier (9x9 grid limit), but quality continues through rarity system. Players receive message when discovering LLM-generated recipes ("You've discovered something new!"). NO messages for mini-game quality bonuses on standard recipes. 
   - **Standardization**: Most players at most levels experience standardized content (guided-play recipes)
   - **Custom Content**: Only at highest end (T4 + high rarity + complex specializations) does LLM create truly personalized items/recipes for individual player profiles
   - **Tier vs Quality**: Tier = complexity/grid size. Rarity = quality within tier. Both matter for endgame.

3. **Guided-Play Foundation:** 
   - **Style**: BOTW/Minecraft approach - hints and info bubbles, but complete freedom
   - **Initial Quest**: Direct player to first city/NPC (NPCs as placeholders for cities)
   - **Gating**: First 3 cities/NPCs have soft gates, then gradually opens to full freedom
   - **Tutorial Vibe**: Easy start with core mechanics, but no forced tutorial sequences
   - **Content Volume**: Large handcrafted dataset acts as "training data" for LLM
     - Every material used in minimum 1 recipe, most in 2+ recipes
     - Lower tier materials appear in progressively more recipes
     - Establishes baseline material interactions and trends

4. **Sub-Specialization Mechanics:** Modifications to base mini-game based on material patterns. Example: Base game = click green squares in time limit. Earth specialization = larger click zones. Fire specialization = shorter time limit. Water specialization = irregular shapes. *Note: These are placeholder concepts, actual mechanics TBD.*

5. **Crafting Time & Instant Craft Option:** 
   - Simpler recipes = faster mini-games
   - ALL items can be instantly crafted with recipe + materials (base stats only)
   - Mini-games add +X bonus stats/attributes to base item
   - Higher tier items have higher potential +X bonuses
   - Both base stats and +X bonuses are procedurally generated

6. **Item Metadata Display:**
   - **Prominent Info (Non-Greyed)**: Stats, attributes, effects, narrative description
   - **Technical Info (Greyed Out)**: Material quality details
     - Example: "Blade forged from Legendary Steel (T2) with Common Oak Handle (T1)"
     - Shows tier mixing and rarity mixing in recipe
   - **Always Visible**: Metadata permanently displayed on item inspection

7. **Durability & Maintenance System:**
   - **100% → 50% Durability**: Item functions at full stats
   - **50% → 0% Durability**: Item stats gradually decline to 75% effectiveness
   - **0% Durability**: Item functions infinitely at 50% effectiveness (never breaks completely)
   - **Wrong Tool Usage**: Drains durability faster
     - Mining Pickaxe used in combat = faster durability loss
     - Battle Sword used for mining = major durability drain
   - **Tool Affinities**: 
     - Correct use = normal durability drain
     - Minor wrong use (T3 Pickaxe as weapon) = increased drain
     - Major wrong use (Sword for mining) = severe drain or impossible
   - **Maintenance**: Repair items to restore durability (separate system TBD)

8. **Failure States & Attempts:**
   - Failure loses some resources (scales with recipe tier/complexity)
   - Multiple attempts allowed (3 attempts?)
   - All attempts have same reward calculation
   - **First-Try Bonus:** Chance-based unique attribute class, only available on first attempt (not guaranteed, adds incentive)

9. **Recipe Discovery & Unlocking:**
   - Guided-play recipes: Given through hints, NPC dialogue, or recipe book
   - Post-guided-play recipes: Experimentation required for non-standard recipes
   - LLM recipes: Discovered through trying unknown material combinations
   - Once unlocked, can be base-crafted (no +X) or mini-game crafted (+X bonuses)
   - Set attributes may exist on items regardless, but mini-games can boost them

### Material Economy & Cross-Discipline Overlap

#### **Venn Diagram Philosophy**

All five crafting disciplines (Smithing, Forging, Alchemy, Engineering, Enchanting) share a unified material economy with intentional overlap:

```
Material Overlap Tiers:

CORE MATERIALS (Center of Venn Diagram - ALL 5 disciplines):
- Basic Metals: Iron Ore, Copper Ore, Tin
- Basic Wood: Oak, Pine, Ash
- Basic Binding: Plant Fiber, Leather Strips, Sinew
- Basic Stone: Limestone, Granite
- Used in every crafting discipline in some form

COMMON MATERIALS (Overlap 3-4 disciplines):
- Elemental Crystals: Fire, Water, Earth, Air, Lightning, Ice
- Processed Metals: Iron Ingots, Steel, Bronze Alloys
- Quality Wood: Birch, Maple, Ironwood
- Refined Materials: Treated Leather, Polished Stone, Crystal Dust
- Used in most crafting, different applications per discipline

MID-TIER MATERIALS (Overlap 2-3 disciplines):
- Special Alloys: Mithril, Adamantine, Orichalcum
- Rare Crystals: Dragon Scales, Phoenix Feathers, Void Essence
- Advanced Components: Gears, Mechanisms, Power Cores
- Exotic Wood: Ebony, Ancient Wood, Petrified Wood
- Used in specific combinations, niche applications

SPECIALTY MATERIALS (Unique to 1 discipline - Outer edges):
- Discipline-specific reagents and components
- Extremely rare, unique crafting applications
- Examples TBD during guided-play design
- Minimal unique materials - most overlap
```

#### **Cross-Discipline Material Examples**

**Iron (Core Material - Used Everywhere):**
- **Smithing**: Weapon blades, armor plates, tool heads
- **Forging**: Refined into steel, alloyed with other metals, elemental infusion
- **Alchemy**: Iron filings as catalyst, iron-based strength potions
- **Engineering**: Turret frames, bomb casings, structural components
- **Enchanting**: Metal base for enchantments, iron accessories

**Fire Crystal (Common Material - 4-5 Disciplines):**
- **Smithing**: (via Forging) Fire-infused weapons directly
- **Forging**: Create Fire Steel, Fire Copper, elemental metals
- **Alchemy**: Fire damage potions, fire resistance elixirs, heat-based recipes
- **Engineering**: Incendiary bombs, flame turrets, thermal devices
- **Enchanting**: Fire enchantments, burning effects, heat patterns

**Wood (Core Material - Used Everywhere):**
- **Smithing**: Weapon handles, shield frames, bow construction
- **Forging**: Fuel source, refined into charcoal, treated wood materials
- **Alchemy**: Fuel for brewing, container material, wood-based reagents
- **Engineering**: Device casings, structural frames, insulation
- **Enchanting**: Wooden charms, staffs, natural-element accessories

**Dragon Scale (Mid-Tier Material - 2-3 Disciplines):**
- **Smithing**: Premium armor plating, legendary weapon components
- **Forging**: Legendary alloy creation, extreme refinement catalyst
- **Alchemy**: Power potions, transmutation elixirs, high-tier recipes
- **Enchanting**: Dragon-aspect enchantments, high-power patterns
- **Engineering**: Might not use (or very specific applications)

**Gears (Mid-Tier Material - 2-3 Disciplines):**
- **Smithing**: Complex weapon mechanisms, advanced tool construction
- **Engineering**: Turret mechanisms, bomb triggers, device internals
- **Enchanting**: Clockwork accessories, mechanical-themed enchantments
- **Forging/Alchemy**: Generally not used

#### **Design Benefits**

1. **Unified Economy**: All crafters hunt for same core materials
2. **Market Interdependence**: Excess iron useful for multiple disciplines
3. **Flexible Specialization**: Can switch disciplines without wasted materials
4. **Shared Progression**: Advancing in one discipline helps others
5. **Discovery Rewards**: Finding rare materials benefits multiple playstyles
6. **Reduced Complexity**: Players don't need to track 5 separate material pools
7. **Natural Trading**: Players have valuable materials for disciplines they don't use

#### **Specialty Material Philosophy**

- Only 5-10% of materials are discipline-unique
- Unique materials are high-tier or extremely specific
- Core progression uses shared materials
- Specialization comes from recipes and techniques, not exclusive materials
- Example unique materials TBD during guided-play design

---

## Smithing ✅ IMPLEMENTED

**Implementation Status:** ✅ Complete with mini-game
**Source Files:**
- `Crafting-subdisciplines/smithing.py` (622 lines)
- `recipes.JSON/recipes-smithing-3.JSON` (30KB)
- `placements.JSON/placements-smithing-1.JSON`

### Base Mechanic
Temperature management + hammering/forging

### Workbench Tier System

- **T1 Forge (3x3 grid)**: Basic weapons, simple recipes
- **T2 Forge (5x5 grid)**: Intermediate weapons, unlocks larger weapon types (longswords, battleaxes)
- **T3 Forge (7x7 grid)**: Advanced weapons, unlocks heavy weapons (greatswords, warhammers)
- **T4 Forge (9x9 grid)**: Master weapons, unlocks exotic weapons (halberds, special items)
- **Backward Compatibility**: Higher tier benches can craft ALL lower tier recipes
- **Recipe Size = Power**: Larger recipes (more materials) produce better items, even with same-tier materials

### Triple Gating System

- **Workbench Gate**: Weapon types locked by bench tier (greatsword needs T2+ bench)
- **Recipe Complexity**: Recipe grid size determines item power/quality potential
- **Material Tier**: Material quality affects base stats
- **Example**: Copper greatsword (T1 materials) in 5x5 recipe (T2 bench) = powerful T1 weapon

### Tool vs Weapon System

- **Separate Tools with Affinities**: Mining Pickaxe, Forestry Axe, etc. are distinct from weapons
- **Cross-Purpose Usage**: Tools can fight, weapons can gather (with penalties)
- **Affinity Examples**:
  - T3 Mining Pickaxe = T2 Weapon equivalent damage (but worse than actual T2 weapon)
  - Using pickaxe in combat = faster durability drain
  - Using sword to mine = severe durability drain or impossible
- **Dual Purpose Balance**: Highest tier tools comparable to mid-tier weapons (not equal-tier)

### Elemental Integration

- **Material-Determined**: Fire Crystals in recipe automatically create Fire Sword
- **Quantity Scaling**: 
  - 1 Fire Crystal = minor fire damage bonus
  - 3+ Fire Crystals = moderate fire specialization
  - 5+ Fire Crystals = major fire specialization with unique attributes
- **No Separate Elemental Recipes**: Elements emerge from material choices

### Mini-Game Structure

- **Temperature:** Keyboard controls (WASD/arrows)
- **Hammering/Forging:** Mouse controls (clicking)
- **Difficulty Scaling:**
  - T1: Simple timing with spacebar + click
  - T2: WASD temperature zones + clicking different forge spots
  - T3-T4: OSU-style complexity with rhythm, precision, multi-tasking
- Combines click timing with spatial awareness

### Progression Formula
Based on workbench tier + recipe size + material tier + rarity. Target: Max complexity T1 recipe ≈ Simple T3 recipe (excluding special abilities)

### Time Requirements
15-120 seconds depending on tier and complexity (exact timing TBD through playtesting)

---

## Forging Refining ✅ IMPLEMENTED

**Implementation Status:** ✅ Complete with hub-spoke system
**Source Files:**
- `Crafting-subdisciplines/refining.py` (669 lines)
- `recipes.JSON/recipes-refining-1.JSON` (24KB)
- `placements.JSON/placements-refining-1.JSON`

**Core Purpose:** Primary source for elemental materials, alloy creation, and material quality enhancement. Enables "anything + anything" combinations for infinite experimentation.

### Base Mechanic
Lockpicking-style timing game - "unlocking" the potential of materials through cylinder alignment

### Workbench Tier System (Hub and Spoke)

- **T1 Refinery**: 1 Core Slot + 2 Surrounding Slots
- **T2 Refinery**: 1 Core Slot + 4 Surrounding Slots
- **T3 Refinery**: 2 Core Slots + 5 Surrounding Slots
- **T4 Refinery**: 3 Core Slots + 6 Surrounding Slots
- **All Slots Stackable**: Up to 256 items per slot
- **Fuel Slot**: Separate optional slot for minigame buffs only

### Slot Rules & Core Mechanics

- **Core Slots**: Determine output type and quantity (stackable to 256)
- **Surrounding Slots**: All identical, position doesn't matter (stackable to 256)
- **Multi-Core Rule**: All core slots MUST have equal quantities
  - Valid: Core 1 = 32, Core 2 = 32 → Output = 32
  - Invalid: Core 1 = 32, Core 2 = 16 → Recipe won't process
- **Core Quantity = Output Quantity**: Amount in core determines output amount
  - Example: 64 Iron Ore in core → 64 Iron Ingot output
  - Exception: Rarity upgrades use ratio (64 → 16 for 4:1 ratio)

### Material Refinement Types

**Type A: Required Refinement (Vertical - Enables Use)**
- Raw ore cannot be used in crafting, must refine to ingot
- Example: Copper Ore → Copper Ingot (1:1 ratio, instant without minigame)

**Type B: Optional Quality Refinement (Vertical - Better Stats)**
- Can use raw material, but refined is significantly better
- Example: Raw Wood vs Treated Wood (both usable, treated has +durability)

**Type C: Horizontal Refinement (Different, Not Better)**
- Refinement changes properties, not power level
- Example: Raw Ruby (high power, unstable) vs Refined Ruby (moderate power, stable)
- Example: Soft Leather (mobility) vs Hardened Leather (defense)
- Use case dependent: Neither is objectively better

**Type D: Rarity Refinement (Vertical - Exponential Cost)**
- Single-ingredient rarity upgrades with exponential material loss
- Placeholder Ratio: 4:1 per rarity tier (subject to guided-play balance)
- Example Path: 1024 Iron Ingot → 256 Uncommon → 64 Rare → 16 Epic → 4 Mythic → 1 Legendary
- Capped at Legendary for single-ingredient refinement
- Total cost example: 4,096 Iron Ore for 1 Legendary Iron Ingot

**Type E: Multi-Material Fusion (Combination Effects)**
- Can change item type + rarity + attributes + tier simultaneously
- Better ratios than single-ingredient (encourages complexity)
- Example: 16 Rare Iron + 16 Rare Steel + 8 Fire Crystal → 16 Epic Fire Steel
- "Anything + Anything" possible: metals, woods, gems, leather, etc.

### Elemental Material Creation (Primary Purpose)

- **Elemental Metals**: Fire Steel, Ice Copper, Lightning Iron, etc.
- **Elemental Woods**: Crystal Maple, Flame Oak, Frost Birch, etc.
- **Elemental Everything**: Any base material + elemental additive = elemental variant
- Created through multi-material recipes with elemental crystals/cores
- Example Recipe:
  ```
  Core: 32 Steel Ingot
  Slot 1: 16 Fire Crystal
  Slot 2: 4 Stabilizer
  Result: 32 Fire Steel Ingot (+fire damage, +heat resistance)
  ```

### Alloy Creation

- Requires T3+ Refinery (multi-core slots)
- Equal parts rule: All cores must have same quantity
- Example: Core 1 = 16 Copper, Core 2 = 16 Tin → 16 Bronze
- Different ratios create different alloys:
  - 50/50 Copper/Tin = Balanced Bronze
  - 70/30 via slots = Copper-Heavy Bronze (different stats)
- Complex Alloys (T4):
  ```
  Core 1: 8 Steel
  Core 2: 8 Mithril
  Core 3: 8 Adamantine
  Slot 1: 4 Fire Core
  Slot 2: 4 Dragon Scale
  Result: 8 Prismatic Alloy (legendary triple-metal fusion)
  ```

### Fuel System (Minigame Only)

- **Base Processing**: Instant, no fuel required, guaranteed output (no minigame)
- **Fuel Purpose**: Optional buffs for minigame attempts only
- **Fuel Types & Effects**:
  - Coal (T1): +10% timing window
  - Refined Coal (T2): +20% window, +1 allowed failure
  - Magma Core (T3): +30% window, +2 failures, +10% fire recipe success
  - Void Crystal (T4): +50% window, +3 failures, +15% all recipe success
  - Elemental Fuels: Matching element bonuses (Frost = slower rotation, etc.)
- Fuel consumed per minigame attempt, not per batch

### Mini-Game Structure (All-or-Nothing)

**Success/Failure Only (No Gradient):**
- Success: Full designed output + rarity upgrade (if applicable) + attributes
- Failure: 50% material loss (configurable), no output, must retry
- No partial success or reduced quality output

**Difficulty Variables:**
- **Time Allowed**: 10-60 seconds based on recipe complexity
- **Cylinder Count**: 2-15+ alignments required
- **Timing Window**: 0.1-1.0 seconds per cylinder
- **Allowed Failures**: 0-3 missed timings before total failure
- **Additional Modifiers**:
  - Rotation speed variations
  - Direction changes mid-game
  - Multiple speeds simultaneously
  - Visual effects/obscuration
  - Shrinking windows over time

**Example Difficulty Tiers:**
- Easy (T1 basic): 45s, 3 cylinders, 0.8s window, 2 failures allowed
- Medium (T2 elemental): 30s, 6 cylinders, 0.5s window, 1 failure allowed
- Hard (T3 rarity): 20s, 10 cylinders, 0.3s window, 0 failures (perfect required)
- Extreme (T4 fusion): 15s, 15 cylinders, 0.2s window, 0 failures, multi-speed

### Processing Time

- **Base Crafting (No Minigame)**: Instant, guaranteed success
- **Minigame Crafting**: Varies by difficulty (10-60 seconds of active play)
- No passive waiting time, all processing is immediate

### Important Disclaimers

- All numerical ratios (4:1 rarity, material quantities, fuel bonuses) are PLACEHOLDERS
- Guided-play recipes will define actual values during balance testing
- System structure is final, numbers are flexible
- Recipe complexity and requirements defined per-recipe basis

---

## Alchemy ✅ IMPLEMENTED

**Implementation Status:** ✅ Complete with gradient success system
**Source Files:**
- `Crafting-subdisciplines/alchemy.py` (695 lines)
- `recipes.JSON/recipes-alchemy-1.JSON` (12KB)
- `placements.JSON/placements-alchemy-1.JSON`

**Core Purpose:** Universal consumable creation system. No distinction between "potions" and "food" - all are consumables with buffs/effects. Same mechanics, different aesthetic (cauldron for potions, pot for food).

### Base Mechanic
Reaction chain management - reading visual cues to identify optimal timing for ingredient additions

### Station Tier System

- **T1 Alchemy Station**: 3 Ingredient Slots
- **T2 Alchemy Station**: 5 Ingredient Slots
- **T3 Alchemy Station**: 7 Ingredient Slots
- **T4 Alchemy Station**: 9 Ingredient Slots
- **All Slots Identical**: No categorization (base/modifier/catalyst), just numbered ingredient slots
- **Order Matters**: When ingredients are added affects outcome
- **Simultaneous Addition**: Multiple ingredients can be added together at same moment
- **All Slots Stackable**: Up to 256 items per slot

### Rarity & Tier System

**Tier = Efficacy (Power & Duration)**
- Higher tier = stronger effect numbers and longer durations
- Example: T1 Fire Resist = -50% for 2:00, T4 = -95% for 4:00
- Tier determined by recipe and materials used

**Rarity = Effect Complexity (Types & Combinations)**
- Common: Single effect
- Uncommon: Two complementary effects
- Rare: Multiple effects with synergies
- Epic: Complex effects with conditional bonuses
- Mythic: Advanced conditional effects and powerful combos
- Legendary: Ultimate effect combinations with dual-state bonuses
- Higher rarity = more effects, better synergies, conditional bonuses

**Output Rarity Rule**: Capped at highest ingredient rarity used
- Rare ingredients max → Rare output max
- Legendary ingredients → Legendary output possible
- Cannot skip rarity tiers through skill alone

### Gradient Success System (NOT All-or-Nothing)

**Progress-Based Quality:**
```
0-25%: Complete Failure (no output, 50% materials lost)
25-50%: Weak Success (50% duration, 50% effect strength)
50-75%: Standard Success (75% duration, 75% effect strength)
75-90%: Quality Success (100% duration, 100% effect strength)
90-99%: Superior Success (120% duration, 110% effect strength)
100%: Perfect Success (150% duration, 125% effect strength)
```

**For Instant Effects (Healing):**
- Progress directly scales effect magnitude
- 50% progress = 50% healing, 100% = full healing, Perfect = 150% healing

**Handcrafting Bonus (Unique to Alchemy):**
- Unlike other crafting (which gives +stats/attributes), Alchemy handcrafting can boost TIER
- Perfect execution: Output can be effectively T2.5 instead of T2 (stronger numbers)
- Poor execution: Gradient decline in tier effectiveness
- Base crafting (no minigame): Always produces T-level output, no bonus possible

### Effect Stacking Rules

- **Different Effects**: Stack fully, timers independent
- **Same Effect, Different Tiers**: Stack (T1 Fire Resist + T2 Fire Resist = both active)
- **Same Effect, Same Tier**: Don't stack - longest remaining timer overwrites
- Example: Can have Fire Resist + Fire Damage + Healing all active simultaneously

### Reaction Chain Minigame

**Core Loop:**
1. Load ingredients into slots (pre-minigame)
2. Start brewing (timer begins)
3. Add first ingredient → reaction begins
4. Watch reaction grow through stages
5. Either CHAIN (add next ingredient) or STABILIZE (end process)
6. Chaining: Locks current reaction, starts new reaction with next ingredient
7. Stabilizing: Locks current reaction, completes recipe
8. Total progress = sum of all locked reaction qualities

**Reaction Growth Stages (Every Ingredient):**

**Stage 1: Initiation (Early)**
- Visual: Small bubble, dim glow, gentle
- Progress: 5% (very weak)
- Player trap: "It's starting, should I add next one?"
- Reality: TOO EARLY

**Stage 2: Building (False Peaks)**
- Visual: Growing bubble, brightening, pulsing begins
- Progress: 15-20% (improving but not optimal)
- Contains FALSE PEAKS that look promising but aren't sweet spot
- Player trap: "It's glowing! This looks good!"
- Reality: STILL TOO EARLY - looks good but hasn't peaked
- Beginners add next ingredient here

**Stage 3: SWEET SPOT (Optimal)**
- Visual: Optimal size, steady intense glow, rhythmic pulse, saturated color
- Audio: Strong resonant bubbling tone
- Progress: 30-35% (OPTIMAL)
- Distinct from Stage 2: sustained vs spiking, harmonic audio, stable size
- Reality: TARGET WINDOW - experienced players recognize this

**Stage 4: Degrading (Late)**
- Visual: Irregular expansion, flickering glow, darkening edges
- Audio: Popping, erratic bubbling
- Progress: 20-25% (declining)
- Reality: LATE but still viable

**Stage 5: Critical Failure (Explosion Risk)**
- Visual: Over-expansion, dark/smoky, violent shaking, red warnings
- Audio: Loud popping, hissing
- Progress: 5-10% (very weak) OR total failure if left too long
- Reality: CRITICAL - explosion imminent
- Waiting longer = explosion = recipe fails, 75% materials lost

### Ingredient Type Behaviors

**Stable Ingredients (Easy):**
- Slow predictable growth
- Smooth transitions, no false peaks
- Sweet spot: 2+ second window
- Easy to read, forgiving
- Example: Healing Herbs, Pure Water, Vegetables

**Moderate Ingredients (Medium):**
- Medium speed, some irregularity
- Occasional pulse variations (distractors)
- Sweet spot: 1.5 second window
- Some false indicators during Stage 2
- Example: Fire Flowers, Mineral Salts, Quality Meats

**Volatile Ingredients (Hard):**
- Fast erratic growth
- Multiple false glows during Stage 2
- Sweet spot: 1 second window
- Must distinguish real peak from fakes
- Example: Dragon Blood, Lightning Cores, Explosive Mushrooms

**Legendary Ingredients (Extreme):**
- Very fast, complex layered reactions
- Many false peaks, color shifts, cascading effects
- Sweet spot: 0.5-0.8 second window
- Requires extensive experience
- Example: Phoenix Ash, Void Essence, Eternity Bloom

### Advanced Mechanics

**Cascading Reactions (CRITICAL for T3-T4):**
- Previous ingredient's reaction quality affects next ingredient's timing
- Example: Fire ingredient added optimally → Water ingredient sweet spot shifts earlier
- Fire added late → Water sweet spot shifts later
- Creates dynamic gameplay - can't just memorize fixed timings
- Must adapt based on actual performance

**Ingredient Total Timers (Narrative Cooking Logic):**
- Some ingredients need longer total cooking time (hardy/base ingredients)
- Other ingredients are "finishing" ingredients (added near end)
- Hardy ingredients: Added first, can cook through multiple other reactions
- Finishing ingredients: Added last, short cooking time before stabilizing
- Example: Meat base cooks for 30s, herbs added at 25s as finisher

**Simultaneous Addition:**
- Can press multiple number keys at once to add multiple ingredients
- Useful for ingredients that should be combined
- Example: Press 2+3 together to add both Cooling Mint and Crystal Dust
- Creates combined reaction with blended properties
- Advanced technique for complex recipes

### Difficulty Scaling

**T1 Recipes:**
- 2-3 ingredients
- All stable or moderate
- No false peaks
- 2+ second sweet spot windows
- No cascading
- 60 second time limit

**T2 Recipes:**
- 3-5 ingredients
- Mix of stable and moderate
- 1-2 false peaks per ingredient
- 1.5 second sweet spot windows
- No cascading
- 45 second time limit

**T3 Recipes:**
- 5-7 ingredients
- Mix of moderate and volatile
- 2-3 false peaks per ingredient
- 1 second sweet spot windows
- Some cascading reactions
- 30 second time limit

**T4 Recipes:**
- 7-9 ingredients
- Volatile and legendary ingredients
- 4-5 false peaks per ingredient
- 0.5-0.8 second sweet spot windows
- Cascading reactions throughout
- Complex simultaneous additions required
- 20 second time limit

### Learning Curve (Experience-Based Pattern Recognition)

- Like learning when water truly boils vs just simmering
- Novice: Fooled by Stage 2 false peaks
- Intermediate: Recognizes Stage 3 sustained glow
- Expert: Feels the "harmonic convergence" at peak
- Audio cues become intuitive (resonant tone at sweet spot)
- Visual rhythm becomes internalized (steady pulse vs erratic)
- Each ingredient type has signature that becomes familiar

### Food vs Potions (Cosmetic Distinction)

- Same exact mechanics and minigame
- Different ingredient pools (food items vs alchemical reagents)
- Different aesthetic (cooking pot vs cauldron)
- Roughly equivalent power and duration
- Effects may slightly differ thematically but mechanically similar

### Important Disclaimers

- ALL numbers (timings, percentages, durations, effect strengths) are PLACEHOLDERS
- Example recipes are for demonstration only
- Guided-play will define actual values during balance testing
- Sweet spot windows, stage durations, progress contributions all subject to change
- System structure is final, numerical values are flexible

---

## Engineering ✅ IMPLEMENTED

**Implementation Status:** ✅ Complete with slot-type puzzle system
**Source Files:**
- `Crafting-subdisciplines/engineering.py` (890 lines)
- `recipes.JSON/recipes-engineering-1.JSON` (11KB)
- `placements.JSON/placements-engineering-1.JSON`

**Core Purpose:** Tactical device creation through cognitive puzzles. Devices can be placed outside claimed territory. Complexity in crafting, simplicity in deployment.

### Base Mechanic
Sequential cognitive puzzle solving - pure problem-solving, no timing, no dexterity

### Station Tier System (Drag-and-Drop Canvas)

**T1 Engineering Station:**
- 3 Slot Types available (FRAME, POWER, FUNCTION)
- 3 Canvas Slots (can place up to 3 slot types)
- Minimum viable devices only

**T2 Engineering Station:**
- 3 Slot Types available (FRAME, POWER, FUNCTION)
- 5 Canvas Slots (more complexity with same types)
- Can use multiple of same type (e.g., 2 POWER slots)

**T3 Engineering Station:**
- 5 Slot Types available (FRAME, POWER, FUNCTION, MODIFIER, UTILITY)
- 5 Canvas Slots (new types, same slot count)
- Advanced customization unlocked

**T4 Engineering Station:**
- 7 Slot Types available (full palette including special types)
- 7 Canvas Slots (maximum customization)
- Legendary device complexity

**UI Flow:**
1. Start with blank canvas
2. Drag slot types from palette onto canvas (up to tier limit)
3. Fill each placed slot with materials from inventory
4. System analyzes combination and determines device type
5. Begin assembly (puzzle sequence)

### Slot Type System (Modular Building Blocks)

**Available Slot Types:**

**FRAME Slot (All Tiers)**
- Purpose: Structural base
- Accepts: Casings, plates, frameworks, mounts
- Affects: Durability, size, weight
- Examples: Iron Casing, Crystal Framework, Wooden Frame

**POWER Slot (All Tiers)**
- Purpose: Energy source
- Accepts: Crystals, cores, fuel sources
- Affects: Output strength, duration, recharge rate
- Can use multiple: Dual/triple power sources create hybrid effects
- Examples: Fire Crystal, Mana Core, Battery Cell, Lightning Core

**FUNCTION Slot (All Tiers) - DEVICE TYPE DETERMINANT**
- Purpose: Defines what device is created
- Accepts: Weapons, explosives, utility items, magic items, tools
- Material attributes determine device category:
  - Explosive attribute → BOMB
  - Ranged weapon attribute → TURRET
  - Hidden/triggered attribute → TRAP
  - Utility attribute → SCANNER/COLLECTOR
  - Magic attribute → SPELL DEVICE
  - Defensive attribute → BARRIER
- **Most critical slot** - determines entire device category

**MODIFIER Slot (T3+)**
- Purpose: Add special effects and attributes
- Accepts: Enhancement items, elemental materials, special components
- Affects: Special attributes, conditional effects, bonus properties
- Can use multiple: Stack different effects
- Examples: Shrapnel (AoE), Timer (delay), Targeting (accuracy), Amplifier (power boost)

**UTILITY Slot (T3+)**
- Purpose: Secondary functions and automation
- Accepts: Tools, sensors, interfaces, automation components
- Affects: Usability, automation, detection, quality-of-life
- Examples: Auto-Reload, Targeting System, Concealment, Remote Trigger

**Special Slot Types (T4 Only - TBD):**
- Advanced slot types unlocked at highest tier
- Examples: DEFENSE, SPECIAL, AUGMENT (exact types TBD)

### Blank Canvas Assembly Process

**Step 1: Drag Slot Types**
- Start with empty canvas
- Drag desired slot types from palette onto canvas
- Can use same type multiple times (e.g., 2 POWER slots, 3 MODIFIER slots)
- Limited by station tier slot count (3, 5, 5, or 7 slots)
- Slot arrangement defines device structure

**Step 2: Fill Slots with Materials**
- Click each placed slot to add materials from inventory
- Each slot accepts specific material categories
- Materials stackable to 256 per slot
- System validates material compatibility with slot type

**Step 3: System Recognition**
- Once all slots filled, system analyzes combination
- FUNCTION slot material determines device category
- Other slots modify device stats and effects
- Shows preview: Known device OR "? Unknown Device ?"

**Step 4: Assembly/Experimentation**
- Known device: [Begin Assembly] → Puzzle sequence
- Unknown device: [Experiment] → Risk materials to discover
- Success: Device created, recipe learned (if new)
- Abandon: 50% materials returned, no device

### Device Type Determination (FUNCTION Slot)

**Material Attributes Define Device:**

**Explosive Attribute → BOMB**
```
[FRAME: Iron Casing]
[POWER: Fire Crystal]
[FUNCTION: Explosive Powder] ← Has "explosive" attribute
[MODIFIER: Shrapnel]
[MODIFIER: Timer]

Result: DELAYED FIRE BOMB (AoE)
```

**Ranged Weapon Attribute → TURRET**
```
[FRAME: Metal Mount]
[POWER: Lightning Crystal]
[FUNCTION: Crossbow] ← Has "ranged_weapon" attribute
[MODIFIER: Auto-Reload]
[UTILITY: Targeting Lens]

Result: LIGHTNING AUTO-TURRET
```

**Hidden/Triggered Attribute → TRAP**
```
[FRAME: Concealed Plate]
[POWER: Pressure Crystal]
[FUNCTION: Spike Ball] ← Has "hidden" + "triggered" attributes
[MODIFIER: Trip Wire]

Result: SPIKE TRAP (one-time use)
```

**Utility Attribute → SCANNER/COLLECTOR**
```
[FRAME: Lightweight Frame]
[POWER: Scanning Crystal]
[FUNCTION: Telescope] ← Has "utility" + "detection" attributes
[MODIFIER: Range Enhancer]

Result: RESOURCE SCANNER
```

**Magic Attribute → SPELL DEVICE**
```
[FRAME: Crystal Framework]
[POWER: Mana Core]
[FUNCTION: Fire Staff] ← Has "magic" + "fire" attributes
[MODIFIER: Amplifier]

Result: FIRE SPELL TURRET
```

### Material Rarity Impact

**Puzzle Count by Device Tier & Material Rarity:**
```
T1 Device (Common materials): 1-2 puzzles
T2 Device (Uncommon materials): 2-3 puzzles
T3 Device (Rare materials): 3-5 puzzles
T4 Device (Epic+ materials): 4-6 puzzles

Higher tier + higher rarity = more puzzles
```

**Sequential Solving:**
- Each puzzle affects different device stat
- Must solve all puzzles to complete device
- Solve in sequence: Puzzle 1 → Puzzle 2 → Puzzle 3 → etc.
- Each puzzle independently affects one aspect (accuracy, fire rate, durability, etc.)

**No Failure State:**
- Untimed - take as long as needed
- No material loss during puzzle solving
- Can attempt puzzle solution as many times as needed
- Optional: Move counter that resets puzzle if exceeded (soft limit, not failure)

**Only Ways to End Without Device:**
- ABANDON: Choose to give up, returns 50% materials, no device created
- Cannot solve puzzle: Eventually must abandon if stuck

### Multiple Puzzle Gauntlet System

**T1: Rotation Pipe Puzzles**
- Grid: 3x3 to 5x5
- Goal: Rotate pieces to connect input to output
- Pieces: Straight pipes, L-bends, T-junctions, crosses
- Constraint: All pieces must connect (no loose ends)
- Difficulty: Easy (3x3, obvious) → Hard (5x5, multiple paths, distractors)

**T2: Rotation + Sliding Tile Puzzles**
- Rotation: Same as T1 but harder (5x5, multiple inputs/outputs)
- Sliding Tiles: Classic sliding puzzle (3x3 or 4x4 grid with empty space)
- Goal: Arrange numbered tiles in order by sliding into empty space
- Difficulty: Easy (3x3, ~15 moves) → Hard (4x4, ~50+ moves)

**T3: Traffic Jam Puzzles**
- Grid: 6x6
- Pieces: Various sized blocks (1x2, 1x3, 2x2, 2x3)
- Goal: Slide target piece to exit by moving blocking pieces
- Pieces slide in direction of orientation only
- Difficulty: Medium (few pieces) → Very Hard (dense, 40+ moves, dead-ends)

**T4: Pattern Matching + Logic Grids**
- Pattern Matching: Complete partial patterns following rules (symmetry, no adjacent same, tiling)
- Logic Grids: Sudoku-style with engineering constraints (power flow, wiring, no loops)
- Grid: 5x5 to 9x9
- Multiple complex rules simultaneously
- Difficulty: Medium (simple rules, 5x5) → Extreme (many constraints, 9x9)

### Puzzle Completion (No Optimization System)

- Once puzzle solved, it's done - cannot retry for better result
- No "par" or optimal move count shown
- No stat bonus for efficient solutions
- Solve puzzle = that stat contribution locked in
- Device stats purely from material quality and slot configuration, NOT puzzle performance
- Puzzles are gateway/skill-check, not optimization minigame

### Save & Resume System

- Can save progress at any time during puzzle
- Click "Save & Exit" → puzzle state saved with current configuration
- Materials remain locked in station while saved
- Slot configuration and filled materials saved
- Can return later from exact same state
- No time penalty for saving/resuming
- Can have multiple devices in progress across different stations
- Example: T2 station with turret 40% done, T3 station with bomb 60% done

### Discovery System

- No blueprints - discovery through experimentation
- Try slot + material combinations
- System recognizes valid device patterns
- Unknown combinations show "? Unknown Device ?"
- Must experiment to discover new devices
- Successful discovery adds recipe to journal
- Recipe journal shows: Slot configuration + materials required
- Can recreate known devices easily after discovery

### Device Durability & Maintenance

**Turrets:**
- No ammo required
- Have durability/health bar
- Take damage when: Attacking (wear), being attacked (enemy damage)
- At 0 durability: Turret breaks, must be rebuilt
- Maintenance/Repair system: TBD (can repair in field or must return to station)
- Efficacy decreases as durability drops (like tools at 50%+ durability loss)

**Bombs:**
- Single-use consumable
- Explodes and consumed on use
- Casing can be recovered after explosion (material return)
- Example: Bomb uses 5 iron plates → After explosion, recover 2-3 iron plates

**Traps:**
- One-time use only
- Trigger once, then destroyed
- Must craft new trap to replace
- No material recovery

**Barriers/Walls:**
- Have durability/health
- Break when durability reaches 0
- Cannot repair (TBD - might allow repair later)

**Utility Devices:**
- Durability system TBD (might be permanent, might degrade)
- Balance decision: Should teleporters/collectors need maintenance?

### Deployment Limits

- Maximum 5 devices deployed simultaneously per player (static limit)
- Must destroy/remove existing device to place new one if at limit
- Applies across all device types (5 total, not 5 per type)
- Example: Can have 3 turrets + 2 traps, but not 3 turrets + 3 bombs
- Conservative limit for initial development, subject to balance changes

### Placement Freedom (UNIQUE TO ENGINEERING)

- Can place devices outside claimed territory
- Turrets/traps/bombs deployable anywhere accessible
- Creates tactical gameplay and forward positions
- Utility devices may still require claimed territory (TBD per device type)
- Tradeoff: Powerful but positional - once placed, devices are immobile

### Immobility & Tactical Positioning

- Devices cannot be picked up and moved after placement
- Must destroy and rebuild to relocate (lose durability investment)
- Encourages thoughtful placement
- Exception: Bombs are throwable/placeable before detonation

### Material Overlap (Critical Design Principle)

- Engineering shares MOST materials with other disciplines
- Only fringe/specialty materials are unique to engineering
- Material economy follows Venn diagram principle:
  - Core materials (iron, wood, fiber): Used in ALL 5 disciplines
  - Common materials (crystals, leather, stone): Used in 3-4 disciplines
  - Mid-tier materials (alloys, refined items): Used in 2-3 disciplines
  - Specialty materials (unique components): Used in 1 discipline only (rare)

### Important Disclaimers

- All device stats (damage, fire rate, durability) are PLACEHOLDERS
- Puzzle difficulty balance TBD through playtesting
- Device limits subject to change based on game balance
- Maintenance/repair systems may evolve during development
- Deployment restrictions per device type TBD

---

## Enchanting ✅ IMPLEMENTED

**Implementation Status:** ✅ Complete with freeform pattern system
**Source Files:**
- `Crafting-subdisciplines/enchanting.py` (1,265 lines)
- `recipes.JSON/recipes-adornments-1.JSON` (22KB)
- `placements.JSON/placements-adornments-1.JSON`

### Base Mechanic & Purpose

- Make existing items stronger (weapons, armor, tools, turrets, anything craftable)
- Can also craft new accessories (rings, amulets, charms) from scratch

### Mini-Game Structure: Freeform Pattern Creation

- **Phase 1 - Placement:** Place enhancement materials anywhere in circular workspace (complete creative freedom, no grid/guides)
- **Phase 2 - Connection:** Draw lines between materials to create pattern
- **Phase 3 - Recognition:** System recognizes what geometric pattern was created
- **Phase 4 - Judgment:** System judges quality/precision of pattern (angle accuracy, spacing, symmetry)

### Material Types

- **Key materials:** Few materials that provide main enhancement properties (gems, essences, cores)
- **Connector materials:** Majority of materials used to form the pattern structure
- More total materials at higher tiers, but key materials remain few

### Pattern Recognition

- System detects geometric shapes (triangles, squares, stars, circles, spirals, nested patterns, etc.)
- Pattern type determines bonus type (offensive, defensive, utility, elemental)
- Pattern complexity determines bonus magnitude
- Pattern quality (precision) determines bonus strength percentage

### Complexity Scaling

- **Scales by grid detail:** Higher tiers have finer placement precision required
- T1: 3-5 materials, simple shapes, forgiving quality judgment
- T2: 6-8 materials, intermediate patterns, moderate precision needed
- T3: 9-12 materials, complex nested patterns, high precision required
- T4: 13-20 materials, multi-layered intricate patterns, pixel-perfect placement

### Discovery Element

Players discover what patterns create what effects through experimentation and experience

### Failure States

- Low-Mid tier: Enchanting materials consumed, item remains intact
- High tier: Materials consumed + item being enchanted BREAKS (high risk/reward)

### Specialization Branches

TBD based on pattern types players gravitate toward

---

## Cross-Crafting Systems

### Crafting Stations

**Tiered Workbench System (Universal Across All Disciplines):**
- **T1 Station (3x3 grid)**: Basic recipes, simple items
- **T2 Station (5x5 grid)**: Intermediate recipes, unlocks new item categories
- **T3 Station (7x7 grid)**: Advanced recipes, unlocks complex item types
- **T4 Station (9x9 grid)**: Master recipes, unlocks exotic/legendary items
- **Backward Compatibility**: T2 bench can craft all T1 recipes, T3 can craft T1+T2, etc.
- **Grid-Only Interface**: Crafting grid is primary/only interface (no additional UI complexity)

**Recipe Size = Item Quality:**
- **Small Recipes (3x3)**: Basic items, simple materials
- **Medium Recipes (5x5)**: Improved items, more materials = better stats
- **Large Recipes (7x7)**: Powerful items, complex material combinations
- **Massive Recipes (9x9)**: Legendary items, maximum material investment
- **Key Principle**: Same materials in larger recipe = better result
  - Example: Copper sword in 3x3 = basic | Copper greatsword in 5x5 = much better
- **No Stacking**: Each grid slot holds exactly 1 material (no quantity stacking)

**Material Tier Flexibility:**
- **Can use lower tier materials in higher tier benches**
- T1 materials in 7x7 recipe = excellent T1 item (better than simple T2 item)
- T3 materials in 9x9 recipe = god-tier T3 item
- Allows material investment to create exceptional lower-tier gear
- **Tier Mixing Allowed**: Can mix T1 + T2 + T3 in same recipe (affects quality metadata)

**Weapon/Item Type Unlocking:**
- **T1 Bench**: Shortswords, daggers, hand axes, basic armor
- **T2 Bench**: Longswords, battleaxes, spears, medium armor, unlocks "heavy" variants
- **T3 Bench**: Greatswords, warhammers, pikes, heavy armor, unlocks "exotic" variants  
- **T4 Bench**: Halberds, dual weapons, special armors, legendary item types
- **Narrative Logic**: Bigger weapons need bigger workspaces

**Station Requirements:**
- Each discipline needs dedicated station
- Stations are prerequisites for crafting (can't smith without forge)
- Starter stations (T1) provided/cheap to craft

**Station Upgrades:**
- Stations upgradable through their own crafting type
- Example: Forge has upgrade slots → Craft "Forge Enhancement" using smithing
- Each upgrade tier unlocks: Next tier recipes, Better +X potential, New mini-game mechanics
- Upgrades use same mini-game as their discipline
- **T4 is Maximum**: No infinite grid expansion beyond 9x9

**Station Placement:**
- Must be placed in claimed territory
- Size requirements (some stations bigger than others)
- Aesthetic variations (reflect player's crafting style?)

### Material Consumption & Failure

**Base Crafting (No Mini-Game):**
- 100% material consumption
- No failure possible
- Produces base item with no +X bonuses

**Mini-Game Crafting:**
- **Success:** 100% material consumption, item created with +X
- **Partial Success:** 100% material consumption, item created with reduced/no +X
- **Failure:** Partial material return or total loss (scales with tier)

**Failure Scaling:**
- T1 Failure: Lose 30-50% of materials
- T2 Failure: Lose 50-70% of materials
- T3 Failure: Lose 70-90% of materials
- T4 Failure: Lose 90-100% of materials
- High stakes at high tiers encourages skill development

**Multi-Attempt System:**
- 3 attempts per recipe instance
- All attempts use same material pool
- First attempt: Chance for unique "First-Try Bonus" attributes
- Subsequent attempts: Standard reward calculation, no bonus chance
- After 3 failures: Must gather new materials to try again

### Quality Tiers & +X System

**Base Item Stats:**
- Every item has base stats determined by recipe and materials
- Base stats are procedurally generated (guided-play defines ranges)
- Example: T2 Iron Sword base = 15-20 damage

**+X Bonus System:**
- Mini-game performance determines +X value
- +X adds to base stats
- Example: Perfect craft = +5 damage → Total 20-25 damage
- Higher tier items have higher potential +X (T4 could get +15)

**Quality Naming:**
- Normal: Base stats, no +X (instant craft)
- Fine: Base stats +1 to +3
- Superior: Base stats +4 to +7
- Masterwork: Base stats +8 to +12
- Legendary: Base stats +13+, possible unique attributes

**Attribute Bonuses:**
- Beyond stat +X, can gain special attributes
- Attributes from materials used (fire materials → fire damage)
- First-Try Bonus attributes (unique, rare)
- LLM-generated attributes (post guided-play)

### Recipe Discovery & Experimentation

**Guided-Play Recipes:**
- Pre-designed, hand-crafted recipes
- Unlocked through tutorial/early quests
- Establish baseline for material interactions
- ~20-30 recipes per discipline to start

**Experimentation Discovery:**
- Select materials → Attempt craft → Mini-game
- Success = Recipe learned + item created
- Failure = No recipe, some materials lost
- Can try any combination (no restrictions)

**Recipe Hints:**
- Item descriptions hint at uses
- Material combinations show "potential" indicator
- NPCs might suggest combinations
- Lore/books contain recipe clues

**LLM Recipe Generation:**
- Post guided-play, LLM generates new valid recipes
- Based on player's material usage patterns
- Validation: Must be balanced, must make thematic sense
- Player discovers through experimentation (LLM doesn't tell them directly)

**Recipe Book/Journal:**
- Personal recipe journal per player
- Records all discovered recipes
- Can instant-craft from journal (base quality)
- Shows materials required, expected output
- Tags/categories for organization

---

# PART VI: TECHNICAL SYSTEMS (NEW in V6)

## Status Effects System ✅ IMPLEMENTED

**Code Reference:** `entities/status_effect.py` (827 lines)

### Damage Over Time (DoT) Effects

| Status | Damage Type | Stack Limit | Special |
|--------|-------------|-------------|---------|
| **Burn** | Fire | 3 | Standard fire DoT |
| **Bleed** | Physical | 5 | Physical piercing |
| **Poison** | Nature | ∞ | 1.2x power per stack |
| **Shock** | Lightning | - | Variable tick rate |

### Crowd Control (CC) Effects

| Status | Effect | Duration | Notes |
|--------|--------|----------|-------|
| **Freeze** | Complete stop | Short | Breaks on damage |
| **Slow** | -30% speed | Medium | Stores original speed |
| **Stun** | No actions | Short | Full incapacitation |
| **Root** | No movement | Medium | Can still attack |

### Buff Effects

| Status | Effect | Duration |
|--------|--------|----------|
| **Regeneration** | +HP/s | Medium |
| **Shield** | Absorb damage | Until depleted |
| **Haste** | +30% speed | Medium |
| **Empower** | +25% damage | Medium |
| **Fortify** | +20% defense | Medium |

### Debuff Effects

| Status | Effect |
|--------|--------|
| **Weaken** | -25% damage dealt |
| **Vulnerable** | +25% damage taken |

### Special Effects

| Status | Effect |
|--------|--------|
| **Phase** | Intangible, immune to damage |
| **Invisible** | Stealth mode |

---

## Save System ✅ IMPLEMENTED

**Code Reference:** `systems/save_manager.py`

### Saved Data Categories

| Category | Data Preserved |
|----------|----------------|
| **Character** | Position, facing direction, stats, level, EXP |
| **Resources** | Health/mana with proportional scaling on load |
| **Equipment** | All 10 slots, durability, enchantments |
| **Inventory** | Items, stack counts, equipment metadata |
| **Skills** | Known skills, skill levels, equipped hotbar slots |
| **Titles** | All earned titles |
| **Activities** | Activity counts for title tracking |
| **Class** | Selected class with all bonuses |
| **Quests** | Active quests, completed quests, progress |
| **World** | Placed entities, modified resources |

### Save Features
- ✅ Version tracking (v2.0)
- ✅ Timestamps
- ✅ Multiple save slots
- ✅ Full state restoration
- ✅ Graceful handling of missing/corrupt data

---

## Tag System ✅ IMPLEMENTED

**Implementation Status:** ✅ Complete tag-to-effects system
**Source File:** `Definitions.JSON/tag-definitions.JSON` (683 lines) - SINGLE SOURCE OF TRUTH
**Code References:**
- `core/effect_executor.py` - Tag-based effect execution
- `core/tag_parser.py` - Tag parsing and resolution

### All Tag Categories

From `tag-definitions.JSON`:

| Category | Tags | Purpose |
|----------|------|---------|
| **equipment** | `1H`, `2H`, `versatile` | Weapon handedness |
| **geometry** | `single_target`, `chain`, `cone`, `circle`, `beam`, `projectile`, `pierce`, `splash` | Area targeting |
| **damage_type** | `physical`, `slashing`, `piercing`, `crushing`, `fire`, `frost`, `lightning`, `poison`, `holy`, `shadow`, `arcane`, `chaos` | Damage classification |
| **status_debuff** | `burn`, `freeze`, `chill`, `slow`, `stun`, `root`, `bleed`, `poison_status`, `shock`, `weaken` | Negative effects |
| **status_buff** | `haste`, `quicken`, `empower`, `fortify`, `regeneration`, `shield`, `barrier`, `invisible` | Positive effects |
| **special** | `lifesteal`, `vampiric`, `reflect`, `thorns`, `knockback`, `pull`, `teleport`, `summon`, `dash`, `charge`, `phase`, `execute`, `critical` | Special mechanics |
| **trigger** | `on_hit`, `on_kill`, `on_damage`, `on_crit`, `on_contact`, `on_proximity`, `passive`, `active`, `instant` | Activation conditions |
| **context** | `self`, `ally`, `friendly`, `enemy`, `hostile`, `all`, `player`, `turret`, `device`, `construct`, `undead`, `mechanical` | Target filtering |
| **class** | `warrior`, `ranger`, `scholar`, `artisan`, `scavenger`, `adventurer` | Class identity |
| **playstyle** | `melee`, `ranged`, `magic`, `crafting`, `gathering`, `balanced`, `tanky`, `agile`, `caster` | Gameplay focus |
| **armor_type** | `heavy`, `medium`, `light`, `robes` | Armor classification |

### Geometry Tags with Parameters

| Tag | Description | Default Parameters |
|-----|-------------|-------------------|
| `chain` | Arcs to nearby targets | chain_count: 2, chain_range: 5.0, chain_falloff: 0.3 |
| `cone` | Frontal cone hit | cone_angle: 60, cone_range: 8.0 |
| `circle` | Radial AoE | radius: 3.0, origin: "target", max_targets: 0 |
| `beam` | Straight line hit | beam_range: 10.0, beam_width: 0.5, pierce_count: 0 |
| `projectile` | Traveling projectile | projectile_speed: 15.0, projectile_gravity: 0.0 |
| `pierce` | Penetrates targets | pierce_count: -1 (infinite), pierce_falloff: 0.1 |
| `splash` | Impact creates AoE | splash_radius: 2.0, splash_falloff: "linear" |

### Status Debuffs with Defaults

| Tag | Effect | Default Duration | Tick Rate | Stacking |
|-----|--------|------------------|-----------|----------|
| `burn` | Fire DoT (5 dmg/tick) | 5.0s | 1.0s | additive |
| `freeze` | Complete immobilization | 3.0s | - | none |
| `chill` | 50% move slow | 4.0s | - | multiplicative |
| `stun` | Cannot act or move | 2.0s | - | diminishing |
| `root` | Cannot move, can act | 3.0s | - | additive |
| `bleed` | Physical DoT (3 dmg/tick) | 6.0s | 1.0s | additive |
| `poison_status` | Poison DoT (4 dmg/tick) | 10.0s | 2.0s | additive |
| `shock` | Damage + interrupt (5 dmg) | 6.0s | 2.0s | additive |
| `weaken` | 25% stat reduction | 5.0s | - | additive |

### Status Buffs with Defaults

| Tag | Effect | Default Duration | Stacking |
|-----|--------|------------------|----------|
| `haste` | +50% move speed | 10.0s | additive |
| `empower` | +50% damage | 10.0s | multiplicative |
| `fortify` | +20 defense | 10.0s | additive |
| `regeneration` | +5 HP/tick | 10.0s | additive |
| `shield` | Absorbs 50 damage | 15.0s | none |
| `invisible` | Undetectable | 10.0s | none |

### Special Tags with Defaults

| Tag | Effect | Default Parameters |
|-----|--------|-------------------|
| `lifesteal` | Heal % of damage dealt | lifesteal_percent: 0.15 (15%) |
| `reflect` | Return damage to attacker | reflect_percent: 0.3 (30%) |
| `knockback` | Push target away | knockback_distance: 2.0 |
| `execute` | Bonus damage below HP threshold | threshold_hp: 0.2, bonus_damage: 2.0x |
| `critical` | Crit chance and multiplier | crit_chance: 0.15, crit_multiplier: 2.0x |

### Tag Conflicts

Mutually exclusive tag combinations:
- `burn` ↔ `freeze` (cannot burn and freeze simultaneously)
- `1H` ↔ `2H` ↔ `versatile` (weapon can only be one type)

### Tag Synergies

Certain tag combinations provide bonuses:
- `lightning` + `chain`: +20% chain range bonus
- `fire` + hit: 10% auto-apply chance for `burn`
- `frost` + hit: 15% auto-apply chance for `chill`
- `holy` + `undead` context: 1.5x damage multiplier
- `holy` + `ally` context: converts damage to healing

### Geometry Priority Resolution

When multiple geometry tags exist, higher priority wins:
1. `chain` (priority 5)
2. `cone` (priority 4)
3. `circle` (priority 3)
4. `beam` (priority 2)
5. `single_target` (priority 1)

### Class Tags with Skill Affinity

| Class | Tags | Skill Affinity (max +20% bonus) |
|-------|------|--------------------------------|
| `warrior` | melee, physical, tanky, frontline | melee, physical, tanky |
| `ranger` | ranged, agile, nature, mobile | ranged, agile, nature |
| `scholar` | magic, alchemy, arcane, caster | magic, arcane, alchemy |
| `artisan` | crafting, smithing, engineering, utility | crafting, smithing, engineering |
| `scavenger` | luck, gathering, treasure, explorer | luck, gathering, treasure |
| `adventurer` | balanced, versatile, generalist, adaptive | balanced, versatile, adaptive |

### Tag Resolution Flow

```
1. Parse tags from skill/equipment
2. Resolve aliases (e.g., "ice" → "frost", "vampiric" → "lifesteal")
3. Check for conflicts and remove lower priority tag
4. Determine geometry type (highest priority wins)
5. Select valid targets based on context tags
6. Apply synergy bonuses (e.g., lightning + chain)
7. Apply damage with type modifiers
8. Calculate status application chance
9. Apply status effects from status tags
10. Handle falloff for AoE effects
```

---

## UI Tooltip Systems ✅ IMPLEMENTED (NEW in V6)

**Code Reference:** `rendering/renderer.py`

### Class Selection Tooltips

When hovering over classes during character creation:
- Shows all class tags
- Explains what tags do (skill affinity, tool bonuses)
- Shows preferred damage types
- Shows preferred armor type
- Displays stat bonuses

### Tool Slot Tooltips

When hovering over equipped tools:
- Shows tool tier and name
- Shows base damage
- Shows durability (color-coded: green/yellow/red)
- Shows efficiency stat
- Shows class bonus if applicable (e.g., "+15% efficiency from Ranger")

---

# APPENDIX: Implementation Summary

## Implementation Status by System

| System | Status | Code Lines | Key File |
|--------|--------|------------|----------|
| Character Stats | ✅ IMPLEMENTED | 1,100+ | character.py |
| Combat | ✅ IMPLEMENTED | 1,377 | combat_manager.py |
| Skills | ✅ IMPLEMENTED | 709 | skill_manager.py |
| Status Effects | ✅ IMPLEMENTED | 827 | status_effect.py |
| Crafting (5 disciplines) | ✅ IMPLEMENTED | 9,159 | Crafting-subdisciplines/ |
| Classes | ✅ IMPLEMENTED | 200+ | class_system.py |
| Titles | ✅ IMPLEMENTED | 300+ | title_system.py |
| Save/Load | ✅ IMPLEMENTED | 400+ | save_manager.py |
| World Generation | ⏳ PARTIAL | 500+ | world_system.py |
| NPC/Quests | ⏳ PARTIAL | 300+ | npc_system.py |
| LLM Integration | 🔮 PLANNED | - | - |
| Block/Parry | 🔮 PLANNED | - | - |
| Summon Mechanics | 🔮 PLANNED | - | - |

## New V6 Features Summary

1. **Tag-Driven Class System**
   - Classes have semantic tags (warrior, melee, physical, etc.)
   - Tags drive multiple gameplay systems

2. **Skill Affinity Bonuses**
   - Matching class/skill tags grant +5% per match (max 20%)
   - Encourages class-appropriate skill usage

3. **Tool Efficiency Bonuses**
   - Nature/gathering tags boost axe efficiency
   - Gathering/explorer tags boost pickaxe efficiency
   - Physical/melee tags boost tool damage

4. **Enchantment Combat Integration**
   - 12+ enchantments active in combat
   - Fire Aspect, Lifesteal, Chain Damage, etc.

5. **Comprehensive Tooltips**
   - Class selection shows tag benefits
   - Tool slots show damage, durability, class bonuses

---

**Document Version:** 6.0
**Total Lines:** ~4700
**Last Updated:** December 31, 2025
**Maintained By:** Development Team
