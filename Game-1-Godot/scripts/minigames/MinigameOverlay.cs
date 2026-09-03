using Godot;

namespace Game1.Godot;

/// <summary>
/// The cinematic CRAFT STAGE — shared cradle for all six crafting minigames
/// (ADR-7: Pygame minigames became 2D Control popups; this is their reinvented,
/// immersive home). Every discipline now plays inside the SAME staged frame: an
/// animated per-discipline backdrop, drifting ambient particles, a header with a
/// discipline glyph + difficulty stars + live timer, and a LIVE QUALITY METER on
/// the right that climbs Normal → Fine → Superior → Masterwork → Legendary as the
/// player performs — so skill-becoming-quality is felt moment to moment.
///
/// The seam is unchanged and sacred: the overlay owns ONLY the play loop and
/// produces a performance score 0..1; material consumption, quality, output, XP
/// and titles all run through the certified CraftingSystem via onComplete.
///
/// Python idioms preserved: modal (UiHub-gated); double-[Esc] within 1.5s abandons
/// (materials lost — the caller decides), first [Esc] warns.
///
/// Subclasses override <see cref="Discipline"/> for their theme, fill their play
/// surface in <see cref="BuildUi"/>, and drive the shared feedback via SetQuality,
/// Shake, Burst, Popup, SetTimer, SetHeaderSub.
/// </summary>
public abstract partial class MinigameOverlay : CanvasLayer
{
    protected Control Root = null!;
    protected double DifficultyPoints;          // certified DifficultyCalculator points
    protected string DifficultyTier = "common";
    protected Label WarnLabel = null!;
    protected Color Accent = UiTheme.Accent;     // discipline accent for subclass draws
    protected RecipeContext? Recipe;             // the recipe being crafted (null for fishing/harvest)

    private Action<double>? _onComplete;
    private Action? _onAbandon;
    private double _escAt = -10;
    private bool _running;

    // stage furniture -----------------------------------------------------
    private Control _shake = null!;
    private ColorRect _backdrop = null!;
    private CpuParticles2D _ambient = null!;
    private Label _glyph = null!;
    private Label _titleLabel = null!;
    private Label _subLabel = null!;
    private Label _timerLabel = null!;
    private Control _stars = null!;
    private Control _meter = null!;
    private Label _bandLabel = null!;
    private double _quality;
    private double _meterFlash;
    private float _shakeAmt;
    private int _starFill = 1;

    public bool Running => _running;

    /// <summary>Discipline key for theming/style (default forge). Subclasses
    /// override — e.g. "alchemy", "refining", "engineering", "adornments",
    /// "fishing".</summary>
    protected virtual string Discipline => "smithing";

    /// <summary>A discipline can own the WHOLE viewport (an immersive first-person scene) instead of the
    /// centered dark card + side quality meter. Default false — the other five minigames are unaffected.
    /// The header/meter controls are still created (so SetTimer/SetQuality/… never null) but not mounted.</summary>
    protected virtual bool FullscreenScene => false;

    /// <summary>Optional (top, bottom, glow) backdrop colours — e.g. a light warm scene for a FullscreenScene.</summary>
    protected virtual (Color Top, Color Bottom, Color Glow)? BackdropTint => null;

    /// <summary>Whether the drifting ambient embers emit (looks like noise over a light custom scene).</summary>
    protected virtual bool ShowAmbient => true;

