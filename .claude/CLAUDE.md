# Claude.md - Game-1 Developer Guide

**Quick Reference for AI Assistants & Developers**
**Last Updated**: March 29, 2026

## Project Summary

**Game-1** is a production-ready crafting RPG built with Python/Pygame featuring:
- 100x100 tile world with procedural chunk generation
- 6 crafting disciplines (Smithing, Alchemy, Refining, Engineering, Enchanting, Fishing) with unique minigames
- **LLM-powered "Invented Items" system** for procedural content generation
- **ML classifiers** (CNN + LightGBM) for recipe validation
- **World Memory System** — 7-layer event tracking, 33 evaluators, tag-based retrieval (SQLite)
- Full combat system with enemies, damage pipeline, enchantments, and status effects
- 100+ skills with mana, cooldowns, and level-based scaling
- Character progression (30 levels, 6 stats, titles, classes)
- Tag-driven effect system for combat and skills
- Complete save/load system preserving all game state
- Equipment system with durability, weight, and repairs

**Architecture**: Modular (239 Python files, ~96,400 LOC, ~90 JSON game-definition files, 3,749 asset images)
**Master Reference**: `docs/GAME_MECHANICS_V6.md` (5,154 lines)
**Status Report**: `docs/REPOSITORY_STATUS_REPORT_2026-01-27.md`
**Project Duration**: October 19, 2025 - Present (Python/Pygame — active development)
**Development Plan**: `Development-Plan/OVERVIEW.md` (active roadmap — Living World + Combat Overhaul)
**World Memory System**: `world_system/docs/HANDOFF_STATUS.md` (current implementation state)
**Living World (WNS/WES) Plan**: `Development-Plan/WORLD_SYSTEM_WORKING_DOC.md` — **canonical spec for the downstream half of Living World (World Narrative System + World Executor System + tool mini-stacks). Supersedes `Development-Plan/WORLD_SYSTEM_SCRATCHPAD.md` as the planning doc. Currently v3 (2026-04-21) awaiting user read-through + feedback before implementation begins.**
**Migration Plan**: `archive/Migration-Plan/COMPLETION_STATUS.md` (paused indefinitely — retained for reference)

---

## Active Development: Living World & Combat Overhaul (March 2026)

All development targets the **2D Python/Pygame version**. Unity migration is paused indefinitely.

### Development Plan
- **Start here**: `Development-Plan/OVERVIEW.md` — roadmap and dependency graph
- **Part 1**: `Development-Plan/PART_1_COMBAT_VISUALS.md` — Action combat, animations, hitboxes, projectiles
- **Part 2**: `Development-Plan/PART_2_LIVING_WORLD.md` — Memory layer, NPC agents, factions, world events, quests (ecosystem as tool). **For the next phase downstream of the memory layer (World Narrative System + World Executor System + tool mini-stacks), see `Development-Plan/WORLD_SYSTEM_WORKING_DOC.md` — the canonical spec.**
- **Part 3**: `Development-Plan/PART_3_PLAYER_INTELLIGENCE.md` — Behavior classifier, preferences, arc tracking
- **Shared**: `Development-Plan/SHARED_INFRASTRUCTURE.md` — Balance validator, async runner, event integration

> **⚠️ Resuming Living World work:** If the user asks about WNS, WES, narrative generation, content generation tools (hostiles/materials/nodes/skills/titles), the content registry, or anything downstream of the WMS, the **first action** is to point them at `Development-Plan/WORLD_SYSTEM_WORKING_DOC.md` and ask them to read it + provide feedback on v3 (unless they've already confirmed they've read it). Two rounds of structured feedback shaped v3; a third pass from them is the next step before any implementation.

### Priority Order
1. **Combat Visuals** (P1): Animation framework → attack state machine → hitboxes → projectiles → dodge → enemy scaling → polish
2. **Living World AI** (P2): Memory layer → model backends → NPC agents → factions → world events → quests (ecosystem as query tool)
3. **Player Intelligence** (P3): Behavior classifier → preference model → arc tracker

### Key Architecture Additions
- `animation/` — Frame-based animation system with procedural generation from static sprites
- `Combat/` — Attack state machine, hitbox system, projectile system (expanded from original 3 files to 11)
- `world_system/` — World Memory System (SQLite-backed 7-layer event architecture, ~20,600 LOC)
  - `world_memory/` — StatStore, EventStore, evaluators, tag library, triggers, daily ledger
  - `living_world/` — BackendManager (Ollama/Claude/Mock), NPC agents, factions, ecosystem (tool interface only)
  - `config/` — 7 JSON config files (memory, geographic, backend, faction, event-triggers, npc, tags)
- `events/` — GameEventBus pub/sub system connecting all systems
- `entities/components/stat_tracker.py` — 65 `record_*` methods writing to SQL via StatStore (1,149 lines)

---

## Unity/C# Migration (PAUSED — February 2026)

The Unity migration plan is retained in `archive/Migration-Plan/` for reference but is **not being actively developed**. See `archive/Migration-Plan/COMPLETION_STATUS.md` for the full plan if resuming later.
7. **Phase 7 — Polish & LLM Stub**: `IItemGenerator` interface, E2E testing, 3D verification (1,024 lines)

