"""Buff system components"""

from dataclasses import dataclass
from typing import List


@dataclass
class ActiveBuff:
    """Represents an active buff on the character

    Buffs are temporary enhancements that modify character stats or abilities.
    They can come from skills, potions, equipment, or other sources.
    """
    buff_id: str                    # Unique identifier for this buff
    name: str                       # Display name
    effect_type: str                # empower, quicken, fortify, etc.
    category: str                   # mining, combat, smithing, movement, etc.
    magnitude: str                  # minor, moderate, major, extreme
    bonus_value: float              # The actual numerical bonus (multiplier or flat value)
    duration: float                 # Original duration in seconds (for UI progress bar)
    duration_remaining: float       # Time remaining in seconds (countdown)
    source: str = "skill"           # skill, potion, equipment, etc.

    def update(self, dt: float) -> bool:
        """Update buff timer. Returns True if buff is still active."""
        self.duration_remaining -= dt
        return self.duration_remaining > 0

    def get_progress_percent(self) -> float:
        """Get the percentage of duration remaining (0.0 to 1.0) for UI display"""
        if self.duration <= 0:
            return 0.0
        return max(0.0, min(1.0, self.duration_remaining / self.duration))


class BuffManager:
    """Manages active buffs on a character"""
    def __init__(self):
        self.active_buffs: List[ActiveBuff] = []

    def add_buff(self, buff: ActiveBuff):
        """Add a new buff (stacks with existing buffs)"""
        self.active_buffs.append(buff)

    def update(self, dt: float, character=None):
        """Update all buffs and remove expired ones. Apply regenerate effects if character provided."""
        # Apply regenerate effects if character is provided
        if character:
            for buff in self.active_buffs:
                if buff.effect_type == "regenerate":
                    amount = buff.bonus_value * dt
                    if "health" in buff.category or "defense" in buff.category:
                        character.health = min(character.max_health, character.health + amount)
                    elif "mana" in buff.category:
                        character.mana = min(character.max_mana, character.mana + amount)

        # Update buff durations and remove expired ones
        self.active_buffs = [buff for buff in self.active_buffs if buff.update(dt)]

    def get_total_bonus(self, effect_type: str, category: str) -> float:
        """Get total bonus from all matching buffs"""
        total = 0.0
        for buff in self.active_buffs:
            if buff.effect_type == effect_type and buff.category == category:
                total += buff.bonus_value
        return total

    def get_movement_speed_bonus(self) -> float:
        """Get total movement speed bonus"""
        return self.get_total_bonus("quicken", "movement")

    def get_damage_bonus(self, category: str) -> float:
        """Get damage bonus for a specific category (mining, combat, etc.)"""
        return self.get_total_bonus("empower", category)

    def get_defense_bonus(self) -> float:
        """Get defense bonus"""
        return self.get_total_bonus("fortify", "defense")
