using System.Text.Json.Nodes;
using Game1.Core.Data;

namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/config.py — all defaults identical; JSON
/// overrides from geography-config.json searched at the same two locations
/// (world_system/config, then Definitions.JSON). Neither exists at repo
/// state, so live behavior is pure defaults.
/// </summary>
public sealed class WorldConfig
{
    public int WorldSize = 512;
    public int ChunkSize = 16;
    public int SpawnX;
    public int SpawnY;
}

public sealed class NationConfig
{
    public int Count = 5;
    public int MinArea = 30000;
    public int MinCorridorWidth = 12;
    public double DeformAmplitude = 24.0;
    public double DeformFrequency = 0.02;
    public int DeformOctaves = 4;
    public double DeformScaleVariance = 0.12;
}

public sealed class RegionConfig
{
    public int MinPerNation = 3;
    public int MaxPerNation = 8;
    public double MinAreaPct = 0.10;
    public double MaxAreaPct = 0.45;
    public double DeformAmplitude = 8.0;
    public double DeformFrequency = 0.04;
}

public sealed class ProvinceConfig
{
    public int MinArea = 600;
    public int MaxArea = 2400;
    public double DeformAmplitude = 4.0;
    public double DeformFrequency = 0.06;
}

public sealed class DistrictConfig
{
    public int MinArea = 200;
    public int MaxArea = 800;
    public double DeformAmplitude = 2.0;
    public double DeformFrequency = 0.08;
}

public sealed class BiomeConfig
{
    public int MinArea = 400;
    public int MaxArea = 800;
    public double PrimaryWeight = 0.70;
    public double SecondaryWeight = 0.30;
}

public sealed class EcosystemConfig
{
    public int GroupSize = 3;
    public int GradientMax = 2;   // present but IGNORED by the generator (models constant used)
    public Dictionary<int, double> BaseDangerWeights = new()
    { [1] = 0.15, [2] = 0.25, [3] = 0.25, [4] = 0.20, [5] = 0.10, [6] = 0.05 };
    public int SpawnSafeRadius = 2;
}

public sealed class DungeonConfig
{
    public double SpawnChance = 0.015;
    public int MinDistanceFromSpawn = 8;
    public bool ExcludedInWater = true;
}

public sealed class GeographicConfig
{
    public WorldConfig World = new();
    public NationConfig Nation = new();
    public RegionConfig Region = new();
    public ProvinceConfig Province = new();
    public DistrictConfig District = new();
    public BiomeConfig Biome = new();
    public EcosystemConfig Ecosystem = new();
    public DungeonConfig Dungeon = new();

