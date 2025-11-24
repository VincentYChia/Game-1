"""Game configuration constants"""

import pygame


class Config:
    """Global configuration constants for game settings"""

    # Base resolution (1600x900 is the design baseline)
    BASE_WIDTH = 1600
    BASE_HEIGHT = 900

    # Actual window size (will be set during init)
    SCREEN_WIDTH = 1600
    SCREEN_HEIGHT = 900
    FPS = 60

    # UI Scale factor (calculated based on actual screen size)
    UI_SCALE = 1.0

    # World
    WORLD_SIZE = 100
    CHUNK_SIZE = 16
    TILE_SIZE = 32

    # Viewport (scales with screen width, 75% of screen width)
    VIEWPORT_WIDTH = 1200
    VIEWPORT_HEIGHT = 900

    # UI Layout (Base values at 1600x900)
    UI_PANEL_WIDTH = 400
    INVENTORY_PANEL_X = 0
    INVENTORY_PANEL_Y = 600
    INVENTORY_PANEL_WIDTH = 1200
    INVENTORY_PANEL_HEIGHT = 300
    INVENTORY_SLOT_SIZE = 50
    INVENTORY_SLOTS_PER_ROW = 10
    # Inventory grid Y position - DEPRECATED, calculate dynamically instead
    INVENTORY_GRID_Y = 725  # INVENTORY_PANEL_Y + 125

    @classmethod
    def init_screen_settings(cls, width=None, height=None):
        """Initialize screen settings based on display or custom size

        Args:
            width: Custom width (None = use display info)
            height: Custom height (None = use display info)
        """
        if width is None or height is None:
            # Auto-detect display size
            pygame.init()
            display_info = pygame.display.Info()
            # Use 90% of screen to leave room for taskbar/etc
            width = width or int(display_info.current_w * 0.9)
            height = height or int(display_info.current_h * 0.9)

            # Clamp to minimum size (keep 16:9 ratio)
            width = max(1280, width)
            height = max(720, height)

            # Clamp to maximum size (don't go above 4K)
            width = min(3840, width)
            height = min(2160, height)

        cls.SCREEN_WIDTH = width
        cls.SCREEN_HEIGHT = height

        # Calculate UI scale for INVENTORY/HUD only (not popup windows)
        cls.UI_SCALE = height / cls.BASE_HEIGHT

        # Scale main layout: viewport (75% width) and UI panel (25% width)
        cls.VIEWPORT_WIDTH = int(width * 0.75)
        cls.VIEWPORT_HEIGHT = height
        cls.UI_PANEL_WIDTH = width - cls.VIEWPORT_WIDTH

        # Scale inventory panel (bottom of screen)
        cls.INVENTORY_PANEL_Y = int(600 * cls.UI_SCALE)
        cls.INVENTORY_PANEL_WIDTH = cls.VIEWPORT_WIDTH
        cls.INVENTORY_PANEL_HEIGHT = height - cls.INVENTORY_PANEL_Y
        cls.INVENTORY_SLOT_SIZE = int(50 * cls.UI_SCALE)

        # Calculate slots per row based on available width
        slot_spacing = 5
        available_width = cls.INVENTORY_PANEL_WIDTH - 40  # 20px margin each side
        cls.INVENTORY_SLOTS_PER_ROW = max(8, available_width // (cls.INVENTORY_SLOT_SIZE + slot_spacing))

        print(f"🖥️  Screen: {width}x{height} (scale: {cls.UI_SCALE:.2f}x)")
        print(f"   Viewport: {cls.VIEWPORT_WIDTH}x{cls.VIEWPORT_HEIGHT}")
        print(f"   Inventory slots: {cls.INVENTORY_SLOT_SIZE}px ({cls.INVENTORY_SLOTS_PER_ROW} per row)")
        print(f"   Note: Popup menus remain fixed-size for consistency")

    @classmethod
    def scale(cls, value):
        """Scale a value by UI_SCALE"""
        return int(value * cls.UI_SCALE)

    # Character/Movement
    PLAYER_SPEED = 0.15
    INTERACTION_RANGE = 3.5
    CLICK_TOLERANCE = 0.7

    # Debug Mode
    DEBUG_INFINITE_RESOURCES = False  # Toggle with F1

    # Colors
    COLOR_BACKGROUND = (20, 20, 30)
    COLOR_GRID = (40, 40, 50)
    COLOR_GRASS = (34, 139, 34)
    COLOR_STONE = (128, 128, 128)
    COLOR_WATER = (30, 144, 255)
    COLOR_PLAYER = (255, 215, 0)
    COLOR_INTERACTION_RANGE = (255, 255, 0, 50)
    COLOR_UI_BG = (30, 30, 40)
    COLOR_TEXT = (255, 255, 255)
    COLOR_HEALTH = (255, 0, 0)
    COLOR_HEALTH_BG = (50, 50, 50)
    COLOR_TREE = (0, 100, 0)
    COLOR_ORE = (169, 169, 169)
    COLOR_STONE_NODE = (105, 105, 105)
    COLOR_HP_BAR = (0, 255, 0)
    COLOR_HP_BAR_BG = (100, 100, 100)
    COLOR_DAMAGE_NORMAL = (255, 255, 255)
    COLOR_DAMAGE_CRIT = (255, 215, 0)
    COLOR_SLOT_EMPTY = (40, 40, 50)
    COLOR_SLOT_FILLED = (50, 60, 70)
    COLOR_SLOT_BORDER = (100, 100, 120)
    COLOR_SLOT_SELECTED = (255, 215, 0)
    COLOR_TOOLTIP_BG = (20, 20, 30, 230)
    COLOR_RESPAWN_BAR = (100, 200, 100)
    COLOR_CAN_HARVEST = (100, 255, 100)
    COLOR_CANNOT_HARVEST = (255, 100, 100)
    COLOR_NOTIFICATION = (255, 215, 0)
    COLOR_EQUIPPED = (255, 215, 0)  # Gold border for equipped items

    RARITY_COLORS = {
        "common": (200, 200, 200),
        "uncommon": (30, 255, 0),
        "rare": (0, 112, 221),
        "epic": (163, 53, 238),
        "legendary": (255, 128, 0),
        "artifact": (230, 204, 128)
    }
