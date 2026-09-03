using Godot;

namespace Game1.Godot;

/// <summary>
/// The crafting layer's shared JUICE + DRAW vocabulary — the seam that turns
/// six flat minigame popups into one cohesive, tactile Workshop. Everything is
/// procedural (no assets): floating score popups, one-shot particle bursts, an
/// animated canvas backdrop, and a set of _Draw() helpers (rounded fills, soft
/// glow, gauges, star ratings, quality bands) so every discipline reads with
/// the same polish. Pure presentation — it owns no game state and never touches
/// the certified craft seam (performance 0..1 is produced by the minigames).
/// </summary>
public static class CraftFx
{
    // ---- Quality bands (mirror RewardCalculator.QualityTier thresholds) -----
    // 0.25 Fine · 0.50 Superior · 0.75 Masterwork · 0.90 Legendary. The colors
    // reuse the rarity palette so a Legendary craft reads gold everywhere.
    public static readonly (double Min, string Name, Color Col)[] QualityBands =
    {
        (0.00, "Normal",     UiTheme.Rarity["common"]),
        (0.25, "Fine",       UiTheme.Rarity["uncommon"]),
        (0.50, "Superior",   UiTheme.Rarity["rare"]),
        (0.75, "Masterwork", UiTheme.Rarity["epic"]),
        (0.90, "Legendary",  UiTheme.Rarity["legendary"]),
    };

    /// <summary>Band (name, color, 0..4 index) for a performance score.</summary>
    public static (string Name, Color Col, int Index) Band(double perf)
    {
        var i = 0;
        for (var b = QualityBands.Length - 1; b >= 0; b--)
            if (perf >= QualityBands[b].Min) { i = b; break; }
        return (QualityBands[i].Name, QualityBands[i].Col, i);
    }

    public static Color QualityColor(double perf) => Band(perf).Col;

    /// <summary>Color for a named quality string (from CraftResult.Quality).</summary>
    public static Color QualityColorByName(string quality)
    {
        foreach (var (_, name, col) in QualityBands)
            if (string.Equals(name, quality, System.StringComparison.OrdinalIgnoreCase))
                return col;
        return UiTheme.Rarity["common"];
    }

    // ------------------------------------------------------------- POPUPS ----

