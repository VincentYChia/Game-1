using Godot;

namespace Game1.Godot;

/// <summary>
/// Base class for the six crafting minigame overlays (ADR-7: Pygame
/// minigames become 2D Control popups). The overlay owns ONLY the play
/// loop and produces a performance score 0..1; material consumption,
/// quality, output, XP and titles all run through the certified
/// CraftingSystem afterwards via the onComplete callback.
///
/// Python idioms preserved for all subclasses: modal (UiHub-gated),
/// double-[Esc] within 1.5s abandons the craft (materials lost — the
/// caller decides), first [Esc] shows a warning.
/// </summary>
public abstract partial class MinigameOverlay : CanvasLayer
{
    protected Control Root = null!;
    protected double DifficultyPoints;   // certified DifficultyCalculator points
    protected string DifficultyTier = "common";
    protected Label WarnLabel = null!;

    private Action<double>? _onComplete;
    private Action? _onAbandon;
    private double _escAt = -10;
    private bool _running;

    public bool Running => _running;

    public override void _Ready()
    {
        Layer = 20;   // minigames render on top of everything (Python parity)
        Root = new Control { Visible = false };
        Root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(Root);

        var dim = new ColorRect { Color = new Color(0, 0, 0, 0.6f) };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        Root.AddChild(dim);

        var center = new CenterContainer();
        center.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        Root.AddChild(center);
        var panel = new PanelContainer();
        center.AddChild(panel);
        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 18);
        panel.AddChild(margin);

        var host = new VBoxContainer();
        host.AddThemeConstantOverride("separation", 8);
        margin.AddChild(host);

        WarnLabel = new Label { Text = "", Modulate = new Color(1f, 0.5f, 0.4f) };
        WarnLabel.AddThemeFontSizeOverride("font_size", 15);

        BuildUi(host);
        host.AddChild(WarnLabel);
    }

    /// <summary>Subclasses build their play surface here (called once).</summary>
    protected abstract void BuildUi(VBoxContainer host);

    /// <summary>Reset play state for a fresh run of this recipe.</summary>
    protected abstract void OnBegin();

    /// <summary>Per-frame while running.</summary>
    protected virtual void OnTick(double delta) { }

    /// <summary>Gameplay input while running (Esc is handled by the base).</summary>
    protected virtual void OnInput(InputEvent @event) { }

    public void Begin(double difficultyPoints, string difficultyTier,
                      Action<double> onComplete, Action onAbandon)
    {
        DifficultyPoints = difficultyPoints;
        DifficultyTier = difficultyTier;
        _onComplete = onComplete;
        _onAbandon = onAbandon;
        _running = true;
        _escAt = -10;
        WarnLabel.Text = "";
        Root.Visible = true;
        UiHub.OpenScreens++;
        OnBegin();
    }

    /// <summary>Subclasses call this with the final performance 0..1.</summary>
    protected void Finish(double performance)
    {
        if (!_running) return;
        _running = false;
        Root.Visible = false;
        UiHub.OpenScreens--;
        _onComplete?.Invoke(Math.Clamp(performance, 0.0, 1.0));
    }

    public override void _Process(double delta)
    {
        if (_running) OnTick(delta);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (!_running) return;
        if (@event is InputEventKey
            { Pressed: true, Echo: false, PhysicalKeycode: Key.Escape })
        {
            var now = Time.GetTicksMsec() / 1000.0;
            if (now - _escAt <= 1.5)
            {
                _running = false;
                Root.Visible = false;
                UiHub.OpenScreens--;
                _onAbandon?.Invoke();
            }
            else
            {
                _escAt = now;
                WarnLabel.Text = "press [Esc] again to abandon — materials will be lost!";
            }
            GetViewport().SetInputAsHandled();
            return;
        }
        OnInput(@event);
    }
}
