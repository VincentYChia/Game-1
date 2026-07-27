using Game1.Core.World;
using Game1.Core.World.Geography;

namespace Game1.Godot;

/// <summary>
/// P11 True 3D — the deterministic elevation field. This is the one layer
/// with NO Python oracle by design: verticality is the 2D→3D-necessitated
/// addition (ADR-6 amendment). Heights derive purely from the certified
/// world (geo chunk type + seed + certified ValueNoise2D), quantized to
/// 0.5-tile steps; chunk-type base differences create natural cliffs.
/// The SIM stays planar — height is presentation plus the combat/fall
/// rules layered on top.
/// </summary>
public static class TerrainHeightField
{
    private static WorldMap? _worldMap;
    private static long _seed;

    /// <summary>Player spawn tile — a flat, hostile-free safe zone.</summary>
    public const double SpawnX = 8;
    public const double SpawnY = 8;
    public const double SpawnFlatRadius = 20;   // fully flat within this
    private const double SpawnBlend = 10;        // blend to natural beyond
    private static float _flatLevel = 1.0f;

    private static readonly Dictionary<string, (float Base, float Amp)> Profile = new()
    {
        ["rocky_highlands"] = (4.0f, 1.5f),
        ["quarry"] = (2.5f, 1.5f),
        ["rocky_forest"] = (2.0f, 1.0f),
        ["barren_waste"] = (1.5f, 0.8f),
        ["overgrown_ruins"] = (1.2f, 0.6f),
        ["forest"] = (1.0f, 0.6f),
        ["dense_thicket"] = (1.0f, 0.6f),
        ["cave"] = (0.5f, 0.4f),
        ["deep_cave"] = (0.5f, 0.4f),
        ["crystal_cavern"] = (0.5f, 0.4f),
        ["flooded_cave"] = (0.25f, 0.3f),
        ["wetland"] = (0.25f, 0.3f),
        ["cursed_marsh"] = (0.25f, 0.3f),
        ["lake"] = (-0.6f, 0.0f),
        ["river"] = (-0.6f, 0.0f),
    };

    public static void Init(WorldMap? worldMap, long seed)
    {
        _worldMap = worldMap;
        _seed = seed;
        // Flat level = the spawn chunk's base elevation (clamped above water)
        var sc = worldMap?.GetChunkData(0, 0)?.ChunkType ?? "forest";
        _flatLevel = Math.Max(0.5f, Profile.GetValueOrDefault(sc, (1.0f, 0.6f)).Item1);
    }

    /// <summary>Elevation at world tile position (quantized 0.5 steps). A
    /// flat safe zone is carved around the spawn point (item 3).</summary>
    public static float H(double x, double y)
    {
        var cx = (int)Math.Floor(x / 16.0);
        var cy = (int)Math.Floor(y / 16.0);
        var chunkType = _worldMap?.GetChunkData(cx, cy)?.ChunkType ?? "forest";
        var (baseH, amp) = Profile.GetValueOrDefault(chunkType, (1.0f, 0.6f));

        float raw;
        if (amp <= 0) raw = baseH;
        else
        {
            var noise = GeoNoise.ValueNoise2D(x * 0.08, y * 0.08, _seed + 909090);
            raw = (float)(baseH + noise * amp);
        }

        // Flatten toward _flatLevel near spawn, blending out to natural terrain
        var d = Math.Sqrt((x - SpawnX) * (x - SpawnX) + (y - SpawnY) * (y - SpawnY));
        if (d < SpawnFlatRadius)
            raw = _flatLevel;
        else if (d < SpawnFlatRadius + SpawnBlend)
        {
            var t = (float)((d - SpawnFlatRadius) / SpawnBlend);
            raw = _flatLevel + (raw - _flatLevel) * t;
        }

        return (float)(Math.Round(raw * 2.0) / 2.0);
    }
}
