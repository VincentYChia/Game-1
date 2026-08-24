using System;
using System.Collections.Generic;
using Godot;

namespace Game1.Godot;

/// <summary>
/// The moving, living layer of the world. Parented to the player (so it follows
/// for free, no recenter rebuild): five always-alive GPUParticles emitters
/// (dust motes / drifting leaves / night fireflies / low mist / water spray)
/// whose amounts CROSS-FADE by the biome and time of day, plus subtle wildlife —
/// birds wheeling overhead, butterflies flitting in green country, and fish that
/// occasionally break the surface of a nearby lake.
///
/// Particle draw uses an inline procedural sprite ShaderMaterial (no texture);
/// the PROCESS material is a plain ParticleProcessMaterial (the safe 4.4 path —
/// a ShaderMaterial must never be the process material).
/// </summary>
public partial class AmbientLife : Node3D
{
    private readonly Func<int, int, string> _biomeAt;
    private readonly Func<float>? _dayFrac;
    private readonly RandomNumberGenerator _rng = new();

    private GpuParticles3D _motes = null!, _leaves = null!, _fireflies = null!,
                          _mist = null!, _spray = null!;
    private readonly List<Node3D> _birds = new();
    private readonly List<MeshInstance3D> _butterflies = new();
    private double _fishTimer = 2.0;

    public AmbientLife(Func<int, int, string> biomeAt, Func<float>? dayFrac = null)
    {
        _biomeAt = biomeAt;
        _dayFrac = dayFrac;
        _rng.Seed = 0xA11BE;
    }

    public override void _Ready()
    {
        //                        tint                         glow  amt  size  offset            box(WxHxD)      gravity
        _motes = Emitter(new Color(1.00f, 0.95f, 0.72f), true, 60, 0.09f, new Vector3(0, 6, 0), new Vector3(40, 14, 40), 0.02f);
        _leaves = Emitter(new Color(0.72f, 0.55f, 0.26f), false, 44, 0.18f, new Vector3(0, 7, 0), new Vector3(34, 12, 34), 0.9f);
        _fireflies = Emitter(new Color(0.80f, 1.00f, 0.42f), true, 40, 0.12f, new Vector3(0, 1.6f, 0), new Vector3(30, 3, 30), 0.0f);
        _mist = Emitter(new Color(0.86f, 0.90f, 0.95f), false, 26, 1.70f, new Vector3(0, 0.6f, 0), new Vector3(42, 2, 42), 0.0f);
        _spray = Emitter(new Color(0.92f, 0.97f, 1.00f), true, 30, 0.07f, new Vector3(0, 0.5f, 0), new Vector3(36, 2, 36), -0.6f);

        BuildBirds();
        BuildButterflies();
    }

    private GpuParticles3D Emitter(Color tint, bool glow, int amount, float size,
        Vector3 offset, Vector3 box, float gravity)
    {
        var pm = new ParticleProcessMaterial
        {
            EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box,
            EmissionBoxExtents = box * 0.5f,
            Gravity = new Vector3(0, -gravity, 0),
            Direction = new Vector3(0, gravity >= 0 ? -1 : 1, 0),
            Spread = 40f,
            InitialVelocityMin = 0.05f,
            InitialVelocityMax = 0.35f,
            TurbulenceEnabled = true,
            TurbulenceNoiseStrength = 0.5f,
            TurbulenceNoiseScale = 1.2f,
            TurbulenceInfluenceMin = 0.1f,
            TurbulenceInfluenceMax = 0.45f,
            ScaleMin = 0.6f,
            ScaleMax = 1.4f,
        };
        var e = new GpuParticles3D
        {
            Amount = amount,
            Lifetime = 6.0,
            Preprocess = 3.0,
            LocalCoords = false,       // particles stay in world as the player moves
            AmountRatio = 0f,          // biome/time-gated each frame
            Emitting = false,
            Position = offset,
            ProcessMaterial = pm,
            DrawPass1 = new QuadMesh
            {
                Size = new Vector2(size, size),
                Material = ShaderLib.Sprite(tint, glow),
            },
            VisibilityAabb = new Aabb(-box, box * 2f),
        };
        AddChild(e);
        return e;
    }

    public override void _Process(double delta)
    {
        var p = GlobalPosition;
        var biome = _biomeAt((int)Mathf.Floor(p.X / 16f), (int)Mathf.Floor(p.Z / 16f));
        var woody = biome.Contains("forest") || biome.Contains("thicket")
                    || biome.Contains("overgrown");
        var marsh = biome.Contains("wetland") || biome.Contains("marsh");
        var green = woody || biome.Contains("plains") || biome == "forest";
        var nearWater = TerrainHeightField.H(p.X, p.Z) < TerrainHeightField.WaterLevel + 3f;
        var f = _dayFrac?.Invoke() ?? 0.5f;
        var night = f < 0.2f || f > 0.82f;

        Fade(_motes, night ? 0.15f : 0.5f, delta);
        Fade(_leaves, woody ? 0.85f : 0f, delta);
        Fade(_fireflies, night ? 0.7f : 0f, delta);
        Fade(_mist, marsh ? 0.9f : nearWater ? 0.4f : 0f, delta);
        Fade(_spray, nearWater ? 0.7f : 0f, delta);

        UpdateBirds();
        UpdateButterflies(green);
        UpdateFish(delta, p);
    }

