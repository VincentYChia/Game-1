# Crafting Classifier & LLM Integration Plan

**Created**: January 25, 2026
**Purpose**: Integrate 5 crafting classifiers and LLM item generation into the Game-1 crafting system
**Target Branch**: `claude/integrate-crafting-llm-XZfjD`

---

## Executive Summary

This plan integrates:
1. **5 Classifiers** (2 CNN + 3 LightGBM) for recipe validation in interactive mode
2. **LLM Item Generation** via Claude API for creating new items from valid recipes
3. **Save System Extension** to persist player-invented recipes

**Complexity Level**: High (touches multiple core systems, requires ML inference integration)

---

## Part 1: Classifier Integration into Interactive Mode

### 1.1 Classifier Mapping by Discipline

| Discipline | Classifier Type | Model Location | Input Format |
|------------|-----------------|----------------|--------------|
| **Smithing** | CNN | `CNN/Smithing/batch 4 (batch 3, no stations)/excellent_minimal_*.keras` | 36×36×3 RGB image |
| **Adornments** | CNN | `CNN/Adornment/smart_search_results/best_*.keras` | 56×56×3 RGB image |
| **Alchemy** | LightGBM | `LightGBM/alchemy_lightGBM/alchemy_model.txt` | ~34 feature vector |
| **Refining** | LightGBM | `LightGBM/refining_lightGBM/refining_model.txt` | ~27 feature vector |
| **Engineering** | LightGBM | `LightGBM/engineering_lightGBM/engineering_model.txt` | ~35 feature vector |

### 1.2 Data Format Transformations

#### **Smithing CNN Input (36×36×3 RGB)**
Transform from `InteractiveSmithingUI.grid` → CNN input:

```python
# Current: InteractiveSmithingUI.grid = {(x,y): PlacedMaterial}
# Required: 9×9 material grid → 36×36 RGB image

def transform_smithing_ui_to_cnn(interactive_ui):
    """Transform InteractiveSmithingUI state to CNN input format"""
    # 1. Create 9×9 grid from UI grid
    grid = [[None] * 9 for _ in range(9)]

    for (x, y), placed_mat in interactive_ui.grid.items():
        # UI uses (x, y) where x=column, y=row
        # Center in 9×9 grid based on station tier
        offset = (9 - interactive_ui.grid_size) // 2
        grid_x = offset + x
        grid_y = offset + y
        if 0 <= grid_x < 9 and 0 <= grid_y < 9:
            grid[grid_y][grid_x] = placed_mat.item_id

    # 2. Convert grid to image (use RecipeValidator.grid_to_image)
    # Each cell → 4×4 pixels with HSV→RGB color encoding
    return grid
```

**Color Encoding (from CNN_game_runner_smithing.py)**:
- **Hue**: Category-based (metal=210°, wood=30°, stone=0°, monster_drop=300°, elemental=varies)
- **Saturation**: Base 0.6, stone=0.2, legendary/mythical +0.2, magical/ancient +0.1
- **Value**: Tier-based (T1=0.50, T2=0.65, T3=0.80, T4=0.95)

#### **Adornments CNN Input (56×56×3 RGB)**
Transform from `InteractiveAdornmentsUI` → CNN input:

```python
def transform_adornments_ui_to_cnn(interactive_ui):
    """Transform InteractiveAdornmentsUI state to CNN input format"""
    # vertices format for CNN: {"x,y": {"materialId": "..."}}
    vertices = {}
    for coord_key, placed_mat in interactive_ui.vertices.items():
        vertices[coord_key] = {"materialId": placed_mat.item_id}

    # shapes format for CNN: [{"type": "...", "vertices": ["x,y", ...]}]
    shapes = []
    for shape_data in interactive_ui.shapes:
        shapes.append({
            "type": shape_data["type"],
            "vertices": shape_data["vertices"]
        })

    return vertices, shapes
```

**Rendering Pipeline (from CNN_tester_adornment.py)**:
1. Coordinate space: [-7, 7] × [-7, 7]
2. Pixel mapping: `(x,y) → (int((x+7)×4), int((7-y)×4))`
3. Draw edges as lines with color blending from endpoint materials
4. Draw vertices as filled circles (radius=3)

