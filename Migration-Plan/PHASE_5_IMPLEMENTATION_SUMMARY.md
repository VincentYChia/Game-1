# Phase 5 Implementation Summary: ML Classifiers

**Date**: 2026-02-13
**Source**: `Game-1-modular/systems/crafting_classifier.py` (1,419 lines)
**Output**: 10 C# files + 2 Python scripts + 1 test file (~2,100 lines C#)

---

## What Was Built

### C# Files (10 files in `Game1.Systems.Classifiers/`)

| File | Lines | Purpose |
|------|-------|---------|
| `ClassifierResult.cs` | 56 | Immutable result struct (Valid, Confidence, Probability, Discipline, Error) |
| `ClassifierConfig.cs` | 48 | Per-discipline config (type, model path, threshold, enabled) |
| `ClassifierManager.cs` | 380 | Singleton orchestrator — preprocessing, inference, lifecycle |
| `Preprocessing/MaterialColorEncoder.cs` | 216 | HSV color encoding (shared by both CNNs) |
| `Preprocessing/SmithingPreprocessor.cs` | 230 | 9×9 grid → 36×36×3 image (5 shape masks, 4 tier fills) |
| `Preprocessing/AdornmentPreprocessor.cs` | 262 | Cartesian graph → 56×56×3 image (Bresenham + circles) |
| `Preprocessing/AlchemyFeatureExtractor.cs` | 225 | 34 features (6 position × 3 + stats) |
| `Preprocessing/RefiningFeatureExtractor.cs` | 179 | 19 features (core/spoke + tier stats) |
| `Preprocessing/EngineeringFeatureExtractor.cs` | 196 | 28 features (8 slot types + stats) |

### Python Scripts (2 files in `Classifiers/Scripts/`)

| File | Purpose |
|------|---------|
| `convert_models_to_onnx.py` | Converts 2 CNN (Keras→ONNX) + 3 LightGBM (txt→ONNX) with validation |
| `generate_golden_files.py` | Generates test cases with known input/output pairs |

### Tests (1 file in `Tests/EditMode/Classifiers/`)

| File | Tests | Purpose |
|------|-------|---------|
| `ClassifierPreprocessorTests.cs` | 24 | HSV correctness, empty input, output sizes, math helpers, result structs |

---

## Architecture Decisions

### AD-P5-001: Pure C# HSV-to-RGB (No UnityEngine)
Per AC-002, Phases 1-5 must use pure C# with no UnityEngine imports. Instead of `Color.HSVToRGB()`, we implement the exact Python `colorsys.hsv_to_rgb` algorithm in C#. This ensures:
- Pixel-perfect match with Python training pipeline
- Testable without Unity editor
- No risk of Unity-specific HSV normalization differences

### AD-P5-002: IModelBackend Abstraction
The ClassifierManager does not directly import Unity Sentis. Instead, it defines an `IModelBackend` interface:
```csharp
public interface IModelBackend : IDisposable
{
    (float probability, string error) Predict(float[] inputData);
    bool IsLoaded { get; }
}
```
Phase 6 provides the Sentis implementation via `IModelBackendFactory`. This keeps Phase 5 as pure C# while still supporting full inference when Unity is available.

### AD-P5-003: Flat Float Arrays for Tensor Data
Rather than using multidimensional arrays, all image and feature data uses flat `float[]` arrays in row-major, channel-last order:
- Smithing: `float[3888]` = 36 × 36 × 3
- Adornments: `float[9408]` = 56 × 56 × 3
- LightGBM: `float[N]` where N = feature count

This matches the tensor layout expected by ONNX/Sentis and avoids array-of-arrays overhead.

### AD-P5-004: Typed Validation Methods
Instead of a single `Validate(discipline, ui_state)` with dynamic object types (as in Python), the ClassifierManager exposes typed methods per discipline:
- `ValidateSmithing(grid, stationGridSize)`
- `ValidateAdornments(vertices, shapes)`
- `ValidateAlchemy(slots, stationTier)`
- `ValidateRefining(coreSlots, surroundingSlots, stationTier)`
- `ValidateEngineering(slotsDict, stationTier)`

This provides compile-time type safety and clearer APIs for Phase 6 integration.

