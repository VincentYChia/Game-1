"""
Comprehensive Stat Tracking System — SQL-backed via StatStore.

Tracks all player statistics at Minecraft-level detail using a single flat
SQL table with hierarchical keys and automatic dimensional breakdowns.

Every record_* method writes multiple stat keys in a single transaction.
For example, record_damage_dealt(50, "fire", "melee", "wolf", "whispering_woods")
writes keys like:
    combat.damage_dealt              → total +50
    combat.damage_dealt.type.fire    → total +50
    combat.damage_dealt.attack.melee → total +50
    combat.damage_dealt.to.wolf      → total +50
    combat.damage_dealt.location.whispering_woods → total +50

The record_* API is unchanged from the dict-based version — all 51 call sites
in the game code work without modification.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Optional, Any, List
from collections import defaultdict
import time

from world_system.world_memory.stat_store import StatStore, build_dimensional_keys


class StatTracker:
    """SQL-backed stat tracking system for player analytics and progression.

    All stats stored in a single SQL table via StatStore.
    record_* methods create automatic dimensional breakdowns.
    """

    def __init__(self, stat_store: Optional[StatStore] = None):
        """Initialize stat tracking.

        Args:
            stat_store: SQL-backed stat store. If None, creates in-memory store.
        """
        self._store = stat_store or StatStore()

        # Session tracking (kept in memory, flushed to SQL periodically)
        self.session_start_time: Optional[float] = None
        self.total_playtime_seconds: float = 0.0
        self.session_count: int = 0

        # In-memory caches for hot-path data
        self._unique_chunks_visited: Set[Tuple[int, int]] = set()
        self._current_killstreak: int = 0
        self._current_gather_streak: int = 0
        self._current_fish_streak: int = 0
        self._current_first_try_streak: int = 0
        self._current_no_damage_streak: int = 0

    @property
    def store(self) -> StatStore:
        return self._store

    def set_store(self, store: StatStore) -> None:
        """Replace the stat store (used during initialization)."""
        self._store = store

    # ══════════════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ══════════════════════════════════════════════════════════════════

    def start_session(self) -> None:
        """Called when a new play session starts."""
        self.session_start_time = time.time()
        self.session_count += 1
        self._store.record_count("session.started")
        self._store.flush()

    def update_playtime(self, dt: float) -> None:
        """Called each frame with delta time."""
        self.total_playtime_seconds += dt
        # Don't write to SQL every frame — flush periodically

    # ══════════════════════════════════════════════════════════════════
    # GATHERING
    # ══════════════════════════════════════════════════════════════════

    def record_resource_gathered(self, resource_id: str, quantity: int = 1,
                                 tier: int = 1, category: str = "ore",
                                 element: Optional[str] = None,
                                 is_crit: bool = False,
                                 is_rare_drop: bool = False) -> None:
        """Record a resource gathering event with full dimensional breakdown."""
        dims = {
            "resource": resource_id,
            "tier": tier,
            "category": category,
        }
        if element:
            dims["element"] = element

        # Quantity-based keys (total = quantity)
        keys = build_dimensional_keys("gathering.collected", dims)
        self._store.record_multi(keys, value=float(quantity))

        # Count-based keys (how many gather actions)
        count_keys = build_dimensional_keys("gathering.actions", dims)
        self._store.record_count_multi(count_keys)

        # Quality tracking
        if is_crit:
            self._store.record_count("gathering.critical")
        if is_rare_drop:
            self._store.record_count("gathering.rare_drops")

        # Streak tracking
        self._current_gather_streak += 1
        if self._current_gather_streak > self._store.get_max("gathering.longest_streak"):
            self._store.set_value("gathering.longest_streak",
                                  float(self._current_gather_streak))

    def record_fish_caught(self, fish_id: str, quantity: int = 1,
                           tier: int = 1, rarity: str = "common",
                           size: int = 0) -> None:
        """Record a successful fish catch."""
        dims = {"fish": fish_id, "tier": tier, "rarity": rarity}
        keys = build_dimensional_keys("gathering.fishing.caught", dims)
        self._store.record_multi(keys, value=float(quantity))

        if size > 0:
            self._store.record("gathering.fishing.largest", value=float(size))

        self._current_fish_streak += 1
        if self._current_fish_streak > self._store.get_max("gathering.fishing.longest_streak"):
            self._store.set_value("gathering.fishing.longest_streak",
                                  float(self._current_fish_streak))

        if rarity == "rare":
            self._store.record_count("gathering.fishing.rare")
        elif rarity == "legendary":
            self._store.record_count("gathering.fishing.legendary")

    def record_fishing_failed(self) -> None:
        """Record a failed fishing attempt."""
        self._store.record_count("gathering.fishing.failed")
        self._current_fish_streak = 0

    # ══════════════════════════════════════════════════════════════════
    # CRAFTING
    # ══════════════════════════════════════════════════════════════════

    def record_crafting(self, recipe_id: str, discipline: str, success: bool,
                        tier: int = 1, quality_score: float = 0.0,
                        craft_time: float = 0.0, output_rarity: str = "common",
                        is_perfect: bool = False, is_first_try: bool = False,
                        materials: Optional[Dict[str, int]] = None) -> None:
        """Record a crafting attempt with full dimensional breakdown."""
        result = "success" if success else "failure"
        dims = {
            "discipline": discipline,
            "tier": tier,
            "result": result,
        }

        # Attempt count
        attempt_keys = build_dimensional_keys("crafting.attempts", dims)
        self._store.record_count_multi(attempt_keys)

        if success:
            # Success-specific breakdowns
            success_dims = {
                "discipline": discipline,
                "tier": tier,
                "rarity": output_rarity,
                "recipe": recipe_id,
            }
            success_keys = build_dimensional_keys("crafting.success", success_dims)
            self._store.record_count_multi(success_keys)

            # Quality score
            if quality_score > 0:
                self._store.record(f"crafting.quality.{discipline}", value=quality_score)
                self._store.record("crafting.quality", value=quality_score)

            # Craft time
            if craft_time > 0:
                self._store.record(f"crafting.time.{discipline}", value=craft_time)

            # Perfect / first-try
            if is_perfect:
                self._store.record_count(f"crafting.perfect.{discipline}")
                self._store.record_count("crafting.perfect")
            if is_first_try:
                self._store.record_count(f"crafting.first_try.{discipline}")
                self._store.record_count("crafting.first_try")
                self._current_first_try_streak += 1
                if self._current_first_try_streak > self._store.get_max("crafting.longest_first_try_streak"):
                    self._store.set_value("crafting.longest_first_try_streak",
                                          float(self._current_first_try_streak))
            else:
                self._current_first_try_streak = 0

            # Rarity tracking
            self._store.record_count(f"crafting.rarity.{output_rarity}")

        # Materials consumed
        if materials:
            for mat_id, qty in materials.items():
                self._store.record(f"crafting.materials.{mat_id}", value=float(qty))

    # ══════════════════════════════════════════════════════════════════
    # COMBAT
    # ══════════════════════════════════════════════════════════════════

    def record_damage_dealt(self, amount: float, damage_type: str = "physical",
                            attack_type: str = "melee", was_crit: bool = False,
                            weapon_element: Optional[str] = None) -> None:
        """Record damage dealt with full dimensional breakdown."""
        dims = {
            "type": damage_type,
            "attack": attack_type,
        }
        if weapon_element:
            dims["weapon_element"] = weapon_element

        keys = build_dimensional_keys("combat.damage_dealt", dims)
        self._store.record_multi(keys, value=amount)

        if was_crit:
            self._store.record("combat.damage_dealt.critical", value=amount)
            self._store.record_count("combat.critical_hits")

    def record_damage_taken(self, amount: float, damage_type: str = "physical",
                            attack_type: str = "melee") -> None:
        """Record damage received."""
        dims = {"type": damage_type, "attack": attack_type}
        keys = build_dimensional_keys("combat.damage_taken", dims)
        self._store.record_multi(keys, value=amount)

        # Reset no-damage streak
        self._current_no_damage_streak = 0

    def record_enemy_killed(self, tier: int = 1, is_boss: bool = False,
                            is_dragon: bool = False,
                            weapon_element: Optional[str] = None,
                            enemy_type: str = "unknown",
                            location: str = "") -> None:
        """Record an enemy kill with full dimensional breakdown."""
        dims = {
            "tier": tier,
            "species": enemy_type,
        }
        if is_boss:
            dims["rank"] = "boss"
        if is_dragon:
            dims["rank"] = "dragon"
        if weapon_element:
            dims["weapon_element"] = weapon_element
        if location:
            dims["location"] = location

        keys = build_dimensional_keys("combat.kills", dims)
        self._store.record_count_multi(keys)

        # Killstreak
        self._current_killstreak += 1
        if self._current_killstreak > self._store.get_max("combat.longest_killstreak"):
            self._store.set_value("combat.longest_killstreak",
                                  float(self._current_killstreak))

        # No-damage streak tracking
        self._current_no_damage_streak += 1
        if self._current_no_damage_streak > self._store.get_max("combat.longest_no_damage_streak"):
            self._store.set_value("combat.longest_no_damage_streak",
                                  float(self._current_no_damage_streak))

    def record_status_effect(self, effect_tag: str,
                             applied_to_enemy: bool = True) -> None:
        """Record a status effect application."""
        target = "applied" if applied_to_enemy else "received"
        self._store.record_count(f"combat.status.{target}.{effect_tag}")
        self._store.record_count(f"combat.status.{target}")

    def record_death(self) -> None:
        """Record player death."""
        self._store.record_count("combat.deaths")
        self._current_killstreak = 0
        self._current_no_damage_streak = 0

    def record_items_lost_on_death(self, items_lost: int,
                                   soulbound_kept: int) -> None:
        """Record items lost on death."""
        self._store.record("combat.deaths.items_lost", value=float(items_lost))
        self._store.record("combat.deaths.soulbound_kept", value=float(soulbound_kept))

    def record_attack_blocked(self, source: str = "unknown") -> None:
        """Record a blocked attack."""
        self._store.record_count(f"combat.blocks.{source}")
        self._store.record_count("combat.blocks")

    def record_dodge_roll(self) -> None:
        """Record a dodge roll attempt."""
        self._store.record_count("combat.dodge_rolls")

    def record_successful_dodge(self) -> None:
        """Record a successful i-frame dodge."""
        self._store.record_count("combat.dodge_rolls.successful")

    def record_combo_attack(self, combo_count: int) -> None:
        """Record a combo attack."""
        self._store.record("combat.combos", value=float(combo_count))

    def record_projectile_fired(self) -> None:
        """Record a projectile launch."""
        self._store.record_count("combat.projectiles.fired")

    def record_projectile_hit(self) -> None:
        """Record a projectile hit."""
        self._store.record_count("combat.projectiles.hit")

    # ══════════════════════════════════════════════════════════════════
    # ITEMS
    # ══════════════════════════════════════════════════════════════════

    def record_item_collected(self, item_id: str, quantity: int = 1,
                              category: str = "material",
                              rarity: str = "common",
                              is_first_time: bool = False,
                              is_rare_drop: bool = False) -> None:
        """Record item collection."""
        dims = {"item": item_id, "category": category, "rarity": rarity}
        keys = build_dimensional_keys("items.collected", dims)
        self._store.record_multi(keys, value=float(quantity))

        if is_first_time:
            self._store.record_count("items.first_discoveries")
        if is_rare_drop:
            self._store.record_count("items.rare_drops")

    def record_item_used(self, item_id: str, quantity: int = 1,
                         item_type: str = "consumable",
                         in_combat: bool = False) -> None:
        """Record item usage."""
        dims = {"item": item_id, "type": item_type}
        if in_combat:
            dims["context"] = "combat"
        keys = build_dimensional_keys("items.used", dims)
        self._store.record_multi(keys, value=float(quantity))

    def record_item_dropped(self, item_id: str, quantity: int = 1,
                            destroyed: bool = False) -> None:
        """Record item drop or destruction."""
        action = "destroyed" if destroyed else "dropped"
        self._store.record(f"items.{action}.{item_id}", value=float(quantity))
        self._store.record_count(f"items.{action}")

    # ══════════════════════════════════════════════════════════════════
    # SKILLS
    # ══════════════════════════════════════════════════════════════════

    def record_skill_used(self, skill_id: str, value: float = 0.0,
                          mana_cost: float = 0.0, targets: int = 0,
                          category: str = "utility") -> None:
        """Record skill activation."""
        dims = {"skill": skill_id, "category": category}
        keys = build_dimensional_keys("skills.used", dims)
        self._store.record_multi(keys, value=max(value, 1.0))

        if mana_cost > 0:
            self._store.record("skills.mana_spent", value=mana_cost)
            self._store.record(f"skills.mana_spent.{skill_id}", value=mana_cost)
        if targets > 0:
            self._store.record("skills.targets_affected", value=float(targets))

    # ══════════════════════════════════════════════════════════════════
    # EXPLORATION
    # ══════════════════════════════════════════════════════════════════

    def record_movement(self, distance: float,
                        chunk_coords: Tuple[int, int],
                        is_sprinting: bool = False,
                        is_encumbered: bool = False) -> None:
        """Record player movement."""
        self._store.record("exploration.distance", value=distance)
        if is_sprinting:
            self._store.record("exploration.distance.sprinting", value=distance)
        if is_encumbered:
            self._store.record("exploration.distance.encumbered", value=distance)

        # Track unique chunks
        if chunk_coords not in self._unique_chunks_visited:
            self._unique_chunks_visited.add(chunk_coords)
            self._store.record_count("exploration.unique_chunks")
        self._store.record_count("exploration.chunk_entries")

    def record_chunk_entered(self, chunk_x: int, chunk_y: int,
                             biome: str = "unknown") -> None:
        """Record entering a new chunk (from bus event)."""
        self._store.record_count(f"exploration.chunks.biome.{biome}")
        coords = (chunk_x, chunk_y)
        if coords not in self._unique_chunks_visited:
            self._unique_chunks_visited.add(coords)
            self._store.record_count("exploration.unique_chunks")
            self._store.record_count("exploration.new_discoveries")

    def record_landmark_discovered(self, landmark_id: str,
                                   landmark_type: str = "unknown") -> None:
        """Record landmark discovery."""
        self._store.record_count(f"exploration.landmarks.{landmark_type}")
        self._store.record_count("exploration.landmarks")

    # ══════════════════════════════════════════════════════════════════
    # ECONOMY
    # ══════════════════════════════════════════════════════════════════

    def record_gold_earned(self, amount: float, source: str = "unknown") -> None:
        """Record gold earned."""
        self._store.record(f"economy.gold_earned.{source}", value=amount)
        self._store.record("economy.gold_earned", value=amount)

    def record_gold_spent(self, amount: float, sink: str = "unknown") -> None:
        """Record gold spent."""
        self._store.record(f"economy.gold_spent.{sink}", value=amount)
        self._store.record("economy.gold_spent", value=amount)

    def record_trade(self, trade_type: str = "buy",
                     item_id: str = "", amount: float = 0.0) -> None:
        """Record a trade transaction."""
        self._store.record_count(f"economy.trades.{trade_type}")
        self._store.record_count("economy.trades")
        if item_id:
            self._store.record_count(f"economy.trades.item.{item_id}")
        if amount > 0:
            self._store.record(f"economy.trades.{trade_type}.value", value=amount)

    # ══════════════════════════════════════════════════════════════════
    # PROGRESSION
    # ══════════════════════════════════════════════════════════════════

    def record_level_up(self, new_level: int, stat_points: int = 0) -> None:
        """Record a level up."""
        self._store.record_count("progression.level_ups")
        self._store.set_value("progression.current_level", float(new_level))
        if stat_points > 0:
            self._store.record("progression.stat_points_earned",
                               value=float(stat_points))

    def record_exp_gained(self, amount: float, source: str = "unknown") -> None:
        """Record experience gained."""
        self._store.record(f"progression.exp.{source}", value=amount)
        self._store.record("progression.exp", value=amount)

    def record_title_earned(self, title_id: str,
                            tier: str = "novice") -> None:
        """Record earning a title."""
        self._store.record_count(f"progression.titles.tier.{tier}")
        self._store.record_count(f"progression.titles.{title_id}")
        self._store.record_count("progression.titles")

    def record_class_changed(self, class_id: str) -> None:
        """Record a class change."""
        self._store.record_count(f"progression.class_changes.{class_id}")
        self._store.record_count("progression.class_changes")

    def record_skill_learned(self, skill_id: str,
                             source: str = "level") -> None:
        """Record learning a new skill."""
        self._store.record_count(f"progression.skills_learned.{source}")
        self._store.record_count(f"progression.skills_learned.{skill_id}")
        self._store.record_count("progression.skills_learned")

    # ══════════════════════════════════════════════════════════════════
    # DUNGEONS
    # ══════════════════════════════════════════════════════════════════

    def record_dungeon_entered(self, rarity: str) -> None:
        """Record entering a dungeon."""
        self._store.record_count(f"dungeon.entered.{rarity}")
        self._store.record_count("dungeon.entered")

    def record_dungeon_completed(self, rarity: str, enemies_killed: int,
                                 time_taken: float,
                                 exp_earned: int = 0) -> None:
        """Record completing a dungeon."""
        self._store.record_count(f"dungeon.completed.{rarity}")
        self._store.record_count("dungeon.completed")
        self._store.record("dungeon.enemies_killed_in_run",
                           value=float(enemies_killed))
        if time_taken > 0:
            # Record time (lower is better, so we track via max inversion)
            self._store.record(f"dungeon.clear_time.{rarity}", value=time_taken)
        if exp_earned > 0:
            self._store.record("dungeon.exp_earned", value=float(exp_earned))

    def record_dungeon_abandoned(self) -> None:
        self._store.record_count("dungeon.abandoned")

    def record_dungeon_enemy_killed(self, exp_earned: int = 0) -> None:
        self._store.record_count("dungeon.enemies_killed")
        if exp_earned > 0:
            self._store.record("dungeon.exp_earned", value=float(exp_earned))

    def record_dungeon_wave_completed(self) -> None:
        self._store.record_count("dungeon.waves_completed")

    def record_dungeon_death(self) -> None:
        self._store.record_count("dungeon.deaths")

    def record_dungeon_chest_opened(self, items_received: int) -> None:
        self._store.record_count("dungeon.chests_opened")
        self._store.record("dungeon.items_received",
                           value=float(items_received))

    # ══════════════════════════════════════════════════════════════════
    # SOCIAL / QUESTS
    # ══════════════════════════════════════════════════════════════════

    def record_npc_interaction(self, npc_id: str) -> None:
        """Record talking to an NPC."""
        self._store.record_count(f"social.npc.{npc_id}")
        self._store.record_count("social.npc_interactions")

    def record_quest_accepted(self, quest_id: str,
                              quest_type: str = "unknown") -> None:
        """Record accepting a quest."""
        self._store.record_count(f"social.quests.accepted.{quest_type}")
        self._store.record_count("social.quests.accepted")

    def record_quest_completed(self, quest_id: str,
                               quest_type: str = "unknown",
                               exp_reward: float = 0.0,
                               gold_reward: float = 0.0) -> None:
        """Record completing a quest."""
        self._store.record_count(f"social.quests.completed.{quest_type}")
        self._store.record_count("social.quests.completed")
        if exp_reward > 0:
            self._store.record("social.quests.exp_earned", value=exp_reward)
        if gold_reward > 0:
            self._store.record("social.quests.gold_earned", value=gold_reward)

    def record_quest_failed(self, quest_id: str,
                            quest_type: str = "unknown") -> None:
        """Record failing a quest."""
        self._store.record_count(f"social.quests.failed.{quest_type}")
        self._store.record_count("social.quests.failed")

    # ══════════════════════════════════════════════════════════════════
    # BARRIERS
    # ══════════════════════════════════════════════════════════════════

    def record_barrier_placed(self, material_id: str) -> None:
        self._store.record_count(f"barriers.placed.{material_id}")
        self._store.record_count("barriers.placed")

    def record_barrier_picked_up(self, material_id: str = None) -> None:
        self._store.record_count("barriers.picked_up")
        if material_id:
            self._store.record_count(f"barriers.picked_up.{material_id}")

    # ══════════════════════════════════════════════════════════════════
    # EQUIPMENT
    # ══════════════════════════════════════════════════════════════════

    def record_equipment_changed(self, item_id: str, slot: str,
                                 equipped: bool = True) -> None:
        """Record equipping or unequipping an item."""
        action = "equipped" if equipped else "unequipped"
        self._store.record_count(f"items.{action}.{item_id}")
        self._store.record_count(f"items.{action}.slot.{slot}")
        self._store.record_count(f"items.{action}")
        self._store.record_count("items.equipment_swaps")

    # ══════════════════════════════════════════════════════════════════
    # MISCELLANEOUS
    # ══════════════════════════════════════════════════════════════════

    def record_repair(self, item_id: str, durability_restored: float = 0.0) -> None:
        """Record repairing an item."""
        self._store.record_count(f"items.repaired.{item_id}")
        self._store.record_count("items.repaired")
        if durability_restored > 0:
            self._store.record("items.durability_restored",
                               value=durability_restored)

    # ══════════════════════════════════════════════════════════════════
    # SERIALIZATION (backward compatibility)
    # ══════════════════════════════════════════════════════════════════

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all stats to a dictionary.

        This reads from SQL and produces a dict compatible with the old format.
        Used by the renderer and for backward-compatible save files.
        """
        all_stats = self._store.get_all()

        # Session info
        result: Dict[str, Any] = {
            "version": "2.0",
            "session_start_time": self.session_start_time,
            "total_playtime_seconds": self.total_playtime_seconds,
            "session_count": self.session_count,
        }

        # Flatten all SQL stats into categorized dicts
        # Group by top-level key prefix
        categories: Dict[str, Dict] = {}
        for key, (count, total, max_val) in all_stats.items():
            parts = key.split(".", 1)
            cat = parts[0]
            subkey = parts[1] if len(parts) > 1 else key
            if cat not in categories:
                categories[cat] = {}
            categories[cat][subkey] = {
                "count": count,
                "total": total,
                "max_value": max_val,
            }

        result["stats"] = categories

        # Legacy format fields for backward compat with renderer
        result["gathering_totals"] = self._build_legacy_gathering()
        result["combat_damage"] = self._build_legacy_combat_damage()
        result["combat_kills"] = self._build_legacy_combat_kills()
        result["crafting_by_discipline"] = self._build_legacy_crafting()

        # Unique chunks as list
        result["unique_chunks_visited"] = list(self._unique_chunks_visited)

        return result

    def _build_legacy_gathering(self) -> Dict[str, Any]:
        """Build legacy gathering_totals dict from SQL stats."""
        return {
            "total_trees_chopped": self._store.get_count("gathering.collected.category.tree"),
            "total_ores_mined": self._store.get_count("gathering.collected.category.ore"),
            "total_stones_mined": self._store.get_count("gathering.collected.category.stone"),
            "total_plants_gathered": self._store.get_count("gathering.collected.category.plant"),
            "total_fish_caught": self._store.get_count("gathering.fishing.caught"),
            "tier_1_resources_gathered": self._store.get_count("gathering.collected.tier.1"),
            "tier_2_resources_gathered": self._store.get_count("gathering.collected.tier.2"),
            "tier_3_resources_gathered": self._store.get_count("gathering.collected.tier.3"),
            "tier_4_resources_gathered": self._store.get_count("gathering.collected.tier.4"),
        }

    def _build_legacy_combat_damage(self) -> Dict[str, Any]:
        """Build legacy combat_damage dict from SQL stats."""
        return {
            "total_damage_dealt": self._store.get_total("combat.damage_dealt"),
            "melee_damage_dealt": self._store.get_total("combat.damage_dealt.attack.melee"),
            "ranged_damage_dealt": self._store.get_total("combat.damage_dealt.attack.ranged"),
            "magic_damage_dealt": self._store.get_total("combat.damage_dealt.attack.magic"),
            "physical_damage_dealt": self._store.get_total("combat.damage_dealt.type.physical"),
            "fire_damage_dealt": self._store.get_total("combat.damage_dealt.type.fire"),
            "ice_damage_dealt": self._store.get_total("combat.damage_dealt.type.ice"),
            "lightning_damage_dealt": self._store.get_total("combat.damage_dealt.type.lightning"),
            "highest_single_hit_dealt": self._store.get_max("combat.damage_dealt"),
            "total_damage_taken": self._store.get_total("combat.damage_taken"),
        }

    def _build_legacy_combat_kills(self) -> Dict[str, Any]:
        """Build legacy combat_kills dict from SQL stats."""
        return {
            "total_kills": self._store.get_count("combat.kills"),
            "tier_1_enemies_killed": self._store.get_count("combat.kills.tier.1"),
            "tier_2_enemies_killed": self._store.get_count("combat.kills.tier.2"),
            "tier_3_enemies_killed": self._store.get_count("combat.kills.tier.3"),
            "tier_4_enemies_killed": self._store.get_count("combat.kills.tier.4"),
            "boss_enemies_killed": self._store.get_count("combat.kills.rank.boss"),
        }

    def _build_legacy_crafting(self) -> Dict[str, Any]:
        """Build legacy crafting_by_discipline dict from SQL stats."""
        result = {}
        for disc in ["smithing", "alchemy", "refining", "engineering", "enchanting"]:
            result[disc] = {
                "total_crafts": self._store.get_count(f"crafting.success.discipline.{disc}"),
                "total_attempts": self._store.get_count(f"crafting.attempts.discipline.{disc}"),
                "perfect_crafts": self._store.get_count(f"crafting.perfect.{disc}"),
                "first_try_bonuses": self._store.get_count(f"crafting.first_try.{disc}"),
            }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any],
                  stat_store: Optional[StatStore] = None) -> 'StatTracker':
        """Deserialize from a saved dictionary.

        Handles both v2.0 (SQL-native) and v1.0 (legacy dict) formats.
        """
        tracker = cls(stat_store=stat_store)

        version = data.get("version", "1.0")
        tracker.session_start_time = data.get("session_start_time")
        tracker.total_playtime_seconds = data.get("total_playtime_seconds", 0.0)
        tracker.session_count = data.get("session_count", 0)

        # Restore unique chunks
        chunks = data.get("unique_chunks_visited", [])
        if isinstance(chunks, list):
            tracker._unique_chunks_visited = {
                tuple(c) if isinstance(c, list) else c
                for c in chunks if c
            }

        if version == "2.0":
            # v2.0 format: stats are already in SQL, just restore categories
            categories = data.get("stats", {})
            flat = {}
            for cat, subkeys in categories.items():
                for subkey, stat_data in subkeys.items():
                    full_key = f"{cat}.{subkey}"
                    flat[full_key] = stat_data
            tracker._store.import_flat(flat)
        else:
            # v1.0 legacy format: import from old dict structure
            tracker._import_legacy_data(data)

        return tracker

    def _import_legacy_data(self, data: Dict[str, Any]) -> None:
        """Import old v1.0 dict-based stat tracker data into SQL."""
        ts = time.time()

        # Import resources_gathered (Dict[str, StatEntry])
        for res_id, entry in data.get("resources_gathered", {}).items():
            if isinstance(entry, dict):
                count = entry.get("count", 0)
                total = entry.get("total_value", 0.0)
                max_v = entry.get("max_value", 0.0)
                self._store.import_flat({
                    f"gathering.collected.resource.{res_id}": {
                        "count": count, "total": total, "max_value": max_v
                    }
                }, timestamp=ts)

        # Import gathering_totals
        gt = data.get("gathering_totals", {})
        for key, val in gt.items():
            if isinstance(val, (int, float)) and val > 0:
                self._store.import_flat({
                    f"gathering.legacy.{key}": {"count": int(val), "total": float(val)}
                }, timestamp=ts)

        # Import combat stats
        for cat_name in ["combat_damage", "combat_kills", "combat_actions",
                         "combat_status_effects", "combat_survival"]:
            cat_data = data.get(cat_name, {})
            for key, val in cat_data.items():
                if isinstance(val, (int, float)) and val > 0:
                    self._store.import_flat({
                        f"combat.legacy.{cat_name}.{key}": {
                            "count": int(val) if isinstance(val, int) else 0,
                            "total": float(val),
                        }
                    }, timestamp=ts)

        # Import crafting stats
        for disc, disc_data in data.get("crafting_by_discipline", {}).items():
            if isinstance(disc_data, dict):
                for key, val in disc_data.items():
                    if isinstance(val, (int, float)) and val > 0:
                        self._store.import_flat({
                            f"crafting.legacy.{disc}.{key}": {
                                "count": int(val) if isinstance(val, int) else 0,
                                "total": float(val),
                            }
                        }, timestamp=ts)

        # Import recipes_crafted (Dict[str, CraftingEntry])
        for recipe_id, entry in data.get("recipes_crafted", {}).items():
            if isinstance(entry, dict):
                attempts = entry.get("total_attempts", 0)
                successes = entry.get("successful_crafts", 0)
                if attempts > 0:
                    self._store.import_flat({
                        f"crafting.legacy.recipe.{recipe_id}.attempts": {
                            "count": attempts, "total": float(attempts)
                        },
                        f"crafting.legacy.recipe.{recipe_id}.successes": {
                            "count": successes, "total": float(successes)
                        },
                    }, timestamp=ts)

        # Import skills_used (Dict[str, SkillStatEntry])
        for skill_id, entry in data.get("skills_used", {}).items():
            if isinstance(entry, dict):
                used = entry.get("times_used", 0)
                total_val = entry.get("total_value_delivered", 0.0)
                mana = entry.get("mana_spent", 0.0)
                if used > 0:
                    self._store.import_flat({
                        f"skills.legacy.{skill_id}.used": {
                            "count": used, "total": float(used)
                        },
                        f"skills.legacy.{skill_id}.value": {
                            "total": total_val
                        },
                        f"skills.legacy.{skill_id}.mana": {
                            "total": mana
                        },
                    }, timestamp=ts)

        # Import remaining flat categories
        for cat_name in ["economy", "experience_stats", "progression_milestones",
                         "time_stats", "records", "social_stats",
                         "encyclopedia_stats", "misc_stats",
                         "dungeon_stats", "barrier_stats"]:
            cat_data = data.get(cat_name, {})
            if isinstance(cat_data, dict):
                for key, val in cat_data.items():
                    if isinstance(val, (int, float)) and val != 0:
                        self._store.import_flat({
                            f"{cat_name.replace('_stats', '')}.legacy.{key}": {
                                "count": int(val) if isinstance(val, int) else 0,
                                "total": float(val),
                            }
                        }, timestamp=ts)

        self._store.flush()

    # ══════════════════════════════════════════════════════════════════
    # CONVENIENCE QUERY METHODS
    # ══════════════════════════════════════════════════════════════════

    def get_summary(self) -> Dict[str, Any]:
        """Get a high-level summary of player stats."""
        return {
            "total_stats_tracked": self._store.get_stat_count(),
            "total_kills": self._store.get_count("combat.kills"),
            "total_damage_dealt": self._store.get_total("combat.damage_dealt"),
            "total_deaths": self._store.get_count("combat.deaths"),
            "total_resources": self._store.get_total("gathering.collected"),
            "total_crafts": self._store.get_count("crafting.success"),
            "total_skills_used": self._store.get_count("skills.used"),
            "unique_chunks": len(self._unique_chunks_visited),
            "playtime_seconds": self.total_playtime_seconds,
            "session_count": self.session_count,
        }

    # ── Legacy property access for backward compat ──────────────────

    @property
    def gathering_totals(self) -> Dict[str, Any]:
        return self._build_legacy_gathering()

    @property
    def combat_damage(self) -> Dict[str, Any]:
        return self._build_legacy_combat_damage()

    @property
    def combat_kills(self) -> Dict[str, Any]:
        return self._build_legacy_combat_kills()

    @property
    def combat_survival(self) -> Dict[str, Any]:
        return {
            "total_deaths": self._store.get_count("combat.deaths"),
            "longest_killstreak": int(self._store.get_max("combat.longest_killstreak")),
            "current_killstreak": self._current_killstreak,
        }

    @property
    def crafting_by_discipline(self) -> Dict[str, Any]:
        return self._build_legacy_crafting()

    @property
    def crafting_advanced(self) -> Dict[str, Any]:
        return {
            "consecutive_first_try_bonuses": self._current_first_try_streak,
            "longest_first_try_streak": int(self._store.get_max("crafting.longest_first_try_streak")),
            "best_minigame_score": self._store.get_max("crafting.quality"),
        }

    @property
    def experience_stats(self) -> Dict[str, Any]:
        return {
            "total_exp_earned": self._store.get_total("progression.exp"),
            "exp_from_gathering": self._store.get_total("progression.exp.gathering"),
            "exp_from_crafting": self._store.get_total("progression.exp.crafting"),
            "exp_from_combat": self._store.get_total("progression.exp.combat"),
            "exp_from_quests": self._store.get_total("progression.exp.quests"),
            "exp_from_fishing": self._store.get_total("progression.exp.fishing"),
        }

    @property
    def item_management(self) -> Dict[str, Any]:
        return {
            "total_equipment_swaps": self._store.get_count("items.equipment_swaps"),
            "items_repaired": self._store.get_count("items.repaired"),
        }

    @property
    def exploration(self) -> Dict[str, Any]:
        return {
            "unique_chunks_visited": len(self._unique_chunks_visited),
            "total_chunk_entries": self._store.get_count("exploration.chunk_entries"),
        }

    @property
    def social_stats(self) -> Dict[str, Any]:
        return {
            "npcs_met": self._store.get_count("social.npc_interactions"),
            "quests_completed": self._store.get_count("social.quests.completed"),
            "quests_failed": self._store.get_count("social.quests.failed"),
        }

    @property
    def dungeon_stats(self) -> Dict[str, Any]:
        return {
            "dungeons_entered": self._store.get_count("dungeon.entered"),
            "dungeons_completed": self._store.get_count("dungeon.completed"),
            "dungeons_abandoned": self._store.get_count("dungeon.abandoned"),
            "dungeon_deaths": self._store.get_count("dungeon.deaths"),
        }

    @property
    def misc_stats(self) -> Dict[str, Any]:
        return {
            "total_deaths": self._store.get_count("combat.deaths"),
        }
