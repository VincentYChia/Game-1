# JSON Exploration Report
**Generated**: 2026-01-09
**Purpose**: Document current JSON structure for LLM generation templates

---

## Directory Structure

```
Game-1-modular/
├── items.JSON/              # Item definitions
│   ├── items-materials-1.JSON
│   ├── items-smithing-1.JSON
│   ├── items-smithing-2.JSON
│   ├── items-alchemy-1.JSON
│   ├── items-refining-1.JSON
│   ├── items-tools-1.JSON
│   ├── items-engineering-1.JSON
│   └── items-testing-tags.JSON
├── recipes.JSON/            # Crafting recipes
│   ├── recipes-smithing-3.JSON
│   ├── recipes-alchemy-1.JSON
│   ├── recipes-refining-1.JSON
│   ├── recipes-engineering-1.JSON
│   ├── recipes-adornments-1.json
│   └── recipes-testing-*.JSON
├── placements.JSON/         # Minigame grid layouts
│   ├── placements-smithing-1.JSON
│   ├── placements-alchemy-1.JSON
│   ├── placements-refining-1.JSON
│   ├── placements-engineering-1.JSON
│   └── placements-enchanting-1.JSON
├── Skills/                  # Skill definitions
│   ├── skills-skills-1.JSON
│   └── skills-testing-*.JSON
├── progression/             # Character progression
│   ├── classes-1.JSON
│   └── titles-1.JSON
└── Definitions.JSON/        # Game systems config
    ├── combat-config.JSON
    ├── hostiles-1.JSON
    ├── Resource-node-1.JSON
    ├── stats-calculations.JSON
    └── value-translation-table-1.JSON
```

---

## Database Loading System

All content loads through singleton database classes:

| Database | Root Key | ID Field | Files Loaded |
|----------|----------|----------|--------------|
| **MaterialDatabase** | `materials` | `materialId` | items-materials-1.JSON |
| **MaterialDatabase (refining)** | Items scan | `itemId` | items-refining-1.JSON |
| **EquipmentDatabase** | Section scan | `itemId` | items-smithing-*.JSON, items-tools-1.JSON |
| **RecipeDatabase** | `recipes` | `recipeId` | recipes-*.JSON |
| **SkillDatabase** | `skills` | `skillId` | skills-skills-1.JSON |
| **TitleDatabase** | `titles` | `titleId` | titles-1.JSON |
| **ClassDatabase** | `classes` | `classId` | classes-1.JSON |
| **PlacementDatabase** | `placements` | `recipeId` | placements-*.JSON |

---

## JSON Schema Structures

### 1. Materials (items-materials-1.JSON)

**Root Key**: `materials`
**ID Field**: `materialId`

```json
{
  "materials": [
    {
      "materialId": "iron_ore",
      "name": "Iron Ore",
      "tier": 1,
      "category": "ore",
      "rarity": "common",
      "stackSize": 100,
      "iconPath": "materials/iron_ore.png"
    }
  ]
}
```

**Field Reference**:
- `materialId` (string, required): Unique identifier (snake_case)
- `name` (string, required): Display name
- `tier` (int, 1-4): Material tier (T1-T4)
- `category` (string): `ore`, `wood`, `stone`, `herb`, `essence`
- `rarity` (string): `common`, `uncommon`, `rare`, `legendary`
- `stackSize` (int): Max stack size (default: 100)
- `iconPath` (string): Path to icon (auto-generated if missing)

---

### 2. Equipment (items-smithing-1.JSON, items-smithing-2.JSON)

**Root Key**: Sections like `weapons`, `armor`, `tools`
**ID Field**: `itemId`

```json
{
  "weapons": [
    {
      "itemId": "iron_sword",
      "name": "Iron Sword",
      "tier": 1,
      "equipSlot": "main_hand",
      "baseDamage": 25,
      "attackSpeed": 1.0,
      "durability": 200,
      "weight": 5.0,
      "handType": "one_handed",
      "tags": ["melee", "physical", "slashing"],
      "iconPath": "weapons/iron_sword.png"
    }
  ],
  "armor": [
    {
      "itemId": "iron_helmet",
      "name": "Iron Helmet",
      "tier": 1,
      "equipSlot": "head",
      "defense": 15,
      "durability": 150,
      "weight": 3.0,
      "tags": ["armor", "heavy"],
      "iconPath": "armor/iron_helmet.png"
    }
  ]
}
```

**Weapon Fields**:
- `itemId`, `name`, `tier`, `iconPath` (standard)
- `equipSlot`: `main_hand`, `off_hand`
- `baseDamage` (int): Base weapon damage
- `attackSpeed` (float): Attack speed multiplier
- `handType`: `one_handed`, `two_handed`
- `durability` (int): Max durability
- `weight` (float): Encumbrance weight
- `tags` (array): Combat tags (see Tag System below)

