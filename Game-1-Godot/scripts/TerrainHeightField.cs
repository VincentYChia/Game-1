using Game1.Core.World;
using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>
/// True-3D elevation — the one presentation layer with no Python oracle.
///
/// The world is a SINGLE CONTINUOUS, DOMAIN-WARPED height field defined over the
/// whole 512² world and sampled everywhere, so features LINK across chunk and
/// region borders by construction (no per-chunk ponds, no boundary steps). The
/// certified geography BIASES the field; it never defines the silhouette:
///
///   H = SeaBase
///     + baseLand         gentle continental roll (plains/forest sit here)
///     + range            long warped ridged crests, gated by a tectonic BELT
///                        mask OR a "mountains/highlands" geography boost
///     - pass             broad notches carve walkable routes THROUGH belts
///     + geoBias          blurred per-chunk elevation bias — lowlands/lakeland/
///                        marsh dip BELOW water so their basins flood & connect
///     - river            winding carved channels that link basins into one net
///     + rockyDetail      jagged crests, only where rocky
///     + fine             texture
///
/// Mountains are HUGE and routed-around (peaks tens of units, steep) while most
/// of the land is gentle — the contrast is the grandeur. H() is the single
/// source of truth (mesh, collider, entity placement, height gate).
/// </summary>
public static class TerrainHeightField
{
    private static WorldMap? _worldMap;
    private static long _seed;

    public const double SpawnX = 8;
    public const double SpawnY = 8;
    public const double SpawnFlatRadius = 18;
    private const double SpawnBlend = 60;   // gentler ramp out of spawn (megascale land)
    // Spawn ENVELOPE: fade the mountain ranges (and their jagged detail) to nothing
    // near origin, so there is ALWAYS a gentle, walkable starting basin — no
    // megascale wall boxing the player in, whatever region the seed puts at spawn.
    private const double SpawnClear = 44;    // ranges fully suppressed within this radius (tiles)
    private const double SpawnFalloff = 380; // then grow back gently over this distance
    private static float _flatLevel = 2.6f;

    public const float WaterLevel = 0.2f;

    // ---- world-shape constants (the primary drama tuning surface) ----
    // NEAR-REAL-LIFE SCALE: mountains are MEGASTRUCTURES — very tall AND very wide
    // (see the much-lower belt/ridge frequencies in Field), so a single massif
    // spans many chunks and carries vertical sub-ecosystems (valley forest →
    // flanks → stone → scree → snow). Villages get carved flat shelves so they sit
    // ON a mountain rather than sprawling down its slope (see the village pads).
    private const double SeaBase = 2.7;     // datum: plains float above water
    private const double BaseAmp = 8.0;     // broad continental roll (grander)
    private const double RangeAmp = 330.0;  // peak range height — trimmed 520->430->330 so mountain FLANKS slope gently by default (climbable); sheer cliffs come from the rocky detail as an occasional feature, not the whole face
    private const double RiverDepth = 45.0; // how deep carved rivers/valleys cut
    private const double DetailAmp = 11.0;  // jagged rocky crest detail — was 24; halved so faces read as broad rock, not a spiky staircase (also steadier collision)
    private const double HillAmp = 20.0;    // rolling hills in NON-mountain regions

    // Caves: a walkable ramped grotto carved into the heightfield at cave/cavern
    // chunks (CaveSystem roofs it over). Walls ≤ ~40° so the player walks in/out;
    // a flat chamber floor kept above water (dry) or below it (flooded).
    public const double CaveRadius = 8.0;
    public const double CaveDepth = 6.0;

    // Region identity → elevation bias (blurred). Lowlands/lakeland/marsh dip
    // below the water datum so their (contiguous) basins flood into one body.
    private static readonly Dictionary<string, float> GeoBias = new()
    {
        ["mountains"] = 2.0f,
        ["highlands"] = 3.5f,
        ["caverns"] = 1.0f,
        ["ruins"] = 0.0f,
        ["steppe"] = -0.5f,
        ["forest"] = 0.4f,
        ["plains"] = 0.0f,
        ["lowlands"] = -5.5f,
        ["marshlands"] = -4.0f,
        ["lakeland"] = -6.5f,
    };

