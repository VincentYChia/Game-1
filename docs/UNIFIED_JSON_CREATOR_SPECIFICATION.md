# Unified JSON Creator - Comprehensive Reference

## Summary

Your game uses **36 JSON files** (922KB) across **13 distinct types** to define all game content. These JSONs are the source of truth for items, crafting, progression, combat, and world generation.

This document provides **complete detail** on all schemas, formulas, and hidden rules scattered across code and JSON files.

---

## JSON Categories

### Tier 1: Foundation Data (Create First)
1. **Materials** - Base resources (ores, wood, crystals)
2. **Items** - Equipment, consumables, devices, tools
   - 6 files, 101KB, ~247 items
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

## Complete Schema Reference

### Items

```json
{
  "itemId": "iron_sword",              // REQUIRED, unique, snake_case
  "name": "Iron Sword",                 // REQUIRED
  "category": "weapon",                 // REQUIRED: weapon|armor|tool|consumable|device|station|material
  "tier": 2,                            // REQUIRED: 1-4
  "rarity": "common",                   // REQUIRED: common|uncommon|rare|epic|legendary|artifact
  "type": "sword",                      // Optional subcategory
  "subtype": "longsword",               // Optional further refinement
  "stackSize": 1,                       // Default: 1
  "statMultipliers": {                  // Optional - multiplies base stats from formulas
    "damage": 1.0,                      // 1.0 = 100%, 1.5 = 150%, 0.5 = 50%
    "defense": 1.0,
    "weight": 1.0
  },
  "requirements": {                     // Optional
    "level": 5,
    "stats": {"STR": 10}                // STR, DEF, VIT, AGI, INT, LCK
  },
  "flags": {                            // Optional
    "stackable": false,
    "placeable": false,
    "repairable": true
  }
}
```

#### Item Categories
- **weapon** - Combat weapons (swords, axes, bows, staves, shields)
- **armor** - Protective gear (helmets, chestplates, leggings, boots, gauntlets)
- **tool** - Gathering tools (pickaxes, axes, fishing rods, sickles)
- **consumable** - Potions, elixirs, food
- **device** - Turrets, bombs, traps
- **station** - Crafting stations
- **material** - Raw resources (ores, ingots, wood, crystals)

#### Weapon Types & Subtypes
| Type | Subtypes | Damage Mult | Speed Mult |
|------|----------|-------------|------------|
| sword | shortsword (0.9), longsword (1.0), greatsword (1.4) | 1.0 | 1.0 / 1.1 / 0.7 |
| axe | hand_axe (0.9), battleaxe (1.0), greataxe (1.3) | 1.1 | 0.9 / 0.9 / 0.7 |
| spear | spear (1.0), pike (1.2), halberd (1.4) | 1.05 | 1.0 / 0.85 / 0.75 |
| mace | mace (1.0), warhammer (1.3), maul (1.5) | 1.15 | 0.95 / 0.8 / 0.65 |
| dagger | dagger (1.0), dual_dagger (0.85) | 0.8 | 1.4 / 1.2 |
| bow | shortbow (0.9), longbow (1.0), crossbow (1.2) | 1.0 | 1.0 / 0.75 / 0.6 |
| staff | staff (1.0), battle_staff (1.1) | 0.9 | 1.2 / 0.9 |
| shield | buckler (1.0), kite (1.2), tower (1.5) | 0.4 | 1.2 / 1.0 / 0.8 |

#### Stat Calculation Formulas

**Damage** (Weapons):
```
FinalDamage = 10 (base) × tierMult × categoryMult × typeMult × subtypeMult × itemMult
Variance: 85%-115% (randomized)

tierMult: T1=1.0, T2=2.0, T3=4.0, T4=8.0
categoryMult: weapon=1.0, tool=0.6, shield=0.4
typeMult: see table above
subtypeMult: see table above
itemMult: from JSON statMultipliers.damage (default 1.0)

Example: Iron Shortsword (T1)
= 10 × 1.0 × 1.0 × 1.0 × 0.9 × 1.0 = 9
With variance: [7.65, 10.35] → [8, 10] damage
```