### Key Architecture Decisions (Migration)
| Decision | Rationale |
|----------|-----------|
| Plain C# for Phases 1-5 | Testable without Unity scene |
| MonoBehaviours only Phase 6 | Thin wrappers around ported logic |
| `IGameItem` interface hierarchy | Type-safe items replace dict-based approach |
| `GamePosition` wrapping `Vector3` | Python `(x,y)` → Unity `(x,0,z)`, height defaults to 0 |
| `TargetFinder` with `DistanceMode` | Toggleable 2D/3D distance calculations |
| `IPathfinder` interface | Grid A* now, NavMesh later — no logic changes |
| `BaseCraftingMinigame` base class | Eliminates ~1,240 lines of duplication |
| `ItemFactory` centralized | 6 scattered creation sites → 1 entry point |
| Event system (`GameEvents`) | Decouples components, replaces direct references |
| Effect dispatch table | Replaces 250-line if/elif chain |

### Migration Document Map
| Document | Lines | Purpose |
|----------|-------|---------|
| `COMPLETION_STATUS.md` | 163 | Central hub and holistic summary |
| `MIGRATION_PLAN.md` | 1,229 | Master overview, risk register |
| `IMPROVEMENTS.md` | 1,424 | All architecture improvements with quick reference |
| `CONVENTIONS.md` | 709 | Living conventions (naming, 3D, items) |
| `PHASE_CONTRACTS.md` | 641 | Per-phase inputs/outputs with C# types |
| `MIGRATION_META_PLAN.md` | 1,075 | Validation strategy, testing approach |
| `phases/PHASE_1-7` | 9,197 | Detailed per-phase instructions |
| `reference/UNITY_PRIMER.md` | 679 | Unity crash course |
| `reference/PYTHON_TO_CSHARP.md` | 902 | Type mappings, pattern conversions |

### Critical Constants (MUST PRESERVE)
```
Damage: base × hand(1.1-1.2) × STR(1+STR×0.05) × skill × class(max 1.2) × crit(2x) - def(max 75%)
EXP: 200 × 1.75^(level-1), max level 30
Stats: STR +5%dmg, DEF +2%red, VIT +15HP, LCK +2%crit, AGI +5%forestry, INT -2%diff +20mana
Tiers: T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x
Durability: 0% = 50% effectiveness, never breaks
```

### Directory Layout
```
Game-1/
├── .claude/                 # AI assistant context (CLAUDE.md, INDEX.md, NAMING_CONVENTIONS.md)
├── .github/                 # CI/CD (workflows/build-game.yml)
├── Development-Plan/        # Active roadmap (19 files — Living World + Combat Overhaul)
├── Game-1-modular/          # Active Python source (239 files, ~96,400 LOC)
├── Scaled JSON Development/ # ML training data/models
├── Python/                  # Pointer directory (README.md only — not a symlink)
├── Unity/                   # Placeholder (README.md only — migration paused)
└── archive/                 # Historical docs
    └── Migration-Plan/      # Paused Unity migration plan (16,013 lines)
```

---

## Critical: What's Implemented vs Designed

### Fully Working
- World generation & rendering (100x100 tiles, chunk-based)
- Resource gathering with tool requirements
- Inventory system (30 slots, drag-and-drop)
- Equipment system (8 slots: weapons, armor, tools)
- **All 6 crafting disciplines with minigames** (8,994 lines total)
- **LLM Item Generation** via Claude API (systems/llm_item_generator.py - 1,392 lines)
- **Crafting Classifiers** - CNN for smithing/adornments, LightGBM for others
- **Invented Recipes** - Player-created content persisted across saves
- Character progression (30 levels, 6 stats, EXP curves)
- Class system (6 classes with tag-driven bonuses)
- Title system (all tiers: Novice through Master)
- **Full combat system** (damage pipeline, enchantments, dual wielding)
- **100+ skills** with mana, cooldowns, effects
- **Status effects** (DoT, CC, buffs, debuffs - 826 lines)
- **14 Enchantments fully integrated** (see Combat section)
- **Full save/load system** (complete state preservation)
- **Durability, weight, and repair systems**
- **Tag-driven effect system** (combat, skills, items)
- **Difficulty/Reward calculators** (material-based scaling)
- **World Memory System** — Layers 1-4 complete, 33 evaluators + 4 consolidators + province summarizer, 93 passing tests (~20,600 LOC)
- **GameEventBus** pub/sub system (events/event_bus.py)
- **StatTracker** — 65 SQL-backed recording methods for comprehensive player analytics
- **Faction System** — Phase 2+ complete (SQLite NPC/player affinity tracking, 19-method API, 21 tests, events published to WMS)
- **Living World consumers** — BackendManager, NPC agents, factions (Phase 2+ complete); ecosystem as tool interface (queries only)

### Partially Implemented
- World generation (basic chunks, detailed templates pending)
- NPC/Quest system (basic functionality, needs expansion)
- World Memory Layers 5-7 (SQL schemas exist, no code writes to them yet)

