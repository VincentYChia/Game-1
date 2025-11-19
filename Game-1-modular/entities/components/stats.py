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
