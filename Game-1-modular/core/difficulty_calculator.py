"""
Difficulty Calculator Module

Centralized difficulty calculation for crafting minigames based on material
tier point values, replacing the previous tier-only system.

Core Principle:
    Difficulty = f(material_tiers, material_count, discipline_modifiers)

Material Point System:
    - Each material contributes: 2^(tier-1) * quantity
    - T1: 1 point, T2: 2 points, T3: 4 points, T4: 8 points per item

Diversity Multiplier (for Refining, Alchemy, Engineering):
    - More unique materials = higher difficulty
    - Formula: 1.0 + (unique_count - 1) * 0.1
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


# =============================================================================
# CONSTANTS
# =============================================================================

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

# Smithing parameter ranges (easy_value, hard_value)
SMITHING_PARAMS = {
    'time_limit': (60, 20),
    'temp_ideal_range': (30, 2),
    'temp_decay_rate': (0.3, 1.5),
    'temp_fan_increment': (4, 1),
    'required_hits': (3, 15),
    'target_width': (120, 30),
    'perfect_width': (60, 10),
    'hammer_speed': (2.0, 7.0),
}

# Refining parameter ranges (easy_value, hard_value)
REFINING_PARAMS = {
    'time_limit': (60, 10),
    'cylinder_count': (2, 18),
    'timing_window': (1.2, 0.15),
    'rotation_speed': (0.8, 3.0),
    'allowed_failures': (3, 0),
}


# =============================================================================
# CORE CALCULATION FUNCTIONS
# =============================================================================

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

        # Calculate points: 2^(tier-1) * quantity
        tier_points = TIER_POINTS.get(tier, 2 ** (tier - 1))
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
        min_points: Points value for easiest difficulty (default from DIFFICULTY_RANGES)
        max_points: Points value for hardest difficulty (default from DIFFICULTY_RANGES)

    Returns:
        Dict of {param_name: interpolated_value}

    Example:
        param_ranges = {
            'time_limit': (60, 20),
            'required_hits': (3, 15),
        }
        points = 50  # Middle difficulty

        Result: {'time_limit': 40, 'required_hits': 9}
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

    # Calculate base points
    base_points = calculate_material_points(inputs)

    # Smithing doesn't use diversity multiplier
    total_points = base_points

    # Interpolate parameters
    params = interpolate_difficulty(total_points, SMITHING_PARAMS)

    # Convert temp_ideal_range to min/max values
    # Range is centered at 50 (neutral temperature)
    temp_range = params['temp_ideal_range']
    params['temp_ideal_min'] = 50 + int((100 - temp_range) / 2) - 25
    params['temp_ideal_max'] = 50 + int((100 + temp_range) / 2) - 25

    # Clamp values to sensible ranges
    params['temp_ideal_min'] = max(50, min(75, params['temp_ideal_min']))
    params['temp_ideal_max'] = max(params['temp_ideal_min'] + 2, min(90, params['temp_ideal_max']))

    # Add metadata
    params['difficulty_points'] = total_points
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

    # Enable multi-speed for high difficulty
    params['multi_speed'] = total_points >= 60

    # Add metadata
    params['difficulty_points'] = total_points
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
            'time_limit': 45, 'temp_ideal_min': 60, 'temp_ideal_max': 80,
            'temp_decay_rate': 0.5, 'temp_fan_increment': 3, 'required_hits': 5,
            'target_width': 100, 'perfect_width': 40, 'hammer_speed': 2.5,
            'difficulty_points': 5
        },
        2: {
            'time_limit': 40, 'temp_ideal_min': 65, 'temp_ideal_max': 75,
            'temp_decay_rate': 0.7, 'temp_fan_increment': 2.5, 'required_hits': 7,
            'target_width': 80, 'perfect_width': 30, 'hammer_speed': 3.5,
            'difficulty_points': 20
        },
        3: {
            'time_limit': 35, 'temp_ideal_min': 68, 'temp_ideal_max': 72,
            'temp_decay_rate': 0.9, 'temp_fan_increment': 2, 'required_hits': 9,
            'target_width': 60, 'perfect_width': 20, 'hammer_speed': 4.5,
            'difficulty_points': 50
        },
        4: {
            'time_limit': 30, 'temp_ideal_min': 69, 'temp_ideal_max': 71,
            'temp_decay_rate': 1.1, 'temp_fan_increment': 1.5, 'required_hits': 12,
            'target_width': 40, 'perfect_width': 15, 'hammer_speed': 5.5,
            'difficulty_points': 80
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
            'time_limit': 45, 'cylinder_count': 3, 'timing_window': 0.8,
            'rotation_speed': 1.0, 'allowed_failures': 2, 'multi_speed': False,
            'difficulty_points': 5, 'diversity_multiplier': 1.0
        },
        2: {
            'time_limit': 30, 'cylinder_count': 6, 'timing_window': 0.5,
            'rotation_speed': 1.3, 'allowed_failures': 1, 'multi_speed': False,
            'difficulty_points': 20, 'diversity_multiplier': 1.0
        },
        3: {
            'time_limit': 20, 'cylinder_count': 10, 'timing_window': 0.3,
            'rotation_speed': 1.6, 'allowed_failures': 0, 'multi_speed': False,
            'difficulty_points': 50, 'diversity_multiplier': 1.0
        },
        4: {
            'time_limit': 15, 'cylinder_count': 15, 'timing_window': 0.2,
            'rotation_speed': 2.0, 'allowed_failures': 0, 'multi_speed': True,
            'difficulty_points': 80, 'diversity_multiplier': 1.0
        },
    }
    return tier_configs.get(tier, tier_configs[1])


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_difficulty_description(points: float) -> str:
    """
    Get a human-readable difficulty description.

    Args:
        points: Difficulty points

    Returns:
        Description string (e.g., "Easy", "Moderate", "Hard", "Extreme")
    """
    if points < 10:
        return "Easy"
    elif points < 30:
        return "Moderate"
    elif points < 60:
        return "Hard"
    elif points < 90:
        return "Very Hard"
    else:
        return "Extreme"


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
        # Refining time = cylinders * ~3 seconds each
        return int(params['cylinder_count'] * 3)
    else:
        return 30  # Default estimate