### Designed But NOT Implemented
- Advanced skill evolution chains
- Block/Parry combat mechanics (TODO in combat_manager.py)
- Summon mechanics (TODO in effect_executor.py:233)
- Advanced spell casting / combos
- BalanceValidator (spec only in Development-Plan/SHARED_INFRASTRUCTURE.md)

**Important**: Don't assume features from design docs exist in code. Check `GAME_MECHANICS_V6.md` for implementation status.

---

## LLM Integration System (NEW - January 2026)

### Overview
Players can **invent new items** by placing materials in unique arrangements. The system:
1. Validates placements using ML classifiers (CNN or LightGBM)
2. Generates item definitions via Claude API
3. Adds items to inventory
4. Persists invented recipes for re-crafting

### Key Files
```
systems/
├── llm_item_generator.py      # Claude API integration (1,392 lines)
└── crafting_classifier.py     # CNN + LightGBM validation (1,419 lines)

Scaled JSON Development/
├── LLM Training Data/Fewshot_llm/    # System prompts & examples
├── Convolution Neural Network (CNN)/ # Trained CNN models
└── Simple Classifiers (LightGBM)/    # Trained LightGBM models
```

### Classifier Mapping
| Discipline | Model Type | Input Format |
|------------|------------|--------------|
| Smithing | CNN | 36×36×3 RGB image |
| Adornments | CNN | 56×56×3 RGB image |
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

### Debug Logs
All LLM API calls are logged to `llm_debug_logs/TIMESTAMP_discipline.json`

---

## Architecture Overview

### Modular Structure

