# Brainstorm: LightGBM Overfitting Solutions

**Goal**: Find the equivalent of "hue variation" for LightGBM features - techniques to prevent the model from memorizing specific material IDs or exact feature values, and instead learn generalizable patterns.

## The Overfitting Problem

Current LightGBM classifiers extract numeric features from recipes:
- **Alchemy**: 34 features (counts, positions, categories, tiers, patterns)
- **Refining**: 18 features (core/spoke counts, ratios, category dist, tier stats)
- **Engineering**: 28 features (slot types, category dist, tier stats)

**Key Issue**: The models see the same ~60 materials repeatedly and learn to recognize specific combinations rather than generalizable patterns. When a new material is introduced (even a valid substitute), the model may reject it because it's never seen that exact combination.

**Why CNNs and LightGBM Differ**:
- CNN inputs are continuous (RGB colors) - hue variation works
- LightGBM inputs include categorical mappings - harder to "blur"

---

## Brainstorm Ideas

### 1. Synthetic Material Injection (Recommended)
**Concept**: Generate "virtual" materials with valid properties and inject them into training data

**Implementation**:
- For each recipe, with probability P (e.g., 30%), substitute one material with a synthetic one
- Synthetic material has:
  - Same category as original
  - Same tier ± 1 (random)
  - Similar tags (random subset + some variation)
  - Random ID (never seen before)

**Feature Impact**:
- Category distribution: Same (category preserved)
- Tier statistics: Slightly varied
- Material diversity: +1 unique material
- Position features: Use synthetic tier/category

**Pros**:
- Directly addresses the problem
- Forces model to learn category/tier patterns, not material IDs
- Generalizes to any new material

**Cons**:
- More complex training data generation
- Must ensure synthetics are "valid" substitutes

### 2. Feature Value Noise Injection
**Concept**: Add small random noise to continuous features

**Implementation**:
```python
# For tier statistics, add noise ±0.2
mean_tier_noisy = mean_tier + uniform(-0.2, 0.2)

# For quantities, add ±1
total_qty_noisy = total_qty + randint(-1, 1)

# For distributions, add small perturbations
category_dist_noisy = category_dist + uniform(-0.1, 0.1)
category_dist_noisy = normalize(category_dist_noisy)
```

**Pros**:
- Easy to implement
- Simulates measurement uncertainty
- Forces model to learn ranges, not exact values

**Cons**:
- May not address core issue (material memorization)
- Could introduce invalid noise for discrete features

### 3. Categorical Feature Smoothing
**Concept**: For features like category indices, use probabilistic encoding

**Instead of**: `category_idx = 1` (for metal)
**Use**: `category_vector = [0.1, 0.8, 0.05, 0.03, 0.02]` (mostly metal, small chance of others)

**Implementation**:
- One-hot encode categories with soft probabilities
- During training, add random "confusion" to category assignments
- Respects category similarity (e.g., monster_drop might rarely be confused with elemental)

**Pros**:
- Prevents hard memorization of category mappings
- Can encode semantic similarity between categories

**Cons**:
- Changes feature dimensionality
- More complex feature extraction

### 4. Tier Smoothing
**Concept**: Instead of exact tiers, use tier probabilities

**Current**: `tier = 3`
**Proposed**: `tier_dist = [0.0, 0.1, 0.7, 0.2]` (mostly T3, some T2/T4)

**Implementation**:
- For position features, replace tier with 4-dim vector
- Or add noise: `tier_noisy = tier + uniform(-0.5, 0.5)`

**Pros**:
- Simulates "adjacent tier" materials
- Encourages learning tier relationships

**Cons**:
- Increases feature count if using vectors

### 5. Material Name Abstraction
**Concept**: Don't encode material IDs at all - only encode properties

**Current Features (example)**:
- slot_1_tier = 2
- slot_1_category_idx = 1 (metal)
- slot_1_qty = 3

**No material ID is used** - this is actually already the case!

**Key Insight**: Looking at the current feature extractors, they DON'T use material IDs directly. They extract:
- Tier
- Category (as index)
- Quantity
- Tags (as distributions)

**So why does overfitting happen?**
- Because specific tier + category combinations appear repeatedly
- Model learns "tier 2 metal in position 1 + tier 3 elemental = valid"
- Doesn't generalize to new combinations

### 6. Position/Order Augmentation
**Concept**: For Alchemy (sequential), vary the slot positions

**Current**: Slot 1 must have material A, Slot 2 must have material B
**Augmented**: Valid with materials in any compatible order

**Already Implemented**: `augment_alchemy_permutations()` does this!

**Additional Ideas**:
- Also permute within slot types (e.g., swap positions of two metals)
- Randomly skip slots (add empty slot padding)

### 7. Abstract Pattern Augmentation
**Concept**: Generate recipes that follow valid PATTERNS but with random materials

**Valid Pattern Examples**:
- Refining: 1 refined hub + 1-3 elemental spokes
- Alchemy: 3-4 ingredients with ascending tiers
- Engineering: FRAME + FUNCTION + POWER with any valid materials

**Implementation**:
- Define "recipe templates" as structural rules
- Fill templates with random valid materials
- Generate many synthetic-but-valid recipes

**Pros**:
- Directly teaches pattern recognition
- Massive augmentation potential

**Cons**:
- Must correctly define what patterns are "valid"
- Risk of generating actually-invalid recipes

### 8. Contrastive Learning Approach
**Concept**: Train on pairs of (similar_valid, similar_invalid)

