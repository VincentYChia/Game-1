namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/ecosystem_generator.py (post determinism
/// patch): 3x3 danger cells with hash-weighted rolls biased by chunk types,
/// ±2 gradient smoothing with stale-read semantics, sequential eco IDs.
/// Uses the models constant gradient (2) — config.ecosystem.gradient_max is
/// IGNORED, matching Python.
/// </summary>
public static class EcosystemGenerator
{
    private static readonly HashSet<string> SafeChunkTypes =
        new() { NewChunkTypes.Lake, NewChunkTypes.River, NewChunkTypes.Forest };

    private static readonly HashSet<string> DangerousChunkTypes = new()
    {
        NewChunkTypes.DeepCave, NewChunkTypes.CursedMarsh,
        NewChunkTypes.CrystalCavern, NewChunkTypes.BarrenWaste,
    };

    // _chunk_to_ecosystem — same double-shift negative bucketing quirk
    public static (int Ex, int Ey) ChunkToEcosystem(int cx, int cy, int groupSize)
    {
        var ex = cx >= 0 ? cx / groupSize
            : GeoBiomeGenerator.FloorDiv(cx - groupSize + 1, groupSize);
        var ey = cy >= 0 ? cy / groupSize
            : GeoBiomeGenerator.FloorDiv(cy - groupSize + 1, groupSize);
        return (ex, ey);
    }

    // _compute_base_danger — ONLY draw: hash_2d(ex, ey, seed + 700000)
    public static int ComputeBaseDanger(int ecoX, int ecoY,
                                        HashSet<(int X, int Y)> ecoChunks,
                                        Dictionary<(int X, int Y), string> chunkTypeMap,
                                        long seed, GeographicConfig config)
    {
        var spawnSafe = config.Ecosystem.SpawnSafeRadius;
        var ecoDist = Math.Max(Math.Abs(ecoX), Math.Abs(ecoY));
        if (ecoDist <= spawnSafe)   // INCLUSIVE — no draw
            return (int)DangerLevel.Tranquil;

        // shallow copy preserving insertion order 1..6 (+ appended keys)
        var weights = new Dictionary<int, double>();
        var weightOrder = new List<int>();
        foreach (var kv in config.Ecosystem.BaseDangerWeights)
        {
            weights[kv.Key] = kv.Value;
            weightOrder.Add(kv.Key);
        }

        var safeCount = 0;
        var dangerousCount = 0;
        foreach (var pos in ecoChunks)
        {
            var ct = chunkTypeMap.GetValueOrDefault(pos);
            if (ct is not null && SafeChunkTypes.Contains(ct)) safeCount += 1;
            else if (ct is not null && DangerousChunkTypes.Contains(ct)) dangerousCount += 1;
        }

        var total = ecoChunks.Count > 0 ? ecoChunks.Count : 1;
        var safeRatio = (double)safeCount / total;
        var dangerousRatio = (double)dangerousCount / total;

        void Bias(int level, double mult)
        {
            if (!weights.ContainsKey(level))
            {
                weights[level] = 0;
                weightOrder.Add(level);   // .get(level, 0) appends missing keys
            }
            weights[level] *= mult;
        }

        if (safeRatio > 0.5)   // STRICT
            foreach (var level in new[] { 1, 2, 3 })
                Bias(level, 1.0 + safeRatio);
        if (dangerousRatio > 0.3)   // STRICT; both can co-fire
            foreach (var level in new[] { 4, 5, 6 })
                Bias(level, 1.0 + dangerousRatio * 2);

        var totalWeight = 0.0;
        foreach (var key in weightOrder)   // sum() in dict insertion order
            totalWeight += weights[key];
        if (totalWeight <= 0)
            return (int)DangerLevel.Moderate;

        var roll = GeoNoise.Hash2D(ecoX, ecoY, seed + 700000);
        var cumulative = 0.0;
        foreach (var level in weights.Keys.OrderBy(k => k))   // sorted ascending
        {
            cumulative += weights[level] / totalWeight;   // divide then add
            if (roll < cumulative)   // STRICT
                return level;
        }
        return (int)DangerLevel.Moderate;   // reachable: hash can be exactly 1.0
    }

    // _smooth_gradient — snapshot pass-start values, live neighbor reads,
    // stale own-level within the 4-neighbor loop, ≤20 passes
    public static (Dictionary<(int, int), int> Smoothed, List<(int, int)> Order)
        SmoothGradient(Dictionary<(int, int), int> ecoDangers,
                       List<(int, int)> ecoOrder, int gradientMax)
    {
        var result = new Dictionary<(int, int), int>(ecoDangers);
        for (var iteration = 0; iteration < 20; iteration++)
        {
            var changed = false;
            var snapshot = ecoOrder.Select(k => (Key: k, Level: result[k])).ToList();
            foreach (var ((ex, ey), level) in snapshot)
            {
                foreach (var (dx, dy) in new[] { (-1, 0), (1, 0), (0, -1), (0, 1) })
                {
                    var neighbor = (ex + dx, ey + dy);
                    if (!result.TryGetValue(neighbor, out var neighborLevel))
                        continue;   // live read
                    var diff = Math.Abs(level - neighborLevel);
                    if (diff > gradientMax)   // STRICT
                    {
                        var newLevel = level > neighborLevel
                            ? neighborLevel + gradientMax
                            : neighborLevel - gradientMax;
                        newLevel = Math.Max(1, Math.Min(6, newLevel));
                        if (newLevel != level)   // compare against STALE level
                        {
                            result[(ex, ey)] = newLevel;
                            changed = true;
                        }
                    }
                }
            }
            if (!changed) break;
        }
        return (result, ecoOrder);
    }

    /// <summary>generate_ecosystems (patched: chunk_type_map order, not set).</summary>
    public static (Dictionary<(int X, int Y), int> EcosystemMap,
                   Dictionary<(int X, int Y), DangerLevel> DangerMap,
                   Dictionary<int, EcosystemData> Metadata)
        GenerateEcosystems(Dictionary<(int X, int Y), string> chunkTypeMap,
                           List<(int X, int Y)> chunkTypeOrder,
                           long seed, GeographicConfig config)
    {
        var groupSize = config.Ecosystem.GroupSize;
        var gradientMax = GeoTables.DangerGradientMax;   // models constant, NOT config

        // Step 1: eco cells in first-seen order
        var ecoCells = new Dictionary<(int, int), HashSet<(int X, int Y)>>();
        var ecoOrder = new List<(int, int)>();
        foreach (var pos in chunkTypeOrder)
        {
            var ecoPos = ChunkToEcosystem(pos.X, pos.Y, groupSize);
            if (!ecoCells.TryGetValue(ecoPos, out var set))
            {
                ecoCells[ecoPos] = set = new HashSet<(int, int)>();
                ecoOrder.Add(ecoPos);
            }
            set.Add(pos);
        }

        // Step 2: base danger per cell
        var ecoDangers = new Dictionary<(int, int), int>();
        foreach (var ecoPos in ecoOrder)
            ecoDangers[ecoPos] = ComputeBaseDanger(ecoPos.Item1, ecoPos.Item2,
                                                   ecoCells[ecoPos], chunkTypeMap,
                                                   seed, config);

        // Step 3: gradient smoothing
        var (smoothed, _) = SmoothGradient(ecoDangers, ecoOrder, gradientMax);

        // Step 4: assemble
        var ecosystemMap = new Dictionary<(int, int), int>();
        var dangerMap = new Dictionary<(int, int), DangerLevel>();
        var ecosystemMetadata = new Dictionary<int, EcosystemData>();
        var ecoId = 0;
        foreach (var ecoPos in ecoOrder)
        {
            var eid = ecoId;
            ecoId += 1;
            var danger = (DangerLevel)Math.Max(1, Math.Min(6,
                smoothed.GetValueOrDefault(ecoPos, 3)));

            ecosystemMetadata[eid] = new EcosystemData
            {
                EcosystemId = eid,
                DangerLevel = danger,
                EcoX = ecoPos.Item1,
                EcoY = ecoPos.Item2,
            };

            foreach (var pos in ecoCells[ecoPos])
            {
                ecosystemMap[pos] = eid;
                dangerMap[pos] = danger;
            }
        }

        return (ecosystemMap, dangerMap, ecosystemMetadata);
    }
}
