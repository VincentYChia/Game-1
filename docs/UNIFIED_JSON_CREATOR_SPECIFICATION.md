# UNIFIED JSON CREATOR SYSTEM
## Comprehensive Design Specification v1.0

> **Project Goal**: Create a unified, human-friendly JSON creator system that handles ALL game data creation, validation, and management with automation hooks for future AI-driven content generation.

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [JSON Type Inventory](#json-type-inventory)
3. [Schema Definitions](#schema-definitions)
4. [Dependency Graph](#dependency-graph)
5. [System Architecture](#system-architecture)
6. [User Interface Design](#user-interface-design)
7. [Validation Engine](#validation-engine)
8. [Template System](#template-system)
9. [Automation API](#automation-api)
10. [Implementation Roadmap](#implementation-roadmap)

---

## 1. EXECUTIVE SUMMARY

### Current State
- **36 JSON files** across 7 directories
- **922KB** of game data
- **10+ distinct JSON schemas** with varying structures
- **Complex interdependencies** between item definitions, recipes, placements, progression, and configuration
- **Partial tooling**: Smithing grid designer exists, but limited to one use case

### Target State
- **Single unified interface** for creating ANY JSON type
- **Real-time validation** with cross-reference checking
- **Template-based creation** with smart defaults
- **Batch operations** for creating item series/variants
- **Visual editors** for spatial data (grids, placements)
- **Search & replace** across all JSON files
- **Export/import** capabilities for data migration
- **API endpoints** for programmatic/AI-driven content creation

###Core JSON Categories

#### **TIER 1: Foundation Data** (Must be created first)
1. **Materials** - Base resources (ores, wood, crystals, essences)
2. **Item Definitions** - Equipment, consumables, devices, tools, accessories

#### **TIER 2: Production Systems** (Depends on Tier 1)
3. **Recipes** - Crafting instructions across all disciplines
4. **Placements** - Spatial layouts for recipe execution

#### **TIER 3: Progression & Narrative** (Depends on Tier 1-2)
5. **NPCs** - Characters with dialogue
6. **Quests** - Objectives, rewards, progression
7. **Skills** - Abilities with effects and evolution
8. **Classes** - Character archetypes
9. **Titles** - Achievement badges with bonuses

#### **TIER 4: Configuration & Balance** (Depends on all others)
10. **Combat Config** - Spawn rates, damage formulas
11. **Rarity Modifiers** - Stat bonuses by quality
12. **Enemy Definitions** - Hostile entities with drops
13. **Resource Nodes** - Gatherable world objects
14. **Translation Tables** - Value mappings

---

## 2. JSON TYPE INVENTORY

### 2.1 ITEMS - Equipment & Materials
**Files**: `items.JSON/*.JSON` (6 files, 101KB)

#### Item Categories:
1. **Weapons** - Swords, axes, spears, maces, daggers, bows, staves, shields
2. **Armor** - Helmets, chestplates, leggings, boots, gauntlets
3. **Tools** - Pickaxes, axes, fishing rods, sickles
4. **Consumables** - Potions (health, mana, buff), elixirs
5. **Devices** - Turrets, bombs, traps, utility devices
6. **Accessories** - Rings, amulets, bracelets
7. **Materials** - Ores, ingots, wood, stone, crystals, essences
8. **Stations** - Forges, refineries, alchemy tables, workbenches

#### Schema Structure:
```json
{
  "metadata": {
    "version": "1.0",
    "narrative": "Flavor text",
    "tags": ["gameplay_tags"]
  },
  "itemId": "unique_id",
  "name": "Display Name",
  "category": "weapon|armor|tool|consumable|device|station|material",
  "type": "sword|axe|helmet|potion|...",
  "subtype": "longsword|greatsword|...",
  "tier": 1-4,
  "rarity": "common|uncommon|rare|epic|legendary|artifact",
  "effect": "Description of effect",
  "stackSize": 1-99,
  "statMultipliers": {
    "weight": 1.0,
    "damage": 1.0,
    "defense": 1.0
  },
  "requirements": {
    "level": 1,
    "stats": {"STR": 10, "DEF": 5}
  },
  "flags": {
    "stackable": true|false,
    "placeable": true|false,
    "repairable": true|false
  }
}
```

#### Required Fields:
- `itemId` (unique identifier)
- `name` (display name)
- `category` (item type)
- `tier` (1-4)
- `rarity` (quality level)

#### Optional Fields:
- `type`, `subtype` (sub-categorization)
- `effect` (description)
- `stackSize` (default: 1)
- `statMultipliers` (damage/defense/weight modifiers)
- `requirements` (level, stats needed)
- `flags` (behavioral properties)

#### Cross-References:
- Referenced by: Recipes (as outputs), Quests (as rewards), Enemy drops, NPC inventory
- References: None (foundational)

---

### 2.2 RECIPES - Crafting Instructions
**Files**: `recipes.JSON/*.JSON` (6 files, 132KB)

#### Recipe Disciplines:
1. **Smithing** - Weapons, armor, tools (37 recipes)
2. **Alchemy** - Potions, elixirs (18 recipes)
3. **Refining** - Ore-to-ingot conversion
4. **Engineering** - Devices, turrets, traps
5. **Enchanting** - Item modification (30 recipes)
6. **Adornments** - Accessory crafting

#### Schema Variants:

**Standard Recipe:**
```json
{
  "metadata": {
    "narrative": "Story text",
    "tags": ["weapon", "starter"]
  },
  "recipeId": "smithing_iron_shortsword",
  "outputId": "iron_shortsword",
  "outputQty": 1,
  "stationTier": 1,
  "stationType": "smithing|alchemy|refining|engineering|enchanting",
  "gridSize": "3x3|5x5|7x7|9x9|12x12",
  "inputs": [
    {"materialId": "iron_ingot", "quantity": 2},
    {"materialId": "oak_plank", "quantity": 1}
  ],
  "miniGame": {
    "type": "smithing",
    "difficulty": "easy|moderate|hard|extreme",
    "baseTime": 30
  }
}
```

**Enchanting Recipe:**
```json
{
  "recipeId": "enchanting_sharpness_basic",
  "enchantmentId": "sharpness_1",
  "enchantmentName": "Sharpness I",
  "applicableTo": ["weapon"],
  "effect": {
    "type": "damage_multiplier",
    "value": 0.10,
    "stackable": false,
    "conflictsWith": ["sharpness_2", "sharpness_3"]
  },
  "inputs": [...]
}
```

#### Tier-to-GridSize Mapping:
- **Tier 1** → 3x3 grid
- **Tier 2** → 5x5 grid
- **Tier 3** → 7x7 grid
- **Tier 4** → 9x9 grid

#### Cross-References:
- References: Items (outputId), Materials (inputs)
- Referenced by: Placements, Crafting stations

---

### 2.3 PLACEMENTS - Spatial Layouts
**Files**: `placements.JSON/*.JSON` (5 files, 170KB)

#### Placement Formats:

**Grid-Based (Smithing/Enchanting):**
```json
{
  "recipeId": "smithing_iron_shortsword",
  "placementMap": {
    "1,1": "iron_ingot",
    "1,2": "iron_ingot",
    "2,2": "oak_plank"
  },
  "metadata": {
    "gridSize": "3x3",
    "narrative": "Placement description"
  }
}
```

**Hub-and-Spoke (Refining):**
```json
{
  "recipeId": "refining_iron_ore",
  "discipline": "refining",
  "core_inputs": [
    {"slot": "center", "materialId": "iron_ore"}
  ],
  "surrounding_inputs": [
    {"slot": "north", "materialId": "flux"},
    {"slot": "south", "materialId": "flux"}
  ]
}
```

**Sequential (Alchemy):**
```json
{
  "recipeId": "alchemy_health_potion",
  "discipline": "alchemy",
  "sequence": [
    {"step": 1, "action": "add", "materialId": "red_herb"},
    {"step": 2, "action": "heat", "duration": 5},
    {"step": 3, "action": "add", "materialId": "water_crystal"},
    {"step": 4, "action": "stir", "direction": "clockwise"}
  ]
}
```

**Slot-Based (Engineering):**
```json
{
  "recipeId": "engineering_turret",
  "discipline": "engineering",
  "slots": {
    "frame": "iron_frame",
    "mechanism": "gear_assembly",
    "power": "fire_crystal",
    "projectile": "iron_bolt"
  }
}
```

#### Cross-References:
- References: Recipes (recipeId), Materials (grid contents)
- Referenced by: None (terminal)

---

### 2.4 NPCS - Non-Player Characters
**Files**: `progression/npcs-*.JSON` (2 files)

#### Schema:
```json
{
  "npc_id": "tutorial_guide",
  "name": "Elder Sage",
  "position": {"x": 48.0, "y": 48.0, "z": 0.0},
  "sprite_color": [200, 150, 255],
  "interaction_radius": 3.0,
  "dialogue_lines": [
    "Welcome, traveler!",
    "I have tasks for you."
  ],
  "quests": ["tutorial_quest", "gathering_quest"]
}
```

#### Required Fields:
- `npc_id` (unique)
- `name` (display name)
- `position` (x, y, z coordinates)
- `dialogue_lines` (array of strings)

#### Optional Fields:
- `sprite_color` (RGB array)
- `interaction_radius` (detection range)
- `quests` (quest IDs offered)

#### Cross-References:
- References: Quests (quest list)
- Referenced by: Quests (quest_giver)

---

### 2.5 QUESTS - Objectives & Rewards
**Files**: `progression/quests-*.JSON` (2 files)

#### Schema:
```json
{
  "quest_id": "tutorial_quest",
  "title": "First Steps",
  "description": "Gather 5 oak logs",
  "npc_id": "tutorial_guide",
  "objectives": {
    "type": "gather|combat|craft",
    "items": [
      {"item_id": "oak_log", "quantity": 5}
    ],
    "enemies_killed": 0
  },
  "rewards": {
    "experience": 100,
    "health_restore": 50,
    "skills": ["sprint"],
    "items": [
      {"item_id": "minor_health_potion", "quantity": 2}
    ],
    "title": "novice_forester"
  },
  "completion_dialogue": [
    "Excellent work!",
    "Take these rewards."
  ]
}
```

#### Objective Types:
1. **Gather** - Collect specific items
2. **Combat** - Kill enemies
3. **Craft** - Create items
4. **Explore** - Visit locations

#### Cross-References:
- References: NPCs (quest_giver), Items (objectives, rewards), Skills (rewards), Titles (rewards)
- Referenced by: NPCs (quest list)

---

### 2.6 SKILLS - Abilities & Powers
**Files**: `Skills/skills-*.JSON` (2 files, 42KB total, 30 skills)

#### Schema:
```json
{
  "skillId": "miners_fury",
  "name": "Miner's Fury",
  "tier": 1-4,
  "rarity": "common|uncommon|rare|epic|legendary|mythic",
  "categories": ["gathering", "mining", "combat"],
  "description": "Skill description",
  "narrative": "Flavor text",
  "tags": ["damage_boost", "gathering"],
  "effect": {
    "type": "empower|quicken|fortify|pierce|regenerate|devastate",
    "category": "mining|combat|crafting|...",
    "magnitude": "minor|moderate|major|extreme",
    "target": "self|enemy|area|resource_node",
    "duration": "instant|brief|moderate|long|extended",
    "additionalEffects": [...]
  },
  "cost": {
    "mana": "low|moderate|high|extreme",
    "cooldown": "short|moderate|long|extreme"
  },
  "evolution": {
    "canEvolve": true,
    "nextSkillId": "titans_excavation",
    "requirement": "Reach level 10 and mine 1000 ore nodes"
  },
  "requirements": {
    "characterLevel": 1,
    "stats": {"STR": 10},
    "titles": []
  }
}
```

#### Effect Types:
- **empower** - Increase damage/power
- **quicken** - Increase speed
- **fortify** - Increase defense/durability
- **pierce** - Increase critical chance
- **regenerate** - Restore over time
- **devastate** - Area of effect damage
- **elevate** - Increase rarity/quality
- **enrich** - Increase yield/quantity
- **restore** - Instant healing
- **transcend** - Bypass restrictions

#### Skill Categories:
- Gathering (mining, forestry, fishing)
- Combat (offense, defense, mobility)
- Crafting (smithing, alchemy, engineering, refining, enchanting)
- Utility (repair, movement, support)

#### Cross-References:
- References: None (self-contained)
- Referenced by: Quests (rewards), Classes (starting skill), Titles (unlocks)

---

### 2.7 CLASSES - Character Archetypes
**Files**: `progression/classes-1.JSON` (6 classes)

#### Schema:
```json
{
  "classId": "warrior",
  "name": "Warrior",
  "description": "Front-line fighter",
  "narrative": "Class backstory",
  "thematicIdentity": "frontline_fighter",
  "startingBonuses": {
    "baseHP": 30,
    "baseMana": 0,
    "meleeDamage": 0.10,
    "inventorySlots": 20
  },
  "startingSkill": {
    "skillId": "battle_rage",
    "skillName": "Battle Rage",
    "initialLevel": 1,
    "description": "Skill description"
  },
  "recommendedStats": {
    "primary": ["STR", "VIT", "DEF"],
    "secondary": ["AGI"],
    "avoid": ["INT", "LCK"]
  }
}
```

#### Available Classes:
1. **Warrior** - High HP, melee damage
2. **Mage** - High mana, INT bonus
3. **Ranger** - AGI focus, ranged damage
4. **Craftsman** - Crafting bonuses, inventory slots
5. **Tank** - Max DEF, HP regen
6. **Assassin** - Critical damage, AGI/LCK

#### Cross-References:
- References: Skills (starting skill)
- Referenced by: Character creation system

---

### 2.8 TITLES - Achievement Badges
**Files**: `progression/titles-1.JSON`

#### Schema:
```json
{
  "titleId": "novice_miner",
  "name": "Novice Miner",
  "titleType": "gathering|crafting|combat",
  "difficultyTier": "novice|apprentice|journeyman|master",
  "description": "Title description",
  "bonuses": {
    "miningDamage": 0.10,
    "miningSpeed": 0.05,
    "rareOreChance": 0.02
  },
  "prerequisites": {
    "activities": {
      "oresMined": 100
    },
    "requiredTitles": [],
    "characterLevel": 0
  },
  "acquisitionMethod": "guaranteed_milestone|discovery|quest",
  "narrative": "Title backstory"
}
```

#### Title Types:
- **Gathering** - Mining, forestry, fishing bonuses
- **Crafting** - Smithing, alchemy, engineering bonuses
- **Combat** - Damage, defense, critical bonuses
- **Exploration** - Movement, discovery bonuses

#### Cross-References:
- References: None (self-contained)
- Referenced by: Quests (rewards), Skill requirements

---

### 2.9 COMBAT CONFIG - Game Balance
**Files**: `Definitions.JSON/combat-config.JSON`

#### Schema:
```json
{
  "experienceRewards": {
    "tier1": 100,
    "tier2": 400,
    "tier3": 1600,
    "tier4": 6400,
    "bossMultiplier": 10.0
  },
  "safeZone": {
    "centerX": 50,
    "centerY": 50,
    "radius": 15,
    "noSpawning": true
  },
  "spawnRates": {
    "peaceful": {
      "minEnemies": 0,
      "maxEnemies": 2,
      "spawnInterval": 120,
      "tierWeights": {"tier1": 0.9, "tier2": 0.1}
    },
    "normal": {...},
    "dangerous": {...}
  },
  "enemyRespawn": {
    "baseRespawnTime": 300,
    "tierMultipliers": {"tier1": 1.0, "tier2": 1.5}
  },
  "combatMechanics": {
    "playerAttackRange": 2.0,
    "baseAttackCooldown": 1.0,
    "toolAttackCooldown": 0.5
  },
  "damageFormulas": {
    "playerDamage": "weaponDamage * (1 + STR * 0.05) * titleBonus",
    "enemyDamage": "enemyBaseDamage * (1 - (DEF * 0.02 + armorBonus))",
    "critMultiplier": 2.0
  }
}
```

#### Configuration Categories:
- Experience/rewards
- Safe zones
- Spawn rates by difficulty
- Respawn timers
- Combat mechanics
- Damage calculations

---

### 2.10 RARITY MODIFIERS - Item Quality Bonuses
**Files**: `Crafting-subdisciplines/rarity-modifiers.JSON` (387KB!)

#### Schema:
```json
{
  "weapon": {
    "common": {
      "description": "Basic weapon",
      "modifiers": {}
    },
    "uncommon": {
      "description": "Improved weapon",
      "modifiers": {
        "damage": 0.10,
        "durability": 0.05
      }
    },
    "rare": {
      "modifiers": {
        "damage": 0.20,
        "durability": 0.10,
        "critical_chance": 0.05
      }
    },
    "legendary": {
      "modifiers": {
        "damage": 1.00,
        "durability": 0.30,
        "critical_chance": 0.15,
        "attack_speed": 0.10,
        "lifesteal": 0.05
      },
      "special_effects": {
        "lifesteal": true
      }
    }
  },
  "armor": {...},
  "tool": {...},
  "consumable": {...},
  "device": {...},
  "station": {...}
}
```

#### Rarity Progression:
1. **Common** - No bonuses
2. **Uncommon** - +10% primary stat, +5% durability
3. **Rare** - +20% primary, +10% durability, +5% secondary
4. **Epic** - +35% primary, +20% durability, +10% secondary, special effect
5. **Legendary** - +100% primary, +30% durability, +15% secondary, multiple effects

#### Item Categories Covered:
- Weapons (damage, crit, lifesteal)
- Armor (defense, resistance, thorns)
- Tools (efficiency, gathering speed, yield)
- Consumables (potency, duration, effect count)
- Devices (power, range, cooldown)
- Stations (durability only)

---

### 2.11 ENEMIES - Hostile Entities
**Files**: `Definitions.JSON/hostiles-1.JSON`

#### Schema:
```json
{
  "enemyId": "wolf_grey",
  "name": "Grey Wolf",
  "tier": 1-4,
  "category": "beast|undead|construct|elemental",
  "behavior": "passive_patrol|aggressive_pack|...",
  "stats": {
    "health": 80,
    "damage": [8, 12],
    "defense": 5,
    "speed": 1.2,
    "aggroRange": 5,
    "attackSpeed": 1.0
  },
  "drops": [
    {
      "materialId": "wolf_pelt",
      "quantity": [2, 4],
      "chance": "guaranteed|high|moderate|low"
    }
  ],
  "aiPattern": {
    "defaultState": "wander",
    "aggroOnDamage": true,
    "fleeAtHealth": 0.2,
    "callForHelpRadius": 8
  }
}
```

#### Enemy Categories:
- **Beast** - Natural animals (wolves, bears, spiders)
- **Undead** - Skeletons, zombies
- **Construct** - Golems, automatons
- **Elemental** - Fire/ice/lightning entities

#### Cross-References:
- References: Materials (drop table)
- Referenced by: Combat config (spawn rates)

---

### 2.12 RESOURCE NODES - Gatherable Objects
**Files**: `Definitions.JSON/resource-node-1.JSON`

#### Schema:
```json
{
  "resourceId": "oak_tree",
  "name": "Oak Tree",
  "category": "tree|ore_deposit|fishing_spot|plant",
  "tier": 1-4,
  "requiredTool": "axe|pickaxe|fishing_rod|sickle",
  "baseHealth": 100,
  "drops": [
    {
      "materialId": "oak_log",
      "quantity": "few|several|many",
      "chance": "guaranteed|high|moderate|low"
    }
  ],
  "respawnTime": "fast|normal|slow|very_slow"
}
```

#### Node Categories:
- **Trees** - Oak, pine, birch, ash, ironwood, ebony
- **Ore Deposits** - Copper, iron, steel, mithril
- **Fishing Spots** - Rivers, lakes, oceans
- **Plants** - Herbs, flowers, mushrooms

#### Cross-References:
- References: Materials (drop table)
- Referenced by: World generation, Skill bonuses

---

### 2.13 TRANSLATION TABLES - Value Mappings
**Files**: `Definitions.JSON/value-translation-table-1.JSON`, `skills-translation-table.JSON`

#### Value Translation:
```json
{
  "quantitative": {
    "few": {"min": 1, "max": 3},
    "several": {"min": 3, "max": 6},
    "many": {"min": 6, "max": 10}
  },
  "qualitative": {
    "low": {"value": 10},
    "moderate": {"value": 25},
    "high": {"value": 50},
    "extreme": {"value": 100}
  },
  "temporal": {
    "brief": {"seconds": 5},
    "short": {"seconds": 15},
    "moderate": {"seconds": 30},
    "long": {"seconds": 60},
    "extended": {"seconds": 120},
    "extreme": {"seconds": 300}
  }
}
```

#### Skills Translation:
```json
{
  "effect_types": {
    "empower": "Increase power/damage",
    "quicken": "Increase speed",
    "fortify": "Increase defense/durability"
  },
  "magnitude_multipliers": {
    "minor": 1.15,
    "moderate": 1.30,
    "major": 1.50,
    "extreme": 2.00
  }
}
```

---

## 3. SCHEMA DEFINITIONS

### 3.1 Base Schema (All JSON Types)
```typescript
interface BaseSchema {
  metadata?: {
    version: string;
    description?: string;
    narrative?: string;
    tags?: string[];
  };
}
```

### 3.2 Item Schema
```typescript
interface ItemSchema extends BaseSchema {
  itemId: string;  // REQUIRED, UNIQUE
  name: string;     // REQUIRED
  category: 'weapon' | 'armor' | 'tool' | 'consumable' | 'device' | 'station' | 'material';
  type?: string;    // Sub-category
  subtype?: string; // Further refinement
  tier: 1 | 2 | 3 | 4;  // REQUIRED
  rarity: 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary' | 'artifact';
  effect?: string;
  stackSize?: number;  // Default: 1
  statMultipliers?: {
    weight?: number;
    damage?: number;
    defense?: number;
    [key: string]: number | undefined;
  };
  requirements?: {
    level?: number;
    stats?: Record<string, number>;
  };
  flags?: {
    stackable?: boolean;
    placeable?: boolean;
    repairable?: boolean;
  };
}
```

### 3.3 Recipe Schema
```typescript
interface RecipeSchema extends BaseSchema {
  recipeId: string;  // REQUIRED, UNIQUE
  outputId: string;  // REQUIRED, must reference valid itemId
  outputQty: number; // REQUIRED
  stationTier: 1 | 2 | 3 | 4;
  stationType: 'smithing' | 'alchemy' | 'refining' | 'engineering' | 'enchanting';
  gridSize: '3x3' | '5x5' | '7x7' | '9x9' | '12x12';
  inputs: Array<{
    materialId: string;  // Must reference valid itemId or materialId
    quantity: number;
  }>;
  miniGame?: {
    type: string;
    difficulty: 'easy' | 'moderate' | 'hard' | 'extreme';
    baseTime: number;  // Seconds
  };
}
```

### 3.4 Placement Schema
```typescript
interface PlacementSchema {
  recipeId: string;  // REQUIRED, must reference valid recipe
  placementMap?: Record<string, string>;  // Grid format: "row,col": "materialId"
  discipline?: 'smithing' | 'alchemy' | 'refining' | 'engineering';

  // Alternative formats
  core_inputs?: Array<{slot: string; materialId: string}>;
  surrounding_inputs?: Array<{slot: string; materialId: string}>;
  sequence?: Array<{step: number; action: string; materialId?: string}>;
  slots?: Record<string, string>;

  metadata?: {
    gridSize: string;
    narrative: string;
  };
}
```

### 3.5 NPC Schema
```typescript
interface NPCSchema {
  npc_id: string;    // REQUIRED, UNIQUE
  name: string;       // REQUIRED
  position: {x: number; y: number; z: number};
  sprite_color?: [number, number, number];
  interaction_radius?: number;
  dialogue_lines: string[];  // REQUIRED
  quests?: string[];  // Quest IDs
}
```

### 3.6 Quest Schema
```typescript
interface QuestSchema {
  quest_id: string;  // REQUIRED, UNIQUE
  title: string;      // REQUIRED
  description: string;
  npc_id: string;     // Must reference valid NPC
  objectives: {
    type: 'gather' | 'combat' | 'craft';
    items?: Array<{item_id: string; quantity: number}>;
    enemies_killed?: number;
  };
  rewards: {
    experience?: number;
    health_restore?: number;
    mana_restore?: number;
    skills?: string[];  // Skill IDs
    items?: Array<{item_id: string; quantity: number}>;
    title?: string;  // Title ID
  };
  completion_dialogue?: string[];
}
```

### 3.7 Skill Schema
```typescript
interface SkillSchema extends BaseSchema {
  skillId: string;  // REQUIRED, UNIQUE
  name: string;      // REQUIRED
  tier: 1 | 2 | 3 | 4;
  rarity: 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary' | 'mythic';
  categories: string[];
  description: string;
  narrative?: string;
  tags?: string[];
  effect: {
    type: 'empower' | 'quicken' | 'fortify' | 'pierce' | 'regenerate' | 'devastate' |
          'elevate' | 'enrich' | 'restore' | 'transcend';
    category: string;
    magnitude: 'minor' | 'moderate' | 'major' | 'extreme';
    target: 'self' | 'enemy' | 'area' | 'resource_node';
    duration: 'instant' | 'brief' | 'moderate' | 'long' | 'extended';
    additionalEffects?: Array<any>;
  };
  cost: {
    mana: 'low' | 'moderate' | 'high' | 'extreme';
    cooldown: 'short' | 'moderate' | 'long' | 'extreme';
  };
  evolution?: {
    canEvolve: boolean;
    nextSkillId?: string;
    requirement?: string;
  };
  requirements: {
    characterLevel: number;
    stats?: Record<string, number>;
    titles?: string[];
  };
}
```

### 3.8 Class Schema
```typescript
interface ClassSchema extends BaseSchema {
  classId: string;  // REQUIRED, UNIQUE
  name: string;      // REQUIRED
  description: string;
  narrative?: string;
  thematicIdentity?: string;
  startingBonuses: {
    baseHP?: number;
    baseMana?: number;
    meleeDamage?: number;
    rangedDamage?: number;
    magicDamage?: number;
    defense?: number;
    criticalChance?: number;
    inventorySlots?: number;
  };
  startingSkill: {
    skillId: string;  // Must reference valid skill
    skillName: string;
    initialLevel: number;
    description: string;
  };
  recommendedStats: {
    primary: string[];
    secondary?: string[];
    avoid?: string[];
  };
}
```

### 3.9 Title Schema
```typescript
interface TitleSchema extends BaseSchema {
  titleId: string;  // REQUIRED, UNIQUE
  name: string;      // REQUIRED
  titleType: 'gathering' | 'crafting' | 'combat' | 'exploration';
  difficultyTier: 'novice' | 'apprentice' | 'journeyman' | 'master' | 'grandmaster';
  description: string;
  bonuses: Record<string, number>;  // Stat bonuses
  prerequisites: {
    activities?: Record<string, number>;
    requiredTitles?: string[];
    characterLevel?: number;
  };
  acquisitionMethod: 'guaranteed_milestone' | 'discovery' | 'quest';
  narrative?: string;
}
```

---

## 4. DEPENDENCY GRAPH

### 4.1 Load Order
```
1. Materials
   ↓
2. Items (reference materials implicitly)
   ↓
3. Recipes (input: materials/items, output: items)
   ↓
4. Placements (reference recipes + materials)
   ↓
5. NPCs (standalone)
   ↓
6. Skills (standalone)
   ↓
7. Classes (reference skills)
   ↓
8. Titles (standalone)
   ↓
9. Quests (reference NPCs, items, skills, titles)
   ↓
10. Enemies (reference materials for drops)
    ↓
11. Resource Nodes (reference materials for drops)
    ↓
12. Config Files (reference everything for balance)
```

### 4.2 Cross-Reference Matrix

| Type | References | Referenced By |
|------|-----------|--------------|
| **Materials** | None | Recipes, Enemies, Nodes, Placements |
| **Items** | None | Recipes, Quests, Enemies, NPC inventory |
| **Recipes** | Items, Materials | Placements, Stations |
| **Placements** | Recipes, Materials | None |
| **NPCs** | Quests | Quests |
| **Quests** | NPCs, Items, Skills, Titles | NPCs |
| **Skills** | None | Classes, Quests, Titles |
| **Classes** | Skills | Character creation |
| **Titles** | None | Quests, Skill requirements |
| **Enemies** | Materials | Combat config |
| **Nodes** | Materials | World generation |
| **Config** | All types | Game systems |

### 4.3 Validation Rules

#### Cross-Reference Validation:
1. **Recipe.outputId** must exist in Items
2. **Recipe.inputs[].materialId** must exist in Materials or Items
3. **Placement.recipeId** must exist in Recipes
4. **Placement.placementMap values** must match Recipe.inputs[].materialId
5. **Quest.npc_id** must exist in NPCs
6. **Quest.rewards.items[].item_id** must exist in Items
7. **Quest.rewards.skills[]** must exist in Skills
8. **Quest.rewards.title** must exist in Titles
9. **Class.startingSkill.skillId** must exist in Skills
10. **Enemy.drops[].materialId** must exist in Materials
11. **Node.drops[].materialId** must exist in Materials

#### Logical Validation:
1. **Tier consistency**: Recipe stationTier ≤ all input item tiers
2. **Grid size**: Placement grid matches Recipe gridSize
3. **Material count**: Placement total quantities match Recipe input quantities
4. **Level requirements**: Quest reward items' requirements ≤ quest level
5. **Skill evolution**: evolution.nextSkillId must exist if canEvolve = true

---

## 5. SYSTEM ARCHITECTURE

### 5.1 High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│         UNIFIED JSON CREATOR INTERFACE          │
│              (Web-based GUI)                    │
└───────────┬─────────────────────────────────────┘
            │
    ┌───────┴────────┐
    │                │
┌───▼────┐    ┌─────▼──────┐
│Template│    │  Validator  │
│ Engine │    │  Engine     │
└───┬────┘    └─────┬───────┘
    │               │
    │         ┌─────▼────────┐
    │         │ Cross-Ref    │
    │         │ Resolver     │
    │         └─────┬────────┘
    │               │
┌───▼───────────────▼────────────┐
│     JSON Data Store            │
│  (File-based + In-memory DB)   │
└───────────┬────────────────────┘
            │
    ┌───────┴────────┐
    │                │
┌───▼───────┐  ┌────▼────────┐
│ Export    │  │  Automation │
│ Manager   │  │  API        │
└───────────┘  └─────────────┘
```

### 5.2 Component Breakdown

#### 5.2.1 Frontend (Web-based GUI)
**Technology**: React + TypeScript + TailwindCSS

**Core Views**:
1. **Dashboard** - Overview of all JSON types, stats, warnings
2. **Creator View** - Form-based creation for any JSON type
3. **Visual Editor** - Grid-based placement designer (extended smithing tool)
4. **Batch Operations** - Create multiple items with templates
5. **Validation Center** - List all errors, warnings, suggestions
6. **Search & Replace** - Cross-file find/replace
7. **Dependency Viewer** - Visual graph of relationships

#### 5.2.2 Backend (Python/FastAPI)
**Technology**: Python 3.10+, FastAPI, Pydantic

**Core Services**:
1. **Schema Service** - Load/validate schemas
2. **CRUD Service** - Create/Read/Update/Delete JSON entries
3. **Validation Service** - Cross-reference checking
4. **Template Service** - Generate from templates
5. **Export Service** - Generate final JSON files
6. **Search Service** - Full-text and structured search

#### 5.2.3 Data Store
**Technology**: File-based JSON + SQLite for indexing

**Structure**:
```
/data
  /items
    /weapons.json
    /armor.json
    ...
  /recipes
    /smithing.json
    ...
  /index.db  (SQLite for fast lookups)
```

#### 5.2.4 Validation Engine
**Components**:
- Schema validator (Pydantic models)
- Cross-reference validator
- Business logic validator
- Data integrity checker

#### 5.2.5 Template Engine
**Features**:
- Predefined templates for each JSON type
- Variable substitution
- Batch generation (e.g., copper/iron/steel variants)
- Smart defaults based on tier/rarity

#### 5.2.6 Export Manager
**Features**:
- Generate production-ready JSON files
- Minify option
- Backup previous versions
- Git integration

#### 5.2.7 Automation API
**Endpoints**:
```
POST /api/items/create
POST /api/recipes/create
POST /api/batch/create-item-series
POST /api/validate/all
GET  /api/search?q=<query>
POST /api/export
```

---

## 6. USER INTERFACE DESIGN

### 6.1 Dashboard View

```
┌─────────────────────────────────────────────────────────────┐
│  UNIFIED JSON CREATOR                       [Settings] [?]   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  📊 PROJECT OVERVIEW                                         │
│  ┌───────────┬───────────┬───────────┬───────────┐          │
│  │   Items   │  Recipes  │   NPCs    │  Quests   │          │
│  │    247    │    112    │     8     │    15     │          │
│  └───────────┴───────────┴───────────┴───────────┘          │
│                                                               │
│  ⚠️ VALIDATION STATUS                                        │
│  ┌─────────────────────────────────────────────────┐        │
│  │ ✅ All schemas valid                             │        │
│  │ ⚠️  3 missing cross-references                   │        │
│  │ 💡 12 optimization suggestions                   │        │
│  └─────────────────────────────────────────────────┘        │
│                                                               │
│  🚀 QUICK ACTIONS                                            │
│  [Create New] [Batch Operations] [Visual Editor]            │
│  [Validate All] [Export] [Import]                           │
│                                                               │
│  📁 RECENT ITEMS                                             │
│  • iron_shortsword (modified 5m ago)                         │
│  • smithing_steel_longsword (created 1h ago)                │
│  • tutorial_quest (modified 2h ago)                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Creator View (Item Example)

```
┌─────────────────────────────────────────────────────────────┐
│  CREATE ITEM                              [Save] [Cancel]    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  📋 BASIC INFO                                               │
│  Item ID: [iron_longsword________________] (auto-generate)  │
│  Name:    [Iron Longsword________________]                  │
│  Category: [Weapon ▼]  Type: [Sword ▼]  Subtype: [Longsword ▼]│
│  Tier:    [2 ▼]        Rarity: [Common ▼]                   │
│                                                               │
│  📊 STATS                                                     │
│  Damage Multiplier:  [1.0____] (base: 20-30 → actual: 20-30)│
│  Defense Multiplier: [0______]                               │
│  Weight Multiplier:  [1.0____]                               │
│  Stack Size:         [1______]                               │
│                                                               │
│  🎯 REQUIREMENTS                                              │
│  Level: [5__]   STR: [10_]   DEF: [5_]   AGI: [__]          │
│                                                               │
│  🏷️ FLAGS                                                     │
│  ☐ Stackable   ☐ Placeable   ☑ Repairable                   │
│                                                               │
│  📝 DESCRIPTION                                               │
│  Effect: [Deals 20-30 physical damage__________________]     │
│                                                               │
│  Narrative:                                                   │
│  ┌─────────────────────────────────────────────────┐        │
│  │A well-crafted iron blade. Not fancy, but reliable.│       │
│  │The balance feels right in your hand.              │        │
│  └─────────────────────────────────────────────────┘        │
│                                                               │
│  🏷️ METADATA                                                  │
│  Tags: [weapon] [sword] [tier2] [+Add]                       │
│                                                               │
│  ✅ VALIDATION: All fields valid, no conflicts               │
│                                                               │
│  [💾 Save Item]  [📋 Save as Template]  [🗑️ Cancel]         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Visual Editor (Grid Placement)

```
┌─────────────────────────────────────────────────────────────┐
│  PLACEMENT EDITOR                         [Save] [Cancel]    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Recipe: [smithing_iron_longsword ▼]                        │
│  Grid Size: 5x5 (Tier 2)                                    │
│                                                               │
│  ┌─────────────┬────────────────────────────┐               │
│  │  PALETTE    │         GRID                │              │
│  ├─────────────┤                             │              │
│  │ 🟢 iron_ingot│    1   2   3   4   5      │              │
│  │    (4/4)    │  ┌───┬───┬───┬───┬───┐    │              │
│  │             │1 │   │   │ I │   │   │    │              │
│  │ 🟢 maple_plank│ ├───┼───┼───┼───┼───┤    │              │
│  │    (1/1)    │2 │   │ I │   │   │   │    │              │
│  │             │  ├───┼───┼───┼───┼───┤    │              │
│  │ 🟢 dire_fang│3 │ D │   │   │   │   │    │              │
│  │    (2/2)    │  ├───┼───┼───┼───┼───┤    │              │
│  │             │4 │   │   │   │ M │   │    │              │
│  │             │  ├───┼───┼───┼───┼───┤    │              │
│  │ [Add Material]│5 │ D │   │   │   │   │    │              │
│  │             │  └───┴───┴───┴───┴───┘    │              │
│  │             │                             │              │
│  │ INSTRUCTIONS│  Legend:                    │              │
│  │ 1. Click    │  I = iron_ingot             │              │
│  │    palette  │  M = maple_plank            │              │
│  │ 2. Click    │  D = dire_fang              │              │
│  │    grid     │                             │              │
│  │ 3. Spacebar │  ✅ Valid placement          │              │
│  │    reselect │                             │              │
│  └─────────────┴────────────────────────────┘               │
│                                                               │
│  JSON PREVIEW:                                               │
│  {                                                           │
│    "1,3": "iron_ingot",                                     │
│    "2,2": "iron_ingot",                                     │
│    "3,1": "dire_fang",                                      │
│    "4,4": "maple_plank",                                    │
│    "5,1": "dire_fang"                                       │
│  }                                                           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Batch Operations View

```
┌─────────────────────────────────────────────────────────────┐
│  BATCH OPERATIONS                         [Execute] [Cancel] │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  OPERATION TYPE: [Create Item Series ▼]                     │
│                                                               │
│  📋 TEMPLATE                                                  │
│  Base Template: [Generic Sword Template ▼]                  │
│                                                               │
│  🔢 SERIES CONFIGURATION                                      │
│  Material Progression:                                        │
│  ☑ copper  →  iron  →  steel  →  mithril                   │
│                                                               │
│  Tier Progression:                                            │
│  ☑ T1 (copper) → T2 (iron) → T3 (steel) → T4 (mithril)     │
│                                                               │
│  Naming Pattern:                                              │
│  [${material}_${weapon_type}] →                             │
│  copper_sword, iron_sword, steel_sword, mithril_sword       │
│                                                               │
│  📊 PREVIEW (4 items will be created)                        │
│  ┌─────────────────────────────────────────────┐            │
│  │ 1. copper_sword   (T1, common, dmg: 8-12)   │            │
│  │ 2. iron_sword     (T2, common, dmg: 20-30)  │            │
│  │ 3. steel_sword    (T3, uncommon, dmg: 45-60)│            │
│  │ 4. mithril_sword  (T4, rare, dmg: 90-120)   │            │
│  └─────────────────────────────────────────────┘            │
│                                                               │
│  ⚙️ ADDITIONAL OPTIONS                                        │
│  ☑ Auto-create recipes for each item                         │
│  ☑ Auto-create placements                                    │
│  ☐ Auto-generate narrative text (AI)                         │
│                                                               │
│  [🚀 Execute Batch Operation]                                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 6.5 Validation Center

```
┌─────────────────────────────────────────────────────────────┐
│  VALIDATION CENTER                        [Fix All] [Refresh]│
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  STATUS OVERVIEW                                             │
│  ┌───────────┬───────────┬───────────┐                      │
│  │ ✅ Valid  │ ⚠️ Warnings│ ❌ Errors │                      │
│  │   234     │     12     │     3     │                      │
│  └───────────┴───────────┴───────────┘                      │
│                                                               │
│  🔴 ERRORS (3)                                               │
│  ┌─────────────────────────────────────────────────┐        │
│  │ ❌ Recipe "smithing_titanium_blade"              │        │
│  │    → outputId "titanium_blade" does not exist   │        │
│  │    [Fix: Create Item] [Fix: Change Output]      │        │
│  ├─────────────────────────────────────────────────┤        │
│  │ ❌ Quest "advanced_smithing"                     │        │
│  │    → npc_id "master_smith" does not exist       │        │
│  │    [Fix: Create NPC] [Fix: Change NPC]          │        │
│  ├─────────────────────────────────────────────────┤        │
│  │ ❌ Placement "smithing_mithril_axe"              │        │
│  │    → Material count mismatch (used 11, need 15) │        │
│  │    [Fix: Update Placement] [Fix: Update Recipe] │        │
│  └─────────────────────────────────────────────────┘        │
│                                                               │
│  ⚠️  WARNINGS (12)                                           │
│  ┌─────────────────────────────────────────────────┐        │
│  │ ⚠️  Item "steel_pickaxe" - No recipe defined     │        │
│  │    [Dismiss] [Create Recipe]                     │        │
│  ├─────────────────────────────────────────────────┤        │
│  │ ⚠️  Recipe "alchemy_elixir_3" - Inefficient grid │        │
│  │    (uses 7x7 but only needs 5x5)                │        │
│  │    [Dismiss] [Optimize]                          │        │
│  └─────────────────────────────────────────────────┘        │
│                                                               │
│  💡 SUGGESTIONS (Show All ▼)                                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. VALIDATION ENGINE

### 7.1 Validation Levels

#### Level 1: Schema Validation
- Check required fields present
- Validate field types
- Check enum values
- Validate numeric ranges

#### Level 2: Cross-Reference Validation
- Verify all referenced IDs exist
- Check bidirectional references
- Validate reference types

#### Level 3: Business Logic Validation
- Tier consistency
- Level requirements
- Grid size matching
- Material count matching

#### Level 4: Data Integrity
- No duplicate IDs
- Consistent naming conventions
- Balanced stats
- Logical progression

### 7.2 Validation Rules Engine

```python
class ValidationRule:
    def __init__(self, rule_id, severity, check_fn, fix_fn=None):
        self.rule_id = rule_id
        self.severity = severity  # 'error', 'warning', 'suggestion'
        self.check_fn = check_fn
        self.fix_fn = fix_fn

# Example rules
RULES = [
    ValidationRule(
        rule_id="R001",
        severity="error",
        check_fn=lambda item: 'itemId' in item,
        fix_fn=lambda item: {**item, 'itemId': generate_id(item)}
    ),
    ValidationRule(
        rule_id="R002",
        severity="error",
        check_fn=lambda recipe: exists_in_db('items', recipe['outputId']),
        fix_fn=None  # Manual fix required
    ),
    ValidationRule(
        rule_id="R003",
        severity="warning",
        check_fn=lambda item: has_recipe(item['itemId']),
        fix_fn=lambda item: create_basic_recipe(item)
    ),
    # ... 100+ rules
]
```

### 7.3 Auto-Fix Capabilities

#### Automatic Fixes:
1. Generate missing IDs
2. Add default metadata
3. Fix casing issues
4. Normalize whitespace
5. Add missing required fields with defaults
6. Optimize grid sizes

#### Semi-Automatic Fixes (with confirmation):
1. Create missing referenced items
2. Update cross-references
3. Rebalance stats
4. Merge duplicate entries

#### Manual Fixes Required:
1. Design decisions (which material to use)
2. Narrative/description text
3. Complex balance changes

---

## 8. TEMPLATE SYSTEM

### 8.1 Template Categories

#### 8.1.1 Item Templates

**Weapon Template:**
```json
{
  "template_id": "basic_weapon",
  "variables": {
    "material": {"type": "string", "options": ["copper", "iron", "steel", "mithril"]},
    "weapon_type": {"type": "string", "options": ["sword", "axe", "mace", "dagger"]},
    "tier": {"type": "integer", "range": [1, 4]},
    "rarity": {"type": "string", "default": "common"}
  },
  "generation": {
    "itemId": "${material}_${weapon_type}",
    "name": "${Material} ${Weapon_Type}",
    "category": "weapon",
    "type": "${weapon_type}",
    "tier": "${tier}",
    "rarity": "${rarity}",
    "statMultipliers": {
      "damage": "tier_multiplier(${tier})",
      "weight": "material_weight(${material})"
    },
    "requirements": {
      "level": "tier_level_requirement(${tier})"
    },
    "narrative": "generate_narrative('weapon', ${material}, ${weapon_type})"
  }
}
```

**Armor Template:**
```json
{
  "template_id": "basic_armor",
  "variables": {
    "material": {"type": "string", "options": ["leather", "iron", "steel", "mithril"]},
    "slot": {"type": "string", "options": ["helmet", "chestplate", "leggings", "boots"]},
    "tier": {"type": "integer", "range": [1, 4]}
  },
  "generation": {
    "itemId": "${material}_${slot}",
    "name": "${Material} ${Slot}",
    "category": "armor",
    "type": "armor",
    "subtype": "${slot}",
    "tier": "${tier}",
    "statMultipliers": {
      "defense": "tier_multiplier(${tier})",
      "weight": "armor_weight(${material}, ${slot})"
    }
  }
}
```

#### 8.1.2 Recipe Templates

**Smithing Recipe Template:**
```json
{
  "template_id": "smithing_equipment",
  "variables": {
    "output_item": {"type": "item_reference"},
    "materials": {"type": "array", "item_type": "material_reference"}
  },
  "generation": {
    "recipeId": "smithing_${output_item.itemId}",
    "outputId": "${output_item.itemId}",
    "outputQty": 1,
    "stationTier": "${output_item.tier}",
    "stationType": "smithing",
    "gridSize": "tier_to_gridsize(${output_item.tier})",
    "inputs": "${materials}",
    "miniGame": {
      "type": "smithing",
      "difficulty": "tier_to_difficulty(${output_item.tier})",
      "baseTime": "calculate_craft_time(${output_item.tier}, ${materials.length})"
    }
  }
}
```

#### 8.1.3 Quest Templates

**Gathering Quest Template:**
```json
{
  "template_id": "gathering_quest",
  "variables": {
    "item": {"type": "item_reference"},
    "quantity": {"type": "integer", "range": [1, 20]},
    "npc": {"type": "npc_reference"},
    "reward_xp": {"type": "integer", "calculated": "quantity * 20"}
  },
  "generation": {
    "quest_id": "gather_${item.itemId}_${quantity}",
    "title": "Gather ${item.name}",
    "description": "${npc.name} needs ${quantity} ${item.name}",
    "npc_id": "${npc.npc_id}",
    "objectives": {
      "type": "gather",
      "items": [{"item_id": "${item.itemId}", "quantity": "${quantity}"}]
    },
    "rewards": {
      "experience": "${reward_xp}",
      "items": "generate_appropriate_rewards(${item.tier})"
    }
  }
}
```

### 8.2 Template Functions

```python
def tier_multiplier(tier: int) -> float:
    """Get damage/defense multiplier for tier"""
    return {1: 1.0, 2: 2.0, 3: 4.0, 4: 8.0}[tier]

def tier_to_gridsize(tier: int) -> str:
    """Map tier to grid size"""
    return {1: "3x3", 2: "5x5", 3: "7x7", 4: "9x9"}[tier]

def tier_level_requirement(tier: int) -> int:
    """Calculate level requirement from tier"""
    return (tier - 1) * 5

def material_weight(material: str) -> float:
    """Get weight multiplier for material"""
    weights = {
        "copper": 1.0,
        "iron": 1.2,
        "steel": 1.5,
        "mithril": 0.8  # Magical light metal
    }
    return weights.get(material, 1.0)

def generate_narrative(item_type: str, material: str, subtype: str) -> str:
    """Generate flavor text for item"""
    templates = {
        "weapon": [
            f"A {material} {subtype} forged with care.",
            f"The {material} gleams with deadly intent.",
            f"A reliable {material} {subtype} for any warrior."
        ]
    }
    return random.choice(templates.get(item_type, ["A well-crafted item."]))

def calculate_craft_time(tier: int, material_count: int) -> int:
    """Calculate base crafting time in seconds"""
    base_time = 30
    tier_multiplier = tier * 1.5
    material_multiplier = material_count * 0.2
    return int(base_time * tier_multiplier * material_multiplier)
```

### 8.3 Batch Generation Examples

#### Generate Weapon Series:
```python
# Input
materials = ["copper", "iron", "steel", "mithril"]
weapon_type = "sword"

# Output (4 items + 4 recipes + 4 placements)
copper_sword (T1, common)
iron_sword (T2, common)
steel_sword (T3, uncommon)
mithril_sword (T4, rare)
```

#### Generate Armor Set:
```python
# Input
material = "iron"
slots = ["helmet", "chestplate", "leggings", "boots"]

# Output (4 items)
iron_helmet
iron_chestplate
iron_leggings
iron_boots
```

#### Generate Progression Chain:
```python
# Input
skill = "miners_fury"
evolution_count = 3

# Output (3 skills with increasing power)
miners_fury (T1, common)
  → titans_excavation (T2, uncommon)
    → earthquake_strike (T3, rare)
```

---

## 9. AUTOMATION API

### 9.1 REST API Endpoints

#### Items
```
POST   /api/items/create
GET    /api/items/{itemId}
PUT    /api/items/{itemId}
DELETE /api/items/{itemId}
GET    /api/items?category={cat}&tier={t}&rarity={r}
POST   /api/items/batch-create
```

#### Recipes
```
POST   /api/recipes/create
GET    /api/recipes/{recipeId}
PUT    /api/recipes/{recipeId}
DELETE /api/recipes/{recipeId}
GET    /api/recipes?stationType={type}&tier={t}
POST   /api/recipes/generate-from-item
```

#### Placements
```
POST   /api/placements/create
GET    /api/placements/{recipeId}
PUT    /api/placements/{recipeId}
POST   /api/placements/auto-generate
```

#### Quests
```
POST   /api/quests/create
GET    /api/quests/{questId}
PUT    /api/quests/{questId}
POST   /api/quests/generate-chain
```

#### Skills
```
POST   /api/skills/create
GET    /api/skills/{skillId}
POST   /api/skills/generate-evolution
```

#### Validation
```
GET    /api/validate/all
GET    /api/validate/{type}
GET    /api/validate/cross-references
POST   /api/validate/fix-all
```

#### Templates
```
GET    /api/templates
GET    /api/templates/{templateId}
POST   /api/templates/apply
POST   /api/templates/batch-apply
```

#### Export
```
POST   /api/export/all
POST   /api/export/{type}
POST   /api/export/production-ready
GET    /api/export/diff
```

### 9.2 API Request/Response Examples

#### Create Item:
```http
POST /api/items/create
Content-Type: application/json

{
  "itemId": "steel_greatsword",
  "name": "Steel Greatsword",
  "category": "weapon",
  "type": "sword",
  "subtype": "greatsword",
  "tier": 3,
  "rarity": "uncommon",
  "statMultipliers": {
    "damage": 1.4,
    "weight": 2.0
  },
  "requirements": {
    "level": 10,
    "stats": {"STR": 15}
  }
}

Response 201 Created:
{
  "success": true,
  "itemId": "steel_greatsword",
  "validation": {
    "schema_valid": true,
    "cross_refs_valid": true,
    "warnings": []
  },
  "generated_fields": {
    "stackSize": 1,
    "flags": {
      "stackable": false,
      "placeable": false,
      "repairable": true
    }
  }
}
```

#### Batch Create Weapon Series:
```http
POST /api/items/batch-create
Content-Type: application/json

{
  "template": "basic_weapon",
  "series": {
    "materials": ["copper", "iron", "steel", "mithril"],
    "weapon_type": "axe"
  },
  "options": {
    "auto_create_recipes": true,
    "auto_create_placements": true
  }
}

Response 201 Created:
{
  "success": true,
  "items_created": 4,
  "recipes_created": 4,
  "placements_created": 4,
  "items": [
    {"itemId": "copper_axe", "tier": 1},
    {"itemId": "iron_axe", "tier": 2},
    {"itemId": "steel_axe", "tier": 3},
    {"itemId": "mithril_axe", "tier": 4}
  ]
}
```

#### Validate All:
```http
GET /api/validate/all

Response 200 OK:
{
  "summary": {
    "total_items": 247,
    "valid": 234,
    "warnings": 12,
    "errors": 3
  },
  "errors": [
    {
      "rule_id": "R002",
      "severity": "error",
      "type": "recipe",
      "id": "smithing_titanium_blade",
      "message": "outputId 'titanium_blade' does not exist",
      "fix_suggestions": [
        {"action": "create_item", "params": {"itemId": "titanium_blade"}},
        {"action": "change_output", "params": {}}
      ]
    }
  ],
  "warnings": [...],
  "suggestions": [...]
}
```

### 9.3 AI Integration Hooks

#### LLM Content Generation:
```python
@app.post("/api/ai/generate-narrative")
async def generate_narrative(
    item_type: str,
    item_id: str,
    context: Dict
) -> str:
    """Use LLM to generate flavor text"""
    prompt = f"""
    Generate a 1-2 sentence narrative description for this item:
    Type: {item_type}
    ID: {item_id}
    Context: {json.dumps(context)}

    Style: Fantasy RPG, slightly humorous
    """
    return await llm_client.complete(prompt)

@app.post("/api/ai/suggest-recipe")
async def suggest_recipe(output_item_id: str) -> Dict:
    """Use LLM to suggest recipe inputs"""
    item = get_item(output_item_id)
    prompt = f"""
    Suggest crafting materials for {item['name']}:
    - Tier {item['tier']}
    - Type: {item['category']}/{item['type']}

    Available materials: {get_materials_by_tier(item['tier'])}

    Return JSON: {{"inputs": [{{"materialId": "...", "quantity": N}}]}}
    """
    return await llm_client.complete_json(prompt)

@app.post("/api/ai/balance-stats")
async def balance_stats(items: List[Dict]) -> List[Dict]:
    """Use LLM to analyze and balance item stats"""
    prompt = f"""
    Analyze these items for balance issues:
    {json.dumps(items, indent=2)}

    Check:
    - Damage progression across tiers
    - Price vs power ratio
    - Tier consistency

    Suggest adjustments as JSON array.
    """
    return await llm_client.complete_json(prompt)
```

### 9.4 Webhook System

```python
# Register webhooks for external systems
@app.post("/api/webhooks/register")
async def register_webhook(
    event_type: str,  # 'item_created', 'validation_failed', etc.
    url: str,
    secret: str
):
    """Register webhook for external notifications"""
    pass

# Example webhook payload
{
  "event": "item_created",
  "timestamp": "2025-11-21T10:30:00Z",
  "data": {
    "itemId": "steel_greatsword",
    "category": "weapon",
    "tier": 3
  },
  "signature": "sha256_hmac_signature"
}
```

---

## 10. IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Weeks 1-2)
**Goal**: Build core infrastructure

- [ ] Set up project structure (React + FastAPI)
- [ ] Create Pydantic models for all JSON schemas
- [ ] Implement file-based data store + SQLite indexing
- [ ] Build basic CRUD API endpoints
- [ ] Create simple validation engine (schema-only)
- [ ] Build dashboard UI with stats overview

**Deliverable**: Basic system that can load/save JSON files with schema validation

---

### Phase 2: Core Features (Weeks 3-5)
**Goal**: Add creation, validation, and basic editing

- [ ] Implement Creator View for all JSON types
- [ ] Add cross-reference validation
- [ ] Build search functionality
- [ ] Create template system (5-10 basic templates)
- [ ] Implement batch operations
- [ ] Add export functionality

**Deliverable**: Functional creator with validation and templates

---

### Phase 3: Visual Tools (Weeks 6-7)
**Goal**: Extend grid designer, add visual editors

- [ ] Refactor existing smithing grid designer into React
- [ ] Extend to support all placement formats (hub-spoke, sequential, slot-based)
- [ ] Add drag-and-drop support
- [ ] Create dependency graph visualizer
- [ ] Build stat calculator/preview

**Deliverable**: Visual editors for complex data types

---

### Phase 4: Automation (Weeks 8-9)
**Goal**: Add AI integration and advanced automation

- [ ] Integrate LLM for narrative generation
- [ ] Add AI-powered recipe suggestions
- [ ] Implement stat balancing AI
- [ ] Create webhook system
- [ ] Build CLI tool for automation
- [ ] Add git integration for version control

**Deliverable**: AI-powered content generation

---

### Phase 5: Polish & Testing (Weeks 10-12)
**Goal**: Refine UX, add advanced features

- [ ] Implement search & replace
- [ ] Add data migration tools
- [ ] Create comprehensive test suite
- [ ] Write documentation
- [ ] Add keyboard shortcuts
- [ ] Implement undo/redo
- [ ] Add dark mode
- [ ] Performance optimization

**Deliverable**: Production-ready unified creator system

---

## 11. TECHNICAL SPECIFICATIONS

### 11.1 Technology Stack

#### Frontend:
- **Framework**: React 18 + TypeScript
- **UI Library**: TailwindCSS + HeadlessUI
- **State Management**: Zustand or Redux Toolkit
- **Forms**: React Hook Form + Zod validation
- **Grid**: React Grid Layout (for placement editor)
- **Charts**: Recharts (for stats/analytics)

#### Backend:
- **Framework**: FastAPI (Python 3.10+)
- **Validation**: Pydantic v2
- **Database**: SQLite (indexing) + JSON files (source of truth)
- **Testing**: Pytest
- **API Docs**: Auto-generated (FastAPI/Swagger)

#### Tooling:
- **Build**: Vite (frontend), Poetry (backend)
- **Linting**: ESLint, Prettier, Black, Ruff
- **Git Hooks**: Pre-commit for validation
- **CI/CD**: GitHub Actions

### 11.2 File Structure

```
unified-json-creator/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard/
│   │   │   ├── Creator/
│   │   │   ├── VisualEditor/
│   │   │   ├── Validation/
│   │   │   └── Common/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   └── utils/
│   ├── public/
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── items.py
│   │   │   ├── recipes.py
│   │   │   ├── validation.py
│   │   │   └── ...
│   │   ├── models/
│   │   ├── services/
│   │   ├── templates/
│   │   └── utils/
│   ├── tests/
│   └── pyproject.toml
├── data/
│   ├── items/
│   ├── recipes/
│   ├── placements/
│   ├── progression/
│   └── index.db
├── docs/
│   ├── API.md
│   ├── USER_GUIDE.md
│   └── SCHEMAS.md
└── README.md
```

### 11.3 Performance Targets

- **Load Time**: < 2s for full dataset
- **Search**: < 100ms for keyword search
- **Validation**: < 5s for full validation
- **Export**: < 10s for all JSON files
- **API Response**: < 200ms (95th percentile)

### 11.4 Security Considerations

- Input sanitization for all user data
- SQL injection prevention (parameterized queries)
- XSS prevention (React auto-escaping)
- CSRF tokens for API calls
- Rate limiting on API endpoints
- Webhook signature verification
- File upload size limits
- JSON bomb protection (depth/size limits)

---

## 12. CONCLUSION

This specification provides a **comprehensive blueprint** for building a unified JSON creator system that:

✅ **Handles all 10+ JSON types** in your game
✅ **Provides human-friendly interfaces** for creation and editing
✅ **Validates data integrity** with 100+ rules
✅ **Supports batch operations** via templates
✅ **Offers visual editors** for complex data
✅ **Enables automation** through REST API
✅ **Integrates AI** for content generation
✅ **Maintains data consistency** across all files

### Next Steps:

1. **Review this specification** - Identify any missing requirements
2. **Prioritize features** - Which phases are most critical?
3. **Set up development environment** - Tools, repos, CI/CD
4. **Begin Phase 1** - Build foundation infrastructure

This system will transform your JSON workflow from **manual, error-prone file editing** to a **streamlined, validated, and automated content creation pipeline**.

---

**Document Version**: 1.0
**Author**: Claude (Anthropic)
**Date**: 2025-11-21
**Status**: Draft for Review
