# Naming Conventions - Game-1

**Purpose:** Establish consistent naming patterns across all modules to prevent API mismatches and improve code maintainability.

**Reference:** This document is referenced in Game Mechanics v5 (see top of document)

---

## Core Principles

1. **Be Consistent:** Use the same names for the same concepts across all modules
2. **Be Descriptive:** Names should clearly indicate purpose
3. **Be Concise:** Avoid unnecessary verbosity (e.g., `chain()` not `chain_ingredient()`)
4. **Be Standard:** Follow Python PEP 8 naming conventions

---

## Method Naming Patterns

### Character Progression

| Concept | Correct Name | ❌ Avoid | Location |
|---------|--------------|----------|----------|
| Add experience | `add_exp(amount, source="")` | `gain_exp()`, `give_exp()` | LevelingSystem |
| Check level up | `check_level_up()` | `level_up()`, `try_level()` | LevelingSystem |
| Allocate stat | `allocate_stat_point(stat_name)` | `add_stat()`, `increase_stat()` | Character |

### Equipment System

| Concept | Correct Name | ❌ Avoid | Notes |
|---------|--------------|----------|-------|
| Equipment slots dict | `equipment.slots` | `equipment.items()` | It's an attribute, not a method |
| Iterate equipment | `equipment.slots.items()` | `equipment.items()` | Use .slots.items() |
| Get bonuses | `get_stat_bonuses()` | `calculate_bonuses()` | Returns Dict[str, float] |

### Minigame Actions

| Discipline | Action | Method Name | ❌ Avoid |
|------------|--------|-------------|----------|
| Smithing | Fan flames | `handle_fan()` | `fan_flames()`, `increase_temp()` |
| Smithing | Strike hammer | `handle_hammer()` | `hammer_strike()`, `hit()` |
| Alchemy | Chain reaction | `chain()` | `chain_ingredient()`, `add_ingredient()` |
| Alchemy | Stabilize | `stabilize()` | `stabilize_reaction()` |
| Refining | Align cylinders | `handle_attempt()` | `align_cylinder()`, `try_align()` |
| Engineering | Check solution | `check_current_puzzle()` | `complete_puzzle()`, `solve()` |

### Minigame Lifecycle

| Stage | Method Name | Parameters | Returns | Notes |
|-------|-------------|------------|---------|-------|
| Initialize | `__init__(recipe, tier)` | recipe dict, tier int | - | All minigames |
| Start | `start()` | None | None | Begin minigame |
| Update | `update(dt)` | dt: float | None | **Skip for engineering (turn-based)** |
| Get state | `get_state()` | None | dict | For rendering |
| End | `end(...)` | Varies by discipline | None | Complete minigame |

---

## Data Structure Naming

### Inventory Conversion

```python
# ✅ CORRECT - Main.py to Crafter format
inv_dict = {}  # Dict[str, int] mapping item_id -> quantity
for slot in inventory.slots:
    if slot:
        inv_dict[slot.item_id] = inv_dict.get(slot.item_id, 0) + slot.quantity

# ❌ WRONG - Don't call it "materials" when it includes equipment
materials = {}  # Ambiguous name
```

### Recipe Input Fields

| Correct Field | Alternative Field | Type | Usage |
|---------------|-------------------|------|-------|
| `materialId` | `itemId` | str | Primary - use `materialId` |
| `quantity` | `qty` | int | Use full word |
| `outputId` | - | str | Recipe output |
| `outputQty` | `outputQuantity` | int | Recipe output amount |

**Important:** When reading recipe inputs, always support BOTH field names:
```python
mat_id = inp.get('materialId') or inp.get('itemId')  # Defensive programming
```

---

## Class and Module Naming

### Crafting Modules

| Module | Class | Crafter Class | Minigame Class |
|--------|-------|---------------|----------------|
| smithing.py | - | `SmithingCrafter` | `SmithingMinigame` |
| refining.py | - | `RefiningCrafter` | `RefiningMinigame` |
| alchemy.py | - | `AlchemyCrafter` | `AlchemyMinigame` |
| engineering.py | - | `EngineeringCrafter` | `EngineeringMinigame` |
| enchanting.py | - | `EnchantingCrafter` | `EnchantingMinigame` |

### Database Classes

| Concept | Class Name | Singleton Method | Instance Attribute |
|---------|------------|------------------|-------------------|
| Materials | `MaterialDatabase` | `get_instance()` | `materials: Dict[str, MaterialDefinition]` |
| Equipment | `EquipmentDatabase` | `get_instance()` | `equipment: Dict[str, EquipmentDefinition]` |
| Recipes | `RecipeDatabase` | `get_instance()` | `recipes: Dict[str, Recipe]` |
| Titles | `TitleDatabase` | `get_instance()` | `titles: Dict[str, TitleDefinition]` |
| Skills | `SkillDatabase` | `get_instance()` | `skills: Dict[str, SkillDefinition]` |

