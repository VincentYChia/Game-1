# Migration Adaptive Changes Tracker
# Tracks all deviations from the plan so downstream phases can account for them.
# Updated after each phase completion.

## Phase 1: Foundation (32 files, 3,385 LOC)

### AC-1.1: UnlockCondition.Evaluate() uses `object` parameter
- **Plan**: `Evaluate(ICharacterState character)`
- **Actual**: `Evaluate(object characterContext)` returning `false` (stub)
- **Reason**: ICharacterState interface exists but cannot be meaningfully implemented until Phase 3 Character class. Using object avoids forcing a fake implementation.
- **Impact on Phase 3**: When Character implements ICharacterState, all 8 UnlockCondition subclasses need Evaluate() updated to cast and use the interface. Pattern: `if (characterContext is ICharacterState state) { ... }`
- **Risk**: LOW - contained to UnlockConditions.cs

### AC-1.2: SkillUnlock methods use `object` parameter
- **Plan**: Separate `ICharacterState`/`ICharacterEconomy` parameters
- **Actual**: Single `object character` parameter with stubs
- **Reason**: Same as AC-1.1. Both interfaces exist but Character doesn't implement them yet.
- **Impact on Phase 3**: SkillUnlock.CanUnlock/Unlock need parameter types changed to use interfaces.
- **Risk**: LOW - contained to SkillUnlocks.cs

### AC-1.3: EquipmentItem.Damage stored as `int[]` not value tuple
- **Plan**: Suggests typed DamageRange or value tuple
- **Actual**: `int[] Damage` with helper properties `DamageMin`/`DamageMax`
- **Reason**: JSON deserialization with Newtonsoft.Json handles arrays natively. Value tuples require custom converters.
- **Impact on Phase 2+**: Database loading will deserialize damage as arrays naturally. No conversion needed.
- **Risk**: NONE - helper properties provide clean access

### AC-1.4: WorldTile.GetColor() uses hardcoded defaults
- **Plan**: Accept `IColorConfig` parameter
- **Actual**: Hardcoded color values matching Python Config class
- **Reason**: Colors are compile-time constants in Python (Config class). No runtime variation.
- **Impact on Phase 6**: If Unity needs different color sources, GetColor() can accept optional parameter then.
- **Risk**: NONE - colors match source exactly

### AC-1.5: IGameItem explicit interface implementation on EquipmentItem
- **Plan**: EquipmentItem directly implements IGameItem properties
- **Actual**: Uses explicit interface implementation (`string IGameItem.Category => "equipment"`) to avoid property name conflicts with existing JSON-mapped properties
- **Reason**: EquipmentItem already has `ItemId`, `Name`, `Tier`, `Rarity` as JSON properties. Explicit implementation avoids ambiguity.
- **Impact on Phase 3**: When accessing via IGameItem interface, cast is needed. When accessing directly, original properties work.
- **Risk**: LOW - standard C# pattern

## Phase 2: Data Layer (18 files, 4,410 LOC)

### AC-2.1: EquipmentDatabase stores raw JObject instead of Dict
- **Plan**: Store equipment data as `Dictionary<string, Dict>` (matching Python)
- **Actual**: Store as `Dictionary<string, JObject>` for direct Newtonsoft.Json interop
- **Reason**: JObject preserves JSON structure and supports nested access more naturally in C#. Avoids lossy conversion to Dictionary<string, object>.
- **Impact on Phase 3**: When creating EquipmentItem instances, access data via JObject API (`Value<T>()`) instead of dictionary access.
- **Risk**: NONE - JObject is richer than Dict, no data loss

### AC-2.2: EquipmentDatabase slot determination inlined (no SmithingTagProcessor)
- **Plan**: Python uses `SmithingTagProcessor.get_equipment_slot(tags)` for tag-based slot resolution
- **Actual**: Inlined `GetSlotFromTags()` method directly in EquipmentDatabase
- **Reason**: SmithingTagProcessor is a Phase 4 crafting system class. Cannot import it in Phase 2 without circular dependency. The slot resolution logic is simple enough to inline.
- **Impact on Phase 4**: When SmithingTagProcessor is ported, verify its slot resolution matches our inline version. Consider delegating to shared utility.
- **Risk**: LOW - logic is straightforward string matching

### AC-2.3: RecipeDatabase.LoadFile exposed as private (not internal)
- **Plan**: Python's `_load_file()` is called directly by UpdateLoader
- **Actual**: `LoadFile()` is private. UpdateLoader recipe updates deferred.
- **Reason**: Exposing internal loading methods breaks encapsulation. Recipe updates need station-type detection logic that should live in RecipeDatabase.
- **Impact on Phase 4**: When crafting system is complete, add public `LoadUpdateRecipes(filepath)` method.
- **Risk**: LOW - update recipe loading is rare

### AC-2.4: ConditionFactory.CreateRequirementsFromJson JObject overload added
- **Plan**: Phase 1 ConditionFactory only accepts `Dictionary<string, object>`
- **Actual**: Added JObject overload that converts to Dictionary and delegates
- **Reason**: Phase 2 databases parse JSON with JObject directly. Avoids repetitive conversion at every call site.
- **Impact on Phase 3+**: Both overloads available. Use whichever is convenient.
- **Risk**: NONE - additive change, original method unchanged

### AC-2.5: GameConfig uses color tuples instead of Color32
- **Plan**: Use `UnityEngine.Color32` for all colors
- **Actual**: Uses `(int R, int G, int B, int A)` value tuples
- **Reason**: Phase 2 is plain C# (no UnityEngine dependency). Color32 is a Unity type.
- **Impact on Phase 6**: Phase 6 will need helper methods or implicit conversion from tuple to Color32. Consider a `GameConfig.ToColor32()` utility.
- **Risk**: NONE - trivial conversion in Phase 6

### AC-2.6: GamePaths uses reflection for Unity path detection
- **Plan**: Direct `Application.streamingAssetsPath` access
- **Actual**: Reflection-based detection of Unity APIs, fallback to current directory
- **Reason**: Phase 2 must compile without UnityEngine.dll. Reflection allows runtime detection.
- **Impact on Phase 6**: Phase 6 MonoBehaviour will call `SetBasePath()` / `SetSavePath()` explicitly, bypassing reflection.
- **Risk**: NONE - Phase 6 overrides reflection path

### AC-2.7: WorldGenerationConfig nested classes are separate (not inner classes)
- **Plan**: Python uses `@dataclass` nested within `WorldGenerationConfig`
- **Actual**: All config classes (BiomeDistributionConfig, DangerDistribution, etc.) are top-level classes in same file
- **Reason**: C# best practice - top-level classes are easier to reference and test. Same namespace provides logical grouping.
- **Impact on Phase 4**: Access via full class name (same either way since they're in same namespace).
- **Risk**: NONE - organizational only

## Phase 3: Entity Layer
(To be updated after Phase 3 completion)
