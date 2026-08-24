using Godot;

namespace Game1.Godot;

/// <summary>
/// The project's FIRST shader layer — the seam that makes surfaces LIVE.
///
/// Everything is procedural inline Godot-4 shader code (no external assets): a
/// vertex WIND sway for foliage, an animated WATER surface (Gerstner waves +
/// depth color + shoreline foam), a TERRAIN surface enrichment (reads the baked
/// vertex COLOR, adds fBm variation + cavity AO), and a soft billboard PARTICLE
/// sprite for ambient motes/leaves/fireflies. Shaders compile once and are
/// shared; each material only varies uniforms.
///
/// NOTE: inline shader code compiles on the GPU at RUNTIME, not at `dotnet
/// build`. The C# here is build-verified; the shaders are validated on first
/// live frame. Kept conservative + syntactically strict for that reason.
/// </summary>
public static class ShaderLib
{
    private static Shader? _wind, _water, _terrain, _spriteAdd, _spriteMix;

    // ---------------------------------------------------------------- WIND ---
    private const string WindCode = @"
shader_type spatial;
render_mode cull_disabled, diffuse_burley;
uniform vec4 albedo : source_color = vec4(0.30, 0.45, 0.22, 1.0);
uniform float rough = 0.9;
uniform float wind_strength = 0.14;
uniform float wind_speed = 1.6;
void vertex() {
    vec3 world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    float phase = world.x * 0.35 + world.z * 0.45;
    float g = sin(TIME * wind_speed + phase)
            + 0.35 * sin(TIME * wind_speed * 2.1 + phase * 1.7);
    float mask = clamp(VERTEX.y + 0.5, 0.0, 1.5); // sway grows toward the tip
    VERTEX.x += g * wind_strength * mask;
    VERTEX.z += g * wind_strength * mask * 0.6;
}
void fragment() {
    ALBEDO = albedo.rgb;
    ROUGHNESS = rough;
}
";

    /// <summary>A wind-swaying foliage material (own albedo, shared shader).</summary>
    public static ShaderMaterial Wind(Color albedo, float rough)
    {
        _wind ??= new Shader { Code = WindCode };
        var m = new ShaderMaterial { Shader = _wind };
        m.SetShaderParameter("albedo", albedo);
        m.SetShaderParameter("rough", rough);
        return m;
    }

    // --------------------------------------------------------------- WATER ---
    private const string WaterCode = @"
shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx, depth_draw_never;
uniform float wave_amp = 0.14;
uniform float wave_speed = 0.7;
uniform float depth_scale = 3.0;
uniform vec4 shallow_col : source_color = vec4(0.20, 0.46, 0.50, 1.0);
uniform vec4 deep_col : source_color = vec4(0.04, 0.16, 0.26, 1.0);
uniform vec4 foam_col : source_color = vec4(0.90, 0.95, 0.97, 1.0);
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
varying vec3 v_wpos;
float wv(vec2 p, vec2 d, float t) { return sin(dot(normalize(d), p) * 0.5 + t); }
void vertex() {
    v_wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    float t = TIME * wave_speed;
    float h = wv(v_wpos.xz, vec2(1.0, 0.3), t)
            + 0.5 * wv(v_wpos.xz, vec2(-0.4, 1.0), t * 1.3);
    VERTEX.y += h * wave_amp;
}
void fragment() {
    vec3 n = normalize(cross(dFdx(v_wpos), dFdy(v_wpos)));
    NORMAL = (VIEW_MATRIX * vec4(n, 0.0)).xyz;

    float dsample = texture(depth_tex, SCREEN_UV).r;
    vec4 ndc = vec4(SCREEN_UV * 2.0 - 1.0, dsample, 1.0);
    vec4 vpos = INV_PROJECTION_MATRIX * ndc;
    vpos.xyz /= vpos.w;
    float behind = -vpos.z;          // scene depth behind the water
    float here = -VERTEX.z;          // this fragment (VERTEX is view-space here)
    float thick = clamp((behind - here) / depth_scale, 0.0, 1.0);

    ALBEDO = mix(shallow_col.rgb, deep_col.rgb, thick);
    float foam = smoothstep(0.16, 0.0, behind - here);
    ALBEDO = mix(ALBEDO, foam_col.rgb, foam * 0.7);

    ROUGHNESS = 0.04;
    METALLIC = 0.0;
    SPECULAR = 0.6;
    ALPHA = max(mix(0.72, 0.96, thick), foam * 0.9);
}
";

    public static ShaderMaterial Water()
    {
        _water ??= new Shader { Code = WaterCode };
        return new ShaderMaterial { Shader = _water };
    }

    // ------------------------------------------------------------- TERRAIN ---
    // Reads the baked per-vertex COLOR (rgb = biome/altitude/slope bands, a = a
    // CPU cavity-AO term) and enriches it with procedural fBm variation so the
    // ground stops reading as flat matte. No tangents / normal maps (kept safe).
    private const string TerrainCode = @"
shader_type spatial;
render_mode cull_disabled, diffuse_burley;
uniform float detail_strength = 0.14;
uniform float ao_strength = 0.55;
varying vec3 v_wpos;
float hsh(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    float a = hsh(i), b = hsh(i + vec2(1,0)), c = hsh(i + vec2(0,1)), d = hsh(i + vec2(1,1));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * vnoise(p); p *= 2.0; a *= 0.5; } return v; }
void vertex() { v_wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
    vec3 base = COLOR.rgb;
    float n = fbm(v_wpos.xz * 0.14) * 0.6 + fbm(v_wpos.xz * 0.85) * 0.4;
    base *= mix(1.0 - detail_strength, 1.0 + detail_strength, n);
    float ao = mix(1.0, COLOR.a, ao_strength);
    ALBEDO = clamp(base * ao, vec3(0.0), vec3(1.0));
    ROUGHNESS = 0.94;
}
";

    public static ShaderMaterial TerrainSurface()
    {
        _terrain ??= new Shader { Code = TerrainCode };
        return new ShaderMaterial { Shader = _terrain };
    }

    // ------------------------------------------------------------ PARTICLE ---
    // Soft round billboard sprite from UV (no texture). Two blend variants:
    // additive (glowy motes/fireflies) and alpha (soft leaves/mist).
    private static string SpriteCode(string blend) => $@"
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, {blend};
uniform vec4 tint : source_color = vec4(1.0);
void vertex() {{
    float sx = length(MODEL_MATRIX[0].xyz);
    float sy = length(MODEL_MATRIX[1].xyz);
    MODELVIEW_MATRIX = VIEW_MATRIX * mat4(
        INV_VIEW_MATRIX[0] * sx, INV_VIEW_MATRIX[1] * sy,
        INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}}
void fragment() {{
    float d = distance(UV, vec2(0.5));
    float a = smoothstep(0.5, 0.0, d);
    ALBEDO = tint.rgb;
    EMISSION = tint.rgb * a;
    ALPHA = a * tint.a;
}}
";

    /// <summary>Soft billboard particle material. glow=true → additive (motes,
    /// fireflies); glow=false → alpha (leaves, mist, spray).</summary>
    public static ShaderMaterial Sprite(Color tint, bool glow)
    {
        if (glow) _spriteAdd ??= new Shader { Code = SpriteCode("blend_add") };
        else _spriteMix ??= new Shader { Code = SpriteCode("blend_mix") };
        var m = new ShaderMaterial { Shader = glow ? _spriteAdd : _spriteMix };
        m.SetShaderParameter("tint", tint);
        return m;
    }
}