#### **Alchemy LightGBM Input (~34 features)**
Transform from `InteractiveAlchemyUI.slots` → feature vector:

```python
def transform_alchemy_ui_to_lightgbm(interactive_ui):
    """Transform InteractiveAlchemyUI state to LightGBM features"""
    # Build recipe dict in expected format
    ingredients = []
    for slot_idx, placed_mat in enumerate(interactive_ui.slots):
        if placed_mat:
            ingredients.append({
                "slot": slot_idx + 1,  # 1-indexed
                "materialId": placed_mat.item_id,
                "quantity": placed_mat.quantity
            })

    recipe = {
        "ingredients": ingredients,
        "stationTier": interactive_ui.station_tier
    }

    # Use RecipeFeatureExtractor.extract_alchemy_features()
    return recipe
```

**Feature Vector Structure** (from LightGBM_runner.py lines 138-214):
- `num_ingredients`, `total_qty`, `avg_qty`
- Position-based (6 positions × 3 features): `tier_pos[N], qty_pos[N], cat_idx_pos[N]`
- `unique_materials_count`
- Category distribution (one per category)
- Refinement distribution (one per refinement type)
- Tier statistics: mean, max, std
- Sequential patterns: tier_increases, tier_decreases
- `station_tier`

#### **Refining LightGBM Input (~27 features)**
Transform from `InteractiveRefiningUI` → feature vector:

```python
def transform_refining_ui_to_lightgbm(interactive_ui):
    """Transform InteractiveRefiningUI state to LightGBM features"""
    core_inputs = []
    for placed_mat in interactive_ui.core_slots:
        if placed_mat:
            core_inputs.append({
                "materialId": placed_mat.item_id,
                "quantity": placed_mat.quantity
            })

    surrounding_inputs = []
    for placed_mat in interactive_ui.surrounding_slots:
        if placed_mat:
            surrounding_inputs.append({
                "materialId": placed_mat.item_id,
                "quantity": placed_mat.quantity
            })

    recipe = {
        "coreInputs": core_inputs,
        "surroundingInputs": surrounding_inputs,
        "stationTier": interactive_ui.station_tier
    }

    # Use RecipeFeatureExtractor.extract_refining_features()
    return recipe
```

**Feature Vector Structure** (from LightGBM_runner.py lines 77-136):
- `num_cores`, `num_spokes`, `core_qty_total`, `spoke_qty_total`
- Ratio features: `num_spokes/num_cores`, `spoke_qty/core_qty`
- `unique_materials_count`
- Category distribution (cores)
- Refinement distribution (cores)
- Tier statistics: mean/max core tiers, mean/max spoke tiers
- Tier mismatch
- `station_tier`

#### **Engineering LightGBM Input (~35 features)**
Transform from `InteractiveEngineeringUI` → feature vector:

```python
def transform_engineering_ui_to_lightgbm(interactive_ui):
    """Transform InteractiveEngineeringUI state to LightGBM features"""
    slots = []
    for slot_type, materials in interactive_ui.slots.items():
        for placed_mat in materials:
            slots.append({
                "type": slot_type,
                "materialId": placed_mat.item_id,
                "quantity": placed_mat.quantity
            })

    recipe = {
        "slots": slots,
        "stationTier": interactive_ui.station_tier
    }

    # Use RecipeFeatureExtractor.extract_engineering_features()
    return recipe
```

**Feature Vector Structure** (from LightGBM_runner.py lines 216-282):
- `num_slots`, `total_qty`
- Slot type counts (8): FRAME, FUNCTION, POWER, MODIFIER, UTILITY, ENHANCEMENT, CORE, CATALYST
- `unique_slot_types`
- Critical slot presence (binary): has_FRAME, has_FUNCTION, has_POWER
- `unique_materials_count`
- Category distribution
- Refinement distribution
- Tier statistics: mean, max, std
- Quantity by slot type: FRAME_qty, POWER_qty, FUNCTION_qty
- `station_tier`

---

### 1.3 UI Changes Required

