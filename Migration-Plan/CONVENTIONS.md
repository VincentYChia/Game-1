# Migration Conventions & Standards

**Purpose**: Single source of truth for all cross-phase conventions. Every phase MUST follow these rules.
**Rule**: If a convention here conflicts with a phase document, THIS document wins.

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
- [ ] Code follows CONVENTIONS.md
- [ ] File headers present on all new files
- [ ] No `TODO` or `HACK` comments without linked issue
- [ ] JSON files unchanged (byte-identical to Python source)
