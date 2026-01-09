# Crafting UI & Minigame Overhaul Plan

**Created**: January 4, 2026
**Status**: Planning Phase
**Priority**: High

---

## Executive Summary

This document outlines a comprehensive overhaul of the crafting system UI and minigame mechanics. The goals are:

1. **UI Polish**: More informative, readable crafting grids especially at larger sizes
2. **Distinct Minigame Vibes**: Each discipline should feel unique and gamelike
3. **Material-Based Difficulty**: Difficulty derived from material tier point values, not just station tier
4. **Proportional Rewards**: Harder difficulty = better rewards across all disciplines

---

## Table of Contents

1. [Global UI Improvements](#1-global-ui-improvements)
2. [Difficulty Calculation Overhaul](#2-difficulty-calculation-overhaul)
3. [Smithing Overhaul](#3-smithing-overhaul)
4. [Refining Overhaul](#4-refining-overhaul)
5. [Alchemy Overhaul](#5-alchemy-overhaul)
6. [Engineering Overhaul](#6-engineering-overhaul)
7. [Enchanting/Adornment](#7-enchantingadornment-deferred)
8. [User Recipe Creation](#8-user-recipe-creation-deferred)
9. [Implementation Order](#9-implementation-order)
10. [Technical Debt & Cleanup](#10-technical-debt--cleanup)

---

## 1. Global UI Improvements

### 1.1 Problem Statement

Current crafting grids become unreadable at larger sizes:
- **3x3**: Items visible with detail
- **5x5**: Items becoming small
- **7x7**: Shapes with colors, hard to distinguish
- **9x9**: Nearly impossible to identify materials

**Current Implementation** (renderer.py:87-99):
```python
cell_size = min(available_w // grid_w, available_h // grid_h) - 4
# At 9x9: ~30px cells with 16px icons - too small!
```

### 1.2 Proposed Solutions

#### A. Zoomable/Scrollable Grid View
- Default view shows entire grid at reduced size
- Click-and-drag or scroll wheel to zoom into regions
- Zoomed view shows full detail (60px+ icons)
- Mini-map overlay showing current viewport position

#### B. Material Detail Panel
- Dedicated sidebar panel (right side of grid)
- Shows hovered/selected material in large format (100x100px)
- Displays: Name, Tier, Rarity, Category, Narrative snippet
- Always visible regardless of grid zoom level

#### C. Grid Cell Enhancements
- Tier badge overlay (T1-T4 in corner)
- Rarity border glow (common=gray, rare=blue, epic=purple, legendary=gold)
- Quantity indicator (if stacked)
- Hover: expand cell temporarily (1.5x size, overlays neighbors)

#### D. Recipe Comparison View
- Side-by-side: Recipe template vs Player placement
- Highlight mismatches in red
- Show completion percentage
- Material substitution suggestions

### 1.3 Color Scheme Standardization

```python
TIER_COLORS = {
    1: (180, 180, 180),  # Silver/Gray
    2: (100, 200, 100),  # Green
    3: (100, 150, 255),  # Blue
    4: (255, 180, 50),   # Gold/Orange
}

RARITY_BORDER_COLORS = {
    "common": (120, 120, 120),
    "uncommon": (80, 200, 80),
    "rare": (80, 120, 255),
    "epic": (180, 80, 255),
    "legendary": (255, 200, 50),
}
```

### 1.4 UI Component Library

Create reusable components:
- `MaterialCard`: Standard material display with all info
- `GridCell`: Enhanced cell with badges/borders
- `TooltipPanel`: Rich tooltip with formatted content
- `ProgressBar`: Animated, color-coded progress indicator
- `TimerDisplay`: Countdown with visual urgency cues

---

## 2. Difficulty Calculation Overhaul

### 2.1 Core Principle

**Difficulty = f(material_tiers, material_count, discipline_modifiers)**

Replace current tier-only system with material-based point calculation.

### 2.2 Material Point Value System

```python
def calculate_material_points(materials: List[Dict]) -> float:
    """
    Calculate total difficulty points from recipe materials.

    Each material contributes: tier_value * quantity
    """
    total_points = 0
    material_db = MaterialDatabase.get_instance()

    for mat in materials:
        material = material_db.get_material(mat['materialId'])
        tier = material.tier if material else 1
        quantity = mat.get('quantity', 1)

        # Base tier points: T1=1, T2=2, T3=4, T4=8 (exponential)
        tier_points = 2 ** (tier - 1)
        total_points += tier_points * quantity

    return total_points
```

### 2.3 Difficulty Multiplier: Material Diversity

For disciplines where material diversity matters (Refining, Alchemy, Engineering):

```python
def calculate_diversity_multiplier(materials: List[Dict]) -> float:
    """
    More unique materials = higher difficulty multiplier.

    Formula: 1.0 + (unique_count - 1) * 0.1
    Example: 3 unique materials = 1.2x multiplier
    """
    unique_materials = len(set(m['materialId'] for m in materials))
    return 1.0 + (unique_materials - 1) * 0.1
```

### 2.4 Difficulty → Parameter Mapping

Create interpolation functions that map point totals to minigame parameters:

```python
def interpolate_difficulty(points: float, param_ranges: Dict) -> Dict:
    """
    Map point total to difficulty parameters via linear interpolation.

    param_ranges = {
        'time_limit': (60, 15),      # Easy: 60s, Hard: 15s
        'timing_window': (1.0, 0.1), # Easy: 1.0s, Hard: 0.1s
        'required_actions': (3, 15), # Easy: 3, Hard: 15
    }

    Points scale: 1-10 (easy) → 100+ (extreme)
    """
    # Normalize points to 0.0-1.0 range
    normalized = min(1.0, max(0.0, (points - 1) / 99))

    result = {}
    for param, (easy_val, hard_val) in param_ranges.items():
        result[param] = easy_val + (hard_val - easy_val) * normalized

    return result
```

### 2.5 Reward Scaling

**Principle**: Harder difficulty unlocks higher reward potential.

```python
def calculate_max_reward_multiplier(difficulty_points: float) -> float:
    """
    Higher difficulty = higher maximum achievable bonus.

    Base: 1.0x at minimum difficulty
    Max: 2.5x at maximum difficulty
    """
    normalized = min(1.0, difficulty_points / 100)
    return 1.0 + (normalized * 1.5)  # 1.0x to 2.5x range
```

---

## 3. Smithing Overhaul

### 3.1 Current State

**File**: `Crafting-subdisciplines/smithing.py`
**Lines**: 68-119 (difficulty), 174-238 (scoring)

Current: Tier-based difficulty with hammer timing + temperature management.

### 3.2 Difficulty Formula

```python
def smithing_difficulty(recipe: Dict) -> Dict:
    """
    Smithing difficulty based on material tier point values.
    """
    materials = recipe.get('inputs', [])
    base_points = calculate_material_points(materials)

    # Smithing doesn't use diversity multiplier (single-focus craft)
    total_points = base_points

    # Map to parameters
    return interpolate_difficulty(total_points, {
        'time_limit': (60, 20),           # seconds
        'temp_ideal_range': (30, 2),      # degrees (80-50 → 71-69)
        'temp_decay_rate': (0.3, 1.5),    # degrees/second
        'required_hits': (3, 15),         # hammer strikes
        'target_width': (120, 30),        # pixels
        'perfect_width': (60, 10),        # pixels
        'hammer_speed': (2.0, 7.0),       # movement speed
    })
```

### 3.3 UI Overhaul

#### Temperature Display
- **Current**: Simple bar with green zone
- **New**: Forge visualization with flame intensity
  - Low temp: Blue flames, ice particles
  - Ideal temp: Bright orange flames, sparks
  - High temp: White-hot flames, smoke
  - Animated bellows indicator

#### Hammer Zone
- **Current**: Moving indicator on horizontal bar
- **New**: Anvil visualization
  - 3D-ish anvil with strike zones
  - Visual impact effects on hit
  - Sparks and metal deformation
  - Rhythm indicator (beat markers)

#### Feedback
- Screen shake on hammer hits
- Color flash based on hit quality
- Combo counter for consecutive perfects
- Sound cues (different pitches for quality)

### 3.4 Reward Calculation

```python
def smithing_rewards(difficulty_points: float, performance: Dict) -> Dict:
    """
    Performance-based rewards scaled by difficulty.
    """
    max_multiplier = calculate_max_reward_multiplier(difficulty_points)

    # Performance score: 0.0 to 1.0
    avg_accuracy = performance['avg_hammer_score'] / 100
    temp_bonus = 1.2 if performance['temp_in_ideal'] else 1.0

    performance_score = avg_accuracy * temp_bonus

    # Final bonus: performance% of max possible
    bonus_multiplier = 1.0 + (max_multiplier - 1.0) * performance_score

    return {
        'stat_multiplier': bonus_multiplier,
        'quality_tier': _score_to_quality(performance_score),  # Normal/Fine/Superior/Masterwork
        'first_try_eligible': performance.get('attempt', 1) == 1,
    }
```

---

## 4. Refining Overhaul

### 4.1 Current State

**File**: `Crafting-subdisciplines/refining.py`
**Lines**: 68-102 (difficulty), 211-233 (success/fail)

Current: Cylinder alignment timing game, tier-based parameters.

### 4.2 Difficulty Formula

```python
def refining_difficulty(recipe: Dict) -> Dict:
    """
    Refining difficulty based on material points × diversity multiplier.

    More unique materials = harder (narratively: complex reactions)
    """
    materials = recipe.get('inputs', [])
    base_points = calculate_material_points(materials)
    diversity_mult = calculate_diversity_multiplier(materials)

    total_points = base_points * diversity_mult

    return interpolate_difficulty(total_points, {
        'time_limit': (60, 10),           # seconds
        'cylinder_count': (2, 18),        # alignments required
        'timing_window': (1.2, 0.15),     # seconds per cylinder
        'rotation_speed': (0.8, 3.0),     # rotations/second
        'allowed_failures': (3, 0),       # mistakes permitted
        'multi_speed': (False, True),     # variable speeds at high diff
    })
```

### 4.3 UI Overhaul

#### Core Visualization
- **Current**: Simple circle with rotating indicator
- **New**: Lock mechanism aesthetic
  - Tumbler-style cylinders (like lockpicking)
  - Each cylinder has unique visual (gears, runes, crystals)
  - Satisfying "click" when aligned
  - Visible mechanism connections

#### Progress Display
- Cylinder stack showing completed/remaining
- Each aligned cylinder "locks" with visual feedback
- Failure: cylinder resets with shake effect
- Near-miss feedback (almost!)

#### Ambient Effects
- Furnace glow in background
- Molten metal effects
- Steam/heat distortion
- Material transformation preview

### 4.4 Reward Calculation

```python
def refining_rewards(difficulty_points: float, success: bool) -> Dict:
    """
    Refining uses rarity upgrade based on difficulty + input quantity.
    Higher difficulty = higher potential upgrade.
    """
    if not success:
        return {'success': False, 'material_loss': 0.5}

    max_multiplier = calculate_max_reward_multiplier(difficulty_points)

    # Rarity upgrade tiers based on difficulty
    # Easy: max +1 tier, Hard: max +4 tiers
    max_rarity_upgrade = int(1 + (max_multiplier - 1) * 2)

    return {
        'success': True,
        'max_rarity_upgrade': max_rarity_upgrade,
        'quality_multiplier': max_multiplier,
    }
```

---

## 5. Alchemy Overhaul

### 5.1 Current State

**File**: `Crafting-subdisciplines/alchemy.py`
**Lines**: 240-258 (difficulty), 151-169 (reaction quality)

Current: Reaction chain timing with ingredient volatility types.

### 5.2 Difficulty Formula

```python
def alchemy_difficulty(recipe: Dict) -> Dict:
    """
    Alchemy difficulty based on:
    1. Material tier points × diversity multiplier
    2. Volatility modifier based on vowel count in narrative descriptions
    3. Average tier exponential modifier (1.2^avg_tier)
    """
    materials = recipe.get('inputs', [])
    material_db = MaterialDatabase.get_instance()

    base_points = calculate_material_points(materials)
    diversity_mult = calculate_diversity_multiplier(materials)

    # Calculate volatility from narrative descriptions
    total_vowels = 0
    total_tier = 0
    for mat in materials:
        material = material_db.get_material(mat['materialId'])
        if material:
            narrative = material.narrative or material.name
            vowels = sum(1 for c in narrative.lower() if c in 'aeiou')
            total_vowels += vowels
            total_tier += material.tier

    avg_tier = total_tier / len(materials) if materials else 1
    tier_modifier = 1.2 ** avg_tier  # Exponential scaling

    # Vowel volatility: more vowels = more volatile reactions
    vowel_modifier = 1.0 + (total_vowels / 100)  # Subtle scaling

    total_points = base_points * diversity_mult * tier_modifier * vowel_modifier

    return interpolate_difficulty(total_points, {
        'time_limit': (90, 15),                    # seconds
        'stage_duration_mult': (1.5, 0.3),         # stage speed
        'sweet_spot_duration': (3.0, 0.4),         # optimal window
        'false_peak_count': (0, 6),                # fake sweet spots
        'reaction_erratic_level': (0.0, 1.0),      # randomness
    })

def calculate_ingredient_volatility(material, difficulty_level: float) -> str:
    """
    Determine ingredient type based on material + difficulty.
    """
    # Base volatility from material tier
    tier_volatility = {1: 0, 2: 1, 3: 2, 4: 3}
    base = tier_volatility.get(material.tier, 0)

    # Add difficulty scaling
    scaled = base + int(difficulty_level * 2)

    volatility_types = ['stable', 'moderate', 'volatile', 'legendary']
    return volatility_types[min(scaled, 3)]
```

### 5.3 UI Overhaul

#### Cauldron Visualization
- **Current**: Bubble with color shifts
- **New**: Full cauldron with liquid simulation
  - Bubbling liquid with particle effects
  - Color changes based on reaction stage
  - Steam/vapor effects
  - Ingredient splash when added

#### Reaction Display
- Graph showing reaction progress over time
- Clear stage indicators (building, sweet spot, declining)
- False peak warnings (shimmer effect)
- Danger zone visualization (red glow, alarm)

#### Ingredient Tray
- Visible ingredient queue
- Drag-and-drop or click to add
- Ingredient preview (what it will do)
- Timing suggestions (when to add)

### 5.4 Reward Calculation

```python
def alchemy_rewards(difficulty_points: float, performance: Dict) -> Dict:
    """
    Alchemy rewards based on reaction chain quality.
    """
    max_multiplier = calculate_max_reward_multiplier(difficulty_points)

    # Progress determines base multiplier
    progress = performance['total_progress']  # 0.0 to 1.0+

    # Map progress to effect multipliers
    if progress < 0.25:
        return {'success': False, 'material_loss': 0.5}

    effect_mult = 0.5 + (progress * max_multiplier * 0.5)
    duration_mult = 0.5 + (progress * max_multiplier * 0.5)

    return {
        'success': True,
        'effect_multiplier': min(effect_mult, max_multiplier),
        'duration_multiplier': min(duration_mult, max_multiplier),
        'quality_tier': _progress_to_quality(progress),
    }
```

---

## 6. Engineering Overhaul

### 6.1 Current State

**File**: `Crafting-subdisciplines/engineering.py`
**Lines**: 450-476 (puzzle count), 491-529 (puzzle types)

Current: Puzzle collection (rotation pipes, sliding tiles), no time pressure.

### 6.2 Difficulty Formula

```python
def engineering_difficulty(recipe: Dict) -> Dict:
    """
    Engineering difficulty based on:
    1. Slot count × slot values
    2. Material diversity multiplier

    Target: 20-30s base → 4-5 min maximum per puzzle set
    """
    materials = recipe.get('inputs', [])
    slots = recipe.get('slots', [])

    base_points = calculate_material_points(materials)
    diversity_mult = calculate_diversity_multiplier(materials)

    # Slot complexity
    slot_count = len(slots)
    slot_value = sum(s.get('tier', 1) for s in slots)
    slot_mult = 1.0 + (slot_count - 1) * 0.1

    total_points = base_points * diversity_mult * slot_mult

    # Map to puzzle parameters
    # Base: 20-30s per puzzle, Max: ~60-75s per puzzle
    # Total time: 1-6 puzzles × puzzle_time
    return interpolate_difficulty(total_points, {
        'puzzle_count': (1, 6),              # number of puzzles
        'puzzle_time_each': (30, 75),        # seconds per puzzle
        'grid_size': (3, 7),                 # puzzle grid dimensions
        'complexity_level': (1, 4),          # puzzle type complexity
        'hint_availability': (3, 0),         # hints allowed
    })
```

### 6.3 UI Overhaul - MAJOR REDESIGN

#### Workbench Aesthetic
- **Current**: Basic slot list with puzzle overlay
- **New**: Blueprint/schematic table
  - Drafting table with grid paper
  - Schematic drawings of device
  - Tool rack on side
  - Assembly progress visualization

#### Puzzle Presentation
- Each puzzle type has unique visual theme:
  - **Rotation Pipes**: Steam-punk gear aesthetic
  - **Sliding Tiles**: Mechanical assembly
  - **Traffic Jam**: Warehouse logistics (future)
  - **Pattern Match**: Circuit board design (future)

#### Time Management
- Per-puzzle timer (not total time)
- Easy: 30s per puzzle
- Hard: 75s per puzzle (but more complex)
- Visual urgency (pulsing border as time runs low)

#### Puzzle Types Expansion

**Tier 1: Rotation Pipes** (keep current)
- 3x3 to 5x5 grids
- Connect input to output
- Satisfying flow animation when complete

**Tier 2: Sliding Tiles** (keep current)
- 3x3 to 5x5 grids
- Numbered or image-based
- Move counter display

**Tier 3: Wire Connection** (NEW - replace Traffic Jam placeholder)
- Grid with nodes
- Draw connections between matching colors
- No crossing wires
- Multiple valid solutions

**Tier 4: Gear Assembly** (NEW - replace Pattern Match placeholder)
- Place gears to transfer rotation
- Input gear → chain → output gear
- Size matters (gear ratios)
- More tactile and engineering-themed

### 6.4 Reward Calculation

```python
def engineering_rewards(difficulty_points: float, performance: Dict) -> Dict:
    """
    Engineering rewards based on puzzles completed.
    Stats boosted per puzzle, scaled by difficulty.
    """
    max_multiplier = calculate_max_reward_multiplier(difficulty_points)

    puzzles_solved = performance['puzzles_solved']
    puzzles_total = performance['puzzles_total']
    completion_rate = puzzles_solved / puzzles_total if puzzles_total > 0 else 0

    # Base +15% per puzzle, scaled by difficulty max
    bonus_per_puzzle = 0.15 * max_multiplier

    stat_bonuses = {}
    stat_types = ['durability', 'efficiency', 'accuracy', 'power']
    for i, puzzle in enumerate(performance.get('solved_puzzles', [])):
        stat = stat_types[i % len(stat_types)]
        stat_bonuses[stat] = stat_bonuses.get(stat, 0) + bonus_per_puzzle

    return {
        'success': completion_rate >= 0.5,  # Need at least half
        'stat_bonuses': stat_bonuses,
        'quality_multiplier': 1.0 + (completion_rate * (max_multiplier - 1)),
    }
```

---

## 7. Enchanting/Adornment (DEFERRED)

### 7.1 Status

**Current Implementation**: Spinning wheel (gambling mechanic)
**Designed**: Freeform pattern drawing
**Decision**: SHELVE - revisit after other disciplines complete

### 7.2 Documented Logic for Future

```python
def adornment_difficulty(recipe: Dict) -> Dict:
    """
    DEFERRED: Adornment difficulty based on:
    1. Number of geometric shapes required
    2. Number of material parts to place
    3. Precision requirements
    """
    shapes_required = recipe.get('shapes', 1)
    parts_count = len(recipe.get('inputs', []))

    base_difficulty = shapes_required * 10 + parts_count * 5

    return {
        'shape_count': shapes_required,
        'part_count': parts_count,
        'precision_required': 0.7 + (base_difficulty / 100) * 0.25,  # 70-95%
        'time_limit': None,  # No time pressure for creative work
    }
```

### 7.3 Integration Notes

- Pattern drawing should feed into recipe creation system
- Shapes determine bonus types (triangle=offensive, etc.)
- Precision determines bonus magnitude
- Keep spinning wheel as "quick enchant" option?

### 7.4 Add to Master Issue Tracker

```markdown
## DEFERRED: Enchanting Pattern Minigame

**Priority**: Medium
**Depends On**: UI framework improvements, user recipe creation system
**Description**: Replace spinning wheel with freeform pattern drawing minigame
**Key Features**:
- Material placement in circular workspace
- Line drawing between materials
- Geometric pattern recognition
- Precision-based quality scoring
```

---

## 8. User Recipe Creation (DEFERRED)

### 8.1 Concept

Players can create custom recipes by:
1. Placing materials in crafting grid experimentally
2. (For Enchanting) Drawing patterns that define new enchantment types
3. Successful experiments become learned recipes

### 8.2 Integration with Difficulty System

Custom recipes would calculate difficulty dynamically:
- No pre-defined stationTier
- Difficulty purely from material composition
- Higher material investment = harder minigame = better potential output

### 8.3 Defer Reason

Requires significant infrastructure:
- Recipe validation system
- Balance constraints
- Recipe storage/persistence
- UI for recipe management

Add to roadmap after core minigame overhaul complete.

---

## 9. Implementation Order

### Phase 1: Foundation (Week 1-2)
1. Create difficulty calculation module (`core/difficulty_calculator.py`)
2. Create UI component library (`rendering/ui_components.py`)
3. Implement material point value system
4. Add diversity multiplier calculation

### Phase 2: Smithing (Week 2-3)
1. New difficulty formula integration
2. UI overhaul (forge visualization)
3. Reward scaling implementation
4. Testing and tuning

### Phase 3: Refining (Week 3-4)
1. Difficulty formula with diversity multiplier
2. Lock mechanism UI redesign
3. Reward calculation update
4. Testing and tuning

### Phase 4: Alchemy (Week 4-5)
1. Vowel-based volatility calculation
2. Tier exponential modifier
3. Cauldron UI redesign
4. Reaction visualization improvements
5. Testing and tuning

### Phase 5: Engineering (Week 5-7)
1. Major UI redesign (blueprint table)
2. New puzzle types (Wire Connection, Gear Assembly)
3. Per-puzzle timing system
4. Difficulty formula implementation
5. Extensive testing (puzzle generation, solvability)

### Phase 6: Polish & Integration (Week 7-8)
1. First-try bonus implementation
2. Tier-scaled failure penalties
3. Cross-discipline consistency pass
4. Performance optimization
5. Save/load compatibility

### Phase 7: Deferred Items (Future)
1. Enchanting pattern minigame
2. User recipe creation
3. Sub-specialization modifiers
4. Material-based minigame modifiers

---

## 10. Technical Debt & Cleanup

### 10.1 Files to Modify

| File | Changes |
|------|---------|
| `core/difficulty_calculator.py` | NEW: Central difficulty calculation |
| `rendering/ui_components.py` | NEW: Reusable UI components |
| `rendering/renderer.py` | UI improvements, component integration |
| `Crafting-subdisciplines/smithing.py` | Difficulty formula, UI hooks |
| `Crafting-subdisciplines/refining.py` | Difficulty formula, UI hooks |
| `Crafting-subdisciplines/alchemy.py` | Volatility system, UI hooks |
| `Crafting-subdisciplines/engineering.py` | Major puzzle redesign |
| `core/game_engine.py` | Minigame rendering updates |

### 10.2 Shelved Items (Do Not Implement Yet)

- [ ] Material-based sub-modifiers (fire materials → fire effects)
- [ ] Sub-specialization mechanics
- [ ] Fuel system for refining
- [ ] Enchanting pattern minigame (document logic only)
- [ ] User recipe creation system

### 10.3 Design Decisions Log

| Decision | Rationale |
|----------|-----------|
| Exponential tier points (2^tier) | Ensures T4 materials significantly harder than T1 |
| Diversity multiplier × 0.1 per unique | Subtle but meaningful complexity increase |
| Vowel-based volatility | Fun, thematic, unpredictable without being random |
| Per-puzzle timing (Engineering) | Allows long total time while maintaining tension |
| No time limit (Enchanting) | Creative work shouldn't be rushed |

---

## Appendix A: Current vs Proposed Comparison

### Smithing Difficulty Parameters

| Parameter | Current T1 | Current T4 | Proposed Easy | Proposed Hard |
|-----------|-----------|-----------|---------------|---------------|
| Time Limit | 45s | 30s | 60s | 20s |
| Temp Range | 20° | 2° | 30° | 2° |
| Required Hits | 5 | 12 | 3 | 15 |
| Target Width | 100px | 40px | 120px | 30px |

### Refining Difficulty Parameters

| Parameter | Current T1 | Current T4 | Proposed Easy | Proposed Hard |
|-----------|-----------|-----------|---------------|---------------|
| Time Limit | 45s | 15s | 60s | 10s |
| Cylinders | 3 | 15 | 2 | 18 |
| Timing Window | 0.8s | 0.2s | 1.2s | 0.15s |
| Allowed Fails | 2 | 0 | 3 | 0 |

### Engineering Puzzle Times

| Difficulty | Puzzles | Time/Puzzle | Total Time |
|------------|---------|-------------|------------|
| Easy (10 pts) | 1 | 30s | 30s |
| Medium (30 pts) | 2-3 | 40s | 80-120s |
| Hard (60 pts) | 4-5 | 55s | 220-275s |
| Extreme (100 pts) | 6 | 75s | 450s (7.5 min) |

---

## Appendix B: File Structure After Implementation

```
Game-1-modular/
├── core/
│   ├── difficulty_calculator.py    # NEW: Central difficulty system
│   ├── reward_calculator.py        # NEW: Unified reward calculations
│   └── ...
├── rendering/
│   ├── ui_components.py            # NEW: Reusable UI components
│   ├── renderer.py                 # MODIFIED: Component integration
│   └── ...
├── Crafting-subdisciplines/
│   ├── smithing.py                 # MODIFIED: New difficulty/UI
│   ├── refining.py                 # MODIFIED: New difficulty/UI
│   ├── alchemy.py                  # MODIFIED: Volatility system
│   ├── engineering.py              # MAJOR REWRITE: Puzzles/UI
│   └── enchanting.py               # MINIMAL: Document for future
└── docs/
    └── CRAFTING_UI_MINIGAME_OVERHAUL_PLAN.md  # This document
```

---

**Document Version**: 1.0
**Last Updated**: January 4, 2026
**Author**: Claude (Planning Session)
