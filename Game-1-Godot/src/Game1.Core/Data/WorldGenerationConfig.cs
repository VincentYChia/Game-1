using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/world_generation_db.py — typed world-generation
/// settings from Definitions.JSON/world_generation.JSON with the same code
/// defaults and the same DILUTIVE normalization (biome distribution, danger
/// distributions, water subtype chances renormalize proportionally when
/// they don't sum to 1.0).
/// </summary>
public sealed record ChunkLoadingConfig(double LoadRadius = 4,
    double SpawnAlwaysLoadedRadius = 1, double ChunkSize = 16);

public sealed record BiomeDistributionConfig(double Water = 0.10,
    double Forest = 0.50, double Cave = 0.40);

public sealed record BiomeClusteringConfig(double BiomeNoiseScale = 4.0,
    double BiomeNoiseOctaves = 3, double DangerNoiseScale = 6.0);

public sealed record DangerDistribution(double Peaceful = 0.5,
    double Dangerous = 0.4, double Rare = 0.1);

public sealed record DangerZonesConfig(
    double SafeZoneRadius, double TransitionZoneRadius, bool MaxDangerEnabled,
    DangerDistribution SafeZone, DangerDistribution TransitionZone,
    DangerDistribution OuterZone);

public sealed record ResourceSpawnConfig(double MinResources,
    double MaxResources, double TierMin, double TierMax);

public sealed record FishingSpotConfig(double MinSpots,
    double MaxSpots, double TierMin, double TierMax);

public sealed record DungeonSpawningConfig(bool Enabled = true,
    double SpawnChancePerChunk = 0.083, bool ExcludedInSpawnArea = true,
    bool ExcludedInWater = true, double MinDistanceFromSpawn = 2);

public sealed class WorldGenerationConfig
{
    public ChunkLoadingConfig ChunkLoading { get; private set; } = new();
    public BiomeDistributionConfig BiomeDistribution { get; private set; } = new();
    public BiomeClusteringConfig BiomeClustering { get; private set; } = new();
    public DangerZonesConfig DangerZones { get; private set; } = new(
        2, 10, true, new DangerDistribution(1.0, 0.0, 0.0),
        new DangerDistribution(0.4, 0.5, 0.1), new DangerDistribution(0.2, 0.5, 0.3));
    public double SpawnResourceExclusionRadius { get; private set; } = 8;
    public bool SpawnCraftingStationsEnabled { get; private set; } = true;
    public ResourceSpawnConfig PeacefulChunks { get; private set; } = new(3, 6, 1, 2);
    public ResourceSpawnConfig DangerousChunks { get; private set; } = new(5, 8, 2, 3);
    public ResourceSpawnConfig RareChunks { get; private set; } = new(6, 10, 3, 4);
    public FishingSpotConfig NormalWater { get; private set; } = new(3, 6, 1, 2);
    public FishingSpotConfig CursedSwamp { get; private set; } = new(5, 8, 3, 4);
    public double LakeChance { get; private set; } = 0.45;
    public double RiverChance { get; private set; } = 0.45;
    public double CursedSwampChance { get; private set; } = 0.10;
    public DungeonSpawningConfig DungeonSpawning { get; private set; } = new();
    public bool UnloadingEnabled { get; private set; } = true;
    public bool SaveModifiedChunks { get; private set; } = true;
    public bool TrackUnloadTime { get; private set; } = true;
    public bool LogChunkGeneration { get; private set; }
    public bool LogBiomeAssignments { get; private set; }
    public bool LogDungeonSpawns { get; private set; } = true;
    public bool ShowSeedOnF1 { get; private set; } = true;
    public bool LoadedFromFile { get; private set; }

    public void Load(string contentRoot)
    {
        var path = Path.Combine(contentRoot, "Definitions.JSON", "world_generation.JSON");
        if (!File.Exists(path)) return;
        JsonObject data;
        try
        {
            data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
        }
        catch
        {
            return;  // world_generation_db.py:201-206 — defaults on any error
        }
        Parse(data);
        LoadedFromFile = true;
    }

