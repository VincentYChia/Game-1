// ============================================================================
// Game1.Data.Databases.WorldGenerationConfig
// Migrated from: systems/world_system.py (generation config), world_generation.JSON
// Migration phase: 2
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Game1.Core;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Danger level distribution for a given distance from spawn.
    /// </summary>
    public class DangerDistribution
    {
        public float Peaceful { get; set; }
        public float Low { get; set; }
        public float Medium { get; set; }
        public float High { get; set; }
        public float Extreme { get; set; }
    }

    /// <summary>
    /// Resource configuration for a danger level.
    /// </summary>
    public class ResourceConfig
    {
        public int MinTier { get; set; } = 1;
        public int MaxTier { get; set; } = 1;
        public float Density { get; set; } = 1.0f;
    }

    /// <summary>
    /// Singleton configuration for world generation parameters.
    /// Loaded from Definitions.JSON/world_generation.JSON.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class WorldGenerationConfig
    {
        private static WorldGenerationConfig _instance;
        private static readonly object _lock = new object();

        private JObject _rawConfig;
        private readonly Dictionary<int, DangerDistribution> _dangerDistributions = new();
        private readonly Dictionary<string, ResourceConfig> _resourceConfigs = new();

        public static WorldGenerationConfig Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new WorldGenerationConfig();
                            _instance._loadConfig();
                        }
                    }
                }
                return _instance;
            }
        }

        private WorldGenerationConfig() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        // ====================================================================
        // Config Values (defaults matching Python)
        // ====================================================================

        public int ChunkLoadRadius { get; private set; } = 4;
        public int SpawnAlwaysLoaded { get; private set; } = 1;
        public float SafeZoneRadius { get; private set; } = 8f;
        public int WorldSeed { get; private set; } = 0;

        // ====================================================================
        // Loading
        // ====================================================================

        private void _loadConfig()
        {
            string fullPath = GamePaths.GetContentPath("Definitions.JSON/world_generation.JSON");
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine("[WorldGenerationConfig] Config file not found, using defaults");
                Loaded = true;
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                _rawConfig = JObject.Parse(json);

                // Extract basic config
                ChunkLoadRadius = _rawConfig["chunkLoadRadius"]?.Value<int>() ?? 4;
                SpawnAlwaysLoaded = _rawConfig["spawnAlwaysLoaded"]?.Value<int>() ?? 1;

                var spawnArea = _rawConfig["spawnArea"] as JObject;
                if (spawnArea != null)
                {
                    SafeZoneRadius = spawnArea["resourceExclusionRadius"]?.Value<float>() ?? 8f;
                }

                WorldSeed = _rawConfig["worldSeed"]?.Value<int>() ?? 0;

                Loaded = true;
                System.Diagnostics.Debug.WriteLine("[WorldGenerationConfig] Loaded world generation config");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[WorldGenerationConfig] Error loading config: {ex.Message}");
                Loaded = true; // Still mark as loaded with defaults
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>
        /// Get danger distribution for a given distance from spawn.
        /// At distance 0 (spawn), danger is 100% peaceful.
        /// </summary>
        public DangerDistribution GetDangerDistribution(int chunkDistance)
        {
            if (chunkDistance <= 0)
            {
                return new DangerDistribution
                {
                    Peaceful = 1.0f, Low = 0f, Medium = 0f, High = 0f, Extreme = 0f
                };
            }

            // Progressive danger scaling
            float peaceful = MathF.Max(0f, 1.0f - chunkDistance * 0.15f);
            float remaining = 1.0f - peaceful;

            return new DangerDistribution
            {
                Peaceful = peaceful,
                Low = remaining * 0.4f,
                Medium = remaining * 0.3f,
                High = remaining * 0.2f,
                Extreme = remaining * 0.1f,
            };
        }

        /// <summary>
        /// Get resource configuration for a danger level string.
        /// </summary>
        public ResourceConfig GetResourceConfig(string dangerLevel)
        {
            if (_resourceConfigs.TryGetValue(dangerLevel, out var config))
                return config;

            // Default based on danger level
            return dangerLevel switch
            {
                "peaceful" => new ResourceConfig { MinTier = 1, MaxTier = 1, Density = 1.0f },
                "low"      => new ResourceConfig { MinTier = 1, MaxTier = 2, Density = 0.8f },
                "medium"   => new ResourceConfig { MinTier = 2, MaxTier = 3, Density = 0.6f },
                "high"     => new ResourceConfig { MinTier = 2, MaxTier = 4, Density = 0.4f },
                "extreme"  => new ResourceConfig { MinTier = 3, MaxTier = 4, Density = 0.3f },
                _          => new ResourceConfig { MinTier = 1, MaxTier = 1, Density = 1.0f },
            };
        }

        /// <summary>Get the raw JObject for advanced queries.</summary>
        public JObject RawConfig => _rawConfig;
    }
}
