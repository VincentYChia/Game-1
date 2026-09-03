using Godot;

namespace Game1.Godot;

/// <summary>
/// SHARED COLOUR + NO-SHADER-GRADIENT helpers for the crafting minigames (extracted from the Alchemy rebuild).
///
/// These are the "keep complex blends vivid" and "fake a smooth gradient without a shader" tools every discipline
/// needs. Alchemy owned private copies of all of them; they now live here so Smithing / Refining / Engineering /
/// Enchanting share one set instead of copy-pasting five slightly-different versions.
///
/// All pure presentation — no game state, no shaders (a shader that silently fails to compile renders as flat
/// garbage, so the whole crafting layer stays on plain <see cref="CanvasItem"/> draw calls).
/// </summary>
public static class CraftColor
{
    /// <summary>Toward black by <paramref name="a"/> (0 = unchanged, 1 = black). Multiplicative, so hue is kept.</summary>
    public static Color Darken(Color c, float a) => new(c.R * (1 - a), c.G * (1 - a), c.B * (1 - a), c.A);

    /// <summary>Toward white by <paramref name="a"/> (a soft tint that also lifts value + drops saturation).</summary>
    public static Color Lighten(Color c, float a) => new(Mathf.Lerp(c.R, 1, a), Mathf.Lerp(c.G, 1, a), Mathf.Lerp(c.B, 1, a), c.A);

    /// <summary>Add <paramref name="a"/> to each channel (a flat brightness lift that keeps saturation better than Lighten).</summary>
    public static Color Brighten(Color c, float a) => new(Mathf.Clamp(c.R + a, 0, 1), Mathf.Clamp(c.G + a, 0, 1), Mathf.Clamp(c.B + a, 0, 1), c.A);

    /// <summary>
    /// DE-MUDDY a heavily-blended colour so it stays vivid and distinct instead of averaging out to grey. Leans the
    /// colour toward a DOMINANT reference hue (e.g. the dominant channel's family colour) and floors saturation and
    /// value. This is the single most important colour tool for multi-channel disciplines — without it, a brew/ingot
    /// with 4-6 mixed essences collapses to a dull tan.
    /// </summary>
    public static Color DeMuddy(Color color, Color dominant, float lean = 0.22f, float floorS = 0.5f, float floorV = 0.58f)
    {
        var m = color.Lerp(dominant, lean);
        return Color.FromHsv(m.H, Mathf.Max(m.S, floorS), Mathf.Max(m.V, floorV), color.A);
    }

    /// <summary>
    /// Fake a SMOOTH RADIAL gradient (no shaders): a solid dark base disc, then many translucent lighter discs that
    /// SHRINK toward a light offset, so their overlaps build a smooth centre-to-rim falloff instead of visible bands.
    /// Used to make a flat circle read as a lit sphere (the Alchemy marble body). <paramref name="lightOff"/> is the
    /// offset of the highlight from centre (e.g. up-left for a top-left light).
    /// </summary>
    public static void RadialGrad(CanvasItem ci, Vector2 c, float radius, Vector2 lightOff, Color dark, Color light, int steps = 16)
    {
        ci.DrawCircle(c, radius, dark);
        for (var i = 1; i <= steps; i++)
        {
            var t = i / (float)steps;
            var rr = radius * (1f - t * 0.6f);
            var cc = dark.Lerp(light, t);
            ci.DrawCircle(c + lightOff * t, rr, new Color(cc.R, cc.G, cc.B, 0.42f));
        }
    }
}
