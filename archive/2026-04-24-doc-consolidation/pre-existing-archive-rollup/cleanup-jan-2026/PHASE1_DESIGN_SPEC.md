# Phase 1: Design Specification

**Created**: January 4, 2026
**Status**: Design Complete - Ready for Implementation

This document contains the detailed design specifications for Phase 1 of the crafting minigame overhaul. Every implementation detail is specified here to ensure nothing is overlooked during coding.

---

## Table of Contents

1. [Difficulty Calculator Module](#1-difficulty-calculator-module)
2. [Reward Calculator Module](#2-reward-calculator-module)
3. [Smithing Integration](#3-smithing-integration)
4. [Refining Integration](#4-refining-integration)
5. [Visual Polish Specifications](#5-visual-polish-specifications)
6. [Tier-Scaled Penalties](#6-tier-scaled-penalties)
7. [Integration Points](#7-integration-points)

---

## 1. Difficulty Calculator Module

### File: `core/difficulty_calculator.py`

### 1.1 Purpose

Centralized difficulty calculation based on material tier point values, replacing the current tier-only system.

### 1.2 Core Functions

```python
# === MATERIAL POINT CALCULATION ===

def calculate_material_points(inputs: List[Dict]) -> float:
    """
    Calculate total difficulty points from recipe inputs.

    Each material contributes: 2^(tier-1) * quantity
    - T1: 1 point per item
    - T2: 2 points per item
    - T3: 4 points per item
    - T4: 8 points per item

    Args:
        inputs: List of {'materialId': str, 'quantity': int}

    Returns:
        Total difficulty points (float)
    """

def calculate_diversity_multiplier(inputs: List[Dict]) -> float:
    """
    Calculate difficulty multiplier based on unique material count.

    Formula: 1.0 + (unique_count - 1) * 0.1
    - 1 material: 1.0x
    - 2 materials: 1.1x
    - 3 materials: 1.2x
    - etc.

    Args:
        inputs: List of {'materialId': str, 'quantity': int}

    Returns:
        Multiplier (float, minimum 1.0)
    """

def calculate_average_tier(inputs: List[Dict]) -> float:
    """
    Calculate weighted average tier of materials.

    Used for: Alchemy tier exponential modifier

    Args:
        inputs: List of {'materialId': str, 'quantity': int}

    Returns:
        Weighted average tier (float)
    """
```

### 1.3 Discipline-Specific Difficulty Functions

```python
def calculate_smithing_difficulty(recipe: Dict) -> Dict:
    """
    Smithing difficulty based on material points only.
    No diversity multiplier (single-focus craft).

    Returns parameters:
    - time_limit: 60s (easy) to 20s (hard)
    - temp_ideal_range: 30° (easy) to 2° (hard)
    - temp_decay_rate: 0.3 (easy) to 1.5 (hard)
    - required_hits: 3 (easy) to 15 (hard)
    - target_width: 120px (easy) to 30px (hard)
    - perfect_width: 60px (easy) to 10px (hard)
    - hammer_speed: 2.0 (easy) to 7.0 (hard)
    """

def calculate_refining_difficulty(recipe: Dict) -> Dict:
    """
    Refining difficulty based on material points × diversity multiplier.

    Returns parameters:
    - time_limit: 60s (easy) to 10s (hard)
    - cylinder_count: 2 (easy) to 18 (hard)
    - timing_window: 1.2s (easy) to 0.15s (hard)
    - rotation_speed: 0.8 (easy) to 3.0 (hard)
    - allowed_failures: 3 (easy) to 0 (hard)
    - multi_speed: False (easy) to True (hard)
    """
```

### 1.4 Interpolation Function

```python
def interpolate_difficulty(
    points: float,
    param_ranges: Dict[str, Tuple[float, float]],
    min_points: float = 1.0,
    max_points: float = 100.0
) -> Dict[str, float]:
    """
    Map difficulty points to parameter values via linear interpolation.

    Args:
        points: Calculated difficulty points
        param_ranges: Dict of {param_name: (easy_value, hard_value)}
        min_points: Points value for easiest difficulty
        max_points: Points value for hardest difficulty

    Returns:
        Dict of {param_name: interpolated_value}

    Example:
        param_ranges = {
            'time_limit': (60, 20),      # Easy: 60s, Hard: 20s
            'required_hits': (3, 15),    # Easy: 3, Hard: 15
        }
        points = 50  # Middle difficulty

        Result: {'time_limit': 40, 'required_hits': 9}
    """
    normalized = max(0.0, min(1.0, (points - min_points) / (max_points - min_points)))

    result = {}
    for param, (easy_val, hard_val) in param_ranges.items():
        result[param] = easy_val + (hard_val - easy_val) * normalized

    return result
```

### 1.5 Constants

```python
# Tier point values (exponential scaling)
TIER_POINTS = {
    1: 1,   # 2^0 = 1
    2: 2,   # 2^1 = 2
    3: 4,   # 2^2 = 4
    4: 8,   # 2^3 = 8
}

# Difficulty scaling ranges
DIFFICULTY_RANGES = {
    'min_points': 1.0,    # Single T1 material
    'max_points': 100.0,  # Large T4 recipe
}

# Smithing parameter ranges
SMITHING_PARAMS = {
    'time_limit': (60, 20),
    'temp_ideal_range': (30, 2),  # Converted to min/max in integration
    'temp_decay_rate': (0.3, 1.5),
    'required_hits': (3, 15),
    'target_width': (120, 30),
    'perfect_width': (60, 10),
    'hammer_speed': (2.0, 7.0),
    'temp_fan_increment': (4, 1),
}

# Refining parameter ranges
REFINING_PARAMS = {
    'time_limit': (60, 10),
    'cylinder_count': (2, 18),
    'timing_window': (1.2, 0.15),
    'rotation_speed': (0.8, 3.0),
    'allowed_failures': (3, 0),
}
```

---

## 2. Reward Calculator Module

### File: `core/reward_calculator.py`

### 2.1 Purpose

Centralized reward calculation that scales with difficulty. Harder recipes unlock higher potential rewards.

### 2.2 Core Functions

```python
def calculate_max_reward_multiplier(difficulty_points: float) -> float:
    """
    Calculate maximum achievable reward multiplier based on difficulty.

    Formula: 1.0 + (normalized_difficulty * 1.5)
    - Easy (1 point): 1.0x max bonus
    - Medium (50 points): 1.75x max bonus
    - Hard (100 points): 2.5x max bonus

    Args:
        difficulty_points: From calculate_material_points()

    Returns:
        Maximum reward multiplier (1.0 to 2.5)
    """

def calculate_smithing_rewards(
    difficulty_points: float,
    performance: Dict
) -> Dict:
    """
    Calculate smithing rewards based on performance.

    Args:
        difficulty_points: Total recipe difficulty
        performance: {
            'avg_hammer_score': 0-100,
            'temp_in_ideal': bool,
            'attempt': int (1 = first try)
        }

    Returns:
        {
            'stat_multiplier': float,  # Applied to all stats
            'quality_tier': str,       # 'Normal'/'Fine'/'Superior'/'Masterwork'/'Legendary'
            'bonus_pct': int,          # Percentage bonus (0-25+)
            'first_try_bonus': bool    # Eligible for special attribute
        }
    """

def calculate_refining_rewards(
    difficulty_points: float,
    success: bool,
    input_quantity: int
) -> Dict:
    """
    Calculate refining rewards.

    Args:
        difficulty_points: Total recipe difficulty
        success: Whether minigame succeeded
        input_quantity: Total input material quantity

    Returns:
        {
            'success': bool,
            'max_rarity_upgrade': int,  # Maximum rarity tiers to upgrade
            'quality_multiplier': float,
            'material_loss': float      # If failed (0.3 to 0.9 based on tier)
        }
    """
```

### 2.3 Quality Tier Mapping

```python
QUALITY_TIERS = {
    (0.0, 0.25): 'Normal',      # 0-25% performance
    (0.25, 0.50): 'Fine',       # 25-50% performance
    (0.50, 0.75): 'Superior',   # 50-75% performance
    (0.75, 0.90): 'Masterwork', # 75-90% performance
    (0.90, 1.0): 'Legendary',   # 90-100% performance
}

def get_quality_tier(performance_score: float) -> str:
    """Map performance score (0-1) to quality tier name."""
    for (min_score, max_score), tier_name in QUALITY_TIERS.items():
        if min_score <= performance_score < max_score:
            return tier_name
    return 'Legendary'  # 1.0 exactly
```

### 2.4 Bonus Calculation Formula

```python
def calculate_bonus_pct(
    performance_score: float,  # 0.0 to 1.0
    max_multiplier: float      # From calculate_max_reward_multiplier()
) -> int:
    """
    Calculate percentage bonus for crafted item stats.

    Formula: performance_score * (max_multiplier - 1) * 20

    At max difficulty (2.5x multiplier):
    - 50% performance = 15% bonus
    - 100% performance = 30% bonus

    At min difficulty (1.0x multiplier):
    - Any performance = 0% bonus (base stats only)
    """
    return int(performance_score * (max_multiplier - 1.0) * 20)
```

---

## 3. Smithing Integration

### File: `Crafting-subdisciplines/smithing.py`

### 3.1 Changes to `SmithingMinigame.__init__`

**Current** (line 33-66):
- Receives `tier` parameter
- Calls `_setup_difficulty()` which hard-codes values per tier

**New**:
- Receive `recipe` parameter (full recipe dict)
- Import and call `calculate_smithing_difficulty(recipe)`
- Use returned parameters instead of tier-based values

```python
def __init__(self, recipe, buff_time_bonus=0.0, buff_quality_bonus=0.0):
    self.recipe = recipe
    self.buff_time_bonus = buff_time_bonus
    self.buff_quality_bonus = buff_quality_bonus

    # NEW: Calculate difficulty from materials
    from core.difficulty_calculator import calculate_smithing_difficulty
    difficulty_params = calculate_smithing_difficulty(recipe)

    # Store difficulty points for reward calculation
    self.difficulty_points = difficulty_params['difficulty_points']

    # Apply parameters
    self.time_limit = int(difficulty_params['time_limit'])
    self.TEMP_IDEAL_MIN = 50 + int((100 - difficulty_params['temp_ideal_range']) / 2)
    self.TEMP_IDEAL_MAX = 50 + int((100 + difficulty_params['temp_ideal_range']) / 2)
    self.TEMP_DECAY = difficulty_params['temp_decay_rate']
    self.TEMP_FAN_INCREMENT = difficulty_params['temp_fan_increment']
    self.REQUIRED_HITS = int(difficulty_params['required_hits'])
    self.TARGET_WIDTH = int(difficulty_params['target_width'])
    self.PERFECT_WIDTH = int(difficulty_params['perfect_width'])
    self.HAMMER_SPEED = difficulty_params['hammer_speed']
    self.HAMMER_BAR_WIDTH = 400

    # Apply buff bonuses
    if self.buff_time_bonus > 0:
        self.time_limit = int(self.time_limit * (1.0 + self.buff_time_bonus))

    # ... rest of initialization
```

### 3.2 Changes to `SmithingMinigame.end`

**Current** (line 188-238):
- Calculates bonus as fixed tiers (15%, 10%, 5%, 0%)

**New**:
- Use reward calculator for scaling bonuses
- Return difficulty_points for craft_with_minigame

```python
def end(self, completed, reason=None):
    self.active = False

    if not completed:
        self.result = {
            "success": False,
            "message": reason or "Failed to complete",
            "score": 0,
            "bonus": 0,
            "difficulty_points": self.difficulty_points
        }
        return

    # Calculate performance score
    avg_hammer_score = sum(self.hammer_scores) / len(self.hammer_scores) if self.hammer_scores else 0
    in_ideal_range = self.TEMP_IDEAL_MIN <= self.temperature <= self.TEMP_IDEAL_MAX
    temp_mult = 1.2 if in_ideal_range else 1.0

    # Normalize to 0-1 scale
    # Max possible: 100 * 1.2 = 120
    performance_score = min(1.0, (avg_hammer_score * temp_mult) / 120)

    # NEW: Calculate rewards using reward calculator
    from core.reward_calculator import calculate_smithing_rewards
    rewards = calculate_smithing_rewards(
        self.difficulty_points,
        {
            'avg_hammer_score': avg_hammer_score,
            'temp_in_ideal': in_ideal_range,
            'attempt': 1  # TODO: Track attempts
        }
    )

    # Apply buff quality bonus
    bonus_pct = rewards['bonus_pct']
    if self.buff_quality_bonus > 0:
        bonus_pct += int(self.buff_quality_bonus * 10)

    self.result = {
        "success": True,
        "score": avg_hammer_score * temp_mult,
        "bonus": bonus_pct,
        "quality_tier": rewards['quality_tier'],
        "stat_multiplier": rewards['stat_multiplier'],
        "temp_mult": temp_mult,
        "avg_hammer": avg_hammer_score,
        "difficulty_points": self.difficulty_points,
        "message": f"Crafted {rewards['quality_tier']} item with +{bonus_pct}% bonus!"
    }
```

### 3.3 Changes to `SmithingCrafter.create_minigame`

**Current** (line 488-506):
- Passes tier to minigame

**New**:
- Pass full recipe to minigame

```python
def create_minigame(self, recipe_id, buff_time_bonus=0.0, buff_quality_bonus=0.0):
    if recipe_id not in self.recipes:
        return None

    recipe = self.recipes[recipe_id]

    # NEW: Pass full recipe instead of just tier
    return SmithingMinigame(recipe, buff_time_bonus, buff_quality_bonus)
```

---

## 4. Refining Integration

### File: `Crafting-subdisciplines/refining.py`

### 4.1 Changes to `RefiningMinigame.__init__`

**Current** (line 35-66):
- Receives `tier` parameter
- Hard-codes values per tier

**New**:
- Receive `recipe` parameter
- Calculate difficulty with diversity multiplier

```python
def __init__(self, recipe, buff_time_bonus=0.0, buff_quality_bonus=0.0):
    self.recipe = recipe
    self.buff_time_bonus = buff_time_bonus
    self.buff_quality_bonus = buff_quality_bonus

    # NEW: Calculate difficulty from materials with diversity
    from core.difficulty_calculator import calculate_refining_difficulty
    difficulty_params = calculate_refining_difficulty(recipe)

    # Store for reward calculation
    self.difficulty_points = difficulty_params['difficulty_points']

    # Apply parameters
    self.cylinder_count = int(difficulty_params['cylinder_count'])
    self.timing_window = difficulty_params['timing_window']
    self.rotation_speed = difficulty_params['rotation_speed']
    self.allowed_failures = int(difficulty_params['allowed_failures'])
    self.time_limit = int(difficulty_params['time_limit'])
    self.multi_speed = difficulty_params.get('multi_speed', False)

    # Apply buff
    if self.buff_time_bonus > 0:
        self.time_limit = int(self.time_limit * (1.0 + self.buff_time_bonus))

    # ... rest of initialization
```

### 4.2 Changes to `RefiningMinigame.end`

```python
def end(self, success, reason=None):
    self.active = False

    if success:
        self.result = {
            "success": True,
            "message": "Refinement successful!",
            "attempts": self.current_cylinder + self.failed_attempts,
            "quality_bonus": self.buff_quality_bonus,
            "difficulty_points": self.difficulty_points
        }
    else:
        # NEW: Tier-scaled material loss
        from core.reward_calculator import calculate_failure_penalty
        material_loss = calculate_failure_penalty(self.difficulty_points)

        self.result = {
            "success": False,
            "message": reason or "Refinement failed",
            "materials_lost": material_loss,
            "difficulty_points": self.difficulty_points
        }
```

---

## 5. Visual Polish Specifications

### 5.1 Smithing Visual Improvements

**Location**: `core/game_engine.py:_render_smithing_minigame()` (lines 3211-3350)

#### 5.1.1 Forge Background

```python
# Add forge/anvil background image or procedural graphics
# Current: Plain dark overlay (20, 20, 30, 250)
# New: Add forge aesthetics

def _render_forge_background(self, surf, ww, wh):
    """Render forge atmosphere background"""
    # Gradient background (dark at top, warm glow at bottom)
    for y in range(wh):
        progress = y / wh
        r = int(20 + 40 * progress)
        g = int(15 + 20 * progress)
        b = int(25 - 10 * progress)
        pygame.draw.line(surf, (r, g, b), (0, y), (ww, y))

    # Ember particles (animated)
    tick = pygame.time.get_ticks()
    for i in range(15):
        x = (tick // 20 + i * 67) % ww
        y = wh - 50 - ((tick // 30 + i * 31) % 200)
        size = 2 + (i % 3)
        alpha = 100 + (i % 100)
        ember_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(ember_surf, (255, 150, 50, alpha), (size, size), size)
        surf.blit(ember_surf, (x, y))
```

#### 5.1.2 Enhanced Temperature Display

```python
# Current: Simple colored bar
# New: Forge fire visualization

def _render_temperature_forge(self, surf, state, x, y, w, h):
    """Render temperature as visual forge fire"""
    temp = state['temperature']
    ideal_min = state['temp_ideal_min']
    ideal_max = state['temp_ideal_max']

    # Fire container (brick frame)
    pygame.draw.rect(surf, (80, 40, 30), (x-5, y-5, w+10, h+10))
    pygame.draw.rect(surf, (60, 30, 20), (x, y, w, h))

    # Flame visualization
    flame_height = int((temp / 100) * h)

    # Multiple flame layers for depth
    tick = pygame.time.get_ticks()
    for layer in range(3):
        wave = math.sin(tick / 200 + layer) * 10
        layer_width = w - layer * 20
        layer_x = x + layer * 10

        # Flame color based on temperature
        if temp > 80:
            color = (255, 255 - layer * 30, 200 - layer * 50)  # White-hot
        elif temp > 60:
            color = (255, 180 - layer * 30, 50)  # Orange
        elif temp > 40:
            color = (255, 120 - layer * 20, 20)  # Red
        else:
            color = (100, 80, 200 - layer * 30)  # Blue (cool)

        # Draw flame polygon
        points = [
            (layer_x, y + h),
            (layer_x + layer_width // 4, y + h - flame_height * 0.6 + wave),
            (layer_x + layer_width // 2, y + h - flame_height),
            (layer_x + layer_width * 3 // 4, y + h - flame_height * 0.7 - wave),
            (layer_x + layer_width, y + h),
        ]
        pygame.draw.polygon(surf, color, points)

    # Ideal range indicator (glowing marks on sides)
    ideal_y_min = y + h - int((ideal_min / 100) * h)
    ideal_y_max = y + h - int((ideal_max / 100) * h)

    in_ideal = ideal_min <= temp <= ideal_max
    mark_color = (100, 255, 100) if in_ideal else (200, 200, 200)
    pygame.draw.line(surf, mark_color, (x - 8, ideal_y_min), (x - 2, ideal_y_min), 3)
    pygame.draw.line(surf, mark_color, (x - 8, ideal_y_max), (x - 2, ideal_y_max), 3)
    pygame.draw.line(surf, mark_color, (x + w + 2, ideal_y_min), (x + w + 8, ideal_y_min), 3)
    pygame.draw.line(surf, mark_color, (x + w + 2, ideal_y_max), (x + w + 8, ideal_y_max), 3)
```

#### 5.1.3 Anvil Hammer Display

```python
def _render_anvil_hammer(self, surf, state, x, y, w, h):
    """Render hammer timing as anvil strike zone"""
    hammer_pos = state['hammer_position']
    target_w = state['target_width']
    perfect_w = state['perfect_width']

    # Anvil shape (trapezoid)
    anvil_color = (80, 80, 90)
    anvil_points = [
        (x + 20, y),
        (x + w - 20, y),
        (x + w, y + h),
        (x, y + h),
    ]
    pygame.draw.polygon(surf, anvil_color, anvil_points)
    pygame.draw.polygon(surf, (120, 120, 130), anvil_points, 3)

    # Strike zone visualization (glowing area on anvil)
    center = w / 2
    target_x = x + int(center - target_w / 2)
    perfect_x = x + int(center - perfect_w / 2)

    # Target zone glow
    target_surf = pygame.Surface((target_w, h), pygame.SRCALPHA)
    target_surf.fill((100, 100, 60, 80))
    surf.blit(target_surf, (target_x, y))

    # Perfect zone glow (brighter)
    perfect_surf = pygame.Surface((perfect_w, h), pygame.SRCALPHA)
    perfect_surf.fill((150, 180, 80, 120))
    surf.blit(perfect_surf, (perfect_x, y))

    # Hammer indicator (hammer head shape)
    hammer_x = x + int(hammer_pos)
    hammer_y = y - 30

    # Hammer head
    pygame.draw.rect(surf, (60, 50, 50), (hammer_x - 15, hammer_y, 30, 25))
    pygame.draw.rect(surf, (100, 90, 80), (hammer_x - 15, hammer_y, 30, 25), 2)

    # Hammer handle
    pygame.draw.rect(surf, (100, 70, 40), (hammer_x - 5, hammer_y + 25, 10, 40))

    # Impact line showing where hammer will strike
    pygame.draw.line(surf, (255, 255, 200, 150),
                     (hammer_x, hammer_y + 25), (hammer_x, y + h), 2)
```

#### 5.1.4 Hit Feedback

```python
def _render_hit_feedback(self, surf, state, x, y):
    """Render visual feedback for hammer hits"""
    scores = state['hammer_scores']

    if scores:
        # Show last hit with dramatic effect
        last_score = scores[-1]

        # Spark burst on hit
        tick = pygame.time.get_ticks()
        if tick - self.last_hit_time < 500:  # Fade over 500ms
            alpha = int(255 * (1 - (tick - self.last_hit_time) / 500))

            if last_score >= 90:
                spark_color = (255, 255, 100, alpha)  # Gold sparks
                spark_count = 12
            elif last_score >= 70:
                spark_color = (255, 200, 100, alpha)  # Orange sparks
                spark_count = 8
            else:
                spark_color = (150, 150, 150, alpha)  # Gray sparks
                spark_count = 4

            for i in range(spark_count):
                angle = (i / spark_count) * 2 * math.pi
                distance = 30 + (tick - self.last_hit_time) / 10
                spark_x = x + int(math.cos(angle) * distance)
                spark_y = y + int(math.sin(angle) * distance)
                pygame.draw.circle(surf, spark_color[:3], (spark_x, spark_y), 3)
```

### 5.2 Refining Visual Improvements

**Location**: `core/game_engine.py:_render_refining_minigame()` (lines 3449-3516)

#### 5.2.1 Lock Mechanism Aesthetic

```python
def _render_lock_mechanism(self, surf, state, cx, cy, radius):
    """Render lock tumbler visualization"""
    current_cyl = state['current_cylinder']
    cylinders = state['cylinders']
    total = state['total_cylinders']

    # Lock body background
    lock_w = radius * 2 + 40
    lock_h = radius * 2 + 60
    lock_x = cx - lock_w // 2
    lock_y = cy - radius - 20

    # Metallic lock body
    pygame.draw.rect(surf, (70, 70, 80), (lock_x, lock_y, lock_w, lock_h), border_radius=10)
    pygame.draw.rect(surf, (100, 100, 110), (lock_x, lock_y, lock_w, lock_h), 3, border_radius=10)

    # Keyhole at bottom
    pygame.draw.ellipse(surf, (30, 30, 35), (cx - 15, cy + radius + 10, 30, 20))
    pygame.draw.rect(surf, (30, 30, 35), (cx - 8, cy + radius + 25, 16, 25))

    # Main tumbler cylinder
    pygame.draw.circle(surf, (50, 50, 55), (cx, cy), radius)
    pygame.draw.circle(surf, (80, 80, 85), (cx, cy), radius - 10)
    pygame.draw.circle(surf, (60, 60, 65), (cx, cy), radius - 20)

    # Outer ring (metallic)
    pygame.draw.circle(surf, (120, 120, 130), (cx, cy), radius, 4)

    # Pin indicators around the edge (showing progress)
    for i in range(total):
        angle = (i / total) * 2 * math.pi - math.pi / 2  # Start from top
        pin_x = cx + int((radius + 25) * math.cos(angle))
        pin_y = cy + int((radius + 25) * math.sin(angle))

        if i < len(state.get('aligned_cylinders', [])):
            pin_color = (100, 200, 100)  # Aligned - green
        elif i == current_cyl:
            pin_color = (255, 215, 0)  # Current - gold
        else:
            pin_color = (60, 60, 70)  # Pending - dark

        pygame.draw.circle(surf, pin_color, (pin_x, pin_y), 8)
        pygame.draw.circle(surf, (40, 40, 45), (pin_x, pin_y), 8, 2)
```

#### 5.2.2 Rotating Tumbler

```python
def _render_rotating_tumbler(self, surf, state, cx, cy, radius):
    """Render the current rotating tumbler with indicator"""
    if state['current_cylinder'] >= len(state['cylinders']):
        return

    cyl = state['cylinders'][state['current_cylinder']]
    angle = cyl['angle']

    # Inner mechanism with notches
    inner_radius = radius - 30

    # Draw notch pattern (lockpicking style)
    notch_count = 8
    for i in range(notch_count):
        notch_angle = (i / notch_count) * 2 * math.pi
        outer_x = cx + int(inner_radius * math.cos(notch_angle))
        outer_y = cy + int(inner_radius * math.sin(notch_angle))
        inner_x = cx + int((inner_radius - 15) * math.cos(notch_angle))
        inner_y = cy + int((inner_radius - 15) * math.sin(notch_angle))
        pygame.draw.line(surf, (40, 40, 45), (inner_x, inner_y), (outer_x, outer_y), 3)

    # Rotating indicator (pick/probe)
    angle_rad = math.radians(angle - 90)  # -90 to start from top

    # Indicator line (the "pick")
    ind_inner = 20
    ind_outer = inner_radius - 5
    inner_x = cx + int(ind_inner * math.cos(angle_rad))
    inner_y = cy + int(ind_inner * math.sin(angle_rad))
    outer_x = cx + int(ind_outer * math.cos(angle_rad))
    outer_y = cy + int(ind_outer * math.sin(angle_rad))

    pygame.draw.line(surf, (200, 180, 100), (inner_x, inner_y), (outer_x, outer_y), 4)
    pygame.draw.circle(surf, (255, 215, 0), (outer_x, outer_y), 8)

    # Target zone indicator at top
    target_width_deg = state['timing_window'] * cyl['speed'] * 360
    target_half = target_width_deg / 2

    # Draw arc for target zone
    target_rect = pygame.Rect(cx - inner_radius, cy - inner_radius,
                              inner_radius * 2, inner_radius * 2)

    # Green arc at top (target zone)
    start_angle = math.radians(90 - target_half)
    end_angle = math.radians(90 + target_half)

    # Draw target zone as filled arc
    points = [(cx, cy - inner_radius)]
    for a in range(int(90 - target_half), int(90 + target_half) + 1, 5):
        rad = math.radians(a)
        x = cx + int(inner_radius * math.cos(rad - math.pi/2))
        y = cy + int(inner_radius * math.sin(rad - math.pi/2))
        points.append((x, y))

    if len(points) > 2:
        pygame.draw.polygon(surf, (80, 180, 80, 150), points)
```

#### 5.2.3 Success/Failure Feedback

```python
def _render_tumbler_feedback(self, surf, state, cx, cy):
    """Render feedback for successful/failed alignment"""
    feedback_timer = state.get('feedback_timer', 0)

    if feedback_timer > 0:
        # Determine if last action was success or failure
        aligned = len(state.get('aligned_cylinders', []))

        # Flash effect
        alpha = int(200 * (feedback_timer / 0.3))

        if aligned > 0:  # Success
            flash_surf = pygame.Surface((200, 200), pygame.SRCALPHA)
            pygame.draw.circle(flash_surf, (100, 255, 100, alpha), (100, 100), 80)
            surf.blit(flash_surf, (cx - 100, cy - 100))

            # "CLICK" text
            click_text = self.renderer.font.render("CLICK!", True, (100, 255, 100))
            text_alpha = pygame.Surface(click_text.get_size(), pygame.SRCALPHA)
            text_alpha.fill((255, 255, 255, alpha))
            click_text.blit(text_alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(click_text, (cx - 40, cy - 120))
        else:  # Failure
            flash_surf = pygame.Surface((200, 200), pygame.SRCALPHA)
            pygame.draw.circle(flash_surf, (255, 100, 100, alpha), (100, 100), 80)
            surf.blit(flash_surf, (cx - 100, cy - 100))
```

---

## 6. Tier-Scaled Penalties

### 6.1 Failure Penalty Calculation

```python
# In core/reward_calculator.py

def calculate_failure_penalty(difficulty_points: float) -> float:
    """
    Calculate material loss on minigame failure.

    Scales from 30% (easy) to 90% (hard).

    Formula: 0.3 + (normalized_difficulty * 0.6)

    Args:
        difficulty_points: From calculate_material_points()

    Returns:
        Material loss fraction (0.3 to 0.9)
    """
    normalized = min(1.0, max(0.0, (difficulty_points - 1) / 99))
    return 0.3 + (normalized * 0.6)
```

### 6.2 Integration Points

**Smithing** (`smithing.py:522-530`):
```python
# Current: 50% fixed loss
loss = inp['quantity'] // 2

# New: Scaled loss
from core.reward_calculator import calculate_failure_penalty
loss_pct = calculate_failure_penalty(minigame_result.get('difficulty_points', 50))
loss = int(inp['quantity'] * loss_pct)
```

**Refining** (`refining.py:489-492`):
```python
# Current: 50% fixed loss
loss = inp['quantity'] // 2

# New: Scaled loss
from core.reward_calculator import calculate_failure_penalty
loss_pct = calculate_failure_penalty(minigame_result.get('difficulty_points', 50))
loss = int(inp['quantity'] * loss_pct)
```

---

## 7. Integration Points

### 7.1 Files to Create

1. `core/difficulty_calculator.py` - New module
2. `core/reward_calculator.py` - New module

### 7.2 Files to Modify

1. `Crafting-subdisciplines/smithing.py`
   - `SmithingMinigame.__init__` (lines 33-67)
   - `SmithingMinigame._setup_difficulty` (DELETE - replace with calculator)
   - `SmithingMinigame.end` (lines 188-238)
   - `SmithingCrafter.create_minigame` (lines 488-506)
   - `SmithingCrafter.craft_with_minigame` (lines 508-610)

2. `Crafting-subdisciplines/refining.py`
   - `RefiningMinigame.__init__` (lines 35-66)
   - `RefiningMinigame._setup_difficulty` (DELETE - replace with calculator)
   - `RefiningMinigame.end` (lines 211-233)
   - `RefiningCrafter.create_minigame` (lines 453-471)
   - `RefiningCrafter.craft_with_minigame` (lines 473-595)

3. `core/game_engine.py`
   - `_render_smithing_minigame` (lines 3211-3350) - Visual polish
   - `_render_refining_minigame` (lines 3449-3516) - Visual polish

### 7.3 Backward Compatibility

- Keep `stationTier` fallback for recipes without material data
- If material lookup fails, fall back to tier-based difficulty
- Log warnings for missing material data

```python
def calculate_smithing_difficulty(recipe: Dict) -> Dict:
    inputs = recipe.get('inputs', [])

    if not inputs:
        # Fallback to tier-based (legacy behavior)
        tier = recipe.get('stationTier', 1)
        return _legacy_tier_difficulty(tier)

    # New material-based calculation
    ...
```

---

## Summary Checklist

### Core Modules
- [ ] Create `core/difficulty_calculator.py`
  - [ ] `calculate_material_points()`
  - [ ] `calculate_diversity_multiplier()`
  - [ ] `calculate_average_tier()`
  - [ ] `interpolate_difficulty()`
  - [ ] `calculate_smithing_difficulty()`
  - [ ] `calculate_refining_difficulty()`

- [ ] Create `core/reward_calculator.py`
  - [ ] `calculate_max_reward_multiplier()`
  - [ ] `calculate_smithing_rewards()`
  - [ ] `calculate_refining_rewards()`
  - [ ] `calculate_failure_penalty()`
  - [ ] `get_quality_tier()`

### Smithing Integration
- [ ] Update `SmithingMinigame.__init__` to use calculator
- [ ] Update `SmithingMinigame.end` to use reward calculator
- [ ] Update `SmithingCrafter.create_minigame`
- [ ] Update `SmithingCrafter.craft_with_minigame` for tier penalties
- [ ] Add visual polish to `_render_smithing_minigame`

### Refining Integration
- [ ] Update `RefiningMinigame.__init__` to use calculator
- [ ] Update `RefiningMinigame.end` to use reward calculator
- [ ] Update `RefiningCrafter.create_minigame`
- [ ] Update `RefiningCrafter.craft_with_minigame` for tier penalties
- [ ] Add visual polish to `_render_refining_minigame`

### Testing
- [ ] Test with T1 materials (low difficulty)
- [ ] Test with T4 materials (high difficulty)
- [ ] Test with mixed tier materials
- [ ] Test with multiple unique materials (diversity)
- [ ] Verify visual polish renders correctly
- [ ] Test failure penalty scaling

---

**Document Version**: 1.0
**Last Updated**: January 4, 2026
