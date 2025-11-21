# Unified JSON Creator - System Overview

## Summary

Your game uses **36 JSON files** (922KB) across **13 distinct types** to define all game content. These JSONs are the source of truth for items, crafting, progression, combat, and world generation.

---

## JSON Categories

### Tier 1: Foundation Data (Create First)
1. **Materials** - Base resources (ores, wood, crystals)
2. **Items** - Equipment, consumables, devices, tools
   - 6 files, 101KB
   - Categories: weapons, armor, tools, consumables, devices, stations

### Tier 2: Production Systems (Depends on Tier 1)
3. **Recipes** - Crafting instructions
   - 6 files, 132KB, 112 recipes
   - Disciplines: smithing, alchemy, refining, engineering, enchanting
4. **Placements** - Spatial layouts for recipes
   - 5 files, 170KB
   - 4 formats: grid (smithing), hub-spoke (refining), sequential (alchemy), slot-based (engineering)

### Tier 3: Progression (Depends on Tier 1-2)
5. **NPCs** - Characters with dialogue (8 NPCs)
6. **Quests** - Objectives and rewards (15 quests)
7. **Skills** - Abilities with effects (30 skills)
8. **Classes** - Character archetypes (6 classes)
9. **Titles** - Achievement badges (45 titles)

### Tier 4: Configuration (Depends on All)
10. **Enemies** - Hostile entities (12 enemies)
11. **Resource Nodes** - Gatherable objects (18 nodes)
12. **Combat Config** - Spawn rates, damage formulas
13. **Rarity Modifiers** - Stat bonuses by quality (387KB!)

---

## Schema Reference

### Items
```json
{
  "itemId": "iron_sword",              // REQUIRED, unique
  "name": "Iron Sword",                 // REQUIRED
  "category": "weapon",                 // REQUIRED: weapon|armor|tool|consumable|device|station|material
  "tier": 2,                            // REQUIRED: 1-4
  "rarity": "common",                   // REQUIRED: common|uncommon|rare|epic|legendary|artifact
  "type": "sword",                      // Optional subcategory
  "subtype": "longsword",               // Optional further refinement
  "stackSize": 1,                       // Default: 1
  "statMultipliers": {                  // Optional
    "damage": 1.0,
    "defense": 1.0,
    "weight": 1.0
  },
  "requirements": {                     // Optional
    "level": 5,
    "stats": {"STR": 10}
  },
  "flags": {                            // Optional
    "stackable": false,
    "placeable": false,
    "repairable": true
  }
}
```

### Recipes
```json
{
  "recipeId": "smithing_iron_sword",    // REQUIRED, unique
  "outputId": "iron_sword",             // REQUIRED, must reference valid item
  "outputQty": 1,                       // REQUIRED
  "stationTier": 2,                     // REQUIRED: 1-4
  "stationType": "smithing",            // REQUIRED: smithing|alchemy|refining|engineering|enchanting
  "gridSize": "5x5",                    // Auto-determined by tier: T1=3x3, T2=5x5, T3=7x7, T4=9x9
  "inputs": [                           // REQUIRED
    {"materialId": "iron_ingot", "quantity": 3},
    {"materialId": "oak_plank", "quantity": 1}
  ],
  "miniGame": {                         // Optional
    "type": "smithing",
    "difficulty": "moderate",           // easy|moderate|hard|extreme
    "baseTime": 40
  }
}
```

### Placements (Grid Format - Smithing/Enchanting)
```json
{
  "recipeId": "smithing_iron_sword",
  "placementMap": {
    "1,1": "iron_ingot",                // "row,col": "materialId"
    "1,2": "iron_ingot",
    "1,3": "iron_ingot",
    "3,1": "oak_plank"
  }
}
```

