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
        'damage',           # Damage bonus (added to base damage)
        'attack_speed',     # Attack speed bonus (additive, e.g., +0.10 = 10% faster)
        'range',            # Range bonus (additive)
        'durability',       # Max durability bonus
        'quality',          # Crafting quality score (metadata)
    ],
    'armor': [
        'defense',          # Defense bonus (added to base defense)
        'durability',       # Max durability bonus
        'quality',          # Crafting quality score (metadata)
    ],
    'shield': [
        'defense',          # Defense bonus (same as armor)
        'block_chance',     # Block chance bonus (0.0-1.0, e.g., 0.05 = 5%)
        'durability',       # Max durability bonus
        'quality',          # Crafting quality score (metadata)
    ],
    'tool': [
        'efficiency',       # Tool efficiency multiplier (e.g., 1.2 = 20% faster)
        'durability',       # Max durability bonus
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

    # Base stats that all items get
    stats = {
        'durability': 100 + (tier * 20),  # T1: 100, T2: 120, T3: 140, T4: 160
        'quality': quality  # 0-100 based on performance
    }

    # Add type-specific stats
    if item_type == 'weapon':
        # Damage bonus scales with tier and quality
        base_damage = 25 + (tier * 10)  # T1: 25, T2: 35, T3: 45, T4: 55
        quality_mult = 1.0 + (quality / 100.0) * 0.5  # Up to +50% from quality
        stats['damage'] = int(base_damage * quality_mult)

        # Attack speed bonus from quality (0.0 to +0.20)
        stats['attack_speed'] = (quality / 100.0) * 0.20

    elif item_type in ['armor', 'shield']:
        # Defense bonus scales with tier and quality
        base_defense = 20 + (tier * 8)  # T1: 20, T2: 28, T3: 36, T4: 44
        quality_mult = 1.0 + (quality / 100.0) * 0.5  # Up to +50% from quality
        stats['defense'] = int(base_defense * quality_mult)

        # Shields get additional block chance
        if item_type == 'shield':
            # 5% base + up to 10% from quality
            stats['block_chance'] = 0.05 + (quality / 100.0) * 0.10

    elif item_type == 'tool':
        # Efficiency scales with tier and quality
        base_eff = 1.0 + (tier * 0.2)  # T1: 1.2, T2: 1.4, T3: 1.6, T4: 1.8
        quality_bonus = (quality / 100.0) * 0.3  # Up to +0.3
        stats['efficiency'] = base_eff + quality_bonus

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
        if stat_name == 'damage':
            # Damage: Calculate bonus over base damage
            if equipment.item_type == 'weapon' and hasattr(equipment, 'damage'):
                base_avg = sum(equipment.damage) / 2
                damage_bonus = stat_value - base_avg
                if damage_bonus > 0:
                    equipment.bonuses['damage'] = int(damage_bonus)
                    print(f"   ✨ Damage bonus: +{int(damage_bonus)}")

        elif stat_name == 'defense':
            # Defense: Calculate bonus over base defense
            if equipment.item_type in ['armor', 'shield'] and hasattr(equipment, 'defense'):
                defense_bonus = stat_value - equipment.defense
                if defense_bonus > 0:
                    equipment.bonuses['defense'] = int(defense_bonus)
                    print(f"   ✨ Defense bonus: +{int(defense_bonus)}")

        elif stat_name == 'attack_speed':
            # Attack speed: Direct additive bonus
            if equipment.item_type == 'weapon':
                equipment.bonuses['attack_speed'] = stat_value
                print(f"   ✨ Attack speed: +{stat_value:.2f}")

        elif stat_name == 'block_chance':
            # Block chance: Direct additive bonus
            if equipment.item_type == 'shield':
                equipment.bonuses['block_chance'] = stat_value
                print(f"   ✨ Block chance: +{stat_value*100:.1f}%")

        elif stat_name == 'durability':
            # Durability: Apply to max durability directly
            if stat_value > equipment.durability_max:
                equipment.durability_max = int(stat_value)
                equipment.durability_current = int(stat_value)
                print(f"   ✨ Max durability: {int(stat_value)}")

        elif stat_name == 'quality':
            # Quality: Store as metadata (doesn't affect combat stats)
            equipment.bonuses['quality'] = stat_value
            print(f"   ✨ Quality: {stat_value}/100")

        elif stat_name == 'efficiency':
            # Efficiency: Apply to tool efficiency directly
            if equipment.item_type == 'tool' and hasattr(equipment, 'efficiency'):
                equipment.efficiency = stat_value
                print(f"   ✨ Efficiency: {stat_value:.2f}x")

        elif stat_name == 'range':
            # Range: Direct additive bonus
            if equipment.item_type == 'weapon':
                if hasattr(equipment, 'range') and equipment.range > 0:
                    # Apply as bonus to existing range
                    range_bonus = stat_value - equipment.range
                    if range_bonus > 0:
                        equipment.bonuses['range'] = range_bonus
                        print(f"   ✨ Range bonus: +{range_bonus:.1f}")


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
