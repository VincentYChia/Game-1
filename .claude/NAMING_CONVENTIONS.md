# Naming Conventions - Game-1

**Purpose:** Establish consistent naming patterns across all modules to prevent API mismatches and improve code maintainability.

**Reference:** This document is referenced in Game Mechanics v6 (see top of document)
**Last Updated:** January 27, 2026

---

## Core Principles

1. **Be Consistent:** Use the same names for the same concepts across all modules
2. **Be Descriptive:** Names should clearly indicate purpose
3. **Be Concise:** Avoid unnecessary verbosity (e.g., `chain()` not `chain_ingredient()`)
4. **Be Standard:** Follow Python PEP 8 naming conventions

---

## Module Paths (Modular Architecture)

### Core Modules
| Module | Path | Purpose |
|--------|------|---------|
| Config | `core/config.py` | Game constants |
| GameEngine | `core/game_engine.py` | Main game loop |
| Camera | `rendering/camera.py` | Viewport/camera |
| Renderer | `rendering/renderer.py` | All rendering |

### Data Layer
| Module | Path | Purpose |
|--------|------|---------|
| MaterialDatabase | `data/databases/material_db.py` | Material definitions |
| EquipmentDatabase | `data/databases/equipment_db.py` | Equipment items |
| RecipeDatabase | `data/databases/recipe_db.py` | Crafting recipes |
| SkillDatabase | `data/databases/skill_db.py` | Skill definitions |
| TitleDatabase | `data/databases/title_db.py` | Title definitions |
| ClassDatabase | `data/databases/class_db.py` | Class definitions |
| PlacementDatabase | `data/databases/placement_db.py` | Crafting layouts |
| TranslationDatabase | `data/databases/translation_db.py` | Text translations |

### Entity Components
| Module | Path | Purpose |
|--------|------|---------|
| Character | `entities/character.py` | Player entity |
| Inventory | `entities/components/inventory.py` | Item storage |
| EquipmentManager | `entities/components/equipment_manager.py` | Equipment slots |
| SkillManager | `entities/components/skill_manager.py` | Skill activation |
| CharacterStats | `entities/components/stats.py` | Stat calculations |
| LevelingSystem | `entities/components/leveling.py` | XP and levels |
| BuffManager | `entities/components/buffs.py` | Active buffs |

### Systems
| Module | Path | Purpose |
|--------|------|---------|
| WorldSystem | `systems/world_system.py` | World generation |
| TitleSystem | `systems/title_system.py` | Title acquisition |
| ClassSystem | `systems/class_system.py` | Class bonuses |
| CombatManager | `Combat/combat_manager.py` | Combat system |
| LLMItemGenerator | `systems/llm_item_generator.py` | LLM-powered item generation (NEW) |
| CraftingClassifierManager | `systems/crafting_classifier.py` | CNN/LightGBM validation (NEW) |

---

## Method Naming Patterns

### Character Progression

| Concept | Correct Name | Avoid | Location |
|---------|--------------|-------|----------|
| Add experience | `add_exp(amount, source="")` | `gain_exp()`, `give_exp()` | LevelingSystem |
| Check level up | `check_level_up()` | `level_up()`, `try_level()` | LevelingSystem |
| Allocate stat | `allocate_stat_point(stat_name)` | `add_stat()`, `increase_stat()` | Character |
| Recalculate stats | `recalculate_stats()` | `update_stats()` | Character |

### Equipment System

| Concept | Correct Name | Avoid | Notes |
|---------|--------------|-------|-------|
| Equipment slots dict | `equipment.slots` | `equipment.items()` | It's an attribute, not a method |
| Iterate equipment | `equipment.slots.items()` | `equipment.items()` | Use .slots.items() |
| Get bonuses | `get_stat_bonuses()` | `calculate_bonuses()` | Returns Dict[str, float] |
| Equip item | `equip_item(item, slot)` | `equip()`, `wear()` | EquipmentManager |
| Unequip item | `unequip_item(slot)` | `unequip()`, `remove()` | EquipmentManager |

### Combat System

