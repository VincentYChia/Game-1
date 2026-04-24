# Crafting Integration - Quick Reference Guide

## Key File Locations in main.py

| Component | Lines | Purpose |
|-----------|-------|---------|
| **Crafting Imports** | 16-28 | Loads 5 crafting modules |
| **ItemStack** | 2134-2197 | Inventory item with rarity/stats |
| **Inventory** | 2200-2314 | 30-slot inventory manager |
| **EquipmentItem** | 322-427 | Equipment definition with stats |
| **EquipmentManager** | 626-716 | 8 equipment slots |
| **EquipmentDatabase** | 429-623 | ~550 equipment items |
| **MaterialDatabase** | 181-267 | Material definitions |
| **RecipeDatabase** | 1495-1644 | All recipes for 5 disciplines |
| **PlacementDatabase** | 1711-1922 | Placement data for crafting |
| **craft_item()** | 5810-5859 | Main crafting entry point |
| **_instant_craft()** | 5861-5965 | No minigame, 0 XP |
| **_start_minigame()** | 5109-5134 | Starts minigame |
| **_complete_minigame()** | 5136-5220 | Processes minigame result |
| **add_crafted_item_to_inventory()** | 5403-5432 | Adds result to inventory |
| **inventory_to_dict()** | 5083-5093 | Converts to crafter format |
| **validate_placement()** | 5631-5808 | Validates grid placement |

---

## Crafting Module Flow

```
Player clicks station
    ↓
GameEngine.handle_station_click()
    ↓
Character.open_crafting_station()
    ↓
render_crafting_ui() displays recipes
    ↓
Player selects recipe + click "Instant" or "Minigame"
    ↓
craft_item(recipe, use_minigame)
    ├─ Checks: materials available, placement valid
    ├─ Branch A: Instant Craft
    │   ├─ inventory_to_dict() converts inventory
    │   ├─ crafter.craft_instant(recipe_id, inv_dict)
    │   ├─ Returns: {success, outputId, quantity, rarity, stats}
    │   ├─ add_crafted_item_to_inventory()
    │   ├─ Records activity (0 XP)
    │   └─ Check for titles
    │
    └─ Branch B: Minigame Craft
        ├─ get_crafter_for_station() returns crafter
        ├─ crafter.create_minigame(recipe_id)
        ├─ MinigameUI displays and captures input
        ├─ Minigame complete:
        │   ├─ inventory_to_dict()
        │   ├─ crafter.craft_with_minigame(recipe_id, inv_dict, result)
        │   ├─ consume_materials() (even on failure!)
        │   ├─ add_crafted_item_to_inventory()
        │   ├─ Records activity (XP: 20 * tier * 1.5)
        │   └─ Check for titles
        └─ Close minigame UI
```

---

## ItemStack Structure

```python
@dataclass
class ItemStack:
    item_id: str                              # 'iron_ore', 'copper_sword', etc
    quantity: int                             # How many stacked
    max_stack: int = 99                       # Limit per slot
    equipment_data: Optional[EquipmentItem]   # If equipment, the actual item
    rarity: str = 'common'                    # 'common', 'uncommon', 'rare', etc
    crafted_stats: Optional[Dict]             # {damage: 25, defense: 15, etc}
```

**Key Methods:**
- `is_equipment()` → bool
- `get_equipment()` → Optional[EquipmentItem]
- `get_material()` → Optional[MaterialDefinition]
- `can_add(amount)` → bool
- `add(amount)` → overflow

---

## EquipmentItem Structure

```python
@dataclass
class EquipmentItem:
    item_id: str                                    # 'copper_sword', 'iron_helmet'
    name: str                                       # 'Copper Sword'
    tier: int                                       # 1-4
    rarity: str                                     # 'common', 'rare', etc
    slot: str                                       # 'mainHand', 'helmet', etc
    damage: Tuple[int, int] = (0, 0)               # (min, max)
    defense: int = 0                                # Only for armor
    durability_current: int = 100
    durability_max: int = 100
    enchantments: List[Dict[str, Any]] = []        # Applied enchantments
```

**Key Methods:**
- `can_equip(character)` → (bool, str)
- `get_effectiveness()` → float (0.5-1.0 based on durability)
- `get_actual_damage()` → Tuple[int, int]
- `apply_enchantment(enchantment_id, name, effect)` → None
- `can_apply_enchantment(id, applicable_to, effect)` → (bool, str)

---

## Inventory Structure

```python
class Inventory:
    slots: List[Optional[ItemStack]]        # 30 slots, each holds 1 ItemStack
    max_slots: int = 30
    dragging_slot: Optional[int]            # When dragging, source slot
    dragging_stack: Optional[ItemStack]     # When dragging, the item
    dragging_from_equipment: bool           # Flag for equipment slot drag
```

**Key Methods:**
- `add_item(item_id, quantity, equipment_instance)` → bool
- `get_empty_slot()` → Optional[int]
- `get_item_count(item_id)` → int
- `start_drag(slot_index)` → None
- `end_drag(target_slot)` → None (smart merge/swap)
- `cancel_drag()` → None

**Rules:**
- Equipment: 1 per slot, max_stack = 1
- Materials: Multiple per slot, max_stack = 99 (or custom)
- Stacking: Identical materials combine, different items swap

---

## Recipe Structure

