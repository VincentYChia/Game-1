# Python Source (Game-1-modular)

This directory serves as a pointer to the original Python/Pygame codebase.

The full Python source lives at `../Game-1-modular/` and should be treated as **read-only reference** during the Unity migration. Do not modify Python source files as part of the migration process unless fixing a bug that affects golden file generation.

## Key Directories
- `../Game-1-modular/core/` - Core systems (game engine, tags, effects, difficulty/reward)
- `../Game-1-modular/data/` - Data models and database singletons
- `../Game-1-modular/entities/` - Character, components, status effects
- `../Game-1-modular/systems/` - World, combat, ML, LLM, save/load
- `../Game-1-modular/Combat/` - Combat manager and enemies
- `../Game-1-modular/Crafting-subdisciplines/` - 6 crafting minigames
- `../Game-1-modular/rendering/` - Pygame rendering (will be rebuilt in Unity)

## Reference Documentation
- `../Game-1-modular/docs/GAME_MECHANICS_V6.md` - Master mechanics reference (5,089 lines)
- `../.claude/CLAUDE.md` - Developer guide
