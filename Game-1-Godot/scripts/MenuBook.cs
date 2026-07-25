using Godot;

namespace Game1.Godot;

/// <summary>
/// One page of the menu book. Pages are plain Controls; the book supplies
/// the frame, tabs, and input routing.
/// </summary>
public abstract partial class MenuPage : Control
{
    public abstract string Title { get; }
    public abstract Key Keybind { get; }
    /// <summary>Called when the page becomes the visible tab.</summary>
    public virtual void OnOpened() { }
    /// <summary>Called every frame while the page is the visible tab.</summary>
    public virtual void Tick(double delta) { }
}

/// <summary>
/// The tabbed "book" that hosts every game menu (inventory, skills, stats,
/// map, quests, encyclopedia — crafting is deliberately NOT a book page).
/// Each page keeps its own key binding: pressing it opens the book on that
/// page (or closes the book if already there); the side tabs switch pages
/// with the mouse. [Esc] closes.
/// </summary>
public partial class MenuBook : CanvasLayer
{
    private readonly List<MenuPage> _pages = new();
    private readonly List<Button> _tabButtons = new();
    private Control _root = null!;
    private MarginContainer _pageHolder = null!;
    private MenuPage? _current;
    private bool _open;

    public void AddPage(MenuPage page) => _pages.Add(page);

    public override void _Ready()
    {
        Layer = 10;
        _root = new Control { Visible = false };
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        var dim = new ColorRect { Color = UiTheme.Dim };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(dim);

        // Screen-relative frame: ~94% of the viewport, SOLID background
        var frame = new PanelContainer();
        frame.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        frame.AnchorLeft = 0.03f;
        frame.AnchorTop = 0.03f;
        frame.AnchorRight = 0.97f;
        frame.AnchorBottom = 0.97f;
        frame.OffsetLeft = frame.OffsetTop = frame.OffsetRight = frame.OffsetBottom = 0;
        frame.AddThemeStyleboxOverride("panel", UiTheme.Box(UiTheme.PanelBg, UiTheme.Border, 3, 12));
        _root.AddChild(frame);
        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 22);
        frame.AddChild(margin);

        var columns = new HBoxContainer();
        columns.AddThemeConstantOverride("separation", 18);
        margin.AddChild(columns);

        // -- side tabs --
        var tabBar = new VBoxContainer { CustomMinimumSize = new Vector2(210, 0) };
        tabBar.AddThemeConstantOverride("separation", 8);
        columns.AddChild(tabBar);
        foreach (var page in _pages)
        {
            var captured = page;
            var btn = new Button
            {
                Text = $"{page.Title}  [{page.Keybind}]",
                Alignment = HorizontalAlignment.Left,
                ToggleMode = true,
                CustomMinimumSize = new Vector2(0, 44),
            };
            btn.AddThemeFontSizeOverride("font_size", 20);
            btn.Pressed += () => Switch(captured);
            tabBar.AddChild(btn);
            _tabButtons.Add(btn);
        }
        tabBar.AddChild(new Control
        { SizeFlagsVertical = Control.SizeFlags.ExpandFill });
        var hint = new Label { Text = "[Esc] close" };
        hint.AddThemeFontSizeOverride("font_size", 15);
        hint.Modulate = new Color(1, 1, 1, 0.5f);
        tabBar.AddChild(hint);

        // -- page area fills the rest --
        _pageHolder = new MarginContainer
        {
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        columns.AddChild(_pageHolder);
        foreach (var page in _pages)
        {
            page.Visible = false;
            page.SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
            page.SizeFlagsVertical = Control.SizeFlags.ExpandFill;
            _pageHolder.AddChild(page);
        }
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey { Pressed: true, Echo: false } key) return;

        if (key.PhysicalKeycode is Key.Escape && _open)
        {
            Close();
            // Consume so this Esc doesn't also open the pause menu
            GetViewport().SetInputAsHandled();
            return;
        }

        foreach (var page in _pages)
        {
            if (key.PhysicalKeycode != page.Keybind
                && !(page.Keybind is Key.I && key.PhysicalKeycode is Key.Tab))
                continue;
            if (!_open)
            {
                // Don't open over dialogue/crafting popups
                if (!UiHub.ScreenOpen) Open(page);
            }
            else if (_current == page) Close();
            else Switch(page);
            return;
        }
    }

    public override void _Process(double delta)
    {
        if (_open) _current?.Tick(delta);
    }

    private void Open(MenuPage page)
    {
        _open = true;
        _root.Visible = true;
        UiHub.OpenScreens++;
        Switch(page);
    }

    private void Close()
    {
        _open = false;
        _root.Visible = false;
        UiHub.OpenScreens--;
    }

    private void Switch(MenuPage page)
    {
        _current = page;
        for (var i = 0; i < _pages.Count; i++)
        {
            _pages[i].Visible = _pages[i] == page;
            _tabButtons[i].ButtonPressed = _pages[i] == page;
        }
        page.OnOpened();
    }
}
