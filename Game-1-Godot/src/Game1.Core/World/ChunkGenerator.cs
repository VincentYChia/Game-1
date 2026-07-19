using Game1.Core.Combat;
using Game1.Core.Data;

namespace Game1.Core.World;

/// <summary>
/// Port of systems/chunk.py Chunk generation — per-chunk seeded RNG drives
/// chunk-type determination (legacy path), tile grids (land/lake/river/
/// swamp), and resource spawning (template resourceDensity pathway →
/// substring-matched database fallback → fishing spots on water).
///
/// The Python hardcoded `_spawn_resources_fallback` (db-not-loaded rescue)
/// is NOT ported: every live boot loads ResourceNodeDatabase, and the
/// substring path's default-to-ores means candidates are never empty with
/// shipped content. Generation throws instead of silently diverging.
/// </summary>
public sealed record ChunkTile(long X, long Y, string TileType, bool Walkable);

public sealed record ChunkResource(long X, long Y, string ResourceType, long Tier);

public sealed class GeneratedChunk
{
    public long ChunkX;
    public long ChunkY;
    public long Seed;
    public string ChunkType = "";
    public List<ChunkTile> Tiles = new();
    public List<ChunkResource> Resources = new();
}

public sealed class ChunkGenerator
{
    public const int ChunkSize = 16;   // core/config.py Config.CHUNK_SIZE

    private readonly ResourceNodeDatabase _resourceDb;
    private readonly WorldGenerationConfig _worldConfig;
    private readonly ChunkTemplateDatabase _templateDb;

    public ChunkGenerator(ResourceNodeDatabase resourceDb,
                          WorldGenerationConfig worldConfig,
                          ChunkTemplateDatabase templateDb)
    {
        _resourceDb = resourceDb;
        _worldConfig = worldConfig;
        _templateDb = templateDb;
    }

    private static readonly string[] WaterChunkTypes =
        { "water_lake", "water_river", "water_cursed_swamp", "wetland" };

    private static readonly string[] PeacefulTypes =
        { "peaceful_forest", "peaceful_quarry", "peaceful_cave" };

    private static readonly string[] DangerousTypes =
        { "dangerous_forest", "dangerous_quarry", "dangerous_cave" };

    private static readonly string[] RareTypes =
        { "rare_hidden_forest", "rare_ancient_quarry", "rare_deep_cave" };

    private static readonly Dictionary<long, string[]> FishingSpotByTier = new()
    {
        [1] = new[] { "fishing_spot_carp", "fishing_spot_sunfish", "fishing_spot_minnow" },
        [2] = new[]
        {
            "fishing_spot_stormfin", "fishing_spot_frostback",
            "fishing_spot_lighteye", "fishing_spot_shadowgill",
        },
        [3] = new[]
        {
            "fishing_spot_phoenixkoi", "fishing_spot_voidswimmer",
            "fishing_spot_tempesteel",
        },
        [4] = new[] { "fishing_spot_leviathan", "fishing_spot_chaosscale" },
    };

    public GeneratedChunk Generate(int chunkX, int chunkY,
                                   long? seed = null,
                                   BiomeGenerator? biomeGenerator = null,
                                   string? geoChunkType = null,
                                   long? geoDangerLevel = null,
                                   string? lockedChunkType = null)
    {
        var chunk = new GeneratedChunk { ChunkX = chunkX, ChunkY = chunkY };

        if (biomeGenerator is not null)
            chunk.Seed = biomeGenerator.GetChunkSeed(chunkX, chunkY);
        else if (seed is not null)
            chunk.Seed = seed.Value;
        else
            throw new ArgumentException(
                "deterministic generation needs a seed or biome generator");

        var rng = new PythonRandom(chunk.Seed);

        chunk.ChunkType = lockedChunkType
            ?? DetermineChunkType(chunkX, chunkY, rng, biomeGenerator, geoChunkType);

        GenerateTiles(chunk, rng);
        SpawnResources(chunk, rng, geoDangerLevel);
        return chunk;
    }

