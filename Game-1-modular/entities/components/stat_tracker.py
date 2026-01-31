"""
Comprehensive Stat Tracking System
Tracks all player statistics at Minecraft-level detail for progression, analytics, and player profiling.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Set, Tuple, Optional, Any, List
from collections import defaultdict
import time


@dataclass
class StatEntry:
    """
    Generic statistical tracking entry for counting and aggregating numeric values.

    Used for tracking things like damage dealt, resources gathered, etc. where we want:
    - Count: How many times this occurred
    - Total: Sum of all values
    - Max: Best single instance
    - Last updated: When this was last modified
    """
    count: int = 0
    total_value: float = 0.0
    max_value: float = 0.0
    last_updated: Optional[float] = None  # Unix timestamp

    def record(self, value: float = 1.0):
        """
        Record a new occurrence.

        Args:
            value: The value to record (default 1.0 for simple counting)
        """
        self.count += 1
        self.total_value += value
        if value > self.max_value:
            self.max_value = value
        self.last_updated = time.time()

    def get_average(self) -> float:
        """Get average value (total / count)."""
        return self.total_value / self.count if self.count > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for saving."""
        return {
            "count": self.count,
            "total_value": self.total_value,
            "max_value": self.max_value,
            "last_updated": self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StatEntry':
        """Deserialize from dictionary."""
        return cls(
            count=data.get("count", 0),
            total_value=data.get("total_value", 0.0),
            max_value=data.get("max_value", 0.0),
            last_updated=data.get("last_updated")
        )


@dataclass
class CraftingEntry:
    """
    Specialized tracking for crafting recipes.

    Tracks success/failure rates, quality scores, timing, and output rarity distribution.
    """
    # Attempts
    total_attempts: int = 0
    successful_crafts: int = 0
    failed_crafts: int = 0

    # Quality
    perfect_crafts: int = 0
    first_try_bonuses: int = 0
    average_quality_score: float = 0.0
    best_quality_score: float = 0.0

    # Timing
    total_crafting_time: float = 0.0  # seconds
    fastest_craft_time: float = float('inf')

    # Output Quality
    common_crafted: int = 0
    uncommon_crafted: int = 0
    rare_crafted: int = 0
    legendary_crafted: int = 0

    # Materials Used
    materials_consumed: Dict[str, int] = field(default_factory=dict)

    def record_craft(self, success: bool, quality_score: float = 0.0,
                     craft_time: float = 0.0, output_rarity: str = "common",
                     is_perfect: bool = False, is_first_try: bool = False,
                     materials: Optional[Dict[str, int]] = None):
        """
        Record a crafting attempt.

        Args:
            success: Whether the craft succeeded
            quality_score: Minigame quality score (0.0-1.0)
            craft_time: Time taken in seconds
            output_rarity: Rarity of crafted item
            is_perfect: Whether this was a perfect craft
            is_first_try: Whether this got first-try bonus
            materials: Materials consumed {material_id: quantity}
        """
        self.total_attempts += 1

        if success:
            self.successful_crafts += 1

            # Quality tracking
            if is_perfect:
                self.perfect_crafts += 1
            if is_first_try:
                self.first_try_bonuses += 1

            # Update average quality score
            if quality_score > 0:
                total_quality = self.average_quality_score * (self.successful_crafts - 1)
                self.average_quality_score = (total_quality + quality_score) / self.successful_crafts
                if quality_score > self.best_quality_score:
                    self.best_quality_score = quality_score

            # Timing
            if craft_time > 0:
                self.total_crafting_time += craft_time
                if craft_time < self.fastest_craft_time:
                    self.fastest_craft_time = craft_time

            # Rarity tracking
            rarity_lower = output_rarity.lower()
            if rarity_lower == "common":
                self.common_crafted += 1
            elif rarity_lower == "uncommon":
                self.uncommon_crafted += 1
            elif rarity_lower == "rare":
                self.rare_crafted += 1
            elif rarity_lower == "legendary":
                self.legendary_crafted += 1

            # Materials
            if materials:
                for mat_id, qty in materials.items():
                    self.materials_consumed[mat_id] = self.materials_consumed.get(mat_id, 0) + qty
        else:
            self.failed_crafts += 1

    def get_success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return (self.successful_crafts / self.total_attempts * 100.0) if self.total_attempts > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_attempts": self.total_attempts,
            "successful_crafts": self.successful_crafts,
            "failed_crafts": self.failed_crafts,
            "perfect_crafts": self.perfect_crafts,
            "first_try_bonuses": self.first_try_bonuses,
            "average_quality_score": self.average_quality_score,
            "best_quality_score": self.best_quality_score,
            "total_crafting_time": self.total_crafting_time,
            "fastest_craft_time": self.fastest_craft_time if self.fastest_craft_time != float('inf') else 0.0,
            "common_crafted": self.common_crafted,
            "uncommon_crafted": self.uncommon_crafted,
            "rare_crafted": self.rare_crafted,
            "legendary_crafted": self.legendary_crafted,
            "materials_consumed": dict(self.materials_consumed)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CraftingEntry':
        """Deserialize from dictionary."""
        entry = cls(
            total_attempts=data.get("total_attempts", 0),
            successful_crafts=data.get("successful_crafts", 0),
            failed_crafts=data.get("failed_crafts", 0),
            perfect_crafts=data.get("perfect_crafts", 0),
            first_try_bonuses=data.get("first_try_bonuses", 0),
            average_quality_score=data.get("average_quality_score", 0.0),
            best_quality_score=data.get("best_quality_score", 0.0),
            total_crafting_time=data.get("total_crafting_time", 0.0),
            fastest_craft_time=data.get("fastest_craft_time", float('inf')),
            common_crafted=data.get("common_crafted", 0),
            uncommon_crafted=data.get("uncommon_crafted", 0),
            rare_crafted=data.get("rare_crafted", 0),
            legendary_crafted=data.get("legendary_crafted", 0),
            materials_consumed=data.get("materials_consumed", {})
        )
        # Handle infinity properly
        if entry.fastest_craft_time == 0.0:
            entry.fastest_craft_time = float('inf')
        return entry


@dataclass
class SkillStatEntry:
    """
    Specialized tracking for skill usage.

    Tracks usage frequency, effectiveness, mana costs, and impact.
    """
    times_used: int = 0
    total_value_delivered: float = 0.0  # damage, healing, buffs applied, etc.
    mana_spent: float = 0.0
    targets_affected: int = 0  # enemies hit, nodes harvested, etc.
    best_single_use: float = 0.0

    def record_use(self, value: float = 0.0, mana_cost: float = 0.0, targets: int = 0):
        """
        Record skill usage.

        Args:
            value: Value delivered (damage, healing, etc.)
            mana_cost: Mana consumed
            targets: Number of targets affected
        """
        self.times_used += 1
        self.total_value_delivered += value
        self.mana_spent += mana_cost
        self.targets_affected += targets
        if value > self.best_single_use:
            self.best_single_use = value

    def get_average_value(self) -> float:
        """Get average value per use."""
        return self.total_value_delivered / self.times_used if self.times_used > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "times_used": self.times_used,
            "total_value_delivered": self.total_value_delivered,
            "mana_spent": self.mana_spent,
            "targets_affected": self.targets_affected,
            "best_single_use": self.best_single_use
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillStatEntry':
        """Deserialize from dictionary."""
        return cls(
            times_used=data.get("times_used", 0),
            total_value_delivered=data.get("total_value_delivered", 0.0),
            mana_spent=data.get("mana_spent", 0.0),
            targets_affected=data.get("targets_affected", 0),
            best_single_use=data.get("best_single_use", 0.0)
        )


class StatTracker:
    """
    Comprehensive stat tracking system for player analytics and progression.

    Tracks 850-1000+ individual statistics across 13 categories:
    1. Gathering (resources, nodes, tools)
    2. Crafting (recipes, disciplines, quality)
    3. Combat (damage, kills, actions)
    4. Items (collection, usage, management)
    5. Skills (usage, progression)
    6. Exploration (distance, chunks, discovery)
    7. Economy (gold, trading)
    8. Progression (XP, titles, classes)
    9. Time (playtime, sessions)
    10. Records (streaks, bests)
    11. Social (quests, NPCs)
    12. Encyclopedia (discovery, completion)
    13. Miscellaneous (UI, saves, etc.)
    """

    def __init__(self):
        """Initialize all stat tracking categories."""
        # Session tracking
        self.session_start_time: Optional[float] = time.time()
        self.total_playtime_seconds: float = 0.0
        self.session_count: int = 0

        # CATEGORY 1: GATHERING STATISTICS
        self._init_gathering_stats()

        # CATEGORY 2: CRAFTING STATISTICS
        self._init_crafting_stats()

        # CATEGORY 3: COMBAT STATISTICS
        self._init_combat_stats()

        # CATEGORY 4: ITEM STATISTICS
        self._init_item_stats()

        # CATEGORY 5: SKILL STATISTICS
        self._init_skill_stats()

        # CATEGORY 6: EXPLORATION STATISTICS
        self._init_exploration_stats()

        # CATEGORY 7: ECONOMIC STATISTICS
        self._init_economy_stats()

        # CATEGORY 8: PROGRESSION STATISTICS
        self._init_progression_stats()

        # CATEGORY 9: TIME STATISTICS
        self._init_time_stats()

        # CATEGORY 10: RECORDS & STREAKS
        self._init_records_stats()

        # CATEGORY 11: SOCIAL STATISTICS
        self._init_social_stats()

        # CATEGORY 12: ENCYCLOPEDIA STATISTICS
        self._init_encyclopedia_stats()

        # CATEGORY 13: MISCELLANEOUS
        self._init_misc_stats()

        # CATEGORY 14: DUNGEON STATISTICS
        self._init_dungeon_stats()

    def _init_gathering_stats(self):
        """Initialize gathering statistics tracking."""
        # Per-resource tracking (will be populated dynamically)
        self.resources_gathered: Dict[str, StatEntry] = {}

        # Aggregate totals
        self.gathering_totals = {
            # By category
            "total_trees_chopped": 0,
            "total_ores_mined": 0,
            "total_stones_mined": 0,
            "total_plants_gathered": 0,
            "total_fish_caught": 0,

            # By tier
            "tier_1_resources_gathered": 0,
            "tier_2_resources_gathered": 0,
            "tier_3_resources_gathered": 0,
            "tier_4_resources_gathered": 0,

            # By element (for elemental-specific titles)
            "fire_resources_gathered": 0,
            "ice_resources_gathered": 0,
            "lightning_resources_gathered": 0,
            "nature_resources_gathered": 0,
            "shadow_resources_gathered": 0,
            "holy_resources_gathered": 0,

            # Quality metrics
            "total_critical_gathers": 0,
            "total_rare_drops_while_gathering": 0,
            "total_gathering_damage_dealt": 0.0,

            # Tool usage
            "axe_swings": 0,
            "pickaxe_swings": 0,
            "fishing_rod_casts": 0,
            "axe_durability_lost": 0.0,
            "pickaxe_durability_lost": 0.0,
            "fishing_rod_durability_lost": 0.0,
            "tools_repaired": 0,
            "tools_broken": 0
        }

        # Advanced gathering metrics
        self.gathering_advanced = {
            "fastest_tree_chop_time": float('inf'),
            "fastest_ore_mine_time": float('inf'),
            "most_resources_one_session": 0,
            "current_gather_streak": 0,
            "longest_gather_streak": 0,
            "aoe_gathers_performed": 0,
            "nodes_broken_via_aoe": 0,
            "distance_traveled_to_resources": 0.0,
            # Fishing-specific
            "largest_fish_caught": 0,
            "fish_catch_streak": 0,
            "longest_fish_catch_streak": 0,
            "rare_fish_caught": 0,
            "legendary_fish_caught": 0
        }

    def _init_crafting_stats(self):
        """Initialize crafting statistics tracking."""
        # Per-recipe tracking (will be populated dynamically)
        self.recipes_crafted: Dict[str, CraftingEntry] = {}

        # By discipline
        self.crafting_by_discipline = {
            "smithing": {
                "total_crafts": 0,
                "total_attempts": 0,
                "success_rate": 0.0,
                "perfect_crafts": 0,
                "first_try_bonuses": 0,
                "tier_1_crafts": 0,
                "tier_2_crafts": 0,
                "tier_3_crafts": 0,
                "tier_4_crafts": 0,
                "legendary_crafts": 0,
                "total_time_spent": 0.0,
                "average_craft_time": 0.0
            },
            "alchemy": {
                "total_crafts": 0,
                "total_attempts": 0,
                "success_rate": 0.0,
                "perfect_crafts": 0,
                "first_try_bonuses": 0,
                "tier_1_crafts": 0,
                "tier_2_crafts": 0,
                "tier_3_crafts": 0,
                "tier_4_crafts": 0,
                "legendary_crafts": 0,
                "total_time_spent": 0.0,
                "average_craft_time": 0.0
            },
            "refining": {
                "total_crafts": 0,
                "total_attempts": 0,
                "success_rate": 0.0,
                "perfect_crafts": 0,
                "first_try_bonuses": 0,
                "tier_1_crafts": 0,
                "tier_2_crafts": 0,
                "tier_3_crafts": 0,
                "tier_4_crafts": 0,
                "legendary_crafts": 0,
                "total_time_spent": 0.0,
                "average_craft_time": 0.0,
                "alloys_created": 0  # Special for refining
            },
            "engineering": {
                "total_crafts": 0,
                "total_attempts": 0,
                "success_rate": 0.0,
                "perfect_crafts": 0,
                "first_try_bonuses": 0,
                "tier_1_crafts": 0,
                "tier_2_crafts": 0,
                "tier_3_crafts": 0,
                "tier_4_crafts": 0,
                "legendary_crafts": 0,
                "total_time_spent": 0.0,
                "average_craft_time": 0.0,
                "traps_created": 0,
                "turrets_created": 0,
                "bombs_created": 0
            },
            "enchanting": {
                "total_crafts": 0,
                "total_attempts": 0,
                "success_rate": 0.0,
                "perfect_crafts": 0,
                "first_try_bonuses": 0,
                "tier_1_crafts": 0,
                "tier_2_crafts": 0,
                "tier_3_crafts": 0,
                "tier_4_crafts": 0,
                "legendary_crafts": 0,
                "total_time_spent": 0.0,
                "average_craft_time": 0.0,
                "enchantments_applied": 0
            }
        }

        # Advanced crafting metrics
        self.crafting_advanced = {
            "total_crafts_all_disciplines": 0,
            "total_crafting_time_all": 0.0,
            "tier_1_crafts_total": 0,
            "tier_2_crafts_total": 0,
            "tier_3_crafts_total": 0,
            "tier_4_crafts_total": 0,
            "common_items_crafted": 0,
            "uncommon_items_crafted": 0,
            "rare_items_crafted": 0,
            "legendary_items_crafted": 0,
            "total_perfect_crafts": 0,
            "total_first_try_bonuses": 0,
            "consecutive_first_try_bonuses": 0,
            "longest_first_try_streak": 0,
            "average_minigame_score": 0.0,
            "best_minigame_score": 0.0,
            "worst_minigame_score": 1.0,
            "total_materials_consumed": {},
            "most_used_material": "",
            "most_used_material_count": 0
        }

    def _init_combat_stats(self):
        """Initialize combat statistics tracking."""
        self.combat_damage = {
            # Damage dealt
            "total_damage_dealt": 0.0,
            "melee_damage_dealt": 0.0,
            "ranged_damage_dealt": 0.0,
            "magic_damage_dealt": 0.0,

            # Damage by element
            "physical_damage_dealt": 0.0,
            "fire_damage_dealt": 0.0,
            "ice_damage_dealt": 0.0,
            "lightning_damage_dealt": 0.0,
            "poison_damage_dealt": 0.0,
            "arcane_damage_dealt": 0.0,
            "shadow_damage_dealt": 0.0,
            "holy_damage_dealt": 0.0,

            # Damage taken
            "total_damage_taken": 0.0,
            "melee_damage_taken": 0.0,
            "ranged_damage_taken": 0.0,
            "magic_damage_taken": 0.0,

            # Damage by element received
            "physical_damage_taken": 0.0,
            "fire_damage_taken": 0.0,
            "ice_damage_taken": 0.0,
            "lightning_damage_taken": 0.0,
            "poison_damage_taken": 0.0,
            "arcane_damage_taken": 0.0,
            "shadow_damage_taken": 0.0,
            "holy_damage_taken": 0.0,

            # Records
            "highest_single_hit_dealt": 0.0,
            "highest_single_hit_taken": 0.0,
            "highest_dps_burst": 0.0
        }

        self.combat_kills = {
            "total_enemies_defeated": 0,
            "total_kills": 0,
            "tier_1_enemies_killed": 0,
            "tier_2_enemies_killed": 0,
            "tier_3_enemies_killed": 0,
            "tier_4_enemies_killed": 0,
            "boss_enemies_killed": 0,
            "dragon_boss_defeated": 0,
            "elite_enemies_killed": 0,
            "miniboss_enemies_killed": 0
        }

        self.combat_actions = {
            "total_attacks": 0,
            "melee_attacks": 0,
            "ranged_attacks": 0,
            "magic_attacks": 0,
            "critical_hits": 0,
            "critical_hit_rate": 0.0,
            "perfect_dodges": 0,
            "blocks": 0,
            "parries": 0,
            "sword_attacks": 0,
            "axe_attacks": 0,
            "bow_attacks": 0,
            "staff_attacks": 0,
            "dual_wield_attacks": 0,
            "unarmed_attacks": 0,
            "used_fire_weapon": False,
            "used_ice_weapon": False,
            "used_lightning_weapon": False,
            "fire_weapon_kills": 0,
            "ice_weapon_kills": 0,
            "lightning_weapon_kills": 0
        }

        self.combat_status_effects = {
            "status_effects_applied": {
                "burn": 0, "freeze": 0, "poison": 0, "stun": 0,
                "root": 0, "slow": 0, "bleed": 0, "shock": 0,
                "weaken": 0, "vulnerable": 0
            },
            "status_effects_received": {
                "burn": 0, "freeze": 0, "poison": 0, "stun": 0,
                "root": 0, "slow": 0, "bleed": 0, "shock": 0,
                "weaken": 0, "vulnerable": 0
            },
            "dot_damage_dealt": 0.0,
            "dot_damage_taken": 0.0,
            "enemies_cc_duration": 0.0,
            "player_cc_duration": 0.0
        }

        self.combat_survival = {
            "total_deaths": 0,
            "death_by_element": {},
            "total_healing_received": 0.0,
            "potions_consumed_in_combat": 0,
            "health_regenerated": 0.0,
            "lifesteal_healing": 0.0,
            "damage_blocked_by_armor": 0.0,
            "damage_blocked_by_shield": 0.0,
            "damage_reflected": 0.0,
            "longest_killstreak": 0,
            "current_killstreak": 0,
            "enemies_killed_without_damage": 0
        }

    def _init_item_stats(self):
        """Initialize item statistics tracking."""
        # Per-item tracking (populated dynamically)
        self.items_collected: Dict[str, int] = {}
        self.items_used: Dict[str, int] = {}

        self.item_collection = {
            "materials_collected": 0,
            "equipment_collected": 0,
            "consumables_collected": 0,
            "tools_collected": 0,
            "common_items_collected": 0,
            "uncommon_items_collected": 0,
            "rare_items_collected": 0,
            "legendary_items_collected": 0,
            "rare_drops_total": 0,
            "first_time_discoveries": 0
        }

        self.item_usage = {
            "total_potions_consumed": 0,
            "total_food_consumed": 0,
            "total_buffs_consumed": 0,
            "potions_used_in_combat": 0,
            "potions_used_out_combat": 0
        }

        self.item_management = {
            "items_picked_up": 0,
            "items_dropped": 0,
            "items_destroyed": 0,
            "inventory_sorts": 0,
            "equipment_equipped": {},
            "equipment_unequipped": {},
            "total_equipment_swaps": 0,
            "items_repaired": 0,
            "durability_restored": 0.0,
            "repair_materials_used": {}
        }

    def _init_skill_stats(self):
        """Initialize skill statistics tracking."""
        # Per-skill tracking (populated dynamically)
        self.skills_used: Dict[str, SkillStatEntry] = {}

        self.skill_usage = {
            "total_skills_activated": 0,
            "gathering_skills_used": 0,
            "combat_skills_used": 0,
            "crafting_skills_used": 0,
            "utility_skills_used": 0,
            "total_mana_spent": 0.0,
            "total_mana_regenerated": 0.0,
            "skills_on_cooldown_missed": 0
        }

        self.skill_progression = {
            "skills_learned": 0,
            "skills_unlocked_via_quest": 0,
            "skills_unlocked_via_milestone": 0,
            "skills_unlocked_via_level": 0,
            "skills_unlocked_via_purchase": 0,
            "skills_unlocked_via_title": 0,
            "skill_levels_gained": 0,
            "max_level_skills": 0,
            "total_skill_exp_earned": {}
        }

    def _init_exploration_stats(self):
        """Initialize exploration statistics tracking."""
        self.distance_traveled = {
            "total_distance": 0.0,
            "distance_walked": 0.0,
            "distance_sprinted": 0.0,
            "distance_while_encumbered": 0.0,
            "distance_in_forest": 0.0,
            "distance_in_mountains": 0.0,
            "distance_in_plains": 0.0,
            "distance_in_caves": 0.0
        }

        # Use list for serialization (converted to set at runtime)
        self._unique_chunks_visited_list: List[Tuple[int, int]] = []
        self._unique_chunks_visited: Set[Tuple[int, int]] = set()

        self.exploration = {
            "unique_chunks_visited": 0,
            "total_chunk_entries": 0,
            "furthest_distance_from_spawn": 0.0,
            "resource_nodes_discovered": 0,
            "crafting_stations_discovered": 0,
            "npcs_met": 0,
            "landmarks_discovered": 0,
            "dungeons_discovered": 0,
            "bosses_discovered": 0
        }

    def _init_economy_stats(self):
        """Initialize economy statistics tracking."""
        self.economy = {
            "total_gold_earned": 0,
            "total_gold_spent": 0,
            "current_gold": 0,
            "highest_gold_balance": 0,
            "trades_made": 0,
            "items_bought": 0,
            "items_sold": 0,
            "gold_from_combat": 0,
            "gold_from_quests": 0,
            "gold_from_selling": 0,
            "gold_spent_on_skills": 0,
            "gold_spent_on_items": 0,
            "gold_spent_on_repairs": 0
        }

    def _init_progression_stats(self):
        """Initialize progression statistics tracking."""
        self.experience_stats = {
            "total_exp_earned": 0,
            "total_exp_to_next_level": 0,
            "exp_from_gathering": 0,
            "exp_from_crafting": 0,
            "exp_from_combat": 0,
            "exp_from_quests": 0,
            "exp_from_exploration": 0,
            "exp_from_fishing": 0,
            "total_levels_gained": 0,
            "highest_level_reached": 0,
            "stat_points_allocated": 0,
            "stat_points_remaining": 0
        }

        self.progression_milestones = {
            "titles_earned": 0,
            "novice_titles": 0,
            "apprentice_titles": 0,
            "journeyman_titles": 0,
            "expert_titles": 0,
            "master_titles": 0,
            "hidden_titles": 0,
            "class_selected": "",
            "class_changes": 0,
            "achievements_unlocked": 0
        }

    def _init_time_stats(self):
        """Initialize time statistics tracking."""
        self.time_stats = {
            "total_playtime_seconds": 0.0,
            "session_count": 0,
            "current_session_time": 0.0,
            "longest_session": 0.0,
            "average_session_length": 0.0,
            "time_spent_gathering": 0.0,
            "time_spent_crafting": 0.0,
            "time_spent_in_combat": 0.0,
            "time_spent_exploring": 0.0,
            "time_spent_in_menus": 0.0,
            "time_spent_idle": 0.0,
            "first_played_timestamp": None,
            "last_played_timestamp": None,
            "days_since_first_played": 0
        }

    def _init_records_stats(self):
        """Initialize records and streaks tracking."""
        self.records = {
            "highest_damage_single_hit": 0.0,
            "highest_dps_5_seconds": 0.0,
            "longest_combat_duration": 0.0,
            "fastest_boss_kill": float('inf'),
            "fastest_craft": float('inf'),
            "best_minigame_score": 0.0,
            "longest_crafting_session": 0,
            "most_resources_single_node": 0,
            "fastest_node_break": float('inf'),
            "longest_gathering_session": 0,
            "current_first_try_streak": 0,
            "longest_first_try_streak": 0,
            "current_no_damage_streak": 0,
            "longest_killstreak": 0,
            "best_exp_per_hour": 0.0,
            "best_gold_per_hour": 0.0,
            "best_crafts_per_hour": 0
        }

    def _init_social_stats(self):
        """Initialize social/quest statistics tracking."""
        self.social_stats = {
            "npcs_met": 0,
            "npc_dialogues_completed": 0,
            "npc_reputation": {},
            "quests_started": 0,
            "quests_completed": 0,
            "quests_failed": 0,
            "quest_exp_earned": 0,
            "quest_gold_earned": 0,
            "gathering_quests_completed": 0,
            "combat_quests_completed": 0,
            "crafting_quests_completed": 0,
            "exploration_quests_completed": 0
        }

    def _init_encyclopedia_stats(self):
        """Initialize encyclopedia/discovery statistics tracking."""
        self.encyclopedia_stats = {
            "unique_items_discovered": 0,
            "unique_recipes_discovered": 0,
            "unique_enemies_encountered": 0,
            "unique_resources_found": 0,
            "encyclopedia_completion_percent": 0.0,
            "materials_encyclopedia_complete": False,
            "equipment_encyclopedia_complete": False,
            "recipes_encyclopedia_complete": False,
            "first_time_item_finds": 0,
            "first_time_recipe_unlocks": 0
        }

    def _init_misc_stats(self):
        """Initialize miscellaneous statistics tracking."""
        self.misc_stats = {
            "inventory_opens": 0,
            "crafting_menu_opens": 0,
            "skill_menu_opens": 0,
            "map_opens": 0,
            "manual_saves": 0,
            "auto_saves": 0,
            "game_loads": 0,
            "debug_mode_activations": 0,
            "debug_resources_spawned": 0,
            "jumps": 0,
            "emotes_used": 0,
            "screenshots_taken": 0
        }

        # Barrier and collision system stats
        self.barrier_stats = {
            "barriers_placed": 0,
            "barriers_picked_up": 0,
            "attacks_blocked_by_barriers": 0,
            "enemy_attacks_blocked": 0,
            "player_attacks_blocked": 0,
            "turret_attacks_blocked": 0
        }
        # Per-material barrier placement tracking
        self.barriers_by_material: Dict[str, int] = {}

    def _init_dungeon_stats(self):
        """Initialize dungeon statistics tracking."""
        self.dungeon_stats = {
            # Overall counts
            "dungeons_entered": 0,
            "dungeons_completed": 0,
            "dungeons_abandoned": 0,

            # By rarity
            "common_dungeons_completed": 0,
            "uncommon_dungeons_completed": 0,
            "rare_dungeons_completed": 0,
            "epic_dungeons_completed": 0,
            "legendary_dungeons_completed": 0,
            "unique_dungeons_completed": 0,

            # Combat in dungeons
            "dungeon_enemies_killed": 0,
            "dungeon_deaths": 0,
            "waves_completed": 0,

            # Loot
            "dungeon_chests_opened": 0,
            "dungeon_items_received": 0,

            # Records
            "fastest_dungeon_clear": float('inf'),
            "highest_rarity_cleared": "",
            "most_enemies_killed_single_dungeon": 0,

            # EXP from dungeons
            "total_dungeon_exp_earned": 0
        }

    # =========================================================================
    # RECORDING METHODS
    # =========================================================================

    def start_session(self):
        """Start a new play session."""
        self.session_start_time = time.time()
        self.session_count += 1
        self.time_stats["session_count"] = self.session_count

        if self.time_stats["first_played_timestamp"] is None:
            self.time_stats["first_played_timestamp"] = self.session_start_time

    def update_playtime(self, dt: float):
        """
        Update session playtime.

        Args:
            dt: Delta time in seconds since last update
        """
        if self.session_start_time is not None:
            self.total_playtime_seconds += dt
            self.time_stats["total_playtime_seconds"] = self.total_playtime_seconds

            current_session = time.time() - self.session_start_time
            self.time_stats["current_session_time"] = current_session

            if current_session > self.time_stats["longest_session"]:
                self.time_stats["longest_session"] = current_session

            if self.session_count > 0:
                self.time_stats["average_session_length"] = self.total_playtime_seconds / self.session_count

            self.time_stats["last_played_timestamp"] = time.time()

    def record_resource_gathered(self, resource_id: str, quantity: int = 1,
                                  tier: int = 1, category: str = "ore",
                                  element: Optional[str] = None, is_crit: bool = False,
                                  is_rare_drop: bool = False):
        """
        Record resource gathering event.

        Args:
            resource_id: Resource type identifier (e.g., "iron_ore_node")
            quantity: Number of items obtained
            tier: Resource tier (1-4)
            category: Resource category (tree/ore/stone/plant)
            element: Optional element type (fire/ice/lightning/etc)
            is_crit: Whether this was a critical gather
            is_rare_drop: Whether rare drop occurred
        """
        # Per-resource tracking
        if resource_id not in self.resources_gathered:
            self.resources_gathered[resource_id] = StatEntry()
        self.resources_gathered[resource_id].record(quantity)

        # Category totals
        category_lower = category.lower()
        if "tree" in category_lower or "wood" in category_lower:
            self.gathering_totals["total_trees_chopped"] += 1
        elif "ore" in category_lower:
            self.gathering_totals["total_ores_mined"] += 1
        elif "stone" in category_lower or "rock" in category_lower:
            self.gathering_totals["total_stones_mined"] += 1
        elif "plant" in category_lower or "herb" in category_lower:
            self.gathering_totals["total_plants_gathered"] += 1
        elif "fish" in category_lower or "fishing" in category_lower:
            self.gathering_totals["total_fish_caught"] += quantity
            self.gathering_totals["fishing_rod_casts"] += 1

        # Tier tracking
        tier_key = f"tier_{tier}_resources_gathered"
        if tier_key in self.gathering_totals:
            self.gathering_totals[tier_key] += 1

        # Element tracking
        if element:
            element_key = f"{element.lower()}_resources_gathered"
            if element_key in self.gathering_totals:
                self.gathering_totals[element_key] += 1

        # Quality tracking
        if is_crit:
            self.gathering_totals["total_critical_gathers"] += 1
        if is_rare_drop:
            self.gathering_totals["total_rare_drops_while_gathering"] += 1
            self.item_collection["rare_drops_total"] += 1

    def record_crafting(self, recipe_id: str, discipline: str, success: bool,
                        tier: int = 1, quality_score: float = 0.0,
                        craft_time: float = 0.0, output_rarity: str = "common",
                        is_perfect: bool = False, is_first_try: bool = False,
                        materials: Optional[Dict[str, int]] = None):
        """
        Record crafting event.

        Args:
            recipe_id: Recipe identifier
            discipline: Crafting discipline (smithing/alchemy/refining/engineering/enchanting)
            success: Whether craft succeeded
            tier: Recipe tier (1-4)
            quality_score: Minigame score (0.0-1.0)
            craft_time: Time taken in seconds
            output_rarity: Output item rarity
            is_perfect: Perfect craft flag
            is_first_try: First-try bonus flag
            materials: Materials consumed {material_id: quantity}
        """
        # Per-recipe tracking
        if recipe_id not in self.recipes_crafted:
            self.recipes_crafted[recipe_id] = CraftingEntry()
        self.recipes_crafted[recipe_id].record_craft(
            success, quality_score, craft_time, output_rarity,
            is_perfect, is_first_try, materials
        )

        # Discipline tracking
        discipline_lower = discipline.lower()
        if discipline_lower in self.crafting_by_discipline:
            disc = self.crafting_by_discipline[discipline_lower]
            disc["total_attempts"] += 1

            if success:
                disc["total_crafts"] += 1
                disc["total_time_spent"] += craft_time

                if disc["total_crafts"] > 0:
                    disc["average_craft_time"] = disc["total_time_spent"] / disc["total_crafts"]
                    disc["success_rate"] = (disc["total_crafts"] / disc["total_attempts"]) * 100.0

                if is_perfect:
                    disc["perfect_crafts"] += 1
                if is_first_try:
                    disc["first_try_bonuses"] += 1

                # Tier tracking
                tier_key = f"tier_{tier}_crafts"
                if tier_key in disc:
                    disc[tier_key] += 1

                # Rarity tracking
                if output_rarity.lower() == "legendary":
                    disc["legendary_crafts"] += 1

                # Special discipline tracking
                if discipline_lower == "refining" and materials:
                    # Check if this is an alloy (multiple metal inputs)
                    metal_count = sum(1 for mat_id in materials.keys() if "ore" in mat_id.lower() or "ingot" in mat_id.lower())
                    if metal_count >= 2:
                        disc["alloys_created"] += 1

        # Advanced totals
        self.crafting_advanced["total_crafts_all_disciplines"] += 1 if success else 0
        self.crafting_advanced["total_crafting_time_all"] += craft_time

        if success:
            tier_key = f"tier_{tier}_crafts_total"
            if tier_key in self.crafting_advanced:
                self.crafting_advanced[tier_key] += 1

            rarity_key = f"{output_rarity.lower()}_items_crafted"
            if rarity_key in self.crafting_advanced:
                self.crafting_advanced[rarity_key] += 1

            if is_perfect:
                self.crafting_advanced["total_perfect_crafts"] += 1
            if is_first_try:
                self.crafting_advanced["total_first_try_bonuses"] += 1
                self.crafting_advanced["consecutive_first_try_bonuses"] += 1
                if self.crafting_advanced["consecutive_first_try_bonuses"] > self.crafting_advanced["longest_first_try_streak"]:
                    self.crafting_advanced["longest_first_try_streak"] = self.crafting_advanced["consecutive_first_try_bonuses"]
            else:
                self.crafting_advanced["consecutive_first_try_bonuses"] = 0

            # Minigame score tracking
            if quality_score > 0:
                if quality_score > self.crafting_advanced["best_minigame_score"]:
                    self.crafting_advanced["best_minigame_score"] = quality_score
                if quality_score < self.crafting_advanced["worst_minigame_score"]:
                    self.crafting_advanced["worst_minigame_score"] = quality_score

            # Material tracking
            if materials:
                for mat_id, qty in materials.items():
                    self.crafting_advanced["total_materials_consumed"][mat_id] = \
                        self.crafting_advanced["total_materials_consumed"].get(mat_id, 0) + qty

                    # Track most used material
                    if self.crafting_advanced["total_materials_consumed"][mat_id] > self.crafting_advanced["most_used_material_count"]:
                        self.crafting_advanced["most_used_material"] = mat_id
                        self.crafting_advanced["most_used_material_count"] = self.crafting_advanced["total_materials_consumed"][mat_id]

    def record_damage_dealt(self, amount: float, damage_type: str = "physical",
                            attack_type: str = "melee", was_crit: bool = False,
                            weapon_element: Optional[str] = None):
        """
        Record damage dealt to enemy.

        Args:
            amount: Damage amount
            damage_type: Element type (physical/fire/ice/etc)
            attack_type: Attack type (melee/ranged/magic)
            was_crit: Whether this was a critical hit
            weapon_element: Element of weapon used
        """
        # Total damage
        self.combat_damage["total_damage_dealt"] += amount

        # Attack type
        attack_key = f"{attack_type.lower()}_damage_dealt"
        if attack_key in self.combat_damage:
            self.combat_damage[attack_key] += amount

        # Element type
        element_key = f"{damage_type.lower()}_damage_dealt"
        if element_key in self.combat_damage:
            self.combat_damage[element_key] += amount

        # Records
        if amount > self.combat_damage["highest_single_hit_dealt"]:
            self.combat_damage["highest_single_hit_dealt"] = amount

        # Actions
        self.combat_actions["total_attacks"] += 1
        attack_action_key = f"{attack_type.lower()}_attacks"
        if attack_action_key in self.combat_actions:
            self.combat_actions[attack_action_key] += 1

        if was_crit:
            self.combat_actions["critical_hits"] += 1

        # Weapon element tracking
        if weapon_element:
            element_lower = weapon_element.lower()
            if element_lower == "fire":
                self.combat_actions["used_fire_weapon"] = True
            elif element_lower == "ice":
                self.combat_actions["used_ice_weapon"] = True
            elif element_lower == "lightning":
                self.combat_actions["used_lightning_weapon"] = True

        # Update crit rate
        if self.combat_actions["total_attacks"] > 0:
            self.combat_actions["critical_hit_rate"] = \
                (self.combat_actions["critical_hits"] / self.combat_actions["total_attacks"]) * 100.0

    def record_damage_taken(self, amount: float, damage_type: str = "physical",
                            attack_type: str = "melee"):
        """
        Record damage taken from enemy.

        Args:
            amount: Damage amount
            damage_type: Element type
            attack_type: Attack type
        """
        self.combat_damage["total_damage_taken"] += amount

        attack_key = f"{attack_type.lower()}_damage_taken"
        if attack_key in self.combat_damage:
            self.combat_damage[attack_key] += amount

        element_key = f"{damage_type.lower()}_damage_taken"
        if element_key in self.combat_damage:
            self.combat_damage[element_key] += amount

        if amount > self.combat_damage["highest_single_hit_taken"]:
            self.combat_damage["highest_single_hit_taken"] = amount

        # Reset no-damage streak
        self.combat_survival["current_killstreak"] = 0

    def record_enemy_killed(self, tier: int = 1, is_boss: bool = False,
                            is_dragon: bool = False, weapon_element: Optional[str] = None):
        """
        Record enemy kill.

        Args:
            tier: Enemy tier (1-4)
            is_boss: Whether this was a boss
            is_dragon: Whether this was a dragon
            weapon_element: Element of weapon used for kill
        """
        self.combat_kills["total_enemies_defeated"] += 1
        self.combat_kills["total_kills"] += 1

        tier_key = f"tier_{tier}_enemies_killed"
        if tier_key in self.combat_kills:
            self.combat_kills[tier_key] += 1

        if is_boss:
            self.combat_kills["boss_enemies_killed"] += 1
        if is_dragon:
            self.combat_kills["dragon_boss_defeated"] += 1

        # Killstreak
        self.combat_survival["current_killstreak"] += 1
        if self.combat_survival["current_killstreak"] > self.combat_survival["longest_killstreak"]:
            self.combat_survival["longest_killstreak"] = self.combat_survival["current_killstreak"]

        # Weapon element kills
        if weapon_element:
            element_lower = weapon_element.lower()
            element_kill_key = f"{element_lower}_weapon_kills"
            if element_kill_key in self.combat_actions:
                self.combat_actions[element_kill_key] += 1

    def record_status_effect(self, effect_tag: str, applied_to_enemy: bool = True):
        """
        Record status effect application.

        Args:
            effect_tag: Status effect tag (burn/freeze/stun/etc)
            applied_to_enemy: True if applied to enemy, False if received
        """
        effect_lower = effect_tag.lower()

        if applied_to_enemy:
            if effect_lower in self.combat_status_effects["status_effects_applied"]:
                self.combat_status_effects["status_effects_applied"][effect_lower] += 1
        else:
            if effect_lower in self.combat_status_effects["status_effects_received"]:
                self.combat_status_effects["status_effects_received"][effect_lower] += 1

    def record_item_collected(self, item_id: str, quantity: int = 1,
                              category: str = "material", rarity: str = "common",
                              is_first_time: bool = False, is_rare_drop: bool = False):
        """
        Record item collection.

        Args:
            item_id: Item identifier
            quantity: Quantity collected
            category: Item category (material/equipment/consumable/tool)
            rarity: Item rarity
            is_first_time: First time discovering this item
            is_rare_drop: Whether this was a rare drop
        """
        self.items_collected[item_id] = self.items_collected.get(item_id, 0) + quantity

        category_key = f"{category.lower()}s_collected"
        if category_key in self.item_collection:
            self.item_collection[category_key] += quantity

        rarity_key = f"{rarity.lower()}_items_collected"
        if rarity_key in self.item_collection:
            self.item_collection[rarity_key] += quantity

        if is_first_time:
            self.item_collection["first_time_discoveries"] += 1
            self.encyclopedia_stats["first_time_item_finds"] += 1

        if is_rare_drop:
            self.item_collection["rare_drops_total"] += 1

        self.item_management["items_picked_up"] += quantity

    def record_item_used(self, item_id: str, quantity: int = 1,
                         item_type: str = "consumable", in_combat: bool = False):
        """
        Record item usage/consumption.

        Args:
            item_id: Item identifier
            quantity: Quantity used
            item_type: Type of item (potion/food/buff/other)
            in_combat: Whether item was used during combat
        """
        self.items_used[item_id] = self.items_used.get(item_id, 0) + quantity

        # Update consumption stats by type
        if "potion" in item_type.lower():
            self.item_usage["total_potions_consumed"] += quantity
            if in_combat:
                self.item_usage["potions_used_in_combat"] += quantity
            else:
                self.item_usage["potions_used_out_combat"] += quantity
        elif "food" in item_type.lower():
            self.item_usage["total_food_consumed"] += quantity
        elif "buff" in item_type.lower():
            self.item_usage["total_buffs_consumed"] += quantity

    def record_item_dropped(self, item_id: str, quantity: int = 1, destroyed: bool = False):
        """
        Record items dropped or destroyed.

        Args:
            item_id: Item identifier
            quantity: Quantity dropped/destroyed
            destroyed: True if destroyed, False if dropped
        """
        if destroyed:
            self.item_management["items_destroyed"] += quantity
        else:
            self.item_management["items_dropped"] += quantity

    def record_skill_used(self, skill_id: str, value: float = 0.0,
                          mana_cost: float = 0.0, targets: int = 0,
                          category: str = "utility"):
        """
        Record skill usage.

        Args:
            skill_id: Skill identifier
            value: Value delivered (damage/healing/etc)
            mana_cost: Mana consumed
            targets: Number of targets affected
            category: Skill category
        """
        if skill_id not in self.skills_used:
            self.skills_used[skill_id] = SkillStatEntry()
        self.skills_used[skill_id].record_use(value, mana_cost, targets)

        self.skill_usage["total_skills_activated"] += 1
        self.skill_usage["total_mana_spent"] += mana_cost

        category_key = f"{category.lower()}_skills_used"
        if category_key in self.skill_usage:
            self.skill_usage[category_key] += 1

    def record_dungeon_entered(self, rarity: str):
        """
        Record entering a dungeon.

        Args:
            rarity: Dungeon rarity (common, uncommon, rare, epic, legendary, unique)
        """
        self.dungeon_stats["dungeons_entered"] += 1

    def record_dungeon_completed(self, rarity: str, enemies_killed: int,
                                  time_taken: float, exp_earned: int):
        """
        Record completing a dungeon.

        Args:
            rarity: Dungeon rarity
            enemies_killed: Total enemies killed in dungeon
            time_taken: Time taken to clear in seconds
            exp_earned: Total EXP earned in dungeon
        """
        self.dungeon_stats["dungeons_completed"] += 1

        # Track by rarity
        rarity_key = f"{rarity.lower()}_dungeons_completed"
        if rarity_key in self.dungeon_stats:
            self.dungeon_stats[rarity_key] += 1

        # Update records
        if time_taken < self.dungeon_stats["fastest_dungeon_clear"]:
            self.dungeon_stats["fastest_dungeon_clear"] = time_taken

        if enemies_killed > self.dungeon_stats["most_enemies_killed_single_dungeon"]:
            self.dungeon_stats["most_enemies_killed_single_dungeon"] = enemies_killed

        # Track highest rarity cleared
        rarity_order = ["common", "uncommon", "rare", "epic", "legendary", "unique"]
        current_highest = self.dungeon_stats["highest_rarity_cleared"]
        if not current_highest or rarity_order.index(rarity.lower()) > rarity_order.index(current_highest.lower()):
            self.dungeon_stats["highest_rarity_cleared"] = rarity.lower()

        self.dungeon_stats["total_dungeon_exp_earned"] += exp_earned

    def record_dungeon_abandoned(self):
        """Record abandoning a dungeon (exiting without clearing)."""
        self.dungeon_stats["dungeons_abandoned"] += 1

    def record_dungeon_enemy_killed(self, exp_earned: int = 0):
        """
        Record killing an enemy in a dungeon.

        Args:
            exp_earned: EXP earned from this kill
        """
        self.dungeon_stats["dungeon_enemies_killed"] += 1
        self.dungeon_stats["total_dungeon_exp_earned"] += exp_earned

    def record_dungeon_wave_completed(self):
        """Record completing a wave in a dungeon."""
        self.dungeon_stats["waves_completed"] += 1

    def record_dungeon_death(self):
        """Record dying in a dungeon."""
        self.dungeon_stats["dungeon_deaths"] += 1

    def record_dungeon_chest_opened(self, items_received: int):
        """
        Record opening a dungeon chest.

        Args:
            items_received: Number of items received from the chest
        """
        self.dungeon_stats["dungeon_chests_opened"] += 1
        self.dungeon_stats["dungeon_items_received"] += items_received

    # =========================================================================
    # FISHING RECORDING METHODS
    # =========================================================================

    def record_fish_caught(self, fish_id: str, quantity: int = 1, tier: int = 1,
                           rarity: str = "common", size: int = 0):
        """
        Record catching a fish.

        Args:
            fish_id: Fish type identifier
            quantity: Number of fish caught
            tier: Fish tier (1-4)
            rarity: Fish rarity (common/uncommon/rare/epic/legendary)
            size: Fish size (for tracking largest catch)
        """
        # Update gathering totals
        self.gathering_totals["total_fish_caught"] += quantity
        self.gathering_totals["fishing_rod_casts"] += 1

        # Track in resources_gathered
        if fish_id not in self.resources_gathered:
            self.resources_gathered[fish_id] = StatEntry()
        self.resources_gathered[fish_id].record(quantity)

        # Tier tracking
        tier_key = f"tier_{tier}_resources_gathered"
        if tier_key in self.gathering_totals:
            self.gathering_totals[tier_key] += quantity

        # Track largest fish
        if size > self.gathering_advanced["largest_fish_caught"]:
            self.gathering_advanced["largest_fish_caught"] = size

        # Track catch streak
        self.gathering_advanced["fish_catch_streak"] += 1
        if self.gathering_advanced["fish_catch_streak"] > self.gathering_advanced["longest_fish_catch_streak"]:
            self.gathering_advanced["longest_fish_catch_streak"] = self.gathering_advanced["fish_catch_streak"]

        # Track rare/legendary catches
        rarity_lower = rarity.lower()
        if rarity_lower == "rare":
            self.gathering_advanced["rare_fish_caught"] += 1
        elif rarity_lower in ("legendary", "epic"):
            self.gathering_advanced["legendary_fish_caught"] += 1

    def record_fishing_failed(self):
        """Record a failed fishing attempt (fish got away)."""
        self.gathering_totals["fishing_rod_casts"] += 1
        # Reset catch streak on failure
        self.gathering_advanced["fish_catch_streak"] = 0

    def record_movement(self, distance: float, chunk_coords: Tuple[int, int],
                        is_sprinting: bool = False, is_encumbered: bool = False):
        """
        Record player movement.

        Args:
            distance: Distance traveled in tiles
            chunk_coords: Current chunk coordinates
            is_sprinting: Whether player is sprinting
            is_encumbered: Whether player is encumbered
        """
        self.distance_traveled["total_distance"] += distance

        if is_sprinting:
            self.distance_traveled["distance_sprinted"] += distance
        else:
            self.distance_traveled["distance_walked"] += distance

        if is_encumbered:
            self.distance_traveled["distance_while_encumbered"] += distance

        # Chunk tracking
        if chunk_coords not in self._unique_chunks_visited:
            self._unique_chunks_visited.add(chunk_coords)
            self._unique_chunks_visited_list = list(self._unique_chunks_visited)
            self.exploration["unique_chunks_visited"] = len(self._unique_chunks_visited)

        self.exploration["total_chunk_entries"] += 1

    # =========================================================================
    # BARRIER STATISTICS
    # =========================================================================

    def record_barrier_placed(self, material_id: str):
        """
        Record a barrier being placed in the world.

        Args:
            material_id: ID of the stone material used
        """
        self.barrier_stats["barriers_placed"] += 1

        # Track per-material
        if material_id not in self.barriers_by_material:
            self.barriers_by_material[material_id] = 0
        self.barriers_by_material[material_id] += 1

    def record_barrier_picked_up(self, material_id: str = None):
        """Record a barrier being picked up."""
        self.barrier_stats["barriers_picked_up"] += 1

    def record_attack_blocked(self, source: str = "unknown"):
        """
        Record an attack being blocked by a barrier or obstacle.

        Args:
            source: Who was attacking ('player', 'enemy', 'turret')
        """
        self.barrier_stats["attacks_blocked_by_barriers"] += 1

        if source == "player":
            self.barrier_stats["player_attacks_blocked"] += 1
        elif source == "enemy":
            self.barrier_stats["enemy_attacks_blocked"] += 1
        elif source == "turret":
            self.barrier_stats["turret_attacks_blocked"] += 1

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize all stats to dictionary for saving.

        Returns:
            Complete stat data as dictionary
        """
        return {
            "version": "1.0",
            "session_start_time": self.session_start_time,
            "total_playtime_seconds": self.total_playtime_seconds,
            "session_count": self.session_count,

            # Per-entity tracking
            "resources_gathered": {
                res_id: entry.to_dict()
                for res_id, entry in self.resources_gathered.items()
            },
            "recipes_crafted": {
                recipe_id: entry.to_dict()
                for recipe_id, entry in self.recipes_crafted.items()
            },
            "skills_used": {
                skill_id: entry.to_dict()
                for skill_id, entry in self.skills_used.items()
            },
            "items_collected": dict(self.items_collected),
            "items_used": dict(self.items_used),

            # Aggregate stats
            "gathering_totals": dict(self.gathering_totals),
            "gathering_advanced": self._serialize_dict_with_inf(self.gathering_advanced),
            "crafting_by_discipline": self.crafting_by_discipline,
            "crafting_advanced": self._serialize_dict_with_inf(self.crafting_advanced),
            "combat_damage": dict(self.combat_damage),
            "combat_kills": dict(self.combat_kills),
            "combat_actions": dict(self.combat_actions),
            "combat_status_effects": dict(self.combat_status_effects),
            "combat_survival": dict(self.combat_survival),
            "item_collection": dict(self.item_collection),
            "item_usage": dict(self.item_usage),
            "item_management": dict(self.item_management),
            "skill_usage": dict(self.skill_usage),
            "skill_progression": dict(self.skill_progression),
            "distance_traveled": dict(self.distance_traveled),
            "exploration": dict(self.exploration),
            "unique_chunks_visited": self._unique_chunks_visited_list,
            "economy": dict(self.economy),
            "experience_stats": dict(self.experience_stats),
            "progression_milestones": dict(self.progression_milestones),
            "time_stats": dict(self.time_stats),
            "records": self._serialize_dict_with_inf(self.records),
            "social_stats": dict(self.social_stats),
            "encyclopedia_stats": dict(self.encyclopedia_stats),
            "misc_stats": dict(self.misc_stats),
            "dungeon_stats": self._serialize_dict_with_inf(self.dungeon_stats),

            # Barrier system
            "barrier_stats": dict(self.barrier_stats),
            "barriers_by_material": dict(self.barriers_by_material)
        }

    def _serialize_dict_with_inf(self, data: Dict) -> Dict:
        """Convert infinity values to None for JSON serialization."""
        result = {}
        for key, value in data.items():
            if isinstance(value, float) and value == float('inf'):
                result[key] = None
            elif isinstance(value, dict):
                result[key] = self._serialize_dict_with_inf(value)
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StatTracker':
        """
        Deserialize stats from dictionary.

        Args:
            data: Saved stat data

        Returns:
            Restored StatTracker instance
        """
        tracker = cls()

        # Session info
        tracker.session_start_time = data.get("session_start_time")
        tracker.total_playtime_seconds = data.get("total_playtime_seconds", 0.0)
        tracker.session_count = data.get("session_count", 0)

        # Per-entity tracking
        resources_data = data.get("resources_gathered", {})
        for res_id, entry_data in resources_data.items():
            tracker.resources_gathered[res_id] = StatEntry.from_dict(entry_data)

        recipes_data = data.get("recipes_crafted", {})
        for recipe_id, entry_data in recipes_data.items():
            tracker.recipes_crafted[recipe_id] = CraftingEntry.from_dict(entry_data)

        skills_data = data.get("skills_used", {})
        for skill_id, entry_data in skills_data.items():
            tracker.skills_used[skill_id] = SkillStatEntry.from_dict(entry_data)

        tracker.items_collected = data.get("items_collected", {})
        tracker.items_used = data.get("items_used", {})

        # Aggregate stats
        tracker.gathering_totals.update(data.get("gathering_totals", {}))
        tracker.gathering_advanced.update(tracker._deserialize_dict_with_inf(data.get("gathering_advanced", {})))
        tracker.crafting_by_discipline.update(data.get("crafting_by_discipline", {}))
        tracker.crafting_advanced.update(tracker._deserialize_dict_with_inf(data.get("crafting_advanced", {})))
        tracker.combat_damage.update(data.get("combat_damage", {}))
        tracker.combat_kills.update(data.get("combat_kills", {}))
        tracker.combat_actions.update(data.get("combat_actions", {}))
        tracker.combat_status_effects.update(data.get("combat_status_effects", {}))
        tracker.combat_survival.update(data.get("combat_survival", {}))
        tracker.item_collection.update(data.get("item_collection", {}))
        tracker.item_usage.update(data.get("item_usage", {}))
        tracker.item_management.update(data.get("item_management", {}))
        tracker.skill_usage.update(data.get("skill_usage", {}))
        tracker.skill_progression.update(data.get("skill_progression", {}))
        tracker.distance_traveled.update(data.get("distance_traveled", {}))
        tracker.exploration.update(data.get("exploration", {}))

        # Restore unique chunks
        chunks_list = data.get("unique_chunks_visited", [])
        tracker._unique_chunks_visited = set(tuple(chunk) for chunk in chunks_list)
        tracker._unique_chunks_visited_list = chunks_list

        tracker.economy.update(data.get("economy", {}))
        tracker.experience_stats.update(data.get("experience_stats", {}))
        tracker.progression_milestones.update(data.get("progression_milestones", {}))
        tracker.time_stats.update(data.get("time_stats", {}))
        tracker.records.update(tracker._deserialize_dict_with_inf(data.get("records", {})))
        tracker.social_stats.update(data.get("social_stats", {}))
        tracker.encyclopedia_stats.update(data.get("encyclopedia_stats", {}))
        tracker.misc_stats.update(data.get("misc_stats", {}))

        # Restore dungeon stats (backwards compatible - won't exist in older saves)
        if "dungeon_stats" in data:
            tracker.dungeon_stats.update(tracker._deserialize_dict_with_inf(data.get("dungeon_stats", {})))

        # Restore barrier stats (backwards compatible - won't exist in older saves)
        if "barrier_stats" in data:
            tracker.barrier_stats.update(data.get("barrier_stats", {}))
        if "barriers_by_material" in data:
            tracker.barriers_by_material.update(data.get("barriers_by_material", {}))

        return tracker

    def _deserialize_dict_with_inf(self, data: Dict) -> Dict:
        """Convert None values back to infinity."""
        result = {}
        for key, value in data.items():
            if value is None:
                result[key] = float('inf')
            elif isinstance(value, dict):
                result[key] = self._deserialize_dict_with_inf(value)
            else:
                result[key] = value
        return result

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_summary(self) -> Dict[str, Any]:
        """
        Generate human-readable statistics summary.

        Returns:
            Summary dictionary with formatted stats
        """
        return {
            "playtime": self._format_time(self.total_playtime_seconds),
            "sessions": self.session_count,
            "level": self.experience_stats.get("highest_level_reached", 1),
            "total_resources_gathered": sum(entry.count for entry in self.resources_gathered.values()),
            "total_items_crafted": self.crafting_advanced["total_crafts_all_disciplines"],
            "total_enemies_defeated": self.combat_kills["total_enemies_defeated"],
            "total_damage_dealt": round(self.combat_damage["total_damage_dealt"], 2),
            "total_distance_traveled": round(self.distance_traveled["total_distance"], 2),
            "titles_earned": self.progression_milestones["titles_earned"],
            "skills_learned": self.skill_progression["skills_learned"]
        }

    def _format_time(self, seconds: float) -> str:
        """Format seconds as human-readable time string."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"