#### **New Button: "INVENT RECIPE"**
Add to each interactive crafting UI (in `renderer.py` or dedicated UI module):

```python
# Button placement in interactive crafting UI
INVENT_RECIPE_BUTTON = {
    "text": "INVENT RECIPE",
    "position": (panel_right - 200, panel_bottom - 80),
    "size": (180, 50),
    "color": (100, 180, 100),  # Green tint
    "hover_color": (120, 200, 120),
    "enabled_condition": lambda ui: len(ui.get_placed_materials()) >= 2
}
```

#### **Validation Feedback Display**
Display after classifier prediction:

```python
# Success feedback
SUCCESS_MESSAGE = {
    "text": "✓ VALID RECIPE DISCOVERED!",
    "color": (50, 200, 50),  # Green
    "subtext": "Generating item...",
    "duration_ms": 2000
}

# Failure feedback
FAILURE_MESSAGE = {
    "text": "✗ INVALID COMBINATION",
    "color": (200, 100, 100),  # Red
    "subtext": "Try a different arrangement",
    "confidence": "67% confident invalid",  # From classifier
    "duration_ms": 2000
}
```

---

### 1.4 New Module: `crafting_classifier.py`

Create at: `Game-1-modular/systems/crafting_classifier.py`

```python
"""
Crafting Recipe Classifier Integration
Validates player-invented recipes using CNN and LightGBM models
"""

import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

# Lazy imports for ML libraries (avoid startup overhead)
_tf = None
_lgb = None

def _get_tensorflow():
    global _tf
    if _tf is None:
        import tensorflow as tf
        _tf = tf
    return _tf

def _get_lightgbm():
    global _lgb
    if _lgb is None:
        import lightgbm as lgb
        _lgb = lgb
    return _lgb


@dataclass
class ClassifierResult:
    """Result from classifier prediction"""
    valid: bool
    confidence: float
    probability: float
    discipline: str


class CraftingClassifier:
    """Unified interface for all 5 crafting classifiers"""

    # Paths relative to Game-1 root
    MODEL_PATHS = {
        'smithing': {
            'type': 'cnn',
            'model': 'Scaled JSON Development/Convolution Neural Network (CNN)/Smithing/batch 4 (batch 3, no stations)/excellent_minimal_batch_20.keras',
            'img_size': 36
        },
        'adornments': {
            'type': 'cnn',
            'model': 'Scaled JSON Development/Convolution Neural Network (CNN)/Adornment/smart_search_results/best_original_20260124_185830_model.keras',
            'img_size': 56
        },
        'alchemy': {
            'type': 'lightgbm',
            'model': 'Scaled JSON Development/Simple Classifiers (LightGBM)/alchemy_lightGBM/alchemy_model.txt',
            'extractor': 'Scaled JSON Development/Simple Classifiers (LightGBM)/alchemy_lightGBM/alchemy_extractor.pkl'
        },
        'refining': {
            'type': 'lightgbm',
            'model': 'Scaled JSON Development/Simple Classifiers (LightGBM)/refining_lightGBM/refining_model.txt',
            'extractor': 'Scaled JSON Development/Simple Classifiers (LightGBM)/refining_lightGBM/refining_extractor.pkl'
        },
        'engineering': {
            'type': 'lightgbm',
            'model': 'Scaled JSON Development/Simple Classifiers (LightGBM)/engineering_lightGBM/engineering_model.txt',
            'extractor': 'Scaled JSON Development/Simple Classifiers (LightGBM)/engineering_lightGBM/engineering_extractor.pkl'
        }
    }

    def __init__(self, game_root: Path, materials_db):
        self.game_root = game_root
        self.materials_db = materials_db
        self._models = {}  # Lazy-loaded models
        self._extractors = {}  # Feature extractors for LightGBM

    def _load_model(self, discipline: str):
        """Lazy-load model on first use"""
        if discipline in self._models:
            return

        config = self.MODEL_PATHS[discipline]
        model_path = self.game_root / config['model']

        if config['type'] == 'cnn':
            tf = _get_tensorflow()
            self._models[discipline] = tf.keras.models.load_model(str(model_path))
            print(f"✓ Loaded {discipline} CNN model")

        elif config['type'] == 'lightgbm':
            lgb = _get_lightgbm()
            self._models[discipline] = lgb.Booster(model_file=str(model_path))

            # Load feature extractor
            import pickle
            extractor_path = self.game_root / config['extractor']
            with open(extractor_path, 'rb') as f:
                self._extractors[discipline] = pickle.load(f)
            print(f"✓ Loaded {discipline} LightGBM model")

    def validate(self, discipline: str, interactive_ui) -> ClassifierResult:
        """
        Validate a recipe from interactive UI state

        Args:
            discipline: One of 'smithing', 'adornments', 'alchemy', 'refining', 'engineering'
            interactive_ui: The InteractiveXUI instance with current placement

        Returns:
            ClassifierResult with valid/invalid and confidence
        """
        self._load_model(discipline)

        config = self.MODEL_PATHS[discipline]

        if config['type'] == 'cnn':
            return self._validate_cnn(discipline, interactive_ui)
        else:
            return self._validate_lightgbm(discipline, interactive_ui)

    def _validate_cnn(self, discipline: str, interactive_ui) -> ClassifierResult:
        """Validate using CNN model"""
        # Transform UI state to image
        if discipline == 'smithing':
            img = self._smithing_ui_to_image(interactive_ui)
        else:  # adornments
            img = self._adornments_ui_to_image(interactive_ui)

        # Add batch dimension and predict
        img_batch = np.expand_dims(img, axis=0)
        prob = float(self._models[discipline].predict(img_batch, verbose=0)[0][0])

        is_valid = prob >= 0.5
        confidence = prob if is_valid else (1 - prob)

        return ClassifierResult(
            valid=is_valid,
            confidence=confidence,
            probability=prob,
            discipline=discipline
        )

    def _validate_lightgbm(self, discipline: str, interactive_ui) -> ClassifierResult:
        """Validate using LightGBM model"""
        extractor = self._extractors[discipline]

        # Transform UI state to recipe dict
        if discipline == 'alchemy':
            recipe = self._alchemy_ui_to_recipe(interactive_ui)
            features = extractor.extract_alchemy_features(recipe)
        elif discipline == 'refining':
            recipe = self._refining_ui_to_recipe(interactive_ui)
            features = extractor.extract_refining_features(recipe)
        else:  # engineering
            recipe = self._engineering_ui_to_recipe(interactive_ui)
            features = extractor.extract_engineering_features(recipe)

        # Predict
        features = features.reshape(1, -1)
        model = self._models[discipline]
        prob = float(model.predict(features, num_iteration=model.best_iteration)[0])

        is_valid = prob >= 0.5
        confidence = prob if is_valid else (1 - prob)

        return ClassifierResult(
            valid=is_valid,
            confidence=confidence,
            probability=prob,
            discipline=discipline
        )

    # Transform methods (implement based on Section 1.2 above)
    def _smithing_ui_to_image(self, ui) -> np.ndarray:
        """Transform InteractiveSmithingUI → 36×36×3 image"""
        # Implementation from Section 1.2
        pass

    def _adornments_ui_to_image(self, ui) -> np.ndarray:
        """Transform InteractiveAdornmentsUI → 56×56×3 image"""
        # Implementation from Section 1.2
        pass

    def _alchemy_ui_to_recipe(self, ui) -> Dict:
        """Transform InteractiveAlchemyUI → recipe dict"""
        # Implementation from Section 1.2
        pass

    def _refining_ui_to_recipe(self, ui) -> Dict:
        """Transform InteractiveRefiningUI → recipe dict"""
        # Implementation from Section 1.2
        pass

    def _engineering_ui_to_recipe(self, ui) -> Dict:
        """Transform InteractiveEngineeringUI → recipe dict"""
        # Implementation from Section 1.2
        pass
```

