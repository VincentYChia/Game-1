using Godot;

namespace Game1.Godot;

/// <summary>
/// The craft RESULT CEREMONY — the payoff moment shared by every craft (quick or
/// minigame). When the certified CraftingSystem returns a CraftResult, the forged
/// item rises on a rarity-colored burst under a big quality banner (Normal → Fine →
/// Superior → Masterwork → Legendary). Pure presentation: it only DISPLAYS what
/// Core already decided, then calls back so the browser can refresh. Dismiss with a
/// click / [Space] / [Enter] / [Esc].
/// </summary>
public partial class CraftResultOverlay : CanvasLayer
{
    private Control _root = null!;
    private Control _fx = null!;
    private Control _glow = null!;
    private TextureRect _icon = null!;
    private Label _banner = null!;
    private Label _name = null!;
    private Label _detail = null!;
    private PanelContainer _panel = null!;

    private Color _qCol = Colors.White;
    private double _pulse;
    private bool _open;
    private System.Action? _onDismiss;

    public bool Open => _open;

    public override void _Ready()
    {
        Layer = 30;   // above the browser (10) and the minigame stage (20)
        _root = new Control { Visible = false };
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        var dim = new ColorRect { Color = new Color(0, 0, 0, 0.72f), MouseFilter = Control.MouseFilterEnum.Stop };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(dim);

        var center = new CenterContainer();
        center.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(center);

        _panel = new PanelContainer();
        center.AddChild(_panel);
        var pad = new MarginContainer();
        foreach (var s in new[] { "left", "right", "top", "bottom" })
            pad.AddThemeConstantOverride($"margin_{s}", 30);
        _panel.AddChild(pad);

        var col = new VBoxContainer { Alignment = BoxContainer.AlignmentMode.Center };
        col.AddThemeConstantOverride("separation", 12);
        pad.AddChild(col);

        _banner = new Label { HorizontalAlignment = HorizontalAlignment.Center };
        _banner.AddThemeFontSizeOverride("font_size", 40);
        _banner.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0, 0.9f));
        _banner.AddThemeConstantOverride("outline_size", 8);
        col.AddChild(_banner);

        // icon on a glowing disc
        var iconWrap = new Control { CustomMinimumSize = new Vector2(180, 180) };
        col.AddChild(iconWrap);
        _glow = new Control { MouseFilter = Control.MouseFilterEnum.Ignore };
        _glow.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _glow.Draw += DrawGlow;
        iconWrap.AddChild(_glow);
        _icon = new TextureRect
        {
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
            MouseFilter = Control.MouseFilterEnum.Ignore,
            PivotOffset = new Vector2(90, 90),
        };
        _icon.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        iconWrap.AddChild(_icon);

        _name = new Label { HorizontalAlignment = HorizontalAlignment.Center };
        _name.AddThemeFontSizeOverride("font_size", 26);
        _name.AddThemeColorOverride("font_color", UiTheme.Text);
        col.AddChild(_name);

        _detail = new Label { HorizontalAlignment = HorizontalAlignment.Center, Modulate = new Color(1, 1, 1, 0.8f) };
        _detail.AddThemeFontSizeOverride("font_size", 16);
        col.AddChild(_detail);

        var cont = new Label { Text = "click / [Space] to continue", HorizontalAlignment = HorizontalAlignment.Center, Modulate = new Color(1, 1, 1, 0.5f) };
        cont.AddThemeFontSizeOverride("font_size", 13);
        col.AddChild(cont);

        _fx = new Control { MouseFilter = Control.MouseFilterEnum.Ignore };
        _fx.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(_fx);
    }

    /// <summary>Show the ceremony for a finished craft. onDismiss fires on close.</summary>
    public void ShowResult(bool success, string quality, string itemName, int qty,
                           Texture2D? icon, string message, System.Action onDismiss)
    {
        _onDismiss = onDismiss;
        _qCol = success ? CraftFx.QualityColorByName(quality) : new Color(1f, 0.4f, 0.35f);

        _banner.Text = success ? quality.ToUpperInvariant() + "!" : "CRAFT FAILED";
        _banner.AddThemeColorOverride("font_color", _qCol);
        _name.Text = success ? $"{itemName}  ×{qty}" : itemName;
        _detail.Text = message;
        _icon.Texture = icon;
        _icon.Modulate = success ? Colors.White : new Color(1, 1, 1, 0.4f);
        _panel.AddThemeStyleboxOverride("panel", UiTheme.Box(new Color(0.08f, 0.09f, 0.13f, 0.97f), _qCol, 3, 16));

        _open = true;
        _root.Visible = true;
        UiHub.OpenScreens++;
        _pulse = 0;
        _glow.QueueRedraw();

        // pop the icon in, then a celebratory burst at screen center
        _icon.Scale = new Vector2(0.2f, 0.2f);
        var tween = _icon.CreateTween();
        tween.TweenProperty(_icon, "scale", Vector2.One, 0.45f)
             .SetTrans(Tween.TransitionType.Back).SetEase(Tween.EaseType.Out);

        if (success)
        {
            var c = GetViewport().GetVisibleRect().Size / 2f;
            CraftFx.Burst(_fx, c, _qCol, 40, 360f, 1.0f, 5f, 220f);
            // an extra shower for the top tiers
            if (CraftFx.QualityColorByName(quality) == UiTheme.Rarity["legendary"]
                || string.Equals(quality, "Masterwork", System.StringComparison.OrdinalIgnoreCase))
                CraftFx.Burst(_fx, c, Colors.White, 24, 260f, 1.2f, 4f, 120f);
        }
    }

    public override void _Process(double delta)
    {
        if (!_open) return;
        _pulse += delta;
        _glow.QueueRedraw();
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (!_open) return;
        if (@event is InputEventMouseButton { Pressed: true }
            || @event is InputEventKey { Pressed: true, Echo: false, PhysicalKeycode: Key.Space or Key.Enter or Key.Escape })
        {
            Dismiss();
            GetViewport().SetInputAsHandled();
        }
    }

    private void Dismiss()
    {
        if (!_open) return;
        _open = false;
        _root.Visible = false;
        UiHub.OpenScreens--;
        var cb = _onDismiss;
        _onDismiss = null;
        cb?.Invoke();
    }

    private void DrawGlow()
    {
        var c = _glow.Size / 2f;
        var r = Mathf.Min(c.X, c.Y);
        var breathe = 0.75f + 0.25f * Mathf.Sin((float)_pulse * 3f);
        CraftFx.Glow(_glow, c, r * breathe, new Color(_qCol.R, _qCol.G, _qCol.B, 0.55f), 8);
        _glow.DrawArc(c, r * 0.82f, 0, Mathf.Tau, 48, new Color(_qCol.R, _qCol.G, _qCol.B, 0.4f), 2f);
    }
}
