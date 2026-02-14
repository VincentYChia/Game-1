# Adaptive Changes Log

**Purpose**: Document all deviations from the original migration plan that occurred during implementation. Future phases MUST read this file to understand what changed and why.

**Format**: Each entry has a unique ID (AC-NNN), the phase where it occurred, what changed, and why.

---

## Phase 4 — Game Systems (2026-02-13)

### AC-001: Foundation Types Built Inline with Phase 4
**Phase**: 4 (affects 1-3)
**Change**: Phases 1-3 (Foundation, Data Layer, Entity Layer) were implemented as part of Phase 4 rather than as separate phases, because no C# code existed yet when Phase 4 began.
**Files Created**:
- Game1.Core: GameConfig, GameEvents, GamePaths (3 files)
- Game1.Data.Enums: DamageType, Rarity, EquipmentSlot, TileType, StatusEffectType, CraftingDiscipline (6 files)
- Game1.Data.Models: GamePosition, IGameItem, MaterialDefinition, EquipmentItem, ItemStack, Recipe, PlacementData, SkillDefinition, TitleDefinition, ClassDefinition (10 files)
- Game1.Data.Databases: Material, Equipment, Recipe, Skill, Placement, Title, Class, ResourceNode, WorldGeneration, DatabaseInitializer (10 files)
- Game1.Entities: Character, Enemy, StatusEffect (3 files)
- Game1.Entities.Components: CharacterStats, Inventory, EquipmentManager, SkillManager, BuffManager, LevelingSystem, StatTracker (7 files)
**Impact**: All Phase 1-3 deliverables are available. Phase 5+ can proceed normally.
**Risk**: Foundation types may need refinement as they were implemented concurrently.

### AC-002: Pure C# Throughout (No UnityEngine References)
**Phase**: 4
**Change**: All files use pure C# with no UnityEngine imports, as specified. GamePosition is a pure struct using System.MathF for calculations instead of wrapping Vector3. Colors use `(byte R, byte G, byte B, byte A)` tuples instead of Color32.
**Rationale**: Enables unit testing without Unity, follows Phase 1-5 plain C# rule.
**Impact**: Phase 6 will need thin wrapper conversions: `GamePosition.ToVector3()` and `Color32 FromTuple()`.

### AC-003: GameEvents as Static Class (Not ScriptableObject)
**Phase**: 4
**Change**: GameEvents implemented as a static class with C# events rather than Unity ScriptableObject event channels.
**Rationale**: Plain C# requirement for Phases 1-5. No MonoBehaviour dependency.
**Impact**: Phase 6 may want to add a MonoBehaviour bridge that subscribes to GameEvents and forwards to Unity's event system if needed for UI binding.

### AC-004: EquipmentDatabase Stores Raw JObject
**Phase**: 4
**Change**: EquipmentDatabase stores raw Newtonsoft.Json.Linq.JObject instead of Dictionary<string, object> for equipment data, matching the user's note about Phase 2 decisions.
**Rationale**: JObject provides richer JSON access (typed value extraction, nested navigation) compared to Dictionary.
**Impact**: Consumers use JObject.Value<T>() for typed access. This is intentional.

### AC-005: Slot Determination Inlined in EquipmentDatabase
**Phase**: 4
**Change**: Equipment slot determination is inlined in EquipmentDatabase.DetermineSlot() rather than delegated to SmithingTagProcessor, matching the user's note about avoiding Phase 4 dependency from Phase 2.
**Rationale**: SmithingTagProcessor is a Phase 4 crafting concern. Database loading shouldn't depend on it.
**Impact**: None — slot logic is straightforward string-to-enum mapping.

### AC-006: SkillCost ManaCost as Object Type
**Phase**: 4
**Change**: SkillDefinition.ManaCost stored as `object` with typed helper methods (GetManaCostFloat, GetManaCostString) to handle Python's union type where mana cost can be a string ("low", "moderate") OR a float (25.0).
**Rationale**: Preserves Python behavior exactly. JSON may contain either type.
**Impact**: Consumers should use the helper methods rather than casting directly.

### AC-007: BaseCraftingMinigame Template Method Pattern
**Phase**: 4
**Change**: Implemented BaseCraftingMinigame as an abstract base class using the Template Method pattern (MACRO-3 from IMPROVEMENTS.md). All 5 discipline minigames extend this base.
**Shared Code Eliminated**: ~1,240 lines of duplicated time management, difficulty calculation, and reward computation.
**New Abstraction**: `MinigameInput` class and `MinigameInputType` enum for input handling.
**Impact**: All minigames share consistent Update/HandleInput/GetReward behavior. New disciplines only need to implement UpdateMinigame(), HandleInput(), CalculatePerformance(), and CalculateRewardForDiscipline().

