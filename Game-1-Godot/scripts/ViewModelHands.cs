using Godot;

namespace Game1.Godot;

/// <summary>
/// Placeholder procedural arms attached to the player (no rigged model yet).
/// A shoulder pivot at chest height carries a forward-pointing arm + fist;
/// CombatWorld points it at the sim facing and calls PlayAttack (overhead
/// swing) or PlayGather (downward chop). Visible in both third and first
/// person since it lives on the body, not the camera.
/// </summary>
public partial class ViewModelHands : Node3D
{
    private Node3D _pivot = null!;
    private Tween? _tween;

    /// <summary>Matches the body capsule color (WorldBootstrap player color).</summary>
    public Color BodyColor { get; set; } = new(80 / 255f, 180 / 255f, 1f);

    public override void _Ready()
    {
        // Shoulder pivot low and to the right so the arm stays out of the
        // first-person view center; it extends forward (-Z).
        _pivot = new Node3D { Position = new Vector3(0.34f, 0.85f, 0) };
        AddChild(_pivot);

        var skin = new StandardMaterial3D { AlbedoColor = BodyColor };

        var arm = new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = new Vector3(0.14f, 0.14f, 0.6f) },
            MaterialOverride = skin,
            Position = new Vector3(0, 0, -0.4f),
        };
        _pivot.AddChild(arm);

        var fist = new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = new Vector3(0.2f, 0.2f, 0.2f) },
            MaterialOverride = skin,
            Position = new Vector3(0, 0, -0.72f),
        };
        _pivot.AddChild(fist);

        _pivot.RotationDegrees = new Vector3(-28, 0, 0);   // resting, angled down
    }

    /// <summary>Point the arm along the camera's flattened forward every
    /// frame so it always aims where the player is looking (the capsule
    /// itself never rotates).</summary>
    public override void _Process(double delta)
    {
        var cam = GetViewport().GetCamera3D();
        if (cam is null) return;
        var fwd = -cam.GlobalTransform.Basis.Z;
        fwd.Y = 0;
        if (fwd.LengthSquared() < 1e-4f) return;
        fwd = fwd.Normalized();
        // Local -Z of a Node with yaw θ is (-sinθ, 0, -cosθ); solve for θ so
        // it aligns with fwd.
        Rotation = new Vector3(0, Mathf.Atan2(-fwd.X, -fwd.Z), 0);
    }

    /// <summary>Overhead swing: wind up, snap down, settle.</summary>
    public void PlayAttack()
    {
        _tween?.Kill();
        _tween = CreateTween();
        _pivot.RotationDegrees = new Vector3(-60, 0, 0);   // wound up
        _tween.TweenProperty(_pivot, "rotation_degrees",
            new Vector3(35, 0, 0), 0.12f)
            .SetTrans(Tween.TransitionType.Cubic).SetEase(Tween.EaseType.Out);
        _tween.TweenProperty(_pivot, "rotation_degrees",
            new Vector3(-28, 0, 0), 0.22f)
            .SetTrans(Tween.TransitionType.Sine).SetEase(Tween.EaseType.InOut);
    }

    /// <summary>Downward chop with a small forward reach (gather).</summary>
    public void PlayGather()
    {
        _tween?.Kill();
        _tween = CreateTween();
        _pivot.RotationDegrees = new Vector3(-45, 0, 0);
        _tween.TweenProperty(_pivot, "rotation_degrees",
            new Vector3(50, 0, 0), 0.16f)
            .SetTrans(Tween.TransitionType.Quad).SetEase(Tween.EaseType.Out);
        _tween.TweenProperty(_pivot, "rotation_degrees",
            new Vector3(-28, 0, 0), 0.24f)
            .SetTrans(Tween.TransitionType.Sine).SetEase(Tween.EaseType.InOut);
    }
}