**Defense** (Armor):
```
FinalDefense = 10 (base) × tierMult × slotMult × itemMult

tierMult: T1=1.0, T2=2.0, T3=4.0, T4=8.0
slotMult: head=0.8, chest=1.5, legs=1.2, feet=0.7, hands=0.6
itemMult: from JSON statMultipliers.defense (default 1.0)

Example: Iron Chestplate (T2)
= 10 × 2.0 × 1.5 × 1.0 = 30 defense
```

**Attack Speed**:
```
AttackSpeed = 1.0 (base) × typeMult × subtypeMult × itemMult
Result in attacks per second

See weapon table for multipliers

Example: Copper Dagger (T1, itemMult 1.3)
= 1.0 × 1.4 × 1.0 × 1.3 = 1.82 attacks/sec
```

**Durability**:
```
Durability = 500 (base) × tierMult × categoryMult × itemMult

tierMult: T1=1.0, T2=2.0, T3=4.0, T4=8.0
categoryMult: weapon=1.0, armor=1.2, tool=1.0, shield=1.5, accessory=0 (infinite)

Durability Mechanics:
- 100%-50%: Full stats
- 50%-0%: Gradual decline to 75% effectiveness
- At 0%: Functions at 50% effectiveness forever (never breaks completely)
- Wrong tool usage: Drastically increased durability drain
```

**Weight**:
```
Weight = 1.0 (base) × tierMult × categoryMult × typeMult × subtypeMult × itemMult

tierMult: T1=1.0, T2=2.0, T3=4.0, T4=8.0
categoryMult: weapon=1.0, armor=2.0, tool=0.8, accessory=0.1, consumable=0.2, device=1.5, station=10.0, material=0.3
typeMult/subtypeMult: see weapon table

Special: Mithril items can have itemMult < 1.0 for lighter weight
Example: Mithril Greatsword (T4, itemMult 0.5)
= 1.0 × 8.0 × 1.0 × 1.0 × 1.6 × 0.5 = 6.4 kg (half normal!)
```

**Range** (Not formula-based, defined per item):
- Melee 1H: 1 unit
- Melee 2H: 1.5 units
- Spear: 2 units
- Pike: 3 units
- Halberd: 2.5 units
- Shortbow: 10 units
- Longbow: 15 units
- Crossbow: 12 units
- Staff: 8 units
- Fishing rod: 5 units

---

### Recipes

```json
{
  "recipeId": "smithing_iron_sword",    // REQUIRED, unique
  "outputId": "iron_sword",             // REQUIRED, must reference valid item
  "outputQty": 1,                       // REQUIRED
  "stationTier": 2,                     // REQUIRED: 1-4
  "stationType": "smithing",            // REQUIRED: smithing|alchemy|refining|engineering|enchanting
  "gridSize": "5x5",                    // Auto-determined by tier (see below)
  "inputs": [                           // REQUIRED
    {"materialId": "iron_ingot", "quantity": 3},
    {"materialId": "oak_plank", "quantity": 1}
  ],
  "miniGame": {                         // Optional
    "type": "smithing",
    "difficulty": "moderate",           // easy|moderate|hard|extreme
    "baseTime": 40                      // seconds
  }
}
```

#### Crafting Disciplines & Tier Meanings

**1. SMITHING** (Weapons, Armor, Tools)
- **Grid Format**: Spatial placement on 2D grid
- **Tier → Grid Size**: T1=3x3, T2=5x5, T3=7x7, T4=9x9
- **Mini-game**: Rhythm-based hammering, timing precision
- **Base Time**: T1=25-35s, T2=40-55s, T3=60-70s, T4=90s+
- **Difficulty**: Tier-based (T1=easy, T2=moderate, T3=hard, T4=extreme)
- **Output**: Always 1 item
- **Materials**: Metals (ingots), wood (planks), leather, crystals

