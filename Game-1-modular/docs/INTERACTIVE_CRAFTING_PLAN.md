# Implementation Plan: Interactable Crafting Menu System

**Date**: 2026-01-06
**Branch**: claude/review-minigame-improvements-hHS5u
**Status**: Planning Phase

---

## Overview

Transform the current static crafting UI into an interactive system where players can:
1. Manually place materials on grids/patterns to attempt recipes
2. Discover recipes by correct placement (no pre-selection required)
3. Use existing placement validation to check if arrangement matches any known recipe
4. Launch minigames or instant-craft when valid recipe detected

---

## Part 1: Complex Recipe Systems (Smithing & Adornments)

### 1.1 Current State Analysis

**Existing tools (Tkinter GUI - for developers):**
- `tools/smithing-grid-designer.py` (585 lines) - Full grid designer
- `tools/enchanting-pattern-designer.py` (1,050 lines) - Vertex/shape pattern designer

**Key differences for survival mode:**
| Feature | Designer Tool | Survival Mode |
|---------|--------------|---------------|
| Material palette | All materials in game | Only player's inventory |
| Tier restrictions | None | Station tier limits |
| Recipe creation | Creates new JSON | No - uses existing recipes |
| Save/export | JSON file output | No persistence needed |
| Unlimited materials | Yes | Inventory quantities |

### 1.2 Smithing Interactive Crafter

**Implementation Steps:**

1. **Create `InteractiveSmithingUI` class** in `core/interactive_crafting.py`
   ```python
   class InteractiveSmithingUI:
       def __init__(self, character, station_tier):
           self.character = character
           self.station_tier = station_tier
           self.grid_size = min(3 + station_tier, 6)  # T1=4, T2=5, T3=6, T4=6
           self.grid = {}  # {(x,y): ItemStack}
           self.dragging_item = None
           self.matched_recipe = None
   ```

2. **Material Palette System**
   ```python
   def get_available_materials(self):
       """Return materials from inventory that can be placed"""
       mat_db = MaterialDatabase.get_instance()
       available = []
       for slot in self.character.inventory.slots:
           if slot and slot.quantity > 0:
               mat_def = mat_db.get_material(slot.item_id)
               if mat_def and mat_def.tier <= self.station_tier:
                   available.append(slot)
       return available
   ```

3. **Grid Placement Logic**
   ```python
   def place_material(self, grid_pos, item_stack):
       """Place material from inventory onto grid"""
       x, y = grid_pos
       if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
           # Remove from previous position if already placed
           for pos, placed in list(self.grid.items()):
               if placed.item_id == item_stack.item_id:
                   # Return to palette (refund)
                   del self.grid[pos]

           # Place at new position
           self.grid[grid_pos] = ItemStack(
               item_stack.item_id, 1,
               crafted_stats=item_stack.crafted_stats
           )
           # Check for recipe match
           self._check_recipe_match()
   ```

4. **Recipe Matching** (reverse lookup)
   ```python
   def _check_recipe_match(self):
       """Check if current grid matches any known recipe"""
       placement_db = PlacementDatabase.get_instance()
       recipe_db = RecipeDatabase.get_instance()

       # Convert grid to placement format
       current_placement = {}
       for (x, y), item in self.grid.items():
           current_placement[f"{x},{y}"] = item.item_id

       # Search all smithing recipes
       for recipe_id, placement in placement_db.smithing_placements.items():
           recipe = recipe_db.get_recipe(recipe_id)
           if recipe and recipe.station_tier <= self.station_tier:
               if self._placements_match(current_placement, placement.placement_map):
                   self.matched_recipe = recipe
                   return

       self.matched_recipe = None
   ```

5. **UI Rendering** (themed forge aesthetic)
   - Reuse `minigame_effects.py` themed backgrounds
   - Grid cells with forge-glow when filled
   - Material palette on right side (scrollable)
   - Recipe match indicator at bottom
   - Craft/Minigame buttons appear when match found

### 1.3 Adornments Interactive Crafter

Similar to smithing but with vertex-based placement:

1. **Vertex Grid** instead of cell grid
2. **Shape Templates** available (triangle_small, triangle_large, square_small, square_large)
3. **Key Vertex Marking** for special materials
4. **Pattern Rotation** support

---

## Part 2: Simple Recipe Systems (Refining, Alchemy, Engineering)

### 2.1 Refining Interactive Crafter

**Hub-and-Spoke Model:**
```
        [Surr_0]
           |
[Surr_5]--[CORE]--[Surr_1]
           |
        [Surr_2]
  [Surr_4]   [Surr_3]
```

