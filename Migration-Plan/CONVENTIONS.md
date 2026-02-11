# Migration Conventions & Standards

**Purpose**: Single source of truth for all cross-phase conventions. Every phase MUST follow these rules.
**Rule**: If a convention here conflicts with a phase document, THIS document wins.
**Living Document**: This file grows during migration. When you discover a new pattern, naming decision, or lesson learned, ADD IT HERE. Future phases inherit all conventions from earlier phases.

### How to Update This Document
When migrating code, if you encounter a decision that affects multiple files:
1. Make the decision
2. Document it here under the appropriate section (or create a new section)
3. Add a `[Phase N]` tag so readers know when it was established
4. Reference the specific Python source that motivated the decision

### Cross-References
- **IMPROVEMENTS.md** — Architectural improvements to apply during migration (macro changes + per-file fixes)
- **PHASE_CONTRACTS.md** — What each phase receives and delivers
- **reference/PYTHON_TO_CSHARP.md** — Language-level conversion patterns
- **reference/UNITY_PRIMER.md** — Unity concepts for C# developers

---

## 0. Improvement Philosophy

This migration is a REWRITE, not a blind port. We preserve:
- All game mechanics exactly (formulas, constants, behavior)
- All JSON schemas and file structures (moddability)
- All game content (items, recipes, skills, enemies)

We improve:
- Architecture (event-driven decoupling, no circular dependencies)
- Type safety (enums replace magic strings, strong typing)
- Efficiency (caching, pre-computation, single-source-of-truth data)
- Testability (no side effects in constructors, injectable dependencies)
- Robustness (save migration pipeline, proper error handling)

See `IMPROVEMENTS.md` for the full list of macro architecture changes and per-file fixes.

---

## 1. C# Naming Conventions

### Code Naming
| Element | Convention | Example |
|---------|-----------|---------|
| Namespace | PascalCase, prefixed `Game1.` | `Game1.Data.Models` |
| Class | PascalCase | `MaterialDefinition` |
| Interface | PascalCase with `I` prefix | `IItemGenerator` |
| Public method | PascalCase | `GetMaterial()` |
| Private method | camelCase with `_` prefix | `_calculateDamage()` |
| Public property | PascalCase | `MaterialId { get; set; }` |
| Private field | camelCase with `_` prefix | `_instance` |
| Constant | PascalCase | `MaxLevel = 30` |
| Enum value | PascalCase | `DamageType.Fire` |
| Local variable | camelCase | `float baseDamage` |
| Parameter | camelCase | `string materialId` |
| Unity SerializeField | camelCase with `_` prefix | `[SerializeField] int _chunkSize` |

### JSON Field Naming
All JSON files use **camelCase** (e.g., `materialId`, `stationTier`, `effectParams`).
C# properties use **PascalCase** with `[JsonProperty("camelCase")]` attributes.

```csharp
[JsonProperty("materialId")]
public string MaterialId { get; set; }

[JsonProperty("stationTier")]
public int StationTier { get; set; }
```

### File Naming
| Type | Convention | Example |
|------|-----------|---------|
| C# source | PascalCase.cs | `MaterialDefinition.cs` |
| Test file | PascalCase + Tests.cs | `MaterialDefinitionTests.cs` |
| JSON data | kebab-case-N.JSON | `items-materials-1.JSON` |
| Namespace folder | PascalCase | `Game1.Data/Models/` |

---

## 2. Namespace Hierarchy

