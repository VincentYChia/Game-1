# JSON Quick Reference

## Common Fields

### All Items/Equipment
```json
{
  "itemId": "iron_sword",        // REQUIRED: unique, snake_case
  "name": "Iron Sword",           // REQUIRED: display name
  "category": "weapon",           // REQUIRED: see categories below
  "tier": 2,                      // REQUIRED: 1-4
  "rarity": "common"              // REQUIRED: see rarities below
}
```

### All Recipes
```json
{
  "recipeId": "smithing_iron_sword",
  "outputId": "iron_sword",            // Must exist in Items
  "outputQty": 1,
  "stationTier": 2,
  "stationType": "smithing",           // smithing|alchemy|refining|engineering|enchanting
  "inputs": [
    {"materialId": "iron_ingot", "quantity": 3}
  ]
}
```

---

## Categories & Values

### Item Categories
- `weapon` - Swords, axes, bows, staves, shields
- `armor` - Helmets, chestplates, leggings, boots, gauntlets
- `tool` - Pickaxes, axes, fishing rods, sickles
- `consumable` - Potions, elixirs, food
- `device` - Turrets, bombs, traps
- `station` - Forges, refineries, alchemy tables
- `material` - Ores, ingots, wood, crystals

### Rarities (in order)
`common` → `uncommon` → `rare` → `epic` → `legendary` → `artifact`

### Tiers
- **1** - Starter (copper, oak)
- **2** - Basic (iron, birch)
- **3** - Advanced (steel, ironwood)
- **4** - Legendary (mithril, ebony)

### Grid Sizes (by Tier)
- Tier 1 → `3x3`
- Tier 2 → `5x5`
- Tier 3 → `7x7`
- Tier 4 → `9x9`

### Stats
- `STR` - Strength
- `DEF` - Defense
- `VIT` - Vitality
- `AGI` - Agility
- `INT` - Intelligence
- `LCK` - Luck

---

## Minimal Examples

### Item (Weapon)
```json
{
  "itemId": "iron_sword",
  "name": "Iron Sword",
  "category": "weapon",
  "type": "sword",
  "tier": 2,
  "rarity": "common",
  "statMultipliers": {"damage": 1.0}
}
```

### Recipe
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

### Placement (Grid)
```json
{
  "recipeId": "smithing_iron_sword",
  "placementMap": {
    "1,1": "iron_ingot",
    "1,2": "iron_ingot",
    "1,3": "iron_ingot",
    "3,1": "oak_plank"
  }
}
```

### Quest
```json
{
  "quest_id": "gather_logs",
  "title": "Gather Oak Logs",
  "description": "Collect 10 oak logs",
  "npc_id": "tutorial_guide",
  "objectives": {
    "type": "gather",
    "items": [{"item_id": "oak_log", "quantity": 10}]
  },
  "rewards": {
    "experience": 100
  }
}
```

### NPC
```json
{
  "npc_id": "merchant",
  "name": "Village Merchant",
  "position": {"x": 50.0, "y": 50.0, "z": 0.0},
  "dialogue_lines": ["Welcome to my shop!"]
}
```

### Skill
```json
{
  "skillId": "power_strike",
  "name": "Power Strike",
  "tier": 1,
  "rarity": "common",
  "categories": ["combat"],
  "description": "Deal massive damage",
  "effect": {
    "type": "empower",
    "category": "damage",
    "magnitude": "major",
    "target": "enemy",
    "duration": "instant"
  },
  "cost": {"mana": "high", "cooldown": "short"},
  "requirements": {"characterLevel": 1}
}
```

---

## Validation Checklist

Before saving:
- [ ] All IDs are unique
- [ ] IDs use snake_case (no spaces, no capitals)
- [ ] Required fields present
- [ ] Recipe outputId exists in Items
- [ ] Recipe inputs exist in Materials/Items
- [ ] Placement quantities match recipe inputs
- [ ] Quest npc_id exists in NPCs
- [ ] Quest reward items exist
- [ ] Tier/gridSize consistent

---

## Common Mistakes

❌ `"itemId": "Iron Sword"` (spaces)
✅ `"itemId": "iron_sword"`

❌ `"tier": "2"` (string)
✅ `"tier": 2` (number)

❌ Recipe outputs non-existent item
✅ Create item first, then recipe

❌ Placement uses wrong grid size for tier
✅ T1=3x3, T2=5x5, T3=7x7, T4=9x9

❌ Placement quantities don't match recipe
✅ Count materials in placement = recipe inputs
