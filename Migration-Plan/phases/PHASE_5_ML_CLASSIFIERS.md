# Phase 5: ML Classifier Migration
## CNN and LightGBM Models to ONNX for Unity Sentis Inference

**Phase**: 5 of 10
**Depends On**: Phase 1 (Data Models) for MaterialDefinition; Phase 2 (Data Layer) for MaterialDatabase
**Can Parallel With**: Phases 2, 3, 4 (independent ML pipeline)
**Estimated Scope**: 1,420 lines Python -> ~1,800 lines C# + 5 ONNX models
**Source File**: `Game-1-modular/systems/crafting_classifier.py` (1,420 lines)
**Created**: 2026-02-10

---

## 1. Overview

### Goal

Convert all 5 ML classifier models (2 CNN, 3 LightGBM) from their native Python formats to ONNX, then port all preprocessing and inference logic to C# for use with Unity Sentis. The preprocessing code must reproduce the Python output exactly -- any deviation in image rendering or feature extraction will cause the models to produce incorrect predictions.

### Why This Phase Can Run in Parallel

The ML classifier pipeline is self-contained. It depends only on:
- `MaterialDefinition` (Phase 1) for category, tier, and tag data
- `MaterialDatabase` (Phase 2) for material lookups during preprocessing

It does NOT depend on combat, crafting UI, world systems, or entity code. A developer can work on ONNX conversion and C# preprocessors while other phases are in progress, provided stub interfaces for material lookups are available.

### Deliverables

| Deliverable | Count | Description |
|-------------|-------|-------------|
| ONNX model files | 5 | One per discipline (smithing, adornments, alchemy, refining, engineering) |
| C# preprocessor files | 5 | Image renderers (2) and feature extractors (3) |
| C# orchestrator | 2 | ClassifierManager.cs + ClassifierResult.cs |
| Python conversion scripts | 2 | Keras-to-ONNX and LightGBM-to-ONNX converters |
| Golden file test data | 5 sets | 50+ test cases per model with input/output pairs |
| C# unit tests | 5+ | Golden file validation per model |

### Target Project Structure

```
Assets/
  Scripts/Game1.Systems/
    Classifiers/
      ClassifierManager.cs            # Orchestrator (singleton)
      ClassifierResult.cs             # Result data structure
      ClassifierConfig.cs             # Per-model configuration
      Preprocessing/
        MaterialColorEncoder.cs       # HSV color encoding (shared)
        SmithingPreprocessor.cs       # 9x9 grid -> 36x36 image
        AdornmentPreprocessor.cs      # Cartesian -> 56x56 image
        AlchemyFeatureExtractor.cs    # 34 features
        RefiningFeatureExtractor.cs   # 19 features
        EngineeringFeatureExtractor.cs # 28 features
  Resources/
    Models/
      smithing.onnx
      adornments.onnx
      alchemy.onnx
      refining.onnx
      engineering.onnx
  Tests/
    EditMode/
      Classifiers/
        SmithingPreprocessorTests.cs
        AdornmentPreprocessorTests.cs
        AlchemyFeatureExtractorTests.cs
        RefiningFeatureExtractorTests.cs
        EngineeringFeatureExtractorTests.cs
        ClassifierManagerTests.cs
    GoldenFiles/
      Classifiers/
        smithing_golden.json
        adornments_golden.json
        alchemy_golden.json
        refining_golden.json
        engineering_golden.json
```

---

## 2. Models to Migrate

### 2.1 Model Inventory

| Model | Type | Input Shape | Output | Python Path | Conversion Path |
|-------|------|-------------|--------|-------------|-----------------|
| Smithing | CNN (Keras) | 36x36x3 float32 | 1 float (sigmoid) | `Scaled JSON Development/models/smithing/smithing_best.keras` | Keras -> tf2onnx -> ONNX -> Sentis |
| Adornments | CNN (Keras) | 56x56x3 float32 | 1 float (sigmoid) | `Scaled JSON Development/models/adornment/adornment_best.keras` | Keras -> tf2onnx -> ONNX -> Sentis |
| Alchemy | LightGBM | 34 float32 | 1 float (probability) | `Scaled JSON Development/models/alchemy/alchemy_model.txt` | LightGBM -> onnxmltools -> ONNX -> Sentis |
| Refining | LightGBM | 19 float32 | 1 float (probability) | `Scaled JSON Development/models/refining/refining_model.txt` | LightGBM -> onnxmltools -> ONNX -> Sentis |
| Engineering | LightGBM | 28 float32 | 1 float (probability) | `Scaled JSON Development/models/engineering/engineering_model.txt` | LightGBM -> onnxmltools -> ONNX -> Sentis |

### 2.2 Model Output Interpretation

All 5 models output a single float probability in [0, 1]:
- `probability >= threshold (0.5)` -> recipe is **valid**
- `probability < threshold (0.5)` -> recipe is **invalid**
- `confidence = probability` if valid, `1 - probability` if invalid

The threshold is configurable per discipline via `ClassifierConfig.threshold`.

### 2.3 Existing Model Files on Disk

