using Godot;

namespace Game1.Godot;

/// <summary>
/// Procedural combat/interaction feedback: swing arcs, floating text, scale
/// punches. Pure presentation — CombatWorld spawns these on certified sim
/// events; nothing here owns game state. Damage-number lifetime and crit
/// scale honor the designer's visual-config values (VisualConfig port).
/// </summary>
public partial class FxManager : Node3D
{
    public const float TextLifetime = 1.2f;   // visual-config lifetimeMs 1200
    public const float CritScale = 1.8f;      // visual-config critScaleMultiplier

    /// <summary>Sweeping wedge slash in front of the attacker (sim facing).</summary>
    public void SwingArc(Vector3 origin, double simFacingDeg)
    {
        var mat = new StandardMaterial3D
        {
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            BlendMode = BaseMaterial3D.BlendModeEnum.Add,
            CullMode = BaseMaterial3D.CullModeEnum.Disabled,
            AlbedoColor = new Color(1f, 0.92f, 0.6f, 0.85f),
        };
        var pivot = new Node3D { Position = origin + new Vector3(0, 1.15f, 0) };
        pivot.AddChild(new MeshInstance3D { Mesh = BuildWedge(), MaterialOverride = mat });

        // Sim angle a has direction (cos a, sin a) in the XZ plane → yaw -a
        var yaw = -Mathf.DegToRad((float)simFacingDeg);
        const float sweep = 0.9f;
        pivot.Rotation = new Vector3(0, yaw + sweep, 0);
        AddChild(pivot);

        var tween = CreateTween();
        tween.TweenProperty(pivot, "rotation:y", yaw - sweep, 0.16f)
             .SetTrans(Tween.TransitionType.Cubic).SetEase(Tween.EaseType.Out);
        tween.Parallel().TweenProperty(mat, "albedo_color:a", 0f, 0.26f)
             .SetTrans(Tween.TransitionType.Sine).SetEase(Tween.EaseType.In);
        tween.TweenCallback(Callable.From(pivot.QueueFree));
    }

    private static ArrayMesh BuildWedge()
    {
        // Flat 25-degree fan in the XZ plane pointing +X, radius 0.45 → 1.75
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        const int segs = 6;
        const float half = 0.22f;
        for (var i = 0; i < segs; i++)
        {
            var a0 = -half + 2 * half * i / segs;
            var a1 = -half + 2 * half * (i + 1) / segs;
            var i0 = new Vector3(Mathf.Cos(a0) * 0.45f, 0, Mathf.Sin(a0) * 0.45f);
            var i1 = new Vector3(Mathf.Cos(a1) * 0.45f, 0, Mathf.Sin(a1) * 0.45f);
            var o0 = new Vector3(Mathf.Cos(a0) * 1.75f, 0, Mathf.Sin(a0) * 1.75f);
            var o1 = new Vector3(Mathf.Cos(a1) * 1.75f, 0, Mathf.Sin(a1) * 1.75f);
            st.AddVertex(i0); st.AddVertex(o0); st.AddVertex(o1);
            st.AddVertex(i0); st.AddVertex(o1); st.AddVertex(i1);
        }
        return st.Commit();
    }

    /// <summary>Rising, fading billboard text (damage numbers, loot, events).</summary>
    public void FloatText(Vector3 worldPos, string text, Color color, float scale = 1f)
    {
        var label = new Label3D
        {
            Text = text,
            Modulate = color,
            FontSize = (int)(56 * scale),
            OutlineSize = 14,
            Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
            NoDepthTest = true,
            Position = worldPos + new Vector3(0, 1.9f, 0),
        };
        AddChild(label);
        var tween = CreateTween();
        tween.TweenProperty(label, "position:y", label.Position.Y + 1.3f, TextLifetime)
             .SetTrans(Tween.TransitionType.Cubic).SetEase(Tween.EaseType.Out);
        tween.Parallel().TweenProperty(label, "modulate:a", 0f, TextLifetime)
             .SetTrans(Tween.TransitionType.Quad).SetEase(Tween.EaseType.In);
        tween.TweenCallback(Callable.From(label.QueueFree));
    }

    /// <summary>Impact punch: quick scale-up, springy settle.</summary>
    public void PunchScale(Node3D node, float amount = 1.18f)
    {
        var tween = CreateTween();
        tween.TweenProperty(node, "scale", Vector3.One * amount, 0.05f);
        tween.TweenProperty(node, "scale", Vector3.One, 0.14f)
             .SetTrans(Tween.TransitionType.Back).SetEase(Tween.EaseType.Out);
    }
}
