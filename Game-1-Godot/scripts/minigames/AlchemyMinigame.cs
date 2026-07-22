using Godot;

namespace Game1.Godot;

/// <summary>
/// Reaction-chain brewing (alchemy) — sequential timing game. Each ingredient
/// is a bubbling reaction advancing through 5 stages on fixed per-type timers
/// (stable/moderate/volatile/legendary); the player presses [C] CHAIN to lock
/// the current oscillating quality and start the next ingredient, or [S]
/// STABILIZE to lock and finish. Letting a reaction pass stage 5 explodes it
/// (+0.10 flat progress, −0.15 performance each). Performance =
/// clamp(chainRatio·0.6 + progress·0.4 − explosions·0.15) + 0.10 first-try
/// bonus (Python applies it every run — quirk preserved; exploded reactions
/// also still count toward chainRatio — quirk preserved). Difficulty points
/// interpolate time limit 60→20s and reaction count 2→6 over 1-80 points; the
/// tier label picks ingredient behavior types. Deviation: with no recipe
/// material IDs available, vowel-derived secret values are randomized and
/// per-ingredient max-quality shares use the equal 1/N split (the contract's
/// sanctioned zero-vowel fallback).
/// </summary>
public partial class AlchemyMinigame : MinigameOverlay
{
    // Stage duration tables, seconds, stages 1-5 (alchemy.py:135-154). The
    // stage-3 entry IS the sweet-spot duration.
    private static readonly Dictionary<string, double[]> StageDurations = new()
    {
        ["stable"] = new[] { 1.0, 2.5, 2.0, 2.0, 1.5 },
        ["moderate"] = new[] { 0.8, 2.0, 1.5, 1.5, 1.2 },
        ["volatile"] = new[] { 0.5, 1.5, 1.0, 1.0, 0.8 },
        ["legendary"] = new[] { 0.4, 1.0, 0.5, 0.7, 0.5 },
    };

    // Fake glow-spike positions within stage 2 (visual only).
    private static readonly Dictionary<string, double[]> FalsePeaks = new()
    {
        ["stable"] = Array.Empty<double>(),
        ["moderate"] = new[] { 0.4, 0.7 },
        ["volatile"] = new[] { 0.3, 0.5, 0.7, 0.9 },
        ["legendary"] = new[] { 0.2, 0.4, 0.5, 0.6, 0.8 },
    };

    // Difficulty tier → first three ingredient types (alchemy.py:446-479).
    private static readonly Dictionary<string, string[]> TierTypes = new()
    {
        ["common"] = new[] { "stable", "stable", "moderate" },
        ["uncommon"] = new[] { "stable", "moderate", "moderate" },
        ["rare"] = new[] { "moderate", "moderate", "volatile" },
        ["epic"] = new[] { "moderate", "volatile", "volatile" },
        ["legendary"] = new[] { "volatile", "volatile", "legendary" },
    };

    private static readonly Dictionary<string, Color> TypeColors = new()
    {
        ["stable"] = new Color(0.35f, 0.75f, 0.55f),
        ["moderate"] = new Color(0.85f, 0.70f, 0.32f),
        ["volatile"] = new Color(0.90f, 0.45f, 0.25f),
        ["legendary"] = new Color(0.70f, 0.40f, 0.90f),
    };

    private static readonly string[] StageNames =
    { "initiation", "building", "SWEET SPOT", "degrading", "CRITICAL" };

    private sealed class Ingredient
    {
        public string Type = "moderate";
        public double Secret;      // stands in for the vowel-derived value
        public int Oscillations;   // <0.25→1, <0.65→2, else 3
        public double MaxQuality;  // equal 1/N split (shares sum to 1.0)
    }

    private readonly Random _rng = new();
    private readonly List<Ingredient> _ingredients = new();
    private readonly List<double> _locked = new();

    private int _index;
    private int _stage;             // 1..5 live, 6 = exploded
    private double _stageProgress;  // 0..1 within the current stage
    private double _totalProgress;  // banked quality, 0..1 across the brew
    private int _explosions;
    private double _timeLeft;
    private int _timeLimit;
    private double _norm;           // difficulty 0..1 over points 1-80
    private bool _done;
    private double _finalPerf;