```python
@dataclass
class Recipe:
    recipe_id: str                              # 'copper_sword_recipe'
    output_id: str                              # 'copper_sword'
    output_qty: int                             # 1
    station_type: str                           # 'smithing', 'refining', etc
    station_tier: int                           # 1-4
    inputs: List[Dict]                          # [{materialId, quantity}, ...]
    grid_size: str = "3x3"                      # For smithing/enchanting
    mini_game_type: str = ""                    # Minigame type
    
    # Enchanting-specific
    is_enchantment: bool = False
    enchantment_name: str = ""
    applicable_to: List[str] = []               # ['weapon', 'armor', etc]
    effect: Dict = {}                           # Enchantment effect data
```

---

## Database Singleton Pattern

All databases use singleton pattern:

```python
# Get instance
db = EquipmentDatabase.get_instance()
db = RecipeDatabase.get_instance()
db = MaterialDatabase.get_instance()
db = PlacementDatabase.get_instance()

# Check loading
if not db.loaded:
    db.load_from_file(path)
```

---

## Crafter Module Interface

Each crafter has:

```python
class XXXCrafter:
    def can_craft(self, recipe_id: str, inventory: Dict) → (bool, str)
    
    def craft_instant(self, recipe_id: str, inventory: Dict) → {
        success: bool,
        outputId: str,
        quantity: int,
        rarity: str,
        stats: Optional[Dict]
    }
    
    def craft_with_minigame(self, recipe_id: str, inventory: Dict, result) → {
        success: bool,
        outputId: str,
        quantity: int,
        rarity: str,
        stats: Optional[Dict],
        message: str
    }
    
    def create_minigame(self, recipe_id: str) → MinigameInstance
```

---

## Recent Bug Fixes (Nov 13, 2025)

| Bug | Fix | Status |
|-----|-----|--------|
| pygame.font.Font.render_to() doesn't exist | Changed to render()+blit() | ✓ Fixed |
| Smithing grid coords inverted | Changed "x,y" to "y,x" format | ✓ Fixed |
| _get_crafter() method not found | Renamed to get_crafter_for_station() | ✓ Fixed |
| Enchantment selection crashes | Changed .items() to enumerate() | ✓ Fixed |
| Minigame inputs not working | Added keyboard/mouse handlers for all | ✓ Fixed |

---

## Known Issues Remaining

| Issue | Severity | Location |
|-------|----------|----------|
| Verbose debug output (ItemStack) | HIGH | 2144-2171 |
| Verbose debug output (Inventory) | HIGH | 2209-2267 |
| Duplicate crafter init | MEDIUM | 4619 & 4655 |
| Minigame render placeholders | MEDIUM | 5360-5393 |
| Missing get_placement() method | MEDIUM | PlacementDatabase |
| Coordinate system confusion | LOW | validate_placement() |

---

## Testing Checklist

When testing crafting integration:

- [ ] Instant craft works (0 XP)
- [ ] Minigame craft works (with XP)
- [ ] Rarity modifiers apply
- [ ] Equipment stats calculated correctly
- [ ] Materials consumed properly
- [ ] Inventory doesn't overflow
- [ ] All 5 disciplines work
- [ ] Station tier filtering works
- [ ] Enchantment selection shows correct items
- [ ] Placement validation passes/fails correctly
- [ ] No console spam from debug output

---

## XP Calculations

```python
# Instant Craft (No minigame)
XP = 0

# Minigame Craft (Success)
XP = 20 * station_tier * 1.5
  # Example: T3 station = 20 * 3 * 1.5 = 90 XP

# Activity Tracking
Tracked as: 'smithing', 'refining', 'alchemy', 'engineering', 'enchanting'

# Titles
Check after each craft:
  character.titles.check_for_title(activity_type, activity_count)
```

---

## Station Tier Benefits

| Tier | T1 | T2 | T3 | T4 |
|------|----|----|----|----|
| Recipes | Basic | Intermediate | Advanced | Rare |
| Grid Size | 3x3 | 5x5 | 7x7 | 9x9 |
| XP Multiple | 1x | 2x | 3x | 4x |
| Example XP | 20 | 40 | 60 | 80 |

---

## File Paths for JSON Data

```
Game-1/
├─ recipes.JSON/
│  ├─ recipes-smithing-3.json
│  ├─ recipes-refining-1.JSON
│  ├─ recipes-alchemy-1.JSON
│  ├─ recipes-engineering-1.JSON
│  └─ recipes-adornments-1.json
├─ placements.JSON/
│  ├─ placements-smithing-1.JSON
│  ├─ placements-refining-1.JSON
│  ├─ placements-alchemy-1.JSON
│  ├─ placements-engineering-1.JSON
│  └─ placements-adornments-1.JSON
├─ items.JSON/
│  └─ items-1.JSON (equipment)
├─ Definitions.JSON/
│  └─ materials-*.JSON
└─ Crafting-subdisciplines/
   ├─ smithing.py
   ├─ refining.py
   ├─ alchemy.py
   ├─ engineering.py
   ├─ enchanting.py
   └─ rarity_utils.py
```

---

## Performance Notes

- **Inventory Rendering:** All 30 slots rendered every frame (potential optimization)
- **Debug Printing:** HIGH IMPACT - currently prints for every item (remove before release)
- **Crafter Init:** Done twice (redundant)
- **Placement Validation:** O(n) where n = recipe input count (acceptable)

---

## Quick Debug Commands

Toggle debug mode:
```python
# Press F1 in game to toggle DEBUG_INFINITE_RESOURCES
if key == pygame.K_F1:
    Config.DEBUG_INFINITE_RESOURCES = not Config.DEBUG_INFINITE_RESOURCES
```

Debug mode gives:
- Infinite resources (doesn't consume)
- Infinite tool durability
- Skip all requirement checks
- Rarity checks bypassed