**2. ALCHEMY** (Potions, Elixirs, Transmutation)
- **Grid Format**: Sequential steps (not spatial)
- **Tier → Station**: T1=basic table, T2=advanced table, T3=master lab, T4=grand sanctum
- **Mini-game**: Sequence of actions (add, heat, stir, cool)
- **Base Time**: T1=20-35s, T2=30-40s, T3=45-60s, T4=75-90s
- **Difficulty**: Recipe-specific (not always tier-matched)
- **Output**: Usually 1-3 items (batch production)
- **Materials**: Organic (herbs, gels), crystals, essences
- **Special**: Can transmute materials (copper→tin, iron→steel)
- **Effect Scaling by Tier**:
  - T1: Health=50, Mana=30, Buff=10%, Duration=60s
  - T2: Health=100, Mana=60, Buff=20%, Duration=120s
  - T3: Health=200, Mana=120, Buff=35%, Duration=180s
  - T4: Health=400, Mana=250, Buff=50%, Duration=300s

**3. REFINING** (Ore→Ingot, Log→Plank, Alloys)
- **Grid Format**: Hub-and-spoke (center + surrounding slots)
- **Tier → Heat**: T1=basic forge, T2=hot forge, T3=extreme heat, T4=impossible heat
- **Mini-game**: Heat management (not too hot, not too cold)
- **Base Time**: Fast (10-30s) - automated process
- **Difficulty**: Generally easy-moderate
- **Output**:
  - Ores: 1 ore → 1 ingot
  - Logs: 1 log → 2-4 planks (less yield for harder woods)
  - Alloys: Multiple inputs → combined output
- **Materials**: Raw ores, logs, existing ingots
- **Special**: Rarity upgrading (4 common → 1 uncommon, etc.)
- **Rarity Progression**:
  - Common → Uncommon: 4:1 ratio, T1 station
  - Uncommon → Rare: 4:1 ratio, T2 station
  - Rare → Epic: 4:1 ratio, T3 station
  - Epic → Legendary: 4:1 ratio, T4 station
  - Legendary → Mythical: 4:1 ratio, T4 station (only for special materials)