    // Region identity → "mountainness" [0,1] — boosts the range mask so a region
    // NAMED mountains/highlands really towers even where no tectonic belt passes.
    private static readonly Dictionary<string, float> GeoMtn = new()
    {
        ["mountains"] = 1.0f,
        ["highlands"] = 0.75f,
        ["caverns"] = 0.5f,
        ["ruins"] = 0.2f,
        ["steppe"] = 0.15f,
        ["forest"] = 0.1f,
        ["plains"] = 0.05f,
        ["lowlands"] = 0.0f,
        ["marshlands"] = 0.0f,
        ["lakeland"] = 0.0f,
    };

    // Chunk type → small extra elevation nudge (folded into the blurred bias so
    // lake/river chunks deepen a basin smoothly instead of tiling into ponds).
    private static readonly Dictionary<string, float> ChunkBias = new()
    {
        ["rocky_highlands"] = 1.5f,
        ["rocky_forest"] = 0.6f,
        ["quarry"] = 0.4f,
        ["barren_waste"] = 0.2f,
        ["wetland"] = -1.6f,
        ["cursed_marsh"] = -1.6f,
        ["flooded_cave"] = -2.5f,
        ["river"] = -2.6f,
        ["lake"] = -3.6f,
    };

    // Smoothed macro grids (per chunk), indexed [(cy+half)*size + (cx+half)].
    private static float[]? _geoBias;
    private static float[]? _geoMtn;
    private static int _macroSize;
    private static int _macroHalf;

    public static void Init(WorldMap? worldMap, long seed)
    {
        _worldMap = worldMap;
        _seed = seed;

        if (worldMap is null || worldMap.ChunkData.Count == 0)
        {
            _geoBias = null;
            _geoMtn = null;
            _quarries = null;
            _flatLevel = (float)Math.Clamp(Field(SpawnX, SpawnY), 1.8, 6.0);
            return;
        }

        _macroSize = worldMap.WorldSize;
        _macroHalf = _macroSize / 2;
        var bias = new float[_macroSize * _macroSize];
        var mtn = new float[_macroSize * _macroSize];
        // default: gentle plains everywhere ungenerated
        // (0 bias, 0 mountainness — arrays already zero)

        foreach (var (key, geo) in worldMap.ChunkData)
        {
            var identity = worldMap.Regions.TryGetValue(geo.RegionId, out var r)
                ? r.Identity : "plains";
            var b = GeoBias.GetValueOrDefault(identity, 0f)
                    + ChunkBias.GetValueOrDefault(geo.ChunkType, 0f);
            var m = GeoMtn.GetValueOrDefault(identity, 0.05f);
            if (geo.ChunkType.Contains("rock") || geo.ChunkType.Contains("quarry")
                || geo.ChunkType.Contains("barren") || geo.ChunkType.Contains("cave"))
                m = Math.Max(m, 0.4f);
            var i = Idx(key.X, key.Y);
            bias[i] = b;
            mtn[i] = m;
        }

        _geoBias = Blur(bias, 3);   // ~27-tile gradients → boundaries vanish
        _geoMtn = Blur(mtn, 3);

        BuildQuarries(worldMap);
        _flatLevel = (float)Math.Clamp(Field(SpawnX, SpawnY), 1.8, 6.0);
    }

    // ---- consolidated terraced quarry pits -------------------------------
    private sealed record QuarryPit(double Cx, double Cy, double R, double Depth, double RampAng);
    private static List<QuarryPit>? _quarries;
    private const int QuarryTerraces = 5;
    private const double QuarryRampHalf = 0.5;   // ramp wedge half-width (radians)

