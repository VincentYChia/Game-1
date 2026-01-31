# Fishing System Implementation

**Status**: FULLY IMPLEMENTED
**Date**: 2026-01-31
**Version**: 2.0

---

## Overview

The fishing system is an OSU-style rhythm minigame where players click expanding ripples on a virtual pond. Success rewards materials and XP similar to combat, while failure results in no rewards and double durability loss on the fishing rod.

### Core Mechanics

- **OSU-Style Minigame**: Click when expanding rings hit target rings
- **Stat Effects**:
  - **LCK (Luck)**: Reduces number of ripples needed (shorter game)
  - **STR (Strength)**: Increases hit tolerance (larger click area)
  - **Rod Tier/Quality**: Slows expansion speed (more time to react)
- **Win**: Get materials + XP (like killing a mob)
- **Fail**: Get nothing + double durability loss

---

## Files Created/Modified

### New Files

| File | Purpose |
|------|---------|
| `Crafting-subdisciplines/fishing.py` | OSU-style fishing minigame (~500 lines) |

### Modified Files

| File | Changes |
|------|---------|
| `items.JSON/items-materials-1.JSON` | Added 8 scale materials (2 per tier) |
| `Definitions.JSON/resource-node-1.JSON` | Added 12 fishing nodes across 4 tiers |
| `items.JSON/items-smithing-2.JSON` | Added 3 fishing rods (T2, T3, T4) |
| `recipes.JSON/recipes-smithing-3.JSON` | Added 3 fishing rod recipes |
| `data/models/world.py` | Added fishing spot ResourceType enums |
| `systems/chunk.py` | Updated fishing spot spawning logic |
| `systems/natural_resource.py` | Updated fishing spot handling |
| `core/game_engine.py` | Added fishing minigame integration |

---

## New Materials: Scales

8 new scale materials with the "scales" tag (2 per tier):

| Material ID | Tier | Rarity | Description |
|-------------|------|--------|-------------|
| common_scales | 1 | Common | Basic freshwater fish scales |
| fine_scales | 1 | Uncommon | Silvery-white iridescent scales |
| steel_scales | 2 | Uncommon | Metallic scales from ore-fed fish |
| mithril_scales | 2 | Rare | Luminous moonlight-drinking scales |
| adamantine_scales | 3 | Rare | Heat-resistant volcanic spring scales |
| orichalcum_scales | 3 | Epic | Otherworldly spirit-blessed scales |
| primordial_scales | 4 | Legendary | Dimension-phasing scales |
| chaos_scales | 4 | Legendary | Reality-warping chaotic scales |

---

## Fishing Nodes

12 unique fishing spots across 4 tiers:

### Tier 1 (3 nodes)
| Resource ID | Name | Elemental Drops | Scale Drops |
|-------------|------|-----------------|-------------|
| fishing_spot_carp | Carp Pool | water_crystal, earth_crystal | common_scales, fine_scales |
| fishing_spot_sunfish | Sunfish Shallows | fire_crystal, air_crystal | common_scales, fine_scales |
| fishing_spot_minnow | Minnow Stream | All T1 crystals | common_scales |

### Tier 2 (4 nodes - covers all T2 elements)
| Resource ID | Name | Elemental Drops | Scale Drops |
|-------------|------|-----------------|-------------|
| fishing_spot_stormfin | Stormfin Pool | lightning_shard | steel_scales, mithril_scales |
| fishing_spot_frostback | Frostback Pool | frost_essence | steel_scales, mithril_scales |
| fishing_spot_lighteye | Lighteye Grotto | light_gem | mithril_scales, steel_scales |
| fishing_spot_shadowgill | Shadowgill Depths | shadow_core | mithril_scales, steel_scales |

### Tier 3 (3 nodes)
| Resource ID | Name | Elemental Drops | Scale Drops |
|-------------|------|-----------------|-------------|
| fishing_spot_phoenixkoi | Phoenix Koi Spring | phoenix_ash, fire_crystal | adamantine_scales, orichalcum_scales |
| fishing_spot_voidswimmer | Voidswimmer Abyss | void_essence, shadow_core | adamantine_scales, orichalcum_scales |
| fishing_spot_tempesteel | Tempest Eel Waters | storm_heart, lightning_shard | orichalcum_scales, adamantine_scales |