```
Game1.Core              # GameManager, Config, MigrationLogger, GamePaths
Game1.Data.Models       # All data classes (MaterialDefinition, EquipmentItem, etc.)
Game1.Data.Databases    # All singleton database loaders
Game1.Data.Enums        # All enums (DamageType, Rarity, TileType, etc.)
Game1.Entities          # Character, Enemy
Game1.Entities.Components  # Stats, Inventory, Equipment, Skills, Buffs, Leveling
Game1.Systems.Tags      # TagRegistry, TagParser, EffectContext
Game1.Systems.Effects   # EffectExecutor, TargetFinder, MathUtils
Game1.Systems.Combat    # CombatManager, AttackEffects, TurretSystem
Game1.Systems.Crafting  # All 6 minigames, DifficultyCalculator, RewardCalculator
Game1.Systems.World     # WorldSystem, BiomeGenerator, Chunk, CollisionSystem
Game1.Systems.ML        # ClassifierManager, all preprocessors
Game1.Systems.LLM       # IItemGenerator, StubItemGenerator
Game1.Systems.Save      # SaveManager
Game1.Systems.Progression  # TitleSystem, ClassSystem, QuestSystem, SkillUnlockSystem
Game1.Systems.Items     # PotionSystem
Game1.UI                # All MonoBehaviour UI components
Game1.UI.Crafting       # Minigame UIs
Game1.UI.Combat         # Combat HUD
```

**Rule**: Every `.cs` file MUST have exactly one `namespace` declaration matching the folder path.

---

## 3. Singleton Pattern (Unified)

ALL database singletons MUST use this exact pattern:

```csharp
namespace Game1.Data.Databases
{
    public class MaterialDatabase
    {
        private static MaterialDatabase _instance;
        private static readonly object _lock = new object();

        public static MaterialDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new MaterialDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private MaterialDatabase() { }

        /// <summary>
        /// Reset singleton for testing only. Never call in production.
        /// </summary>
        public static void ResetInstance()
        {
            lock (_lock)
            {
                _instance = null;
            }
        }

        public bool Loaded { get; private set; }

        // ... methods ...
    }
}
```

**Rules**:
- Thread-safe double-checked locking
- `ResetInstance()` for test teardown only
- `Loaded` property to check initialization state
- Private constructor prevents external instantiation

---

## 4. JSON Loading Pattern (Unified)

ALL JSON loading MUST use this pattern:

```csharp
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using System.IO;
using UnityEngine;

namespace Game1.Core
{
    public static class JsonLoader
    {
        /// <summary>
        /// Base path for all JSON content files.
        /// StreamingAssets allows runtime editing (moddability).
        /// </summary>
        public static string ContentPath =>
            Path.Combine(Application.streamingAssetsPath, "Content");

        /// <summary>
        /// Load and deserialize a JSON file.
        /// </summary>
        /// <typeparam name="T">Target type</typeparam>
        /// <param name="relativePath">Path relative to Content/ (e.g., "items.JSON/items-materials-1.JSON")</param>
        /// <returns>Deserialized object, or default(T) on failure</returns>
        public static T Load<T>(string relativePath)
        {
            string fullPath = Path.Combine(ContentPath, relativePath);

            if (!File.Exists(fullPath))
            {
                Debug.LogWarning($"[JsonLoader] File not found: {fullPath}");
                return default;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                return JsonConvert.DeserializeObject<T>(json, Settings);
            }
            catch (JsonException ex)
            {
                Debug.LogError($"[JsonLoader] Parse error in {relativePath}: {ex.Message}");
                return default;
            }
        }

        /// <summary>
        /// Load a JSON file as a JObject for dynamic access.
        /// </summary>
        public static JObject LoadDynamic(string relativePath)
        {
            string fullPath = Path.Combine(ContentPath, relativePath);

            if (!File.Exists(fullPath))
            {
                Debug.LogWarning($"[JsonLoader] File not found: {fullPath}");
                return null;
            }

            string json = File.ReadAllText(fullPath);
            return JObject.Parse(json);
        }

        private static readonly JsonSerializerSettings Settings = new()
        {
            NullValueHandling = NullValueHandling.Ignore,
            MissingMemberHandling = MissingMemberHandling.Ignore,
            FloatParseHandling = FloatParseHandling.Double
        };
    }
}
```

