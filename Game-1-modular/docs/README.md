# Documentation Index

Complete documentation for Game-1-Modular.

**Last Updated**: 2026-04-24 (doc consolidation pass)
**Version**: 2.1 (post-consolidation)

> **2026-04-24**: Documentation underwent a consolidation pass. Several superseded or shipped-design docs were moved to `../../archive/2026-04-24-doc-consolidation/`. Key reference docs for active development are listed below.

---

## Quick Links

### 🚀 Getting Started
- **[HOW_TO_RUN.md](../HOW_TO_RUN.md)** - Quick start guide, installation, troubleshooting

### 🎮 Game Mechanics
- **[GAME_MECHANICS_V6.md](GAME_MECHANICS_V6.md)** — Master reference for all game mechanics (damage, stats, tiers, crafting, etc.)

### 🏗️ Architecture
- **[`../.claude/CLAUDE.md`](../../.claude/CLAUDE.md)** — Current architecture + directory layout (canonical). The prior `ARCHITECTURE.md` was archived on 2026-04-24 as its contents were subsumed by CLAUDE.md and its own header admitted staleness.

### 📚 Module Reference
- **[MODULE_REFERENCE.md](MODULE_REFERENCE.md)** - Detailed documentation of every file
  - Purpose of each module
  - Key classes and methods
  - Usage examples
  - Dependencies

### 👩‍💻 Development
- **[DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)** - Guide for contributors
  - Setup instructions
  - Coding standards
  - Adding new features
  - Debugging tips
  - Testing strategies
  - Best practices

---

## Documentation Overview

### For New Users
1. Start with [HOW_TO_RUN.md](../HOW_TO_RUN.md) to get the game running
2. Press **L** in-game to open Encyclopedia (built-in game guide)
3. Press **F1** for debug mode (infinite materials for testing)

### For Developers
1. Read [`../../.claude/CLAUDE.md`](../../.claude/CLAUDE.md) for current architecture + directory layout
2. Review [MODULE_REFERENCE.md](MODULE_REFERENCE.md) to find specific modules
3. Follow [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) for coding standards
4. For JSON content authoring, see [DEVELOPER_GUIDE_JSON_INTEGRATION.md](DEVELOPER_GUIDE_JSON_INTEGRATION.md) and [UPDATE_N_SYSTEM.md](UPDATE_N_SYSTEM.md)

### For Maintainers
1. Update docs when making architectural changes
2. Keep [MODULE_REFERENCE.md](MODULE_REFERENCE.md) in sync with code
3. Document new features in all relevant guides
4. Feature-parity checklist (vs. original singular `main.py`) is archived at [`../../archive/2026-04-24-doc-consolidation/historical-planning/FEATURES_CHECKLIST.md`](../../archive/2026-04-24-doc-consolidation/historical-planning/FEATURES_CHECKLIST.md); the parity goal was achieved.

---

## Project Statistics

| Metric | Value |
|--------|-------|
| **Total Lines of Code** | ~33,000+ |
| **Python Files** | 70+ |
| **Classes** | 62+ |
| **Average Lines/File** | ~150 |
| **Documentation Files** | 40+ |
| **Total Doc Lines** | ~10,000 |

---

## Key Concepts

### Modular Architecture
The codebase is organized into layers:
```
main.py → core/ → systems/, rendering/, entities/ → data/ → config
```
No circular dependencies. Each layer imports from lower layers only.

### Component-Based Entities
Character is composed of pluggable components:
- Stats, Leveling, Skills, Equipment, Inventory, etc.
- Easy to test and extend

### Singleton Databases
All data loaded from JSON into singleton databases:
- MaterialDatabase, EquipmentDatabase, RecipeDatabase, etc.
- Consistent state across the application

### Separation of Concerns
- **Data models**: Define structure (dataclasses)
- **Databases**: Manage collections (singletons)
- **Components**: Add capabilities (composable)
- **Systems**: Orchestrate logic (stateful)
- **Rendering**: Visualize state (stateless)
- **Game Engine**: Coordinate everything (top-level)

---

## Documentation Standards

### When to Update Documentation

