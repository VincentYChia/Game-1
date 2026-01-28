# Claude Context - Living Documentation Index

**LIVING DOCUMENT**: This index should be modified to reflect changes as the project evolves. Update entries when files are added, removed, or significantly modified.

**Last Updated**: January 27, 2026

---

## Purpose

This directory contains curated developer context for AI assistants and human developers working on Game-1. Files here provide quick references, architectural summaries, and naming conventions to accelerate onboarding and maintain consistency.

---

## File Directory

### 1. **CLAUDE.md**
**Path**: `.claude/CLAUDE.md`
**Purpose**: Primary developer guide for AI assistants and new developers
**Contains**:
- Project summary and current state assessment
- What's implemented vs what's designed
- Architecture overview with module paths
- **LLM integration system** (NEW - January 2026)
- Tag system overview
- Key classes and design patterns
- Critical warnings about assuming features exist

**When to Use**: First file to read when starting work on Game-1. Reference before implementing any feature to check if it's already built.

**Status**: Current (January 27, 2026)
- Reflects modular architecture (136 files, ~62,380 lines)
- LLM integration documented (llm_item_generator.py, crafting_classifier.py)
- 14 enchantments fully working
- Tag system documented
- Combat, skills, save/load all marked as implemented
- Class affinity system documented

---

### 2. **NAMING_CONVENTIONS.md**
**Path**: `.claude/NAMING_CONVENTIONS.md`
**Purpose**: Authoritative API naming reference to prevent method mismatch errors
**Contains**:
- Core naming principles
- Module paths for modular architecture
- **LLM system method names** (NEW - January 2026)
- Character progression method names (`add_exp`, `check_level_up`, `allocate_stat_point`)
- Equipment system conventions (`equipment.slots`, `get_stat_bonuses()`)
- Combat system methods (`calculate_damage`, `apply_status_effect`)
- Skill system methods (`activate_skill`, `get_skill_affinity_bonus`)
- Tag system field naming
- Minigame action patterns
- Save/load system methods
- Common mistakes and corrections

**When to Use**: Before calling ANY method on Character, CombatManager, SkillManager, LLMItemGenerator, or crafting modules. Reference when you get AttributeError or KeyError.

**Status**: Current (January 27, 2026)

**Key Learnings**:
- `add_exp()` NOT `gain_exp()`
- `equipment.slots.items()` NOT `equipment.items()`
- `activate_skill()` NOT `use_skill()`
- Always support both `materialId` and `itemId`

---

### 3. **docs/GAME_MECHANICS_V6.md**
**Path**: `Game-1-modular/docs/GAME_MECHANICS_V6.md`
**Purpose**: **MASTER REFERENCE** - Complete game mechanics specification
**Contains**:
- Implementation status markers (IMPLEMENTED / PARTIAL / PLANNED)
- All stats, formulas, and calculations
- Skill system with 100+ skills
- Combat system with full damage pipeline
- All 5 crafting disciplines
- **LLM Invented Items System** (NEW - January 2026)
- Status effects system
- Title and class systems
- JSON schema specifications

**When to Use**: Source of truth for what's actually implemented. Check before implementing any game mechanic.

**Status**: Current (January 27, 2026) - v6.1 - 5,089+ lines

---

### 4. **docs/tag-system/TAG-GUIDE.md**
**Path**: `Game-1-modular/docs/tag-system/TAG-GUIDE.md`
**Purpose**: Comprehensive tag system documentation
**Contains**:
- All damage type tags (physical, fire, ice, lightning, etc.)
- Geometry tags (single, chain, cone, circle, beam, pierce)
- Status effect tags (burn, bleed, freeze, stun, etc.)
- Special behavior tags (knockback, lifesteal, execute, etc.)
- Tag parameter requirements
- Tag combination examples
- Debugging guide

**When to Use**: When implementing new skills, weapons, or combat effects. Essential for understanding the tag-driven effect system.

**Status**: Current (December 29, 2025) - Production Ready

---

### 5. **MASTER_ISSUE_TRACKER.md**
**Path**: `Game-1-modular/MASTER_ISSUE_TRACKER.md`
**Purpose**: Comprehensive tracking of all known issues, bugs, and testing requirements
**Contains**:
- Quick status overview
- Enchantment system testing status (14/17 working)
- Bug fixes required (with line numbers)
- UI enhancements needed
- Content improvements
- **LLM Integration section** (NEW - January 2026)

**When to Use**: Before starting any bug fix or feature work. Check if issue is already known and tracked.

**Status**: Current (January 27, 2026)

**Recent Resolutions**: Inventory click misalignment, 5 enchantments (Lifesteal, Knockback, etc.), icon_path restoration

---

### 6. **docs/ARCHITECTURE.md**
**Path**: `Game-1-modular/docs/ARCHITECTURE.md`
**Purpose**: System architecture overview
**Contains**:
- Modular architecture statistics (136 files, ~62,380 lines)
- Design principles (composition, singleton, layered)
- Directory structure breakdown
- Layer architecture diagram
- Component system documentation
- Database pattern explanation
- Event and data flow diagrams
- Rendering pipeline
- **LLM Integration line counts** (NEW)

**When to Use**: When understanding how systems connect, adding new modules, or debugging cross-system issues.

**Status**: Current (January 27, 2026) - v3.0

