# Interactive Crafting System - Usage Guide

**Status**: ✅ FULLY IMPLEMENTED AND INTEGRATED
**Date**: 2026-01-08
**Branch**: `claude/interactive-crafting-ui-fPYjX`

---

## 🎯 Overview

The interactive crafting system allows players to manually place materials in discipline-specific patterns to discover and craft recipes. This provides a more engaging crafting experience compared to the traditional recipe list.

## 🚀 How to Use

### Opening Interactive Mode

1. **Approach a crafting station** (Smithing, Refining, Alchemy, Engineering, or Adornments)
2. **Press `C`** to open the regular crafting UI
3. **Click the "Interactive Mode" button** in the crafting UI header
4. The interactive crafting UI will open with a material palette and placement area

### Controls

| Action | Control |
|--------|---------|
| **Select Material** | Left-click material in palette |
| **Place Material** | Left-click placement area |
| **Remove Material** | Right-click placement area |
| **Scroll Materials** | Mouse wheel in palette area |
| **Clear All** | Click "Clear" button |
| **Instant Craft** | Click "Instant Craft" (when recipe matches) |
| **Start Minigame** | Click "Minigame" (when recipe matches) |
| **Close** | Press `ESC` |

### Workflow

1. **Select a material** from the palette on the left
2. **Place it** in the appropriate position in the placement area
3. **Continue placing materials** until the pattern matches a recipe
4. **Recipe matched!** - The status will show the matched recipe
5. **Choose how to craft**:
   - **Instant Craft**: Quick craft with base stats
   - **Minigame**: Play the discipline minigame for quality bonuses

---

## 📐 Discipline-Specific Layouts

### 1. Smithing - Grid Placement

**Grid Sizes by Tier:**
- Tier 1: **3x3** grid
- Tier 2: **5x5** grid
- Tier 3: **7x7** grid
- Tier 4: **9x9** grid

**How it Works:**
- Materials are placed in specific grid positions
- Pattern must match recipe placement exactly
- Example: Iron Sword might require iron ingots in a sword-shaped pattern

**Visual:**
```
T1 Smithing (3x3):
┌─┬─┬─┐
│ │I│ │  I = Iron Ingot
├─┼─┼─┤  W = Wood Handle
│ │I│ │
├─┼─┼─┤
│ │W│ │
└─┴─┴─┘
```

### 2. Refining - Hub-and-Spoke

**Slot Configuration by Tier:**
- Tier 1: **1 core** + **2 surrounding**
- Tier 2: **1 core** + **4 surrounding**
- Tier 3: **2 cores** + **5 surrounding**
- Tier 4: **3 cores** + **6 surrounding**

**How it Works:**
- Core materials go in the center slot(s)
- Modifiers/catalysts go in surrounding slots
- Order doesn't matter within core or surrounding groups

**Visual:**
```
T2 Refining (1+4):
      [S1]
       |
[S4]─[CORE]─[S2]
       |
      [S3]
```

### 3. Alchemy - Sequential Slots

**Slot Counts by Tier:**
- Tier 1: **2 slots**
- Tier 2: **3 slots**
- Tier 3: **4 slots**
- Tier 4: **6 slots**

**How it Works:**
- Ingredients are placed in order from left to right
- **Order matters!** Base → Reagent → Catalyst
- Each slot can hold one material

**Visual:**
```
T3 Alchemy (4 slots):
[Slot 1] → [Slot 2] → [Slot 3] → [Slot 4] → [Result]
  Base      Reagent   Catalyst   Modifier
```

### 4. Engineering - Slot-Type Canvas

**Slot Types:**
1. **FRAME** - Structural component
2. **FUNCTION** - Core mechanism
3. **POWER** - Energy source
4. **MODIFIER** - Enhancement
5. **UTILITY** - Additional feature

**How it Works:**
- Materials are assigned to specific slot types
- Each slot type can hold multiple materials
- Recipe specifies which types are required

**Visual:**
```
FRAME:    [Material] [Material]
FUNCTION: [Material]
POWER:    [Material]
MODIFIER: [Material] [Material] [Material]
UTILITY:  [Material]
```

### 5. Adornments - Vertex-Based

**Grid Templates by Tier:**
- Tier 1: **square_8x8** (±7 coordinate range)
- Tier 2: **square_10x10** (±7 coordinate range)
- Tier 3: **square_12x12** (±7 coordinate range)
- Tier 4: **square_14x14** (±7 coordinate range)

**How it Works:**
- Uses Cartesian coordinate system with origin (0,0) at center
- Materials placed at specific vertices like (3,3), (-2,5), etc.
- Recipes define exact coordinate patterns
- Origin is highlighted in blue

