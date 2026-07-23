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

    public override void _Ready()
    {
        // Shoulder pivot at chest height; arm extends forward (-Z)
        _pivot = new Node3D { Position = new Vector3(0, 1.15f, 0) };
        AddChild(_pivot);

        var skin = new StandardMaterial3D
        { AlbedoColor = new Color(0.85f, 0.68f, 0.52f) };

        var arm = new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = new Vector3(0.16f, 0.16f, 0.7f) },
            MaterialOverride = skin,
            Position = new Vector3(0.18f, 0, -0.45f),
        };
        _pivot.AddChild(arm);

        var fist = new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = new Vector3(0.22f, 0.22f, 0.22f) },
            MaterialOverride = skin,
            Position = new Vector3(0.18f, 0, -0.82f),
        };
        _pivot.AddChild(fist);

        _pivot.RotationDegrees = new Vector3(-10, 0, 0);   // resting
    }

    /// <summary>Aim the arm at a sim facing (degrees; sim angle a has
    /// direction (cos a, sin a) in the XZ plane → world yaw -a).</summary>
    public void SetFacing(double simFacingDeg) =>
        RotationDegrees = new Vector3(0, -(float)simFacingDeg, 0);

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
            new Vector3(-10, 0, 0), 0.22f)
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
            new Vector3(-10, 0, 0), 0.24f)
            .SetTrans(Tween.TransitionType.Sine).SetEase(Tween.EaseType.InOut);
    }
}