    public override void _Ready()
    {
        Layer = 20;   // minigames render on top of everything (Python parity)

        var st = CraftStyle.Get(Discipline);
        Accent = st.Accent;

        Root = new Control { Visible = false };
        Root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(Root);

        // animated atmospheric backdrop -----------------------------------
        var (bt, bb, bg) = BackdropTint ?? (st.Top, st.Bottom, st.Glow);
        var glowStrength = FullscreenScene ? 0.35f : 0.6f;

        // NO-SHADER fallback painted BEHIND the shader backdrop: the one shader in the crafting stack renders opaquely
        // when it compiles (so this is invisible in the normal case), but if it ever fails (old GPU / headless) the
        // player still sees a coherent staged gradient instead of a flat black card. Fix once, here, for all disciplines.
        var backdropFallback = new Control { MouseFilter = Control.MouseFilterEnum.Ignore };
        backdropFallback.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        backdropFallback.Draw += () => CraftFx.GradientBackdrop(backdropFallback, backdropFallback.Size, bt, bb, bg, new Vector2(0.5f, 0.7f), glowStrength);
        Root.AddChild(backdropFallback);

        _backdrop = new ColorRect
        {
            Material = CraftFx.Backdrop(bt, bb, bg, new Vector2(0.5f, 0.7f), glowStrength),
            MouseFilter = Control.MouseFilterEnum.Ignore,
        };
        _backdrop.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        Root.AddChild(_backdrop);

        _shake = new Control { MouseFilter = Control.MouseFilterEnum.Pass };
        _shake.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        Root.AddChild(_shake);

        _ambient = CraftFx.Ambient(st.Ember, 46, st.Rise, new Vector2(520, 40), true, 4.5f);
        _shake.AddChild(_ambient);

        // header + quality meter are always CREATED (fields populated) but only MOUNTED in the card layout
        var headerBar = BuildHeader(st);
        var meterCol = BuildQualityMeter();
        WarnLabel = new Label { Text = "", Modulate = new Color(1f, 0.5f, 0.4f) };
        WarnLabel.AddThemeFontSizeOverride("font_size", 15);
        WarnLabel.HorizontalAlignment = HorizontalAlignment.Center;

        if (FullscreenScene)
        {
            var scene = new VBoxContainer();
            scene.SetAnchorsPreset(Control.LayoutPreset.FullRect);
            _shake.AddChild(scene);
            BuildUi(scene);
            WarnLabel.SetAnchorsPreset(Control.LayoutPreset.CenterTop);
            WarnLabel.Position = new Vector2(0, 46);
            _shake.AddChild(WarnLabel);
            return;
        }

        // centered workshop card ------------------------------------------
        var center = new CenterContainer();
        center.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _shake.AddChild(center);

        var card = new PanelContainer();
        card.AddThemeStyleboxOverride("panel", UiTheme.Box(new Color(0.08f, 0.09f, 0.13f, 0.94f), st.Accent, 3, 16));
        center.AddChild(card);

        var pad = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            pad.AddThemeConstantOverride($"margin_{side}", 22);
        card.AddChild(pad);

        var column = new VBoxContainer();
        column.AddThemeConstantOverride("separation", 12);
        pad.AddChild(column);

        column.AddChild(headerBar);

        var contentRow = new HBoxContainer();
        contentRow.AddThemeConstantOverride("separation", 16);
        column.AddChild(contentRow);

        var host = new VBoxContainer { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        host.AddThemeConstantOverride("separation", 8);
        contentRow.AddChild(host);

        contentRow.AddChild(meterCol);

        BuildUi(host);
        column.AddChild(WarnLabel);
    }

    private Control BuildHeader(DisciplineStyle st)
    {
        var bar = new HBoxContainer();
        bar.AddThemeConstantOverride("separation", 14);

        _glyph = new Label { Text = st.Glyph };
        _glyph.AddThemeFontSizeOverride("font_size", 46);
        _glyph.AddThemeColorOverride("font_color", st.Accent);
        _glyph.VerticalAlignment = VerticalAlignment.Center;
        bar.AddChild(_glyph);

        var titleCol = new VBoxContainer { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        titleCol.AddThemeConstantOverride("separation", 0);
        _titleLabel = new Label { Text = st.Name };
        _titleLabel.AddThemeFontSizeOverride("font_size", 30);
        _titleLabel.AddThemeColorOverride("font_color", UiTheme.Text);
        titleCol.AddChild(_titleLabel);
        _subLabel = new Label { Text = "", Modulate = new Color(1, 1, 1, 0.7f) };
        _subLabel.AddThemeFontSizeOverride("font_size", 15);
        titleCol.AddChild(_subLabel);
        bar.AddChild(titleCol);

        _stars = new Control { CustomMinimumSize = new Vector2(5 * 24, 22) };
        _stars.Draw += DrawStars;
        bar.AddChild(_stars);

        _timerLabel = new Label { Text = "", HorizontalAlignment = HorizontalAlignment.Right };
        _timerLabel.AddThemeFontSizeOverride("font_size", 22);
        _timerLabel.CustomMinimumSize = new Vector2(110, 0);
        bar.AddChild(_timerLabel);

        return bar;
    }

    private Control BuildQualityMeter()
    {
        var col = new VBoxContainer { SizeFlagsVertical = Control.SizeFlags.ShrinkCenter };
        col.AddThemeConstantOverride("separation", 6);

        _meter = new Control { CustomMinimumSize = new Vector2(58, 300) };
        _meter.Draw += DrawMeter;
        col.AddChild(_meter);

        _bandLabel = new Label
        {
            Text = "Normal",
            HorizontalAlignment = HorizontalAlignment.Center,
            CustomMinimumSize = new Vector2(58, 0),
        };
        _bandLabel.AddThemeFontSizeOverride("font_size", 14);
        _bandLabel.AddThemeColorOverride("font_color", CraftFx.QualityBands[0].Col);
        col.AddChild(_bandLabel);
        return col;
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
        => Begin(difficultyPoints, difficultyTier, null, onComplete, onAbandon);

    public void Begin(double difficultyPoints, string difficultyTier, RecipeContext? recipe,
                      Action<double> onComplete, Action onAbandon)
    {
        Recipe = recipe;
        DifficultyPoints = difficultyPoints;
        DifficultyTier = difficultyTier;
        _onComplete = onComplete;
        _onAbandon = onAbandon;
        _running = true;
        _escAt = -10;
        _quality = 0;
        _meterFlash = 0;
        _shakeAmt = 0;
        WarnLabel.Text = "";
        _starFill = TierStars(difficultyTier);

        var sub = $"{char.ToUpperInvariant(DifficultyTier[0])}{DifficultyTier[1..]} craft · {DifficultyPoints:0.#} pts";
        _subLabel.Text = sub;
        _timerLabel.Text = "";
        Root.Visible = true;

        // seat the ember emitter along the bottom of the viewport
        var vp = GetViewport().GetVisibleRect().Size;
        _ambient.Position = new Vector2(vp.X * 0.5f, vp.Y + 10);
        _ambient.Emitting = ShowAmbient;

        UiHub.OpenScreens++;
        _stars.QueueRedraw();
        _meter.QueueRedraw();
        OnBegin();
    }

    /// <summary>Subclasses call this with the final performance 0..1.</summary>
    protected void Finish(double performance)
    {
        if (!_running) return;
        _running = false;
        _ambient.Emitting = false;
        Root.Visible = false;
        UiHub.OpenScreens--;
        _onComplete?.Invoke(Math.Clamp(performance, 0.0, 1.0));
    }

    /// <summary>End the run as a FAILED craft — materials are lost and NO item is produced
    /// (routes through the caller's abandon path). Use when the player misses the goal entirely
    /// (e.g. the mixture ends outside the target band / boils over).</summary>
    protected void FailCraft()
    {
        if (!_running) return;
        _running = false;
        _ambient.Emitting = false;
        Root.Visible = false;
        UiHub.OpenScreens--;
        _onAbandon?.Invoke();
    }

    public override void _Process(double delta)
    {
        if (!Root.Visible) return;

        // shake decay + offset
        if (_shakeAmt > 0.01f)
        {
            _shakeAmt = Mathf.Max(0f, _shakeAmt - (float)delta * 40f);
            _shake.Position = new Vector2(GD.Randf() * 2f - 1f, GD.Randf() * 2f - 1f) * _shakeAmt;
        }
        else if (_shake.Position != Vector2.Zero) _shake.Position = Vector2.Zero;

        if (_meterFlash > 0) { _meterFlash = Math.Max(0, _meterFlash - delta * 3.0); _meter.QueueRedraw(); }

        if (_running) OnTick(delta);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (!_running) return;
        if (@event is InputEventKey { Pressed: true, Echo: false, PhysicalKeycode: Key.Escape })
        {
            var now = Time.GetTicksMsec() / 1000.0;
            if (now - _escAt <= 1.5)
            {
                _running = false;
                _ambient.Emitting = false;
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

    // ---- shared feedback helpers (subclasses call these) --------------------

    /// <summary>Feed the live quality meter (0..1). Drives the band readout.</summary>
    protected void SetQuality(double q01)
    {
        _quality = Math.Clamp(q01, 0.0, 1.0);
        var band = CraftFx.Band(_quality);
        _bandLabel.Text = band.Name;
        _bandLabel.AddThemeColorOverride("font_color", band.Col);
        _meter.QueueRedraw();
    }

    /// <summary>A bright pulse on the quality meter (a good hit landed).</summary>
    protected void FlashQuality() { _meterFlash = 1.0; _meter.QueueRedraw(); }

    /// <summary>Kick the whole stage (impact feedback).</summary>
    protected void Shake(float amt = 7f) => _shakeAmt = Mathf.Max(_shakeAmt, amt);

    /// <summary>Set/refresh the header countdown; reddens under warnAt seconds.</summary>
    protected void SetTimer(double seconds, double warnAt = 10)
    {
        _timerLabel.Text = $"{seconds:0.0}s";
        _timerLabel.Modulate = seconds <= warnAt
            ? new Color(1f, 0.3f, 0.3f, 0.65f + 0.35f * Mathf.Sin(Time.GetTicksMsec() / 110f))
            : seconds <= warnAt * 2 ? new Color(1f, 0.9f, 0.35f) : Colors.White;
    }

    protected void HideTimer() => _timerLabel.Text = "";

    /// <summary>Secondary header line (recipe params, stage name, etc.).</summary>
    protected void SetHeaderSub(string text) => _subLabel.Text = text;

    protected void Popup(CanvasItem parent, Vector2 pos, string text, Color col, int size = 22)
        => CraftFx.Popup(parent, pos, text, col, size);

    protected void Burst(CanvasItem parent, Vector2 pos, Color col, int n = 18, float speed = 220f)
        => CraftFx.Burst(parent, pos, col, n, speed);

    private static int TierStars(string tier) => tier switch
    {
        "common" => 1,
        "uncommon" => 2,
        "rare" => 3,
        "epic" => 4,
        "legendary" => 5,
        _ => 1,
    };

    private void DrawStars() => CraftFx.Stars(_stars, Vector2.Zero, _starFill, 5, 20f, Accent, 4f);

    private void DrawMeter()
    {
        var size = _meter.Size;
        var trackW = 34f;
        var x = (size.X - trackW) * 0.5f;
        var top = 6f; var bot = size.Y - 6f; var h = bot - top;
        var track = new Rect2(x, top, trackW, h);

        // band backdrop segments (bottom Normal → top Legendary)
        CraftFx.RoundRect(_meter, track, new Color(0.05f, 0.06f, 0.09f), null, 0, 8);
        for (var i = 0; i < CraftFx.QualityBands.Length; i++)
        {
            var lo = (float)CraftFx.QualityBands[i].Min;
            var hi = i + 1 < CraftFx.QualityBands.Length ? (float)CraftFx.QualityBands[i + 1].Min : 1f;
            var segTop = top + h * (1f - hi);
            var segH = h * (hi - lo);
            var c = CraftFx.QualityBands[i].Col;
            _meter.DrawRect(new Rect2(x, segTop, trackW, segH), new Color(c.R, c.G, c.B, 0.12f));
        }

        // fill up to current quality, colored by its band
        var band = CraftFx.Band(_quality);
        var fillH = h * (float)_quality;
        if (fillH > 1)
        {
            var fr = new Rect2(x, bot - fillH, trackW, fillH);
            CraftFx.RoundRect(_meter, fr, new Color(band.Col.R, band.Col.G, band.Col.B, 0.85f), null, 0, 8);
            var edge = new Vector2(x + trackW * 0.5f, bot - fillH);
            CraftFx.Glow(_meter, edge, 16f + 8f * (float)_meterFlash,
                new Color(band.Col.R, band.Col.G, band.Col.B, 0.6f + 0.4f * (float)_meterFlash));
        }

        // band boundary ticks
        foreach (var (min, _, _) in CraftFx.QualityBands)
        {
            if (min <= 0) continue;
            var ty = bot - h * (float)min;
            _meter.DrawLine(new Vector2(x, ty), new Vector2(x + trackW, ty), new Color(0, 0, 0, 0.5f), 1.5f);
        }
        _meter.DrawRect(track, new Color(band.Col.R, band.Col.G, band.Col.B, 0.8f), false, 2f);
    }
}
