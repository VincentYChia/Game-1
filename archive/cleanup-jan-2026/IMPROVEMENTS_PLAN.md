# Interactive Crafting UI Improvements Plan

## Changes to Implement

### 1. Alchemy Quantity Indicator ✓ (Core done, renderer pending)
- Core logic: Already supports quantity stacking (completed)
- Renderer: Add visual quantity display (e.g., "x2") on placed materials

### 2. Adornments Shape-Based UI (Complete redesign)
- Core logic: Already redesigned with shape placement system
- Renderer needs:
  - Shape selection buttons (triangle_equilateral_small, square_small, etc.)
  - Rotation controls (0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°)
  - Grid visualization (Cartesian coordinates, -7 to +7)
  - Shape preview (follows mouse before placement)
  - Shape rendering (draw lines between vertices)
  - Vertex rendering (dots at coordinates, highlighted when material assigned)
  - Material assignment UI (click vertex to assign)

### 3. UI Overlap Fix
- Problem: Smithing grid extends too far down
- Solution: Adjust placement_h dimensions in renderer

### 4. Tooltips System
- Add hover tooltips for:
  - Regular crafting UI (recipe materials)
  - Interactive crafting UI (all materials in palette)
  - Placed materials (show name on hover)
- Implementation: Track mouse position, detect hover, render tooltip near cursor

### 5. Disable Recipe Material Replacement
- Location: core/game_engine.py lines 2454-2480
- Current: Clicking placement slots adds/removes materials
- New: Remove this functionality, keep only tooltip display

### 6. PNG Icons Verification
- Status: Already implemented in interactive_crafting renderer
- Need to verify: All materials display with PNG icons

## Implementation Order

1. Disable material replacement (game_engine.py)
2. Add tooltip system (renderer.py)
3. Fix UI overlap (renderer.py)
4. Add alchemy quantity indicators (renderer.py)
5. Implement complete adornments UI (renderer.py)
6. Test all disciplines with debug mode