    private static JsonObject Section(JsonObject data, string key) =>
        data.TryGetPropertyValue(key, out var n) && n is JsonObject o ? o : new JsonObject();

    private void Parse(JsonObject data)
    {
        if (data.ContainsKey("chunk_loading"))
        {
            var cl = Section(data, "chunk_loading");
            ChunkLoading = new ChunkLoadingConfig(
                J.Num(cl, "load_radius", 4),
                J.Num(cl, "spawn_always_loaded_radius", 1),
                J.Num(cl, "chunk_size", 16));
        }

        if (data.ContainsKey("biome_distribution"))
        {
            var bd = Section(data, "biome_distribution");
            var water = J.Num(bd, "water", 0.10);
            var forest = J.Num(bd, "forest", 0.50);
            var cave = J.Num(bd, "cave", 0.40);
            var total = water + forest + cave;
            if (Math.Abs(total - 1.0) >= 0.001)
            {
                water /= total; forest /= total; cave /= total;
            }
            BiomeDistribution = new BiomeDistributionConfig(water, forest, cave);
        }

        if (data.ContainsKey("biome_clustering"))
        {
            var bc = Section(data, "biome_clustering");
            BiomeClustering = new BiomeClusteringConfig(
                J.Num(bc, "biome_noise_scale", 4.0),
                J.Num(bc, "biome_noise_octaves", 3),
                J.Num(bc, "danger_noise_scale", 6.0));
        }

        if (data.ContainsKey("danger_zones"))
        {
            var dz = Section(data, "danger_zones");
            DangerZones = new DangerZonesConfig(
                J.Num(dz, "safe_zone_radius", 2),
                J.Num(dz, "transition_zone_radius", 10),
                J.Bool(dz, "max_danger_enabled", true),
                ParseDangerDistribution(Section(dz, "safe_zone_distribution"),
                    new DangerDistribution(1.0, 0.0, 0.0)),
                ParseDangerDistribution(Section(dz, "transition_zone_distribution"),
                    new DangerDistribution(0.4, 0.5, 0.1)),
                ParseDangerDistribution(Section(dz, "outer_zone_distribution"),
                    new DangerDistribution(0.2, 0.5, 0.3)));
        }

        if (data.ContainsKey("spawn_area"))
        {
            var sa = Section(data, "spawn_area");
            SpawnResourceExclusionRadius = J.Num(sa, "resource_exclusion_radius", 8);
            SpawnCraftingStationsEnabled =
                J.Bool(Section(sa, "crafting_station_area"), "enabled", true);
        }

        if (data.ContainsKey("resource_spawning"))
        {
            var rs = Section(data, "resource_spawning");
            PeacefulChunks = ParseResourceSpawn(Section(rs, "peaceful_chunks"),
                new ResourceSpawnConfig(3, 6, 1, 2));
            DangerousChunks = ParseResourceSpawn(Section(rs, "dangerous_chunks"),
                new ResourceSpawnConfig(5, 8, 2, 3));
            RareChunks = ParseResourceSpawn(Section(rs, "rare_chunks"),
                new ResourceSpawnConfig(6, 10, 3, 4));
        }

        if (data.ContainsKey("water_chunks"))
        {
            var wc = Section(data, "water_chunks");
            var fishing = Section(wc, "fishing_spots");
            var subtypes = Section(wc, "water_subtypes");

            var lake = J.Num(subtypes, "lake_chance", 0.45);
            var river = J.Num(subtypes, "river_chance", 0.45);
            var swamp = J.Num(subtypes, "cursed_swamp_chance", 0.10);
            var total = lake + river + swamp;
            if (Math.Abs(total - 1.0) > 0.001 && total > 0)
            {
                lake /= total; river /= total; swamp /= total;
            }
            NormalWater = ParseFishingSpots(Section(fishing, "normal_water"),
                new FishingSpotConfig(3, 6, 1, 2));
            CursedSwamp = ParseFishingSpots(Section(fishing, "cursed_swamp"),
                new FishingSpotConfig(5, 8, 3, 4));
            LakeChance = lake; RiverChance = river; CursedSwampChance = swamp;
        }

        if (data.ContainsKey("dungeon_spawning"))
        {
            var ds = Section(data, "dungeon_spawning");
            DungeonSpawning = new DungeonSpawningConfig(
                J.Bool(ds, "enabled", true),
                J.Num(ds, "spawn_chance_per_chunk", 0.083),
                J.Bool(ds, "excluded_in_spawn_area", true),
                J.Bool(ds, "excluded_in_water", true),
                J.Num(ds, "min_distance_from_spawn", 2));
        }

        if (data.ContainsKey("chunk_unloading"))
        {
            var cu = Section(data, "chunk_unloading");
            UnloadingEnabled = J.Bool(cu, "enabled", true);
            SaveModifiedChunks = J.Bool(cu, "save_modified_chunks", true);
            TrackUnloadTime = J.Bool(cu, "track_unload_time", true);
        }

        if (data.ContainsKey("debug"))
        {
            var db = Section(data, "debug");
            LogChunkGeneration = J.Bool(db, "log_chunk_generation", false);
            LogBiomeAssignments = J.Bool(db, "log_biome_assignments", false);
            LogDungeonSpawns = J.Bool(db, "log_dungeon_spawns", true);
            ShowSeedOnF1 = J.Bool(db, "show_seed_on_f1", true);
        }
    }

