"""Game configuration constants"""


class Config:
    """Global configuration constants for game settings"""

    # Window
    SCREEN_WIDTH = 1600
    SCREEN_HEIGHT = 900
    FPS = 60

    # World
    WORLD_SIZE = 100
    CHUNK_SIZE = 16
    TILE_SIZE = 32

    # Viewport (FIXED)
    VIEWPORT_WIDTH = 1200
    VIEWPORT_HEIGHT = 900

    # UI Layout
    UI_PANEL_WIDTH = 400
    INVENTORY_PANEL_X = 0
    INVENTORY_PANEL_Y = 600
    INVENTORY_PANEL_WIDTH = 1200
    INVENTORY_PANEL_HEIGHT = 300
    INVENTORY_SLOT_SIZE = 50
    INVENTORY_SLOTS_PER_ROW = 10

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
