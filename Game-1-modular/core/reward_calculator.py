"""
Reward Calculator Module

Centralized reward calculation for crafting minigames that scales with difficulty.
Harder recipes unlock higher potential rewards.

Core Principle:
    Reward Potential = f(difficulty, performance)
    - Higher difficulty = higher maximum achievable bonus
    - Better performance = closer to that maximum
    - First-try bonus feeds into performance calculation
"""

from typing import Dict, Tuple, Optional


# =============================================================================
# CONSTANTS
# =============================================================================

# Difficulty scaling ranges (for max reward calculation)
# Aligned with linear tier system: T1=1, T2=2, T3=3, T4=4
DIFFICULTY_RANGES = {
    'min_points': 1.0,    # Single T1 material
    'max_points': 80.0,   # Adjusted for linear scaling (e.g., 20x T4 materials)
}

# Reward multiplier range
REWARD_MULTIPLIER = {
    'min': 1.0,   # At minimum difficulty
    'max': 2.5,   # At maximum difficulty
}

# Quality tier thresholds (performance_score: tier_name)
QUALITY_TIERS = [
    (0.00, 0.25, 'Normal'),
    (0.25, 0.50, 'Fine'),
    (0.50, 0.75, 'Superior'),
    (0.75, 0.90, 'Masterwork'),
    (0.90, 1.01, 'Legendary'),  # 1.01 to include 1.0 exactly
]

# Failure penalty scaling (difficulty-based)
FAILURE_PENALTY = {
    'min_loss': 0.30,  # 30% loss at minimum difficulty
    'max_loss': 0.90,  # 90% loss at maximum difficulty
}

# First-try bonus
FIRST_TRY_BONUS = {
    'performance_boost': 0.10,  # +10% performance on first try
    'eligible_threshold': 0.50,  # Must achieve 50%+ to qualify for special attributes
}


# =============================================================================
# CORE REWARD FUNCTIONS
# =============================================================================

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
    min_pts = DIFFICULTY_RANGES['min_points']
    max_pts = DIFFICULTY_RANGES['max_points']

    # Normalize to 0-1
    normalized = max(0.0, min(1.0, (difficulty_points - min_pts) / (max_pts - min_pts)))

    # Calculate multiplier
    mult_range = REWARD_MULTIPLIER['max'] - REWARD_MULTIPLIER['min']
    return REWARD_MULTIPLIER['min'] + (normalized * mult_range)


def get_quality_tier(performance_score: float) -> str:
    """
    Map performance score (0-1) to quality tier name.

    Args:
        performance_score: Normalized performance (0.0 to 1.0)

    Returns:
        Quality tier name ('Normal', 'Fine', 'Superior', 'Masterwork', 'Legendary')
    """
    for min_score, max_score, tier_name in QUALITY_TIERS:
        if min_score <= performance_score < max_score:
            return tier_name
    return 'Legendary'  # Fallback for 1.0 exactly


def calculate_bonus_pct(performance_score: float, max_multiplier: float) -> int:
    """
    Calculate percentage bonus for crafted item stats.

    Formula: performance_score * (max_multiplier - 1) * 20

    At max difficulty (2.5x multiplier):
    - 50% performance = 15% bonus
    - 100% performance = 30% bonus

    At min difficulty (1.0x multiplier):
    - Any performance = 0% bonus (base stats only)

    Args:
        performance_score: Normalized performance (0.0 to 1.0)
        max_multiplier: From calculate_max_reward_multiplier()

    Returns:
        Percentage bonus (0 to ~30)
    """
    return int(performance_score * (max_multiplier - 1.0) * 20)


def calculate_stat_multiplier(performance_score: float, max_multiplier: float) -> float:
    """
    Calculate stat multiplier for crafted item.

    Similar to bonus_pct but as a multiplier (1.0 + bonus).

    Args:
        performance_score: Normalized performance (0.0 to 1.0)
        max_multiplier: From calculate_max_reward_multiplier()

    Returns:
        Stat multiplier (1.0 to ~1.3)
    """
    bonus_pct = calculate_bonus_pct(performance_score, max_multiplier)
    return 1.0 + (bonus_pct / 100.0)


