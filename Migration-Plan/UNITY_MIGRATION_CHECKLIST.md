# Unity Migration Checklist — Master Hub

**Version**: 2.0 (Restructured)
**Date**: 2026-02-19
**Scope**: Every gap between current Unity/C# codebase and a fully operational **3D** game
**Methodology**: 7-domain audit of 133 C# files (31,623 LOC) cross-referenced against Python source (75,911 LOC), Migration Plan (16,013 lines), and 3,749 asset images
**Goal**: Plan is "complete" when the game is **fully 3D** — every 2D aspect has at least a low-fidelity 3D counterpart (enemies as cubes, terrain with height, perspective camera, 2D overlay UI like Minecraft)

---

## How To Use This Document

This is the **hub**. It summarizes findings and points to 7 detailed domain audit documents. Do NOT try to read everything here — jump to the domain that matters to you.

### Quick Navigation

| If you need to... | Go to |
|---|---|
| Set up the Unity project from scratch | [Phase A: Make It Compile](#phase-a-make-it-compile-infrastructure--domain-1) → [`AUDIT_1`](audits/AUDIT_1_INFRASTRUCTURE.md) |
| Wire combat, movement, skills into the game loop | [Phase B: Make It Run](#phase-b-make-it-run-wiring--domains-2-3-5) → [`AUDIT_2`](audits/AUDIT_2_COMBAT_AND_MOVEMENT.md) |
| Connect crafting stations to minigames | [Phase B: Make It Run](#phase-b-make-it-run-wiring--domains-2-3-5) → [`AUDIT_3`](audits/AUDIT_3_CRAFTING_AND_MINIGAMES.md) |
| Build all UI panels (Minecraft-style 2D overlay) | [Phase C: Make It Complete](#phase-c-make-it-complete-missing-systems--domains-3-4-5) → [`AUDIT_4`](audits/AUDIT_4_UI_SYSTEMS.md) |
| Implement dungeons, map, world systems | [Phase C: Make It Complete](#phase-c-make-it-complete-missing-systems--domains-3-4-5) → [`AUDIT_5`](audits/AUDIT_5_WORLD_AND_PROGRESSION.md) |
| Know what "low-fidelity 3D" means for each system | [Phase D: Make It 3D](#phase-d-make-it-3d--domain-6) → [`AUDIT_6`](audits/AUDIT_6_3D_REQUIREMENTS.md) |
| Write or run tests | [Phase E: Make It Tested](#phase-e-make-it-tested--domain-7) → [`AUDIT_7`](audits/AUDIT_7_TESTING_STRATEGY.md) |
| See the full gap count and priority | [Master Gap Summary](#master-gap-summary) |
| Understand dependency order | [Implementation Order](#implementation-order) |

---

## Executive Summary

### Current State
The C# migration has **133 source files (31,623 LOC)**. All 7 migration phases have been written as plain C# and MonoBehaviour wrappers. Core game logic (data models, databases, entities, combat, crafting, world gen, save/load) is **ported and functional as C# classes**.

### The Problem
The Unity project **cannot actually run**. The gap between "C# files exist" and "playable 3D game in Unity Editor" is substantial. The 7-domain audit identified:

| Domain | Gaps Found | Critical | High | Medium | Low |
|---|---|---|---|---|---|
| 1. Infrastructure | 25 | 6 | 7 | 8 | 4 |
| 2. Combat & Movement | 17 | 3 | 8 | 4 | 2 |
| 3. Crafting & Minigames | 20 | 4 | 5 | 7 | 4 |
| 4. UI Systems | 27 | 2 | 10 | 10 | 5 |
| 5. World & Progression | 31 | 2 | 8 | 14 | 7 |
| 6. 3D Requirements | 15 | 0 | 6 | 7 | 2 |
| 7. Testing | 16 | 1 | 5 | 7 | 3 |
| **TOTAL** | **~151** | **18** | **49** | **57** | **27** |

### What's Done (Verified)
- **Phase 1 Foundation** (19 files): All data models, enums, GamePosition, IGameItem hierarchy
- **Phase 2 Data Layer** (10 files): All 8 database singletons with JSON loading
- **Phase 3 Entity Layer** (10 files): Character (7 components), Enemy AI, StatusEffect
- **Phase 4 Game Systems** (40 files): CombatManager, EffectExecutor, TargetFinder, TagSystem, 5 crafting minigames, DifficultyCalculator, RewardCalculator, WorldSystem, BiomeGenerator, Chunks, CollisionSystem, SaveManager, QuestSystem, PotionSystem
- **Phase 5 ML Classifiers** (10 files): 5 preprocessors, ClassifierManager, golden file scripts
- **Phase 6 Unity Integration** (45 files): 22 UI components, 9 world renderers, InputManager, CameraController, GameManager, GameStateManager
- **Phase 7 LLM Stub** (13 files): IItemGenerator, StubItemGenerator, 87+ tests

### What's NOT Done
1. **No Unity project infrastructure** — No scenes, prefabs, meta files, packages
2. **No StreamingAssets/Content** — JSON files not copied; databases load empty
3. **No sprite/asset imports** — 3,744 PNGs not in Unity Assets
4. **Combat not wired to game loop** — TODOs in GameManager.cs
5. **7 UI panels missing** — Skills Menu, several minigame UIs not created
6. **2 systems missing entirely** — Dungeon System (805 lines Python), Map/Waypoint System (716 lines Python)
7. **Fishing minigame not ported** — 872 lines Python, 0 C#
8. **No 3D geometry** — Everything is 2D Tilemap + SpriteRenderer
9. **260+ unit tests not written** — Only ML + E2E tests exist (104/364)

---

## Domain Audit Documents

Each domain was audited independently with full access to both Python source and C# code. The detailed findings, acceptance criteria, and recommendations live in these documents:

### audits/ Directory

| Document | Focus | Key Finding |
|---|---|---|
| [`audits/AUDIT_1_INFRASTRUCTURE.md`](audits/AUDIT_1_INFRASTRUCTURE.md) | Unity project setup, packages, JSON, assets, scenes, assemblies | 25 infra gaps (12 new beyond original 13). No Unity project exists. |
| [`audits/AUDIT_2_COMBAT_AND_MOVEMENT.md`](audits/AUDIT_2_COMBAT_AND_MOVEMENT.md) | Player movement, attacks, damage pipeline, enchantments, status effects, enemy AI, skills | Math 100% ported, 0% wired. No CombatInputHandler, no enemy spawning, no death system. |
| [`audits/AUDIT_3_CRAFTING_AND_MINIGAMES.md`](audits/AUDIT_3_CRAFTING_AND_MINIGAMES.md) | 6 crafting disciplines, minigames, difficulty/reward, ML classifiers, LLM | 5/6 minigames ported. Fishing missing. Station→minigame pipeline not wired. |
| [`audits/AUDIT_4_UI_SYSTEMS.md`](audits/AUDIT_4_UI_SYSTEMS.md) | All 27+ UI panels, keyboard shortcuts, canvas architecture, tooltips | 20/27 panels exist. Skills Menu missing entirely. Canvas architecture correct. |
| [`audits/AUDIT_5_WORLD_AND_PROGRESSION.md`](audits/AUDIT_5_WORLD_AND_PROGRESSION.md) | World gen, biomes, dungeons, day/night, map, leveling, stats, classes, titles, skills, save/load, NPCs, quests | 17/31 features fully implemented. Dungeon System and Map/Waypoint System completely missing. |
| [`audits/AUDIT_6_3D_REQUIREMENTS.md`](audits/AUDIT_6_3D_REQUIREMENTS.md) | Every system's 3D counterpart — terrain, entities, camera, lighting, effects | Most rendering code exists. ~44 hours for 3D MVP. "80% plumbing, 20% new." |
| [`audits/AUDIT_7_TESTING_STRATEGY.md`](audits/AUDIT_7_TESTING_STRATEGY.md) | 364+ tests across 15 systems — unit, integration, E2E, golden files | 104/364 tests exist (28%). Core system unit tests not started. |

---

## Master Gap Summary

### CRITICAL (Game Cannot Run)

| # | Gap | Domain | Detail |
|---|---|---|---|
| 1 | No Unity project structure | D1 | No ProjectSettings/, Packages/manifest.json, .csproj, .sln |
| 2 | No assembly definitions (.asmdef) | D1 | 7 namespaces have no assembly boundaries |
| 3 | No scene files (.unity) | D1 | No GameWorld or MainMenu scene |
| 4 | No .meta files | D1 | Unity cannot track any assets |
| 5 | No StreamingAssets/Content/ | D1 | All 14 databases load empty |
| 6 | No package definitions | D1 | Newtonsoft.Json, InputSystem, TMP, Sentis unresolvable |
| 7 | Combat not wired to game loop | D2 | GameManager.cs has TODOs where combat should integrate |
| 8 | Crafting station→minigame pipeline broken | D3 | CraftingUI exists but doesn't launch minigames |
| 9 | No CombatInputHandler | D2 | Click-to-attack not implemented |
| 10 | No enemy spawning integration | D2 | Enemies exist as classes but never instantiate in world |

### HIGH (Game Runs But Major Features Missing)

| # | Gap | Domain | Detail |
|---|---|---|---|
| 11 | Dungeon System missing entirely | D5 | 805 lines Python, 0 C# |
| 12 | Map/Waypoint System missing entirely | D5 | 716 lines Python, 0 C# |
| 13 | Fishing minigame not ported | D3 | 872 lines Python, 0 C# |
| 14 | Skills Menu UI missing | D4 | No skill browser/equip panel |
| 15 | Interactive crafting drag-drop missing | D3 | Material placement not functional |
| 16 | Invent button flow incomplete | D3 | Classifier→LLM→inventory pipeline broken |
| 17 | No sprite assets imported | D1 | 3,744 PNGs not in Unity |
| 18 | No ONNX model files | D1 | ML classifiers can't run |
| 19 | Death system not wired | D2 | Player/enemy death → loot → respawn not connected |
| 20 | Day/night not affecting gameplay | D5 | Logic exists, not wired to enemies/rendering |
| 21 | NPC system core logic missing | D5 | UI exists, backend not implemented |
| 22 | Resource gathering not wired | D5 | Click→tool check→harvest→inventory not connected |
| 23 | No 3D terrain mesh | D6 | Still 2D Tilemap |
| 24 | No 3D entity representation | D6 | No cubes/cylinders for enemies, NPCs, stations |
| 25 | No perspective camera | D6 | Ortho only |
| 26 | 260+ unit tests missing | D7 | Core system tests not written |

### COVERAGE GAPS (Systems in Python not adequately covered by audits)

These Python systems exist but are not explicitly audited in the domain documents above. They should be verified during implementation:

| System | Python File | Lines | Notes |
|---|---|---|---|
| Weapon Tag Calculator | `entities/components/weapon_tag_calculator.py` | ~80 | Extracts/calculates weapon effect tags for damage pipeline |
| Activity Tracker | `entities/components/activity_tracker.py` | ~120 | Tracks player activities for achievements/stats |
| Translation Database | `data/databases/translation_db.py` | ~200 | Localization layer for game text |
| Notification System | `core/notifications.py` | ~200 | Toast notifications, UI feedback overlays |
| Config System | `core/config.py` | ~150 | Game configuration constants (used everywhere) |
| Rarity System | `Crafting-subdisciplines/rarity_utils.py` | 259 | Material rarity validation and stat modifiers — partially in AUDIT_3 |
| Training Dummy | `systems/training_dummy.py` | ~100 | Combat practice entity — framework exists, not spawnable |
| Turret System | `systems/turret_system.py` | ~200 | Engineering turret placement — framework exists, not integrated |
| Update Loader | `data/databases/update_loader.py` | ~150 | Dynamic content update (may be dev-time only) |

### See individual audit documents for MEDIUM and LOW priority gaps.

---

## Implementation Order

The dependencies between domains create a natural execution sequence. This is the recommended order to go from "C# files exist" to "fully playable 3D game":

### Phase A: Make It Compile (Infrastructure) — Domain 1
**Prerequisite for everything else.**

1. Create Unity project (ProjectSettings/, Packages/manifest.json)
2. Create 8 .asmdef files with correct dependency graph
3. Copy JSON to StreamingAssets/Content/ (byte-identical)
4. Create GameWorld.unity and MainMenu.unity scenes
5. Populate scene GameObject hierarchy
6. Create ScriptableObject config instances
7. Let Unity auto-generate .meta files, commit them
8. Import and organize sprite assets into Resources/

**Acceptance**: Unity Editor opens project, compiles with 0 errors, Play mode starts without exceptions.

**Full details**: [`audits/AUDIT_1_INFRASTRUCTURE.md`](audits/AUDIT_1_INFRASTRUCTURE.md)

---

### Phase B: Make It Run (Wiring) — Domains 2, 3, 5
**Connect existing C# systems to the game loop.**

Can be parallelized across developers:

| Task | Domain | What |
|---|---|---|
| Wire combat to GameManager | D2 | CombatInputHandler, attack triggering, damage display |
| Wire enemy spawning | D2 | ChunkSystem → EnemySpawner → world |
| Wire resource gathering | D5 | Click→tool check→harvest→inventory |
| Wire crafting stations | D3 | Station interaction → CraftingUI → minigame launch |
| Wire skills to hotbar | D2 | Skill activation (1-5 keys), mana/cooldown checks |
| Wire day/night modifiers | D5 | Night → enemy aggro/speed buffs |
| Wire death/respawn | D2 | Player death → death chest, enemy death → loot |
| Wire save slot UI | D5 | Multiple save files, auto-save, quick save/load |

**Acceptance**: Can walk around, attack enemies, gather resources, open crafting, use skills, save/load.

**Full details**: [`audits/AUDIT_2_COMBAT_AND_MOVEMENT.md`](audits/AUDIT_2_COMBAT_AND_MOVEMENT.md), [`audits/AUDIT_3_CRAFTING_AND_MINIGAMES.md`](audits/AUDIT_3_CRAFTING_AND_MINIGAMES.md), [`audits/AUDIT_5_WORLD_AND_PROGRESSION.md`](audits/AUDIT_5_WORLD_AND_PROGRESSION.md)

---

### Phase C: Make It Complete (Missing Systems) — Domains 3, 4, 5
**Implement systems that have no C# code at all.**

| Task | Domain | Python Lines | Priority |
|---|---|---|---|
| Dungeon System | D5 | 805 | HIGH — endgame content |
| Map/Waypoint System | D5 | 716 | HIGH — navigation |
| Fishing Minigame | D3 | 872 | MEDIUM — 6th discipline |
| Skills Menu UI | D4 | ~400 | HIGH — skill management |
| Interactive drag-drop crafting | D3 | 1,179 | HIGH — material placement |
| NPC system backend | D5 | ~300 | MEDIUM — quest delivery |
| Encyclopedia tab content | D5 | 332 | LOW — info display |

**Acceptance**: All game systems from Python version have C# equivalents.

**Full details**: [`audits/AUDIT_5_WORLD_AND_PROGRESSION.md`](audits/AUDIT_5_WORLD_AND_PROGRESSION.md), [`audits/AUDIT_3_CRAFTING_AND_MINIGAMES.md`](audits/AUDIT_3_CRAFTING_AND_MINIGAMES.md), [`audits/AUDIT_4_UI_SYSTEMS.md`](audits/AUDIT_4_UI_SYSTEMS.md)

---

### Phase D: Make It 3D — Domain 6
**Replace 2D rendering with low-fidelity 3D. Every system gets a 3D counterpart.**

| System | 2D (Current) | 3D (Target) |
|---|---|---|
| **Terrain** | Tilemap (flat) | Mesh with height (flat-shaded cubes per tile) |
| **Player** | SpriteRenderer | Capsule with colored material |
| **Enemies** | SpriteRenderer (billboard) | Colored cubes (red=hostile, yellow=neutral) |
| **NPCs** | SpriteRenderer | Colored cylinders (green) |
| **Resources** | SpriteRenderer | Scaled primitives (cones=trees, cubes=ore, spheres=stones) |
| **Crafting Stations** | SpriteRenderer | Boxes with discipline-colored materials |
| **Camera** | Orthographic top-down | Perspective, 45° angle, follows player |
| **Lighting** | Day/night overlay alpha | Directional light rotation (sun cycle) |
| **Combat VFX** | Sprite particles | Unity particle system with 3D billboards |
| **UI** | Screen Space Overlay | Same (Minecraft-style 2D overlay on 3D world) |
| **Dungeons** | Flat tile area | Walled room with 3D floor mesh |
| **Loot/Items** | Inventory icon only | Spinning cube on ground |

**Key principle**: UI stays 2D (Screen Space Overlay Canvas). World becomes 3D. This is the Minecraft model.

**Acceptance**: Can play entire game in 3D perspective view with primitive geometry. All systems functional. UI overlays work.

**Full details**: [`audits/AUDIT_6_3D_REQUIREMENTS.md`](audits/AUDIT_6_3D_REQUIREMENTS.md)

---

### Phase E: Make It Tested — Domain 7
**Can run in parallel with Phases B-D.**

| Category | Tests Needed | Currently | Status |
|---|---|---|---|
| Data Models | 20 | 0 | Not started |
| Damage Pipeline | 30 | 0 | Not started |
| Stat Formulas | 15 | 0 | Not started |
| EXP Curve | 12 | 0 | Not started |
| Difficulty Calculator | 20 | 0 | Not started |
| Reward Calculator | 15 | 0 | Not started |
| Tag System | 50+ | 0 | Not started |
| Status Effects | 18+ | 0 | Not started |
| Inventory/Equipment | 27 | 0 | Not started |
| Skill System | 15 | 0 | Not started |
| Save/Load | 15 | 0 | Not started |
| World Generation | 10 | 0 | Not started |
| Enemy AI | 8 | 0 | Not started |
| Crafting Logic (all 6) | 150 | 0 | Not started |
| ML Preprocessing | 40+ | 40+ | **COMPLETE** |
| E2E Scenarios | 10 | 10 | **COMPLETE** |
| LLM Integration | 14 | 14 | **COMPLETE** |
| **TOTAL** | **364+** | **104** | **28%** |

**Priority order**: Data Models → Damage Pipeline → Tag System → Crafting Logic → everything else.

**Acceptance**: 90%+ unit test pass rate, 100% E2E pass rate, all formulas match Python within tolerance.

**Full details**: [`audits/AUDIT_7_TESTING_STRATEGY.md`](audits/AUDIT_7_TESTING_STRATEGY.md)

---

### Phase F: Make It Polished — All Domains
**After the game is playable and tested.**

- Particle effects for combat and crafting (minigame_effects.py → Unity ParticleSystem)
- Audio system (SFX + ambient music)
- Rarity visual effects (glow, color coding)
- Tooltip z-ordering fixes
- Encyclopedia content population
- ONNX model conversion and Sentis integration
- Real LLM API integration (replace StubItemGenerator)
- Performance optimization
- Missing crafting station icons (T3/T4)

---

## Relationship to Existing Documents

This checklist and its 7 audit documents augment (not replace) the existing Migration Plan:

| Existing Document | Still Valid? | Relationship |
|---|---|---|
| `COMPLETION_STATUS.md` | Yes | Central hub for the overall migration plan |
| `MIGRATION_PLAN.md` | Yes | Master 7-phase plan — describes WHAT was ported |
| `IMPROVEMENTS.md` | Yes | Architecture improvements — describes HOW it was improved |
| `CONVENTIONS.md` | Yes | Coding standards — still applies to all new code |
| `PHASE_CONTRACTS.md` | Yes | Phase I/O contracts — completed |
| `phases/PHASE_1-7` | Yes | Detailed phase instructions — completed |
| `reference/UNITY_PRIMER.md` | Yes | Unity crash course — still useful |
| `reference/PYTHON_TO_CSHARP.md` | Yes | Type mappings — still useful |
| **This checklist** | **NEW** | **Identifies what's LEFT to do after the 7-phase port** |
| **audits/AUDIT_1-7** | **NEW** | **Domain-specific gap analysis with acceptance criteria** |

### Reading Order
1. `COMPLETION_STATUS.md` — Understand what was planned and built
2. **This document** (`UNITY_MIGRATION_CHECKLIST.md`) — Understand what's LEFT
3. The specific `audits/AUDIT_*.md` for your domain — Get detailed gap lists and acceptance criteria
4. `CONVENTIONS.md` — Follow coding standards
5. `reference/` docs — If you need Unity or C# conversion help

---

## Critical Constants (MUST PRESERVE in All Work)

These formulas must be preserved exactly in any new code:

```
Damage: base × hand(1.1-1.2) × STR(1+STR×0.05) × skill × class(max 1.2) × crit(2x) - def(max 75%)
EXP: floor(200 × 1.75^(level-1)), max level 30
Stats: STR +5%dmg, DEF +2%red, VIT +15HP, LCK +2%crit, AGI +5%forestry, INT -2%diff +20mana
Tiers: T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x
Durability: 0% = 50% effectiveness, never breaks
Quality: Normal(0-25%) → Fine(25-50%) → Superior(50-75%) → Masterwork(75-90%) → Legendary(90-100%)
Day/Night: 16 min day + 8 min night = 24 min cycle, start at noon
Dungeon: 6 rarity levels, 3 waves, 2x EXP, no material drops
```

---

**Last Updated**: 2026-02-19
**Previous Version**: 1.0 (2026-02-18) — single monolithic document with 46 gaps
**Current Version**: 2.0 — restructured as hub + 7 domain audit documents with ~151 gaps identified