    /// <summary>Rising, fading text over a play surface (score / "PERFECT!").
    /// Parented to <paramref name="parent"/> so <paramref name="pos"/> is in that
    /// control's local space — no coordinate conversion needed.</summary>
    public static void Popup(CanvasItem parent, Vector2 pos, string text, Color col,
                             int size = 22, float rise = 46f)
    {
        if (parent is not Node parentNode) return;
        var label = new Label
        {
            Text = text,
            Position = pos - new Vector2(60, 12),
            CustomMinimumSize = new Vector2(120, 0),
            HorizontalAlignment = HorizontalAlignment.Center,
            MouseFilter = Control.MouseFilterEnum.Ignore,
            ZIndex = 50,
        };
        label.AddThemeFontSizeOverride("font_size", size);
        label.AddThemeColorOverride("font_color", col);
        label.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0, 0.9f));
        label.AddThemeConstantOverride("outline_size", 6);
        parentNode.AddChild(label);

        var tween = label.CreateTween();
        tween.TweenProperty(label, "position:y", label.Position.Y - rise, 0.75f)
             .SetTrans(Tween.TransitionType.Cubic).SetEase(Tween.EaseType.Out);
        tween.Parallel().TweenProperty(label, "modulate:a", 0f, 0.75f)
             .SetTrans(Tween.TransitionType.Quad).SetEase(Tween.EaseType.In).SetDelay(0.18f);
        tween.TweenCallback(Callable.From(label.QueueFree));
    }

    // ------------------------------------------------------------ PARTICLES --

    /// <summary>One-shot particle burst at a local point on a play surface. Auto
    /// frees when the emission finishes. glow=true → additive spark look.</summary>
    public static void Burst(CanvasItem parent, Vector2 pos, Color col, int count = 18,
                             float speed = 220f, float lifetime = 0.7f, float size = 4f,
                             float gravity = 380f, bool glow = true)
    {
        if (parent is not Node parentNode) return;
        var p = new CpuParticles2D
        {
            Position = pos,
            Amount = Mathf.Max(1, count),
            Lifetime = lifetime,
            OneShot = true,
            Explosiveness = 1f,
            Direction = new Vector2(0, -1),
            Spread = 180f,
            Gravity = new Vector2(0, gravity),
            InitialVelocityMin = speed * 0.4f,
            InitialVelocityMax = speed,
            ScaleAmountMin = size * 0.5f,
            ScaleAmountMax = size,
            Color = col,
            ZIndex = 40,
        };
        if (glow) p.Material = new CanvasItemMaterial { BlendMode = CanvasItemMaterial.BlendModeEnum.Add };
        parentNode.AddChild(p);
        p.Emitting = true;
        p.Finished += p.QueueFree;
    }

    /// <summary>A steady ambient emitter (embers, bubbles, motes) for the stage
    /// backdrop. Caller owns the node (add it, position it, free with the stage).</summary>
    public static CpuParticles2D Ambient(Color col, int amount, float riseSpeed,
                                         Vector2 area, bool glow = true, float size = 4f)
    {
        var p = new CpuParticles2D
        {
            Amount = Mathf.Max(1, amount),
            Lifetime = 3.2f,
            Preprocess = 2.0f,
            Direction = new Vector2(0, -1),
            Spread = 24f,
            Gravity = new Vector2(0, -riseSpeed),
            InitialVelocityMin = riseSpeed * 0.4f,
            InitialVelocityMax = riseSpeed * 0.9f,
            ScaleAmountMin = size * 0.4f,
            ScaleAmountMax = size,
            Color = col,
            EmissionShape = CpuParticles2D.EmissionShapeEnum.Rectangle,
            EmissionRectExtents = area,
            ZIndex = 1,
        };
        if (glow) p.Material = new CanvasItemMaterial { BlendMode = CanvasItemMaterial.BlendModeEnum.Add };
        return p;
    }

    // -------------------------------------------------------- DRAW HELPERS ---

    /// <summary>Rounded filled rect (optionally bordered) inside a _Draw().</summary>
    public static void RoundRect(CanvasItem ci, Rect2 r, Color bg, Color? border = null,
                                 int borderW = 0, int radius = 8)
    {
        var sb = UiTheme.Box(bg, border, borderW, radius);
        sb.Draw(ci.GetCanvasItem(), r);
    }

    /// <summary>Soft additive glow: concentric translucent discs, brightest at
    /// the center. Cheap "bloom" for a _Draw surface.</summary>
    public static void Glow(CanvasItem ci, Vector2 c, float radius, Color col, int layers = 6)
    {
        for (var i = layers; i >= 1; i--)
        {
            var t = i / (float)layers;
            var a = col.A * (1f - t) * 0.5f;
            ci.DrawCircle(c, radius * t, new Color(col.R, col.G, col.B, a));
        }
    }

    /// <summary>Horizontal fill bar with a rounded track (progress / meters).</summary>
    public static void Bar(CanvasItem ci, Rect2 r, float fill01, Color track, Color fillCol,
                           int radius = 6)
    {
        RoundRect(ci, r, track, null, 0, radius);
        var w = r.Size.X * Mathf.Clamp(fill01, 0f, 1f);
        if (w > 1)
            RoundRect(ci, new Rect2(r.Position, new Vector2(w, r.Size.Y)), fillCol, null, 0, radius);
    }

    /// <summary>A row of star glyphs (difficulty / rating). Filled then hollow.</summary>
    public static void Stars(CanvasItem ci, Vector2 at, int filled, int total, float size,
                             Color col, float gap = 6f)
    {
        for (var i = 0; i < total; i++)
        {
            var c = at + new Vector2(i * (size + gap) + size * 0.5f, size * 0.5f);
            var on = i < filled;
            DrawStar(ci, c, size * 0.5f, on ? col : new Color(col.R, col.G, col.B, 0.22f));
        }
    }

    /// <summary>A 5-point star polygon (filled).</summary>
    public static void DrawStar(CanvasItem ci, Vector2 c, float r, Color col)
    {
        var pts = new Vector2[10];
        for (var i = 0; i < 10; i++)
        {
            var ang = -Mathf.Pi / 2f + i * Mathf.Pi / 5f;
            var rad = (i % 2 == 0) ? r : r * 0.44f;
            pts[i] = c + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * rad;
        }
        ci.DrawColoredPolygon(pts, col);
    }

    /// <summary>An arc segment as a thick stroke (gauge ticks, dials).</summary>
    public static void Arc(CanvasItem ci, Vector2 c, float radius, float fromRad, float toRad,
                           Color col, float width = 3f, int steps = 48)
        => ci.DrawArc(c, radius, fromRad, toRad, steps, col, width, true);

    // ------------------------------------------- EXTRA PRIMITIVES (shared) ---
    // Small pure-2D signatures every minigame re-invents inline (expanding rings, flowing streaks, cracks, wakes).
    // Kept here so Smithing / Refining / Engineering / Enchanting share ONE set instead of copy-pasting five. Phase
    // args are 0..1. All build on plain DrawArc/DrawLine/DrawCircle — no shaders.

    /// <summary>A full ring (thin circle outline) — surge telegraphs, resonance halos, gauge rings.</summary>
    public static void Ring(CanvasItem ci, Vector2 c, float radius, Color col, float width = 2f, int steps = 48)
        => ci.DrawArc(c, Mathf.Max(0.5f, radius), 0, Mathf.Tau, steps, col, width, true);

    /// <summary>An EXPANDING, FADING ring at phase 0..1 (a surge/impact wave): radius grows by spread, alpha → 0.</summary>
    public static void RingPulse(CanvasItem ci, Vector2 c, float baseR, float phase01, Color col, float width = 2.5f, float spread = 0.7f)
    {
        var p = Mathf.Clamp(phase01, 0f, 1f);
        Ring(ci, c, baseR * (1f + p * spread), new Color(col.R, col.G, col.B, col.A * (1f - p)), width);
    }

    /// <summary>A tapering STREAK (thick→thin, fading line) — signal flow, sparks, polish strokes.</summary>
    public static void Streak(CanvasItem ci, Vector2 from, Vector2 to, Color col, float width = 3f, int segs = 6)
    {
        var prev = from;
        for (var i = 1; i <= segs; i++)
        {
            var t = i / (float)segs; var pt = from.Lerp(to, t);
            ci.DrawLine(prev, pt, new Color(col.R, col.G, col.B, col.A * (1f - t * 0.85f)), Mathf.Max(0.5f, width * (1f - t * 0.8f)));
            prev = pt;
        }
    }

    /// <summary>A wavering WISP (curling translucent line flowing from an origin along dir) — vapour, essence, drift.
    /// seed varies the waver deterministically; wobble is the lateral amplitude in px; phase 0..1 animates it.</summary>
    public static void Wisp(CanvasItem ci, Vector2 origin, Vector2 dir, float len, Color col, float phase, float width = 2f, float wobble = 8f, int seed = 0, int segs = 8)
    {
        var d = dir.LengthSquared() > 1e-6f ? dir.Normalized() : Vector2.Up;
        var perp = new Vector2(-d.Y, d.X); var prev = origin;
        for (var i = 1; i <= segs; i++)
        {
            var t = i / (float)segs;
            var sway = Mathf.Sin(phase * Mathf.Tau + t * 5f + seed * 1.7f) * wobble * t;
            var pt = origin + d * (len * t) + perp * sway;
            ci.DrawLine(prev, pt, new Color(col.R, col.G, col.B, col.A * (1f - t)), Mathf.Max(0.5f, width * (1f - t * 0.6f)));
            prev = pt;
        }
    }

    /// <summary>A jagged CRACK / fracture line from an origin along dir — brittle / shatter / stress cues.</summary>
    public static void Crack(CanvasItem ci, Vector2 origin, Vector2 dir, float len, Color col, float width = 2f, int seed = 0, int segs = 5)
    {
        var d = dir.LengthSquared() > 1e-6f ? dir.Normalized() : Vector2.Right;
        var perp = new Vector2(-d.Y, d.X); var prev = origin;
        for (var i = 1; i <= segs; i++)
        {
            var t = i / (float)segs;
            var jag = (Hash01(seed * 31 + i) - 0.5f) * len * 0.28f;
            var pt = origin + d * (len * t) + perp * jag;
            ci.DrawLine(prev, pt, new Color(col.R, col.G, col.B, col.A * (1f - t * 0.5f)), Mathf.Max(1f, width * (1f - t * 0.6f)));
            prev = pt;
        }
    }

    /// <summary>A drifting WAKE — a short trail of shrinking, fading discs along a path (movement/history trail).</summary>
    public static void Wake(CanvasItem ci, Vector2 from, Vector2 to, Color col, float size = 5f, int count = 6)
    {
        for (var i = 0; i < count; i++)
        {
            var t = i / (float)Mathf.Max(1, count - 1); var pt = from.Lerp(to, t);
            ci.DrawCircle(pt, size * (1f - t * 0.7f), new Color(col.R, col.G, col.B, col.A * (1f - t)));
        }
    }

    /// <summary>Points of an ellipse polygon (for DrawColoredPolygon — soft shadows, specular highlights, bands).</summary>
    public static Vector2[] Ellipse(Vector2 c, float rx, float ry, int n = 18)
    {
        var p = new Vector2[Mathf.Max(3, n)];
        for (var i = 0; i < p.Length; i++) { var a = Mathf.Tau * i / p.Length; p[i] = c + new Vector2(Mathf.Cos(a) * rx, Mathf.Sin(a) * ry); }
        return p;
    }

    /// <summary>Deterministic 0..1 hash of an int — stable per-index jitter (no Math.Random; safe for resume/replay).</summary>
    public static float Hash01(int i) { var x = Mathf.Sin(i * 12.9898f) * 43758.5453f; return x - Mathf.Floor(x); }

    // -------------------------------------------------------- BACKDROP -------

    private static Shader? _backdrop;
    private const string BackdropCode = @"