```
Scaled JSON Development/
  models/
    smithing/
      smithing_best.keras          # Keras CNN model
    adornment/
      adornment_best.keras         # Keras CNN model
    alchemy/
      alchemy_model.txt            # LightGBM Booster text file
      alchemy_extractor.pkl        # Pickled extractor (NOT used -- see Section 3)
    refining/
      refining_model.txt           # LightGBM Booster text file
      refining_extractor.pkl       # Pickled extractor (NOT used)
    engineering/
      engineering_model.txt        # LightGBM Booster text file
      engineering_extractor.pkl    # Pickled extractor (NOT used)
```

**NOTE**: The `.pkl` extractor files contain a `RecipeFeatureExtractor` class from the training script that does not exist in the game runtime. The Python code explicitly does NOT use these files (see `LightGBMBackend.__init__` comment at line 967). The game uses its own `LightGBMFeatureExtractor` class for feature extraction. The C# port must replicate the game's `LightGBMFeatureExtractor`, not the pickled training extractor.

---

## 3. Preprocessing -- CRITICAL (Must Match Python EXACTLY)

The preprocessing code transforms UI state (grid placements, slot contents) into model input tensors. Any deviation from the Python implementation will produce incorrect predictions because the models were trained on data generated by the exact same preprocessing pipeline.

### 3.1 Shared: Material Color Encoder (MaterialColorEncoder)

**Source**: `crafting_classifier.py` lines 64-213

The color encoder converts a `material_id` string into an RGB color triple using HSV color space. This is shared by both CNN preprocessors.

#### Step 1: Category to Hue (0-360 degrees)

```
Category        Hue (degrees)
--------        -------------
metal           210
wood            30
stone           0
monster_drop    300
gem             280
herb            120
fabric          45
```

**Special case -- elemental category**: Use element tag to determine hue:
```
fire=0, water=210, earth=120, air=60, lightning=270,
ice=180, light=45, dark=280, void=290, chaos=330
```
Default for elemental with no matching tag: 280.

#### Step 2: Tier to Value (brightness, 0.0-1.0)

```
Tier    Value
----    -----
1       0.50
2       0.65
3       0.80
4       0.95
```
Default for unknown tier: 0.50.

#### Step 3: Tags to Saturation

```python
base_saturation = 0.6
if category == 'stone':
    base_saturation = 0.2
if 'legendary' in tags or 'mythical' in tags:
    base_saturation = min(1.0, base_saturation + 0.2)
elif 'magical' in tags or 'ancient' in tags:
    base_saturation = min(1.0, base_saturation + 0.1)
```

**IMPORTANT**: The `elif` means legendary/mythical takes priority. If a material has both `legendary` and `magical` tags, only the +0.2 applies.

#### Step 4: HSV to RGB Conversion

```python
hue_normalized = hue / 360.0
rgb = colorsys.hsv_to_rgb(hue_normalized, saturation, value)
```

Output is an `(R, G, B)` tuple with each channel in [0.0, 1.0].

#### Special Cases

- `material_id == None` -> return `(0.0, 0.0, 0.0)` (black)
- Unknown material (not in database) -> return `(0.3, 0.3, 0.3)` (gray)

#### C# Implementation Notes

C# does not have a built-in `hsv_to_rgb`. Implement manually or use `Color.HSVToRGB()` from UnityEngine (note: Unity expects hue in [0,1] not [0,360]):

```csharp
float hueNormalized = hue / 360f;
Color rgb = Color.HSVToRGB(hueNormalized, saturation, value);
// rgb.r, rgb.g, rgb.b are in [0, 1]
```

Verify that `UnityEngine.Color.HSVToRGB` produces identical output to Python's `colorsys.hsv_to_rgb` for the same inputs. Create a test matrix of all (category, tier, tag) combinations and compare outputs.

---

### 3.2 CNN Image Rendering: Smithing (SmithingImageRenderer)

**Source**: `crafting_classifier.py` lines 220-387
**Output**: 36x36x3 float32 array, pixel values in [0, 1]

#### Constants

```
IMG_SIZE   = 36
CELL_SIZE  = 4
GRID_SIZE  = 9
```

#### Algorithm

**Step 1: Build 9x9 material grid from UI state**

The smithing UI has a variable-size grid (`station_grid_size`, typically 3x3 to 9x9). This is centered within a fixed 9x9 canvas:

```python
offset = (9 - station_grid_size) // 2
for (x, y), placed_mat in ui.grid.items():
    grid[offset + y][offset + x] = placed_mat.item_id
```

**Step 2: For each non-empty cell, compute the pixel block**

For cell at grid position `(row=i, col=j)` with material `material_id`:

a. **Get base color** via `MaterialColorEncoder.encode(material_id)` -> RGB [0,1]

b. **Get shape mask** (4x4 pattern based on material category):

| Category | Shape Pattern (4x4) | Description |
|----------|---------------------|-------------|
| metal | `[[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]]` | Solid square |
| wood | `[[1,1,1,1],[0,0,0,0],[1,1,1,1],[0,0,0,0]]` | Horizontal lines |
| stone | `[[1,0,0,1],[0,1,1,0],[0,1,1,0],[1,0,0,1]]` | X pattern |
| monster_drop | `[[0,1,1,0],[1,1,1,1],[1,1,1,1],[0,1,1,0]]` | Diamond |
| elemental | `[[0,1,1,0],[1,1,1,1],[1,1,1,1],[0,1,1,0]]` | Plus/cross |
| (default) | `[[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]]` | Solid square |

**NOTE**: `monster_drop` and `elemental` share the same diamond/cross pattern in the current code. `gem`, `herb`, and `fabric` fall through to the default solid square.