### Quests
```json
{
  "quest_id": "gather_logs",            // REQUIRED, unique
  "title": "Gather Oak Logs",           // REQUIRED
  "description": "Collect 10 oak logs", // REQUIRED
  "npc_id": "tutorial_guide",           // REQUIRED, must reference valid NPC
  "objectives": {                       // REQUIRED
    "type": "gather",                   // gather|combat|craft
    "items": [
      {"item_id": "oak_log", "quantity": 10}
    ]
  },
  "rewards": {                          // REQUIRED
    "experience": 100,
    "items": [{"item_id": "minor_health_potion", "quantity": 2}],
    "skills": ["sprint"],               // Optional: skill IDs
    "title": "novice_forester"          // Optional: title ID
  }
}
```

### NPCs
```json
{
  "npc_id": "merchant",                 // REQUIRED, unique
  "name": "Village Merchant",           // REQUIRED
  "position": {"x": 50.0, "y": 50.0, "z": 0.0}, // REQUIRED
  "dialogue_lines": [                   // REQUIRED
    "Welcome to my shop!"
  ],
  "quests": ["quest_id_1"]              // Optional
}
```

### Skills
```json
{
  "skillId": "power_strike",            // REQUIRED, unique
  "name": "Power Strike",               // REQUIRED
  "tier": 1,                            // REQUIRED: 1-4
  "rarity": "common",                   // REQUIRED
  "categories": ["combat"],             // REQUIRED
  "description": "Deal massive damage", // REQUIRED
  "effect": {                           // REQUIRED
    "type": "empower",                  // empower|quicken|fortify|pierce|regenerate|devastate|etc
    "category": "damage",
    "magnitude": "major",               // minor|moderate|major|extreme
    "target": "enemy",                  // self|enemy|area|resource_node
    "duration": "instant"               // instant|brief|moderate|long|extended
  },
  "cost": {                             // REQUIRED
    "mana": "high",                     // low|moderate|high|extreme
    "cooldown": "short"                 // short|moderate|long|extreme
  },
  "requirements": {                     // REQUIRED
    "characterLevel": 1,
    "stats": {},
    "titles": []
  }
}
```

---

## Dependencies

### Cross-References
- **Recipes** reference **Items** (outputId) and **Materials** (inputs)
- **Placements** reference **Recipes** (recipeId) and **Materials** (grid contents)
- **Quests** reference **NPCs** (npc_id), **Items** (rewards), **Skills** (rewards), **Titles** (rewards)
- **Classes** reference **Skills** (starting skill)
- **Enemies** reference **Materials** (drop table)
- **Resource Nodes** reference **Materials** (drop table)

### Load Order
```
1. Materials → 2. Items → 3. Recipes → 4. Placements
5. NPCs → 6. Skills → 7. Classes → 8. Titles → 9. Quests
10. Enemies → 11. Resource Nodes → 12. Config
```

---

## Validation Rules

### Required Validations
1. All `itemId` are unique across all item files
2. All `recipeId` are unique across all recipe files
3. Recipe `outputId` exists in Items
4. Recipe `inputs[].materialId` exists in Materials or Items
5. Placement `recipeId` exists in Recipes
6. Placement material IDs match Recipe inputs
7. Placement quantities match Recipe input quantities
8. Quest `npc_id` exists in NPCs
9. Quest reward `item_id` exists in Items
10. Quest reward `skills[]` exist in Skills
11. Quest reward `title` exists in Titles
12. Class `startingSkill.skillId` exists in Skills

### Logical Validations
1. Recipe `stationTier` ≤ output item tier
2. Recipe `gridSize` matches tier: T1→3x3, T2→5x5, T3→7x7, T4→9x9
3. All recipe input materials ≤ output item tier
4. Quest reward items' level requirements ≤ quest level

---

## File Locations