**4. ENGINEERING** (Turrets, Bombs, Traps, Devices)
- **Grid Format**: Slot-based (frame, mechanism, power, projectile)
- **Tier → Complexity**: T1=simple (3 slots), T2=moderate (4 slots), T3=advanced (5 slots), T4=master (6+ slots)
- **Mini-game**: Assembly puzzle (correct parts in correct slots)
- **Base Time**: T1=25-35s, T2=35-45s, T3=50-65s, T4=80s+
- **Difficulty**: Tier-based
- **Output**: 1-10 devices (bombs/traps stack, turrets don't)
- **Materials**: Metals, crystals, mechanical parts, elemental essences
- **Device Scaling**:
  - Turrets: Damage = 10 × tierMult × 0.8, Fire rate = T1:1/s, T2:1.5/s, T3:2/s, T4:3/s
  - Bombs: Damage = 10 × tierMult × 3.0, Radius = T1:3, T2:4, T3:5, T4:6 units
  - Traps: Damage = 10 × tierMult × 2.0, Trigger radius = 1.5 units (fixed)

**5. ENCHANTING** (Item Modification)
- **Grid Format**: Pattern-based (specific material arrangements)
- **Tier → Power**: T1=basic enchants (+5-10%), T2=moderate (+15-25%), T3=strong (+30-50%), T4=legendary (+75-100%+)
- **Mini-game**: Pattern replication (memory/precision)
- **Base Time**: T1=30-40s, T2=45-60s, T3=70-90s, T4=100s+
- **Difficulty**: Pattern complexity increases with tier
- **Output**: Modified existing item (not new item)
- **Materials**: Crystals, essences, rare materials, existing enchanted items
- **Special**: Enchantments can conflict (can't have Sharpness I and Sharpness II)
- **Applicability**: weapon, armor, tool, accessory

---

### Placements

**Grid Format** (Smithing, Enchanting):
```json
{
  "recipeId": "smithing_iron_sword",
  "placementMap": {
    "1,1": "iron_ingot",                // "row,col": "materialId"
    "1,2": "iron_ingot",                // Rows and columns start at 1
    "1,3": "iron_ingot",                // Must match recipe gridSize
    "3,1": "oak_plank"
  }
}
```
- Coordinates are `"row,col"` starting at 1 (not 0)
- Must match recipe's `gridSize` (3x3, 5x5, 7x7, 9x9)
- Material counts in grid MUST equal recipe input quantities
- Empty cells allowed

**Hub-and-Spoke Format** (Refining):
```json
{
  "recipeId": "refining_iron_ore",
  "discipline": "refining",
  "core_inputs": [
    {"slot": "center", "materialId": "iron_ore"}
  ],
  "surrounding_inputs": [
    {"slot": "north", "materialId": "flux"},
    {"slot": "south", "materialId": "flux"},
    {"slot": "east", "materialId": "catalyst"},
    {"slot": "west", "materialId": "catalyst"}
  ]
}
```
- Core: center slot (primary material)
- Surrounding: north, south, east, west, northeast, northwest, southeast, southwest
- Used for ore smelting and material purification

**Sequential Format** (Alchemy):
```json
{
  "recipeId": "alchemy_health_potion",
  "discipline": "alchemy",
  "sequence": [
    {"step": 1, "action": "add", "materialId": "red_herb"},
    {"step": 2, "action": "heat", "duration": 5},
    {"step": 3, "action": "add", "materialId": "water_crystal"},
    {"step": 4, "action": "stir", "direction": "clockwise", "duration": 3},
    {"step": 5, "action": "cool", "duration": 2}
  ]
}
```
- Steps must be in order (1, 2, 3, ...)
- Actions: add, heat, cool, stir, wait, distill, crystallize
- Some actions require duration (seconds)
- Some actions require direction (clockwise, counterclockwise)

**Slot Format** (Engineering):
```json
{
  "recipeId": "engineering_turret",
  "discipline": "engineering",
  "slots": {
    "frame": "iron_frame",
    "mechanism": "gear_assembly",
    "power": "fire_crystal",
    "projectile": "iron_bolt",
    "targeting": "optical_lens"
  }
}
```
- Slots vary by device type
- Common slots: frame, mechanism, power, projectile, targeting, trigger, payload
- All slots must be filled

---

### Skills

```json
{
  "skillId": "power_strike",            // REQUIRED, unique
  "name": "Power Strike",               // REQUIRED
  "tier": 1,                            // REQUIRED: 1-4
  "rarity": "common",                   // REQUIRED: common|uncommon|rare|epic|legendary|mythic
  "categories": ["combat"],             // REQUIRED: gathering|combat|crafting|utility
  "description": "Deal massive damage", // REQUIRED
  "effect": {                           // REQUIRED
    "type": "empower",                  // See effect types below
    "category": "damage",               // What it affects
    "magnitude": "major",               // minor|moderate|major|extreme
    "target": "enemy",                  // self|enemy|area|resource_node
    "duration": "instant",              // instant|brief|moderate|long|extended
    "additionalEffects": []             // Can chain multiple effects
  },
  "cost": {                             // REQUIRED
    "mana": "high",                     // low|moderate|high|extreme
    "cooldown": "short"                 // short|moderate|long|extreme
  },
  "evolution": {                        // Optional
    "canEvolve": true,
    "nextSkillId": "decimating_blow",
    "requirement": "Reach level 10 and deal 10000 damage"
  },
  "requirements": {                     // REQUIRED
    "characterLevel": 1,
    "stats": {"STR": 0},
    "titles": []
  }
}
```

#### Skill Effect Types (Complete List)

| Effect Type | What It Does | Categories Affected | Example |
|-------------|-------------|---------------------|---------|
| **empower** | Increase power/damage | damage, mining, crafting, smithing, alchemy, etc | +50% damage |
| **quicken** | Increase speed | movement, combat, mining, forestry, smithing, etc | +30% attack speed |
| **fortify** | Increase defense/durability | defense, durability | +40% damage reduction |
| **pierce** | Increase critical chance | damage, crafting (quality) | +15% crit chance |
| **regenerate** | Heal/restore over time | defense (health), durability | +10 HP/sec for 30s |
| **devastate** | Area of effect damage | damage, mining (multi-node) | 100 damage in 5 unit radius |
| **elevate** | Increase rarity/quality | mining (rare drops), crafting (quality) | +20% rare material chance |
| **enrich** | Increase yield/quantity | mining (drops), crafting (output qty) | +30% material yield |
| **restore** | Instant heal/repair | defense (health), durability | Restore 100 HP instantly |
| **transcend** | Bypass restrictions | mining (tier limits), crafting | Use any tool on any resource |

#### Effect Magnitudes (with multipliers)

| Magnitude | Multiplier | Description | Example |
|-----------|-----------|-------------|---------|
| minor | 1.15× | +15% | 100 → 115 |
| moderate | 1.30× | +30% | 100 → 130 |
| major | 1.50× | +50% | 100 → 150 |
| extreme | 2.00× | +100% | 100 → 200 |

#### Effect Durations (in seconds)

| Duration | Seconds | Description |
|----------|---------|-------------|
| instant | 0 | One-time effect |
| brief | 5 | Very short buff |
| short | 15 | Short buff |
| moderate | 30 | Standard buff duration |
| long | 60 | Long buff |
| extended | 120 | Very long buff |
| extreme | 300 | Extremely long (5 min) |

#### Cost Values

**Mana Cost:**
- low: 10 mana
- moderate: 25 mana
- high: 50 mana
- extreme: 100 mana

**Cooldown:**
- short: 15 seconds
- moderate: 30 seconds
- long: 60 seconds
- extreme: 300 seconds (5 min)

#### Skill Categories
- **gathering**: mining, forestry, fishing
- **combat**: offense, defense, mobility
- **crafting**: smithing, alchemy, engineering, refining, enchanting
- **utility**: repair, movement, support

#### Skill Evolution Chains
Skills can evolve into more powerful versions:
```
miners_fury (T1, common)
  → titans_excavation (T2, uncommon)
    → earthquake_strike (T3, rare)

sprint (T1, common)
  → wind_runner (T2, uncommon)
    → teleport_dash (T3, rare)
```
- Evolution requires meeting level + activity requirements
- Next tier skill replaces previous (not additive)
- `canEvolve: false` means max tier

---

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
    ],
    "enemies_killed": 0                 // For combat quests
  },
  "rewards": {                          // REQUIRED
    "experience": 100,
    "health_restore": 50,               // Optional instant heal
    "mana_restore": 0,                  // Optional instant mana
    "items": [
      {"item_id": "minor_health_potion", "quantity": 2}
    ],
    "skills": ["sprint"],               // Optional: skill IDs to unlock
    "title": "novice_forester"          // Optional: title ID to grant
  },
  "completion_dialogue": [              // Optional
    "Excellent work!",
    "Take these rewards."
  ]
}
```

#### Quest Types
- **gather**: Collect X of item Y
- **combat**: Kill X enemies (any or specific type)
- **craft**: Craft X of item Y
- **explore**: Visit location or discover area

---

### NPCs

```json
{
  "npc_id": "merchant",                 // REQUIRED, unique
  "name": "Village Merchant",           // REQUIRED
  "position": {"x": 50.0, "y": 50.0, "z": 0.0}, // REQUIRED
  "sprite_color": [200, 150, 255],      // Optional RGB
  "interaction_radius": 3.0,            // Optional (default 3.0)
  "dialogue_lines": [                   // REQUIRED
    "Welcome to my shop!",
    "What can I get you?"
  ],
  "quests": ["quest_id_1", "quest_id_2"] // Optional
}
```

---

### Classes

```json
{
  "classId": "warrior",                 // REQUIRED, unique
  "name": "Warrior",                    // REQUIRED
  "description": "Front-line fighter",  // REQUIRED
  "narrative": "Class backstory",       // Optional
  "thematicIdentity": "frontline_fighter", // Optional
  "startingBonuses": {                  // REQUIRED
    "baseHP": 30,                       // Extra health
    "baseMana": 0,                      // Extra mana
    "meleeDamage": 0.10,                // +10% melee
    "rangedDamage": 0.0,
    "magicDamage": 0.0,
    "defense": 0.0,
    "criticalChance": 0.0,
    "inventorySlots": 20                // Default 20
  },
  "startingSkill": {                    // REQUIRED
    "skillId": "power_strike",
    "skillName": "Power Strike",
    "initialLevel": 1,
    "description": "Deal bonus damage"
  },
  "recommendedStats": {                 // REQUIRED
    "primary": ["STR", "VIT", "DEF"],
    "secondary": ["AGI"],
    "avoid": ["INT", "LCK"]
  }
}
```

#### Available Classes
1. **Warrior** - High HP, melee damage
2. **Mage** - High mana, INT bonus
3. **Ranger** - AGI focus, ranged damage
4. **Craftsman** - Crafting bonuses, inventory
5. **Tank** - Max DEF, HP regen
6. **Assassin** - Critical damage, AGI/LCK

---

### Titles

```json
{
  "titleId": "novice_miner",            // REQUIRED, unique
  "name": "Novice Miner",               // REQUIRED
  "titleType": "gathering",             // REQUIRED: gathering|crafting|combat|exploration
  "difficultyTier": "novice",           // REQUIRED: novice|apprentice|journeyman|master|grandmaster
  "description": "Title description",   // REQUIRED
  "bonuses": {                          // REQUIRED (can be empty)
    "miningDamage": 0.10,               // +10% mining damage
    "miningSpeed": 0.05,                // +5% mining speed
    "rareOreChance": 0.02               // +2% rare ore chance
  },
  "prerequisites": {                    // REQUIRED
    "activities": {
      "oresMined": 100                  // Track specific activities
    },
    "requiredTitles": [],               // Must have these titles first
    "characterLevel": 0
  },
  "acquisitionMethod": "guaranteed_milestone", // guaranteed_milestone|discovery|quest
  "narrative": "Title backstory"        // Optional
}
```

---

## Value Translation Tables

### Yield Quantities
| Keyword | Min | Max | Description |
|---------|-----|-----|-------------|
| few | 1 | 2 | Minimal yield |
| several | 3 | 5 | Standard low |
| many | 6 | 9 | Good yield |
| abundant | 10 | 15 | High yield |
| plentiful | 16 | 25 | Exceptional |

### Drop Chances
| Keyword | Probability | Percentage | Description |
|---------|------------|------------|-------------|
| guaranteed | 1.0 | 100% | Always drops |
| high | 0.75 | 75% | Very likely |
| moderate | 0.5 | 50% | 50/50 chance |
| low | 0.25 | 25% | Unlikely |
| rare | 0.1 | 10% | Rare drop |
| improbable | 0.03 | 3% | Very rare |

### Respawn Times
| Keyword | Seconds | Description |
|---------|---------|-------------|
| null | - | Never respawns (finite) |
| quick | 120 | 2 minutes |
| normal | 300 | 5 minutes |
| slow | 600 | 10 minutes |
| very_slow | 1200 | 20 minutes |

### Resource Density (Nodes per Chunk)
| Keyword | Count | Description |
|---------|-------|-------------|
| none | 0 | Does not spawn |
| very_low | 1-2 | Scarce |
| low | 3-5 | Light presence |
| moderate | 6-10 | Standard |
| high | 11-16 | Common |
| very_high | 17-24 | Abundant |

### Tier Bias (Resource Distribution)
| Bias | T1 | T2 | T3 | T4 | Description |
|------|-----|-----|-----|-----|-------------|
| low | 70% | 25% | 5% | 0% | Mostly T1 |
| mid | 30% | 50% | 18% | 2% | Favors T2 |
| high | 10% | 30% | 50% | 10% | Favors T3 |
| legendary | 0% | 10% | 40% | 50% | Favors T4 |

### Tool Efficiency (vs Resource Tier)
| Tool vs Resource | Efficiency | Description |
|-----------------|-----------|-------------|
| Same tier | 100% | Optimal |
| One tier higher | 50% | Slow but viable |
| Two tiers higher | 10% | Impractical |
| Lower tier | 150% | Overkill |

### Resource Health by Tier
| Tier | Base HP | Description |
|------|---------|-------------|
| T1 | 100 | Baseline |
| T2 | 200 | Doubled |
| T3 | 400 | Quadrupled |
| T4 | 800 | Octupled |

### Tool Damage by Tier
| Tier | Damage | Durability | Description |
|------|--------|-----------|-------------|
| T1 | 10 | 500 | Baseline |
| T2 | 20 | 1000 | Doubled |
| T3 | 40 | 2000 | Quadrupled |
| T4 | 80 | 4000 | Octupled |

---

## Tier System Deep Dive

### Universal Tier Multiplier: **2× per tier**
- T1: 1.0× (baseline)
- T2: 2.0× (double)
- T3: 4.0× (quadruple)
- T4: 8.0× (octuple)

This applies to:
- Weapon damage
- Armor defense
- Tool gathering power
- Durability
- Resource health
- Enemy stats
- Experience rewards

### Tier Meanings by System

**Items**:
- T1: Starter materials (copper, oak, common enemies)
- T2: Basic materials (iron, birch, tougher enemies)
- T3: Advanced materials (steel, ironwood, rare enemies)
- T4: Legendary materials (mithril, ebony, bosses)

**Crafting Stations**:
- T1: Basic stations (can craft T1 items)
- T2: Improved stations (can craft T1-T2 items)
- T3: Master stations (can craft T1-T3 items)
- T4: Legendary stations (can craft all items)

**Recipes**:
- `stationTier`: Minimum station tier required
- `gridSize`: Auto-determined by stationTier (3x3, 5x5, 7x7, 9x9)

**Enemies**:
- T1: 80-150 HP, 8-12 damage, grants 100 XP
- T2: 200-400 HP, 20-30 damage, grants 400 XP
- T3: 500-1000 HP, 45-70 damage, grants 1600 XP
- T4: 1200-2500 HP, 90-150 damage, grants 6400 XP
- Boss: 10× multiplier on XP

---

## Rarity System

### Rarity Tiers (in order)
`common` → `uncommon` → `rare` → `epic` → `legendary` → `artifact` → `mythic`

### How Rarity Works
- **Rarity does NOT directly affect stats**
- Stats are controlled by `itemMultipliers` and materials used
- Rarity affects:
  - Drop rates
  - Visual style/color
  - Perceived value
  - Some special effects at legendary+ tiers

### Rarity Modifiers (from rarity-modifiers.JSON)
Applied when crafting based on mini-game performance:

**Weapons**:
- Common: No bonuses
- Uncommon: +10% damage, +5% durability
- Rare: +20% damage, +10% durability, +5% crit
- Epic: +35% damage, +20% durability, +10% crit, +5% attack speed
- Legendary: +100% damage, +30% durability, +15% crit, +10% attack speed, +5% lifesteal

**Armor**:
- Common: No bonuses
- Uncommon: +10% defense, +5% durability
- Rare: +20% defense, +10% durability, +5% resistance
- Epic: +35% defense, +20% durability, +10% resistance, +5% damage reduction, knockback resistance
- Legendary: +100% defense, +30% durability, +15% resistance, +10% damage reduction, thorns, damage boost

**Tools**:
- Common: No bonuses
- Uncommon: +10% efficiency, +5% durability
- Rare: +20% efficiency, +10% durability, +5% gathering speed
- Epic: +35% efficiency, +20% durability, +10% gathering speed, +5% yield
- Legendary: +100% efficiency, +30% durability, +15% gathering speed, +10% yield, auto-smelt

### Rarity Upgrading (Refining)
Materials can be upgraded in rarity through refining:
- **Ratio**: 4 lower → 1 higher (4:1)
- **Station Requirements**:
  - Common → Uncommon: T1 refinery
  - Uncommon → Rare: T2 refinery
  - Rare → Epic: T3 refinery
  - Epic → Legendary: T4 refinery
  - Legendary → Mythical: T4 refinery (only special materials like mithril, orichalcum, etherion)

---

## Dependencies & Validation

### Cross-References
- **Recipes** reference **Items** (outputId) and **Materials** (inputs)
- **Placements** reference **Recipes** (recipeId) and **Materials** (grid contents)
- **Quests** reference **NPCs** (npc_id), **Items** (rewards), **Skills** (rewards), **Titles** (rewards)
- **Classes** reference **Skills** (starting skill)
- **Enemies** reference **Materials** (drop table)
- **Resource Nodes** reference **Materials** (drop table)

### Load Order
```
1. Materials
2. Items
3. Recipes
4. Placements
5. NPCs
6. Skills
7. Classes
8. Titles
9. Quests
10. Enemies
11. Resource Nodes
12. Config
```

### Critical Validation Rules

1. **All `itemId` unique** across all item files
2. **All `recipeId` unique** across all recipe files
3. **Recipe `outputId` exists** in Items
4. **Recipe `inputs[].materialId` exists** in Materials or Items
5. **Placement `recipeId` exists** in Recipes
6. **Placement material IDs** match Recipe inputs (both types AND quantities)
7. **Placement grid size** matches Recipe gridSize
8. **Quest `npc_id` exists** in NPCs
9. **Quest reward `item_id` exists** in Items
10. **Quest reward `skills[]` exist** in Skills
11. **Quest reward `title` exists** in Titles
12. **Class `startingSkill.skillId` exists** in Skills
13. **Recipe `stationTier` ≤** output item tier (can't craft T3 item at T1 station)
14. **All recipe input materials ≤** output item tier (can't use T4 materials for T1 item)

---

## Common Patterns

### Naming Convention
- IDs: `snake_case` (iron_sword, tutorial_quest, miners_fury)
- No spaces, no capitals in IDs
- Names: Any format ("Iron Sword", "Miner's Fury")

### Materials by Tier

**T1 Materials**:
- Metals: copper, tin
- Wood: oak, pine
- Stone: limestone, granite
- Drops: slime_gel, wolf_pelt

**T2 Materials**:
- Metals: iron, bronze
- Wood: ash, birch
- Stone: basalt
- Drops: beetle_carapace, dire_fang, living_ichor
- Crystals: fire, water, earth, air

**T3 Materials**:
- Metals: steel, mithril
- Wood: maple, ironwood
- Stone: obsidian
- Drops: golem_core, spectral_thread
- Crystals: light_gem, lightning_shard, frost_essence

**T4 Materials**:
- Metals: adamantine, orichalcum, etherion
- Wood: ebony, worldtree
- Drops: phoenix_ash, storm_heart, essence_blood
- Crystals: void_essence, shadow_core, voidstone

---

## File Locations

```
Game-1-modular/
├── items.JSON/                     (6 files, 101KB, ~247 items)
├── recipes.JSON/                   (6 files, 132KB, 112 recipes)
├── placements.JSON/                (5 files, 170KB)
├── progression/                    (7 files, 53KB)
│   ├── npcs-1.JSON                (8 NPCs)
│   ├── quests-1.JSON              (15 quests)
│   ├── classes-1.JSON             (6 classes)
│   ├── titles-1.JSON              (45 titles)
│   └── skill-unlocks.JSON
├── Skills/                         (2 files, 42KB, 30 skills)
├── Definitions.JSON/               (10 files, 137KB)
│   ├── combat-config.JSON
│   ├── hostiles-1.JSON            (12 enemies)
│   ├── resource-node-1.JSON       (18 nodes)
│   ├── stats-calculations.JSON     (ALL FORMULAS!)
│   ├── value-translation-table-1.JSON (ALL TRANSLATIONS!)
│   └── skills-translation-table.JSON
└── Crafting-subdisciplines/       (1 file, 387KB!)
    └── rarity-modifiers.JSON      (stat bonuses by rarity)
```

---

**Last Updated**: 2025-11-21
**Version**: 2.0 - Comprehensive Detail Edition