---

## Part 2: LLM Integration for Item Generation

### 2.1 System Overview

When a classifier validates a recipe as valid:
1. Build input prompt from placed materials + station context
2. Select appropriate system prompt based on discipline
3. Call Claude API with few-shot examples
4. Parse and validate generated item JSON
5. Add to player's discovered recipes

### 2.2 Input Handler by Discipline

Create at: `Game-1-modular/systems/llm_item_generator.py`

```python
"""
LLM Item Generator
Generates new items from validated player-invented recipes
"""

import anthropic
import json
from typing import Dict, Any, Optional
from pathlib import Path


class ItemGenerator:
    """Generate items using Claude API based on recipe inputs"""

    SYSTEM_MAPPING = {
        'smithing': '1',      # System 1: Smithing Items
        'refining': '2',      # System 2: Refining Materials
        'alchemy': '3',       # System 3: Alchemy Items
        'engineering': '4',   # System 4: Engineering Devices
        'adornments': '5'     # System 5: Enchantments
    }

    def __init__(self, api_key: str, prompts_dir: Path, examples_path: Path):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.prompts_dir = prompts_dir
        self.examples = self._load_examples(examples_path)

    def _load_examples(self, path: Path) -> Dict:
        """Load few-shot examples"""
        with open(path, 'r') as f:
            return json.load(f)

    def _build_prompt(self, discipline: str, interactive_ui, station_tier: int) -> Dict:
        """Build input prompt from UI state"""

        if discipline == 'smithing':
            return self._build_smithing_prompt(interactive_ui, station_tier)
        elif discipline == 'refining':
            return self._build_refining_prompt(interactive_ui, station_tier)
        elif discipline == 'alchemy':
            return self._build_alchemy_prompt(interactive_ui, station_tier)
        elif discipline == 'engineering':
            return self._build_engineering_prompt(interactive_ui, station_tier)
        elif discipline == 'adornments':
            return self._build_adornments_prompt(interactive_ui, station_tier)

    def _build_smithing_prompt(self, ui, tier) -> Dict:
        """Build smithing recipe input for LLM"""
        inputs = []
        for (x, y), placed_mat in ui.grid.items():
            # Aggregate by material
            existing = next((inp for inp in inputs
                           if inp['materialId'] == placed_mat.item_id), None)
            if existing:
                existing['quantity'] += placed_mat.quantity
            else:
                inputs.append({
                    'materialId': placed_mat.item_id,
                    'quantity': placed_mat.quantity
                })

        # Calculate dominant material tier for narrative
        mat_db = MaterialDatabase.get_instance()
        max_tier = max(
            mat_db.get_material(inp['materialId']).tier
            for inp in inputs
        )

        return {
            'recipeId': f'invented_smithing_{uuid.uuid4().hex[:8]}',
            'stationType': 'smithing',
            'stationTier': tier,
            'inputs': inputs,
            'narrative': f'A tier {max_tier} item crafted from {len(inputs)} materials at a tier {tier} forge.'
        }

    def _build_refining_prompt(self, ui, tier) -> Dict:
        """Build refining recipe input for LLM"""
        core_inputs = []
        for placed_mat in ui.core_slots:
            if placed_mat:
                existing = next((inp for inp in core_inputs
                               if inp['materialId'] == placed_mat.item_id), None)
                if existing:
                    existing['quantity'] += placed_mat.quantity
                else:
                    core_inputs.append({
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })

        surrounding_inputs = []
        for placed_mat in ui.surrounding_slots:
            if placed_mat:
                existing = next((inp for inp in surrounding_inputs
                               if inp['materialId'] == placed_mat.item_id), None)
                if existing:
                    existing['quantity'] += placed_mat.quantity
                else:
                    surrounding_inputs.append({
                        'materialId': placed_mat.item_id,
                        'quantity': placed_mat.quantity
                    })

        return {
            'recipeId': f'invented_refining_{uuid.uuid4().hex[:8]}',
            'stationType': 'refining',
            'stationTier': tier,
            'coreInputs': core_inputs,
            'surroundingInputs': surrounding_inputs,
            'narrative': f'Material refined from {len(core_inputs)} core materials with {len(surrounding_inputs)} modifiers.'
        }

    def _build_alchemy_prompt(self, ui, tier) -> Dict:
        """Build alchemy recipe input for LLM"""
        ingredients = []
        for slot_idx, placed_mat in enumerate(ui.slots):
            if placed_mat:
                ingredients.append({
                    'slot': slot_idx + 1,
                    'materialId': placed_mat.item_id,
                    'quantity': placed_mat.quantity
                })

        return {
            'recipeId': f'invented_alchemy_{uuid.uuid4().hex[:8]}',
            'stationType': 'alchemy',
            'stationTier': tier,
            'ingredients': ingredients,
            'narrative': f'A potion brewed from {len(ingredients)} ingredients in sequence.'
        }

    def _build_engineering_prompt(self, ui, tier) -> Dict:
        """Build engineering recipe input for LLM"""
        slots = []
        for slot_type, materials in ui.slots.items():
            for placed_mat in materials:
                slots.append({
                    'type': slot_type,
                    'materialId': placed_mat.item_id,
                    'quantity': placed_mat.quantity
                })

        return {
            'recipeId': f'invented_engineering_{uuid.uuid4().hex[:8]}',
            'stationType': 'engineering',
            'stationTier': tier,
            'slots': slots,
            'narrative': f'A device constructed with {len(slots)} component slots.'
        }

    def _build_adornments_prompt(self, ui, tier) -> Dict:
        """Build adornments/enchanting recipe input for LLM"""
        vertices = {}
        for coord_key, placed_mat in ui.vertices.items():
            vertices[coord_key] = {
                'materialId': placed_mat.item_id,
                'quantity': placed_mat.quantity
            }

        shapes = [
            {'type': s['type'], 'vertices': s['vertices']}
            for s in ui.shapes
        ]

        return {
            'recipeId': f'invented_enchant_{uuid.uuid4().hex[:8]}',
            'stationType': 'adornments',
            'stationTier': tier,
            'placementMap': {
                'vertices': vertices,
                'shapes': shapes
            },
            'narrative': f'An enchantment formed from {len(vertices)} magical vertices in {len(shapes)} shapes.'
        }

    def generate(self, discipline: str, interactive_ui, station_tier: int) -> Dict:
        """
        Generate a new item from validated recipe

        Returns:
            Generated item definition dict, or error dict
        """
        # Build input prompt
        input_prompt = self._build_prompt(discipline, interactive_ui, station_tier)

        # Load system prompt
        system_key = self.SYSTEM_MAPPING[discipline]
        system_prompt_path = self.prompts_dir / f'system_{system_key}.txt'
        with open(system_prompt_path, 'r') as f:
            system_prompt = f.read()

        # Get few-shot examples
        examples = self.examples.get(system_key, [])

        # Build messages
        messages = []
        for example in examples[:3]:  # Use first 3 examples
            messages.append({
                "role": "user",
                "content": json.dumps(example["input"], indent=2)
            })
            messages.append({
                "role": "assistant",
                "content": json.dumps(example["output"], indent=2)
            })

        # Add test prompt
        messages.append({
            "role": "user",
            "content": json.dumps(input_prompt, indent=2)
        })

        # Call API
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                temperature=1.0,
                top_p=0.999,
                system=system_prompt,
                messages=messages
            )

            # Parse response
            output_text = response.content[0].text
            generated_item = json.loads(output_text)

            # Validate basic structure
            if 'itemId' not in generated_item and 'materialId' not in generated_item:
                raise ValueError("Generated item missing ID field")

            return {
                'success': True,
                'item': generated_item,
                'recipe_input': input_prompt,
                'tokens_used': response.usage.input_tokens + response.usage.output_tokens
            }

        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Failed to parse LLM response as JSON: {e}',
                'raw_response': output_text if 'output_text' in dir() else None
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
```

