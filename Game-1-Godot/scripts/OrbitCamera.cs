using Godot;

namespace Game1.Godot;

/// <summary>
/// Third-person orbit/follow camera (ADR-6, 3D-necessitated). Right-drag to
/// orbit, wheel to zoom. Sits on a SpringArm3D so terrain never occludes.
/// </summary>
public partial class OrbitCamera : Node3D
{
    [Export] public float Distance { get; set; } = 12f;
    [Export] public float MinDistance { get; set; } = 4f;
    [Export] public float MaxDistance { get; set; } = 30f;
    [Export] public float OrbitSensitivity { get; set; } = 0.005f;

    private float _yaw;
    private float _pitch = -0.7f;
    private SpringArm3D _arm = null!;

    public override void _Ready()
    {
        _arm = new SpringArm3D { SpringLength = Distance, Margin = 0.5f };
        AddChild(_arm);
        _arm.AddChild(new Camera3D { Current = true });
        UpdateRotation();
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        switch (@event)
        {
            case InputEventMouseMotion motion
                when Input.IsMouseButtonPressed(MouseButton.Right):
                _yaw -= motion.Relative.X * OrbitSensitivity;
                _pitch = Mathf.Clamp(_pitch - motion.Relative.Y * OrbitSensitivity,
                    -1.4f, -0.15f);
                UpdateRotation();
                break;
            case InputEventMouseButton { Pressed: true } button:
                if (button.ButtonIndex == MouseButton.WheelUp)
                    Distance = Mathf.Max(MinDistance, Distance - 1.5f);
                else if (button.ButtonIndex == MouseButton.WheelDown)
                    Distance = Mathf.Min(MaxDistance, Distance + 1.5f);
                _arm.SpringLength = Distance;
                break;
        }
    }

    private void UpdateRotation() => Rotation = new Vector3(_pitch, _yaw, 0);
}
