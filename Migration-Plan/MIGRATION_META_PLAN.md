# Game-1 Migration Meta-Plan
## Python/Pygame → Unity/C# Migration Planning Guide

**Version**: 1.0
**Created**: 2026-02-09
**Purpose**: Define methodology for creating a comprehensive, production-ready migration plan

---

## Table of Contents

1. [Philosophy & Goals](#1-philosophy--goals)
2. [Current Reality Assessment](#2-current-reality-assessment)
3. [Migration Principles](#3-migration-principles)
4. [Validation Strategy](#4-validation-strategy)
5. [Plan Document Structure](#5-plan-document-structure)
6. [System Migration Order](#6-system-migration-order)
7. [ML Classifier Migration](#7-ml-classifier-migration)
8. [LLM System Stub Strategy](#8-llm-system-stub-strategy)
9. [Planning Process Timeline](#9-planning-process-timeline)
10. [Checklists & Quality Gates](#10-checklists--quality-gates)

---

## 1. Philosophy & Goals

### 1.1 Project Philosophy

Game-1 is a **crafting RPG prototype** built to validate core gameplay mechanics before investing in 3D development. The Python/Pygame version has successfully proven:

- **Core game loop** (gather → craft → equip → fight → progress)
- **5 crafting disciplines** with unique minigames
- **Tag-driven combat system** (190+ composable tags)
- **ML-validated recipe discovery** (CNN + LightGBM classifiers)
- **Procedural content generation** (LLM-created items)

The migration to Unity is not merely a port—it's an **evolution** that enables:
- Professional-grade 3D graphics
- Better performance and platform support
- Industry-standard tooling
- Streamlined, maintainable architecture

### 1.2 Migration Goals

| Priority | Goal | Rationale |
|----------|------|-----------|
| **P0** | Preserve game mechanics exactly | Years of balancing in Python must not be lost |
| **P1** | Improve code architecture | Opportunity to fix technical debt |
| **P2** | Enable easy testing | Every system must be independently testable |
| **P3** | Streamline for Unity patterns | Don't fight Unity—embrace its conventions |
| **P4** | Maintain moddability | JSON-driven content must remain editable |

### 1.3 Non-Goals (This Migration)

- ❌ Full LLM integration (stub only—verify hookup, defer implementation)
- ❌ 3D rendering (architecture ready, visuals come later)
- ❌ Platform-specific optimizations (desktop first)
- ❌ Multiplayer considerations (single-player focus)

---

## 2. Current Reality Assessment

### 2.1 Codebase Snapshot

| Metric | Value |
|--------|-------|
| Python files | 147 |
| Lines of code | ~72,600 |
| JSON config files | 52+ |
| Combat tags | 190+ |
| Crafting disciplines | 6 (Smithing, Alchemy, Refining, Engineering, Enchanting, Fishing) |
| ML models | 5 (2 CNN, 3 LightGBM) |
| Test coverage | Limited (crafting-focused) |

### 2.2 Code Quality Assessment

**Strengths** (preserve these):
- Clean data layer (dataclasses, JSON-driven)
- Well-separated systems (crafting, combat, world)
- Tag system is elegant and extensible
- ML integration is modular

**Weaknesses** (improve these):
- `GameEngine` is monolithic (10,098 lines, single class)
- Minigame rendering mixed into engine (should be separate)
- Limited test coverage
- No dependency injection
- Pygame calls scattered (not abstracted)

### 2.3 What's Working vs What Needs Work

| System | Status | Migration Approach |
|--------|--------|-------------------|
| Data Models | ✅ Excellent | Direct port with minor C# idioms |
| Database Singletons | ✅ Good | Port pattern, consider DI |
| Tag System | ✅ Excellent | Direct port, extensive testing |
| Combat Logic | ✅ Good | Port formulas exactly |
| Crafting Logic | ✅ Good | Port, extract from rendering |
| ML Classifiers | ✅ Working | Convert models, port preprocessing |
| LLM System | ✅ Working | **Stub only** for now |
| World Generation | ✅ Good | Port, Unity Tilemap integration |
| Save/Load | ✅ Good | Port, keep JSON format |
| GameEngine | ⚠️ Monolithic | Decompose into Unity components |
| Rendering | 🔄 Pygame-specific | Full rebuild in Unity |
| Input Handling | 🔄 Pygame-specific | Unity Input System |

---

## 3. Migration Principles

### 3.1 Code Import Principles

Every migrated C# file should be:

1. **Self-contained**: Minimal dependencies, clear interfaces
2. **Independently testable**: Can be unit tested in isolation
3. **Namespace-organized**: Clear hierarchy matching folder structure
4. **Documentation-complete**: XML docs on all public members

**Standard C# file template**:
```csharp
// ============================================================================
// Game1.<Namespace>.<ClassName>
// Migrated from: <python_file_path>
// Migration date: YYYY-MM-DD
// ============================================================================

using System;
using System.Collections.Generic;
using UnityEngine;

namespace Game1.<Namespace>
{
    /// <summary>
    /// Brief description of class purpose.
    /// </summary>
    /// <remarks>
    /// Original Python: <python_file_path>:<line_range>
    /// </remarks>
    public class ClassName
    {
        // Implementation
    }
}
```

### 3.2 Improvement Opportunities

During migration, actively improve:

| Python Pattern | C# Improvement |
|----------------|----------------|
| Monolithic GameEngine | Decompose into MonoBehaviours + Services |
| Manual singletons | `[CreateAssetMenu]` ScriptableObjects or DI |
| Dict everywhere | Typed collections, interfaces |
| String comparisons | Enums where appropriate |
| pygame.time.get_ticks() | `Time.time` or `Time.unscaledTime` |
| Threading.Thread | `async/await` or Coroutines |
| Print debugging | Structured logging system |

### 3.3 What NOT to Change

Preserve exactly during migration:

- **All numeric constants** (damage formulas, difficulty curves)
- **Tag definitions and behavior**
- **JSON file schemas** (backward compatibility)
- **ML preprocessing** (exact feature extraction)
- **Random seed behavior** (for reproducibility testing)

---

## 4. Validation Strategy

### 4.1 Standard Practices for Game Migration Validation

**Industry standard approaches**:

1. **Structured Logging** (Recommended)
2. **Unit Testing** (Required)
3. **Integration Testing** (Required)
4. **Golden File Comparison** (Highly Recommended for ML)
5. **Visual Regression Testing** (For UI, later)

### 4.2 Logging Strategy (NOT Print Statements)

**Do NOT use thousands of print statements.** Instead, use a structured logging system:

```csharp
// ============================================================================
// Game1.Core.MigrationLogger
// Purpose: Structured logging for migration validation
// ============================================================================

using System;
using System.Diagnostics;
using UnityEngine;

namespace Game1.Core
{
    public enum LogLevel { Trace, Debug, Info, Warning, Error }

    public static class MigrationLogger
    {
        public static LogLevel MinLevel { get; set; } = LogLevel.Debug;

        [Conditional("MIGRATION_VALIDATION")]
        public static void Log(LogLevel level, string system, string message,
                               object data = null)
        {
            if (level < MinLevel) return;

            string timestamp = DateTime.Now.ToString("HH:mm:ss.fff");
            string dataStr = data != null ? JsonUtility.ToJson(data) : "";

            string formatted = $"[{timestamp}] [{level}] [{system}] {message} {dataStr}";

            switch (level)
            {
                case LogLevel.Error:
                    Debug.LogError(formatted);
                    break;
                case LogLevel.Warning:
                    Debug.LogWarning(formatted);
                    break;
                default:
                    Debug.Log(formatted);
                    break;
            }
        }

        // Convenience methods
        [Conditional("MIGRATION_VALIDATION")]
        public static void Trace(string system, string msg, object data = null)
            => Log(LogLevel.Trace, system, msg, data);

        [Conditional("MIGRATION_VALIDATION")]
        public static void Debug(string system, string msg, object data = null)
            => Log(LogLevel.Debug, system, msg, data);
    }
}
```

**Usage**:
```csharp
// In combat system
MigrationLogger.Debug("Combat", "Damage calculated", new {
    baseDamage = 50,
    finalDamage = 73,
    modifiers = "STR+20%, crit"
});
```

**Key benefits**:
- `[Conditional("MIGRATION_VALIDATION")]` compiles out in release builds
- Structured data (JSON) enables automated comparison
- System tags enable filtering (`grep "[Combat]"`)
- Timestamps enable performance analysis
- **Zero runtime cost in production**

### 4.3 Testing Pyramid

```
                    ╱╲
                   ╱  ╲
                  ╱ E2E╲         (Few - Full game scenarios)
                 ╱──────╲
                ╱        ╲
               ╱Integration╲     (Some - System interactions)
              ╱────────────╲
             ╱              ╲
            ╱   Unit Tests   ╲   (Many - Individual functions)
           ╱──────────────────╲
```

**Unit Test Requirements** (per system):

| System | Minimum Tests | Coverage Target |
|--------|---------------|-----------------|
| Data Models | 20+ | 100% |
| Tag System | 50+ | 100% |
| Combat Formulas | 30+ | 100% |
| Difficulty Calculator | 20+ | 100% |
| ML Preprocessing | 40+ | 100% |
| Crafting Logic | 25+ per discipline | 90%+ |

### 4.4 Golden File Testing (Critical for ML)

For ML classifiers, use **golden file comparison**:

```csharp
[Test]
public void SmithingPreprocessor_MatchesPythonOutput()
{
    // Arrange
    var placement = LoadTestPlacement("smithing_test_001.json");
    var expectedImage = LoadGoldenFile("smithing_test_001_expected.png");

    // Act
    var actualImage = SmithingPreprocessor.GenerateImage(placement);

    // Assert
    AssertImagesEqual(expectedImage, actualImage, tolerance: 0.001f);
}
```

**Golden file generation process**:
1. Run Python preprocessing on test cases
2. Export outputs as golden files (images, feature vectors)
3. C# tests compare against golden files
4. Any mismatch = regression

### 4.5 Comparison Testing (Python vs C#)

During migration, run both systems in parallel:

```
Test Case → Python System → Output A
         → C# System     → Output B

Compare(A, B) → Pass/Fail with diff
```

**Comparison test structure**:
```csharp
[TestFixture]
public class CombatComparisonTests
{
    private PythonBridge _pythonBridge; // Calls Python via subprocess

    [Test]
    [TestCaseSource(nameof(DamageTestCases))]
    public void DamageCalculation_MatchesPython(DamageTestCase testCase)
    {
        // Get Python result
        var pythonResult = _pythonBridge.CalculateDamage(testCase);

        // Get C# result
        var csharpResult = CombatManager.CalculateDamage(testCase);

        // Compare
        Assert.AreEqual(pythonResult.FinalDamage, csharpResult.FinalDamage,
            $"Damage mismatch for case: {testCase.Name}");
    }
}
```

### 4.6 Validation Removal Strategy

All validation code uses `[Conditional]` attributes:

```csharp
// Define in project settings:
// Debug build: MIGRATION_VALIDATION defined
// Release build: MIGRATION_VALIDATION not defined

[Conditional("MIGRATION_VALIDATION")]
public static void ValidateDamageCalculation(float expected, float actual) { }
```

**Removal process**:
1. During migration: Build with `MIGRATION_VALIDATION` defined
2. After validation complete: Remove define from build settings
3. All validation code compiles to nothing (zero overhead)
4. Keep test files in separate test assembly (not in build)

---

## 5. Plan Document Structure

The migration plan should be organized into these documents:

### 5.1 Document Hierarchy

```
docs/migration/
├── MIGRATION_PLAN.md              # Master plan overview
├── phases/
│   ├── PHASE_1_FOUNDATION.md      # Data models, databases
│   ├── PHASE_2_ENTITIES.md        # Character, components
│   ├── PHASE_3_SYSTEMS.md         # Combat, crafting, world
│   ├── PHASE_4_ML.md              # CNN, LightGBM migration
│   ├── PHASE_5_UNITY.md           # Rendering, input, UI
│   └── PHASE_6_INTEGRATION.md     # Final assembly
├── specifications/
│   ├── SPEC_DATA_LAYER.md         # All data structures
│   ├── SPEC_TAG_SYSTEM.md         # Tag definitions, behavior
│   ├── SPEC_COMBAT.md             # Damage formulas, enchantments
│   ├── SPEC_CRAFTING.md           # All 6 disciplines
│   ├── SPEC_ML_CLASSIFIERS.md     # Model conversion, preprocessing
│   └── SPEC_LLM_STUB.md           # Stub interface design
├── testing/
│   ├── TEST_STRATEGY.md           # Overall approach
│   ├── TEST_CASES_COMBAT.md       # Combat test cases
│   ├── TEST_CASES_CRAFTING.md     # Crafting test cases
│   └── GOLDEN_FILES.md            # Golden file inventory
└── reference/
    ├── PYTHON_TO_CSHARP.md        # Language mapping guide
    ├── PYGAME_TO_UNITY.md         # API mapping guide
    └── CONSTANTS_REFERENCE.md     # All magic numbers
```

### 5.2 Per-Phase Document Template

Each phase document should include:

```markdown
# Phase N: <Name>

## Overview
- Goal: What this phase accomplishes
- Dependencies: What must be complete first
- Deliverables: What this phase produces

## Systems Included
| System | Python Files | C# Target | Est. Hours |
|--------|--------------|-----------|------------|
| ... | ... | ... | ... |

## Migration Steps
1. Step with specific instructions
2. Step with specific instructions
...

## Testing Requirements
- Unit tests required
- Integration tests required
- Validation checkpoints

## Quality Gate
- [ ] All tests passing
- [ ] Code review complete
- [ ] Documentation updated
- [ ] No regressions in dependent systems
```

---

## 6. System Migration Order

### 6.1 Dependency-Aware Sequence

```
PHASE 1: Foundation (No dependencies)
┌─────────────────────────────────────────────────────────────┐
│  Data Models          Enums           JSON Schemas          │
│  (dataclasses →       (string →       (document and         │
│   C# classes)         C# enums)       validate)             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
PHASE 2: Data Layer (Depends on Phase 1)
┌─────────────────────────────────────────────────────────────┐
│  MaterialDatabase     EquipmentDatabase    SkillDatabase    │
│  RecipeDatabase       TitleDatabase        ClassDatabase    │
│  TagRegistry          TranslationDB        ConfigLoader     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
PHASE 3: Entity Layer (Depends on Phase 2)
┌─────────────────────────────────────────────────────────────┐
│  CharacterStats       Inventory            EquipmentManager │
│  SkillManager         BuffManager          StatusEffects    │
│  Character            Tool                 Enemy            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
PHASE 4: Game Systems (Depends on Phase 3)
┌─────────────────────────────────────────────────────────────┐
│  TagParser            EffectExecutor       TargetFinder     │
│  CombatManager        WorldSystem          SaveManager      │
│  DifficultyCalc       RewardCalc           CraftingLogic    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
PHASE 5: ML Classifiers (Can parallel with Phase 4)
┌─────────────────────────────────────────────────────────────┐
│  CNN Models           LightGBM Models      Preprocessing    │
│  (→ ONNX → Sentis)    (→ ONNX or native)   (exact match)    │
│  SmithingClassifier   AlchemyClassifier    ValidationPipe   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
PHASE 6: Unity Integration (After Phase 4+5)
┌─────────────────────────────────────────────────────────────┐
│  GameManager          InputHandler         UIManager        │
│  WorldRenderer        CraftingUI           MinigameUIs      │
│  (MonoBehaviours)     (Unity Input)        (UI Toolkit)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
PHASE 7: Polish & LLM Stub
┌─────────────────────────────────────────────────────────────┐
│  LLM Stub Interface   Debug Notifications  Integration Test │
│  (placeholder only)   (verify hookup)      (full game flow) │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Critical Initialization Orders (MUST PRESERVE)

**Database initialization** (from game_engine.py:106-147):
```
ResourceNodeDB → MaterialDB → EquipmentDB → SkillDB → RecipeDB
→ TitleDB → ClassDB → NPCDB
```

**Character component initialization** (from character.py:93-127):
```
Stats → Leveling → Skills → Buffs → Equipment → Inventory
→ Titles → Class → Activities
```

These orders exist because later systems query earlier ones during initialization.

---

## 7. ML Classifier Migration

### 7.1 Models to Migrate

| Model | Type | Input | Output | Conversion Path |
|-------|------|-------|--------|-----------------|
| Smithing | CNN | 36×36×3 RGB | Valid/Invalid + confidence | Keras → ONNX → Sentis |
| Adornments | CNN | 56×56×3 RGB | Valid/Invalid + confidence | Keras → ONNX → Sentis |
| Alchemy | LightGBM | 34 features | Valid/Invalid + confidence | LightGBM → ONNX → Sentis |
| Refining | LightGBM | 19 features | Valid/Invalid + confidence | LightGBM → ONNX → Sentis |
| Engineering | LightGBM | 28 features | Valid/Invalid + confidence | LightGBM → ONNX → Sentis |

### 7.2 Preprocessing Requirements (CRITICAL)

**Smithing Image Generation** (must match exactly):

```csharp
public static class SmithingPreprocessor
{
    // HSV color encoding - MUST MATCH PYTHON EXACTLY
    private static readonly Dictionary<string, float> CategoryHues = new()
    {
        ["metal"] = 210f,        // Blue
        ["wood"] = 30f,          // Orange
        ["stone"] = 0f,          // Red
        ["monster_drop"] = 300f, // Magenta
        ["gem"] = 280f           // Purple
    };

    private static readonly Dictionary<int, float> TierValues = new()
    {
        [1] = 0.50f,
        [2] = 0.65f,
        [3] = 0.80f,
        [4] = 0.95f
    };

    public static float[,,] GenerateImage(PlacementGrid grid)
    {
        // 1. Create 9x9 canvas (always, regardless of actual grid size)
        // 2. Center placement in canvas
        // 3. For each material:
        //    - Get category → shape mask (4x4 pattern)
        //    - Get tier → fill mask (1x1 to 4x4)
        //    - Get color via HSV encoding
        //    - Combine: color * shape_mask * tier_mask
        // 4. Resize to 36x36
        // 5. Normalize to [0, 1]

        // ... exact implementation from Python ...
    }
}
```

**LightGBM Feature Extraction** (category order is CRITICAL):

```csharp
public static class AlchemyFeatureExtractor
{
    // CRITICAL: This order must match training data exactly
    private static readonly string[] CategoryOrder =
    {
        "elemental", "metal", "monster_drop", "stone", "wood"
    };

    public static float[] ExtractFeatures(AlchemyPlacement placement)
    {
        var features = new float[34];
        int idx = 0;

        // Features must be in EXACT same order as Python training
        foreach (var category in CategoryOrder)
        {
            features[idx++] = CountMaterialsInCategory(placement, category);
            features[idx++] = GetAverageTierForCategory(placement, category);
            // ... more features in exact order ...
        }

        return features;
    }
}
```

### 7.3 Model Conversion Process

**Step 1: Export from Python**
```bash
# CNN models (Keras/TensorFlow)
python -m tf2onnx.convert --keras models/smithing_cnn.keras \
    --output models/smithing_cnn.onnx --opset 15

# LightGBM models
python scripts/convert_lgbm_to_onnx.py models/alchemy_lgbm.txt \
    --output models/alchemy_lgbm.onnx
```

**Step 2: Validate ONNX**
```bash
# Check model compatibility
python -c "import onnx; onnx.checker.check_model('models/smithing_cnn.onnx')"
```

**Step 3: Import to Unity Sentis**
1. Copy `.onnx` files to `Assets/Resources/Models/`
2. Unity auto-imports as `ModelAsset`
3. Create runtime worker:
```csharp
var modelAsset = Resources.Load<ModelAsset>("Models/smithing_cnn");
var model = ModelLoader.Load(modelAsset);
var worker = new Worker(model, BackendType.GPUCompute);
```

### 7.4 Validation Strategy for ML

**Golden file tests** (generate from Python):
```python
# generate_golden_files.py
test_cases = load_test_placements()
for case in test_cases:
    # Generate image
    image = smithing_preprocessor.generate_image(case.placement)
    save_image(f"golden/smithing/{case.id}_image.png", image)

    # Get prediction
    prediction = smithing_classifier.predict(image)
    save_json(f"golden/smithing/{case.id}_prediction.json", prediction)
```

**C# validation tests**:
```csharp
[Test]
[TestCaseSource(nameof(SmithingGoldenFiles))]
public void SmithingClassifier_MatchesGoldenFile(string testId)
{
    var placement = LoadTestPlacement($"smithing/{testId}_placement.json");
    var expectedImage = LoadGoldenImage($"smithing/{testId}_image.png");
    var expectedPrediction = LoadGoldenPrediction($"smithing/{testId}_prediction.json");

    var actualImage = SmithingPreprocessor.GenerateImage(placement);
    var actualPrediction = SmithingClassifier.Predict(actualImage);

    AssertImagesEqual(expectedImage, actualImage, tolerance: 0.001f);
    Assert.AreEqual(expectedPrediction.IsValid, actualPrediction.IsValid);
    Assert.AreEqual(expectedPrediction.Confidence, actualPrediction.Confidence, 0.01f);
}
```

---

## 8. LLM System Stub Strategy

### 8.1 Stub Design Philosophy

The LLM system should be **architecturally complete but functionally stubbed**:

- ✅ Full interface defined
- ✅ Dependency injection ready
- ✅ Debug notification on invocation
- ✅ Returns placeholder data
- ❌ No actual API calls
- ❌ No prompt engineering
- ❌ No response parsing

### 8.2 Interface Definition

```csharp
// ============================================================================
// Game1.Systems.LLM.IItemGenerator
// Purpose: Interface for LLM-based item generation (stub for now)
// ============================================================================

namespace Game1.Systems.LLM
{
    public interface IItemGenerator
    {
        /// <summary>
        /// Generate a new item based on crafting placement.
        /// Currently stubbed - returns placeholder item.
        /// </summary>
        Task<GeneratedItem> GenerateItemAsync(ItemGenerationRequest request);

        /// <summary>
        /// Check if the LLM service is available.
        /// Currently always returns true (stub mode).
        /// </summary>
        bool IsAvailable { get; }
    }

    public class ItemGenerationRequest
    {
        public string Discipline { get; set; }
        public List<PlacedMaterial> Materials { get; set; }
        public int StationTier { get; set; }
        public string PlayerProvidedName { get; set; }
        public string PlayerProvidedDescription { get; set; }
    }

    public class GeneratedItem
    {
        public string ItemId { get; set; }
        public string Name { get; set; }
        public string Description { get; set; }
        public Dictionary<string, object> Stats { get; set; }
        public List<string> Tags { get; set; }
        public bool IsStubGenerated { get; set; } // Always true for now
    }
}
```

### 8.3 Stub Implementation

```csharp
// ============================================================================
// Game1.Systems.LLM.StubItemGenerator
// Purpose: Placeholder LLM implementation with debug notifications
// ============================================================================

namespace Game1.Systems.LLM
{
    public class StubItemGenerator : IItemGenerator
    {
        public bool IsAvailable => true;

        public async Task<GeneratedItem> GenerateItemAsync(ItemGenerationRequest request)
        {
            // Debug notification - visible on screen
            NotificationSystem.Show(
                $"[LLM STUB] Item generation requested for {request.Discipline}",
                NotificationType.Debug,
                duration: 5f
            );

            MigrationLogger.Info("LLM", "GenerateItemAsync called", new
            {
                discipline = request.Discipline,
                materialCount = request.Materials.Count,
                stationTier = request.StationTier,
                playerName = request.PlayerProvidedName
            });

            // Simulate async delay (as real API would have)
            await Task.Delay(500);

            // Return placeholder item
            return new GeneratedItem
            {
                ItemId = $"invented_{request.Discipline}_{Guid.NewGuid():N}",
                Name = request.PlayerProvidedName ?? $"Mysterious {request.Discipline} Creation",
                Description = "[STUB] This item was generated by the LLM stub. " +
                              "Real generation will be implemented later.",
                Stats = GeneratePlaceholderStats(request),
                Tags = new List<string> { "invented", request.Discipline.ToLower() },
                IsStubGenerated = true
            };
        }

        private Dictionary<string, object> GeneratePlaceholderStats(ItemGenerationRequest request)
        {
            // Basic stats based on materials (placeholder logic)
            int avgTier = (int)request.Materials.Average(m => m.Tier);
            return new Dictionary<string, object>
            {
                ["damage"] = avgTier * 10,
                ["durability"] = avgTier * 25,
                ["weight"] = request.Materials.Count * 0.5f
            };
        }
    }
}
```

### 8.4 Debug Notification System

```csharp
// ============================================================================
// Game1.UI.NotificationSystem
// Purpose: On-screen notifications for debugging and player feedback
// ============================================================================

namespace Game1.UI
{
    public enum NotificationType
    {
        Info,
        Success,
        Warning,
        Error,
        Debug  // Only shown when debug mode enabled
    }

    public static class NotificationSystem
    {
        private static readonly Queue<Notification> _pending = new();

        public static void Show(string message, NotificationType type = NotificationType.Info,
                                float duration = 3f)
        {
            // Debug notifications only shown in debug builds
            if (type == NotificationType.Debug && !Debug.isDebugBuild)
                return;

            _pending.Enqueue(new Notification
            {
                Message = message,
                Type = type,
                Duration = duration,
                Timestamp = Time.time
            });

            MigrationLogger.Debug("Notification", message, new { type, duration });
        }
    }
}
```

### 8.5 Verification Checklist

When LLM stub is complete, verify:

- [ ] `IItemGenerator.GenerateItemAsync()` can be called
- [ ] Debug notification appears on screen
- [ ] Placeholder item is returned with valid structure
- [ ] Item can be added to inventory
- [ ] Item can be equipped (if equipment type)
- [ ] Item persists through save/load
- [ ] Logging captures all relevant data

---

## 9. Planning Process Timeline

### 9.1 Recommended Schedule

```
WEEK 1: Documentation & Analysis
├── Day 1-2: Export all JSON schemas, document structures
├── Day 3-4: Create dependency graph, identify circular deps
├── Day 5: Document all numeric constants and formulas

WEEK 2: Specification Writing
├── Day 1: Data Layer specification
├── Day 2: Tag System specification
├── Day 3: Combat System specification
├── Day 4: Crafting System specification
├── Day 5: ML Classifier specification

WEEK 3: Architecture Design
├── Day 1-2: Unity project structure design
├── Day 3: Interface definitions for all systems
├── Day 4: Testing infrastructure design
├── Day 5: Golden file generation (from Python)

WEEK 4: Prototype & Validation
├── Day 1-2: Prototype data loading in Unity
├── Day 3: Prototype tag system in Unity
├── Day 4: Prototype one ML classifier in Unity
├── Day 5: Document learnings, finalize plan
```

### 9.2 Deliverables Per Week

**Week 1 Deliverables**:
- `CONSTANTS_REFERENCE.md` - All magic numbers
- `JSON_SCHEMAS.md` - All data structures
- `DEPENDENCY_GRAPH.png` - Visual diagram
- `CIRCULAR_DEPS.md` - Issues to resolve

**Week 2 Deliverables**:
- `SPEC_DATA_LAYER.md`
- `SPEC_TAG_SYSTEM.md`
- `SPEC_COMBAT.md`
- `SPEC_CRAFTING.md`
- `SPEC_ML_CLASSIFIERS.md`

**Week 3 Deliverables**:
- Unity project scaffold
- Interface definitions (`.cs` files)
- `TEST_STRATEGY.md`
- Golden files for ML validation

**Week 4 Deliverables**:
- Working prototypes in Unity
- `PROTOTYPE_LEARNINGS.md`
- Finalized `MIGRATION_PLAN.md`
- Effort estimates with confidence levels

---

## 10. Checklists & Quality Gates

### 10.1 Pre-Migration Checklist

Before starting any code migration:

- [ ] All JSON schemas documented
- [ ] All numeric constants extracted
- [ ] Dependency graph complete
- [ ] Circular dependencies identified and resolution planned
- [ ] Unity project scaffold created
- [ ] Testing infrastructure in place
- [ ] Golden files generated from Python

### 10.2 Per-System Migration Checklist

For each system migrated:

- [ ] Python source code fully read and understood
- [ ] All public methods documented
- [ ] C# interface defined
- [ ] Unit tests written (before implementation)
- [ ] Implementation complete
- [ ] All unit tests passing
- [ ] Comparison tests against Python passing
- [ ] Code review complete
- [ ] Documentation updated
- [ ] No regressions in dependent systems

### 10.3 Phase Completion Quality Gates

**Phase 1 (Foundation) Gate**:
- [ ] All data models compile
- [ ] All enums defined
- [ ] JSON loading works for all files
- [ ] 100% unit test coverage on models

**Phase 2 (Data Layer) Gate**:
- [ ] All databases load correctly
- [ ] Query methods return correct data
- [ ] Tag registry matches Python exactly
- [ ] Comparison tests pass

**Phase 3 (Entity Layer) Gate**:
- [ ] Character can be created
- [ ] All components initialize correctly
- [ ] Inventory operations work
- [ ] Equipment operations work
- [ ] Save/load roundtrip works

**Phase 4 (Game Systems) Gate**:
- [ ] Combat damage matches Python (±0.01)
- [ ] Tag effects execute correctly
- [ ] Crafting logic produces correct results
- [ ] World generation is deterministic (same seed = same world)

**Phase 5 (ML Classifiers) Gate**:
- [ ] All models load in Sentis
- [ ] Preprocessing matches Python exactly
- [ ] Predictions match golden files (±0.01 confidence)
- [ ] Performance acceptable (<100ms per prediction)

**Phase 6 (Unity Integration) Gate**:
- [ ] Game boots without errors
- [ ] Core loop functional (move, gather, craft, fight)
- [ ] UI displays correct information
- [ ] Full game flow testable

**Phase 7 (LLM Stub) Gate**:
- [ ] Stub interface callable
- [ ] Debug notification displays
- [ ] Placeholder items work in game
- [ ] Architecture ready for real implementation

---

## Appendix A: Key File Reference

### Python Files by Priority

**P0 - Migrate First** (pure logic, no pygame):
```
data/models/*.py           # All data models
data/databases/*.py        # All database singletons
core/difficulty_calculator.py
core/reward_calculator.py
core/effect_executor.py
core/tag_system.py
core/tag_parser.py
Combat/combat_manager.py
Combat/enemy.py
systems/save_manager.py
```

**P1 - Migrate Second** (minimal pygame):
```
entities/character.py
entities/components/*.py
systems/world_system.py
systems/crafting_classifier.py
Crafting-subdisciplines/*.py (logic only)
```

**P2 - Stub Only**:
```
systems/llm_item_generator.py  # Interface + stub
```

**P3 - Rebuild for Unity**:
```
core/game_engine.py        # Decompose into Unity components
rendering/renderer.py      # Full rebuild
core/minigame_effects.py   # Rebuild with Unity particles
```

### Unity Target Structure

```
Assets/
├── Scripts/
│   ├── Game1.Core/
│   │   ├── GameManager.cs
│   │   ├── Config.cs
│   │   └── MigrationLogger.cs
│   ├── Game1.Data/
│   │   ├── Models/
│   │   └── Databases/
│   ├── Game1.Entities/
│   │   ├── Character/
│   │   └── Enemies/
│   ├── Game1.Systems/
│   │   ├── Combat/
│   │   ├── Crafting/
│   │   ├── World/
│   │   ├── ML/
│   │   └── LLM/
│   └── Game1.UI/
├── Resources/
│   ├── JSON/
│   ├── Models/          # ONNX files
│   └── Prompts/         # For future LLM
├── Tests/
│   ├── EditMode/
│   └── PlayMode/
└── StreamingAssets/
    └── Content/         # Moddable JSON
```

---

## Appendix B: Research Sources

### Migration Best Practices
- [Python to C# Migration Guide (Elvanco)](https://elvanco.com/blog/migrating-from-python-to-c)
- [Large Codebase Migration Strategies](https://www.scottberrevoets.com/2022/11/15/migration-strategies-in-large-codebases/)

### Unity Patterns
- [Unity Sentis Documentation](https://docs.unity3d.com/Packages/com.unity.sentis@2.1/manual/index.html)
- [Hugging Face Unity Sentis Models](https://huggingface.co/docs/hub/en/unity-sentis)

### C# SDKs
- [Anthropic C# SDK (Official)](https://github.com/anthropics/anthropic-sdk-csharp)
- [Anthropic.SDK (Unofficial, mature)](https://github.com/tghamm/Anthropic.SDK)
- [Claudia (Cysharp)](https://github.com/Cysharp/Claudia)

---

**Document Status**: Ready for review
**Next Steps**: Begin Week 1 documentation sprint
**Owner**: Migration Team
