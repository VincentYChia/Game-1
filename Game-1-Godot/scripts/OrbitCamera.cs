using Godot;

namespace Game1.Godot;

/// <summary>
/// Follow camera (ADR-6). No automatic movement-based zoom — the distance is
/// controlled ONLY by SHIFT + mouse wheel (item 4). Right-drag aims; the
/// cursor leaving the central dead-zone box glides the view to recenter
/// (speed ramps with distance out of the box). Zooming fully in reaches
/// first person (eye pivot, wider FOV, body fades out).
/// </summary>
public partial class OrbitCamera : Node3D
{
    [Export] public float StartDistance { get; set; } = 8f;
    [Export] public float MinDistance { get; set; } = 0f;
    [Export] public float MaxDistance { get; set; } = 16f;
    [Export] public float ZoomStep { get; set; } = 1.0f;
    [Export] public float OrbitSensitivity { get; set; } = 0.005f;

    [Export] public float ThirdFov { get; set; } = 72f;
    [Export] public float FirstFov { get; set; } = 92f;

    /// <summary>Camera-glide dead zone: the centered fraction of the screen
    /// (each axis) where the cursor does NOT turn the camera. Outside it,
    /// turn speed ramps with how far past the box the cursor is.</summary>
    [Export] public float GlideDeadZone { get; set; } = 0.5f;
    [Export] public float EdgeYawSpeed { get; set; } = 2.4f;
    [Export] public float EdgePitchSpeed { get; set; } = 1.6f;

    private const float ThirdPivot = 1.35f;
    private const float FirstPivot = 1.55f;
    private const float FpDistance = 2.0f;   // below this, blend toward FP
    private const float FadeNear = 1.0f;
    private const float FadeFar = 2.4f;

    private float _yaw;
    private float _pitch = -0.32f;
    private float _distance;

    private SpringArm3D _arm = null!;
    private Camera3D _cam = null!;
    private PlayerController? _player;
    private MeshInstance3D? _body;
    private StandardMaterial3D? _bodyMat;

    public override void _Ready()
    {
        _player = GetParent() as PlayerController;
        _distance = StartDistance;

        _arm = new SpringArm3D { SpringLength = _distance, Margin = 0.5f };
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
        EdgeGlide((float)delta);
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

        var nx = m.X / vp.X * 2f - 1f;
        var ny = m.Y / vp.Y * 2f - 1f;
        var deadHalf = Mathf.Clamp(GlideDeadZone, 0f, 0.95f);
        float Ramp(float n)
        {
            var a = Mathf.Abs(n);
            if (a <= deadHalf) return 0f;
            var t = (a - deadHalf) / (1f - deadHalf);
            return Mathf.Sign(n) * t * t;
        }
        _yaw -= Ramp(nx) * EdgeYawSpeed * dt;
        _pitch = Mathf.Clamp(_pitch - Ramp(ny) * EdgePitchSpeed * dt, -1.35f, 1.2f);
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
                when Input.IsKeyPressed(Key.Shift):
                // SHIFT + wheel is the ONLY zoom control (item 4)
                if (button.ButtonIndex == MouseButton.WheelUp)
                    _distance = Mathf.Clamp(_distance - ZoomStep, MinDistance, MaxDistance);
                else if (button.ButtonIndex == MouseButton.WheelDown)
                    _distance = Mathf.Clamp(_distance + ZoomStep, MinDistance, MaxDistance);
                break;
        }
    }

    private void ApplyRig()
    {
        // First-person amount: 1 when zoomed all the way in, 0 by FpDistance.
        var fp = Mathf.Clamp(1f - _distance / FpDistance, 0f, 1f);
        var te = Mathf.SmoothStep(0f, 1f, fp);

        Position = new Vector3(0, Mathf.Lerp(ThirdPivot, FirstPivot, te), 0);
        Rotation = new Vector3(_pitch, _yaw, 0);
        _arm.SpringLength = _distance;
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
