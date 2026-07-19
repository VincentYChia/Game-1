namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/political_generator.py (post determinism
/// patch): generic parent→child Voronoi subdivision for provinces
/// (offset 200000) and districts (offset 300000), with first-adjacent
/// sibling merging (the code, not the "most shared border" comment).
/// </summary>
public static class PoliticalGenerator
{
    // _determine_subdivision_count
    public static int DetermineSubdivisionCount(int parentChunkCount, int minChildArea,
                                                int maxChildArea, int parentId, long seed)
    {
        if (minChildArea <= 0) return 1;
        var minCount = Math.Max(2, parentChunkCount / maxChildArea);
        var maxCount = Math.Max(minCount, parentChunkCount / minChildArea);
        if (minCount >= maxCount) return minCount;   // NO hash draw
        var rangeSize = maxCount - minCount + 1;
        var offset = GeoNoise.Hash2DInt(parentId, 0, seed, rangeSize);
        return minCount + offset;
    }

    // _fix_contiguity (political flavor: FIRST adjacent sibling, not edge counts)
    public static List<HashSet<(int X, int Y)>> FixContiguity(
        List<HashSet<(int X, int Y)>> regions)
    {
        var result = new List<HashSet<(int X, int Y)>>(regions);
        for (var i = 0; i < result.Count; i++)
        {
            var components = GeoNoise.FindComponents(result[i]);
            if (components.Count <= 1) continue;

            components = components.OrderByDescending(c => c.Count).ToList();  // stable
            result[i] = components[0];

            foreach (var fragment in components.Skip(1))
            {
                var merged = false;
                foreach (var (cx, cy) in fragment.OrderBy(p => p))   // sorted (patched)
                {
                    foreach (var (dx, dy) in new[] { (-1, 0), (1, 0), (0, -1), (0, 1) })
                    {
                        var neighbor = (cx + dx, cy + dy);
                        for (var j = 0; j < result.Count; j++)
                        {
                            if (j != i && result[j].Contains(neighbor))
                            {
                                result[j].UnionWith(fragment);
                                merged = true;
                                break;
                            }
                        }
                        if (merged) break;
                    }
                    if (merged) break;
                }
                if (!merged)
                    result[i].UnionWith(fragment);
            }
        }
        return result;
    }

    // _merge_tiny — ≤5 sweeps, first-adjacent target, pop without increment
    public static List<HashSet<(int X, int Y)>> MergeTiny(
        List<HashSet<(int X, int Y)>> children, int minArea)
    {
        var result = new List<HashSet<(int X, int Y)>>(children);
        var changed = true;
        var maxIter = 5;
        while (changed && maxIter > 0)
        {
            changed = false;
            maxIter -= 1;
            var i = 0;
            while (i < result.Count)
            {
                if (result[i].Count < minArea && result.Count > 1)
                {
                    var bestIdx = -1;
                    foreach (var (cx, cy) in result[i].OrderBy(p => p))   // sorted (patched)
                    {
                        foreach (var (dx, dy) in new[] { (-1, 0), (1, 0), (0, -1), (0, 1) })
                        {
                            var neighbor = (cx + dx, cy + dy);
                            for (var j = 0; j < result.Count; j++)
                            {
                                if (j != i && result[j].Contains(neighbor))
                                {
                                    bestIdx = j;
                                    break;
                                }
                            }
                            if (bestIdx >= 0) break;
                        }
                        if (bestIdx >= 0) break;
                    }

                    if (bestIdx >= 0)
                    {
                        result[bestIdx].UnionWith(result[i]);
                        result.RemoveAt(i);
                        changed = true;
                        continue;
                    }
                }
                i += 1;
            }
        }
        return result;
    }

    /// <summary>_subdivide_territories — parents ascending; global dense
    /// child ids; returns records (childId, parentId, chunks).</summary>
    public static (Dictionary<(int X, int Y), int> ChildMap,
                   List<(int ChildId, int ParentId, HashSet<(int X, int Y)> Chunks)> Records)
        SubdivideTerritories(Dictionary<int, HashSet<(int X, int Y)>> territories,
                             long seed, long seedOffset, int minArea, int maxArea,
                             double noiseAmplitude, double noiseFrequency)
    {
        var childMap = new Dictionary<(int, int), int>();
        var childRecords = new List<(int, int, HashSet<(int X, int Y)>)>();
        var nextId = 0;

        foreach (var parentId in territories.Keys.OrderBy(k => k))
        {
            var territory = territories[parentId];
            if (territory.Count == 0) continue;

            var childSeed = seed + parentId * 500 + seedOffset;
            var count = DetermineSubdivisionCount(territory.Count, minArea, maxArea,
                                                  parentId, childSeed);
            if (count <= 1)
            {
                var cid0 = nextId;
                nextId += 1;
                foreach (var pos in territory)
                    childMap[pos] = cid0;
                childRecords.Add((cid0, parentId, new HashSet<(int, int)>(territory)));
                continue;
            }

            var rawChildren = GeoNoise.VoronoiSubdivide(
                territory, count, childSeed,
                noiseAmplitude: noiseAmplitude, noiseFrequency: noiseFrequency);
            var fixedChildren = FixContiguity(rawChildren);
            var merged = MergeTiny(fixedChildren, minArea);

            foreach (var childChunks in merged)
            {
                if (childChunks.Count == 0) continue;
                var cid = nextId;
                nextId += 1;
                foreach (var pos in childChunks)
                    childMap[pos] = cid;
                childRecords.Add((cid, parentId, childChunks));
            }
        }

        return (childMap, childRecords);
    }

    // generate_provinces — offset 200000; mutates region metadata
    public static (Dictionary<(int X, int Y), int> ProvinceMap,
                   Dictionary<int, ProvinceData> Metadata)
        GenerateProvinces(Dictionary<(int X, int Y), int> regionMap,
                          Dictionary<int, RegionData> regionMetadata,
                          long seed, GeographicConfig config)
    {
        var regionTerritories = new Dictionary<int, HashSet<(int, int)>>();
        foreach (var kv in regionMap)
        {
            if (!regionTerritories.TryGetValue(kv.Value, out var set))
                regionTerritories[kv.Value] = set = new HashSet<(int, int)>();
            set.Add(kv.Key);
        }

        var (provinceMap, records) = SubdivideTerritories(
            regionTerritories, seed, 200000,
            config.Province.MinArea, config.Province.MaxArea,
            config.Province.DeformAmplitude, config.Province.DeformFrequency);

        var provinceMetadata = new Dictionary<int, ProvinceData>();
        foreach (var (pid, parentRid, chunks) in records)
        {
            var region = regionMetadata.GetValueOrDefault(parentRid);
            var nationId = region?.NationId ?? -1;
            provinceMetadata[pid] = new ProvinceData
            {
                ProvinceId = pid,
                Name = "",
                RegionId = parentRid,
                NationId = nationId,
                ChunkCount = chunks.Count,
                Bounds = RegionGenerator.ComputeBounds(chunks),
            };
            region?.ProvinceIds.Add(pid);
        }

        return (provinceMap, provinceMetadata);
    }

    // generate_districts — offset 300000; mutates province metadata
    public static (Dictionary<(int X, int Y), int> DistrictMap,
                   Dictionary<int, DistrictData> Metadata)
        GenerateDistricts(Dictionary<(int X, int Y), int> provinceMap,
                          Dictionary<int, ProvinceData> provinceMetadata,
                          long seed, GeographicConfig config)
    {
        var provinceTerritories = new Dictionary<int, HashSet<(int, int)>>();
        foreach (var kv in provinceMap)
        {
            if (!provinceTerritories.TryGetValue(kv.Value, out var set))
                provinceTerritories[kv.Value] = set = new HashSet<(int, int)>();
            set.Add(kv.Key);
        }

        var (districtMap, records) = SubdivideTerritories(
            provinceTerritories, seed, 300000,
            config.District.MinArea, config.District.MaxArea,
            config.District.DeformAmplitude, config.District.DeformFrequency);

        var districtMetadata = new Dictionary<int, DistrictData>();
        foreach (var (did, parentPid, chunks) in records)
        {
            var province = provinceMetadata.GetValueOrDefault(parentPid);
            districtMetadata[did] = new DistrictData
            {
                DistrictId = did,
                Name = "",
                ProvinceId = parentPid,
                RegionId = province?.RegionId ?? -1,
                NationId = province?.NationId ?? -1,
                ChunkCount = chunks.Count,
                Bounds = RegionGenerator.ComputeBounds(chunks),
            };
            province?.DistrictIds.Add(did);
        }

        return (districtMap, districtMetadata);
    }
}
