"""Map and waypoint system for world exploration tracking and teleportation.

Tracks explored chunks for the world map display and manages player waypoints
for fast travel. Integrates with the save system for persistence.

Usage:
    system = MapWaypointSystem(world_seed=12345)
    system.mark_chunk_explored(5, -3)
    system.add_waypoint("Mining Camp", Position(100, 50, 0), player_level=10)
    system.teleport_to_waypoint(character, waypoint_index=1)
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from data.models import Position
from data.databases.map_waypoint_db import MapWaypointConfig


@dataclass
class Waypoint:
    """A player-placed teleportation waypoint.

    Attributes:
        name: Display name for the waypoint
        position: World position (x, y, z)
        chunk_coords: Chunk coordinates (chunk_x, chunk_y)
        created_at: Timestamp when waypoint was created
        slot: Waypoint slot index (0 = spawn)
        is_spawn: Whether this is the permanent spawn waypoint
    """
    name: str
    position: Position
    chunk_coords: Tuple[int, int]
    created_at: str
    slot: int
    is_spawn: bool = False

    def to_dict(self) -> Dict:
        """Serialize waypoint for saving."""
        return {
            'name': self.name,
            'position': {'x': self.position.x, 'y': self.position.y, 'z': self.position.z},
            'chunk_coords': list(self.chunk_coords),
            'created_at': self.created_at,
            'slot': self.slot,
            'is_spawn': self.is_spawn
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Waypoint':
        """Deserialize waypoint from save data."""
        pos_data = data.get('position', {'x': 0, 'y': 0, 'z': 0})
        return cls(
            name=data.get('name', 'Waypoint'),
            position=Position(pos_data['x'], pos_data['y'], pos_data['z']),
            chunk_coords=tuple(data.get('chunk_coords', [0, 0])),
            created_at=data.get('created_at', datetime.now().isoformat()),
            slot=data.get('slot', 0),
            is_spawn=data.get('is_spawn', False)
        )


@dataclass
class ExploredChunk:
    """Data about an explored chunk for the map.

    Attributes:
        chunk_x: Chunk X coordinate
        chunk_y: Chunk Y coordinate
        chunk_type: The biome/type of the chunk
        discovered_at: When the chunk was first visited
        has_dungeon: Whether a dungeon entrance was found here
    """
    chunk_x: int
    chunk_y: int
    chunk_type: str
    discovered_at: str
    has_dungeon: bool = False

    def to_dict(self) -> Dict:
        """Serialize for saving."""
        return {
            'x': self.chunk_x,
            'y': self.chunk_y,
            'type': self.chunk_type,
            'discovered_at': self.discovered_at,
            'has_dungeon': self.has_dungeon
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ExploredChunk':
        """Deserialize from save data."""
        return cls(
            chunk_x=data.get('x', 0),
            chunk_y=data.get('y', 0),
            chunk_type=data.get('type', 'unknown'),
            discovered_at=data.get('discovered_at', datetime.now().isoformat()),
            has_dungeon=data.get('has_dungeon', False)
        )


class MapWaypointSystem:
    """Manages world map exploration and waypoint teleportation.

    Tracks which chunks the player has explored (for map display) and
    manages waypoint placement and teleportation.

    Attributes:
        explored_chunks: Dictionary of explored chunk data keyed by (x, y) tuple
        waypoints: List of player waypoints
        last_teleport_time: Game time of last teleport (for cooldown)
    """

    def __init__(self, chunk_size: int = 16):
        """Initialize the map and waypoint system.

        Args:
            chunk_size: Size of chunks in tiles (default 16)
        """
        self._config = MapWaypointConfig.get_instance()
        self._chunk_size = chunk_size

        # Explored chunks: key = (chunk_x, chunk_y), value = ExploredChunk
        self.explored_chunks: Dict[Tuple[int, int], ExploredChunk] = {}

        # Waypoints: list indexed by slot
        self.waypoints: List[Optional[Waypoint]] = [None] * self._config.waypoint.max_waypoints

        # Teleport cooldown tracking
        self.last_teleport_time: float = 0.0

        # Map UI state
        self.map_open: bool = False
        self.map_zoom: float = self._config.map_display.default_zoom
        self.map_scroll_x: float = 0.0
        self.map_scroll_y: float = 0.0
        self.selected_waypoint_slot: int = -1

        # Map dragging state
        self.map_dragging: bool = False
        self.drag_start_x: float = 0.0
        self.drag_start_y: float = 0.0
        self.drag_start_scroll_x: float = 0.0
        self.drag_start_scroll_y: float = 0.0

        # Statistics tracking
        self.stats = {
            'waypoints_placed_total': 0,
            'waypoints_removed_total': 0,
            'teleport_count': 0,
            'distance_teleported': 0.0,
            'chunks_explored_total': 0
        }

        # Initialize spawn waypoint if configured
        if self._config.waypoint.spawn_always_available:
            self._init_spawn_waypoint()

    def _init_spawn_waypoint(self) -> None:
        """Initialize the spawn waypoint (slot 0)."""
        spawn_pos = self._config.waypoint.spawn_position
        self.waypoints[0] = Waypoint(
            name=self._config.waypoint.spawn_default_name,
            position=Position(spawn_pos[0], spawn_pos[1], 0),
            chunk_coords=(0, 0),
            created_at=datetime.now().isoformat(),
            slot=0,
            is_spawn=True
        )

    def toggle_map(self) -> None:
        """Toggle the map UI open/closed."""
        self.map_open = not self.map_open

    def close_map(self) -> None:
        """Close the map UI."""
        self.map_open = False

    def open_map(self) -> None:
        """Open the map UI."""
        self.map_open = True

    # =========================================================================
    # CHUNK EXPLORATION
    # =========================================================================

    def mark_chunk_explored(self, chunk_x: int, chunk_y: int, chunk_type: str,
                           has_dungeon: bool = False) -> None:
        """Mark a chunk as explored for the map.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate
            chunk_type: The ChunkType value (e.g., 'peaceful_forest')
            has_dungeon: Whether a dungeon entrance exists in this chunk
        """
        key = (chunk_x, chunk_y)

        if key not in self.explored_chunks:
            self.explored_chunks[key] = ExploredChunk(
                chunk_x=chunk_x,
                chunk_y=chunk_y,
                chunk_type=chunk_type,
                discovered_at=datetime.now().isoformat(),
                has_dungeon=has_dungeon
            )
            self.stats['chunks_explored_total'] += 1
        elif has_dungeon and not self.explored_chunks[key].has_dungeon:
            # Update dungeon status if discovered later
            self.explored_chunks[key].has_dungeon = True

    def is_chunk_explored(self, chunk_x: int, chunk_y: int) -> bool:
        """Check if a chunk has been explored.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            True if the chunk has been visited
        """
        return (chunk_x, chunk_y) in self.explored_chunks

    def get_explored_chunk(self, chunk_x: int, chunk_y: int) -> Optional[ExploredChunk]:
        """Get explored chunk data.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            ExploredChunk data or None if not explored
        """
        return self.explored_chunks.get((chunk_x, chunk_y))

    def get_exploration_bounds(self) -> Tuple[int, int, int, int]:
        """Get the bounding box of explored area.

        Returns:
            Tuple of (min_x, min_y, max_x, max_y) chunk coordinates
        """
        if not self.explored_chunks:
            return (0, 0, 0, 0)

        min_x = min(c[0] for c in self.explored_chunks.keys())
        max_x = max(c[0] for c in self.explored_chunks.keys())
        min_y = min(c[1] for c in self.explored_chunks.keys())
        max_y = max(c[1] for c in self.explored_chunks.keys())

        return (min_x, min_y, max_x, max_y)

    def get_explored_count(self) -> int:
        """Get the number of explored chunks.

        Returns:
            Total count of explored chunks
        """
        return len(self.explored_chunks)

    # =========================================================================
    # WAYPOINT MANAGEMENT
    # =========================================================================

    def get_available_slots(self, player_level: int) -> int:
        """Get number of waypoint slots available at current level.

        Args:
            player_level: Character's current level

        Returns:
            Number of available waypoint slots
        """
        return self._config.get_max_waypoints_for_level(player_level)

    def get_next_unlocked_level(self, player_level: int) -> Optional[int]:
        """Get the level at which the next waypoint slot unlocks.

        Args:
            player_level: Character's current level

        Returns:
            Next unlock level, or None if all unlocked
        """
        for level in self._config.waypoint.unlock_levels:
            if player_level < level:
                return level
        return None

    def can_add_waypoint(self, player_level: int) -> Tuple[bool, str]:
        """Check if player can add a new waypoint.

        Args:
            player_level: Character's current level

        Returns:
            Tuple of (can_add, reason_if_not)
        """
        if not self._config.waypoint.enabled:
            return False, "Waypoints are disabled"

        available_slots = self.get_available_slots(player_level)
        used_slots = sum(1 for w in self.waypoints if w is not None)

        if used_slots >= available_slots:
            next_level = self.get_next_unlocked_level(player_level)
            if next_level:
                return False, f"No slots available. Next unlock at level {next_level}"
            return False, "All waypoint slots are used"

        return True, ""

    def find_empty_slot(self, player_level: int) -> Optional[int]:
        """Find the first empty waypoint slot.

        Args:
            player_level: Character's current level

        Returns:
            Slot index or None if no slots available
        """
        available = self.get_available_slots(player_level)

        for i in range(available):
            if self.waypoints[i] is None:
                return i

        return None

    def add_waypoint(self, name: str, position: Position, player_level: int,
                    force_slot: Optional[int] = None) -> Tuple[bool, str]:
        """Add a new waypoint at the given position.

        Args:
            name: Display name for the waypoint
            position: World position to place waypoint
            player_level: Character's current level
            force_slot: Specific slot to use (None = auto-select)

        Returns:
            Tuple of (success, message)
        """
        can_add, reason = self.can_add_waypoint(player_level)
        if not can_add and force_slot is None:
            return False, reason

        # Calculate chunk coordinates
        chunk_x = math.floor(position.x) // self._chunk_size
        chunk_y = math.floor(position.y) // self._chunk_size

        # Check minimum distance from other waypoints
        min_dist = self._config.waypoint.min_distance_between_waypoints
        if min_dist > 0:
            for wp in self.waypoints:
                if wp is not None and not wp.is_spawn:
                    dist = math.sqrt((position.x - wp.position.x)**2 +
                                   (position.y - wp.position.y)**2)
                    if dist < min_dist:
                        return False, f"Too close to '{wp.name}' (min {min_dist} tiles apart)"

        # Find slot
        if force_slot is not None:
            slot = force_slot
            if slot < 0 or slot >= len(self.waypoints):
                return False, f"Invalid slot {slot}"
            if self.waypoints[slot] is not None and self.waypoints[slot].is_spawn:
                return False, "Cannot overwrite spawn waypoint"
        else:
            slot = self.find_empty_slot(player_level)
            if slot is None:
                return False, "No empty slots available"

        # Truncate name if needed
        max_len = self._config.waypoint.max_name_length
        if len(name) > max_len:
            name = name[:max_len]

        # Create waypoint - IMPORTANT: Copy position to avoid reference issues
        # If we store the original Position object, the waypoint will move with the player!
        self.waypoints[slot] = Waypoint(
            name=name,
            position=Position(position.x, position.y, position.z),
            chunk_coords=(chunk_x, chunk_y),
            created_at=datetime.now().isoformat(),
            slot=slot,
            is_spawn=False
        )

        self.stats['waypoints_placed_total'] += 1
        return True, f"Waypoint '{name}' created in slot {slot + 1}"

    def remove_waypoint(self, slot: int) -> Tuple[bool, str]:
        """Remove a waypoint from a slot.

        Args:
            slot: Waypoint slot index to clear

        Returns:
            Tuple of (success, message)
        """
        if slot < 0 or slot >= len(self.waypoints):
            return False, f"Invalid slot {slot}"

        if self.waypoints[slot] is None:
            return False, "Slot is already empty"

        if self.waypoints[slot].is_spawn:
            return False, "Cannot remove spawn waypoint"

        name = self.waypoints[slot].name
        self.waypoints[slot] = None
        self.stats['waypoints_removed_total'] += 1
        return True, f"Waypoint '{name}' removed"

    def rename_waypoint(self, slot: int, new_name: str) -> Tuple[bool, str]:
        """Rename a waypoint.

        Args:
            slot: Waypoint slot index
            new_name: New name for the waypoint

        Returns:
            Tuple of (success, message)
        """
        if slot < 0 or slot >= len(self.waypoints):
            return False, f"Invalid slot {slot}"

        if self.waypoints[slot] is None:
            return False, "No waypoint in this slot"

        max_len = self._config.waypoint.max_name_length
        if len(new_name) > max_len:
            new_name = new_name[:max_len]

        old_name = self.waypoints[slot].name
        self.waypoints[slot].name = new_name
        return True, f"Renamed '{old_name}' to '{new_name}'"

    def get_waypoint(self, slot: int) -> Optional[Waypoint]:
        """Get waypoint at a specific slot.

        Args:
            slot: Waypoint slot index

        Returns:
            Waypoint or None if slot is empty
        """
        if slot < 0 or slot >= len(self.waypoints):
            return None
        return self.waypoints[slot]

    def get_all_waypoints(self) -> List[Waypoint]:
        """Get all non-empty waypoints.

        Returns:
            List of active waypoints
        """
        return [w for w in self.waypoints if w is not None]

    # =========================================================================
    # TELEPORTATION
    # =========================================================================

    def can_teleport(self, game_time: float, in_dungeon: bool = False,
                    enemies_nearby: bool = False) -> Tuple[bool, str]:
        """Check if teleportation is currently allowed.

        Args:
            game_time: Current game time
            in_dungeon: Whether player is in a dungeon
            enemies_nearby: Whether combat is active

        Returns:
            Tuple of (can_teleport, reason_if_not)
        """
        if not self._config.waypoint.enabled:
            return False, "Waypoints are disabled"

        if in_dungeon and self._config.waypoint.blocked_in_dungeons:
            return False, "Cannot teleport in dungeons"

        if enemies_nearby and self._config.waypoint.blocked_in_combat:
            return False, "Cannot teleport during combat"

        cooldown = self._config.waypoint.teleport_cooldown
        time_since_last = game_time - self.last_teleport_time
        if time_since_last < cooldown:
            remaining = int(cooldown - time_since_last)
            return False, f"Teleport on cooldown ({remaining}s remaining)"

        return True, ""

    def teleport_to_waypoint(self, slot: int, game_time: float,
                            in_dungeon: bool = False,
                            enemies_nearby: bool = False,
                            current_position: Optional[Position] = None) -> Tuple[bool, str, Optional[Position]]:
        """Attempt to teleport to a waypoint.

        Args:
            slot: Waypoint slot index
            game_time: Current game time
            in_dungeon: Whether player is in a dungeon
            enemies_nearby: Whether combat is active
            current_position: Current player position (for distance tracking)

        Returns:
            Tuple of (success, message, destination_position)
        """
        can_tp, reason = self.can_teleport(game_time, in_dungeon, enemies_nearby)
        if not can_tp:
            print(f"🚫 Teleport blocked: {reason}")
            return False, reason, None

        waypoint = self.get_waypoint(slot)
        if waypoint is None:
            print(f"🚫 Teleport failed: No waypoint in slot {slot + 1}")
            return False, f"No waypoint in slot {slot + 1}", None

        # Calculate distance for stats
        if current_position:
            distance = math.sqrt(
                (waypoint.position.x - current_position.x) ** 2 +
                (waypoint.position.y - current_position.y) ** 2
            )
            self.stats['distance_teleported'] += distance

        # Update cooldown and stats
        self.last_teleport_time = game_time
        self.stats['teleport_count'] += 1

        print(f"✅ Teleport successful to '{waypoint.name}' at ({waypoint.position.x}, {waypoint.position.y})")
        return True, f"Teleported to '{waypoint.name}'", waypoint.position

    def get_teleport_cooldown_remaining(self, game_time: float) -> float:
        """Get remaining teleport cooldown time.

        Args:
            game_time: Current game time

        Returns:
            Seconds remaining on cooldown (0 if ready)
        """
        cooldown = self._config.waypoint.teleport_cooldown
        time_since_last = game_time - self.last_teleport_time
        return max(0, cooldown - time_since_last)

    # =========================================================================
    # MAP UI HELPERS
    # =========================================================================

    def adjust_zoom(self, delta: float) -> None:
        """Adjust map zoom level.

        Args:
            delta: Amount to change zoom by
        """
        step = self._config.map_display.zoom_step
        self.map_zoom += delta * step
        self.map_zoom = max(self._config.map_display.min_zoom,
                           min(self._config.map_display.max_zoom, self.map_zoom))

    def center_on_chunk(self, chunk_x: int, chunk_y: int) -> None:
        """Center the map view on a specific chunk.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate
        """
        self.map_scroll_x = float(chunk_x)
        self.map_scroll_y = float(chunk_y)

    def center_on_position(self, position: Position) -> None:
        """Center the map view on a world position.

        Args:
            position: World position to center on
        """
        chunk_x = math.floor(position.x) // self._chunk_size
        chunk_y = math.floor(position.y) // self._chunk_size
        self.center_on_chunk(chunk_x, chunk_y)

    # =========================================================================
    # MAP DRAGGING
    # =========================================================================

    def start_drag(self, mouse_x: float, mouse_y: float) -> None:
        """Start dragging the map.

        Args:
            mouse_x: Mouse X position when drag started
            mouse_y: Mouse Y position when drag started
        """
        self.map_dragging = True
        self.drag_start_x = mouse_x
        self.drag_start_y = mouse_y
        self.drag_start_scroll_x = self.map_scroll_x
        self.drag_start_scroll_y = self.map_scroll_y

    def update_drag(self, mouse_x: float, mouse_y: float, chunk_pixel_size: float) -> None:
        """Update map position while dragging.

        Args:
            mouse_x: Current mouse X position
            mouse_y: Current mouse Y position
            chunk_pixel_size: Current size of chunks in pixels (for scaling)
        """
        if not self.map_dragging:
            return

        # Calculate drag delta in chunks
        dx = (mouse_x - self.drag_start_x) / max(1, chunk_pixel_size)
        dy = (mouse_y - self.drag_start_y) / max(1, chunk_pixel_size)

        # Update scroll position (subtract because dragging right should move map left)
        self.map_scroll_x = self.drag_start_scroll_x - dx
        self.map_scroll_y = self.drag_start_scroll_y - dy

    def end_drag(self) -> None:
        """End map dragging."""
        self.map_dragging = False

    # =========================================================================
    # SAVE / LOAD
    # =========================================================================

    def get_save_data(self) -> Dict:
        """Get data for saving to file.

        Returns:
            Dictionary containing all map and waypoint data
        """
        return {
            'explored_chunks': [chunk.to_dict() for chunk in self.explored_chunks.values()],
            'waypoints': [wp.to_dict() if wp else None for wp in self.waypoints],
            'last_teleport_time': self.last_teleport_time,
            'map_zoom': self.map_zoom,
            'map_scroll_x': self.map_scroll_x,
            'map_scroll_y': self.map_scroll_y,
            'stats': self.stats.copy()
        }

    def restore_from_save(self, data: Dict) -> None:
        """Restore state from saved data.

        Args:
            data: Dictionary containing saved map/waypoint data
        """
        # Restore explored chunks
        self.explored_chunks.clear()
        for chunk_data in data.get('explored_chunks', []):
            chunk = ExploredChunk.from_dict(chunk_data)
            self.explored_chunks[(chunk.chunk_x, chunk.chunk_y)] = chunk

        # Restore waypoints
        waypoints_data = data.get('waypoints', [])
        for i, wp_data in enumerate(waypoints_data):
            if i < len(self.waypoints):
                if wp_data is not None:
                    self.waypoints[i] = Waypoint.from_dict(wp_data)
                else:
                    self.waypoints[i] = None

        # Ensure spawn waypoint exists with correct position
        # Always reset spawn to config position (in case save has wrong coords)
        if self._config.waypoint.spawn_always_available:
            self._init_spawn_waypoint()  # Always reinitialize to ensure correct position

        # Restore other state
        self.last_teleport_time = data.get('last_teleport_time', 0.0)
        self.map_zoom = data.get('map_zoom', self._config.map_display.default_zoom)
        self.map_scroll_x = data.get('map_scroll_x', 0.0)
        self.map_scroll_y = data.get('map_scroll_y', 0.0)

        # Restore stats
        saved_stats = data.get('stats', {})
        for key in self.stats:
            if key in saved_stats:
                self.stats[key] = saved_stats[key]

    def get_debug_info(self, game_time: float = 0.0) -> Dict:
        """Get debug information about the map/waypoint system.

        Args:
            game_time: Current game time (for accurate cooldown display)

        Returns:
            Dictionary with debug information
        """
        return {
            'explored_chunks': len(self.explored_chunks),
            'exploration_bounds': self.get_exploration_bounds(),
            'active_waypoints': sum(1 for w in self.waypoints if w is not None),
            'max_waypoints': self._config.waypoint.max_waypoints,
            'map_zoom': self.map_zoom,
            'map_position': (self.map_scroll_x, self.map_scroll_y),
            'teleport_cooldown_remaining': self.get_teleport_cooldown_remaining(game_time),
            'stats': self.stats.copy()
        }
