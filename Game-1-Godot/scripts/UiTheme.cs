using Godot;

namespace Game1.Godot;

/// <summary>
/// Shared visual language for every menu (solid panels, slot widgets, rarity
/// colors, section headers). Recreating + improving the 2D game's UI: opaque
/// dark panels with accent borders, icon-based slots, generous sizing. All
/// menus build against these helpers so they stay coherent and vibrant.
/// </summary>
public static class UiTheme
{
    public static readonly Color PanelBg = new(0.10f, 0.11f, 0.16f, 0.98f);
    public static readonly Color PanelInner = new(0.14f, 0.16f, 0.22f);
    public static readonly Color SlotBg = new(0.18f, 0.20f, 0.27f);
    public static readonly Color SlotEmpty = new(0.12f, 0.13f, 0.18f);
    public static readonly Color Border = new(0.42f, 0.48f, 0.66f);
    public static readonly Color Accent = new(1f, 0.84f, 0.30f);
    public static readonly Color Text = new(0.92f, 0.94f, 1f);
    public static readonly Color Dim = new(0f, 0f, 0f, 0.62f);

    public static readonly Dictionary<string, Color> Rarity = new()
    {
        ["common"] = new Color(0.78f, 0.80f, 0.86f),
        ["uncommon"] = new Color(0.45f, 0.9f, 0.45f),
        ["rare"] = new Color(0.4f, 0.65f, 1f),
        ["epic"] = new Color(0.78f, 0.45f, 0.98f),
        ["legendary"] = new Color(1f, 0.68f, 0.25f),
    };

    public static readonly Dictionary<string, Color> TierColor = new()
    {
        ["novice"] = new Color(0.78f, 0.78f, 0.78f),
        ["apprentice"] = new Color(0.4f, 1f, 0.4f),
        ["journeyman"] = new Color(0.4f, 0.6f, 1f),
        ["expert"] = new Color(0.78f, 0.4f, 1f),
        ["master"] = new Color(1f, 0.84f, 0f),
    };

    public static StyleBoxFlat Box(Color bg, Color? border = null,
                                   int borderW = 2, int radius = 8)
    {
        var sb = new StyleBoxFlat
        {
            BgColor = bg,
            CornerRadiusTopLeft = radius,
            CornerRadiusTopRight = radius,
            CornerRadiusBottomLeft = radius,
            CornerRadiusBottomRight = radius,
            ContentMarginLeft = 8,
            ContentMarginRight = 8,
            ContentMarginTop = 6,
            ContentMarginBottom = 6,
        };
        if (border is { } b)
        {
            sb.BorderColor = b;
            sb.SetBorderWidthAll(borderW);
        }
        return sb;
    }

    /// <summary>Full-screen dim + a solid rounded panel anchored to a fraction
    /// of the viewport. Returns the inner VBox to fill with content.</summary>
    public static (Control Root, VBoxContainer Body) Overlay(
        Node host, float hMargin, float vMargin, float dimAlpha = 0.62f)
    {
        var root = new Control { Visible = false };
        root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        host.AddChild(root);

        var dim = new ColorRect { Color = new Color(0, 0, 0, dimAlpha) };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        root.AddChild(dim);

        var panel = new PanelContainer();
        panel.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        panel.AnchorLeft = hMargin;
        panel.AnchorRight = 1f - hMargin;
        panel.AnchorTop = vMargin;
        panel.AnchorBottom = 1f - vMargin;
        panel.OffsetLeft = panel.OffsetRight = panel.OffsetTop = panel.OffsetBottom = 0;
        panel.AddThemeStyleboxOverride("panel", Box(PanelBg, Border, 3, 12));
        root.AddChild(panel);

        var margin = new MarginContainer();
        foreach (var s in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{s}", 26);
        panel.AddChild(margin);

        var body = new VBoxContainer();
        body.AddThemeConstantOverride("separation", 14);
        margin.AddChild(body);
        return (root, body);
    }

    public static Label Header(string text, int size = 42)
    {
        var l = new Label { Text = text };
        l.AddThemeFontSizeOverride("font_size", size);
        l.AddThemeColorOverride("font_color", Accent);
        return l;
    }

    public static Label Section(string text, int size = 26)
    {
        var l = new Label { Text = text };
        l.AddThemeFontSizeOverride("font_size", size);
        l.AddThemeColorOverride("font_color", new Color(0.7f, 0.78f, 0.95f));
        return l;
    }

    /// <summary>An icon slot: bordered square Button with a centered icon and
    /// a bottom-right quantity label. Caller wires Pressed/GuiInput and calls
    /// SetSlot to fill it.</summary>
    public static Button Slot(int size, out TextureRect icon, out Label qty)
    {
        var btn = new Button
        {
            CustomMinimumSize = new Vector2(size, size),
            Flat = false,
        };
        btn.AddThemeStyleboxOverride("normal", Box(SlotEmpty, Border, 1, 6));
        btn.AddThemeStyleboxOverride("hover", Box(SlotBg, Accent, 1, 6));
        btn.AddThemeStyleboxOverride("pressed", Box(SlotBg, Accent, 2, 6));

        icon = new TextureRect
        {
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
            MouseFilter = Control.MouseFilterEnum.Ignore,
        };
        icon.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        icon.OffsetLeft = 4; icon.OffsetTop = 4;
        icon.OffsetRight = -4; icon.OffsetBottom = -4;
        btn.AddChild(icon);

        qty = new Label
        {
            MouseFilter = Control.MouseFilterEnum.Ignore,
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Bottom,
        };
        qty.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        qty.OffsetRight = -4; qty.OffsetBottom = -2;
        qty.AddThemeFontSizeOverride("font_size", 15);
        qty.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
        qty.AddThemeConstantOverride("outline_size", 5);
        btn.AddChild(qty);
        return btn;
    }

    public static ScrollContainer VScroll()
    {
        return new ScrollContainer
        {
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
            HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled,
        };
    }

    public static Button TextButton(string text, int size = 18)
    {
        var b = new Button { Text = text };
        b.AddThemeFontSizeOverride("font_size", size);
        return b;
    }
}
