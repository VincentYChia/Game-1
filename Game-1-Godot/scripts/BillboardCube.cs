using Godot;

namespace Game1.Godot;

/// <summary>
/// Builds a "billboard cube" visual: a colored body box whose TOP and BOTTOM
/// stay plain, plus four full-texture quads on the side faces so the sprite
/// is recognizable from every horizontal direction (a BoxMesh alone unwraps
/// the texture across faces as a net, which looks wrapped/sliced). Returns
/// the body material and the four side materials for tinting (hit-flash,
/// telegraph, corpse graying).
/// </summary>
public static class BillboardCube
{
    public static (StandardMaterial3D Body, List<StandardMaterial3D> Sides) Build(
        Node3D parent, float size, Color color, Texture2D? tex)
    {
        var body = new StandardMaterial3D { AlbedoColor = color };
        parent.AddChild(new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = new Vector3(size, size, size) },
            MaterialOverride = body,
            Position = new Vector3(0, 0.5f * size, 0),
        });

        var sides = new List<StandardMaterial3D>();
        if (tex is not null)
        {
            var half = size / 2f + 0.01f;
            var faces = new (Vector3 Pos, float YawDeg)[]
            {
                (new Vector3(0, 0.5f * size, half), 0f),     // +Z front
                (new Vector3(0, 0.5f * size, -half), 180f),  // -Z back
                (new Vector3(half, 0.5f * size, 0), 90f),    // +X right
                (new Vector3(-half, 0.5f * size, 0), -90f),  // -X left
            };
            foreach (var (fpos, yaw) in faces)
            {
                var m = new StandardMaterial3D
                {
                    AlbedoTexture = tex,
                    AlbedoColor = Colors.White,
                    TextureFilter = BaseMaterial3D.TextureFilterEnum.Linear,
                };
                parent.AddChild(new MeshInstance3D
                {
                    Mesh = new QuadMesh { Size = new Vector2(size, size) },
                    MaterialOverride = m,
                    Position = fpos,
                    RotationDegrees = new Vector3(0, yaw, 0),
                });
                sides.Add(m);
            }
        }
        return (body, sides);
    }
}