**Armor Fields**:
- `itemId`, `name`, `tier`, `iconPath` (standard)
- `equipSlot`: `head`, `chest`, `legs`, `feet`, `hands`
- `defense` (int): Armor defense value
- `durability`, `weight`, `tags`

---

### 3. Recipes (recipes-smithing-3.JSON, recipes-alchemy-1.JSON)

**Root Key**: `recipes`
**ID Field**: `recipeId`

**Standard Format** (Smithing, Alchemy):
```json
{
  "recipes": [
    {
      "recipeId": "smithing_iron_sword_001",
      "outputId": "iron_sword",
      "outputQty": 1,
      "stationType": "smithing",
      "stationTier": 1,
      "inputs": [
        {"materialId": "iron_ingot", "qty": 3},
        {"materialId": "oak_plank", "qty": 1}
      ]
    }
  ]
}
```

**Refining Format** (recipes-refining-1.JSON):
```json
{
  "recipes": [
    {
      "recipeId": "refining_iron_ingot_001",
      "outputs": [
        {"materialId": "iron_ingot", "quantity": 2}
      ],
      "stationType": "refining",
      "stationTier": 1,
      "coreInputs": [
        {"materialId": "iron_ore", "quantity": 3}
      ],
      "surroundingInputs": [
        {"materialId": "coal", "quantity": 1}
      ]
    }
  ]
}
```

**Enchanting Format** (recipes-adornments-1.json):
```json
{
  "recipes": [
    {
      "recipeId": "enchanting_sharpness_001",
      "enchantmentId": "sharpness",
      "stationType": "enchanting",
      "stationTier": 1,
      "inputs": [
        {"materialId": "arcane_essence", "qty": 5}
      ]
    }
  ]
}
```

**Field Reference**:
- `recipeId` (string, required): Unique recipe ID
- `outputId` (string): Item produced (smithing/alchemy)
- `enchantmentId` (string): Enchantment produced (enchanting)
- `outputs` (array): Multiple outputs (refining)
- `outputQty` / `quantity` (int): Amount produced
- `stationType`: `smithing`, `alchemy`, `refining`, `engineering`, `enchanting`
- `stationTier` (int, 1-4): Required crafting station tier
- `inputs` (array): Standard input materials
- `coreInputs` (array): Refining center slot materials
- `surroundingInputs` (array): Refining surrounding slot materials

---

### 4. Placements (placements-smithing-1.JSON)

**Root Key**: `placements`
**ID Field**: `recipeId` (links to recipe)

**Smithing Format** (grid-based):
```json
{
  "placements": [
    {
      "recipeId": "smithing_iron_sword_001",
      "gridSize": 5,
      "placements": {
        "iron_ingot": [[2, 1], [2, 2], [2, 3]],
        "oak_plank": [[2, 4]]
      }
    }
  ]
}
```

**Alchemy Format** (sequence-based):
```json
{
  "placements": [
    {
      "recipeId": "alchemy_health_potion_001",
      "sequence": [
        {"slot": 0, "materialId": "healing_herb"},
        {"slot": 1, "materialId": "spring_water"},
        {"slot": 2, "materialId": "honey"}
      ]
    }
  ]
}
```

**Refining Format** (hub-and-spoke):
```json
{
  "placements": [
    {
      "recipeId": "refining_iron_ingot_001",
      "coreSlot": {"materialId": "iron_ore"},
      "surroundingSlots": [
        {"position": 0, "materialId": "coal"},
        {"position": 2, "materialId": "coal"}
      ]
    }
  ]
}
```

**Engineering Format** (slot-type):
```json
{
  "placements": [
    {
      "recipeId": "engineering_iron_trap_001",
      "slots": [
        {"slotType": "frame", "materialId": "iron_ingot"},
        {"slotType": "mechanism", "materialId": "copper_gear"},
        {"slotType": "trigger", "materialId": "spring"}
      ]
    }
  ]
}
```

**Enchanting Format** (pattern-based):
```json
{
  "placements": [
    {
      "recipeId": "enchanting_sharpness_001",
      "pattern": "cross",
      "placementMap": {
        "center": "arcane_essence",
        "north": "diamond_dust",
        "south": "diamond_dust",
        "east": "diamond_dust",
        "west": "diamond_dust"
      }
    }
  ]
}
```

---

### 5. Skills (skills-skills-1.JSON)

**Root Key**: `skills`
**ID Field**: `skillId`

```json
{
  "skills": [
    {
      "skillId": "miners_fury",
      "name": "Miner's Fury",
      "tier": 1,
      "discipline": "mining",
      "maxLevel": 10,
      "manaCost": 50,
      "cooldown": 120,
      "effectType": "empower",
      "effectTags": ["mining", "damage", "buff"],
      "effectParams": {
        "damageMultiplier": 1.5,
        "duration": 30.0,
        "radius": 0
      },
      "tags": ["mining", "physical", "buff"],
      "iconPath": "skills/miners_fury.png"
    }
  ]
}
```

