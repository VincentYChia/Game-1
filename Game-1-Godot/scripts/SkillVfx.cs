using Godot;

namespace Game1.Godot;

/// <summary>
/// Modular 3D skill/combat effects, keyed on geometry tags the same way the
/// 2D attack_effects manager was (circle → ground ring, beam → thrust,
/// cone → wedge, chain → links, single/pierce → slash). Element tags pick
/// the color. Everything is procedural (mesh + tween), additive-blended, and
/// self-frees — no assets.
/// </summary>
public partial class SkillVfx : Node3D
{
    private static readonly Dictionary<string, Color> Element = new()
    {
        ["fire"] = new Color(1f, 0.5f, 0.15f),
        ["ice"] = new Color(0.55f, 0.85f, 1f),
        ["lightning"] = new Color(1f, 0.92f, 0.35f),
        ["poison"] = new Color(0.55f, 0.9f, 0.35f),
        ["arcane"] = new Color(0.75f, 0.45f, 1f),
        ["shadow"] = new Color(0.55f, 0.35f, 0.7f),
        ["holy"] = new Color(1f, 0.98f, 0.7f),
        ["chaos"] = new Color(1f, 0.3f, 0.6f),
        ["physical"] = new Color(0.92f, 0.92f, 0.95f),
    };

    public static Color ColorFor(IEnumerable<string> tags)
    {
        foreach (var t in tags)
            if (Element.TryGetValue(t, out var c)) return c;
        return new Color(0.7f, 0.85f, 1f);   // generic magic
    }

    private static StandardMaterial3D Mat(Color c, float alpha = 0.85f)
        => new()
        {
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            BlendMode = BaseMaterial3D.BlendModeEnum.Add,
            CullMode = BaseMaterial3D.CullModeEnum.Disabled,
            AlbedoColor = new Color(c, alpha),
        };

    /// <summary>Expanding flat ring on the ground (circle/AoE skills).</summary>
    public void Circle(Vector3 pos, float radius, Color color)
    {
        var mat = Mat(color);
        var mesh = new MeshInstance3D
        {
            Mesh = new TorusMesh { InnerRadius = radius * 0.72f, OuterRadius = radius },
            MaterialOverride = mat,
            Position = pos + new Vector3(0, 0.12f, 0),
            Rotation = new Vector3(Mathf.Pi / 2, 0, 0),   // lay flat
            Scale = new Vector3(0.2f, 0.2f, 0.2f),
        };
        AddChild(mesh);
        var tw = CreateTween();
        tw.TweenProperty(mesh, "scale", Vector3.One, 0.28f)
            .SetTrans(Tween.TransitionType.Cubic).SetEase(Tween.EaseType.Out);
        tw.Parallel().TweenProperty(mat, "albedo_color:a", 0f, 0.5f)
            .SetEase(Tween.EaseType.In);
        tw.TweenCallback(Callable.From(mesh.QueueFree));
    }

    /// <summary>A bright thrust cylinder from origin to target (beam/line).</summary>
    public void Beam(Vector3 from, Vector3 to, Color color)
    {
        var mid = (from + to) * 0.5f;
        var len = from.DistanceTo(to);
        if (len < 0.05f) len = 0.05f;
        var mat = Mat(color);
        var mesh = new MeshInstance3D
        {
            Mesh = new CylinderMesh
            { TopRadius = 0.12f, BottomRadius = 0.12f, Height = len },
            MaterialOverride = mat,
            Position = mid,
        };
        // Cylinder's axis is +Y; aim it along (to-from)
        var dir = (to - from).Normalized();
        if (dir.LengthSquared() > 0.001f && Mathf.Abs(dir.Dot(Vector3.Up)) < 0.999f)
            mesh.LookAtFromPosition(mid, to, Vector3.Up);
        mesh.RotateObjectLocal(Vector3.Right, Mathf.Pi / 2);   // +Z → +Y axis
        AddChild(mesh);
        var tw = CreateTween();
        tw.TweenProperty(mat, "albedo_color:a", 0f, 0.3f).SetEase(Tween.EaseType.In);
        tw.Parallel().TweenProperty(mesh, "scale",
            new Vector3(0.3f, 1f, 0.3f), 0.3f);
        tw.TweenCallback(Callable.From(mesh.QueueFree));
    }

    /// <summary>A flat expanding wedge in front of the caster (cone/slash).</summary>
    public void Wedge(Vector3 origin, float yawDeg, float halfAngle, float range,
                      Color color)
    {
        var mat = Mat(color, 0.7f);
        var pivot = new Node3D
        {
            Position = origin + new Vector3(0, 0.9f, 0),
            RotationDegrees = new Vector3(0, yawDeg, 0),
        };
        pivot.AddChild(new MeshInstance3D
        { Mesh = BuildFan(halfAngle, range), MaterialOverride = mat });
        AddChild(pivot);
        var tw = CreateTween();
        tw.TweenProperty(pivot, "scale", Vector3.One * 1.15f, 0.14f)
            .SetTrans(Tween.TransitionType.Cubic).SetEase(Tween.EaseType.Out);
        tw.Parallel().TweenProperty(mat, "albedo_color:a", 0f, 0.28f)
            .SetEase(Tween.EaseType.In);
        tw.TweenCallback(Callable.From(pivot.QueueFree));
    }

    /// <summary>A small burst sphere at a point (single-target / chain node).</summary>
    public void Burst(Vector3 pos, Color color)
    {
        var mat = Mat(color);
        var mesh = new MeshInstance3D
        {
            Mesh = new SphereMesh { Radius = 0.35f, Height = 0.7f },
            MaterialOverride = mat,
            Position = pos + new Vector3(0, 0.9f, 0),
            Scale = Vector3.One * 0.3f,
        };
        AddChild(mesh);
        var tw = CreateTween();
        tw.TweenProperty(mesh, "scale", Vector3.One * 1.4f, 0.22f)
            .SetTrans(Tween.TransitionType.Cubic).SetEase(Tween.EaseType.Out);
        tw.Parallel().TweenProperty(mat, "albedo_color:a", 0f, 0.3f)
            .SetEase(Tween.EaseType.In);
        tw.TweenCallback(Callable.From(mesh.QueueFree));
    }

    // Flat fan in the XZ plane pointing +X (before the pivot yaw)
    private static ArrayMesh BuildFan(float halfAngleRad, float range)
    {
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        const int segs = 10;
        for (var i = 0; i < segs; i++)
        {
            var a0 = -halfAngleRad + 2 * halfAngleRad * i / segs;
            var a1 = -halfAngleRad + 2 * halfAngleRad * (i + 1) / segs;
            var c = Vector3.Zero;
            var o0 = new Vector3(Mathf.Cos(a0) * range, 0, Mathf.Sin(a0) * range);
            var o1 = new Vector3(Mathf.Cos(a1) * range, 0, Mathf.Sin(a1) * range);
            st.AddVertex(c); st.AddVertex(o0); st.AddVertex(o1);
        }
        return st.Commit();
    }
}
