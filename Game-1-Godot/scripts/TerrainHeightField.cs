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
    }

    /// <summary>Elevation at world tile position (quantized 0.5 steps).</summary>
    public static float H(double x, double y)
    {
        var cx = (int)Math.Floor(x / 16.0);
        var cy = (int)Math.Floor(y / 16.0);
        var chunkType = _worldMap?.GetChunkData(cx, cy)?.ChunkType ?? "forest";
        var (baseH, amp) = Profile.GetValueOrDefault(chunkType, (1.0f, 0.6f));
        if (amp <= 0) return baseH;
        var noise = GeoNoise.ValueNoise2D(x * 0.08, y * 0.08, _seed + 909090);
        var h = baseH + noise * amp;
        return (float)(Math.Round(h * 2.0) / 2.0);
    }
}