**Field Reference**:
- `skillId`, `name`, `tier` (standard)
- `discipline`: `combat`, `mining`, `forestry`, `smithing`, `alchemy`, `universal`
- `maxLevel` (int): Max skill level (usually 10)
- `manaCost` (int): Mana required to activate
- `cooldown` (int): Cooldown in seconds
- `effectType`: `empower`, `restore`, `quicken`, `fortify`, `pierce`, etc.
- `effectTags` (array): Tags describing effects
- `effectParams` (object): Effect-specific parameters
- `tags` (array): Skill classification tags

---

### 6. Classes (classes-1.JSON)

**Root Key**: `classes`
**ID Field**: `classId`

```json
{
  "classes": [
    {
      "classId": "warrior",
      "name": "Warrior",
      "description": "Masters of melee combat",
      "tags": ["warrior", "melee", "physical", "tanky"],
      "startingBonuses": {
        "baseHP": 30,
        "meleeDamage": 0.10
      },
      "recommendedStats": ["STR", "VIT", "DEF"],
      "startingSkill": "battle_rage",
      "iconPath": "classes/warrior.png"
    }
  ]
}
```

**Field Reference**:
- `classId`, `name`, `description` (standard)
- `tags` (array): Class classification tags (used for skill affinity)
- `startingBonuses` (object): Initial stat bonuses (camelCase keys)
- `recommendedStats` (array): Suggested stat allocation
- `startingSkill` (string): Free skill at character creation
- `iconPath` (string)

---

### 7. Titles (titles-1.JSON)

**Root Key**: `titles`
**ID Field**: `titleId`

```json
{
  "titles": [
    {
      "titleId": "novice_miner",
      "name": "Novice Miner",
      "tier": "novice",
      "discipline": "mining",
      "requirement": {
        "type": "mining_exp",
        "value": 100
      },
      "bonuses": {
        "miningDamage": 0.05,
        "pickaxeEfficiency": 0.03
      },
      "iconPath": "titles/novice_miner.png"
    }
  ]
}
```

**Field Reference**:
- `titleId`, `name` (standard)
- `tier`: `novice`, `apprentice`, `journeyman`, `expert`, `master`
- `discipline`: Matching discipline or `universal`
- `requirement` (object): Unlock conditions
  - `type`: `mining_exp`, `combat_kills`, `crafted_items`, etc.
  - `value` (int): Required amount
- `bonuses` (object): Stat bonuses (camelCase keys)
- `iconPath` (string)

---

### 8. Hostiles (hostiles-1.JSON)

**Root Key**: `hostiles` or `enemies`
**ID Field**: `enemyId`

```json
{
  "hostiles": [
    {
      "enemyId": "grey_wolf",
      "name": "Grey Wolf",
      "tier": 1,
      "baseHP": 100,
      "baseMana": 0,
      "meleeDamage": 15,
      "defense": 5,
      "moveSpeed": 1.2,
      "aggroRange": 8.0,
      "behavior": "wander",
      "aggroOnDamage": true,
      "aggroOnProximity": true,
      "fleeAtHealth": 0.2,
      "abilities": [],
      "lootTable": [
        {"itemId": "wolf_pelt", "dropChance": 0.5, "minQty": 1, "maxQty": 2},
        {"itemId": "raw_meat", "dropChance": 0.8, "minQty": 1, "maxQty": 3}
      ],
      "tags": ["beast", "physical", "agile"],
      "iconPath": "enemies/grey_wolf.png"
    }
  ]
}
```

**Field Reference**:
- `enemyId`, `name`, `tier` (standard)
- `baseHP`, `baseMana` (int): Base stats
- `meleeDamage` (int): Base damage
- `defense` (int): Damage reduction
- `moveSpeed` (float): Movement speed multiplier
- `aggroRange` (float): Detection radius
- `behavior`: `idle`, `wander`, `patrol`
- `aggroOnDamage`, `aggroOnProximity` (bool): Aggro triggers
- `fleeAtHealth` (float, 0.0-1.0): Health % to flee
- `abilities` (array): Special ability IDs
- `lootTable` (array): Drop definitions
- `tags` (array): Enemy classification tags

---

## Tag System Reference

Tags are used for:
1. **Combat effects** (damage types, geometry, status effects)
2. **Skill affinity** (class-skill matching)
3. **Equipment bonuses** (tag-based stat modifiers)
4. **Item classification** (filtering, categorization)

### Damage Type Tags
`physical`, `fire`, `ice`, `lightning`, `poison`, `arcane`, `shadow`, `holy`