### 2.3 Integration Flow

```
Player places materials in interactive UI
    ↓
Player clicks "INVENT RECIPE" button
    ↓
CraftingClassifier.validate(discipline, ui)
    ↓
┌─────────────────────────────────────────┐
│ If VALID (probability >= 0.5):          │
│   1. Show success message               │
│   2. ItemGenerator.generate()           │
│   3. Create Recipe + Item objects       │
│   4. Add to PlayerRecipeManager         │
│   5. Show generated item preview        │
└─────────────────────────────────────────┘
    │
    │ If INVALID (probability < 0.5):
    │   1. Show failure message with confidence
    │   2. Suggest trying different arrangement
    ↓
Continue crafting or close UI
```

---

## Part 3: Save System Extension

### 3.1 New Data Structures

#### **PlayerRecipe**
```python
@dataclass
class PlayerRecipe:
    """A recipe invented by the player"""
    recipe_id: str
    output_id: str
    output_qty: int
    station_type: str
    station_tier: int
    inputs: List[Dict]  # Same format as regular recipes
    placement_data: Dict  # UI state for recreation

    # Metadata
    created_at: str  # ISO timestamp
    created_at_level: int
    discovery_method: str = "invention"  # "invention", "quest", "achievement"
    times_crafted: int = 0

    # Generated item template
    generated_item: Dict = field(default_factory=dict)
```