Update documentation when:
- ✅ Adding new features
- ✅ Changing architecture
- ✅ Modifying public APIs
- ✅ Fixing major bugs
- ✅ Adding new modules
- ✅ Changing file structure

### Documentation Style

- **Clear**: Use simple language
- **Concise**: Avoid redundancy
- **Complete**: Cover all aspects
- **Current**: Keep in sync with code
- **Examples**: Show, don't just tell

### Code Comments vs Documentation

```python
# Code comments: Explain WHY, not WHAT
def calculate_damage(base, multiplier):
    # Use int() to prevent floating-point damage
    return int(base * multiplier)
```

Documentation explains WHAT the function does for users of the API.

---

## File Organization

```
docs/
├── README.md                             # This file - documentation index
├── GAME_MECHANICS_V6.md                  # Master game mechanics reference
├── MODULE_REFERENCE.md                   # Per-file documentation
├── DEVELOPMENT_GUIDE.md                  # Developer workflow
├── DEVELOPER_GUIDE_JSON_INTEGRATION.md   # JSON content authoring paths
├── UPDATE_N_SYSTEM.md                    # Update-N deployment system
├── INTERACTIVE_CRAFTING_SPECIFICATION.md # Crafting UI spec
├── tag-system/                           # Tag system docs
└── json-reference/                       # JSON structure references

../ (project root)
└── HOW_TO_RUN.md              # Quick start guide

Archived (see ../../archive/2026-04-24-doc-consolidation/):
├── ARCHITECTURE.md             (superseded by ../.claude/CLAUDE.md)
└── FEATURES_CHECKLIST.md       (parity goal achieved)
```

---

## Contributing to Documentation

### Adding New Documentation

1. **Determine scope**: What are you documenting?
2. **Choose file**: Which doc file is most appropriate?
3. **Follow style**: Match existing format and tone
4. **Add examples**: Code snippets help understanding
5. **Update index**: Add links from this README if needed

### Reporting Documentation Issues

Found an issue?
- Outdated information
- Unclear explanations
- Missing topics
- Broken links
- Typos

Please open an issue or submit a PR!

---

## Version History

### v2.1 - Feature Complete (2025-12-29)
- Complete turret/trap/bomb/utility device systems
- 100% hostile ability tag coverage
- 5 missing enchantments implemented
- Documentation cleanup (50% reduction, improved organization)

### v2.0 - Modular Refactor (2025-11-19)
- Complete refactor from 10,327-line singular file
- Organized into 70+ Python modules
- 100% feature parity maintained
- Comprehensive documentation suite created

### v1.0 - Original Singular Version
- Single 10,327-line main.py file
- All features implemented
- Basic inline comments only

---

## Additional Resources

### In-Game Help
- Press **L** to open Encyclopedia
- Press **F1** for debug mode
- Press **ESC** for menu

### External Links
- [Pygame Documentation](https://www.pygame.org/docs/)
- [Python Dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [Type Hints Guide](https://docs.python.org/3/library/typing.html)

---

## Quick Reference

### Control Keys
```
WASD       - Movement
E          - Equipment UI
C          - Stats UI
K          - Skills UI
L          - Encyclopedia
TAB        - Cycle weapons
1-5        - Skill hotbar
F1         - Debug mode
F5         - Save
F6         - Load
ESC        - Close UI / Menu
```

### Debug Commands
```
F1         - Toggle debug mode
F5         - Autosave
F6         - Load save
F9         - Quicksave
F10        - Quickload
```

### Common File Locations
```
Core logic:       core/game_engine.py
Configuration:    core/config.py
Character:        entities/character.py
Rendering:        rendering/renderer.py
World:            systems/world_system.py
Combat:           Combat/combat_manager.py
```

---

## Support

### Getting Help

1. **Check documentation** (this folder)
2. **Review code comments** in relevant modules
3. **Use verify_imports.py** to test setup
4. **Search git history** for context
5. **Ask maintainers** if stuck

### Reporting Issues

Include:
- What you expected
- What happened instead
- Steps to reproduce
- Error messages (full traceback)
- Python version
- OS (Windows/Linux/Mac)

---

**Happy Gaming & Coding!** 🎮

For the latest updates, see the git commit log.
For questions, contact project maintainers.
