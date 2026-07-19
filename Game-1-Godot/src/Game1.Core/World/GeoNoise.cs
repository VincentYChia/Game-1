namespace Game1.Core.World;

/// <summary>
/// Port of systems/geography/noise.py — the determinism core of the primary
/// (geographic) world generator. All-masked 32-bit hash noise, smooth value/
/// fractal noise, contiguity checks, and Voronoi subdivision with farthest-
/// point seed spreading. Pure functions; results are set-iteration-order
/// independent (assignment is per-chunk; seed placement uses sorted order).
/// Pinned by conformance/goldens/db_parity/geo_noise.json.
/// </summary>
public static class GeoNoise
{
    // noise.py:20-26
    public static double Hash2D(int x, int y, long seed)
    {
        unchecked
        {
            var h = (ulong)seed;
            h = ((h ^ (ulong)(x * 374761393L)) + (ulong)(y * 668265263L)) & 0xFFFFFFFFUL;
            h = ((h ^ (h >> 13)) * 1274126177UL) & 0xFFFFFFFFUL;
            h = (h ^ (h >> 16)) & 0xFFFFFFFFUL;
            return (h & 0x7FFFFFFFUL) / (double)0x7FFFFFFF;
        }
    }

    // :29-33
    public static int Hash2DInt(int x, int y, long seed, int maxVal)
    {
        if (maxVal <= 0) return 0;
        return (int)(Hash2D(x, y, seed) * maxVal) % maxVal;
    }

    private static double Smoothstep(double t) => t * t * (3.0 - 2.0 * t);

    // :45-62
    public static double ValueNoise2D(double x, double y, long seed)
    {
        var ix = (int)Math.Floor(x);
        var iy = (int)Math.Floor(y);
        var sx = Smoothstep(x - ix);
        var sy = Smoothstep(y - iy);

        var v00 = Hash2D(ix, iy, seed) * 2.0 - 1.0;
        var v10 = Hash2D(ix + 1, iy, seed) * 2.0 - 1.0;
        var v01 = Hash2D(ix, iy + 1, seed) * 2.0 - 1.0;
        var v11 = Hash2D(ix + 1, iy + 1, seed) * 2.0 - 1.0;

        var top = v00 + sx * (v10 - v00);
        var bottom = v01 + sx * (v11 - v01);
        return top + sy * (bottom - top);
    }

    // :65-80
    public static double FractalNoise2D(double x, double y, long seed,
        int octaves = 4, double lacunarity = 2.0, double persistence = 0.5)
    {
        var total = 0.0;
        var amplitude = 1.0;
        var frequency = 1.0;
        var maxAmplitude = 0.0;
        for (var i = 0; i < octaves; i++)
        {
            total += ValueNoise2D(x * frequency, y * frequency, seed + i * 31337L) * amplitude;
            maxAmplitude += amplitude;
            amplitude *= persistence;
            frequency *= lacunarity;
        }
        return maxAmplitude > 0 ? total / maxAmplitude : 0.0;
    }

    // :87-101
    public static bool IsContiguous(IReadOnlySet<(int X, int Y)> territory)
    {
        if (territory.Count == 0) return true;
        var visited = new HashSet<(int, int)>();
        var stack = new Stack<(int, int)>();
        stack.Push(territory.First());
        while (stack.Count > 0)
        {
            var (x, y) = stack.Pop();
            if (visited.Contains((x, y)) || !territory.Contains((x, y)))
                continue;
            visited.Add((x, y));
            stack.Push((x - 1, y));
            stack.Push((x + 1, y));
            stack.Push((x, y - 1));
            stack.Push((x, y + 1));
        }
        return visited.Count == territory.Count;
    }

    // :104-121
    public static List<HashSet<(int X, int Y)>> FindComponents(
        IReadOnlySet<(int X, int Y)> territory)
    {
        var remaining = new HashSet<(int, int)>(territory);
        var components = new List<HashSet<(int, int)>>();
        while (remaining.Count > 0)
        {
            var component = new HashSet<(int, int)>();
            var stack = new Stack<(int, int)>();
            // noise.py 2026-07-19 determinism patch: start = min(remaining)
            stack.Push(remaining.Min());
            while (stack.Count > 0)
            {
                var (x, y) = stack.Pop();
                if (component.Contains((x, y)) || !remaining.Contains((x, y)))
                    continue;
                component.Add((x, y));
                stack.Push((x - 1, y));
                stack.Push((x + 1, y));
                stack.Push((x, y - 1));
                stack.Push((x, y + 1));
            }
            remaining.ExceptWith(component);
            components.Add(component);
        }
        return components;
    }

