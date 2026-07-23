using Godot;

namespace Game1.Godot;

/// <summary>
/// Blended follow camera (ADR-6): THIRD person when standing still, glides to
/// FIRST person while moving. Right-drag aims; cursor near a screen edge
/// glides the view that way. Holding RIGHT-CLICK + mouse wheel applies a
/// manual zoom bias that persists whether you're moving or not (layered on
/// top of the auto blend). The body mesh fades by real camera proximity so
/// first person never stares at the inside of the head.
/// </summary>
public partial class OrbitCamera : Node3D
{
    /// <summary>Distance behind the player when standing still (third person).</summary>
    [Export] public float ThirdDistance { get; set; } = 8f;
    [Export] public float MaxDistance { get; set; } = 16f;
    [Export] public float OrbitSensitivity { get; set; } = 0.005f;

    [Export] public float ThirdFov { get; set; } = 72f;
    /// <summary>Wider field of view in first person (moving).</summary>
    [Export] public float FirstFov { get; set; } = 92f;

    [Export] public float BlendInTime { get; set; } = 0.9f;    // still → moving (FP)
    [Export] public float BlendOutTime { get; set; } = 1.3f;   // moving → still (TP)
    [Export] public float MoveCommitDelay { get; set; } = 0.15f;
    [Export] public float StopCommitDelay { get; set; } = 0.35f;

    /// <summary>Edge-glide: cursor within this fraction of a screen edge
    /// smoothly turns the camera toward it (on top of right-drag aim).</summary>
    [Export] public float EdgeMargin { get; set; } = 0.10f;
    [Export] public float EdgeYawSpeed { get; set; } = 2.2f;
    [Export] public float EdgePitchSpeed { get; set; } = 1.4f;

    private const float ThirdPivot = 1.35f;  // chest framing behind the player
    private const float FirstPivot = 1.55f;  // eye level of the 1.7 capsule
    private const float FadeNear = 1.0f;
    private const float FadeFar = 2.4f;

    private float _yaw;
    private float _pitch = -0.32f;   // resting downward tilt (over-the-shoulder)
    private float _blend;            // 0 = third person, 1 = first person
    private float _blendTarget;
    private float _movingFor, _stillFor;
    private float _distBias;         // right-click + wheel manual zoom

    private SpringArm3D _arm = null!;
    private Camera3D _cam = null!;
    private PlayerController? _player;
    private MeshInstance3D? _body;
    private StandardMaterial3D? _bodyMat;

    public override void _Ready()
    {
        _player = GetParent() as PlayerController;

        _arm = new SpringArm3D { SpringLength = ThirdDistance, Margin = 0.5f };
        AddChild(_arm);
        _cam = new Camera3D { Current = true, Fov = ThirdFov, Near = 0.05f };
        _arm.AddChild(_cam);

        if (_player is not null)
        {
            _arm.AddExcludedObject(_player.GetRid());
            _body = _player.GetNodeOrNull<MeshInstance3D>("Body");
            if (_body?.MaterialOverride is StandardMaterial3D mat)
            {
                mat.Transparency = BaseMaterial3D.TransparencyEnum.Alpha;
                _bodyMat = mat;
            }
        }

        ApplyRig();
    }

    public override void _Process(double delta)
    {
        var dt = (float)delta;

        var hSpeed = 0f;
        if (_player is not null)
        {
            var real = _player.GetRealVelocity();
            hSpeed = new Vector2(real.X, real.Z).Length();
        }

        var moving = hSpeed > 0.5f;
        _movingFor = moving ? _movingFor + dt : 0f;
        _stillFor = moving ? 0f : _stillFor + dt;
        if (_movingFor >= MoveCommitDelay) _blendTarget = 1f;
        else if (_stillFor >= StopCommitDelay) _blendTarget = 0f;

        var rate = 1f / (_blendTarget > _blend ? BlendInTime : BlendOutTime);
        _blend = Mathf.MoveToward(_blend, _blendTarget, rate * dt);

        EdgeGlide(dt);
        ApplyRig();
    }

    private void EdgeGlide(float dt)
    {
        if (UiHub.ScreenOpen || Input.IsMouseButtonPressed(MouseButton.Right))
            return;
        var vp = GetViewport().GetVisibleRect().Size;
        if (vp.X < 1 || vp.Y < 1) return;
        var m = GetViewport().GetMousePosition();
        if (m.X < 0 || m.Y < 0 || m.X > vp.X || m.Y > vp.Y) return;

        var mx = EdgeMargin * vp.X;
        var my = EdgeMargin * vp.Y;
        var dx = m.X < mx ? -(mx - m.X) / mx
               : m.X > vp.X - mx ? (m.X - (vp.X - mx)) / mx : 0f;
        var dy = m.Y < my ? -(my - m.Y) / my
               : m.Y > vp.Y - my ? (m.Y - (vp.Y - my)) / my : 0f;

        _yaw -= Mathf.Sign(dx) * dx * dx * EdgeYawSpeed * dt;
        _pitch = Mathf.Clamp(
            _pitch - Mathf.Sign(dy) * dy * dy * EdgePitchSpeed * dt, -1.35f, 1.2f);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (UiHub.ScreenOpen) return;
        switch (@event)
        {
            case InputEventMouseMotion motion
                when Input.IsMouseButtonPressed(MouseButton.Right):
                _yaw -= motion.Relative.X * OrbitSensitivity;
                _pitch = Mathf.Clamp(_pitch - motion.Relative.Y * OrbitSensitivity,
                    -1.35f, 1.2f);
                break;
            case InputEventMouseButton { Pressed: true } button
                when Input.IsMouseButtonPressed(MouseButton.Right):
                // Right-click + wheel: manual zoom bias, works moving or still
                if (button.ButtonIndex == MouseButton.WheelUp)
                    _distBias = Mathf.Clamp(_distBias - 0.8f, -ThirdDistance, MaxDistance);
                else if (button.ButtonIndex == MouseButton.WheelDown)
                    _distBias = Mathf.Clamp(_distBias + 0.8f, -ThirdDistance, MaxDistance);
                break;
        }
    }

    private void ApplyRig()
    {
        var te = Mathf.SmoothStep(0f, 1f, _blend);

        Position = new Vector3(0, Mathf.Lerp(ThirdPivot, FirstPivot, te), 0);
        Rotation = new Vector3(_pitch, _yaw, 0);

        var autoDist = Mathf.Lerp(ThirdDistance, 0f, te);
        _arm.SpringLength = Mathf.Clamp(autoDist + _distBias, 0f, MaxDistance);
        _cam.Fov = Mathf.Lerp(ThirdFov, FirstFov, te);

        if (_bodyMat is not null && _body is not null)
        {
            var camDist = _cam.GlobalPosition.DistanceTo(_body.GlobalPosition);
            var alpha = Mathf.Clamp((camDist - FadeNear) / (FadeFar - FadeNear), 0f, 1f);
            var c = _bodyMat.AlbedoColor;
            c.A = alpha;
            _bodyMat.AlbedoColor = c;
            _body.Visible = alpha > 0.02f;
        }
    }
}