#### **PlayerRecipeManager Component**
Add to Character at: `Game-1-modular/entities/components/player_recipes.py`

```python
class PlayerRecipeManager:
    """Manages player-invented recipes"""

    def __init__(self):
        self.recipes: Dict[str, PlayerRecipe] = {}
        self.recipe_history: List[str] = []  # Chronological order

    def add_recipe(self, recipe: PlayerRecipe) -> bool:
        """Add a newly discovered recipe"""
        if recipe.recipe_id in self.recipes:
            return False  # Already known

        self.recipes[recipe.recipe_id] = recipe
        self.recipe_history.append(recipe.recipe_id)
        return True

    def get_recipes_for_station(self, station_type: str, tier: int) -> List[PlayerRecipe]:
        """Get player recipes available at a station"""
        return [
            r for r in self.recipes.values()
            if r.station_type == station_type and r.station_tier <= tier
        ]

    def mark_crafted(self, recipe_id: str):
        """Increment craft count for recipe"""
        if recipe_id in self.recipes:
            self.recipes[recipe_id].times_crafted += 1

    def to_save_data(self) -> Dict:
        """Serialize for save file"""
        return {
            'recipes': {
                rid: {
                    'recipe_id': r.recipe_id,
                    'output_id': r.output_id,
                    'output_qty': r.output_qty,
                    'station_type': r.station_type,
                    'station_tier': r.station_tier,
                    'inputs': r.inputs,
                    'placement_data': r.placement_data,
                    'created_at': r.created_at,
                    'created_at_level': r.created_at_level,
                    'discovery_method': r.discovery_method,
                    'times_crafted': r.times_crafted,
                    'generated_item': r.generated_item
                }
                for rid, r in self.recipes.items()
            },
            'recipe_history': self.recipe_history
        }

    @classmethod
    def from_save_data(cls, data: Dict) -> 'PlayerRecipeManager':
        """Deserialize from save file"""
        manager = cls()

        for rid, recipe_data in data.get('recipes', {}).items():
            manager.recipes[rid] = PlayerRecipe(
                recipe_id=recipe_data['recipe_id'],
                output_id=recipe_data['output_id'],
                output_qty=recipe_data['output_qty'],
                station_type=recipe_data['station_type'],
                station_tier=recipe_data['station_tier'],
                inputs=recipe_data['inputs'],
                placement_data=recipe_data.get('placement_data', {}),
                created_at=recipe_data.get('created_at', ''),
                created_at_level=recipe_data.get('created_at_level', 1),
                discovery_method=recipe_data.get('discovery_method', 'invention'),
                times_crafted=recipe_data.get('times_crafted', 0),
                generated_item=recipe_data.get('generated_item', {})
            )

        manager.recipe_history = data.get('recipe_history', [])
        return manager
```

