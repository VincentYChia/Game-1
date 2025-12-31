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
    consume_on_use: bool = False    # If True, buff is consumed when relevant action is performed

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
                    elif "durability" in buff.category:
                        # Regenerate durability on all equipped items
                        self._regenerate_durability(character, amount)

        # Update buff durations and remove expired ones
        self.active_buffs = [buff for buff in self.active_buffs if buff.update(dt)]

    def _regenerate_durability(self, character, amount: float):
        """Apply durability regeneration to all equipped items.

        Args:
            character: The character whose equipment to repair
            amount: Amount of durability to restore
        """
        # Repair equipped items (armor, weapons, accessories)
        if hasattr(character, 'equipment') and character.equipment:
            for slot_name, item in character.equipment.slots.items():
                if item and hasattr(item, 'durability_current') and hasattr(item, 'durability_max'):
                    if item.durability_current < item.durability_max:
                        item.durability_current = min(item.durability_max,
                            item.durability_current + amount)

        # Repair tools
        for tool_attr in ['axe', 'pickaxe']:
            if hasattr(character, tool_attr):
                tool = getattr(character, tool_attr)
                if tool and hasattr(tool, 'durability_current') and hasattr(tool, 'durability_max'):
                    if tool.durability_current < tool.durability_max:
                        tool.durability_current = min(tool.durability_max,
                            tool.durability_current + amount)

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

    def consume_buffs_for_action(self, action_type: str, category: str = None):
        """
        Consume (remove) buffs that are marked consume_on_use for this action type.

        Args:
            action_type: Type of action performed ("attack", "gather", "craft", etc.)
            category: Optional category filter (e.g., "combat", "mining", "smithing")
        """
        buffs_to_remove = []

        for buff in self.active_buffs:
            if not buff.consume_on_use:
                continue

            # Match by action type
            should_consume = False

            if action_type == "attack":
                # Consume combat/damage buffs on attack
                if buff.category in ["combat", "damage"]:
                    should_consume = True
            elif action_type == "gather":
                # Consume gathering buffs (mining, forestry, fishing) on gather
                if category:
                    # If category specified, only consume exact matches
                    if buff.category == category:
                        should_consume = True
                else:
                    # If no category specified, consume all gathering buffs
                    if buff.category in ["mining", "forestry", "fishing", "gathering"]:
                        should_consume = True
            elif action_type == "craft":
                # Consume crafting buffs on craft
                if category:
                    # If category specified, only consume exact matches
                    if buff.category == category:
                        should_consume = True
                else:
                    # If no category specified, consume all crafting buffs
                    if buff.category in ["smithing", "alchemy", "engineering", "refining", "enchanting"]:
                        should_consume = True

            if should_consume:
                buffs_to_remove.append(buff)

        # Remove consumed buffs
        for buff in buffs_to_remove:
            print(f"   ⚡ Consumed: {buff.name}")
            self.active_buffs.remove(buff)
