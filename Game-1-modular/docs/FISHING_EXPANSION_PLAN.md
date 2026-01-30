# Fishing Expansion Plan

**Purpose**: This document provides everything needed to implement a complete fishing system.
**Target**: Lower model implementation
**Date**: 2026-01-29

---

## Current State Analysis

### What Exists
1. **ResourceType.FISHING_SPOT** - Defined in `data/models/world.py:73`
2. **Fishing spot spawning** - In `systems/chunk.py:286-311`, spawns 3-8 fishing spots on water chunks
3. **Tier distribution**: Lake/River = tier 1-2, Cursed Swamp = tier 3-4
4. **One fishing rod** - `bamboo_fishing_rod` (tier 1) in `items.JSON/items-smithing-2.JSON:571`
5. **Hardcoded loot** - In `systems/natural_resource.py:184`: `("raw_fish", 1, 3)` - **BUT THIS ITEM DOESN'T EXIST**

### What's Missing
1. **No fish materials** - `raw_fish` is referenced but not defined anywhere
2. **No fishing nodes in JSON** - `resource-node-1.JSON` has no fishing entries
3. **No tiered fish** - Only one generic "raw_fish" hardcoded
4. **No higher-tier fishing rods** - Only tier 1 exists
5. **No cooked fish/recipes** - No alchemy or cooking recipes for fish

---

## Implementation Tasks

### Task 1: Add Fish Materials to items-materials-1.JSON

**File**: `items.JSON/items-materials-1.JSON`

Add these fish materials at the end of the materials array. Follow the existing format in the file.

```json
{
  "metadata": {
    "narrative": "Common freshwater fish caught in calm waters. The staple catch of novice anglers.",
    "tags": ["fish", "food", "raw", "common"]
  },
  "materialId": "raw_carp",
  "name": "Raw Carp",
  "category": "fish",
  "tier": 1,
  "rarity": "common",
  "stackSize": 20,
  "weight": 0.5,
  "sources": ["fishing_spot"],
  "flags": {
    "stackable": true,
    "perishable": false
  }
},
{
  "metadata": {
    "narrative": "Small silvery fish that swim in schools. Easy to catch, quick to cook.",
    "tags": ["fish", "food", "raw", "common"]
  },
  "materialId": "raw_minnow",
  "name": "Raw Minnow",
  "category": "fish",
  "tier": 1,
  "rarity": "common",
  "stackSize": 30,
  "weight": 0.2,
  "sources": ["fishing_spot"],
  "flags": {
    "stackable": true,
    "perishable": false
  }
},
{
  "metadata": {
    "narrative": "Spotted river fish with firm flesh. Prized for its taste when properly prepared.",
    "tags": ["fish", "food", "raw", "quality"]
  },
  "materialId": "raw_trout",
  "name": "Raw Trout",
  "category": "fish",
  "tier": 2,
  "rarity": "common",
  "stackSize": 20,
  "weight": 0.8,
  "sources": ["fishing_spot"],
  "flags": {
    "stackable": true,
    "perishable": false
  }
},
{
  "metadata": {
    "narrative": "Large predatory fish that fights hard on the line. Excellent eating.",
    "tags": ["fish", "food", "raw", "quality"]
  },
  "materialId": "raw_bass",
  "name": "Raw Bass",
  "category": "fish",
  "tier": 2,
  "rarity": "common",
  "stackSize": 15,
  "weight": 1.2,
  "sources": ["fishing_spot"],
  "flags": {
    "stackable": true,
    "perishable": false
  }
},
{
  "metadata": {
    "narrative": "Ancient fish that lurks in deep, still waters. Said to grant visions when consumed.",
    "tags": ["fish", "food", "raw", "rare", "magical"]
  },
  "materialId": "raw_ghostfish",
  "name": "Raw Ghostfish",
  "category": "fish",
  "tier": 3,
  "rarity": "uncommon",
  "stackSize": 10,
  "weight": 1.5,
  "sources": ["fishing_spot"],
  "flags": {
    "stackable": true,
    "perishable": false
  }
},
{
  "metadata": {
    "narrative": "Eel-like fish found in cursed waters. Its flesh pulses with dark energy.",
    "tags": ["fish", "food", "raw", "rare", "cursed"]
  },
  "materialId": "raw_shadoweel",
  "name": "Raw Shadoweel",
  "category": "fish",
  "tier": 3,
  "rarity": "uncommon",
  "stackSize": 10,
  "weight": 1.0,
  "sources": ["fishing_spot"],
  "flags": {
    "stackable": true,
    "perishable": false
  }
},
{
  "metadata": {
    "narrative": "Legendary fish that shimmers with otherworldly light. Grants temporary magical enhancement.",
    "tags": ["fish", "food", "raw", "legendary", "magical"]
  },
  "materialId": "raw_starscale",
  "name": "Raw Starscale",
  "category": "fish",
  "tier": 4,
  "rarity": "rare",
  "stackSize": 5,
  "weight": 2.0,
  "sources": ["fishing_spot"],
  "flags": {
    "stackable": true,
    "perishable": false
  }
},
{
  "metadata": {
    "narrative": "Massive primordial fish from the deepest waters. Its scales are harder than iron.",
    "tags": ["fish", "food", "raw", "legendary", "ancient"]
  },
  "materialId": "raw_leviathan_fry",
  "name": "Raw Leviathan Fry",
  "category": "fish",
  "tier": 4,
  "rarity": "rare",
  "stackSize": 5,
  "weight": 3.0,
  "sources": ["fishing_spot"],
  "flags": {
    "stackable": true,
    "perishable": false
  }
}
```

