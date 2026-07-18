using Godot;

namespace Game1.Godot;

/// <summary>
/// Placeholder engine entry point proving the Game1.Core link. Real boot
/// (content load, world build, sidecar launch) arrives in Phase 3.
/// </summary>
public partial class Bootstrap : Node3D
{
    public override void _Ready()
    {
        GD.Print("Game-1 Godot bootstrap. EXP to reach level 2: " +
                 Core.Progression.ExperienceCurve.RequirementForLevel(2));
    }
}
