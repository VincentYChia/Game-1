using Godot;

namespace Game1.Godot;

/// <summary>
/// Speed-blended hybrid camera (ADR-6, 3D-necessitated).
/// Third-person orbit when stationary; glides toward first-person while the
/// player moves. Transition choreography: FOV leads, distance follows — a
/// mid-transition FOV bulge widens the view BEFORE the camera pulls back past
/// the character's head (and optically softens the dolly-in on the way in).
/// The body mesh fades by real camera proximity, not by mode, so manual zoom
/// and spring-arm compression are covered too. Right-drag aims in both
/// regimes; wheel sets the third-person orbit distance.
/// </summary>
public partial class OrbitCamera : Node3D
{
    // -- third-person orbit --
    [Export] public float Distance { get; set; } = 12f;
    [Export] public float MinDistance { get; set; } = 4f;
    [Export] public float MaxDistance { get; set; } = 30f;
    [Export] public float OrbitSensitivity { get; set; } = 0.005f;

    // -- blend choreography --
    [Export] public float FovThird { get; set; } = 70f;
    [Export] public float FovFirstWalk { get; set; } = 80f;
    [Export] public float FovFirstSprint { get; set; } = 84f;
    /// <summary>Extra mid-transition FOV widening (peaks at half-blend).</summary>
    [Export] public float FovBulge { get; set; } = 9f;
    [Export] public float BlendInTime { get; set; } = 1.4f;
    /// <summary>Slower than blend-in: pulling out should feel calm.</summary>
    [Export] public float BlendOutTime { get; set; } = 2.0f;
    /// <summary>Sustained movement required before committing to first person
    /// (kills the tap-tap yo-yo).</summary>
    [Export] public float MoveCommitDelay { get; set; } = 0.18f;
    [Export] public float StopCommitDelay { get; set; } = 0.40f;

    private const float PivotThird = 1.2f;   // chest framing while orbiting
    private const float PivotFirst = 1.55f;  // eye level of the 1.7 capsule
    private const float FadeNear = 0.9f;     // body invisible inside this
    private const float FadeFar = 2.2f;      // body fully opaque beyond this

    private float _yaw;
    private float _pitchThird = -0.7f;
    private float _pitchFirst = -0.12f;
    private float _blend;        // 0 = third person, 1 = first person
    private float _blendTarget;
    private float _movingFor, _stillFor;
    private bool _manualFp;      // shift+wheel-up while standing

    private SpringArm3D _arm = null!;
    private Camera3D _cam = null!;
    private PlayerController? _player;
    private MeshInstance3D? _body;
    private StandardMaterial3D? _bodyMat;

    public override void _Ready()
    {
        _player = GetParent() as PlayerController;

        _arm = new SpringArm3D { SpringLength = Distance, Margin = 0.5f };
        AddChild(_arm);
        _cam = new Camera3D { Current = true, Fov = FovThird, Near = 0.05f };
        _arm.AddChild(_cam);

        if (_player is not null)
        {
            // Without this the arm collides with the player's own capsule and
            // compresses toward the ground whenever the pitch dips.
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

        // Real (post-collision) velocity, not commanded velocity — pushing
        // against a wall reads as standing still, so it never zooms you in.
        var hSpeed = 0f;
        if (_player is not null)
        {
            var real = _player.GetRealVelocity();
            hSpeed = new Vector2(real.X, real.Z).Length();
        }

        // Hysteresis: the target only flips after sustained motion/stillness;
        // between the commit windows it holds, so direction changes and brief
        // taps never flip-flop the camera.
        var moving = hSpeed > 0.5f;
        _movingFor = moving ? _movingFor + dt : 0f;
        _stillFor = moving ? 0f : _stillFor + dt;
        if (_movingFor >= MoveCommitDelay) _blendTarget = 1f;
        else if (_stillFor >= StopCommitDelay) _blendTarget = _manualFp ? 1f : 0f;

        // Rate-limited master blend. Zoom-in rate scales with actual speed
        // (slow drift at low speed, brisk at sprint); zoom-out is constant
        // and slower. The shaped curves below ease both endpoints.
        var rate = 1f / (_blendTarget > _blend ? BlendInTime : BlendOutTime);
        if (_blendTarget > _blend && _player is not null && _player.MoveSpeed > 0f)
            rate *= Mathf.Clamp(hSpeed / _player.MoveSpeed, 0.4f, 1.6f);
        _blend = Mathf.MoveToward(_blend, _blendTarget, rate * dt);

        ApplyRig(hSpeed);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (UiHub.ScreenOpen) return;   // don't orbit/zoom behind popups
        switch (@event)
        {
            case InputEventMouseMotion motion
                when Input.IsMouseButtonPressed(MouseButton.Right):
                _yaw -= motion.Relative.X * OrbitSensitivity;
                var dp = -motion.Relative.Y * OrbitSensitivity;
                // Both regimes accumulate the same aim delta with their own
                // comfort clamps: orbit stays above the ground plane, first
                // person may look up. Stopping returns to the orbit you left.
                _pitchThird = Mathf.Clamp(_pitchThird + dp, -1.4f, -0.15f);
                _pitchFirst = Mathf.Clamp(_pitchFirst + dp, -1.2f, 1.2f);
                break;
            case InputEventMouseButton { Pressed: true } button:
                var shift = Input.IsKeyPressed(Key.Shift);
                if (button.ButtonIndex == MouseButton.WheelUp)
                {
                    // Shift+wheel-up: glide into first person while standing.
                    if (shift) _manualFp = true;
                    else Distance = Mathf.Max(MinDistance, Distance - 1.5f);
                }
                else if (button.ButtonIndex == MouseButton.WheelDown)
                {
                    // Any wheel-down releases a manual first person.
                    if (_manualFp) _manualFp = false;
                    else if (!shift) Distance = Mathf.Min(MaxDistance, Distance + 1.5f);
                }
                break;
        }
    }

    private void ApplyRig(float hSpeed)
    {
        var t = _blend;
        var te = Mathf.SmoothStep(0f, 1f, t); // eased master for pitch/pivot/FOV

        var pitch = Mathf.Lerp(_pitchThird, _pitchFirst, te);
        Rotation = new Vector3(pitch, _yaw, 0);

        // Pivot rises from chest framing to eye level (never the feet — the
        // old feet-level pivot was why the camera dove into the ground).
        Position = new Vector3(0, Mathf.Lerp(PivotThird, PivotFirst, te), 0);

        // Distance collapse lives in the LOWER half of the blend: entering
        // first person the dolly-in happens while the FOV bulge is widening
        // (optically softened); leaving first person the FOV widens first and
        // only then does the camera pull back past the (still faded) head.
        var dShape = Mathf.SmoothStep(0.1f, 0.55f, t);
        _arm.SpringLength = Distance * (1f - dShape);

        var sprintFrac = 0f;
        if (_player is not null && _player.MoveSpeed > 0f)
            sprintFrac = Mathf.Clamp(
                (hSpeed - _player.MoveSpeed) /
                (_player.MoveSpeed * (_player.SprintMultiplier - 1f)), 0f, 1f);
        var fovFirst = Mathf.Lerp(FovFirstWalk, FovFirstSprint, sprintFrac);
        _cam.Fov = Mathf.Lerp(FovThird, fovFirst, te) + FovBulge * 4f * te * (1f - te);

        // Fade the body by real camera proximity so you never stare at the
        // inside of the capsule — regardless of whether the camera got close
        // via the blend, the wheel, or spring-arm compression.
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