    private string DetermineChunkType(int chunkX, int chunkY, PythonRandom rng,
                                      BiomeGenerator? biomeGenerator,
                                      string? geoChunkType)
    {
        // Geographic system: JSON-driven geo dispatch → template
        if (geoChunkType is not null)
        {
            if (_templateDb.GeoDispatch.TryGetValue(geoChunkType, out var mapped)
                && _templateDb.Get(mapped) is { } template)
                return template.ChunkType;
            return "peaceful_forest";
        }

        if (biomeGenerator is not null)
            return biomeGenerator.GetChunkType(chunkX, chunkY);

        // Legacy random distribution (Chunk._water_chunks legacy-restore path
        // not ported — it only exists for pre-seed-era save compatibility)
        if (Math.Abs(chunkX) <= 1 && Math.Abs(chunkY) <= 1)
            return rng.Choice(PeacefulTypes);

        var roll = rng.RandInt(1, 10);
        if (roll <= 5)
            return rng.Choice(PeacefulTypes);
        if (roll <= 8)
            return rng.Choice(DangerousTypes);
        if (rng.NextDouble() < 0.25)
            return "water_cursed_swamp";
        return rng.Choice(RareTypes);
    }

    private static bool IsWaterChunk(string chunkType) =>
        WaterChunkTypes.Contains(chunkType);

    private static void GenerateTiles(GeneratedChunk chunk, PythonRandom rng)
    {
        var startX = chunk.ChunkX * ChunkSize;
        var startY = chunk.ChunkY * ChunkSize;

        if (IsWaterChunk(chunk.ChunkType))
            GenerateWaterTiles(chunk, rng, startX, startY);
        else
            GenerateLandTiles(chunk, rng, startX, startY);
    }

    private static void GenerateLandTiles(GeneratedChunk chunk, PythonRandom rng,
                                          long startX, long startY)
    {
        var isStoneBiome = chunk.ChunkType.Contains("quarry")
                           || chunk.ChunkType.Contains("cave");
        var baseTile = isStoneBiome ? "stone" : "grass";

        for (var x = startX; x < startX + ChunkSize; x++)
        {
            for (var y = startY; y < startY + ChunkSize; y++)
            {
                var tileType = rng.NextDouble() < 0.1 ? "dirt" : baseTile;
                chunk.Tiles.Add(new ChunkTile(x, y, tileType, true));
            }
        }
    }

    private static void GenerateWaterTiles(GeneratedChunk chunk, PythonRandom rng,
                                           long startX, long startY)
    {
        var isSwamp = chunk.ChunkType == "water_cursed_swamp";
        var isLake = chunk.ChunkType == "water_lake";

        const int centerX = ChunkSize / 2;
        const int centerY = ChunkSize / 2;

        for (var localX = 0; localX < ChunkSize; localX++)
        {
            for (var localY = 0; localY < ChunkSize; localY++)
            {
                var x = startX + localX;
                var y = startY + localY;
                string tileType;

                if (isLake)
                {
                    var distFromCenter = Math.Sqrt(
                        Math.Pow(localX - centerX, 2) + Math.Pow(localY - centerY, 2));
                    if (localX < 2 || localX >= ChunkSize - 2
                        || localY < 2 || localY >= ChunkSize - 2)
                        tileType = "grass";
                    else if (distFromCenter < 5)
                        tileType = "water";
                    else
                        tileType = "grass";
                }
                else if (isSwamp)
                {
                    var isPath = Math.Abs(localX - centerX) < 2
                                 || Math.Abs(localY - centerY) < 2;
                    if (isPath)
                        tileType = "dirt";
                    else if (rng.NextDouble() < 0.5)   // draw only off-path
                        tileType = "water";
                    else
                        tileType = "dirt";
                }
                else
                {
                    // River — Python short-circuit: rng draw ONLY when dist < 3
                    var distFromCenter = Math.Abs(localX - ChunkSize / 2);
                    if (distFromCenter < 3 && rng.NextDouble() < 0.8)
                        tileType = "water";
                    else
                        tileType = "grass";
                }

                chunk.Tiles.Add(new ChunkTile(x, y, tileType, tileType != "water"));
            }
        }
    }

