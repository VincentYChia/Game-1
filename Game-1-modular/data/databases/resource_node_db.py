"""Resource Node Database - loads resource definitions from JSON"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from data.models.resources import ResourceNodeDefinition, ResourceDrop


class ResourceNodeDatabase:
    """Singleton database for resource node definitions loaded from JSON"""
    _instance = None

    # Icon name mapping: JSON resource_id -> actual PNG filename (without extension)
    # This preserves compatibility with existing PNG files
    ICON_NAME_MAP = {
        # Trees - use resource_id directly (no suffix)
        'oak_tree': 'oak_tree',
        'pine_tree': 'pine_tree',
        'ash_tree': 'ash_tree',
        'birch_tree': 'birch_tree',
        'maple_tree': 'maple_tree',
        'ironwood_tree': 'ironwood_tree',
        'ebony_tree': 'ebony_tree',
        'worldtree_sapling': 'worldtree_sapling',
        # Ores - map new JSON IDs to existing PNG names (with _node suffix in file)
        'copper_vein': 'copper_ore_node',
        'iron_deposit': 'iron_ore_node',
        'tin_seam': 'tin_seam',  # New resource, uses JSON ID
        'steel_node': 'steel_ore_node',
        'mithril_cache': 'mithril_ore_node',
        'adamantine_lode': 'adamantine_lode',  # New resource
        'orichalcum_trove': 'orichalcum_trove',  # New resource
        'etherion_nexus': 'etherion_nexus',  # New resource
        # Stones - map new JSON IDs to existing PNG names
        'limestone_outcrop': 'limestone_node',
        'granite_formation': 'granite_node',
        'shale_bed': 'shale_bed',  # New resource
        'basalt_column': 'basalt_column',  # New resource
        'marble_quarry': 'marble_quarry',  # New resource
        'quartz_cluster': 'quartz_cluster',  # New resource
        'obsidian_flow': 'obsidian_node',
        'voidstone_shard': 'voidstone_shard',  # New resource
        'diamond_geode': 'diamond_geode',  # New resource (replaces star_crystal)
        'eternity_monolith': 'eternity_monolith',  # New resource
        'primordial_formation': 'primordial_formation',  # New resource
        'genesis_structure': 'genesis_structure',  # New resource
    }

    def __init__(self):
        self.nodes: Dict[str, ResourceNodeDefinition] = {}
        self.loaded = False
        # Cached lists by category for spawn logic
        self._trees: List[ResourceNodeDefinition] = []
        self._ores: List[ResourceNodeDefinition] = []
        self._stones: List[ResourceNodeDefinition] = []
        # Mapping from resource_id to tier
        self._tier_map: Dict[str, int] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ResourceNodeDatabase()
        return cls._instance

    def load_from_file(self, filepath: str) -> bool:
        """Load resource node definitions from JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            for node_data in data.get('nodes', []):
                resource_id = node_data.get('resourceId', '')
                if not resource_id:
                    continue

                # Parse drops
                drops = []
                for drop_data in node_data.get('drops', []):
                    drops.append(ResourceDrop(
                        material_id=drop_data.get('materialId', ''),
                        quantity=drop_data.get('quantity', 'several'),
                        chance=drop_data.get('chance', 'guaranteed')
                    ))

                # Parse metadata
                metadata = node_data.get('metadata', {})
                tags = metadata.get('tags', [])
                narrative = metadata.get('narrative', '')

                node = ResourceNodeDefinition(
                    resource_id=resource_id,
                    name=node_data.get('name', ''),
                    category=node_data.get('category', ''),
                    tier=node_data.get('tier', 1),
                    required_tool=node_data.get('requiredTool', 'pickaxe'),
                    base_health=node_data.get('baseHealth', 100),
                    drops=drops,
                    respawn_time=node_data.get('respawnTime'),
                    tags=tags,
                    narrative=narrative
                )

                self.nodes[resource_id] = node
                self._tier_map[resource_id] = node.tier

                # Cache by category
                if node.is_tree:
                    self._trees.append(node)
                elif node.is_ore:
                    self._ores.append(node)
                elif node.is_stone:
                    self._stones.append(node)

            self.loaded = True
            print(f"[ResourceNodeDB] Loaded {len(self.nodes)} resource nodes "
                  f"({len(self._trees)} trees, {len(self._ores)} ores, {len(self._stones)} stones)")
            return True

        except Exception as e:
            print(f"[ResourceNodeDB] Error loading resource nodes: {e}")
            self._create_placeholders()
            return False

    def _create_placeholders(self):
        """Create minimal placeholders for essential resources"""
        placeholders = [
            # Trees
            ("oak_tree", "Oak Tree", "tree", 1, "axe", 100, [("oak_log", "many", "guaranteed")], "normal"),
            ("birch_tree", "Birch Tree", "tree", 2, "axe", 200, [("birch_log", "several", "guaranteed")], "slow"),
            ("maple_tree", "Maple Tree", "tree", 2, "axe", 200, [("maple_log", "several", "high")], "very_slow"),
            ("ironwood_tree", "Ironwood Tree", "tree", 3, "axe", 400, [("ironwood_log", "few", "high")], "very_slow"),
            # Ores
            ("copper_vein", "Copper Vein", "ore", 1, "pickaxe", 100, [("copper_ore", "many", "guaranteed")], None),
            ("iron_deposit", "Iron Deposit", "ore", 1, "pickaxe", 100, [("iron_ore", "many", "guaranteed")], None),
            ("steel_node", "Steel Node", "ore", 2, "pickaxe", 200, [("steel_ore", "several", "guaranteed")], None),
            ("mithril_cache", "Mithril Cache", "ore", 2, "pickaxe", 200, [("mithril_ore", "few", "high")], None),
            # Stones
            ("limestone_outcrop", "Limestone Outcrop", "stone", 1, "pickaxe", 100, [("limestone", "abundant", "guaranteed")], None),
            ("granite_formation", "Granite Formation", "stone", 1, "pickaxe", 100, [("granite", "abundant", "guaranteed")], None),
            ("obsidian_flow", "Obsidian Flow", "stone", 3, "pickaxe", 400, [("obsidian", "several", "guaranteed")], None),
        ]

        for res_id, name, category, tier, tool, health, drops_data, respawn in placeholders:
            drops = [ResourceDrop(d[0], d[1], d[2]) for d in drops_data]
            node = ResourceNodeDefinition(
                resource_id=res_id,
                name=name,
                category=category,
                tier=tier,
                required_tool=tool,
                base_health=health,
                drops=drops,
                respawn_time=respawn
            )
            self.nodes[res_id] = node
            self._tier_map[res_id] = tier
            if node.is_tree:
                self._trees.append(node)
            elif node.is_ore:
                self._ores.append(node)
            elif node.is_stone:
                self._stones.append(node)

        self.loaded = True
        print(f"[ResourceNodeDB] Created {len(self.nodes)} placeholder resource nodes")

    def get_node(self, resource_id: str) -> Optional[ResourceNodeDefinition]:
        """Get a resource node definition by ID"""
        return self.nodes.get(resource_id)

    def get_tier(self, resource_id: str) -> int:
        """Get the tier of a resource by ID"""
        return self._tier_map.get(resource_id, 1)

    def get_all_trees(self) -> List[ResourceNodeDefinition]:
        """Get all tree resource nodes"""
        return self._trees

    def get_all_ores(self) -> List[ResourceNodeDefinition]:
        """Get all ore resource nodes"""
        return self._ores

    def get_all_stones(self) -> List[ResourceNodeDefinition]:
        """Get all stone resource nodes"""
        return self._stones

    def get_trees_by_tier(self, max_tier: int) -> List[ResourceNodeDefinition]:
        """Get trees up to and including max_tier"""
        return [t for t in self._trees if t.tier <= max_tier]

    def get_ores_by_tier(self, max_tier: int) -> List[ResourceNodeDefinition]:
        """Get ores up to and including max_tier"""
        return [o for o in self._ores if o.tier <= max_tier]

    def get_stones_by_tier(self, max_tier: int) -> List[ResourceNodeDefinition]:
        """Get stones up to and including max_tier"""
        return [s for s in self._stones if s.tier <= max_tier]

    def get_resources_for_chunk(self, chunk_type: str, tier_range: tuple) -> List[ResourceNodeDefinition]:
        """Get appropriate resources for a chunk type and tier range

        Args:
            chunk_type: String containing category hint (e.g., "peaceful_forest", "dangerous_quarry")
            tier_range: Tuple of (min_tier, max_tier)

        Returns:
            List of ResourceNodeDefinition that can spawn in this chunk
        """
        min_tier, max_tier = tier_range

        # Determine category from chunk type
        if "forest" in chunk_type:
            candidates = self._trees
        elif "quarry" in chunk_type:
            candidates = self._stones
        else:  # cave
            candidates = self._ores

        # Filter by tier range
        return [r for r in candidates if min_tier <= r.tier <= max_tier]

    def get_all_resource_ids(self) -> List[str]:
        """Get all resource IDs"""
        return list(self.nodes.keys())

    def build_tier_map(self) -> Dict[str, int]:
        """Build and return the tier map for all resources

        This can be used to populate RESOURCE_TIERS dynamically
        """
        return dict(self._tier_map)

    def get_icon_name(self, resource_id: str) -> str:
        """Get the icon filename (without extension) for a resource

        Maps JSON resource_id to the actual PNG filename to preserve
        compatibility with existing icon files.

        Args:
            resource_id: The resource ID from JSON (e.g., 'copper_vein')

        Returns:
            Icon filename without extension (e.g., 'copper_ore_node')
        """
        return self.ICON_NAME_MAP.get(resource_id, resource_id)

    def get_icon_path(self, resource_id: str) -> str:
        """Get the full icon path for a resource

        Args:
            resource_id: The resource ID from JSON

        Returns:
            Path like 'resources/copper_ore_node.png'
        """
        icon_name = self.get_icon_name(resource_id)
        return f"resources/{icon_name}.png"