### Tier 4 (2 nodes - full coverage)
| Resource ID | Name | Elemental Drops | Scale Drops |
|-------------|------|-----------------|-------------|
| fishing_spot_leviathan | Leviathan Deep | phoenix_ash, void_essence, storm_heart | primordial_scales, chaos_scales |
| fishing_spot_chaosscale | Chaosscale Rift | chaos_matrix, void_essence, all T3 | chaos_scales, primordial_scales |

---

## Fishing Rods

4 tiers of fishing rods:

| Item ID | Tier | Rarity | Gathering Mult | Station Tier |
|---------|------|--------|----------------|--------------|
| bamboo_fishing_rod | 1 | Common | 1.0x | 1 |
| reinforced_fishing_rod | 2 | Uncommon | 1.3x | 2 |
| mithril_fishing_rod | 3 | Rare | 1.6x | 3 |
| worldtree_fishing_rod | 4 | Epic | 2.0x | 4 |

### Rod Effects on Minigame
- Higher tier rods slow down ripple expansion
- Speed multiplier: T1=1.0x, T2=0.85x, T3=0.70x, T4=0.55x
- This gives players more time to react with better rods

---

## Minigame Mechanics

### Starting the Minigame
1. Player clicks on a fishing spot in the world
2. Must have a fishing rod equipped with tier >= spot tier
3. Fishing minigame window opens

### Gameplay
1. Ripples spawn at random positions on a virtual pond
2. Each ripple has:
   - A fixed **target ring** (what to hit)
   - An **expanding outer ring** that starts small and grows
3. Player clicks when the expanding ring overlaps the target ring
4. Scoring based on timing accuracy:
   - Within 5px = **PERFECT** (100 points)
   - Within 10px = **GOOD** (75 points)
   - Within 15px = **FAIR** (50 points)
   - Beyond tolerance = **MISS** (0 points)

### Stat Effects
- **LCK**: Each point reduces required ripples by 0.1 (min 4, max 15)
- **STR**: Each point adds 0.5px hit tolerance (max 30px)
- **Rod Tier**: Reduces expansion speed (more time to react)

### Success Criteria
- Need at least 50% hit rate
- Need at least 40 average score
- Both conditions must be met

### Rewards (Success)
- **Materials**: All drops from the fishing spot's drop table
- **XP**: Tier-based like mob kills (T1=100, T2=400, T3=1600, T4=6400)
- **Quality Bonus**: Performance multiplier (0.8x to 1.5x on rewards)
- **Durability**: Normal loss (1 point)

### Penalties (Failure)
- **No materials**
- **No XP**
- **Durability**: Double loss (2 points)

---

## Respawn Mechanics

Fishing spots respawn like other resources:
- T1: 30 seconds
- T2: 45 seconds
- T3: 60 seconds
- T4: 90 seconds
- (Debug mode: 1 second)

---

## Stat Tracking

The following fishing statistics are tracked:

**Gathering Totals**:
- `total_fish_caught`
- `fishing_rod_casts`
- `fishing_rod_durability_lost`

**Advanced Metrics**:
- `largest_fish_caught`
- `fish_catch_streak`
- `longest_fish_catch_streak`
- `rare_fish_caught`
- `legendary_fish_caught`

---

## Integration Points

### Game Engine Integration
- Fishing minigame triggered when clicking fishing spots
- Renders above all other UI
- Updates at 60 FPS like other minigames
- Results processed on click after completion

### Save System
- Fishing rod durability saved with equipment
- Fishing stats saved with character stat tracker
- Fishing spot depletion/respawn state saved with world chunks

---

## Testing

1. Find a water chunk (blue tiles on the map)
2. Look for fishing spots (deep sky blue color)
3. Equip a fishing rod (craft one at smithing station)
4. Click on a fishing spot to start minigame
5. Click ripples when rings overlap
6. Collect rewards on success

### Debug Commands
- F1: Toggle debug mode (instant respawn, infinite resources)
- F7: Toggle infinite durability

---

## Design Philosophy

The fishing system was designed to:
1. **Work with existing systems** - Uses the same resource node, spawning, and loot systems
2. **Be JSON-driven** - All fishing spots, drops, and rods defined in JSON
3. **Be scalable** - Easy to add new fishing spots, drops, or mechanics
4. **Provide unique value** - Best source of elemental materials and scales
5. **Be balanced** - Not more impactful than combat/gathering, but has its niche

---

## Future Expansion Ideas

1. **Fishing-specific enchantments** (e.g., "Lucky Lure" for better drops)
2. **Weather effects** on fishing (rain = better catches)
3. **Rare fish achievements/titles**
4. **Fishing tournaments/events**
5. **Bait system** for targeting specific fish
