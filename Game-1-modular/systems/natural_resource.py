"""Natural resource system for harvestable world resources

Loot tables and resource properties are loaded from JSON files:
- Definitions.JSON/resource-node-1.JSON - Resource node definitions
- Definitions.JSON/value-translation-tables-1.JSON - Qualitative value mappings
"""

import os
import json
import random
from typing import List, Tuple, Dict, Any, Optional

from data.models import Position, ResourceType, LootDrop
from core.config import Config


# Module-level cache for JSON data
_resource_nodes_cache: Optional[Dict[str, Any]] = None
_translation_tables_cache: Optional[Dict[str, Any]] = None
_json_load_warned: bool = False


def _load_resource_nodes() -> Dict[str, Any]:
    """Load resource node definitions from JSON file."""
    global _resource_nodes_cache, _json_load_warned

    if _resource_nodes_cache is not None:
        return _resource_nodes_cache

    json_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "Definitions.JSON", "resource-node-1.JSON"
    )

    try:
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
                # Index by resourceId for quick lookup
                _resource_nodes_cache = {}
                for node in data.get("nodes", []):
                    resource_id = node.get("resourceId", "")
                    if resource_id:
                        _resource_nodes_cache[resource_id] = node
                return _resource_nodes_cache
    except (json.JSONDecodeError, IOError) as e:
        if not _json_load_warned:
            print(f"⚠️ DEBUG: Failed to load resource-node-1.JSON: {e}")

    if not _json_load_warned:
        _json_load_warned = True
        print(f"⚠️ DEBUG: Using HARDCODED resource loot tables - JSON not found at: {json_path}")

    _resource_nodes_cache = {}
    return _resource_nodes_cache


def _load_translation_tables() -> Dict[str, Any]:
    """Load value translation tables from JSON file."""
    global _translation_tables_cache

    if _translation_tables_cache is not None:
        return _translation_tables_cache

    json_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "Definitions.JSON", "value-translation-tables-1.JSON"
    )

    try:
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                _translation_tables_cache = json.load(f)
                return _translation_tables_cache
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ DEBUG: Failed to load value-translation-tables-1.JSON: {e}")

    # Hardcoded fallback
    _translation_tables_cache = {
        "quantities": {
            "few": {"min": 1, "max": 2},
            "several": {"min": 2, "max": 4},
            "many": {"min": 3, "max": 5},
            "abundant": {"min": 4, "max": 6}
        },
        "chances": {
            "guaranteed": 1.0,
            "high": 0.8,
            "moderate": 0.5,
            "low": 0.25,
            "rare": 0.1,
            "improbable": 0.05
        },
        "respawnTimes": {
            "fast": 30.0,
            "normal": 60.0,
            "slow": 120.0,
            "very_slow": 300.0
        }
    }
    return _translation_tables_cache


def _translate_quantity(qty_str: str) -> Tuple[int, int]:
    """Translate qualitative quantity to min/max values."""
    tables = _load_translation_tables()
    quantities = tables.get("quantities", {})

    if qty_str in quantities:
        qty_data = quantities[qty_str]
        return qty_data.get("min", 1), qty_data.get("max", 2)

    # Try parsing as int range (e.g., "2-4")
    if "-" in qty_str:
        try:
            parts = qty_str.split("-")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass

    return 1, 2  # Default fallback


def _translate_chance(chance_str: str) -> float:
    """Translate qualitative chance to float value."""
    tables = _load_translation_tables()
    chances = tables.get("chances", {})

    if chance_str in chances:
        return chances[chance_str]

    # Try parsing as float
    try:
        return float(chance_str)
    except ValueError:
        pass

    return 1.0  # Default to guaranteed


def _get_resource_node_data(resource_type: ResourceType) -> Optional[Dict[str, Any]]:
    """Get resource node data from JSON by matching resourceId to ResourceType."""
    nodes = _load_resource_nodes()

    # Map ResourceType enum values to JSON resourceId patterns
    type_to_id_map = {
        ResourceType.OAK_TREE: "oak_tree",
        ResourceType.BIRCH_TREE: "birch_tree",
        ResourceType.MAPLE_TREE: "maple_tree",
        ResourceType.IRONWOOD_TREE: "ironwood_tree",
        ResourceType.COPPER_ORE: "copper_vein",
        ResourceType.IRON_ORE: "iron_deposit",
        ResourceType.STEEL_ORE: "steel_node",
        ResourceType.MITHRIL_ORE: "mithril_cache",
        ResourceType.LIMESTONE: "limestone_outcrop",
        ResourceType.GRANITE: "granite_formation",
        ResourceType.OBSIDIAN: "obsidian_flow",
        ResourceType.STAR_CRYSTAL: "diamond_geode",  # Map star_crystal to diamond
        ResourceType.FISHING_SPOT: None,  # No JSON definition for fishing
    }

    resource_id = type_to_id_map.get(resource_type)
    if resource_id and resource_id in nodes:
        return nodes[resource_id]

    return None