---

### Task 2: Add Fishing Nodes to resource-node-1.JSON

**File**: `Definitions.JSON/resource-node-1.JSON`

Add these entries to the `nodes` array. Place them after the stone/ore entries.

```json
{
  "metadata": {
    "narrative": "Calm shallows where small fish gather. Ripples on the surface betray their presence.",
    "tags": ["water", "fishing", "starter"]
  },
  "resourceId": "fishing_spot_shallow",
  "name": "Shallow Fishing Spot",
  "category": "fishing",
  "tier": 1,
  "requiredTool": "fishing_rod",
  "baseHealth": 50,
  "drops": [
    {
      "materialId": "raw_carp",
      "quantity": "several",
      "chance": "high"
    },
    {
      "materialId": "raw_minnow",
      "quantity": "many",
      "chance": "guaranteed"
    }
  ],
  "respawnTime": "fast"
},
{
  "metadata": {
    "narrative": "Deeper waters where larger fish swim. Patience and skill required.",
    "tags": ["water", "fishing", "quality"]
  },
  "resourceId": "fishing_spot_deep",
  "name": "Deep Fishing Spot",
  "category": "fishing",
  "tier": 2,
  "requiredTool": "fishing_rod",
  "baseHealth": 50,
  "drops": [
    {
      "materialId": "raw_trout",
      "quantity": "several",
      "chance": "high"
    },
    {
      "materialId": "raw_bass",
      "quantity": "few",
      "chance": "moderate"
    }
  ],
  "respawnTime": "fast"
},
{
  "metadata": {
    "narrative": "Dark waters that seem to swallow light. Strange fish lurk in the depths.",
    "tags": ["water", "fishing", "rare", "cursed"]
  },
  "resourceId": "fishing_spot_cursed",
  "name": "Cursed Fishing Spot",
  "category": "fishing",
  "tier": 3,
  "requiredTool": "fishing_rod",
  "baseHealth": 50,
  "drops": [
    {
      "materialId": "raw_ghostfish",
      "quantity": "few",
      "chance": "moderate"
    },
    {
      "materialId": "raw_shadoweel",
      "quantity": "few",
      "chance": "moderate"
    }
  ],
  "respawnTime": "normal"
},
{
  "metadata": {
    "narrative": "Waters that shimmer with starlight even during the day. Legendary catches await.",
    "tags": ["water", "fishing", "legendary", "magical"]
  },
  "resourceId": "fishing_spot_ethereal",
  "name": "Ethereal Fishing Spot",
  "category": "fishing",
  "tier": 4,
  "requiredTool": "fishing_rod",
  "baseHealth": 50,
  "drops": [
    {
      "materialId": "raw_starscale",
      "quantity": "few",
      "chance": "low"
    },
    {
      "materialId": "raw_leviathan_fry",
      "quantity": "few",
      "chance": "rare"
    },
    {
      "materialId": "raw_ghostfish",
      "quantity": "few",
      "chance": "moderate"
    }
  ],
  "respawnTime": "slow"
}
```