c. **Get tier fill mask** (centered in 4x4):

| Tier | Fill Size | Mask (4x4, 1=filled) |
|------|-----------|----------------------|
| T1 | 1x1 | `offset=1; mask[1:2, 1:2] = 1` (center pixel only) |
| T2 | 2x2 | `offset=1; mask[1:3, 1:3] = 1` |
| T3 | 3x3 | `offset=0; mask[0:3, 0:3] = 1` (note: offset=(4-3)//2=0) |
| T4 | 4x4 | `offset=0; mask[0:4, 0:4] = 1` (full cell) |

Computation:
```python
fill_size = TIER_FILL_SIZES[tier]  # {1:1, 2:2, 3:3, 4:4}
offset = (4 - fill_size) // 2
mask[offset:offset+fill_size, offset:offset+fill_size] = 1.0
```

d. **Combine**: `combined_mask = shape_mask * tier_mask` (element-wise multiply)

e. **Apply color**: For each RGB channel c: `cell[:,:,c] = color[c] * combined_mask`

**Step 3: Place cell in image**

```python
y_start = i * 4    # row * CELL_SIZE
y_end   = (i+1) * 4
x_start = j * 4    # col * CELL_SIZE
x_end   = (j+1) * 4
img[y_start:y_end, x_start:x_end] = cell
```

**Step 4: Return image as-is**

No resize step is needed. The 9x9 grid with 4x4 pixel cells produces exactly a 36x36 image. Values are already in [0, 1] because the color encoder outputs [0, 1].

---

### 3.3 CNN Image Rendering: Adornments (AdornmentImageRenderer)

**Source**: `crafting_classifier.py` lines 390-511
**Output**: 56x56x3 float32 array, pixel values in [0, 1]

#### Constants

```
IMG_SIZE    = 56
COORD_RANGE = 7
```

Coordinate space: `[-7, +7]` on both axes (Cartesian).

#### Coordinate to Pixel Mapping

```python
def _coord_to_pixel(x, y):
    px = int((x + 7) * 4)
    py = int((7 - y) * 4)
    return px, py
```

This maps Cartesian `(-7,-7)` to pixel `(0, 56)` and `(+7,+7)` to pixel `(56, 0)`.

#### Algorithm

**Step 1: Extract vertices and shapes from UI**

```python
vertices = {coord_key: {'materialId': placed_mat.item_id} for coord_key, placed_mat in ui.vertices.items()}
shapes = [{'type': s['type'], 'vertices': s['vertices']} for s in ui.shapes]
```

Vertex keys are strings like `"3,4"` (x,y coordinates).

**Step 2: Draw edges (lines between shape vertices)**

For each shape, iterate consecutive vertex pairs (wrapping: last connects to first):

```python
for i in range(len(shape_vertices)):
    v1_str = shape_vertices[i]
    v2_str = shape_vertices[(i + 1) % len(shape_vertices)]
```

Line color is determined by endpoint materials:
- Both endpoints have materials: average the two colors
- Only one has material: use that color
- Neither has material: use `(0.3, 0.3, 0.3)` gray

Lines are drawn with **Bresenham's algorithm** with `thickness=2`. Pixel blending: if existing pixel is non-zero, average with new color; otherwise overwrite.

**Step 3: Draw vertices (filled circles)**

For each vertex, draw a filled circle at the pixel coordinates:
- `radius = 3` pixels
- Color from `MaterialColorEncoder.encode(material_id)`
- Circle test: `(x - cx)^2 + (y - cy)^2 <= radius^2`

Vertices are drawn AFTER edges, so they overwrite edge pixels at intersection points.

#### C# Implementation Notes

The Bresenham line drawing with blending and the filled circle rendering must be implemented pixel-for-pixel identically. Pay special attention to:
- Integer truncation in `_coord_to_pixel` (Python `int()` truncates toward zero)
- Bresenham error accumulation (sign of `sx`, `sy`)
- Blending order: `(existing + new) / 2` when existing pixel has any non-zero channel
- Circle: inclusive inequality `<=`

---

### 3.4 LightGBM Feature Extraction: Alchemy (34 features)

**Source**: `crafting_classifier.py` lines 678-763

#### Feature Vector Layout (EXACT ORDER)

| Index | Feature Name | Computation |
|-------|-------------|-------------|
| 0 | num_ingredients | Count of non-empty slots |
| 1 | total_qty | Sum of all ingredient quantities |
| 2 | avg_qty | total_qty / max(1, num_ingredients) |
| 3-4-5 | position_0: tier, qty, cat_idx | First slot: material tier, quantity, category index |
| 6-7-8 | position_1: tier, qty, cat_idx | Second slot (0,0,0 if empty) |
| 9-10-11 | position_2: tier, qty, cat_idx | Third slot |
| 12-13-14 | position_3: tier, qty, cat_idx | Fourth slot |
| 15-16-17 | position_4: tier, qty, cat_idx | Fifth slot |
| 18-19-20 | position_5: tier, qty, cat_idx | Sixth slot |
| 21 | material_diversity | Count of unique material IDs |
| 22 | cat_elemental | Count of ingredients with category 'elemental' |
| 23 | cat_metal | Count of 'metal' |
| 24 | cat_monster_drop | Count of 'monster_drop' |
| 25 | cat_stone | Count of 'stone' |
| 26 | cat_wood | Count of 'wood' |
| 27 | ref_basic | Count of ingredients with refinement level 'basic' |
| 28 | tier_mean | Mean tier of all ingredients (0 if empty) |
| 29 | tier_max | Max tier (0 if empty) |
| 30 | tier_std | Standard deviation of tiers (0 if < 2 ingredients) |
| 31 | tier_increases | Count of tier increases in sequential order |
| 32 | tier_decreases | Count of tier decreases in sequential order |
| 33 | station_tier | Station tier from UI |

**Total: 34 features** (3 + 18 + 1 + 5 + 1 + 3 + 2 + 1)

#### Category Index Mapping (HARDCODED, alphabetical)

```
elemental    = 0
metal        = 1
monster_drop = 2
stone        = 3
wood         = 4
```

Unknown categories default to index 0.

#### Refinement Level Detection

```python
def _get_refinement_level(material):
    tags = material.get('metadata', {}).get('tags', [])
    for tag in tags:
        if tag in ['basic', 'refined', 'raw', 'processed']:
            return tag
    return 'basic'
```

#### Sequential Pattern Features

```python
tiers = [tier_of_ingredient_0, tier_of_ingredient_1, ...]
tier_increases = sum(1 for i in range(len(tiers)-1) if tiers[i+1] > tiers[i])
tier_decreases = sum(1 for i in range(len(tiers)-1) if tiers[i+1] < tiers[i])
```

---

### 3.5 LightGBM Feature Extraction: Refining (19 features)

**Source**: `crafting_classifier.py` lines 588-676

#### Feature Vector Layout (EXACT ORDER)

| Index | Feature Name | Computation |
|-------|-------------|-------------|
| 0 | num_cores | Count of non-empty core slots |
| 1 | num_spokes | Count of non-empty surrounding slots |
| 2 | core_qty | Sum of quantities in core slots |
| 3 | spoke_qty | Sum of quantities in surrounding slots |
| 4 | spoke_core_ratio | num_spokes / max(1, num_cores) |
| 5 | qty_ratio | spoke_qty / max(1, core_qty) |
| 6 | material_diversity | Count of unique material IDs across all slots |
| 7 | cat_elemental | Count of CORE materials with category 'elemental' |
| 8 | cat_metal | Count of 'metal' in cores |
| 9 | cat_monster_drop | Count of 'monster_drop' in cores |
| 10 | cat_stone | Count of 'stone' in cores |
| 11 | cat_wood | Count of 'wood' in cores |
| 12 | ref_basic | Count of core materials with refinement 'basic' |
| 13 | core_tier_mean | Mean tier of core materials (0 if empty) |
| 14 | core_tier_max | Max tier of core materials (0 if empty) |
| 15 | spoke_tier_mean | Mean tier of spoke materials (0 if empty) |
| 16 | spoke_tier_max | Max tier of spoke materials (0 if empty) |
| 17 | tier_mismatch | abs(core_tier_mean - spoke_tier_mean), 0 if either empty |
| 18 | station_tier | Station tier from UI |

**Total: 19 features** (2 + 2 + 2 + 1 + 5 + 1 + 5 + 1)

**IMPORTANT**: Category distribution (features 7-11) is computed from **core materials only**, not all materials. This differs from alchemy which uses all ingredients.

---

### 3.6 LightGBM Feature Extraction: Engineering (28 features)

**Source**: `crafting_classifier.py` lines 765-850

#### Feature Vector Layout (EXACT ORDER)

| Index | Feature Name | Computation |
|-------|-------------|-------------|
| 0 | num_slots | Total count of filled slots across all types |
| 1 | total_qty | Sum of quantities across all slots |
| 2 | count_FRAME | Count of FRAME-type slots |
| 3 | count_FUNCTION | Count of FUNCTION-type slots |
| 4 | count_POWER | Count of POWER-type slots |
| 5 | count_MODIFIER | Count of MODIFIER-type slots |
| 6 | count_UTILITY | Count of UTILITY-type slots |
| 7 | count_ENHANCEMENT | Count of ENHANCEMENT-type slots |
| 8 | count_CORE | Count of CORE-type slots |
| 9 | count_CATALYST | Count of CATALYST-type slots |
| 10 | unique_slot_types | Count of distinct slot types used |
| 11 | has_FRAME | 1 if FRAME present, 0 otherwise |
| 12 | has_FUNCTION | 1 if FUNCTION present, 0 otherwise |
| 13 | has_POWER | 1 if POWER present, 0 otherwise |
| 14 | material_diversity | Count of unique material IDs |
| 15 | cat_elemental | Count of all materials with category 'elemental' |
| 16 | cat_metal | Count of 'metal' |
| 17 | cat_monster_drop | Count of 'monster_drop' |
| 18 | cat_stone | Count of 'stone' |
| 19 | cat_wood | Count of 'wood' |
| 20 | ref_basic | Count of materials with refinement 'basic' |
| 21 | tier_mean | Mean tier of all materials (0 if empty) |
| 22 | tier_max | Max tier of all materials (0 if empty) |
| 23 | tier_std | Standard deviation of tiers (0 if < 2 materials) |
| 24 | frame_qty | Sum of quantities in FRAME slots |
| 25 | power_qty | Sum of quantities in POWER slots |
| 26 | function_qty | Sum of quantities in FUNCTION slots |
| 27 | station_tier | Station tier from UI |

**Total: 28 features** (2 + 8 + 4 + 1 + 5 + 1 + 3 + 3 + 1)

#### Slot Type Order (MUST BE EXACT)

The 8 slot type counts at indices 2-9 iterate in this order:
```
FRAME, FUNCTION, POWER, MODIFIER, UTILITY, ENHANCEMENT, CORE, CATALYST
```

---

## 4. Model Conversion Process

### 4.1 Step 1: Export CNN Models (Keras to ONNX)

```bash
# Install conversion tools
pip install tf2onnx onnx

# Convert smithing model
python -m tf2onnx.convert \
    --keras "Scaled JSON Development/models/smithing/smithing_best.keras" \
    --output "Scaled JSON Development/models/smithing/smithing.onnx" \
    --opset 15

# Convert adornments model
python -m tf2onnx.convert \
    --keras "Scaled JSON Development/models/adornment/adornment_best.keras" \
    --output "Scaled JSON Development/models/adornment/adornments.onnx" \
    --opset 15
```

**OPSET 15** is recommended as the baseline. If Sentis requires a different opset, adjust accordingly. Check the Unity Sentis documentation for supported opset versions.

### 4.2 Step 2: Export LightGBM Models to ONNX

```python
# scripts/convert_lgbm_to_onnx.py
import lightgbm as lgb
import onnxmltools
from onnxmltools.convert import convert_lightgbm
from onnxmltools.convert.common.data_types import FloatTensorType

MODELS = {
    'alchemy':     ('models/alchemy/alchemy_model.txt',         34),
    'refining':    ('models/refining/refining_model.txt',        19),
    'engineering': ('models/engineering/engineering_model.txt',   28),
}

for name, (path, num_features) in MODELS.items():
    booster = lgb.Booster(model_file=path)

    # Define input shape: [batch_size, num_features]
    initial_type = [('input', FloatTensorType([None, num_features]))]

    # Convert
    onnx_model = convert_lightgbm(
        booster,
        initial_types=initial_type,
        target_opset=15
    )

    # Save
    output_path = f"models/{name}/{name}.onnx"
    onnxmltools.utils.save_model(onnx_model, output_path)
    print(f"Saved {output_path}")
```

### 4.3 Step 3: Validate ONNX Models

```python
# scripts/validate_onnx_output.py
import onnx
import onnxruntime as ort
import numpy as np
import lightgbm as lgb
import tensorflow as tf

def validate_cnn(keras_path, onnx_path, img_size):
    """Compare Keras and ONNX predictions on random inputs."""
    keras_model = tf.keras.models.load_model(keras_path)
    ort_session = ort.InferenceSession(onnx_path)

    for i in range(100):
        test_input = np.random.rand(1, img_size, img_size, 3).astype(np.float32)

        keras_pred = float(keras_model.predict(test_input, verbose=0)[0][0])
        ort_pred = float(ort_session.run(None, {'input': test_input})[0][0][0])

        diff = abs(keras_pred - ort_pred)
        assert diff < 0.001, f"Test {i}: Keras={keras_pred:.6f}, ONNX={ort_pred:.6f}, diff={diff:.6f}"

    print(f"PASS: {onnx_path} matches Keras within 0.001")

def validate_lgbm(model_path, onnx_path, num_features):
    """Compare LightGBM and ONNX predictions on random inputs."""
    booster = lgb.Booster(model_file=model_path)
    ort_session = ort.InferenceSession(onnx_path)

    for i in range(100):
        test_input = np.random.rand(1, num_features).astype(np.float32)

        lgbm_pred = float(booster.predict(test_input)[0])
        ort_pred = float(ort_session.run(None, {'input': test_input})[0][0])

        diff = abs(lgbm_pred - ort_pred)
        assert diff < 0.0001, f"Test {i}: LightGBM={lgbm_pred:.6f}, ONNX={ort_pred:.6f}, diff={diff:.6f}"

    print(f"PASS: {onnx_path} matches LightGBM within 0.0001")
```

### 4.4 Step 4: Import to Unity Sentis

Copy the 5 `.onnx` files to `Assets/Resources/Models/` in the Unity project.

```csharp
// Loading an ONNX model in Sentis
using Unity.Sentis;

ModelAsset modelAsset = Resources.Load<ModelAsset>("Models/smithing");
Model runtimeModel = ModelLoader.Load(modelAsset);
Worker worker = new Worker(runtimeModel, BackendType.GPUCompute);

// Prepare input tensor
TensorFloat inputTensor = new TensorFloat(new TensorShape(1, 36, 36, 3), pixelData);

// Run inference
worker.Schedule(inputTensor);

// Read output
TensorFloat outputTensor = worker.PeekOutput() as TensorFloat;
outputTensor.CompleteAllPendingOperations();
float probability = outputTensor[0];

// Cleanup
inputTensor.Dispose();
worker.Dispose();
```

**Backend Selection**:
- `BackendType.GPUCompute`: Best performance, requires compute shader support
- `BackendType.CPU`: Fallback for systems without GPU compute
- Consider detecting GPU support at runtime and falling back gracefully

---

## 5. C# Implementation

### 5.1 ClassifierResult.cs

```csharp
namespace Game1.Systems.Classifiers
{
    public struct ClassifierResult
    {
        public bool Valid { get; }
        public float Confidence { get; }
        public float Probability { get; }
        public string Discipline { get; }
        public string Error { get; }

        public bool IsError => Error != null;

        public ClassifierResult(bool valid, float confidence, float probability,
                                string discipline, string error = null)
        {
            Valid = valid;
            Confidence = confidence;
            Probability = probability;
            Discipline = discipline;
            Error = error;
        }

        public static ClassifierResult CreateError(string discipline, string error)
            => new ClassifierResult(false, 0f, 0f, discipline, error);
    }
}
```

### 5.2 MaterialColorEncoder.cs

Port the exact HSV encoding logic. Key method:

```csharp
public Vector3 Encode(string materialId)
{
    if (materialId == null)
        return Vector3.zero; // (0, 0, 0) black

    var matData = GetMaterialData(materialId);
    if (matData == null)
        return new Vector3(0.3f, 0.3f, 0.3f); // gray

    // Category -> Hue
    float hue = GetCategoryHue(matData.Category, matData.Tags);

    // Tier -> Value
    float value = TierValues.GetValueOrDefault(matData.Tier, 0.5f);

    // Tags -> Saturation
    float saturation = ComputeSaturation(matData.Category, matData.Tags);

    // HSV -> RGB
    Color rgb = Color.HSVToRGB(hue / 360f, saturation, value);
    return new Vector3(rgb.r, rgb.g, rgb.b);
}
```

### 5.3 SmithingPreprocessor.cs

Responsible for converting smithing UI grid state into a 36x36x3 float array suitable for the CNN model.

```csharp
public class SmithingPreprocessor
{
    private const int ImgSize = 36;
    private const int CellSize = 4;
    private const int GridSize = 9;

    private readonly MaterialColorEncoder _encoder;
    private readonly Dictionary<string, float[,]> _categoryShapes;
    private readonly Dictionary<int, int> _tierFillSizes;

    public float[] Preprocess(Dictionary<(int,int), PlacedMaterial> grid,
                              int stationGridSize)
    {
        // 1. Build 9x9 grid
        // 2. For each cell: get color, shape mask, tier mask
        // 3. Combine and place in image array
        // 4. Return flat float array [36*36*3] in row-major, channel-last order
    }
}
```

### 5.4 AdornmentPreprocessor.cs

Responsible for converting adornment vertex/shape state into a 56x56x3 float array.

```csharp
public class AdornmentPreprocessor
{
    private const int ImgSize = 56;
    private const int CoordRange = 7;

    private readonly MaterialColorEncoder _encoder;

    public float[] Preprocess(Dictionary<string, PlacedMaterial> vertices,
                              List<ShapeData> shapes)
    {
        // 1. Create 56x56x3 zero array
        // 2. Draw edges via Bresenham with thickness=2 and blending
        // 3. Draw vertex circles (radius=3)
        // 4. Return flat float array
    }

    private (int px, int py) CoordToPixel(int x, int y)
        => ((x + CoordRange) * 4, (CoordRange - y) * 4);
}
```

### 5.5 AlchemyFeatureExtractor.cs

```csharp
public class AlchemyFeatureExtractor
{
    private const int FeatureCount = 34;
    private const int MaxPositions = 6;

    public float[] Extract(List<SlotData> slots, int stationTier)
    {
        float[] features = new float[FeatureCount];
        int idx = 0;

        // Basic counts (3)
        features[idx++] = numIngredients;
        features[idx++] = totalQty;
        features[idx++] = totalQty / Mathf.Max(1, numIngredients);

        // Per-position (6 * 3 = 18)
        for (int pos = 0; pos < MaxPositions; pos++) { ... }

        // Diversity (1), categories (5), refinement (1)
        // Tier stats (3), sequential patterns (2), station (1)

        Debug.Assert(idx == FeatureCount);
        return features;
    }
}
```

### 5.6 RefiningFeatureExtractor.cs

```csharp
public class RefiningFeatureExtractor
{
    private const int FeatureCount = 19;

    public float[] Extract(List<SlotData> coreSlots,
                           List<SlotData> surroundingSlots,
                           int stationTier)
    {
        // 19 features in exact order per Section 3.5
    }
}
```

### 5.7 EngineeringFeatureExtractor.cs

```csharp
public class EngineeringFeatureExtractor
{
    private const int FeatureCount = 28;
    private static readonly string[] SlotTypeOrder = {
        "FRAME", "FUNCTION", "POWER", "MODIFIER",
        "UTILITY", "ENHANCEMENT", "CORE", "CATALYST"
    };

    public float[] Extract(Dictionary<string, List<SlotData>> slots,
                           int stationTier)
    {
        // 28 features in exact order per Section 3.6
    }
}
```

### 5.8 ClassifierManager.cs

```csharp
public class ClassifierManager
{
    private static ClassifierManager _instance;
    private readonly Dictionary<string, Worker> _workers;
    private readonly Dictionary<string, Model> _models;
    private readonly MaterialColorEncoder _encoder;

    public ClassifierResult Validate(string discipline, object uiState)
    {
        // 1. Preprocess UI state to model input
        // 2. Create input tensor
        // 3. Schedule worker
        // 4. Read output probability
        // 5. Compare to threshold
        // 6. Return ClassifierResult
    }

    public void Preload(string discipline = null) { /* Load models eagerly */ }
    public void Unload(string discipline = null) { /* Dispose workers */ }
}
```

---

## 6. Golden File Testing

### 6.1 Golden File Generation (Python)

Run the Python preprocessing on a curated set of test cases and save the complete pipeline:

```python
# scripts/generate_golden_files.py
import json
import numpy as np

def generate_smithing_golden(classifier_manager, test_cases):
    """Generate golden files for smithing classifier."""
    results = []
    for case in test_cases:
        # case = {'grid': {(x,y): material_id, ...}, 'station_grid_size': 5}

        # Run preprocessing
        image = renderer._grid_to_image(build_grid(case))

        # Run prediction
        prob, _ = backend.predict(image)

        results.append({
            'input': case,
            'preprocessed_image': image.tolist(),  # Full 36x36x3 array
            'image_checksum': float(np.sum(image)),
            'image_nonzero_count': int(np.count_nonzero(image)),
            'prediction': float(prob),
            'valid': bool(prob >= 0.5)
        })

    with open('tests/golden_files/smithing_golden.json', 'w') as f:
        json.dump(results, f, indent=2)
```

### 6.2 Test Case Categories (50+ per model)

For each model, golden files should include:

**Basic cases (10)**:
- Empty grid/slots (all zeros)
- Single material in one position
- Two materials of same category
- Two materials of different categories
- All positions filled with same material

**Category coverage (10)**:
- One test per material category (metal, wood, stone, gem, monster_drop, elemental)
- Mixed categories in various positions

**Tier coverage (8)**:
- T1-only, T2-only, T3-only, T4-only
- Mixed tiers (ascending, descending, random)

**Tag coverage (6)**:
- Material with 'legendary' tag
- Material with 'magical' tag
- Material with elemental sub-tags (fire, ice, etc.)
- Stone category (saturation=0.2 base)

**Edge cases (6)**:
- Unknown material IDs (should produce gray)
- Materials with no tags
- Station tier boundaries (1, 2, 3, 4)

**Valid recipe reproductions (10+)**:
- Known valid recipes from the training data
- Known invalid recipes from the training data

### 6.3 C# Golden File Validation

```csharp
[Test]
public void SmithingPreprocessor_GoldenFileTests()
{
    var goldenData = LoadGoldenFile("smithing_golden.json");

    foreach (var testCase in goldenData)
    {
        // Run C# preprocessing
        float[] csharpImage = preprocessor.Preprocess(testCase.Grid, testCase.GridSize);

        // Compare preprocessed output pixel-by-pixel
        float[] expectedImage = testCase.PreprocessedImage;
        Assert.AreEqual(expectedImage.Length, csharpImage.Length);

        for (int i = 0; i < expectedImage.Length; i++)
        {
            Assert.AreEqual(expectedImage[i], csharpImage[i], 0.001f,
                $"Pixel mismatch at index {i}");
        }

        // Compare prediction
        float csharpPred = RunInference("smithing", csharpImage);
        Assert.AreEqual(testCase.Prediction, csharpPred, 0.01f,
            "Prediction mismatch");
    }
}
```

### 6.4 Tolerances

| Comparison | Tolerance | Rationale |
|------------|-----------|-----------|
| Image pixels (CNN input) | +/- 0.001 | HSV->RGB floating point differences |
| Feature values (LightGBM input) | +/- 0.0001 | Mean/std computation precision |
| CNN predictions | +/- 0.01 | GPU vs CPU, ONNX vs Keras differences |
| LightGBM predictions | +/- 0.001 | Tree traversal should be near-exact |
| Valid/Invalid classification | EXACT match | Binary decision must agree |

---

## 7. Quality Control

### 7.1 Pre-Migration Checklist

- [ ] Generate golden files from Python (50+ per model, all 5 disciplines)
- [ ] Verify ONNX conversion succeeds for all 5 models (no unsupported ops)
- [ ] Validate ONNX predictions match native predictions (100 random inputs each)
- [ ] Document exact Python library versions (TensorFlow, LightGBM, NumPy)
- [ ] Verify Unity Sentis supports the ONNX opset used (test with empty Unity project)
- [ ] Confirm `Color.HSVToRGB` matches `colorsys.hsv_to_rgb` for all test HSV values

### 7.2 Per-Model QC Checklist

For each of the 5 models:

- [ ] ONNX file loads in Unity Sentis without errors
- [ ] Model input shape matches expected dimensions
- [ ] Model output shape is `[1, 1]` (single probability)
- [ ] C# preprocessing output matches golden files (pixel/feature comparison)
- [ ] Inference predictions match golden files within tolerance
- [ ] Valid/Invalid classification agrees on all golden file test cases
- [ ] Performance: preprocessing + inference < 100ms per prediction
- [ ] Memory: model fits within reasonable allocation (< 50MB per model)
- [ ] Warmup prediction completes without error (first inference compiles graph)

### 7.3 Phase 5 Quality Gate

All of the following must pass before Phase 5 is considered complete:

- [ ] All 5 ONNX models load successfully in Unity Sentis
- [ ] All preprocessing C# code produces output matching Python golden files
- [ ] All model predictions match golden files within specified tolerances
- [ ] No golden file test case produces a valid/invalid classification disagreement
- [ ] Performance is acceptable (< 100ms per prediction on target hardware)
- [ ] ClassifierManager can preload and unload models without memory leaks
- [ ] Integration with crafting UI triggers validation correctly
- [ ] Graceful fallback when model file is missing (returns error result, no crash)
- [ ] All C# unit tests pass
- [ ] Code review confirms all preprocessing constants match Python exactly

---

## 8. Risks and Mitigations

### 8.1 ONNX Operator Support

**Risk**: Unity Sentis may not support all ONNX operators used by the converted models. LightGBM tree ensemble operators are particularly prone to compatibility issues.

**Mitigation**:
- Test ONNX import in Sentis early (before writing C# preprocessors)
- If Sentis lacks tree ensemble support, consider: (a) using ONNX Runtime native plugin instead, (b) implementing tree traversal in C# directly from the LightGBM text model, or (c) converting LightGBM to a simple neural network approximation
- Keep the opset version at 15 or below for maximum compatibility

### 8.2 Floating Point Differences

**Risk**: GPU compute (Sentis) may produce slightly different floating point results compared to CPU (Python). IEEE 754 rounding differences between platforms can compound through many operations.

**Mitigation**:
- Use generous tolerances for prediction comparison (+/- 0.01 for CNN, +/- 0.001 for LightGBM)
- Verify that classification decisions (valid/invalid) agree exactly -- small numerical differences that do not flip the decision are acceptable
- Test on both `BackendType.GPUCompute` and `BackendType.CPU` to identify platform-specific issues

### 8.3 Feature Order Sensitivity

**Risk**: LightGBM models are extremely sensitive to feature order. A single swap of two features will silently produce incorrect predictions without any error.

**Mitigation**:
- The feature index tables in Sections 3.4-3.6 are the authoritative reference
- C# extractors must use explicit index counters, not dictionary iteration (which has non-deterministic order in some implementations)
- Golden file tests compare feature vectors element-by-element, catching any reordering
- Add assertion: `Debug.Assert(idx == FeatureCount)` at end of every extractor

### 8.4 Image Resize Interpolation

**Risk**: If any resize operation is needed, different interpolation methods (nearest, bilinear, bicubic) will produce different pixel values.

**Mitigation**: The current Python code does NOT resize. The 9x9 grid with 4x4 pixel cells produces exactly 36x36. The adornment renderer writes directly to a 56x56 canvas. Verify that no resize step is introduced in the C# implementation.

### 8.5 Bresenham Algorithm Precision

**Risk**: The adornment preprocessor uses Bresenham's line algorithm with thickness and blending. Different implementations can produce different pixel patterns, especially at endpoints and with thick lines.

**Mitigation**:
- Port the exact Python Bresenham implementation line-by-line (source: lines 475-502)
- Golden file tests for adornments must include shapes with lines at various angles
- Compare adornment images pixel-by-pixel, not just checksums

### 8.6 NumPy vs C# Floating Point Semantics

**Risk**: `np.mean()`, `np.std()`, and `np.max()` have specific behaviors with empty arrays and single-element arrays. C# LINQ equivalents may differ.

**Mitigation**:
- `np.mean([])` -> Python raises error, but the code guards with `if tiers else 0`
- `np.std([x])` -> returns 0.0 (population std, not sample std). C# must use population std (divide by N, not N-1)
- `np.max([])` -> raises error, guarded by `if tiers else 0`
- Explicitly test these edge cases in golden files

### 8.7 Model Loading Time

**Risk**: Loading 5 ONNX models and compiling Sentis workers on game startup may cause noticeable delay.

**Mitigation**:
- Use lazy loading: only load models when the crafting UI opens (matching Python behavior)
- Run warmup predictions on background thread
- Show loading indicator during model initialization (Python already does this via `_get_classifier_loading_state()`)
- Preload only the discipline being used, not all 5

---

## 9. Estimated Effort

| Task | Estimated Hours |
|------|----------------|
| ONNX conversion scripts (CNN + LightGBM) | 4 |
| ONNX validation (Python) | 3 |
| Golden file generation script | 4 |
| MaterialColorEncoder.cs | 3 |
| SmithingPreprocessor.cs | 4 |
| AdornmentPreprocessor.cs (Bresenham + circles) | 6 |
| AlchemyFeatureExtractor.cs | 3 |
| RefiningFeatureExtractor.cs | 2 |
| EngineeringFeatureExtractor.cs | 3 |
| ClassifierManager.cs + ClassifierResult.cs + ClassifierConfig.cs | 4 |
| Sentis integration + tensor handling | 4 |
| Golden file C# test framework | 3 |
| Unit tests (all 5 preprocessors) | 6 |
| Integration testing + debugging | 6 |
| Performance optimization | 3 |
| **Total** | **~58 hours** |

---

## 10. Success Criteria

Phase 5 is complete when:

1. All 5 ONNX models are converted and validated against Python originals
2. All 5 C# preprocessors produce output matching golden files within tolerance
3. All model predictions in Unity Sentis match golden file expected values
4. No valid/invalid classification disagreements exist across all golden file test cases
5. Preprocessing + inference completes in < 100ms per prediction
6. ClassifierManager supports preload, validate, and unload lifecycle
7. Graceful fallback behavior when models are unavailable (error result, no crash)
8. All unit tests and golden file tests pass
9. Code review confirms no hardcoded constants deviate from Python source
10. Integration smoke test: crafting UI triggers validation and displays correct result

**Next Phase**: Phase 5 feeds into the crafting UI integration phase, where the ClassifierManager is wired into the interactive crafting screens to validate player-invented recipes before LLM generation.