| Concept | Correct Name | Avoid | Location |
|---------|--------------|-------|----------|
| Calculate damage | `calculate_damage(attacker, target, weapon)` | `get_damage()` | CombatManager |
| Apply damage | `apply_damage(target, amount, damage_type)` | `deal_damage()` | CombatManager |
| Apply status effect | `apply_status_effect(target, effect_type, duration)` | `add_effect()` | CombatManager |
| Process enchantments | `process_enchantments(weapon, target, damage)` | `apply_enchantments()` | CombatManager |
| Check if in combat | `is_in_combat()` | `in_combat` | Character |

### Skill System

| Concept | Correct Name | Avoid | Location |
|---------|--------------|-------|----------|
| Activate skill | `activate_skill(slot, character)` | `use_skill()`, `cast()` | SkillManager |
| Learn skill | `learn_skill(skill_id, ...)` | `add_skill()` | SkillManager |
| Get affinity bonus | `get_skill_affinity_bonus(skill_tags)` | `calculate_affinity()` | ClassDefinition |
| Apply skill effect | `_apply_skill_effect(skill, target)` | `do_effect()` | SkillManager |
| Check cooldown | `is_on_cooldown(skill_id)` | `cooldown_active()` | SkillManager |
| Get mana cost | `get_mana_cost(skill)` | `mana_required()` | SkillManager |

### Tag System

| Concept | Correct Name | Avoid | Location |
|---------|--------------|-------|----------|
| Get effect tags | `get_effect_tags()` | `tags()` | Equipment/Skill models |
| Process tags | `process_tags(tags, params)` | `handle_tags()` | EffectExecutor |
| Apply geometry | `apply_geometry(tags, source, target)` | `get_targets()` | EffectExecutor |
| Get tag debugger | `get_tag_debugger()` | `debug_tags()` | core/tag_debug |

### LLM Integration System (NEW - January 2026)

| Concept | Correct Name | Avoid | Location |
|---------|--------------|-------|----------|
| Generate item | `generate_item(materials, discipline, callback)` | `create_item()` | LLMItemGenerator |
| Build prompt | `_build_prompt(materials, discipline)` | `create_prompt()` | LLMItemGenerator |
| Parse response | `_parse_response(response)` | `extract_item()` | LLMItemGenerator |
| Validate placement | `validate_placement(placement, discipline)` | `check_placement()` | CraftingClassifierManager |
| Preprocess image | `preprocess(grid)` | `convert_grid()` | SmithingCNN/AdornmentsCNN |
| Extract features | `extract_features(placement)` | `get_features()` | LightGBM classifiers |
| Run prediction | `predict(input)` | `classify()` | All classifiers |

### Classifier Class Naming

| Discipline | CNN Class | LightGBM Class |
|------------|-----------|----------------|
| Smithing | `SmithingCNN` | N/A |
| Adornments | `AdornmentsCNN` | N/A |
| Alchemy | N/A | `AlchemyLightGBM` |
| Refining | N/A | `RefiningLightGBM` |
| Engineering | N/A | `EngineeringLightGBM` |

### Minigame Actions

| Discipline | Action | Method Name | Avoid |
|------------|--------|-------------|-------|
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

### Save/Load System

| Concept | Correct Name | Avoid | Location |
|---------|--------------|-------|----------|
| Save game | `save_game(filepath)` | `write_save()` | SaveManager |
| Load game | `load_game(filepath)` | `read_save()` | SaveManager |
| Get save data | `get_save_data()` | `to_dict()` | Character |
| Load from data | `load_from_data(data)` | `from_dict()` | Character |
| Auto-save | `auto_save()` | `quick_save()` | GameEngine |

---

## Data Structure Naming

### Inventory Conversion

