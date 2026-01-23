"""
Crafted Stats System

Handles generation and application of stats from crafting minigames.

Key Principles:
1. Stats are filtered by item type (weapon, armor, shield, tool)
2. Quality = earned_points / max_points ratio (0-100)
3. Stats apply to equipment.bonuses dict (NOT direct attributes)
4. No inappropriate stats (no defense on weapons, no damage on armor, etc.)
5. Modular and JSON-driven

Created: 2026-01-23
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass


# =============================================================================
# STAT TYPE DEFINITIONS
# =============================================================================

VALID_STATS_BY_TYPE = {
    'weapon': [
        'damage',           # Legacy damage bonus (deprecated)
        'damage_multiplier',  # Damage multiplier (-0.5 to +0.5, e.g., 0.25 = 25% more damage)
        'attack_speed',     # Attack speed bonus (additive, e.g., +0.10 = 10% faster)
        'range',            # Range bonus (additive)
        'durability_multiplier',  # Durability multiplier (-0.5 to +0.5, e.g., 0.25 = 25% more durability)
        'quality',          # Crafting quality score (metadata)
    ],
    'armor': [
        'defense',          # Legacy defense bonus (deprecated)
        'defense_multiplier',  # Defense multiplier (-0.5 to +0.5, e.g., 0.25 = 25% more defense)
        'durability_multiplier',  # Durability multiplier (-0.5 to +0.5, e.g., 0.25 = 25% more durability)
        'quality',          # Crafting quality score (metadata)
    ],
    'shield': [
        'defense',          # Legacy defense bonus (deprecated)
        'defense_multiplier',  # Defense multiplier (-0.5 to +0.5, e.g., 0.25 = 25% more defense)
        'block_chance',     # Block chance bonus (0.0-1.0, e.g., 0.05 = 5%)
        'durability_multiplier',  # Durability multiplier (-0.5 to +0.5, e.g., 0.25 = 25% more durability)
        'quality',          # Crafting quality score (metadata)
    ],
    'tool': [
        'efficiency',       # Tool efficiency multiplier (0.5 to 1.5, e.g., 1.2 = 20% faster)
        'durability_multiplier',  # Durability multiplier (-0.5 to +0.5, e.g., 0.25 = 25% more durability)
        'quality',          # Crafting quality score (metadata)
    ],
}


# =============================================================================
# STAT GENERATION
# =============================================================================

def generate_crafted_stats(
    minigame_result: Dict[str, Any],
    recipe: Dict[str, Any],
    item_type: str,
    slot: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate appropriate crafted stats based on minigame performance.

    Args:
        minigame_result: Result dict from minigame containing:
            - earned_points: Points earned in minigame
            - max_points: Maximum possible points
            - bonus: Legacy percentage bonus (deprecated)
            - success: Whether crafting succeeded
        recipe: Recipe dict with stationTier, etc.
        item_type: Type of item ('weapon', 'armor', 'shield', 'tool')
        slot: Equipment slot (e.g., 'mainHand', 'helmet') - optional

    Returns:
        Dict of stat_name: stat_value for this item type
    """
    # Calculate quality from points ratio
    earned = minigame_result.get('earned_points', 0)
    max_points = minigame_result.get('max_points', 100)
    quality = int((earned / max_points) * 100) if max_points > 0 else 50

    # Get tier for scaling
    tier = recipe.get('stationTier', 1)

    # Durability multiplier (0.5x to 1.5x based on quality)
    # quality 100 = +50%, quality 50 = 0%, quality 0 = -50%
    durability_multiplier = ((quality - 50) / 100.0)  # -0.5 to +0.5

    # Base stats
    stats = {
        'durability_multiplier': durability_multiplier,
        'quality': quality  # 0-100 based on performance
    }

    # Add type-specific stats
    if item_type == 'weapon':
        # Damage MULTIPLIER: quality determines % increase/decrease
        # quality 100 = +50%, quality 50 = +0%, quality 0 = -50%
        damage_mult = ((quality - 50) / 100.0)  # -0.5 to +0.5
        stats['damage_multiplier'] = damage_mult

        # Attack speed bonus from quality (0.0 to +0.20 or -0.20 to 0.0)
        if quality >= 50:
            stats['attack_speed'] = ((quality - 50) / 50.0) * 0.20  # 0 to +0.20
        else:
            stats['attack_speed'] = ((quality - 50) / 50.0) * 0.10  # -0.10 to 0

    elif item_type in ['armor', 'shield']:
        # Defense MULTIPLIER: quality determines % increase/decrease
        defense_mult = ((quality - 50) / 100.0)  # -0.5 to +0.5
        stats['defense_multiplier'] = defense_mult

        # Shields get additional block chance
        if item_type == 'shield':
            if quality >= 50:
                # 0% to +10% block chance
                stats['block_chance'] = ((quality - 50) / 50.0) * 0.10
            else:
                # -5% to 0% block chance
                stats['block_chance'] = ((quality - 50) / 50.0) * 0.05

    elif item_type == 'tool':
        # Efficiency MULTIPLIER: quality determines multiplier
        # quality 100 = 1.5x, quality 50 = 1.0x, quality 0 = 0.5x
        efficiency_mult = 0.5 + (quality / 100.0)  # 0.5 to 1.5
        stats['efficiency'] = efficiency_mult

    return stats


# =============================================================================
# STAT APPLICATION
# =============================================================================

