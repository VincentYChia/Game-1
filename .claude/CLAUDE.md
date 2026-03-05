# Claude.md - Game-1 Developer Guide

**Quick Reference for AI Assistants & Developers**
**Last Updated**: March 5, 2026

## Project Summary

**Game-1** is a crafting RPG built with Python/Pygame featuring:
- 100x100 tile world with procedural chunk generation
- 5 crafting disciplines (Smithing, Alchemy, Refining, Engineering, Enchanting) with unique minigames
- LLM-powered "Invented Items" system for procedural content generation
- ML classifiers (CNN + LightGBM) for recipe validation
- Full combat system with enemies, damage pipeline, enchantments, and status effects
- 100+ skills with mana, cooldowns, and level-based scaling
- Character progression (30 levels, 6 stats, titles, classes)
- Tag-driven effect system for combat and skills
- Complete save/load system preserving all game state
- Equipment system with durability, weight, and repairs

**Architecture**: Modular (149 Python files, ~75,911 LOC, 398+ JSON data files, 3,749 asset images)
**Master Reference**: `Game-1-modular/docs/GAME_MECHANICS_V6.md` (5,089 lines)
**Status Report**: `Game-1-modular/docs/REPOSITORY_STATUS_REPORT_2026-01-27.md`
**Project Duration**: October 19, 2025 - Present

---

## Unity/C# Migration (PAUSED)

A Unity/C# migration exists in `Unity/` and `Migration-Plan/` but is **paused as of March 2026**.
The Unity port has all 7 phases of C# code written but UIs are ~55-60% functional.
Active development is on the **Python/Pygame 2D version**.

When resuming migration, start with:
- `Migration-Plan/COMPLETION_STATUS.md` (central hub)
- `Migration-Plan/AUDIT_IMPROVEMENT_PLAN.md` (corrected gap list)
- `VISUAL_SYSTEM_REWORK_PLAN.md` (rendering is broken — most urgent)
- `Unity/UI_AUDIT_REPORT.md` (panel-by-panel status)
- `Unity/MANUAL_TASKS_README.md` (scene setup tasks)

---

## Critical: What's Implemented vs Designed

### Fully Working (Python 2D)
- World generation & rendering (100x100 tiles, chunk-based)
- Resource gathering with tool requirements
- Inventory system (30 slots, drag-and-drop)
- Equipment system (8 slots: weapons, armor, tools)
- All 5 crafting disciplines with minigames (5,346 lines total)
- LLM Item Generation via Claude API (systems/llm_item_generator.py - 1,393 lines)
- Crafting Classifiers - CNN for smithing/adornments, LightGBM for others
- Invented Recipes - Player-created content persisted across saves
- Character progression (30 levels, 6 stats, EXP curves)
- Class system (6 classes with tag-driven bonuses)
- Title system (all tiers: Novice through Master)
- Full combat system (damage pipeline, enchantments, dual wielding)
- 100+ skills with mana, cooldowns, effects
- Status effects (DoT, CC, buffs, debuffs - 827 lines)
- 14 Enchantments fully integrated
- Full save/load system (complete state preservation)
- Durability, weight, and repair systems
- Tag-driven effect system (combat, skills, items)
- Difficulty/Reward calculators (material-based scaling)

### Partially Implemented
- World generation (basic chunks, detailed templates pending)
- NPC/Quest system (basic functionality, needs expansion)

### Designed But NOT Implemented
- Advanced skill evolution chains
- Block/Parry combat mechanics (TODO in combat_manager.py)
- Summon mechanics (TODO in effect_executor.py:233)
- Advanced spell casting / combos

**Important**: Don't assume features from design docs exist in code. Check `GAME_MECHANICS_V6.md` for implementation status.

---

## LLM Integration System

### Overview
Players can **invent new items** by placing materials in unique arrangements. The system:
1. Validates placements using ML classifiers (CNN or LightGBM)
2. Generates item definitions via Claude API
3. Adds items to inventory
4. Persists invented recipes for re-crafting

### Key Files
```
systems/
├── llm_item_generator.py      # Claude API integration (1,393 lines)
└── crafting_classifier.py     # CNN + LightGBM validation (1,256 lines)

Scaled JSON Development/
├── LLM Training Data/Fewshot_llm/    # System prompts & examples
├── Convolution Neural Network (CNN)/ # Trained CNN models
└── Simple Classifiers (LightGBM)/    # Trained LightGBM models
```

### Classifier Mapping
| Discipline | Model Type | Input Format |
|------------|------------|--------------|
| Smithing | CNN | 36x36x3 RGB image |
| Adornments | CNN | 56x56x3 RGB image |
| Alchemy | LightGBM | 34 numeric features |
| Refining | LightGBM | 18 numeric features |
| Engineering | LightGBM | 28 numeric features |

