namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/models.py — enums (as the strings Python's
/// str-Enums are), the region→chunk-type tables, danger tables, tier
/// metadata, GeographicData, and WorldMap. Python str-Enum members behave
/// as plain strings everywhere downstream (JSON keys, geo dispatch), so
/// chunk types and identities stay strings here.
/// </summary>
public static class NewChunkTypes
{
    public const string Forest = "forest";
    public const string DenseThicket = "dense_thicket";
    public const string Cave = "cave";
    public const string DeepCave = "deep_cave";
    public const string Quarry = "quarry";
    public const string RockyHighlands = "rocky_highlands";
    public const string Wetland = "wetland";
    public const string Lake = "lake";
    public const string River = "river";
    public const string FloodedCave = "flooded_cave";
    public const string RockyForest = "rocky_forest";
    public const string CrystalCavern = "crystal_cavern";
    public const string OvergrownRuins = "overgrown_ruins";
    public const string BarrenWaste = "barren_waste";
    public const string CursedMarsh = "cursed_marsh";
}

public enum DangerLevel
{
    Tranquil = 1,
    Peaceful = 2,
    Moderate = 3,
    Dangerous = 4,
    Perilous = 5,
    Lethal = 6,
}

public static class GeoTables
{
    public const double RegionPrimaryWeight = 0.70;
    public const double RegionSecondaryWeight = 0.30;
    public const int DangerGradientMax = 2;

    /// <summary>models.py RegionIdentity member order (declaration order —
    /// list(RegionIdentity) iterates in this order).</summary>
    public static readonly string[] RegionIdentities =
    {
        "forest", "mountains", "plains", "steppe", "lowlands",
        "marshlands", "caverns", "highlands", "lakeland", "ruins",
    };

    /// <summary>models.py NamingFlavor member order.</summary>
    public static readonly string[] NamingFlavors =
        { "stoic", "flowing", "imperial", "stoneworn", "ethereal" };

    public static readonly Dictionary<string, string[]> RegionPrimaryChunks = new()
    {
        ["forest"] = new[] { "forest", "dense_thicket" },
        ["mountains"] = new[] { "rocky_highlands", "quarry", "cave" },
        ["plains"] = new[] { "forest", "quarry" },
        ["steppe"] = new[] { "barren_waste", "quarry" },
        ["lowlands"] = new[] { "forest", "river" },
        ["marshlands"] = new[] { "wetland", "cursed_marsh" },
        ["caverns"] = new[] { "cave", "deep_cave", "crystal_cavern" },
        ["highlands"] = new[] { "rocky_highlands", "rocky_forest" },
        ["lakeland"] = new[] { "lake", "river" },
        ["ruins"] = new[] { "overgrown_ruins", "crystal_cavern" },
    };

    public static readonly Dictionary<string, string[]> RegionSecondaryChunks = new()
    {
        ["forest"] = new[] { "rocky_forest", "wetland" },
        ["mountains"] = new[] { "deep_cave", "barren_waste" },
        ["plains"] = new[] { "rocky_highlands", "wetland" },
        ["steppe"] = new[] { "rocky_highlands", "overgrown_ruins" },
        ["lowlands"] = new[] { "wetland", "lake", "rocky_forest" },
        ["marshlands"] = new[] { "flooded_cave", "lake" },
        ["caverns"] = new[] { "flooded_cave" },
        ["highlands"] = new[] { "quarry", "forest" },
        ["lakeland"] = new[] { "wetland", "forest" },
        ["ruins"] = new[] { "deep_cave", "dense_thicket" },
    };

    public static readonly Dictionary<DangerLevel, Dictionary<int, double>> DangerTierWeights = new()
    {
        [DangerLevel.Tranquil] = new() { [1] = 1.00, [2] = 0.00, [3] = 0.00, [4] = 0.00 },
        [DangerLevel.Peaceful] = new() { [1] = 0.80, [2] = 0.15, [3] = 0.05, [4] = 0.00 },
        [DangerLevel.Moderate] = new() { [1] = 0.60, [2] = 0.30, [3] = 0.10, [4] = 0.00 },
        [DangerLevel.Dangerous] = new() { [1] = 0.25, [2] = 0.35, [3] = 0.30, [4] = 0.10 },
        [DangerLevel.Perilous] = new() { [1] = 0.15, [2] = 0.20, [3] = 0.45, [4] = 0.20 },
        [DangerLevel.Lethal] = new() { [1] = 0.00, [2] = 0.15, [3] = 0.45, [4] = 0.40 },
    };

    public static readonly Dictionary<DangerLevel, string> DangerSpawnDensity = new()
    {
        [DangerLevel.Tranquil] = "very_sparse",
        [DangerLevel.Peaceful] = "sparse",
        [DangerLevel.Moderate] = "normal",
        [DangerLevel.Dangerous] = "dense",
        [DangerLevel.Perilous] = "dense",
        [DangerLevel.Lethal] = "very_dense",
    };

    /// <summary>DangerLevel.display_name — Python str.capitalize().</summary>
    public static string DisplayName(this DangerLevel d) => d switch
    {
        DangerLevel.Tranquil => "Tranquil",
        DangerLevel.Peaceful => "Peaceful",
        DangerLevel.Moderate => "Moderate",
        DangerLevel.Dangerous => "Dangerous",
        DangerLevel.Perilous => "Perilous",
        _ => "Lethal",
    };
}

public sealed class GeographicData
{
    public int NationId = -1;
    public int RegionId = -1;
    public int ProvinceId = -1;
    public int DistrictId = -1;
    public string ChunkType = NewChunkTypes.Forest;
    public int BiomeId = -1;
    public int EcosystemId = -1;
    public DangerLevel DangerLevel = DangerLevel.Moderate;
    public int LocalityId = -1;
}

public sealed class NationData
{
    public int NationId;
    public string Name = "";
    public string NamingFlavor = "stoic";
    public int ChunkCount;
    public List<int> RegionIds = new();
    public (int R, int G, int B) Color = (128, 128, 128);
}

public sealed class RegionData
{
    public int RegionId;
    public string Name = "";
    public int NationId;
    public string Identity = "forest";
    public int ChunkCount;
    public List<int> ProvinceIds = new();
    public (int MinX, int MinY, int MaxX, int MaxY) Bounds;
}

public sealed class ProvinceData
{
    public int ProvinceId;
    public string Name = "";
    public int RegionId;
    public int NationId;
    public int ChunkCount;
    public List<int> DistrictIds = new();
    public (int MinX, int MinY, int MaxX, int MaxY) Bounds;
}

public sealed class DistrictData
{
    public int DistrictId;
    public string Name = "";
    public int ProvinceId;
    public int RegionId;
    public int NationId;
    public int ChunkCount;
    public (int MinX, int MinY, int MaxX, int MaxY) Bounds;
}

public sealed class BiomeData
{
    public int BiomeId;
    public string DominantChunkType = NewChunkTypes.Forest;
    public string RegionIdentity = "forest";
    public int ChunkCount;
    public (int MinX, int MinY, int MaxX, int MaxY) Bounds;
}

public sealed class EcosystemData
{
    public int EcosystemId;
    public DangerLevel DangerLevel;
    public int EcoX;
    public int EcoY;
}

public sealed class LocalityData
{
    public int LocalityId;
    public string Name = "";
    public int ChunkX;
    public int ChunkY;
    public string FeatureType = "";
    public List<(int X, int Y)> AdjacentChunks = new();
}

public sealed class WorldMap
{
    public long Seed;
    public int WorldSize = 512;

    public Dictionary<(int X, int Y), GeographicData> ChunkData = new();

    /// <summary>Insertion order of ChunkData (Python dict order: Phase-8
    /// assembly is y-outer/x-inner row-major). Load-bearing for village
    /// candidate scanning.</summary>
    public List<(int X, int Y)> ChunkOrder = new();

    /// <summary>Insertion order of Nations (locality naming uses the
    /// FIRST-INSERTED nation — Python dict-order quirk).</summary>
    public List<int> NationOrder = new();

    public Dictionary<int, NationData> Nations = new();
    public Dictionary<int, RegionData> Regions = new();
    public Dictionary<int, ProvinceData> Provinces = new();
    public Dictionary<int, DistrictData> Districts = new();
    public Dictionary<int, BiomeData> Biomes = new();
    public Dictionary<int, EcosystemData> Ecosystems = new();
    public Dictionary<int, LocalityData> Localities = new();

    public int MinChunk => -(WorldSize / 2);
    public int MaxChunk => WorldSize / 2;

    public bool InBounds(int chunkX, int chunkY) =>
        MinChunk <= chunkX && chunkX < MaxChunk
        && MinChunk <= chunkY && chunkY < MaxChunk;

    public GeographicData? GetChunkData(int chunkX, int chunkY) =>
        !InBounds(chunkX, chunkY) ? null
        : ChunkData.GetValueOrDefault((chunkX, chunkY));
}