    private void SpawnResources(GeneratedChunk chunk, PythonRandom rng,
                                long? geoDangerLevel)
    {
        if (IsWaterChunk(chunk.ChunkType))
        {
            SpawnFishingSpots(chunk, rng);
            return;
        }

        var startX = chunk.ChunkX * ChunkSize;
        var startY = chunk.ChunkY * ChunkSize;

        ResourceSpawnConfig resConfig;
        if (geoDangerLevel is { } danger)
        {
            resConfig = danger <= 2 ? _worldConfig.PeacefulChunks
                : danger <= 4 ? _worldConfig.DangerousChunks
                : _worldConfig.RareChunks;
        }
        else if (chunk.ChunkType.Contains("peaceful"))
        {
            resConfig = _worldConfig.PeacefulChunks;
        }
        else if (chunk.ChunkType.Contains("dangerous"))
        {
            resConfig = _worldConfig.DangerousChunks;
        }
        else
        {
            resConfig = _worldConfig.RareChunks;
        }

        var resourceCount = rng.RandInt((long)resConfig.MinResources,
                                        (long)resConfig.MaxResources);
        var tierRange = ((long)resConfig.TierMin, (long)resConfig.TierMax);
        var occupied = new HashSet<(long, long)>();

        var template = _templateDb.Get(chunk.ChunkType);
        if (template is not null && template.ResourceDensity.Count > 0
            && SpawnFromTemplate(chunk, rng, template, startX, startY,
                                 resourceCount, tierRange, occupied))
            return;

        if (_resourceDb.Loaded)
        {
            var candidates = GetResourcesForChunk(chunk.ChunkType, tierRange);
            if (candidates.Count > 0)
            {
                for (var i = 0; i < resourceCount; i++)
                {
                    var pos = FindResourcePosition(rng, startX, startY, occupied);
                    if (pos is null) continue;

                    var tier = Math.Min(rng.RandInt(tierRange.Item1, tierRange.Item2), 4);
                    var valid = candidates.Where(r => (long)r.Tier <= tier).ToList();
                    if (valid.Count > 0)
                    {
                        var nodeDef = rng.Choice(valid);
                        chunk.Resources.Add(new ChunkResource(
                            pos.Value.X, pos.Value.Y, nodeDef.ResourceId, (long)nodeDef.Tier));
                    }
                }
                return;
            }
        }

        throw new InvalidOperationException(
            "chunk resource spawn reached the unported hardcoded fallback — "
            + "ResourceNodeDatabase not loaded or empty candidate pool");
    }

    /// <summary>resource_node_db.py get_resources_for_chunk — substring
    /// category matching with default-to-ores, then tier-range filter.</summary>
    public List<ResourceNodeDefinition> GetResourcesForChunk(
        string chunkType, (long Min, long Max) tierRange)
    {
        var candidates = new List<ResourceNodeDefinition>();
        if (chunkType.Contains("forest")) candidates.AddRange(_resourceDb.Trees);
        if (chunkType.Contains("quarry")) candidates.AddRange(_resourceDb.Stones);
        if (chunkType.Contains("cave")) candidates.AddRange(_resourceDb.Ores);
        if (chunkType.Contains("wetland")) candidates.AddRange(_resourceDb.Trees);

        if (candidates.Count == 0)
            candidates = new List<ResourceNodeDefinition>(_resourceDb.Ores);

        return candidates
            .Where(r => tierRange.Min <= (long)r.Tier && (long)r.Tier <= tierRange.Max)
            .ToList();
    }