    /// <summary>Flood-fill quarry chunks (adjacent within ±2 → merged) into a few
    /// LARGE pits, so the land isn't dotted with holes. Each pit is a terraced
    /// open cast with one smooth ramp; depth scales with size so the ramp stays
    /// walkable.</summary>
    private static void BuildQuarries(WorldMap map)
    {
        _quarries = new List<QuarryPit>();
        var q = new HashSet<(int, int)>();
        foreach (var (k, geo) in map.ChunkData)
            if (geo.ChunkType == "quarry") q.Add((k.X, k.Y));

        var visited = new HashSet<(int, int)>();
        foreach (var start in q)
        {
            if (!visited.Add(start)) continue;
            var comp = new List<(int, int)>();
            var stack = new Stack<(int, int)>();
            stack.Push(start);
            while (stack.Count > 0)
            {
                var c = stack.Pop();
                comp.Add(c);
                for (var dy = -2; dy <= 2; dy++)
                    for (var dx = -2; dx <= 2; dx++)
                    {
                        var nb = (c.Item1 + dx, c.Item2 + dy);
                        if (q.Contains(nb) && visited.Add(nb)) stack.Push(nb);
                    }
            }
            double sx = 0, sy = 0;
            foreach (var c in comp) { sx += c.Item1 * 16 + 8; sy += c.Item2 * 16 + 8; }
            var cx = sx / comp.Count;
            var cy = sy / comp.Count;
            var r = 11.0;
            foreach (var c in comp)
                r = Math.Max(r, Math.Sqrt(Math.Pow(c.Item1 * 16 + 8 - cx, 2)
                                          + Math.Pow(c.Item2 * 16 + 8 - cy, 2)) + 11);
            var rampAng = GeoNoise.Hash2D((int)cx, (int)cy, _seed + 8300) * Math.Tau;
            _quarries.Add(new QuarryPit(cx, cy, r, Math.Min(13.0, r * 0.5), rampAng));
        }
    }

    /// <summary>Depth to subtract at (x,y) for the enclosing quarry pit: stepped
    /// terraces around, a smooth walkable ramp through one wedge. 0 if not in a pit.</summary>
    private static double QuarryCarve(double x, double y)
    {
        if (_quarries is null) return 0;
        foreach (var p in _quarries)
        {
            var dx = x - p.Cx;
            var dy = y - p.Cy;
            var r = Math.Sqrt(dx * dx + dy * dy);
            if (r >= p.R) continue;
            var profile = p.Depth * Smooth((float)(1.0 - r / p.R));   // 0 rim → depth centre
            var onRamp = Math.Abs(AngleDifference(Math.Atan2(dy, dx), p.RampAng)) < QuarryRampHalf;
            if (onRamp) return profile;                               // smooth ramp
            var step = p.Depth / QuarryTerraces;
            return Math.Floor(profile / step + 1e-6) * step;          // flat terraces
        }
        return 0;
    }

    private static double AngleDifference(double a, double b)
    {
        var d = a - b;
        while (d > Math.PI) d -= Math.Tau;
        while (d < -Math.PI) d += Math.Tau;
        return d;
    }

    // ---- road corridor: the road IS the ground ----------------------------
    // ONE height authority (the fix for float/clip/intertwine): each road carves a
    // corridor into the field with a real cross-section — a FLAT CROWN at the deck
    // height (its own width), then depth-adaptive graded SHOULDERS (cut banks /
    // fill embankments) that ramp back to natural terrain. H() SNAPS to the deck
    // across the whole crown, so the mesh (sampled from H) is a perfectly flat plane
    // under the road and the ribbon painted on it can't float or clip. Rebuilt (and
    // array-reused) per render window.
    private static float[]? _roadW, _roadH, _roadFlat, _roadNat;
    private static int _rgW, _rgH;
    private static float _rgCell, _rgMinX, _rgMinY;

    // depth-adaptive shoulder: a cut/fill of D units ramps back over max(base, D/BankGrade)
    // so a bank never exceeds BankGrade (~45°) — no vertical wall of terrain beside a road.
    private const float BankGrade = 1.0f;
    // The graded bank ramps a cut/fill back to natural at ~BankGrade (~45deg) over a
    // width that scales with depth, up to this cap. 60 made a deep cut read as a wide
    // graded VALLEY gouged through the hill (the "valley not a tunnel" report); 30 made
    // near-vertical walls. 40 is the middle: cuts stay a modest notch, and because the
    // router now seeks the terrain's natural PASSES and refuses steep faces (there is no
    // open-cut tunnel term any more), deep ridge cuts are rare in the first place.
    private const float MaxShoulder = 40f;

    public static void ClearRoads() { _roadW = null; _roadH = null; _roadFlat = null; _roadNat = null; }

    /// <summary>True (0..1) if a carved road corridor covers this point — used to clip
    /// the painted ribbon to exactly the ground that was carved.</summary>
    public static float RoadWeight(double x, double y) => SampleRoad(x, y).W;