def apply_crafted_stats_to_equipment(equipment, stats: Dict[str, Any]) -> None:
    """
    Apply crafted stats to equipment properly.

    Stats are applied to equipment.bonuses dict so character.recalculate_stats()
    can read them correctly.

    Args:
        equipment: EquipmentItem instance
        stats: Dict of stat_name: stat_value from generate_crafted_stats()
    """
    if not equipment or not stats:
        return

    # Get valid stats for this item type
    valid_stats = VALID_STATS_BY_TYPE.get(equipment.item_type, [])

    for stat_name, stat_value in stats.items():
        # Filter: only apply valid stats for this item type
        if stat_name not in valid_stats:
            print(f"   ⚠️ Skipping invalid stat '{stat_name}' for {equipment.item_type}")
            continue

        # Apply stat based on type
        if stat_name == 'damage_multiplier':
            # Damage multiplier: -0.5 to +0.5 (50% less to 50% more damage)
            if equipment.item_type == 'weapon':
                equipment.bonuses['damage_multiplier'] = stat_value
                sign = '+' if stat_value >= 0 else ''
                print(f"   ✨ Damage: {sign}{stat_value*100:.0f}%")

        elif stat_name == 'defense_multiplier':
            # Defense multiplier: -0.5 to +0.5 (50% less to 50% more defense)
            if equipment.item_type in ['armor', 'shield']:
                equipment.bonuses['defense_multiplier'] = stat_value
                sign = '+' if stat_value >= 0 else ''
                print(f"   ✨ Defense: {sign}{stat_value*100:.0f}%")

        elif stat_name == 'attack_speed':
            # Attack speed: Direct additive bonus (-0.10 to +0.20)
            if equipment.item_type == 'weapon':
                equipment.bonuses['attack_speed'] = stat_value
                sign = '+' if stat_value >= 0 else ''
                print(f"   ✨ Attack speed: {sign}{stat_value*100:.0f}%")

        elif stat_name == 'block_chance':
            # Block chance: Direct additive bonus (-0.05 to +0.10)
            if equipment.item_type == 'shield':
                equipment.bonuses['block_chance'] = stat_value
                sign = '+' if stat_value >= 0 else ''
                print(f"   ✨ Block chance: {sign}{stat_value*100:.1f}%")

        elif stat_name == 'durability_multiplier':
            # Durability multiplier: -0.5 to +0.5 (50% less to 50% more durability)
            if hasattr(equipment, 'durability_max'):
                old_max = equipment.durability_max
                # Apply multiplier: durability_max *= (1.0 + multiplier)
                new_max = int(old_max * (1.0 + stat_value))
                # Set both current and max (fresh craft)
                equipment.durability_current = new_max
                equipment.durability_max = new_max
                sign = '+' if stat_value >= 0 else ''
                print(f"   ✨ Max durability: {sign}{stat_value*100:.0f}% (new max: {new_max} from {old_max})")

        elif stat_name == 'quality':
            # Quality: Store as metadata (doesn't affect combat stats)
            equipment.bonuses['quality'] = stat_value
            print(f"   ✨ Quality: {stat_value}/100")

        elif stat_name == 'efficiency':
            # Efficiency: Set tool efficiency multiplier (0.5 to 1.5)
            if equipment.item_type == 'tool' and hasattr(equipment, 'efficiency'):
                equipment.efficiency = stat_value
                print(f"   ✨ Efficiency: {stat_value:.2f}x")

        elif stat_name == 'range':
            # Range: Direct additive bonus
            if equipment.item_type == 'weapon':
                if hasattr(equipment, 'range') and equipment.range > 0:
                    # Apply as bonus to existing range
                    range_bonus = stat_value - equipment.range
                    equipment.bonuses['range'] = range_bonus
                    sign = '+' if range_bonus >= 0 else ''
                    print(f"   ✨ Range: {sign}{range_bonus:.1f}")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_item_type_from_slot(slot: str) -> str:
    """
    Determine item type from equipment slot.

    Args:
        slot: Equipment slot name ('mainHand', 'offHand', 'helmet', etc.)

    Returns:
        Item type string ('weapon', 'armor', 'shield', 'tool')
    """
    if slot in ['mainHand', 'offHand']:
        return 'weapon'  # May be weapon, shield, or tool - caller should check actual item
    elif slot in ['helmet', 'chestplate', 'leggings', 'boots']:
        return 'armor'
    else:
        return 'weapon'  # Default fallback


def get_stat_display_name(stat_name: str) -> str:
    """
    Get human-readable display name for stat.

    Args:
        stat_name: Internal stat name ('attack_speed', 'block_chance', etc.)

    Returns:
        Display name ('Attack Speed', 'Block Chance', etc.)
    """
    display_names = {
        'damage': 'Damage',
        'defense': 'Defense',
        'attack_speed': 'Attack Speed',
        'block_chance': 'Block Chance',
        'durability': 'Durability',
        'quality': 'Quality',
        'efficiency': 'Efficiency',
        'range': 'Range',
    }
    return display_names.get(stat_name, stat_name.replace('_', ' ').title())


def format_stat_value(stat_name: str, stat_value: Any) -> str:
    """
    Format stat value for display.

    Args:
        stat_name: Internal stat name
        stat_value: Stat value (int, float, etc.)

    Returns:
        Formatted string ('+10', '+15%', '95/100', etc.)
    """
    if stat_name == 'quality':
        return f"{stat_value}/100"
    elif stat_name in ['attack_speed', 'block_chance']:
        # Percentage display
        return f"+{stat_value*100:.1f}%"
    elif stat_name == 'efficiency':
        # Multiplier display
        return f"{stat_value:.2f}x"
    elif isinstance(stat_value, float):
        return f"+{stat_value:.1f}"
    else:
        return f"+{stat_value}"
