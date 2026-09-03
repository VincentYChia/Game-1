using Godot;

namespace Game1.Godot;

/// <summary>
/// SHARED STATE-VISUAL toolkit for the crafting minigames (extracted from the Alchemy rebuild — it owned all of
/// these as private <c>Fx*</c> methods on <c>AlchemyMinigame</c>).
///
/// A "named state" is the shared vocabulary of BOTH mechanics AND visuals: a finite enumerated list where each state
/// has a magnitude 0..1, one distinct visual, and a scored effect. This class is the RENDERING MACHINERY — a family
/// of pure-2D signatures (rising plumes, flames, molten veins, ripples, crystals, vines, …) each driven by a colour +
/// a magnitude so several can fire at once and still read. Each discipline supplies its OWN
/// <c>(name, look, hue, effect-bias)</c> table (the content); the drawing is shared here.
///
/// Two ways to use it:
///   • Fine control — call a specific primitive (<see cref="Flame"/>, <see cref="Crystals"/>, …) per named state,
///     exactly as Alchemy does (17 states → 15 primitives).
///   • Coarse/shared — map a state to a <see cref="Look"/> and call <see cref="DrawLook"/>; the dispatcher picks a
///     representative primitive. New disciplines that don't need Alchemy's fidelity use this.
///
/// magnitude <c>m</c> ∈ 0..1 drives count / size / reach / alpha. <c>anim</c> is a free-running seconds clock. All
/// draws are plain <see cref="CanvasItem"/> calls (no shaders).
/// </summary>
public static class StateVisual
{
    /// <summary>The coarse visual primitive a state renders as (keeps the shared animation set tiny; colour +
    /// magnitude do the rest). A discipline's state table maps each state → one of these.</summary>
    public enum Look { None = 0, Rise, Ring, Veins, Lava, Shards, Ripple, Core }

    /// <summary>Dispatch a coarse <see cref="Look"/> to a representative primitive. The shared entry point for
    /// disciplines that map states → look rather than hand-picking a primitive per state.</summary>
    public static void DrawLook(CanvasItem ci, Look look, Vector2 center, float radius, float magnitude, Color col, float anim)
    {
        var m = Mathf.Clamp(magnitude, 0f, 1f);
        if (m < 0.06f) return;
        switch (look)
        {
            case Look.Rise:   Plume(ci, center, radius, col, m, anim); break;
            case Look.Ring:   RippleOut(ci, center, radius, col, m, anim); break;
            case Look.Veins:  Vines(ci, center, radius, col, m, anim); break;
            case Look.Lava:   Molten(ci, center, radius, col, m, anim); break;
            case Look.Shards: Crystals(ci, center, radius, col, m, anim); break;
            case Look.Ripple: RippleOut(ci, center, radius, col, m, anim); break;
            case Look.Core:   CoreGlow(ci, center, radius, col, m, anim); break;
        }
    }

    // ---- the primitives: distinct big signatures (form + colour + screen-region so several read at once) ----

    /// <summary>Rising translucent VAPOUR/steam plume above the object. dark=true tints in the state colour (smoke);
    /// else it's pale white with a coloured core (steam). dens/sz scale the count and puff size.</summary>
    public static void Plume(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim, float dens = 1f, float sz = 1f, bool dark = false)
    {
        var n = 3 + (int)(m * 7 * dens);
        for (var i = 0; i < n; i++)
        {
            var ph = Mathf.PosMod(anim * (0.5f + 0.25f * m) + i * 0.618f, 1f);
            var x = c.X + Mathf.Sin(anim * 1.5f + i * 2.1f) * R * 0.45f * (0.4f + ph);
            var y = c.Y - R * 0.5f - ph * R * (1.6f + m * 0.9f);
            var rad = (R * 0.12f + ph * R * 0.34f) * sz * (0.6f + m * 0.6f); var a = (1 - ph) * 0.5f * m;
            if (dark) ci.DrawCircle(new Vector2(x, y), rad, new Color(col.R, col.G, col.B, a));
            else { ci.DrawCircle(new Vector2(x, y), rad, new Color(0.95f, 0.97f, 1f, a * 0.85f)); ci.DrawCircle(new Vector2(x, y), rad * 0.6f, new Color(col.R, col.G, col.B, a * 0.5f)); }
        }
    }

