using Godot;

namespace Game1.Godot;

/// <summary>
/// A slowly rotating icon sprite floated above a resource node so trees/rocks
/// are identifiable from a distance (unshaded, double-sided, spins around Y).
/// </summary>
public partial class SpinSprite : Sprite3D
{
    [Export] public float SpinSpeed { get; set; } = 1.1f;

    public override void _Ready()
    {
        Shaded = false;
        DoubleSided = true;
        NoDepthTest = false;
        TextureFilter = BaseMaterial3D.TextureFilterEnum.Linear;
    }

    public override void _Process(double delta) => RotateY((float)delta * SpinSpeed);
}
