# Default Save System

## Overview

The game now includes a **default save** system for quick testing and development. This is a pre-configured save file with a well-equipped character, making it easy to test features without starting from scratch every time.

## Creating the Default Save

Before you can use the default save, you need to create it first:

```bash
python create_default_save.py
```

This will create `saves/default_save.json` with the following setup:

### Default Character Stats
- **Level:** 10
- **Class:** Warrior
- **Unallocated Stat Points:** 5
- **Stats Distribution:**
  - Strength: 15
  - Defense: 12
  - Vitality: 14
  - Luck: 8
  - Agility: 10
  - Intelligence: 11

### Inventory (18 items)
**Raw Materials:**
- Copper Ore (25), Iron Ore (20), Steel Ore (10)
- Oak Log (30), Birch Log (20), Maple Log (15)
- Limestone (20), Granite (15)

**Refined Materials:**
- Copper Ingot (15), Iron Ingot (10)
- Oak Plank (20), Birch Plank (15)

**Consumables:**
- Minor Health Potion (5)
- Minor Mana Potion (5)

**Equipment (in inventory):**
- Iron Sword (Tier 2, 25 ATK)
- Iron Helmet (Tier 2, 15 DEF)

**Devices:**
- Basic Turret (3)
- Spike Trap (5)

### Equipped Items
- **Main Hand:** Copper Sword
- **Helmet:** Copper Helmet
- **Chestplate:** Copper Chestplate
- **Axe:** Copper Axe
- **Pickaxe:** Copper Pickaxe

### Skills
**Known Skills (5):**
- Fireball (Level 2)
- Heal (Level 1)
- Shield Bash (Level 3)
- Ice Shard (Level 1)
- Power Strike (Level 2)

**Equipped Skills:**
- Slot 1: Fireball
- Slot 2: Heal
- Slot 3: Shield Bash

### Titles
- Novice Explorer
- Apprentice Smith

### Activity Progress
- Mining: 50
- Forestry: 40
- Combat: 60
- Smithing: 25
- Refining: 20
- Engineering: 15
- Alchemy: 10
- Enchanting: 5

### World State
- 1 Basic Turret placed at (48, 48)
- 1 Partially harvested Oak Tree at (45, 45)
- All crafting stations (Tiers 1-4) at default positions

### Quest Progress
- Completed: Tutorial Quest
- Active: None

## How to Load the Default Save

### From Start Menu
1. Launch the game
2. Use UP/DOWN arrows to navigate
3. Select **"Load Default Save"** (3rd option)
4. Press ENTER or SPACE

### During Gameplay
**Shift + F9** - Load default save

This will reload your character with the default save configuration, allowing you to quickly reset to a known testing state.

### Regular Load (for comparison)
**F9** - Load autosave.json (your normal save)

## Use Cases

The default save is perfect for:

### Testing
- **Crafting Systems:** You have materials ready to test all crafting tiers
- **Combat:** Medium-level character with multiple skills to test
- **Equipment:** Both equipped and inventory items for testing equip/unequip
- **Placement:** Devices in inventory to test turret/trap placement
- **Skills:** Multiple skills at different levels to test progression

### Development
- **Quick Start:** Skip the early grind to test mid-game features
- **Consistent State:** Same starting point every time for reproducible testing
- **Feature Testing:** Pre-configured character makes it easy to test new features

### Debugging
- **Known State:** Predictable starting point for debugging
- **Variety:** Enough different items/skills to trigger various code paths
- **Save/Load Testing:** Test save system with a complex character state

## Modifying the Default Save

To customize the default save for your testing needs:

1. Edit `create_default_save.py`
2. Modify the `default_save` dictionary with your desired setup
3. Run `python create_default_save.py` to regenerate
4. Load the updated default save

Example modifications:
```python
# Give yourself more materials
{"item_id": "copper_ore", "quantity": 999, ...},

# Change level
"leveling": {
    "level": 20,  # Instead of 10
    "current_exp": 50000,
    "unallocated_stat_points": 15
},

# Add more skills
"known_skills": {
    "fireball": {"level": 5, "experience": 500},
    # ... add more skills
}
```

## File Location

- **Script:** `create_default_save.py`
- **Save File:** `saves/default_save.json`
- **Documentation:** `SAVE_SYSTEM.md` (main save system docs)

## Controls Reference

### Save Controls
- **F5** - Quick save (autosave.json)
- **F6** - Timestamped save (save_YYYYMMDD_HHMMSS.json)

### Load Controls
- **F9** - Load autosave
- **Shift+F9** - Load default save

### Start Menu
- **Option 1:** New World
- **Option 2:** Load World (autosave)
- **Option 3:** Load Default Save ← New!
- **Option 4:** Temporary World (no saves)

## Troubleshooting

**"Default save not found!"**
- Solution: Run `python create_default_save.py` to create it

**Default save loads but items are missing**
- Check that item IDs in `create_default_save.py` match your item database
- Some items may not exist in older versions of the game

**Character appears but inventory is empty**
- The save system may have changed - regenerate the default save
- Check console for error messages about missing item definitions

**Crashes on load**
- Ensure save version matches current game version
- Check `SAVE_SYSTEM.md` for compatibility information
- Regenerate default save with updated script

## Notes

- The default save is **version 2.0** format (new save system)
- It includes all features: inventory, equipment, skills, world state, quests
- The world will regenerate randomly, but placed items will be restored
- Useful for both development and testing purposes
- Does not interfere with your normal saves (uses separate file)