    /// <summary>config.py load — same search paths relative to the content
    /// root; missing/broken file → defaults. Only fields present in the JSON
    /// are overridden (hasattr-guarded setattr in Python).</summary>
    public static GeographicConfig Load(string contentRoot, string? configPath = null)
    {
        var cfg = new GeographicConfig();
        var searchPaths = new List<string>();
        if (configPath is not null)
            searchPaths.Add(configPath);
        searchPaths.Add(Path.Combine(contentRoot, "world_system", "config", "geography-config.json"));
        searchPaths.Add(Path.Combine(contentRoot, "Definitions.JSON", "geography-config.json"));

        JsonObject? data = null;
        foreach (var path in searchPaths)
        {
            if (!File.Exists(path)) continue;
            try
            {
                data = JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
                break;
            }
            catch
            {
                // json.JSONDecodeError/IOError → try next path
            }
        }
        if (data is null) return cfg;

        void OverInt(JsonObject? s, string key, Action<int> set)
        { if (s?[key] is { } v && J.AsNum(v) is { } n) set((int)n); }
        void OverDouble(JsonObject? s, string key, Action<double> set)
        { if (s?[key] is { } v && J.AsNum(v) is { } n) set(n); }
        void OverBool(JsonObject? s, string key, Action<bool> set)
        { if (s?[key] is JsonValue v && v.TryGetValue<bool>(out var b)) set(b); }

        var world = data["world"] as JsonObject;
        OverInt(world, "world_size", v => cfg.World.WorldSize = v);
        OverInt(world, "chunk_size", v => cfg.World.ChunkSize = v);
        OverInt(world, "spawn_x", v => cfg.World.SpawnX = v);
        OverInt(world, "spawn_y", v => cfg.World.SpawnY = v);

        var nation = data["nation"] as JsonObject;
        OverInt(nation, "count", v => cfg.Nation.Count = v);
        OverInt(nation, "min_area", v => cfg.Nation.MinArea = v);
        OverInt(nation, "min_corridor_width", v => cfg.Nation.MinCorridorWidth = v);
        OverDouble(nation, "deform_amplitude", v => cfg.Nation.DeformAmplitude = v);
        OverDouble(nation, "deform_frequency", v => cfg.Nation.DeformFrequency = v);
        OverInt(nation, "deform_octaves", v => cfg.Nation.DeformOctaves = v);
        OverDouble(nation, "deform_scale_variance", v => cfg.Nation.DeformScaleVariance = v);

        var region = data["region"] as JsonObject;
        OverInt(region, "min_per_nation", v => cfg.Region.MinPerNation = v);
        OverInt(region, "max_per_nation", v => cfg.Region.MaxPerNation = v);
        OverDouble(region, "min_area_pct", v => cfg.Region.MinAreaPct = v);
        OverDouble(region, "max_area_pct", v => cfg.Region.MaxAreaPct = v);
        OverDouble(region, "deform_amplitude", v => cfg.Region.DeformAmplitude = v);
        OverDouble(region, "deform_frequency", v => cfg.Region.DeformFrequency = v);

        var province = data["province"] as JsonObject;
        OverInt(province, "min_area", v => cfg.Province.MinArea = v);
        OverInt(province, "max_area", v => cfg.Province.MaxArea = v);
        OverDouble(province, "deform_amplitude", v => cfg.Province.DeformAmplitude = v);
        OverDouble(province, "deform_frequency", v => cfg.Province.DeformFrequency = v);

        var district = data["district"] as JsonObject;
        OverInt(district, "min_area", v => cfg.District.MinArea = v);
        OverInt(district, "max_area", v => cfg.District.MaxArea = v);
        OverDouble(district, "deform_amplitude", v => cfg.District.DeformAmplitude = v);
        OverDouble(district, "deform_frequency", v => cfg.District.DeformFrequency = v);

        var biome = data["biome"] as JsonObject;
        OverInt(biome, "min_area", v => cfg.Biome.MinArea = v);
        OverInt(biome, "max_area", v => cfg.Biome.MaxArea = v);
        OverDouble(biome, "primary_weight", v => cfg.Biome.PrimaryWeight = v);
        OverDouble(biome, "secondary_weight", v => cfg.Biome.SecondaryWeight = v);

        var ecosystem = data["ecosystem"] as JsonObject;
        OverInt(ecosystem, "group_size", v => cfg.Ecosystem.GroupSize = v);
        OverInt(ecosystem, "gradient_max", v => cfg.Ecosystem.GradientMax = v);
        OverInt(ecosystem, "spawn_safe_radius", v => cfg.Ecosystem.SpawnSafeRadius = v);
        if (ecosystem?["base_danger_weights"] is JsonObject weights)
        {
            var parsed = new Dictionary<int, double>();
            foreach (var kv in weights)
                if (int.TryParse(kv.Key, out var k) && J.AsNum(kv.Value) is { } w)
                    parsed[k] = w;
            if (parsed.Count > 0) cfg.Ecosystem.BaseDangerWeights = parsed;
        }

        var dungeon = data["dungeon"] as JsonObject;
        OverDouble(dungeon, "spawn_chance", v => cfg.Dungeon.SpawnChance = v);
        OverInt(dungeon, "min_distance_from_spawn", v => cfg.Dungeon.MinDistanceFromSpawn = v);
        OverBool(dungeon, "excluded_in_water", v => cfg.Dungeon.ExcludedInWater = v);

        return cfg;
    }
}