### AC-008: CollisionSystem Implements IPathfinder Interface
**Phase**: 4
**Change**: Created IPathfinder interface with GridPathfinder implementation inside CollisionSystem.cs. The interface supports future NavMesh swap (Phase 6+).
**Rationale**: Follows MACRO improvement for IPathfinder from migration plan.
**Impact**: GridPathfinder uses A* with Bresenham's line algorithm for LoS. Phase 6 can provide NavMeshPathfinder implementing the same interface.

### AC-009: TargetFinder Uses Static DistanceMode
**Phase**: 4
**Change**: TargetFinder.Mode is a static field defaulting to DistanceMode.Horizontal. All distance calculations route through GetDistance() which respects this mode.
**Rationale**: Implements the 2D/3D toggle from CONVENTIONS.md §12.2 without requiring dependency injection.
**Impact**: Set `TargetFinder.Mode = DistanceMode.Full3D` to enable 3D distance when needed.

### AC-010: Effect Dispatch Table in EffectExecutor
**Phase**: 4
**Change**: Special mechanics in EffectExecutor use a method dispatch approach (switch on tag name) rather than the 250-line if/elif chain from Python. Each mechanic (lifesteal, knockback, pull, execute, teleport, dash, phase) is a separate private method.
**Rationale**: Follows IMPROVEMENTS.md recommendation for dispatch table pattern.
**Impact**: Adding new special mechanics requires adding a case to the switch and a new method.

### AC-011: SaveManager Version 3.0 Format
**Phase**: 4
**Change**: SaveManager uses version "3.0" (infinite world with seed-based generation) as the current save format, matching the Python source exactly.
**Migration Path**: SaveMigrator handles v1.0→v2.0→v3.0 upgrades.
**Impact**: Save files from the Python version should be loadable after JSON path adjustments.

### AC-012: DamageCalculator Extracted as Static Class
**Phase**: 4
**Change**: Damage calculation logic extracted from CombatManager into a standalone DamageCalculator static class.
**Rationale**: Pure math functions are more testable in isolation. CombatManager delegates to DamageCalculator.
**Impact**: All damage formula constants are in DamageCalculator, making them easy to verify against Python.

---

## Phase 5 — ML Classifiers (2026-02-13)

