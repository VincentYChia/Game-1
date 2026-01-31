"""Natural resource system for harvestable world resources - JSON-driven via ResourceNodeDatabase"""

import random
from typing import List, Tuple, Optional

from data.models import Position, ResourceType, LootDrop
from core.config import Config


class NaturalResource:
    # Class-level database reference
    _resource_db = None

    def __init__(self, position: Position, resource_type: ResourceType, tier: int):
        self.position = position
        self.resource_type = resource_type
        self.tier = tier

        # Try to get properties from JSON database
        node_def = self._get_node_definition()

        if node_def:
            # JSON-driven properties
            self.max_hp = node_def.base_health
            self.required_tool = node_def.required_tool
            self.respawns = node_def.does_respawn()
            respawn_seconds = node_def.get_respawn_seconds()
            self.respawn_timer = (respawn_seconds if respawn_seconds else None)
            if Config.DEBUG_INFINITE_RESOURCES and self.respawns:
                self.respawn_timer = 1.0
        else:
            # Fallback to hardcoded defaults
            self.max_hp = {1: 100, 2: 200, 3: 400, 4: 800}.get(tier, 100)
            if "tree" in resource_type.value:
                self.required_tool = "axe"
                self.respawns = True
                self.respawn_timer = 60.0 if not Config.DEBUG_INFINITE_RESOURCES else 1.0
            elif "fishing_spot" in resource_type.value:
                # All fishing spots (carp, sunfish, stormfin, etc.)
                self.required_tool = "fishing_rod"
                self.respawns = True
                # Higher tier fishing spots respawn slower
                base_respawn = {1: 30.0, 2: 45.0, 3: 60.0, 4: 90.0}.get(tier, 30.0)
                self.respawn_timer = base_respawn if not Config.DEBUG_INFINITE_RESOURCES else 1.0
                # Fishing spot HP scales with tier
                self.max_hp = {1: 50, 2: 75, 3: 100, 4: 150}.get(tier, 50)
            else:
                self.required_tool = "pickaxe"
                self.respawns = False
                self.respawn_timer = None

        self.current_hp = self.max_hp
        self.time_until_respawn = 0.0
        self.loot_table = self._generate_loot_table()
        self.depleted = False

    @classmethod
    def _get_resource_db(cls):
        """Get the ResourceNodeDatabase singleton"""
        if cls._resource_db is None:
            try:
                from data.databases.resource_node_db import ResourceNodeDatabase
                cls._resource_db = ResourceNodeDatabase.get_instance()
            except ImportError:
                cls._resource_db = None
        return cls._resource_db

    def _get_node_definition(self):
        """Get the node definition from database"""
        db = self._get_resource_db()
        if db and db.loaded:
            return db.get_node(self.resource_type.value)
        return None

    def _generate_loot_table(self) -> List[LootDrop]:
        """Generate loot table from JSON database or fallback to hardcoded"""
        # Try JSON database first
        node_def = self._get_node_definition()
        if node_def and node_def.drops:
            loot_drops = []
            for drop in node_def.drops:
                min_q, max_q = drop.get_quantity_range()
                chance = drop.get_chance_value()
                loot_drops.append(LootDrop(drop.material_id, min_q, max_q, chance))
            return loot_drops

        # Fallback to expanded hardcoded map (all 28 resources)
        loot_map = {
            # Trees
            ResourceType.OAK_TREE: ("oak_log", 3, 5),
            ResourceType.PINE_TREE: ("pine_log", 3, 5),
            ResourceType.ASH_TREE: ("ash_log", 2, 4),
            ResourceType.BIRCH_TREE: ("birch_log", 2, 4),
            ResourceType.MAPLE_TREE: ("maple_log", 2, 4),
            ResourceType.IRONWOOD_TREE: ("ironwood_log", 1, 2),
            ResourceType.EBONY_TREE: ("ebony_log", 1, 2),
            ResourceType.WORLDTREE_SAPLING: ("worldtree_log", 1, 2),
            # Ores
            ResourceType.COPPER_VEIN: ("copper_ore", 3, 5),
            ResourceType.IRON_DEPOSIT: ("iron_ore", 3, 5),
            ResourceType.TIN_SEAM: ("tin_ore", 2, 4),
            ResourceType.STEEL_NODE: ("steel_ore", 2, 4),
            ResourceType.MITHRIL_CACHE: ("mithril_ore", 1, 2),
            ResourceType.ADAMANTINE_LODE: ("adamantine_ore", 1, 2),
            ResourceType.ORICHALCUM_TROVE: ("orichalcum_ore", 1, 2),
            ResourceType.ETHERION_NEXUS: ("etherion_ore", 1, 2),
            # Stones
            ResourceType.LIMESTONE_OUTCROP: ("limestone", 4, 8),
            ResourceType.GRANITE_FORMATION: ("granite", 4, 8),
            ResourceType.SHALE_BED: ("shale", 3, 5),
            ResourceType.BASALT_COLUMN: ("basalt", 2, 4),
            ResourceType.MARBLE_QUARRY: ("marble", 2, 4),
            ResourceType.QUARTZ_CLUSTER: ("crystal_quartz", 2, 4),
            ResourceType.OBSIDIAN_FLOW: ("obsidian", 2, 4),
            ResourceType.VOIDSTONE_SHARD: ("voidstone", 1, 2),
            ResourceType.DIAMOND_GEODE: ("diamond", 1, 2),
            ResourceType.ETERNITY_MONOLITH: ("eternity_stone", 1, 2),
            ResourceType.PRIMORDIAL_FORMATION: ("primordial_crystal", 1, 2),
            ResourceType.GENESIS_STRUCTURE: ("genesis_lattice", 1, 2),
            # Legacy aliases
            ResourceType.COPPER_ORE: ("copper_ore", 1, 3),
            ResourceType.IRON_ORE: ("iron_ore", 1, 3),
            ResourceType.STEEL_ORE: ("steel_ore", 2, 4),
            ResourceType.MITHRIL_ORE: ("mithril_ore", 2, 5),
            ResourceType.LIMESTONE: ("limestone", 1, 2),
            ResourceType.GRANITE: ("granite", 1, 2),
            ResourceType.OBSIDIAN: ("obsidian", 2, 3),
            ResourceType.STAR_CRYSTAL: ("diamond", 1, 2),
            # Water resources
            ResourceType.FISHING_SPOT: ("raw_fish", 1, 3),
        }
        if self.resource_type in loot_map:
            item_id, min_q, max_q = loot_map[self.resource_type]
            return [LootDrop(item_id, min_q, max_q)]
        return []

    def take_damage(self, damage: int, is_crit: bool = False) -> Tuple[int, bool]:
        if self.depleted:
            return 0, False
        actual_damage = damage * 2 if is_crit else damage
        self.current_hp -= actual_damage
        if self.current_hp <= 0:
            self.current_hp = 0
            self.depleted = True
            return actual_damage, True
        return actual_damage, False

    def get_loot(self) -> List[Tuple[str, int]]:
        return [(loot.item_id, random.randint(loot.min_quantity, loot.max_quantity))
                for loot in self.loot_table if random.random() <= loot.chance]

    def update(self, dt: float):
        if self.depleted and self.respawns:
            self.time_until_respawn += dt
            if self.time_until_respawn >= self.respawn_timer:
                self.current_hp = self.max_hp
                self.depleted = False
                self.time_until_respawn = 0.0

    def get_respawn_progress(self) -> float:
        if not self.depleted or not self.respawns:
            return 0.0
        return min(1.0, self.time_until_respawn / self.respawn_timer)

    def get_color(self) -> Tuple[int, int, int]:
        if self.depleted:
            if self.respawns:
                progress = self.get_respawn_progress()
                gray = int(50 + progress * 50)
                green = int(progress * 100)
                return (gray, green, gray)
            return (50, 50, 50)

        # Determine color based on resource category
        res_value = self.resource_type.value.lower()

        # Trees: contain "tree" or "sapling"
        if "tree" in res_value or "sapling" in res_value:
            return Config.COLOR_TREE

        # Fishing spots (all types)
        if "fishing_spot" in res_value:
            return (0, 191, 255)  # Deep sky blue for fishing spots

        # Ores: contain ore-related keywords
        ore_keywords = ["vein", "deposit", "seam", "node", "cache", "lode", "trove", "nexus", "ore"]
        if any(kw in res_value for kw in ore_keywords):
            return Config.COLOR_ORE

        # Stones: everything else (outcrop, formation, bed, column, quarry, cluster, flow, shard, geode, monolith)
        return Config.COLOR_STONE_NODE
