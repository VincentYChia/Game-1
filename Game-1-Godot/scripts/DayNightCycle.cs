using Godot;

namespace Game1.Godot;

/// <summary>
/// A slow ambient day/night sweep (atmosphere only — no gameplay night). Drives
/// the retained sun + ProceduralSkyMaterial + Environment each frame from four
/// keyframed moods (night → dawn → day → dusk) and a smooth solar arc. The night
/// keeps a non-zero ambient floor and a dim-navy (never black) sky so the world
/// stays readable. All typed C# setters — no shader, fully build-verifiable.
/// </summary>
public partial class DayNightCycle : Node
{
    /// <summary>Real seconds for one full day. Long + gentle by default.</summary>
    [Export] public float DayLengthSeconds { get; set; } = 600f;
    [Export(PropertyHint.Range, "0,1")] public float StartFraction { get; set; } = 0.35f;

    private readonly DirectionalLight3D _sun;
    private readonly ProceduralSkyMaterial _sky;
    private readonly global::Godot.Environment _env;
    private float _frac;

    private struct Key
    {
        public float T;
        public Color Sun, SkyTop, SkyHoriz, GroundHoriz, Fog;
        public float SunEnergy, Ambient;
    }

    private readonly Key[] _keys;

    /// <summary>Normalized time of day in [0,1) — 0 = midnight, 0.5 = noon.
    /// Read by AmbientLife to gate fireflies to the night.</summary>
    public float Fraction => _frac;

    public DayNightCycle(DirectionalLight3D sun, ProceduralSkyMaterial sky,
                         global::Godot.Environment env)
    {
        _sun = sun;
        _sky = sky;
        _env = env;
        _frac = StartFraction;

        _keys = new[]
        {
            new Key
            {
                T = 0.00f, SunEnergy = 0.05f, Ambient = 0.18f,           // deep night (floor)
                Sun = new Color(0.35f, 0.42f, 0.70f),
                SkyTop = new Color(0.03f, 0.05f, 0.12f),
                SkyHoriz = new Color(0.08f, 0.10f, 0.20f),
                GroundHoriz = new Color(0.05f, 0.06f, 0.10f),
                Fog = new Color(0.06f, 0.08f, 0.16f),
            },
            new Key
            {
                T = 0.23f, SunEnergy = 0.9f, Ambient = 0.42f,            // dawn (warm)
                Sun = new Color(1.0f, 0.70f, 0.45f),
                SkyTop = new Color(0.30f, 0.45f, 0.72f),
                SkyHoriz = new Color(0.95f, 0.68f, 0.50f),
                GroundHoriz = new Color(0.55f, 0.50f, 0.48f),
                Fog = new Color(0.85f, 0.70f, 0.62f),
            },
            new Key
            {
                T = 0.50f, SunEnergy = 1.3f, Ambient = 0.62f,           // noon
                Sun = new Color(1.0f, 0.96f, 0.87f),
                SkyTop = new Color(0.28f, 0.48f, 0.78f),
                SkyHoriz = new Color(0.72f, 0.80f, 0.86f),
                GroundHoriz = new Color(0.68f, 0.72f, 0.74f),
                Fog = new Color(0.76f, 0.83f, 0.90f),
            },
            new Key
            {
                T = 0.77f, SunEnergy = 0.9f, Ambient = 0.42f,           // dusk (amber)
                Sun = new Color(1.0f, 0.55f, 0.32f),
                SkyTop = new Color(0.20f, 0.24f, 0.52f),
                SkyHoriz = new Color(0.95f, 0.55f, 0.42f),
                GroundHoriz = new Color(0.45f, 0.38f, 0.42f),
                Fog = new Color(0.80f, 0.55f, 0.50f),
            },
        };
        Apply(_frac);
    }

    public override void _Process(double delta)
    {
        _frac += (float)delta / Mathf.Max(1f, DayLengthSeconds);
        _frac -= Mathf.Floor(_frac);   // wrap to [0,1)
        Apply(_frac);
    }

    private void Apply(float f)
    {
        var n = _keys.Length;
        var i = n - 1;
        for (var k = 0; k < n; k++)
            if (_keys[k].T <= f) i = k;
        var a = _keys[i];
        var b = _keys[(i + 1) % n];
        var span = (b.T - a.T + 1f) % 1f;
        if (span <= 0f) span = 1f;
        var local = ((f - a.T + 1f) % 1f) / span;

        Color L(Color x, Color y) => x.Lerp(y, local);
        _sky.SkyTopColor = L(a.SkyTop, b.SkyTop);
        _sky.SkyHorizonColor = L(a.SkyHoriz, b.SkyHoriz);
        _sky.GroundHorizonColor = L(a.GroundHoriz, b.GroundHoriz);
        _sun.LightColor = L(a.Sun, b.Sun);
        _sun.LightEnergy = Mathf.Lerp(a.SunEnergy, b.SunEnergy, local);
        _env.AmbientLightEnergy = Mathf.Lerp(a.Ambient, b.Ambient, local);
        _env.FogLightColor = L(a.Fog, b.Fog);

        // solar arc: elevation over the day + a gentle east→west yaw sweep so
        // shadows actually crawl. Sun hidden below the horizon at night.
        var elev = 80f * Mathf.Sin((f - 0.25f) * Mathf.Tau);
        _sun.RotationDegrees = new Vector3(-elev, -110f + f * 220f, 0f);
        _sun.Visible = elev > -2f;
    }
}