    // :124-157 — min horizontal/vertical run length across rows and columns
    public static int MeasureMinCorridorWidth(IReadOnlySet<(int X, int Y)> territory)
    {
        if (territory.Count == 0) return 0;
        var rows = new Dictionary<int, List<int>>();
        var cols = new Dictionary<int, List<int>>();
        foreach (var (x, y) in territory)
        {
            if (!rows.TryGetValue(y, out var xs)) rows[y] = xs = new List<int>();
            xs.Add(x);
            if (!cols.TryGetValue(x, out var ys)) cols[x] = ys = new List<int>();
            ys.Add(y);
        }

        var minWidth = int.MaxValue;
        foreach (var xs in rows.Values.Concat(cols.Values))
        {
            xs.Sort();
            var runLength = 1;
            for (var i = 1; i < xs.Count; i++)
            {
                if (xs[i] == xs[i - 1] + 1)
                {
                    runLength++;
                }
                else
                {
                    minWidth = Math.Min(minWidth, runLength);
                    runLength = 1;
                }
            }
            minWidth = Math.Min(minWidth, runLength);
        }
        return minWidth == int.MaxValue ? 0 : minWidth;
    }

    // :164-222
    public static List<HashSet<(int X, int Y)>> VoronoiSubdivide(
        IReadOnlySet<(int X, int Y)> territory, int numRegions, long seed,
        double noiseAmplitude = 0.0, double noiseFrequency = 0.05)
    {
        if (territory.Count == 0 || numRegions <= 0)
            return territory.Count > 0
                ? new List<HashSet<(int, int)>> { new(territory) }
                : new List<HashSet<(int, int)>>();
        if (numRegions >= territory.Count)
            // noise.py 2026-07-19 follow-up: sorted singleton order
            return territory.OrderBy(c => c)
                .Select(c => new HashSet<(int, int)> { c }).ToList();

        var seedPoints = PlaceSpreadSeeds(territory, numRegions, seed);
        var useNoise = noiseAmplitude > 0;
        var regions = seedPoints.Select(_ => new HashSet<(int, int)>()).ToList();
        var ampSq = noiseAmplitude * noiseAmplitude;

        foreach (var (cx, cy) in territory)
        {
            var bestIdx = 0;
            var bestDist = double.PositiveInfinity;
            var noiseOffset = useNoise
                ? ValueNoise2D(cx * noiseFrequency, cy * noiseFrequency, seed + 77777) * ampSq
                : 0.0;
            for (var i = 0; i < seedPoints.Count; i++)
            {
                double dx = cx - seedPoints[i].X;
                double dy = cy - seedPoints[i].Y;
                var dist = dx * dx + dy * dy + (i % 2 == 0 ? noiseOffset : -noiseOffset);
                if (dist < bestDist)
                {
                    bestDist = dist;
                    bestIdx = i;
                }
            }
            regions[bestIdx].Add((cx, cy));
        }
        return regions.Where(r => r.Count > 0).ToList();
    }

    // :225-265 — first seed by hash; then farthest-point over hashed samples
    private static List<(int X, int Y)> PlaceSpreadSeeds(
        IReadOnlySet<(int X, int Y)> territory, int count, long seed)
    {
        var territoryList = territory.OrderBy(c => c.X).ThenBy(c => c.Y).ToList();
        if (count >= territoryList.Count)
            return territoryList.Take(count).ToList();

        var idx = Hash2DInt(0, 0, seed, territoryList.Count);
        var seeds = new List<(int X, int Y)> { territoryList[idx] };

        var sampleSize = Math.Min(territoryList.Count,
            Math.Max(100, territoryList.Count / 20));

        for (var i = 1; i < count; i++)
        {
            (int X, int Y)? bestPos = null;
            var bestMinDist = -1L;
            for (var j = 0; j < sampleSize; j++)
            {
                var cIdx = Hash2DInt(i, j, seed + 999, territoryList.Count);
                var candidate = territoryList[cIdx];
                var minDist = seeds.Min(s =>
                    (long)(candidate.X - s.X) * (candidate.X - s.X)
                    + (long)(candidate.Y - s.Y) * (candidate.Y - s.Y));
                if (minDist > bestMinDist)
                {
                    bestMinDist = minDist;
                    bestPos = candidate;
                }
            }
            if (bestPos is not null)
                seeds.Add(bestPos.Value);
        }
        return seeds;
    }
}