    /// <summary>Drifting glowing SPORES rising and spreading (life+air).</summary>
    public static void Spore(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        var n = 3 + (int)(m * 6);
        for (var i = 0; i < n; i++) { var ph = Mathf.PosMod(anim * 0.35f + i * 0.4f, 1f); var x = c.X + (CraftFx.Hash01(i) - 0.5f) * R * 1.6f + Mathf.Sin(anim + i) * R * 0.2f; var y = c.Y - R * 0.3f - ph * R * 1.2f; ci.DrawCircle(new Vector2(x, y), 1.5f + 2.5f * m, new Color(col.R, col.G, col.B, (1 - ph) * 0.55f * m)); ci.DrawCircle(new Vector2(x, y), 0.9f, new Color(1, 1, 0.9f, (1 - ph) * 0.6f * m)); }
    }

    /// <summary>Horizontal drifting MIST bands crossing the object (water+air).</summary>
    public static void Mist(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        for (var i = 0; i < 4; i++) { var ph = Mathf.PosMod(anim * 0.3f + i * 0.25f, 1f); var x = c.X - R + ph * R * 2f; var y = c.Y - R * 0.4f + Mathf.Sin(anim + i * 2f) * R * 0.25f; ci.DrawColoredPolygon(CraftFx.Ellipse(new Vector2(x, y), R * 0.5f, R * 0.16f, 14), new Color(col.R, col.G, col.B, (0.5f - Mathf.Abs(ph - 0.5f)) * 0.45f * m)); }
    }

    /// <summary>Kicked-up DUST motes swirling upward (earth+air).</summary>
    public static void Dust(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        var n = 4 + (int)(m * 8);
        for (var i = 0; i < n; i++) { var ph = Mathf.PosMod(anim * 0.8f + i * 0.35f, 1f); var a = i * 2.4f; var x = c.X + Mathf.Cos(a) * R * (0.6f + ph * 0.9f); var y = c.Y - ph * R * 0.9f + Mathf.Sin(a) * R * 0.3f; ci.DrawCircle(new Vector2(x, y), 1f + 1.6f * (1 - ph), new Color(col.R, col.G, col.B, (1 - ph) * 0.55f * m)); }
    }

    /// <summary>Licking FLAMES off the top with a dark rim for separation. dark=true = a shadow-fire variant with a
    /// pulsing aura; else warm sparks rise.</summary>
    public static void Flame(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim, float height = 1f, bool dark = false)
    {
        var n = 3 + (int)(m * 4); var baseY = c.Y - R * 0.5f;
        var outer = dark ? col : new Color(1f, 0.45f, 0.12f); var inner = dark ? new Color(1f, 0.5f, 0.35f) : new Color(1f, 0.9f, 0.4f);
        for (var i = 0; i < n; i++)
        {
            var bx = c.X + (i - (n - 1) / 2f) * R * 0.3f + Mathf.Sin(anim * 4f + i) * R * 0.06f;
            var h = R * (0.7f + m * 0.9f) * height * (0.8f + 0.35f * Mathf.Sin(anim * 9f + i * 1.7f)); var wdt = R * 0.2f;
            var tip = new Vector2(bx + Mathf.Sin(anim * 6f + i) * R * 0.1f, baseY - h);
            ci.DrawColoredPolygon(new[] { new Vector2(bx - wdt * 1.3f, baseY + 2), new Vector2(tip.X, tip.Y - 2), new Vector2(bx + wdt * 1.3f, baseY + 2) }, new Color(0.04f, 0.02f, 0.0f, 0.4f * m)); // dark rim = separation
            ci.DrawColoredPolygon(new[] { new Vector2(bx - wdt, baseY), tip, new Vector2(bx + wdt, baseY) }, new Color(outer.R, outer.G, outer.B, 0.6f * m));
            ci.DrawColoredPolygon(new[] { new Vector2(bx - wdt * 0.5f, baseY), new Vector2(bx, baseY - h * 0.7f), new Vector2(bx + wdt * 0.5f, baseY) }, new Color(inner.R, inner.G, inner.B, 0.82f * m));
        }
        if (dark) { var pp = Mathf.PosMod(anim * 1.4f, 1f); ci.DrawArc(c, R * (1f + pp * 0.4f), 0, Mathf.Tau, 44, new Color(col.R, col.G, col.B, (1 - pp) * 0.55f * m), 3f); }
        else for (var i = 0; i < (int)(m * 6); i++) { var ph = Mathf.PosMod(anim * 1.2f + CraftFx.Hash01(i) * 3f, 1f); ci.DrawCircle(new Vector2(c.X + (CraftFx.Hash01(i * 2) - 0.5f) * R, baseY - ph * R * 1.4f), 1.5f * (1 - ph), new Color(1f, 0.8f, 0.3f, (1 - ph) * 0.85f * m)); }
    }

