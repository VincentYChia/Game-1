"""
Difficulty Calculator Module

Centralized difficulty calculation for crafting minigames based on material
tier point values, replacing the previous tier-only system.

Core Principle:
    Difficulty = f(material_tiers, material_count, discipline_modifiers)

Material Point System (Linear):
    - Each material contributes: tier * quantity
    - T1: 1 point, T2: 2 points, T3: 3 points, T4: 4 points per item

Diversity Multiplier (for Refining, Alchemy, Engineering):
    - More unique materials = higher difficulty
    - Formula: 1.0 + (unique_count - 1) * 0.1

Difficulty Tiers (match rarity naming):
    - Common (1-8 points): Basic single-material recipes
    - Uncommon (9-20 points): Multi-material or T2 recipes
    - Rare (21-40 points): Complex T3 recipes
    - Epic (41-70 points): High-tier multi-material recipes
    - Legendary (71+ points): Extreme T4 complex recipes
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


# =============================================================================
# CONSTANTS
# =============================================================================

# Tier point values (LINEAR scaling as requested)
TIER_POINTS = {
    1: 1,   # T1 = 1 point per item
    2: 2,   # T2 = 2 points per item
    3: 3,   # T3 = 3 points per item
    4: 4,   # T4 = 4 points per item
}

# Difficulty thresholds (matching rarity naming)
DIFFICULTY_THRESHOLDS = {
    'common': (0, 8),       # Easy beginner recipes
    'uncommon': (9, 20),    # Moderate challenge
    'rare': (21, 40),       # Skilled crafters
    'epic': (41, 70),       # Expert level
    'legendary': (71, 150), # Master crafters only
}

# Default scaling range for interpolation
DIFFICULTY_RANGES = {
    'min_points': 1.0,      # Single T1 material
    'max_points': 80.0,     # Adjusted for linear scaling (was 100 for exponential)
}


# =============================================================================
# SMITHING PARAMETERS - Forge/Anvil minigame
# =============================================================================

SMITHING_PARAMS = {
    # Time limit: generous at low difficulty, tight at high
    'time_limit': (60, 25),

    # Temperature ideal range: wide at low difficulty, narrow at high
    'temp_ideal_range': (25, 5),  # Degrees of acceptable range

    # Temperature decay: slow at low, fast at high
    'temp_decay_rate': (0.3, 1.2),

    # Fan increment: big boost at low, small at high
    'temp_fan_increment': (4, 1.5),

    # Required hammer hits
    'required_hits': (3, 12),

    # Target zone width (pixels) - where hits count
    'target_width': (100, 35),

    # Perfect zone width (pixels) - for bonus score
    'perfect_width': (50, 12),

    # Hammer oscillation speed
    'hammer_speed': (2.0, 6.0),
}


# =============================================================================
# REFINING PARAMETERS - Lock/Tumbler minigame (MADE HARDER)
# =============================================================================

REFINING_PARAMS = {
    # Time limit: reasonable at low, tight at high
    'time_limit': (45, 15),

    # Cylinder count: few at low, MANY at high (can go past 3!)
    'cylinder_count': (3, 12),

    # Timing window in SECONDS - this was too large before!
    # Now: 0.4s at easy (still requires timing), 0.08s at hard (very precise)
    'timing_window': (0.4, 0.08),

    # Rotation speed: slow at low, fast at high
    'rotation_speed': (0.6, 2.5),

    # Allowed failures: forgiving at low, zero tolerance at high
    'allowed_failures': (2, 0),
}


# =============================================================================
# CORE CALCULATION FUNCTIONS
# =============================================================================

def calculate_material_points(inputs: List[Dict]) -> float:
    """
    Calculate total difficulty points from recipe inputs.

    Each material contributes: tier * quantity (LINEAR)
    - T1: 1 point per item
    - T2: 2 points per item
    - T3: 3 points per item
    - T4: 4 points per item

    Args:
        inputs: List of {'materialId': str, 'quantity': int}

    Returns:
        Total difficulty points (float)
    """
    if not inputs:
        return 1.0  # Minimum difficulty

    total_points = 0.0

    # Try to import MaterialDatabase for tier lookup
    try:
        from data.databases.material_db import MaterialDatabase
        mat_db = MaterialDatabase.get_instance()
        has_db = mat_db.loaded if hasattr(mat_db, 'loaded') else bool(mat_db.materials)
    except ImportError:
        mat_db = None
        has_db = False

    for inp in inputs:
        material_id = inp.get('materialId', inp.get('itemId', ''))
        quantity = inp.get('quantity', 1)

        # Get tier from database or default to 1
        tier = 1
        if has_db and mat_db:
            material = mat_db.get_material(material_id)
            if material:
                tier = material.tier

        # Calculate points: tier * quantity (LINEAR)
        tier_points = TIER_POINTS.get(tier, tier)
        total_points += tier_points * quantity

    return max(1.0, total_points)


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
    if not inputs:
        return 1.0

    unique_materials = set()
    for inp in inputs:
        material_id = inp.get('materialId', inp.get('itemId', ''))
        if material_id:
            unique_materials.add(material_id)

    unique_count = len(unique_materials)
    return 1.0 + (unique_count - 1) * 0.1


def calculate_average_tier(inputs: List[Dict]) -> float:
    """
    Calculate weighted average tier of materials.

    Used for: Alchemy tier exponential modifier (1.2^avg_tier)

    Args:
        inputs: List of {'materialId': str, 'quantity': int}

    Returns:
        Weighted average tier (float, minimum 1.0)
    """
    if not inputs:
        return 1.0

    # Try to import MaterialDatabase for tier lookup
    try:
        from data.databases.material_db import MaterialDatabase
        mat_db = MaterialDatabase.get_instance()
        has_db = mat_db.loaded if hasattr(mat_db, 'loaded') else bool(mat_db.materials)
    except ImportError:
        mat_db = None
        has_db = False

    total_tier = 0.0
    total_quantity = 0

    for inp in inputs:
        material_id = inp.get('materialId', inp.get('itemId', ''))
        quantity = inp.get('quantity', 1)

        tier = 1
        if has_db and mat_db:
            material = mat_db.get_material(material_id)
            if material:
                tier = material.tier

        total_tier += tier * quantity
        total_quantity += quantity

    if total_quantity == 0:
        return 1.0

    return total_tier / total_quantity


def interpolate_difficulty(
    points: float,
    param_ranges: Dict[str, Tuple[float, float]],
    min_points: float = None,
    max_points: float = None
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
    """
    if min_points is None:
        min_points = DIFFICULTY_RANGES['min_points']
    if max_points is None:
        max_points = DIFFICULTY_RANGES['max_points']

    # Normalize points to 0-1 range
    normalized = max(0.0, min(1.0, (points - min_points) / (max_points - min_points)))

    result = {}
    for param, (easy_val, hard_val) in param_ranges.items():
        result[param] = easy_val + (hard_val - easy_val) * normalized

    return result


