# Claude Context - Living Documentation Index

**⚠️ LIVING DOCUMENT**: This index should be modified to reflect changes as the project evolves. Update entries when files are added, removed, or significantly modified.

**Last Updated**: November 17, 2025

---

## Purpose

This directory contains curated developer context for AI assistants and human developers working on Game-1. Files here provide quick references, architectural summaries, and naming conventions to accelerate onboarding and maintain consistency.

---

## 📁 File Directory

### 1. **Claude.md**
**Path**: `claude-context/Claude.md`
**Purpose**: Primary developer guide for AI assistants and new developers
**Contains**:
- Project summary and current state assessment
- What's implemented vs what's only designed
- Architecture overview with line number references
- File organization structure
- Key classes and design patterns
- Critical warnings about assuming features exist

**When to Use**: First file to read when starting work on Game-1. Reference before implementing any feature to check if it's already built.

**Status**: Mostly current but predates recent fixes:
- ✅ Core system descriptions accurate
- ⚠️ States "Enchantments don't apply stats yet" (NOW FIXED as of Nov 17)
- ⚠️ States "Zero combat mechanics coded" (Combat IS functional as of Nov 17)
- **TODO**: Update combat and enchantment sections to reflect Nov 17 fixes

---

### 2. **NAMING_CONVENTIONS.md**
**Path**: `claude-context/NAMING_CONVENTIONS.md`
**Purpose**: Authoritative API naming reference to prevent method mismatch errors
**Contains**:
- Core naming principles
- Character progression method names (`add_exp`, `check_level_up`, `allocate_stat_point`)
- Equipment system conventions (`equipment.slots`, `get_stat_bonuses()`)
- Minigame action patterns (`handle_fan()`, `chain()`, `stabilize()`)
- Minigame lifecycle naming
- Common mistakes and corrections

**When to Use**: Before calling ANY method on Character, LevelingSystem, EquipmentManager, or crafting modules. Reference when you get AttributeError or KeyError.

**Status**: ✅ Fully current and accurate

**Key Learnings**:
- `add_exp()` NOT `gain_exp()`
- `equipment.slots.items()` NOT `equipment.items()`
- Minigame methods use `handle_*()` pattern

---

### 3. **CRAFTING_INTEGRATION_QUICK_REFERENCE.md**
**Path**: `claude-context/CRAFTING_INTEGRATION_QUICK_REFERENCE.md`
**Purpose**: Quick lookup for crafting system integration points
**Contains**:
- Line number references to key components in main.py
- Flow diagrams for instant craft vs minigame craft
- Recipe data structure examples
- Placement validation process
- Material consumption logic
- Rarity system integration

**When to Use**: When modifying crafting UI, adding new recipes, debugging crafting errors, or understanding how the 5 disciplines integrate.

**Status**: ✅ Current, line numbers match current main.py (updated Nov 17)

**Quick Lookup**:
- Crafting entry point: `craft_item()` line ~5810
- Instant craft (0 XP): `_instant_craft()` line ~5861
- Minigame craft: `_start_minigame()` line ~5109
- Material validation: `validate_placement()` line ~5631

---

## 📊 Related Documentation

### Archive Directory (`../archive/`)
Historical documentation from past development sessions. Useful for understanding decision rationale but may contain outdated information:

- `ANALYSIS_AND_RECOMMENDATIONS.md` (Nov 16) - What was completed in early sessions
- `BUG_FIX_SUMMARY.md` (Nov 16) - Fixes from systematic debugging session
- `ERROR_ANALYSIS_AND_FIXES.md` (Nov 16) - Root cause analyses
- `MAIN_PY_ANALYSIS.md` (Nov 16) - Comprehensive codebase analysis

**When to Reference**: If you need to understand why a decision was made or what issues were already fixed.

### Development Logs (`../Game-1/Development-logs/`)
Design documentation and game mechanics specifications:

- `Most-Recent-Game-Mechanics-v5` - Master design specification (4,432 lines)
- `Game-Mechanics-1` through `Game-Mechanics-4` - Evolution of design
- `Dev-Sprint-1.txt` - Initial development sprint
- `Initial-Outline.txt` - Original project outline

