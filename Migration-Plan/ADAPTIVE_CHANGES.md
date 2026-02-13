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

## Convention Additions Discovered During Phase 4

| Date | Convention | Detail |
|------|-----------|--------|
| 2026-02-13 | StatusEffectManager location | StatusEffectManager lives in Game1.Entities namespace alongside StatusEffect, not in Systems |
| 2026-02-13 | MinigameInput abstraction | All minigame input goes through MinigameInput class (type + value + index) |
| 2026-02-13 | ActiveBuff model | ActiveBuff lives in Game1.Entities.Components.BuffManager with fields: BuffId, BuffType, Value, Duration, RemainingDuration, Source |
| 2026-02-13 | DeathChest model | DeathChest is defined in WorldSystem.cs (not a separate file) |

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total C# files created | 72 |
| Total lines of C# | 21,796 |
| Phase 4 Game System files | 40 |
| Foundation prerequisite files | 32 |
| Adaptive changes documented | 12 |
| Architecture improvements applied | 6 (MACRO-1,3,6; FIX-4; dispatch table; IPathfinder) |