    /// <summary>Rasterise road segments into the corridor grid. Each segment carries
    /// endpoint deck heights + a CROWN half-width (the flat road surface); shoulders
    /// grade back to natural over a depth-adaptive width. <paramref name="shoulder"/>
    /// is the minimum (flat-ground) embankment.</summary>
    public static void SetRoads(
        System.Collections.Generic.List<(Vector2 A, Vector2 B, float Ha, float Hb, float Half)> segs,
        float minX, float minY, float maxX, float maxY, float cell, float shoulder)
    {
        _rgCell = cell; _rgMinX = minX; _rgMinY = minY;
        _rgW = (int)((maxX - minX) / cell) + 2;
        _rgH = (int)((maxY - minY) / cell) + 2;
        var need = _rgW * _rgH;
        if (_roadW is null || _roadH is null || _roadFlat is null || _roadNat is null
            || _roadW.Length != need)
        {
            _roadW = new float[need]; _roadH = new float[need];
            _roadFlat = new float[need]; _roadNat = new float[need];
        }
        else { Array.Clear(_roadW, 0, need); Array.Clear(_roadH, 0, need); Array.Clear(_roadFlat, 0, need); }

        // Natural ground height per corridor cell, computed ONCE (in parallel). The old
        // code called PadHeight() — ~30 noise octaves — for every (segment, cell) pair;
        // near spawn the dense road net overlaps the same cells thousands of times, and
        // that redundant recompute alone was the ~12-16s hitch on a stream-recenter / F6
        // teleport. PadHeight is a pure function of immutable field state here (village
        // pads + quarries are already fixed for this window), so the fill parallelises
        // cleanly and the cached value is bit-identical to the per-cell calls it replaces.
        var nat = _roadNat!;
        int rgW = _rgW; float rgMinX = minX, rgMinY = minY, rgCell = cell;
        System.Threading.Tasks.Parallel.For(0, _rgH, ry =>
        {
            var row = ry * rgW;
            for (var cxi = 0; cxi < rgW; cxi++)
                nat[row + cxi] = (float)PadHeight(rgMinX + (cxi + 0.5f) * rgCell,
                                                  rgMinY + (ry + 0.5f) * rgCell);
        });

        // Rasterise the corridors in parallel by disjoint horizontal BANDS of grid rows.
        // Each band owns a unique row range, so two threads never touch the same cell —
        // no locks, no private buffers, and each cell still sees the segments in the same
        // order (its band processes the whole segment list), so the per-cell max-reduction
        // is bit-identical to the old serial pass. (Near spawn ~1,700 segments each scan a
        // 30-wide corridor; serialised that was the last ~400ms of the recenter hitch.)
        var roadW = _roadW!; var roadH = _roadH!; var roadFlat = _roadFlat!; var natG = nat;
        int gW = _rgW, gH = _rgH;
        int bands = Math.Clamp(System.Environment.ProcessorCount, 1, 16);
        System.Threading.Tasks.Parallel.For(0, bands, band =>
        {
            int y0 = (int)((long)band * gH / bands);
            int y1 = (int)((long)(band + 1) * gH / bands);   // exclusive
            foreach (var s in segs)
            {
                var crown = s.Half;
                var corridor = crown + MaxShoulder;   // bbox uses the max possible bank
                int c0 = Math.Max(0, (int)((Math.Min(s.A.X, s.B.X) - corridor - minX) / cell));
                int c1 = Math.Min(gW - 1, (int)((Math.Max(s.A.X, s.B.X) + corridor - minX) / cell));
                int r0 = Math.Max(y0, (int)((Math.Min(s.A.Y, s.B.Y) - corridor - minY) / cell));
                int r1 = Math.Min(Math.Min(gH - 1, y1 - 1),
                                  (int)((Math.Max(s.A.Y, s.B.Y) + corridor - minY) / cell));
                if (r0 > r1 || c0 > c1) continue;
                var ab = s.B - s.A;
                var len2 = ab.LengthSquared();
                for (var ry = r0; ry <= r1; ry++)
                    for (var cxi = c0; cxi <= c1; cxi++)
                    {
                        var p = new Vector2(minX + (cxi + 0.5f) * cell, minY + (ry + 0.5f) * cell);
                        var t = len2 < 1e-6f ? 0f : Mathf.Clamp((p - s.A).Dot(ab) / len2, 0f, 1f);
                        var dist = p.DistanceTo(s.A + ab * t);
                        if (dist >= corridor) continue;
                        var rh = Mathf.Lerp(s.Ha, s.Hb, t);
                        var idx = ry * gW + cxi;
                        float w, flat;
                        if (dist <= crown) { w = 1f; flat = 1f; }
                        else
                        {
                            // adapt the bank width to how deep the cut/fill is here (cached)
                            var natH = natG[idx];
                            var sh = Mathf.Clamp(Mathf.Abs(natH - rh) / BankGrade, shoulder, MaxShoulder);
                            if (dist > crown + sh) continue;
                            w = Smooth(1f - (dist - crown) / sh); flat = 0f;
                        }
                        if (w > roadW[idx]) { roadW[idx] = w; roadH[idx] = rh; roadFlat[idx] = flat; }
                    }
            }
        });
    }

