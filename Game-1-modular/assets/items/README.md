# Item Image System

**Version**: 1.0
**Created**: November 26, 2025
**Purpose**: This directory contains item icons for the game's inventory and UI systems.

---

## 📁 Directory Structure

```
assets/items/
├── materials/      # Stackable materials (ores, logs, ingots, crystals, etc.)
├── weapons/        # Weapon icons (swords, axes, bows, staves, etc.)
├── armor/          # Armor icons (helmets, chestplates, boots, etc.)
├── tools/          # Tool icons (pickaxes, axes, fishing rods, etc.)
├── accessories/    # Accessory icons (rings, amulets, bracelets)
├── stations/       # Crafting station icons (forges, tables, benches)
├── devices/        # Device icons (turrets, bombs, traps, utilities)
└── consumables/    # Consumable icons (potions, oils, food)
```

---

## 🎨 Image Requirements

### File Format
- **Supported formats**: PNG (recommended), JPG/JPEG
- **Recommended format**: PNG with transparency (alpha channel)
- **Color space**: RGB or RGBA

### Image Dimensions
- **Recommended size**: 64x64 pixels or 128x128 pixels
- **Minimum size**: 50x50 pixels (scaled automatically to inventory slot size)
- **Maximum size**: No hard limit, but images are scaled down (larger = slower loading)
- **Aspect ratio**: 1:1 (square) recommended for best display

### File Naming Convention
- **Use the item ID as the filename**: `{item_id}.png` or `{item_id}.jpg`
- **Examples**:
  - Material: `copper_ore.png` (materialId: "copper_ore")
  - Equipment: `iron_shortsword.png` (itemId: "iron_shortsword")
  - Station: `forge_t1.png` (itemId: "forge_t1")

### Quality Guidelines
- **Clarity**: Images should be clear and recognizable at 50x50 display size
- **Transparency**: Use PNG with transparent backgrounds for best results
- **Consistency**: Maintain similar style across all item icons
- **Lighting**: Consider consistent lighting direction for visual coherence

---

## 🔗 Integration with Game Data

### Adding Icons to JSON Files

To link an icon to an item, add the `iconPath` field to your item definition:

#### Materials (items.JSON/items-materials-1.JSON)
```json
{
  "materials": [
    {
      "materialId": "copper_ore",
      "name": "Copper Ore",
      "tier": 1,
      "rarity": "common",
      "category": "ore",
      "iconPath": "materials/copper_ore.png"
    }
  ]
}
```

#### Equipment (items.JSON/items-smithing-1.JSON)
```json
{
  "weapons": [
    {
      "itemId": "iron_shortsword",
      "name": "Iron Shortsword",
      "category": "equipment",
      "tier": 1,
      "rarity": "common",
      "iconPath": "weapons/iron_shortsword.png"
    }
  ]
}
```

#### Stations (items.JSON/items-*.JSON)
```json
{
  "stations": [
    {
      "itemId": "forge_t1",
      "name": "Basic Forge",
      "category": "station",
      "tier": 1,
      "iconPath": "stations/forge_t1.png"
    }
  ]
}
```

### Path Format
- **Relative path**: Always relative to `Game-1-modular/assets/items/`
- **Subdirectory**: Use subdirectory name (materials/, weapons/, etc.)
- **Forward slashes**: Use `/` even on Windows (handled by Python)
- **Optional field**: If `iconPath` is omitted or image doesn't exist, game falls back to colored rectangles

---

## 🎮 How It Works

### Image Loading Flow

1. **JSON Parsing**: When the game loads item definitions, it reads the optional `iconPath` field
2. **Image Cache**: On first render, the image is loaded from disk and cached in memory
3. **Scaling**: Images are automatically scaled to fit inventory slot size (default 50x50)
4. **Fallback**: If image doesn't exist or fails to load, game displays colored rectangle based on rarity
5. **Overlay**: Tier, name, quantity, and equipped markers are always overlaid on top

### Graceful Degradation

The system is designed to **never break the game**:
- ✅ Missing `iconPath` field → uses colored rectangles
- ✅ Invalid file path → uses colored rectangles
- ✅ Corrupted image file → uses colored rectangles
- ✅ Wrong format → uses colored rectangles

The colored rectangle fallback uses rarity-based colors:
- **Common**: Gray (200, 200, 200)
- **Uncommon**: Green (30, 255, 0)
- **Rare**: Blue (0, 112, 221)
- **Epic**: Purple (163, 53, 238)
- **Legendary**: Orange (255, 128, 0)
- **Artifact**: Gold (230, 204, 128)

---

## 📊 Item Catalog

The game currently has **165+ items** requiring icons:

### Equipment (30 items)
- **Weapons**: 11 items (swords, daggers, bows, staves, shields, spears)
- **Armor**: 6 items (helmets, chestplates, leggings, boots, gauntlets)
- **Tools**: 10 items (pickaxes, axes, fishing rods, sickles)
- **Accessories**: 3 items (rings, amulets, bracelets)

### Stations (11 items)
- Forges (T1-T3)
- Refineries (T1-T3)
- Alchemy Tables (T1-T2)
- Engineering Benches (T1-T2)
- Enchanting Table (T1)

### Devices (16 items)
- **Turrets**: 5 items (arrow, fire, lightning, flamethrower, laser)
- **Bombs**: 3 items (simple, fire, cluster)
- **Traps**: 3 items (spike, frost, bear)
- **Utilities**: 5 items (healing beacon, net launcher, EMP, grappling hook, jetpack)

