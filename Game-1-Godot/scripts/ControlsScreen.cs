using Godot;

namespace Game1.Godot;

/// <summary>
/// Options / Controls reference (item 5). A solid panel listing every key
/// binding grouped by category. Opened from the pause menu's "Controls"
/// button; [Esc] closes.
/// </summary>
public partial class ControlsScreen : CanvasLayer
{
    private static readonly (string Section, (string Key, string Action)[] Rows)[] Bindings =
    {
        ("Movement", new[]
        {
            ("W A S D", "Move (camera-relative)"),
            ("Shift", "Sprint"),
            ("Space", "Jump"),
        }),
        ("Camera", new[]
        {
            ("Right-drag", "Look / aim"),
            ("Mouse to screen edge", "Glide camera to recenter (center is a dead zone)"),
            ("Shift + Mouse wheel", "Zoom in / out (full in = first person)"),
        }),
        ("Combat & Interaction", new[]
        {
            ("Left-click", "Attack, gather, talk, or open a station — whatever you click"),
            ("E", "Gather the nearest resource"),
            ("F", "Talk to the nearest NPC"),
            ("1 – 5", "Use hotbar skill (aimed at the mouse)"),
        }),
        ("Menus", new[]
        {
            ("I  /  Tab", "Inventory"),
            ("C", "Character / Stats"),
            ("K", "Skills"),
            ("J", "Quest Log"),
            ("L", "Encyclopedia"),
            ("M", "World Map"),
            ("Esc", "Pause menu / close a menu"),
        }),
        ("Saving", new[]
        {
            ("F8", "Quick save"),
            ("F9", "Load save"),
        }),
        ("Debug", new[]
        {
            ("F1", "Toggle: give all materials"),
            ("F2", "Learn all skills"),
            ("F3", "Grant all titles"),
            ("F4", "Max level + stats"),
            ("F5 / F6", "Teleport to prev / next biome"),
            ("F7", "Toggle infinite durability"),
        }),
    };

    private Control _root = null!;
    private bool _open;

    public override void _Ready()
    {
        Layer = 31;   // above the pause menu
        var (root, body) = UiTheme.Overlay(this, 0.14f, 0.05f, 0.72f);
        _root = root;

        body.AddChild(UiTheme.Header("Controls"));

        var scroll = UiTheme.VScroll();
        body.AddChild(scroll);
        var list = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        list.AddThemeConstantOverride("separation", 8);
        scroll.AddChild(list);

        foreach (var (section, rows) in Bindings)
        {
            list.AddChild(UiTheme.Section(section));
            foreach (var (key, action) in rows)
            {
                var row = new HBoxContainer();
                row.AddThemeConstantOverride("separation", 20);
                list.AddChild(row);

                var keyLabel = new Label
                {
                    Text = key,
                    CustomMinimumSize = new Vector2(280, 0),
                };
                keyLabel.AddThemeFontSizeOverride("font_size", 19);
                keyLabel.AddThemeColorOverride("font_color", UiTheme.Accent);
                row.AddChild(keyLabel);

                var actLabel = new Label
                {
                    Text = action,
                    SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
                    AutowrapMode = TextServer.AutowrapMode.WordSmart,
                };
                actLabel.AddThemeFontSizeOverride("font_size", 19);
                actLabel.AddThemeColorOverride("font_color", UiTheme.Text);
                row.AddChild(actLabel);
            }
            list.AddChild(new Control { CustomMinimumSize = new Vector2(0, 8) });
        }

        var hint = new Label { Text = "[Esc] close" };
        hint.AddThemeFontSizeOverride("font_size", 15);
        hint.Modulate = new Color(1, 1, 1, 0.55f);
        body.AddChild(hint);
    }

    public void Open()
    {
        if (_open) return;
        _open = true;
        _root.Visible = true;
        UiHub.OpenScreens++;
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (_open && @event is InputEventKey
            { Pressed: true, Echo: false, PhysicalKeycode: Key.Escape })
        {
            _open = false;
            _root.Visible = false;
            UiHub.OpenScreens--;
            GetViewport().SetInputAsHandled();
        }
    }
}