---

### 7. **DOCUMENTATION_INDEX.md**
**Path**: `Game-1-modular/DOCUMENTATION_INDEX.md`
**Purpose**: Master index of all documentation files
**Contains**:
- Links to all active documentation
- Role-based quick reference (developer, content creator, bug fixer, playtester)
- Documentation statistics

**When to Use**: When looking for specific documentation not listed here.

**Status**: Current (December 30, 2025)

---

## Related Documentation

### Tag System (`docs/tag-system/`)
Complete tag system documentation:
- `TAG-GUIDE.md` - Comprehensive guide (START HERE)
- `TAG-REFERENCE.md` - Tag catalog
- `DEBUG-GUIDE.md` - Debugging tags
- `README.md` - Tag system overview

### Archived Context (`../archive/claude-context-nov-17/`)
Previous version of Claude context from November 17, 2025. Historical reference only - superseded by current documents:
- `Claude.md` - Old version (monolithic architecture)
- `CRAFTING_INTEGRATION_QUICK_REFERENCE.md` - Old line number references
- `JSON_VALIDATION_REPORT.md` - Template validation
- `JSON_GENERATION_CHECKLIST.md` - Content creation guide
- `MASS_GENERATION_RECOMMENDATIONS.md` - JSON generation strategy

**When to Reference**: Only for historical context or understanding past decisions.

---

## Quick Start for New Developers

### First-Time Setup:
1. Read `CLAUDE.md` (15 min) - Get project overview
2. Skim `NAMING_CONVENTIONS.md` (5 min) - Familiarize with API patterns
3. Reference `docs/tag-system/TAG-GUIDE.md` for combat/skill work

### Before Implementing Features:
1. Check `docs/GAME_MECHANICS_V6.md` section "Implementation Status"
2. Search codebase to verify current state
3. Reference `NAMING_CONVENTIONS.md` for method names
4. Check `MASTER_ISSUE_TRACKER.md` for known issues

### Before Creating JSON Content:
1. Check existing JSON files for patterns
2. Reference `GAME_MECHANICS_V6.md` Part VI for JSON schemas
3. Follow tag system conventions from `TAG-GUIDE.md`

### When Debugging:
1. Check `NAMING_CONVENTIONS.md` for common API mistakes
2. Check `MASTER_ISSUE_TRACKER.md` for known bugs
3. Use tag debugger for combat issues (see TAG-GUIDE.md)
4. Check architecture docs for system interactions

---

## Key Architectural Principles

### Current System Status (January 27, 2026):

**Fully Functional:**
- World generation & rendering (100x100, chunk-based)
- Resource gathering with tool requirements
- Inventory system (30 slots, drag-and-drop)
- Equipment system (8 slots, durability, weight, repair)
- All 5 crafting disciplines with minigames (5,346 lines)
- Character progression (30 levels, 6 stats)
- Class system (6 classes with tag-driven bonuses)
- Title system (all tiers: Novice through Master)
- **Skill system** (100+ skills, mana, cooldowns, affinity bonuses)
- **Combat system** (full damage pipeline, enchantments, dual wielding)
- **Status effects** (DoT, CC, buffs, debuffs)
- **Enchantments** (14 types active in combat)
- **Full save/load system** (complete state preservation)
- **Tag-driven effect system** (combat, skills, equipment)
- **LLM Integration** (Claude API for invented items) - NEW
- **ML Classifiers** (CNN + LightGBM for recipe validation) - NEW

**Partially Implemented:**
- World generation (basic chunks, detailed templates pending)
- NPC/Quest system (basic functionality)

**Designed But Not Implemented:**
- Advanced skill evolution chains
- Block/Parry combat mechanics
- Summon mechanics
- Advanced spell casting / combos

---

## Tools Directory

### Development Tools (`tools/`)
- `smithing-grid-designer.py` - Tkinter GUI for designing smithing patterns
- `enchanting-pattern-designer.py` - GUI for enchanting patterns

### LLM/ML Tools (`Scaled JSON Development/`)
- `LLM Training Data/Fewshot_llm/` - System prompts and few-shot examples
- `Convolution Neural Network (CNN)/` - Trained CNN models for smithing/adornments
- `Simple Classifiers (LightGBM)/` - Trained LightGBM models for alchemy/refining/engineering

---

## Maintenance Guidelines

### When to Update This Index

1. **New Files Added**: Add entry with path, purpose, and summary
2. **Files Removed**: Delete entry and note in archive if historically significant
3. **Major Refactors**: Update line number references in file summaries
4. **Feature Completion**: Update status indicators
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
- "Add new tag system documentation to claude-context"
- "Update INDEX.md to reflect combat system implementation"
- "Archive outdated integration checklist"

---

## External Resources

- **GitHub**: https://github.com/VincentYChia/Game-1
- **Main Branch**: `main`
- **Development Branch Pattern**: `claude/*`

---

## Support & Questions

When encountering issues:
1. Search this INDEX.md for relevant documentation
2. Check specific guide files listed above
3. Review `MASTER_ISSUE_TRACKER.md` for known issues
4. Check git commits for recent changes (`git log --oneline`)

**Remember**: This is a living document. Keep it updated as the project evolves!

---

**Last Updated**: January 27, 2026
**Maintained By**: Development Team