### Consumables (16 items)
- **Healing Potions**: 4 items
- **Buff Potions**: 4 items
- **Resistance Potions**: 3 items
- **Utility Items**: 5 items (oils, powders, solvents)

### Materials (62 items)
- **Ingots**: 7 items (copper, iron, steel, mithril, adamantine, orichalcum, etherion)
- **Alloys**: 4 items (bronze, fire steel, frost steel, lightning copper)
- **Planks**: 5 items (oak, ash, ironwood, ebony, worldtree)
- **Raw Ores**: 8 items
- **Raw Logs**: 8 items
- **Raw Stones**: 10 items
- **Elemental Crystals**: 14 items
- **Monster Drops**: 9 items

### Skills (30 items)
Skills use effect type icons rather than individual skill icons.

See `/assets/icons/ITEM_CATALOG_FOR_ICONS.md` for complete item list with descriptions.

---

## 🛠️ Technical Implementation

### Code Architecture

1. **Data Models** (`data/models/`)
   - `MaterialDefinition`: Added `icon_path: Optional[str]` field
   - `EquipmentItem`: Added `icon_path: Optional[str]` field

2. **Databases** (`data/databases/`)
   - `MaterialDatabase`: Parses `iconPath` from JSON
   - `EquipmentDatabase`: Parses `iconPath` from JSON

3. **Image Cache** (`rendering/image_cache.py`)
   - Singleton pattern for efficient caching
   - Loads images on-demand
   - Scales images to target size
   - Tracks failed loads to avoid repeated attempts
   - Supports cache clearing for development

4. **Renderer** (`rendering/renderer.py`)
   - `render_item_in_slot()`: Modified to use image cache
   - Tries to load image first
   - Falls back to colored rectangles
   - Always overlays text (tier, name, quantity)

### Performance Considerations

- **Lazy Loading**: Images are only loaded when first displayed
- **Caching**: Each scaled image is cached in memory (no repeated disk I/O)
- **Failed Path Tracking**: Failed loads are remembered to avoid repeated attempts
- **Memory Usage**: ~4 bytes per pixel per cached image (RGBA)
- **Example**: 100 cached 50x50 images ≈ 1MB of RAM

### Cache Management

```python
from rendering.image_cache import ImageCache

# Get cache instance
cache = ImageCache.get_instance()

# Get cache statistics
stats = cache.get_cache_stats()
print(f"Cached images: {stats['cached_images']}")
print(f"Failed paths: {stats['failed_paths']}")
print(f"Memory usage: {stats['memory_estimate_mb']:.2f} MB")

# Clear cache (useful during development)
cache.clear_cache()
```

---

## 📝 Example Workflow

### Adding a New Item with Icon

1. **Create the icon**:
   - Design a 64x64 PNG with transparent background
   - Save as `copper_ore.png`

2. **Place the file**:
   - Copy to `Game-1-modular/assets/items/materials/copper_ore.png`

3. **Update JSON**:
   ```json
   {
     "materialId": "copper_ore",
     "name": "Copper Ore",
     "iconPath": "materials/copper_ore.png",
     ...
   }
   ```

4. **Test**:
   - Run the game
   - Collect or craft the item
   - Verify icon displays in inventory
   - If not, check console for loading errors

---

## 🐛 Troubleshooting

### Icon Not Displaying

1. **Check file path**:
   - Ensure `iconPath` in JSON is correct
   - Use forward slashes: `materials/copper_ore.png` (not backslashes)
   - Path is relative to `Game-1-modular/assets/items/`

2. **Check file existence**:
   - Verify file exists at the full path
   - Check file name matches exactly (case-sensitive on Linux)

3. **Check file format**:
   - Ensure file is valid PNG or JPG
   - Try opening in image viewer to verify it's not corrupted

4. **Check console output**:
   - Game silently falls back on errors
   - Check for pygame loading errors in console

### Common Mistakes

❌ **Absolute path**: `iconPath: "/home/user/Game-1/assets/items/materials/copper_ore.png"`
✅ **Relative path**: `iconPath: "materials/copper_ore.png"`

❌ **Missing subdirectory**: `iconPath: "copper_ore.png"`
✅ **With subdirectory**: `iconPath: "materials/copper_ore.png"`

❌ **Wrong ID**: File named `iron_ore.png` but `materialId: "copper_ore"`
✅ **Matching ID**: File named `copper_ore.png` with `materialId: "copper_ore"`

---

## 🎯 Next Steps

### For Artists/Designers

1. Reference `ITEM_CATALOG_FOR_ICONS.md` for item descriptions
2. Create icons following the guidelines above
3. Place files in appropriate subdirectories
4. Update JSON files with `iconPath` references
5. Test in-game and iterate

### For Developers

1. The system is production-ready
2. No code changes needed to add new icons
3. Simply add `iconPath` field to JSON definitions
4. Consider adding thumbnail support for tooltips (future enhancement)
5. Consider adding animated icons (future enhancement)

---

## 📚 References

- **Item Catalog**: `/assets/icons/ITEM_CATALOG_FOR_ICONS.md`
- **JSON Templates**: `/Game-1-modular/Definitions.JSON/JSON Templates/`
- **Code Documentation**: `/Game-1-modular/docs/ARCHITECTURE.md`

---

**Questions or issues?** Check the game's GitHub repository or documentation.