---

### Task 3: Update natural_resource.py Type-to-ID Mapping

**File**: `systems/natural_resource.py`

**Location**: Find the `_get_resource_node_data` function around line 141.

**Current code** (around line 159):
```python
ResourceType.FISHING_SPOT: None,  # No JSON definition for fishing
```

**Change to**:
```python
ResourceType.FISHING_SPOT: "fishing_spot_shallow",  # Default to shallow, tier determines actual spot
```

**Additional change**: The mapping should be tier-aware. Update the function to handle fishing specially:

Find the `_get_resource_node_data` function and modify it. After the line:
```python
resource_id = type_to_id_map.get(resource_type)
```

Add this logic BEFORE the return statement:
```python
# Special handling for fishing spots - map by tier
if resource_type == ResourceType.FISHING_SPOT:
    # This will be handled differently - fishing spots use tier from spawning
    # The actual node lookup happens in NaturalResource.__init__
    return None  # Let the tier-based lookup handle it
```

Then in `NaturalResource.__init__`, after the line `node_data = _get_resource_node_data(resource_type)`:
```python
# Special handling for tiered fishing spots
if resource_type == ResourceType.FISHING_SPOT and node_data is None:
    nodes = _load_resource_nodes()
    tier_to_fishing_spot = {
        1: "fishing_spot_shallow",
        2: "fishing_spot_deep",
        3: "fishing_spot_cursed",
        4: "fishing_spot_ethereal"
    }
    fishing_id = tier_to_fishing_spot.get(tier, "fishing_spot_shallow")
    node_data = nodes.get(fishing_id)
```

---

### Task 4: Add Higher-Tier Fishing Rods to items-smithing-2.JSON

**File**: `items.JSON/items-smithing-2.JSON`

Find the `tools` array (around line 565) and add these after the `bamboo_fishing_rod`:

```json
{
  "metadata": {
    "narrative": "Sturdy oak rod reinforced with iron fittings. Reliable for medium-sized catches.",
    "tags": ["tool", "fishing", "gathering", "quality"]
  },
  "itemId": "reinforced_fishing_rod",
  "name": "Reinforced Fishing Rod",
  "category": "equipment",
  "type": "tool",
  "subtype": "fishing_rod",
  "tier": 2,
  "rarity": "common",
  "range": 6,
  "slot": "mainHand",
  "statMultipliers": {
    "damage": 0.6,
    "gathering": 1.3,
    "durability": 1.0,
    "weight": 0.8
  },
  "requirements": {
    "level": 5,
    "stats": {}
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
},
{
  "metadata": {
    "narrative": "Mithril-tipped rod with enchanted line. Can sense fish before they bite.",
    "tags": ["tool", "fishing", "gathering", "rare", "magical"]
  },
  "itemId": "mithril_fishing_rod",
  "name": "Mithril Fishing Rod",
  "category": "equipment",
  "type": "tool",
  "subtype": "fishing_rod",
  "tier": 3,
  "rarity": "uncommon",
  "range": 8,
  "slot": "mainHand",
  "statMultipliers": {
    "damage": 0.7,
    "gathering": 1.6,
    "durability": 1.2,
    "weight": 0.5
  },
  "requirements": {
    "level": 12,
    "stats": {}
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
},
{
  "metadata": {
    "narrative": "Legendary rod crafted from worldtree branches. The line seems to know where fish will be.",
    "tags": ["tool", "fishing", "gathering", "legendary", "sentient"]
  },
  "itemId": "worldtree_fishing_rod",
  "name": "Worldtree Fishing Rod",
  "category": "equipment",
  "type": "tool",
  "subtype": "fishing_rod",
  "tier": 4,
  "rarity": "rare",
  "range": 10,
  "slot": "mainHand",
  "statMultipliers": {
    "damage": 0.8,
    "gathering": 2.0,
    "durability": 1.5,
    "weight": 0.4
  },
  "requirements": {
    "level": 20,
    "stats": {}
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}
```

