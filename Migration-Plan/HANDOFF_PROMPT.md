# Handoff Prompt for Phase 6 — Unity Integration

**Updated**: 2026-02-13
**Context**: Phases 1-5 are complete (82 C# files, ~24,100 LOC). This document provides the exact prompt and context needed for the next conversation to implement Phase 6.

---

## Recommended Initial Prompt

Copy everything below the line into a new conversation:

---

## BEGIN PROMPT

I'm migrating a production crafting RPG from Python/Pygame to Unity/C#. Phases 1-5 are complete (82 C# files, ~24,100 lines). I need you to implement Phase 6 (Unity Integration) — the first phase that uses MonoBehaviours and UnityEngine.

### Protocol

1. **Read** `Migration-Plan/COMPLETION_STATUS.md` as the central hub
2. **Read** `.claude/CLAUDE.md` for project context
3. **Read** `Migration-Plan/ADAPTIVE_CHANGES.md` for all 17 deviations from the plan
4. **Read** `Migration-Plan/phases/PHASE_6_UNITY_INTEGRATION.md` (954 lines — your primary specification)
5. **Read** the implementation summaries for completed phases:
   - `Migration-Plan/phases/PHASE_3_IMPLEMENTATION_SUMMARY.md`
   - `Migration-Plan/phases/PHASE_4_IMPLEMENTATION_SUMMARY.md`
   - `Migration-Plan/PHASE_5_IMPLEMENTATION_SUMMARY.md`
6. **Read** `Migration-Plan/CONVENTIONS.md` before writing any C# code
7. **Read** `Migration-Plan/PHASE_CONTRACTS.md` for input/output contracts
8. **Read** `Migration-Plan/reference/UNITY_PRIMER.md` if new to Unity
9. **Implement** Phase 6 code following the migration order in §9 of the Phase 6 doc
10. **Summarize** what was created (file names, line counts, key decisions)
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

**Phase 3 (Entity Layer)** — 3 Entities + 7 Components = 10 files (2,127 LOC)
- Character.cs, Enemy.cs, StatusEffect.cs (includes factory + manager)
- CharacterStats, Inventory, EquipmentManager, SkillManager, BuffManager, LevelingSystem, StatTracker

**Phase 4 (Game Systems)** — 40 files across 8 subsystems (15,688 LOC)
- Tags: TagRegistry, TagParser, EffectConfig, EffectContext
- Effects: EffectExecutor, TargetFinder, MathUtils
- Combat: CombatConfig, DamageCalculator, CombatManager, EnemySpawner, TurretSystem, AttackEffects
- Crafting: BaseCraftingMinigame + 5 discipline minigames + DifficultyCalculator + RewardCalculator
- World: WorldSystem, BiomeGenerator, Chunk, CollisionSystem, NaturalResource
- Progression: TitleSystem, ClassSystem, QuestSystem, SkillUnlockSystem
- Items: PotionSystem
- Save: SaveManager, SaveMigrator

**Phase 5 (ML Classifiers)** — 10 C# files + 2 Python scripts + 1 test file (~2,300 LOC)
- Preprocessing: MaterialColorEncoder, SmithingPreprocessor, AdornmentPreprocessor, AlchemyFeatureExtractor, RefiningFeatureExtractor, EngineeringFeatureExtractor
- Orchestration: ClassifierManager (defines IModelBackend + IModelBackendFactory interfaces)
- Data: ClassifierResult, ClassifierConfig
- Scripts: convert_models_to_onnx.py, generate_golden_files.py
- Tests: ClassifierPreprocessorTests.cs (24 tests)

All files are under `Unity/Assets/Scripts/` in namespaces: Game1.Core, Game1.Data.*, Game1.Entities.*, Game1.Systems.*

### What Phase 6 Must Do

**Decompose** the Python monoliths into Unity components:
- `game_engine.py` (10,098 lines) → ~20 MonoBehaviour components
- `renderer.py` (6,936 lines) → ~9 rendering components + Canvas UI
- `minigame_effects.py` (1,522 lines) → Unity Particle System
- Total: ~40-50 files, ~18,000-22,000 LOC estimated

**Key deliverables** (see Phase 6 doc §1.4):
- 5 Core MonoBehaviours: GameManager, GameStateManager, InputManager, CameraController, AudioManager
- 16 UI Components: Inventory, Equipment, Crafting, 5 Minigames, SkillBar, StatusBar, Map, etc.
- 8 World Rendering components: Tilemap, resources, entities, enemies, player, particles, effects
- 4 ScriptableObjects: GameConfig, CraftingConfig, CombatConfig, RenderingConfig
- 8+ Prefabs, 2 Scenes, 1 Input Action Asset, 5+ Sprite Atlases

### Critical Rules for Phase 6

1. **MonoBehaviours are THIN wrappers** — All game logic lives in Phases 1-5 pure C# classes. Phase 6 components call into that logic, they don't reimplement it.
2. **GamePosition.ToVector3()** — Use this for all position conversions, never manual coordinate mapping.
3. **Color tuple conversion** — Phases 1-5 use `(byte R, byte G, byte B, byte A)` tuples. Phase 6 needs `Color32 FromTuple()` helper.
4. **GameEvents bridge** — GameEvents is a static C# class (AC-003). Phase 6 may need a MonoBehaviour that subscribes to GameEvents and forwards to Unity UI components.
5. **Preserve all game constants** — No formula changes. Phase 6 is presentation only.
6. **JSON from StreamingAssets** — Call `GamePaths.SetBasePath(Application.streamingAssetsPath)` before any database loads.

### Phase 5 Integration Points for Phase 6

Phase 6 must provide the Sentis model backend for Phase 5's classifiers:

```csharp
// Phase 6 creates this:
public class SentisBackendFactory : IModelBackendFactory
{
    public IModelBackend Create(string modelPath, string classifierType)
    {
        // Load ONNX model via Unity Sentis
        var modelAsset = Resources.Load<ModelAsset>(modelPath);
        return new SentisModelBackend(modelAsset);
    }
}

public class SentisModelBackend : IModelBackend
{
    public (float probability, string error) Predict(float[] inputData) { ... }
    public bool IsLoaded => _worker != null;
    public void Dispose() { _worker?.Dispose(); }
}

// Wire it up in GameManager initialization:
ClassifierManager.Instance.Initialize(new SentisBackendFactory());
```

Crafting UI calls classifier validation:
```csharp
var result = ClassifierManager.Instance.ValidateSmithing(grid, stationGridSize);
if (result.Valid && result.Confidence > 0.7f) { /* proceed to invented recipe flow */ }
```

### Things Learned During Phases 1-5 (NOT in the plan docs)

These are practical discoveries that came up during implementation:

**From Phases 1-4:**

1. **Python object unions**: ManaCost can be string ("low") OR float (25.0). C# stores as `object` with typed helper methods.

2. **EquipmentDatabase stores raw JObject**: Not Dictionary<string, object>. JObject provides richer JSON access (AC-004).

3. **Slot determination inlined**: In EquipmentDatabase.DetermineSlot(), not SmithingTagProcessor (AC-005).

4. **Colors as value tuples**: `(byte R, byte G, byte B, byte A)` tuples, not Unity's Color32. Phase 6 needs converter.

5. **GamePaths uses reflection**: SetBasePath must be called before any database loads.

6. **StatusEffect consolidated**: Single StatusEffect.cs with StatusEffectFactory.Create() — not 6+ files.

7. **StatTracker simplified**: 145 LOC with extensible RecordActivity pattern.

8. **BaseCraftingMinigame pattern**: All 5 minigames extend abstract base. Phase 6 MinigameUI components call into these.

9. **TargetFinder.Mode is static**: Default Horizontal (2D). Set to Full3D for 3D distance.

10. **Save format is v3.0**: SaveMigrator handles v1.0→v3.0 upgrades.

11. **Thread-safe singletons**: All with `ResetInstance()` for testing.

12. **GameEvents is a static class**: NOT a ScriptableObject. Phase 6 may need a MonoBehaviour bridge.

**From Phase 5:**

13. **HSV must match Python exactly** (AC-013): MaterialColorEncoder.HsvToRgb() implements Python's colorsys algorithm. Do NOT replace with Unity's Color.HSVToRGB() — it would break classifier accuracy.

14. **IModelBackend abstraction** (AC-014): Phase 6 must implement IModelBackendFactory with Sentis Workers. Pass to ClassifierManager.Instance.Initialize(factory).

15. **Typed validation methods** (AC-015): Each discipline has its own typed validate method — `ValidateSmithing(grid, size)`, `ValidateAlchemy(slots, tier)`, etc.

16. **Flat float arrays** (AC-016): Preprocessor output is flat `float[]` in row-major, channel-last layout. Feed directly to Sentis input tensors.

17. **Feature order is sacred**: LightGBM models silently fail if feature indices change. The extractors have hardcoded order matching Python training data.

18. **Population std dev**: All standard deviation uses ÷N (population), not ÷(N-1) (sample), matching numpy.std.

### Adaptive Changes (17 entries in ADAPTIVE_CHANGES.md)

| ID | Summary |
|----|---------|
| AC-001 | Phases 1-3 built inline with Phase 4 |
| AC-002 | Pure C# throughout (no UnityEngine) for Phases 1-5 |
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
| AC-013 | Pure C# HSV-to-RGB (not Unity's Color.HSVToRGB) |
| AC-014 | IModelBackend abstraction for Sentis injection |
| AC-015 | Typed validation methods per discipline |
| AC-016 | Flat float arrays for tensor data |
| AC-017 | Math helpers shared via AlchemyFeatureExtractor |

### Documentation

After completing Phase 6, create `PHASE_6_IMPLEMENTATION_SUMMARY.md` documenting:
- Files created with line counts
- Architecture decisions made
- Constants/formulas preserved
- Deviations from the plan (add to ADAPTIVE_CHANGES.md)
- Cross-phase dependencies
- Verification checklist

Think about all of this and work to implement Phase 6. This is the largest and most complex phase — it turns all the pure C# logic into a playable Unity game. Follow the recommended build order in Phase 6 doc §9 for incremental testing.

## END PROMPT

---

## Notes for the User

### Phase 6 Special Requirements
Phase 6 requires:
- Unity project initialized with proper folder structure
- Unity packages: Input System, TextMeshPro, Newtonsoft.Json, Sentis
- Understanding of MonoBehaviour lifecycle (see `Migration-Plan/reference/UNITY_PRIMER.md`)
- JSON files copied to `StreamingAssets/Content/` (byte-identical)
- ONNX model files in `Resources/Models/` (from Phase 5 conversion scripts)
- 3,749 sprite images organized into sprite atlases

### Phase 6 Build Order (from §9)
The Phase 6 doc recommends building in this order for incremental testing:
1. Scene setup + GameManager bootstrap
2. WorldRenderer + CameraController
3. PlayerRenderer + InputManager (movement)
4. ResourceRenderer + EntityRenderer
5. EnemyRenderer + combat visuals
6. StatusBarUI + SkillBarUI + NotificationUI
7. GameStateManager + panel infrastructure
8. InventoryUI + DragDropManager
9. EquipmentUI + TooltipRenderer
10. CraftingUI (recipe selection + placement)
11. MinigameUIs (all 5)
12. MapUI + EncyclopediaUI + StatsUI
13. NPCDialogueUI + ChestUI
14. StartMenuUI + ClassSelectionUI
15. DebugOverlay + ParticleEffects
16. Save/Load integration + polish
17. Integration testing + bug fixing

### Remaining Phase 5 Tasks (Pre-Phase 6)
Before Phase 6 can test ML classifiers end-to-end:
- Run `Unity/Assets/Scripts/Game1.Systems/Classifiers/Scripts/convert_models_to_onnx.py` (requires TensorFlow + LightGBM)
- Place output ONNX files in `Assets/Resources/Models/`
- Install Unity Sentis package

### What Could Go Wrong
1. **Cross-phase type mismatches**: If Phase 6 MonoBehaviours can't find C# types from Phases 1-5, check assembly definitions (.asmdef files) and namespace imports.
2. **JSON loading paths**: GamePaths must be configured with `Application.streamingAssetsPath` before any database loads.
3. **GameEvents → UI binding**: GameEvents is static C# events. MonoBehaviours need to subscribe in OnEnable/unsubscribe in OnDisable.
4. **Color conversion**: All Phase 1-5 colors are value tuples. Need systematic converter for Unity's Color32/Color.
5. **Sentis version compatibility**: Ensure ONNX opset 15 is supported by the installed Sentis version.
6. **Large scope**: Phase 6 is ~43 files, ~42 days estimated. Consider splitting into sub-phases (world rendering → UI panels → minigames → polish).
