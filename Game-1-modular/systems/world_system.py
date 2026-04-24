"""World system for managing the game world, tiles, resources, and stations.

Supports infinite world generation through seed-based deterministic chunk loading.
Chunks are loaded on-demand as the player explores and unloaded to save memory.
"""

import math
import random
import os
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Set, Any

from data.models import (
    Position, WorldTile, TileType, StationType, CraftingStation,
    PlacedEntity, PlacedEntityType, DungeonRarity, DungeonEntrance
)
from data.models.world import DUNGEON_CONFIG
from systems.dungeon import LootChest
from systems.natural_resource import NaturalResource
from systems.chunk import Chunk
from systems.biome_generator import BiomeGenerator
from data.databases.world_generation_db import WorldGenerationConfig
from core.config import Config
from core.paths import get_save_path


class WorldSystem:
    """Manages the finite game world with lazy chunk loading.

    The world is generated from a seed using the geographic system:
    World -> Nations -> Regions -> Provinces -> Districts -> Biomes -> Ecosystems

    Attributes:
        seed: World seed for deterministic generation
        biome_generator: BiomeGenerator for chunk type determination (legacy)
        geographic_map: WorldMap from the geographic system (new)
        loaded_chunks: Dictionary of currently loaded chunks
    """

    def __init__(self, seed: Optional[int] = None):
        """Initialize the world system.

        Args:
            seed: World seed for deterministic generation. If None, generates random seed.
        """
        # Generate or use provided seed
        self.seed = seed if seed is not None else random.randint(0, 2**32 - 1)
        self._world_rng = random.Random(self.seed)

        # Initialize biome generator (legacy fallback)
        self.biome_generator = BiomeGenerator(self.seed)

        # Initialize geographic system (new finite world)
        self.geographic_map = None
        self.map_images = {}  # Pre-rendered map LOD surfaces
        self._villages = []  # Village definitions from geographic system
        self._village_chunks = set()  # Set of (cx,cy) that are part of villages
        self._village_npcs = []  # NPC instances spawned in villages
        self._init_geographic_system()
        self.loaded_chunks: Dict[Tuple[int, int], Chunk] = {}
        self._chunk_save_dir: Optional[Path] = None  # Set when save path known

        # World state tracking
        self.game_time: float = 0.0  # For respawn calculations

        # Fixed entities (not chunk-dependent)
        self.crafting_stations: List[CraftingStation] = []
        self.placed_entities: List[PlacedEntity] = []

        # Barrier position cache for O(1) collision lookup
        # Key: (tile_x, tile_y), avoids iterating all entities in is_walkable
        self._barrier_positions: Set[Tuple[int, int]] = set()

        # Discovered dungeon entrances (persisted once found)
        self.discovered_dungeon_entrances: Dict[Tuple[int, int], DungeonEntrance] = {}

        # Dungeon manager reference (set by game_engine)
        self.dungeon_manager = None

        # Map system reference (set by game_engine) for death chest markers
        self.map_system = None

        # Spawn storage chest (player-placed items)
        self.spawn_storage_chest = None  # Will be set in spawn_storage_chest()

        # Death chests (items dropped on death)
        self.death_chests: List[LootChest] = []

        # Callbacks fired when a chunk is unloaded, signature: (chunk_key: Tuple[int,int]) -> None
        self._on_chunk_unload_callbacks: List[Callable[[Tuple[int, int]], None]] = []

        # Load initial chunks and spawn fixed content
        self._load_initial_chunks()
        self.spawn_starting_stations()
        self.spawn_spawn_storage_chest()

        if self.geographic_map:
            nm = len(self.geographic_map.nations)
            nr = len(self.geographic_map.regions)
            np_ = len(self.geographic_map.provinces)
            nd = len(self.geographic_map.districts)
            print(f"🌍 World initialized with seed: {self.seed}")
            print(f"   Geographic: {nm} nations, {nr} regions, {np_} provinces, {nd} districts")
            print(f"   Loaded {len(self.loaded_chunks)} initial chunks")
            self._print_world_debug()
        else:
            print(f"🌍 World initialized with seed: {self.seed} (legacy mode)")
            print(f"   Loaded {len(self.loaded_chunks)} initial chunks")

    def _print_world_debug(self):
        """Print debug statistics about the generated world."""
        if not self.geographic_map:
            return
        gm = self.geographic_map
        cd = gm.chunk_data

        # Chunk type distribution
        type_counts = {}
        for geo in cd.values():
            ct = geo.chunk_type.value if hasattr(geo.chunk_type, 'value') else str(geo.chunk_type)
            type_counts[ct] = type_counts.get(ct, 0) + 1

        print(f"\n   ═══ WORLD DEBUG ═══")
        print(f"   Chunk type distribution ({len(cd):,} total):")
        for ct, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            pct = count / len(cd) * 100
            print(f"      {ct:25s}: {count:6,} ({pct:5.1f}%)")

        # Danger level distribution
        danger_counts = {}
        for geo in cd.values():
            dl = geo.danger_level
            name = dl.name if hasattr(dl, 'name') else str(dl)
            danger_counts[name] = danger_counts.get(name, 0) + 1

        print(f"   Danger distribution:")
        for name, count in sorted(danger_counts.items()):
            pct = count / len(cd) * 100
            print(f"      {name:12s}: {count:6,} ({pct:5.1f}%)")

        # Region identity distribution
        identity_counts = {}
        for rid, reg in gm.regions.items():
            identity_counts[reg.identity.value] = identity_counts.get(reg.identity.value, 0) + reg.chunk_count

        print(f"   Region identities (by chunk coverage):")
        for ident, count in sorted(identity_counts.items(), key=lambda x: -x[1]):
            pct = count / len(cd) * 100
            print(f"      {ident:15s}: {count:6,} ({pct:5.1f}%)")

        # Loaded chunk types (verify bridge table works)
        loaded_types = {}
        for chunk in self.loaded_chunks.values():
            ct = chunk.chunk_type
            loaded_types[ct] = loaded_types.get(ct, 0) + 1
        print(f"   Loaded chunk types (spawn area, {len(self.loaded_chunks)} chunks):")
        for ct, count in sorted(loaded_types.items()):
            print(f"      {ct}: {count}")

        # Verify resources spawned in loaded chunks
        total_resources = sum(len(c.resources) for c in self.loaded_chunks.values())
        resource_types = {}
        for chunk in self.loaded_chunks.values():
            for res in chunk.resources:
                rt = res.resource_type
                resource_types[rt] = resource_types.get(rt, 0) + 1
        print(f"   Resources in loaded chunks: {total_resources}")
        for rt, count in sorted(resource_types.items(), key=lambda x: -x[1])[:10]:
            print(f"      {rt}: {count}")

        # Setting tag distribution (sample 1000 chunks)
        try:
            from systems.geography.setting_resolver import get_chunk_tags
            setting_counts = {}
            pop_counts = {}
            res_counts = {}
            sample = list(cd.values())[:5000]
            for geo in sample:
                tags = get_chunk_tags(geo, gm)
                setting_counts[tags["setting"]] = setting_counts.get(tags["setting"], 0) + 1
                pop_counts[tags["population_status"]] = pop_counts.get(tags["population_status"], 0) + 1
                res_counts[tags["resource_status"]] = res_counts.get(tags["resource_status"], 0) + 1
            print(f"   Setting tags (sample {len(sample)}):")
            for s, c in sorted(setting_counts.items(), key=lambda x: -x[1]):
                print(f"      {s}: {c}")
            print(f"   Population status:")
            for s, c in sorted(pop_counts.items(), key=lambda x: -x[1]):
                print(f"      {s}: {c}")
            print(f"   Resource status:")
            for s, c in sorted(res_counts.items(), key=lambda x: -x[1]):
                print(f"      {s}: {c}")
        except Exception as e:
            print(f"   Setting tags: failed ({e})")

        # Villages
        if self._villages:
            print(f"   Villages: {len(self._villages)}")
            for v in self._villages[:5]:
                print(f"      {v['name']} at chunk {v['center_chunk']}, {len(v.get('npc_positions', []))} NPCs")
            if len(self._villages) > 5:
                print(f"      ... and {len(self._villages) - 5} more")

        print(f"   ═══ END DEBUG ═══\n")

    def _get_geo_cache_path(self) -> str:
        """Get the cache file path for the geographic map."""
        from core.paths import PathManager
        save_path = PathManager().save_path
        return str(Path(save_path) / f"world_map_seed_{self.seed}.gz")

    def _init_geographic_system(self):
        """Initialize the geographic system for finite world generation.

        First tries to load a cached map from disk. If not found,
        generates the full world map and saves it for next time.
        """
        try:
            import time
            from systems.geography.models import WorldMap

            cache_path = self._get_geo_cache_path()

            # Try loading from cache first
            t_start = time.time()
            cached = WorldMap.load(cache_path)
            if cached and cached.seed == self.seed:
                self.geographic_map = cached
                self._rebuild_villages_from_localities()
                self._generate_map_images()
                elapsed = time.time() - t_start
                print(f"🗺️  Geographic map loaded from cache in {elapsed:.1f}s")
                return

            # Generate fresh
            print("🗺️  Generating geographic world map (first time)...")
            from systems.geography.world_generator import WorldGenerator
            from systems.geography.config import GeographicConfig

            cfg = GeographicConfig.load()
            gen = WorldGenerator(seed=self.seed, config=cfg)
            self.geographic_map = gen.generate(verbose=False)
            elapsed = time.time() - t_start
            print(f"🗺️  Geographic map generated in {elapsed:.1f}s")

            # Store village data
            self._villages = getattr(gen, '_villages', [])
            self._init_village_data()

            # Save to cache for next startup
            try:
                self.geographic_map.save(cache_path)
            except Exception as e:
                print(f"[Geographic] Cache save failed (non-fatal): {e}")

            # Generate pre-rendered map images
            self._generate_map_images()
        except Exception as e:
            print(f"[Geographic] Init failed (falling back to legacy): {e}")
            import traceback
            traceback.print_exc()
            self.geographic_map = None

    def _init_village_data(self):
        """Build village chunk lookup from village definitions."""
        self._village_chunks = set()
        for v in self._villages:
            for cx, cy in v.get("chunks", []):
                self._village_chunks.add((cx, cy))
        if self._villages:
            print(f"🏘️  {len(self._villages)} villages, {len(self._village_chunks)} village chunks")

    def _rebuild_villages_from_localities(self):
        """Reconstruct village data from cached WorldMap localities."""
        if not self.geographic_map:
            return
        self._villages = []
        rng = random.Random(self.seed + 777777)
        try:
            from systems.geography.village_generator import _load_config, _select_tier, _select_npc_template
            cfg = _load_config()
        except Exception:
            cfg = None

        for lid, loc in self.geographic_map.localities.items():
            if loc.feature_type == "village":
                if cfg:
                    _, tier = _select_tier(rng)
                else:
                    tier = {"size": 2, "npc_min": 3, "npc_max": 5, "entrances": 4,
                            "entrance_width": 3, "wall_inset": 1, "buildings_min": 2, "buildings_max": 4,
                            "building_width_range": [4, 6], "building_height_range": [3, 4]}

                size = tier.get("size", 2)
                npc_count = rng.randint(tier.get("npc_min", 3), tier.get("npc_max", 5))
                inset = tier.get("wall_inset", 1)
                inner_x = loc.chunk_x * 16 + inset + 3
                inner_y = loc.chunk_y * 16 + inset + 3
                inner_w = size * 16 - (inset + 3) * 2
                inner_h = size * 16 - (inset + 3) * 2

                npc_positions = []
                npc_templates = []
                for _ in range(npc_count):
                    nx = inner_x + rng.randint(2, max(3, inner_w - 2))
                    ny = inner_y + rng.randint(2, max(3, inner_h - 2))
                    npc_positions.append((nx, ny))
                    if cfg:
                        npc_templates.append(_select_npc_template(rng))
                    else:
                        npc_templates.append({"npc_id_prefix": "villager", "name": "Villager",
                                              "sprite_color": [180, 160, 140], "dialogue_lines": ["Hello!"]})

                chunks = loc.adjacent_chunks if loc.adjacent_chunks else [(loc.chunk_x, loc.chunk_y)]
                self._villages.append({
                    "center_chunk": (loc.chunk_x, loc.chunk_y),
                    "chunks": chunks,
                    "size": size,
                    "tier_config": tier,
                    "npc_positions": npc_positions,
                    "npc_templates": npc_templates,
                    "locality_id": lid,
                    "name": loc.name,
                })
        self._init_village_data()

    def _generate_map_images(self):
        """Generate pre-rendered map images for fast map rendering."""
        if not self.geographic_map:
            return
        try:
            import time
            t = time.time()
            from rendering.map_cache import generate_map_images
            from data.databases.map_waypoint_db import MapWaypointConfig
            config = MapWaypointConfig.get_instance()
            nation_colors = {}
            for nid, nd in self.geographic_map.nations.items():
                if nd.color:
                    nation_colors[nid] = nd.color
            self.map_images = generate_map_images(
                self.geographic_map, config.get_biome_color, nation_colors,
            )
            print(f"🗺️  Map images generated in {time.time() - t:.1f}s")
        except Exception as e:
            print(f"[MapCache] Generation failed (non-fatal): {e}")
            self.map_images = {}

    def _load_initial_chunks(self):
        """Load chunks around spawn that should always be loaded."""
        world_config = WorldGenerationConfig.get_instance()
        spawn_radius = world_config.chunk_loading.spawn_always_loaded_radius

        for cx in range(-spawn_radius, spawn_radius + 1):
            for cy in range(-spawn_radius, spawn_radius + 1):
                self.get_chunk(cx, cy)

    def in_world_bounds(self, chunk_x: int, chunk_y: int) -> bool:
        """Check if chunk coordinates are within the finite world."""
        if self.geographic_map:
            return self.geographic_map.in_bounds(chunk_x, chunk_y)
        return True  # Legacy: infinite world

    def get_chunk(self, chunk_x: int, chunk_y: int) -> Optional[Chunk]:
        """Get or generate a chunk at the given coordinates.

        Returns None if out of world bounds (finite world).
        This is the primary method for accessing chunks. It handles:
        - Loading from cache if already loaded
        - Loading from save file if previously saved
        - Generating new chunk if first access

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            The Chunk at the given coordinates
        """
        key = (chunk_x, chunk_y)

        # Enforce finite world boundaries
        if not self.in_world_bounds(chunk_x, chunk_y):
            return None

        # Return cached chunk if loaded
        if key in self.loaded_chunks:
            return self.loaded_chunks[key]

        # Try to load from save file
        chunk = self._load_chunk_from_file(chunk_x, chunk_y)

        if chunk is None:
            # Generate new chunk — pass geographic data if available
            geo_data = None
            if self.geographic_map:
                geo_data = self.geographic_map.get_chunk_data(chunk_x, chunk_y)
            chunk = Chunk(chunk_x, chunk_y,
                          biome_generator=self.biome_generator,
                          geographic_data=geo_data)

            # Check if dungeon should spawn in this chunk
            self._maybe_spawn_dungeon(chunk)

        # Apply village structures (walls/buildings) on EVERY load, not just generation
        # This ensures walls persist across save/load cycles
        if key in self._village_chunks:
            self._apply_village_to_chunk(chunk)

        self.loaded_chunks[key] = chunk
        return chunk

    def get_village_npc_definitions(self) -> list:
        """Get NPC definitions for all villages (for game_engine to spawn).

        Uses NPC templates from village data (selected from village-config.JSON).
        """
        npc_defs = []
        for village in self._villages:
            v_name = village.get("name", "Village")
            positions = village.get("npc_positions", [])
            templates = village.get("npc_templates", [])
            for i, (nx, ny) in enumerate(positions):
                if i < len(templates):
                    t = templates[i]
                else:
                    t = {"npc_id_prefix": "village_villager", "name": "Villager",
                         "sprite_color": [180, 160, 140],
                         "dialogue_lines": ["Hello!"]}
                npc_defs.append({
                    "npc_id": f"{t.get('npc_id_prefix', 'villager')}_{village['locality_id']}_{i}",
                    "name": f"{t['name']} of {v_name}",
                    "position": {"x": float(nx), "y": float(ny), "z": 0.0},
                    "sprite_color": t.get("sprite_color", [180, 160, 140]),
                    "interaction_radius": 2.5,
                    "dialogue_lines": t.get("dialogue_lines", ["Hello!"]),
                    "quests": [],
                })
        return npc_defs

    def _apply_village_to_chunk(self, chunk: Chunk):
        """Apply village structures (walls, buildings) to a chunk that's part of a village."""
        key = (chunk.chunk_x, chunk.chunk_y)
        # Find which village this chunk belongs to
        village = None
        for v in self._villages:
            if key in [tuple(c) for c in v.get("chunks", [])]:
                village = v
                break
        if not village:
            return

        from systems.geography.village_generator import get_village_wall_tiles, get_village_building_tiles

        # Get wall tile positions and check if any fall in this chunk
        wall_tiles = get_village_wall_tiles(village)
        building_groups = get_village_building_tiles(village, self.seed)

        cx_min = chunk.chunk_x * Config.CHUNK_SIZE
        cy_min = chunk.chunk_y * Config.CHUNK_SIZE
        cx_max = cx_min + Config.CHUNK_SIZE
        cy_max = cy_min + Config.CHUNK_SIZE

        # Place wall tiles as stone tiles (non-walkable)
        for wx, wy in wall_tiles:
            if cx_min <= wx < cx_max and cy_min <= wy < cy_max:
                tile_key = f"{wx},{wy},0"
                if tile_key in chunk.tiles:
                    chunk.tiles[tile_key] = WorldTile(
                        position=Position(wx, wy, 0),
                        tile_type=TileType.STONE,
                        walkable=False,
                    )

        # Place building walls
        for building in building_groups:
            for bx, by in building:
                if cx_min <= bx < cx_max and cy_min <= by < cy_max:
                    tile_key = f"{bx},{by},0"
                    if tile_key in chunk.tiles:
                        chunk.tiles[tile_key] = WorldTile(
                            position=Position(bx, by, 0),
                            tile_type=TileType.STONE,
                            walkable=False,
                        )

    def _maybe_spawn_dungeon(self, chunk: Chunk):
        """Check if a dungeon entrance should spawn in this chunk.

        Args:
            chunk: The chunk to potentially add a dungeon to
        """
        key = (chunk.chunk_x, chunk.chunk_y)

        # Check if we already have a discovered dungeon here
        if key in self.discovered_dungeon_entrances:
            chunk.dungeon_entrance = self.discovered_dungeon_entrances[key]
            return

        # Use biome generator to determine if dungeon should spawn
        if self.biome_generator.should_spawn_dungeon(chunk.chunk_x, chunk.chunk_y):
            # Generate position within chunk (avoid edges)
            start_x = chunk.chunk_x * Config.CHUNK_SIZE
            start_y = chunk.chunk_y * Config.CHUNK_SIZE

            # Use chunk's RNG for deterministic position
            tile_x = start_x + chunk._rng.randint(2, Config.CHUNK_SIZE - 3)
            tile_y = start_y + chunk._rng.randint(2, Config.CHUNK_SIZE - 3)

            pos = Position(tile_x, tile_y, 0)

            # Check tile is walkable (not water)
            tile = chunk.tiles.get(pos.to_key())
            if tile and tile.tile_type != TileType.WATER:
                rarity = self._roll_dungeon_rarity(chunk._rng)
                entrance = DungeonEntrance(position=pos, rarity=rarity)

                chunk.dungeon_entrance = entrance
                self.discovered_dungeon_entrances[key] = entrance

    def _roll_dungeon_rarity(self, rng: random.Random) -> DungeonRarity:
        """Roll for dungeon rarity based on spawn weights.

        Args:
            rng: Random number generator to use

        Returns:
            DungeonRarity based on weighted roll
        """
        total_weight = sum(DUNGEON_CONFIG[r]["spawn_weight"] for r in DungeonRarity)
        roll = rng.randint(1, total_weight)

        cumulative = 0
        for rarity in DungeonRarity:
            cumulative += DUNGEON_CONFIG[rarity]["spawn_weight"]
            if roll <= cumulative:
                return rarity

        return DungeonRarity.COMMON

    def spawn_starting_stations(self):
        """Spawn all tiers of crafting stations near player spawn at origin (0, 0).

        Stations are placed NORTH of spawn (negative Y) in a grid layout
        to avoid collision with player spawn position.
        """
        # Station layout: spread horizontally around X=0, placed north (Y < 0)
        station_positions = [
            (-8, StationType.SMITHING),
            (-4, StationType.REFINING),
            (0, StationType.ADORNMENTS),
            (4, StationType.ALCHEMY),
            (8, StationType.ENGINEERING),
        ]

        # Spawn T1-T4 of each station type, arranged vertically going north
        for base_x, stype in station_positions:
            for tier in range(1, 5):
                y = -10 - (tier - 1) * 2  # -10, -12, -14, -16
                self.crafting_stations.append(
                    CraftingStation(Position(base_x, y, 0), stype, tier)
                )

    def spawn_spawn_storage_chest(self):
        """Spawn a player storage chest near the spawn point.

        This chest allows players to store items for inventory management.
        Position: East of spawn at (3, -2) to be accessible but not blocking.
        """
        self.spawn_storage_chest = LootChest(
            position=Position(3, -2, 0),
            tier=1,
            is_opened=False,
            contents=[],  # Empty - player adds items
            is_player_storage=True,
            chest_id="spawn_storage_chest"
        )
        print("📦 Spawn storage chest placed at (3, -2)")

    def spawn_death_chest(self, position: Position, rich_items: List[Dict[str, Any]]) -> Optional[LootChest]:
        """Spawn a death chest at the given position containing dropped items.

        Death chests are created when a player dies with KEEP_INVENTORY off.
        They have a distinctive red color and persist until the player
        retrieves their items. Items are stored with full state (enchantments,
        durability, etc.) to be restored when retrieved.

        Args:
            position: Position where the player died
            rich_items: List of serialized item dictionaries with full state

        Returns:
            The created LootChest, or None if no items to store
        """
        if not rich_items:
            return None

        # Generate unique chest ID based on position and timestamp
        import time
        chest_id = f"death_chest_{int(position.x)}_{int(position.y)}_{int(time.time())}"

        # Build simple contents list for backwards compatibility
        simple_contents = []
        for item_data in rich_items:
            item_id = item_data.get('item_id') or item_data.get('material_id', 'unknown')
            quantity = item_data.get('quantity', 1)
            simple_contents.append((item_id, quantity))

        death_chest = LootChest(
            position=Position(position.x, position.y, position.z),
            tier=1,
            is_opened=False,
            contents=simple_contents,
            is_player_storage=True,  # Allow player to retrieve items
            chest_id=chest_id,
            is_death_chest=True,
            rich_contents=rich_items
        )

        self.death_chests.append(death_chest)

        # Mark chunk on map with skull icon
        chunk_x = int(position.x) // Config.CHUNK_SIZE
        chunk_y = int(position.y) // Config.CHUNK_SIZE
        if self.map_system:
            self.map_system.set_death_chest_marker(chunk_x, chunk_y, True)

        print(f"💀 Death chest spawned at ({position.x:.1f}, {position.y:.1f}) with {len(rich_items)} items")
        return death_chest

    def remove_death_chest(self, chest: LootChest):
        """Remove a death chest (when emptied or despawned).

        Args:
            chest: The death chest to remove
        """
        if chest in self.death_chests:
            self.death_chests.remove(chest)

            # Remove skull marker from map if no other death chests in this chunk
            chunk_x = int(chest.position.x) // Config.CHUNK_SIZE
            chunk_y = int(chest.position.y) // Config.CHUNK_SIZE
            # Check if any other death chests remain in this chunk
            has_other_chests = any(
                int(c.position.x) // Config.CHUNK_SIZE == chunk_x and
                int(c.position.y) // Config.CHUNK_SIZE == chunk_y
                for c in self.death_chests
            )
            if self.map_system and not has_other_chests:
                self.map_system.set_death_chest_marker(chunk_x, chunk_y, False)

            print(f"📦 Death chest removed: {chest.chest_id}")

    def get_nearby_death_chest(self, position: Position, max_distance: float = 1.5) -> Optional[LootChest]:
        """Get a death chest within interaction range.

        Args:
            position: Position to check from
            max_distance: Maximum distance for interaction

        Returns:
            The nearest death chest within range, or None
        """
        for chest in self.death_chests:
            if chest.position.distance_to(position) <= max_distance:
                return chest
        return None

    # =========================================================================
    # Chunk Loading Management
    # =========================================================================

    def register_chunk_unload_callback(self, callback: Callable[[Tuple[int, int]], None]):
        """Register a callback to be called when a chunk is unloaded.

        Args:
            callback: Function taking (chunk_x, chunk_y) tuple, called before chunk removal.
        """
        self._on_chunk_unload_callbacks.append(callback)

    def update_loaded_chunks(self, player_pos: Position):
        """Update which chunks are loaded based on player position.

        Loads chunks within load_radius of player and unloads distant ones.
        Radius values are read from world_generation.JSON configuration.

        Args:
            player_pos: Current player position
        """
        player_chunk_x = int(player_pos.x) // Config.CHUNK_SIZE
        player_chunk_y = int(player_pos.y) // Config.CHUNK_SIZE

        # Get chunk loading config from JSON
        world_config = WorldGenerationConfig.get_instance()
        load_radius = world_config.chunk_loading.load_radius
        spawn_radius = world_config.chunk_loading.spawn_always_loaded_radius

        # Determine which chunks should be loaded
        should_be_loaded: Set[Tuple[int, int]] = set()

        # Spawn area always loaded
        for dx in range(-spawn_radius, spawn_radius + 1):
            for dy in range(-spawn_radius, spawn_radius + 1):
                should_be_loaded.add((dx, dy))

        # Player vicinity (filtered by world bounds)
        for dx in range(-load_radius, load_radius + 1):
            for dy in range(-load_radius, load_radius + 1):
                pos = (player_chunk_x + dx, player_chunk_y + dy)
                if self.in_world_bounds(pos[0], pos[1]):
                    should_be_loaded.add(pos)

        # Load missing chunks
        for key in should_be_loaded:
            if key not in self.loaded_chunks:
                self.get_chunk(*key)

        # Unload distant chunks
        chunks_to_unload = []
        for key in self.loaded_chunks:
            if key not in should_be_loaded:
                chunks_to_unload.append(key)

        for key in chunks_to_unload:
            self._unload_chunk(key)

    def _unload_chunk(self, key: Tuple[int, int]):
        """Unload a chunk, saving its state if modified.

        Args:
            key: (chunk_x, chunk_y) tuple
        """
        if key not in self.loaded_chunks:
            return

        chunk = self.loaded_chunks[key]

        # Prepare for unload (records timestamp for respawn calculation)
        chunk.prepare_for_unload(self.game_time)

        # Save chunk if it has modifications
        if chunk.has_modifications():
            self._save_chunk_to_file(chunk)

        # Notify listeners (e.g. combat_manager cleans up enemies in this chunk)
        for callback in self._on_chunk_unload_callbacks:
            callback(key)

        # Remove from loaded chunks
        del self.loaded_chunks[key]

    def _get_chunk_file_path(self, chunk_x: int, chunk_y: int) -> Path:
        """Get the file path for a chunk's save data.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            Path to chunk save file
        """
        if self._chunk_save_dir is None:
            # Use default chunks directory in save folder
            self._chunk_save_dir = Path(get_save_path()) / "chunks"
            self._chunk_save_dir.mkdir(parents=True, exist_ok=True)

        return self._chunk_save_dir / f"chunk_{chunk_x}_{chunk_y}.json"

    def _save_chunk_to_file(self, chunk: Chunk):
        """Save a chunk's modifications to file.

        Args:
            chunk: The chunk to save
        """
        save_data = chunk.get_save_data()
        if save_data is None:
            return

        file_path = self._get_chunk_file_path(chunk.chunk_x, chunk.chunk_y)

        try:
            with open(file_path, 'w') as f:
                json.dump(save_data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save chunk ({chunk.chunk_x}, {chunk.chunk_y}): {e}")

    def _load_chunk_from_file(self, chunk_x: int, chunk_y: int) -> Optional[Chunk]:
        """Load a chunk from its save file if it exists.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            Loaded Chunk with restored state, or None if no save exists
        """
        file_path = self._get_chunk_file_path(chunk_x, chunk_y)

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                save_data = json.load(f)

            # Generate the base chunk
            chunk = Chunk(chunk_x, chunk_y, biome_generator=self.biome_generator)

            # Calculate elapsed time since unload
            unload_time = save_data.get("unload_timestamp", 0.0)
            elapsed_time = max(0.0, self.game_time - unload_time)

            # Restore modifications
            chunk.restore_modifications(save_data, elapsed_time)

            # Restore dungeon entrance if present
            if "dungeon_entrance" in save_data:
                entrance_data = save_data["dungeon_entrance"]
                pos = Position(
                    entrance_data["position"]["x"],
                    entrance_data["position"]["y"],
                    entrance_data["position"]["z"]
                )
                rarity = DungeonRarity(entrance_data["rarity"])
                entrance = DungeonEntrance(position=pos, rarity=rarity)

                chunk.dungeon_entrance = entrance
                self.discovered_dungeon_entrances[(chunk_x, chunk_y)] = entrance

            return chunk

        except Exception as e:
            print(f"Warning: Failed to load chunk ({chunk_x}, {chunk_y}): {e}")
            return None

    def set_chunk_save_directory(self, save_name: str):
        """Set the directory for chunk saves based on save file name.

        Args:
            save_name: Name of the save file (e.g., "autosave.json")
        """
        base_name = save_name.rsplit('.', 1)[0]  # Remove extension
        self._chunk_save_dir = Path(get_save_path()) / f"{base_name}_chunks"
        self._chunk_save_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Tile and Resource Access
    # =========================================================================

    def get_tile(self, position: Position) -> Optional[WorldTile]:
        """Get the tile at a position, auto-loading chunk if needed.

        Args:
            position: World position

        Returns:
            WorldTile at position, or None if invalid
        """
        # Use math.floor for proper negative coordinate handling
        tile_x = math.floor(position.x)
        tile_y = math.floor(position.y)
        chunk_x = tile_x // Config.CHUNK_SIZE
        chunk_y = tile_y // Config.CHUNK_SIZE

        chunk = self.get_chunk(chunk_x, chunk_y)
        if chunk is None:
            return None
        return chunk.tiles.get(position.snap_to_grid().to_key())

    def is_walkable(self, position: Position) -> bool:
        """Check if a position is walkable.

        Args:
            position: World position to check

        Returns:
            True if position is walkable
        """
        # Check if in dungeon
        if self.dungeon_manager and self.dungeon_manager.in_dungeon:
            dungeon = self.dungeon_manager.current_dungeon
            if dungeon:
                tile_key = position.snap_to_grid().to_key()
                tile = dungeon.tiles.get(tile_key)
                if not tile:
                    return False
                return tile.walkable
            return False

        # Normal world check
        tile = self.get_tile(position)
        if not tile or tile.tile_type == TileType.WATER or not tile.walkable:
            return False

        # Check for blocking resources using distance-based collision
        # This is more accurate than tile-based matching for sub-tile positioning
        tile_x = math.floor(position.x)
        tile_y = math.floor(position.y)
        chunk_x = tile_x // Config.CHUNK_SIZE
        chunk_y = tile_y // Config.CHUNK_SIZE

        chunk = self.loaded_chunks.get((chunk_x, chunk_y))
        if chunk:
            for resource in chunk.resources:
                if not resource.depleted:
                    dx = abs(resource.position.x - position.x)
                    dy = abs(resource.position.y - position.y)
                    if dx < 0.5 and dy < 0.5:
                        return False

        # Check for blocking placed barriers using distance-based collision
        for entity in self.placed_entities:
            if entity.entity_type == PlacedEntityType.BARRIER:
                dx = abs(entity.position.x - position.x)
                dy = abs(entity.position.y - position.y)
                if dx < 0.5 and dy < 0.5:
                    return False

        return True

    def get_visible_tiles(self, camera_pos: Position, vw: int, vh: int) -> List[WorldTile]:
        """Get all tiles visible in the camera viewport.

        Args:
            camera_pos: Camera center position
            vw: Viewport width in pixels
            vh: Viewport height in pixels

        Returns:
            List of visible WorldTiles
        """
        tw = vw // Config.TILE_SIZE + 2
        th = vh // Config.TILE_SIZE + 2
        sx = int(camera_pos.x - tw // 2)
        sy = int(camera_pos.y - th // 2)

        visible = []
        for x in range(sx, sx + tw):
            for y in range(sy, sy + th):
                tile = self.get_tile(Position(x, y, 0))
                if tile:
                    visible.append(tile)

        return visible

    def get_visible_resources(self, camera_pos: Position, vw: int, vh: int) -> List[NaturalResource]:
        """Get all resources visible in the camera viewport.

        Args:
            camera_pos: Camera center position
            vw: Viewport width in pixels
            vh: Viewport height in pixels

        Returns:
            List of visible NaturalResources
        """
        tw = vw // Config.TILE_SIZE + 2
        th = vh // Config.TILE_SIZE + 2
        sx = camera_pos.x - tw // 2
        sy = camera_pos.y - th // 2
        ex = camera_pos.x + tw // 2
        ey = camera_pos.y + th // 2

        visible = []
        for chunk in self.loaded_chunks.values():
            for r in chunk.resources:
                if sx <= r.position.x <= ex and sy <= r.position.y <= ey:
                    visible.append(r)

        return visible

    def get_resource_at(self, position: Position,
                        tolerance: float = Config.CLICK_TOLERANCE) -> Optional[NaturalResource]:
        """Get resource at position within tolerance.

        Args:
            position: World position
            tolerance: Distance tolerance for matching

        Returns:
            NaturalResource at position, or None
        """
        tile_x = math.floor(position.x)
        tile_y = math.floor(position.y)
        chunk_x = tile_x // Config.CHUNK_SIZE
        chunk_y = tile_y // Config.CHUNK_SIZE

        # Check current and adjacent chunks
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                key = (chunk_x + dx, chunk_y + dy)
                chunk = self.loaded_chunks.get(key)
                if chunk:
                    for r in chunk.resources:
                        if not r.depleted:
                            dist_x = abs(r.position.x - position.x)
                            dist_y = abs(r.position.y - position.y)
                            if dist_x <= tolerance and dist_y <= tolerance:
                                return r

        return None

    # =========================================================================
    # Dungeon Entrances
    # =========================================================================

    def get_visible_dungeon_entrances(self, camera_pos: Position,
                                       vw: int, vh: int) -> List[DungeonEntrance]:
        """Get all dungeon entrances visible in the camera viewport.

        Args:
            camera_pos: Camera center position
            vw: Viewport width in pixels
            vh: Viewport height in pixels

        Returns:
            List of visible DungeonEntrances
        """
        tw = vw // Config.TILE_SIZE + 2
        th = vh // Config.TILE_SIZE + 2
        sx = camera_pos.x - tw // 2
        sy = camera_pos.y - th // 2
        ex = camera_pos.x + tw // 2
        ey = camera_pos.y + th // 2

        visible = []
        for chunk in self.loaded_chunks.values():
            if chunk.dungeon_entrance:
                e = chunk.dungeon_entrance
                if sx <= e.position.x <= ex and sy <= e.position.y <= ey:
                    visible.append(e)

        return visible

    def get_dungeon_entrance_at(self, position: Position,
                                tolerance: float = 1.0) -> Optional[DungeonEntrance]:
        """Get dungeon entrance at position with tolerance.

        Args:
            position: World position
            tolerance: Distance tolerance for matching

        Returns:
            DungeonEntrance at position, or None
        """
        for entrance in self.discovered_dungeon_entrances.values():
            dx = abs(entrance.position.x - position.x)
            dy = abs(entrance.position.y - position.y)
            if dx <= tolerance and dy <= tolerance:
                return entrance

        return None

    # =========================================================================
    # Crafting Stations (Fixed at Spawn)
    # =========================================================================

    def get_visible_stations(self, camera_pos: Position,
                             vw: int, vh: int) -> List[CraftingStation]:
        """Get all crafting stations visible in the camera viewport.

        Args:
            camera_pos: Camera center position
            vw: Viewport width in pixels
            vh: Viewport height in pixels

        Returns:
            List of visible CraftingStations
        """
        tw = vw // Config.TILE_SIZE + 2
        th = vh // Config.TILE_SIZE + 2
        sx = camera_pos.x - tw // 2
        sy = camera_pos.y - th // 2
        ex = camera_pos.x + tw // 2
        ey = camera_pos.y + th // 2

        return [s for s in self.crafting_stations
                if sx <= s.position.x <= ex and sy <= s.position.y <= ey]

    def get_station_at(self, position: Position,
                       tolerance: float = 0.8) -> Optional[CraftingStation]:
        """Get crafting station at position with tolerance.

        Args:
            position: World position
            tolerance: Distance tolerance for matching

        Returns:
            CraftingStation at position, or None
        """
        for s in self.crafting_stations:
            dx = abs(s.position.x - position.x)
            dy = abs(s.position.y - position.y)
            if dx <= tolerance and dy <= tolerance:
                return s

        return None

    # =========================================================================
    # Placed Entities (Player-Placed)
    # =========================================================================

    def place_entity(self, position: Position, item_id: str,
                     entity_type: PlacedEntityType, tier: int = 1,
                     range: float = 5.0, damage: float = 20.0,
                     tags: List[str] = None, effect_params: dict = None,
                     crafted_stats: dict = None) -> PlacedEntity:
        """Place a player entity in the world.

        Args:
            position: World position
            item_id: Item identifier
            entity_type: Type of entity
            tier: Entity tier
            range: Attack/effect range
            damage: Base damage
            tags: Effect tags
            effect_params: Effect parameters
            crafted_stats: Crafted statistics

        Returns:
            The placed PlacedEntity
        """
        entity = PlacedEntity(
            position=position.snap_to_grid(),
            item_id=item_id,
            entity_type=entity_type,
            tier=tier,
            range=range,
            damage=damage,
            tags=tags,
            effect_params=effect_params,
            crafted_stats=crafted_stats
        )
        self.placed_entities.append(entity)

        # Update barrier cache for O(1) collision lookup
        if entity_type == PlacedEntityType.BARRIER:
            tile_pos = (int(entity.position.x), int(entity.position.y))
            self._barrier_positions.add(tile_pos)

        return entity

    def remove_entity(self, entity: PlacedEntity) -> bool:
        """Remove a placed entity from the world.

        Args:
            entity: The entity to remove

        Returns:
            True if entity was removed
        """
        if entity in self.placed_entities:
            self.placed_entities.remove(entity)

            # Update barrier cache
            if entity.entity_type == PlacedEntityType.BARRIER:
                tile_pos = (int(entity.position.x), int(entity.position.y))
                self._barrier_positions.discard(tile_pos)

            return True
        return False

    def get_entity_at(self, position: Position,
                      tolerance: float = 0.8) -> Optional[PlacedEntity]:
        """Get placed entity at position with tolerance.

        Args:
            position: World position
            tolerance: Distance tolerance for matching

        Returns:
            PlacedEntity at position, or None
        """
        for entity in self.placed_entities:
            dx = abs(entity.position.x - position.x)
            dy = abs(entity.position.y - position.y)
            if dx <= tolerance and dy <= tolerance:
                return entity

        return None

    def get_visible_placed_entities(self, camera_pos: Position,
                                     vw: int, vh: int) -> List[PlacedEntity]:
        """Get all placed entities visible in the camera viewport.

        Args:
            camera_pos: Camera center position
            vw: Viewport width in pixels
            vh: Viewport height in pixels

        Returns:
            List of visible PlacedEntities
        """
        tw = vw // Config.TILE_SIZE + 2
        th = vh // Config.TILE_SIZE + 2
        sx = camera_pos.x - tw // 2
        sy = camera_pos.y - th // 2
        ex = camera_pos.x + tw // 2
        ey = camera_pos.y + th // 2

        return [e for e in self.placed_entities
                if sx <= e.position.x <= ex and sy <= e.position.y <= ey]

    # =========================================================================
    # Update and Resource Management
    # =========================================================================

    def update(self, dt: float):
        """Update world state.

        Args:
            dt: Delta time in seconds
        """
        self.game_time += dt

        # Update resources in loaded chunks
        for chunk in self.loaded_chunks.values():
            for resource in chunk.resources:
                resource.update(dt)

    def mark_resource_modified(self, resource: NaturalResource):
        """Mark a resource as modified in its chunk.

        Called when a resource is harvested or damaged.

        Args:
            resource: The modified resource
        """
        tile_x = math.floor(resource.position.x)
        tile_y = math.floor(resource.position.y)
        chunk_x = tile_x // Config.CHUNK_SIZE
        chunk_y = tile_y // Config.CHUNK_SIZE

        chunk = self.loaded_chunks.get((chunk_x, chunk_y))
        if chunk:
            chunk.mark_resource_modified(resource)

    # =========================================================================
    # Save/Load Integration
    # =========================================================================

    def get_save_state(self) -> dict:
        """Get world state for saving.

        Returns:
            Dictionary containing world save data
        """
        # Save all modified chunks
        for chunk in self.loaded_chunks.values():
            if chunk.has_modifications():
                self._save_chunk_to_file(chunk)

        # Build save data
        return {
            "seed": self.seed,
            "game_time": self.game_time,
            "placed_entities": self._serialize_placed_entities(),
            "crafting_stations": self._serialize_crafting_stations(),
            "discovered_dungeons": self._serialize_discovered_dungeons(),
            "spawn_chest": self._serialize_spawn_chest(),
            "death_chests": self._serialize_death_chests(),
        }

    def _serialize_placed_entities(self) -> List[dict]:
        """Serialize placed entities for saving."""
        entities = []
        for entity in self.placed_entities:
            entity_data = {
                "position": {
                    "x": entity.position.x,
                    "y": entity.position.y,
                    "z": entity.position.z
                },
                "item_id": entity.item_id,
                "entity_type": entity.entity_type.name,
                "tier": entity.tier,
                "health": entity.health,
                "owner": entity.owner,
                "time_remaining": entity.time_remaining,
                "tags": entity.tags if hasattr(entity, 'tags') else None,
                "effect_params": entity.effect_params if hasattr(entity, 'effect_params') else None
            }

            if hasattr(entity, 'range'):
                entity_data["range"] = entity.range
                entity_data["damage"] = entity.damage
                entity_data["attack_speed"] = entity.attack_speed

            entities.append(entity_data)

        return entities

    def _serialize_crafting_stations(self) -> List[dict]:
        """Serialize crafting stations for saving."""
        return [
            {
                "position": {"x": s.position.x, "y": s.position.y, "z": s.position.z},
                "station_type": s.station_type.name,
                "tier": s.tier
            }
            for s in self.crafting_stations
        ]

    def _serialize_discovered_dungeons(self) -> List[dict]:
        """Serialize discovered dungeon entrances for saving."""
        return [
            {
                "chunk_x": key[0],
                "chunk_y": key[1],
                "position": {"x": e.position.x, "y": e.position.y, "z": e.position.z},
                "rarity": e.rarity.value
            }
            for key, e in self.discovered_dungeon_entrances.items()
        ]

    def _serialize_spawn_chest(self) -> Optional[dict]:
        """Serialize spawn storage chest for saving."""
        if not self.spawn_storage_chest:
            return None
        chest = self.spawn_storage_chest
        return chest.to_dict()

    def _serialize_death_chests(self) -> List[dict]:
        """Serialize death chests for saving."""
        return [chest.to_dict() for chest in self.death_chests]

    def restore_from_save(self, world_state: dict):
        """Restore world state from save data.

        Args:
            world_state: Dictionary containing world state from save file
        """
        # Restore game time
        self.game_time = world_state.get("game_time", 0.0)

        # Restore placed entities
        self.placed_entities.clear()
        for entity_data in world_state.get("placed_entities", []):
            position = Position(
                entity_data["position"]["x"],
                entity_data["position"]["y"],
                entity_data["position"]["z"]
            )

            entity_type = PlacedEntityType[entity_data["entity_type"]]

            entity = PlacedEntity(
                position=position,
                item_id=entity_data["item_id"],
                entity_type=entity_type,
                tier=entity_data.get("tier", 1),
                health=entity_data.get("health", 100.0),
                owner=entity_data.get("owner"),
                time_remaining=entity_data.get("time_remaining", 300.0),
                tags=entity_data.get("tags"),
                effect_params=entity_data.get("effect_params")
            )

            if "range" in entity_data:
                entity.range = entity_data["range"]
                entity.damage = entity_data["damage"]
                entity.attack_speed = entity_data["attack_speed"]

            self.placed_entities.append(entity)

        # Rebuild barrier position cache from restored entities
        self._barrier_positions.clear()
        for entity in self.placed_entities:
            if entity.entity_type == PlacedEntityType.BARRIER:
                tile_pos = (int(entity.position.x), int(entity.position.y))
                self._barrier_positions.add(tile_pos)

        # Restore discovered dungeons
        self.discovered_dungeon_entrances.clear()
        for dungeon_data in world_state.get("discovered_dungeons", []):
            key = (dungeon_data["chunk_x"], dungeon_data["chunk_y"])
            pos = Position(
                dungeon_data["position"]["x"],
                dungeon_data["position"]["y"],
                dungeon_data["position"]["z"]
            )
            rarity = DungeonRarity(dungeon_data["rarity"])
            entrance = DungeonEntrance(position=pos, rarity=rarity)
            self.discovered_dungeon_entrances[key] = entrance

            # Update loaded chunk if it exists
            if key in self.loaded_chunks:
                self.loaded_chunks[key].dungeon_entrance = entrance

        # Restore crafting stations if different from default
        saved_stations = world_state.get("crafting_stations", [])
        if saved_stations:
            self.crafting_stations.clear()
            for station_data in saved_stations:
                position = Position(
                    station_data["position"]["x"],
                    station_data["position"]["y"],
                    station_data["position"]["z"]
                )
                station_type = StationType[station_data["station_type"]]
                station = CraftingStation(
                    position=position,
                    station_type=station_type,
                    tier=station_data.get("tier", 1)
                )
                self.crafting_stations.append(station)

        # Restore spawn storage chest contents
        spawn_chest_data = world_state.get("spawn_chest")
        if spawn_chest_data:
            self.spawn_storage_chest = LootChest.from_dict(spawn_chest_data)
            print(f"   Restored spawn chest with {len(self.spawn_storage_chest.contents)} items")
        else:
            # Create fresh chest if not in save (backwards compatibility)
            self.spawn_spawn_storage_chest()

        # Restore death chests
        self.death_chests.clear()
        death_chests_data = world_state.get("death_chests", [])
        for chest_data in death_chests_data:
            death_chest = LootChest.from_dict(chest_data)
            self.death_chests.append(death_chest)
        if death_chests_data:
            print(f"   Restored {len(death_chests_data)} death chest(s)")

        print(f"Restored world state: {len(self.placed_entities)} entities, "
              f"{len(self.discovered_dungeon_entrances)} dungeons")

    # =========================================================================
    # Legacy Compatibility
    # =========================================================================

    @property
    def tiles(self) -> Dict[str, WorldTile]:
        """Legacy property for accessing all tiles.

        Note: This is inefficient for large worlds. Prefer using get_tile().

        Returns:
            Dictionary of all tiles in loaded chunks
        """
        all_tiles = {}
        for chunk in self.loaded_chunks.values():
            all_tiles.update(chunk.tiles)
        return all_tiles

    @property
    def resources(self) -> List[NaturalResource]:
        """Legacy property for accessing all resources.

        Note: This is inefficient for large worlds. Prefer using get_visible_resources().

        Returns:
            List of all resources in loaded chunks
        """
        all_resources = []
        for chunk in self.loaded_chunks.values():
            all_resources.extend(chunk.resources)
        return all_resources

    @property
    def dungeon_entrances(self) -> List[DungeonEntrance]:
        """Legacy property for accessing all dungeon entrances.

        Returns:
            List of all discovered dungeon entrances
        """
        return list(self.discovered_dungeon_entrances.values())

    @property
    def chunks(self) -> Dict[Tuple[int, int], Chunk]:
        """Legacy property for accessing loaded chunks.

        Returns:
            Dictionary of loaded chunks
        """
        return self.loaded_chunks
