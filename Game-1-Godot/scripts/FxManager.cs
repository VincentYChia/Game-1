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
