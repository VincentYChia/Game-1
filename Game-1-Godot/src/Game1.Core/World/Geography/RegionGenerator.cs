namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/region_generator.py (post determinism patch):
/// noise-perturbed Voronoi subdivision of each nation into 3-8 regions,
/// contiguity repair, small-region merging, identity assignment by
/// list-index hash. Mutates nation metadata region_ids like Python.
/// </summary>
public static class RegionGenerator
{
    // _determine_region_count — seed here is region_seed
    public static int DetermineRegionCount(int nationId, int nationChunkCount,
                                           long seed, GeographicConfig config)
    {
        var minR = config.Region.MinPerNation;
        var maxR = config.Region.MaxPerNation;
        var rangeR = maxR - minR;
        var sizeFactor = Math.Min(1.0, nationChunkCount / 60000.0);
        var baseCount = minR + sizeFactor * rangeR;
        var variance = GeoNoise.Hash2D(nationId, 0, seed + 33333) * 2.0 - 1.0;
        var count = (int)(baseCount + variance * 1.5);   // int() truncation
        return Math.Max(minR, Math.Min(maxR, count));
    }

    // _assign_identity — index into RegionIdentity declaration order
    public static string AssignIdentity(int regionIdx, int nationId, long seed)
    {
        var identityIdx = GeoNoise.Hash2DInt(regionIdx, nationId, seed + 44444,
                                             GeoTables.RegionIdentities.Length);
        return GeoTables.RegionIdentities[identityIdx];
    }

    // _find_adjacent_region (patched: sorted region iteration) — most
    // adjacency EDGES wins; Python max() first-max-in-insertion-order ties
    public static int FindAdjacentRegion(HashSet<(int X, int Y)> region,
                                         List<HashSet<(int X, int Y)>> allRegions,
                                         int excludeIdx)
    {
        var neighborCounts = new Dictionary<int, int>();
        var neighborOrder = new List<int>();
        foreach (var (cx, cy) in region.OrderBy(p => p))   // sorted(region)
        {
            foreach (var (dx, dy) in new[] { (-1, 0), (1, 0), (0, -1), (0, 1) })
            {
                var neighbor = (cx + dx, cy + dy);
                for (var idx = 0; idx < allRegions.Count; idx++)
                {
                    if (idx != excludeIdx && allRegions[idx].Contains(neighbor))
                    {
                        if (!neighborCounts.ContainsKey(idx))
                        {
                            neighborCounts[idx] = 0;
                            neighborOrder.Add(idx);
                        }
                        neighborCounts[idx] += 1;
                        break;
                    }
                }
            }
        }

        if (neighborCounts.Count == 0) return -1;

        var best = neighborOrder[0];
        var bestCount = neighborCounts[best];
        foreach (var key in neighborOrder)
        {
            if (neighborCounts[key] > bestCount)
            {
                bestCount = neighborCounts[key];
                best = key;
            }
        }
        return best;
    }

    // _fix_contiguity — shares set objects like Python's shallow list copy
    public static List<HashSet<(int X, int Y)>> FixContiguity(
        List<HashSet<(int X, int Y)>> regions)
    {
        var result = new List<HashSet<(int X, int Y)>>(regions);
        for (var i = 0; i < result.Count; i++)
        {
            var components = GeoNoise.FindComponents(result[i]);
            if (components.Count <= 1) continue;

            components = components.OrderByDescending(c => c.Count).ToList();  // stable
            result[i] = components[0];   // rebind to main

            foreach (var fragment in components.Skip(1))
            {
                var mergeTarget = FindAdjacentRegion(fragment, result, i);
                if (mergeTarget >= 0)
                    result[mergeTarget].UnionWith(fragment);
                else
                    result[i].UnionWith(fragment);
            }
        }
        return result;
    }