### LLM Configuration
```python
# In systems/llm_item_generator.py
model = "claude-sonnet-4-20250514"
temperature = 0.4
max_tokens = 2000
timeout = 30.0
```

### API Key Setup
1. Set environment variable: `export ANTHROPIC_API_KEY="sk-ant-..."`
2. Or create `.env` file in Game-1-modular/: `ANTHROPIC_API_KEY=sk-ant-...`
3. Fallback: MockBackend generates placeholder items without API

---

## Architecture Overview

### Modular Structure

```
Game-1-modular/
├── main.py                      # Entry point (~30 lines)
├── core/                        # Core game systems (23 files, 15,589 LOC)
│   ├── config.py                # Game configuration constants
│   ├── game_engine.py           # Main game engine (7,817 lines)
│   ├── interactive_crafting.py  # 5 discipline crafting UIs (1,078 lines)
│   ├── effect_executor.py       # Tag-based combat effects (624 lines)
│   ├── difficulty_calculator.py # Material-based difficulty (803 lines)
│   ├── reward_calculator.py     # Performance rewards (608 lines)
│   ├── tag_system.py            # Tag registry
│   ├── tag_parser.py            # Tag parsing
│   ├── crafting_tag_processor.py # Discipline tag processing
│   ├── minigame_effects.py      # Particle effects (~2,000 lines)
│   └── testing.py               # Crafting system tester
├── data/                        # Data layer (25 files, 3,745 LOC)
│   ├── models/                  # Pure data classes (dataclasses)
│   └── databases/               # Singleton database loaders (10 files)
├── entities/                    # Game entities (17 files, 6,909 LOC)
│   ├── character.py             # Character class (1,008 lines)
│   └── components/              # Stats, Inventory, Equipment, Skills, etc.
├── systems/                     # Game system managers (16 files, 5,856 LOC)
│   ├── world_system.py          # WorldSystem (generation, chunks)
│   ├── llm_item_generator.py    # LLM integration (1,393 lines)
│   └── crafting_classifier.py   # ML classifiers (1,256 lines)
├── rendering/                   # All rendering code (3 files, 5,679 LOC)
│   └── renderer.py              # Renderer class (2,782 lines)
├── Combat/                      # Combat system (3 files, 2,527 LOC)
│   ├── combat_manager.py        # CombatManager (1,655 lines)
│   └── enemy.py                 # Enemy, EnemyDatabase (867 lines)
├── Crafting-subdisciplines/     # Crafting minigames (8 files, 5,346 LOC)
├── save_system/                 # Save/load system
└── docs/                        # Technical documentation
    ├── GAME_MECHANICS_V6.md     # MASTER REFERENCE (5,089 lines)
    └── tag-system/              # Tag system documentation
```

### Key Classes

**Database Singletons** (load on startup):
- `MaterialDatabase` - 57+ materials from JSON
- `EquipmentDatabase` - Weapons, armor, tools
- `RecipeDatabase` - 100+ recipes across 5 disciplines + invented recipes
- `TitleDatabase` - 40+ achievement titles
- `ClassDatabase` - 6 starting classes with tags
- `SkillDatabase` - 100+ skill definitions
- `PlacementDatabase` - Minigame grid layouts

**Core Systems**:
- `Character` - Player entity with stats, inventory, equipment, skills
- `CombatManager` - Full damage pipeline, enchantments, status effects
- `SkillManager` - Skill activation, mana, cooldowns, affinity bonuses
- `WorldSystem` - 100x100 tiles, chunk-based generation
- `Renderer` - All drawing logic (2,782 lines)
- `GameEngine` - Main loop, event handling, UI (7,817 lines)
- `LLMItemGenerator` - Claude API integration for invented items
- `CraftingClassifierManager` - CNN/LightGBM validation

### Design Patterns

1. **Singleton Databases**: All data loaded once at startup via `get_instance()`
2. **Component Pattern**: Character composed of pluggable components
3. **Dataclasses**: Heavy use of `@dataclass` for data structures
4. **Tag-Driven Effects**: Combat, skills, and items use composable tag system
5. **JSON-Driven Content**: All items, recipes, materials, skills defined in JSON
6. **Background Threading**: LLM generation runs async to avoid UI freeze

---

## Critical Constants

```
Damage: base x hand(1.1-1.2) x STR(1+STRx0.05) x skill x class(max 1.2) x crit(2x) - def(max 75%)
EXP: 200 x 1.75^(level-1), max level 30
Stats: STR +5%dmg, DEF +2%red, VIT +15HP, LCK +2%crit, AGI +5%forestry, INT -2%diff +20mana
Tiers: T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x
Durability: 0% = 50% effectiveness, never breaks
Final Value = Base x (1 + Stat) x (1 + Title) x (1 + Equipment) x (1 + Class Affinity)
```