    private Label _infoLabel = null!;
    private Label _timerLabel = null!;
    private ProgressBar _timerBar = null!;
    private Control _bubble = null!;
    private Label _stageLabel = null!;
    private Label _ingredientLabel = null!;
    private Label _lockedLabel = null!;
    private ProgressBar _progressBar = null!;
    private HBoxContainer _playBox = null!;
    private VBoxContainer _resultBox = null!;
    private Label _resultLabel = null!;
    private Label _resultDetail = null!;

    protected override void BuildUi(VBoxContainer host)
    {
        var title = new Label { Text = "REACTION CHAIN BREWING" };
        title.AddThemeFontSizeOverride("font_size", 26);
        host.AddChild(title);

        _infoLabel = new Label { Modulate = new Color(1, 1, 1, 0.75f) };
        _infoLabel.AddThemeFontSizeOverride("font_size", 14);
        host.AddChild(_infoLabel);

        _timerLabel = new Label();
        _timerLabel.AddThemeFontSizeOverride("font_size", 16);
        host.AddChild(_timerLabel);
        _timerBar = new ProgressBar
        {
            MinValue = 0, MaxValue = 1, Value = 1, ShowPercentage = false,
            CustomMinimumSize = new Vector2(360, 10),
        };
        host.AddChild(_timerBar);

        _bubble = new Control
        {
            CustomMinimumSize = new Vector2(360, 180),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
        };
        _bubble.Draw += DrawBubble;
        host.AddChild(_bubble);

        _stageLabel = new Label
        { HorizontalAlignment = HorizontalAlignment.Center };
        _stageLabel.AddThemeFontSizeOverride("font_size", 18);
        host.AddChild(_stageLabel);

        _ingredientLabel = new Label();
        _ingredientLabel.AddThemeFontSizeOverride("font_size", 15);
        host.AddChild(_ingredientLabel);

        _lockedLabel = new Label { Modulate = new Color(1, 1, 1, 0.7f) };
        _lockedLabel.AddThemeFontSizeOverride("font_size", 14);
        host.AddChild(_lockedLabel);

        _progressBar = new ProgressBar
        {
            MinValue = 0, MaxValue = 1, ShowPercentage = false,
            CustomMinimumSize = new Vector2(360, 14),
        };
        host.AddChild(_progressBar);

        _playBox = new HBoxContainer();
        _playBox.AddThemeConstantOverride("separation", 12);
        host.AddChild(_playBox);
        var chain = new Button { Text = "CHAIN [C]" };
        chain.Pressed += Chain;
        _playBox.AddChild(chain);
        var stabilize = new Button { Text = "STABILIZE [S]" };
        stabilize.Pressed += Stabilize;
        _playBox.AddChild(stabilize);
        var hint = new Label
        {
            Text = "lock at the glow peak — past CRITICAL it explodes!",
            Modulate = new Color(0.6f, 0.75f, 1f),
        };
        hint.AddThemeFontSizeOverride("font_size", 13);
        _playBox.AddChild(hint);

        _resultBox = new VBoxContainer { Visible = false };
        _resultBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_resultBox);
        _resultLabel = new Label();
        _resultLabel.AddThemeFontSizeOverride("font_size", 20);
        _resultBox.AddChild(_resultLabel);
        _resultDetail = new Label();
        _resultDetail.AddThemeFontSizeOverride("font_size", 15);
        _resultBox.AddChild(_resultDetail);
        var collect = new Button { Text = "COLLECT" };
        collect.Pressed += () => Finish(_finalPerf);
        _resultBox.AddChild(collect);
    }

    protected override void OnBegin()
    {
        _norm = Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);
        _timeLimit = (int)Math.Round(60.0 + _norm * (20.0 - 60.0));
        var count = Math.Max(2, (int)Math.Round(2.0 + _norm * 4.0));
        var volatility = _norm;   // interpolated 0→1 (difficulty_calculator.py)

        _ingredients.Clear();
        var tierList = TierTypes.TryGetValue(DifficultyTier, out var tl)
            ? tl : TierTypes["common"];
        for (var i = 0; i < count; i++)
        {
            var type = i < 3 ? tierList[i]
                : volatility > 0.7 ? "legendary"
                : volatility > 0.4 ? "volatile"
                : volatility > 0.2 ? "moderate" : "stable";
            var secret = _rng.NextDouble();
            _ingredients.Add(new Ingredient
            {
                Type = type,
                Secret = secret,
                Oscillations = secret < 0.25 ? 1 : secret < 0.65 ? 2 : 3,
                MaxQuality = 1.0 / count,
            });
        }

        _index = 0;
        _stage = 1;
        _stageProgress = 0;
        _totalProgress = 0;
        _explosions = 0;
        _locked.Clear();
        _timeLeft = _timeLimit;
        _done = false;
        _playBox.Visible = true;
        _resultBox.Visible = false;
        _infoLabel.Text = $"alchemy · {DifficultyTier} ({DifficultyPoints:0.#} pts)"
                          + $" · {count} reactions · {_timeLimit}s";
        RefreshHud();
    }

    protected override void OnTick(double delta)
    {
        _bubble.QueueRedraw();
        if (_done) return;

        _timeLeft -= delta;
        if (_timeLeft <= 0)
        {
            _timeLeft = 0;
            Stabilize();   // banks the CURRENT oscillating value (can be a trough)
            return;
        }

        var ing = _ingredients[_index];
        _stageProgress += delta / StageDurations[ing.Type][_stage - 1];
        if (_stageProgress >= 1.0)
        {
            _stageProgress = 0;
            _stage++;
            if (_stage > 5) Explode();
        }
        RefreshHud();
    }

    /// <summary>Quality if locked right now (alchemy.py:227-290).</summary>
    private double QualityNow()
    {
        if (_stage >= 6) return 0.0;
        var ing = _ingredients[_index];
        var osc = ing.Oscillations;
        var total = (_stage - 1 + _stageProgress) / 5.0;
        var cycleProgress = total * osc;
        var currentCycle = (int)cycleProgress;
        var cycleValue = Math.Sin((cycleProgress - currentCycle) * Math.PI);
        var amplitude = osc == 1
            ? 1.0 : 0.6 + 0.4 * Math.Min(currentCycle, osc - 1) / (osc - 1);
        var finalPeak = (osc - 0.5) / osc;
        var baseFraction = Math.Min(0.45, 0.15 + total / finalPeak * 0.30);
        var quality = (baseFraction + cycleValue * amplitude * 0.55) * ing.MaxQuality;
        return Math.Clamp(quality, 0.0, ing.MaxQuality);
    }

    private void Chain()
    {
        if (_done || !Running) return;
        var q = QualityNow();
        _totalProgress += q;
        _locked.Add(q);
        AdvanceOrEnd();
    }

    private void Stabilize()
    {
        if (_done || !Running) return;
        if (_index < _ingredients.Count)
        {
            var q = QualityNow();
            _totalProgress += q;
            _locked.Add(q);
            _index++;
        }
        End();
    }

    private void Explode()
    {
        _explosions++;
        _totalProgress += 0.10;   // flat consolation (alchemy.py:562)
        _locked.Add(0.0);         // still counts toward chainRatio (quirk)
        AdvanceOrEnd();
    }

    private void AdvanceOrEnd()
    {
        _index++;
        if (_index >= _ingredients.Count) { End(); return; }
        _stage = 1;
        _stageProgress = 0;
        RefreshHud();
    }

    private void End()
    {
        _done = true;
        var total = Math.Clamp(_totalProgress, 0.0, 1.0);
        var chainRatio = (double)_locked.Count / _ingredients.Count;
        var perf = Math.Clamp(
            chainRatio * 0.6 + total * 0.4 - _explosions * 0.15, 0.0, 1.0);
        _finalPerf = Math.Min(1.0, perf + 0.10);   // first-try bonus, every run
        var earned = (int)(total * 100);

        if (total < 0.25)   // failure threshold (alchemy.py:674)
        {
            var loss = 0.30 + _norm * 0.60;
            _resultLabel.Text = "BREW FAILED";
            _resultDetail.Text = $"progress {earned}/100 · ~{loss:P0} materials lost"
                                 + $" · explosions: {_explosions}";
        }
        else
        {
            var tier = _finalPerf < 0.25 ? "Normal"
                : _finalPerf < 0.50 ? "Fine"
                : _finalPerf < 0.75 ? "Superior"
                : _finalPerf < 0.90 ? "Masterwork" : "Legendary";
            _resultLabel.Text = $"BREW COMPLETE — {tier}";
            _resultDetail.Text = $"Quality: {earned}/100 points"
                                 + $" · chains {_locked.Count}/{_ingredients.Count}"
                                 + $" · explosions: {_explosions}";
        }
        _playBox.Visible = false;
        _resultBox.Visible = true;
        RefreshHud();
    }

    protected override void OnInput(InputEvent @event)
    {
        if (@event is not InputEventKey { Pressed: true, Echo: false } key) return;
        if (_done)
        {
            if (key.PhysicalKeycode is Key.Space or Key.Enter) Finish(_finalPerf);
            return;
        }
        switch (key.PhysicalKeycode)
        {
            case Key.C: Chain(); GetViewport().SetInputAsHandled(); break;
            case Key.S: Stabilize(); GetViewport().SetInputAsHandled(); break;
        }
    }

    private void RefreshHud()
    {
        _timerLabel.Text = $"Time: {_timeLeft:0.0}s";
        _timerBar.Value = _timeLimit > 0 ? _timeLeft / _timeLimit : 0;
        _progressBar.Value = Math.Clamp(_totalProgress, 0.0, 1.0);
        var parts = _locked.Select(q => q <= 0 ? "boom" : $"{q:0.00}");
        _lockedLabel.Text = "locked: "
            + (_locked.Count == 0 ? "—" : string.Join(", ", parts))
            + $"   |   progress {(int)(Math.Clamp(_totalProgress, 0, 1) * 100)}/100";
        if (_done || _index >= _ingredients.Count)
        {
            _stageLabel.Text = "";
            _ingredientLabel.Text = "";
            return;
        }
        var ing = _ingredients[_index];
        _stageLabel.Text = $"Stage {Math.Min(_stage, 5)}/5 — {StageNames[Math.Min(_stage, 5) - 1]}";
        _ingredientLabel.Text = $"Ingredient {_index + 1}/{_ingredients.Count}"
                                + $" ({ing.Type}) · share {ing.MaxQuality:P0}"
                                + $" · {ing.Oscillations} pulse(s)";
    }

    private void DrawBubble()
    {
        var c = _bubble.Size / 2f;
        if (_done || _index >= _ingredients.Count)
        {
            _bubble.DrawCircle(c, 24f, new Color(0.4f, 0.4f, 0.45f, 0.5f));
            return;
        }
        var ing = _ingredients[_index];
        var baseColor = TypeColors[ing.Type];
        var prog = (float)_stageProgress;
        float radius, glow;
        switch (_stage)
        {
            case 1: radius = 16f + prog * 8f; glow = 0.20f; break;
            case 2:
                radius = 24f + prog * 14f;
                glow = 0.35f;
                foreach (var peak in FalsePeaks[ing.Type])
                    if (Math.Abs(prog - peak) < 0.06) glow = 0.85f;   // fake spike
                break;
            case 3: radius = 40f; glow = 0.90f; break;               // sweet spot
            case 4:
                radius = 40f;
                glow = 0.45f + 0.15f * Mathf.Sin(Time.GetTicksMsec() / 60f);
                baseColor = baseColor.Lerp(new Color(0.3f, 0.3f, 0.3f), prog * 0.5f);
                break;
            default:
                radius = 52f + prog * 8f;                            // critical
                glow = 0.12f;
                baseColor = baseColor.Darkened(0.6f);
                break;
        }
        // Oscillation shimmer rides on the same sine the quality curve uses.
        var shimmer = (float)(QualityNow() / ing.MaxQuality);
        _bubble.DrawCircle(c, radius + 16f * glow,
            new Color(baseColor, 0.15f + 0.35f * glow * shimmer));
        _bubble.DrawCircle(c, radius, baseColor.Lerp(Colors.White, glow * 0.4f));
        _bubble.DrawArc(c, radius + 20f, 0, Mathf.Tau, 48,
            new Color(baseColor, 0.20f + 0.5f * shimmer), 3f);
    }
}