**Implementation:**
```python
class InteractiveRefiningUI:
    def __init__(self, character, station_tier):
        self.core_slot = None  # Single central material
        self.surrounding_slots = [None] * 6  # 6 surrounding slots
        self.station_tier = station_tier

    def place_core(self, item_stack):
        self.core_slot = item_stack
        self._check_recipe_match()

    def place_surrounding(self, slot_index, item_stack):
        if 0 <= slot_index < 6:
            self.surrounding_slots[slot_index] = item_stack
            self._check_recipe_match()
```

### 2.2 Alchemy Interactive Crafter

**Sequential Slots Model:**
```
[Slot 1] -> [Slot 2] -> [Slot 3] -> [Result]
   |           |           |
  Base      Reagent     Catalyst
```

**Implementation:**
```python
class InteractiveAlchemyUI:
    def __init__(self, character, station_tier):
        self.slots = [None] * (3 + station_tier)  # More slots at higher tiers
        self.station_tier = station_tier

    def place_in_slot(self, slot_index, item_stack):
        if 0 <= slot_index < len(self.slots):
            self.slots[slot_index] = item_stack
            self._check_recipe_match()
```

### 2.3 Engineering Interactive Crafter

**Slot-Type Model:**
```
[Core] [Core]        <- Core components (metal frame)
[Spring] [Gear]      <- Mechanical parts
[Wiring]             <- Optional enhancements
```

**Implementation:**
```python
class InteractiveEngineeringUI:
    SLOT_TYPES = ['core', 'spring', 'gear', 'wiring', 'enhancement']

    def __init__(self, character, station_tier):
        self.slots = {slot_type: [] for slot_type in self.SLOT_TYPES}
        self.station_tier = station_tier

    def place_in_slot_type(self, slot_type, item_stack):
        if slot_type in self.slots:
            self.slots[slot_type].append(item_stack)
            self._check_recipe_match()
```

---

## Part 3: Crafting UI Integration

### 3.1 Add "Interactive Mode" Button

**Location**: Right panel of crafting UI, above recipe preview

**Implementation in `renderer.py`:**
```python
def _render_crafting_ui_header(self, discipline, station_tier):
    # ... existing header code ...

    # Add Interactive Mode button
    btn_x = panel_x + panel_w - 150
    btn_y = panel_y + 10
    btn_rect = pygame.Rect(btn_x, btn_y, 140, 35)

    pygame.draw.rect(surface, (60, 80, 60), btn_rect, border_radius=5)
    pygame.draw.rect(surface, (100, 140, 100), btn_rect, 2, border_radius=5)

    btn_text = self.small_font.render("Interactive Mode", True, (200, 255, 200))
    surface.blit(btn_text, (btn_x + 70 - btn_text.get_width()//2, btn_y + 8))

    return btn_rect  # Store for click handling
```

### 3.2 Click Handler in `game_engine.py`

```python
def _handle_crafting_ui_click(self, mouse_pos):
    # ... existing click handling ...

    # Check Interactive Mode button
    if hasattr(self, 'interactive_mode_btn') and self.interactive_mode_btn:
        if self.interactive_mode_btn.collidepoint(mouse_pos):
            self._open_interactive_crafting()
            return
```

### 3.3 Interactive Mode State Management

```python
def _open_interactive_crafting(self):
    """Open interactive crafting for current discipline"""
    station = self.current_crafting_station

    if station.station_type == StationType.SMITHING:
        self.interactive_ui = InteractiveSmithingUI(self.character, station.tier)
    elif station.station_type == StationType.REFINING:
        self.interactive_ui = InteractiveRefiningUI(self.character, station.tier)
    elif station.station_type == StationType.ALCHEMY:
        self.interactive_ui = InteractiveAlchemyUI(self.character, station.tier)
    elif station.station_type == StationType.ENGINEERING:
        self.interactive_ui = InteractiveEngineeringUI(self.character, station.tier)
    elif station.station_type == StationType.ADORNMENTS:
        self.interactive_ui = InteractiveAdornmentsUI(self.character, station.tier)

    self.interactive_crafting_active = True
```

---

## Part 4: Recipe Validation & Crafting

### 4.1 Recipe Match Feedback

When no recipe matches:
```
"No matching recipe found"
[Grid shows current placement]
[Buttons disabled]
```

When recipe matches:
```
"Recipe Found: Iron Sword"
[Grid highlights matched placement]
[INSTANT CRAFT] [MINIGAME]
```

### 4.2 Craft Button Logic

```python
def _handle_interactive_craft(self, use_minigame=False):
    if not self.interactive_ui or not self.interactive_ui.matched_recipe:
        self.add_notification("No valid recipe!", (255, 100, 100))
        return

    recipe = self.interactive_ui.matched_recipe

    # Validate player has required materials
    if not self._validate_materials_available(recipe):
        self.add_notification("Insufficient materials!", (255, 100, 100))
        return

    if use_minigame:
        self._start_minigame(recipe)
    else:
        self._instant_craft(recipe)

    # Close interactive UI
    self.interactive_crafting_active = False
    self.interactive_ui = None
```

