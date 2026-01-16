"""
Potion Effect Executor System
Tag-driven potion effect application system
"""

from typing import Dict, Tuple, Any, TYPE_CHECKING
from data.models.materials import MaterialDefinition
from entities.components.buffs import ActiveBuff

if TYPE_CHECKING:
    from entities.character import Character


class PotionEffectExecutor:
    """
    Executes potion effects based on tags and parameters.

    Supported Tags:
    - healing: Restore HP (instant or over_time)
    - mana_restore: Restore mana (instant or over_time)
    - buff: Apply stat buffs (strength, defense, speed, etc.)
    - resistance: Elemental damage resistance (fire, ice, elemental)
    - utility: Tool/armor enhancements (efficiency, armor, weapon)

    Tag Modifiers:
    - instant: Effect applies immediately
    - over_time: Effect applies gradually
    - self: Targets the character using the potion
    """

    def __init__(self):
        """Initialize the potion effect executor"""
        pass

    def apply_potion_effect(
        self,
        character: 'Character',
        potion_def: MaterialDefinition,
        crafted_stats: Dict[str, Any] = None
    ) -> Tuple[bool, str]:
        """
        Apply potion effects to character based on tags and parameters.

        Args:
            character: Character to apply effects to
            potion_def: Potion material definition with effect_tags and effect_params
            crafted_stats: Optional crafting quality stats (potency, duration, quality)

        Returns:
            Tuple[bool, str]: (success, message)
        """
        if crafted_stats is None:
            crafted_stats = {}

        # Get quality multipliers
        potency = crafted_stats.get('potency', 100) / 100.0  # Effect strength multiplier
        duration_mult = crafted_stats.get('duration', 100) / 100.0  # Duration multiplier

        tags = potion_def.effect_tags
        params = potion_def.effect_params

        if not tags:
            return False, f"{potion_def.name} has no effect tags defined"

        messages = []
        success = False

        # Process healing effects
        if 'healing' in tags:
            heal_success, heal_msg = self._apply_healing(character, tags, params, potency, duration_mult)
            if heal_success:
                success = True
                messages.append(heal_msg)

        # Process mana restoration effects
        if 'mana_restore' in tags:
            mana_success, mana_msg = self._apply_mana_restore(character, tags, params, potency, duration_mult)
            if mana_success:
                success = True
                messages.append(mana_msg)

        # Process buff effects
        if 'buff' in tags:
            buff_success, buff_msg = self._apply_buff(character, tags, params, potency, duration_mult)
            if buff_success:
                success = True
                messages.append(buff_msg)

        # Process resistance effects
        if 'resistance' in tags:
            resist_success, resist_msg = self._apply_resistance(character, tags, params, potency, duration_mult)
            if resist_success:
                success = True
                messages.append(resist_msg)

        # Process utility effects (oils, polishes)
        if 'utility' in tags:
            utility_success, utility_msg = self._apply_utility(character, tags, params, potency, duration_mult)
            if utility_success:
                success = True
                messages.append(utility_msg)

        # Combine all messages
        final_message = " | ".join(messages) if messages else "No effect"

        # Add potency indicator if enhanced
        if success and potency > 1.0:
            final_message += f" (potency: {int(potency*100)}%)"

        return success, final_message

    def _apply_healing(
        self,
        character: 'Character',
        tags: list,
        params: dict,
        potency: float,
        duration_mult: float
    ) -> Tuple[bool, str]:
        """Apply healing effects (instant or over time)"""
        if 'instant' in tags:
            # Instant heal
            base_heal = params.get('heal_amount', 50)
            heal_amount = min(int(base_heal * potency), character.max_health - character.health)
            character.health += heal_amount
            return True, f"Restored {heal_amount:.0f} HP"

        elif 'over_time' in tags:
            # Heal over time (regeneration)
            base_regen = params.get('heal_per_second', 5.0)
            base_duration = params.get('duration', 60.0)

            actual_regen = base_regen * potency
            actual_duration = base_duration * duration_mult

            # Add regeneration buff
            buff = ActiveBuff(
                buff_id="potion_health_regen",
                name="Health Regeneration",
                effect_type="regenerate",
                category="health",
                magnitude="moderate",
                bonus_value=actual_regen,
                duration=actual_duration,
                duration_remaining=actual_duration,
                source="potion",
                consume_on_use=False
            )
            character.buffs.add_buff(buff)
            return True, f"Regenerating {actual_regen:.1f} HP/s for {actual_duration:.0f}s"

        return False, "Unknown healing type"

    def _apply_mana_restore(
        self,
        character: 'Character',
        tags: list,
        params: dict,
        potency: float,
        duration_mult: float
    ) -> Tuple[bool, str]:
        """Apply mana restoration effects (instant or over time)"""
        if 'instant' in tags:
            # Instant mana restore
            base_mana = params.get('mana_amount', 50)
            mana_amount = min(int(base_mana * potency), character.max_mana - character.mana)
            character.mana += mana_amount
            return True, f"Restored {mana_amount:.0f} Mana"

        elif 'over_time' in tags:
            # Mana over time (regeneration)
            base_regen = params.get('mana_per_second', 2.0)
            base_duration = params.get('duration', 60.0)

            actual_regen = base_regen * potency
            actual_duration = base_duration * duration_mult

            # Add mana regeneration buff
            buff = ActiveBuff(
                buff_id="potion_mana_regen",
                name="Mana Regeneration",
                effect_type="regenerate",
                category="mana",
                magnitude="moderate",
                bonus_value=actual_regen,
                duration=actual_duration,
                duration_remaining=actual_duration,
                source="potion",
                consume_on_use=False
            )
            character.buffs.add_buff(buff)
            return True, f"Regenerating {actual_regen:.1f} Mana/s for {actual_duration:.0f}s"

        return False, "Unknown mana restore type"

    def _apply_buff(
        self,
        character: 'Character',
        tags: list,
        params: dict,
        potency: float,
        duration_mult: float
    ) -> Tuple[bool, str]:
        """Apply stat buff effects"""
        buff_type = params.get('buff_type', 'strength')  # strength, defense, speed, max_hp, etc.
        base_value = params.get('buff_value', 0.2)  # Multiplier or flat value
        base_duration = params.get('duration', 300.0)

        actual_value = base_value * potency
        actual_duration = base_duration * duration_mult

        # Map buff type to category
        category_map = {
            'strength': 'combat',
            'defense': 'defense',
            'speed': 'movement',
            'max_hp': 'health'
        }
        category = category_map.get(buff_type, 'combat')

        # Map buff type to display name
        name_map = {
            'strength': 'Strength Boost',
            'defense': 'Defense Boost',
            'speed': 'Speed Boost',
            'max_hp': 'Vitality Boost'
        }
        buff_name = name_map.get(buff_type, f'{buff_type.capitalize()} Buff')

        # Create and add buff
        buff = ActiveBuff(
            buff_id=f"potion_{buff_type}",
            name=buff_name,
            effect_type="empower",
            category=category,
            magnitude="moderate",
            bonus_value=actual_value,
            duration=actual_duration,
            duration_remaining=actual_duration,
            source="potion",
            consume_on_use=False
        )
        character.buffs.add_buff(buff)

        # Format message based on buff type
        if buff_type == 'strength':
            return True, f"+{int(actual_value*100)}% physical damage for {actual_duration:.0f}s"
        elif buff_type == 'defense':
            return True, f"+{int(actual_value*100)}% defense for {actual_duration:.0f}s"
        elif buff_type == 'speed':
            return True, f"+{int(actual_value*100)}% speed for {actual_duration:.0f}s"
        elif buff_type == 'max_hp':
            return True, f"+{int(actual_value*100)}% max HP for {actual_duration:.0f}s"
        else:
            return True, f"{buff_type} buff for {actual_duration:.0f}s"

    def _apply_resistance(
        self,
        character: 'Character',
        tags: list,
        params: dict,
        potency: float,
        duration_mult: float
    ) -> Tuple[bool, str]:
        """Apply elemental resistance effects"""
        resistance_type = params.get('resistance_type', 'fire')  # fire, ice, elemental (all)
        base_reduction = params.get('damage_reduction', 0.5)  # 50% reduction
        base_duration = params.get('duration', 360.0)

        actual_reduction = min(base_reduction * potency, 0.9)  # Cap at 90%
        actual_duration = base_duration * duration_mult

        # Map resistance type to display name
        name_map = {
            'fire': 'Fire Resistance',
            'ice': 'Ice Resistance',
            'elemental': 'Elemental Resistance'
        }
        buff_name = name_map.get(resistance_type, f'{resistance_type.capitalize()} Resistance')

        # Create and add resistance buff
        buff = ActiveBuff(
            buff_id=f"resistance_{resistance_type}",
            name=buff_name,
            effect_type="fortify",
            category="defense",
            magnitude="moderate",
            bonus_value=actual_reduction,
            duration=actual_duration,
            duration_remaining=actual_duration,
            source="potion",
            consume_on_use=False
        )
        character.buffs.add_buff(buff)

        if resistance_type == 'elemental':
            return True, f"All elemental resistance for {actual_duration:.0f}s"
        else:
            return True, f"{int(actual_reduction*100)}% {resistance_type} resistance for {actual_duration:.0f}s"

    def _apply_utility(
        self,
        character: 'Character',
        tags: list,
        params: dict,
        potency: float,
        duration_mult: float
    ) -> Tuple[bool, str]:
        """Apply utility effects (efficiency oil, armor polish, weapon oil)"""
        utility_type = params.get('utility_type', 'efficiency')  # efficiency, armor, weapon
        base_value = params.get('utility_value', 0.15)
        base_duration = params.get('duration', 3600.0)

        actual_value = base_value * potency
        actual_duration = base_duration * duration_mult

        # Map utility type to category
        category_map = {
            'efficiency': 'gathering',
            'armor': 'defense',
            'weapon': 'combat'
        }
        category = category_map.get(utility_type, 'gathering')

        # Map utility type to display name
        name_map = {
            'efficiency': 'Efficiency Oil',
            'armor': 'Armor Polish',
            'weapon': 'Weapon Oil'
        }
        buff_name = name_map.get(utility_type, f'{utility_type.capitalize()} Enhancement')

        # Create and add utility buff
        buff = ActiveBuff(
            buff_id=f"utility_{utility_type}",
            name=buff_name,
            effect_type="empower",
            category=category,
            magnitude="moderate",
            bonus_value=actual_value,
            duration=actual_duration,
            duration_remaining=actual_duration,
            source="potion",
            consume_on_use=False
        )
        character.buffs.add_buff(buff)

        if utility_type == 'efficiency':
            return True, f"+{int(actual_value*100)}% gathering speed for {actual_duration:.0f}s"
        elif utility_type == 'armor':
            return True, f"+{int(actual_value*100)}% armor defense for {actual_duration:.0f}s"
        elif utility_type == 'weapon':
            return True, f"+{int(actual_value*100)}% weapon damage for {actual_duration:.0f}s"
        else:
            return True, f"{utility_type} enhancement for {actual_duration:.0f}s"


# Singleton instance
_potion_executor_instance = None

def get_potion_executor() -> PotionEffectExecutor:
    """Get singleton potion executor instance"""
    global _potion_executor_instance
    if _potion_executor_instance is None:
        _potion_executor_instance = PotionEffectExecutor()
    return _potion_executor_instance