---

## Tag System

The tag-driven effect system is the core combat mechanic. See `docs/tag-system/TAG-GUIDE.md` for full reference.

**Damage Types**: `physical`, `fire`, `ice`, `lightning`, `poison`, `arcane`, `shadow`, `holy`
**Geometry Tags**: `single`, `chain`, `cone`, `circle`, `beam`, `pierce`
**Status Effects**: `burn`, `bleed`, `poison`, `freeze`, `chill`, `stun`, `root`, `shock`
**Special Behaviors**: `knockback`, `pull`, `lifesteal`, `execute`, `critical`, `reflect`

Tag flow: `JSON Definition -> Database -> Equipment/Skills -> Effect Executor -> Game World`

---

## Combat System

### Damage Pipeline
```
Base Damage (weapon)
  x Hand Type Bonus (+10-20%)
  x Strength Multiplier (1.0 + STR x 0.05)
  x Skill Buff Bonus (+50% to +400%)
  x Class Affinity Bonus (up to +20%)
  x Title Bonus x Weapon Tag Bonuses
  x Critical Hit (2x if triggered)
  - Enemy Defense (max 75% reduction)
  = Final Damage
```

### Enchantments (14 Working)
Sharpness I-III, Protection I-III, Efficiency I-II, Fortune I-II, Unbreaking I-II,
Fire Aspect, Poison, Swiftness, Thorns, Knockback, Lifesteal, Health Regen, Frost Touch, Chain Damage.
Deferred: Self-Repair, Weightless, Silk Touch.

### Status Effects
- **DoT**: Burn, Bleed, Poison, Shock
- **CC**: Freeze, Stun, Root, Slow/Chill
- **Buffs**: Empower, Fortify, Haste, Regeneration, Shield
- **Debuffs**: Vulnerable, Weaken

---

## Key Design Principles

- **Hardcode vs JSON**: System mechanics are hardcoded; all content/values/balance in JSON
- **Stats**: STR, DEF, VIT, LCK, AGI, INT — start at 0, +1 per level, max 30
- **Tiers**: T1 (common) -> T2 (uncommon) -> T3 (rare) -> T4 (legendary), multipliers 1x/2x/4x/8x
- **Durability**: 0% = 50% effectiveness, items never break

---

## Known Issues

**See**: `MASTER_ISSUE_TRACKER.md` for comprehensive bug list

- Tooltip z-order (can be covered by equipment menu)
- Missing crafting station definitions (Tier 3/4)
- Missing station icons (forge_t4.png, enchanting_table_t2.png)
- Block/Parry, Summon mechanics not yet implemented

---

## Quick Command Reference

```bash
cd Game-1-modular
python main.py              # Run game
python -m pytest tests/ -v  # Run tests
```

Debug keys: F1 (debug mode), F2 (learn skills), F3 (grant titles), F4 (max level), F7 (infinite durability)

---

## When Working on This Project

### For Python Development:
- Check `GAME_MECHANICS_V6.md` for implementation status before assuming features exist
- Reference `.claude/NAMING_CONVENTIONS.md` for method names
- Use singleton pattern for databases
- Follow tag system conventions for new combat effects
- Test JSON changes by restarting the game

### DON'T:
- Assume design docs describe implemented features
- Create new JSON schemas without checking existing patterns
- Hardcode values that should be in JSON

---

## Documentation Index

### Primary (in `Game-1-modular/`)
| Document | Purpose |
|----------|---------|
| **docs/GAME_MECHANICS_V6.md** | Master reference - all mechanics (5,089 lines) |
| **docs/REPOSITORY_STATUS_REPORT_2026-01-27.md** | Current system state |
| **MASTER_ISSUE_TRACKER.md** | Known bugs and improvements |
| **docs/tag-system/TAG-GUIDE.md** | Comprehensive tag system guide |
| **docs/ARCHITECTURE.md** | System architecture overview |
| **DOCUMENTATION_INDEX.md** | Full doc index |

### Migration (PAUSED — in `Migration-Plan/`)
| Document | Purpose |
|----------|---------|
| **COMPLETION_STATUS.md** | Central hub |
| **AUDIT_IMPROVEMENT_PLAN.md** | Corrected gap list |
| **MIGRATION_PLAN.md** | Master overview |

---

## Version History

- **v5.0** (March 5, 2026): Trimmed migration bloat (migration paused), refocused on Python 2D development
- **v4.0** (February 11, 2026): Added Unity/C# migration plan context
- **v3.0** (January 27, 2026): LLM integration, crafting classifiers, invented items
- **v2.0** (December 31, 2025): Modular architecture, tag system, combat, skills, save/load
- **v1.0** (November 17, 2025): Initial Claude.md

---

**Last Updated**: 2026-03-05
**For**: AI assistants and developers working on Game-1