**Implementation**:
- For each valid recipe, generate a nearly-identical invalid one
- Teach model to distinguish based on subtle differences
- Example: Valid recipe vs same recipe with one wrong-category material

**Pros**:
- Learns discriminative features
- Focuses on what makes a recipe invalid

**Cons**:
- Different training paradigm
- May need architectural changes

### 9. Ensemble with Different Feature Sets
**Concept**: Train multiple models, each with slightly different features

**Model A**: Full 34 features
**Model B**: Only tier + category features (no quantities)
**Model C**: Only structural features (slot counts, diversity)

**Final Prediction**: Average or vote across models

**Pros**:
- Robustness through diversity
- Different models capture different aspects

**Cons**:
- Slower inference (3x models)
- More complex deployment

### 10. Regularization Techniques
**Concept**: Apply stronger regularization to prevent overfitting

**LightGBM Options**:
- `lambda_l1`: L1 regularization on leaf weights
- `lambda_l2`: L2 regularization on leaf weights
- `min_data_in_leaf`: Require more samples per leaf
- `max_depth`: Limit tree depth
- `feature_fraction`: Randomly drop features per tree
- `bagging_fraction`: Use random subset of data per tree

**Current Settings** (check and potentially increase):
```python
params = {
    'lambda_l1': 0.1,        # Try 0.5-1.0
    'lambda_l2': 0.1,        # Try 0.5-1.0
    'min_data_in_leaf': 20,  # Try 50-100
    'max_depth': 6,          # Try 4-5
    'feature_fraction': 0.8, # Try 0.6-0.7
    'bagging_fraction': 0.8, # Try 0.6-0.7
}
```

**Pros**:
- Easy to tune
- Standard ML practice

**Cons**:
- May reduce accuracy on validation set
- Doesn't address root cause

---

## Recommendation Matrix

| Approach | Implementation Effort | Generalization Impact | Risk | Priority |
|----------|----------------------|----------------------|------|----------|
| Synthetic Material Injection | Medium | Very High | Low | **HIGH** |
| Feature Value Noise | Low | Medium | Low | Medium |
| Categorical Smoothing | Medium | Medium | Medium | Low |
| Tier Smoothing | Low | Medium | Low | Medium |
| Position Augmentation | Low (exists) | Medium | Low | Medium |
| Abstract Pattern Gen | High | Very High | Medium | Medium |
| Contrastive Learning | High | High | High | Low |
| Ensemble Models | Medium | Medium | Low | Low |
| Regularization Tuning | Low | Medium | Low | **HIGH** |

---

## Top Recommendations

### 1. Synthetic Material Injection (Primary Solution)

```python
def generate_synthetic_material(base_material, materials_dict):
    """Create a synthetic substitute for a material."""
    base = materials_dict[base_material]

    synthetic = {
        'materialId': f'synthetic_{uuid4().hex[:8]}',
        'category': base['category'],
        'tier': base['tier'] + random.choice([-1, 0, 0, 1]),  # Mostly same tier
        'rarity': base.get('rarity', 'common'),
        'metadata': {
            'tags': augment_tags(base['metadata']['tags'])
        }
    }
    # Clamp tier to 1-4
    synthetic['tier'] = max(1, min(4, synthetic['tier']))
    return synthetic

def augment_tags(tags):
    """Create similar but not identical tags."""
    base_tags = set(tags)
    # Keep essential tags (refined/basic, category)
    essential = {'refined', 'basic', 'metal', 'wood', 'stone', 'elemental'}
    keep = base_tags & essential
    # Randomly modify non-essential tags
    optional = base_tags - essential
    # ... add/remove 0-2 optional tags
    return list(keep | optional)
```

### 2. Regularization Tuning (Quick Win)

Add to trainer:
```python
strong_regularization_params = {
    'lambda_l1': 0.5,
    'lambda_l2': 0.5,
    'min_data_in_leaf': 50,
    'max_depth': 5,
    'feature_fraction': 0.7,
    'bagging_fraction': 0.7,
    'num_leaves': 20,  # Reduce from default 31
}
```

### 3. Feature Value Noise (Easy Add-On)

```python
def add_feature_noise(features, noise_level=0.1):
    """Add small noise to continuous features."""
    noised = features.copy()

    # Tier statistics (indices vary by discipline)
    tier_indices = [...]  # e.g., mean_tier, max_tier, std_tier
    for idx in tier_indices:
        noised[idx] += np.random.uniform(-0.3, 0.3)

    # Quantity features
    qty_indices = [...]
    for idx in qty_indices:
        noised[idx] += np.random.randint(-1, 2)  # ±1

    return noised
```

---

## Implementation Plan

### Phase 1: Quick Wins
1. **Add regularization tuning** to LightGBM trainer
2. **Add feature noise** option to data augmentation

### Phase 2: Synthetic Materials
1. Create `synthetic_material_generator.py`
2. Integrate into `data_augment_GBM.py`
3. Generate synthetic-augmented datasets
4. Retrain and compare

### Phase 3: Validation
1. Test with held-out "new" materials
2. Measure generalization to unseen material combinations
3. Compare baseline vs augmented performance

---

## Key Insight

**The core problem isn't feature engineering - it's data diversity.**

The models aren't overfitting to features, they're overfitting to the limited set of material combinations in training data. The solution is to massively expand the training data with synthetic but valid combinations.

This is analogous to how hue variation for CNNs creates "virtual" color variations. For LightGBM, we need "virtual" material variations that maintain valid structural patterns but use materials the model hasn't memorized.
