# Documentation Index

**Last Updated**: 2025-12-30

This is the master documentation index for Game-1. All documentation has been reorganized for clarity and maintainability.

> **IMPORTANT:** Use `GAME_MECHANICS_V6.md` as the source of truth for what's actually implemented.
> Design docs (v5 and earlier) describe aspirations, not reality.

---

## 🎯 AUTHORITATIVE DOCUMENTS (Source of Truth)

These documents reflect what is ACTUALLY IMPLEMENTED in code:

| Document | Purpose | Priority |
|----------|---------|----------|
| **[docs/GAME_MECHANICS_V6.md](docs/GAME_MECHANICS_V6.md)** | **MASTER REFERENCE** - All implemented game mechanics | READ FIRST |
| **[MASTER_ISSUE_TRACKER.md](MASTER_ISSUE_TRACKER.md)** | Known issues, bugs, unimplemented features | Check for bugs |
| **[PLAYTEST_CHANGES.md](PLAYTEST_CHANGES.md)** | Recent changes needing testing | For testers |

---

## 🚀 Getting Started

- **[README.md](README.md)** - Project overview and quick start
- **[HOW_TO_RUN.md](HOW_TO_RUN.md)** - Running the game
- **[PLAYTEST_README.md](PLAYTEST_README.md)** - Playtesting guide

---

## 📋 Current Work

- **[MASTER_ISSUE_TRACKER.md](MASTER_ISSUE_TRACKER.md)** - **START HERE** - All known issues, bugs, and improvements
- **[PLAYTEST_CHANGES.md](PLAYTEST_CHANGES.md)** - Changes that need playtesting
- **[GRANULAR_TASK_BREAKDOWN.md](GRANULAR_TASK_BREAKDOWN.md)** - Detailed task list (Phases 1-7)

---

## 📚 Core Documentation

### Architecture & Development
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture overview
- **[docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)** - Development guidelines
- **[docs/MODULE_REFERENCE.md](docs/MODULE_REFERENCE.md)** - Module and file reference
- **[docs/CODEBASE-CONTEXT.md](docs/CODEBASE-CONTEXT.md)** - Codebase context for developers

### Tag System (Combat & Effects)
- **[docs/tag-system/README.md](docs/tag-system/README.md)** - Tag system overview
- **[docs/tag-system/TAG-GUIDE.md](docs/tag-system/TAG-GUIDE.md)** - **START HERE** - Comprehensive tag guide
- **[docs/tag-system/TAG-REFERENCE.md](docs/tag-system/TAG-REFERENCE.md)** - Tag catalog
- **[docs/tag-system/DEBUG-GUIDE.md](docs/tag-system/DEBUG-GUIDE.md)** - Debugging tags

### JSON Integration
- **[docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md](docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md)** - JSON data integration guide
- **[docs/UPDATE_N_AUTOMATION_WORKFLOW.md](docs/UPDATE_N_AUTOMATION_WORKFLOW.md)** - Update-N automation system
- **[docs/UPDATE_SYSTEM_DOCUMENTATION.md](docs/UPDATE_SYSTEM_DOCUMENTATION.md)** - Update system details

### Features & Planning
- **[docs/GAME_MECHANICS_V6.md](docs/GAME_MECHANICS_V6.md)** - **PRIMARY** - What's actually implemented
- **[docs/FUTURE_MECHANICS_TO_IMPLEMENT.md](docs/FUTURE_MECHANICS_TO_IMPLEMENT.md)** - Planned but NOT implemented features
- **[docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)** - Known limitations and constraints
- **[docs/FEATURES_CHECKLIST.md](docs/FEATURES_CHECKLIST.md)** - Historical feature checklist (may be outdated)

---

## 🎨 Assets & Icons

- **[docs/ICON_PATH_CONVENTIONS.md](docs/ICON_PATH_CONVENTIONS.md)** - Icon file path conventions
- **[assets/ICON_REQUIREMENTS.md](assets/ICON_REQUIREMENTS.md)** - Icon requirements
- **[assets/ICON_SELECTOR_README.md](assets/ICON_SELECTOR_README.md)** - Icon selector tool
- **[assets/icons/ITEM_CATALOG_FOR_ICONS.md](assets/icons/ITEM_CATALOG_FOR_ICONS.md)** - Item catalog
- **[tools/README_ICON_AUTOMATION.md](tools/README_ICON_AUTOMATION.md)** - Icon automation

---

## 💾 Save System

