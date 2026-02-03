# Brainstorm: Smithing CNN Visual Representation Improvements

**Goal**: Move beyond simple colored squares to create richer visual representations that encode more semantic information about materials, while maintaining fast inference.

## Current Approach

The current system renders a 9x9 material grid as a 36x36 RGB image:
- Each grid cell = 4x4 pixels of solid color
- Color encodes: Category (Hue), Tier (Brightness), Tags (Saturation)
- Result: Flat colored blocks with no internal structure

**Limitations**:
1. All cells look identical except for color - no visual distinction between "ingot" vs "ore" vs "plank"
2. No indication of material rarity or importance
3. No texture or pattern information
4. CNN may overly rely on exact color matching

---

## Brainstorm Ideas

### 1. Tier-Based Cell Size/Fill
**Concept**: Higher tier materials visually "dominate" more space

**Implementation Options**:
- **Centered fill**: T1 fills 25% of cell, T2 fills 50%, T3 fills 75%, T4 fills 100%
  - Creates visual hierarchy
  - Higher tier = bigger presence
  - Background could be black or very dark gray

- **Ring/border approach**: T4 is solid, lower tiers have progressively larger black borders
  - T4: Full 4x4 solid color
  - T3: 3x3 centered with 1px black border
  - T2: 2x2 centered with 1px black border
  - T1: 1x1 center pixel

**Pros**: Adds tier information visually beyond brightness
**Cons**: Might make lower-tier recipes harder to see

### 2. Material Shape Indicators
**Concept**: Different material types get different internal shapes

**Shape Vocabulary**:
- **Ingots (refined metal)**: Rectangle/bar shape
- **Ores (basic metal)**: Diamond/crystal shape
- **Planks (refined wood)**: Horizontal lines pattern
- **Logs (basic wood)**: Concentric circles (tree rings)
- **Stone**: Irregular/angular polygon
- **Elemental**: Star burst or radiating pattern
- **Monster drops**: Organic curve/blob

**Implementation**: Pre-render 4x4 binary masks for each shape, multiply by material color

**Pros**:
- CNN learns shape→type mapping
- More robust to color variations
- Visually interesting

**Cons**:
- More complex rendering
- Shapes must be distinguishable at 4x4 pixels (challenging)

### 3. Gradient Fills
**Concept**: Instead of flat colors, use gradients that encode direction/tier

**Options**:
- **Radial gradient**: Center bright, edges darker (tier controls gradient steepness)
- **Directional gradient**: Top-left bright to bottom-right dark
- **Category-specific gradients**: Metals = horizontal, Wood = vertical, Stone = radial

**Pros**: Adds depth and visual interest
**Cons**: Might not add useful information for classification

### 4. Pattern Overlays
**Concept**: Add small patterns based on material properties

**Pattern Ideas**:
- **Refined materials**: Subtle vertical/horizontal lines (processed look)
- **Basic/raw materials**: Random noise texture (rough look)
- **Magical materials**: Small sparkle/dot pattern
- **Legendary materials**: Cross-hatch or diamond pattern

**Implementation**: Boolean masks applied as transparency or color mixing

**Pros**: Encodes refined/basic visually
**Cons**: May be too subtle at 4x4 pixel resolution

### 5. Connection Visualization
**Concept**: Draw subtle connections between adjacent same-type materials

**Options**:
- **Same-category glow**: When two adjacent cells are same category, blend boundary
- **Same-material merge**: Identical materials appear to "flow" together
- **Contrast borders**: Draw thin border between different categories

**Pros**: Shows recipe structure, not just individual materials
**Cons**: Makes rendering more complex

### 6. Multi-Channel Encoding
**Concept**: Use RGB channels for different semantic meanings

**Current**: RGB = color (combined meaning)

**Alternative**:
- **R channel**: Category (0-1 scale mapping 5 categories)
- **G channel**: Tier (0.25, 0.5, 0.75, 1.0)
- **B channel**: Refined/Basic flag (0 or 1)

**Pros**:
- Explicit semantic channels
- CNN can learn each independently
- More information density

**Cons**:
- Loses visual interpretability
- May not work well with pre-trained CNN features

### 7. Texture Atlas Approach
**Concept**: Pre-create 4x4 (or 8x8) textures for each material

**Implementation**:
- Create a texture atlas with unique 4x4 patterns for each of the ~60 materials
- At training time, look up material → texture
- Optionally add hue variation to textures

**Pros**:
- Maximum visual distinction
- Can design textures to be meaningful

**Cons**:
- Texture design is manual work
- Doesn't generalize to new materials

### 8. Subpixel Precision
**Concept**: Increase resolution to 8x8 pixels per cell (72x72 total image)

**What this enables**:
- Room for shapes and patterns
- Better gradient rendering
- More visual detail

**Trade-offs**:
- 4x more pixels = slightly more computation
- May need to retrain CNN architecture
- Current 36x36 was chosen for speed

---

## Recommendation Matrix

| Approach | Implementation Effort | Visual Impact | Semantic Value | Performance Impact |
|----------|----------------------|---------------|----------------|-------------------|
| Tier-Based Size | Low | Medium | Medium | None |
| Material Shapes | Medium | High | High | Low |
| Gradient Fills | Low | Low | Low | None |
| Pattern Overlays | Medium | Medium | Medium | Low |
| Connection Viz | High | Medium | Medium | Medium |
| Multi-Channel | Low | Low | High | None |
| Texture Atlas | High | High | High | Low |
| Subpixel (8x8) | Medium | High | Variable | Medium |

---

## Top Recommendations

### Quick Win: Tier-Based Cell Fill
Easy to implement, adds useful visual information:
```python
def render_cell(material_id, cell_size=4):
    tier = get_tier(material_id)
    fill_sizes = {1: 1, 2: 2, 3: 3, 4: 4}
    fill = fill_sizes[tier]
    offset = (cell_size - fill) // 2

    cell = np.zeros((cell_size, cell_size, 3))
    cell[offset:offset+fill, offset:offset+fill] = get_color(material_id)
    return cell
```

### Medium Effort, High Impact: Simple Shape Indicators
4x4 binary masks for major categories:
- Metal (refined): Full square
- Metal (ore): Diamond shape
- Wood (plank): Two horizontal bars
- Wood (log): One center pixel + corners
- Stone: X pattern
- Elemental: + pattern
- Monster: Single center dot

### Future Consideration: 8x8 Resolution
If computational budget allows, doubling resolution would enable much richer visuals without architectural changes (just different input size).

---

## Next Steps (When Ready to Implement)

1. Start with Tier-Based Cell Fill - minimal code change
2. A/B test: Does it improve validation accuracy?
3. If beneficial, add Simple Shape Indicators
4. Consider resolution increase if patterns prove valuable

**Note**: Any visual changes require retraining the CNN. Test on a validation set before committing.