---

## Constant Verification Checklist

All constants verified against Python `crafting_classifier.py`:

| Constant | Python Value | C# Value | Status |
|----------|-------------|----------|--------|
| CATEGORY_HUES[metal] | 210 | 210f | ✅ |
| CATEGORY_HUES[wood] | 30 | 30f | ✅ |
| CATEGORY_HUES[stone] | 0 | 0f | ✅ |
| CATEGORY_HUES[monster_drop] | 300 | 300f | ✅ |
| CATEGORY_HUES[gem] | 280 | 280f | ✅ |
| CATEGORY_HUES[herb] | 120 | 120f | ✅ |
| CATEGORY_HUES[fabric] | 45 | 45f | ✅ |
| TIER_VALUES[1-4] | 0.50, 0.65, 0.80, 0.95 | 0.50f, 0.65f, 0.80f, 0.95f | ✅ |
| Stone base_saturation | 0.2 | 0.2f | ✅ |
| Default base_saturation | 0.6 | 0.6f | ✅ |
| Legendary/mythical sat boost | +0.2 | +0.2f | ✅ |
| Magical/ancient sat boost | +0.1 | +0.1f | ✅ |
| Smithing IMG_SIZE | 36 | 36 | ✅ |
| Smithing CELL_SIZE | 4 | 4 | ✅ |
| Smithing GRID_SIZE | 9 | 9 | ✅ |
| TIER_FILL_SIZES[1-4] | 1,2,3,4 | 1,2,3,4 | ✅ |
| Adornment IMG_SIZE | 56 | 56 | ✅ |
| Adornment COORD_RANGE | 7 | 7 | ✅ |
| Line thickness | 2 | 2 | ✅ |
| Vertex radius | 3 | 3 | ✅ |
| CATEGORY_TO_IDX | elemental=0...wood=4 | elemental=0...wood=4 | ✅ |
| All thresholds | 0.5 | 0.5f | ✅ |
| 5 shape masks (4×4 each) | Verified pixel-by-pixel | ✅ | ✅ |
| All 10 ELEMENT_HUES | Verified | ✅ | ✅ |
| Alchemy features | 34 | 34 | ✅ |
| Refining features | 19 | 19 | ✅ |
| Engineering features | 28 | 28 | ✅ |
| Engineering slot type order | FRAME...CATALYST | FRAME...CATALYST | ✅ |
| np.std → population std | ÷N | ÷N (not N-1) | ✅ |

---

## Integration Points

### Phase 4 calls Phase 5:
```csharp
var result = ClassifierManager.Instance.ValidateSmithing(grid, stationGridSize);
if (result.Valid && result.Confidence > 0.7f)
{
    // Proceed to minigame
}
```

### Phase 6 provides Sentis backend:
```csharp
ClassifierManager.Instance.Initialize(
    backendFactory: new SentisBackendFactory(), // Phase 6 provides this
    configs: null // Use defaults
);
```

---

## Remaining Work for Full Quality Gate

- [ ] Run ONNX conversion scripts (requires TensorFlow + LightGBM installed)
- [ ] Validate ONNX models against Python originals (100 random inputs each)
- [ ] Generate comprehensive golden files (50+ per model)
- [ ] Run golden file validation after Phase 6 Sentis integration
- [ ] Performance benchmark (< 100ms per prediction target)
- [ ] Verify Color.HSVToRGB parity if Unity path is ever used

---

## File Listing (All Phase 5 Output)

```
Unity/Assets/Scripts/Game1.Systems/Classifiers/
├── ClassifierResult.cs
├── ClassifierConfig.cs
├── ClassifierManager.cs
├── Preprocessing/
│   ├── MaterialColorEncoder.cs
│   ├── SmithingPreprocessor.cs
│   ├── AdornmentPreprocessor.cs
│   ├── AlchemyFeatureExtractor.cs
│   ├── RefiningFeatureExtractor.cs
│   └── EngineeringFeatureExtractor.cs
└── Scripts/
    ├── convert_models_to_onnx.py
    └── generate_golden_files.py

Unity/Assets/Tests/EditMode/Classifiers/
└── ClassifierPreprocessorTests.cs
```
