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
# Adjusted based on actual recipe difficulty distribution analysis:
# - Most recipes fall in 1-20 point range
# - Engineering has widest spread (6-85 pts)
# - Need lower thresholds for meaningful difficulty progression
DIFFICULTY_THRESHOLDS = {
    'common': (0, 4),       # Basic single-material recipes (bottom ~20%)
    'uncommon': (5, 10),    # Multi-material or T2 recipes (next ~25%)
    'rare': (11, 20),       # Complex T2/T3 recipes (next ~30%)
    'epic': (21, 40),       # High-tier multi-material (next ~20%)
    'legendary': (41, 150), # Extreme T4 complex recipes (top ~5%)
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

    # Temperature ideal range: wide at low difficulty, VERY narrow at high (min 3°C)
    'temp_ideal_range': (25, 3),  # Degrees of acceptable range

    # Temperature decay rate per 100ms tick
    # Easy (0.3): 3°/sec decay, with FAN=4 need ~0.75 clicks/sec to maintain
    # Hard (0.6): 6°/sec decay, with FAN=1.5 need ~4 clicks/sec to maintain
    # This parameter is used by smithing.py update() and modified by INT stat
    'temp_decay_rate': (0.3, 0.6),

    # Fan increment: big boost at low difficulty, small at high
    'temp_fan_increment': (4, 1.5),

    # Required hammer hits
    'required_hits': (3, 12),

    # Target zone width (pixels) - where 70+ score is achieved
    # Note: This is now less important as scoring uses binned system
    'target_width': (100, 30),

    # Perfect zone width (pixels) - where 100 score is achieved
    # Note: This is now less important as scoring uses binned system
    'perfect_width': (50, 10),

    # Hammer oscillation speed (pixels/frame) - higher = faster = harder to time
    # Updated: ~50% faster average, ~2x max speed
    # Easy: 3.0 (was 2.0), Hard: 14.0 (was 7.0)
    'hammer_speed': (3.0, 14.0),
}


# =============================================================================
# REFINING PARAMETERS - Lock/Tumbler minigame (BALANCED DIFFICULTY)
# =============================================================================

