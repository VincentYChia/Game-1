# Icon Selector Tool

A GUI application to review, compare, and select generated icons for replacing placeholder images.

## Features

- **Side-by-side comparison**: View current placeholder alongside all generated versions
- **Catalog integration**: Displays item metadata (category, type, subtype, narrative)
- **Multiple selection modes**:
  - Select 1 image → Replace placeholder immediately
  - Select 2+ images → Save for later decision
- **Deferred decisions**: Store multiple candidates for items requiring further review
- **Auto-backup**: Original placeholders are backed up before replacement
- **Navigation**: Browse through all 219 catalog items with Previous/Next buttons

## Requirements

```bash
pip install pillow
```

## Usage

### Starting the Tool

```bash
cd Game-1-modular/assets
python3 icon-selector.py
```

### Workflow

1. **Review Item**: The tool displays:
   - Item name and metadata (category, type, subtype, narrative)
   - Current placeholder (if exists)
   - All generated versions from generation cycles

2. **Select Options**:
   - Click on images to select them (border highlights when selected)
   - Select 1 image for immediate replacement
   - Select 2+ images to defer the decision for later review

3. **Take Action**:
   - **Replace Placeholder**: Replace current placeholder with selected image (requires exactly 1 selection)
   - **Save for Later**: Store multiple candidates for later review (requires 2+ selections)
   - **Clear Selection**: Deselect all images
   - **View Deferred**: See all items with deferred decisions

4. **Navigate**:
   - Use **Previous/Next** buttons to browse items
   - Progress indicator shows current position (e.g., "45/219")

### Deferred Decisions

When you can't decide between multiple good options:

1. Select 2-3 candidate images
2. Click **Save for Later**
3. Access them later via **View Deferred** button
4. The tool stores decisions in `deferred_icon_decisions.json`

### Backups

- Replaced placeholders are automatically backed up to `replaced_placeholders/`
- Backup filename format: `{item_name}_{timestamp}.png`
- Example: `iron_sword_20251204_143022.png`

## Directory Structure

### Placeholders (Current Assets)
```
assets/
├── items/
│   ├── weapons/
│   ├── armor/
│   ├── tools/
│   ├── accessories/
│   ├── consumables/
│   ├── materials/
│   ├── stations/
│   └── devices/
├── enemies/
├── resources/
├── skills/
└── titles/
```

### Generated Icons (Generation Cycles)
```
assets/
└── icons-generation-cycle-1/
    ├── generated_icons-2/  (version 2)
    │   ├── items/
    │   ├── enemies/
    │   └── ...
    └── generated_icons-3/  (version 3)
        ├── items/
        └── ...
```

Future cycles would be:
- `icons-generation-cycle-2/`
- `icons-generation-cycle-3/`
- etc.

## File Naming Convention

- **Placeholders**: `{item_name}.png`
  - Example: `iron_sword.png`

- **Generated versions**: `{item_name}-{version}.png`
  - Example: `iron_sword-2.png`, `iron_sword-3.png`

## Keyboard Shortcuts

*Currently not implemented, but could be added:*
- Arrow keys for navigation
- Number keys for quick selection
- Enter to confirm replacement
- Escape to cancel

## Troubleshooting

### "No generated versions found"
- Ensure generation cycles exist in `icons-generation-cycle-*/`
- Check that PNG files follow naming convention
- Verify folder structure matches placeholder structure

### "Placeholder not found"
- Item may not have a placeholder yet
- Check folder structure matches catalog category/type

### Images not loading
- Ensure PIL/Pillow is installed: `pip install pillow`
- Check file permissions
- Verify PNG files are not corrupted

## Technical Details

### Catalog Integration
- Reads from: `assets/icons/ITEM_CATALOG_FOR_ICONS.md`
- Parses 233 items with full metadata (includes Update-N content)
- Auto-categorizes items into correct folder structure

### Selection Logic
- Single selection: Enables immediate replacement
- Multiple selection (2+): Enables deferred decision
- Zero selection: All action buttons disabled

### File Operations
- Safe copy operations (original preserved until successful copy)
- Automatic backup creation
- Atomic file operations to prevent corruption

## Future Enhancements

- [ ] Keyboard shortcuts for faster navigation
- [ ] Bulk replacement mode
- [ ] Image comparison slider (overlay view)
- [ ] Filter by category/type
- [ ] Search by item name
- [ ] Statistics (items completed, remaining, deferred)
- [ ] Export report of all replacements made
- [ ] Undo last replacement
- [ ] Grid view option (multiple items at once)
- [ ] Quality score/rating system

## Files Generated

- `deferred_icon_decisions.json` - Stores items with multiple candidates
- `replaced_placeholders/` - Backup folder for original placeholders
- `__pycache__/` - Python bytecode cache (can be ignored)
