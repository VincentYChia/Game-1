using Godot;

namespace Game1.Godot;

/// <summary>
/// First-person-home camera (ADR-6, 3D-necessitated). At rest the view sits
/// at the character's eyes; while moving it eases back a few meters so you
/// see your character and the ground ahead. Hysteresis + slow eased blending
/// keep it calm (no tap yo-yo, no snap). The body mesh fades by real camera
/// proximity so the pull-back never stares at the inside of the head.
/// Right-drag aims; wheel adjusts the moving pull-back distance.
/// </summary>
public partial class OrbitCamera : Node3D
{
    /// <summary>How far the camera eases back while moving.</summary>
    [Export] public float MovingDistance { get; set; } = 3.5f;
    [Export] public float MinDistance { get; set; } = 2f;
    [Export] public float MaxDistance { get; set; } = 9f;
    [Export] public float OrbitSensitivity { get; set; } = 0.005f;

    [Export] public float Fov { get; set; } = 75f;
    /// <summary>Subtle extra FOV at full sprint (speed feel).</summary>
    [Export] public float SprintFovBonus { get; set; } = 3f;

    [Export] public float BlendOutTime { get; set; } = 1.2f;   // rest → moving
    [Export] public float BlendBackTime { get; set; } = 1.6f;  // moving → rest
    [Export] public float MoveCommitDelay { get; set; } = 0.18f;
    [Export] public float StopCommitDelay { get; set; } = 0.40f;

    private const float EyeHeight = 1.55f;   // eyes of the 1.7 capsule
    private const float FadeNear = 0.9f;     // body invisible inside this
    private const float FadeFar = 2.2f;      // body fully opaque beyond this

    private float _yaw;
    private float _pitch = -0.1f;
    private float _blend;        // 0 = first person (rest), 1 = pulled back
    private float _blendTarget;
    private float _movingFor, _stillFor;

    private SpringArm3D _arm = null!;
    private Camera3D _cam = null!;
    private PlayerController? _player;
    private MeshInstance3D? _body;
    private StandardMaterial3D? _bodyMat;

    public override void _Ready()
    {
        _player = GetParent() as PlayerController;

        Position = new Vector3(0, EyeHeight, 0);
        _arm = new SpringArm3D { SpringLength = 0, Margin = 0.5f };
        AddChild(_arm);
        _cam = new Camera3D { Current = true, Fov = Fov, Near = 0.05f };
        _arm.AddChild(_cam);

        if (_player is not null)
        {
            // Without this the arm collides with the player's own capsule.
            _arm.AddExcludedObject(_player.GetRid());
            _body = _player.GetNodeOrNull<MeshInstance3D>("Body");
            if (_body?.MaterialOverride is StandardMaterial3D mat)
            {
                mat.Transparency = BaseMaterial3D.TransparencyEnum.Alpha;
                _bodyMat = mat;
            }
        }

        ApplyRig(0f);
    }

    public override void _Process(double delta)
    {
        var dt = (float)delta;

        // Real (post-collision) velocity: pushing a wall = standing still.
        var hSpeed = 0f;
        if (_player is not null)
        {
            var real = _player.GetRealVelocity();
            hSpeed = new Vector2(real.X, real.Z).Length();
        }

        // Hysteresis: commit windows stop tap/turn flip-flop.
        var moving = hSpeed > 0.5f;
        _movingFor = moving ? _movingFor + dt : 0f;
        _stillFor = moving ? 0f : _stillFor + dt;
        if (_movingFor >= MoveCommitDelay) _blendTarget = 1f;
        else if (_stillFor >= StopCommitDelay) _blendTarget = 0f;

        var rate = 1f / (_blendTarget > _blend ? BlendOutTime : BlendBackTime);
        _blend = Mathf.MoveToward(_blend, _blendTarget, rate * dt);

        ApplyRig(hSpeed);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (UiHub.ScreenOpen) return;   // don't aim/zoom behind popups
        switch (@event)
        {
            case InputEventMouseMotion motion
                when Input.IsMouseButtonPressed(MouseButton.Right):
                _yaw -= motion.Relative.X * OrbitSensitivity;
                _pitch = Mathf.Clamp(_pitch - motion.Relative.Y * OrbitSensitivity,
                    -1.2f, 1.2f);
                break;
            case InputEventMouseButton { Pressed: true } button:
                if (button.ButtonIndex == MouseButton.WheelUp)
                    MovingDistance = Mathf.Max(MinDistance, MovingDistance - 0.75f);
                else if (button.ButtonIndex == MouseButton.WheelDown)
                    MovingDistance = Mathf.Min(MaxDistance, MovingDistance + 0.75f);
                break;
        }
    }

    private void ApplyRig(float hSpeed)
    {
        Rotation = new Vector3(_pitch, _yaw, 0);

        // Eased pull-back: zero slope at both endpoints, so leaving and
        // arriving are both gentle.
        var te = Mathf.SmoothStep(0f, 1f, _blend);
        _arm.SpringLength = MovingDistance * te;

        var sprintFrac = 0f;
        if (_player is not null && _player.MoveSpeed > 0f)
            sprintFrac = Mathf.Clamp(
                (hSpeed - _player.MoveSpeed) /
                (_player.MoveSpeed * (_player.SprintMultiplier - 1f)), 0f, 1f);
        _cam.Fov = Fov + SprintFovBonus * te * sprintFrac;

        // Body fades by real camera proximity — never see inside the head.
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