    private static void Fade(GpuParticles3D e, float target, double dt)
    {
        e.AmountRatio = Mathf.MoveToward(e.AmountRatio, target, (float)dt * 0.7f);
        e.Emitting = e.AmountRatio > 0.02f;
    }

    // ------------------------------------------------------------- birds ----
    private void BuildBirds()
    {
        var mat = new StandardMaterial3D { AlbedoColor = new Color(0.14f, 0.14f, 0.17f) };
        for (var i = 0; i < 4; i++)
        {
            var bird = new Node3D();
            bird.AddChild(new MeshInstance3D
            {
                Mesh = new BoxMesh { Size = new Vector3(1.4f, 0.05f, 0.4f) },
                MaterialOverride = mat,
            });
            AddChild(bird);
            _birds.Add(bird);
        }
    }

    private void UpdateBirds()
    {
        var t = (float)Time.GetTicksMsec() / 1000f;
        for (var i = 0; i < _birds.Count; i++)
        {
            var ph = i * 1.7f;
            var r = 22f + i * 4f;
            var ang = t * 0.25f + ph;
            _birds[i].Position = new Vector3(
                Mathf.Cos(ang) * r, 26f + Mathf.Sin(t * 0.5f + ph) * 3f, Mathf.Sin(ang) * r);
            // face the tangent, flap the wings
            _birds[i].Rotation = new Vector3(0, -ang + Mathf.Pi * 0.5f,
                Mathf.Sin(t * 6f + ph) * 0.5f);
        }
    }

    // -------------------------------------------------------- butterflies ----
    private void BuildButterflies()
    {
        var cols = new[]
        {
            new Color(1f, 0.7f, 0.2f), new Color(0.9f, 0.4f, 0.7f),
            new Color(0.5f, 0.7f, 1f),
        };
        for (var i = 0; i < 3; i++)
        {
            _butterflies.Add(new MeshInstance3D
            {
                Mesh = new QuadMesh { Size = new Vector2(0.35f, 0.35f) },
                MaterialOverride = new StandardMaterial3D
                {
                    AlbedoColor = cols[i],
                    EmissionEnabled = true,
                    Emission = cols[i] * 0.4f,
                    Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                    BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
                    CullMode = BaseMaterial3D.CullModeEnum.Disabled,
                },
                Visible = false,
            });
            AddChild(_butterflies[i]);
        }
    }

    private void UpdateButterflies(bool green)
    {
        var t = (float)Time.GetTicksMsec() / 1000f;
        var origin = GlobalPosition;
        for (var i = 0; i < _butterflies.Count; i++)
        {
            var b = _butterflies[i];
            b.Visible = green;
            if (!green) continue;
            var ph = i * 2.1f;
            var x = Mathf.Sin(t * 0.7f + ph) * 6f + Mathf.Sin(t * 2.3f + ph) * 1.5f;
            var z = Mathf.Cos(t * 0.6f + ph * 1.3f) * 6f + Mathf.Cos(t * 1.9f + ph) * 1.5f;
            var ground = TerrainHeightField.H(origin.X + x, origin.Z + z);
            b.Position = new Vector3(x, ground - origin.Y + 1.0f + Mathf.Sin(t * 3f + ph) * 0.5f, z);
        }
    }

    // -------------------------------------------------------------- fish ----
    private void UpdateFish(double delta, Vector3 p)
    {
        _fishTimer -= delta;
        if (_fishTimer > 0) return;
        _fishTimer = 3.0 + _rng.Randf() * 4.0;
        for (var k = 0; k < 8; k++)
        {
            var a = _rng.Randf() * Mathf.Tau;
            var d = 8f + _rng.Randf() * 22f;
            var wx = p.X + Mathf.Cos(a) * d;
            var wz = p.Z + Mathf.Sin(a) * d;
            if (TerrainHeightField.IsWater(wx, wz))
            {
                SpawnFishArc(wx, TerrainHeightField.WaterLevel, wz);
                return;
            }
        }
    }

    private void SpawnFishArc(float x, float y, float z)
    {
        var fish = new MeshInstance3D
        {
            Mesh = new CapsuleMesh { Radius = 0.12f, Height = 0.5f },
            MaterialOverride = new StandardMaterial3D
            { AlbedoColor = new Color(0.6f, 0.65f, 0.7f), Metallic = 0.3f, Roughness = 0.3f },
            Position = new Vector3(x, y, z),
            RotationDegrees = new Vector3(90, 0, 0),
        };
        var host = GetTree().CurrentScene ?? (Node)this;
        host.AddChild(fish);
        var tw = fish.CreateTween();
        tw.TweenProperty(fish, "position", new Vector3(x, y + 1.6f, z), 0.4)
            .SetTrans(Tween.TransitionType.Quad).SetEase(Tween.EaseType.Out);
        tw.TweenProperty(fish, "position", new Vector3(x, y, z), 0.4)
            .SetTrans(Tween.TransitionType.Quad).SetEase(Tween.EaseType.In);
        tw.TweenCallback(Callable.From(fish.QueueFree));
    }
}
