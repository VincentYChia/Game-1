# Implementation Plan: Classifier Training System Updates

**Created**: 2026-02-02
**Status**: PLANNING COMPLETE - READY FOR IMPLEMENTATION

---

## Understanding Summary

### Color Encoding System (HSV)
From `crafting_classifier.py:MaterialColorEncoder`:

| Component | Maps To | Values |
|-----------|---------|--------|
| **HUE** | Category | metal=210°, wood=30°, stone=0°, monster_drop=300°, elemental=varies |
| **VALUE** | Tier | T1=0.50, T2=0.65, T3=0.80, T4=0.95 |
| **SATURATION** | Tags | stone=0.2, base=0.6, +0.2 legendary/mythical, +0.1 magical/ancient |

**CRITICAL**: Hue must stay constant (it's the category). Vary VALUE and SATURATION to simulate new materials within the same category.

### Material Substitution Rules
From `valid_smithing_data.py:find_substitutable_materials`:

**HARD REQUIREMENTS** (must match exactly):
1. Same category (metal→metal, wood→wood, etc.)
2. Same refined/basic status (refined tag must match)

**SUBSTITUTION RULES** (one must be true):
- **Rule 1**: ALL tags identical → can substitute at ANY tier
- **Rule 2**: Tier ±1 AND ≥2 matching tags → can substitute

### Game Model Paths
From `crafting_classifier.py:DEFAULT_CONFIGS`:

```
Smithing:    Scaled JSON Development/Convolution Neural Network (CNN)/Smithing/batch 4 (batch 3, no stations)/excellent_minimal_batch_20.keras
Adornments:  Scaled JSON Development/Convolution Neural Network (CNN)/Adornment/smart_search_results/best_original_20260124_185830_f10.9520_model.keras
Alchemy:     Scaled JSON Development/Simple Classifiers (LightGBM)/alchemy_lightGBM/alchemy_model.txt
Refining:    Scaled JSON Development/Simple Classifiers (LightGBM)/refining_lightGBM/refining_model.txt
Engineering: Scaled JSON Development/Simple Classifiers (LightGBM)/engineering_lightGBM/engineering_model.txt
```

---

## Changes Needed

### 1. Fix Color Augmentation (CNN)

**File**: `color_augmentation.py`

**Current (WRONG)**:
- Varies HUE by ±30° per category
- This is wrong because HUE = CATEGORY

**Correct Approach**:
- Keep HUE constant (category stays same)
- Vary VALUE to simulate different tiers within same category: ±0.10
- Vary SATURATION to simulate different tag combinations: ±0.15

**Implementation**:
```python
# Keep hue constant
hue = base_hue  # NO VARIATION

# Vary value (tier) - simulate materials at different tiers
value_offset = random.uniform(-0.10, 0.10)
value = max(0.3, min(0.95, base_val + value_offset))

# Vary saturation (tags) - simulate different tag combinations
sat_offset = random.uniform(-0.15, 0.15)
saturation = max(0.1, min(1.0, base_sat + sat_offset))
```

### 2. Category-Based Shapes + Tier Fill (Smithing CNN)

**File**: `valid_smithing_data_v2.py`

**Shape Vocabulary** (4x4 pixel masks):
- **metal**: Full square (solid block)
- **wood**: Horizontal lines (2 lines, simulating grain)
- **stone**: X pattern (angular/rocky)
- **monster_drop**: Diamond shape (organic)
- **elemental**: Plus/cross pattern (radiating energy)

**Tier Fill**:
- T1: 1x1 center pixel
- T2: 2x2 centered
- T3: 3x3 centered
- T4: Full 4x4

**Combined**: Shape mask × tier fill size

### 3. LightGBM Synthetic Material Injection

**Files**: `data_augment_GBM.py`, `data_augment_ref.py`

**Rules** (STRICT):
1. Only substitute augmentable materials (must pass substitution rules)
2. Never cross-category replace
3. Never break refined/basic status
4. Replace ALL instances of material (consistency)

**Implementation**:
- Generate synthetic materials with:
  - Same category
  - Same refined/basic status
  - Similar tags (keep essential, vary optional)
  - Varied tier within ±1
- Inject into recipes by replacing existing materials
- Each synthetic material gets assigned temporary features

### 4. Unified Training Script

**File**: `train_all_classifiers.py` (rewrite)

**Requirements**:
1. Run training scripts in order:
   - Smithing (CNN)
   - Adornments (CNN)
   - Alchemy (LightGBM)
   - Refining (LightGBM - separate script)
   - Engineering (LightGBM)

2. Model Selection Formula:
   ```
   score = val_accuracy - 2.0 * overfit_gap
   ```
   Higher is better. Penalizes overfitting 2x.

3. Archive old models:
   - Copy to `archived_classifiers/`
   - Rename with timestamp: `{discipline}_{original_name}_{timestamp}.{ext}`

4. Install new models:
   - Copy best model to EXACT path game expects
   - For Smithing: Must update `crafting_classifier.py:DEFAULT_CONFIGS` or copy to expected path

---

## Implementation Order

1. **Fix color_augmentation.py** - Change from hue variation to saturation/value variation
2. **Update valid_smithing_data_v2.py** - Add shape masks + tier fill
3. **Update data_augment_adornment_v2.py** - Use fixed color augmentation
4. **Enhance data_augment_GBM.py** - Add synthetic material injection
5. **Enhance data_augment_ref.py** - Add synthetic material injection (separate)
6. **Rewrite train_all_classifiers.py** - Proper orchestration and model selection

---

## Validation Checklist

Before committing, verify:
- [ ] Hue stays constant in color augmentation
- [ ] Value/saturation variation is within reasonable bounds
- [ ] Shape masks are visually distinct at 4x4
- [ ] Tier fill creates visible size differences
- [ ] Synthetic materials follow ALL substitution rules
- [ ] Training script selects by score = accuracy - 2*overfit
- [ ] Old models properly archived with timestamps
- [ ] New models copied to game-expected paths
