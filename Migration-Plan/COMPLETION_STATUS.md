# Migration Plan — Holistic Summary & Completion Status

**Last Updated**: 2026-02-13
**Branch**: `claude/review-migration-docs-gMRfn`
**Total Documentation**: 16,013 lines across 15 documents (+ 3 organizational READMEs)
**Implementation Status**: Phases 1-6 complete (127 C# files, ~30,800 LOC)

---

## What This Plan Is

A comprehensive, actionable plan for migrating **Game-1** — a production crafting RPG built in Python/Pygame (~75,911 LOC, 149 Python files, 398+ JSON data files, 3,749 asset images) — to **Unity/C#**. The plan is not just a language port; it's a migration into a 3D game engine with architecture improvements that eliminate known Python-era technical debt.

The plan covers every aspect of the migration: data models, database singletons, entity/character systems, combat, 5 crafting disciplines with minigames, world generation, ML classifiers (CNN + LightGBM), save/load, and the full Unity integration layer.

---

## The Five Pillars

### 1. Exact Mechanical Fidelity

Every game formula, constant, and behavior is preserved verbatim:
- Damage pipeline: `base × hand(1.1-1.2) × STR(1+STR×0.05) × skill × class(max 1.2) × crit(2x) - def(max 75%)`
- EXP curve: `200 × 1.75^(level-1)`, max level 30
- 6 stats, each with exact multipliers (STR +5%dmg, DEF +2%red, VIT +15HP, LCK +2%crit, AGI +5%forestry, INT -2%diff +20mana)
- Tier multipliers: T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x
- Durability: 0% = 50% effectiveness, never breaks
- 190+ combat tags, 14 enchantments, 17 status effects, 100+ skills
- All balance numbers, crafting formulas, and difficulty curves unchanged

### 2. JSON-Driven Architecture

The game is driven by JSON data files — items, recipes, materials, skills, enemies, world generation, all defined in JSON and loaded at runtime. This is preserved exactly:
- JSON files copied byte-identical to `StreamingAssets/Content/`
- Loaded via Newtonsoft.Json at runtime
- Moddable without recompilation
- No schema changes

### 3. 3D-Ready Architecture

This is not just a Python→C# translation. It's migration into Unity, a 3D engine. All code is structured so upgrading to 3D visuals later is a content/rendering change, not a logic rewrite:
- **`GamePosition`** wraps `Vector3`. Python `(x, y)` becomes `(x, 0, z)` — height defaults to 0.
- **`TargetFinder`** provides `GetDistance()` with toggleable `DistanceMode` (Horizontal for 2D parity, Full3D for future)
- **`IPathfinder`** interface — `GridPathfinder` (A* on tiles) now, `NavMeshPathfinder` later
- **Camera** supports orthographic (2D top-down) and perspective (3D) via config toggle
- All tile-to-world conversion centralized in `WorldSystem` — swap Tilemap to terrain in one place

### 4. Architecture Improvements (Not a Blind Port)

Since the entire codebase is being rewritten, the plan identifies and fixes 8 macro-level architecture issues and 13 per-file inefficiencies — plus a complete item type hierarchy. These improve the codebase without changing any game behavior:

**Macro changes** (8): Event system, enum-based slots, UI/data separation, save migration pipeline, effect dispatch table, GamePosition, 3D-ready geometry, crafting base class

**Per-file fixes** (13): ItemStack factory, equipment serialization, enemy parser consolidation, inventory caching, pre-sorted abilities, rarity single source, cached skills, invented recipe UUIDs, computed bonuses, GameEngine decomposition map, stat recalculation caching, NavMesh-ready pathfinder, centralized ItemFactory

**Item type hierarchy**: `IGameItem` interface with `MaterialItem`, `EquipmentItem`, `ConsumableItem`, `PlaceableItem` concrete types replacing the Python dict-based item system

### 5. Modularity and Independence

The 7-phase plan is dependency-ordered so developers can work on phases independently:
- Phases 1-2 (data) must complete before Phases 3-4 (gameplay)
- Phase 5 (ML classifiers) runs in parallel with Phases 3-4
- Phase 6 (Unity integration) depends on Phases 4-5
- Phase 7 (polish) depends on everything
- Phase contracts specify exactly what each phase RECEIVES and DELIVERS

---

## Document Map

### Core Documents (Read First)

| Document | Lines | Purpose |
|----------|-------|---------|
| `MIGRATION_PLAN.md` | 1,229 | Master overview: project stats, 7-phase summary, critical preservation formulas, 3D readiness strategy, risk register, document index |
| `IMPROVEMENTS.md` | 1,424 | All architecture improvements: 8 MACRO changes + 13 FIX items + IGameItem hierarchy + 3D readiness + application schedule. Quick reference index at top. |
| `CONVENTIONS.md` | 709 | Living document: naming, patterns, error handling, singleton pattern, JSON loading, 3D conventions, item hierarchy conventions. Grows during migration. |
| `PHASE_CONTRACTS.md` | 641 | Per-phase inputs/outputs with exact C# types, verification code, and cross-phase dependency matrix |
| `MIGRATION_META_PLAN.md` | 1,075 | Pre-existing methodology document: validation strategy, testing approach, risk framework |

### Phase Documents (All Complete)

| Phase | Lines | What It Covers |
|-------|-------|----------------|
| **Phase 1: Foundation** | 1,908 | 13 data model files → C# classes, 7 enum types, `GamePosition`, `IGameItem` hierarchy, `ItemFactory`. Line-by-line field mappings. |
| **Phase 2: Data Layer** | 1,702 | 14 database singletons, JSON loading infrastructure, initialization order, 3D-compatible position deserialization |
| **Phase 3: Entity Layer** | 1,080 | `Character` (2,576 lines), 11 components, 17 status effects, `Enemy` AI, stat caching, `GamePosition` for all positions |
| **Phase 4: Game Systems** | 1,413 | Combat (10-step damage pipeline), 5 crafting minigames with `BaseCraftingMinigame`, world generation, tag/effect system with 3D-ready `TargetFinder`, `IPathfinder`, save/load |
| **Phase 5: ML Classifiers** | 1,116 | 2 CNN + 3 LightGBM → ONNX → Unity Sentis. Exact preprocessing constants. Golden file testing. No 3D impact. |
| **Phase 6: Unity Integration** | 954 | GameEngine (10,098 lines) decomposed into ~40 Unity components. Camera (ortho/perspective), XZ-plane rendering, Input System, UI. |
| **Phase 7: Polish & LLM Stub** | 1,024 | `IItemGenerator` interface + `StubItemGenerator`, 10 E2E test scenarios, 3D readiness verification checklist |

### Reference Documents

| Document | Lines | Purpose |
|----------|-------|---------|
| `UNITY_PRIMER.md` | 679 | Unity crash course: MonoBehaviour vs plain C#, lifecycle, SerializeField, Canvas, Input System, Tilemap, coordinate system, camera setup |
| `PYTHON_TO_CSHARP.md` | 902 | Type mappings, pattern conversions, singleton migration, enum migration, Position→GamePosition, IGameItem patterns, 9 common gotchas |

---

## Architecture Decisions (All 15)

| Decision | Rationale |
|----------|-----------|
| Manual singletons for databases | Matches Python, simplest migration path |
| Newtonsoft.Json via StreamingAssets | JSON compat + moddability |
| Plain C# for game logic (Phases 1-5) | Testable without Unity scene |
| MonoBehaviours only for Phase 6 | Thin wrappers around ported logic |
| Status effects as abstract hierarchy | Polymorphic dispatch, matches Python |
| Enemy AI as enum state machine | Simple, testable |
| LLM system: interface + stub only | Defer API integration |
| ML models: ONNX via Unity Sentis | Unity-native, GPU acceleration |
| JSON files byte-identical | Backward compat, moddability |
| `IGameItem` interface hierarchy | Type-safe items replace dict-based approach |
| `GamePosition` wrapping `Vector3` | 3D-ready positions, zero cost |
| `TargetFinder` with `DistanceMode` | Toggleable 2D/3D distance |
| `IPathfinder` interface | Grid→NavMesh swap without logic changes |
| `BaseCraftingMinigame` base class | Eliminates ~1,240 lines of duplication |
| `ItemFactory` for all creation | Single entry point, consistent item lifecycle |

---

## Implementation Progress

| Phase | Status | Files | LOC | Summary |
|-------|--------|-------|-----|---------|
| Phase 1 — Foundation | **COMPLETE** | 19 | ~3,200 | Data models, enums, GamePosition, IGameItem |
| Phase 2 — Data Layer | **COMPLETE** | 10 | ~2,300 | Database singletons, JSON loading |
| Phase 3 — Entity Layer | **COMPLETE** | 10 | 2,127 | Character, Enemy, StatusEffect, 7 components |
| Phase 4 — Game Systems | **COMPLETE** | 40 | 15,688 | Combat, crafting, world, save/load |
| Phase 5 — ML Classifiers | **COMPLETE** | 10 | ~2,300 | 5 preprocessors + ClassifierManager + tests |
| Phase 6 — Unity Integration | **COMPLETE** | 45 | 6,697 | GameEngine decomposition, rendering, UI |
| Phase 7 — Polish & LLM Stub | **NOT STARTED** | ~10 | ~2,000 est | IItemGenerator, E2E tests, 3D verification |

**Implementation summaries**:
- `Migration-Plan/phases/PHASE_3_IMPLEMENTATION_SUMMARY.md`
- `Migration-Plan/phases/PHASE_4_IMPLEMENTATION_SUMMARY.md`
- `Migration-Plan/PHASE_5_IMPLEMENTATION_SUMMARY.md`
- `Migration-Plan/phases/PHASE_6_IMPLEMENTATION_SUMMARY.md`

## What To Do Next

### Phase 7 — Polish & LLM Stub (Next Phase)
1. **Read** `Migration-Plan/phases/PHASE_7_POLISH.md` (1,024 lines)
2. `IItemGenerator` interface + `StubItemGenerator` (LLM stub)
3. 10 E2E test scenarios
4. 3D readiness verification checklist

### Remaining Phase 5 Tasks (Can Be Done Anytime)
- Run `convert_models_to_onnx.py` (requires TensorFlow + LightGBM Python environments)
- Run `generate_golden_files.py` to produce test validation data
- Validate ONNX models match Python originals (100 random inputs each)

### Unity Scene Assembly (Required Before Running)
- Assemble scene hierarchy per Phase 6 implementation summary §6
- Create prefabs for grid cells, class cards, save slots, damage numbers, etc.
- Configure InputActionAsset or rely on InputManager's inline fallback bindings
- Copy JSON files to `StreamingAssets/Content/` (byte-identical)
- Copy ONNX models to `Resources/Models/`

### Reading Order for New Developers
1. `MIGRATION_PLAN.md` §0 — How to use this plan
2. `CONVENTIONS.md` — All rules (naming, 3D, items)
3. `IMPROVEMENTS.md` Quick Reference — See all improvements at a glance
4. `PHASE_CONTRACTS.md` — Your phase's inputs/outputs
5. Your phase document — Detailed instructions
6. `UNITY_PRIMER.md` — If new to Unity
7. `PYTHON_TO_CSHARP.md` — Language conversion reference

---

## Session History

| Session | Date | Work Done |
|---------|------|-----------|
| 1 | 2026-02-10 | Read entire Python codebase (~75,911 LOC). Created master plan + 7 phase docs + 2 reference docs. 11,164 lines across 14 documents. |
| 2 | 2026-02-11 | Quality audit. Created `PHASE_CONTRACTS.md`, `CONVENTIONS.md`, `UNITY_PRIMER.md`, `IMPROVEMENTS.md` (5 macro + 9 fixes). Expanded to 14,847 lines. |
| 3 | 2026-02-11 | 3D readiness pass + deeper code audit. Added `IGameItem` hierarchy, `GamePosition`, `TargetFinder`, `IPathfinder`, `BaseCraftingMinigame`, `ItemFactory`. Updated all 15 docs. 16,013 lines. |
| 4 | 2026-02-11 | Holistic review and cleanup. Fixed duplicate schedule, stale cross-references, line counts. Added quick reference index. Final consistency pass. |
| 5 | 2026-02-13 | Phase 1-4 implementation. 72 C# files, 21,796 LOC. All foundation, data, entity, and game system code complete. 12 adaptive changes documented. |
| 6 | 2026-02-13 | Phase 5 implementation. 10 C# files + 2 Python scripts + 1 test file (~2,300 LOC C#). ML classifier preprocessing, ClassifierManager, golden file scripts. 5 new adaptive changes (AC-013 through AC-017). |
| 7 | 2026-02-13 | Phase 6 implementation. 45 C# files (6,697 LOC). Full Unity integration: GameManager, GameStateManager, InputManager, CameraController, 4 ScriptableObject configs, 3 utilities (Color/Position/Sprite), 2 Sentis ML backends, 9 world renderers, 22 UI components (HUD, panels, minigames, menus). 3 new adaptive changes (AC-018 through AC-020). |

---

**Status**: Phases 1-6 complete. Ready for Phase 7 (Polish & LLM Stub) execution.