### 3.2 Save Manager Modifications

Modify: `Game-1-modular/systems/save_manager.py`

```python
# In SaveManager.create_save_data():
def create_save_data(self):
    save_data = {
        "version": "2.1",  # Increment version
        "save_timestamp": datetime.now().isoformat(),
        "player": self._serialize_character(self.character),
        "world_state": self._serialize_world_state(),
        "quest_state": self._serialize_quest_state(),
        "npc_state": self._serialize_npc_state(),
        # NEW: Player recipes
        "player_recipes": self._serialize_player_recipes()
    }
    return save_data

def _serialize_player_recipes(self) -> Dict:
    """Serialize player-invented recipes"""
    if hasattr(self.character, 'player_recipes'):
        return self.character.player_recipes.to_save_data()
    return {'recipes': {}, 'recipe_history': []}

# In Character.restore_from_save():
def restore_from_save(self, save_data: Dict):
    # ... existing restoration code ...

    # NEW: Restore player recipes
    if 'player_recipes' in save_data:
        self.player_recipes = PlayerRecipeManager.from_save_data(
            save_data['player_recipes']
        )
    else:
        self.player_recipes = PlayerRecipeManager()
```

### 3.3 Recipe Display Integration

Player recipes need special handling in crafting UIs:

```python
# In RecipeDatabase or crafting UI:
def get_all_recipes_for_station(self, station_type: str, tier: int, player_recipes: PlayerRecipeManager):
    """Get both base and player recipes for a station"""
    base_recipes = self.get_recipes_for_station(station_type, tier)
    player = player_recipes.get_recipes_for_station(station_type, tier)

    # Mark player recipes for special display
    for recipe in player:
        recipe._is_player_invented = True

    return base_recipes + player
```