# =============================================================================
# DISCIPLINE-SPECIFIC REWARD FUNCTIONS
# =============================================================================

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
            'stat_multiplier': float,
            'quality_tier': str,
            'bonus_pct': int,
            'first_try_eligible': bool,
            'first_try_bonus_applied': bool
        }
    """
    # Calculate max possible reward for this difficulty
    max_multiplier = calculate_max_reward_multiplier(difficulty_points)

    # Calculate base performance score (0-1)
    avg_score = performance.get('avg_hammer_score', 0)
    temp_bonus = 1.2 if performance.get('temp_in_ideal', False) else 1.0

    # Max possible score: 100 * 1.2 = 120
    base_performance = min(1.0, (avg_score * temp_bonus) / 120)

    # Apply first-try bonus
    attempt = performance.get('attempt', 1)
    first_try_bonus_applied = False
    if attempt == 1:
        base_performance = min(1.0, base_performance + FIRST_TRY_BONUS['performance_boost'])
        first_try_bonus_applied = True

    # Calculate rewards
    bonus_pct = calculate_bonus_pct(base_performance, max_multiplier)
    stat_mult = calculate_stat_multiplier(base_performance, max_multiplier)
    quality_tier = get_quality_tier(base_performance)

    # First-try eligible for special attributes if performance is high enough
    first_try_eligible = (
        attempt == 1 and
        base_performance >= FIRST_TRY_BONUS['eligible_threshold']
    )

    return {
        'stat_multiplier': stat_mult,
        'quality_tier': quality_tier,
        'bonus_pct': bonus_pct,
        'performance_score': base_performance,
        'max_multiplier': max_multiplier,
        'first_try_eligible': first_try_eligible,
        'first_try_bonus_applied': first_try_bonus_applied,
    }


def calculate_refining_rewards(
    difficulty_points: float,
    success: bool,
    input_quantity: int = 1
) -> Dict:
    """
    Calculate refining rewards.

    Refining uses rarity upgrade based on difficulty + input quantity.
    Higher difficulty = higher potential upgrade.

    Args:
        difficulty_points: Total recipe difficulty
        success: Whether minigame succeeded
        input_quantity: Total input material quantity

    Returns:
        {
            'success': bool,
            'max_rarity_upgrade': int,
            'quality_multiplier': float,
            'material_loss': float (if failed)
        }
    """
    if not success:
        material_loss = calculate_failure_penalty(difficulty_points)
        return {
            'success': False,
            'max_rarity_upgrade': 0,
            'quality_multiplier': 1.0,
            'material_loss': material_loss,
        }

    # Calculate max possible reward for this difficulty
    max_multiplier = calculate_max_reward_multiplier(difficulty_points)

    # Rarity upgrade tiers based on difficulty
    # Easy: max +1 tier, Hard: max +4 tiers
    # But also limited by input quantity (4:1 ratio per tier)
    difficulty_based_max = int(1 + (max_multiplier - 1.0) * 2)

    # Input-based limit (same as current system)
    if input_quantity >= 256:
        quantity_based_max = 4
    elif input_quantity >= 64:
        quantity_based_max = 3
    elif input_quantity >= 16:
        quantity_based_max = 2
    elif input_quantity >= 4:
        quantity_based_max = 1
    else:
        quantity_based_max = 0

    # Take the minimum of both limits
    max_rarity_upgrade = min(difficulty_based_max, quantity_based_max)

    return {
        'success': True,
        'max_rarity_upgrade': max_rarity_upgrade,
        'quality_multiplier': max_multiplier,
        'material_loss': 0.0,
    }


def calculate_alchemy_rewards(
    difficulty_points: float,
    performance: Dict
) -> Dict:
    """
    Calculate alchemy rewards based on reaction chain performance.

    Args:
        difficulty_points: Total recipe difficulty
        performance: {
            'chains_completed': int,
            'total_chains': int,
            'avg_timing_score': 0-100,
            'explosions': int,
            'attempt': int
        }

    Returns:
        {
            'potency_multiplier': float,
            'quality_tier': str,
            'bonus_pct': int,
            'duration_multiplier': float (for timed effects)
        }
    """
    max_multiplier = calculate_max_reward_multiplier(difficulty_points)

    # Calculate base performance
    chains = performance.get('chains_completed', 0)
    total = performance.get('total_chains', 1)
    timing = performance.get('avg_timing_score', 50)
    explosions = performance.get('explosions', 0)
    attempt = performance.get('attempt', 1)

    # Chain completion ratio
    chain_score = chains / max(1, total)

    # Timing precision
    timing_score = timing / 100

    # Explosion penalty
    explosion_penalty = explosions * 0.15

    # Base performance
    base_performance = (chain_score * 0.6 + timing_score * 0.4) - explosion_penalty
    base_performance = max(0.0, min(1.0, base_performance))

    # First-try bonus
    first_try_applied = False
    if attempt == 1:
        base_performance = min(1.0, base_performance + FIRST_TRY_BONUS['performance_boost'])
        first_try_applied = True

    bonus_pct = calculate_bonus_pct(base_performance, max_multiplier)
    quality_tier = get_quality_tier(base_performance)

    # Potency and duration scale with performance
    # performance 1.0 = max bonus, 0.5 = neutral (100%), 0.0 = penalty
    # Allows negative stats for poor performance
    potency_mult = 1.0 + (base_performance - 0.5) * (max_multiplier - 1.0)
    duration_mult = 1.0 + (base_performance - 0.5) * (max_multiplier - 1.0) * 0.6

    # Clamp to reasonable bounds (25% to 200%)
    potency_mult = max(0.25, min(2.0, potency_mult))
    duration_mult = max(0.25, min(2.0, duration_mult))

    return {
        'potency_multiplier': potency_mult,
        'duration_multiplier': duration_mult,
        'quality_tier': quality_tier,
        'bonus_pct': bonus_pct,
        'performance_score': base_performance,
        'max_multiplier': max_multiplier,
        'first_try_bonus_applied': first_try_applied,
    }


def calculate_engineering_rewards(
    difficulty_points: float,
    performance: Dict
) -> Dict:
    """
    Calculate engineering rewards based on puzzle completion.

    Args:
        difficulty_points: Total recipe difficulty
        performance: {
            'puzzles_solved': int,
            'total_puzzles': int,
            'hints_used': int,
            'time_remaining': float (fraction of time left),
            'attempt': int
        }

    Returns:
        {
            'efficiency_multiplier': float,
            'quality_tier': str,
            'bonus_pct': int,
            'durability_bonus': int
        }
    """
    max_multiplier = calculate_max_reward_multiplier(difficulty_points)

    solved = performance.get('puzzles_solved', 0)
    total = performance.get('total_puzzles', 1)
    hints = performance.get('hints_used', 0)
    time_remaining = performance.get('time_remaining', 0.5)
    attempt = performance.get('attempt', 1)

    # Puzzle completion is primary
    completion_score = solved / max(1, total)

    # Time bonus for finishing early
    time_bonus = time_remaining * 0.2

    # Hint penalty
    hint_penalty = hints * 0.1

    base_performance = completion_score + time_bonus - hint_penalty
    base_performance = max(0.0, min(1.0, base_performance))

    # First-try bonus
    first_try_applied = False
    if attempt == 1:
        base_performance = min(1.0, base_performance + FIRST_TRY_BONUS['performance_boost'])
        first_try_applied = True

    bonus_pct = calculate_bonus_pct(base_performance, max_multiplier)
    quality_tier = get_quality_tier(base_performance)

    # Engineering devices get efficiency and durability bonuses
    efficiency_mult = 1.0 + (base_performance * (max_multiplier - 1.0) * 0.4)
    durability_bonus = int(base_performance * 50)  # Up to +50 durability

    return {
        'efficiency_multiplier': efficiency_mult,
        'durability_bonus': durability_bonus,
        'quality_tier': quality_tier,
        'bonus_pct': bonus_pct,
        'performance_score': base_performance,
        'max_multiplier': max_multiplier,
        'first_try_bonus_applied': first_try_applied,
    }


def calculate_enchanting_rewards(
    difficulty_points: float,
    performance: Dict
) -> Dict:
    """
    Calculate enchanting rewards based on wheel spin outcomes.

    Args:
        difficulty_points: Total recipe difficulty
        performance: {
            'final_currency': int (out of starting 100),
            'spins_completed': int,
            'green_hits': int,
            'red_hits': int
        }

    Returns:
        {
            'efficacy_multiplier': float (affects enchantment strength),
            'quality_tier': str,
            'bonus_pct': int
        }
    """
    max_multiplier = calculate_max_reward_multiplier(difficulty_points)

    final_currency = performance.get('final_currency', 100)
    starting = 100

    # Currency difference determines efficacy
    # +100 = +50% efficacy, -100 = -50% efficacy
    currency_diff = final_currency - starting
    efficacy_modifier = currency_diff / 200  # -0.5 to +0.5

    # Performance score based on final currency
    # 0 currency = 0%, 100 = 50%, 200 = 100%
    base_performance = min(1.0, max(0.0, final_currency / 200))

    bonus_pct = calculate_bonus_pct(base_performance, max_multiplier)
    quality_tier = get_quality_tier(base_performance)

    # Efficacy multiplier affects enchantment power
    efficacy_mult = 1.0 + efficacy_modifier

    return {
        'efficacy_multiplier': efficacy_mult,
        'quality_tier': quality_tier,
        'bonus_pct': bonus_pct,
        'performance_score': base_performance,
        'max_multiplier': max_multiplier,
        'currency_change': currency_diff,
    }


# =============================================================================
# FAILURE PENALTY CALCULATION
# =============================================================================

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
    min_pts = DIFFICULTY_RANGES['min_points']
    max_pts = DIFFICULTY_RANGES['max_points']

    # Normalize to 0-1
    normalized = max(0.0, min(1.0, (difficulty_points - min_pts) / (max_pts - min_pts)))

    # Calculate loss
    loss_range = FAILURE_PENALTY['max_loss'] - FAILURE_PENALTY['min_loss']
    return FAILURE_PENALTY['min_loss'] + (normalized * loss_range)


def calculate_material_loss(
    inputs: list,
    difficulty_points: float
) -> Dict[str, int]:
    """
    Calculate specific material quantities lost on failure.

    Args:
        inputs: List of {'materialId': str, 'quantity': int}
        difficulty_points: Recipe difficulty

    Returns:
        Dict of {material_id: quantity_lost}
    """
    loss_fraction = calculate_failure_penalty(difficulty_points)

    losses = {}
    for inp in inputs:
        material_id = inp.get('materialId', inp.get('itemId', ''))
        quantity = inp.get('quantity', 1)
        lost = int(quantity * loss_fraction)
        if lost > 0:
            losses[material_id] = lost

    return losses


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_reward_description(bonus_pct: int, quality_tier: str) -> str:
    """
    Get a human-readable reward description.

    Args:
        bonus_pct: Percentage bonus achieved
        quality_tier: Quality tier name

    Returns:
        Description string
    """
    if bonus_pct == 0:
        return f"{quality_tier} quality (base stats)"
    else:
        return f"{quality_tier} quality (+{bonus_pct}% bonus)"


def estimate_reward_potential(difficulty_points: float) -> Dict:
    """
    Estimate potential rewards for a given difficulty.

    Useful for showing players what they can achieve.

    Args:
        difficulty_points: Recipe difficulty

    Returns:
        Dict with potential rewards at different performance levels
    """
    max_mult = calculate_max_reward_multiplier(difficulty_points)

    return {
        'max_multiplier': max_mult,
        'at_50_percent': {
            'bonus_pct': calculate_bonus_pct(0.5, max_mult),
            'quality': get_quality_tier(0.5),
        },
        'at_75_percent': {
            'bonus_pct': calculate_bonus_pct(0.75, max_mult),
            'quality': get_quality_tier(0.75),
        },
        'at_100_percent': {
            'bonus_pct': calculate_bonus_pct(1.0, max_mult),
            'quality': get_quality_tier(1.0),
        },
        'failure_penalty': calculate_failure_penalty(difficulty_points),
    }


def format_rewards_for_display(rewards: Dict) -> str:
    """
    Format rewards dict for console/UI display.

    Args:
        rewards: Result from calculate_smithing_rewards or similar

    Returns:
        Formatted string
    """
    lines = []

    if rewards.get('success', True):
        lines.append(f"Quality: {rewards.get('quality_tier', 'Unknown')}")
        lines.append(f"Bonus: +{rewards.get('bonus_pct', 0)}%")
        lines.append(f"Stat Multiplier: {rewards.get('stat_multiplier', 1.0):.2f}x")

        if rewards.get('first_try_bonus_applied'):
            lines.append("First-try bonus applied!")

        if rewards.get('first_try_eligible'):
            lines.append("Eligible for special attributes!")
    else:
        loss = rewards.get('material_loss', 0.5)
        lines.append(f"FAILED - {int(loss * 100)}% materials lost")

    return "\n".join(lines)
