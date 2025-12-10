# Icon Path Conventions

This document explains how icon paths are constructed and loaded in the game, ensuring consistency between the icon generator, databases, and renderers.

## Directory Structure

All icons live under `assets/` with the following structure:

```
assets/
├── items/                  # All craftable/obtainable items
│   ├── materials/          # Raw materials, components
│   ├── weapons/            # Weapons (swords, axes, bows, staffs, etc.)
│   ├── armor/              # Armor pieces (helmet, chestplate, boots, etc.)
│   ├── tools/              # Tools (pickaxe, axe for chopping)
│   ├── accessories/        # Accessories (rings, amulets)
│   ├── stations/           # Crafting stations
│   ├── devices/            # Placeable devices (turrets, traps, bombs)
│   └── consumables/        # Consumables (potions, food, buffs)
├── enemies/                # Enemy/hostile creature icons
├── resources/              # Harvestable resource nodes (trees, ore, stone)
├── skills/                 # Skill/ability icons
├── titles/                 # Character titles
├── npcs/                   # NPC character icons
├── quests/                 # Quest icons
└── classes/                # Character class icons
```

## Icon Path Construction Rules

### 1. Items (Equipment & Materials)

**Items** require the `items/` prefix and are categorized by subfolder:

- **Location**: `assets/items/{subfolder}/{item_id}.png`
- **Icon Path**: `{subfolder}/{item_id}.png` (ImageCache adds `items/` prefix)

**Subfolder determination logic** (from `equipment_db.py` and `material_db.py`):

```python
# Equipment items (from equipment JSONs)
if slot in ['mainHand', 'offHand'] and has_damage:
    subfolder = 'weapons'
elif slot in ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']:
    subfolder = 'armor'
elif slot in ['tool', 'axe', 'pickaxe'] or type == 'tool':
    subfolder = 'tools'
elif slot == 'accessory' or type == 'accessory':
    subfolder = 'accessories'
elif type == 'station':
    subfolder = 'stations'
else:
    subfolder = 'weapons'  # Default

# Material items (from materials JSON or refining/alchemy outputs)
if category == 'consumable' or type == 'potion':
    subfolder = 'consumables'
elif category == 'device' or type in ['turret', 'bomb', 'trap', 'utility']:
    subfolder = 'devices'
elif category == 'station':
    subfolder = 'stations'
else:
    subfolder = 'materials'  # Default
```

**Examples**:
- `copper_ingot` → `assets/items/materials/copper_ingot.png` → icon_path: `materials/copper_ingot.png`
- `iron_shortsword` → `assets/items/weapons/iron_shortsword.png` → icon_path: `weapons/iron_shortsword.png`
- `health_potion` → `assets/items/consumables/health_potion.png` → icon_path: `consumables/health_potion.png`

### 2. Non-Item Entities

**Non-items** use direct asset paths (no `items/` prefix):

- **Enemies**: `enemies/{enemy_id}.png`
- **Resources**: `resources/{resource_id}.png` (or `resources/{resource_type}_node.png` for ores/stones)
- **Skills**: `skills/{skill_id}.png`
- **Titles**: `titles/{title_id}.png`
- **NPCs**: `npcs/{npc_id}.png`
- **Quests**: `quests/{quest_id}.png`
- **Classes**: `classes/{class_id}.png`

**Examples**:
- `wolf_grey` → `assets/enemies/wolf_grey.png` → icon_path: `enemies/wolf_grey.png`
- `warrior` → `assets/classes/warrior.png` → icon_path: `classes/warrior.png`
- `oak_tree` → `assets/resources/oak_tree.png` → icon_path: `resources/oak_tree.png`
- `copper_ore` (ResourceType enum) → `assets/resources/copper_ore_node.png` → icon_path: `resources/copper_ore_node.png`

### 3. Special Case: Resource Nodes

Resource nodes use the `ResourceType` enum values with special naming rules:

```python
# From renderer.py (resource icon loading)
resource_value = resource.resource_type.value  # e.g., "copper_ore", "oak_tree"

if "tree" not in resource_value:
    # Ores and stones need "_node" suffix
    icon_path = f"resources/{resource_value}_node.png"
else:
    # Trees use value directly
    icon_path = f"resources/{resource_value}.png"
```

**Resource enum → icon mapping**:
- `ResourceType.OAK_TREE` ("oak_tree") → `resources/oak_tree.png`
- `ResourceType.COPPER_ORE` ("copper_ore") → `resources/copper_ore_node.png`
- `ResourceType.MITHRIL_ORE` ("mithril_ore") → `resources/mithril_ore_node.png`
- `ResourceType.LIMESTONE` ("limestone") → `resources/limestone_node.png`

## ImageCache Path Resolution

The `ImageCache` (in `rendering/image_cache.py`) handles path resolution:

```python
# Direct asset paths (no items/ prefix needed)
if icon_path.startswith(('enemies/', 'resources/', 'skills/', 'titles/',
                         'npcs/', 'quests/', 'classes/')):
    full_path = os.path.join(base_path, icon_path)
else:
    # Item paths (need items/ prefix)
    full_path = os.path.join(base_path, 'items', icon_path)
```

## Adding New Entities

When adding a new entity to the game:

1. **Add JSON entry** (e.g., to `items-smithing-2.JSON`)
2. **Run icon generator**: `python tools/unified_icon_generator.py`
   - Generates placeholder PNG at correct location
   - Updates catalog with correct path
3. **Game auto-loads icon**:
   - Equipment/Material databases construct icon_path automatically
   - ImageCache resolves path correctly
   - No additional code changes needed!

### Example: Adding a New Weapon

1. Add to `items.JSON/items-smithing-2.JSON`:
```json
{
  "itemId": "mythril_greatsword",
  "name": "Mythril Greatsword",
  "category": "equipment",
  "type": "weapon",
  "slot": "mainHand",
  ...
}
```

2. Run icon generator:
```bash
python tools/unified_icon_generator.py
```

3. Result:
   - Placeholder: `assets/items/weapons/mythril_greatsword.png`
   - Catalog entry created
   - Database loads it as: `icon_path = "weapons/mythril_greatsword.png"`
   - Game displays it automatically!

## Consistency Requirements

To ensure icons work correctly:

1. **Icon generator** must use same subfolder logic as databases
2. **Database** must construct icon paths following same rules
3. **ImageCache** must know which paths need `items/` prefix
4. **Renderer** must pass correctly formatted paths to ImageCache

All four components must stay synchronized. If you modify subfolder logic in one place, update all four!

## Troubleshooting

**Icon not loading?**

1. Check file exists: `ls assets/{path}/{id}.png`
2. Check database constructs correct path (add debug print to icon_path)
3. Check ImageCache gets correct path (uncomment debug line in image_cache.py:93)
4. Verify path starts with correct prefix for ImageCache routing

**Wrong subfolder?**

1. Check entity's category/type/slot in JSON
2. Verify subfolder logic in appropriate database
3. Verify icon generator uses same logic in `categorize_item()` and extraction functions