```
Game-1-modular/
├── items.JSON/                     (6 files, 101KB)
│   ├── items-smithing-1.JSON      (weapons, armor)
│   ├── items-smithing-2.JSON      (more equipment)
│   ├── items-alchemy-1.JSON       (potions)
│   ├── items-materials-1.JSON     (ores, wood)
│   ├── items-refining-1.JSON      (ingots)
│   └── items-tools-1.JSON         (tools)
├── recipes.JSON/                   (6 files, 132KB, 112 recipes)
│   ├── recipes-smithing-3.JSON
│   ├── recipes-alchemy-1.JSON
│   ├── recipes-refining-1.JSON
│   ├── recipes-engineering-1.JSON
│   ├── recipes-enchanting-1.JSON
│   └── recipes-adornments-1.json
├── placements.JSON/                (5 files, 170KB)
│   ├── placements-smithing-1.JSON
│   ├── placements-alchemy-1.JSON
│   ├── placements-refining-1.JSON
│   ├── placements-engineering-1.JSON
│   └── placements-adornments-1.JSON
├── progression/                    (7 files, 53KB)
│   ├── npcs-1.JSON                (8 NPCs)
│   ├── quests-1.JSON              (15 quests)
│   ├── classes-1.JSON             (6 classes)
│   ├── titles-1.JSON              (45 titles)
│   └── skill-unlocks.JSON
├── Skills/                         (2 files, 42KB)
│   ├── skills-skills-1.JSON       (30 skills)
│   └── skills-base-effects-1.JSON
├── Definitions.JSON/               (8 files, 137KB)
│   ├── combat-config.JSON
│   ├── hostiles-1.JSON            (12 enemies)
│   ├── resource-node-1.JSON       (18 nodes)
│   ├── crafting-stations-1.JSON
│   ├── value-translation-table-1.JSON
│   └── skills-translation-table.JSON
└── Crafting-subdisciplines/       (1 file, 387KB!)
    └── rarity-modifiers.JSON      (stat bonuses by item category & rarity)
```

---

## Common Patterns

### Naming Convention
- IDs use `snake_case`: `iron_sword`, `tutorial_quest`, `miners_fury`
- No spaces, no capitals in IDs
- Names can have spaces and capitals: `"Iron Sword"`

### Tier System (1-4)
- **Tier 1**: Starter (copper, oak, common enemies)
- **Tier 2**: Basic (iron, birch, tougher enemies)
- **Tier 3**: Advanced (steel, ironwood, rare enemies)
- **Tier 4**: Legendary (mithril, ebony, bosses)

### Rarity Progression
`common` → `uncommon` → `rare` → `epic` → `legendary` → `artifact`

### Stats (Character)
- `STR` - Strength (melee damage)
- `DEF` - Defense (damage reduction)
- `VIT` - Vitality (health)
- `AGI` - Agility (speed, dodge)
- `INT` - Intelligence (magic damage, crafting)
- `LCK` - Luck (crits, drops)

### Qualitative → Quantitative Mappings
From `value-translation-table-1.JSON`:
- Quantity: `few` (1-3), `several` (3-6), `many` (6-10)
- Power: `low` (10), `moderate` (25), `high` (50), `extreme` (100)
- Duration: `brief` (5s), `short` (15s), `moderate` (30s), `long` (60s), `extended` (120s)

---

## Existing Tools

### Smithing Grid Designer (`tools/smithing-grid-designer.py`)
**What it does**:
- Loads recipes and materials
- Visual grid editor (3x3 to 9x9)
- Material palette with usage tracking
- Validates material counts
- Auto-saves placements
- Spacebar quick-reselect

**Could be extended** to support:
- All JSON types (add type selector dropdown)
- All placement formats (grid, hub-spoke, sequential, slot)
- Form-based editors for non-spatial types

---

## Statistics

| Type | Files | Count | Size |
|------|-------|-------|------|
| Items | 6 | 247 | 101KB |
| Recipes | 6 | 112 | 132KB |
| Placements | 5 | 112 | 170KB |
| NPCs | 2 | 8 | 15KB |
| Quests | 2 | 15 | 22KB |
| Skills | 2 | 30 | 42KB |
| Classes | 1 | 6 | 8KB |
| Titles | 1 | 45 | 18KB |
| Enemies | 1 | 12 | 25KB |
| Nodes | 1 | 18 | 12KB |
| Config | 8 | - | 137KB |
| **Total** | **36** | **~500+** | **922KB** |

---

**Last Updated**: 2025-11-21