    // _validate_region_areas — merge tiny regions, ≤10 sweeps
    public static List<HashSet<(int X, int Y)>> ValidateRegionAreas(
        List<HashSet<(int X, int Y)>> regions, int nationChunkCount,
        GeographicConfig config)
    {
        var minArea = (int)(nationChunkCount * config.Region.MinAreaPct);
        var result = new List<HashSet<(int X, int Y)>>(regions);
        var changed = true;
        var maxIterations = 10;
        while (changed && maxIterations > 0)
        {
            changed = false;
            maxIterations -= 1;
            var i = 0;
            while (i < result.Count)
            {
                if (result[i].Count < minArea && result.Count > 1)
                {
                    var mergeTarget = FindAdjacentRegion(result[i], result, i);
                    if (mergeTarget >= 0)
                    {
                        result[mergeTarget].UnionWith(result[i]);
                        result.RemoveAt(i);
                        changed = true;
                        continue;   // same i — shifted element next
                    }
                }
                i += 1;
            }
        }
        return result;
    }

    public static (int MinX, int MinY, int MaxX, int MaxY) ComputeBounds(
        HashSet<(int X, int Y)> chunks)
    {
        if (chunks.Count == 0) return (0, 0, 0, 0);
        return (chunks.Min(c => c.X), chunks.Min(c => c.Y),
                chunks.Max(c => c.X), chunks.Max(c => c.Y));
    }

    /// <summary>generate_regions — global dense region ids across nations in
    /// ascending nation order; region_map filled sorted (patched Python).</summary>
    public static (Dictionary<(int X, int Y), int> RegionMap,
                   List<(int X, int Y)> RegionMapOrder,
                   Dictionary<int, RegionData> Metadata)
        GenerateRegions(NationGenerator.OrderedNationMap nationMap,
                        Dictionary<int, NationData> nationMetadata,
                        long seed, GeographicConfig config)
    {
        var nationTerritories = new Dictionary<int, HashSet<(int, int)>>();
        foreach (var pos in nationMap.Order)
        {
            var nid = nationMap.Map[pos];
            if (!nationTerritories.TryGetValue(nid, out var set))
                nationTerritories[nid] = set = new HashSet<(int, int)>();
            set.Add(pos);
        }

        var regionMap = new Dictionary<(int, int), int>();
        var regionMapOrder = new List<(int X, int Y)>();
        var regionMetadata = new Dictionary<int, RegionData>();
        var nextRegionId = 0;

        foreach (var nationId in nationTerritories.Keys.OrderBy(k => k))
        {
            var territory = nationTerritories[nationId];
            var nationData = nationMetadata.GetValueOrDefault(nationId);
            if (nationData is null || territory.Count == 0)
                continue;

            var regionSeed = seed + nationId * 1000 + 100000;
            var regionCount = DetermineRegionCount(nationId, territory.Count,
                                                   regionSeed, config);
            var rawRegions = GeoNoise.VoronoiSubdivide(
                territory, regionCount, regionSeed,
                noiseAmplitude: config.Region.DeformAmplitude,
                noiseFrequency: config.Region.DeformFrequency);
            var fixedRegions = FixContiguity(rawRegions);
            var validatedRegions = ValidateRegionAreas(fixedRegions, territory.Count, config);

            for (var i = 0; i < validatedRegions.Count; i++)
            {
                var regionChunks = validatedRegions[i];
                if (regionChunks.Count == 0) continue;   // consumes index i, no id

                var rid = nextRegionId;
                nextRegionId += 1;
                var identity = AssignIdentity(i, nationId, regionSeed);

                regionMetadata[rid] = new RegionData
                {
                    RegionId = rid,
                    Name = "",
                    NationId = nationId,
                    Identity = identity,
                    ChunkCount = regionChunks.Count,
                    Bounds = ComputeBounds(regionChunks),
                };

                nationData.RegionIds.Add(rid);

                foreach (var pos in regionChunks.OrderBy(p => p))   // sorted (patched)
                {
                    regionMap[pos] = rid;
                    regionMapOrder.Add(pos);
                }
            }
        }

        return (regionMap, regionMapOrder, regionMetadata);
    }
}