```
Game-1-modular/
├── main.py                      # Entry point (39 lines)
├── core/                        # Core game systems (23 files, 18,764 LOC)
│   ├── config.py                # Game configuration constants
│   ├── game_engine.py           # Main game engine (10,809 lines)
│   ├── interactive_crafting.py  # 6 discipline crafting UIs (1,179 lines)
│   ├── effect_executor.py       # Tag-based combat effects (623 lines)
│   ├── difficulty_calculator.py # Material-based difficulty (808 lines)
│   ├── reward_calculator.py     # Performance rewards (607 lines)
│   ├── tag_system.py            # Tag registry
│   ├── tag_parser.py            # Tag parsing
│   ├── crafting_tag_processor.py # Discipline tag processing
│   ├── minigame_effects.py      # Particle effects (1,522 lines)
│   └── testing.py               # Crafting system tester
├── data/                        # Data layer (30 files, 5,424 LOC)
│   ├── models/                  # Pure data classes (dataclasses)
│   │   ├── materials.py         # MaterialDefinition
│   │   ├── equipment.py         # EquipmentItem
│   │   ├── skills.py            # SkillDefinition, PlayerSkill
│   │   ├── recipes.py           # Recipe, PlacementData
│   │   ├── world.py             # Position, TileType, WorldTile
│   │   ├── titles.py            # TitleDefinition
│   │   ├── classes.py           # ClassDefinition with tags
│   │   └── (+ npcs, quests, resources, skill_unlocks, unlock_conditions)
│   └── databases/               # Singleton database loaders (16 files)
│       ├── material_db.py       # MaterialDatabase
│       ├── equipment_db.py      # EquipmentDatabase
│       ├── recipe_db.py         # RecipeDatabase
│       ├── skill_db.py          # SkillDatabase
│       ├── title_db.py          # TitleDatabase
│       ├── class_db.py          # ClassDatabase
│       ├── npc_db.py            # NPCDatabase
│       ├── placement_db.py      # PlacementDatabase
│       ├── translation_db.py    # TranslationDatabase
│       ├── skill_unlock_db.py   # SkillUnlockDatabase
│       └── (+ map_waypoint_db, resource_node_db, update_loader, visual_config_db, world_generation_db)
├── entities/                    # Game entities (17 files, 7,263 LOC)
│   ├── character.py             # Character class (2,593 lines)
│   ├── status_effect.py         # Status effects (826 lines)
│   ├── status_manager.py        # Status management
│   ├── tool.py                  # Tool class
│   └── components/              # Character components
│       ├── inventory.py         # Inventory, ItemStack
│       ├── equipment_manager.py # EquipmentManager
│       ├── skill_manager.py     # SkillManager (1,124 lines)
│       ├── stat_tracker.py      # SQL-backed player analytics (1,149 lines)
│       ├── stats.py             # CharacterStats
│       ├── buffs.py             # Buff/debuff tracking
│       ├── leveling.py          # LevelingSystem
│       └── (+ activity_tracker, crafted_stats, weapon_tag_calculator)
├── systems/                     # Game system managers (21 files, 10,631 LOC)
│   ├── world_system.py          # WorldSystem (generation, chunks)
│   ├── save_manager.py          # Full state persistence (634 lines)
│   ├── title_system.py          # TitleSystem
│   ├── class_system.py          # ClassSystem with tag bonuses
│   ├── llm_item_generator.py    # LLM integration (1,392 lines)
│   ├── crafting_classifier.py   # ML classifiers (1,419 lines)
│   └── (+ biome_generator, chunk, collision_system, dungeon, encyclopedia,
│        map_waypoint_system, npc_system, quest_system, turret_system, etc.)
├── world_system/                # World Memory System (87 files, ~20,600 LOC)
│   ├── world_memory/            # Core WMS engine
│   │   ├── world_memory_system.py # Facade (449 lines)
│   │   ├── stat_store.py        # SQL-backed hierarchical stats (327 lines)
│   │   ├── event_store.py       # 20 SQL tables (1,140 lines)
│   │   ├── event_recorder.py    # Bus→SQLite bridge (481 lines)
│   │   ├── trigger_manager.py   # Threshold-based dual-track triggers (194 lines)
│   │   ├── tag_library.py       # 65-category taxonomy (559 lines)
│   │   ├── tag_assignment.py    # Layer 1→7 tag engine (410 lines)
│   │   ├── layer_store.py       # Per-layer SQL + tag junction tables (426 lines)
│   │   ├── daily_ledger.py      # Daily aggregation (277 lines)
│   │   ├── evaluators/          # 33 Layer 2 evaluators (1,700+ lines)
│   │   └── (+ geographic_registry, entity_registry, query, interpreter,
│   │        time_envelope, retention, position_sampler, tag_browser)
│   ├── living_world/            # Consumer systems (NOT part of WMS)
│   │   ├── backends/            # BackendManager — LLM abstraction (553 lines)
│   │   ├── npc/                 # NPCAgentSystem + NPCMemory (665 lines)
│   │   ├── factions/            # FactionSystem Phase 2+ (1,300+ LOC, 50 tests, prompt UI wired)
│   │   └── ecosystem/           # Tool interface for resource queries (stateless, no agent)
│   ├── config/                  # 7 JSON configs (memory, geographic, backend, etc.)
│   ├── tests/                   # 56 passing tests across 4 test files
│   └── docs/                    # WORLD_MEMORY_SYSTEM.md (canonical design doc)
├── events/                      # Event system (2 files, 198 LOC)
│   └── event_bus.py             # GameEventBus pub/sub
├── animation/                   # Animation system (7 files, 1,008 LOC)
│   └── (animation_manager, procedural, weapon_visuals, combat_particles, etc.)
├── rendering/                   # All rendering code (5 files, 8,841 LOC)
│   └── renderer.py              # Renderer class (7,931 lines)
├── Combat/                      # Combat system (11 files, 5,562 LOC)
│   ├── combat_manager.py        # CombatManager (2,317 lines)
│   ├── enemy.py                 # Enemy, EnemyDatabase (1,348 lines)
│   └── (+ attack_state_machine, hitbox_system, projectile_system,
│        attack_profile_generator, combat_data_loader, player_actions, etc.)
├── Crafting-subdisciplines/     # Crafting minigames (9 files, 8,994 LOC)
│   ├── smithing.py              # Smithing minigame (909 lines)
│   ├── alchemy.py               # Alchemy minigame (1,070 lines)
│   ├── refining.py              # Refining minigame (826 lines)
│   ├── engineering.py           # Engineering minigame (1,312 lines)
│   ├── enchanting.py            # Enchanting minigame (1,408 lines)
│   ├── fishing.py               # Fishing minigame (872 lines)
│   └── crafting_simulator.py    # Crafting simulation (2,337 lines)
├── tests/                       # Test suite (24 files, 6,594 LOC)
├── tools/                       # Dev utilities (10 files — grid designers, icon audit, etc.)
├── save_system/                 # Save system docs + create_default_save.py
└── docs/                        # Technical documentation
    ├── GAME_MECHANICS_V6.md     # MASTER REFERENCE (5,154 lines)
    ├── REPOSITORY_STATUS_REPORT_2026-01-27.md # Current status
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
- `Character` - Player entity with stats, inventory, equipment, skills (2,593 lines)
- `CombatManager` - Full damage pipeline, enchantments, status effects (2,317 lines)
- `SkillManager` - Skill activation, mana, cooldowns, affinity bonuses (1,124 lines)
- `WorldSystem` - 100x100 tiles, chunk-based generation
- `Renderer` - All drawing logic (7,931 lines)
- `GameEngine` - Main loop, event handling, UI (10,809 lines)
- `LLMItemGenerator` - Claude API integration for invented items
- `CraftingClassifierManager` - CNN/LightGBM validation
- `WorldMemorySystem` - 7-layer event tracking facade (world_system/)
- `FactionSystem` - NPC/player affinity tracking + hierarchy (world_system/living_world/factions/) — **Phase 2+ complete**
- `StatTracker` - SQL-backed player analytics (65 record methods)
- `GameEventBus` - Pub/sub event system (events/event_bus.py)
- `BackendManager` - LLM abstraction layer (Ollama/Claude/Mock)

### Design Patterns

1. **Singleton Databases**: All data loaded once at startup via `get_instance()`
2. **Component Pattern**: Character composed of pluggable components
3. **Dataclasses**: Heavy use of `@dataclass` for data structures
4. **Tag-Driven Effects**: Combat, skills, and items use composable tag system
5. **JSON-Driven Content**: All items, recipes, materials, skills defined in JSON
6. **Background Threading**: LLM generation runs async to avoid UI freeze
7. **Pub/Sub Events**: GameEventBus decouples systems; WorldMemorySystem subscribes to ~60 event types

---

## Crafting System

### Difficulty Calculator
Material-based difficulty scaling (core/difficulty_calculator.py):

**Point System** (Linear):
- T1 = 1 point, T2 = 2 points, T3 = 3 points, T4 = 4 points per item

**Difficulty Tiers**:
| Tier | Points | Distribution |
|------|--------|--------------|
| Common | 0-4 | ~20% |
| Uncommon | 5-10 | ~25% |
| Rare | 11-20 | ~30% |
| Epic | 21-40 | ~20% |
| Legendary | 41+ | ~5% |

**Discipline-Specific Modifiers**:
- Smithing: base_points only
- Refining: base × diversity × station_tier (1.5x-4.5x)
- Alchemy: base × diversity × tier_modifier × volatility
- Engineering: base × diversity × slot_modifier
- Enchanting: base × diversity

### Reward Calculator
Performance-based rewards (core/reward_calculator.py):

**Quality Tiers** (by performance 0.0-1.0):
| Score | Quality |
|-------|---------|
| 0-25% | Normal |
| 25-50% | Fine |
| 50-75% | Superior |
| 75-90% | Masterwork |
| 90-100% | Legendary |

---

## Tag System (Major Feature)

The tag-driven effect system is the core combat mechanic. All effects are defined through composable tags:

### Tag Categories

**Damage Types**: `physical`, `fire`, `ice`, `lightning`, `poison`, `arcane`, `shadow`, `holy`

**Geometry Tags**: `single`, `chain`, `cone`, `circle`, `beam`, `pierce`

**Status Effects**: `burn`, `bleed`, `poison`, `freeze`, `chill`, `stun`, `root`, `shock`

**Special Behaviors**: `knockback`, `pull`, `lifesteal`, `execute`, `critical`, `reflect`

### Tag Flow
```
JSON Definition → Database → Equipment/Skills → Effect Executor → Game World
```

### Example: Fire Skill
```json
{
  "skillId": "fireball",
  "tags": ["fire", "circle", "burn"],
  "effectParams": {
    "baseDamage": 50,
    "circle_radius": 3.0,
    "burn_duration": 5.0,
    "burn_damage_per_second": 8.0
  }
}
```

**Documentation**: See `docs/tag-system/TAG-GUIDE.md` for comprehensive tag reference.

---

## Combat System

### Damage Pipeline
```
Base Damage (weapon)
  × Hand Type Bonus (+10-20%)
  × Strength Multiplier (1.0 + STR × 0.05)
  × Skill Buff Bonus (+50% to +400%)
  × Class Affinity Bonus (up to +20%)
  × Title Bonus
  × Weapon Tag Bonuses
  × Critical Hit (2x if triggered)
  - Enemy Defense (max 75% reduction)
  = Final Damage