**Rules**:
- ALL JSON files live under `StreamingAssets/Content/` (moddable, not compiled)
- Use `Newtonsoft.Json` (NOT `JsonUtility` — it can't handle Dictionary, polymorphism, etc.)
- Relative paths from Content root (e.g., `"items.JSON/items-materials-1.JSON"`)
- Always handle missing files gracefully (warning, not crash)
- Always handle malformed JSON gracefully (error log, not crash)

---

## 5. Error Handling Strategy

### Categories

| Error Type | Response | Example |
|------------|----------|---------|
| **Missing JSON file** | Log warning, use fallback placeholders | `items-materials-1.JSON` not found |
| **Malformed JSON** | Log error, use fallback placeholders | Invalid JSON syntax |
| **Missing field in JSON** | Use default value, log info | Recipe missing `stationTier` → default 1 |
| **Invalid value range** | Clamp to valid range, log warning | `tier: 7` → clamped to 4 |
| **Missing database reference** | Return null/empty, log warning | `GetMaterial("nonexistent")` → null |
| **Runtime exception** | Catch, log error, continue game loop | Division by zero in damage calc |

### Error Handling Code Pattern

```csharp
// GOOD - Game continues, error logged
public MaterialDefinition GetMaterial(string materialId)
{
    if (string.IsNullOrEmpty(materialId))
    {
        Debug.LogWarning("[MaterialDatabase] GetMaterial called with null/empty ID");
        return null;
    }

    if (_materials.TryGetValue(materialId, out var material))
        return material;

    Debug.LogWarning($"[MaterialDatabase] Material not found: {materialId}");
    return null;
}

// BAD - Game crashes
public MaterialDefinition GetMaterial(string materialId)
{
    return _materials[materialId]; // KeyNotFoundException crashes game
}
```

### Log Format
All log messages MUST follow: `[ClassName] Description`
```csharp
Debug.Log("[MaterialDatabase] Loaded 57 materials");
Debug.LogWarning("[MaterialDatabase] Material not found: mythril_ore");
Debug.LogError("[MaterialDatabase] Failed to parse items-materials-1.JSON: ...");
```

---

## 6. Validation Rules

### Data Model Validation

All data models validate in their constructors or `Load()` methods:

| Field | Valid Range | On Invalid |
|-------|------------|------------|
| `tier` | 1–4 | Clamp: `Mathf.Clamp(tier, 1, 4)` |
| `level` | 1–30 | Clamp: `Mathf.Clamp(level, 1, 30)` |
| `durability_current` | 0–durability_max | Clamp: `Mathf.Clamp(current, 0, max)` |
| `stat` (STR, DEF, etc.) | 0–30 | Clamp: `Mathf.Clamp(stat, 0, 30)` |
| `probability` | 0.0–1.0 | Clamp: `Mathf.Clamp01(prob)` |
| `damage (min, max)` | min >= 0, max >= min | If max < min, swap |
| `rarity` | Known enum value | Default to `Rarity.Common` |
| `item_id` | Non-null, non-empty | Log warning, skip record |

### Probability Normalization

When loading probability distributions (biome weights, danger zones, etc.), if values don't sum to 1.0, normalize:

```csharp
public static void NormalizeProbabilities(ref float a, ref float b, ref float c)
{
    float sum = a + b + c;
    if (sum <= 0f)
    {
        a = b = c = 1f / 3f; // Equal distribution fallback
        return;
    }
    a /= sum;
    b /= sum;
    c /= sum;
}
```

---

## 7. Testing Conventions

### Test File Location
```
Assets/Tests/
├── EditMode/                    # Unit tests (no scene, no MonoBehaviours)
│   ├── Game1.Data.Models/       # Model tests
│   ├── Game1.Data.Databases/    # Database loading tests
│   ├── Game1.Systems.Combat/    # Damage formula tests
│   ├── Game1.Systems.Crafting/  # Minigame formula tests
│   ├── Game1.Systems.Tags/      # Tag system tests
│   └── Game1.Systems.ML/        # Preprocessor tests
└── PlayMode/                    # Integration tests (require scene)
    ├── Game1.Integration/       # Cross-system tests
    └── Game1.E2E/               # Full game flow tests
```

### Test Naming Convention
```csharp
[Test]
public void MethodName_Scenario_ExpectedResult()
{
    // Arrange
    // Act
    // Assert
}

// Examples:
public void CalculateDamage_WithStrength10_Returns45()
public void GetMaterial_WithInvalidId_ReturnsNull()
public void SmithingPreprocessor_MatchesGoldenFile_WithinTolerance()
```

### Required Test Coverage Per Phase
| Phase | Minimum Unit Tests | Coverage Target |
|-------|-------------------|-----------------|
| Phase 1 (Models) | 80+ | 100% of public methods |
| Phase 2 (Databases) | 60+ | 100% of load + query methods |
| Phase 3 (Entities) | 50+ | 90% of component logic |
| Phase 4 (Systems) | 100+ | 100% of formulas, 90% of logic |
| Phase 5 (ML) | 40+ | 100% of preprocessing |
| Phase 6 (Unity) | 30+ | Key integration points |
| Phase 7 (Stub + E2E) | 20+ | All E2E scenarios |

---

## 8. File Header Template

Every C# file MUST begin with this header:

```csharp
// ============================================================================
// Game1.<Namespace>.<ClassName>
// Migrated from: <python_file_path> (lines <start>-<end>)
// Migration phase: <phase_number>
// Date: <YYYY-MM-DD>
// ============================================================================
```

Example:
```csharp
// ============================================================================
// Game1.Data.Models.MaterialDefinition
// Migrated from: data/models/materials.py (lines 1-68)
// Migration phase: 1
// Date: 2026-02-15
// ============================================================================
```

---

## 9. JSON File Organization in Unity

```
StreamingAssets/Content/           ← EXACT same structure as Python
├── items.JSON/
│   ├── items-materials-1.JSON     ← File names preserved exactly
│   ├── items-smithing-2.JSON
│   ├── items-alchemy-1.JSON
│   ├── items-refining-1.JSON
│   ├── items-engineering-1.JSON
│   └── items-tools-1.JSON
├── recipes.JSON/
│   ├── recipes-smithing-3.json
│   ├── recipes-alchemy-1.JSON
│   ├── recipes-refining-1.JSON
│   ├── recipes-engineering-1.JSON
│   ├── recipes-enchanting-1.JSON
│   └── recipes-adornments-1.json
├── placements.JSON/
│   ├── placements-smithing-1.json
│   ├── placements-alchemy-1.JSON
│   ├── placements-refining-1.JSON
│   ├── placements-engineering-1.JSON
│   └── placements-adornments-1.JSON
├── Skills/
│   ├── skills-skills-1.JSON
│   └── skills-base-effects-1.JSON
├── Definitions.JSON/
│   ├── tag-definitions.JSON
│   ├── hostiles-1.JSON
│   ├── resource-node-1.JSON
│   ├── crafting-stations-1.JSON
│   ├── world_generation.JSON
│   ├── stats-calculations.JSON
│   ├── combat-config.JSON
│   ├── dungeon-config-1.JSON
│   ├── map-waypoint-config.JSON
│   ├── fishing-config.JSON
│   ├── Chunk-templates-2.JSON
│   ├── skills-translation-table.JSON
│   └── value-translation-table-1.JSON
└── progression/
    ├── classes-1.JSON
    ├── titles-1.JSON
    ├── npcs-enhanced.JSON
    ├── quests-enhanced.JSON
    └── skill-unlocks.JSON
```

**Rule**: File names, directory structure, and JSON schemas are IDENTICAL to Python. Do not rename, restructure, or modify JSON content during migration.

---

## 10. Git Conventions for Migration

### Branch Naming
```
migration/phase-1-foundation
migration/phase-2-data-layer
migration/phase-3-entities
migration/phase-4-game-systems
migration/phase-5-ml
migration/phase-6-unity
migration/phase-7-polish
```

### Commit Message Format
```
phase-N: Brief description of change

Migrated from: <python_file_path>
Tests: <pass/fail count>
```

Example:
```
phase-1: Port MaterialDefinition data model

Migrated from: data/models/materials.py
Tests: 12/12 passing
```

### Pull Request Checklist
Before merging any phase branch:
- [ ] All unit tests pass
- [ ] All integration tests pass (if applicable)
- [ ] Code follows CONVENTIONS.md (this file)
- [ ] File headers present on all new files
- [ ] No `TODO` or `HACK` comments without linked issue
- [ ] JSON files unchanged (byte-identical to Python source)
- [ ] Any applicable improvements from IMPROVEMENTS.md applied
- [ ] New conventions documented in this file (if any discovered)

---

## 11. Architecture Improvement Patterns

These patterns are applied DURING migration, not after. See `IMPROVEMENTS.md` for the full list.

### 11.1 Event-Driven Decoupling [MACRO-1]

Components emit events instead of calling parent methods directly.

```csharp
// WRONG: Component reaches up to parent
public void Equip(EquipmentItem item, Character character)
{
    _slots[slot] = item;
    character.RecalculateStats();  // Circular dependency!
}

// RIGHT: Component emits event, parent subscribes
public void Equip(EquipmentItem item)
{
    _slots[slot] = item;
    GameEvents.RaiseEquipmentChanged(item, slot);  // Decoupled
}
```

### 11.2 Factory Methods over Constructor Side Effects [FIX-1]

Constructors take only primitive data. Database lookups happen in factory methods.

```csharp
// WRONG: Constructor has side effects
public ItemStack(string itemId, int qty)
{
    var mat = MaterialDatabase.Instance.GetMaterial(itemId);  // Breaks in tests!
    MaxStack = mat?.MaxStack ?? 99;
}

// RIGHT: Constructor is pure, factory has side effects
public ItemStack(string itemId, int qty, int maxStack = 99) { /* pure */ }

public static ItemStack CreateFromDatabase(string itemId, int qty)
{
    var mat = MaterialDatabase.Instance.GetMaterial(itemId);
    return new ItemStack(itemId, qty, mat?.MaxStack ?? 99);
}
```

### 11.3 Single Source of Truth for Derived Data [FIX-6]

Never store the same value in two places. Compute from the canonical source.

```csharp
// WRONG: Rarity on both ItemStack and EquipmentItem
public class ItemStack
{
    public string Rarity { get; set; }              // Stored here
    public EquipmentItem EquipmentData { get; set; } // Also has .Rarity
}

// RIGHT: Computed from canonical source
public class ItemStack
{
    public string Rarity => EquipmentData?.Rarity ?? _baseRarity;
    private string _baseRarity;
}
```

### 11.4 Serialization on the Model [FIX-2]

Models own their serialization. SaveManager calls `ToDict()`/`FromDict()`, never accesses fields directly.

```csharp
// WRONG: SaveManager knows internal structure of EquipmentItem
saveData["item_id"] = item.ItemId;
saveData["name"] = item.Name;
// ... 20 more lines repeated in 3 places

// RIGHT: Model owns serialization
saveData["equipment"] = item.ToDict();
// ... and deserialization
var item = EquipmentItem.FromDict(saveData["equipment"]);
```

### 11.5 Enum over Magic String [MACRO-2]

Every repeated string literal that represents a fixed set of values becomes an enum.

```csharp
// WRONG: Strings everywhere
if (item.HandType == "2H") ...
slots["mainHand"] = item;

// RIGHT: Enums with JSON compatibility
if (item.HandType == HandType.TwoHanded) ...
slots[EquipmentSlot.MainHand] = item;
```

### 11.6 When to Improve vs When to Port Exactly

| Situation | Action |
|-----------|--------|
| Formula or constant | Port EXACTLY. Do not adjust, optimize, or "fix" balance. |
| Algorithm producing game-visible results | Port EXACTLY. Same inputs must produce same outputs. |
| Internal architecture (how code is organized) | IMPROVE. Use patterns above. |
| Type safety (strings → enums) | IMPROVE. Compile-time safety is always better. |
| Performance (caching, pre-computation) | IMPROVE where flagged in IMPROVEMENTS.md. |
| Data structure (how state is stored) | IMPROVE for single-source-of-truth. |
| ML preprocessing | Port EXACTLY. Model compatibility requires bit-identical preprocessing. |
| JSON schemas | Do NOT change. Moddability and save compatibility depend on stability. |

---

## 12. 3D Readiness Conventions

All code MUST follow these rules to ensure the architecture supports future 3D upgrades without logic rewrites.

### 12.1 Position Convention

```csharp
// ALWAYS use GamePosition or Vector3. NEVER use (float, float) tuples.
// WRONG:
float distance = Mathf.Sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1));

// RIGHT:
float distance = TargetFinder.GetDistance(posA, posB);
```

### 12.2 Distance Convention

```csharp
// ALWAYS use TargetFinder.GetDistance(). It respects the current distance mode.
// For initial 2D migration, this uses HorizontalDistanceTo() (XZ plane).
// When 3D is enabled, it switches to full Vector3.Distance().

// WRONG: Inline distance calculation
if (Vector3.Distance(a, b) < 5f) { ... }

// RIGHT: Centralized distance
if (TargetFinder.GetDistance(a, b) < GameConfig.MeleeRange) { ... }
```

### 12.3 World Coordinate Convention

```csharp
// Tile coordinates → world coordinates conversion ALWAYS goes through WorldSystem
// WRONG: Manual conversion
Vector3 worldPos = new Vector3(tileX * 32, 0, tileY * 32);

// RIGHT: Centralized conversion
Vector3 worldPos = WorldSystem.Instance.TileToWorld(tileX, tileY);
```

### 12.4 Height Default

All positions default to `Y = 0` (ground level). Height is only set when explicitly needed (flying enemies, terrain elevation, dungeon floors). Never assume `Y == 0` — always use `GamePosition.HorizontalDistanceTo()` when height should be ignored.

---

## 13. Item Type Hierarchy Convention [MACRO — Part 4]

### 13.1 All Items Implement IGameItem

Every item type (materials, equipment, consumables, placeables) implements `IGameItem`. This provides:
- Unified serialization (`ToSaveData()` / `FromSaveData()`)
- Type-safe inventory operations
- Single `Rarity` source of truth
- Polymorphic behavior without `hasattr` / `isinstance` checks

### 13.2 Item Creation Goes Through ItemFactory

```csharp
// WRONG: Direct constructor with database lookup side effects
var stack = new ItemStack("iron_sword", 1); // calls EquipmentDatabase in constructor

// RIGHT: Factory method
var item = ItemFactory.CreateFromId("iron_sword");
var stack = new ItemStack(item, 1);
```

### 13.3 Type Checking Uses Pattern Matching

```csharp
// WRONG: String-based type checks
if (item.Category == "equipment") { ... }

// RIGHT: C# pattern matching
if (stack.Item is EquipmentItem equip)
{
    float effectiveness = equip.GetEffectiveness();
}
```

---

## 14. Changelog (Living Document Updates)

Record every convention addition or change here with date and phase.

| Date | Phase | Change | Reason |
|------|-------|--------|--------|
| 2026-02-10 | Planning | Created CONVENTIONS.md | Centralize cross-phase rules |
| 2026-02-11 | Planning | Added §0 Improvement Philosophy | Define improve-vs-port boundaries |
| 2026-02-11 | Planning | Added §11 Architecture Improvement Patterns | Document reusable patterns from IMPROVEMENTS.md |
| 2026-02-11 | Planning | Added §12 Changelog | Make this a living document |
| 2026-02-11 | Planning | Added §12 3D Readiness Conventions | Ensure architecture supports future 3D upgrades |
| 2026-02-11 | Planning | Added §13 Item Type Hierarchy Convention | IGameItem interface, ItemFactory, pattern matching |
| | | *(Add entries as migration progresses)* | |
