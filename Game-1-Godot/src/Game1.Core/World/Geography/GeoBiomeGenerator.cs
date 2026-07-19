namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/biome_generator.py — per-chunk types from
/// region identity (pure noise functions) + coarse 16-cell biome zones with
/// first-encounter IDs. Preserves the quirky negative floor-division cell
/// bucketing verbatim (cell -1 is a width-1 column).
/// </summary>
public static class GeoBiomeGenerator
{
    /// <summary>Python floor division (rounds toward negative infinity).</summary>
    public static int FloorDiv(int a, int b)
    {
        var q = a / b;
        if (a % b != 0 && (a < 0) != (b < 0)) q--;
        return q;
    }

    // _assign_chunk_type — pure function of (cx, cy, identity, seed)
    public static string AssignChunkType(int cx, int cy, string identity,
                                         long seed, double primaryWeight)
    {
        // biome_generator.py:32-44 exact structure
        var primary = GeoTables.RegionPrimaryChunks.GetValueOrDefault(
            identity, new[] { NewChunkTypes.Forest });
        var secondary = GeoTables.RegionSecondaryChunks.GetValueOrDefault(
            identity, Array.Empty<string>());
        if (primary.Length == 0)
            primary = new[] { NewChunkTypes.Forest };

        var biomeVal = (GeoNoise.ValueNoise2D(cx * 0.03, cy * 0.03, seed + 500000)
                        + 1.0) * 0.5;

        var pool = biomeVal < primaryWeight || secondary.Length == 0
            ? primary : secondary;

        var typeIdx = (int)(GeoNoise.Hash2D(cx, cy, seed + 600000) * pool.Length)
                      % pool.Length;
        return pool[typeIdx];
    }

    /// <summary>generate_biomes — walks the region map in ITS insertion order
    /// (post-patch: sorted region fill); biome cells are 16-wide with the
    /// double-shifted negative bucketing; BiomeData takes the FIRST chunk's
    /// type/identity and bounds never expand.</summary>
    public static (Dictionary<(int X, int Y), string> ChunkTypeMap,
                   List<(int X, int Y)> ChunkTypeOrder,
                   Dictionary<(int X, int Y), int> BiomeMap,
                   Dictionary<int, BiomeData> Metadata)
        GenerateBiomes(Dictionary<(int X, int Y), int> regionMap,
                       List<(int X, int Y)> regionMapOrder,
                       Dictionary<int, RegionData> regionMetadata,
                       long seed, GeographicConfig config)
    {
        var primaryWeight = config.Biome.PrimaryWeight;

        // Step 1: chunk types (insertion order = regionMapOrder)
        var chunkTypeMap = new Dictionary<(int, int), string>();
        var chunkTypeOrder = new List<(int X, int Y)>();
        foreach (var pos in regionMapOrder)
        {
            var rid = regionMap[pos];
            var region = regionMetadata.GetValueOrDefault(rid);
            string ct;
            if (region is null)
                ct = NewChunkTypes.Forest;
            else
                ct = AssignChunkType(pos.X, pos.Y, region.Identity, seed, primaryWeight);
            chunkTypeMap[pos] = ct;
            chunkTypeOrder.Add(pos);
        }

        // Step 2: coarse biome zones (cell size 16, first-encounter IDs)
        const int biomeCellSize = 16;
        var biomeMap = new Dictionary<(int, int), int>();
        var biomeMetadata = new Dictionary<int, BiomeData>();
        var cellToBiome = new Dictionary<(int, int), int>();
        var nextBiomeId = 0;

        foreach (var (cx, cy) in chunkTypeOrder)
        {
            // Python quirk preserved: negative branch double-shifts because
            // // already floors — cell -1 covers ONLY coordinate -1.
            var bx = cx >= 0 ? cx / biomeCellSize
                : FloorDiv(cx - biomeCellSize + 1, biomeCellSize);
            var by = cy >= 0 ? cy / biomeCellSize
                : FloorDiv(cy - biomeCellSize + 1, biomeCellSize);
            var cellKey = (bx, by);

            if (!cellToBiome.TryGetValue(cellKey, out var bid))
            {
                bid = nextBiomeId;
                nextBiomeId += 1;
                cellToBiome[cellKey] = bid;
                var ct = chunkTypeMap[(cx, cy)];
                var rid = regionMap.GetValueOrDefault((cx, cy), -1);
                var region = regionMetadata.GetValueOrDefault(rid);
                biomeMetadata[bid] = new BiomeData
                {
                    BiomeId = bid,
                    DominantChunkType = ct,
                    RegionIdentity = region?.Identity ?? "forest",
                    ChunkCount = 0,
                    Bounds = (cx, cy, cx, cy),   // first chunk, never updated
                };
            }

            biomeMap[(cx, cy)] = cellToBiome[cellKey];
            biomeMetadata[cellToBiome[cellKey]].ChunkCount += 1;
        }

        return (chunkTypeMap, chunkTypeOrder, biomeMap, biomeMetadata);
    }
}