```

### Enchantment Effects (14 Implemented - January 2026)
| Enchantment | Type | Trigger | Status |
|-------------|------|---------|--------|
| Sharpness I-III | damage_multiplier | Passive | ✅ Working |
| Protection I-III | defense_multiplier | Passive | ✅ Working |
| Efficiency I-II | gathering_speed_multiplier | Passive | ✅ Working |
| Fortune I-II | bonus_yield_chance | Passive | ✅ Working |
| Unbreaking I-II | durability_multiplier | Passive | ✅ Working |
| Fire Aspect | damage_over_time | On hit | ✅ Working |
| Poison | damage_over_time | On hit | ✅ Working |
| Swiftness | movement_speed_multiplier | Equip | ✅ Working |
| Thorns | reflect_damage | On hit received | ✅ Working |
| Knockback | knockback | On hit | ✅ Working |
| Lifesteal | lifesteal | On hit | ✅ Working |
| Health Regen | health_regeneration | Periodic | ✅ Working |
| Frost Touch | slow | On hit | ✅ Working |
| Chain Damage | chain_damage | On hit | ✅ Working |

**Deferred** (3 types - by design):
- Self-Repair, Weightless, Silk Touch

### Status Effects (All Implemented)
- **DoT**: Burn, Bleed, Poison, Shock (damage per second)
- **CC**: Freeze, Stun, Root, Slow/Chill (movement/action prevention)
- **Buffs**: Empower, Fortify, Haste, Regeneration, Shield
- **Debuffs**: Vulnerable, Weaken
- **Special**: Phase/Ethereal, Invisible

---

## File Organization

```
Game-1-modular/
├── items.JSON/                  # Item definitions
│   ├── items-materials-1.JSON   # 57 raw materials
│   ├── items-smithing-2.JSON    # Weapons, armor
│   ├── items-alchemy-1.JSON     # Potions, consumables
│   ├── items-refining-1.JSON    # Ingots, planks
│   ├── items-engineering-1.JSON # Devices
│   └── items-tools-1.JSON       # Placeable tools
├── recipes.JSON/                # Crafting recipes
│   ├── recipes-smithing-3.json  # Most current smithing
│   ├── recipes-alchemy-1.JSON   # Alchemy recipes
│   ├── recipes-refining-1.JSON  # Material processing
│   ├── recipes-engineering-1.JSON
│   ├── recipes-enchanting-1.JSON
│   └── recipes-adornments-1.json # Enchantments
├── placements.JSON/             # Grid layouts for minigames
├── progression/                 # Character progression
│   ├── classes-1.JSON           # 6 classes with tags
│   ├── titles-1.JSON            # 40+ titles
│   └── npcs-1.JSON              # NPC definitions
├── Skills/                      # Skill definitions
│   └── skills-skills-1.JSON     # 100+ skills
└── Definitions.JSON/            # System definitions
    ├── tag-definitions.JSON     # All tag definitions
    ├── hostiles-1.JSON          # Enemy definitions
    ├── stats-calculations.JSON  # Stat formulas
    └── crafting-stations-1.JSON # Station definitions