# =============================================================================
# DISCIPLINE-SPECIFIC DIFFICULTY FUNCTIONS
# =============================================================================

def calculate_smithing_difficulty(recipe: Dict) -> Dict:
    """
    Calculate smithing difficulty based on material points.
    Smithing does NOT use diversity multiplier (single-focus craft).

    Args:
        recipe: Full recipe dictionary with 'inputs' list

    Returns:
        Dict with all smithing parameters plus 'difficulty_points'
    """
    inputs = recipe.get('inputs', [])

    # Calculate base points (no diversity for smithing)
    total_points = calculate_material_points(inputs)

    # Interpolate parameters
    params = interpolate_difficulty(total_points, SMITHING_PARAMS)

    # Convert temp_ideal_range to min/max values
    # Ideal zone centered around 70°C
    temp_range = params['temp_ideal_range']
    center_temp = 70
    params['temp_ideal_min'] = center_temp - temp_range / 2
    params['temp_ideal_max'] = center_temp + temp_range / 2

    # Ensure reasonable bounds
    params['temp_ideal_min'] = max(55, min(75, params['temp_ideal_min']))
    params['temp_ideal_max'] = max(params['temp_ideal_min'] + 3, min(85, params['temp_ideal_max']))

    # Add metadata
    params['difficulty_points'] = total_points
    params['difficulty_tier'] = get_difficulty_tier(total_points)
    params['tier_fallback'] = recipe.get('stationTier', 1)

    return params


def calculate_refining_difficulty(recipe: Dict) -> Dict:
    """
    Calculate refining difficulty based on material points × diversity multiplier.

    More unique materials = harder (narratively: complex reactions)

    Args:
        recipe: Full recipe dictionary with 'inputs' list

    Returns:
        Dict with all refining parameters plus 'difficulty_points'
    """
    inputs = recipe.get('inputs', [])

    # Calculate base points with diversity
    base_points = calculate_material_points(inputs)
    diversity_mult = calculate_diversity_multiplier(inputs)

    total_points = base_points * diversity_mult

    # Interpolate parameters
    params = interpolate_difficulty(total_points, REFINING_PARAMS)

    # Round integer parameters
    params['cylinder_count'] = max(2, int(round(params['cylinder_count'])))
    params['allowed_failures'] = max(0, int(round(params['allowed_failures'])))
    params['time_limit'] = int(round(params['time_limit']))

    # Enable multi-speed for Rare+ difficulty
    params['multi_speed'] = total_points >= DIFFICULTY_THRESHOLDS['rare'][0]

    # Add metadata
    params['difficulty_points'] = total_points
    params['difficulty_tier'] = get_difficulty_tier(total_points)
    params['diversity_multiplier'] = diversity_mult
    params['tier_fallback'] = recipe.get('stationTier', 1)

    return params


# =============================================================================
# LEGACY FALLBACK (for recipes without proper material data)
# =============================================================================

