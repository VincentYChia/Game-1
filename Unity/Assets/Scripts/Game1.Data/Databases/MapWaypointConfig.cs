// Game1.Data.Databases.MapWaypointConfig
// Migrated from: data/databases/map_waypoint_db.py (301 lines)
// Phase: 2 - Data Layer
// Loads from Definitions.JSON/map-waypoint-config.JSON.

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace Game1.Data.Databases
{
    // -- Nested config classes --

    [Serializable]
    public class MapDisplayConfig
    {
        public float DefaultZoom { get; set; } = 1.0f;
        public float MinZoom { get; set; } = 0.25f;
        public float MaxZoom { get; set; } = 4.0f;
        public float ZoomStep { get; set; } = 0.25f;
        public int ChunkRenderSize { get; set; } = 12;
        public bool ShowGrid { get; set; } = true;
        public bool ShowCoordinates { get; set; } = true;
        public bool ShowPlayerMarker { get; set; } = true;
        public bool ShowWaypointMarkers { get; set; } = true;
        public bool CenterOnPlayer { get; set; } = true;
    }

    [Serializable]
    public class MarkerConfig
    {
        public (int R, int G, int B) Color { get; set; } = (255, 255, 255);
        public int Size { get; set; } = 8;
        public string Shape { get; set; } = "circle";
        public bool ShowLabel { get; set; } = false;
    }

    [Serializable]
    public class WaypointSystemConfig
    {
        public bool Enabled { get; set; } = true;
        public bool SpawnAlwaysAvailable { get; set; } = true;
        public string SpawnDefaultName { get; set; } = "Spawn";
        public (int X, int Y) SpawnPosition { get; set; } = (0, 0);
        public List<int> UnlockLevels { get; set; } = new() { 5, 10, 15, 20, 25, 30 };
        public int MaxWaypoints { get; set; } = 7;
        public float TeleportCooldown { get; set; } = 30.0f;
        public int TeleportManaCost { get; set; } = 0;
        public bool RequireSolidGround { get; set; } = true;
        public int MinDistanceBetweenWaypoints { get; set; } = 32;
        public bool BlockedInDungeons { get; set; } = true;
        public bool BlockedInCombat { get; set; } = true;
        public int MaxNameLength { get; set; } = 24;
        public string DefaultNameFormat { get; set; } = "Waypoint {number}";
    }

    [Serializable]
    public class MapUIConfig
    {
        public (int W, int H) MapWindowSize { get; set; } = (700, 600);
        public int WaypointPanelWidth { get; set; } = 200;
        public (int R, int G, int B, int A) BackgroundColor { get; set; } = (20, 20, 30, 240);
        public (int R, int G, int B) BorderColor { get; set; } = (100, 100, 120);
        public (int R, int G, int B) FontColor { get; set; } = (220, 220, 220);
    }

    /// <summary>
    /// Singleton config for map display and waypoint system.
    /// Loads from Definitions.JSON/map-waypoint-config.JSON.
    /// </summary>
    public class MapWaypointConfig
    {
        private static MapWaypointConfig _instance;
        private static readonly object _lock = new object();

        public MapDisplayConfig MapDisplay { get; private set; }
        public Dictionary<string, (int R, int G, int B)> BiomeColors { get; private set; }
        public MarkerConfig PlayerMarker { get; private set; }
        public MarkerConfig WaypointMarker { get; private set; }
        public MarkerConfig DungeonMarker { get; private set; }
        public WaypointSystemConfig Waypoint { get; private set; }
        public MapUIConfig UI { get; private set; }
        public bool Loaded { get; private set; }

        public static MapWaypointConfig GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new MapWaypointConfig();
                }
            }
            return _instance;
        }

        private MapWaypointConfig()
        {
            MapDisplay = new MapDisplayConfig();
            BiomeColors = new Dictionary<string, (int, int, int)>();
            PlayerMarker = new MarkerConfig();
            WaypointMarker = new MarkerConfig();
            DungeonMarker = new MarkerConfig();
            Waypoint = new WaypointSystemConfig();
            UI = new MapUIConfig();

            LoadConfig();
        }

        private void LoadConfig()
        {
            var data = JsonLoader.LoadRawJson("Definitions.JSON/map-waypoint-config.JSON");
            if (data == null)
            {
                SetDefaults();
                return;
            }

            try
            {
                ParseMapDisplay(data["map_display"] as JObject);
                ParseBiomeColors(data["biome_colors"] as JObject);
                ParseMarkers(data["marker_icons"] as JObject);
                ParseWaypointSystem(data["waypoint_system"] as JObject);
                ParseUISettings(data["ui_settings"] as JObject);

                Loaded = true;
                JsonLoader.Log($"Loaded map/waypoint config (max {Waypoint.MaxWaypoints} waypoints, {BiomeColors.Count} biome colors)");
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error parsing map-waypoint-config.JSON: {ex.Message}");
                SetDefaults();
            }
        }

        private void ParseMapDisplay(JObject data)
        {
            if (data == null) return;

            MapDisplay = new MapDisplayConfig
            {
                DefaultZoom = data.Value<float?>("default_zoom") ?? 1.0f,
                MinZoom = data.Value<float?>("min_zoom") ?? 0.25f,
                MaxZoom = data.Value<float?>("max_zoom") ?? 4.0f,
                ZoomStep = data.Value<float?>("zoom_step") ?? 0.25f,
                ChunkRenderSize = data.Value<int?>("chunk_render_size") ?? 12,
                ShowGrid = data.Value<bool?>("show_grid") ?? true,
                ShowCoordinates = data.Value<bool?>("show_coordinates") ?? true,
                ShowPlayerMarker = data.Value<bool?>("show_player_marker") ?? true,
                ShowWaypointMarkers = data.Value<bool?>("show_waypoint_markers") ?? true,
                CenterOnPlayer = data.Value<bool?>("center_on_player") ?? true
            };
        }

        private void ParseBiomeColors(JObject data)
        {
            var defaultColors = new Dictionary<string, (int, int, int)>
            {
                { "peaceful_forest", (34, 139, 34) },
                { "dangerous_forest", (0, 100, 0) },
                { "rare_hidden_forest", (50, 205, 50) },
                { "peaceful_cave", (105, 105, 105) },
                { "dangerous_cave", (64, 64, 64) },
                { "rare_deep_cave", (138, 43, 226) },
                { "peaceful_quarry", (160, 82, 45) },
                { "dangerous_quarry", (139, 69, 19) },
                { "rare_ancient_quarry", (255, 140, 0) },
                { "water_lake", (65, 105, 225) },
                { "water_river", (70, 130, 180) },
                { "water_cursed_swamp", (75, 0, 130) },
                { "unexplored", (30, 30, 40) },
                { "spawn_area", (255, 215, 0) }
            };

            BiomeColors = new Dictionary<string, (int, int, int)>();
            foreach (var kvp in defaultColors)
            {
                if (data != null && data[kvp.Key] is JArray arr && arr.Count >= 3)
                {
                    BiomeColors[kvp.Key] = (arr[0].Value<int>(), arr[1].Value<int>(), arr[2].Value<int>());
                }
                else
                {
                    BiomeColors[kvp.Key] = kvp.Value;
                }
            }
        }

        private void ParseMarkers(JObject data)
        {
            if (data == null) return;

            var playerData = data["player"] as JObject;
            if (playerData != null)
            {
                PlayerMarker = new MarkerConfig
                {
                    Color = ParseColor(playerData["color"] as JArray, (255, 255, 255)),
                    Size = playerData.Value<int?>("size") ?? 8,
                    Shape = playerData.Value<string>("shape") ?? "triangle",
                    ShowLabel = false
                };
            }

            var waypointData = data["waypoint"] as JObject;
            if (waypointData != null)
            {
                WaypointMarker = new MarkerConfig
                {
                    Color = ParseColor(waypointData["color"] as JArray, (255, 215, 0)),
                    Size = waypointData.Value<int?>("size") ?? 10,
                    Shape = waypointData.Value<string>("shape") ?? "diamond",
                    ShowLabel = waypointData.Value<bool?>("show_label") ?? true
                };
            }

            var dungeonData = data["dungeon"] as JObject;
            if (dungeonData != null)
            {
                DungeonMarker = new MarkerConfig
                {
                    Color = ParseColor(dungeonData["color"] as JArray, (220, 20, 60)),
                    Size = dungeonData.Value<int?>("size") ?? 8,
                    Shape = dungeonData.Value<string>("shape") ?? "skull",
                    ShowLabel = false
                };
            }
        }

        private void ParseWaypointSystem(JObject data)
        {
            if (data == null) return;

            var spawnData = data["spawn_waypoint"] as JObject;
            var unlockData = data["unlock_schedule"] as JObject;
            var placementData = data["placement_rules"] as JObject;
            var namingData = data["waypoint_naming"] as JObject;
            var costData = data["teleport_cost"] as JObject;

            var spawnPos = spawnData?["position"] as JArray;
            var unlockLevels = unlockData?["levels"] as JArray;

            bool costEnabled = costData?.Value<bool?>("enabled") ?? false;

            Waypoint = new WaypointSystemConfig
            {
                Enabled = data.Value<bool?>("enabled") ?? true,
                SpawnAlwaysAvailable = spawnData?.Value<bool?>("always_available") ?? true,
                SpawnDefaultName = spawnData?.Value<string>("default_name") ?? "Spawn",
                SpawnPosition = spawnPos != null && spawnPos.Count >= 2
                    ? (spawnPos[0].Value<int>(), spawnPos[1].Value<int>())
                    : (0, 0),
                UnlockLevels = unlockLevels?.Select(v => v.Value<int>()).ToList() ?? new List<int> { 5, 10, 15, 20, 25, 30 },
                MaxWaypoints = data.Value<int?>("max_waypoints") ?? 7,
                TeleportCooldown = data.Value<float?>("teleport_cooldown") ?? 30.0f,
                TeleportManaCost = costEnabled ? (costData?.Value<int?>("mana_cost") ?? 0) : 0,
                RequireSolidGround = placementData?.Value<bool?>("require_solid_ground") ?? true,
                MinDistanceBetweenWaypoints = placementData?.Value<int?>("min_distance_between_waypoints") ?? 32,
                BlockedInDungeons = placementData?.Value<bool?>("blocked_in_dungeons") ?? true,
                BlockedInCombat = placementData?.Value<bool?>("blocked_in_combat") ?? true,
                MaxNameLength = namingData?.Value<int?>("max_name_length") ?? 24,
                DefaultNameFormat = namingData?.Value<string>("default_name_format") ?? "Waypoint {number}"
            };
        }

        private void ParseUISettings(JObject data)
        {
            if (data == null) return;

            var size = data["map_window_size"] as JArray;
            var bg = data["background_color"] as JArray;
            var border = data["border_color"] as JArray;
            var font = data["font_color"] as JArray;

            UI = new MapUIConfig
            {
                MapWindowSize = size != null && size.Count >= 2
                    ? (size[0].Value<int>(), size[1].Value<int>())
                    : (700, 600),
                WaypointPanelWidth = data.Value<int?>("waypoint_panel_width") ?? 200,
                BackgroundColor = bg != null && bg.Count >= 4
                    ? (bg[0].Value<int>(), bg[1].Value<int>(), bg[2].Value<int>(), bg[3].Value<int>())
                    : bg != null && bg.Count >= 3
                        ? (bg[0].Value<int>(), bg[1].Value<int>(), bg[2].Value<int>(), 240)
                        : (20, 20, 30, 240),
                BorderColor = ParseColor(border, (100, 100, 120)),
                FontColor = ParseColor(font, (220, 220, 220))
            };
        }

        private void SetDefaults()
        {
            MapDisplay = new MapDisplayConfig();
            ParseBiomeColors(null);
            PlayerMarker = new MarkerConfig { Color = (255, 255, 255), Shape = "triangle" };
            WaypointMarker = new MarkerConfig { Color = (255, 215, 0), Shape = "diamond", ShowLabel = true };
            DungeonMarker = new MarkerConfig { Color = (220, 20, 60), Shape = "skull" };
            Waypoint = new WaypointSystemConfig();
            UI = new MapUIConfig();
            Loaded = true;
        }

        /// <summary>
        /// Get the color for a specific chunk type.
        /// </summary>
        public (int R, int G, int B) GetBiomeColor(string chunkType)
        {
            string key = chunkType.ToLower();
            if (BiomeColors.TryGetValue(key, out var color))
                return color;
            if (BiomeColors.TryGetValue("unexplored", out var unexplored))
                return unexplored;
            return (30, 30, 40);
        }

        /// <summary>
        /// Calculate how many waypoint slots are available at a given level.
        /// </summary>
        public int GetMaxWaypointsForLevel(int level)
        {
            if (!Waypoint.Enabled) return 0;

            int slots = Waypoint.SpawnAlwaysAvailable ? 1 : 0;

            foreach (int unlockLevel in Waypoint.UnlockLevels)
            {
                if (level >= unlockLevel)
                    slots++;
            }

            return Math.Min(slots, Waypoint.MaxWaypoints);
        }

        public Dictionary<string, object> GetSummary()
        {
            return new Dictionary<string, object>
            {
                { "map_zoom_range", $"{MapDisplay.MinZoom}-{MapDisplay.MaxZoom}" },
                { "chunk_render_size", MapDisplay.ChunkRenderSize },
                { "max_waypoints", Waypoint.MaxWaypoints },
                { "unlock_levels", Waypoint.UnlockLevels },
                { "teleport_cooldown", Waypoint.TeleportCooldown },
                { "waypoints_enabled", Waypoint.Enabled }
            };
        }

        private static (int R, int G, int B) ParseColor(JArray arr, (int, int, int) defaultColor)
        {
            if (arr != null && arr.Count >= 3)
                return (arr[0].Value<int>(), arr[1].Value<int>(), arr[2].Value<int>());
            return defaultColor;
        }

        internal static void ResetInstance() => _instance = null;
    }
}