**Visual:**
```
      7
      │
   ─7─┼─7─  Coordinate grid
      │    Materials at vertices
     -7    like (0,0), (3,3), etc.
```

---

## 🎨 Visual Features

### Material Palette (Left Side)

- **PNG Icons**: Shows material icon (32px) next to name
- **Tier Colors**: Border color indicates tier (gray/green/blue/purple)
- **Selection**: Gold border when selected
- **Scrolling**: Mouse wheel to scroll through materials
- **Quantity**: Shows available quantity and tier

### Placement Area (Right Side)

- **PNG Icons**: Materials show as icons in placements (12-40px)
- **Hover Effects**: Cells/slots highlight on hover
- **Recipe Match**: Green "✓ RECIPE MATCHED" status when pattern matches
- **Clear Visual**: Different backgrounds for empty/filled cells

### Buttons (Bottom)

- **Clear**: Red button - removes all placed materials
- **Instant Craft**: Green button - appears when recipe matches
- **Minigame**: Blue button - appears when recipe matches

---

## 🐛 Debug Mode

When `Config.DEBUG_INFINITE_RESOURCES = True`:
- Material palette shows **99 of every material** up to station tier
- Useful for testing recipe patterns
- Enable in `core/config.py`

---

## 📊 Implementation Details

### Core Files

| File | Purpose | Lines |
|------|---------|-------|
| `core/interactive_crafting.py` | Interactive UI classes | 687 |
| `rendering/renderer.py` | UI rendering with icons | 450 |
| `core/game_engine.py` | Integration and event handling | 150 |
| `docs/INTERACTIVE_CRAFTING_SPECIFICATION.md` | Complete specifications | 1,531 |

### Database Integration

- **MaterialDatabase**: Provides materials for palette
- **RecipeDatabase**: Gets recipes for station/tier
- **PlacementDatabase**: Loads placement patterns
- **ImageCache**: Loads material PNG icons

### Material Borrowing System

When materials are placed:
1. Material is **temporarily removed** from inventory
2. Tracked in `borrowed_materials` dict
3. **Returned on cancel/close** automatically
4. **Consumed on craft** (instant or minigame)

This prevents duplication exploits and ensures clean inventory management.

---

## ✅ Testing

Run the test suite:
```bash
python test_interactive_crafting.py
```

**Test Results:**
- ✓ All modules import correctly
- ✓ All databases load (171 placements)
- ✓ All tier specifications verified correct
- ✓ Debug mode working (99 quantities)
- ✓ Factory function creates all UI types

---

## 🎮 In-Game Usage Example

### Crafting an Iron Sword (Smithing)

1. **Go to Tier 1 Smithing Station**
2. **Press C** → **Click "Interactive Mode"**
3. **Select Iron Ingot** from palette
4. **Place in sword pattern**:
   - (1,0) - Iron Ingot
   - (1,1) - Iron Ingot
   - (1,2) - Iron Ingot
5. **Select Oak Wood** from palette
6. **Place handle**:
   - (1,3) - Oak Wood
7. **✓ RECIPE MATCHED: Iron Sword**
8. **Click "Minigame"** to start smithing minigame
9. **Complete minigame** for quality bonus
10. **Receive crafted Iron Sword!**

---

## 📝 Recipe Discovery

Players can experiment with material combinations to discover recipes:
- Try different patterns in smithing grids
- Test ingredient orders in alchemy
- Combine slot types in engineering
- Explore vertex patterns in adornments

When a valid pattern is created, the recipe is **instantly matched** and shown in the status bar.

---

## 🔧 Configuration

Located in `core/config.py`:

```python
DEBUG_INFINITE_RESOURCES = False  # Set True for debug mode
MENU_XLARGE_W = 1200              # Interactive UI window width
MENU_LARGE_H = 700                # Interactive UI window height
```

---

## 📚 Additional Documentation

- **Specifications**: `docs/INTERACTIVE_CRAFTING_SPECIFICATION.md`
- **Game Mechanics**: `docs/GAME_MECHANICS_V6.md`
- **Tag System**: `docs/tag-system/TAG-GUIDE.md`

---

## 🎉 Features

✅ All 5 disciplines implemented
✅ Tier-specific specifications verified
✅ PNG icon display throughout
✅ Debug mode support
✅ Recipe matching functional
✅ Material borrowing system
✅ Mouse wheel scrolling
✅ Right-click removal
✅ Minigame integration
✅ Instant craft option
✅ Full game engine integration

**The interactive crafting system is complete and ready to use!**