    private bool SpawnFromTemplate(GeneratedChunk chunk, PythonRandom rng,
                                   ChunkTemplate template, long startX, long startY,
                                   long resourceCount, (long Min, long Max) tierRange,
                                   HashSet<(long, long)> occupied)
    {
        if (!_resourceDb.Loaded) return false;

        // spawn_pool_resources(): specs ordered by resource_id; orphans skipped
        var weightedPool = new List<(ResourceNodeDefinition Node, double Weight)>();
        foreach (var key in template.ResourceDensity.Keys.OrderBy(x => x, StringComparer.Ordinal))
        {
            var spec = template.ResourceDensity[key];
            if (_resourceDb.Nodes.TryGetValue(spec.ResourceId, out var nodeDef))
                weightedPool.Add((nodeDef, spec.SpawnWeight));
        }

        if (weightedPool.Count == 0) return false;

        for (var i = 0; i < resourceCount; i++)
        {
            var pos = FindResourcePosition(rng, startX, startY, occupied);
            if (pos is null) continue;

            var tierCap = Math.Min(rng.RandInt(tierRange.Min, tierRange.Max), 4);
            var eligible = weightedPool
                .Where(p => (long)p.Node.Tier <= tierCap).ToList();
            if (eligible.Count == 0) continue;

            var nodes = eligible.Select(p => p.Node).ToList();
            var weights = eligible.Select(p => p.Weight).ToList();
            var chosen = CombatGen.WeightedChoice(nodes, weights, rng);
            chunk.Resources.Add(new ChunkResource(
                pos.Value.X, pos.Value.Y, chosen.ResourceId, (long)chosen.Tier));
        }

        return true;
    }

    private (long X, long Y)? FindResourcePosition(PythonRandom rng,
                                                   long startX, long startY,
                                                   HashSet<(long, long)> occupied)
    {
        var exclusionRadius = _worldConfig.SpawnResourceExclusionRadius;

        for (var attempt = 0; attempt < 10; attempt++)
        {
            var candidateX = startX + rng.RandInt(1, ChunkSize - 2);
            var candidateY = startY + rng.RandInt(1, ChunkSize - 2);

            var distToOrigin = Math.Sqrt(
                (double)candidateX * candidateX + (double)candidateY * candidateY);
            if (distToOrigin < exclusionRadius) continue;
            if (occupied.Contains((candidateX, candidateY))) continue;

            occupied.Add((candidateX, candidateY));
            return (candidateX, candidateY);
        }
        return null;
    }

    private void SpawnFishingSpots(GeneratedChunk chunk, PythonRandom rng)
    {
        var waterTiles = chunk.Tiles
            .Where(t => t.TileType == "water")
            .Select(t => (t.X, t.Y)).ToList();

        var isSwamp = chunk.ChunkType == "water_cursed_swamp";
        var fishingConfig = isSwamp ? _worldConfig.CursedSwamp : _worldConfig.NormalWater;

        var tierRange = ((long)fishingConfig.TierMin, (long)fishingConfig.TierMax);
        var numSpots = Math.Min(
            rng.RandInt((long)fishingConfig.MinSpots, (long)fishingConfig.MaxSpots),
            waterTiles.Count);

        if (waterTiles.Count > 0 && numSpots > 0)
        {
            var spots = rng.Sample(waterTiles, (int)numSpots);
            foreach (var (x, y) in spots)
            {
                var tier = rng.RandInt(tierRange.Item1, tierRange.Item2);
                tier = Math.Min(4, Math.Max(1, tier));

                var availableSpots = FishingSpotByTier.GetValueOrDefault(
                    tier, new[] { "fishing_spot" });
                var spotType = availableSpots.Length > 0
                    ? rng.Choice(availableSpots) : "fishing_spot";

                chunk.Resources.Add(new ChunkResource(x, y, spotType, tier));
            }
        }
    }
}
