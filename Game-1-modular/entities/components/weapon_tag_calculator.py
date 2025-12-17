"""Weapon tag modifier calculator

This module provides centralized logic for converting weapon metadata tags
into combat bonuses. Tags like '2H', 'fast', 'precision', 'reach', etc. are
read from weapon JSON definitions and translated into mechanical effects.

Tag Categories:
- Hand Requirement: 2H, 1H, versatile → Damage modifiers
- Combat Properties: fast, precision, reach, crushing, armor_breaker, cleaving → Various bonuses
"""

from typing import List


class WeaponTagModifiers:
    """Calculate combat bonuses from weapon metadata tags"""

    @staticmethod
    def get_damage_multiplier(tags: List[str], has_offhand: bool = False) -> float:
        """Calculate damage multiplier from hand requirement tags

        Args:
            tags: List of weapon metadata tags
            has_offhand: Whether player has offhand item equipped

        Returns:
            float: Damage multiplier (1.0 = no bonus, 1.2 = +20%)
        """
        multiplier = 1.0

        # Hand requirement bonuses
        if "2H" in tags:
            multiplier *= 1.2  # +20% damage for two-handed weapons
        elif "versatile" in tags and not has_offhand:
            multiplier *= 1.1  # +10% if using versatile weapon without offhand

        return multiplier

    @staticmethod
    def get_attack_speed_bonus(tags: List[str]) -> float:
        """Calculate attack speed bonus from tags

        Args:
            tags: List of weapon metadata tags

        Returns:
            float: Attack speed bonus (0.15 = +15% attack speed)
        """
        bonus = 0.0

        if "fast" in tags:
            bonus += 0.15  # +15% attack speed for fast weapons

        return bonus

    @staticmethod
    def get_crit_chance_bonus(tags: List[str]) -> float:
        """Calculate critical hit chance bonus from tags

        Args:
            tags: List of weapon metadata tags

        Returns:
            float: Crit chance bonus (0.10 = +10% crit chance)
        """
        bonus = 0.0

        if "precision" in tags:
            bonus += 0.10  # +10% crit chance for precision weapons

        return bonus

    @staticmethod
    def get_range_bonus(tags: List[str]) -> float:
        """Calculate attack range bonus from tags

        Args:
            tags: List of weapon metadata tags

        Returns:
            float: Range bonus in units (1.0 = +1 unit)
        """
        bonus = 0.0

        if "reach" in tags:
            bonus += 1.0  # +1 unit range for reach weapons

        return bonus

    @staticmethod
    def get_armor_penetration(tags: List[str]) -> float:
        """Calculate armor penetration percentage

        Args:
            tags: List of weapon metadata tags

        Returns:
            float: Armor penetration (0.0-1.0, where 0.25 = ignore 25% of armor)
        """
        if "armor_breaker" in tags:
            return 0.25  # Ignore 25% of enemy armor
        return 0.0

    @staticmethod
    def get_damage_vs_armored_bonus(tags: List[str]) -> float:
        """Get bonus damage percentage vs armored targets

        Args:
            tags: List of weapon metadata tags

        Returns:
            float: Damage bonus (0.20 = +20% vs armored)
        """
        if "crushing" in tags:
            return 0.20  # +20% damage vs armored enemies
        return 0.0

    @staticmethod
    def has_cleaving(tags: List[str]) -> bool:
        """Check if weapon has cleaving (AOE) property

        Args:
            tags: List of weapon metadata tags

        Returns:
            bool: True if weapon has cleaving property
        """
        return "cleaving" in tags

    @staticmethod
    def get_all_modifiers_summary(tags: List[str], has_offhand: bool = False) -> str:
        """Get human-readable summary of all tag modifiers

        Args:
            tags: List of weapon metadata tags
            has_offhand: Whether offhand is equipped

        Returns:
            str: Summary of active modifiers
        """
        modifiers = []

        damage_mult = WeaponTagModifiers.get_damage_multiplier(tags, has_offhand)
        if damage_mult > 1.0:
            modifiers.append(f"+{int((damage_mult - 1.0) * 100)}% damage")

        speed_bonus = WeaponTagModifiers.get_attack_speed_bonus(tags)
        if speed_bonus > 0:
            modifiers.append(f"+{int(speed_bonus * 100)}% attack speed")

        crit_bonus = WeaponTagModifiers.get_crit_chance_bonus(tags)
        if crit_bonus > 0:
            modifiers.append(f"+{int(crit_bonus * 100)}% crit chance")

        range_bonus = WeaponTagModifiers.get_range_bonus(tags)
        if range_bonus > 0:
            modifiers.append(f"+{range_bonus:.1f} range")

        armor_pen = WeaponTagModifiers.get_armor_penetration(tags)
        if armor_pen > 0:
            modifiers.append(f"{int(armor_pen * 100)}% armor penetration")

        crushing_bonus = WeaponTagModifiers.get_damage_vs_armored_bonus(tags)
        if crushing_bonus > 0:
            modifiers.append(f"+{int(crushing_bonus * 100)}% vs armored")

        if WeaponTagModifiers.has_cleaving(tags):
            modifiers.append("cleaves adjacent enemies (50% damage)")

        if not modifiers:
            return "No tag modifiers"

        return ", ".join(modifiers)
