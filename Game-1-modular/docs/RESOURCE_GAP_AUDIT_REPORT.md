# Resource Gap Audit Report

**Generated**: 2026-01-28
**Auditor**: Claude (Automated Analysis)
**Severity**: CRITICAL - Affects game progression

---

## Executive Summary

The game has a **fundamental JSON-to-Code desynchronization** problem. Resource definitions exist in JSON files, but the game code uses hardcoded values that only recognize 12 of 28 defined resources. This blocks player progression for any recipe requiring the 16 missing resources.

### Key Numbers

| Category | In JSON | In Code | Missing | Impact |
|----------|---------|---------|---------|--------|
| Trees | 8 | 4 | 4 | **Blocks T1-T4 wood recipes** |
| Ores | 8 | 4 | 4 | **Blocks T1-T4 metal recipes** |
| Stones | 12 | 4 | 8 | **Blocks T1-T4 stone recipes** |
| **TOTAL** | **28** | **12** | **16** | **57% of resources unusable** |

---

## 1. Complete Resource Comparison

### 1.1 Trees (JSON vs Code)

| Resource ID | JSON | Code | PNGs | Status |
|-------------|------|------|------|--------|
| oak_tree | T1 | T1 | Yes | Working |
| pine_tree | T1 | NO | NO | **MISSING** |
| ash_tree | T1 | NO | NO | **MISSING** |
| birch_tree | T2 | T2 | Yes | Working |
| maple_tree | T2 | T2 | Yes | Working |
| ironwood_tree | T3 | T3 | Yes | Working |
| ebony_tree | T3 | NO | NO | **MISSING** |
| worldtree_sapling | T4 | NO | NO | **MISSING** |

### 1.2 Ores (JSON vs Code)

| Resource ID | JSON | Code | PNGs | Status |
|-------------|------|------|------|--------|
| copper_vein | T1 | T1 (as COPPER_ORE) | Yes | Working |
| iron_deposit | T1 | T1 (as IRON_ORE) | Yes | Working |
| tin_seam | T1 | NO | NO | **MISSING** |
| steel_node | T2 | T2 (as STEEL_ORE) | Yes | Working |
| mithril_cache | T2 | T2 (as MITHRIL_ORE) | Yes | Working |
| adamantine_lode | T3 | NO | NO | **MISSING** |
| orichalcum_trove | T3 | NO | NO | **MISSING** |
| etherion_nexus | T4 | NO | NO | **MISSING** |

### 1.3 Stones (JSON vs Code)

| Resource ID | JSON | Code | PNGs | Status |
|-------------|------|------|------|--------|
| limestone_outcrop | T1 | T1 (as LIMESTONE) | Yes | Working |
| granite_formation | T1 | T1 (as GRANITE) | Yes | Working |
| shale_bed | T1 | NO | NO | **MISSING** |
| basalt_column | T2 | NO | NO | **MISSING** |
| marble_quarry | T2 | NO | NO | **MISSING** |
| quartz_cluster | T2 | NO | NO | **MISSING** |
| obsidian_flow | T3 | T3 (as OBSIDIAN) | Yes | Working |
| voidstone_shard | T3 | NO | NO | **MISSING** |
| diamond_geode | T3 | NO | NO | **MISSING** |
| eternity_monolith | T4 | NO | NO | **MISSING** |
| primordial_formation | T4 | NO | NO | **MISSING** |
| genesis_structure | T4 | NO | NO | **MISSING** |
| star_crystal* | N/A | T4 | Yes | **In code but NOT in JSON** |

*Note: `star_crystal` exists in code but has no corresponding JSON node definition

---

## 2. Hardcoding Locations

The following files contain hardcoded resource values instead of reading from JSON:

### 2.1 data/models/world.py (Lines 58-90)

**Problem**: `ResourceType` enum is hardcoded with only 12 resources.

```python
class ResourceType(Enum):
    """Types of harvestable resources"""
    OAK_TREE = "oak_tree"
    BIRCH_TREE = "birch_tree"
    MAPLE_TREE = "maple_tree"
    IRONWOOD_TREE = "ironwood_tree"
    COPPER_ORE = "copper_ore"
    IRON_ORE = "iron_ore"
    STEEL_ORE = "steel_ore"
    MITHRIL_ORE = "mithril_ore"
    LIMESTONE = "limestone"
    GRANITE = "granite"
    OBSIDIAN = "obsidian"
    STAR_CRYSTAL = "star_crystal"
```

**Also hardcoded**: `RESOURCE_TIERS` dictionary (lines 74-90) with tier mappings for only 12 resources.

### 2.2 systems/chunk.py (Lines 49-62)

**Problem**: Spawn code uses hardcoded `ResourceType` lists.