```

---

## Key Design Principles

### 1. Hardcode vs JSON Philosophy
- **Hardcode**: System mechanics (HOW things work)
- **JSON**: All content, values, balance numbers

### 2. Stats System (6 Core Stats)
All stats start at 0, gain 1 point per level (max 30):
- **STR**: +5% mining/melee damage, +10 inventory slots
- **DEF**: +2% damage reduction, +3% armor effectiveness
- **VIT**: +15 max HP, +1% health regen
- **LCK**: +2% crit chance, +2% resource quality, +3% rare drops
- **AGI**: +5% forestry damage, +3% attack speed
- **INT**: -2% minigame difficulty (smithing, refining, alchemy, engineering), +20 mana, +5% elemental damage

### 3. Multiplicative Scaling
```
Final Value = Base × (1 + Stat Bonuses) × (1 + Title Bonuses) × (1 + Equipment Bonuses) × (1 + Class Affinity)
```

### 4. Tier System
- **T1**: Common materials (oak, iron, limestone)
- **T2**: Uncommon (ash, steel, marble)
- **T3**: Rare (ironwood, mithril, obsidian)
- **T4**: Legendary (voidsteel, dragonsteel, voidstone)

Tier multipliers: T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x

### 5. No Breaking (Durability)
- 100% durability = 100% effectiveness
- 0% durability = 50% effectiveness forever
- Items never destroyed, only degraded

---

## Known Issues & Current Work

**See**: `MASTER_ISSUE_TRACKER.md` for comprehensive bug list
**See**: `docs/REPOSITORY_STATUS_REPORT_2026-01-27.md` for full status

### Recently Resolved (January 2026)
- ✅ Inventory click misalignment - spacing synchronized
- ✅ All 14 enchantments now working (Lifesteal, Knockback, Chain Damage, Health Regen, Frost Touch)
- ✅ Unused imports (`Path`, `copy`) removed from crafting files
- ✅ `import random` in enchanting.py - uses inline imports (functional)

### Code Quality Notes
- Duplicate singleton pattern across 10 database files (acceptable technical debt)
- Duplicate methods across 5 crafting minigame files (could be refactored)

### Not Yet Implemented (Despite Documentation)
- Block/Parry combat mechanics
- Summon mechanics
- Advanced skill evolution chains

### Open Issues
- Tooltip z-order (can be covered by equipment menu)
- Missing crafting station definitions (Tier 3/4)
- Missing station icons (forge_t4.png, enchanting_table_t2.png)

---

## Debugging Tips

### Enable Debug Mode
Press **F1** in-game to toggle debug mode:
- Infinite resources
- Debug info overlays

Additional debug keys:
- **F2**: Auto-learn all skills
- **F3**: Grant all titles
- **F4**: Max level + stats
- **F7**: Infinite durability

### Check Database Loading
```python
mat_db = MaterialDatabase.get_instance()
print(f"Loaded {len(mat_db.materials)} materials")

