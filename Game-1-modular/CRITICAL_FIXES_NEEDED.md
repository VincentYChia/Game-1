# Critical Fixes Needed

## Issue 1: Mouse Misalignment in Regular Crafting UI
**Problem:** Mouse perceived as far below actual position when clicking recipes
**Root Cause:** Need to verify coordinate system between renderer and game engine
**Location:** `core/game_engine.py` handle_craft_click(), `rendering/renderer.py` render_crafting_ui()

## Issue 2: Tooltips Not Appearing
**Problem:** Tooltips added but not rendering
**Root Cause:**
- `_pending_tooltips` may not persist between render calls
- Tooltip rendering may happen before surface blit
**Location:** `rendering/renderer.py` multiple locations

## Issue 3: PNGs Not Showing in Interactive Mode
**Problem:** Material icons not displaying in palette or when placed
**Root Cause:** ImageCache paths or get_image() calls failing silently
**Location:** `rendering/renderer.py` interactive crafting renderer

## Issue 4: Adornments Shape Placement Not Working
**Problem:** Can click shapes but can't place them on grid
**Root Cause:** Click handler not properly detecting grid clicks vs shape placement mode
**Also:** Grid should render as dots (vertices) not squares
**Location:** `core/game_engine.py` _handle_interactive_click(), `rendering/renderer.py` adornments renderer

## Issue 5: Recipe Matching Failures
**Problem:** Smithing recipes (iron shortsword) not matching even when correct
**Root Cause:** Coordinate system mismatch between placement and validation
**Location:** `core/interactive_crafting.py` check_recipe_match methods
