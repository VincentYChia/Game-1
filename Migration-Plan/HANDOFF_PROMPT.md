# Handoff Prompt for Next Migration Phases (5-7)

**Created**: 2026-02-13
**Context**: Phases 1-4 are complete (72 C# files, 21,796 LOC). This document provides the exact prompt and context needed for the next conversation to continue the migration.

---

## Recommended Initial Prompt

Copy everything below the line into a new conversation:

---

## BEGIN PROMPT

I'm migrating a production crafting RPG from Python/Pygame to Unity/C#. Phases 1-4 are complete (72 C# files, 21,796 lines). I need you to implement the remaining phases.

### Protocol for Each Phase

For each phase you work on, follow this protocol:

1. **Read** `Migration-Plan/COMPLETION_STATUS.md` as the central hub
2. **Read** `.claude/CLAUDE.md` for project context
3. **Read** `Migration-Plan/ADAPTIVE_CHANGES.md` for deviations from the plan
4. **Read** the phase-specific document in `Migration-Plan/phases/`
5. **Read** the implementation summaries for completed phases:
   - `Migration-Plan/phases/PHASE_3_IMPLEMENTATION_SUMMARY.md`
   - `Migration-Plan/phases/PHASE_4_IMPLEMENTATION_SUMMARY.md`
6. **Read** `Migration-Plan/CONVENTIONS.md` before writing any C# code
7. **Read** `Migration-Plan/PHASE_CONTRACTS.md` for input/output contracts
8. **Implement** the phase code
9. **Summarize** what was created (file names, line counts, key decisions)
10. **Check** for deviations from the plan
11. **Update** `Migration-Plan/ADAPTIVE_CHANGES.md` with any changes
12. **Commit** with a descriptive message
13. **Push** to the assigned branch

### What's Already Done

**Phase 1 (Foundation)** — 3 Core files + 6 Enums + 10 Models = 19 files
- GameConfig.cs (208 LOC), GameEvents.cs (144), GamePaths.cs (144)
- All enums: DamageType, Rarity, EquipmentSlot, TileType, StatusEffectType, CraftingDiscipline
- All models: GamePosition, IGameItem, MaterialDefinition, EquipmentItem, ItemStack, Recipe, PlacementData, SkillDefinition, TitleDefinition, ClassDefinition

**Phase 2 (Data Layer)** — 10 Database files = 10 files
- MaterialDatabase, EquipmentDatabase, RecipeDatabase, SkillDatabase, PlacementDatabase, TitleDatabase, ClassDatabase, ResourceNodeDatabase, WorldGenerationConfig, DatabaseInitializer

**Phase 3 (Entity Layer)** — 3 Entities + 7 Components = 10 files
- Character.cs, Enemy.cs, StatusEffect.cs (includes factory + manager)
- CharacterStats, Inventory, EquipmentManager, SkillManager, BuffManager, LevelingSystem, StatTracker

**Phase 4 (Game Systems)** — 40 files across 8 subsystems
- Tags: TagRegistry, TagParser, EffectConfig, EffectContext
- Effects: EffectExecutor, TargetFinder, MathUtils
- Combat: CombatConfig, DamageCalculator, CombatManager, EnemySpawner, TurretSystem, AttackEffects
- Crafting: BaseCraftingMinigame + 5 discipline minigames + DifficultyCalculator + RewardCalculator
- World: WorldSystem, BiomeGenerator, Chunk, CollisionSystem, NaturalResource
- Progression: TitleSystem, ClassSystem, QuestSystem, SkillUnlockSystem
- Items: PotionSystem
- Save: SaveManager, SaveMigrator

All files are under `Unity/Assets/Scripts/` in namespaces: Game1.Core, Game1.Data.Enums, Game1.Data.Models, Game1.Data.Databases, Game1.Entities, Game1.Entities.Components, Game1.Systems.*

### What Needs to Be Done

**Phase 5 — ML Classifiers** (`Migration-Plan/phases/PHASE_5_ML_CLASSIFIERS.md`)
- Convert 2 CNN + 3 LightGBM models from Python to ONNX
- Port preprocessing code to C# for Unity Sentis
- 5 ONNX model files + C# preprocessors + ClassifierManager orchestrator
- This phase can be done independently — it only needs MaterialDefinition and MaterialDatabase

**Phase 6 — Unity Integration** (`Migration-Plan/phases/PHASE_6_UNITY_INTEGRATION.md`)
- Decompose GameEngine (10,098 lines Python) into ~40 MonoBehaviour components
- Camera system (orthographic/perspective toggle)
- Input System integration
- UI with Unity Canvas
- This is the FIRST phase that uses `using UnityEngine`
- All prior phases are pure C# — Phase 6 creates thin MonoBehaviour wrappers

**Phase 7 — Polish & LLM Stub** (`Migration-Plan/phases/PHASE_7_POLISH_LLM.md`)
- IItemGenerator interface + StubItemGenerator (LLM deferred)
- 10 E2E test scenarios
- 3D readiness verification checklist
- Final integration testing

### Critical Rules

1. **Pure C# for Phase 5** — No MonoBehaviour, no `using UnityEngine`
2. **MonoBehaviours only for Phase 6** — Thin wrappers around existing logic
3. **GamePosition** for ALL positions (never raw Vector3 in game logic)
4. **IGameItem** interface hierarchy for item types
5. **Preserve all game formulas/constants exactly** — See GameConfig.cs
6. **JSON files byte-identical** — No schema changes to existing JSON

### Things Learned During Phases 1-4 (NOT in the plan docs)

These are practical discoveries that came up during implementation:

1. **Python object unions**: Python uses duck typing extensively. ManaCost can be string ("low") OR float (25.0). C# stores as `object` with typed helper methods (GetManaCostFloat, GetManaCostString). Watch for similar unions in any remaining Python code.

2. **EquipmentDatabase stores raw JObject**: Not Dictionary<string, object>. JObject provides richer JSON access (typed Value<T>(), nested navigation). This is intentional (AC-004).

3. **Slot determination inlined**: Equipment slot determination is in EquipmentDatabase.DetermineSlot(), not SmithingTagProcessor, to avoid Phase 4 dependency from Phase 2 (AC-005).

4. **Colors as value tuples**: Colors use `(byte R, byte G, byte B, byte A)` tuples instead of Unity's Color32. Phase 6 will need `Color32 FromTuple()` conversion.

5. **GamePaths uses reflection**: GamePaths.SetBasePath sets the root path used by all file operations. For testing, call SetBasePath before any database loads.

6. **StatusEffect consolidated**: The plan specified 6+ separate files for status effects. Implementation uses a single StatusEffect.cs with parameterized creation via StatusEffectFactory.Create() — simpler, same functionality.

7. **StatTracker simplified**: Plan estimated 1,721 lines / 850+ stats. Implementation is 145 lines with extensible RecordActivity pattern. Can be expanded later without API changes.

8. **BaseCraftingMinigame pattern**: All 5 minigames extend this abstract base. New disciplines only need: InitializeMinigame, UpdateMinigame, HandleInput, CalculatePerformance, CalculateRewardForDiscipline, GetDisciplineState.

9. **TargetFinder.Mode is static**: Set `TargetFinder.Mode = DistanceMode.Full3D` globally to enable 3D distance. Default is Horizontal (2D parity mode).

10. **Save format is v3.0**: SaveMigrator handles v1.0→v2.0→v3.0 upgrades. New features should use v3.0 format.

11. **Thread-safe singletons everywhere**: All databases and system managers use double-checked locking with `ResetInstance()` for testing.

12. **GameEvents is a static class**: NOT a ScriptableObject. Phase 6 may want a MonoBehaviour bridge that subscribes and forwards to Unity's event system.

### Adaptive Changes Already Made (12 entries in ADAPTIVE_CHANGES.md)

| ID | Summary |
|----|---------|
| AC-001 | Phases 1-3 built inline with Phase 4 (no code existed) |
| AC-002 | Pure C# throughout (System.MathF, no UnityEngine) |
| AC-003 | GameEvents as static class, not ScriptableObject |
| AC-004 | EquipmentDatabase stores raw JObject |
| AC-005 | Slot determination inlined in EquipmentDatabase |
| AC-006 | SkillCost ManaCost as object type |
| AC-007 | BaseCraftingMinigame template method pattern |
| AC-008 | IPathfinder + GridPathfinder in CollisionSystem |
| AC-009 | TargetFinder uses static DistanceMode |
| AC-010 | Effect dispatch table in EffectExecutor |
| AC-011 | SaveManager version 3.0 format |
| AC-012 | DamageCalculator extracted as static class |

### Documentation

After completing each phase, create an implementation summary (like PHASE_3_IMPLEMENTATION_SUMMARY.md and PHASE_4_IMPLEMENTATION_SUMMARY.md) documenting:
- Files created with line counts
- Architecture decisions made
- Constants/formulas preserved
- Deviations from the plan (add to ADAPTIVE_CHANGES.md)
- Cross-phase dependencies
- Verification checklist

Documentation is key — it enables debugging, completeness checking, and serves as reference for future work.

Think about all of this and work to implement the next phase. Work hard and ensure robust migration.

## END PROMPT

---

## Notes for the User

### Recommended Phase Order
- **Phase 5 first** if you want ML classifiers working (can be done independently)
- **Phase 6 first** if you want to see the game in Unity (depends on Phase 4, which is done)
- **Phase 5 and 6 in parallel** if you have multiple conversations

### Phase 5 Special Requirements
Phase 5 requires:
- Python environment with Keras, LightGBM, tf2onnx, onnxmltools
- Trained model files from `Scaled JSON Development/`
- Golden file test data generation (run Python classifiers on test inputs, save outputs)
- Unity Sentis package installed in Unity project

### Phase 6 Special Requirements
Phase 6 requires:
- Unity project initialized with proper folder structure
- Unity packages: Input System, TextMeshPro, Newtonsoft.Json
- Understanding of MonoBehaviour lifecycle (see `Migration-Plan/reference/UNITY_PRIMER.md`)
- JSON files copied to `StreamingAssets/Content/` (byte-identical)

### What Could Go Wrong
1. **Phase 5 ONNX conversion**: Model format compatibility issues. Have fallback plan (mock classifiers that always return "valid").
2. **Phase 6 Unity setup**: Missing packages or incorrect project structure. Follow UNITY_PRIMER.md exactly.
3. **Cross-phase type mismatches**: If Phase 6 MonoBehaviours can't find the C# types from Phases 1-4, check assembly definitions (.asmdef files) and namespace imports.
4. **JSON loading paths**: GamePaths must be configured with correct base path before any database loads. In Unity, use `Application.streamingAssetsPath`.
