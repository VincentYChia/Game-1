# Game-1 Master Migration Plan
## Python/Pygame to Unity/C# Migration

**Version**: 1.0
**Created**: 2026-02-10
**Status**: Active
**Scope**: Complete migration of Game-1 from Python/Pygame to Unity/C#

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Statistics](#2-project-statistics)
3. [Repository Organization](#3-repository-organization)
4. [Migration Phases Overview](#4-migration-phases-overview)
5. [Phase Details](#5-phase-details)
6. [Critical Preservation Requirements](#6-critical-preservation-requirements)
7. [Database Initialization Order](#7-database-initialization-order)
8. [Character Component Initialization Order](#8-character-component-initialization-order)
9. [Validation Strategy Summary](#9-validation-strategy-summary)
10. [Risk Register](#10-risk-register)
11. [Document Index](#11-document-index)

---

## 1. Executive Summary

### 1.1 Project Overview

Game-1 is a production-ready crafting RPG built with Python and Pygame. Over four months
of development (October 2025 to present), the project has grown to 215 Python files and
approximately 75,911 lines of code. It features a 100x100 tile world, six crafting
disciplines with unique minigames, ML-powered recipe validation (CNN + LightGBM),
LLM-powered procedural item generation, a full tag-driven combat system, and deep
character progression.

The Python/Pygame prototype has successfully validated all core gameplay mechanics.
This migration moves the proven game logic into Unity/C# to enable professional-grade
rendering, better performance, platform portability, and industry-standard tooling.

### 1.2 Migration Goals

| Priority | Goal | Rationale |
|----------|------|-----------|
| **P0** | Preserve all game mechanics exactly | Years of balancing and tuning in Python must not be lost. Every formula, constant, threshold, and behavior must transfer 1:1. |
| **P1** | Improve code architecture | The monolithic GameEngine (10,098 lines) will be decomposed. Duplicate singleton patterns will be consolidated. Dependency injection will replace manual wiring. |
| **P2** | Enable comprehensive testing | Every system must be independently unit-testable. Comparison tests between Python and C# outputs will validate the migration. Golden file tests will verify ML accuracy. |
| **P3** | Adopt Unity patterns and idioms | MonoBehaviours for scene objects, ScriptableObjects for data, Unity Input System for controls, UI Toolkit for interfaces. Do not fight Unity -- embrace it. |
| **P4** | Maintain moddability | All JSON-driven content must remain human-editable. StreamingAssets for moddable content, Resources for built-in data. |

### 1.3 Non-Goals (This Migration)

| Non-Goal | Rationale |
|----------|-----------|
| Full LLM integration | Stub interface only. The Claude API integration will be verified architecturally but not reimplemented. Real LLM calls are deferred to a future phase. |
| 3D rendering | The architecture will be 3D-ready, but visual assets and full 3D rendering are out of scope. The migration focuses on logic parity, not visual fidelity. |
| Multiplayer | Single-player focus. No networking, no shared state, no server architecture. |
| Platform-specific optimizations | Desktop-first. Mobile, console, and web builds are future work. |
| Content expansion | No new items, skills, enemies, or mechanics. The migration ports what exists. |

---

## 2. Project Statistics

### 2.1 Codebase Metrics

| Metric | Value |
|--------|-------|
| **Python files** | 215 |
| **Total lines of code** | ~75,911 (Python) |
| **JSON configuration files** | 398+ (292 in Game-1-modular, 159 in Scaled JSON Development) |
| **Asset files** | 3,749 (sprites, icons, sounds, images) |
| **Crafting disciplines** | 6 (Smithing, Alchemy, Refining, Engineering, Enchanting, Fishing) |
| **Combat tags** | 190+ composable tags |
| **ML models** | 5 (2 CNN, 3 LightGBM) |
| **Skills** | 100+ skill definitions |
| **Materials** | 57+ material definitions |
| **Titles** | 40+ achievement titles |
| **Character classes** | 6 starting classes with tag-driven bonuses |
| **Enemies** | 50+ enemy definitions |
| **Enchantments** | 14 implemented, 3 deferred by design |
| **Status effects** | 18 types (DoT, CC, Buffs, Debuffs, Special) |
| **Recipes** | 100+ across all disciplines plus invented recipes |

### 2.2 File Size Distribution (Largest Files)

| File | Lines | Migration Notes |
|------|-------|-----------------|
| `core/game_engine.py` | 10,098 | **Decompose** into 8-12 Unity MonoBehaviours/Services |
| `rendering/renderer.py` | 6,936 | **Rebuild** entirely in Unity rendering pipeline |
| `entities/character.py` | 2,576 | Port with component decomposition |
| `Combat/combat_manager.py` | 2,009 | Direct port, preserve all formulas |
| `entities/components/stat_tracker.py` | 1,721 | Direct port |
| `core/minigame_effects.py` | 1,522 | Rebuild with Unity particle system |
| `systems/crafting_classifier.py` | 1,419 | Port preprocessing, convert models to ONNX |
| `Crafting-subdisciplines/enchanting.py` | 1,408 | Port logic, rebuild UI |
| `systems/llm_item_generator.py` | 1,392 | **Stub only** -- interface + placeholder |
| `Crafting-subdisciplines/engineering.py` | 1,312 | Port logic, rebuild UI |
| `core/interactive_crafting.py` | 1,179 | Port logic, rebuild UI |
| `systems/world_system.py` | 1,110 | Port logic, integrate with Unity Tilemap |
| `Crafting-subdisciplines/alchemy.py` | 1,070 | Port logic, rebuild UI |
| `entities/components/skill_manager.py` | 971 | Direct port |

### 2.3 System Size Summary

| System | Files | Lines | Migration Approach |
|--------|-------|-------|--------------------|
| Core engine | 22 | ~18,500 | Decompose + port logic |
| Data models | 13 | ~2,000 | Direct port to C# classes |
| Database singletons | 15 | ~3,156 | Port pattern, consider ScriptableObjects |
| Entity layer | 17 | ~7,566 | Port with component pattern |
| Game systems | 21 | ~10,542 | Port logic, Unity integration |
| Combat | 3 | ~2,984 | Direct port, exact formula preservation |
| Crafting minigames | 8 | ~6,397 | Port logic, rebuild rendering |
| Rendering | 3 | ~7,000+ | Full rebuild in Unity |
| Save system | 1 | ~634 | Port, maintain JSON format |
| ML/LLM | 2 | ~2,811 | Convert models, stub LLM |

---

## 3. Repository Organization

The migration repository is organized into four top-level directories, each serving a
distinct purpose:

```
Game-1/
├── Migration-Plan/          # This plan and all migration documents
│   ├── MIGRATION_PLAN.md    # THIS FILE - central hub for the migration
│   ├── MIGRATION_META_PLAN.md  # Methodology and planning philosophy
│   ├── phases/              # Per-phase detailed migration guides
│   ├── specifications/      # System-level technical specifications
│   ├── reference/           # Language mapping, constants, API guides
│   └── testing/             # Test strategy, test cases, golden files
│
├── Python/                  # Pointer to Game-1-modular (read-only reference)
│   └── README.md            # Points to ../Game-1-modular/
│
├── Unity/                   # Target Unity project (empty until Phase 1)
│   └── README.md            # Planned project structure
│
├── archive/                 # Historical documentation and prior work
│   ├── Game-1-singular/     # Original monolithic main.py
│   ├── batch-notes/         # Development batch notes
│   ├── bug-reports/         # Historical bug reports
│   ├── cleanup-*/           # Prior cleanup efforts
│   └── ...                  # Other historical documents
│
├── Game-1-modular/          # ACTIVE Python source (the code being migrated)
│   ├── main.py              # Entry point
│   ├── core/                # Core systems (22 files)
│   ├── data/                # Data layer (28 files)
│   ├── entities/            # Entity layer (17 files)
│   ├── systems/             # Game systems (21 files)
│   ├── Combat/              # Combat system (3 files)
│   ├── Crafting-subdisciplines/  # Crafting minigames (8 files)
│   ├── rendering/           # Pygame rendering (3 files)
│   ├── save_system/         # Save/load system
│   ├── items.JSON/          # Item definition files
│   ├── recipes.JSON/        # Recipe definition files
│   ├── Skills/              # Skill definition files
│   ├── Definitions.JSON/    # System definitions
│   ├── progression/         # Character progression data
│   ├── placements.JSON/     # Crafting grid layouts
│   └── docs/                # Technical documentation
│
├── Scaled JSON Development/ # ML training data, models, and tools
│   ├── Convolution Neural Network (CNN)/
│   ├── Simple Classifiers (LightGBM)/
│   ├── LLM Training Data/
│   └── models/              # Trained model files
│
└── docs/                    # Project-level documentation
    └── GAME_MECHANICS_V6.md # Master mechanics reference (5,089 lines)
```

### 3.1 Directory Purposes

**Migration-Plan/** -- The authoritative source for all migration decisions,
specifications, and tracking. Every phase document, specification, and test plan lives
here. This is the directory you are reading from now.

**Python/** -- A symbolic pointer to `Game-1-modular/`. During migration, Python source
is treated as **read-only reference**. No modifications should be made to Python files
unless fixing a bug that affects golden file generation for validation.

**Unity/** -- The target Unity project. Currently empty (contains only a README
describing the planned structure). The Unity project will be initialized when Phase 1
begins. All new C# code goes here.

**archive/** -- Historical documentation from earlier development phases. Includes the
original monolithic `main.py`, early bug reports, cleanup notes, and prior planning
documents. Preserved for historical reference but not actively used during migration.

---

## 4. Migration Phases Overview

### 4.1 Phase Summary

| Phase | Name | Description | Dependencies | Parallelizable |
|-------|------|-------------|--------------|----------------|
| **1** | Foundation | Data Models, Enums, JSON Schemas | None | -- |
| **2** | Data Layer | Database Singletons, Config Loading | Phase 1 | -- |
| **3** | Entity Layer | Character, Components, Status Effects | Phase 2 | -- |
| **4** | Game Systems | Combat, Crafting Logic, World, Tags, Effects | Phase 3 | -- |
| **5** | ML Classifiers | CNN to ONNX to Sentis, LightGBM to ONNX to Sentis | Phase 1 | Yes, with Phase 4 |
| **6** | Unity Integration | Rendering, Input, UI, Scene Setup | Phase 4 + 5 | -- |
| **7** | Polish and LLM Stub | Stub interface, Debug notifications, E2E testing | Phase 6 | -- |

### 4.2 Dependency Diagram

```
Phase 1: Foundation (Data Models, Enums, JSON Schemas)
    |                                          \
    |                                           \
    v                                            v
Phase 2: Data Layer                   Phase 5: ML Classifiers
(Database Singletons,                 (CNN -> ONNX -> Sentis,
 Config Loading)                       LightGBM -> ONNX -> Sentis)
    |                                            |
    v                                            |
Phase 3: Entity Layer                            |
(Character, Components,                          |
 Status Effects)                                 |
    |                                            |
    v                                            |
Phase 4: Game Systems                            |
(Combat, Crafting Logic,                         |
 World, Tags, Effects)                           |
    |                                            |
    +--------------------------------------------+
    |
    v
Phase 6: Unity Integration
(Rendering, Input, UI,
 Scene Setup)
    |
    v
Phase 7: Polish & LLM Stub
(Stub interface, Debug notifications,
 E2E testing, Save/Load verification)
```

### 4.3 Critical Path

The critical path runs through Phases 1 -> 2 -> 3 -> 4 -> 6 -> 7. Phase 5 (ML
Classifiers) can proceed in parallel with Phases 2 through 4, as it only depends on the
Foundation data models from Phase 1. This parallel track is the primary opportunity to
accelerate the migration timeline.

---

## 5. Phase Details

### 5.1 Phase 1: Foundation

**Goal**: Establish all data types, enumerations, and JSON schema definitions in C#.

**Python Sources**:
| File | Lines | C# Target |
|------|-------|-----------|
| `data/models/materials.py` | 24 | `Game1.Data.Models.MaterialDefinition` |
| `data/models/equipment.py` | 360 | `Game1.Data.Models.EquipmentItem` |
| `data/models/skills.py` | 135 | `Game1.Data.Models.SkillDefinition` |
| `data/models/recipes.py` | 52 | `Game1.Data.Models.Recipe` |
| `data/models/world.py` | 526 | `Game1.Data.Models.WorldTile`, `Position`, `TileType` |
| `data/models/titles.py` | 27 | `Game1.Data.Models.TitleDefinition` |
| `data/models/classes.py` | 46 | `Game1.Data.Models.ClassDefinition` |
| `data/models/resources.py` | 77 | `Game1.Data.Models.ResourceNode` |
| `data/models/skill_unlocks.py` | 182 | `Game1.Data.Models.SkillUnlock` |
| `data/models/unlock_conditions.py` | 481 | `Game1.Data.Models.UnlockCondition` |
| `data/models/npcs.py` | 17 | `Game1.Data.Models.NPCDefinition` |
| `data/models/quests.py` | 46 | `Game1.Data.Models.QuestDefinition` |
| `core/config.py` | -- | `Game1.Core.GameConfig` |

**Deliverables**:
- All C# data model classes (matching Python dataclasses)
- All enumerations (replacing Python string constants)
- JSON schema documentation for every data file
- JSON deserialization tests for all 398+ JSON files
- 100% unit test coverage on all data models

**Quality Gate**:
- [ ] All data models compile without errors
- [ ] All enums defined with correct values
- [ ] JSON loading works for every data file in the project
- [ ] Round-trip serialization tests pass (load -> save -> load -> compare)

### 5.2 Phase 2: Data Layer

**Goal**: Port all database singletons and configuration loading infrastructure.

**Depends on**: Phase 1 (all data models must exist)

**Python Sources**:
| File | Lines | C# Target |
|------|-------|-----------|
| `data/databases/resource_node_db.py` | 257 | `Game1.Data.Databases.ResourceNodeDatabase` |
| `data/databases/material_db.py` | 202 | `Game1.Data.Databases.MaterialDatabase` |
| `data/databases/equipment_db.py` | 400 | `Game1.Data.Databases.EquipmentDatabase` |
| `data/databases/skill_db.py` | 122 | `Game1.Data.Databases.SkillDatabase` |
| `data/databases/recipe_db.py` | 211 | `Game1.Data.Databases.RecipeDatabase` |
| `data/databases/title_db.py` | 175 | `Game1.Data.Databases.TitleDatabase` |
| `data/databases/class_db.py` | 108 | `Game1.Data.Databases.ClassDatabase` |
| `data/databases/npc_db.py` | 146 | `Game1.Data.Databases.NPCDatabase` |
| `data/databases/placement_db.py` | 216 | `Game1.Data.Databases.PlacementDatabase` |
| `data/databases/skill_unlock_db.py` | 137 | `Game1.Data.Databases.SkillUnlockDatabase` |
| `data/databases/translation_db.py` | 52 | `Game1.Data.Databases.TranslationDatabase` |
| `data/databases/world_generation_db.py` | 440 | `Game1.Data.Databases.WorldGenerationDatabase` |
| `data/databases/map_waypoint_db.py` | 300 | `Game1.Data.Databases.MapWaypointDatabase` |
| `data/databases/update_loader.py` | 363 | `Game1.Data.Databases.UpdateLoader` |
| `core/tag_system.py` | 192 | `Game1.Core.Tags.TagRegistry` |

**Deliverables**:
- All database singleton classes with `get_instance()` pattern or DI equivalent
- Tag registry with all 190+ tag definitions loaded
- Config loading from JSON files
- Query methods matching Python API exactly
- Comparison tests against Python query results

**Quality Gate**:
- [ ] All databases load without errors
- [ ] Query methods return correct data for sample queries
- [ ] Tag registry contains all 190+ tags
- [ ] Initialization order preserved (see Section 7)
- [ ] Comparison tests against Python pass

### 5.3 Phase 3: Entity Layer

**Goal**: Port the Character entity, all components, and the status effect system.

**Depends on**: Phase 2 (databases must be loadable for component initialization)

**Python Sources**:
| File | Lines | C# Target |
|------|-------|-----------|
| `entities/character.py` | 2,576 | `Game1.Entities.Character` |
| `entities/components/stats.py` | 89 | `Game1.Entities.Components.CharacterStats` |
| `entities/components/stat_tracker.py` | 1,721 | `Game1.Entities.Components.StatTracker` |
| `entities/components/leveling.py` | 26 | `Game1.Entities.Components.LevelingSystem` |
| `entities/components/skill_manager.py` | 971 | `Game1.Entities.Components.SkillManager` |
| `entities/components/buffs.py` | 156 | `Game1.Entities.Components.BuffManager` |
| `entities/components/equipment_manager.py` | 171 | `Game1.Entities.Components.EquipmentManager` |
| `entities/components/inventory.py` | 231 | `Game1.Entities.Components.Inventory` |
| `entities/components/crafted_stats.py` | 295 | `Game1.Entities.Components.CraftedStats` |
| `entities/components/activity_tracker.py` | 16 | `Game1.Entities.Components.ActivityTracker` |
| `entities/components/weapon_tag_calculator.py` | 173 | `Game1.Entities.Components.WeaponTagCalculator` |
| `entities/status_effect.py` | 826 | `Game1.Entities.StatusEffect` |
| `entities/status_manager.py` | 294 | `Game1.Entities.StatusManager` |
| `entities/tool.py` | -- | `Game1.Entities.Tool` |
| `entities/damage_number.py` | -- | `Game1.Entities.DamageNumber` |
| `Combat/enemy.py` | 975 | `Game1.Entities.Enemy`, `EnemyDatabase` |

**Deliverables**:
- Character class with all components initialized in correct order
- Full status effect system (18 effect types)
- Enemy entity with all stats and behaviors
- Inventory operations (add, remove, swap, stack)
- Equipment operations (equip, unequip, durability)
- Save/load round-trip for character state

**Quality Gate**:
- [ ] Character can be created with all components
- [ ] Component initialization order preserved (see Section 8)
- [ ] Inventory operations produce identical results to Python
- [ ] Equipment operations produce identical results to Python
- [ ] Status effects tick and expire correctly
- [ ] Save -> Load -> Compare produces identical state

### 5.4 Phase 4: Game Systems

**Goal**: Port combat, crafting logic, world generation, tag parsing, and effect
execution -- all core gameplay systems.

**Depends on**: Phase 3 (entities must exist for systems to operate on)

**Python Sources**:
| File | Lines | C# Target |
|------|-------|-----------|
| `Combat/combat_manager.py` | 2,009 | `Game1.Systems.Combat.CombatManager` |
| `core/effect_executor.py` | 623 | `Game1.Systems.Combat.EffectExecutor` |
| `core/tag_parser.py` | 191 | `Game1.Core.Tags.TagParser` |
| `core/crafting_tag_processor.py` | -- | `Game1.Systems.Crafting.CraftingTagProcessor` |
| `core/difficulty_calculator.py` | 808 | `Game1.Systems.Crafting.DifficultyCalculator` |
| `core/reward_calculator.py` | 607 | `Game1.Systems.Crafting.RewardCalculator` |
| `core/interactive_crafting.py` | 1,179 | `Game1.Systems.Crafting.CraftingManager` |
| `Crafting-subdisciplines/smithing.py` | 909 | `Game1.Systems.Crafting.Disciplines.Smithing` |
| `Crafting-subdisciplines/alchemy.py` | 1,070 | `Game1.Systems.Crafting.Disciplines.Alchemy` |
| `Crafting-subdisciplines/refining.py` | 826 | `Game1.Systems.Crafting.Disciplines.Refining` |
| `Crafting-subdisciplines/engineering.py` | 1,312 | `Game1.Systems.Crafting.Disciplines.Engineering` |
| `Crafting-subdisciplines/enchanting.py` | 1,408 | `Game1.Systems.Crafting.Disciplines.Enchanting` |
| `Crafting-subdisciplines/fishing.py` | 872 | `Game1.Systems.Crafting.Disciplines.Fishing` |
| `systems/world_system.py` | 1,110 | `Game1.Systems.World.WorldSystem` |
| `systems/biome_generator.py` | 596 | `Game1.Systems.World.BiomeGenerator` |
| `systems/chunk.py` | 558 | `Game1.Systems.World.ChunkSystem` |
| `systems/collision_system.py` | 599 | `Game1.Systems.World.CollisionSystem` |
| `systems/save_manager.py` | 634 | `Game1.Systems.Save.SaveManager` |
| `systems/title_system.py` | 86 | `Game1.Systems.Progression.TitleSystem` |
| `systems/class_system.py` | 69 | `Game1.Systems.Progression.ClassSystem` |
| `systems/potion_system.py` | 386 | `Game1.Systems.Items.PotionSystem` |
| `systems/quest_system.py` | 292 | `Game1.Systems.Quests.QuestSystem` |
| `systems/npc_system.py` | 48 | `Game1.Systems.NPCs.NPCSystem` |
| `systems/attack_effects.py` | 233 | `Game1.Systems.Combat.AttackEffects` |
| `systems/skill_unlock_system.py` | 205 | `Game1.Systems.Progression.SkillUnlockSystem` |
| `systems/training_dummy.py` | 298 | `Game1.Systems.Combat.TrainingDummy` |
| `systems/turret_system.py` | 551 | `Game1.Systems.Combat.TurretSystem` |
| `systems/dungeon.py` | 805 | `Game1.Systems.World.DungeonSystem` |
| `systems/encyclopedia.py` | 332 | `Game1.Systems.UI.Encyclopedia` |
| `systems/natural_resource.py` | 191 | `Game1.Systems.World.NaturalResource` |
| `systems/map_waypoint_system.py` | 716 | `Game1.Systems.World.MapWaypointSystem` |

**Deliverables**:
- Complete combat damage pipeline matching Python exactly
- All 14 enchantment effects working
- All 18 status effects working
- Tag parser and effect executor handling all 190+ tags
- Difficulty calculator with exact tier thresholds
- Reward calculator with exact quality tier mapping
- Crafting logic for all 6 disciplines (logic only, not UI)
- World generation producing deterministic results
- Save/load system preserving complete game state

**Quality Gate**:
- [ ] Combat damage calculations match Python output (tolerance: +/-0.01)
- [ ] All tag effects execute with correct behavior
- [ ] Difficulty tiers map identically to Python
- [ ] Quality tiers map identically to Python
- [ ] World generation with same seed produces same result
- [ ] Full save/load round-trip preserves all state

### 5.5 Phase 5: ML Classifiers (Parallel Track)

**Goal**: Convert all 5 ML models to ONNX format and run inference via Unity Sentis.
Port all preprocessing code to C# with exact numerical parity.

**Depends on**: Phase 1 only (data models for material definitions)
**Parallel with**: Phases 2, 3, and 4

**Models to Convert**:

| Model | Type | Python Format | Input Shape | Output | Conversion Path |
|-------|------|---------------|-------------|--------|-----------------|
| Smithing | CNN | Keras/TF | 36x36x3 RGB | Valid/Invalid + confidence | Keras -> ONNX -> Sentis |
| Adornments | CNN | Keras/TF | 56x56x3 RGB | Valid/Invalid + confidence | Keras -> ONNX -> Sentis |
| Alchemy | LightGBM | .txt model | 34 float features | Valid/Invalid + confidence | LightGBM -> ONNX -> Sentis |
| Refining | LightGBM | .txt model | 18 float features | Valid/Invalid + confidence | LightGBM -> ONNX -> Sentis |
| Engineering | LightGBM | .txt model | 28 float features | Valid/Invalid + confidence | LightGBM -> ONNX -> Sentis |

**Preprocessing Requirements (CRITICAL -- must match Python exactly)**:

CNN image generation:
- HSV color encoding: metal=210, wood=30, stone=0, monster_drop=300, gem=280
- Tier value mapping: T1=0.50, T2=0.65, T3=0.80, T4=0.95
- Canvas sizes: Smithing 9x9 -> 36x36, Adornments 14x14 -> 56x56
- Normalization: pixel values in [0, 1]

LightGBM feature extraction:
- Category order MUST match training data exactly
- Feature order within each category MUST match exactly
- Floating-point feature values MUST match within tolerance

**Deliverables**:
- 5 ONNX model files validated with onnx.checker
- C# preprocessing pipeline for each model
- Golden file test suite (generated from Python outputs)
- Inference wrapper using Unity Sentis
- Performance benchmarks (target: <100ms per prediction)

**Quality Gate**:
- [ ] All 5 models load successfully in Unity Sentis
- [ ] Preprocessing output matches Python golden files (tolerance: 0.001)
- [ ] Predictions match Python golden files (tolerance: 0.01 confidence)
- [ ] Inference completes within 100ms per prediction
- [ ] No memory leaks during repeated inference

### 5.6 Phase 6: Unity Integration

**Goal**: Wire all ported systems into Unity MonoBehaviours, implement rendering,
input handling, and UI. Decompose the monolithic GameEngine.

**Depends on**: Phase 4 + Phase 5 (all logic and ML systems must be ported)

**GameEngine Decomposition Plan** (10,098 lines -> multiple components):

| GameEngine Responsibility | Unity Component | Estimated Lines |
|---------------------------|-----------------|-----------------|
| Main loop and state machine | `GameManager.cs` (MonoBehaviour) | 400-600 |
| Input handling | `InputManager.cs` (Unity Input System) | 200-400 |
| Camera and viewport | `CameraController.cs` (MonoBehaviour) | 150-300 |
| World rendering | `WorldRenderer.cs` (MonoBehaviour) | 500-800 |
| UI management | `UIManager.cs` (UI Toolkit) | 600-1,000 |
| Crafting UI | `CraftingUIController.cs` | 400-600 |
| Combat UI | `CombatUIController.cs` | 300-500 |
| Inventory UI | `InventoryUIController.cs` | 300-500 |
| Minigame rendering | Per-discipline MonoBehaviours | 200-400 each |
| Debug overlays | `DebugOverlay.cs` | 200-300 |

**Additional Unity-Specific Work**:
| Component | Purpose |
|-----------|---------|
| `Renderer.py` (6,936 lines) | Full rebuild using Unity SpriteRenderer, Tilemap |
| `minigame_effects.py` (1,522 lines) | Rebuild using Unity Particle System |
| Scene setup | Main scene, crafting scene, combat scene |
| Asset pipeline | Import all 3,749 sprites and icons |
| Audio system | Placeholder audio manager |

**Deliverables**:
- Functional Unity project with main game loop
- All UI screens (inventory, equipment, crafting, combat, world map)
- Input handling via Unity Input System
- World rendered via Unity Tilemap
- Particle effects for minigames
- Debug mode (F1-F7 keys preserved)

**Quality Gate**:
- [ ] Game boots without errors
- [ ] Core loop functional: move, gather, craft, equip, fight
- [ ] All UI screens display correct information
- [ ] Debug keys (F1-F7) work as in Python version
- [ ] No rendering artifacts or missing sprites
- [ ] Frame rate acceptable (>30 FPS at minimum)

### 5.7 Phase 7: Polish and LLM Stub

**Goal**: Implement the LLM stub interface, add debug notifications for unimplemented
features, run full end-to-end testing, and verify save compatibility.

**Depends on**: Phase 6 (full game must be runnable)

**LLM Stub Requirements**:
- `IItemGenerator` interface defined with `GenerateItemAsync()`
- `StubItemGenerator` implementation returns placeholder items
- Debug notification displayed on screen when stub is invoked
- Placeholder items have valid structure (can be inventoried, equipped, saved)
- Architecture ready for real LLM implementation in future

**End-to-End Test Scenarios**:
1. New game -> create character -> select class -> enter world
2. Gather resources -> open crafting -> select recipe -> complete minigame
3. Equip crafted item -> find enemy -> engage combat -> defeat enemy
4. Level up -> allocate stats -> learn new skill -> use skill in combat
5. Save game -> quit -> reload -> verify all state preserved
6. Trigger invented item flow -> verify stub notification -> verify placeholder item

**Deliverables**:
- LLM stub interface and implementation
- Debug notification system for all stubs
- Full E2E test suite covering core game loop
- Save format compatibility verification
- Performance profiling report
- Migration completion report

**Quality Gate**:
- [ ] LLM stub is callable and returns valid placeholder items
- [ ] Debug notifications appear for all stub invocations
- [ ] All 6 E2E scenarios pass
- [ ] Save files from C# can be loaded and state matches
- [ ] No P0 or P1 bugs remaining
- [ ] Performance meets minimum targets

---

## 6. Critical Preservation Requirements

These values, formulas, and behaviors MUST be preserved exactly during migration.
Any deviation is a migration bug.

### 6.1 Damage Pipeline

The complete damage calculation must produce identical results:

```
Final Damage = floor(
    Base Damage (from weapon)
    * Hand Type Bonus       (+10% one-hand, +20% two-hand)
    * STR Multiplier        (1.0 + STR * 0.05)
    * Skill Buff Bonus      (+50% to +400% depending on skill)
    * Class Affinity Bonus  (up to +20%)
    * Title Bonus           (varies by title)
    * Weapon Tag Bonuses    (composable from tags)
    * Critical Hit          (2x if triggered)
    - Enemy Defense         (max 75% reduction)
)
```

### 6.2 Stat Formulas

All six core stats start at 0 and gain 1 point per level (max level 30):

| Stat | Effect per Point | Formula |
|------|------------------|---------|
| **STR** | +5% mining/melee damage, +10 inventory capacity | `damage * (1 + STR * 0.05)` |
| **DEF** | +2% damage reduction, +3% armor effectiveness | `reduction = min(DEF * 0.02, 0.75)` |
| **VIT** | +15 max HP, +1% health regen rate | `max_hp = base_hp + VIT * 15` |
| **LCK** | +2% crit chance, +2% resource quality, +3% rare drops | `crit = 0.05 + LCK * 0.02` |
| **AGI** | +5% forestry damage, +3% attack speed | `speed = base * (1 + AGI * 0.03)` |
| **INT** | -2% minigame difficulty, +20 mana, +5% elemental damage | `mana = base_mana + INT * 20` |

### 6.3 EXP Curve

```
EXP required for level N = floor(200 * 1.75^(level - 1))
```

| Level | EXP Required | Cumulative |
|-------|-------------|------------|
| 1 | 200 | 200 |
| 2 | 350 | 550 |
| 5 | 1,876 | 4,856 |
| 10 | 29,802 | 78,190 |
| 15 | 473,469 | -- |
| 20 | 7,518,602 | -- |
| 30 | 1,895,147,941 | -- |

### 6.4 Difficulty Tiers

Material-based difficulty uses a linear point system:

**Point Values**: T1 = 1 point, T2 = 2 points, T3 = 3 points, T4 = 4 points per item

| Tier | Point Range | Expected Distribution |
|------|-------------|----------------------|
| **Common** | 0-4 | ~20% |
| **Uncommon** | 5-10 | ~25% |
| **Rare** | 11-20 | ~30% |
| **Epic** | 21-40 | ~20% |
| **Legendary** | 41+ | ~5% |

**Discipline-Specific Modifiers**:

| Discipline | Formula |
|------------|---------|
| Smithing | `base_points` (no modifier) |
| Refining | `base_points * diversity * station_tier` (1.5x-4.5x range) |
| Alchemy | `base_points * diversity * tier_modifier * volatility` |
| Engineering | `base_points * diversity * slot_modifier` |
| Enchanting | `base_points * diversity` |

### 6.5 Quality Tiers

Performance-based quality assignment (performance score 0.0 to 1.0):

| Score Range | Quality | Color |
|-------------|---------|-------|
| 0.00 - 0.25 | Normal | White |
| 0.25 - 0.50 | Fine | Green |
| 0.50 - 0.75 | Superior | Blue |
| 0.75 - 0.90 | Masterwork | Purple |
| 0.90 - 1.00 | Legendary | Gold |

### 6.6 Tier Multipliers

| Tier | Multiplier | Materials |
|------|-----------|-----------|
| **T1** | 1.0x | Common (oak, iron, limestone) |
| **T2** | 2.0x | Uncommon (ash, steel, marble) |
| **T3** | 4.0x | Rare (ironwood, mithril, obsidian) |
| **T4** | 8.0x | Legendary (voidsteel, dragonsteel, voidstone) |

### 6.7 Durability System

```
Effectiveness = 0.50 + (durability_percent * 0.50)
```

- 100% durability = 100% effectiveness
- 50% durability = 75% effectiveness
- 0% durability = 50% effectiveness
- Items are **never destroyed**, only degraded
- Minimum effectiveness is always 50%

### 6.8 Defense Cap

```
Maximum damage reduction = 75%
defense_reduction = min(total_defense_rating, 0.75)
```

### 6.9 Critical Hit

```
Base crit chance = 5%
Per-point bonus = LCK * 2%
Total crit chance = 0.05 + (LCK * 0.02)
Crit damage multiplier = 2.0x
```

### 6.10 Multiplicative Scaling Pattern

All bonuses stack multiplicatively (not additively):

```
Final Value = Base
    * (1 + Stat Bonuses)
    * (1 + Title Bonuses)
    * (1 + Equipment Bonuses)
    * (1 + Class Affinity)
```

### 6.11 ML Preprocessing Constants

**CNN Color Encoding (HSV)**:

| Category | Hue | Shape |
|----------|-----|-------|
| metal | 210 (Blue) | 4x4 solid |
| wood | 30 (Orange) | 4x4 cross |
| stone | 0 (Red) | 4x4 diamond |
| monster_drop | 300 (Magenta) | 4x4 circle |
| gem | 280 (Purple) | 4x4 star |

**CNN Tier Value Mapping**:

| Tier | Value | Fill Pattern |
|------|-------|-------------|
| T1 | 0.50 | 1x1 center |
| T2 | 0.65 | 2x2 center |
| T3 | 0.80 | 3x3 center |
| T4 | 0.95 | 4x4 full |

**LightGBM Feature Extraction Order** (alphabetical by category -- CRITICAL):

```
Alchemy (34 features):
  For each category in ["elemental", "metal", "monster_drop", "stone", "wood"]:
    count, average_tier, max_tier, min_tier, tier_variance, ...
  Global features: total_count, unique_categories, tier_spread, ...

Refining (18 features):
  [exact order must match Python training data]

Engineering (28 features):
  [exact order must match Python training data]
```

---

## 7. Database Initialization Order

The following initialization order MUST be preserved. Later databases query earlier ones
during their initialization. Violating this order will cause null references or incorrect
data.

```
1. ResourceNodeDB     -- No dependencies. Defines what can be gathered.
2. MaterialDB         -- References resource nodes for gathering sources.
3. EquipmentDB        -- References materials for crafting requirements.
4. SkillDB            -- References equipment types for skill applicability.
5. RecipeDB           -- References materials and equipment for recipe definitions.
6. TitleDB            -- References skills and equipment for unlock conditions.
7. ClassDB            -- References skills for class affinity bonuses.
8. NPCDB              -- References all of the above for NPC inventories/quests.
```

**Source**: `Game-1-modular/core/game_engine.py`, lines 106-147

**C# Implementation Notes**:
- Consider a `DatabaseBootstrapper` class that enforces this order
- Each database should have an `IsInitialized` flag
- Late initialization (lazy loading) is NOT safe -- all databases must be fully
  loaded before gameplay begins
- Consider using a dependency injection container to manage initialization order

---

## 8. Character Component Initialization Order

Character components must be initialized in this specific order because later
components query earlier ones during setup.

```
1. Stats          -- Base stat values (STR, DEF, VIT, LCK, AGI, INT)
2. Leveling       -- Level, EXP, stat point allocation (reads Stats)
3. Skills         -- Learned skills, cooldowns, affinities (reads Stats, Leveling)
4. Buffs          -- Active buffs and debuffs (reads Stats)
5. Equipment      -- Equipped items, durability (reads Stats, Skills)
6. Inventory      -- Item storage, capacity (reads Stats for capacity bonus)
7. Titles         -- Earned titles, active title (reads Skills, Equipment)
8. Class          -- Selected class, affinity bonuses (reads Skills, Titles)
9. Activities     -- Activity tracking and cooldowns (reads all above)
```

**Source**: `Game-1-modular/entities/character.py`, lines 93-127

**C# Implementation Notes**:
- Consider a `CharacterBuilder` that enforces this order
- Components should declare their dependencies explicitly
- Circular dependencies are NOT allowed between components
- The `StatTracker` (1,721 lines) aggregates bonuses from Equipment, Buffs,
  Titles, and Class -- it must run after those components initialize

---

## 9. Validation Strategy Summary

### 9.1 Testing Pyramid

```
                        /\
                       /  \
                      / E2E\           Few: Full game scenarios (6+)
                     /------\
                    /        \
                   /Integration\       Some: System interactions (50+)
                  /--------------\
                 /                \
                /   Unit Tests     \   Many: Individual functions (200+)
               /--------------------\
```

### 9.2 Test Coverage Targets

| System | Minimum Tests | Coverage Target | Test Type |
|--------|---------------|-----------------|-----------|
| Data Models | 20+ | 100% | Unit |
| Tag System | 50+ | 100% | Unit |
| Combat Formulas | 30+ | 100% | Unit + Comparison |
| Difficulty Calculator | 20+ | 100% | Unit + Comparison |
| Reward Calculator | 15+ | 100% | Unit + Comparison |
| ML Preprocessing | 40+ | 100% | Unit + Golden File |
| ML Inference | 25+ | 95%+ | Golden File |
| Crafting Logic | 25+ per discipline | 90%+ | Unit + Integration |
| Character Components | 30+ | 95%+ | Unit |
| Save/Load | 15+ | 100% | Round-trip |

### 9.3 Golden File Testing (ML Systems)

Golden files are pre-computed outputs from the Python system used as ground truth:

1. **Generation**: Run Python preprocessing and inference on a curated set of test
   inputs. Export all intermediate values (images, feature vectors, predictions).
2. **Storage**: Golden files stored in `Migration-Plan/testing/golden-files/`
3. **C# Tests**: Load same inputs, run C# preprocessing and inference, compare
   outputs against golden files with defined tolerances.
4. **Tolerances**: Image pixels +/-0.001, feature values +/-0.0001,
   confidence scores +/-0.01

### 9.4 Comparison Testing (Python vs C#)

During migration, both systems run on identical inputs and outputs are compared:

```
Test Input ──> Python System ──> Python Output ──┐
                                                  ├──> Compare ──> Pass/Fail
Test Input ──> C# System    ──> C# Output    ──┘
```

Comparison tests are written for:
- Damage calculations (all scenarios)
- Stat calculations (all 6 stats at various levels)
- Difficulty scoring (all disciplines)
- Quality tier assignment (boundary cases)
- EXP curve values (levels 1-30)
- Durability effectiveness (0%, 25%, 50%, 75%, 100%)

### 9.5 Structured Logging with Conditional Compilation

All migration validation logging uses `[Conditional("MIGRATION_VALIDATION")]`
attributes. This means:

- **During migration**: Build with `MIGRATION_VALIDATION` defined. All validation
  logs are active, structured as JSON, filterable by system tag.
- **After migration**: Remove the define from build settings. All validation
  code compiles to nothing. Zero runtime overhead. Zero binary size impact.
- **Test assemblies**: Always have validation enabled regardless of build settings.

---

## 10. Risk Register

### 10.1 High-Priority Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R1 | **Monolithic GameEngine decomposition** introduces regressions | High | High | Decompose incrementally. Each extracted component gets its own test suite. Run E2E tests after each extraction. Keep Python version runnable for comparison. |
| R2 | **ML model conversion** produces different predictions | Medium | High | Golden file testing with strict tolerances. Test every preprocessing step independently. Validate ONNX models before importing to Sentis. Maintain Python fallback. |
| R3 | **Tag system completeness** -- missing tag handlers in C# | Medium | High | Exhaustive enumeration of all 190+ tags before migration starts. Automated test that every registered tag has a handler. Cross-reference with Python tag registry. |
| R4 | **Save format compatibility** breaks between Python and C# | Medium | Medium | Define JSON schema explicitly. Write bidirectional compatibility tests. Version the save format. Keep Python save/load as reference implementation. |
| R5 | **Floating-point divergence** between Python and C# | High | Medium | Use `double` where Python uses `float` for critical calculations. Document all rounding points. Comparison tests with appropriate tolerances. Never compare floats with exact equality. |

### 10.2 Medium-Priority Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R6 | **Unity Sentis** does not support all ONNX ops used by models | Low | High | Verify op compatibility early in Phase 5. Have fallback plan: custom inference for LightGBM (tree traversal is simple), ONNX Runtime as alternative to Sentis. |
| R7 | **JSON loading performance** with 398+ files | Medium | Low | Profile early. Consider bundling related JSONs. Use streaming deserialization for large files. Cache parsed data. |
| R8 | **Scope creep** -- temptation to improve during migration | High | Medium | Strict adherence to P0 (preserve mechanics). All improvements tracked separately. No "while we are in here" changes to formulas or balance. |
| R9 | **Missing Python test coverage** means no baseline to compare | Medium | Medium | Generate golden files from Python before starting C# work. Instrument Python code to capture intermediate values. Document expected behavior manually where tests do not exist. |
| R10 | **Circular dependencies** discovered during migration | Medium | Medium | Map all dependencies before starting. Use interfaces to break cycles. Dependency injection container to manage initialization. |

### 10.3 Low-Priority Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R11 | **Asset pipeline** issues with 3,749 files | Low | Low | Batch import scripts. Verify atlas/sprite sheet generation. Automated checks for missing references. |
| R12 | **Third-party package** compatibility issues | Low | Low | Pin all Unity package versions. Test on target Unity LTS version. Document all package dependencies. |

---

## 11. Document Index

### 11.1 Migration Plan Documents

| Document | Location | Status | Purpose |
|----------|----------|--------|---------|
| **MIGRATION_PLAN.md** | `Migration-Plan/MIGRATION_PLAN.md` | Active | This file -- central hub |
| **MIGRATION_META_PLAN.md** | `Migration-Plan/MIGRATION_META_PLAN.md` | Complete | Planning methodology |

### 11.2 Phase Documents

| Document | Location | Status | Purpose |
|----------|----------|--------|---------|
| PHASE_1_FOUNDATION.md | `Migration-Plan/phases/` | Planned | Data models, enums, JSON schemas |
| PHASE_2_DATA_LAYER.md | `Migration-Plan/phases/` | Planned | Database singletons, config loading |
| PHASE_3_ENTITY_LAYER.md | `Migration-Plan/phases/` | Planned | Character, components, status effects |
| PHASE_4_GAME_SYSTEMS.md | `Migration-Plan/phases/` | Planned | Combat, crafting, world, tags, effects |
| PHASE_5_ML_CLASSIFIERS.md | `Migration-Plan/phases/` | Planned | CNN/LightGBM to ONNX to Sentis |
| PHASE_6_UNITY_INTEGRATION.md | `Migration-Plan/phases/` | Planned | Rendering, input, UI, scene setup |
| PHASE_7_POLISH_LLM_STUB.md | `Migration-Plan/phases/` | Planned | LLM stub, E2E testing, polish |

### 11.3 Specification Documents

| Document | Location | Status | Purpose |
|----------|----------|--------|---------|
| SPEC_DATA_LAYER.md | `Migration-Plan/specifications/` | Planned | All data structures and schemas |
| SPEC_TAG_SYSTEM.md | `Migration-Plan/specifications/` | Planned | Tag definitions, behaviors, handlers |
| SPEC_COMBAT.md | `Migration-Plan/specifications/` | Planned | Damage formulas, enchantments, status effects |
| SPEC_CRAFTING.md | `Migration-Plan/specifications/` | Planned | All 6 disciplines, difficulty, rewards |
| SPEC_ML_CLASSIFIERS.md | `Migration-Plan/specifications/` | Planned | Model details, preprocessing, conversion |
| SPEC_LLM_STUB.md | `Migration-Plan/specifications/` | Planned | Interface design, stub behavior |

### 11.4 Testing Documents

| Document | Location | Status | Purpose |
|----------|----------|--------|---------|
| TEST_STRATEGY.md | `Migration-Plan/testing/` | Planned | Overall testing approach and infrastructure |
| TEST_CASES_COMBAT.md | `Migration-Plan/testing/` | Planned | Combat system test cases |
| TEST_CASES_CRAFTING.md | `Migration-Plan/testing/` | Planned | Crafting system test cases |
| GOLDEN_FILES.md | `Migration-Plan/testing/` | Planned | Golden file inventory and generation scripts |

### 11.5 Reference Documents

| Document | Location | Status | Purpose |
|----------|----------|--------|---------|
| PYTHON_TO_CSHARP.md | `Migration-Plan/reference/` | Planned | Language pattern mapping guide |
| PYGAME_TO_UNITY.md | `Migration-Plan/reference/` | Planned | API and pattern mapping guide |
| CONSTANTS_REFERENCE.md | `Migration-Plan/reference/` | Planned | All numeric constants and magic numbers |

### 11.6 Source Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| GAME_MECHANICS_V6.md | `Game-1-modular/docs/` | Master mechanics reference (5,089 lines) |
| REPOSITORY_STATUS_REPORT_2026-01-27.md | `Game-1-modular/docs/` | Current system state assessment |
| CLAUDE.md | `.claude/CLAUDE.md` | Developer guide and quick reference |
| TAG-GUIDE.md | `Game-1-modular/docs/tag-system/` | Comprehensive tag system documentation |
| NAMING_CONVENTIONS.md | `Game-1-modular/` | API naming standards |

---

## Appendix A: Unity Target Project Structure

```
Unity/
├── Assets/
│   ├── Scripts/
│   │   ├── Game1.Core/
│   │   │   ├── GameManager.cs              # Main game loop (MonoBehaviour)
│   │   │   ├── GameConfig.cs               # Configuration constants
│   │   │   ├── MigrationLogger.cs          # Structured logging
│   │   │   └── ServiceLocator.cs           # DI container
│   │   ├── Game1.Data/
│   │   │   ├── Models/                     # All data model classes
│   │   │   │   ├── MaterialDefinition.cs
│   │   │   │   ├── EquipmentItem.cs
│   │   │   │   ├── SkillDefinition.cs
│   │   │   │   ├── Recipe.cs
│   │   │   │   ├── WorldTile.cs
│   │   │   │   └── ...
│   │   │   ├── Databases/                  # Singleton database loaders
│   │   │   │   ├── DatabaseBootstrapper.cs # Enforces init order
│   │   │   │   ├── MaterialDatabase.cs
│   │   │   │   ├── EquipmentDatabase.cs
│   │   │   │   └── ...
│   │   │   └── Enums/                      # All enumerations
│   │   │       ├── DamageType.cs
│   │   │       ├── CraftingDiscipline.cs
│   │   │       ├── MaterialCategory.cs
│   │   │       └── ...
│   │   ├── Game1.Entities/
│   │   │   ├── Character/
│   │   │   │   ├── Character.cs
│   │   │   │   └── CharacterBuilder.cs     # Enforces component init order
│   │   │   ├── Components/
│   │   │   │   ├── CharacterStats.cs
│   │   │   │   ├── StatTracker.cs
│   │   │   │   ├── LevelingSystem.cs
│   │   │   │   ├── SkillManager.cs
│   │   │   │   ├── BuffManager.cs
│   │   │   │   ├── EquipmentManager.cs
│   │   │   │   ├── Inventory.cs
│   │   │   │   └── ...
│   │   │   ├── StatusEffects/
│   │   │   │   ├── StatusEffect.cs
│   │   │   │   └── StatusManager.cs
│   │   │   └── Enemies/
│   │   │       ├── Enemy.cs
│   │   │       └── EnemyDatabase.cs
│   │   ├── Game1.Systems/
│   │   │   ├── Combat/
│   │   │   │   ├── CombatManager.cs
│   │   │   │   ├── EffectExecutor.cs
│   │   │   │   ├── AttackEffects.cs
│   │   │   │   └── DamageCalculator.cs
│   │   │   ├── Crafting/
│   │   │   │   ├── CraftingManager.cs
│   │   │   │   ├── DifficultyCalculator.cs
│   │   │   │   ├── RewardCalculator.cs
│   │   │   │   └── Disciplines/
│   │   │   │       ├── Smithing.cs
│   │   │   │       ├── Alchemy.cs
│   │   │   │       ├── Refining.cs
│   │   │   │       ├── Engineering.cs
│   │   │   │       ├── Enchanting.cs
│   │   │   │       └── Fishing.cs
│   │   │   ├── Tags/
│   │   │   │   ├── TagRegistry.cs
│   │   │   │   ├── TagParser.cs
│   │   │   │   └── CraftingTagProcessor.cs
│   │   │   ├── World/
│   │   │   │   ├── WorldSystem.cs
│   │   │   │   ├── BiomeGenerator.cs
│   │   │   │   ├── ChunkSystem.cs
│   │   │   │   └── CollisionSystem.cs
│   │   │   ├── ML/
│   │   │   │   ├── ClassifierManager.cs
│   │   │   │   ├── SmithingPreprocessor.cs
│   │   │   │   ├── AlchemyFeatureExtractor.cs
│   │   │   │   └── SentisInferenceWorker.cs
│   │   │   ├── LLM/
│   │   │   │   ├── IItemGenerator.cs
│   │   │   │   └── StubItemGenerator.cs
│   │   │   ├── Save/
│   │   │   │   └── SaveManager.cs
│   │   │   └── Progression/
│   │   │       ├── TitleSystem.cs
│   │   │       ├── ClassSystem.cs
│   │   │       └── SkillUnlockSystem.cs
│   │   └── Game1.UI/
│   │       ├── UIManager.cs
│   │       ├── NotificationSystem.cs
│   │       ├── InventoryUI.cs
│   │       ├── EquipmentUI.cs
│   │       ├── CraftingUI.cs
│   │       ├── CombatUI.cs
│   │       └── DebugOverlay.cs
│   ├── Resources/
│   │   ├── JSON/                           # All game data JSONs
│   │   └── Models/                         # ONNX model files
│   ├── Tests/
│   │   ├── EditMode/                       # Unit tests (no scene)
│   │   │   ├── DataModelTests.cs
│   │   │   ├── CombatFormulaTests.cs
│   │   │   ├── DifficultyCalculatorTests.cs
│   │   │   ├── TagSystemTests.cs
│   │   │   └── MLPreprocessingTests.cs
│   │   └── PlayMode/                       # Integration tests (with scene)
│   │       ├── CraftingFlowTests.cs
│   │       ├── CombatFlowTests.cs
│   │       └── SaveLoadTests.cs
│   └── StreamingAssets/
│       └── Content/                        # Moddable JSON content
├── Packages/
│   └── manifest.json                       # Unity Sentis, Test Framework, etc.
└── ProjectSettings/
```

---

## Appendix B: Key Decisions Log

| Decision | Rationale | Date |
|----------|-----------|------|
| Stub LLM instead of porting | Reduces scope, API integration is a separate concern | 2026-02-09 |
| ONNX + Sentis for ML | Unity-native, no external dependencies, GPU acceleration | 2026-02-09 |
| JSON format preserved | Backward compatibility with Python saves, moddability | 2026-02-09 |
| Phase 5 parallel with 2-4 | ML models only depend on data models, not entities/systems | 2026-02-09 |
| Decompose GameEngine | 10,098-line monolith is unmaintainable, must be split | 2026-02-09 |
| `[Conditional]` for validation | Zero-cost in release builds, no manual cleanup needed | 2026-02-09 |
| Golden file testing for ML | Only reliable way to verify preprocessing parity | 2026-02-09 |
| Multiplicative not additive scaling | Preserves existing balance, documented in Python | 2026-02-09 |

---

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| **Golden File** | Pre-computed output from Python used as ground truth for C# comparison tests |
| **Sentis** | Unity's built-in ML inference engine (supports ONNX models) |
| **ONNX** | Open Neural Network Exchange -- portable ML model format |
| **Tag** | A composable label that drives game effects (e.g., "fire", "chain", "lifesteal") |
| **Discipline** | A crafting category with its own minigame (Smithing, Alchemy, etc.) |
| **Tier** | Material quality level (T1 Common through T4 Legendary) |
| **Quality** | Crafted item quality based on minigame performance (Normal through Legendary) |
| **Stub** | A placeholder implementation that satisfies the interface but defers real logic |
| **MonoBehaviour** | Unity's base class for components attached to GameObjects |
| **ScriptableObject** | Unity's data container class, useful for shared configuration |
| **StreamingAssets** | Unity folder for files accessible at runtime (supports modding) |
| **Edit Mode Tests** | Unity tests that run without a scene (pure logic, fast) |
| **Play Mode Tests** | Unity tests that run with a scene (integration, slower) |

---

**Document Status**: Active
**Next Steps**: Begin creating Phase 1 detailed specification
**Owner**: Migration Team
**Last Updated**: 2026-02-10
