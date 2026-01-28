# Documentation Index

**Last Updated**: 2026-01-27

This is the master documentation index for Game-1. All documentation has been reorganized for clarity and maintainability.

> **IMPORTANT:** Use `GAME_MECHANICS_V6.md` as the source of truth for what's actually implemented.
> Use `REPOSITORY_STATUS_REPORT_2026-01-27.md` for comprehensive current state.

---

## AUTHORITATIVE DOCUMENTS (Source of Truth)

These documents reflect what is ACTUALLY IMPLEMENTED in code:

| Document | Purpose | Priority |
|----------|---------|----------|
| **[docs/GAME_MECHANICS_V6.md](docs/GAME_MECHANICS_V6.md)** | **MASTER REFERENCE** - All implemented game mechanics (v6.1) | READ FIRST |
| **[docs/REPOSITORY_STATUS_REPORT_2026-01-27.md](docs/REPOSITORY_STATUS_REPORT_2026-01-27.md)** | Comprehensive system state (NEW) | Current status |
| **[.claude/CLAUDE.md](../.claude/CLAUDE.md)** | Developer guide for AI assistants | Developer reference |
| **[MASTER_ISSUE_TRACKER.md](MASTER_ISSUE_TRACKER.md)** | Known issues, bugs, unimplemented features | Check for bugs |

---

## NEW: LLM Integration Documentation

| Document | Purpose |
|----------|---------|
| **[../Scaled JSON Development/LLM Training Data/Fewshot_llm/README.md](../Scaled%20JSON%20Development/LLM%20Training%20Data/Fewshot_llm/README.md)** | LLM system overview |
| **[../Scaled JSON Development/LLM Training Data/Fewshot_llm/MANUAL_TUNING_GUIDE.md](../Scaled%20JSON%20Development/LLM%20Training%20Data/Fewshot_llm/MANUAL_TUNING_GUIDE.md)** | Prompt tuning guide |

---

## Getting Started

- **[README.md](README.md)** - Project overview and quick start
- **[HOW_TO_RUN.md](HOW_TO_RUN.md)** - Running the game
- **[PLAYTEST_README.md](PLAYTEST_README.md)** - Playtesting guide

---

## Core Documentation

### Architecture & Development
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture overview (136 files, ~62,380 LOC)
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

---

## Crafting & Interactive Systems

- **[docs/INTERACTIVE_CRAFTING_SPECIFICATION.md](docs/INTERACTIVE_CRAFTING_SPECIFICATION.md)** - Technical spec for crafting UIs
- **[docs/INTERACTIVE_CRAFTING_USAGE.md](docs/INTERACTIVE_CRAFTING_USAGE.md)** - Usage guide
- **[Crafting-subdisciplines/SIMPLIFIED_RARITY_SYSTEM.md](Crafting-subdisciplines/SIMPLIFIED_RARITY_SYSTEM.md)** - Rarity system
- **[Crafting-subdisciplines/STAT_MODIFIER_DESIGN.md](Crafting-subdisciplines/STAT_MODIFIER_DESIGN.md)** - Stat modifiers

---

## Assets & Icons

- **[docs/ICON_PATH_CONVENTIONS.md](docs/ICON_PATH_CONVENTIONS.md)** - Icon file path conventions
- **[tools/README_ICON_AUTOMATION.md](tools/README_ICON_AUTOMATION.md)** - Icon automation

---

## Save System

- **[save_system/README.md](save_system/README.md)** - Save system overview
- **[save_system/SAVE_SYSTEM.md](save_system/SAVE_SYSTEM.md)** - Technical details
- **[save_system/README_DEFAULT_SAVE.md](save_system/README_DEFAULT_SAVE.md)** - Default save

---

## Packaging & Distribution

- **[docs/PACKAGING.md](docs/PACKAGING.md)** - Packaging guide

---

## Historical Documentation (Archived)

All historical implementation notes, completion reports, and phase summaries have been archived:

