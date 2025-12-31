"""Character stats component"""

from dataclasses import dataclass


@dataclass
class CharacterStats:
    strength: int = 0
    defense: int = 0
    vitality: int = 0
    luck: int = 0
    agility: int = 0
    intelligence: int = 0

    def get_bonus(self, stat_name: str) -> float:
        val = getattr(self, stat_name.lower(), 0)
        scaling = {'strength': 0.05, 'defense': 0.02, 'vitality': 0.01, 'luck': 0.02, 'agility': 0.05,
                   'intelligence': 0.02}
        return val * scaling.get(stat_name.lower(), 0.05)

    def get_flat_bonus(self, stat_name: str, bonus_type: str) -> float:
        val = getattr(self, stat_name.lower(), 0)
        if stat_name == 'strength' and bonus_type == 'carry_capacity':
            return val * 10
        elif stat_name == 'vitality' and bonus_type == 'max_health':
            return val * 15
        elif stat_name == 'intelligence' and bonus_type == 'mana':
            return val * 20
        return 0

    def get_durability_loss_multiplier(self) -> float:
        """Get multiplier for durability loss based on DEF stat.

        DEF reduces durability loss by 2% per point.
        Example: 10 DEF = 20% less durability loss (0.8 multiplier)

        Returns:
            float: Multiplier between 0.1 and 1.0
        """
        def_reduction = self.defense * 0.02  # 2% per DEF point
        return max(0.1, 1.0 - def_reduction)  # Minimum 10% durability loss

    def get_durability_bonus_multiplier(self) -> float:
        """Get multiplier for max durability based on VIT stat.

        VIT increases max durability by 1% per point.
        Example: 10 VIT = 10% more max durability (1.1 multiplier)

        Returns:
            float: Multiplier >= 1.0
        """
        vit_bonus = self.vitality * 0.01  # +1% per VIT point
        return 1.0 + vit_bonus

    def get_carry_capacity_multiplier(self) -> float:
        """Get multiplier for carry capacity based on STR stat.

        STR increases carry capacity by 2% per point.
        Example: 10 STR = 20% more capacity (1.2 multiplier)

        Returns:
            float: Multiplier >= 1.0
        """
        str_bonus = self.strength * 0.02  # +2% per STR point
        return 1.0 + str_bonus