```python
# CORRECT - Main.py to Crafter format
inv_dict = {}  # Dict[str, int] mapping item_id -> quantity
for slot in inventory.slots:
    if slot:
        inv_dict[slot.item_id] = inv_dict.get(slot.item_id, 0) + slot.quantity

# WRONG - Don't call it "materials" when it includes equipment
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

### Tag System Fields

| Field | Type | Used In | Example |
|-------|------|---------|---------|
| `tags` | List[str] | Skills, Equipment | `["fire", "circle", "burn"]` |
| `effectParams` | Dict | Skills | `{"baseDamage": 50, "circle_radius": 3.0}` |
| `attackTags` | List[str] | Weapons | `["physical", "single"]` |
| `attackParams` | Dict | Weapons | `{"burn_duration": 3.0}` |
| `effectTags` | List[str] | Turrets | `["fire", "piercing", "burn"]` |

---

## Class and Module Naming

### Crafting Modules

| Module | Crafter Class | Minigame Class |
|--------|---------------|----------------|
| smithing.py | `SmithingCrafter` | `SmithingMinigame` |
| refining.py | `RefiningCrafter` | `RefiningMinigame` |
| alchemy.py | `AlchemyCrafter` | `AlchemyMinigame` |
| engineering.py | `EngineeringCrafter` | `EngineeringMinigame` |
| enchanting.py | `EnchantingCrafter` | `EnchantingMinigame` |

### Database Classes

| Concept | Class Name | Singleton Method | Instance Attribute |
|---------|------------|------------------|-------------------|
| Materials | `MaterialDatabase` | `get_instance()` | `materials: Dict[str, MaterialDefinition]` |
| Equipment | `EquipmentDatabase` | `get_instance()` | `equipment: Dict[str, EquipmentDefinition]` |
| Recipes | `RecipeDatabase` | `get_instance()` | `recipes: Dict[str, Recipe]` |
| Titles | `TitleDatabase` | `get_instance()` | `titles: Dict[str, TitleDefinition]` |
| Skills | `SkillDatabase` | `get_instance()` | `skills: Dict[str, SkillDefinition]` |
| Classes | `ClassDatabase` | `get_instance()` | `classes: Dict[str, ClassDefinition]` |

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
# In game_engine.py update loop
if self.active_minigame:
    # Skip update for turn-based minigames
    if self.minigame_type != 'engineering':
        self.active_minigame.update(dt)
```

### Defensive Material Access

```python
# CORRECT - Handle both field names and missing keys
for inp in recipe['inputs']:
    mat_id = inp.get('materialId') or inp.get('itemId')
    qty = inp.get('quantity', 1)

    if mat_id not in inventory:
        inventory[mat_id] = 0  # Defensive - prevents KeyError

    inventory[mat_id] = max(0, inventory[mat_id] - qty)

# WRONG - Crashes on missing key
for inp in recipe['inputs']:
    inventory[inp['materialId']] -= inp['quantity']  # KeyError!
```

### Tag Processing Pattern

```python
# CORRECT - Check for tags before processing
if 'burn' in tags:
    duration = params.get('burn_duration', 5.0)
    damage = params.get('burn_damage_per_second', 5.0)
    apply_status_effect(target, 'burn', duration, damage)

if 'chain' in tags:
    chain_count = params.get('chain_count', 2)
    chain_range = params.get('chain_range', 5.0)
    # Chain logic...
```

---

## Attributes vs Methods

### When to Use Attributes (Direct Access)

```python
# Simple data access
equipment.slots  # Dict attribute
character.stats  # CharacterStats object
inventory.slots  # List[Optional[ItemStack]]
skill.tags       # List[str]
```

### When to Use Methods (Computed/Action)

```python
# Computation or action required
equipment.get_stat_bonuses()  # Calculates and returns bonuses
equipment.equip_item(item, slot)  # Performs action
inventory.add_item(item_id, quantity)  # Modifies state
skill_manager.activate_skill(slot, character)  # Complex action
class_def.get_skill_affinity_bonus(skill_tags)  # Calculation
```

---

## API Compatibility Checklist

Before calling a method from another module, verify:

1. Method name matches exactly (use grep/search)
2. Parameter types match (int, str, dict, etc.)
3. Parameter count matches (required vs optional)
4. Return type is what you expect
5. Attribute exists if accessing directly (not a method call)

### Example Verification Process

```bash
# Check if method exists in target module
grep -n "def method_name" entities/character.py

# Check method signature
grep -A 5 "def method_name" entities/character.py

# Check all calls to that method
grep -n "method_name(" core/game_engine.py
```

---

## JSON Field Naming

### Material/Item JSONs