REFINING_PARAMS = {
    # Time limit: reasonable at low, tight at high
    'time_limit': (45, 15),

    # Cylinder count: few at low, MANY at high (can go past 3!)
    'cylinder_count': (3, 12),

    # Timing window in SECONDS - SHRUNK by 2/3 (much tighter passable range!)
    # Now: 0.05s at easy (very precise), 0.01s at hard (extremely precise)
    # This is 1/3 of previous values (2/3 shrink), making acceptable window much smaller
    'timing_window': (0.05, 0.01),

    # Rotation speed: REDUCED to 2/3 of previous (ensures UI sync, no lag)
    # Now: 1.0 at low (moderate), 4.0 at high (fast but smooth)
    # This is 2/3 of the 1.5-6.0 range, ensuring graphics stay perfectly synced
    'rotation_speed': (1.0, 4.0),

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
    Calculate refining difficulty based on material points × station tier × diversity.

    Refining uses station tier as a key multiplier since:
    - Higher tier stations = more complex refining processes
    - Single materials are common, so tier matters more

    Args:
        recipe: Full recipe dictionary with 'inputs' list

    Returns:
        Dict with all refining parameters plus 'difficulty_points'
    """
    inputs = recipe.get('inputs', [])

    # Calculate base points with diversity
    base_points = calculate_material_points(inputs)
    diversity_mult = calculate_diversity_multiplier(inputs)

    # Station tier multiplier (T1=1.5x, T2=2.5x, T3=3.5x, T4=4.5x)
    station_tier = recipe.get('stationTierRequired', recipe.get('stationTier', 1))
    station_mult = 1.0 + (station_tier * 0.5)

    total_points = base_points * diversity_mult * station_mult

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
    params['station_multiplier'] = station_mult
    params['tier_fallback'] = recipe.get('stationTier', 1)

    return params


# =============================================================================
# ALCHEMY PARAMETERS - Reaction chain minigame
# =============================================================================

ALCHEMY_PARAMS = {
    # Time limit per reaction stage
    'time_limit': (60, 20),

    # Reaction count (ingredients to chain)
    'reaction_count': (2, 6),

    # Sweet spot duration (seconds) - when to chain
    'sweet_spot_duration': (2.0, 0.4),

    # Base stage duration (seconds)
    'stage_duration': (2.5, 0.8),

    # False peak count (visual distractions)
    'false_peaks': (0, 5),

    # Volatility modifier (affects timing unpredictability)
    'volatility': (0.0, 1.0),
}


def calculate_alchemy_difficulty(recipe: Dict) -> Dict:
    """
    Calculate alchemy difficulty based on material points × diversity × volatility.

    Alchemy-specific modifiers:
    - Vowel-based volatility: Materials with vowel-heavy names are more volatile
    - Tier exponential: 1.2^avg_tier modifier

    Args:
        recipe: Full recipe dictionary with 'inputs' list

    Returns:
        Dict with all alchemy parameters plus 'difficulty_points'
    """
    inputs = recipe.get('inputs', [])

    # Calculate base points with diversity
    base_points = calculate_material_points(inputs)
    diversity_mult = calculate_diversity_multiplier(inputs)
    avg_tier = calculate_average_tier(inputs)

    # Alchemy tier exponential modifier
    tier_modifier = 1.2 ** (avg_tier - 1)

    # Calculate volatility from material names (vowel ratio)
    volatility = _calculate_volatility(inputs)

    # Total difficulty with alchemy modifiers
    total_points = base_points * diversity_mult * tier_modifier * (1 + volatility * 0.3)

    # Interpolate parameters
    params = interpolate_difficulty(total_points, ALCHEMY_PARAMS)

    # Round integer parameters
    params['reaction_count'] = max(2, int(round(params['reaction_count'])))
    params['false_peaks'] = max(0, int(round(params['false_peaks'])))
    params['time_limit'] = int(round(params['time_limit']))

    # Add metadata
    params['difficulty_points'] = total_points
    params['difficulty_tier'] = get_difficulty_tier(total_points)
    params['diversity_multiplier'] = diversity_mult
    params['tier_modifier'] = tier_modifier
    params['volatility'] = volatility
    params['avg_tier'] = avg_tier
    params['tier_fallback'] = recipe.get('stationTier', 1)

    return params


def _calculate_volatility(inputs: List[Dict]) -> float:
    """
    Calculate volatility based on vowel ratio in material names.

    More vowels = more volatile/unpredictable reactions.

    Returns:
        Volatility score 0.0 to 1.0
    """
    if not inputs:
        return 0.0

    vowels = set('aeiouAEIOU')
    total_chars = 0
    vowel_count = 0

    for inp in inputs:
        material_id = inp.get('materialId', inp.get('itemId', ''))
        for char in material_id:
            if char.isalpha():
                total_chars += 1
                if char in vowels:
                    vowel_count += 1

    if total_chars == 0:
        return 0.0

    # Normal vowel ratio is ~40%, so normalize around that
    vowel_ratio = vowel_count / total_chars
    volatility = max(0.0, min(1.0, (vowel_ratio - 0.3) * 2.5))
    return volatility


# =============================================================================
# ENGINEERING PARAMETERS - Puzzle minigame
# =============================================================================

ENGINEERING_PARAMS = {
    # Time limit (generous since it's puzzle-based, no failure)
    'time_limit': (300, 120),  # 5 min to 2 min (more generous)

    # Puzzle count per device - REDUCED for faster completion
    # Base: 1 puzzle, Max: 2 puzzles (was 1-4)
    'puzzle_count': (1, 2),

    # Grid size for puzzles - REDUCED for easier solving
    # 3x3 is easy, 4x4 is hard (was 3-6)
    'grid_size': (3, 4),

    # Puzzle complexity (affects piece types available)
    # Lower range for easier base puzzles
    'complexity': (1, 3),

    # Hint count allowed - MORE hints for accessibility
    'hints_allowed': (4, 1),

    # Ideal moves for logic switch puzzle (6-8 range)
    # Lower = easier puzzle, higher = more complex
    'ideal_moves': (6, 8),
}

# 12-tier thresholds for engineering ideal_moves distribution
# Maps difficulty_points ranges to ideal_moves (6, 7, or 8)
# Based on actual recipe distribution analysis:
#   6 moves: 5 recipes (6.6 - 22.6 pts)
#   7 moves: 5 recipes (31.9 - 55.8 pts)
#   8 moves: 6 recipes (62.4 - 122.2 pts)
ENGINEERING_IDEAL_MOVES_TIERS = [
    # (max_difficulty_points, ideal_moves)
    (8, 6),    # Tier 1: simple_bomb (6.6) - 6 moves
    (13, 6),   # Tier 2: spike_trap (12.0) - 6 moves
    (18, 6),   # Tier 3: frost_mine (17.8) - 6 moves
    (23, 6),   # Tier 4: basic_arrow_turret (21.8), fire_bomb (22.6) - 6 moves
    (35, 7),   # Tier 5: bear_trap (31.9) - 7 moves
    (44, 7),   # Tier 6: fire_arrow_turret (42.8) - 7 moves
    (50, 7),   # Tier 7: grappling_hook (44.6) - 7 moves
    (56, 7),   # Tier 8: healing_beacon (55.8), emp_device (55.8) - 7 moves
    (68, 8),   # Tier 9: cluster_bomb (62.4), net_launcher (67.2) - 8 moves
    (76, 8),   # Tier 10: lightning_cannon (71.4), flamethrower (75.2) - 8 moves
    (100, 8),  # Tier 11: laser_turret (93.6) - 8 moves
    (999, 8),  # Tier 12: jetpack (122.2) - 8 moves
]


def get_engineering_ideal_moves(difficulty_points: float) -> int:
    """
    Get ideal moves for logic switch puzzle based on 12-tier difficulty system.

    Maps difficulty_points to ideal_moves (6, 7, or 8) using tiered thresholds
    for roughly equal distribution across existing recipes.

    Args:
        difficulty_points: Calculated difficulty points

    Returns:
        Ideal moves (6, 7, or 8)
    """
    for max_pts, ideal_moves in ENGINEERING_IDEAL_MOVES_TIERS:
        if difficulty_points <= max_pts:
            return ideal_moves
    return 8  # Default to max if above all tiers


def calculate_engineering_difficulty(recipe: Dict) -> Dict:
    """
    Calculate engineering difficulty based on slot count × diversity.

    Engineering uses puzzle-based minigames where:
    - More materials = more puzzles
    - Higher tier = larger/harder puzzles

    Args:
        recipe: Full recipe dictionary with 'inputs' list

    Returns:
        Dict with all engineering parameters plus 'difficulty_points'
    """
    inputs = recipe.get('inputs', [])

    # Calculate base points with diversity
    base_points = calculate_material_points(inputs)
    diversity_mult = calculate_diversity_multiplier(inputs)

    # Count total slots used (sum of quantities)
    total_slots = sum(inp.get('quantity', 1) for inp in inputs)

    # Engineering modifier: slot count matters more
    slot_modifier = 1.0 + (total_slots - 1) * 0.05

    total_points = base_points * diversity_mult * slot_modifier

    # Interpolate parameters
    params = interpolate_difficulty(total_points, ENGINEERING_PARAMS)

    # Round integer parameters
    params['puzzle_count'] = max(1, int(round(params['puzzle_count'])))
    params['grid_size'] = max(3, int(round(params['grid_size'])))
    params['complexity'] = max(1, min(4, int(round(params['complexity']))))
    params['hints_allowed'] = max(0, int(round(params['hints_allowed'])))
    params['time_limit'] = int(round(params['time_limit']))

    # Calculate ideal_moves using 12-tier system (6-8 range)
    params['ideal_moves'] = get_engineering_ideal_moves(total_points)

    # Add metadata
    params['difficulty_points'] = total_points
    params['difficulty_tier'] = get_difficulty_tier(total_points)
    params['diversity_multiplier'] = diversity_mult
    params['slot_modifier'] = slot_modifier
    params['total_slots'] = total_slots
    params['tier_fallback'] = recipe.get('stationTier', 1)

    return params


# =============================================================================
# ENCHANTING PARAMETERS - Wheel spin minigame
# =============================================================================

ENCHANTING_PARAMS = {
    # Starting currency
    'starting_currency': (100, 100),  # Always starts at 100

    # Green slice count (favorable outcomes)
    'green_slices': (12, 6),  # More green at easy, less at hard

    # Red slice count (unfavorable outcomes)
    'red_slices': (3, 10),  # Less red at easy, more at hard

    # Green multiplier
    'green_multiplier': (1.5, 1.2),  # Better payoff at easy

    # Red multiplier (loss)
    'red_multiplier': (0.8, 0.0),  # Less punishing at easy

    # Spin count
    'spin_count': (3, 3),  # Always 3 spins
}


def calculate_enchanting_difficulty(recipe: Dict) -> Dict:
    """
    Calculate enchanting difficulty for wheel spin minigame.

    Higher difficulty = worse odds on the wheel.

    Args:
        recipe: Full recipe dictionary with 'inputs' list

    Returns:
        Dict with all enchanting parameters plus 'difficulty_points'
    """
    inputs = recipe.get('inputs', [])

    # Calculate base points (enchanting uses materials too)
    base_points = calculate_material_points(inputs)
    diversity_mult = calculate_diversity_multiplier(inputs)

    total_points = base_points * diversity_mult

    # Interpolate parameters
    params = interpolate_difficulty(total_points, ENCHANTING_PARAMS)

    # Round slice counts (must total 20)
    green = max(4, min(14, int(round(params['green_slices']))))
    red = max(2, min(12, int(round(params['red_slices']))))

    # Ensure total is 20
    grey = 20 - green - red
    if grey < 2:
        # Adjust to ensure at least 2 grey
        excess = 2 - grey
        if green > red:
            green -= excess
        else:
            red -= excess
        grey = 2

    params['green_slices'] = green
    params['red_slices'] = red
    params['grey_slices'] = grey
    params['spin_count'] = 3

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