    /// <summary>Glowing MOLTEN veins fanning out from the core, plus a drip (fire+earth, hot).</summary>
    public static void Molten(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        for (var i = 0; i < 4; i++) { var a = Mathf.Pi * (0.15f + i * 0.23f); var prev = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * R * 0.2f; for (var t = 1; t <= 4; t++) { var tt = t / 4f; var jit = (CraftFx.Hash01(i * 4 + t) - 0.5f) * R * 0.12f; var pt = c + new Vector2(Mathf.Cos(a) * R * 0.82f * tt, Mathf.Sin(a) * R * 0.82f * tt + jit); var glow = 0.5f + 0.5f * Mathf.Sin(anim * 5f + i); ci.DrawLine(prev, pt, new Color(1f, 0.5f + 0.3f * glow, 0.1f, 0.78f * m), 2.6f - tt); prev = pt; } }
        ci.DrawCircle(c + new Vector2(0, R * 0.1f), R * 0.3f * (0.8f + 0.2f * Mathf.Sin(anim * 7f)), new Color(1f, 0.6f, 0.2f, 0.35f * m));
        var dph = Mathf.PosMod(anim * 0.5f, 1f); ci.DrawCircle(new Vector2(c.X + R * 0.2f, c.Y + R * 0.4f + dph * R * 0.5f), 2.5f * m, new Color(1f, 0.55f, 0.15f, (1 - dph) * 0.85f * m));
    }

    /// <summary>Charred SOOT ring + a rising scorch trail (fire+life burning).</summary>
    public static void Scorch(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        for (var i = 0; i < 8; i++) { var a = i * Mathf.Tau / 8 + anim * 0.1f; var d = R * (0.75f + 0.15f * Mathf.Sin(anim * 3f + i)); ci.DrawCircle(c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * d, R * 0.14f * m, new Color(0.08f, 0.05f, 0.05f, 0.55f * m)); }
        var prev = new Vector2(c.X, c.Y - R * 0.4f); for (var t = 1; t <= 8; t++) { var tt = t / 8f; var pt = new Vector2(c.X + Mathf.Sin(anim * 2f + tt * 6f) * R * 0.3f, c.Y - R * 0.4f - tt * R * 1.1f); ci.DrawLine(prev, pt, new Color(0.22f, 0.16f, 0.16f, (1 - tt) * 0.45f * m), 3f * (1 - tt) + 1f); prev = pt; }
    }

    /// <summary>Expanding concentric RIPPLES + rising droplets (water quench / any wave).</summary>
    public static void RippleOut(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        for (var i = 0; i < 3; i++) { var pp = Mathf.PosMod(anim * 1.0f + i / 3f, 1f); ci.DrawArc(c, R * (0.4f + pp * 0.7f), 0, Mathf.Tau, 40, new Color(col.R, col.G, col.B, (1 - pp) * 0.55f * m), 2.5f); }
        for (var i = 0; i < (int)(m * 5); i++) { var a = i * 1.3f; var ph = Mathf.PosMod(anim * 1.5f + CraftFx.Hash01(i), 1f); ci.DrawCircle(c + new Vector2(Mathf.Cos(a), -Mathf.Abs(Mathf.Sin(a))) * R * (0.6f + ph * 0.5f), 1.5f * (1 - ph), new Color(col.R, col.G, col.B, (1 - ph) * 0.7f * m)); }
    }

    /// <summary>Settling SEDIMENT layers low in the object + a few falling grains (water+earth silt).</summary>
    public static void Sediment(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        for (var k = 0; k < 3; k++) { var yy = c.Y + R * (0.55f - k * 0.16f); var settle = Mathf.Sin(anim * 1.5f + k) * R * 0.02f; ci.DrawColoredPolygon(CraftFx.Ellipse(new Vector2(c.X, yy + settle), R * (0.8f - k * 0.12f), R * 0.1f, 16), new Color(col.R * 0.85f, col.G * 0.72f, col.B * 0.55f, (0.42f + 0.15f * k) * m)); }
        for (var i = 0; i < (int)(m * 4); i++) { var ph = Mathf.PosMod(anim * 0.9f + CraftFx.Hash01(i) * 2f, 1f); ci.DrawCircle(new Vector2(c.X + (CraftFx.Hash01(i * 3) - 0.5f) * R * 1.2f, c.Y - R * 0.2f + ph * R * 0.7f), 1.3f, new Color(col.R, col.G, col.B, (1 - ph) * 0.5f * m)); }
    }

