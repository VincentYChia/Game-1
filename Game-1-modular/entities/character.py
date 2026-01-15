"""Main player character class that integrates all character components and systems"""

from __future__ import annotations
import random
import json
import os
from typing import List, Optional, Tuple, TYPE_CHECKING

# Components
from entities.components import (
    CharacterStats,
    LevelingSystem,
    SkillManager,
    BuffManager,
    ActiveBuff,
    ActivityTracker,
    EquipmentManager,
    Inventory
)

# Systems
from systems import (
    Encyclopedia,
    QuestManager,
    WorldSystem,
    TitleSystem,
    ClassSystem,
    NaturalResource
)

# Models
from data.models import (
    Position,
    CraftingStation,
    EquipmentItem,
    ClassDefinition
)

# Databases
from data.databases import (
    EquipmentDatabase,
    ClassDatabase,
    SkillDatabase,
    TitleDatabase,
    MaterialDatabase
)

# Config
from core.config import Config

# Tool class
from entities import Tool

# Status effect system
from entities.status_manager import add_status_manager_to_entity


class Character:
    def __init__(self, start_position: Position):
        self.position = start_position
        self.facing = "down"
        self.movement_speed = Config.PLAYER_SPEED
        self.interaction_range = Config.INTERACTION_RANGE

        # Knockback system - smooth forced movement
        self.knockback_velocity_x = 0.0
        self.knockback_velocity_y = 0.0
        self.knockback_duration_remaining = 0.0

        self.stats = CharacterStats()
        self.leveling = LevelingSystem()
        self.skills = SkillManager()
        self.buffs = BuffManager()
        self.titles = TitleSystem()
        self.class_system = ClassSystem()
        self.class_system.register_on_class_set(self._on_class_selected)
        self.activities = ActivityTracker()
        self.equipment = EquipmentManager()
        self.encyclopedia = Encyclopedia()
        self.quests = QuestManager()

        self.base_max_health = 100
        self.base_max_mana = 100
        self.max_health = self.base_max_health
        self.health = self.max_health
        self.max_mana = self.base_max_mana
        self.mana = self.max_mana
        self.shield_amount = 0.0  # Temporary damage absorption from shield/barrier buffs

        self.inventory = Inventory(30)
        self.tools: List[Tool] = []
        self.selected_tool: Optional[Tool] = None
        self._selected_weapon: Optional[EquipmentItem] = None  # For Tab cycling through weapons
        self._selected_slot: str = 'mainHand'  # Default to mainHand until player presses TAB

        # Add status effect manager
        add_status_manager_to_entity(self)
        self.category = "player"  # For tag system context-awareness

        self.active_station: Optional[CraftingStation] = None
        self.crafting_ui_open = False
        self.stats_ui_open = False
        self.equipment_ui_open = False
        self.skills_ui_open = False
        self.skills_menu_scroll_offset = 0  # For scrolling in skills menu
        self.class_selection_open = False

        # Combat
        self.attack_cooldown = 0.0
        self.mainhand_cooldown = 0.0
        self.offhand_cooldown = 0.0
        self.last_attacked_enemy = None

        # Health regeneration tracking
        self.time_since_last_damage_taken = 0.0
        self.time_since_last_damage_dealt = 0.0
        self.health_regen_threshold = 5.0  # 5 seconds
        self.health_regen_rate = 5.0  # 5 HP per second

        self._give_starting_tools()
        if Config.DEBUG_INFINITE_RESOURCES:
            self._give_debug_items()

    def _give_starting_tools(self):
        # Give starting tools as equipped items in tool slots
        equip_db = EquipmentDatabase.get_instance()

        # Equip copper axe
        copper_axe = equip_db.create_equipment_from_id("copper_axe")
        if copper_axe:
            self.equipment.slots['axe'] = copper_axe
            print(f"✓ Starting tool equipped: {copper_axe.name} in axe slot")

        # Equip copper pickaxe
        copper_pickaxe = equip_db.create_equipment_from_id("copper_pickaxe")
        if copper_pickaxe:
            self.equipment.slots['pickaxe'] = copper_pickaxe
            print(f"✓ Starting tool equipped: {copper_pickaxe.name} in pickaxe slot")

    def _on_class_selected(self, class_def):
        """Called when a class is selected - applies tag-driven tool bonuses."""
        if not class_def or not class_def.tags:
            return

        # Apply efficiency bonuses to equipped tools based on class tags
        axe_bonus = self.class_system.get_tool_efficiency_bonus('axe')
        pick_bonus = self.class_system.get_tool_efficiency_bonus('pickaxe')

        # Apply to equipped axe
        if axe_bonus > 0:
            axe = self.equipment.slots.get('axe')
            if axe and hasattr(axe, 'efficiency'):
                axe.efficiency = 1.0 + axe_bonus
                print(f"   → {class_def.name} class bonus: +{axe_bonus*100:.0f}% axe efficiency")

        # Apply to equipped pickaxe
        if pick_bonus > 0:
            pick = self.equipment.slots.get('pickaxe')
            if pick and hasattr(pick, 'efficiency'):
                pick.efficiency = 1.0 + pick_bonus
                print(f"   → {class_def.name} class bonus: +{pick_bonus*100:.0f}% pickaxe efficiency")

        # Log tag-driven bonuses
        if axe_bonus > 0 or pick_bonus > 0:
            print(f"✓ Applied tag-driven tool bonuses for {class_def.name}")

    def _give_debug_items(self):
        """Give starter items in debug mode"""
        # Set max level
        self.leveling.level = self.leveling.max_level
        self.leveling.unallocated_stat_points = 100
        print(f"🔧 DEBUG: Set level to {self.leveling.level} with {self.leveling.unallocated_stat_points} stat points")

        # Give lots of materials
        self.inventory.add_item("copper_ore", 50)
        self.inventory.add_item("iron_ore", 50)
        self.inventory.add_item("oak_log", 50)
        self.inventory.add_item("birch_log", 50)

    def save_to_file(self, filename: str) -> bool:
        """Save character data to a JSON file"""
        try:
            save_data = {
                "version": "1.0",
                "position": {"x": self.position.x, "y": self.position.y, "z": self.position.z},
                "stats": {
                    "strength": self.stats.strength,
                    "defense": self.stats.defense,
                    "vitality": self.stats.vitality,
                    "luck": self.stats.luck,
                    "agility": self.stats.agility,
                    "intelligence": self.stats.intelligence
                },
                "leveling": {
                    "level": self.leveling.level,
                    "current_exp": self.leveling.current_exp,
                    "unallocated_stat_points": self.leveling.unallocated_stat_points
                },
                "health": self.health,
                "mana": self.mana,
                "class": self.class_system.current_class.class_id if self.class_system.current_class else None,
                "inventory": [
                    {"item_id": slot.item_id, "quantity": slot.quantity} if slot else None
                    for slot in self.inventory.slots
                ],
                "equipped_skills": self.skills.equipped_skills,
                "known_skills": {
                    skill_id: {"level": skill.level, "experience": skill.experience}
                    for skill_id, skill in self.skills.known_skills.items()
                },
                "titles": [title.title_id for title in self.titles.earned_titles],
                "activities": dict(self.activities.activity_counts),
                "equipment": {
                    slot_name: item.item_id if item else None
                    for slot_name, item in self.equipment.slots.items()
                }
            }

            # Create saves directory if it doesn't exist
            os.makedirs("saves", exist_ok=True)

            with open(f"saves/{filename}", 'w') as f:
                json.dump(save_data, f, indent=2)

            print(f"✓ Game saved to saves/{filename}")
            return True

        except Exception as e:
            print(f"⚠ Error saving game: {e}")
            return False

    @staticmethod
    def load_from_file(filename: str):
        """Load character data from a JSON file and create a Character instance"""
        try:
            with open(f"saves/{filename}", 'r') as f:
                save_data = json.load(f)

            # Create character at saved position
            pos_data = save_data.get("position", {"x": 0, "y": 0, "z": 0})
            character = Character(Position(pos_data["x"], pos_data["y"], pos_data["z"]))

            # Restore stats
            stats_data = save_data.get("stats", {})
            character.stats.strength = stats_data.get("strength", 0)
            character.stats.defense = stats_data.get("defense", 0)
            character.stats.vitality = stats_data.get("vitality", 0)
            character.stats.luck = stats_data.get("luck", 0)
            character.stats.agility = stats_data.get("agility", 0)
            character.stats.intelligence = stats_data.get("intelligence", 0)

            # Restore leveling
            leveling_data = save_data.get("leveling", {})
            character.leveling.level = leveling_data.get("level", 1)
            character.leveling.current_exp = leveling_data.get("current_exp", 0)
            character.leveling.unallocated_stat_points = leveling_data.get("unallocated_stat_points", 0)

            # Restore health and mana
            character.recalculate_stats()
            character.health = save_data.get("health", character.max_health)
            character.mana = save_data.get("mana", character.max_mana)

            # Restore class
            class_id = save_data.get("class")
            if class_id:
                class_db = ClassDatabase.get_instance()
                if class_id in class_db.classes:
                    character.class_system.set_class(class_db.classes[class_id])
                    character.class_selection_open = False

            # Restore inventory
            inv_data = save_data.get("inventory", [])
            for idx, item_data in enumerate(inv_data):
                if item_data and idx < character.inventory.max_slots:
                    character.inventory.add_item(item_data["item_id"], item_data["quantity"])

            # Restore skills
            known_skills_data = save_data.get("known_skills", {})
            for skill_id, skill_info in known_skills_data.items():
                character.skills.learn_skill(skill_id, skip_checks=True)
                if skill_id in character.skills.known_skills:
                    character.skills.known_skills[skill_id].level = skill_info.get("level", 1)
                    character.skills.known_skills[skill_id].experience = skill_info.get("experience", 0)

            # Restore equipped skills
            equipped_data = save_data.get("equipped_skills", [None] * 5)
            for slot_idx, skill_id in enumerate(equipped_data):
                if skill_id:
                    character.skills.equip_skill(skill_id, slot_idx)

            # Restore titles
            title_db = TitleDatabase.get_instance()
            titles_data = save_data.get("titles", [])
            for title_id in titles_data:
                if title_id in title_db.titles:
                    title = title_db.titles[title_id]
                    if title not in character.titles.earned_titles:
                        character.titles.earned_titles.append(title)

            # Restore activities
            activities_data = save_data.get("activities", {})
            for activity_type, count in activities_data.items():
                character.activities.activity_counts[activity_type] = count

            # Restore equipment
            equipment_db = EquipmentDatabase.get_instance()
            equipment_data = save_data.get("equipment", {})
            for slot_name, item_id in equipment_data.items():
                if item_id and equipment_db.is_equipment(item_id):
                    equipment_item = equipment_db.create_equipment_from_id(item_id)
                    character.equipment.slots[slot_name] = equipment_item

            character.recalculate_stats()
            print(f"✓ Game loaded from saves/{filename}")
            return character

        except FileNotFoundError:
            print(f"⚠ Save file not found: saves/{filename}")
            return None
        except Exception as e:
            print(f"⚠ Error loading game: {e}")
            import traceback
            traceback.print_exc()
            return None

    def restore_from_save(self, player_data: dict):
        """
        Restore character state from save data (new SaveManager format).

        Args:
            player_data: Dictionary containing player data from save file
        """
        from data.databases import ClassDatabase, EquipmentDatabase, TitleDatabase

        # Restore position
        pos_data = player_data.get("position", {"x": 0, "y": 0, "z": 0})
        self.position.x = pos_data["x"]
        self.position.y = pos_data["y"]
        self.position.z = pos_data["z"]
        self.facing = player_data.get("facing", "down")

        # Restore stats
        stats_data = player_data.get("stats", {})
        self.stats.strength = stats_data.get("strength", 0)
        self.stats.defense = stats_data.get("defense", 0)
        self.stats.vitality = stats_data.get("vitality", 0)
        self.stats.luck = stats_data.get("luck", 0)
        self.stats.agility = stats_data.get("agility", 0)
        self.stats.intelligence = stats_data.get("intelligence", 0)

        # Restore leveling
        leveling_data = player_data.get("leveling", {})
        self.leveling.level = leveling_data.get("level", 1)
        self.leveling.current_exp = leveling_data.get("current_exp", 0)
        self.leveling.unallocated_stat_points = leveling_data.get("unallocated_stat_points", 0)

        # Restore class
        class_id = player_data.get("class")
        if class_id:
            class_db = ClassDatabase.get_instance()
            if class_id in class_db.classes:
                self.class_system.set_class(class_db.classes[class_id])
                self.class_selection_open = False

        # Recalculate stats to get correct max health/mana
        self.recalculate_stats()

        # Restore health and mana AFTER recalculation
        self.health = player_data.get("health", self.max_health)
        self.mana = player_data.get("mana", self.max_mana)

        # Restore inventory
        self.inventory.slots = [None] * self.inventory.max_slots
        inv_data = player_data.get("inventory", [])
        for idx, item_data in enumerate(inv_data):
            if item_data and idx < self.inventory.max_slots:
                from entities.components.inventory import ItemStack
                from data.models.equipment import EquipmentItem

                # Restore basic item stack
                item_stack = ItemStack(
                    item_id=item_data["item_id"],
                    quantity=item_data["quantity"],
                    max_stack=item_data.get("max_stack", 99),
                    rarity=item_data.get("rarity", "common")
                )

                # Restore equipment data if present
                if "equipment_data" in item_data:
                    eq_data = item_data["equipment_data"]

                    # Convert damage list back to tuple if needed
                    damage = eq_data.get("damage", [0, 0])
                    if isinstance(damage, list):
                        damage = tuple(damage)

                    item_stack.equipment_data = EquipmentItem(
                        item_id=eq_data["item_id"],
                        name=eq_data.get("name", eq_data["item_id"]),
                        tier=eq_data.get("tier", 1),
                        rarity=eq_data.get("rarity", "common"),
                        slot=eq_data.get("slot", "mainHand"),
                        damage=damage,
                        defense=eq_data.get("defense", 0),
                        durability_current=eq_data.get("durability_current", 100),
                        durability_max=eq_data.get("durability_max", 100),
                        attack_speed=eq_data.get("attack_speed", 1.0),
                        weight=eq_data.get("weight", 1.0),
                        range=eq_data.get("range", 1.0),
                        hand_type=eq_data.get("hand_type", "default"),
                        item_type=eq_data.get("item_type", "weapon"),
                        icon_path=eq_data.get("icon_path")  # Restore icon path for proper PNG rendering
                    )

                    # Restore bonuses if present
                    if "bonuses" in eq_data:
                        item_stack.equipment_data.bonuses = eq_data["bonuses"]

                    # Restore enchantments if present
                    if "enchantments" in eq_data:
                        item_stack.equipment_data.enchantments = eq_data["enchantments"]

                    # Restore requirements if present
                    if "requirements" in eq_data:
                        item_stack.equipment_data.requirements = eq_data["requirements"]

                # Restore crafted stats if present
                if "crafted_stats" in item_data:
                    item_stack.crafted_stats = item_data["crafted_stats"]

                self.inventory.slots[idx] = item_stack

        # Restore equipment
        self.equipment.slots = {slot: None for slot in self.equipment.slots.keys()}
        equipment_data = player_data.get("equipment", {})
        equipment_db = EquipmentDatabase.get_instance()

        for slot_name, eq_data in equipment_data.items():
            if eq_data is None:
                self.equipment.slots[slot_name] = None
            elif isinstance(eq_data, dict):
                # New format: full equipment data with durability, enchantments, etc.
                from data.models.equipment import EquipmentItem

                # Convert damage list back to tuple if needed
                damage = eq_data.get("damage", [0, 0])
                if isinstance(damage, list):
                    damage = tuple(damage)

                equipment_item = EquipmentItem(
                    item_id=eq_data["item_id"],
                    name=eq_data.get("name", eq_data["item_id"]),
                    tier=eq_data.get("tier", 1),
                    rarity=eq_data.get("rarity", "common"),
                    slot=eq_data.get("slot", slot_name),
                    damage=damage,
                    defense=eq_data.get("defense", 0),
                    durability_current=eq_data.get("durability_current", 100),
                    durability_max=eq_data.get("durability_max", 100),
                    attack_speed=eq_data.get("attack_speed", 1.0),
                    weight=eq_data.get("weight", 1.0),
                    range=eq_data.get("range", 1.0),
                    hand_type=eq_data.get("hand_type", "default"),
                    item_type=eq_data.get("item_type", "weapon"),
                    icon_path=eq_data.get("icon_path")  # Restore icon path for proper PNG rendering
                )

                # Restore bonuses if present
                if "bonuses" in eq_data:
                    equipment_item.bonuses = eq_data["bonuses"]

                # Restore enchantments if present
                if "enchantments" in eq_data:
                    equipment_item.enchantments = eq_data["enchantments"]

                # Restore requirements if present
                if "requirements" in eq_data:
                    equipment_item.requirements = eq_data["requirements"]

                self.equipment.slots[slot_name] = equipment_item

            elif isinstance(eq_data, str):
                # Old format: just item_id (for backward compatibility)
                item_id = eq_data
                if equipment_db.is_equipment(item_id):
                    equipment_item = equipment_db.create_equipment_from_id(item_id)
                    self.equipment.slots[slot_name] = equipment_item

        # Restore skills
        self.skills.known_skills.clear()
        known_skills_data = player_data.get("known_skills", {})
        for skill_id, skill_info in known_skills_data.items():
            self.skills.learn_skill(skill_id, character=self, skip_checks=True)
            if skill_id in self.skills.known_skills:
                self.skills.known_skills[skill_id].level = skill_info.get("level", 1)
                self.skills.known_skills[skill_id].experience = skill_info.get("experience", 0)

        # Restore equipped skills
        self.skills.equipped_skills = [None] * 5
        equipped_data = player_data.get("equipped_skills", [None] * 5)
        for slot_idx, skill_id in enumerate(equipped_data):
            if skill_id and slot_idx < 5:
                self.skills.equip_skill(skill_id, slot_idx)

        # Restore titles
        title_db = TitleDatabase.get_instance()
        self.titles.earned_titles.clear()
        titles_data = player_data.get("titles", [])
        for title_id in titles_data:
            if title_id in title_db.titles:
                title = title_db.titles[title_id]
                if title not in self.titles.earned_titles:
                    self.titles.earned_titles.append(title)

        # Restore activities
        activities_data = player_data.get("activities", {})
        for activity_type, count in activities_data.items():
            self.activities.activity_counts[activity_type] = count

        # Final recalculation after all equipment and stats are restored
        self.recalculate_stats()

        # Initialize _selected_slot if not already set (for saves from before this feature)
        if not hasattr(self, '_selected_slot'):
            self._selected_slot = 'mainHand'

        print(f"✓ Character state restored: Level {self.leveling.level}, HP {self.health}/{self.max_health}")

    def recalculate_stats(self):
        """Recalculate character stats based on equipment, class, titles, etc."""
        # Start with base + stat bonuses
        stat_health = self.stats.get_flat_bonus('vitality', 'max_health')
        stat_mana = self.stats.get_flat_bonus('intelligence', 'mana')

        # Add class bonuses
        class_health = self.class_system.get_bonus('max_health')
        class_mana = self.class_system.get_bonus('max_mana')

        # Add equipment bonuses
        equip_bonuses = self.equipment.get_stat_bonuses()
        equip_health = equip_bonuses.get('max_health', 0)
        equip_mana = equip_bonuses.get('max_mana', 0)

        # Calculate new max values
        old_max_health = self.max_health
        old_max_mana = self.max_mana

        self.max_health = self.base_max_health + stat_health + class_health + equip_health
        self.max_mana = self.base_max_mana + stat_mana + class_mana + equip_mana

        # Scale current health/mana proportionally
        if old_max_health > 0:
            health_ratio = self.health / old_max_health
            self.health = min(self.max_health, int(self.max_health * health_ratio))
        if old_max_mana > 0:
            mana_ratio = self.mana / old_max_mana
            self.mana = min(self.max_mana, int(self.max_mana * mana_ratio))

    def allocate_stat_point(self, stat_name: str) -> bool:
        if self.leveling.unallocated_stat_points <= 0:
            return False
        if hasattr(self.stats, stat_name):
            setattr(self.stats, stat_name, getattr(self.stats, stat_name) + 1)
            self.leveling.unallocated_stat_points -= 1
            self.recalculate_stats()
            return True
        return False

    def update_knockback(self, dt: float, world: WorldSystem):
        """Apply knockback velocity over time (smooth forced movement)"""
        if self.knockback_duration_remaining > 0:
            # Apply knockback velocity to position
            dx = self.knockback_velocity_x * dt
            dy = self.knockback_velocity_y * dt

            # Modify position directly (don't use move() to avoid creating new Position object)
            new_x = self.position.x + dx
            new_y = self.position.y + dy

            # Clamp to world bounds
            new_x = max(0, min(Config.WORLD_SIZE - 1, new_x))
            new_y = max(0, min(Config.WORLD_SIZE - 1, new_y))

            # Check if walkable (optional - knockback can push through obstacles)
            new_pos = Position(new_x, new_y, self.position.z)
            if world.is_walkable(new_pos):
                self.position.x = new_x
                self.position.y = new_y
            # If not walkable, knockback is blocked but still counts as applied

            # Reduce remaining duration
            self.knockback_duration_remaining -= dt
            if self.knockback_duration_remaining <= 0:
                # Knockback finished
                self.knockback_velocity_x = 0.0
                self.knockback_velocity_y = 0.0
                self.knockback_duration_remaining = 0.0

    def move(self, dx: float, dy: float, world: WorldSystem) -> bool:
        # Check if immobilized by status effects
        if hasattr(self, 'status_manager') and self.status_manager.is_immobilized():
            return False

        # If being knocked back, reduce player movement significantly (knockback takes priority)
        if self.knockback_duration_remaining > 0:
            dx *= 0.1  # Reduce player input to 10% during knockback
            dy *= 0.1

        # Calculate movement speed from stats, class, and active buffs
        speed_mult = 1.0 + self.stats.get_bonus('agility') * 0.02 + self.class_system.get_bonus('movement_speed') + self.buffs.get_movement_speed_bonus()

        # Apply slow/chill speed reduction
        if hasattr(self, 'status_manager'):
            # Check for chill or slow status
            chill_effect = self.status_manager._find_effect('chill')
            if not chill_effect:
                chill_effect = self.status_manager._find_effect('slow')

            if chill_effect:
                slow_amount = chill_effect.params.get('slow_amount', 0.5)
                speed_mult *= (1.0 - slow_amount)  # Reduce speed by slow_amount

        # Apply movement speed enchantments from armor
        if hasattr(self, 'equipment'):
            armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']
            for slot in armor_slots:
                armor_piece = self.equipment.slots.get(slot)
                if armor_piece and hasattr(armor_piece, 'enchantments'):
                    for ench in armor_piece.enchantments:
                        effect = ench.get('effect', {})
                        if effect.get('type') == 'movement_speed_multiplier':
                            speed_mult += effect.get('value', 0.0)

        # Modify position directly instead of creating new Position object
        new_x = self.position.x + dx * speed_mult
        new_y = self.position.y + dy * speed_mult

        # Check bounds
        if new_x < 0 or new_x >= Config.WORLD_SIZE or new_y < 0 or new_y >= Config.WORLD_SIZE:
            return False

        # Check walkability
        new_pos = Position(new_x, new_y, self.position.z)
        if world.is_walkable(new_pos):
            self.position.x = new_x
            self.position.y = new_y
            self.facing = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")
            return True
        return False

    def is_in_range(self, target_position: Position) -> bool:
        return self.position.distance_to(target_position) <= self.interaction_range

    def get_equipped_tool(self, tool_type: str) -> Optional[EquipmentItem]:
        """
        Get the currently selected tool/weapon for use.

        If player has selected a specific slot via TAB, use that.
        Otherwise, default to the correct tool type (backward compatibility).

        Args:
            tool_type: The optimal tool type for this action ('axe' or 'pickaxe')

        Returns:
            The equipped item from the selected slot, or None if nothing equipped
        """
        # If player has explicitly selected a slot via TAB, use that
        if hasattr(self, '_selected_slot') and self._selected_slot:
            selected_item = self.equipment.slots.get(self._selected_slot)
            if selected_item:
                return selected_item

        # Otherwise, default to the correct tool type (backward compatibility)
        if tool_type in ['axe', 'pickaxe']:
            equipped_tool = self.equipment.slots.get(tool_type)
            if equipped_tool:
                return equipped_tool

        # Fallback to mainHand weapon if no tool equipped
        main_weapon = self.equipment.slots.get('mainHand')
        if main_weapon:
            return main_weapon

        return None

    def get_tool_effectiveness_for_action(self, equipment_item: EquipmentItem, action_type: str) -> float:
        """
        Calculate effectiveness multiplier based on tool/weapon type vs action.

        Tools and weapons are optimized for specific purposes and suffer penalties outside their domain:
        - Axes: 100% on trees, 25% on ore/enemies
        - Pickaxes: 100% on ore, 25% on trees/enemies
        - Weapons: 100% on enemies, 25% on trees/ore

        Args:
            equipment_item: The tool or weapon being used
            action_type: 'forestry', 'mining', or 'combat'

        Returns:
            float: Effectiveness multiplier (1.0 for optimal, 0.25 for sub-optimal)
        """
        # Get the slot to determine tool type
        tool_slot = equipment_item.slot

        # Axes are optimal for forestry
        if tool_slot == 'axe':
            if action_type == 'forestry':
                return 1.0  # Perfect for chopping trees
            else:
                return 0.25  # Poor for mining/combat

        # Pickaxes are optimal for mining
        elif tool_slot == 'pickaxe':
            if action_type == 'mining':
                return 1.0  # Perfect for mining ore
            else:
                return 0.25  # Poor for forestry/combat

        # Weapons (swords, daggers, etc.) are optimal for combat
        elif tool_slot in ['mainHand', 'offHand']:
            if action_type == 'combat':
                return 1.0  # Perfect for fighting
            else:
                return 0.25  # Poor for harvesting

        # Unknown tool type - assume full effectiveness
        return 1.0

    def can_harvest_resource(self, resource: NaturalResource) -> Tuple[bool, str]:
        # Get equipped tool for this resource type
        equipped_tool = self.get_equipped_tool(resource.required_tool)

        if not equipped_tool:
            tool_name = "axe" if resource.required_tool == "axe" else "pickaxe"
            return False, f"No {tool_name} equipped"
        if not self.is_in_range(resource.position):
            return False, "Too far away"

        # Check tool tier
        if equipped_tool.tier < resource.tier:
            return False, f"Tool tier too low (need T{resource.tier})"
        if equipped_tool.durability_current <= 0 and not Config.DEBUG_INFINITE_RESOURCES:
            return False, "Tool broken"
        return True, "OK"

    def _execute_aoe_gathering(self, primary_resource: NaturalResource, radius: int, all_resources: list, equipped_tool):
        """
        Execute AoE gathering (devastate effect) harvesting all resource nodes in radius
        Similar to combat's _execute_aoe_attack but for resource gathering
        """
        import math
        from core.debug_display import debug_print

        # Determine activity type from tool
        activity = 'mining' if primary_resource.required_tool == "pickaxe" else 'forestry'

        # Find all harvestable resources in radius (matching tool type)
        targets = []
        for res in all_resources:
            # Must match tool requirement and not be depleted
            if res.required_tool == primary_resource.required_tool and not res.depleted:
                dx = res.position.x - self.position.x
                dy = res.position.y - self.position.y
                distance = math.sqrt(dx*dx + dy*dy)
                if distance <= radius:
                    targets.append(res)

        if not targets:
            targets = [primary_resource]  # Fallback to primary resource

        print(f"\n🌀 CHAIN HARVEST (AoE Gathering): Harvesting {len(targets)} node(s) in {radius}-tile radius!")
        debug_print(f"🌀 Chain Harvest: {len(targets)} nodes in {radius}-tile radius")

        # Consume the devastate buff before gathering
        self.buffs.consume_buffs_for_action("gather", category=activity)

        # Harvest each resource node
        total_loot = []
        total_damage = 0
        any_crit = False

        for i, resource in enumerate(targets):
            # Call single-node harvest logic (reuse existing logic below)
            result = self._single_node_harvest(resource, equipped_tool, activity)
            if result:
                loot, dmg, is_crit = result
                if loot:
                    total_loot.extend(loot)
                total_damage += dmg
                any_crit = any_crit or is_crit

        print(f"   ✓ Total loot: {len(total_loot)} items from {len(targets)} nodes")
        return (total_loot, total_damage, any_crit) if total_loot else None

    def _single_node_harvest(self, resource: NaturalResource, equipped_tool, activity: str):
        """Single-node harvest logic (extracted from harvest_resource for reuse in AoE)"""
        # Calculate base damage from tool's damage stat
        if isinstance(equipped_tool.damage, tuple):
            base_damage = (equipped_tool.damage[0] + equipped_tool.damage[1]) // 2
        else:
            base_damage = equipped_tool.damage

        # Durability-based effectiveness
        durability_effectiveness = equipped_tool.get_effectiveness()

        # Tool type effectiveness
        tool_type_effectiveness = self.get_tool_effectiveness_for_action(equipped_tool, activity)

        # Combine effectiveness multipliers
        total_effectiveness = durability_effectiveness * tool_type_effectiveness

        stat_bonus = self.stats.get_bonus('strength' if activity == 'mining' else 'agility')
        title_bonus = self.titles.get_total_bonus(f'{activity}_damage')
        buff_bonus = self.buffs.get_damage_bonus(activity) if hasattr(self, 'buffs') else 0.0
        damage_mult = 1.0 + stat_bonus + title_bonus + buff_bonus

        # Check for Efficiency enchantment (gathering speed multiplier)
        # This should multiply the final damage, not add to the multiplier
        efficiency_mult = 1.0
        if hasattr(equipped_tool, 'enchantments') and equipped_tool.enchantments:
            for ench in equipped_tool.enchantments:
                effect = ench.get('effect', {})
                if effect.get('type') == 'gathering_speed_multiplier':
                    efficiency_bonus = effect.get('value', 0.0)
                    efficiency_mult = 1.0 + efficiency_bonus
                    # Visual feedback for efficiency
                    if efficiency_bonus > 0:
                        print(f"   ⚡ Efficiency: +{efficiency_bonus*100:.0f}% gathering speed")

        crit_chance = self.stats.luck * 0.02 + self.class_system.get_bonus('crit_chance')
        if hasattr(self, 'buffs'):
            crit_chance += self.buffs.get_total_bonus('pierce', activity)

        is_crit = random.random() < crit_chance
        # Apply efficiency as a true multiplicative bonus (40% efficiency = 40% more damage)
        damage = int(base_damage * total_effectiveness * damage_mult * efficiency_mult)
        actual_damage, depleted = resource.take_damage(damage, is_crit)

        # Reduce tool durability
        if not Config.DEBUG_INFINITE_DURABILITY:
            # -1 durability for proper use (correct tool type), -2 for improper use (wrong tool type)
            base_durability_loss = 1.0 if tool_type_effectiveness >= 1.0 else 2.0
            durability_loss = base_durability_loss

            # DEF stat reduces durability loss
            durability_loss *= self.stats.get_durability_loss_multiplier()

            # Unbreaking enchantment reduces durability loss
            if hasattr(equipped_tool, 'enchantments') and equipped_tool.enchantments:
                for ench in equipped_tool.enchantments:
                    effect = ench.get('effect', {})
                    if effect.get('type') == 'durability_multiplier':
                        reduction = effect.get('value', 0.0)
                        durability_loss *= (1.0 - reduction)

            equipped_tool.durability_current = max(0, equipped_tool.durability_current - durability_loss)

            # Only warn about improper use, low, or broken
            if base_durability_loss >= 2.0:
                print(f"   ⚠️ Improper tool use! {equipped_tool.name} loses extra durability ({equipped_tool.durability_current:.0f}/{equipped_tool.durability_max})")
            elif equipped_tool.durability_current == 0:
                print(f"   💥 {equipped_tool.name} has broken! (0/{equipped_tool.durability_max})")
            elif equipped_tool.durability_current <= equipped_tool.durability_max * 0.2:
                print(f"   ⚠️ {equipped_tool.name} durability low: {equipped_tool.durability_current:.0f}/{equipped_tool.durability_max}")

        loot = None
        if depleted:
            loot = resource.get_loot()
            processed_loot = []
            for item_id, qty in loot:
                # Luck-based bonus
                if random.random() < (self.stats.luck * 0.02 + self.class_system.get_bonus('resource_quality')):
                    qty += 1

                # Enrich buff bonuses
                if hasattr(self, 'buffs'):
                    enrich_bonus = int(self.buffs.get_total_bonus('enrich', activity))
                    if enrich_bonus > 0:
                        qty += enrich_bonus

                # Fortune enchantment bonus
                if hasattr(equipped_tool, 'enchantments') and equipped_tool.enchantments:
                    for ench in equipped_tool.enchantments:
                        effect = ench.get('effect', {})
                        if effect.get('type') == 'bonus_yield_chance':
                            bonus_chance = effect.get('value', 0.0)
                            # Roll for bonus yield
                            if random.random() < bonus_chance:
                                qty += 1
                                print(f"   💎 Fortune! +1 bonus {item_id}")
                                break  # Only proc once per item

                processed_loot.append((item_id, qty))
                self.inventory.add_item(item_id, qty)

            return (processed_loot, actual_damage, is_crit)

        return None

    def harvest_resource(self, resource: NaturalResource, nearby_resources: list = None):
        can_harvest, reason = self.can_harvest_resource(resource)
        if not can_harvest:
            return None

        # Get equipped tool
        equipped_tool = self.get_equipped_tool(resource.required_tool)
        if not equipped_tool:
            return None

        # Check for active devastate buffs (AoE gathering like Chain Harvest)
        if hasattr(self, 'buffs') and nearby_resources:
            # Determine activity type from resource
            activity = 'mining' if resource.required_tool == "pickaxe" else 'forestry'

            for buff in self.buffs.active_buffs:
                # Must be devastate type AND match the activity category (or be generic 'gathering')
                if buff.effect_type == "devastate" and (buff.category == activity or buff.category == "gathering"):
                    # Execute AoE gathering instead of single-node
                    result = self._execute_aoe_gathering(resource, int(buff.bonus_value), nearby_resources, equipped_tool)
                    # Still record activity/XP/titles for AoE gathering
                    self.activities.record_activity(activity, 1)
                    new_title = self.titles.check_for_title(activity, self.activities.get_count(activity))
                    if new_title:
                        print(f"🏆 TITLE EARNED: {new_title.name} - {new_title.bonus_description}")
                    leveled_up = self.leveling.add_exp({1: 10, 2: 40, 3: 160, 4: 640}.get(resource.tier, 10))
                    if leveled_up:
                        self.check_and_notify_new_skills()
                    self.time_since_last_damage_dealt = 0.0
                    return result

        # Normal single-node harvest - use extracted helper method
        activity = 'mining' if resource.required_tool == "pickaxe" else 'forestry'
        result = self._single_node_harvest(resource, equipped_tool, activity)

        # Track activities, titles, XP (same as before)
        self.activities.record_activity(activity, 1)
        new_title = self.titles.check_for_title(activity, self.activities.get_count(activity))
        if new_title:
            print(f"🏆 TITLE EARNED: {new_title.name} - {new_title.bonus_description}")

        leveled_up = self.leveling.add_exp({1: 10, 2: 40, 3: 160, 4: 640}.get(resource.tier, 10))
        if leveled_up:
            self.check_and_notify_new_skills()

        # Reset damage dealt timer (harvesting counts as dealing damage)
        self.time_since_last_damage_dealt = 0.0

        return result

    def switch_tool(self):
        """Cycle through equipped tools and weapons (mainHand/offHand → axe → pickaxe)"""
        # Build list of available items from equipment slots
        # Order: mainHand/offHand first (weapons), then tools (axe, pickaxe)
        available_items = []

        # Add equipped weapons first
        main_weapon = self.equipment.slots.get('mainHand')
        if main_weapon:
            available_items.append(('mainHand', main_weapon))

        off_weapon = self.equipment.slots.get('offHand')
        if off_weapon:
            available_items.append(('offHand', off_weapon))

        # Add equipped tools after weapons
        axe_tool = self.equipment.slots.get('axe')
        if axe_tool:
            available_items.append(('axe', axe_tool))

        pickaxe_tool = self.equipment.slots.get('pickaxe')
        if pickaxe_tool:
            available_items.append(('pickaxe', pickaxe_tool))

        if not available_items:
            return None

        # Find current index based on what's currently selected
        current_idx = -1
        if hasattr(self, '_selected_slot') and self._selected_slot:
            for i, (slot_name, item) in enumerate(available_items):
                if slot_name == self._selected_slot:
                    current_idx = i
                    break

        # Cycle to next
        next_idx = (current_idx + 1) % len(available_items)
        slot_name, next_item = available_items[next_idx]

        # Store the selected slot
        self._selected_slot = slot_name

        # Return descriptive name
        if slot_name in ['axe', 'pickaxe']:
            return f"{next_item.name} (Tool)"
        else:  # weapon
            return f"{next_item.name} (Weapon)"

    def interact_with_station(self, station: CraftingStation):
        if self.is_in_range(station.position):
            self.active_station = station
            self.crafting_ui_open = True

    def close_crafting_ui(self):
        self.active_station = None
        self.crafting_ui_open = False

    def update_health_regen(self, dt: float):
        """Update health and mana regeneration"""
        self.time_since_last_damage_taken += dt
        self.time_since_last_damage_dealt += dt

        # Health regeneration - 5 HP/sec after 5 seconds of no combat
        if (self.time_since_last_damage_taken >= self.health_regen_threshold and
            self.time_since_last_damage_dealt >= self.health_regen_threshold):
            if self.health < self.max_health:
                regen_amount = self.health_regen_rate * dt
                self.health = min(self.max_health, self.health + regen_amount)

        # HEALTH REGENERATION ENCHANTMENT: Always active bonus regen from armor
        if self.health < self.max_health:
            enchant_regen_bonus = 0.0
            armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']
            for slot in armor_slots:
                armor_piece = self.equipment.slots.get(slot)
                if armor_piece and hasattr(armor_piece, 'enchantments'):
                    for ench in armor_piece.enchantments:
                        effect = ench.get('effect', {})
                        if effect.get('type') == 'health_regeneration':
                            enchant_regen_bonus += effect.get('value', 1.0)  # HP per second

            if enchant_regen_bonus > 0:
                self.health = min(self.max_health, self.health + enchant_regen_bonus * dt)

        # Mana regeneration - 1% per second (always active)
        if self.mana < self.max_mana:
            mana_regen_amount = self.max_mana * 0.01 * dt  # 1% of max mana per second
            self.mana = min(self.max_mana, self.mana + mana_regen_amount)

    def update_buffs(self, dt: float):
        """Update all active buffs and status effects"""
        self.buffs.update(dt, character=self)
        self.skills.update_cooldowns(dt)

        # Process Self-Repair enchantments on equipment
        self._update_self_repair_enchantments(dt)

        # Update status effects
        if hasattr(self, 'status_manager'):
            self.status_manager.update(dt)

    def _update_self_repair_enchantments(self, dt: float):
        """Process Self-Repair enchantments on equipped items.

        Items with Self-Repair enchantment passively regenerate durability over time.
        """
        from core.config import Config
        if Config.DEBUG_INFINITE_RESOURCES:
            return

        # Check equipped items for self-repair enchantment
        if hasattr(self, 'equipment') and self.equipment:
            for slot_name, item in self.equipment.slots.items():
                if not item or not hasattr(item, 'enchantments'):
                    continue

                for ench in item.enchantments:
                    effect = ench.get('effect', {})
                    if effect.get('type') == 'durability_regeneration':
                        # Self-repair: regenerate durability over time
                        regen_rate = effect.get('value', 1.0)  # Durability per second
                        regen_amount = regen_rate * dt

                        if hasattr(item, 'durability_current') and hasattr(item, 'durability_max'):
                            if item.durability_current < item.durability_max:
                                item.durability_current = min(item.durability_max,
                                    item.durability_current + regen_amount)

        # Check tools for self-repair enchantment
        for tool_attr in ['axe', 'pickaxe']:
            if hasattr(self, tool_attr):
                tool = getattr(self, tool_attr)
                if not tool or not hasattr(tool, 'enchantments'):
                    continue

                enchantments = getattr(tool, 'enchantments', [])
                for ench in enchantments:
                    effect = ench.get('effect', {})
                    if effect.get('type') == 'durability_regeneration':
                        regen_rate = effect.get('value', 1.0)
                        regen_amount = regen_rate * dt

                        if hasattr(tool, 'durability_current') and hasattr(tool, 'durability_max'):
                            if tool.durability_current < tool.durability_max:
                                tool.durability_current = min(tool.durability_max,
                                    tool.durability_current + regen_amount)

    def toggle_stats_ui(self):
        self.stats_ui_open = not self.stats_ui_open

    def toggle_skills_ui(self):
        self.skills_ui_open = not self.skills_ui_open
        if not self.skills_ui_open:
            self.skills_menu_scroll_offset = 0  # Reset scroll when closing

    def toggle_equipment_ui(self):
        self.equipment_ui_open = not self.equipment_ui_open

    def select_class(self, class_def: ClassDefinition):
        self.class_system.set_class(class_def)
        self.recalculate_stats()
        self.health = self.max_health
        self.mana = self.max_mana
        print(f"✓ Class selected: {class_def.name}")

        # Grant starting skill if the class has one
        if class_def.starting_skill:
            # Map class skill names to actual skill IDs in skills-skills-1.JSON
            skill_mapping = {
                "battle_rage": "combat_strike",  # Warrior → Power Strike (T1 common)
                "forestry_frenzy": "lumberjacks_rhythm",  # Ranger → Lumberjack's Rhythm
                "alchemists_touch": "alchemists_insight",  # Scholar → Alchemist's Insight
                "smithing_focus": "smiths_focus",  # Artisan → Smith's Focus
                "treasure_hunters_luck": "treasure_sense",  # Scavenger → Treasure Sense (T2)
                "versatile_start": None  # Adventurer → Player chooses (handled separately)
            }

            requested_skill = class_def.starting_skill
            actual_skill_id = skill_mapping.get(requested_skill, requested_skill)

            # Get skill database instance (used by both paths below)
            skill_db = SkillDatabase.get_instance()

            if actual_skill_id:
                # Check if skill exists in database
                if actual_skill_id in skill_db.skills:
                    # Learn the skill (skip requirement checks for starting skills)
                    if self.skills.learn_skill(actual_skill_id, character=self, skip_checks=True):
                        print(f"   ✓ Learned starting skill: {skill_db.skills[actual_skill_id].name}")
                        # Auto-equip to slot 0
                        self.skills.equip_skill(actual_skill_id, 0)
                        print(f"   ✓ Equipped to hotbar slot 1")
                    else:
                        print(f"   ⚠ Skill {actual_skill_id} already known")
                else:
                    print(f"   ⚠ Warning: Starting skill '{actual_skill_id}' not found in skill database")
            elif requested_skill == "versatile_start":
                # Adventurer class - player should choose a T1 skill
                # For now, we'll give them sprint as a default, but ideally this should open a choice dialog
                default_skill = "sprint"
                if self.skills.learn_skill(default_skill, character=self, skip_checks=True):
                    print(f"   ✓ Learned starter skill: {skill_db.skills[default_skill].name}")
                    self.skills.equip_skill(default_skill, 0)
                    print(f"   ℹ Adventurer class: You can learn any skill! (Sprint given as default)")

    def check_and_notify_new_skills(self) -> List[str]:
        """
        Check if any new skills are available for the character to learn.
        Returns list of newly available skill IDs.
        """
        available_skills = self.skills.get_available_skills(self)
        if available_skills:
            skill_db = SkillDatabase.get_instance()
            print(f"📚 {len(available_skills)} new skill(s) available! Check Skills menu (K) to learn.")
            for skill_id in available_skills[:3]:  # Show first 3
                skill_def = skill_db.skills.get(skill_id)
                if skill_def:
                    print(f"   - {skill_def.name} (Tier {skill_def.tier})")
            if len(available_skills) > 3:
                print(f"   ... and {len(available_skills) - 3} more!")
        return available_skills

    def _determine_best_slot(self, equipment) -> str:
        """Intelligently determine which slot to equip an item to

        Rules:
        - 2H weapons: Always mainhand (will auto-unequip offhand), nothing allowed in offhand
        - Versatile weapons: Always mainhand, but allows 1H or shield in offhand
        - 1H weapons: Prefer offhand if empty, but never replace shields
        - Shields: Prefer offhand, replace shields
        - Default weapons: Always mainhand
        """
        # For non-weapon items, use their designated slot
        if equipment.slot not in ['mainHand', 'offHand']:
            return equipment.slot

        # For weapons/shields, determine best hand slot
        mainhand = self.equipment.slots.get('mainHand')
        offhand = self.equipment.slots.get('offHand')

        print(f"   🎯 _determine_best_slot for {equipment.name}")
        print(f"      - equipment.hand_type: {equipment.hand_type}")
        print(f"      - equipment.item_type: {equipment.item_type}")
        print(f"      - mainhand: {mainhand.name if mainhand else None} ({mainhand.hand_type if mainhand else None})")
        print(f"      - offhand: {offhand.name if offhand else None} ({offhand.item_type if offhand else None})")

        # If mainhand is empty, always equip there first
        if mainhand is None:
            print(f"      → mainHand (empty)")
            return 'mainHand'

        # 2H weapons always go to mainhand (caller will handle offhand unequip)
        if equipment.hand_type == "2H":
            print(f"      → mainHand (2H weapon)")
            return 'mainHand'

        # Check if mainhand allows offhand
        if mainhand.hand_type == "2H":
            # Mainhand is 2H, must replace it
            print(f"      → mainHand (replacing 2H mainhand)")
            return 'mainHand'

        # Mainhand allows dual-wielding, decide based on item type
        if equipment.item_type == "shield":
            # Shields always prefer offhand
            if offhand is None:
                print(f"      → offHand (shield, empty offhand)")
                return 'offHand'
            else:
                # Replace whatever is in offhand (shield or weapon)
                print(f"      → offHand (shield replacing {offhand.item_type})")
                return 'offHand'

        # Versatile weapons always go to mainhand (can be used with 1H in offhand)
        if equipment.hand_type == "versatile":
            print(f"      → mainHand (versatile weapon)")
            return 'mainHand'

        # Equipping a 1H weapon
        if equipment.hand_type == "1H":
            if offhand is None:
                # Offhand is empty, use it
                print(f"      → offHand (1H weapon, empty offhand)")
                return 'offHand'
            elif offhand.item_type == "shield":
                # Don't replace shield with weapon - replace mainhand weapon instead
                print(f"      → mainHand (1H weapon, shield in offhand)")
                return 'mainHand'
            else:
                # Offhand has a weapon, replace mainhand weapon
                # (User likely wants to replace what they're holding, not offhand)
                print(f"      → mainHand (1H weapon, weapon in offhand)")
                return 'mainHand'

        # Default weapons can't dual-wield, always mainhand
        print(f"      → mainHand (default weapon)")
        return 'mainHand'

    def try_equip_from_inventory(self, slot_index: int) -> Tuple[bool, str]:
        """Try to equip item from inventory slot"""
        print(f"\n🎯 try_equip_from_inventory called for slot {slot_index}")

        if slot_index < 0 or slot_index >= self.inventory.max_slots:
            print(f"   ❌ Invalid slot index")
            return False, "Invalid slot"

        item_stack = self.inventory.slots[slot_index]
        if not item_stack:
            print(f"   ❌ Empty slot")
            return False, "Empty slot"

        print(f"   📦 Item: {item_stack.item_id}")
        is_equip = item_stack.is_equipment()
        print(f"   🔍 is_equipment(): {is_equip}")

        if not is_equip:
            print(f"   ❌ Not equipment - FAILED")
            return False, "Not equipment"

        equipment = item_stack.get_equipment()
        print(f"   ⚙️  get_equipment(): {equipment}")

        if not equipment:
            print(f"   ❌ Invalid equipment - FAILED")
            return False, "Invalid equipment"

        print(f"   📋 Equipment details:")
        print(f"      - name: {equipment.name}")
        print(f"      - slot: {equipment.slot}")
        print(f"      - hand_type: {equipment.hand_type}")
        print(f"      - item_type: {equipment.item_type}")
        print(f"      - tier: {equipment.tier}")

        # Intelligently determine best slot for weapons/shields
        target_slot = self._determine_best_slot(equipment)
        print(f"   🎯 Target slot determined: {target_slot}")

        # Update equipment slot to target slot
        equipment.slot = target_slot

        # Auto-unequip offhand if equipping 2H weapon to mainhand
        offhand_item = None
        if target_slot == 'mainHand' and equipment.hand_type == "2H":
            offhand_item = self.equipment.slots.get('offHand')
            if offhand_item:
                print(f"   🔄 Auto-unequipping offhand for 2H weapon: {offhand_item.name}")
                # Try to add offhand to inventory first
                if not self.inventory.add_item(offhand_item.item_id, 1, offhand_item):
                    print(f"   ❌ Inventory full, cannot equip 2H weapon")
                    return False, "Inventory full (need space for offhand)"
                # Unequip offhand
                self.equipment.slots['offHand'] = None
                print(f"   ✅ Offhand unequipped and moved to inventory")

        # Try to equip
        print(f"   🔄 Calling equipment.equip()...")
        old_item, status = self.equipment.equip(equipment, self)
        print(f"   📤 equip() returned: old_item={old_item}, status={status}")

        if status != "OK":
            print(f"   ❌ Equip failed with status: {status}")
            # If we unequipped offhand, put it back
            if offhand_item:
                self.equipment.slots['offHand'] = offhand_item
                # Try to remove from inventory (may fail if inventory was modified)
                for i, stack in enumerate(self.inventory.slots):
                    if stack and stack.item_id == offhand_item.item_id and hasattr(stack, '_equipment_data'):
                        self.inventory.slots[i] = None
                        break
            return False, status

        # Remove from inventory
        self.inventory.slots[slot_index] = None
        print(f"   ✅ Removed from inventory slot {slot_index}")

        # If there was an old item, put it back in inventory (preserve equipment data)
        if old_item:
            if not self.inventory.add_item(old_item.item_id, 1, old_item):
                # Inventory full, swap back
                self.equipment.slots[target_slot] = old_item
                self.inventory.slots[slot_index] = item_stack
                self.recalculate_stats()
                print(f"   ❌ Inventory full, swapped back")
                return False, "Inventory full"
            print(f"   ↩️  Returned old item to inventory")

        print(f"   ✅ SUCCESS - Equipped {equipment.name} to {target_slot}")
        return True, "OK"

    def try_unequip_to_inventory(self, slot_name: str) -> Tuple[bool, str]:
        """Try to unequip item to inventory"""
        if slot_name not in self.equipment.slots:
            return False, "Invalid slot"

        item = self.equipment.slots[slot_name]
        if not item:
            return False, "Empty slot"

        # Try to add to inventory (preserve equipment data)
        if not self.inventory.add_item(item.item_id, 1, item):
            return False, "Inventory full"

        # Remove from equipment
        self.equipment.unequip(slot_name, self)

        return True, "OK"

    def take_damage(self, damage: float, damage_type: str = "physical", **kwargs):
        """
        Take damage from enemy

        Args:
            damage: Amount of damage to take
            damage_type: Type of damage (physical, fire, poison, etc.)
            **kwargs: Additional context (source, tags, context) for advanced damage systems
        """
        # Phase immunity - completely immune to damage
        if hasattr(self, 'is_phased') and self.is_phased:
            print(f"   👻 PHASED! Damage completely negated ({damage:.1f} damage avoided)")
            return

        # Shield/Barrier absorption
        if self.shield_amount > 0:
            absorbed = min(damage, self.shield_amount)
            self.shield_amount -= absorbed
            damage -= absorbed
            if absorbed > 0:
                print(f"   🛡️ Shield absorbed {absorbed:.1f} damage (Shield: {self.shield_amount:.1f} remaining)")

        # Apply remaining damage to health
        self.health -= damage

        # Apply armor durability loss when taking damage
        if damage > 0:  # Only lose durability if damage was actually taken
            from core.config import Config
            if not Config.DEBUG_INFINITE_DURABILITY:
                # DEF stat reduces durability loss
                durability_loss = 1.0 * self.stats.get_durability_loss_multiplier()

                armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']
                for slot in armor_slots:
                    armor_piece = self.equipment.slots.get(slot)
                    if armor_piece and hasattr(armor_piece, 'durability_current'):
                        # Apply Unbreaking enchantment
                        piece_loss = durability_loss
                        if hasattr(armor_piece, 'enchantments') and armor_piece.enchantments:
                            for ench in armor_piece.enchantments:
                                effect = ench.get('effect', {})
                                if effect.get('type') == 'durability_multiplier':
                                    reduction = effect.get('value', 0.0)
                                    piece_loss *= (1.0 - reduction)

                        armor_piece.durability_current = max(0, armor_piece.durability_current - piece_loss)

                        # Warn if armor is breaking (use effective max with VIT bonus)
                        effective_max = self.get_effective_max_durability(armor_piece)
                        if armor_piece.durability_current == 0:
                            print(f"   💥 {armor_piece.name} has broken!")
                        elif armor_piece.durability_current <= effective_max * 0.2:
                            print(f"   ⚠️ {armor_piece.name} durability low: {armor_piece.durability_current:.0f}/{effective_max}")

        if self.health <= 0:
            self.health = 0
            self._handle_death()

    def _handle_death(self):
        """Handle player death - respawn at spawn point"""
        print("💀 You died! Respawning...")
        self.health = self.max_health
        self.position = Position(50, 50, 0)  # Respawn at spawn
        # Keep all items and equipment (no death penalty)

    def get_effective_max_durability(self, item) -> int:
        """Get effective max durability for an item, including VIT bonus.

        VIT increases max durability by 1% per point.
        Example: Item with 100 max durability, 10 VIT = 110 effective max

        Args:
            item: Equipment or Tool with durability_max attribute

        Returns:
            int: Effective max durability
        """
        if not hasattr(item, 'durability_max'):
            return 100
        base_max = item.durability_max
        vit_mult = self.stats.get_durability_bonus_multiplier()
        return int(base_max * vit_mult)

    def get_durability_percent(self, item) -> float:
        """Get durability percentage for an item, accounting for VIT bonus.

        Args:
            item: Equipment or Tool with durability attributes

        Returns:
            float: Durability percentage (0.0 - 1.0+)
        """
        if not hasattr(item, 'durability_current') or not hasattr(item, 'durability_max'):
            return 1.0
        effective_max = self.get_effective_max_durability(item)
        if effective_max <= 0:
            return 0.0
        return item.durability_current / effective_max

    # ==================== WEIGHT SYSTEM ====================

    def get_total_weight(self) -> float:
        """Calculate total weight of all equipped items, tools, and inventory.

        Returns:
            float: Total weight in weight units
        """
        total = 0.0

        # Equipment weight (armor, weapons, accessories)
        if hasattr(self, 'equipment') and self.equipment:
            for slot_name, item in self.equipment.slots.items():
                if item and hasattr(item, 'weight'):
                    total += item.weight

        # Tool weight (axe, pickaxe)
        if hasattr(self, 'axe') and self.axe and hasattr(self.axe, 'weight'):
            total += self.axe.weight
        if hasattr(self, 'pickaxe') and self.pickaxe and hasattr(self.pickaxe, 'weight'):
            total += self.pickaxe.weight

        # Inventory weight (materials and equipment in inventory)
        if hasattr(self, 'inventory') and self.inventory:
            from data.databases.material_db import MaterialDatabase
            mat_db = MaterialDatabase.get_instance()

            for slot in self.inventory.slots:
                if slot and slot.item_id:
                    # Check if it's equipment (has equipment_data)
                    if slot.equipment_data and hasattr(slot.equipment_data, 'weight'):
                        total += slot.equipment_data.weight
                    else:
                        # It's a material - look up weight
                        mat = mat_db.get_material(slot.item_id)
                        if mat and hasattr(mat, 'weight'):
                            total += mat.weight * slot.quantity
                        else:
                            # Default material weight: 0.1 per item
                            total += 0.1 * slot.quantity

        return total

    def get_max_carry_capacity(self) -> float:
        """Calculate max carry capacity based on STR stat.

        Base capacity: 100 weight units
        STR bonus: +2% per point

        Returns:
            float: Maximum carry capacity
        """
        base_capacity = 100.0
        str_mult = self.stats.get_carry_capacity_multiplier()

        # Title/class bonuses could add here
        bonus = 0.0
        if hasattr(self, 'class_system'):
            bonus += self.class_system.get_bonus('carry_capacity')

        return base_capacity * str_mult + bonus

    def get_encumbrance_percent(self) -> float:
        """Get how far over capacity we are.

        Returns:
            float: 0.0 if at or under capacity, otherwise % over (0.1 = 10% over)
        """
        weight = self.get_total_weight()
        capacity = self.get_max_carry_capacity()
        if capacity <= 0:
            return 1.0
        ratio = weight / capacity
        return max(0.0, ratio - 1.0)

    def get_encumbrance_speed_penalty(self) -> float:
        """Get movement speed penalty from encumbrance.

        For every 1% over capacity, -2% movement speed.
        Example: 10% over = -20% speed (returns 0.8)
        Example: 50% over = -100% speed (returns 0.0)

        Returns:
            float: Speed multiplier (0.0 - 1.0)
        """
        over_percent = self.get_encumbrance_percent()
        if over_percent <= 0:
            return 1.0  # No penalty

        # -2% speed per 1% over capacity
        penalty = over_percent * 2.0
        return max(0.0, 1.0 - penalty)

    def is_over_encumbered(self) -> bool:
        """Check if character is over carry capacity.

        Returns:
            bool: True if over capacity
        """
        return self.get_encumbrance_percent() > 0

    def get_weight_ratio(self) -> float:
        """Get current weight as ratio of capacity.

        Returns:
            float: weight / capacity (1.0 = at capacity)
        """
        capacity = self.get_max_carry_capacity()
        if capacity <= 0:
            return 1.0
        return self.get_total_weight() / capacity

    def get_weapon_damage(self) -> float:
        """
        Get average weapon damage from currently selected weapon/tool INCLUDING ENCHANTMENTS.

        If player has selected a slot via TAB, use that slot's damage.
        Otherwise, use mainHand (backward compatibility).
        """
        # If player has selected a specific slot, get damage from that
        if hasattr(self, '_selected_slot') and self._selected_slot:
            selected_item = self.equipment.slots.get(self._selected_slot)
            if selected_item and selected_item.damage:
                # Use get_actual_damage() to include enchantment bonuses
                actual_damage = selected_item.get_actual_damage()
                if isinstance(actual_damage, tuple):
                    return (actual_damage[0] + actual_damage[1]) / 2.0
                else:
                    return float(actual_damage)

        # Otherwise, default to mainHand (backward compatibility)
        damage_range = self.equipment.get_weapon_damage()
        # Return average damage
        return (damage_range[0] + damage_range[1]) / 2.0

    def is_shield_active(self) -> bool:
        """Check if player has a shield equipped in offhand"""
        offhand = self.equipment.slots.get('offHand')
        return offhand is not None and offhand.item_type == 'shield'

    def get_shield_damage_reduction(self) -> float:
        """Get damage reduction multiplier from active shield (0.0-1.0)"""
        if not self.is_shield_active():
            return 0.0

        offhand = self.equipment.slots.get('offHand')
        # Shield uses its damage stat multiplier as damage reduction
        # E.g., if shield has damage multiplier 0.6, it reduces incoming damage by 40%
        damage_multiplier = offhand.stat_multipliers.get('damage', 1.0)

        # Convert to damage reduction (lower damage multiplier = higher reduction)
        # damage_multiplier of 0.6 means 40% reduction
        reduction = 1.0 - damage_multiplier
        return max(0.0, min(0.75, reduction))  # Cap at 75% reduction

    def update_attack_cooldown(self, dt: float):
        """Update attack cooldown timer"""
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
        if self.mainhand_cooldown > 0:
            self.mainhand_cooldown -= dt
        if self.offhand_cooldown > 0:
            self.offhand_cooldown -= dt

    def can_attack(self, hand: str = 'mainHand') -> bool:
        """Check if player can attack with specified hand (cooldown ready)"""
        if hand == 'mainHand':
            return self.mainhand_cooldown <= 0
        elif hand == 'offHand':
            return self.offhand_cooldown <= 0
        return self.attack_cooldown <= 0  # Legacy fallback

    def reset_attack_cooldown(self, is_weapon: bool = True, hand: str = 'mainHand'):
        """Reset attack cooldown based on attack speed and hand"""
        if is_weapon:
            # Get weapon-specific attack speed
            weapon_attack_speed = self.equipment.get_weapon_attack_speed(hand)

            # Weapon attack cooldown based on attack speed stat and weapon speed
            base_cooldown = 1.0
            attack_speed_bonus = self.stats.agility * 0.03  # 3% faster per AGI

            # Add weapon tag attack speed bonus (fast)
            weapon = self.equipment.slots.get(hand)
            if weapon:
                weapon_tags = weapon.get_metadata_tags()
                if weapon_tags:
                    from entities.components.weapon_tag_calculator import WeaponTagModifiers
                    tag_speed_bonus = WeaponTagModifiers.get_attack_speed_bonus(weapon_tags)
                    attack_speed_bonus += tag_speed_bonus

            cooldown = (base_cooldown / weapon_attack_speed) / (1.0 + attack_speed_bonus)

            if hand == 'mainHand':
                self.mainhand_cooldown = cooldown
            elif hand == 'offHand':
                self.offhand_cooldown = cooldown
            else:
                self.attack_cooldown = cooldown  # Legacy fallback
        else:
            # Tool attack cooldown (faster)
            if hand == 'mainHand':
                self.mainhand_cooldown = 0.5
            else:
                self.attack_cooldown = 0.5

    def use_consumable(self, item_id: str, crafted_stats: Dict = None, consume_from_inventory: bool = True) -> Tuple[bool, str]:
        """
        Use a consumable item from inventory (TAG-DRIVEN SYSTEM)

        Args:
            item_id: ID of the consumable item
            crafted_stats: Optional stats from alchemy minigame (potency, duration, quality)
            consume_from_inventory: If True, automatically remove item from inventory. If False, caller handles removal.

        Returns (success, message)
        """
        # Get item from database
        mat_db = MaterialDatabase.get_instance()
        item_def = mat_db.get_material(item_id)

        if not item_def:
            return False, f"Unknown item: {item_id}"

        # Check if item is consumable
        if item_def.category != "consumable":
            return False, f"{item_def.name} is not consumable"

        # Check if player has the item
        if not self.inventory.has_item(item_id, 1):
            return False, f"You don't have any {item_def.name}"

        # Use the tag-driven potion effect executor
        from systems.potion_system import get_potion_executor
        potion_executor = get_potion_executor()

        success, message = potion_executor.apply_potion_effect(self, item_def, crafted_stats)

        # LEGACY FALLBACK: If potion has no effect tags and executor didn't handle it
        if not item_def.effect_tags and not success:
            return False, f"Effect for {item_def.name} not yet implemented (no effectTags defined)"

        # If successful, consume the item (only if consume_from_inventory is True)
        if success and consume_from_inventory:
            self.inventory.remove_item(item_id, 1)
            print(f"✓ Used {item_def.name}: {message}")
        elif success:
            print(f"✓ Used {item_def.name}: {message} (caller handles inventory)")

        return success, message