- **[archive/batch-notes/](../archive/batch-notes/)** - BATCH_1-4 implementation notes
- **[archive/old-summaries/](../archive/old-summaries/)** - Completion reports and status updates
- **[archive/tag-system-old/](../archive/tag-system-old/)** - Tag system phase documentation
- **[archive/cleanup-jan-2026/](../archive/cleanup-jan-2026/)** - January 2026 archived planning docs

**When to reference archives**: Only when investigating historical context or understanding how a feature was implemented.

---

## Quick Reference by Role

### New Developer
1. Start: [README.md](README.md)
2. Current State: [docs/REPOSITORY_STATUS_REPORT_2026-01-27.md](docs/REPOSITORY_STATUS_REPORT_2026-01-27.md)
3. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
4. Reference: [docs/MODULE_REFERENCE.md](docs/MODULE_REFERENCE.md)

### Content Creator (JSON)
1. Start: [docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md](docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md)
2. Tags: [docs/tag-system/TAG-GUIDE.md](docs/tag-system/TAG-GUIDE.md)
3. Reference: [docs/tag-system/TAG-REFERENCE.md](docs/tag-system/TAG-REFERENCE.md)

### LLM/Classifier Work
1. LLM System: [Fewshot_llm/README.md](../Scaled%20JSON%20Development/LLM%20Training%20Data/Fewshot_llm/README.md)
2. Prompt Tuning: [MANUAL_TUNING_GUIDE.md](../Scaled%20JSON%20Development/LLM%20Training%20Data/Fewshot_llm/MANUAL_TUNING_GUIDE.md)
3. Integration: Check `systems/llm_item_generator.py` and `systems/crafting_classifier.py`

### Bug Fixer
1. Start: [docs/GAME_MECHANICS_V6.md](docs/GAME_MECHANICS_V6.md) - See what's actually implemented
2. Issues: [MASTER_ISSUE_TRACKER.md](MASTER_ISSUE_TRACKER.md) - Known issues
3. Debug: [docs/tag-system/DEBUG-GUIDE.md](docs/tag-system/DEBUG-GUIDE.md)
4. Reference: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)

### Playtester
1. Start: [PLAYTEST_README.md](PLAYTEST_README.md)

---

## Documentation Statistics

**Total Markdown Files**: 155 files (68 active, 87 archived)
**Python Files**: 136 (Game-1-modular) + 39 (Scaled JSON Development)
**Total Lines of Code**: ~83,826

**Key Documents by Importance**:
1. `docs/GAME_MECHANICS_V6.md` - Source of truth for mechanics
2. `docs/REPOSITORY_STATUS_REPORT_2026-01-27.md` - Current comprehensive state
3. `.claude/CLAUDE.md` - Developer guide
4. `MASTER_ISSUE_TRACKER.md` - What needs fixing
5. `docs/tag-system/TAG-GUIDE.md` - How tags work

**Organization**:
- Root: Core tracking docs
- docs/: Technical documentation
- docs/tag-system/: Tag system specifics
- archive/: Historical docs (don't reference unless needed)
- Scaled JSON Development/: LLM/ML training and integration

---

## Finding Documentation

**By Topic**:
- Combat/Effects → `docs/tag-system/`
- Architecture → `docs/ARCHITECTURE.md`
- JSON Data → `docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md`
- LLM/Classifiers → `Scaled JSON Development/LLM Training Data/Fewshot_llm/`
- Icons → `docs/ICON_PATH_CONVENTIONS.md`
- Saves → `save_system/`

**By Activity**:
- Debugging → `docs/tag-system/DEBUG-GUIDE.md`
- Adding content → `docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md`
- Testing → `PLAYTEST_README.md`
- LLM work → `Fewshot_llm/MANUAL_TUNING_GUIDE.md`

---

**Last Updated**: 2026-01-27 - Added LLM integration docs, updated statistics, archived planning docs
