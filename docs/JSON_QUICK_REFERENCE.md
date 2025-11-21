# JSON Quick Reference Guide

## Quick Navigation by Need

**"I want to create a..."**
- [New weapon/armor/tool](#creating-items) → Items JSON
- [Crafting recipe](#creating-recipes) → Recipes JSON
- [Recipe placement pattern](#creating-placements) → Placements JSON
- [Quest](#creating-quests) → Quests JSON
- [NPC](#creating-npcs) → NPCs JSON
- [Skill/ability](#creating-skills) → Skills JSON
- [Character class](#creating-classes) → Classes JSON
- [Enemy](#creating-enemies) → Hostiles JSON

---

## JSON Type Summary

| Type | Location | Count | Depends On | Size |
|------|----------|-------|------------|------|
| **Items** | `items.JSON/*.JSON` | 247 | Materials | 101KB |
| **Recipes** | `recipes.JSON/*.JSON` | 112 | Items, Materials | 132KB |
| **Placements** | `placements.JSON/*.JSON` | 112 | Recipes, Materials | 170KB |
| **NPCs** | `progression/npcs-*.JSON` | 8 | Quests | 15KB |
| **Quests** | `progression/quests-*.JSON` | 15 | NPCs, Items, Skills, Titles | 22KB |
| **Skills** | `Skills/skills-*.JSON` | 30 | None | 42KB |
| **Classes** | `progression/classes-1.JSON` | 6 | Skills | 8KB |
| **Titles** | `progression/titles-1.JSON` | 45 | None | 18KB |
| **Enemies** | `Definitions.JSON/hostiles-1.JSON` | 12 | Materials | 25KB |
| **Nodes** | `Definitions.JSON/resource-node-1.JSON` | 18 | Materials | 12KB |

---

## Creating Items

### Minimal Item Example:
```json
{
  "itemId": "iron_sword",
  "name": "Iron Sword",
  "category": "weapon",
  "tier": 2,
  "rarity": "common"
}
```

### Full Item Example:
```json
{
  "metadata": {
    "narrative": "A sturdy iron blade.",
    "tags": ["weapon", "sword", "tier2"]
  },
  "itemId": "iron_sword",
  "name": "Iron Sword",
  "category": "weapon",
  "type": "sword",
  "subtype": "longsword",
  "tier": 2,
  "rarity": "common",
  "effect": "Deals 20-30 physical damage",
  "stackSize": 1,
  "statMultipliers": {
    "damage": 1.0,
    "weight": 1.2
  },
  "requirements": {
    "level": 5,
    "stats": {"STR": 10}
  },
  "flags": {
    "stackable": false,
    "placeable": false,
    "repairable": true
  }
}
```

### Item Categories:
- `weapon` - Swords, axes, bows, etc.
- `armor` - Helmets, chestplates, etc.
- `tool` - Pickaxes, axes, fishing rods
- `consumable` - Potions, food
- `device` - Turrets, bombs, traps
- `station` - Crafting stations
- `material` - Ores, wood, crystals

### Rarities (in order):
`common` → `uncommon` → `rare` → `epic` → `legendary` → `artifact`

### Tiers:
- **Tier 1** - Starter (copper, oak)
- **Tier 2** - Basic (iron, birch)
- **Tier 3** - Advanced (steel, ironwood)
- **Tier 4** - Legendary (mithril, ebony)

---

## Creating Recipes

### Minimal Recipe:
```json
{
  "recipeId": "smithing_iron_sword",
  "outputId": "iron_sword",
  "outputQty": 1,
  "stationTier": 2,
  "stationType": "smithing",
  "inputs": [
    {"materialId": "iron_ingot", "quantity": 3},
    {"materialId": "oak_plank", "quantity": 1}
  ]
}
```

### Station Types:
- `smithing` - Weapons, armor, tools
- `alchemy` - Potions, elixirs
- `refining` - Ore to ingot conversion
- `engineering` - Devices, turrets
- `enchanting` - Item modifications

### Grid Sizes by Tier:
- Tier 1 → `3x3`
- Tier 2 → `5x5`
- Tier 3 → `7x7`
- Tier 4 → `9x9`

### Mini-Game Difficulties:
`easy` → `moderate` → `hard` → `extreme`

---

## Creating Placements

### Grid Format (Smithing/Enchanting):
```json
{
  "recipeId": "smithing_iron_sword",
  "placementMap": {
    "1,1": "iron_ingot",
    "1,2": "iron_ingot",
    "2,2": "iron_ingot",
    "3,1": "oak_plank"
  },
  "metadata": {
    "gridSize": "5x5"
  }
}
```

**Grid Coordinates**: `"row,col"` where rows and columns start at 1

### Hub-and-Spoke Format (Refining):
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

### Sequential Format (Alchemy):
```json
{
  "recipeId": "alchemy_health_potion",
  "discipline": "alchemy",
  "sequence": [
    {"step": 1, "action": "add", "materialId": "red_herb"},
    {"step": 2, "action": "heat", "duration": 5},
    {"step": 3, "action": "add", "materialId": "water_crystal"}
  ]
}
```

### Slot Format (Engineering):
```json
{
  "recipeId": "engineering_turret",
  "discipline": "engineering",
  "slots": {
    "frame": "iron_frame",
    "mechanism": "gear_assembly",
    "power": "fire_crystal"
  }
}
```

---

## Creating Quests

### Minimal Quest:
```json
{
  "quest_id": "gather_logs",
  "title": "Gather Oak Logs",
  "description": "Collect 10 oak logs",
  "npc_id": "tutorial_guide",
  "objectives": {
    "type": "gather",
    "items": [
      {"item_id": "oak_log", "quantity": 10}
    ]
  },
  "rewards": {
    "experience": 100
  }
}
```

### Quest Types:
- **gather** - Collect items
- **combat** - Kill enemies
- **craft** - Create items
- **explore** - Visit locations

### Reward Types:
- `experience` - XP points
- `health_restore` - HP recovery
- `mana_restore` - Mana recovery
- `skills` - Array of skill IDs
- `items` - Array of {item_id, quantity}
- `title` - Title ID

---

## Creating NPCs

### Minimal NPC:
```json
{
  "npc_id": "merchant",
  "name": "Village Merchant",
  "position": {"x": 50.0, "y": 50.0, "z": 0.0},
  "dialogue_lines": [
    "Welcome to my shop!",
    "What can I get you?"
  ]
}
```

### NPC with Quests:
```json
{
  "npc_id": "quest_giver",
  "name": "Elder Sage",
  "position": {"x": 48.0, "y": 48.0, "z": 0.0},
  "sprite_color": [200, 150, 255],
  "interaction_radius": 3.0,
  "dialogue_lines": [
    "Greetings, traveler.",
    "I have tasks for you."
  ],
  "quests": ["tutorial_quest", "gathering_quest"]
}
```

---

## Creating Skills

### Minimal Skill:
```json
{
  "skillId": "power_strike",
  "name": "Power Strike",
  "tier": 1,
  "rarity": "common",
  "categories": ["combat"],
  "description": "Deal massive damage with your next attack",
  "effect": {
    "type": "empower",
    "category": "damage",
    "magnitude": "major",
    "target": "enemy",
    "duration": "instant"
  },
  "cost": {
    "mana": "high",
    "cooldown": "short"
  },
  "requirements": {
    "characterLevel": 1
  }
}
```

### Effect Types:
- `empower` - Increase power/damage
- `quicken` - Increase speed
- `fortify` - Increase defense
- `pierce` - Increase critical chance
- `regenerate` - Heal over time
- `devastate` - Area damage
- `elevate` - Increase rarity/quality
- `enrich` - Increase yield
- `restore` - Instant heal
- `transcend` - Bypass restrictions

### Magnitudes:
`minor` (15%) → `moderate` (30%) → `major` (50%) → `extreme` (100%)

### Durations:
`instant` → `brief` (5s) → `moderate` (30s) → `long` (60s) → `extended` (120s)

### Cost Levels:
- Mana: `low` → `moderate` → `high` → `extreme`
- Cooldown: `short` (15s) → `moderate` (30s) → `long` (60s) → `extreme` (300s)

---

## Creating Classes

### Minimal Class:
```json
{
  "classId": "warrior",
  "name": "Warrior",
  "description": "Strong melee fighter",
  "startingBonuses": {
    "baseHP": 30,
    "meleeDamage": 0.10
  },
  "startingSkill": {
    "skillId": "power_strike",
    "skillName": "Power Strike",
    "initialLevel": 1,
    "description": "Deal bonus damage"
  },
  "recommendedStats": {
    "primary": ["STR", "VIT"]
  }
}
```

### Starting Bonuses Available:
- `baseHP` - Extra health points
- `baseMana` - Extra mana points
- `meleeDamage` - % bonus to melee
- `rangedDamage` - % bonus to ranged
- `magicDamage` - % bonus to magic
- `defense` - % bonus to defense
- `criticalChance` - % bonus to crits
- `inventorySlots` - Extra inventory space

---

## Creating Enemies

### Minimal Enemy:
```json
{
  "enemyId": "wolf",
  "name": "Wolf",
  "tier": 1,
  "category": "beast",
  "stats": {
    "health": 80,
    "damage": [8, 12],
    "defense": 5
  },
  "drops": [
    {
      "materialId": "wolf_pelt",
      "quantity": [2, 4],
      "chance": "high"
    }
  ]
}
```

### Enemy Categories:
- `beast` - Animals
- `undead` - Zombies, skeletons
- `construct` - Golems
- `elemental` - Fire/ice/lightning

### Drop Chances:
`guaranteed` → `high` (80%) → `moderate` (50%) → `low` (20%)

---

## Common Patterns & Best Practices

### ID Naming Convention:
- Use `snake_case`
- Format: `{material}_{type}` or `{category}_{name}`
- Examples: `iron_sword`, `tutorial_quest`, `miners_fury`

### Tier Consistency:
- Recipe station tier should match output item tier
- Input materials should be same or lower tier
- Quests should reward items at appropriate tier

### Cross-Reference Checklist:
✅ All `outputId` in recipes exist as items
✅ All `materialId` in recipes/placements exist
✅ All `npc_id` in quests exist as NPCs
✅ All reward items in quests exist
✅ All skill IDs referenced exist
✅ Placement material counts match recipe inputs

### Material Quantity Keywords:
- `few` = 1-3
- `several` = 3-6
- `many` = 6-10

### Quality Keywords:
- `low` = 10
- `moderate` = 25
- `high` = 50
- `extreme` = 100

---

## Stat Stats

**Available Stats**:
- `STR` - Strength (melee damage)
- `DEF` - Defense (damage reduction)
- `VIT` - Vitality (health)
- `AGI` - Agility (speed, dodge)
- `INT` - Intelligence (magic damage, crafting)
- `LCK` - Luck (crits, drops, gathering)

**Typical Stat Requirements by Tier**:
- Tier 1: 5-10
- Tier 2: 10-15
- Tier 3: 15-25
- Tier 4: 25-35

---

## File Locations Reference

```
Game-1-modular/
├── items.JSON/
│   ├── items-smithing-1.JSON (weapons, armor)
│   ├── items-smithing-2.JSON (more equipment)
│   ├── items-alchemy-1.JSON (potions)
│   ├── items-materials-1.JSON (ores, wood)
│   ├── items-refining-1.JSON (ingots)
│   └── items-tools-1.JSON (tools)
├── recipes.JSON/
│   ├── recipes-smithing-3.JSON
│   ├── recipes-alchemy-1.JSON
│   ├── recipes-refining-1.JSON
│   ├── recipes-engineering-1.JSON
│   ├── recipes-enchanting-1.JSON
│   └── recipes-adornments-1.json
├── placements.JSON/
│   ├── placements-smithing-1.JSON
│   ├── placements-alchemy-1.JSON
│   ├── placements-refining-1.JSON
│   ├── placements-engineering-1.JSON
│   └── placements-adornments-1.JSON
├── progression/
│   ├── npcs-1.JSON
│   ├── npcs-enhanced.JSON
│   ├── quests-1.JSON
│   ├── quests-enhanced.JSON
│   ├── classes-1.JSON
│   ├── titles-1.JSON
│   └── skill-unlocks.JSON
├── Skills/
│   ├── skills-skills-1.JSON
│   └── skills-base-effects-1.JSON
├── Definitions.JSON/
│   ├── combat-config.JSON
│   ├── hostiles-1.JSON
│   ├── resource-node-1.JSON
│   ├── crafting-stations-1.JSON
│   ├── value-translation-table-1.JSON
│   └── skills-translation-table.JSON
└── Crafting-subdisciplines/
    └── rarity-modifiers.JSON
```

---

## Validation Checklist

Before saving your JSON:

**Schema Validation**:
- [ ] All required fields present
- [ ] Field types correct (string, number, array, object)
- [ ] Enum values valid (tier, rarity, category)
- [ ] No duplicate IDs

**Cross-Reference Validation**:
- [ ] All referenced IDs exist
- [ ] Recipes output to valid items
- [ ] Recipes use valid materials
- [ ] Placements match recipes
- [ ] Quests reference valid NPCs
- [ ] Quest rewards reference valid items/skills/titles

**Business Logic**:
- [ ] Tier consistency (inputs ≤ output tier)
- [ ] Grid size matches tier
- [ ] Placement quantities match recipe inputs
- [ ] Level requirements logical

**Best Practices**:
- [ ] Descriptive ID (`iron_sword` not `item_001`)
- [ ] Human-readable names
- [ ] Narrative text included
- [ ] Tags for categorization

---

## Common Mistakes to Avoid

❌ **Wrong**: `"itemId": "Item 001"` (spaces, capitals)
✅ **Correct**: `"itemId": "iron_sword"`

❌ **Wrong**: `"tier": "2"` (string instead of number)
✅ **Correct**: `"tier": 2`

❌ **Wrong**: Recipe outputs item that doesn't exist
✅ **Correct**: Create item first, then recipe

❌ **Wrong**: Placement uses 7x7 grid for Tier 1 recipe
✅ **Correct**: Tier 1 = 3x3, Tier 2 = 5x5, Tier 3 = 7x7, Tier 4 = 9x9

❌ **Wrong**: Recipe needs 5 iron, placement only has 3
✅ **Correct**: Placement quantities must match recipe inputs

---

**Last Updated**: 2025-11-21
**Version**: 1.0
