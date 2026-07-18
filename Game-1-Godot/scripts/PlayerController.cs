using Godot;

namespace Game1.Godot;

/// <summary>
/// Camera-relative WASD movement on a CharacterBody3D (ADR-6: the new input
/// mapping of the existing 8-direction movement; simulation stays planar).
/// Uses physical key polling — no InputMap configuration required.
/// </summary>
public partial class PlayerController : CharacterBody3D
{
    [Export] public float MoveSpeed { get; set; } = 6.0f;
    [Export] public float SprintMultiplier { get; set; } = 1.6f;

    public override void _PhysicsProcess(double delta)
    {
        var input = Vector2.Zero;
        if (Input.IsKeyPressed(Key.W)) input.Y -= 1;
        if (Input.IsKeyPressed(Key.S)) input.Y += 1;
        if (Input.IsKeyPressed(Key.A)) input.X -= 1;
        if (Input.IsKeyPressed(Key.D)) input.X += 1;
        input = input.Normalized();

        // Camera-relative: forward = camera's flattened -Z
        var camera = GetViewport().GetCamera3D();
        Vector3 direction;
        if (camera is not null)
        {
            var forward = -camera.GlobalTransform.Basis.Z;
            forward.Y = 0;
            forward = forward.Normalized();
            var right = camera.GlobalTransform.Basis.X;
            right.Y = 0;
            right = right.Normalized();
            direction = (right * input.X + forward * -input.Y).Normalized();
        }
        else
        {
            direction = new Vector3(input.X, 0, input.Y);
        }

        var speed = MoveSpeed * (Input.IsKeyPressed(Key.Shift) ? SprintMultiplier : 1f);
        var velocity = Velocity;
        velocity.X = direction.X * speed;
        velocity.Z = direction.Z * speed;
        velocity.Y = IsOnFloor() ? 0 : velocity.Y - 24f * (float)delta;
        Velocity = velocity;
        MoveAndSlide();
    }
}