---

### Task 5: Add Fishing Rod Recipes to recipes-smithing-3.json

**File**: `recipes.JSON/recipes-smithing-3.json`

Add these recipes to the appropriate section:

```json
{
  "recipeId": "smithing_reinforced_fishing_rod_001",
  "outputId": "reinforced_fishing_rod",
  "outputQty": 1,
  "stationType": "smithing",
  "stationTier": 1,
  "discipline": "smithing",
  "inputs": [
    {"materialId": "oak_log", "qty": 2},
    {"materialId": "iron_ingot", "qty": 1},
    {"materialId": "silk_thread", "qty": 2}
  ]
},
{
  "recipeId": "smithing_mithril_fishing_rod_001",
  "outputId": "mithril_fishing_rod",
  "outputQty": 1,
  "stationType": "smithing",
  "stationTier": 2,
  "discipline": "smithing",
  "inputs": [
    {"materialId": "ironwood_log", "qty": 1},
    {"materialId": "mithril_ingot", "qty": 2},
    {"materialId": "enchanted_thread", "qty": 2}
  ]
},
{
  "recipeId": "smithing_worldtree_fishing_rod_001",
  "outputId": "worldtree_fishing_rod",
  "outputQty": 1,
  "stationType": "smithing",
  "stationTier": 3,
  "discipline": "smithing",
  "inputs": [
    {"materialId": "worldtree_log", "qty": 1},
    {"materialId": "etherion_ingot", "qty": 1},
    {"materialId": "starweave_thread", "qty": 2}
  ]
}
```

**Note**: Check if `silk_thread`, `enchanted_thread`, and `starweave_thread` exist in materials. If not, either:
- Use existing materials like `fiber` or `leather`
- Add thread materials to items-materials-1.JSON

---

### Task 6 (Optional): Add Cooked Fish Consumables

**File**: `items.JSON/items-alchemy-1.JSON`

Add a new section `food` or add to existing consumables:

```json
{
  "metadata": {
    "narrative": "Simply grilled fish. Restores a small amount of health over time.",
    "tags": ["food", "fish", "cooked", "healing"]
  },
  "itemId": "grilled_fish",
  "name": "Grilled Fish",
  "category": "consumable",
  "type": "food",
  "subtype": "cooked_fish",
  "tier": 1,
  "rarity": "common",
  "effect": "Restores 30 HP over 10 seconds",
  "duration": 10,
  "stackSize": 20,
  "effectTags": ["healing", "over_time", "self"],
  "effectParams": {
    "heal_per_second": 3,
    "duration": 10
  },
  "flags": {
    "stackable": true,
    "consumable": true
  }
},
{
  "metadata": {
    "narrative": "Expertly prepared fish filet. The taste alone is worth the effort.",
    "tags": ["food", "fish", "cooked", "healing", "quality"]
  },
  "itemId": "fish_filet",
  "name": "Fish Filet",
  "category": "consumable",
  "type": "food",
  "subtype": "cooked_fish",
  "tier": 2,
  "rarity": "common",
  "effect": "Restores 60 HP over 10 seconds",
  "duration": 10,
  "stackSize": 20,
  "effectTags": ["healing", "over_time", "self"],
  "effectParams": {
    "heal_per_second": 6,
    "duration": 10
  },
  "flags": {
    "stackable": true,
    "consumable": true
  }
},
{
  "metadata": {
    "narrative": "Magical fish prepared with arcane seasonings. Grants temporary mana regeneration.",
    "tags": ["food", "fish", "cooked", "magical", "mana"]
  },
  "itemId": "ethereal_fish_stew",
  "name": "Ethereal Fish Stew",
  "category": "consumable",
  "type": "food",
  "subtype": "cooked_fish",
  "tier": 3,
  "rarity": "uncommon",
  "effect": "Restores 5 mana per second for 30 seconds",
  "duration": 30,
  "stackSize": 10,
  "effectTags": ["mana", "over_time", "self"],
  "effectParams": {
    "mana_per_second": 5,
    "duration": 30
  },
  "flags": {
    "stackable": true,
    "consumable": true
  }
}
```