class NaturalResource:
    # Hardcoded fallback loot table (used when JSON not available)
    _HARDCODED_LOOT_MAP = {
        ResourceType.OAK_TREE: ("oak_log", 2, 4),
        ResourceType.BIRCH_TREE: ("birch_log", 2, 4),
        ResourceType.MAPLE_TREE: ("maple_log", 2, 5),
        ResourceType.IRONWOOD_TREE: ("ironwood_log", 3, 6),
        ResourceType.COPPER_ORE: ("copper_ore", 1, 3),
        ResourceType.IRON_ORE: ("iron_ore", 1, 3),
        ResourceType.STEEL_ORE: ("steel_ore", 2, 4),
        ResourceType.MITHRIL_ORE: ("mithril_ore", 2, 5),
        ResourceType.LIMESTONE: ("limestone", 1, 2),
        ResourceType.GRANITE: ("granite", 1, 2),
        ResourceType.OBSIDIAN: ("obsidian", 2, 3),
        ResourceType.STAR_CRYSTAL: ("star_crystal", 1, 2),
        ResourceType.FISHING_SPOT: ("raw_fish", 1, 3),
    }

    def __init__(self, position: Position, resource_type: ResourceType, tier: int):
        self.position = position
        self.resource_type = resource_type
        self.tier = tier

        # Try to load from JSON first
        node_data = _get_resource_node_data(resource_type)

        if node_data:
            # Use JSON-defined values
            self.max_hp = node_data.get("baseHealth", {1: 100, 2: 200, 3: 400, 4: 800}.get(tier, 100))
            self.required_tool = node_data.get("requiredTool", "pickaxe")

            # Respawn settings from JSON
            respawn_time_str = node_data.get("respawnTime")
            if respawn_time_str and respawn_time_str != "null":
                self.respawns = True
                tables = _load_translation_tables()
                respawn_times = tables.get("respawnTimes", {})
                self.respawn_timer = respawn_times.get(respawn_time_str, 60.0)
                if Config.DEBUG_INFINITE_RESOURCES:
                    self.respawn_timer = 1.0
            else:
                self.respawns = False
                self.respawn_timer = None
        else:
            # Fallback to hardcoded logic
            self.max_hp = {1: 100, 2: 200, 3: 400, 4: 800}.get(tier, 100)

            if "tree" in resource_type.value:
                self.required_tool = "axe"
                self.respawns = True
                self.respawn_timer = 60.0 if not Config.DEBUG_INFINITE_RESOURCES else 1.0
            elif resource_type == ResourceType.FISHING_SPOT:
                self.required_tool = "fishing_rod"
                self.respawns = True
                self.respawn_timer = 30.0 if not Config.DEBUG_INFINITE_RESOURCES else 1.0
                self.max_hp = 50  # Fishing spots are quick to "deplete"
            else:
                self.required_tool = "pickaxe"
                self.respawns = False
                self.respawn_timer = None

        self.current_hp = self.max_hp
        self.time_until_respawn = 0.0
        self.loot_table = self._generate_loot_table()
        self.depleted = False

    def _generate_loot_table(self) -> List[LootDrop]:
        """Generate loot table from JSON definitions or fallback to hardcoded values."""
        node_data = _get_resource_node_data(self.resource_type)

        if node_data and "drops" in node_data:
            # Load from JSON
            loot_drops = []
            for drop in node_data["drops"]:
                material_id = drop.get("materialId", "")
                if not material_id:
                    continue

                # Translate qualitative values
                qty_str = drop.get("quantity", "several")
                chance_str = drop.get("chance", "guaranteed")

                min_qty, max_qty = _translate_quantity(qty_str)
                chance = _translate_chance(chance_str)

                loot_drops.append(LootDrop(material_id, min_qty, max_qty, chance))

            if loot_drops:
                return loot_drops

        # Hardcoded fallback
        if self.resource_type in self._HARDCODED_LOOT_MAP:
            item_id, min_q, max_q = self._HARDCODED_LOOT_MAP[self.resource_type]
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
        if "tree" in self.resource_type.value:
            return Config.COLOR_TREE
        if self.resource_type == ResourceType.FISHING_SPOT:
            return (0, 191, 255)  # Deep sky blue for fishing spots
        return Config.COLOR_ORE if "ore" in self.resource_type.value else Config.COLOR_STONE_NODE