**Important**: Design docs describe intended features, not implemented ones. Always verify implementation status before using.

---

## 🛠️ Tools Directory (`../Game-1/tools/`)

### `enchanting-pattern-designer.py`
- Tkinter GUI for designing enchanting placement patterns
- Creates vertex-based geometric shapes on 8×8 grid
- Outputs JSON for placements-enchanting-1.JSON

### `smithing-grid-designer.py`
- Tkinter GUI for designing smithing grid placements
- Creates grid-based patterns (3×3 to 9×9 by tier)
- Outputs JSON for placements-smithing-1.JSON

---

## 🔄 Maintenance Guidelines

### When to Update This Index

1. **New Files Added**: Add entry with path, purpose, and summary
2. **Files Removed**: Delete entry and note in archive if historically significant
3. **Major Refactors**: Update line number references in file summaries
4. **Feature Completion**: Update status indicators (⚠️ → ✅)
5. **Significant Bugs Fixed**: Note fixes that invalidate documented issues

### Update Format

When updating, use this structure:
```markdown
### N. **FileName.md**
**Path**: `relative/path/to/file.md`
**Purpose**: One-line summary
**Contains**: Bullet list of key sections
**When to Use**: Guidance on when this file is relevant
**Status**: Current status with version/date if applicable
```

### Version Control

This INDEX.md should be committed with meaningful messages like:
- "Add new performance profiling guide to claude-context"
- "Update Claude.md to reflect combat system implementation"
- "Archive outdated integration checklist"

---

## 📝 Quick Start for New Developers

### First-Time Setup:
1. Read `Claude.md` (10 min) - Get project overview
2. Skim `NAMING_CONVENTIONS.md` (5 min) - Familiarize with API patterns
3. Reference `CRAFTING_INTEGRATION_QUICK_REFERENCE.md` as needed

### Before Implementing Features:
1. Check `Claude.md` section "What's Implemented vs Designed"
2. Search codebase to verify current state
3. Reference `NAMING_CONVENTIONS.md` for method names

### When Debugging:
1. Check `NAMING_CONVENTIONS.md` for common API mistakes
2. Review `CRAFTING_INTEGRATION_QUICK_REFERENCE.md` for line references
3. Consult `../archive/ERROR_ANALYSIS_AND_FIXES.md` for similar historical issues

---

## 🎯 Key Architectural Principles

### Current System Status (as of Nov 17, 2025):

**✅ Fully Functional:**
- World generation & rendering
- Resource gathering with tool requirements
- Inventory system (30 slots, drag-and-drop)
- Equipment system (weapons, armor, 8 slots)
- Crafting (100+ recipes, 5 disciplines, instant + minigame)
- Character progression (30 levels, 6 stats)
- Class system (6 classes with bonuses)
- Title system (all tiers working)
- **Enchantments** (applied to items AND affect combat stats) ✅ Nov 17
- **Combat system** (enemies spawn, attack, drop loot) ✅ Nov 17
- **Weapon range** (different weapons have tactical differences) ✅ Nov 17

**⚠️ Partially Implemented:**
- Skills (30+ defined in JSON, basic mechanics exist, effects not fully implemented)
- Minigames (working for all 5 disciplines but need polish)

**❌ Designed But Not Implemented:**
- Advanced skill evolution chains
- Quest system (designed only)
- NPC interactions (designed only)
- Advanced combat mechanics (spell casting, combos)

---

## 🔗 External Resources

- **GitHub**: https://github.com/VincentYChia/Game-1
- **Main Branch**: `main`
- **Development Branch Pattern**: `claude/*`

---

## 📞 Support & Questions

When encountering issues:
1. Search this INDEX.md for relevant documentation
2. Check specific guide files listed above
3. Review archived documentation for historical context
4. Check git commits for recent changes (`git log --oneline`)

**Remember**: This is a living document. Keep it updated as the project evolves!
