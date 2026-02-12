// Game1.Core.GameConfig
// Migrated from: core/config.py (200 lines)
// Phase: 2 - Data Layer
// All game configuration constants from the Python Config class.

using System;
using System.Collections.Generic;

namespace Game1.Core
{
    /// <summary>
    /// Global configuration constants. Ported 1:1 from Python Config class.
    /// In Unity, display/screen management uses Unity's built-in systems,
    /// so init_screen_settings is simplified.
    /// </summary>
    public static class GameConfig
    {
        // Base resolution (1600x900 is the design baseline)
        public const int BASE_WIDTH = 1600;
        public const int BASE_HEIGHT = 900;

        // Runtime values (set during init)
        public static int ScreenWidth = 1600;
        public static int ScreenHeight = 900;
        public const int FPS = 60;
        public static bool Fullscreen = false;

        // UI Scale factor (calculated based on actual screen size)
        public static float UIScale = 1.0f;

        // World - Centered coordinate system with (0,0,0) at center
        // Infinite world - no fixed size, chunks generated on demand
        public const int CHUNK_SIZE = 16;
        public const int TILE_SIZE = 32;

        // Chunk loading (defaults - actual values from WorldGenerationConfig)
        public const int CHUNK_LOAD_RADIUS = 4;
        public const int SPAWN_ALWAYS_LOADED = 1;

        // Legacy constants (kept for compatibility during transition)
        public const int WORLD_SIZE = 176;
        public const int NUM_CHUNKS = 11;

        // Player spawn and safe zone
        public const float PLAYER_SPAWN_X = 0.0f;
        public const float PLAYER_SPAWN_Y = 0.0f;
        public const float PLAYER_SPAWN_Z = 0.0f;
        public const int SAFE_ZONE_RADIUS = 8;

        // Character/Movement
        public const float PLAYER_SPEED = 0.15f;
        public const float INTERACTION_RANGE = 3.5f;
        public const float CLICK_TOLERANCE = 0.7f;

        // Viewport (scales with screen width, 75% of screen width)
        public static int VIEWPORT_WIDTH = 1200;
        public static int VIEWPORT_HEIGHT = 900;

        // UI Layout (Base values at 1600x900 - will be scaled)
        public static int UI_PANEL_WIDTH = 400;
        public static int INVENTORY_PANEL_X = 0;
        public static int INVENTORY_PANEL_Y = 600;
        public static int INVENTORY_PANEL_WIDTH = 1200;
        public static int INVENTORY_PANEL_HEIGHT = 300;
        public static int INVENTORY_SLOT_SIZE = 50;
        public static int INVENTORY_SLOTS_PER_ROW = 10;

        // Pre-calculated menu sizes (scaled during init)
        public static int MENU_SMALL_W = 600;
        public static int MENU_SMALL_H = 500;
        public static int MENU_MEDIUM_W = 800;
        public static int MENU_MEDIUM_H = 600;
        public static int MENU_LARGE_W = 1000;
        public static int MENU_LARGE_H = 700;
        public static int MENU_XLARGE_W = 1200;
        public static int MENU_XLARGE_H = 750;

        // Debug Mode
        public static bool DEBUG_INFINITE_RESOURCES = false;
        public static bool DEBUG_INFINITE_DURABILITY = false;

        // Death Penalty Settings
        public static bool KEEP_INVENTORY = true;