    // world_generation_db.py:344-368
    private static DangerDistribution ParseDangerDistribution(
        JsonObject data, DangerDistribution def)
    {
        if (data.Count == 0) return def;
        var peaceful = J.Num(data, "peaceful", def.Peaceful);
        var dangerous = J.Num(data, "dangerous", def.Dangerous);
        var rare = J.Num(data, "rare", def.Rare);
        var total = peaceful + dangerous + rare;
        if (Math.Abs(total - 1.0) > 0.001 && total > 0)
        {
            peaceful /= total; dangerous /= total; rare /= total;
        }
        return new DangerDistribution(peaceful, dangerous, rare);
    }

    private static ResourceSpawnConfig ParseResourceSpawn(
        JsonObject data, ResourceSpawnConfig def)
    {
        if (data.Count == 0) return def;
        var tierRange = data.TryGetPropertyValue("tier_range", out var tr) && tr is JsonArray a
                        && a.Count >= 2
            ? (a[0]!.GetValue<double>(), a[1]!.GetValue<double>())
            : (def.TierMin, def.TierMax);
        return new ResourceSpawnConfig(
            J.Num(data, "min_resources", def.MinResources),
            J.Num(data, "max_resources", def.MaxResources),
            tierRange.Item1, tierRange.Item2);
    }

    private static FishingSpotConfig ParseFishingSpots(
        JsonObject data, FishingSpotConfig def)
    {
        if (data.Count == 0) return def;
        var tierRange = data.TryGetPropertyValue("tier_range", out var tr) && tr is JsonArray a
                        && a.Count >= 2
            ? (a[0]!.GetValue<double>(), a[1]!.GetValue<double>())
            : (def.TierMin, def.TierMax);
        return new FishingSpotConfig(
            J.Num(data, "min_spots", def.MinSpots),
            J.Num(data, "max_spots", def.MaxSpots),
            tierRange.Item1, tierRange.Item2);
    }

    // world_generation_db.py:392-406 — Chebyshev distance zone lookup
    public DangerDistribution GetDangerDistribution(double chunkDistance)
    {
        if (chunkDistance <= DangerZones.SafeZoneRadius)
            return DangerZones.SafeZone;
        if (chunkDistance <= DangerZones.TransitionZoneRadius)
            return DangerZones.TransitionZone;
        return DangerZones.OuterZone;
    }

    // :408-422 — anything not peaceful/dangerous falls to rare
    public ResourceSpawnConfig GetResourceConfig(string dangerLevel) => dangerLevel switch
    {
        "peaceful" => PeacefulChunks,
        "dangerous" => DangerousChunks,
        _ => RareChunks,
    };
}