skill_db = SkillDatabase.get_instance()
print(f"Loaded {len(skill_db.skills)} skills")
```

### Tag System Debugging
```python
from core.tag_debug import get_tag_debugger
debugger = get_tag_debugger()
debugger.enable()
# ... your code ...
debugger.disable()
```

### LLM Debug Logs
Check `llm_debug_logs/` for full API request/response logs

---

## Quick Command Reference

### Run Game
```bash
cd Game-1-modular
python main.py
```

### Run Tests
```bash
cd Game-1-modular
python -m pytest tests/ -v
```

### Check JSON Validity
```bash
python -m json.tool recipes.JSON/recipes-smithing-3.json > /dev/null
```

---

## Common Development Tasks

### Adding a New Recipe

1. Choose discipline and locate file:
   - Smithing: `recipes.JSON/recipes-smithing-3.json`
   - Alchemy: `recipes.JSON/recipes-alchemy-1.JSON`

2. Add recipe object with required fields:
```json
{
  "recipeId": "smithing_iron_sword_001",
  "outputId": "iron_sword",
  "outputQty": 1,
  "stationType": "smithing",
  "stationTier": 1,
  "inputs": [
    {"materialId": "iron_ingot", "qty": 3}
  ]
}
```

3. Game auto-loads on restart

### Adding a New Material

1. Add to `items.JSON/items-materials-1.JSON`:
```json
{
  "materialId": "mythril_ore",
  "name": "Mythril Ore",
  "tier": 3,
  "category": "ore",
  "rarity": "rare"
}
```

2. Add resource node to `Definitions.JSON/Resource-node-1.JSON` if gatherable

### Adding a Skill with Tags

1. Add to `Skills/skills-skills-1.JSON`:
```json
{
  "skillId": "flame_strike",
  "name": "Flame Strike",
  "tags": ["fire", "melee", "single", "burn"],
  "effectParams": {
    "baseDamage": 75,
    "burn_duration": 5.0,
    "burn_damage_per_second": 10.0
  },
  "manaCost": "moderate",
  "cooldown": "short"
}
```

---

## Visual Overhaul Design Standards (March 2026)

**MANDATORY**: These principles govern all visual/animation/combat-visual work. Read before writing any code.

### The Prime Directive

> **"The code layer implements the rules. The data layer defines the world. The rules never change. The world grows without limits."**

### DO NOT TOUCH (Sacred Boundaries)

1. **No content JSON modifications** — All `items.JSON/`, `recipes.JSON/`, `placements.JSON/`, `Skills/`, `Definitions.JSON/`, `progression/`, `hostiles-*.JSON` files are OFF LIMITS. These define game content and must remain unchanged.
2. **No new content tags** — The existing tag system defines game behavior. Visual work does not add tags to `tag-definitions.JSON` or any content schema.
3. **No icon/asset PNGs** — The `assets/` folder contains game icons (inventory, items, UI). These are NOT animation sprites. Do not modify, replace, or rename them.
4. **No formula changes** — The damage pipeline, EXP curve, stat scaling, tier multipliers, and all balance constants are immutable:
   ```
   Damage: base × hand(1.1-1.2) × STR(1+STR×0.05) × skill × class(max 1.2) × crit(2x) - def(max 75%)
   EXP:    200 × 1.75^(level-1), max level 30
   Tiers:  T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x
   ```
5. **No restructuring existing systems** — `combat_manager.py`, `effect_executor.py`, `skill_manager.py`, crafting minigames — extend via new modules, don't rewrite.

### ALLOWED (Visual Overhaul Scope)

1. **New configuration JSONs** — Animation configs, VFX configs, hitbox definitions, visual timing data. These are *system configuration*, not game content.
2. **New Python modules** — `animation/`, `events/`, and new files within `Combat/` for visual systems.
3. **Sprite overhaul** — Entity/world sprites (NOT icon PNGs in `assets/`) can be replaced, enhanced, or supplemented with new animation sprite assets.
4. **Procedural animation from static sprites** — Rotation, scaling, tinting, flashing, particle generation from existing sprites.
5. **Minimal integration hooks** — Small additions to existing code (event publications, component attachments) to connect visual systems.

### Architecture Standards for Visual Systems

1. **Configuration-Driven**: All visual parameters (frame counts, timings, colors, hitbox shapes, particle configs) live in configuration JSON files, not hardcoded in Python.
2. **Tag-Aware Rendering**: Visual effects should READ existing tags to determine presentation. A `"fire"` tag on a skill implies fire VFX. A `"circle"` geometry tag implies radial effects. No per-skill hardcoding.
3. **Decoupled via Events**: Visual systems subscribe to game events (`DAMAGE_DEALT`, `SKILL_ACTIVATED`, `ENEMY_KILLED`). They do not import or call game logic systems directly.
4. **Component-Based Entities**: Animation/visual state attaches to entities as components. Systems check `hasattr(entity, 'animation_component')` and degrade gracefully.
5. **Singleton Pattern for Visual Data**: Animation databases, VFX registries follow the same `get_instance()` pattern as all other databases.
6. **Centralized Visual Manager**: A single manager (like stats/class systems) coordinates animation state, VFX dispatch, and rendering pipeline integration.

### Naming Conventions (Visual Systems)

- Config files: `animation-config.json`, `vfx-config.json`, `hitbox-config.json`
- New modules: `animation/animation_manager.py`, `animation/sprite_animator.py`
- Classes: `AnimationManager`, `HitboxSystem`, `ProjectileRenderer`
- Methods: `play_animation()`, `spawn_particles()`, `check_hitbox()`
- JSON keys: `camelCase` (`frameCount`, `swingArc`, `particleColor`)

### What BalanceValidator Is (Context)

BalanceValidator is **designed but NOT implemented**. It exists only as a spec in `Development-Plan/SHARED_INFRASTRUCTURE.md` (lines 7-56). It was planned to gate AI-generated content with tier-based stat range checks. No Python code exists for it. **Do not reference it as if it works. Do not build against it. It is a future TODO.**

### JSON File Count Clarification

The ~90 JSON game-definition files are spread across `items.JSON/`, `recipes.JSON/`, `placements.JSON/`, `Skills/`, `Definitions.JSON/`, `progression/`, `Update-*/`, and `world_system/config/`. Save/chunk files and ML training logs are excluded from this count and are gitignored.

---

## When Working on This Project

### For Python Development (bug fixes, features):
- Check `GAME_MECHANICS_V6.md` for implementation status before assuming features exist
- Check `REPOSITORY_STATUS_REPORT_2026-01-27.md` for current system state
- Reference `NAMING_CONVENTIONS.md` for method names
- Use singleton pattern for databases
- Follow tag system conventions for new combat effects
- Test JSON changes by restarting the game
- Check `llm_debug_logs/` when debugging LLM issues

### For Living World / Combat Overhaul Work:
- **Start with** `Development-Plan/OVERVIEW.md` — roadmap and dependency graph
- **Read** the relevant Part document before implementing any phase
- **Read** `world_system/docs/HANDOFF_STATUS.md` for current WMS implementation state
- **Use** `GameEventBus` for all new inter-system communication
- **Use** `BackendManager` (world_system/living_world/backends/) for all LLM inference (never call APIs directly)
- **All timing, hitboxes, attack patterns in configuration JSON** — consistent with project philosophy
- **Preserve** all game constants exactly (damage pipeline, EXP curve, tier multipliers)
- **New visual modules** go in `animation/`, `Combat/`, `events/`
- **New world/AI modules** go in `world_system/` (world_memory/ for WMS, living_world/ for consumers)
- **Existing code** modified minimally — add event publishing, don't restructure

### DON'T:
- Assume design docs describe implemented features
- Modify any content JSON (items, recipes, skills, hostiles, placements, tags)
- Modify icon PNGs in `assets/` folder
- Hardcode visual parameters that should be in configuration JSON
- Skip checking tag documentation for combat/skill work
- Change any game formula, constant, or balance number
- Modify existing combat_manager.py logic — extend via new modules
- Reference BalanceValidator as if it exists in code (it doesn't yet — spec only in Development-Plan/SHARED_INFRASTRUCTURE.md)

---

## Documentation Index

### Migration Plan (in `archive/Migration-Plan/`)
| Document | Purpose |
|----------|---------|
| **COMPLETION_STATUS.md** | Central hub — start here for migration |
| **MIGRATION_PLAN.md** | Master overview (1,229 lines) |
| **IMPROVEMENTS.md** | All architecture improvements (1,424 lines) |
| **CONVENTIONS.md** | Living conventions for C# code (709 lines) |
| **PHASE_CONTRACTS.md** | Phase inputs/outputs with C# types (641 lines) |
| **phases/PHASE_1-7** | Detailed per-phase instructions (9,197 lines total) |
| **reference/UNITY_PRIMER.md** | Unity crash course (679 lines) |
| **reference/PYTHON_TO_CSHARP.md** | Type mappings and conversions (902 lines) |

### Python Source Documentation (in `Game-1-modular/`)
| Document | Purpose |
|----------|---------|
| **GAME_MECHANICS_V6.md** | Master reference - all mechanics (5,154 lines) |
| **REPOSITORY_STATUS_REPORT_2026-01-27.md** | Current system state |
| **MASTER_ISSUE_TRACKER.md** | Known bugs and improvements |
| **docs/tag-system/TAG-GUIDE.md** | Comprehensive tag system guide |
| **docs/ARCHITECTURE.md** | System architecture overview |
| **NAMING_CONVENTIONS.md** | API naming standards |
| **Fewshot_llm/README.md** | LLM system documentation |
| **Fewshot_llm/MANUAL_TUNING_GUIDE.md** | LLM prompt editing guide |

### World Memory System Documentation (in `Game-1-modular/world_system/docs/`)
| Document | Purpose |
|----------|---------|
| **WORLD_MEMORY_SYSTEM.md** | Single source of truth — 1,864 lines covering all 16 design sections |
| **HANDOFF_STATUS.md** | Implementation state as of 2026-03-28 |
| **TAG_LIBRARY.md** | 65-category tag taxonomy across 7 layers |
| **FOUNDATION_IMPLEMENTATION_PLAN.md** | Layer 1-2 build plan (mostly executed) |

---

## Version History

- **v7.0** (March 29, 2026): Major accuracy update. Fixed all file/LOC counts against actual codebase (239 files, ~96,400 LOC). Added World Memory System (14,269 LOC, 71 files). Fixed directory layout (Migration-Plan moved to archive/, Python/ is not a symlink). Corrected ai/ → world_system/living_world/, combat/ → Combat/. Removed stale "BackendManager doesn't exist" warning. Added StatTracker, GameEventBus, fishing discipline. Updated all individual file line counts.
- **v6.0** (March 8, 2026): Added Visual Overhaul Design Standards section. Clarified sacred boundaries (no content JSON, no icon PNGs, no formula changes). Corrected BalanceValidator status (designed, not implemented). Fixed JSON file count (60 game-definition files, not 398).
- **v5.0** (March 6, 2026): Strategic pivot to Python/Pygame active development. Added Living World + Combat Overhaul development plan. Unity migration paused indefinitely.
- **v4.0** (February 11, 2026): Added Unity/C# migration plan context (16,013 lines, 15 documents), updated stats, migration guidelines
- **v3.0** (January 27, 2026): Major update for LLM integration, crafting classifiers, invented items system
- **v2.0** (December 31, 2025): Major update for modular architecture, tag system, full combat, skills, save/load
- **v1.0** (November 17, 2025): Initial Claude.md creation (monolithic main.py)

---

**Last Updated**: 2026-03-29
**For**: AI assistants and developers working on Game-1 (Python/Pygame active development)
**Maintained By**: Project developers