        // Colors (R, G, B, A) - converted to int tuples for portability
        // Phase 6 will convert these to UnityEngine.Color32
        public static readonly (int R, int G, int B, int A) COLOR_BACKGROUND = (20, 20, 30, 255);
        public static readonly (int R, int G, int B, int A) COLOR_GRID = (40, 40, 50, 255);
        public static readonly (int R, int G, int B, int A) COLOR_GRASS = (34, 139, 34, 255);
        public static readonly (int R, int G, int B, int A) COLOR_STONE = (128, 128, 128, 255);
        public static readonly (int R, int G, int B, int A) COLOR_WATER = (30, 144, 255, 255);
        public static readonly (int R, int G, int B, int A) COLOR_PLAYER = (255, 215, 0, 255);
        public static readonly (int R, int G, int B, int A) COLOR_INTERACTION_RANGE = (255, 255, 0, 50);
        public static readonly (int R, int G, int B, int A) COLOR_UI_BG = (30, 30, 40, 255);
        public static readonly (int R, int G, int B, int A) COLOR_TEXT = (255, 255, 255, 255);
        public static readonly (int R, int G, int B, int A) COLOR_HEALTH = (255, 0, 0, 255);
        public static readonly (int R, int G, int B, int A) COLOR_HEALTH_BG = (50, 50, 50, 255);
        public static readonly (int R, int G, int B, int A) COLOR_TREE = (0, 100, 0, 255);
        public static readonly (int R, int G, int B, int A) COLOR_ORE = (169, 169, 169, 255);
        public static readonly (int R, int G, int B, int A) COLOR_STONE_NODE = (105, 105, 105, 255);
        public static readonly (int R, int G, int B, int A) COLOR_HP_BAR = (0, 255, 0, 255);
        public static readonly (int R, int G, int B, int A) COLOR_HP_BAR_BG = (100, 100, 100, 255);
        public static readonly (int R, int G, int B, int A) COLOR_DAMAGE_NORMAL = (255, 255, 255, 255);
        public static readonly (int R, int G, int B, int A) COLOR_DAMAGE_CRIT = (255, 215, 0, 255);
        public static readonly (int R, int G, int B, int A) COLOR_SLOT_EMPTY = (40, 40, 50, 255);
        public static readonly (int R, int G, int B, int A) COLOR_SLOT_FILLED = (50, 60, 70, 255);
        public static readonly (int R, int G, int B, int A) COLOR_SLOT_BORDER = (100, 100, 120, 255);
        public static readonly (int R, int G, int B, int A) COLOR_SLOT_SELECTED = (255, 215, 0, 255);
        public static readonly (int R, int G, int B, int A) COLOR_TOOLTIP_BG = (20, 20, 30, 230);
        public static readonly (int R, int G, int B, int A) COLOR_RESPAWN_BAR = (100, 200, 100, 255);
        public static readonly (int R, int G, int B, int A) COLOR_CAN_HARVEST = (100, 255, 100, 255);
        public static readonly (int R, int G, int B, int A) COLOR_CANNOT_HARVEST = (255, 100, 100, 255);
        public static readonly (int R, int G, int B, int A) COLOR_NOTIFICATION = (255, 215, 0, 255);
        public static readonly (int R, int G, int B, int A) COLOR_EQUIPPED = (255, 215, 0, 255);

        public static readonly Dictionary<string, (int R, int G, int B, int A)> RARITY_COLORS = new()
        {
            { "common",    (200, 200, 200, 255) },
            { "uncommon",  (30, 255, 0, 255) },
            { "rare",      (0, 112, 221, 255) },
            { "epic",      (163, 53, 238, 255) },
            { "legendary", (255, 128, 0, 255) },
            { "artifact",  (230, 204, 128, 255) }
        };

        /// <summary>
        /// Initialize screen settings. In Unity, this reads from Screen class.
        /// Simplified from Python version which used pygame display info.
        /// </summary>
        public static void InitScreenSettings(int width, int height, bool fullscreen = false)
        {
            ScreenWidth = Math.Clamp(width, 1280, 3840);
            ScreenHeight = Math.Clamp(height, 720, 2160);
            Fullscreen = fullscreen;

            UIScale = (float)ScreenHeight / BASE_HEIGHT;

            VIEWPORT_WIDTH = (int)(ScreenWidth * 0.75f);
            VIEWPORT_HEIGHT = ScreenHeight;
            UI_PANEL_WIDTH = ScreenWidth - VIEWPORT_WIDTH;

            INVENTORY_PANEL_Y = Scale(600);
            INVENTORY_PANEL_WIDTH = VIEWPORT_WIDTH;
            INVENTORY_PANEL_HEIGHT = ScreenHeight - INVENTORY_PANEL_Y;
            INVENTORY_SLOT_SIZE = Scale(50);

            int slotSpacing = 5;
            int availableWidth = INVENTORY_PANEL_WIDTH - 40;
            INVENTORY_SLOTS_PER_ROW = Math.Max(8, availableWidth / (INVENTORY_SLOT_SIZE + slotSpacing));

            MENU_SMALL_W = Scale(600);
            MENU_SMALL_H = Scale(500);
            MENU_MEDIUM_W = Scale(800);
            MENU_MEDIUM_H = Scale(600);
            MENU_LARGE_W = Scale(1000);
            MENU_LARGE_H = Scale(700);
            MENU_XLARGE_W = Scale(1200);
            MENU_XLARGE_H = Scale(750);
        }

        public static int Scale(int value) => (int)(value * UIScale);
        public static float ScaleF(float value) => value * UIScale;
    }
}
