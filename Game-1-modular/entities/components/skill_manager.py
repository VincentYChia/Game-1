"""Skill management component"""

from typing import Dict, List, Optional
import json
from pathlib import Path

from data.models import PlayerSkill
from data.databases import SkillDatabase
from .buffs import ActiveBuff
from core.effect_executor import get_effect_executor
from core.tag_debug import get_tag_debugger
from core.paths import get_resource_path
from core.debug_display import debug_print


class SkillManager:
    def __init__(self):
        self.known_skills: Dict[str, PlayerSkill] = {}
        self.equipped_skills: List[Optional[str]] = [None] * 5  # 5 hotbar slots
        self.effect_executor = get_effect_executor()
        self.debugger = get_tag_debugger()
        self.magnitude_values = self._load_magnitude_values()

    def _load_magnitude_values(self) -> dict:
        """Load magnitude values from skills-base-effects-1.JSON"""
        try:
            base_effects_path = get_resource_path("Skills/skills-base-effects-1.JSON")
            with open(base_effects_path, 'r') as f:
                data = json.load(f)

            # Extract magnitude values for each effect type
            magnitude_map = {}
            for effect_name, effect_data in data.get("BASE_EFFECT_TYPES", {}).items():
                magnitude_map[effect_name] = effect_data.get("magnitudeValues", {})

            print(f"[SkillManager] Loaded magnitude values from skills-base-effects-1.JSON")
            return magnitude_map
        except Exception as e:
            print(f"[SkillManager] Warning: Could not load magnitude values: {e}")
            # Fallback to hardcoded values (old system)
            return {
                'empower': {'minor': 0.5, 'moderate': 1.0, 'major': 2.0, 'extreme': 4.0},
                'quicken': {'minor': 0.3, 'moderate': 0.5, 'major': 0.75, 'extreme': 1.0},
                'fortify': {'minor': 10, 'moderate': 20, 'major': 40, 'extreme': 80},
                'pierce': {'minor': 0.1, 'moderate': 0.15, 'major': 0.25, 'extreme': 0.4}
            }

    def can_learn_skill(self, skill_id: str, character) -> tuple[bool, str]:
        """
        Check if character meets requirements to learn a skill.
        Returns (can_learn, reason)
        """
        # Already known?
        if skill_id in self.known_skills:
            return False, "Already known"

        # Get skill definition
        skill_db = SkillDatabase.get_instance()
        skill_def = skill_db.skills.get(skill_id)
        if not skill_def:
            return False, "Skill not found"

        # Check character level
        if character.leveling.level < skill_def.requirements.character_level:
            return False, f"Requires level {skill_def.requirements.character_level}"

        # Check stat requirements
        for stat_name, required_value in skill_def.requirements.stats.items():
            # Map stat names to character stats
            stat_map = {
                'STR': character.stats.strength,
                'DEF': character.stats.defense,
                'VIT': character.stats.vitality,
                'LCK': character.stats.luck,
                'AGI': character.stats.agility,
                'INT': character.stats.intelligence,
                'DEX': character.stats.agility  # DEX maps to AGI in this game
            }
            current_value = stat_map.get(stat_name.upper(), 0)
            if current_value < required_value:
                return False, f"Requires {stat_name} {required_value}"

        # Check title requirements (if any)
        if skill_def.requirements.titles:
            # Get player's title IDs
            player_titles = {title.title_id for title in character.titles.titles}
            for required_title in skill_def.requirements.titles:
                if required_title not in player_titles:
                    return False, f"Requires title: {required_title}"

        return True, "Requirements met"

    def learn_skill(self, skill_id: str, character=None, skip_checks: bool = False) -> bool:
        """
        Learn a new skill.
        If character is provided and skip_checks is False, requirements will be checked.
        skip_checks=True bypasses requirement checks (for starting skills, admin commands, etc.)
        """
        # Check if already known
        if skill_id in self.known_skills:
            return False

        # Check requirements if character provided and not skipping checks
        if character and not skip_checks:
            can_learn, reason = self.can_learn_skill(skill_id, character)
            if not can_learn:
                print(f"   ⚠ Cannot learn {skill_id}: {reason}")
                return False

        # Learn the skill
        self.known_skills[skill_id] = PlayerSkill(skill_id=skill_id)
        return True

    def unlock_skill(self, skill_id: str) -> bool:
        """
        Unlock a skill (called by SkillUnlockSystem after conditions/cost verified).

        This is a wrapper around learn_skill with skip_checks=True since
        the unlock system has already verified all conditions and paid costs.

        Args:
            skill_id: ID of skill to unlock

        Returns:
            True if successfully unlocked
        """
        return self.learn_skill(skill_id, character=None, skip_checks=True)

    def get_available_skills(self, character) -> List[str]:
        """
        Get list of skill IDs that the character can learn but hasn't yet.
        Returns list of skill IDs that meet requirements.
        """
        available = []
        skill_db = SkillDatabase.get_instance()
        if not skill_db.loaded:
            return available

        for skill_id in skill_db.skills.keys():
            # Skip if already known
            if skill_id in self.known_skills:
                continue

            # Check if requirements are met
            can_learn, _ = self.can_learn_skill(skill_id, character)
            if can_learn:
                available.append(skill_id)

        return available

    def equip_skill(self, skill_id: str, slot: int) -> bool:
        """Equip a skill to a hotbar slot (0-4)"""
        if 0 <= slot < 5 and skill_id in self.known_skills:
            self.equipped_skills[slot] = skill_id
            self.known_skills[skill_id].is_equipped = True
            return True
        return False

    def unequip_skill(self, slot: int) -> bool:
        """Unequip a skill from a hotbar slot"""
        if 0 <= slot < 5 and self.equipped_skills[slot]:
            skill_id = self.equipped_skills[slot]
            self.equipped_skills[slot] = None
            if skill_id in self.known_skills:
                self.known_skills[skill_id].is_equipped = False
            return True
        return False

    def update_cooldowns(self, dt: float):
        """Update all skill cooldowns"""
        for skill in self.known_skills.values():
            if skill.current_cooldown > 0:
                skill.current_cooldown = max(0, skill.current_cooldown - dt)

    def use_skill(self, slot: int, character, combat_manager=None, mouse_world_pos=None) -> tuple[bool, str]:
        """Use a skill from hotbar slot (0-4). Returns (success, message)

        Args:
            slot: Hotbar slot (0-4)
            character: Character using the skill
            combat_manager: Combat manager (optional, for combat skills)
            mouse_world_pos: Mouse cursor world position (optional, for directional skills)
        """
        if not (0 <= slot < 5):
            return False, "Invalid slot"

        skill_id = self.equipped_skills[slot]
        if not skill_id:
            return False, "No skill in slot"

        player_skill = self.known_skills.get(skill_id)
        if not player_skill:
            return False, "Skill not learned"

        skill_def = player_skill.get_definition()
        if not skill_def:
            return False, "Skill definition not found"

        # Check cooldown
        if player_skill.current_cooldown > 0:
            return False, f"On cooldown ({player_skill.current_cooldown:.1f}s)"

        # Check mana cost
        skill_db = SkillDatabase.get_instance()
        mana_cost = skill_db.get_mana_cost(skill_def.cost.mana)
        if character.mana < mana_cost:
            return False, f"Not enough mana ({mana_cost} required)"

        # Consume mana
        character.mana -= mana_cost

        # Start cooldown
        cooldown_duration = skill_db.get_cooldown_seconds(skill_def.cost.cooldown)
        player_skill.current_cooldown = cooldown_duration

        # Apply skill effect (with level scaling)
        self._apply_skill_effect(skill_def, character, player_skill, combat_manager, mouse_world_pos)

        # Track skill usage in stat tracker
        if hasattr(character, 'stat_tracker'):
            category = self._get_skill_category(skill_def)
            value, targets = self._extract_skill_value(skill_def, player_skill)
            character.stat_tracker.record_skill_used(
                skill_id=skill_id,
                value=value,
                mana_cost=mana_cost,
                targets=targets,
                category=category
            )

        # Award skill EXP (100 EXP per activation)
        leveled_up, new_level = player_skill.add_exp(100)
        if leveled_up:
            return True, f"Used {skill_def.name}! 🌟 Level {new_level}!"

        return True, f"Used {skill_def.name}!"

    def _apply_skill_effect(self, skill_def, character, player_skill, combat_manager=None, mouse_world_pos=None):
        """Apply the skill's effect with level scaling

        Args:
            skill_def: Skill definition
            character: Character using skill
            player_skill: Player's skill instance (for level)
            combat_manager: Combat manager (optional)
            mouse_world_pos: Mouse cursor world position (optional, for directional skills)
        """
        from core.debug_display import debug_print

        # Check if skill uses tag-based combat system
        if skill_def.combat_tags and len(skill_def.combat_tags) > 0:
            # Check if enemies are available (regardless of in_combat flag)
            # This allows skills to INITIATE combat, just like weapon attacks
            if combat_manager and hasattr(combat_manager, 'get_all_active_enemies'):
                available_enemies = combat_manager.get_all_active_enemies()

                # If enemies exist, use combat-aware skill execution
                if available_enemies:
                    target_enemy = available_enemies[0]

                    # Set player in combat (skills can initiate combat)
                    if hasattr(combat_manager, 'player_in_combat'):
                        combat_manager.player_in_combat = True

                    return self._apply_combat_skill_with_context(
                        skill_def, character, player_skill,
                        target_enemy, available_enemies, mouse_world_pos
                    )

            # No enemies available - will warn if skill needs combat context
            return self._apply_combat_skill(skill_def, character, player_skill)

        # Otherwise use legacy buff-based system
        effect = skill_def.effect
        skill_db = SkillDatabase.get_instance()

        # Get duration for buffs
        base_duration = skill_db.get_duration_seconds(effect.duration)
        is_instant = (base_duration == 0)  # "instant" duration translates to 0

        # Apply level scaling: +10% per level
        level_bonus = player_skill.get_level_scaling_bonus()

        # Calculate class skill affinity bonus based on tag overlap
        class_affinity_bonus = 0.0
        if hasattr(character, 'class_system') and character.class_system.current_class:
            # Get skill tags from combat_tags or effect category
            skill_tags = skill_def.combat_tags if skill_def.combat_tags else [effect.category]
            class_affinity_bonus = character.class_system.current_class.get_skill_affinity_bonus(skill_tags)

        # For instant buffs, use 60s duration but mark as consume_on_use
        # For timed buffs, use calculated duration
        if is_instant:
            duration = 60.0  # Fallback duration
            consume_on_use = True
        else:
            duration = base_duration * (1.0 + level_bonus)
            consume_on_use = False

        # Apply level scaling and class affinity to magnitude values
        def apply_level_scaling(base_value):
            return base_value * (1.0 + level_bonus + class_affinity_bonus)

        def get_magnitude_value(effect_type: str, magnitude: str) -> float:
            """Get magnitude value from loaded JSON data"""
            effect_magnitudes = self.magnitude_values.get(effect_type, {})
            return effect_magnitudes.get(magnitude, 0.5)  # Default to 0.5 if not found

        level_indicator = f" Lv{player_skill.level}" if player_skill.level > 1 else ""
        affinity_indicator = f" (+{class_affinity_bonus*100:.0f}% affinity)" if class_affinity_bonus > 0 else ""
        debug_print(f"⚡ {skill_def.name}{level_indicator}{affinity_indicator}: {effect.effect_type} - {effect.category} ({effect.magnitude})")

        # EMPOWER - Increases damage/output
        if effect.effect_type == "empower":
            base_bonus = get_magnitude_value('empower', effect.magnitude)
            bonus = apply_level_scaling(base_bonus)
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_empower",
                name=f"{skill_def.name} (Damage)",
                effect_type="empower",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration=duration,
                duration_remaining=duration,
                consume_on_use=consume_on_use
            )
            character.buffs.add_buff(buff)
            if consume_on_use:
                debug_print(f"   +{int(bonus*100)}% {effect.category} damage for next action")
            else:
                debug_print(f"   +{int(bonus*100)}% {effect.category} damage for {int(duration)}s")

        # QUICKEN - Increases speed
        elif effect.effect_type == "quicken":
            base_bonus = get_magnitude_value('quicken', effect.magnitude)
            bonus = apply_level_scaling(base_bonus)
            category = "movement" if effect.category == "movement" else effect.category
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_quicken",
                name=f"{skill_def.name} (Speed)",
                effect_type="quicken",
                category=category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration=duration,
                duration_remaining=duration,
                consume_on_use=consume_on_use
            )
            character.buffs.add_buff(buff)
            if consume_on_use:
                print(f"   +{int(bonus*100)}% {category} speed for next action")
            else:
                print(f"   +{int(bonus*100)}% {category} speed for {int(duration)}s")

        # FORTIFY - Increases defense
        elif effect.effect_type == "fortify":
            base_bonus = get_magnitude_value('fortify', effect.magnitude)
            bonus = apply_level_scaling(base_bonus)
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_fortify",
                name=f"{skill_def.name} (Defense)",
                effect_type="fortify",
                category="defense",
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration=duration,
                duration_remaining=duration,
                consume_on_use=consume_on_use
            )
            character.buffs.add_buff(buff)
            if consume_on_use:
                print(f"   +{int(bonus)} flat damage reduction for next hit")
            else:
                print(f"   +{int(bonus)} flat damage reduction for {int(duration)}s")

        # PIERCE - Increases critical chance
        elif effect.effect_type == "pierce":
            base_bonus = get_magnitude_value('pierce', effect.magnitude)
            bonus = apply_level_scaling(base_bonus)
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_pierce",
                name=f"{skill_def.name} (Crit)",
                effect_type="pierce",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration=duration,
                duration_remaining=duration,
                consume_on_use=consume_on_use
            )
            character.buffs.add_buff(buff)
            if consume_on_use:
                print(f"   +{int(bonus*100)}% critical chance for next action")
            else:
                print(f"   +{int(bonus*100)}% critical chance for {int(duration)}s")

        # RESTORE - Instant restoration (health, mana, or durability)
        elif effect.effect_type == "restore":
            # For durability, use percentage-based restoration
            restore_percents = {'minor': 0.15, 'moderate': 0.30, 'major': 0.50, 'extreme': 0.75}
            restore_amounts = {'minor': 50, 'moderate': 100, 'major': 200, 'extreme': 400}

            if "durability" in effect.category:
                # Restore durability to all equipped items and tools
                percent = restore_percents.get(effect.magnitude, 0.30)
                percent *= (1.0 + level_bonus)  # Level scaling

                repaired_items = self._restore_all_durability(character, percent)
                if repaired_items:
                    print(f"   🔧 Repaired {len(repaired_items)} item(s): {', '.join(repaired_items)}")
                else:
                    print(f"   ✓ All equipment at full durability")

            elif "health" in effect.category or "defense" in effect.category:
                amount = restore_amounts.get(effect.magnitude, 100)
                character.health = min(character.max_health, character.health + amount)
                print(f"   Restored {amount} HP")
            elif "mana" in effect.category:
                amount = restore_amounts.get(effect.magnitude, 100)
                character.mana = min(character.max_mana, character.mana + amount)
                print(f"   Restored {amount} MP")

        # ENRICH - Bonus gathering yield
        elif effect.effect_type == "enrich":
            enrich_values = get_magnitude_value('enrich', effect.magnitude)
            bonus = int(apply_level_scaling(enrich_values))  # Whole items only
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_enrich",
                name=f"{skill_def.name} (Yield)",
                effect_type="enrich",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration=duration,
                duration_remaining=duration,
                consume_on_use=consume_on_use
            )
            character.buffs.add_buff(buff)
            if consume_on_use:
                print(f"   +{int(bonus)} bonus items from next {effect.category} action")
            else:
                print(f"   +{int(bonus)} bonus items from {effect.category} for {int(duration)}s")

        # ELEVATE - Rarity upgrade chance
        elif effect.effect_type == "elevate":
            base_bonus = get_magnitude_value('elevate', effect.magnitude)
            bonus = apply_level_scaling(base_bonus)
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_elevate",
                name=f"{skill_def.name} (Quality)",
                effect_type="elevate",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration=duration,
                duration_remaining=duration,
                consume_on_use=consume_on_use
            )
            character.buffs.add_buff(buff)
            if consume_on_use:
                print(f"   +{int(bonus*100)}% rarity upgrade chance for next {effect.category} action")
            else:
                print(f"   +{int(bonus*100)}% rarity upgrade chance for {int(duration)}s")

        # REGENERATE - Restore resources over time (never instant)
        elif effect.effect_type == "regenerate":
            regen_values = get_magnitude_value('regenerate', effect.magnitude)
            amount = apply_level_scaling(regen_values)
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_regenerate",
                name=f"{skill_def.name} (Regen)",
                effect_type="regenerate",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=amount,
                duration=duration if not consume_on_use else 60.0,
                duration_remaining=duration if not consume_on_use else 60.0,
                consume_on_use=False  # Regenerate is always over time
            )
            character.buffs.add_buff(buff)

            # Determine resource type for display
            if "durability" in effect.category:
                resource_type = "durability/s"
            elif "health" in effect.category or "defense" in effect.category:
                resource_type = "HP/s"
            else:
                resource_type = "MP/s"
            print(f"   Regenerating {amount:.1f} {resource_type} for {int(duration if not consume_on_use else 60)}s")

        # DEVASTATE - Area of effect (instant execution for combat skills)
        elif effect.effect_type == "devastate":
            devastate_values = get_magnitude_value('devastate', effect.magnitude)
            radius = int(apply_level_scaling(devastate_values))

            # For INSTANT combat/damage AoE skills: Execute immediately!
            if consume_on_use and effect.category in ["damage", "combat"]:
                print(f"\n🌀 INSTANT AoE: {skill_def.name} executing immediately!")
                debug_print(f"🌀 INSTANT AoE: {skill_def.name} ({radius}-tile radius)")

                # Execute instant AoE if combat manager available
                if combat_manager and hasattr(combat_manager, 'execute_instant_player_aoe'):
                    # Execute instant AoE damage
                    affected = combat_manager.execute_instant_player_aoe(
                        radius=radius,
                        skill_name=skill_def.name
                    )
                    print(f"   ✓ Hit {affected} enemy(s) in {radius}-tile radius!")
                else:
                    # Fallback: create buff if combat manager not available
                    print(f"   ⚠️  Combat manager not available, creating buff instead")
                    buff = ActiveBuff(
                        buff_id=f"{skill_def.skill_id}_devastate",
                        name=f"{skill_def.name} (AoE)",
                        effect_type="devastate",
                        category=effect.category,
                        magnitude=effect.magnitude,
                        bonus_value=radius,
                        duration=duration,
                        duration_remaining=duration,
                        consume_on_use=consume_on_use
                    )
                    character.buffs.add_buff(buff)

            # For gathering AoE (Chain Harvest) or timed AoE: Create buff
            else:
                buff = ActiveBuff(
                    buff_id=f"{skill_def.skill_id}_devastate",
                    name=f"{skill_def.name} (AoE)",
                    effect_type="devastate",
                    category=effect.category,
                    magnitude=effect.magnitude,
                    bonus_value=radius,
                    duration=duration,
                    duration_remaining=duration,
                    consume_on_use=consume_on_use
                )
                character.buffs.add_buff(buff)
                if consume_on_use:
                    print(f"\n🌀 DEVASTATE READY: Next {effect.category} action hits {radius}-tile radius!")
                    print(f"   Buff active: {skill_def.name} (AoE)")
                    debug_print(f"🌀 DEVASTATE: {skill_def.name} ready ({radius}-tile radius)")
                else:
                    print(f"   {effect.category.capitalize()} affects {radius}-tile radius for {int(duration)}s")

        # TRANSCEND - Bypass tier restrictions
        elif effect.effect_type == "transcend":
            transcend_values = get_magnitude_value('transcend', effect.magnitude)
            bypass = int(apply_level_scaling(transcend_values))
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_transcend",
                name=f"{skill_def.name} (Transcend)",
                effect_type="transcend",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=bypass,
                duration=duration,
                duration_remaining=duration,
                consume_on_use=consume_on_use
            )
            character.buffs.add_buff(buff)
            if consume_on_use:
                print(f"   Next {effect.category} action bypasses {bypass} tier restriction(s)")
            else:
                print(f"   Bypass {bypass} tier restriction(s) for {effect.category} for {int(duration)}s")

    def _get_skill_category(self, skill_def) -> str:
        """Determine skill category for stat tracking.

        Args:
            skill_def: Skill definition

        Returns:
            Category string: combat, gathering, crafting, or utility
        """
        # Combat skills have combat_tags
        if skill_def.combat_tags and len(skill_def.combat_tags) > 0:
            return "combat"

        # Check effect category for gathering/crafting
        effect_category = skill_def.effect.category.lower()

        # Gathering skills
        gathering_keywords = ["mining", "forestry", "gathering", "harvest", "wood", "ore", "stone"]
        if any(keyword in effect_category for keyword in gathering_keywords):
            return "gathering"

        # Crafting skills
        crafting_keywords = ["smithing", "alchemy", "refining", "engineering", "enchanting", "crafting"]
        if any(keyword in effect_category for keyword in crafting_keywords):
            return "crafting"

        # Default to utility (buffs, movement, etc.)
        return "utility"

    def _extract_skill_value(self, skill_def, player_skill, scaled_params=None) -> tuple[float, int]:
        """Extract value delivered and targets affected for stat tracking.

        This provides best-effort estimation of skill impact:
        - Combat skills: Use base damage from params
        - Restore skills: Use restoration amount
        - Buff skills: Use magnitude level as proxy
        - Other skills: Minimal value (effect is indirect)

        Args:
            skill_def: Skill definition
            player_skill: Player skill instance (for level scaling)
            scaled_params: Scaled combat parameters (if available)

        Returns:
            (value, targets): Estimated value delivered and number of targets
        """
        effect = skill_def.effect
        value = 0.0
        targets = 0

        # Combat skills - use baseDamage if available
        if scaled_params and "baseDamage" in scaled_params:
            value = scaled_params["baseDamage"]
            targets = 1  # Default single target (combat_manager may update this)

        # Restore skills - calculate restoration amount
        elif effect.effect_type == "restore":
            restore_amounts = {'minor': 50, 'moderate': 100, 'major': 200, 'extreme': 400}
            base_value = restore_amounts.get(effect.magnitude, 100)
            # Apply level scaling
            level_bonus = player_skill.get_level_scaling_bonus()
            value = base_value * (1.0 + level_bonus)
            targets = 1  # Self-targeting

        # Buff skills - use magnitude as relative value
        elif effect.effect_type in ["empower", "quicken", "fortify", "pierce",
                                     "enrich", "elevate", "regenerate", "devastate", "transcend"]:
            # Map magnitude to numeric value (proxy for buff strength)
            magnitude_values = {
                'minor': 1.0,
                'moderate': 2.0,
                'major': 3.0,
                'extreme': 4.0
            }
            value = magnitude_values.get(effect.magnitude, 1.0)
            targets = 1  # Buffs typically affect self

        return value, targets

    def _restore_all_durability(self, character, percent: float) -> List[str]:
        """Restore durability to all equipped items and tools.

        Args:
            character: The character whose equipment to repair
            percent: Percentage of max durability to restore (0.0-1.0)

        Returns:
            List[str]: Names of items that were repaired
        """
        repaired_items = []

        # Repair equipped items (armor, weapons, accessories)
        if hasattr(character, 'equipment') and character.equipment:
            for slot_name, item in character.equipment.slots.items():
                if item and hasattr(item, 'repair') and hasattr(item, 'needs_repair'):
                    if item.needs_repair():
                        repaired = item.repair(percent=percent)
                        if repaired > 0:
                            repaired_items.append(item.name)

        # Repair tools (axe, pickaxe)
        if hasattr(character, 'axe') and character.axe:
            tool = character.axe
            if hasattr(tool, 'durability_current') and hasattr(tool, 'durability_max'):
                if tool.durability_current < tool.durability_max:
                    repair_amount = int(tool.durability_max * percent)
                    tool.durability_current = min(tool.durability_max,
                        tool.durability_current + repair_amount)
                    if repair_amount > 0:
                        repaired_items.append(tool.name)

        if hasattr(character, 'pickaxe') and character.pickaxe:
            tool = character.pickaxe
            if hasattr(tool, 'durability_current') and hasattr(tool, 'durability_max'):
                if tool.durability_current < tool.durability_max:
                    repair_amount = int(tool.durability_max * percent)
                    tool.durability_current = min(tool.durability_max,
                        tool.durability_current + repair_amount)
                    if repair_amount > 0:
                        repaired_items.append(tool.name)

        return repaired_items

    def _apply_combat_skill(self, skill_def, character, player_skill, suppress_warnings=False):
        """Apply a tag-based combat skill using the effect executor

        Args:
            suppress_warnings: If True, don't print warnings for context-dependent skills
        """
        # Apply level scaling to combat params
        level_bonus = player_skill.get_level_scaling_bonus()
        scaled_params = skill_def.combat_params.copy()

        # Scale damage parameters
        if "baseDamage" in scaled_params:
            scaled_params["baseDamage"] *= (1.0 + level_bonus)
        if "baseHealing" in scaled_params:
            scaled_params["baseHealing"] *= (1.0 + level_bonus)

        level_indicator = f" Lv{player_skill.level}" if player_skill.level > 1 else ""
        print(f"⚡ {skill_def.name}{level_indicator}: Combat skill using tags {skill_def.combat_tags}")

        # Determine primary target based on skill target type
        effect = skill_def.effect
        primary_target = None
        available_entities = []

        if effect.target == "enemy":
            # Enemy-targeted skills require enemies to be nearby
            print(f"   ⚠ No enemies in range (enemy-targeted skill)")
            return

        elif effect.target == "self":
            # Self-targeting skill (e.g., shield, regeneration)
            primary_target = character
            available_entities = [character]

        elif effect.target == "area":
            # Area effect skills require enemies to be nearby
            print(f"   ⚠ No enemies in range (area-effect skill)")
            return

        else:
            # Default to self
            primary_target = character
            available_entities = [character]

        # Execute effect using tag system
        try:
            context = self.effect_executor.execute_effect(
                source=character,
                primary_target=primary_target,
                tags=skill_def.combat_tags,
                params=scaled_params,
                available_entities=available_entities
            )

            self.debugger.info(
                f"Skill {skill_def.skill_id} executed: {len(context.targets)} targets affected"
            )
            print(f"   ✓ Affected {len(context.targets)} target(s)")

        except Exception as e:
            self.debugger.error(f"Combat skill execution failed: {e}")
            print(f"   ⚠ Skill execution failed: {e}")

    def use_skill_in_combat(self, slot: int, character, target_enemy=None, available_enemies=None) -> tuple[bool, str]:
        """Use a skill from hotbar slot in combat context with enemy targeting

        Args:
            slot: Hotbar slot (0-4)
            character: Player character
            target_enemy: Primary target enemy (for single-target skills)
            available_enemies: List of all available enemies (for AOE/chain skills)

        Returns:
            (success, message)
        """
        if not (0 <= slot < 5):
            return False, "Invalid slot"

        skill_id = self.equipped_skills[slot]
        if not skill_id:
            return False, "No skill in slot"

        player_skill = self.known_skills.get(skill_id)
        if not player_skill:
            return False, "Skill not learned"

        skill_def = player_skill.get_definition()
        if not skill_def:
            return False, "Skill definition not found"

        # Check cooldown
        if player_skill.current_cooldown > 0:
            return False, f"On cooldown ({player_skill.current_cooldown:.1f}s)"

        # Check mana cost
        skill_db = SkillDatabase.get_instance()
        mana_cost = skill_db.get_mana_cost(skill_def.cost.mana)
        if character.mana < mana_cost:
            return False, f"Not enough mana ({mana_cost} required)"

        # Consume mana
        character.mana -= mana_cost

        # Start cooldown
        cooldown_duration = skill_db.get_cooldown_seconds(skill_def.cost.cooldown)
        player_skill.current_cooldown = cooldown_duration

        # Apply skill effect with combat context
        if skill_def.combat_tags and len(skill_def.combat_tags) > 0:
            # For combat skills, prepare scaled params for value extraction
            level_bonus = player_skill.get_level_scaling_bonus()
            scaled_params = skill_def.combat_params.copy()
            if "baseDamage" in scaled_params:
                scaled_params["baseDamage"] *= (1.0 + level_bonus)
            if "baseHealing" in scaled_params:
                scaled_params["baseHealing"] *= (1.0 + level_bonus)

            self._apply_combat_skill_with_context(
                skill_def, character, player_skill,
                target_enemy, available_enemies or []
            )

            # Track combat skill usage with scaled damage
            if hasattr(character, 'stat_tracker'):
                category = self._get_skill_category(skill_def)
                value, targets = self._extract_skill_value(skill_def, player_skill, scaled_params)
                character.stat_tracker.record_skill_used(
                    skill_id=skill_id,
                    value=value,
                    mana_cost=mana_cost,
                    targets=targets,
                    category=category
                )
        else:
            self._apply_skill_effect(skill_def, character, player_skill)

            # Track non-combat skill usage
            if hasattr(character, 'stat_tracker'):
                category = self._get_skill_category(skill_def)
                value, targets = self._extract_skill_value(skill_def, player_skill)
                character.stat_tracker.record_skill_used(
                    skill_id=skill_id,
                    value=value,
                    mana_cost=mana_cost,
                    targets=targets,
                    category=category
                )

        # Award skill EXP (100 EXP per activation)
        leveled_up, new_level = player_skill.add_exp(100)
        if leveled_up:
            return True, f"Used {skill_def.name}! 🌟 Level {new_level}!"

        return True, f"Used {skill_def.name}!"

    def _apply_combat_skill_with_context(self, skill_def, character, player_skill,
                                          target_enemy, available_enemies, mouse_world_pos=None):
        """Apply a combat skill with full combat context (enemies available)

        Args:
            skill_def: Skill definition
            character: Character using skill
            player_skill: Player's skill instance (for level)
            target_enemy: Primary target enemy
            available_enemies: List of all available enemies
            mouse_world_pos: Mouse cursor world position (optional, for directional skills)
        """
        # Apply level scaling to combat params
        level_bonus = player_skill.get_level_scaling_bonus()
        scaled_params = skill_def.combat_params.copy()

        # Scale damage parameters
        if "baseDamage" in scaled_params:
            scaled_params["baseDamage"] *= (1.0 + level_bonus)
        if "baseHealing" in scaled_params:
            scaled_params["baseHealing"] *= (1.0 + level_bonus)

        # Apply class skill affinity bonus based on tag overlap
        class_affinity_bonus = 0.0
        if hasattr(character, 'class_system') and character.class_system.current_class:
            # Get skill tags from combat_tags or effect
            skill_tags = skill_def.combat_tags if skill_def.combat_tags else []
            class_affinity_bonus = character.class_system.current_class.get_skill_affinity_bonus(skill_tags)

            if class_affinity_bonus > 0:
                # Apply affinity bonus to damage and healing
                if "baseDamage" in scaled_params:
                    scaled_params["baseDamage"] *= (1.0 + class_affinity_bonus)
                if "baseHealing" in scaled_params:
                    scaled_params["baseHealing"] *= (1.0 + class_affinity_bonus)

        level_indicator = f" Lv{player_skill.level}" if player_skill.level > 1 else ""
        affinity_indicator = f" (+{class_affinity_bonus*100:.0f}% affinity)" if class_affinity_bonus > 0 else ""
        print(f"⚡ {skill_def.name}{level_indicator}{affinity_indicator}: Combat skill using tags {skill_def.combat_tags}")

        # Determine primary target based on skill target type
        effect = skill_def.effect
        primary_target = None
        available_entities = []

        # Check if skill uses directional geometry (beam, cone, line)
        directional_geometries = ['beam', 'cone', 'line']
        is_directional = any(tag in directional_geometries for tag in skill_def.combat_tags)

        # Use mouse position for directional skills if available
        if is_directional and mouse_world_pos:
            primary_target = mouse_world_pos  # Use mouse position as aiming point
            available_entities = available_enemies
            print(f"   🎯 Aiming toward mouse cursor")

        elif effect.target == "enemy":
            # Use provided target enemy
            if not target_enemy:
                print(f"   ⚠ No target enemy provided")
                return
            primary_target = target_enemy
            available_entities = available_enemies

        elif effect.target == "self":
            # Self-targeting skill
            primary_target = character
            available_entities = [character]

        elif effect.target == "area":
            # Area effect - use all available enemies
            if not available_enemies:
                print(f"   ⚠ No enemies available for area skill")
                return
            # For AOE, primary target is first enemy (or nearest)
            # Use mouse position for directional AOE if available
            if is_directional and mouse_world_pos:
                primary_target = mouse_world_pos
            else:
                primary_target = available_enemies[0] if available_enemies else character
            available_entities = available_enemies

        else:
            # Default to self
            primary_target = character
            available_entities = [character]

        # Execute effect using tag system
        try:
            context = self.effect_executor.execute_effect(
                source=character,
                primary_target=primary_target,
                tags=skill_def.combat_tags,
                params=scaled_params,
                available_entities=available_entities
            )

            self.debugger.info(
                f"Skill {skill_def.skill_id} executed: {len(context.targets)} targets affected"
            )
            print(f"   ✓ Affected {len(context.targets)} target(s)")

        except Exception as e:
            self.debugger.error(f"Combat skill execution failed: {e}")
            print(f"   ⚠ Skill execution failed: {e}")
