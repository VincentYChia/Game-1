# Crafting Subdisciplines Integration Checklist

## Current Understanding

### Main.py State
- ✅ Has CraftingStation class with tier and station_type
- ✅ RecipeDatabase loads all 5 disciplines from JSON
- ✅ Current crafting is instant (craft_item method line 3465)
- ✅ Inventory system exists and working
- ✅ Equipment database with stats and enchantments
- ✅ Material database with rarities
- ❌ No minigames implemented (all instant craft)
- ❌ No rarity tracking for crafted items
- ❌ No placement grid UI

### Crafting Subdisciplines State
- ✅ 5 modules: smithing.py, refining.py, alchemy.py, engineering.py, enchanting.py
- ✅ All have minigame implementations
- ✅ All have craft_instant() and craft_with_minigame() methods
- ✅ Rarity system fully implemented (rarity_utils.py)
- ✅ Placement data loading
- ✅ Stats calculation with rarity modifiers
- ⚠️ Uses different inventory format than main.py

### Game Mechanics v5 Requirements
- Mini-games are OPTIONAL (instant craft gives 0 EXP, minigame gives EXP)
- Station tier determines recipe availability
- Rarity upgrades via input material rarity
- Refining uses 4:1 ratio for rarity upgrades
- Stats multiply with rarity modifiers
- Special effects at epic/legendary rarities

## Integration Tasks

### Phase 1: Setup & Imports
- [ ] Add crafting module imports to main.py
- [ ] Import rarity_system from rarity_utils
- [ ] Add placement database loading
- [ ] Initialize crafters at game start

### Phase 2: Inventory System Bridge
- [ ] Create inventory adapter (main.py format <-> crafter format)
  - Main.py uses: ItemStack with equipment_data/material_id
  - Crafters use: Dict[material_id: quantity]
- [ ] Handle rarity tracking in ItemStack
- [ ] Add stats field to ItemStack for crafted items

### Phase 3: Crafting UI Modifications
- [ ] Modify craft_item() to support instant OR minigame
- [ ] Add "Craft (Instant)" vs "Craft (Minigame)" buttons
- [ ] Add minigame state tracking to GameEngine
- [ ] Integrate minigame rendering into main render loop

### Phase 4: Discipline-Specific Integration
**Smithing:**
- [ ] Load SmithingCrafter, recipes, placements
- [ ] Integrate temperature + hammering minigame
- [ ] Apply rarity modifiers to weapon/armor stats

**Refining:**
- [ ] Load RefiningCrafter
- [ ] Integrate cylinder alignment minigame
- [ ] Implement 4:1 rarity upgrade system
- [ ] Handle material output (not equipment)

**Alchemy:**
- [ ] Load AlchemyCrafter
- [ ] Integrate reaction chain minigame
- [ ] Handle consumable outputs

**Engineering:**
- [ ] Load EngineeringCrafter
- [ ] Integrate puzzle minigame
- [ ] Handle device stats (power, range, cooldown)

**Enchanting (Adornments):**
- [ ] Load EnchantingCrafter
- [ ] Integrate pattern drawing minigame
- [ ] Bridge to existing enchantment system

### Phase 5: Rarity System Integration
- [ ] Load rarity-modifiers.JSON
- [ ] Apply rarity modifiers to crafted equipment stats
- [ ] Display rarity in inventory tooltips
- [ ] Store rarity with ItemStack
- [ ] Material rarity tracking (for refining)

### Phase 6: EXP & Progression
- [ ] Instant craft = 0 EXP (keep current behavior)
- [ ] Minigame craft = base_exp * tier (as per Game Mechanics v5)
- [ ] Perfect craft = 2x EXP
- [ ] Add minigame performance tracking

### Phase 7: Testing
- [ ] Test smithing with T1-T4 benches
- [ ] Test refining rarity upgrades (4, 16, 64, 256 inputs)
- [ ] Test all disciplines' minigames
- [ ] Test rarity modifiers applying correctly
- [ ] Test inventory compatibility
- [ ] Test equipment stat calculations

### Phase 8: Cleanup
- [ ] Remove crafting_simulator.py (testing tool)
- [ ] Remove unused test files
- [ ] Update README if needed
- [ ] Verify all JSON paths are correct

## Critical Integration Points

### 1. Inventory Format Bridge
```python
# Main.py: ItemStack with .equipment_data or .material_id
# Crafters: Dict[str, int] = {material_id: quantity}

def inventory_to_dict(inventory: Inventory) -> Dict[str, int]:
    """Convert main.py inventory to crafter format"""
    materials = {}
    for slot in inventory.slots:
        if slot and not slot.is_equipment():
            materials[slot.item_id] = slot.quantity
    return materials

def add_crafted_item(inventory: Inventory, item_id: str, quantity: int,
                     rarity: str = 'common', stats: Dict = None):
    """Add crafted item back to main.py inventory with rarity/stats"""
    # Check if equipment or material
    # Create ItemStack with proper data
    # Handle rarity and stats storage
```

### 2. Station Click Flow
```
User clicks station
  ↓
interact_with_station(station)
  ↓
render_crafting_ui() - shows recipes
  ↓
User clicks recipe → shows "Instant" / "Minigame" buttons
  ↓
If Instant: crafter.craft_instant() → add to inventory
If Minigame: crafter.create_minigame() → enter minigame mode
  ↓
Minigame active: render minigame UI
  ↓
Minigame complete: crafter.craft_with_minigame(result) → add to inventory
```

### 3. Rarity Storage in ItemStack
```python
@dataclass
class ItemStack:
    item_id: str
    quantity: int
    equipment_data: Optional[Equipment] = None
    rarity: str = 'common'  # ADD THIS
    crafted_stats: Optional[Dict] = None  # ADD THIS for rarity-modified stats
```

### 4. Module Loading Pattern
```python
# At GameEngine.__init__
from Crafting-subdisciplines.smithing import SmithingCrafter
from Crafting-subdisciplines.refining import RefiningCrafter
from Crafting-subdisciplines.alchemy import AlchemyCrafter
from Crafting-subdisciplines.engineering import EngineeringCrafter
from Crafting-subdisciplines.enchanting import EnchantingCrafter
from Crafting-subdisciplines.rarity_utils import rarity_system

self.smithing_crafter = SmithingCrafter()
self.refining_crafter = RefiningCrafter()
# ... etc
```

## Risk Areas

1. **Inventory format mismatch** - Need careful adapter
2. **Equipment stats** - Main.py Equipment class vs crafted stats dict
3. **Rarity persistence** - Need to store rarity with items
4. **Minigame rendering** - Need to integrate into main render loop
5. **Station tier filtering** - Recipes must filter by tier
6. **JSON path resolution** - Crafters use relative paths

## Success Criteria

- ✓ All 5 crafting disciplines work in main.py
- ✓ Instant craft option available (0 EXP)
- ✓ Minigame craft option available (with EXP)
- ✓ Rarity system functional
- ✓ Stats apply correctly with modifiers
- ✓ No crashes or inventory corruption
- ✓ Station tiers gate recipes properly