---

## Common Patterns

### Singleton Pattern (All Databases)

```python
class SomeDatabase:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SomeDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        # Load JSON and populate self.items dict
        pass
```

### Minigame Update Pattern

```python
# In main.py update loop
if self.active_minigame:
    # Skip update for turn-based minigames
    if self.minigame_type != 'engineering':
        self.active_minigame.update(dt)
```

### Defensive Material Access

```python
# ✅ CORRECT - Handle both field names and missing keys
for inp in recipe['inputs']:
    mat_id = inp.get('materialId') or inp.get('itemId')
    qty = inp.get('quantity', 1)

    if mat_id not in inventory:
        inventory[mat_id] = 0  # Defensive - prevents KeyError

    inventory[mat_id] = max(0, inventory[mat_id] - qty)

# ❌ WRONG - Crashes on missing key
for inp in recipe['inputs']:
    inventory[inp['materialId']] -= inp['quantity']  # KeyError!
```

---

## Attributes vs Methods

### When to Use Attributes (Direct Access)

```python
# ✅ Simple data access
equipment.slots  # Dict attribute
character.stats  # CharacterStats object
inventory.slots  # List[Optional[ItemStack]]
```

### When to Use Methods (Computed/Action)

```python
# ✅ Computation or action required
equipment.get_stat_bonuses()  # Calculates and returns bonuses
equipment.equip_item(item, slot)  # Performs action
inventory.add_item(item_id, quantity)  # Modifies state
```

---

## API Compatibility Checklist

Before calling a method from another module, verify:

1. ✅ Method name matches exactly (use grep/search)
2. ✅ Parameter types match (int, str, dict, etc.)
3. ✅ Parameter count matches (required vs optional)
4. ✅ Return type is what you expect
5. ✅ Attribute exists if accessing directly (not a method call)

### Example Verification Process

```bash
# Check if method exists in target module
grep -n "def method_name" target_module.py

# Check method signature
grep -A 5 "def method_name" target_module.py

# Check all calls to that method
grep -n "method_name(" calling_module.py
```

---

## JSON Field Naming

### Material/Item JSONs

```json
{
  "materialId": "iron_ore",  // Primary key (prefer over itemId)
  "itemId": "iron_ore",      // Alternative (support both)
  "name": "Iron Ore",
  "tier": 1,
  "category": "ore",
  "max_stack": 99
}
```

### Recipe JSONs

```json
{
  "recipeId": "smithing_iron_sword_001",
  "outputId": "iron_sword",
  "outputQty": 1,
  "stationTier": 1,
  "inputs": [
    {
      "materialId": "iron_ingot",  // Prefer materialId
      "quantity": 3
    }
  ]
}
```

### Minigame Result Format

```json
{
  "success": true,
  "score": 132.0,
  "bonus": 10,
  "message": "Crafted with 10% bonus!",
  "temp_mult": 1.5  // Smithing-specific
}
```

---

## Error Prevention Rules

1. **Always use .get() for dict access when key might not exist**
   ```python
   value = my_dict.get('key', default_value)  # Safe
   value = my_dict['key']  # Can crash!
   ```

2. **Check hasattr() before calling methods on minigames**
   ```python
   if hasattr(self.active_minigame, 'update'):
       self.active_minigame.update(dt)
   ```

3. **Support multiple field name variants**
   ```python
   mat_id = inp.get('materialId') or inp.get('itemId')  # Handles both
   ```

4. **Validate inventory before crafting**
   ```python
   # Add missing recipe inputs with quantity 0
   for inp in recipe.inputs:
       mat_id = inp.get('materialId') or inp.get('itemId')
       if mat_id not in inv_dict:
           inv_dict[mat_id] = 0
   ```

---

## Testing Checklist

When adding a new feature:

- [ ] Check all method names match conventions above
- [ ] Grep for similar patterns in existing code
- [ ] Add defensive programming for dict access
- [ ] Support both materialId and itemId field names
- [ ] Handle missing inventory items gracefully
- [ ] Document any new patterns in this file

---

## Reference Quick Links

- **Method Names:** See "Method Naming Patterns" section above
- **Data Structures:** See "Data Structure Naming" section
- **Common Errors:** See ERROR_ANALYSIS_AND_FIXES.md
- **Architecture:** See MAIN_PY_ANALYSIS.md

---

**Last Updated:** November 16, 2025
**Maintained By:** Development Team
**Status:** Living Document - Update as patterns evolve
