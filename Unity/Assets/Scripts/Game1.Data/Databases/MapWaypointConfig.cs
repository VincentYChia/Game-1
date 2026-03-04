// ============================================================================
// Game1.Data.Databases.MapWaypointConfig
// Migrated from: core/game_engine.py (map/waypoint config sections)
// Migration phase: 2
// Date: 2026-02-21
//
// Configuration for map display, biome colors, and waypoint limits.
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;
using Game1.Core;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton configuration for map UI: biome colors, waypoint limits, display settings.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class MapWaypointConfig
    {
        private static MapWaypointConfig _instance;
        private static readonly object _lock = new object();

        public static MapWaypointConfig Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new MapWaypointConfig();
                        }
                    }
                }
                return _instance;
            }
        }

        private MapWaypointConfig()
        {
            InitializeDefaults();
        }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        // ====================================================================
        // Biome Colors (RGB tuples for map rendering)
        // Matches Python: game_engine.py biome color definitions
        // ====================================================================

        private readonly Dictionary<string, BiomeColor> _biomeColors = new(StringComparer.OrdinalIgnoreCase);

        // ====================================================================
        // Waypoint Configuration
        // ====================================================================

        /// <summary>Base number of waypoints a player can place.</summary>
        public int BaseWaypoints { get; private set; } = 3;

        /// <summary>Additional waypoints gained per 5 levels.</summary>
        public int WaypointsPerTier { get; private set; } = 1;

        /// <summary>Maximum waypoints at any level.</summary>
        public int MaxWaypoints { get; private set; } = 10;

        /// <summary>Map zoom levels available.</summary>
        public float[] ZoomLevels { get; private set; } = { 0.5f, 1.0f, 2.0f, 4.0f };

        // ====================================================================
        // Initialization
        // ====================================================================

        private void InitializeDefaults()
        {
            // Default biome colors (R, G, B as 0-255)
            // Matches Python game_engine.py map rendering
            _biomeColors["plains"]    = new BiomeColor(120, 180, 80);
            _biomeColors["forest"]    = new BiomeColor(34, 120, 34);
            _biomeColors["mountain"]  = new BiomeColor(140, 130, 120);
            _biomeColors["desert"]    = new BiomeColor(210, 190, 130);
            _biomeColors["swamp"]     = new BiomeColor(80, 100, 60);
            _biomeColors["snow"]      = new BiomeColor(230, 230, 240);
            _biomeColors["volcanic"]  = new BiomeColor(70, 30, 20);
            _biomeColors["ocean"]     = new BiomeColor(40, 80, 160);
            _biomeColors["river"]     = new BiomeColor(60, 100, 180);
            _biomeColors["cave"]      = new BiomeColor(60, 50, 50);
            _biomeColors["ruins"]     = new BiomeColor(150, 140, 100);

            Loaded = true;
        }

        /// <summary>
        /// Load optional config overrides from JSON.
        /// </summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[MapWaypointConfig] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var data = JObject.Parse(json);

                if (data["baseWaypoints"] != null)
                    BaseWaypoints = data["baseWaypoints"].Value<int>();
                if (data["waypointsPerTier"] != null)
                    WaypointsPerTier = data["waypointsPerTier"].Value<int>();
                if (data["maxWaypoints"] != null)
                    MaxWaypoints = data["maxWaypoints"].Value<int>();

                // Load biome color overrides
                var colors = data["biomeColors"] as JObject;
                if (colors != null)
                {
                    foreach (var kvp in colors)
                    {
                        var arr = kvp.Value as JArray;
                        if (arr != null && arr.Count >= 3)
                        {
                            _biomeColors[kvp.Key] = new BiomeColor(
                                arr[0].Value<int>(),
                                arr[1].Value<int>(),
                                arr[2].Value<int>()
                            );
                        }
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine($"[MapWaypointConfig] Loaded config from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[MapWaypointConfig] Error loading {relativePath}: {ex.Message}");
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>
        /// Get the biome color for map rendering. Returns default gray for unknown biomes.
        /// </summary>
        public BiomeColor GetBiomeColor(string chunkType)
        {
            if (string.IsNullOrEmpty(chunkType))
                return new BiomeColor(128, 128, 128);

            return _biomeColors.TryGetValue(chunkType, out var color) ? color : new BiomeColor(128, 128, 128);
        }

        /// <summary>
        /// Get maximum waypoints for a given player level.
        /// Base + 1 per 5 levels, capped at MaxWaypoints.
        /// </summary>
        public int GetMaxWaypointsForLevel(int level)
        {
            int bonus = (level / 5) * WaypointsPerTier;
            return Math.Min(BaseWaypoints + bonus, MaxWaypoints);
        }
    }

    /// <summary>Simple RGB color for map rendering (0-255).</summary>
    public struct BiomeColor
    {
        public int R { get; }
        public int G { get; }
        public int B { get; }

        public BiomeColor(int r, int g, int b)
        {
            R = Math.Clamp(r, 0, 255);
            G = Math.Clamp(g, 0, 255);
            B = Math.Clamp(b, 0, 255);
        }
    }
}