shader_type canvas_item;
uniform vec4 top_color : source_color = vec4(0.06, 0.07, 0.11, 1.0);
uniform vec4 bottom_color : source_color = vec4(0.02, 0.02, 0.04, 1.0);
uniform vec4 glow_color : source_color = vec4(0.90, 0.50, 0.20, 1.0);
uniform vec2 glow_pos = vec2(0.5, 0.66);
uniform float glow_strength = 0.55;
float h(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
void fragment() {
    vec2 uv = UV;
    vec3 col = mix(top_color.rgb, bottom_color.rgb, smoothstep(0.0, 1.0, uv.y));
    float d = distance(uv * vec2(1.7, 1.0), glow_pos * vec2(1.7, 1.0));
    float g = smoothstep(0.9, 0.0, d) * glow_strength;
    col += glow_color.rgb * g;
    float n = h(floor(uv * 90.0) + floor(vec2(TIME * 3.0, TIME * 1.0)));
    col += (n - 0.5) * 0.015;
    // soft edge vignette
    float vig = smoothstep(1.15, 0.35, distance(uv, vec2(0.5)));
    col *= mix(0.72, 1.0, vig);
    COLOR = vec4(col, 1.0);
}
";

    /// <summary>Animated per-discipline backdrop material for the stage.</summary>
    public static ShaderMaterial Backdrop(Color top, Color bottom, Color glow,
                                          Vector2 glowPos, float glowStrength = 0.55f)
    {
        _backdrop ??= new Shader { Code = BackdropCode };
        var m = new ShaderMaterial { Shader = _backdrop };
        m.SetShaderParameter("top_color", top);
        m.SetShaderParameter("bottom_color", bottom);
        m.SetShaderParameter("glow_color", glow);
        m.SetShaderParameter("glow_pos", glowPos);
        m.SetShaderParameter("glow_strength", glowStrength);
        return m;
    }

    /// <summary>
    /// NO-SHADER fallback backdrop: a vertical banded gradient (top→bottom) + a soft radial glow + a gentle vignette,
    /// painted with plain draw calls inside a _Draw(). This is the safety net for the ONE shader in the crafting stack
    /// (<see cref="Backdrop"/>): if that shader ever fails to compile (old GPU / headless), the overlay still shows a
    /// coherent staged gradient instead of a flat black/garbage card. <paramref name="glowPos"/> is in 0..1 UV space.
    /// </summary>
    public static void GradientBackdrop(CanvasItem ci, Vector2 size, Color top, Color bottom, Color glow,
                                        Vector2 glowPos, float glowStrength = 0.5f, int bands = 48)
    {
        var W = Mathf.Max(1f, size.X); var H = Mathf.Max(1f, size.Y);
        for (var i = 0; i < bands; i++)
        {
            var t = i / (float)bands; var st = t * t * (3 - 2 * t);   // smoothstep top→bottom
            ci.DrawRect(new Rect2(0, H * t, W, H / bands + 1.5f), top.Lerp(bottom, st));
        }
        var gp = new Vector2(glowPos.X * W, glowPos.Y * H);
        for (var i = 10; i >= 1; i--) { var t = i / 10f; ci.DrawCircle(gp, Mathf.Max(W, H) * 0.5f * t, new Color(glow.R, glow.G, glow.B, glowStrength * 0.05f * (1 - t))); }
        for (var i = 6; i >= 1; i--) { var t = i / 6f; ci.DrawRect(new Rect2(0, 0, W, H * 0.05f * t), new Color(0, 0, 0, 0.05f)); ci.DrawRect(new Rect2(0, H * (1 - 0.05f * t), W, H * 0.05f * t), new Color(0, 0, 0, 0.05f)); }
    }
}