```json
{
  "materialId": "iron_ore",
  "itemId": "iron_ore",
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
  "stationType": "smithing",
  "stationTier": 1,
  "inputs": [
    {
      "materialId": "iron_ingot",
      "quantity": 3
    }
  ]
}
```

**CRITICAL RULE: Station Type Naming**
- Use `"stationType": "adornments"` for enchanting/adornment recipes
- **NEVER** use `"stationType": "enchanting"` - the game does not recognize this!
- Valid station types: `"smithing"`, `"alchemy"`, `"refining"`, `"engineering"`, `"adornments"`

### Skill JSONs

```json
{
  "skillId": "fireball",
  "name": "Fireball",
  "tags": ["fire", "circle", "burn"],
  "effectParams": {
    "baseDamage": 50,
    "circle_radius": 3.0,
    "burn_duration": 5.0,
    "burn_damage_per_second": 8.0
  },
  "manaCost": "moderate",
  "cooldown": "short",
  "duration": "instant"
}
```

### Class JSONs

```json
{
  "classId": "warrior",
  "name": "Warrior",
  "tags": ["warrior", "melee", "physical", "tanky", "frontline"],
  "preferredDamageTypes": ["physical", "slashing", "crushing"],
  "preferredArmorType": "heavy",
  "startingSkill": "battle_rage",
  "bonuses": {
    "health": 30,
    "melee_damage": 0.10
  }
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

5. **Check tag existence before accessing params**
   ```python
   if 'burn' in tags and 'burn_duration' in params:
       # Safe to process burn effect
   ```

---

## Testing Checklist

When adding a new feature:

- [ ] Check all method names match conventions above
- [ ] Grep for similar patterns in existing code
- [ ] Add defensive programming for dict access
- [ ] Support both materialId and itemId field names
- [ ] Handle missing inventory items gracefully
- [ ] Check tag parameters exist before using
- [ ] Document any new patterns in this file

---

## Coordinate Systems

### Smithing & Adornments Grid Coordinates

**JSON Format:** Placement JSONs use **"row,col" format** which is **(Y,X)** with **1-based indexing**.

**UI Format:** Internal UI code uses **(x,y)** where **x=column, y=row** with **0-based indexing**.

#### Conversion Formula

```python
# UI to JSON (0-indexed (x,y) → 1-indexed "row,col")
json_key = f"{y+1},{x+1}"  # row,col = Y,X

# Example:
# UI position (3, 5) → JSON key "6,4"
#   - y=5 → row=6 (5+1)
#   - x=3 → col=4 (3+1)
```

#### Critical Rules

1. **JSON keys are ALWAYS "row,col" (Y,X)**, NOT "col,row" (X,Y)
2. **Use f"{y+1},{x+1}"** when converting UI coords to JSON format
3. **JSON indices start at 1**, UI indices start at 0
4. **row = y-coordinate** (vertical), **col = x-coordinate** (horizontal)

#### Examples

| UI Coords (0-indexed) | JSON Key (1-indexed) | Explanation |
|-----------------------|----------------------|-------------|
| (0, 0) | "1,1" | Top-left corner |
| (2, 0) | "1,3" | Top row, 3rd column |
| (0, 2) | "3,1" | 3rd row, 1st column |
| (4, 3) | "4,5" | 4th row, 5th column |

#### In Practice

```python
# ✓ CORRECT - Converting UI placement to JSON format
for (x, y), material in ui_grid.items():
    json_placement[f"{y+1},{x+1}"] = material  # row,col = Y,X

# ✗ WRONG - This creates col,row (X,Y) which doesn't match JSON
for (x, y), material in ui_grid.items():
    json_placement[f"{x+1},{y+1}"] = material  # SWAPPED!
```

---

## Reference Quick Links

- **Method Names:** See "Method Naming Patterns" section above
- **Data Structures:** See "Data Structure Naming" section
- **Tag System:** See `docs/tag-system/TAG-GUIDE.md`
- **Architecture:** See `docs/ARCHITECTURE.md`
- **Issues:** See `MASTER_ISSUE_TRACKER.md`

---

**Last Updated:** January 27, 2026
**Maintained By:** Development Team
**Status:** Living Document - Update as patterns evolve
