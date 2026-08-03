using Game1.Core.World;
using Game1.Core.World.Geography;

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
    private const double SpawnBlend = 14;
    private static float _flatLevel = 2.6f;

    public const float WaterLevel = 0.2f;

    // ---- world-shape constants (the primary drama tuning surface) ----
    private const double SeaBase = 3.2;    // datum: plains float above water
    private const double BaseAmp = 2.3;    // gentle continental roll
    private const double RangeAmp = 52.0;  // peak range height (the "huge" read)
    private const double RiverDepth = 6.5; // how deep carved rivers cut
    private const double DetailAmp = 9.0;  // jagged rocky crest detail

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

        _flatLevel = (float)Math.Clamp(Field(SpawnX, SpawnY), 1.8, 6.0);
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

    // ---- the continuous world field (no spawn-flat override) ----
    private static double Field(double x, double y)
    {
        var s = _seed;

        // Domain warp → sinuous ranges/rivers (grandiose, non-blobby).
        const double warp = 62.0;
        var wx = x + GeoNoise.FractalNoise2D(x * 0.0016, y * 0.0016, s + 4101, 2) * warp;
        var wy = y + GeoNoise.FractalNoise2D((x + 1700) * 0.0016, (y - 1700) * 0.0016,
                                             s + 4102, 2) * warp;

        // Gentle continental base — plains/forest live here, above the datum.
        var baseLand = GeoNoise.FractalNoise2D(x * 0.006, y * 0.006, s + 11, 4) * BaseAmp;

        // Tectonic belt mask: where ranges live (independent of region hashing),
        // reinforced by "mountains/highlands" geography so named ranges tower.
        var beltRaw = GeoNoise.FractalNoise2D(wx * 0.0032, wy * 0.0032, s + 21, 3);
        var belt = beltRaw * 0.5 + 0.5;                                  // [0,1]
        var geoM = _geoMtn is not null ? SampleMacro(_geoMtn, x, y) : 0.0;
        var mask = Smooth((float)Clamp01((belt - 0.52) * 2.6 + geoM * 1.1));

        // Range height: long warped ridged crests, crest-sharpened.
        var ridge = RidgedFractal(wx * 0.010, wy * 0.010, s + 31, 5);
        ridge = ridge * ridge * (3.0 - 2.0 * ridge);
        var range = ridge * mask * RangeAmp;

        // Passes: broad notches carve walkable routes through the belts.
        var passF = GeoNoise.FractalNoise2D(wx * 0.0042, wy * 0.0042, s + 51, 2);
        var pass = Smooth((float)Channel(passF, 0.06));
        range -= pass * mask * (RangeAmp * 0.72);
        if (range < 0) range = 0;

        // Geography elevation bias (lowlands/lakeland dip below the water datum).
        var geoBias = _geoBias is not null ? SampleMacro(_geoBias, x, y) : 0.0;

        // Rivers: winding carved channels that link basins; avoid high ranges.
        var riverF = GeoNoise.FractalNoise2D(wx * 0.0055, wy * 0.0055, s + 61, 3);
        var river = Smooth((float)Channel(riverF, 0.045));
        var riverCarve = river * RiverDepth * (1.0 - mask * 0.7);

        var raw = SeaBase + baseLand + range + geoBias - riverCarve;

        // Rocky detail: jagged crests only where rocky (ranges / cliffs).
        var rocky = Clamp01(mask + geoM * 0.4);
        if (rocky > 0.02)
            raw += RidgedFractal(x * 0.05, y * 0.05, s + 71, 5) * rocky * DetailAmp;

        // Fine texture everywhere.
        raw += GeoNoise.ValueNoise2D(x * 0.25, y * 0.25, s + 81) * 0.35;

        // Quarry chunks: an excavated pit (chunk-local bowl).
        var cxk = (int)Math.Floor(x / 16.0);
        var cyk = (int)Math.Floor(y / 16.0);
        if (ChunkTypeAt(cxk, cyk) == "quarry")
        {
            var lx = x - (cxk * 16 + 8);
            var ly = y - (cyk * 16 + 8);
            var t = Math.Max(0.0, 1.0 - (lx * lx + ly * ly) / (7.0 * 7.0));
            raw -= 5.0 * t;
        }
        // Cave/cavern chunks: a walkable grotto bowl with a flat chamber floor.
        else if (IsCaveChunk(cxk, cyk))
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

    /// <summary>Smooth elevation at a world tile position (the single source of
    /// truth). Applies the flat-spawn override around the origin safe zone.</summary>
    public static float H(double x, double y)
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