    private static (float W, float H, float Flat) SampleRoad(double x, double y)
    {
        if (_roadW is null || _roadH is null || _roadFlat is null) return (0f, 0f, 0f);
        var fx = (float)((x - _rgMinX) / _rgCell) - 0.5f;
        var fy = (float)((y - _rgMinY) / _rgCell) - 0.5f;
        if (fx < 0 || fy < 0 || fx >= _rgW - 1 || fy >= _rgH - 1) return (0f, 0f, 0f);
        int x0 = (int)fx, y0 = (int)fy;
        float tx = fx - x0, ty = fy - y0;
        int i00 = y0 * _rgW + x0, i10 = i00 + 1, i01 = i00 + _rgW, i11 = i01 + 1;
        float W(float a, float b, float c, float d) =>
            (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
        return (W(_roadW[i00], _roadW[i10], _roadW[i01], _roadW[i11]),
                W(_roadH[i00], _roadH[i10], _roadH[i01], _roadH[i11]),
                W(_roadFlat[i00], _roadFlat[i10], _roadFlat[i01], _roadFlat[i11]));
    }

    // ---- village terracing: a flat shelf carved under each settlement ---------
    // So a mountain village sits on a level part of the slope (like a real terrace)
    // instead of sprawling down one whole face. Each pad flattens the ground to a
    // fixed level within Radius, blended back to the natural slope over Blend.
    // Rebuilt per render window (few settlements in view → iterated directly in H,
    // same pattern as the quarry pits).
    private readonly record struct VillagePad(double Cx, double Cz, double Radius,
                                              double Level, double Blend);
    private static List<VillagePad>? _villagePads;

    public static void ClearVillagePads() => _villagePads = null;

    /// <summary>Install the settlement shelves for the current window: each is
    /// (centre x, centre z, flat radius, shelf level, blend margin).</summary>
    public static void SetVillagePads(
        System.Collections.Generic.List<(double Cx, double Cz, double Radius,
                                         double Level, double Blend)> pads)
    {
        if (pads.Count == 0) { _villagePads = null; return; }
        var list = new List<VillagePad>(pads.Count);
        foreach (var p in pads)
            list.Add(new VillagePad(p.Cx, p.Cz, p.Radius, p.Level, p.Blend));
        _villagePads = list;
    }

    private static int Idx(int cx, int cy) =>
        (Math.Clamp(cy, -_macroHalf, _macroHalf - 1) + _macroHalf) * _macroSize
        + (Math.Clamp(cx, -_macroHalf, _macroHalf - 1) + _macroHalf);

    private static float[] Blur(float[] src, int passes)
    {
        var a = src;
        var b = new float[src.Length];
        for (var p = 0; p < passes; p++)
        {
            for (var cy = -_macroHalf; cy < _macroHalf; cy++)
                for (var cx = -_macroHalf; cx < _macroHalf; cx++)
                {
                    float sum = 0;
                    var n = 0;
                    for (var oy = -1; oy <= 1; oy++)
                        for (var ox = -1; ox <= 1; ox++)
                        {
                            sum += a[Idx(cx + ox, cy + oy)];
                            n++;
                        }
                    b[Idx(cx, cy)] = sum / n;
                }
            (a, b) = (b, a);
        }
        return a;
    }

    private static float SampleMacro(float[] grid, double x, double y)
    {
        var fx = x / 16.0 - 0.5;
        var fy = y / 16.0 - 0.5;
        var cx0 = (int)Math.Floor(fx);
        var cy0 = (int)Math.Floor(fy);
        var tx = (float)(fx - cx0);
        var ty = (float)(fy - cy0);
        var v00 = grid[Idx(cx0, cy0)];
        var v10 = grid[Idx(cx0 + 1, cy0)];
        var v01 = grid[Idx(cx0, cy0 + 1)];
        var v11 = grid[Idx(cx0 + 1, cy0 + 1)];
        return (v00 * (1 - tx) + v10 * tx) * (1 - ty)
             + (v01 * (1 - tx) + v11 * tx) * ty;
    }

    private static string ChunkTypeAt(int cx, int cy) =>
        _worldMap?.GetChunkData(cx, cy)?.ChunkType ?? "forest";

    /// <summary>A chunk that gets a carved, roofed cave grotto (CaveSystem
    /// decorates the same chunks): any cave chunk type, or a caverns region.</summary>
    public static bool IsCaveChunk(int cx, int cy)
    {
        var geo = _worldMap?.GetChunkData(cx, cy);
        if (geo is null) return false;
        var t = geo.ChunkType;
        if (t is "cave" or "deep_cave" or "crystal_cavern" or "flooded_cave")
            return true;
        return _worldMap!.Regions.TryGetValue(geo.RegionId, out var r)
               && r.Identity == "caverns";
    }

    public static bool IsFloodedCave(int cx, int cy) =>
        _worldMap?.GetChunkData(cx, cy)?.ChunkType == "flooded_cave";

    /// <summary>Only a FRACTION of cave chunks actually get a carved grotto + boulder
    /// ring, so a caverns region reads as occasional cave mouths instead of a bubble-
    /// wrap carpet (the old code carved + ringed EVERY cave chunk — ~10% of the whole
    /// world). Shared by the height carve (below) and CaveSystem so the bowl and the
    /// boulders always agree on where a grotto is.</summary>
    public static bool GrottoAt(int cx, int cy) =>
        IsCaveChunk(cx, cy) && GeoNoise.Hash2D(cx, cy, _seed + 4242) < 0.10;

    // ---- the continuous world field (no spawn-flat override) ----
    private static double Field(double x, double y)
    {
        var s = _seed;

        // Domain warp → long, sweeping sinuous ranges/rivers (wider = lower freq).
        // MEGASCALE (4×): a colossal, long warp so massifs sweep across the map.
        const double warp = 460.0;   // wider massif sweep → broader, less wall-like ranges
        var wx = x + GeoNoise.FractalNoise2D(x * 0.0001875, y * 0.0001875, s + 4101, 2) * warp;
        var wy = y + GeoNoise.FractalNoise2D((x + 1700) * 0.0001875, (y - 1700) * 0.0001875,
                                             s + 4102, 2) * warp;

        // Regional swell — broad rises and basins so one stretch of country sits higher
        // than the next (the large-scale variety you travel across). The +offset floats
        // most land comfortably above the datum instead of half-drowning it.
        var baseLand = 8.0 + GeoNoise.FractalNoise2D(x * 0.0018, y * 0.0018, s + 11, 4) * 22.0;

        // RANGE MASK — GEOGRAPHY-DRIVEN. Mountains rise ONLY where the certified
        // region says so (mountains / highlands / caverns), never wherever a noise
        // belt happens to wander: geoM (region mountain-ness) sets the envelope, and
        // the belt only sculpts ridge/valley STRUCTURE INSIDE a range. Plains, forest
        // and lowlands get ~0 range → hills at most, so the map honors its geography.
        var geoM = _geoMtn is not null ? SampleMacro(_geoMtn, x, y) : 0.0;
        var beltRaw = GeoNoise.FractalNoise2D(wx * 0.00026, wy * 0.00026, s + 21, 3);   // wider belts
        var belt = beltRaw * 0.5 + 0.5;                                  // [0,1]
        var envelope = Clamp01(geoM * 1.4 - 0.1);                        // region gate
        var mask = Smooth((float)(envelope * (0.45 + belt * 0.55)));

        // spawn envelope: suppress ranges near origin so the start is always walkable.
        var dsp = Math.Sqrt((x - SpawnX) * (x - SpawnX) + (y - SpawnY) * (y - SpawnY));
        var spawnFade = Clamp01((dsp - SpawnClear) / SpawnFalloff);
        mask *= (float)spawnFade;

        // Range height: long warped ridged crests. Broadened (lower freq) and only
        // lightly crest-shaped so massifs are WIDE and gently-flanked rather than sharp
        // spikes — a road can switchback up them and the player can climb.
        var ridge = RidgedFractal(wx * 0.00055, wy * 0.00055, s + 31, 5);
        ridge = ridge * ridge * (2.4 - 1.4 * ridge);
        var range = ridge * mask * RangeAmp;

        // Passes: broad notches carve walkable routes through the belts (deepened so
        // massifs break into shoulders instead of one continuous vertical wall).
        var passF = GeoNoise.FractalNoise2D(wx * 0.00045, wy * 0.00045, s + 51, 2);
        var pass = Smooth((float)Channel(passF, 0.075));
        range -= pass * mask * (RangeAmp * 0.82);
        if (range < 0) range = 0;

        // Geography elevation bias (lowlands/lakeland dip below the water datum).
        var geoBias = _geoBias is not null ? SampleMacro(_geoBias, x, y) : 0.0;

        // Rivers: winding carved channels that link basins; avoid high ranges.
        var riverF = GeoNoise.FractalNoise2D(wx * 0.0006, wy * 0.0006, s + 61, 3);
        var river = Smooth((float)Channel(riverF, 0.045));
        var riverCarve = river * RiverDepth * (1.0 - mask * 0.7);

        var raw = SeaBase + baseLand + range + geoBias - riverCarve;

        // WALKING-SCALE landforms — layered so the ground always gives you something at
        // the scale you actually move: hills you crest every ~60 tiles, and knolls/dells
        // every ~20. Lightly kept on mountain flanks (hillFactor) so massifs read solid.
        var hillFactor = Clamp01(1.0 - mask * 0.7);
        raw += GeoNoise.FractalNoise2D(x * 0.008, y * 0.008, s + 91, 3) * 16.0 * hillFactor;
        raw += GeoNoise.FractalNoise2D(x * 0.022, y * 0.022, s + 92, 2) * 9.0 * hillFactor;

        // Rocky detail: jagged crests only where rocky (ranges / cliffs) — also faded
        // near spawn so the starting basin stays smooth.
        var rocky = Clamp01(mask + geoM * 0.4);
        if (rocky > 0.02)
            raw += RidgedFractal(x * 0.012, y * 0.012, s + 71, 5) * rocky * DetailAmp * spawnFade;

        // Fine texture everywhere.
        raw += GeoNoise.ValueNoise2D(x * 0.25, y * 0.25, s + 81) * 0.35;

        // Quarry clusters: a large TERRACED open-pit (stepped rings + one smooth
        // walkable ramp), consolidated across adjacent quarry chunks.
        var cxk = (int)Math.Floor(x / 16.0);
        var cyk = (int)Math.Floor(y / 16.0);
        var quarry = QuarryCarve(x, y);
        if (quarry > 0.0)
        {
            raw -= quarry;
        }
        // Cave/cavern chunks: a walkable grotto bowl with a flat chamber floor — only
        // at the sparse GrottoAt chunks, so caverns regions aren't pockmarked all over.
        else if (GrottoAt(cxk, cyk))
        {
            var lx = x - (cxk * 16 + 8);
            var ly = y - (cyk * 16 + 8);
            var r = Math.Sqrt(lx * lx + ly * ly);
            if (r < CaveRadius)
            {
                var coneT = 1.0 - r / CaveRadius;            // 0 rim → 1 centre
                var floor = IsFloodedCave(cxk, cyk)
                    ? WaterLevel - 1.6 : WaterLevel + 1.2;
                var carved = Math.Max(raw - CaveDepth * coneT, floor);
                if (carved < raw) raw = carved;
            }
        }

        return raw;
    }

    /// <summary>NATURAL elevation — Field + spawn-flat only, WITHOUT village terracing
    /// or road grading. Village shelf levels sample this so a shelf sits at the
    /// mountainside's own natural height (not on top of a road/another shelf).</summary>
    public static double NaturalHeight(double x, double y)
    {
        var raw = Field(x, y);
        var d = Math.Sqrt((x - SpawnX) * (x - SpawnX) + (y - SpawnY) * (y - SpawnY));
        if (d < SpawnFlatRadius)
            raw = _flatLevel;
        else if (d < SpawnFlatRadius + SpawnBlend)
        {
            var t = (float)((d - SpawnFlatRadius) / SpawnBlend);
            raw = _flatLevel + (raw - _flatLevel) * Smooth(t);
        }
        return raw;
    }

    /// <summary>Natural field + spawn-flat + VILLAGE TERRACING, but WITHOUT road
    /// grading — the surface roads are draped onto / graded toward. The road deck profile
    /// samples this so it is independent of the road grade it will itself produce.</summary>
    public static double PadHeight(double x, double y)
    {
        var raw = NaturalHeight(x, y);
        // village terrace: flatten a shelf so a mountain village sits on a flat part
        // of the slope, its edge blended back into the mountainside.
        if (_villagePads is not null)
            foreach (var v in _villagePads)
            {
                var dx = x - v.Cx; var dz = y - v.Cz;
                var dist = Math.Sqrt(dx * dx + dz * dz);
                if (dist >= v.Radius + v.Blend) continue;
                var t = dist <= v.Radius
                    ? 1.0 : Smooth((float)(1.0 - (dist - v.Radius) / v.Blend));
                raw = raw * (1.0 - t) + v.Level * t;
            }
        return raw;
    }

    /// <summary>Smooth elevation at a world tile position (the single source of
    /// truth): natural field + spawn-flat + village terracing (<see cref="PadHeight"/>)
    /// then ROAD GRADING (the ground flattens toward every road, fading out over its
    /// graded embankment).</summary>
    public static float H(double x, double y)
    {
        var raw = PadHeight(x, y);
        var (rw, rh, flat) = SampleRoad(x, y);
        if (rw > 0.001f)
            // flat crown → SNAP to the deck (a perfectly level plane under the road, so
            // the mesh can't bulge and the ribbon can't float); shoulder → ramp by weight.
            raw = flat > 0.5f ? rh : raw * (1.0 - rw) + rh * rw;
        return (float)raw;
    }

    private static double Clamp01(double v) => v < 0 ? 0 : v > 1 ? 1 : v;
    private static float Smooth(float t) => t * t * (3f - 2f * t);

    /// <summary>[0,1], 1 at the channel centerline, 0 beyond halfWidth.</summary>
    private static double Channel(double fieldVal, double halfWidth) =>
        Math.Max(0.0, 1.0 - Math.Abs(fieldVal) / halfWidth);

    /// <summary>Ridged multifractal in [0,1] (1 at sharp crests) — the mountain
    /// crest generator, giving long jagged ridge lines rather than round bumps.</summary>
    private static double RidgedFractal(double x, double y, long seed, int octaves)
    {
        double total = 0, amp = 1, freq = 1, max = 0;
        for (var i = 0; i < octaves; i++)
        {
            var n = 1.0 - Math.Abs(GeoNoise.ValueNoise2D(x * freq, y * freq,
                                                         seed + i * 31337L));
            n *= n;
            total += n * amp;
            max += amp;
            amp *= 0.5;
            freq *= 2.0;
        }
        return max > 0 ? total / max : 0;
    }

    public static bool IsWater(double x, double y) => H(x, y) < WaterLevel;

    /// <summary>Height the terrain MESH presents (bilinear of the 4 integer-tile
    /// vertices) — for the player's catastrophe floor net.</summary>
    public static float HMesh(double x, double y)
    {
        var x0 = Math.Floor(x);
        var y0 = Math.Floor(y);
        var tx = (float)(x - x0);
        var ty = (float)(y - y0);
        var h00 = H(x0, y0);
        var h10 = H(x0 + 1, y0);
        var h01 = H(x0, y0 + 1);
        var h11 = H(x0 + 1, y0 + 1);
        return (h00 * (1 - tx) + h10 * tx) * (1 - ty)
             + (h01 * (1 - tx) + h11 * tx) * ty;
    }
}
