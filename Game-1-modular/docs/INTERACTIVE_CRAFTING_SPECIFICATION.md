# INTERACTIVE CRAFTING UI - COMPLETE IMPLEMENTATION SPECIFICATION

**Version:** 1.0
**Date:** 2026-01-07
**Purpose:** Complete, unambiguous specification for implementing interactive crafting UI
**Status:** Ready for Implementation

---

## TABLE OF CONTENTS

1. [Overall System Requirements](#1-overall-system-requirements)
2. [Smithing Specification](#2-smithing-specification)
3. [Refining Specification](#3-refining-specification)
4. [Alchemy Specification](#4-alchemy-specification)
5. [Engineering Specification](#5-engineering-specification)
6. [Adornments Specification](#6-adornments-specification)
7. [UI Layout Standards](#7-ui-layout-standards)
8. [Recipe Matching Logic](#8-recipe-matching-logic)
9. [Material Management](#9-material-management)
10. [Visual Assets](#10-visual-assets)

---

## 1. OVERALL SYSTEM REQUIREMENTS

### 1.1 Debug Mode Material Display

**Requirement:**
When `Config.DEBUG_INFINITE_RESOURCES == True`, material palette must show 99 of every material regardless of actual inventory quantity.

**Implementation:**
```python
def get_available_materials(self):
    mat_db = MaterialDatabase.get_instance()
    available = []

    if Config.DEBUG_INFINITE_RESOURCES:
        # Debug mode: Show 99 of EVERY material at or below station tier
        for mat_id, mat_def in mat_db.materials.items():
            if mat_def.tier <= self.station_tier:
                # Create ItemStack with quantity=99
                available.append(ItemStack(
                    item_id=mat_id,
                    quantity=99,
                    crafted_stats=None,
                    rarity='common'
                ))
    else:
        # Normal mode: Show actual inventory
        for slot in self.inventory.slots:
            if slot and slot.quantity > 0:
                mat_def = mat_db.get_material(slot.item_id)
                if mat_def and mat_def.tier <= self.station_tier:
                    available.append(slot)

    # Sort by tier → category → name
    available.sort(key=self._sort_key_function)
    return available
```

**Behavior:**
- Debug mode does NOT bypass material borrowing/return logic
- Materials are still removed from inventory when placed (even in debug)
- Only affects DISPLAY quantity in palette
- Prevents "out of materials" errors during testing

---

### 1.2 Material Icon Display

**Requirement:**
All materials MUST display PNG icons in both palette and placement areas.

**Icon Path Pattern:**
```
assets/generated_icons-2/items/materials/{material_id}-2.png
```

**Examples:**
- `iron_ingot` → `materials/iron_ingot-2.png`
- `fire_crystal` → `materials/fire_crystal-2.png`
- `oak_plank` → `materials/oak_plank-2.png`

**Implementation (Material Palette):**
```python
# Get icon from ImageCache
from rendering.image_cache import ImageCache
image_cache = ImageCache.get_instance()

icon_path = f"materials/{mat_stack.item_id}-2.png"
icon_size = s(35)  # Adjust based on cell size
icon = image_cache.get_image(icon_path, (icon_size, icon_size))

if icon:
    # Render icon centered in item rect
    icon_x = item_rect.centerx - icon_size // 2
    icon_y = item_rect.y + s(5)
    surf.blit(icon, (icon_x, icon_y))
else:
    # Fallback to text abbreviation if icon missing
    abbrev = mat_def.name[:3].upper()
    text = self.tiny_font.render(abbrev, True, (220, 220, 220))
    surf.blit(text, (item_rect.centerx - text.get_width()//2, item_rect.centery))
```

**Implementation (Placement Areas):**
```python
# In grid cells, slots, or vertices
if placed_material:
    icon_path = f"materials/{placed_material.item_id}-2.png"
    icon_size = min(cell_size - s(8), s(40))  # Leave padding
    icon = image_cache.get_image(icon_path, (icon_size, icon_size))

    if icon:
        icon_x = cell_rect.centerx - icon_size // 2
        icon_y = cell_rect.centery - icon_size // 2
        surf.blit(icon, (icon_x, icon_y))
```

**Fallback Behavior:**
- If PNG not found, display first 3-4 letters of material name
- Do NOT crash or throw errors on missing icons
- Icons are loaded via ImageCache singleton (handles caching and missing files)

---

### 1.3 UI Window Sizing

**Requirement:**
Interactive UI uses larger window than regular crafting UI.

**Window Dimensions:**
```python
ww, wh = Config.MENU_XLARGE_W, Config.MENU_LARGE_H
# MENU_XLARGE_W = scale(1200)
# MENU_LARGE_H = scale(700)
```

**Panel Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  INTERACTIVE {DISCIPLINE} (T{tier})         [ESC] Close     │
├──────────────┬──────────────────────────────────────────────┤
│              │                                               │
│  MATERIALS   │        PLACEMENT AREA                        │
│  (scrollable)│        (discipline-specific)                 │
│              │                                               │
│  300px wide  │        Remaining width                       │
│              │                                               │
│              │                                               │
├──────────────┴──────────────────────────────────────────────┤
│  Recipe Status: [✓ MATCHED / No recipe matched]            │
│  [CLEAR]  [INSTANT CRAFT (0 XP)]  [MINIGAME (1.5x XP)]     │
└─────────────────────────────────────────────────────────────┘
```

**Dimensions:**
- Left panel (palette): 300px width
- Right panel (placement): Remaining width (~900px)
- Bottom panel (status/buttons): 120px height
- Padding: 20px around all panels

---

## 2. SMITHING SPECIFICATION

### 2.1 Grid Sizes by Tier

**SOURCE:** GAME_MECHANICS_V6.md lines 3851-3854

**EXACT SPECIFICATIONS:**

| Tier | Grid Size | Description |
|------|-----------|-------------|
| T1   | **3x3**   | Basic weapons, simple recipes |
| T2   | **5x5**   | Intermediate weapons, longswords, battleaxes |
| T3   | **7x7**   | Advanced weapons, greatswords, warhammers |
| T4   | **9x9**   | Master weapons, halberds, exotic items |

**Implementation:**
```python
class InteractiveSmithingUI(InteractiveBaseUI):
    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)

        # EXACT GRID SIZES - DO NOT MODIFY
        grid_sizes = {1: 3, 2: 5, 3: 7, 4: 9}
        self.grid_size = grid_sizes.get(station_tier, 3)

        # Grid storage: {(x, y): PlacedMaterial}
        self.grid: Dict[Tuple[int, int], PlacedMaterial] = {}
```

**Backward Compatibility:**
- Higher tier stations CAN craft lower tier recipes
- 3x3 recipe can be placed anywhere in 9x9 grid
- Recipe matching checks EXACT pattern, ignoring empty cells

---

### 2.2 Grid Rendering Specifications

**Cell Sizing:**
```python
# Calculate cell size based on grid and available space
placement_w = ww - palette_w - s(60)  # Available width
placement_h = wh - s(200)  # Available height

# Cell size fits largest grid (9x9 at T4)
max_cell_size = s(60)
cell_size = min(max_cell_size, (placement_w - s(40)) // self.grid_size)

# Grid centering
grid_offset_x = placement_x + (placement_w - self.grid_size * cell_size) // 2
grid_offset_y = placement_y + s(40)
```

**Cell States:**
1. **Empty Cell:**
   - Background: `(40, 45, 50)`
   - Border: `(80, 90, 100)` width 2px
   - Border radius: 3px

2. **Hovered Empty Cell:**
   - Background: `(70, 80, 90)`
   - Border: `(120, 140, 160)` width 2px

3. **Filled Cell (Material Placed):**
   - Background: Tier-based color
     - T1: `(60, 60, 70)`
     - T2: `(60, 80, 60)`
     - T3: `(60, 70, 90)`
     - T4: `(90, 60, 90)`
   - Border: Tier color (brighter) width 2px
   - Material icon: Centered, size = cell_size - 8px

4. **Hovered Filled Cell:**
   - Border color: `(255, 215, 0)` (gold)
   - Border width: 3px

**Grid Coordinate System:**
```
Origin at top-left (0, 0)
X increases right →
Y increases down ↓

3x3 grid:      5x5 grid:         9x9 grid:
0 1 2          0 1 2 3 4         0 1 2 3 4 5 6 7 8
0 1 2          0 1 2 3 4         0 1 2 3 4 5 6 7 8
0 1 2          0 1 2 3 4         ...
               0 1 2 3 4
               0 1 2 3 4
```

---

### 2.3 Recipe Matching Logic

**Placement Data Format (from placements-smithing-1.JSON):**
```json
{
  "placementMap": {
    "0,0": "iron_ingot",
    "1,0": "iron_ingot",
    "1,1": "oak_plank"
  }
}
```

**Matching Algorithm:**
```python
def check_recipe_match(self) -> Optional[Recipe]:
    if not self.grid:
        return None

    placement_db = PlacementDatabase.get_instance()
    recipe_db = RecipeDatabase.get_instance()

    # Convert current grid to string-key format
    current_placement = {
        f"{x},{y}": mat.item_id
        for (x, y), mat in self.grid.items()
    }

    # Get all smithing recipes for this tier and below
    recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

    for recipe in recipes:
        placement = placement_db.get_placement(recipe.recipe_id)
        if not placement or placement.discipline != 'smithing':
            continue

        # EXACT MATCH required (key sets and values must match)
        if current_placement == placement.placement_map:
            return recipe

    return None
```

**Important:**
- Position matters (1,0 ≠ 0,1)
- Material IDs must match exactly
- Empty cells not included in placement map
- NO partial matching or hints

---

## 3. REFINING SPECIFICATION

### 3.1 Slot Configuration by Tier

**SOURCE:** GAME_MECHANICS_V6.md lines 3917-3920

**EXACT SPECIFICATIONS:**

| Tier | Core Slots | Surrounding Slots | Total Slots |
|------|-----------|-------------------|-------------|
| T1   | **1**     | **2**             | 3           |
| T2   | **1**     | **4**             | 5           |
| T3   | **2**     | **5**             | 7           |
| T4   | **3**     | **6**             | 9           |

**Implementation:**
```python
class InteractiveRefiningUI(InteractiveBaseUI):
    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)

        # EXACT SLOT COUNTS - DO NOT MODIFY
        slot_config = {
            1: {'core': 1, 'surrounding': 2},
            2: {'core': 1, 'surrounding': 4},
            3: {'core': 2, 'surrounding': 5},
            4: {'core': 3, 'surrounding': 6}
        }
        config = slot_config.get(station_tier, {'core': 1, 'surrounding': 2})

        # Core slots (LIST for multi-core at T3+)
        self.core_slots: List[Optional[PlacedMaterial]] = [None] * config['core']

        # Surrounding slots
        self.surrounding_slots: List[Optional[PlacedMaterial]] = [None] * config['surrounding']
```

---

### 3.2 Visual Layout by Tier

**T1 (1 core + 2 surrounding):**
```
    [Surr_0]
       |
    [CORE]
       |
    [Surr_1]
```

**T2 (1 core + 4 surrounding):**
```
    [Surr_0]
       |
[Surr_3]-[CORE]-[Surr_1]
       |
    [Surr_2]
```

**T3 (2 cores + 5 surrounding):**
```
      [Surr_0]
         |
[CORE_0]-+-[CORE_1]
    |    |    |
[Surr_3]-+-[Surr_1]
    |    |
 [Surr_4]-[Surr_2]
```

**T4 (3 cores + 6 surrounding):**
```
Triangle arrangement:
       [CORE_0]
      /   |   \
  [S_0] [S_1] [S_2]
    |     |     |
[CORE_1]-+-[CORE_2]
    |     |     |
  [S_3] [S_4] [S_5]
```

**Core Slot Rendering:**
- Size: 80x80px at T1/T2, 70x70px at T3/T4 (smaller to fit multiple)
- Color (empty): `(50, 60, 70)`
- Color (filled): `(80, 100, 80)`
- Border: `(140, 160, 180)` width 3px
- Label: "CORE" or "CORE 1", "CORE 2", etc.

**Surrounding Slot Rendering:**
- Size: 60x60px
- Color (empty): `(45, 55, 65)`
- Color (filled): `(70, 90, 70)`
- Border: `(120, 140, 160)` width 2px
- Label: Slot number (0, 1, 2...)

**Positioning:**
- Use circular/geometric arrangement
- Core slots always central
- Surrounding slots distributed evenly around cores
- Spacing: 130px radius from core center for T1/T2

---

### 3.3 Recipe Matching Logic

**Placement Data Format (from placements-refining-1.JSON):**
```json
{
  "coreInputs": [
    {"materialId": "iron_ore", "quantity": 1}
  ],
  "surroundingInputs": [
    {"materialId": "coal", "quantity": 1}
  ]
}
```

**Matching Algorithm:**
```python
def check_recipe_match(self) -> Optional[Recipe]:
    # Must have at least one core filled
    if not any(self.core_slots):
        return None

    placement_db = PlacementDatabase.get_instance()
    recipe_db = RecipeDatabase.get_instance()
    recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

    for recipe in recipes:
        placement = placement_db.get_placement(recipe.recipe_id)
        if not placement or placement.discipline != 'refining':
            continue

        # Match core materials (order doesn't matter for refining)
        placed_cores = [c.item_id for c in self.core_slots if c is not None]
        required_cores = [inp['materialId'] for inp in placement.core_inputs]

        if sorted(placed_cores) != sorted(required_cores):
            continue

        # Match surrounding materials (order doesn't matter)
        placed_surrounding = [s.item_id for s in self.surrounding_slots if s is not None]
        required_surrounding = [inp['materialId'] for inp in placement.surrounding_inputs]

        if sorted(placed_surrounding) == sorted(required_surrounding):
            return recipe

    return None
```

**Important:**
- Order does NOT matter for refining (unlike alchemy)
- Empty slots (None) are filtered out before comparison
- Both core and surrounding must match

---

## 4. ALCHEMY SPECIFICATION

### 4.1 Slot Count by Tier

**SOURCE:** Analysis of placements-alchemy-1.JSON

**VERIFIED SPECIFICATIONS:**

| Tier | Min Slots | Max Slots | Description |
|------|-----------|-----------|-------------|
| T1   | 2         | **2**     | Basic potions (2 ingredients) |
| T2   | 2         | **3**     | Intermediate potions (2-3 ingredients) |
| T3   | 3         | **4**     | Advanced potions (3-4 ingredients) |
| T4   | 4         | **6**     | Master potions (4-6 ingredients) |

**Implementation:**
```python
class InteractiveAlchemyUI(InteractiveBaseUI):
    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)

        # EXACT MAX SLOTS - DO NOT MODIFY
        max_slots = {1: 2, 2: 3, 3: 4, 4: 6}
        num_slots = max_slots.get(station_tier, 2)

        # Sequential slots (order matters!)
        self.slots: List[Optional[PlacedMaterial]] = [None] * num_slots
```

**Key Rule:**
- Display ALL slots even if recipe only uses subset
- Example: T4 shows 6 slots, but recipe might only use slots 1-4
- Empty slots at end are ignored in recipe matching

---

### 4.2 Visual Layout

**Horizontal Sequential Layout:**
```
Slot 1    Slot 2    Slot 3    Slot 4    Slot 5    Slot 6
[  1  ] → [  2  ] → [  3  ] → [  4  ] → [  5  ] → [  6  ]
 Base     Reagent  Catalyst  Modifier  Enhance  Stabilize
```

**Slot Rendering:**
- Width: 100px
- Height: 80px
- Spacing: 15px between slots
- Arrow indicators between slots (→)

**Slot States:**
1. **Empty:**
   - Background: `(40, 50, 60)`
   - Border: `(90, 110, 130)` width 2px

2. **Filled:**
   - Background: `(70, 80, 90)`
   - Border: `(120, 140, 160)` width 2px
   - Material icon centered

3. **Hovered:**
   - Border color: `(160, 180, 200)`
   - Border width: 3px

**Labels:**
- Top of each slot: "Slot 1", "Slot 2", etc.
- Font: tiny_font, color: (180, 180, 180)

---

### 4.3 Recipe Matching Logic

**Placement Data Format (from placements-alchemy-1.JSON):**
```json
{
  "ingredients": [
    {"slot": 1, "materialId": "slime_gel", "quantity": 2},
    {"slot": 2, "materialId": "wolf_pelt", "quantity": 1}
  ]
}
```

**CRITICAL:** Slot numbers in JSON start at 1, arrays start at 0!

**Matching Algorithm:**
```python
def check_recipe_match(self) -> Optional[Recipe]:
    placement_db = PlacementDatabase.get_instance()
    recipe_db = RecipeDatabase.get_instance()
    recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

    for recipe in recipes:
        placement = placement_db.get_placement(recipe.recipe_id)
        if not placement or placement.discipline != 'alchemy':
            continue

        # Build required sequence (slot numbers are 1-indexed in JSON!)
        required = [None] * len(self.slots)
        for ingredient in placement.ingredients:
            slot_idx = ingredient['slot'] - 1  # Convert to 0-indexed
            if 0 <= slot_idx < len(required):
                required[slot_idx] = ingredient['materialId']

        # Build current sequence
        current = [s.item_id if s else None for s in self.slots]

        # Match: ALL required slots must match, extra slots must be empty
        match = True
        for i, required_mat in enumerate(required):
            if required_mat:  # Required material at this position
                if current[i] != required_mat:
                    match = False
                    break
            # If required[i] is None, current[i] can be anything (recipe doesn't use this slot)

        if match:
            return recipe

    return None
```

**Important:**
- Order MATTERS (slot 1 → slot 2 → slot 3)
- Empty slots at end are allowed
- Cannot skip slots (if recipe uses slots 1,2,4, slot 3 must be empty)

---

## 5. ENGINEERING SPECIFICATION

### 5.1 Slot Type System

**SOURCE:** placements-engineering-1.JSON metadata and verification

**EXACT SLOT TYPES:**
```python
SLOT_TYPES = ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'UTILITY']
```

**Do NOT use:** 'core', 'spring', 'gear', 'wiring', 'enhancement' (these are wrong)

---

### 5.2 Canvas Slot Limits by Tier

**SOURCE:** placements-engineering-1.JSON metadata

**EXACT SPECIFICATIONS:**

| Tier | Max Canvas Slots | Available Slot Types | Description |
|------|------------------|----------------------|-------------|
| T1   | **3**            | 3 types              | Basic devices |
| T2   | **5**            | 5 types              | Intermediate devices |
| T3   | **5**            | 5 types              | Advanced devices (all types) |
| T4   | **7**            | 5 types              | Master devices |

**Implementation:**
```python
class InteractiveEngineeringUI(InteractiveBaseUI):
    SLOT_TYPES = ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'UTILITY']

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)

        # EXACT CANVAS LIMITS - DO NOT MODIFY
        canvas_limits = {1: 3, 2: 5, 3: 5, 4: 7}
        self.max_slots = canvas_limits.get(station_tier, 3)

        # Canvas: List of placed slots (each has type + material)
        # Format: [{'type': 'FRAME', 'material': PlacedMaterial}, ...]
        self.canvas: List[Dict] = []
```

**Slot Type Availability:**
- T1: FRAME, FUNCTION, POWER (3 types)
- T2+: All 5 types available

---

### 5.3 Visual Layout - Canvas System

**Canvas Layout:**
```
┌─────────────────────────────────────────────┐
│  ENGINEERING CANVAS (3/5 slots used)        │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │ FRAME   │  │FUNCTION │  │ POWER   │    │
│  │ [icon]  │  │ [icon]  │  │ [icon]  │    │
│  │ Iron    │  │Oak Plank│  │Fire Crys│    │
│  └─────────┘  └─────────┘  └─────────┘    │
│                                             │
│  ┌─────────────────┐                       │
│  │ [+] Add Slot    │ ← Opens slot type menu│
│  └─────────────────┘                       │
│                                             │
└─────────────────────────────────────────────┘

SLOT TYPE MENU (shown when clicking +Add):
┌─────────────┐
│ FRAME       │
│ FUNCTION    │
│ POWER       │
│ MODIFIER    │
│ UTILITY     │
└─────────────┘
```

**Slot Rendering:**
- Width: 120px
- Height: 100px
- Spacing: 10px between slots
- Horizontal arrangement (wrap if needed)

**Slot States:**
1. **Empty Canvas Position:**
   - "[+] Add Slot" button shown
   - Color: `(50, 70, 90)`
   - Clickable to add new slot

2. **Filled Slot:**
   - Background: `(70, 90, 70)`
   - Border: `(120, 160, 120)` width 2px
   - Type label at top: "FRAME", "FUNCTION", etc.
   - Material icon in center
   - Material name below icon (truncated)

3. **Hovered Slot:**
   - Border: `(255, 215, 0)` gold
   - Border width: 3px
   - Right-click to remove

**Add Slot Flow:**
1. Click "[+] Add Slot" button
2. Dropdown/menu shows available slot types
3. Select slot type
4. Material palette highlights → click material
5. New slot added to canvas

---

### 5.4 Recipe Matching Logic

**Placement Data Format (from placements-engineering-1.JSON):**
```json
{
  "slots": [
    {"type": "FRAME", "materialId": "iron_ingot", "quantity": 4},
    {"type": "FUNCTION", "materialId": "oak_plank", "quantity": 3},
    {"type": "POWER", "materialId": "beetle_carapace", "quantity": 2}
  ]
}
```

**Matching Algorithm:**
```python
def check_recipe_match(self) -> Optional[Recipe]:
    if not self.canvas:
        return None

    placement_db = PlacementDatabase.get_instance()
    recipe_db = RecipeDatabase.get_instance()
    recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

    # Build current slot configuration
    # Group by type: {type: [material_ids]}
    current_by_type = {}
    for slot in self.canvas:
        slot_type = slot['type']
        mat_id = slot['material'].item_id
        if slot_type not in current_by_type:
            current_by_type[slot_type] = []
        current_by_type[slot_type].append(mat_id)

    # Sort each type's materials for comparison
    for slot_type in current_by_type:
        current_by_type[slot_type].sort()

    for recipe in recipes:
        placement = placement_db.get_placement(recipe.recipe_id)
        if not placement or placement.discipline != 'engineering':
            continue

        # Build required slot configuration
        required_by_type = {}
        for slot_entry in placement.slots:
            slot_type = slot_entry['type']
            mat_id = slot_entry['materialId']
            if slot_type not in required_by_type:
                required_by_type[slot_type] = []
            required_by_type[slot_type].append(mat_id)

        # Sort required materials
        for slot_type in required_by_type:
            required_by_type[slot_type].sort()

        # Compare
        if current_by_type == required_by_type:
            return recipe

    return None
```

**Important:**
- Slot TYPE matters (FRAME vs FUNCTION)
- Order within type does NOT matter
- All slots must match exactly (no partial matches)

---

## 6. ADORNMENTS SPECIFICATION

### 6.1 Vertex-Based System Overview

**CRITICAL:** Adornments use a completely different system than smithing!

**Key Differences:**
- **Smithing:** Cell-based grid (discrete cells)
- **Adornments:** Vertex-based coordinate system (points on graph)

**Coordinate System:**
```
Cartesian coordinate plane:
       Y
       ↑
   -6,-6 to 6,6 (typical)
       │
─────0,0──────→ X
       │
       ↓
```

**Example Coordinates:**
```
(0, 0)    = Origin/center
(3, 3)    = Upper-right
(-3, -3)  = Lower-left
(0, 6)    = Top center
```

---

### 6.2 Grid Types and Sizes

**SOURCE:** placements-adornments-1.JSON verification

**Observed Grid Types:**
- `square_8x8` (coordinates -4 to 4)
- `square_10x10` (coordinates -5 to 5)
- `square_12x12` (coordinates -6 to 6)
- `square_14x14` (coordinates -7 to 7)

**Implementation:**
```python
class InteractiveAdornmentsUI(InteractiveBaseUI):
    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)

        # Default grid based on tier (can be overridden by recipe)
        grid_ranges = {
            1: 8,   # -4 to 4
            2: 10,  # -5 to 5
            3: 12,  # -6 to 6
            4: 14   # -7 to 7
        }
        half_size = grid_ranges.get(station_tier, 8) // 2
        self.grid_min = -half_size
        self.grid_max = half_size

        # Vertices: {(x, y): PlacedMaterial}
        self.vertices: Dict[Tuple[int, int], PlacedMaterial] = {}

        # Shape system
        self.shape_templates = self.define_shape_templates()
        self.selected_shape = None
        self.shape_rotation = 0  # Degrees: 0, 45, 90, 135, 180, 225, 270, 315
```

---

### 6.3 Shape Templates

**SOURCE:** tools/enchanting-pattern-designer.py lines 58-102

**Shape Definitions:**
```python
def define_shape_templates(self):
    return {
        # T1: Basic small shapes
        "triangle_equilateral_small": [
            (0, 0),    # Anchor: top vertex
            (-1, -2),  # Bottom left
            (1, -2)    # Bottom right
        ],
        "square_small": [
            (0, 0),    # Top-left
            (2, 0),    # Top-right
            (2, -2),   # Bottom-right
            (0, -2)    # Bottom-left
        ],

        # T2: Add isosceles
        "triangle_isosceles_small": [
            (0, 0),    # Top vertex
            (-1, -3),  # Bottom left
            (1, -3)    # Bottom right
        ],

        # T3: Large shapes
        "triangle_equilateral_large": [
            (0, 0),
            (-2, -3),
            (2, -3)
        ],
        "square_large": [
            (0, 0),
            (4, 0),
            (4, -4),
            (0, -4)
        ],

        # T4: Large isosceles
        "triangle_isosceles_large": [
            (0, 0),
            (-1, -5),
            (1, -5)
        ]
    }

def get_available_shapes_for_tier(self, tier):
    shapes = []
    if tier >= 1:
        shapes.extend(["triangle_equilateral_small", "square_small"])
    if tier >= 2:
        shapes.append("triangle_isosceles_small")
    if tier >= 3:
        shapes.extend(["triangle_equilateral_large", "square_large"])
    if tier >= 4:
        shapes.append("triangle_isosceles_large")
    return shapes
```

**Shape Rotation:**
- Angles: 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°
- Shift key cycles through rotations
- Rotation formula:
```python
def rotate_point(x, y, degrees):
    rad = math.radians(degrees)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    new_x = round(x * cos_a - y * sin_a)
    new_y = round(x * sin_a + y * cos_a)
    return (new_x, new_y)
```

---

### 6.4 Visual Layout

**UI Structure:**
```
┌────────────────────────────────────────────────────────────┐
│  Shape Selector (Left)  │  Coordinate Grid (Right)        │
├─────────────────────────┼─────────────────────────────────┤
│                         │         ↑ Y                      │
│ Available Shapes:       │         │                        │
│  ○ Triangle Small       │    ·····│·····                  │
│  ○ Square Small         │    ·····│·····                  │
│  ○ Triangle Iso Small   │  ──────0,0────── X→             │
│  ○ Triangle Large       │    ·····│·····                  │
│  ○ Square Large         │    ·····│·····                  │
│                         │         ↓                        │
│ Rotation: [0°]          │                                  │
│  [Shift] to rotate      │  • = Grid point                 │
│                         │  ● = Placed vertex               │
│ Selected Material:      │  Ghost = Shape preview          │
│  [Iron Ingot icon]      │                                  │
│                         │                                  │
└─────────────────────────┴─────────────────────────────────┘
```

**Grid Rendering:**
- Show grid lines every 1 unit
- Major grid lines every 5 units (thicker)
- Grid dots at each integer coordinate
- Coordinate labels at edges

**Vertex Rendering:**
- **Empty vertex (grid point):** Small dot, color `(100, 100, 100)`
- **Placed vertex:** Larger dot with material icon overlay
  - Dot size: 8px radius
  - Icon size: 30x30px centered on dot
  - Border: Tier color, 2px width

**Ghost Shape Preview:**
- When shape selected + mouse over grid
- Show transparent outline of shape at mouse position
- Color: `(150, 200, 150, 100)` (semi-transparent green)
- Updates on mouse move
- Snaps to nearest grid point

**Placement Flow:**
1. Select shape from left panel
2. Shape ghost follows mouse on grid
3. Shift key rotates shape (ghost updates)
4. Click to place shape vertices
5. Each vertex gets selected material
6. Shape selection remains active for multi-place

---

### 6.5 Recipe Matching Logic

**Placement Data Format (from placements-adornments-1.JSON):**
```json
{
  "placementMap": {
    "gridType": "square_12x12",
    "vertices": {
      "0,0": {"materialId": "golem_core", "isKey": false},
      "3,3": {"materialId": "spectral_thread", "isKey": false},
      "-3,-3": {"materialId": "spectral_thread", "isKey": false}
    }
  }
}
```

**Matching Algorithm:**
```python
def check_recipe_match(self) -> Optional[Recipe]:
    if not self.vertices:
        return None

    placement_db = PlacementDatabase.get_instance()
    recipe_db = RecipeDatabase.get_instance()
    recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

    # Convert current vertices to string-key format
    current_vertices = {
        f"{x},{y}": mat.item_id
        for (x, y), mat in self.vertices.items()
    }

    for recipe in recipes:
        placement = placement_db.get_placement(recipe.recipe_id)
        if not placement or placement.discipline != 'adornments':
            continue

        # Get required vertices from placement
        required_vertices = {}
        for coord_str, vertex_data in placement.placement_map.get('vertices', {}).items():
            required_vertices[coord_str] = vertex_data['materialId']

        # EXACT MATCH required
        if current_vertices == required_vertices:
            return recipe

    return None
```

**Important:**
- Coordinates are stored as strings "x,y"
- Negative coordinates are valid: "-3,3"
- `isKey` field is metadata (not used in matching)
- Position AND material must match exactly

---

## 7. UI LAYOUT STANDARDS

### 7.1 Material Palette Panel

**Position:** Left side of window
**Dimensions:** 300px width, full height minus header
**Background:** `(30, 30, 40)`
**Border:** `(100, 100, 120)` 2px

**Header:**
```
"MATERIALS (Click to Select)"
Font: small_font
Color: (200, 200, 200)
Position: 10px from top
```

**Item List:**
- **Scrollable:** Mouse wheel scrolls
- **Item height:** 45px per material
- **Visible count:** Calculate based on available height
- **Padding:** 10px left/right, 5px top/bottom

**Item Rendering:**
```python
# Per material item
item_rect = pygame.Rect(palette_x + 10, mat_y, palette_w - 20, 40)

# Background (selection state)
if is_selected:
    bg_color = (80, 100, 80)
    border_color = (255, 215, 0)  # Gold
elif is_hovered:
    bg_color = (60, 70, 80)
    border_color = (120, 140, 160)
else:
    bg_color = (40, 45, 55)
    border_color = tier_color

# Icon
icon_path = f"materials/{mat_stack.item_id}-2.png"
icon = image_cache.get_image(icon_path, (32, 32))
if icon:
    surf.blit(icon, (item_rect.x + 5, item_rect.centery - 16))

# Text
name_text = tiny_font.render(mat_def.name, True, (220, 220, 220))
surf.blit(name_text, (item_rect.x + 42, item_rect.y + 5))

qty_text = tiny_font.render(f"x{mat_stack.quantity} (T{mat_def.tier})", True, (180, 180, 180))
surf.blit(qty_text, (item_rect.x + 42, item_rect.y + 22))
```

**Tier Colors (for borders):**
```python
tier_colors = {
    1: (150, 150, 150),  # Gray
    2: (100, 200, 100),  # Green
    3: (100, 150, 255),  # Blue
    4: (200, 100, 255)   # Purple
}
```

**Scroll Indicators:**
- Show "▲ Scroll Up" at top if scrolled down
- Show "▼ Scroll Down" at bottom if more items below
- Font: tiny_font, color: (150, 200, 150)

---

### 7.2 Bottom Action Panel

**Position:** Bottom of window
**Height:** 120px
**Background:** `(25, 25, 35)`
**Top border:** `(80, 80, 90)` 2px

**Recipe Status Display:**
```python
status_y = bottom_panel_y + 20

if matched_recipe:
    # Get output name
    output_name = get_output_name(matched_recipe.output_id)
    status_text = f"✓ RECIPE MATCHED: {output_name} (x{matched_recipe.output_qty})"
    status_color = (100, 255, 100)
else:
    status_text = "No recipe matched"
    status_color = (200, 200, 200)

status_surf = font.render(status_text, True, status_color)
surf.blit(status_surf, (placement_x, status_y))
```

**Button Layout:**
```python
button_y = status_y + 35
button_w = 150
button_h = 40
button_spacing = 20

# CLEAR button (always enabled)
clear_rect = pygame.Rect(placement_x, button_y, button_w, button_h)
clear_color = (100, 60, 60) if is_hovered else (80, 50, 50)
clear_border = (180, 100, 100)
clear_text = "CLEAR"

# INSTANT CRAFT button (enabled if recipe matched)
instant_x = clear_rect.right + button_spacing
instant_rect = pygame.Rect(instant_x, button_y, button_w, button_h)
if recipe_matched:
    instant_color = (60, 100, 60) if is_hovered else (50, 80, 50)
    instant_border = (120, 180, 120)
    instant_text_color = (220, 255, 220)
else:
    instant_color = (40, 40, 40)
    instant_border = (80, 80, 80)
    instant_text_color = (120, 120, 120)

# Render button with text and subtext
main_text = small_font.render("INSTANT CRAFT", True, instant_text_color)
sub_text = tiny_font.render("0 XP", True, instant_text_color)

# MINIGAME button (enabled if recipe matched)
minigame_x = instant_rect.right + button_spacing
minigame_rect = pygame.Rect(minigame_x, button_y, button_w, button_h)
# Colors same as instant craft
main_text = small_font.render("MINIGAME", True, text_color)
sub_text = tiny_font.render("1.5x XP", True, (255, 200, 100) if enabled else text_color)
```

---

### 7.3 Color Palette Reference

**Background Colors:**
- Main window: `(20, 20, 30, 240)`
- Material palette: `(30, 30, 40)`
- Placement area: `(25, 30, 35)`
- Bottom panel: `(25, 25, 35)`

**Tier Colors:**
- T1: `(150, 150, 150)` Gray
- T2: `(100, 200, 100)` Green
- T3: `(100, 150, 255)` Blue
- T4: `(200, 100, 255)` Purple

**Interactive States:**
- Hover: Increase border brightness by 40 points
- Selected: Gold border `(255, 215, 0)`
- Disabled: Gray `(80, 80, 80)` with dark text `(120, 120, 120)`

**Status Colors:**
- Success/Matched: `(100, 255, 100)`
- Error/Failed: `(255, 100, 100)`
- Neutral: `(200, 200, 200)`
- Warning: `(255, 200, 100)`

---

## 8. RECIPE MATCHING LOGIC

### 8.1 General Matching Flow

**For ALL disciplines:**
```python
def check_recipe_match(self) -> Optional[Recipe]:
    # 1. Early exit if no materials placed
    if not self.has_any_materials_placed():
        return None

    # 2. Get databases
    placement_db = PlacementDatabase.get_instance()
    recipe_db = RecipeDatabase.get_instance()

    # 3. Get recipes for this station and tier (backward compatible)
    recipes = recipe_db.get_recipes_for_station(
        self.station_type,
        self.station_tier
    )

    # 4. Convert current placement to comparable format
    current_placement = self.get_current_placement_format()

    # 5. Iterate through all recipes
    for recipe in recipes:
        placement = placement_db.get_placement(recipe.recipe_id)

        # Skip if wrong discipline
        if not placement or placement.discipline != self.station_type:
            continue

        # Compare placement
        if self.placements_match(current_placement, placement):
            return recipe

    # 6. No match found
    return None
```

**Backward Compatibility:**
- T4 station can craft T1, T2, T3, T4 recipes
- Recipe tier ≤ station tier

---

### 8.2 Exact Matching Rules

**Smithing:**
- Key-value exact match: `current_map == placement_map`
- Position matters: `(0,1) ≠ (1,0)`
- Material IDs must match exactly

**Refining:**
- Sorted comparison: `sorted(current) == sorted(required)`
- Order does NOT matter
- Core and surrounding checked separately

**Alchemy:**
- Sequential exact match with slot offset
- Order DOES matter
- JSON uses 1-indexed slots, code uses 0-indexed arrays

**Engineering:**
- Group by type, then sorted comparison
- Slot type matters
- Order within type does NOT matter

**Adornments:**
- Vertex coordinate exact match
- Position matters (Cartesian coordinates)
- String key format: "x,y"

---

## 9. MATERIAL MANAGEMENT

### 9.1 Borrowing System

**Concept:**
Materials are temporarily removed from inventory when placed. They're returned on cancel/close.

**Implementation:**
```python
class InteractiveBaseUI:
    def __init__(self, ...):
        self.borrowed_materials: Dict[str, int] = {}  # {item_id: quantity}

    def borrow_material(self, item_id: str, quantity: int = 1) -> bool:
        removed = self.inventory.remove_item(item_id, quantity)
        if removed > 0:
            self.borrowed_materials[item_id] = \
                self.borrowed_materials.get(item_id, 0) + removed
            return True
        return False

    def return_material(self, item_id: str, quantity: int = 1):
        if item_id in self.borrowed_materials and \
           self.borrowed_materials[item_id] >= quantity:
            self.inventory.add_item(item_id, quantity)
            self.borrowed_materials[item_id] -= quantity
            if self.borrowed_materials[item_id] == 0:
                del self.borrowed_materials[item_id]

    def return_all_materials(self):
        for item_id, quantity in list(self.borrowed_materials.items()):
            self.inventory.add_item(item_id, quantity)
        self.borrowed_materials.clear()
```

---

### 9.2 Placement Operations

**Place Material:**
1. Check if position is valid for discipline
2. If position already occupied, return old material first
3. Borrow new material from inventory
4. Create PlacedMaterial object
5. Store in data structure
6. Check recipe match
7. Update UI

**Remove Material:**
1. Get material from position
2. Return material to inventory
3. Remove from data structure
4. Check recipe match
5. Update UI

**Clear All:**
1. Iterate through all placements
2. Return each material to inventory
3. Clear data structure
4. Reset matched_recipe to None
5. Update UI

---

### 9.3 Craft Operation Flow

**Instant Craft:**
```python
def _handle_interactive_craft(self, use_minigame=False):
    recipe = self.interactive_ui.matched_recipe

    if not use_minigame:
        # Instant craft
        self._instant_craft(recipe)

        # Materials already consumed by _instant_craft via recipe_db
        # Clear borrowed materials to avoid double-return
        self.interactive_ui.borrowed_materials.clear()

        # Close UI
        self._close_interactive_crafting()
```

**Minigame:**
```python
def _handle_interactive_craft(self, use_minigame=True):
    recipe = self.interactive_ui.matched_recipe

    # Start minigame
    self._start_minigame(recipe)

    # Materials stay borrowed during minigame
    # They'll be consumed when minigame completes

    # Close interactive UI
    self._close_interactive_crafting()
```

**Important:**
- Materials are already removed from inventory (borrowed)
- Instant craft consumes via recipe_db (double-check not needed)
- Minigame consumes on completion
- ESC/cancel returns all borrowed materials

---

## 10. VISUAL ASSETS

### 10.1 Material Icons

**Path Pattern:**
```
assets/generated_icons-2/items/materials/{material_id}-2.png
```

**Verified Examples:**
- `iron_ingot-2.png`
- `fire_crystal-2.png`
- `oak_plank-2.png`
- `slime_gel-2.png`
- `wolf_pelt-2.png`

**Total Available:** 69 material icons

**Usage via ImageCache:**
```python
from rendering.image_cache import ImageCache

image_cache = ImageCache.get_instance()
icon_path = f"materials/{material_id}-2.png"
icon = image_cache.get_image(icon_path, (width, height))

if icon:
    surf.blit(icon, (x, y))
else:
    # Fallback to text
    text = font.render(material_name[:3], True, (255, 255, 255))
    surf.blit(text, (x, y))
```

**Icon Sizing by Context:**
- Material palette: 32x32px
- Smithing grid cells: cell_size - 8px (max 40px)
- Refining slots: 50x50px
- Alchemy slots: 60x60px
- Engineering canvas: 50x50px
- Adornments vertices: 30x30px

---

### 10.2 UI Fonts

**Available Fonts:**
```python
self.font = pygame.font.Font(None, Config.scale(24))        # Main text
self.small_font = pygame.font.Font(None, Config.scale(18))  # Buttons, labels
self.tiny_font = pygame.font.Font(None, Config.scale(14))   # Details, quantities
```

**Usage Guidelines:**
- Headers: `font`
- Button text: `small_font`
- Material names: `tiny_font`
- Slot labels: `tiny_font`
- Status messages: `font`

---

### 10.3 Scaling Function

**All dimensions must use Config.scale():**
```python
s = Config.scale

# Examples:
button_width = s(150)   # NOT 150
cell_size = s(60)       # NOT 60
padding = s(20)         # NOT 20
```

**Why:** Supports different screen resolutions and DPI scaling

---

## IMPLEMENTATION CHECKLIST

**Before starting, verify:**
- [ ] Config.DEBUG_INFINITE_RESOURCES location
- [ ] ImageCache.get_instance() works
- [ ] PlacementDatabase format matches specs
- [ ] RecipeDatabase.get_recipes_for_station() exists
- [ ] All 5 placement JSON files are loaded

**Phase 1 - Core Fixes:**
- [ ] Smithing: 3x3, 5x5, 7x7, 9x9 grid sizes
- [ ] Refining: Variable core+surrounding by tier
- [ ] Alchemy: 2, 3, 4, 6 max slots by tier
- [ ] Engineering: FRAME/FUNCTION/POWER/MODIFIER/UTILITY types
- [ ] Adornments: Complete vertex system redesign

**Phase 2 - Visual Assets:**
- [ ] Material icons in palette
- [ ] Material icons in placements
- [ ] Debug mode 99 quantity display
- [ ] Tier-colored borders
- [ ] Hover states

**Phase 3 - Recipe Matching:**
- [ ] Test all smithing recipes match correctly
- [ ] Test refining with multiple cores (T3/T4)
- [ ] Test alchemy sequential ordering
- [ ] Test engineering slot type grouping
- [ ] Test adornments vertex coordinates

**Phase 4 - Integration:**
- [ ] Verify material borrowing/return
- [ ] Test instant craft flow
- [ ] Test minigame launch
- [ ] Test ESC cancel
- [ ] Test cross-tier compatibility

---

## VERIFICATION DATA

**From Analysis:**

**Smithing Grid Sizes (observed in JSON):**
- T1: 3x3, 5x5, 7x7 all observed (backward compatibility)
- T2: 5x5 standard
- T3: 7x7 standard

**Refining Slot Counts (observed in JSON):**
- All recipes use 1 core currently
- Surrounding counts vary 0-1 (metadata says should be more)

**Alchemy Slot Counts (observed in JSON):**
- T1: max slot 2
- T2: max slot 3
- T3: max slot 4
- T4: max slot 6

**Engineering Slot Types (observed in JSON):**
- FRAME, FUNCTION, POWER, MODIFIER, UTILITY (5 types)
- T1: 2-3 slots used
- T2: 3 slots used
- T3: 3-4 slots used
- T4: 4 slots used

**Adornments Vertex Counts (observed in JSON):**
- Min: 8 vertices
- Max: 42 vertices
- Avg: 17.6 vertices

---

**END OF SPECIFICATION**

This document contains complete, unambiguous specifications for implementing the interactive crafting UI system. No additional documentation should be needed for implementation.
