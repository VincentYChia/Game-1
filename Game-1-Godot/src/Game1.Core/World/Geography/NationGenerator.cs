using System.Text.Json.Nodes;

namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/nation_generator.py (post 2026-07-19
/// determinism patch): angular-sector template (or JSON template file) →
/// severe hash-noise border deformation → Fisher-Yates id shuffle →
/// contiguity/min-area repair → NationData metadata. No random module —
/// all stochastic values are stateless GeoNoise hashes.
///
/// Maps are Dictionary + explicit insertion-order key lists: after the
/// Python patch, every output-affecting iteration is either row-major
/// template order or sorted(), both reproduced exactly here.
/// </summary>
public static class NationGenerator
{
    private static readonly string[] DefaultFlavors =
        { "stoic", "flowing", "imperial", "stoneworn", "ethereal" };

    private static readonly (int R, int G, int B)[] DefaultColors =
    {
        (70, 110, 170), (80, 155, 80), (190, 155, 60), (155, 95, 70),
        (130, 100, 175), (170, 80, 80), (80, 155, 150), (160, 140, 90),
        (100, 80, 140), (140, 160, 80), (180, 120, 100), (90, 130, 120),
    };

    /// <summary>Ordered chunk→nation map: dictionary + insertion-order keys.</summary>
    public sealed class OrderedNationMap
    {
        public readonly Dictionary<(int X, int Y), int> Map = new();
        public readonly List<(int X, int Y)> Order = new();

        public void Add((int X, int Y) pos, int nid)
        {
            if (!Map.ContainsKey(pos)) Order.Add(pos);
            Map[pos] = nid;
        }
    }

    // nation_generator.py _generate_default_template
    public static OrderedNationMap GenerateDefaultTemplate(int worldSize, int nationCount)
    {
        var half = worldSize / 2;
        var angleStep = 2.0 * Math.PI / nationCount;
        var template = new OrderedNationMap();
        for (var y = -half; y < half; y++)
        {
            for (var x = -half; x < half; x++)
            {
                var angle = Math.Atan2(y, x) + Math.PI;
                var nationId = (int)(angle / angleStep) % nationCount;
                template.Add((x, y), nationId);
            }
        }
        return template;
    }

    // _load_template_from_file — {"template": [[nid,...],...]} row-major
    public static OrderedNationMap? LoadTemplateFromFile(string path, int worldSize)
    {
        try
        {
            var data = JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
            if (data?["template"] is not JsonArray grid || grid.Count < worldSize)
                return null;
            var half = worldSize / 2;
            var template = new OrderedNationMap();
            for (var rowIdx = 0; rowIdx < Math.Min(grid.Count, worldSize); rowIdx++)
            {
                if (grid[rowIdx] is not JsonArray row) return null;
                var y = rowIdx - half;
                for (var colIdx = 0; colIdx < Math.Min(row.Count, worldSize); colIdx++)
                {
                    var x = colIdx - half;
                    // Python int() truncates toward zero on float JSON values
                    var v = Data.J.AsNum(row[colIdx]) ?? 0;
                    template.Add((x, y), (int)v);
                }
            }
            return template;
        }
        catch
        {
            return null;
        }
    }

    // _deform_nations (patched: iterates template insertion order)
    public static OrderedNationMap DeformNations(OrderedNationMap template, long seed,
                                                 GeographicConfig config)
    {
        var worldSize = config.World.WorldSize;
        var half = worldSize / 2;
        var amplitude = config.Nation.DeformAmplitude;
        var frequency = config.Nation.DeformFrequency;
        var octaves = config.Nation.DeformOctaves;
        var nationCount = config.Nation.Count;

        // Phase 1: per-nation scale factors
        var scaleSeed = seed + 7777;
        var scaleFactors = new Dictionary<int, double>();
        for (var nid = 0; nid < nationCount; nid++)
        {
            var raw = GeoNoise.Hash2D(nid, 0, scaleSeed) * 2.0 - 1.0;
            scaleFactors[nid] = 1.0 + raw * config.Nation.DeformScaleVariance;
        }

        // Phase 2: border displacement
        var result = new OrderedNationMap();
        foreach (var (cx, cy) in template.Order)
        {
            var originalNation = template.Map[(cx, cy)];

            var noiseX = GeoNoise.FractalNoise2D(cx * frequency, cy * frequency,
                                                 seed + 11111, octaves: octaves);
            var noiseY = GeoNoise.FractalNoise2D(cx * frequency + 500.0,
                                                 cy * frequency + 500.0,
                                                 seed + 22222, octaves: octaves);
            var lookupX = cx + noiseX * amplitude;
            var lookupY = cy + noiseY * amplitude;

            // Python round() = banker's rounding
            var lx = (int)Math.Max(-half, Math.Min(half - 1,
                (int)Math.Round(lookupX, MidpointRounding.ToEven)));
            var ly = (int)Math.Max(-half, Math.Min(half - 1,
                (int)Math.Round(lookupY, MidpointRounding.ToEven)));

            var lookupPos = (lx, ly);
            if (template.Map.TryGetValue(lookupPos, out var displacedNation))
            {
                if (displacedNation != originalNation)
                {
                    var scaleDisplaced = scaleFactors.GetValueOrDefault(displacedNation, 1.0);
                    var scaleOriginal = scaleFactors.GetValueOrDefault(originalNation, 1.0);
                    result.Add((cx, cy),
                        scaleDisplaced > scaleOriginal ? displacedNation : originalNation);
                }
                else
                {
                    result.Add((cx, cy), displacedNation);
                }
            }
            else
            {
                result.Add((cx, cy), originalNation);
            }
        }
        return result;
    }

    // _shuffle_nation_ids — Fisher-Yates on [0..count) via Hash2DInt
    public static OrderedNationMap ShuffleNationIds(OrderedNationMap nationMap,
                                                    int nationCount, long seed)
    {
        var ids = Enumerable.Range(0, nationCount).ToList();
        for (var i = ids.Count - 1; i >= 1; i--)
        {
            var j = GeoNoise.Hash2DInt(i, 0, seed + 55555, i + 1);
            (ids[i], ids[j]) = (ids[j], ids[i]);
        }
        var idMap = new Dictionary<int, int>();
        for (var old = 0; old < ids.Count; old++)
            idMap[old] = ids[old];

        var result = new OrderedNationMap();
        foreach (var pos in nationMap.Order)
        {
            var nid = nationMap.Map[pos];
            result.Add(pos, idMap.GetValueOrDefault(nid, nid));
        }
        return result;
    }

    // _find_nearest_nation — ring scan radius 1..49, dx outer / dy inner,
    // perimeter cells only, first hit wins; fallback 0
    public static int FindNearestNation(int x, int y, int excludeNation,
                                        Dictionary<(int, int), int> nationMap)
    {
        for (var radius = 1; radius < 50; radius++)
        {
            for (var dx = -radius; dx <= radius; dx++)
            {
                for (var dy = -radius; dy <= radius; dy++)
                {
                    if (Math.Abs(dx) != radius && Math.Abs(dy) != radius)
                        continue;
                    var pos = (x + dx, y + dy);
                    if (nationMap.TryGetValue(pos, out var nid) && nid != excludeNation)
                        return nid;
                }
            }
        }
        return 0;
    }

    /// <summary>Ordered territories: nid → set, keys in first-appearance order.</summary>
    public sealed class OrderedTerritories
    {
        public readonly Dictionary<int, HashSet<(int X, int Y)>> Map = new();
        public readonly List<int> Order = new();

        public HashSet<(int X, int Y)> GetOrAdd(int nid)
        {
            if (!Map.TryGetValue(nid, out var set))
            {
                set = new HashSet<(int, int)>();
                Map[nid] = set;
                Order.Add(nid);
            }
            return set;
        }
    }

    // _validate_and_repair (patched: sorted fragments + sorted merge scans)
    public static OrderedNationMap ValidateAndRepair(OrderedNationMap nationMap,
                                                     GeographicConfig config)
    {
        var minArea = config.Nation.MinArea;

        var territories = new OrderedTerritories();
        foreach (var pos in nationMap.Order)
            territories.GetOrAdd(nationMap.Map[pos]).Add(pos);

        var result = new OrderedNationMap();
        foreach (var pos in nationMap.Order)
            result.Add(pos, nationMap.Map[pos]);

        // Pass 1: contiguity — snapshot taken ONCE (keys added mid-loop skipped)
        var pass1Snapshot = territories.Order.ToList();
        foreach (var nid in pass1Snapshot)
        {
            if (!territories.Map.TryGetValue(nid, out var terr) || terr.Count == 0)
                continue;

            var components = GeoNoise.FindComponents(terr);
            if (components.Count <= 1) continue;

            // stable descending-by-size (discovery order deterministic post-patch)
            components = components.OrderByDescending(c => c.Count).ToList();

            var fragments = new List<(int X, int Y)>();
            foreach (var comp in components.Skip(1))
                foreach (var p in comp.OrderBy(p => p))   // sorted(comp)
                    fragments.Add(p);

            foreach (var (fx, fy) in fragments)
            {
                var bestNation = FindNearestNation(fx, fy, nid, result.Map);
                result.Map[(fx, fy)] = bestNation;   // key exists — order unchanged
                territories.Map[nid].Remove((fx, fy));
                territories.GetOrAdd(bestNation).Add((fx, fy));
            }
        }

        // Pass 2: min area — FRESH snapshot including Pass-1 additions
        var pass2Snapshot = territories.Order.ToList();
        foreach (var nid in pass2Snapshot)
        {
            if (!territories.Map.ContainsKey(nid)) continue;
            if (territories.Map[nid].Count < minArea)
            {
                var neighborCounts = new Dictionary<int, int>();
                var neighborOrder = new List<int>();
                foreach (var (cx, cy) in territories.Map[nid].OrderBy(p => p))  // sorted
                {
                    foreach (var (dx, dy) in new[] { (-1, 0), (1, 0), (0, -1), (0, 1) })
                    {
                        var neighborPos = (cx + dx, cy + dy);
                        if (result.Map.TryGetValue(neighborPos, out var nnid) && nnid != nid)
                        {
                            if (!neighborCounts.ContainsKey(nnid))
                            {
                                neighborCounts[nnid] = 0;
                                neighborOrder.Add(nnid);
                            }
                            neighborCounts[nnid] += 1;
                        }
                    }
                }

                if (neighborCounts.Count > 0)
                {
                    // Python max(): FIRST key attaining the max in insertion order
                    var mergeInto = neighborOrder[0];
                    var best = neighborCounts[mergeInto];
                    foreach (var key in neighborOrder)
                    {
                        if (neighborCounts[key] > best)
                        {
                            best = neighborCounts[key];
                            mergeInto = key;
                        }
                    }

                    foreach (var pos in territories.Map[nid])
                        result.Map[pos] = mergeInto;
                    foreach (var pos in territories.Map[nid])
                        territories.GetOrAdd(mergeInto).Add(pos);
                    territories.Map[nid] = new HashSet<(int, int)>();
                }
            }
        }

        return result;
    }

    // generate_nations — full pipeline step
    public static (OrderedNationMap Map, Dictionary<int, NationData> Metadata)
        GenerateNations(long seed, GeographicConfig config, string? templatePath = null)
    {
        var worldSize = config.World.WorldSize;
        var nationCount = config.Nation.Count;

        OrderedNationMap? template = null;
        if (!string.IsNullOrEmpty(templatePath) && File.Exists(templatePath))
            template = LoadTemplateFromFile(templatePath, worldSize);
        template ??= GenerateDefaultTemplate(worldSize, nationCount);

        var deformed = DeformNations(template, seed, config);
        var shuffled = ShuffleNationIds(deformed, nationCount, seed);
        var validated = ValidateAndRepair(shuffled, config);

        // Metadata
        var territories = new Dictionary<int, HashSet<(int, int)>>();
        foreach (var pos in validated.Order)
        {
            var nid = validated.Map[pos];
            if (!territories.TryGetValue(nid, out var set))
                territories[nid] = set = new HashSet<(int, int)>();
            set.Add(pos);
        }

        var flavorSeed = seed + 88888;
        var flavorOrder = Enumerable.Range(0, nationCount).ToList();
        for (var i = nationCount - 1; i >= 1; i--)
        {
            var j = GeoNoise.Hash2DInt(i, 0, flavorSeed, i + 1);
            (flavorOrder[i], flavorOrder[j]) = (flavorOrder[j], flavorOrder[i]);
        }

        var metadata = new Dictionary<int, NationData>();
        for (var nid = 0; nid < nationCount; nid++)
        {
            var flavorIdx = flavorOrder[nid] % DefaultFlavors.Length;
            var chunkCount = territories.TryGetValue(nid, out var chunks) ? chunks.Count : 0;
            metadata[nid] = new NationData
            {
                NationId = nid,
                Name = "",
                NamingFlavor = DefaultFlavors[flavorIdx],
                ChunkCount = chunkCount,
                Color = DefaultColors[flavorIdx % DefaultColors.Length],
            };
        }

        return (validated, metadata);
    }
}
