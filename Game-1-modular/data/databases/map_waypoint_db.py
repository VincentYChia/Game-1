"""Database loader for map and waypoint configuration.

Loads settings from map-waypoint-config.JSON for the world map display
and teleportation waypoint system.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class MapDisplayConfig:
    """Configuration for map display settings."""
    default_zoom: float = 1.0
    min_zoom: float = 0.25
    max_zoom: float = 4.0
    zoom_step: float = 0.25
    chunk_render_size: int = 12
    show_grid: bool = True
    show_coordinates: bool = True
    show_player_marker: bool = True
    show_waypoint_markers: bool = True
    center_on_player: bool = True


@dataclass
class MarkerConfig:
    """Configuration for a map marker type."""
    color: Tuple[int, int, int] = (255, 255, 255)
    size: int = 8
    shape: str = "circle"
    show_label: bool = False


@dataclass
class WaypointSystemConfig:
    """Configuration for the waypoint teleportation system."""
    enabled: bool = True
    spawn_always_available: bool = True
    spawn_default_name: str = "Spawn"
    spawn_position: Tuple[int, int] = (0, 0)
    unlock_levels: List[int] = field(default_factory=lambda: [5, 10, 15, 20, 25, 30])
    max_waypoints: int = 7
    teleport_cooldown: float = 30.0
    teleport_mana_cost: int = 0
    require_solid_ground: bool = True
    min_distance_between_waypoints: int = 32
    blocked_in_dungeons: bool = True
    blocked_in_combat: bool = True
    max_name_length: int = 24
    default_name_format: str = "Waypoint {number}"


@dataclass
class UIConfig:
    """Configuration for map/waypoint UI appearance."""
    map_window_size: Tuple[int, int] = (700, 600)
    waypoint_panel_width: int = 200
    background_color: Tuple[int, int, int, int] = (20, 20, 30, 240)
    border_color: Tuple[int, int, int] = (100, 100, 120)
    font_color: Tuple[int, int, int] = (220, 220, 220)


class MapWaypointConfig:
    """Singleton configuration loader for map and waypoint settings.

    Loads from Definitions.JSON/map-waypoint-config.JSON and provides
    structured access to all map and waypoint settings.

    Usage:
        config = MapWaypointConfig.get_instance()
        zoom = config.map_display.default_zoom
        unlock_levels = config.waypoint.unlock_levels
    """

    _instance: Optional['MapWaypointConfig'] = None

    def __init__(self):
        """Initialize and load configuration from JSON."""
        self.map_display = MapDisplayConfig()
        self.biome_colors: Dict[str, Tuple[int, int, int]] = {}
        self.player_marker = MarkerConfig()
        self.waypoint_marker = MarkerConfig()
        self.dungeon_marker = MarkerConfig()
        self.waypoint = WaypointSystemConfig()
        self.ui = UIConfig()

        self._load_config()

    @classmethod
    def get_instance(cls) -> 'MapWaypointConfig':
        """Get singleton instance of the configuration.

        Returns:
            MapWaypointConfig singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        config_path = Path(__file__).parent.parent.parent / "Definitions.JSON" / "map-waypoint-config.JSON"

        if not config_path.exists():
            print(f"Warning: map-waypoint-config.JSON not found at {config_path}")
            print("Using default map/waypoint configuration")
            self._set_defaults()
            return

        try:
            with open(config_path, 'r') as f:
                data = json.load(f)

            self._parse_map_display(data.get('map_display', {}))
            self._parse_biome_colors(data.get('biome_colors', {}))
            self._parse_markers(data.get('marker_icons', {}))
            self._parse_waypoint_system(data.get('waypoint_system', {}))
            self._parse_ui_settings(data.get('ui_settings', {}))

        except json.JSONDecodeError as e:
            print(f"Error parsing map-waypoint-config.JSON: {e}")
            self._set_defaults()
        except Exception as e:
            print(f"Error loading map-waypoint-config.JSON: {e}")
            self._set_defaults()

    def _parse_map_display(self, data: Dict) -> None:
        """Parse map display configuration."""
        self.map_display = MapDisplayConfig(
            default_zoom=data.get('default_zoom', 1.0),
            min_zoom=data.get('min_zoom', 0.25),
            max_zoom=data.get('max_zoom', 4.0),
            zoom_step=data.get('zoom_step', 0.25),
            chunk_render_size=data.get('chunk_render_size', 12),
            show_grid=data.get('show_grid', True),
            show_coordinates=data.get('show_coordinates', True),
            show_player_marker=data.get('show_player_marker', True),
            show_waypoint_markers=data.get('show_waypoint_markers', True),
            center_on_player=data.get('center_on_player', True)
        )

    def _parse_biome_colors(self, data: Dict) -> None:
        """Parse biome color mapping."""
        # Default colors for all biome types
        default_colors = {
            'peaceful_forest': (34, 139, 34),
            'dangerous_forest': (0, 100, 0),
            'rare_hidden_forest': (50, 205, 50),
            'peaceful_cave': (105, 105, 105),
            'dangerous_cave': (64, 64, 64),
            'rare_deep_cave': (138, 43, 226),
            'peaceful_quarry': (160, 82, 45),
            'dangerous_quarry': (139, 69, 19),
            'rare_ancient_quarry': (255, 140, 0),
            'water_lake': (65, 105, 225),
            'water_river': (70, 130, 180),
            'water_cursed_swamp': (75, 0, 130),
            'unexplored': (30, 30, 40),
            'spawn_area': (255, 215, 0)
        }

        self.biome_colors = {}
        for biome, default in default_colors.items():
            color_data = data.get(biome, default)
            if isinstance(color_data, list) and len(color_data) >= 3:
                self.biome_colors[biome] = tuple(color_data[:3])
            else:
                self.biome_colors[biome] = default

    def _parse_markers(self, data: Dict) -> None:
        """Parse marker configuration."""
        player_data = data.get('player', {})
        self.player_marker = MarkerConfig(
            color=tuple(player_data.get('color', [255, 255, 255])[:3]),
            size=player_data.get('size', 8),
            shape=player_data.get('shape', 'triangle'),
            show_label=False
        )

        waypoint_data = data.get('waypoint', {})
        self.waypoint_marker = MarkerConfig(
            color=tuple(waypoint_data.get('color', [255, 215, 0])[:3]),
            size=waypoint_data.get('size', 10),
            shape=waypoint_data.get('shape', 'diamond'),
            show_label=waypoint_data.get('show_label', True)
        )

        dungeon_data = data.get('dungeon', {})
        self.dungeon_marker = MarkerConfig(
            color=tuple(dungeon_data.get('color', [220, 20, 60])[:3]),
            size=dungeon_data.get('size', 8),
            shape=dungeon_data.get('shape', 'skull'),
            show_label=False
        )

    def _parse_waypoint_system(self, data: Dict) -> None:
        """Parse waypoint system configuration."""
        spawn_data = data.get('spawn_waypoint', {})
        unlock_data = data.get('unlock_schedule', {})
        placement_data = data.get('placement_rules', {})
        naming_data = data.get('waypoint_naming', {})
        cost_data = data.get('teleport_cost', {})

        self.waypoint = WaypointSystemConfig(
            enabled=data.get('enabled', True),
            spawn_always_available=spawn_data.get('always_available', True),
            spawn_default_name=spawn_data.get('default_name', 'Spawn'),
            spawn_position=tuple(spawn_data.get('position', [0, 0])),
            unlock_levels=unlock_data.get('levels', [5, 10, 15, 20, 25, 30]),
            max_waypoints=data.get('max_waypoints', 7),
            teleport_cooldown=data.get('teleport_cooldown', 30.0),
            teleport_mana_cost=cost_data.get('mana_cost', 0) if cost_data.get('enabled', False) else 0,
            require_solid_ground=placement_data.get('require_solid_ground', True),
            min_distance_between_waypoints=placement_data.get('min_distance_between_waypoints', 32),
            blocked_in_dungeons=placement_data.get('blocked_in_dungeons', True),
            blocked_in_combat=placement_data.get('blocked_in_combat', True),
            max_name_length=naming_data.get('max_name_length', 24),
            default_name_format=naming_data.get('default_name_format', 'Waypoint {number}')
        )

    def _parse_ui_settings(self, data: Dict) -> None:
        """Parse UI settings configuration."""
        size = data.get('map_window_size', [700, 600])
        bg = data.get('background_color', [20, 20, 30, 240])
        border = data.get('border_color', [100, 100, 120])
        font = data.get('font_color', [220, 220, 220])

        self.ui = UIConfig(
            map_window_size=tuple(size[:2]),
            waypoint_panel_width=data.get('waypoint_panel_width', 200),
            background_color=tuple(bg[:4]) if len(bg) >= 4 else tuple(bg[:3]) + (240,),
            border_color=tuple(border[:3]),
            font_color=tuple(font[:3])
        )

    def _set_defaults(self) -> None:
        """Set default configuration values."""
        self.map_display = MapDisplayConfig()
        self._parse_biome_colors({})
        self.player_marker = MarkerConfig(color=(255, 255, 255), shape='triangle')
        self.waypoint_marker = MarkerConfig(color=(255, 215, 0), shape='diamond', show_label=True)
        self.dungeon_marker = MarkerConfig(color=(220, 20, 60), shape='skull')
        self.waypoint = WaypointSystemConfig()
        self.ui = UIConfig()

    def get_biome_color(self, chunk_type: str) -> Tuple[int, int, int]:
        """Get the color for a specific chunk type.

        Args:
            chunk_type: The chunk type string (e.g., 'peaceful_forest')

        Returns:
            RGB tuple for the biome color
        """
        return self.biome_colors.get(chunk_type.lower(), self.biome_colors.get('unexplored', (30, 30, 40)))

    def get_max_waypoints_for_level(self, level: int) -> int:
        """Calculate how many waypoint slots are available at a given level.

        Args:
            level: Character level (1-30)

        Returns:
            Number of waypoint slots available (1-7)
        """
        if not self.waypoint.enabled:
            return 0

        # Spawn is always slot 1
        slots = 1 if self.waypoint.spawn_always_available else 0

        # Add slots based on level
        for unlock_level in self.waypoint.unlock_levels:
            if level >= unlock_level:
                slots += 1

        return min(slots, self.waypoint.max_waypoints)

    def get_summary(self) -> Dict:
        """Get a summary of key configuration values.

        Returns:
            Dictionary with key config values for debugging
        """
        return {
            'map_zoom_range': f"{self.map_display.min_zoom}-{self.map_display.max_zoom}",
            'chunk_render_size': self.map_display.chunk_render_size,
            'max_waypoints': self.waypoint.max_waypoints,
            'unlock_levels': self.waypoint.unlock_levels,
            'teleport_cooldown': self.waypoint.teleport_cooldown,
            'waypoints_enabled': self.waypoint.enabled
        }