---

### Task 7 (Optional): Add Cooking Recipes

**File**: `recipes.JSON/recipes-alchemy-1.JSON`

```json
{
  "recipeId": "alchemy_grilled_fish_001",
  "outputId": "grilled_fish",
  "outputQty": 2,
  "stationType": "alchemy",
  "stationTier": 1,
  "discipline": "alchemy",
  "inputs": [
    {"materialId": "raw_carp", "qty": 1}
  ]
},
{
  "recipeId": "alchemy_grilled_fish_002",
  "outputId": "grilled_fish",
  "outputQty": 3,
  "stationType": "alchemy",
  "stationTier": 1,
  "discipline": "alchemy",
  "inputs": [
    {"materialId": "raw_minnow", "qty": 2}
  ]
},
{
  "recipeId": "alchemy_fish_filet_001",
  "outputId": "fish_filet",
  "outputQty": 2,
  "stationType": "alchemy",
  "stationTier": 1,
  "discipline": "alchemy",
  "inputs": [
    {"materialId": "raw_trout", "qty": 1}
  ]
},
{
  "recipeId": "alchemy_fish_filet_002",
  "outputId": "fish_filet",
  "outputQty": 2,
  "stationType": "alchemy",
  "stationTier": 1,
  "discipline": "alchemy",
  "inputs": [
    {"materialId": "raw_bass", "qty": 1}
  ]
},
{
  "recipeId": "alchemy_ethereal_fish_stew_001",
  "outputId": "ethereal_fish_stew",
  "outputQty": 1,
  "stationType": "alchemy",
  "stationTier": 2,
  "discipline": "alchemy",
  "inputs": [
    {"materialId": "raw_ghostfish", "qty": 1},
    {"materialId": "water_crystal", "qty": 1}
  ]
}
```

---

## Verification Checklist

After implementation, verify:

1. [ ] Fish materials load correctly - check `MaterialDatabase.get_instance().materials`
2. [ ] Fishing nodes appear in resource-node-1.JSON
3. [ ] Fishing spots drop tiered fish based on location tier
4. [ ] Higher-tier fishing rods exist in equipment database
5. [ ] Fishing rod recipes appear in smithing
6. [ ] (Optional) Cooked fish items work as consumables
7. [ ] (Optional) Cooking recipes appear in alchemy

## Testing Commands

In-game, use debug mode (F1) and:
1. Find a water chunk (blue area)
2. Look for fishing spots (should be visible)
3. Equip a fishing rod
4. Interact with fishing spot
5. Check inventory for fish drops

---

## File Summary

| File | Action |
|------|--------|
| `items.JSON/items-materials-1.JSON` | ADD 8 fish materials |
| `Definitions.JSON/resource-node-1.JSON` | ADD 4 fishing node definitions |
| `systems/natural_resource.py` | MODIFY tier-based fishing spot lookup |
| `items.JSON/items-smithing-2.JSON` | ADD 3 fishing rods (tier 2-4) |
| `recipes.JSON/recipes-smithing-3.json` | ADD 3 fishing rod recipes |
| `items.JSON/items-alchemy-1.JSON` | ADD 3 cooked fish consumables (optional) |
| `recipes.JSON/recipes-alchemy-1.JSON` | ADD 5 cooking recipes (optional) |

---

## Notes for Implementer

1. **JSON Format**: Always validate JSON after editing. Use `python -m json.tool filename.json`
2. **IDs must be unique**: Check existing IDs before adding new ones
3. **Tier consistency**: Fish tier should match fishing spot tier
4. **Translation tables**: Quantities like "few", "several", "many" are translated via `value-translation-table-1.JSON`
5. **Existing patterns**: Follow the exact format of existing entries in each file