---

## Part 5: Themed Visual Design

### 5.1 Discipline-Specific Themes

| Discipline | Background | Grid Color | Accent |
|------------|-----------|-----------|--------|
| Smithing | Forge glow, embers | Iron gray | Orange/gold |
| Refining | Molten metal | Bronze | Yellow/copper |
| Alchemy | Bubbling cauldron | Purple/green | Teal glow |
| Engineering | Workshop, gears | Steel blue | Bronze/copper |
| Enchanting | Arcane circles | Deep purple | Cyan runes |

### 5.2 Visual Elements

1. **Grid Cells/Slots**
   - Empty: Dark, subtle glow
   - Filled: Material icon + tier-based border
   - Hover: Highlight glow
   - Invalid: Red tint

2. **Material Palette**
   - Grouped by category (ore, wood, gem, etc.)
   - Quantity overlay
   - Tier badge (T1-T4)
   - Grayed out if tier exceeds station

3. **Recipe Match Indicator**
   - Hidden until match found
   - Green glow animation
   - Recipe name + output preview
   - XP bonus indicator

---

## Part 6: File Structure

```
core/
├── interactive_crafting.py (NEW)
│   ├── InteractiveSmithingUI
│   ├── InteractiveRefiningUI
│   ├── InteractiveAlchemyUI
│   ├── InteractiveEngineeringUI
│   └── InteractiveAdornmentsUI
│
├── game_engine.py (MODIFY)
│   ├── _open_interactive_crafting()
│   ├── _handle_interactive_craft()
│   └── _render_interactive_ui()
│
└── minigame_effects.py (REUSE)
    └── Themed backgrounds/particles

rendering/
└── renderer.py (MODIFY)
    └── _render_interactive_mode_btn()
```

---

## Part 7: Implementation Order

### Phase 1: Core Framework (3-4 files)
1. Create `core/interactive_crafting.py` with base class
2. Implement `InteractiveSmithingUI` first (most complex)
3. Add rendering in `game_engine.py`
4. Add button + click handling

### Phase 2: Simple Disciplines
5. Implement `InteractiveRefiningUI`
6. Implement `InteractiveAlchemyUI`
7. Implement `InteractiveEngineeringUI`

### Phase 3: Complex Second System
8. Implement `InteractiveAdornmentsUI` (vertex-based)

### Phase 4: Polish
9. Add themed visual effects
10. Add material return on placement change
11. Add recipe hint system (optional)
12. Add tutorial tooltips

---

## Part 8: Key Design Decisions

### 8.1 Material Handling
- Materials are **borrowed** from inventory during placement
- On successful craft: Materials consumed
- On cancel/close: Materials returned to inventory
- On minigame failure: Partial materials lost (existing penalty system)

### 8.2 Recipe Discovery
- Players can discover recipes by correct placement
- Matched recipes are highlighted
- No recipe book required (though existing UI remains available)

### 8.3 Tier Restrictions
- Station tier limits maximum material tier
- Higher tier materials show but are grayed out
- Tooltip explains tier restriction

### 8.4 Stacking Behavior
- Materials with different `crafted_stats` don't stack
- When placing, use highest-bonus material first (optional setting)

---

## Part 9: Data Flow

```
[Player Inventory]
       |
       v
[Material Palette] ---(drag)---> [Placement Grid/Slots]
       ^                                    |
       |                                    v
       +---------(return)------------ [Recipe Matcher]
                                           |
                                           v
                              [Recipe Found?]
                                /           \
                             No              Yes
                              |               |
                        [Disabled]      [Craft Buttons]
                                              |
                                              v
                                   [Minigame / Instant]
                                              |
                                              v
                                     [Consume Materials]
                                              |
                                              v
                                      [Output Item]
```

---

## Estimated Scope

| Component | Estimated Lines | Complexity |
|-----------|----------------|------------|
| `interactive_crafting.py` | 600-800 | Medium |
| `game_engine.py` changes | 200-300 | Medium |
| `renderer.py` changes | 300-400 | Medium |
| Visual effects integration | 100-150 | Low |
| **Total** | **1200-1650** | |

---

## Open Questions

1. **Recipe hints**: Should the UI show hints for partially-matched recipes?
2. **Favorites**: Save favorite placements for quick re-use?
3. **Tutorial**: First-time tutorial explaining interactive mode?
4. **Keyboard shortcuts**: Allow grid navigation via keyboard?

---

## Summary

This implementation creates a unified interactive crafting system that:
- Reuses existing placement validation logic
- Respects survival mode restrictions (inventory, tiers)
- Provides discipline-specific themed UIs
- Integrates seamlessly with existing minigame system
- Maintains backwards compatibility with recipe-selection mode