- **[save_system/README.md](save_system/README.md)** - Save system overview
- **[save_system/SAVE_SYSTEM.md](save_system/SAVE_SYSTEM.md)** - Technical details
- **[save_system/README_DEFAULT_SAVE.md](save_system/README_DEFAULT_SAVE.md)** - Default save

---

## 📦 Packaging & Distribution

- **[docs/PACKAGING.md](docs/PACKAGING.md)** - Packaging guide
- **[docs/PACKAGING_SETUP_COMPLETE.md](docs/PACKAGING_SETUP_COMPLETE.md)** - Packaging setup

---

## 🎓 Specialized Systems

### Skills
- **[docs/SKILL-SYSTEM-BUGS.md](docs/SKILL-SYSTEM-BUGS.md)** - Skill system known issues
- **[docs/SKILL-SYSTEM-HANDOFF.md](docs/SKILL-SYSTEM-HANDOFF.md)** - Skill system documentation

### Crafting
- **[Crafting-subdisciplines/SIMPLIFIED_RARITY_SYSTEM.md](Crafting-subdisciplines/SIMPLIFIED_RARITY_SYSTEM.md)** - Rarity system
- **[Crafting-subdisciplines/STAT_MODIFIER_DESIGN.md](Crafting-subdisciplines/STAT_MODIFIER_DESIGN.md)** - Stat modifiers

---

## 📁 Historical Documentation

All historical implementation notes, completion reports, and phase summaries have been archived to reduce clutter:

- **[archive/batch-notes/](archive/batch-notes/)** - BATCH_1-4 implementation notes
- **[archive/old-summaries/](archive/old-summaries/)** - Completion reports and status updates
- **[archive/tag-system-old/](archive/tag-system-old/)** - Tag system phase documentation

**When to reference archives**: Only when investigating historical context or understanding how a feature was implemented.

---

## 🎯 Quick Reference by Role

### New Developer
1. Start: [README.md](README.md)
2. Then: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
3. Then: [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)
4. Reference: [docs/MODULE_REFERENCE.md](docs/MODULE_REFERENCE.md)

### Content Creator (JSON)
1. Start: [docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md](docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md)
2. Tags: [docs/tag-system/TAG-GUIDE.md](docs/tag-system/TAG-GUIDE.md)
3. Reference: [docs/tag-system/TAG-REFERENCE.md](docs/tag-system/TAG-REFERENCE.md)

### Bug Fixer
1. Start: [docs/GAME_MECHANICS_V6.md](docs/GAME_MECHANICS_V6.md) - See what's actually implemented
2. Issues: [MASTER_ISSUE_TRACKER.md](MASTER_ISSUE_TRACKER.md) - Known issues
3. Debug: [docs/tag-system/DEBUG-GUIDE.md](docs/tag-system/DEBUG-GUIDE.md)
4. Reference: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)

### Playtester
1. Start: [PLAYTEST_README.md](PLAYTEST_README.md)
2. Features: [COMPLETE_FEATURE_COVERAGE_PLAN.md](COMPLETE_FEATURE_COVERAGE_PLAN.md)

---

## 📊 Documentation Statistics

**Total Markdown Files**: 92 files
**Active Documentation**: ~40 files (most useful)
**Archived**: ~50 files (historical reference only)

**Key Documents by Importance**:
1. `docs/GAME_MECHANICS_V6.md` - Source of truth for mechanics
2. `MASTER_ISSUE_TRACKER.md` - What needs fixing
3. `PLAYTEST_CHANGES.md` - What to test
4. `docs/tag-system/TAG-GUIDE.md` - How tags work
5. `docs/ARCHITECTURE.md` - System overview

**Organization**:
- Root: Core tracking docs
- docs/: Technical documentation
- docs/tag-system/: Tag system specifics
- archive/: Historical docs (don't reference unless needed)

---

## 🔍 Finding Documentation

**By Topic**:
- Combat/Effects → `docs/tag-system/`
- Architecture → `docs/ARCHITECTURE.md`
- JSON Data → `docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md`
- Icons → `assets/` and `docs/ICON_PATH_CONVENTIONS.md`
- Saves → `save_system/`

**By Activity**:
- Implementing features → `COMPLETE_FEATURE_COVERAGE_PLAN.md` + `GRANULAR_TASK_BREAKDOWN.md`
- Debugging → `docs/tag-system/DEBUG-GUIDE.md`
- Adding content → `docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md`
- Testing → `PLAYTEST_README.md`

---

**Last Updated**: 2025-12-30 - Added Game Mechanics V6 as authoritative source, consolidated documentation