UI indicators for player recipes:
- Different background color (e.g., gold tint)
- "★ Invented" badge
- Tooltip showing creation date and times crafted

---

## Implementation Order

### Phase 1: Classifier Integration (Est. 3-5 files, ~800 lines)
1. Create `systems/crafting_classifier.py` with all transform methods
2. Add material color encoding (copy from CNN runners)
3. Add "INVENT RECIPE" button to renderer
4. Wire up button click → classifier validation
5. Show success/failure feedback

### Phase 2: LLM Integration (Est. 2-3 files, ~400 lines)
1. Create `systems/llm_item_generator.py`
2. Build prompts for each discipline
3. Wire up successful validation → LLM generation
4. Parse and validate generated items
5. Add generated item preview UI

### Phase 3: Save System (Est. 3-4 files, ~300 lines)
1. Create `entities/components/player_recipes.py`
2. Add PlayerRecipeManager to Character
3. Extend SaveManager serialization
4. Extend Character restoration
5. Merge player recipes into crafting UI lists

### Phase 4: Testing & Polish
1. End-to-end testing of all 5 disciplines
2. Edge case handling (API failures, invalid responses)
3. UI polish and feedback refinement
4. Performance optimization (lazy model loading)

---

## Dependencies

### Python Packages Required
```
tensorflow>=2.10.0       # For CNN models
lightgbm>=3.3.0         # For LightGBM models
anthropic>=0.18.0       # For Claude API
numpy>=1.21.0           # Already present
```

### External Resources
- Claude API key (set via environment variable `ANTHROPIC_API_KEY`)
- Pre-trained model files (already in repository)
- Few-shot examples (already in repository)

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| ML libraries increase startup time | Medium | Lazy load models on first use |
| API rate limits | Low | Cache generated items, limit invention frequency |
| Invalid LLM outputs | Medium | Three-layer validation, fallback to error state |
| Model accuracy issues | Medium | Log predictions for review, allow manual override |
| Save file corruption | High | Versioned save format, backwards compatibility |

---

## File Summary

### New Files
- `Game-1-modular/systems/crafting_classifier.py` (~400 lines)
- `Game-1-modular/systems/llm_item_generator.py` (~300 lines)
- `Game-1-modular/entities/components/player_recipes.py` (~150 lines)

### Modified Files
- `Game-1-modular/core/interactive_crafting.py` (add invention methods)
- `Game-1-modular/rendering/renderer.py` (add button and feedback)
- `Game-1-modular/systems/save_manager.py` (add player recipe serialization)
- `Game-1-modular/entities/character.py` (add PlayerRecipeManager component)
- `Game-1-modular/core/game_engine.py` (wire up event handling)

---

**Document Version**: 1.0
**Last Updated**: January 25, 2026