### AC-013: Pure C# HSV-to-RGB Instead of Unity's Color.HSVToRGB
**Phase**: 5
**Change**: Implemented Python's `colorsys.hsv_to_rgb` algorithm directly in C# (`MaterialColorEncoder.HsvToRgb()`) rather than using Unity's `Color.HSVToRGB()`.
**Rationale**: AC-002 (pure C# throughout Phases 1-5) prohibits UnityEngine imports. Additionally, Unity's HSV implementation may have normalization differences that would break pixel-perfect matching with the Python training pipeline.
**Impact**: Phase 6 should NOT replace this with Unity's built-in — the training data was generated with Python's algorithm, so any HSV divergence would silently degrade classifier accuracy.

### AC-014: IModelBackend Abstraction Instead of Direct Sentis Dependency
**Phase**: 5
**Change**: ClassifierManager defines `IModelBackend` and `IModelBackendFactory` interfaces rather than importing Unity Sentis directly. Phase 6 provides the concrete implementation.
**Rationale**: Keeps Phase 5 as pure C# per AC-002. Also enables unit testing with mock backends and fallback to placeholder predictions when Sentis is unavailable.
**Impact**: Phase 6 must implement `IModelBackendFactory` that creates Sentis-backed `IModelBackend` instances. The factory is passed to `ClassifierManager.Instance.Initialize(factory)`.

### AC-015: Typed Validation Methods Instead of Single Generic Validate()
**Phase**: 5
**Change**: Python's single `validate(discipline, interactive_ui)` with dynamic duck typing replaced by 5 typed methods: `ValidateSmithing(grid, size)`, `ValidateAdornments(vertices, shapes)`, `ValidateAlchemy(slots, tier)`, `ValidateRefining(core, surrounding, tier)`, `ValidateEngineering(slotsDict, tier)`.
**Rationale**: C# is statically typed — each discipline has fundamentally different input data structures. Typed methods provide compile-time safety, IDE autocomplete, and clearer API documentation.
**Impact**: Phase 6 UI components call the specific typed method for their discipline rather than a generic validate call.

### AC-016: Flat Float Arrays for Tensor Data
**Phase**: 5
**Change**: All preprocessor output uses flat `float[]` in row-major, channel-last layout (e.g., `float[3888]` for 36×36×3) rather than multidimensional arrays or custom tensor types.
**Rationale**: Matches ONNX tensor layout expected by Sentis. Avoids array-of-arrays overhead and simplifies index arithmetic.
**Impact**: Phase 6 Sentis backend can feed `float[]` directly to model input tensors without reshaping.

### AC-017: Math Helpers Shared Across Feature Extractors
**Phase**: 5
**Change**: `Mean()`, `Max()`, and `PopulationStdDev()` implemented as `internal static` methods in `AlchemyFeatureExtractor` and reused by `RefiningFeatureExtractor` and `EngineeringFeatureExtractor`, rather than creating a separate shared utility class.
**Rationale**: Only 3 methods needed, all within the same namespace. A separate utility file would be over-engineering for this scope.
**Impact**: If future phases need these math utilities elsewhere, consider extracting to a shared `MathHelpers` class.

---

## Phase 6 — Unity Integration (2026-02-13)

### AC-018: InputManager Inline Fallback Bindings
**Phase**: 6
**Change**: InputManager creates inline `InputAction` bindings as fallback when no `InputActionAsset` is assigned via Inspector — enables runtime testing without a pre-configured Unity asset.
**Rationale**: InputActionAssets are binary Unity Editor assets that cannot be created from code. Inline bindings provide a working default for all keybindings (WASD, E, Tab, M, J, C, K, 1-5, F1-F7).
**Impact**: When a proper InputActionAsset is assigned, it takes priority. The fallback is functionally equivalent.

### AC-019: MinigameUI Abstract MonoBehaviour Base (Separate from Phase 4 Base)
**Phase**: 6
**Change**: Phase 6 minigame UIs use their own abstract `MinigameUI : MonoBehaviour` base class rather than directly wrapping Phase 4's `BaseCraftingMinigame`. Phase 4's base handles game logic (difficulty, performance, rewards); Phase 6's base handles Unity rendering (timer UI, result display, canvas management, quality tier text).
**Rationale**: Phase 4's BaseCraftingMinigame is pure C# with no Unity dependencies. Phase 6 needs MonoBehaviour lifecycle, SerializeField bindings, and UI rendering — a different abstraction layer.
**Impact**: Each minigame has two layers: Phase 4 (game logic) and Phase 6 (rendering). Phase 6 minigame UIs call into Phase 4 logic for performance scoring and reward calculation.

### AC-020: ScriptableObject Configs for Visual Settings Only
**Phase**: 6
**Change**: Four ScriptableObject configurations created (`GameConfigAsset`, `CraftingConfigAsset`, `CombatConfigAsset`, `RenderingConfigAsset`) that store only visual/display settings (camera speed, damage number colors, tile colors, UI animation durations). No game balance values.
**Rationale**: Game balance (damage formulas, EXP curves, stat multipliers) must stay in Phase 1's `GameConfig` static class to preserve mechanical fidelity. ScriptableObjects are for Unity Inspector-tunable display settings only.
**Impact**: Artists/designers can adjust visual settings without touching game logic code.

---

## Convention Additions Discovered During Phase 6

| Date | Convention | Detail |
|------|-----------|--------|
| 2026-02-13 | Canvas sort order | HUD=0, Panels=10, Minigames=20, Overlay=30 |
| 2026-02-13 | Tooltip deferred rendering | TooltipRenderer renders in LateUpdate on Canvas sort order 100, fixing Python z-order bug |
| 2026-02-13 | DamageNumber pool size | 30 pre-instantiated objects, recycled via activation/deactivation |
| 2026-02-13 | Camera orientation | Orthographic top-down, Quaternion.Euler(90, 0, 0), XZ plane |
| 2026-02-13 | Day/night cycle | Dawn=0.20, Day=0.30, Dusk=0.75, Night=0.85 (as fraction of cycle) |

---

## Convention Additions Discovered During Phase 5

| Date | Convention | Detail |
|------|-----------|--------|
| 2026-02-13 | Population std dev | All standard deviation calculations use ÷N (population), not ÷(N-1) (sample), matching numpy.std default |
| 2026-02-13 | Tensor layout | Flat float[] in row-major, channel-last order for all ML preprocessing output |
| 2026-02-13 | Feature order is sacred | LightGBM feature indices MUST match Python training order exactly — models silently fail otherwise |
| 2026-02-13 | Classifier threshold | Default 0.5f for all disciplines, configurable via ClassifierManager.UpdateConfig() |

---

## Convention Additions Discovered During Phase 4

| Date | Convention | Detail |
|------|-----------|--------|
| 2026-02-13 | StatusEffectManager location | StatusEffectManager lives in Game1.Entities namespace alongside StatusEffect, not in Systems |
| 2026-02-13 | MinigameInput abstraction | All minigame input goes through MinigameInput class (type + value + index) |
| 2026-02-13 | ActiveBuff model | ActiveBuff lives in Game1.Entities.Components.BuffManager with fields: BuffId, BuffType, Value, Duration, RemainingDuration, Source |
| 2026-02-13 | DeathChest model | DeathChest is defined in WorldSystem.cs (not a separate file) |

---

## Phase 7 — Polish & LLM Stub (2026-02-14)

### AC-021: NotificationSystem as Pure C# Singleton (Not MonoBehaviour)
**Phase**: 7
**Change**: The Phase 7 plan specified `NotificationSystem : MonoBehaviour`. Implemented as a pure C# singleton instead.
**Rationale**: AC-002 (pure C# for game logic) applies. Phase 6's `NotificationUI` MonoBehaviour already handles rendering. Adding another MonoBehaviour would create duplicate responsibility.
**Impact**: NotificationSystem provides the typed API (NotificationType enum, queue management, filtering). Phase 6 NotificationUI handles on-screen rendering. Connected via `OnNotificationShow` event.

### AC-022: NotificationSystem Decoupled from NotificationUI
**Phase**: 7
**Change**: Rather than replacing Phase 6's `NotificationUI`, created a parallel pure C# system with an `OnNotificationShow` event bridge.
**Rationale**: Don't break working Phase 6 code. The existing `NotificationUI.Show(string, Color, float)` API works. Phase 7 adds typed notifications, queue management, and debug filtering on top.
**Integration**: `NotificationUI` subscribes to `NotificationSystem.OnNotificationShow` and calls its own `Show()` method, bridging the two systems.

### AC-023: LoadingState Injectable Time Provider
**Phase**: 7
**Change**: Added `Func<float> timeProvider` constructor parameter to `LoadingState` for deterministic testing.
**Rationale**: Without this, animation formula tests (`GetAnimatedProgress()`) would depend on wall-clock time and be non-deterministic. Default uses `Environment.TickCount / 1000f` (pure C#, no Unity dependency).
**Impact**: Production code passes no argument (uses default). Tests pass a controllable clock: `float time = 0; var state = new LoadingState(() => time);`.

### AC-024: E2E Tests as Pure C# (Not Unity PlayMode)
**Phase**: 7
**Change**: The Phase 7 plan specified `[UnityTest]` coroutines with `SceneManager.LoadScene("TestScene")`. Implemented as pure C# test classes instead.
**Rationale**: No Unity scene is assembled yet — scene assembly is a post-migration task. Pure C# tests can verify game formulas, state machines, and data flow immediately. They exercise the same Phase 1-5 game logic that Unity will render.
**Impact**: Tests verify logic correctness. Visual correctness tests (sprite positions, UI layout) should be written during scene assembly as Unity PlayMode tests.

### AC-025: Stub Categories Aligned to Python Logic
**Phase**: 7
**Change**: The Phase 7 plan mapped `engineering → "device"` and `enchanting → "enchantment"`. Changed to `engineering → "equipment"` and `enchanting → "equipment"`.
**Rationale**: Python's `_add_invented_item_to_game()` (game_engine.py lines 3698-3805) produces equipment-category items for both engineering (turrets with EquipmentItem stats) and enchanting (accessories). Using `"device"` or `"enchantment"` would bypass the inventory/equipment code path that real items use.
**Impact**: Stub items flow through the same `EquipmentDatabase`/`Inventory` pipeline as real items.

---

## Convention Additions Discovered During Phase 7

| Date | Convention | Detail |
|------|-----------|--------|
| 2026-02-14 | LLM namespace | All LLM-related code in `Game1.Systems.LLM` namespace |
| 2026-02-14 | Stub item ID format | `invented_{discipline}_{placementHash}` — deterministic, cacheable |
| 2026-02-14 | Quality prefix thresholds | Common(≤4), Uncommon(≤10), Rare(≤20), Epic(≤40), Legendary(41+) — matches DifficultyCalculator |
| 2026-02-14 | Debug notification prefix | `[STUB]` for stub invocations, `[NOT IMPL]` for unimplemented features |
| 2026-02-14 | Test pattern | Simple assert-based framework (no NUnit/Unity Test Runner dependency) matching Phase 5 |

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total C# files created | 147 |
| Total lines of C# | ~34,700 |
| Phase 7 LLM stub/notification files | 6 |
| Phase 7 test files | 5 |
| Phase 6 Unity Integration files | 45 |
| Phase 5 Classifier files | 10 |
| Phase 4 Game System files | 40 |
| Foundation prerequisite files | 32 |
| Adaptive changes documented | 25 |
| Architecture improvements applied | 7 (MACRO-1,3,6; FIX-4; dispatch table; IPathfinder; IItemGenerator) |
| Total tests (all phases) | 145+ |