def get_legacy_smithing_params(tier: int) -> Dict:
    """
    Get smithing parameters using legacy tier-based system.
    Used as fallback when material data is unavailable.
    """
    tier_configs = {
        1: {
            'time_limit': 50, 'temp_ideal_min': 60, 'temp_ideal_max': 80,
            'temp_decay_rate': 0.4, 'temp_fan_increment': 3.5, 'required_hits': 4,
            'target_width': 90, 'perfect_width': 40, 'hammer_speed': 2.5,
            'difficulty_points': 4, 'difficulty_tier': 'common'
        },
        2: {
            'time_limit': 40, 'temp_ideal_min': 62, 'temp_ideal_max': 78,
            'temp_decay_rate': 0.6, 'temp_fan_increment': 2.8, 'required_hits': 6,
            'target_width': 70, 'perfect_width': 30, 'hammer_speed': 3.5,
            'difficulty_points': 12, 'difficulty_tier': 'uncommon'
        },
        3: {
            'time_limit': 32, 'temp_ideal_min': 66, 'temp_ideal_max': 74,
            'temp_decay_rate': 0.9, 'temp_fan_increment': 2, 'required_hits': 9,
            'target_width': 50, 'perfect_width': 18, 'hammer_speed': 4.8,
            'difficulty_points': 30, 'difficulty_tier': 'rare'
        },
        4: {
            'time_limit': 25, 'temp_ideal_min': 68, 'temp_ideal_max': 72,
            'temp_decay_rate': 1.1, 'temp_fan_increment': 1.5, 'required_hits': 11,
            'target_width': 38, 'perfect_width': 14, 'hammer_speed': 5.8,
            'difficulty_points': 60, 'difficulty_tier': 'epic'
        },
    }
    return tier_configs.get(tier, tier_configs[1])


def get_legacy_refining_params(tier: int) -> Dict:
    """
    Get refining parameters using legacy tier-based system.
    Used as fallback when material data is unavailable.
    """
    tier_configs = {
        1: {
            'time_limit': 40, 'cylinder_count': 3, 'timing_window': 0.35,
            'rotation_speed': 0.7, 'allowed_failures': 2, 'multi_speed': False,
            'difficulty_points': 4, 'difficulty_tier': 'common', 'diversity_multiplier': 1.0
        },
        2: {
            'time_limit': 30, 'cylinder_count': 5, 'timing_window': 0.25,
            'rotation_speed': 1.0, 'allowed_failures': 1, 'multi_speed': False,
            'difficulty_points': 12, 'difficulty_tier': 'uncommon', 'diversity_multiplier': 1.0
        },
        3: {
            'time_limit': 22, 'cylinder_count': 8, 'timing_window': 0.15,
            'rotation_speed': 1.5, 'allowed_failures': 1, 'multi_speed': True,
            'difficulty_points': 30, 'difficulty_tier': 'rare', 'diversity_multiplier': 1.0
        },
        4: {
            'time_limit': 18, 'cylinder_count': 10, 'timing_window': 0.10,
            'rotation_speed': 2.0, 'allowed_failures': 0, 'multi_speed': True,
            'difficulty_points': 60, 'difficulty_tier': 'epic', 'diversity_multiplier': 1.0
        },
    }
    return tier_configs.get(tier, tier_configs[1])


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_difficulty_tier(points: float) -> str:
    """
    Get the rarity-style difficulty tier name.

    Args:
        points: Difficulty points

    Returns:
        Tier name: 'common', 'uncommon', 'rare', 'epic', or 'legendary'
    """
    for tier_name, (min_pts, max_pts) in DIFFICULTY_THRESHOLDS.items():
        if min_pts <= points <= max_pts:
            return tier_name

    # If above all thresholds, it's legendary
    if points > DIFFICULTY_THRESHOLDS['legendary'][1]:
        return 'legendary'

    return 'common'


def get_difficulty_description(points: float) -> str:
    """
    Get a human-readable difficulty description (capitalized tier name).

    Args:
        points: Difficulty points

    Returns:
        Description string (e.g., "Common", "Rare", "Legendary")
    """
    return get_difficulty_tier(points).capitalize()


def estimate_completion_time(points: float, discipline: str) -> int:
    """
    Estimate expected completion time in seconds based on difficulty.

    Args:
        points: Difficulty points
        discipline: 'smithing' or 'refining'

    Returns:
        Estimated seconds to complete
    """
    if discipline == 'smithing':
        params = interpolate_difficulty(points, SMITHING_PARAMS)
        # Smithing time = time_limit (with some buffer for actual gameplay)
        return int(params['time_limit'] * 0.8)
    elif discipline == 'refining':
        params = interpolate_difficulty(points, REFINING_PARAMS)
        # Refining time = cylinders * ~2.5 seconds each
        return int(params['cylinder_count'] * 2.5)
    else:
        return 30  # Default estimate
