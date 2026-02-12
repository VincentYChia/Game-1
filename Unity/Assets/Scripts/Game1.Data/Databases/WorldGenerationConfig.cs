// Game1.Data.Databases.WorldGenerationConfig
// Migrated from: data/databases/world_generation_db.py (441 lines)
// Phase: 2 - Data Layer
// Loads from Definitions.JSON/world_generation.JSON.
// CRITICAL: Uses dilutive normalization for danger distributions and water subtypes.

using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace Game1.Data.Databases
{
    // -- Nested config classes (Python @dataclass -> C# class) --

    [Serializable]
    public class ChunkLoadingConfig
    {
        public int LoadRadius { get; set; } = 4;
        public int SpawnAlwaysLoadedRadius { get; set; } = 1;
        public int ChunkSize { get; set; } = 16;
    }

    [Serializable]
    public class BiomeDistributionConfig
    {
        public float Water { get; set; } = 0.10f;
        public float Forest { get; set; } = 0.50f;
        public float Cave { get; set; } = 0.40f;

        public bool Validate()
        {
            float total = Water + Forest + Cave;
            return MathF.Abs(total - 1.0f) < 0.001f;
        }
    }

    [Serializable]
    public class BiomeClusteringConfig
    {
        public float BiomeNoiseScale { get; set; } = 4.0f;
        public int BiomeNoiseOctaves { get; set; } = 3;
        public float DangerNoiseScale { get; set; } = 6.0f;
    }

    [Serializable]
    public class DangerDistribution
    {
        public float Peaceful { get; set; } = 0.5f;
        public float Dangerous { get; set; } = 0.4f;
        public float Rare { get; set; } = 0.1f;

        public DangerDistribution() { }

        public DangerDistribution(float peaceful, float dangerous, float rare)
        {
            Peaceful = peaceful;
            Dangerous = dangerous;
            Rare = rare;
        }
    }

    [Serializable]
    public class DangerZonesConfig
    {
        public int SafeZoneRadius { get; set; } = 2;
        public int TransitionZoneRadius { get; set; } = 10;
        public bool MaxDangerEnabled { get; set; } = true;
        public DangerDistribution SafeZoneDistribution { get; set; } = new(1.0f, 0.0f, 0.0f);
        public DangerDistribution TransitionZoneDistribution { get; set; } = new(0.4f, 0.5f, 0.1f);
        public DangerDistribution OuterZoneDistribution { get; set; } = new(0.2f, 0.5f, 0.3f);
    }

    [Serializable]
    public class ResourceSpawnConfig
    {
        public int MinResources { get; set; }
        public int MaxResources { get; set; }
        public int TierMin { get; set; }
        public int TierMax { get; set; }

        public ResourceSpawnConfig() { }

        public ResourceSpawnConfig(int minRes, int maxRes, int tierMin, int tierMax)
        {
            MinResources = minRes;
            MaxResources = maxRes;
            TierMin = tierMin;
            TierMax = tierMax;
        }
    }

    [Serializable]
    public class ResourceSpawningConfig
    {
        public ResourceSpawnConfig PeacefulChunks { get; set; } = new(3, 6, 1, 2);
        public ResourceSpawnConfig DangerousChunks { get; set; } = new(5, 8, 2, 3);
        public ResourceSpawnConfig RareChunks { get; set; } = new(6, 10, 3, 4);
    }

    [Serializable]
    public class FishingSpotConfig
    {
        public int MinSpots { get; set; }
        public int MaxSpots { get; set; }
        public int TierMin { get; set; }
        public int TierMax { get; set; }

        public FishingSpotConfig() { }

        public FishingSpotConfig(int minSpots, int maxSpots, int tierMin, int tierMax)
        {
            MinSpots = minSpots;
            MaxSpots = maxSpots;
            TierMin = tierMin;
            TierMax = tierMax;
        }
    }

    [Serializable]
    public class WaterChunksConfig
    {
        public FishingSpotConfig NormalWater { get; set; } = new(3, 6, 1, 2);
        public FishingSpotConfig CursedSwamp { get; set; } = new(5, 8, 3, 4);
        public float LakeChance { get; set; } = 0.45f;
        public float RiverChance { get; set; } = 0.45f;
        public float CursedSwampChance { get; set; } = 0.10f;
    }

    [Serializable]
    public class DungeonSpawningConfig
    {
        public bool Enabled { get; set; } = true;
        public float SpawnChancePerChunk { get; set; } = 0.083f;
        public bool ExcludedInSpawnArea { get; set; } = true;
        public bool ExcludedInWater { get; set; } = true;
        public int MinDistanceFromSpawn { get; set; } = 2;
    }

    [Serializable]
    public class SpawnAreaConfig
    {
        public int ResourceExclusionRadius { get; set; } = 8;
        public bool CraftingStationsEnabled { get; set; } = true;
    }

    [Serializable]
    public class ChunkUnloadingConfig
    {
        public bool Enabled { get; set; } = true;
        public bool SaveModifiedChunks { get; set; } = true;
        public bool TrackUnloadTime { get; set; } = true;
    }

    [Serializable]
    public class WorldGenDebugConfig
    {
        public bool LogChunkGeneration { get; set; } = false;
        public bool LogBiomeAssignments { get; set; } = false;
        public bool LogDungeonSpawns { get; set; } = true;
        public bool ShowSeedOnF1 { get; set; } = true;
    }

    /// <summary>
    /// Singleton world generation configuration.
    /// Loads from Definitions.JSON/world_generation.JSON.
    /// CRITICAL: Dilutive normalization for distributions.
    /// </summary>
    public class WorldGenerationConfig
    {
        private static WorldGenerationConfig _instance;
        private static readonly object _lock = new object();
        private static bool _loaded = false;

        public ChunkLoadingConfig ChunkLoading { get; private set; }
        public BiomeDistributionConfig BiomeDistribution { get; private set; }
        public BiomeClusteringConfig BiomeClustering { get; private set; }
        public DangerZonesConfig DangerZones { get; private set; }
        public SpawnAreaConfig SpawnArea { get; private set; }
        public ResourceSpawningConfig ResourceSpawning { get; private set; }
        public WaterChunksConfig WaterChunks { get; private set; }
        public DungeonSpawningConfig DungeonSpawning { get; private set; }
        public ChunkUnloadingConfig ChunkUnloading { get; private set; }
        public WorldGenDebugConfig Debug { get; private set; }
        public bool LoadedFromFile { get; private set; }

        public static WorldGenerationConfig GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                    {
                        _instance = new WorldGenerationConfig();
                    }
                }
            }
            return _instance;
        }

        public static WorldGenerationConfig Reload()
        {
            _loaded = false;
            _instance = null;
            return GetInstance();
        }

        private WorldGenerationConfig()
        {
            InitDefaults();
            if (!_loaded)
            {
                LoadConfig();
                _loaded = true;
            }
        }

        private void InitDefaults()
        {
            ChunkLoading = new ChunkLoadingConfig();
            BiomeDistribution = new BiomeDistributionConfig();
            BiomeClustering = new BiomeClusteringConfig();
            DangerZones = new DangerZonesConfig();
            SpawnArea = new SpawnAreaConfig();
            ResourceSpawning = new ResourceSpawningConfig();
            WaterChunks = new WaterChunksConfig();
            DungeonSpawning = new DungeonSpawningConfig();
            ChunkUnloading = new ChunkUnloadingConfig();
            Debug = new WorldGenDebugConfig();
            LoadedFromFile = false;
        }

        private void LoadConfig()
        {
            var data = JsonLoader.LoadRawJson("Definitions.JSON/world_generation.JSON");
            if (data == null)
            {
                JsonLoader.LogWarning("World generation config not found, using defaults");
                return;
            }

            try
            {
                ParseConfig(data);
                LoadedFromFile = true;
                JsonLoader.Log("Loaded world generation config");
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error parsing world_generation.JSON: {ex.Message}, using defaults");
            }
        }

        private void ParseConfig(JObject data)
        {
            // Chunk loading
            if (data["chunk_loading"] is JObject cl)
            {
                ChunkLoading = new ChunkLoadingConfig
                {
                    LoadRadius = cl.Value<int?>("load_radius") ?? 4,
                    SpawnAlwaysLoadedRadius = cl.Value<int?>("spawn_always_loaded_radius") ?? 1,
                    ChunkSize = cl.Value<int?>("chunk_size") ?? 16
                };
            }

            // Biome distribution
            if (data["biome_distribution"] is JObject bd)
            {
                BiomeDistribution = new BiomeDistributionConfig
                {
                    Water = bd.Value<float?>("water") ?? 0.10f,
                    Forest = bd.Value<float?>("forest") ?? 0.50f,
                    Cave = bd.Value<float?>("cave") ?? 0.40f
                };

                if (!BiomeDistribution.Validate())
                {
                    float total = BiomeDistribution.Water + BiomeDistribution.Forest + BiomeDistribution.Cave;
                    if (total > 0)
                    {
                        BiomeDistribution.Water /= total;
                        BiomeDistribution.Forest /= total;
                        BiomeDistribution.Cave /= total;
                    }
                }
            }

            // Biome clustering
            if (data["biome_clustering"] is JObject bc)
            {
                BiomeClustering = new BiomeClusteringConfig
                {
                    BiomeNoiseScale = bc.Value<float?>("biome_noise_scale") ?? 4.0f,
                    BiomeNoiseOctaves = bc.Value<int?>("biome_noise_octaves") ?? 3,
                    DangerNoiseScale = bc.Value<float?>("danger_noise_scale") ?? 6.0f
                };
            }

            // Danger zones
            if (data["danger_zones"] is JObject dz)
            {
                DangerZones = new DangerZonesConfig
                {
                    SafeZoneRadius = dz.Value<int?>("safe_zone_radius") ?? 2,
                    TransitionZoneRadius = dz.Value<int?>("transition_zone_radius") ?? 10,
                    MaxDangerEnabled = dz.Value<bool?>("max_danger_enabled") ?? true,
                    SafeZoneDistribution = ParseDangerDistribution(
                        dz["safe_zone_distribution"] as JObject,
                        new DangerDistribution(1.0f, 0.0f, 0.0f)),
                    TransitionZoneDistribution = ParseDangerDistribution(
                        dz["transition_zone_distribution"] as JObject,
                        new DangerDistribution(0.4f, 0.5f, 0.1f)),
                    OuterZoneDistribution = ParseDangerDistribution(
                        dz["outer_zone_distribution"] as JObject,
                        new DangerDistribution(0.2f, 0.5f, 0.3f))
                };
            }

            // Spawn area
            if (data["spawn_area"] is JObject sa)
            {
                var stationArea = sa["crafting_station_area"] as JObject;
                SpawnArea = new SpawnAreaConfig
                {
                    ResourceExclusionRadius = sa.Value<int?>("resource_exclusion_radius") ?? 8,
                    CraftingStationsEnabled = stationArea?.Value<bool?>("enabled") ?? true
                };
            }

            // Resource spawning
            if (data["resource_spawning"] is JObject rs)
            {
                ResourceSpawning = new ResourceSpawningConfig
                {
                    PeacefulChunks = ParseResourceSpawn(
                        rs["peaceful_chunks"] as JObject,
                        new ResourceSpawnConfig(3, 6, 1, 2)),
                    DangerousChunks = ParseResourceSpawn(
                        rs["dangerous_chunks"] as JObject,
                        new ResourceSpawnConfig(5, 8, 2, 3)),
                    RareChunks = ParseResourceSpawn(
                        rs["rare_chunks"] as JObject,
                        new ResourceSpawnConfig(6, 10, 3, 4))
                };
            }

            // Water chunks
            if (data["water_chunks"] is JObject wc)
            {
                var fishing = wc["fishing_spots"] as JObject;
                var subtypes = wc["water_subtypes"] as JObject;

                float lakeChance = subtypes?.Value<float?>("lake_chance") ?? 0.45f;
                float riverChance = subtypes?.Value<float?>("river_chance") ?? 0.45f;
                float cursedChance = subtypes?.Value<float?>("cursed_swamp_chance") ?? 0.10f;

                // Dilutive normalization for water subtypes
                float totalWater = lakeChance + riverChance + cursedChance;
                if (MathF.Abs(totalWater - 1.0f) > 0.001f && totalWater > 0)
                {
                    lakeChance /= totalWater;
                    riverChance /= totalWater;
                    cursedChance /= totalWater;
                }

                WaterChunks = new WaterChunksConfig
                {
                    NormalWater = ParseFishingSpots(
                        fishing?["normal_water"] as JObject,
                        new FishingSpotConfig(3, 6, 1, 2)),
                    CursedSwamp = ParseFishingSpots(
                        fishing?["cursed_swamp"] as JObject,
                        new FishingSpotConfig(5, 8, 3, 4)),
                    LakeChance = lakeChance,
                    RiverChance = riverChance,
                    CursedSwampChance = cursedChance
                };
            }

            // Dungeon spawning
            if (data["dungeon_spawning"] is JObject ds)
            {
                DungeonSpawning = new DungeonSpawningConfig
                {
                    Enabled = ds.Value<bool?>("enabled") ?? true,
                    SpawnChancePerChunk = ds.Value<float?>("spawn_chance_per_chunk") ?? 0.083f,
                    ExcludedInSpawnArea = ds.Value<bool?>("excluded_in_spawn_area") ?? true,
                    ExcludedInWater = ds.Value<bool?>("excluded_in_water") ?? true,
                    MinDistanceFromSpawn = ds.Value<int?>("min_distance_from_spawn") ?? 2
                };
            }

            // Chunk unloading
            if (data["chunk_unloading"] is JObject cu)
            {
                ChunkUnloading = new ChunkUnloadingConfig
                {
                    Enabled = cu.Value<bool?>("enabled") ?? true,
                    SaveModifiedChunks = cu.Value<bool?>("save_modified_chunks") ?? true,
                    TrackUnloadTime = cu.Value<bool?>("track_unload_time") ?? true
                };
            }

            // Debug
            if (data["debug"] is JObject db)
            {
                Debug = new WorldGenDebugConfig
                {
                    LogChunkGeneration = db.Value<bool?>("log_chunk_generation") ?? false,
                    LogBiomeAssignments = db.Value<bool?>("log_biome_assignments") ?? false,
                    LogDungeonSpawns = db.Value<bool?>("log_dungeon_spawns") ?? true,
                    ShowSeedOnF1 = db.Value<bool?>("show_seed_on_f1") ?? true
                };
            }
        }

        /// <summary>
        /// Parse danger distribution with dilutive normalization.
        /// If values don't sum to 1.0, they are divided by their total.
        /// </summary>
        private static DangerDistribution ParseDangerDistribution(JObject data, DangerDistribution defaultVal)
        {
            if (data == null) return defaultVal;

            float peaceful = data.Value<float?>("peaceful") ?? defaultVal.Peaceful;
            float dangerous = data.Value<float?>("dangerous") ?? defaultVal.Dangerous;
            float rare = data.Value<float?>("rare") ?? defaultVal.Rare;

            float total = peaceful + dangerous + rare;
            if (MathF.Abs(total - 1.0f) > 0.001f && total > 0)
            {
                peaceful /= total;
                dangerous /= total;
                rare /= total;
            }

            return new DangerDistribution(peaceful, dangerous, rare);
        }

        private static ResourceSpawnConfig ParseResourceSpawn(JObject data, ResourceSpawnConfig defaultVal)
        {
            if (data == null) return defaultVal;

            var tierRange = data["tier_range"] as JArray;
            return new ResourceSpawnConfig
            {
                MinResources = data.Value<int?>("min_resources") ?? defaultVal.MinResources,
                MaxResources = data.Value<int?>("max_resources") ?? defaultVal.MaxResources,
                TierMin = tierRange != null && tierRange.Count > 0 ? tierRange[0].Value<int>() : defaultVal.TierMin,
                TierMax = tierRange != null && tierRange.Count > 1 ? tierRange[1].Value<int>() : defaultVal.TierMax
            };
        }

        private static FishingSpotConfig ParseFishingSpots(JObject data, FishingSpotConfig defaultVal)
        {
            if (data == null) return defaultVal;

            var tierRange = data["tier_range"] as JArray;
            return new FishingSpotConfig
            {
                MinSpots = data.Value<int?>("min_spots") ?? defaultVal.MinSpots,
                MaxSpots = data.Value<int?>("max_spots") ?? defaultVal.MaxSpots,
                TierMin = tierRange != null && tierRange.Count > 0 ? tierRange[0].Value<int>() : defaultVal.TierMin,
                TierMax = tierRange != null && tierRange.Count > 1 ? tierRange[1].Value<int>() : defaultVal.TierMax
            };
        }

        /// <summary>
        /// Get danger distribution for a chunk at given distance from spawn.
        /// </summary>
        public DangerDistribution GetDangerDistribution(int chunkDistance)
        {
            if (chunkDistance <= DangerZones.SafeZoneRadius)
                return DangerZones.SafeZoneDistribution;
            else if (chunkDistance <= DangerZones.TransitionZoneRadius)
                return DangerZones.TransitionZoneDistribution;
            else
                return DangerZones.OuterZoneDistribution;
        }

        /// <summary>
        /// Get resource spawn config for a danger level.
        /// </summary>
        public ResourceSpawnConfig GetResourceConfig(string dangerLevel)
        {
            return dangerLevel switch
            {
                "peaceful" => ResourceSpawning.PeacefulChunks,
                "dangerous" => ResourceSpawning.DangerousChunks,
                _ => ResourceSpawning.RareChunks
            };
        }

        public Dictionary<string, object> GetSummary()
        {
            return new Dictionary<string, object>
            {
                { "loaded_from_file", LoadedFromFile },
                { "chunk_load_radius", ChunkLoading.LoadRadius },
                { "biome_water", BiomeDistribution.Water },
                { "biome_forest", BiomeDistribution.Forest },
                { "biome_cave", BiomeDistribution.Cave },
                { "safe_zone_radius", DangerZones.SafeZoneRadius },
                { "transition_zone_radius", DangerZones.TransitionZoneRadius },
                { "dungeon_spawn_chance", DungeonSpawning.SpawnChancePerChunk }
            };
        }

        internal static void ResetInstance()
        {
            _instance = null;
            _loaded = false;
        }
    }
}
