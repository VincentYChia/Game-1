using Godot;

namespace Game1.Godot;

/// <summary>
/// NPC dialogue popup: bottom-of-screen conversation panel. Lines are built
/// from the certified world data (village name, nation) — the full NPC
/// speechbank/agent system is a later porting tranche; this gives villages
/// their voice today. Click / [E] / [Space] advances, [Esc] closes.
/// </summary>
public partial class DialogueScreen : CanvasLayer
{
    private Control _root = null!;
    private Label _name = null!;
    private Label _text = null!;
    private bool _open;
    private List<string> _lines = new();
    private int _line;

    public override void _Ready()
    {
        Layer = 11;
        _root = new Control { Visible = false };
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        var panel = new PanelContainer
        {
            AnchorLeft = 0.22f, AnchorRight = 0.78f,
            AnchorTop = 0.74f, AnchorBottom = 0.92f,
        };
        _root.AddChild(panel);

        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 14);
        panel.AddChild(margin);

        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 6);
        margin.AddChild(box);

        _name = new Label { Text = "" };
        _name.AddThemeFontSizeOverride("font_size", 22);
        _name.Modulate = new Color(1f, 0.9f, 0.6f);
        box.AddChild(_name);

        _text = new Label
        { Text = "", AutowrapMode = TextServer.AutowrapMode.WordSmart };
        _text.AddThemeFontSizeOverride("font_size", 18);
        box.AddChild(_text);

        var hint = new Label { Text = "click to continue  ·  [Esc] leave" };
        hint.AddThemeFontSizeOverride("font_size", 12);
        hint.Modulate = new Color(1, 1, 1, 0.5f);
        box.AddChild(hint);
    }

    public void Open(LiveNpc npc)
    {
        if (_open) return;
        _open = true;
        _root.Visible = true;
        UiHub.OpenScreens++;

        _lines = BuildLines(npc);
        _line = 0;
        _name.Text = $"{npc.Name} — {npc.VillageName}";
        _text.Text = _lines[0];
    }

    private static List<string> BuildLines(LiveNpc npc) => new()
    {
        $"Welcome to {npc.VillageName}, traveler.",
        $"These are {npc.NationName} lands — mind the wilds beyond our walls.",
        $"I'm {npc.Name}. If you need supplies, gather what the land offers "
            + "and craft at the stations.",
        "Safe travels out there.",
    };

    public override void _UnhandledInput(InputEvent @event)
    {
        if (!_open) return;
        var advance =
            @event is InputEventMouseButton { ButtonIndex: MouseButton.Left, Pressed: true }
            || @event is InputEventKey
            { Pressed: true, Echo: false, PhysicalKeycode: Key.E or Key.Space };
        var close = @event is InputEventKey
        { Pressed: true, Echo: false, PhysicalKeycode: Key.Escape };

        if (close) { Close(); return; }
        if (!advance) return;

        _line++;
        if (_line >= _lines.Count) Close();
        else _text.Text = _lines[_line];
    }

    private void Close()
    {
        _open = false;
        _root.Visible = false;
        UiHub.OpenScreens--;
    }
}