    /// <summary>Growing VINES radiating out (down=true drapes them downward; flower=true buds tips) — life states.</summary>
    public static void Vines(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim, bool down = false, bool flower = false)
    {
        var n = 3 + (int)(m * 3); var grow = Mathf.Clamp(m * 1.2f, 0.3f, 1f);
        for (var v = 0; v < n; v++)
        {
            var baseA = down ? Mathf.Pi * (0.32f + v * 0.36f / n) : v * Mathf.Tau / n + anim * 0.2f; var prev = c;
            for (var t = 1; t <= 7; t++) { var tt = t / 7f; if (tt > grow) break; var a = baseA + Mathf.Sin(anim * 2f + v + tt * 5f) * 0.2f; var pt = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * R * 0.85f * tt; ci.DrawLine(prev, pt, new Color(col.R, col.G, col.B, 0.6f * m), 3f - tt * 1.5f); prev = pt; }
            var tip = CraftColor.Lighten(col, 0.3f);
            if (flower && grow > 0.6f) for (var p = 0; p < 5; p++) { var pa = p * Mathf.Tau / 5f + anim; ci.DrawColoredPolygon(CraftFx.Ellipse(prev + new Vector2(Mathf.Cos(pa), Mathf.Sin(pa)) * R * 0.06f, R * 0.05f, R * 0.03f, 8), new Color(tip.R, tip.G, tip.B, 0.7f * m)); }
            else ci.DrawCircle(prev, R * 0.05f, new Color(col.R, col.G, col.B, 0.6f * m));
        }
    }

    /// <summary>Spreading ROT blotches + rising decay bubbles (life+shadow).</summary>
    public static void Rot(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        for (var i = 0; i < (int)(3 + m * 5); i++) { var a = i * 2.1f; var d = R * (0.3f + 0.5f * CraftFx.Hash01(i)); var pulse = 0.5f + 0.5f * Mathf.Sin(anim * 3f + i); ci.DrawCircle(c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * d, R * (0.1f + 0.08f * pulse) * m, new Color(col.R, col.G * 0.9f, col.B * 0.5f, 0.48f * m)); }
        for (var i = 0; i < (int)(m * 4); i++) { var ph = Mathf.PosMod(anim * 1.1f + CraftFx.Hash01(i * 2) * 2f, 1f); ci.DrawArc(new Vector2(c.X + (CraftFx.Hash01(i) - 0.5f) * R, c.Y - ph * R * 0.8f), (1.5f + ph * 3f) * m, 0, Mathf.Tau, 12, new Color(col.R, col.G, col.B * 0.6f, (1 - ph) * 0.6f * m), 1.5f); }
    }

    /// <summary>CRYSTAL shards growing inward from the rim, white-lit edges (earth+shadow / any crystallise).</summary>
    public static void Crystals(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        var n = 4 + (int)(m * 5); var grow = Mathf.Clamp(m * 1.3f, 0.3f, 1f);
        for (var i = 0; i < n; i++) { var a = i * Mathf.Tau / n + anim * 0.05f; var dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a)); var tip = c + dir * R * (1f - 0.55f * grow); var baseP = c + dir * R * 1.02f; var wid = new Vector2(-dir.Y, dir.X) * R * 0.1f; ci.DrawColoredPolygon(new[] { baseP - wid * 1.5f, tip - dir * 2f, baseP + wid * 1.5f }, new Color(0.03f, 0.0f, 0.05f, 0.35f * m)); ci.DrawColoredPolygon(new[] { baseP - wid, tip, baseP + wid }, new Color(col.R, col.G, col.B, 0.55f * m)); ci.DrawLine(baseP, tip, new Color(1, 1, 1, 0.42f * m), 1.2f); }
    }

    /// <summary>Inward SWIRL spiral + a dark core (water+shadow brine / any vortex).</summary>
    public static void Swirl(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        var prev = c; for (var t = 1; t <= 24; t++) { var tt = t / 24f; var a = anim * 1.5f + tt * 12f; var rr = R * 0.85f * (1 - tt * 0.7f); var pt = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * rr; ci.DrawLine(prev, pt, new Color(col.R, col.G, col.B, (1 - tt) * 0.55f * m), 2.5f * (1 - tt) + 0.5f); prev = pt; }
        ci.DrawCircle(c, R * 0.2f, new Color(col.R * 0.5f, col.G * 0.5f, col.B * 0.6f, 0.4f * m));
    }

    /// <summary>A pulsing radiant CORE glow + ring (temper / any steady-energy state).</summary>
    public static void CoreGlow(CanvasItem ci, Vector2 c, float R, Color col, float m, float anim)
    {
        var pulse = 0.7f + 0.3f * Mathf.Sin(anim * 3.5f);
        for (var i = 0; i < 5; i++) { var t = i / 5f; ci.DrawCircle(c, R * 0.55f * (1 - t) * (0.9f + 0.1f * pulse), new Color(col.R, col.G, col.B, 0.32f * m * (1 - t) * pulse)); }
        ci.DrawArc(c, R * 0.6f, 0, Mathf.Tau, 40, new Color(col.R, col.G, col.B, 0.35f * m * pulse), 2f);
    }
}
