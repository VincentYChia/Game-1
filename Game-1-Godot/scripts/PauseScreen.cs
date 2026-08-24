using Godot;

namespace Game1.Godot;

/// <summary>
/// Pause menu ([Esc] when nothing else is open — the END of the Python ESC
/// priority chain, game_engine.py:847-853): Return / Save &amp; Exit / Exit
/// without saving. Also owns the persistence utility keys: [F8] quick
/// save, [F9] load (game_engine.py:1186-1203, 1231-1286).
/// </summary>
public partial class PauseScreen : CanvasLayer
{
    private readonly CombatWorld _combat;
    private readonly PlayerController _player;
    private Control _root = null!;
    private Label _status = null!;
    private bool _open;

    /// <summary>Wired by WorldBootstrap so the Controls button can open it.</summary>
    public ControlsScreen? Controls { get; set; }

    public PauseScreen(CombatWorld combat, PlayerController player)
    {
        _combat = combat;
        _player = player;
    }

    public override void _Ready()
    {
        Layer = 30;   // pause draws over everything (Python render order)
        _root = new Control { Visible = false };
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        var dim = new ColorRect { Color = new Color(0, 0, 0, 0.6f) };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(dim);

        var center = new CenterContainer();
        center.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(center);
        var panel = new PanelContainer();
        panel.AddThemeStyleboxOverride("panel",
            UiTheme.Box(UiTheme.PanelBg, UiTheme.Border, 3, 14));
        center.AddChild(panel);
        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 48);
        panel.AddChild(margin);

        var box = new VBoxContainer { CustomMinimumSize = new Vector2(560, 0) };
        box.AddThemeConstantOverride("separation", 18);
        margin.AddChild(box);

        var title = new Label
        { Text = "PAUSED", HorizontalAlignment = HorizontalAlignment.Center };
        title.AddThemeFontSizeOverride("font_size", 52);
        title.AddThemeColorOverride("font_color", UiTheme.Accent);
        box.AddChild(title);

        AddButton(box, "Return to game", Toggle);
        AddButton(box, "Controls", () =>
        {
            Toggle();
            Controls?.Open();
        });
        AddButton(box, "Save & Exit", () =>
        {
            SaveSystem.Save(_combat, _player);
            GetTree().Quit();
        });
        AddButton(box, "Exit without saving", () => GetTree().Quit());

        _status = new Label
        {
            Text = "[F8] quick save   ·   [F9] load",
            HorizontalAlignment = HorizontalAlignment.Center,
            Modulate = new Color(1, 1, 1, 0.6f),
        };
        _status.AddThemeFontSizeOverride("font_size", 16);
        box.AddChild(_status);
    }

    private static void AddButton(VBoxContainer box, string text, Action action)
    {
        var btn = new Button
        { Text = text, CustomMinimumSize = new Vector2(0, 58) };
        btn.AddThemeFontSizeOverride("font_size", 26);
        btn.Pressed += () => action();
        box.AddChild(btn);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey { Pressed: true, Echo: false } key) return;

        if (key.PhysicalKeycode is Key.F8)
        {
            _status.Text = SaveSystem.Save(_combat, _player);
            return;
        }
        if (key.PhysicalKeycode is Key.F9)
        {
            _status.Text = SaveSystem.Load(_combat, _player);
            return;
        }
        if (key.PhysicalKeycode is not Key.Escape) return;

        if (_open) Toggle();
        else if (!UiHub.ScreenOpen) Toggle();   // end of the ESC chain
    }

    private void Toggle()
    {
        _open = !_open;
        _root.Visible = _open;
        UiHub.OpenScreens += _open ? 1 : -1;
        if (_open) _status.Text = "[F8] quick save   ·   [F9] load";
    }
}