```python
if "forest" in self.chunk_type.value:
    types = [ResourceType.OAK_TREE, ResourceType.BIRCH_TREE,
             ResourceType.MAPLE_TREE, ResourceType.IRONWOOD_TREE]
elif "quarry" in self.chunk_type.value:
    types = [ResourceType.LIMESTONE, ResourceType.GRANITE,
             ResourceType.OBSIDIAN, ResourceType.STAR_CRYSTAL]
else:  # cave
    types = [ResourceType.COPPER_ORE, ResourceType.IRON_ORE,
             ResourceType.STEEL_ORE, ResourceType.MITHRIL_ORE]
```

### 2.3 systems/natural_resource.py (Lines 32-39)

**Problem**: Loot table is hardcoded with only 12 resources.

```python
loot_map = {
    ResourceType.OAK_TREE: ("oak_log", 2, 4),
    ResourceType.BIRCH_TREE: ("birch_log", 2, 4),
    ResourceType.MAPLE_TREE: ("maple_log", 2, 5),
    ResourceType.IRONWOOD_TREE: ("ironwood_log", 3, 6),
    ResourceType.COPPER_ORE: ("copper_ore", 1, 3),
    ResourceType.IRON_ORE: ("iron_ore", 1, 3),
    ResourceType.STEEL_ORE: ("steel_ore", 2, 4),
    ResourceType.MITHRIL_ORE: ("mithril_ore", 2, 5),
    ResourceType.LIMESTONE: ("limestone", 1, 2),
    ResourceType.GRANITE: ("granite", 1, 2),
    ResourceType.OBSIDIAN: ("obsidian", 2, 3),
    ResourceType.STAR_CRYSTAL: ("star_crystal", 1, 2),
}
```

### 2.4 assets/icons/unified_icon_generator.py (Lines 58-84)

**Problem**: Intentionally uses hardcoded `RESOURCES` list.

```python
# Hardcoded resources (from ResourceType enum in code)
RESOURCES = [
    {'id': 'oak_tree', 'name': 'Oak Tree', 'tier': 1, ...},
    # ... only 12 resources
]
```

**Comment in code** (lines 396-401):
> "resource-node-1.JSON contains 28 resources for future expansion, but the game only currently uses the 12 resources defined in the ResourceType enum."

---

## 3. Blocked Recipes Analysis

### 3.1 Recipes Blocked by Missing Trees

| Recipe ID | Requires | Discipline |
|-----------|----------|------------|
| smithing_copper_spear | ash_log | Smithing |
| smithing_iron_pickaxe | ash_plank | Smithing |
| smithing_composite_longbow | ash_plank | Smithing |
| smithing_pine_shortbow | pine_plank | Smithing |
| smithing_ebony_staff | ebony_plank | Smithing |
| smithing_ebony_wand | ebony_plank | Smithing |
| smithing_ebony_rod | ebony_plank | Smithing |
| refining_ash_log_to_plank | ash_log | Refining |
| refining_pine_log_to_plank | pine_log | Refining |
| refining_ebony_log_to_plank | ebony_log | Refining |
| refining_worldtree_log_to_plank | worldtree_log | Refining |
| adornments (multiple) | ash_plank, ebony_plank, worldtree_plank | Adornments |

### 3.2 Recipes Blocked by Missing Ores

| Recipe ID | Requires | Discipline |
|-----------|----------|------------|
| refining_tin_ore_to_ingot | tin_ore | Refining |
| refining_adamantine_ore_to_ingot | adamantine_ore | Refining |
| refining_orichalcum_ore_to_ingot | orichalcum_ore | Refining |
| refining_etherion_ore_to_ingot | etherion_ore | Refining |
| alchemy_void_elixir | voidstone (from missing node) | Alchemy |
| enchanting_unbreaking_ii | adamantine_ingot | Enchanting |
| enchanting_multi_projectile_iii | orichalcum_ingot | Enchanting |
| engineering_teleport_beacon | orichalcum_ingot | Engineering |
| adornments (multiple) | adamantine_ingot, orichalcum_ingot | Adornments |

### 3.3 Recipes Blocked by Missing Stones

| Recipe ID | Requires | Discipline |
|-----------|----------|------------|
| adornments (multiple) | marble | Adornments |
| adornments_shale_foundation | shale | Adornments |
| smithing_volcanic_hammer | basalt | Smithing |
| adornments (multiple) | crystal_quartz | Adornments |
| enchanting (multiple) | crystal_quartz | Enchanting |
| engineering_mana_battery | crystal_quartz | Engineering |
| adornments (multiple) | diamond | Adornments |
| enchanting_fortune_ii | diamond | Enchanting |
| enchanting_mana_infusion_iii | diamond, genesis_lattice | Enchanting |
| adornments_ultimate | voidstone, eternity_stone, primordial_crystal | Adornments |

---

## 4. Why unified_icon_generator.py Didn't Create Resource PNGs

The `unified_icon_generator.py` file contains the answer at lines 396-401:

```python
def extract_resources(base_path: Path) -> List[EntityEntry]:
    """Extract resources from hardcoded RESOURCES list (matches game's ResourceType enum)

    Note: resource-node-1.JSON contains 28 resources for future expansion, but the game
    only currently uses the 12 resources defined in the ResourceType enum.
    """
    return [...]
```

**Root Cause**: The icon generator was intentionally designed to only generate icons for resources that actually spawn in the game. Since the game code only supports 12 resources, the generator only creates 12 resource icons.

**This was a design decision, not a bug** - but it reveals the deeper architectural problem.

---

## 5. Architectural Issues

### 5.1 ID Mismatch Between JSON and Code

The JSON uses descriptive suffixes, while the code uses simplified names:

| JSON ID | Code ID |
|---------|---------|
| copper_vein | COPPER_ORE |
| iron_deposit | IRON_ORE |
| limestone_outcrop | LIMESTONE |
| granite_formation | GRANITE |
| obsidian_flow | OBSIDIAN |

This mismatch prevents simple JSON-to-code mapping.

### 5.2 No Resource Node Database Loader

Unlike materials (`MaterialDatabase`), recipes (`RecipeDatabase`), etc., there is **no** `ResourceNodeDatabase` singleton that loads from `resource-node-1.JSON`.

### 5.3 Circular Dependency Risk

The design intentionally avoids loading resource data from JSON because:
1. `ResourceType` enum is used in type hints throughout the codebase
2. Changing to dynamic resource loading would require significant refactoring
3. The chunk spawning system relies on compile-time enum values

---

## 6. Recommendations

### 6.1 Short-Term Fix (Expand Hardcoded Values)

Add the missing 16 resources to all hardcoded locations:

1. **data/models/world.py**: Add to `ResourceType` enum and `RESOURCE_TIERS`
2. **systems/chunk.py**: Add new resources to spawn lists by tier
3. **systems/natural_resource.py**: Add to `loot_map`
4. **assets/icons/unified_icon_generator.py**: Add to `RESOURCES` list, then regenerate icons

**Estimated effort**: 2-4 hours

### 6.2 Long-Term Fix (JSON-Driven Architecture)

Create a `ResourceNodeDatabase` singleton that:
1. Loads resource definitions from `resource-node-1.JSON`
2. Dynamically generates spawn lists by category/tier
3. Provides loot tables from JSON `drops` field
4. Eliminates hardcoded `ResourceType` enum (use string IDs)

**Estimated effort**: 8-16 hours (includes testing)

### 6.3 Critical Path Priority

For immediate game playability, prioritize adding:

1. **ash_tree** - Required for T1 weapon recipes (copper spear, iron pickaxe)
2. **pine_tree** - Required for T1 bow recipes
3. **tin_seam** - Required for bronze alloy recipes
4. **marble_quarry** - Required for multiple enchantments
5. **crystal_quartz** - Required for magical recipes

---

## 7. Files Modified in This Audit

None - this is a read-only analysis report.

## 8. Related Documentation

- `/home/user/Game-1/Game-1-modular/Definitions.JSON/resource-node-1.JSON` - Full resource definitions (28 nodes)
- `/home/user/Game-1/Game-1-modular/data/models/world.py` - ResourceType enum (12 resources)
- `/home/user/Game-1/Game-1-modular/systems/chunk.py` - Spawn logic
- `/home/user/Game-1/Game-1-modular/systems/natural_resource.py` - Loot tables
- `/home/user/Game-1/Game-1-modular/assets/icons/unified_icon_generator.py` - Icon generation

---

## Appendix A: Complete Missing Resources List

### Trees (4 missing)
1. `pine_tree` (T1) - Drops: pine_log
2. `ash_tree` (T1) - Drops: ash_log
3. `ebony_tree` (T3) - Drops: ebony_log
4. `worldtree_sapling` (T4) - Drops: worldtree_log

### Ores (4 missing)
1. `tin_seam` (T1) - Drops: tin_ore
2. `adamantine_lode` (T3) - Drops: adamantine_ore
3. `orichalcum_trove` (T3) - Drops: orichalcum_ore
4. `etherion_nexus` (T4) - Drops: etherion_ore

### Stones (8 missing)
1. `shale_bed` (T1) - Drops: shale, earth_crystal
2. `basalt_column` (T2) - Drops: basalt, fire_crystal
3. `marble_quarry` (T2) - Drops: marble, light_gem
4. `quartz_cluster` (T2) - Drops: crystal_quartz, lightning_shard
5. `voidstone_shard` (T3) - Drops: voidstone, void_essence
6. `diamond_geode` (T3) - Drops: diamond, storm_heart
7. `eternity_monolith` (T4) - Drops: eternity_stone
8. `primordial_formation` (T4) - Drops: primordial_crystal
9. `genesis_structure` (T4) - Drops: genesis_lattice, chaos_matrix

---

**Report generated for Game-1 repository audit**