### Geometry Tags
`single`, `chain`, `cone`, `circle`, `beam`, `pierce`, `bounce`

### Status Effect Tags
`burn`, `bleed`, `poison`, `freeze`, `chill`, `stun`, `root`, `shock`, `slow`

### Special Behavior Tags
`knockback`, `pull`, `lifesteal`, `execute`, `critical`, `reflect`, `cleave`

### Class/Skill Tags
`warrior`, `ranger`, `scholar`, `artisan`, `scavenger`, `melee`, `ranged`, `magic`, `crafting`, `gathering`, `nature`, `tanky`, `agile`

### Discipline Tags
`mining`, `forestry`, `smithing`, `alchemy`, `refining`, `engineering`, `enchanting`, `combat`

---

## Field Naming Conventions

### JSON (camelCase)
Used in all JSON files:
- `itemId`, `skillId`, `recipeId`, `materialId`
- `baseDamage`, `attackSpeed`, `moveSpeed`
- `meleeDamage`, `baseHP`, `baseMana`
- `outputQty`, `stackSize`, `iconPath`

### Python (snake_case)
Used in all Python code:
- `item_id`, `skill_id`, `recipe_id`, `material_id`
- `base_damage`, `attack_speed`, `move_speed`
- `melee_damage`, `base_hp`, `base_mana`
- `output_qty`, `stack_size`, `icon_path`

**Note**: Database loaders automatically convert camelCase → snake_case

---

## Current Inconsistencies (For Reference)

### ID Field Variations
- Materials: `materialId`
- Equipment/Items: `itemId`
- Refining items: `itemId` (not `materialId`)
- Recipes: `recipeId`, `outputId`, `enchantmentId`
- Skills: `skillId`
- Classes: `classId`

### File Extension Variations
- Most files: `.JSON` (uppercase)
- Some files: `.json` (lowercase)
- Example: `recipes-smithing-3.JSON` vs `recipes-adornments-1.json`

### Recipe Output Field Variations
- Standard: `outputId` + `outputQty`
- Refining: `outputs[]` array
- Enchanting: `enchantmentId`

---

## Database Bonus Field Mapping

Common camelCase → snake_case mappings in databases:

```
miningDamage → mining_damage
meleeDamage → melee_damage
forestryDamage → forestry_damage
craftingTime → crafting_time
firstTryBonus → first_try_bonus
pickaxeEfficiency → pickaxe_efficiency
axeEfficiency → axe_efficiency
baseHP → max_health
baseMana → max_mana
moveSpeed → move_speed
attackSpeed → attack_speed
damageReduction → damage_reduction
inventorySlots → inventory_slots
```

---

## Files by Purpose

### Core Item Data
- `items-materials-1.JSON` - Raw materials (ores, wood, herbs)
- `items-refining-1.JSON` - Processed materials (ingots, planks)
- `items-smithing-1.JSON` - Weapons and armor
- `items-smithing-2.JSON` - More equipment
- `items-alchemy-1.JSON` - Potions and consumables
- `items-engineering-1.JSON` - Devices and machines
- `items-tools-1.JSON` - Placeable crafting stations

### Crafting Recipes
- `recipes-smithing-3.JSON` - Current smithing recipes
- `recipes-alchemy-1.JSON` - Alchemy recipes
- `recipes-refining-1.JSON` - Material processing
- `recipes-engineering-1.JSON` - Device crafting
- `recipes-adornments-1.json` - Enchantments

### Minigame Layouts
- `placements-smithing-1.JSON` - Grid placements
- `placements-alchemy-1.JSON` - Sequence placements
- `placements-refining-1.JSON` - Hub-spoke placements
- `placements-engineering-1.JSON` - Slot placements
- `placements-enchanting-1.JSON` - Pattern placements

### Character Progression
- `classes-1.JSON` - Starting classes
- `titles-1.JSON` - Achievement titles
- `skills-skills-1.JSON` - All skills

### Game Systems
- `combat-config.JSON` - Combat and spawning config
- `hostiles-1.JSON` - Enemy definitions
- `Resource-node-1.JSON` - Gatherable resources
- `stats-calculations.JSON` - Stat formulas
- `value-translation-table-1.JSON` - Value mappings

---

## Next Steps for LLM Generation Templates

This report provides the foundation for creating LLM generation templates. Areas to define:

1. **Item generation templates** (materials, equipment, consumables)
2. **Recipe generation templates** (per discipline)
3. **Placement generation templates** (per minigame type)
4. **Skill generation templates** (per discipline)
5. **Enemy generation templates** (per tier)
6. **Class/Title generation templates** (progression system)

Each template should include:
- Required fields with types
- Optional fields with defaults
- Validation rules
- Example outputs
- Tag recommendations
- Balance guidelines
