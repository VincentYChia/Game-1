using Godot;

namespace Game1.Godot;

/// <summary>
/// Spirit Wheel (adornments/enchanting) — pure gambling, no dexterity input.
/// 20-slice wheel (green/grey/red), 3 spins, starting 100 Essence. The player
/// bets via slider / quick-bet buttons, spins, and the slice color pays a
/// per-spin multiplier (later spins have worse wheels AND worse payouts).
/// Performance = clamp(finalEssence / 200) + 0.10 first-try bonus (which the
/// Python original applies on EVERY run — quirk preserved). The wheel always
/// "succeeds"; a bad run just means low performance.
/// </summary>
public partial class EnchantingMinigame : MinigameOverlay
{
    private const int Slices = 20;
    private const int SpinsPerGame = 3;
    private const int StartingCurrency = 100;
    private const double SpinDurationMs = 2000.0;

    // [spin, color] with color 0=green, 1=grey, 2=red (enchanting.py:90-94).
    private static readonly double[,] Payout =
    {
        { 1.2, 1.0, 0.66 },
        { 1.5, 0.95, 0.5 },
        { 2.0, 0.8, 0.0 },
    };

    private static readonly Color[] SliceColors =
    {
        new(0.30f, 0.78f, 0.42f),   // green
        new(0.55f, 0.55f, 0.60f),   // grey
        new(0.84f, 0.28f, 0.28f),   // red
    };

    private readonly Random _rng = new();
    private readonly int[][] _wheels = new int[SpinsPerGame][];

    private int _currency;
    private int _spin;              // 0..2
    private int _bet;
    private string _phase = "betting";
    private bool _wheelHidden;
    private double _rotation;       // degrees
    private int _resultSlice;
    private ulong _spinStartMs;
    private double _finalPerf;

    private Label _infoLabel = null!;
    private Label _essenceLabel = null!;
    private Label _spinLabel = null!;
    private Label _payoutLabel = null!;
    private Control _wheel = null!;
    private Label _hiddenMark = null!;
    private Label _hintLabel = null!;
    private VBoxContainer _betBox = null!;
    private Label _betLabel = null!;
    private HSlider _slider = null!;
    private VBoxContainer _readyBox = null!;
    private Label _wagerLabel = null!;
    private VBoxContainer _resultBox = null!;
    private Label _resultLabel = null!;
    private Button _advanceButton = null!;
    private VBoxContainer _doneBox = null!;
    private Label _doneEssence = null!;
    private Label _doneGift = null!;
    private Label _donePower = null!;

    protected override void BuildUi(VBoxContainer host)
    {
        var title = new Label { Text = "SPIRIT WHEEL" };
        title.AddThemeFontSizeOverride("font_size", 26);
        host.AddChild(title);

        _infoLabel = new Label { Modulate = new Color(1, 1, 1, 0.75f) };
        _infoLabel.AddThemeFontSizeOverride("font_size", 14);
        host.AddChild(_infoLabel);

        var row = new HBoxContainer();
        row.AddThemeConstantOverride("separation", 40);
        host.AddChild(row);
        _essenceLabel = new Label();
        _essenceLabel.AddThemeFontSizeOverride("font_size", 18);
        row.AddChild(_essenceLabel);
        _spinLabel = new Label();
        _spinLabel.AddThemeFontSizeOverride("font_size", 18);
        row.AddChild(_spinLabel);

        _payoutLabel = new Label();
        _payoutLabel.AddThemeFontSizeOverride("font_size", 15);
        host.AddChild(_payoutLabel);

        _wheel = new Control
        {
            CustomMinimumSize = new Vector2(280, 280),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
        };
        _wheel.Draw += DrawWheel;
        host.AddChild(_wheel);
        _hiddenMark = new Label { Text = "?" };
        _hiddenMark.AddThemeFontSizeOverride("font_size", 64);
        _hiddenMark.SetAnchorsPreset(Control.LayoutPreset.Center);
        _wheel.AddChild(_hiddenMark);

        _hintLabel = new Label
        {
            Text = "Place bet to reveal the wheel",
            Modulate = new Color(0.6f, 0.75f, 1f),
        };
        _hintLabel.AddThemeFontSizeOverride("font_size", 14);
        host.AddChild(_hintLabel);

        // betting phase -------------------------------------------------
        _betBox = new VBoxContainer();
        _betBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_betBox);
        _betLabel = new Label();
        _betLabel.AddThemeFontSizeOverride("font_size", 16);
        _betBox.AddChild(_betLabel);
        _slider = new HSlider
        {
            MinValue = 0, MaxValue = 100, Step = 1,
            CustomMinimumSize = new Vector2(280, 0),
        };
        _slider.ValueChanged += _ => RefreshBetLabel();
        _betBox.AddChild(_slider);
        var quick = new HBoxContainer();
        quick.AddThemeConstantOverride("separation", 8);
        _betBox.AddChild(quick);
        foreach (var amount in new[] { 10, 25, 50, -1 })
        {
            var b = new Button { Text = amount < 0 ? "ALL" : $"${amount}" };
            var captured = amount;
            b.Pressed += () => QuickBet(captured);
            quick.AddChild(b);
        }
        var channel = new Button { Text = "CHANNEL SPIRITS" };
        channel.Pressed += PlaceBet;
        _betBox.AddChild(channel);

        // ready_to_spin phase -------------------------------------------
        _readyBox = new VBoxContainer();
        _readyBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_readyBox);
        _wagerLabel = new Label();
        _wagerLabel.AddThemeFontSizeOverride("font_size", 16);
        _readyBox.AddChild(_wagerLabel);
        var spinButton = new Button { Text = "SPIN THE WHEEL" };
        spinButton.Pressed += SpinWheel;
        _readyBox.AddChild(spinButton);

        // spin_result phase ---------------------------------------------
        _resultBox = new VBoxContainer();
        _resultBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_resultBox);
        _resultLabel = new Label();
        _resultLabel.AddThemeFontSizeOverride("font_size", 16);
        _resultBox.AddChild(_resultLabel);
        _advanceButton = new Button { Text = "CONTINUE" };
        _advanceButton.Pressed += AdvanceToNextSpin;
        _resultBox.AddChild(_advanceButton);

        // completed phase -----------------------------------------------
        _doneBox = new VBoxContainer();
        _doneBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_doneBox);
        var appeased = new Label { Text = "SPIRITS APPEASED" };
        appeased.AddThemeFontSizeOverride("font_size", 22);
        _doneBox.AddChild(appeased);
        _doneEssence = new Label();
        _doneBox.AddChild(_doneEssence);
        _doneGift = new Label();
        _doneBox.AddChild(_doneGift);
        _donePower = new Label();
        _doneBox.AddChild(_donePower);
        var collect = new Button { Text = "Click anywhere to continue" };
        collect.Pressed += () => Finish(_finalPerf);
        _doneBox.AddChild(collect);
    }

    protected override void OnBegin()
    {
        _currency = StartingCurrency;
        _spin = 0;
        _bet = 0;
        _rotation = 0;
        BuildWheels();
        var maxBonus = 1.0 + DifficultyPoints * 0.025;   // display-only, Python parity
        _infoLabel.Text = $"enchanting · {DifficultyTier} ({DifficultyPoints:0.#} pts)"
                          + $" · max bonus x{maxBonus:0.00} · spins: {SpinsPerGame}";
        EnterBettingPhase(revealWheel: true);   // wheel visible from start on spin 1
    }

    /// <summary>Difficulty → base slice counts, then per-spin decay (both clamp layers).</summary>
    private void BuildWheels()
    {
        var t = Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);
        var baseGreen = Math.Clamp((int)Math.Round(12.0 + t * (6.0 - 12.0)), 4, 14);
        var baseRed = Math.Clamp((int)Math.Round(3.0 + t * (10.0 - 3.0)), 2, 12);
        var grey = Slices - baseGreen - baseRed;
        if (grey < 2)
        {
            var excess = 2 - grey;
            if (baseGreen >= baseRed) baseGreen -= excess;
            else baseRed -= excess;
        }

        for (var s = 0; s < SpinsPerGame; s++)
        {
            var g = Math.Max(3, baseGreen - s);
            var r = Math.Min(12, baseRed + s);
            if (g + r > 17) g = Math.Max(3, g - (g + r - 17));
            var wheel = new int[Slices];
            for (var i = 0; i < Slices; i++)
                wheel[i] = i < g ? 0 : i < g + r ? 2 : 1;
            for (var i = Slices - 1; i > 0; i--)   // shuffle (visual only — odds are counts)
            {
                var j = _rng.Next(i + 1);
                (wheel[i], wheel[j]) = (wheel[j], wheel[i]);
            }
            _wheels[s] = wheel;
        }
    }

    private void EnterBettingPhase(bool revealWheel)
    {
        if (_currency < 1) { Complete(); return; }   // soft-lock guard (deviation)
        _phase = "betting";
        _bet = 0;
        _wheelHidden = !revealWheel;
        var defaultBet = Math.Min(10, _currency);
        _slider.SetValueNoSignal(defaultBet * 100.0 / _currency);
        UpdatePhaseUi();
    }

    private int CurrentSliderBet()
        => Math.Clamp((int)(_slider.Value / 100.0 * _currency), 1, Math.Max(1, _currency));

    private void QuickBet(int amount)
    {
        if (_phase != "betting" || _currency < 1) return;
        var bet = amount < 0 ? _currency : Math.Min(amount, _currency);
        _slider.SetValueNoSignal(bet * 100.0 / _currency);
        RefreshBetLabel();
    }

    private void PlaceBet()
    {
        if (_phase != "betting") return;
        var bet = CurrentSliderBet();
        if (bet < 1 || bet > _currency)
        {
            WarnLabel.Text = "invalid bet!";
            return;
        }
        _bet = bet;
        _wheelHidden = false;   // bet confirmed reveals the wheel
        _phase = "ready_to_spin";
        UpdatePhaseUi();
    }

    private void SpinWheel()
    {
        if (_phase != "ready_to_spin" || _bet <= 0) return;
        _resultSlice = _rng.Next(Slices);          // uniform; deceleration is presentation
        _spinStartMs = Time.GetTicksMsec();        // wall clock, Python time.time() parity
        _phase = "spinning";
        UpdatePhaseUi();
    }

    protected override void OnTick(double delta)
    {
        if (_phase == "spinning")
        {
            var p = Math.Clamp((Time.GetTicksMsec() - _spinStartMs) / SpinDurationMs, 0.0, 1.0);
            var eased = 1.0 - Math.Pow(1.0 - p, 3.0);   // ease-out cubic
            _rotation = eased * (5 * 360 + _resultSlice * 18 + 9);
            if (p >= 1.0) ResolveSpin();
        }
        _wheel.QueueRedraw();   // spin + hidden-orb pulse both animate
    }

    private void ResolveSpin()
    {
        var color = _wheels[_spin][_resultSlice];
        var mult = Payout[_spin, color];
        var winnings = (int)(_bet * mult);
        var profit = winnings - _bet;
        _currency = _currency - _bet + winnings;
        _bet = 0;
        _phase = "spin_result";
        var colorName = color switch { 0 => "GREEN", 1 => "GREY", _ => "RED" };
        _resultLabel.Text = $"Spirit landed on: {colorName}   ({profit:+0;-0;+0} Essence)";
        _advanceButton.Text = _spin >= SpinsPerGame - 1 ? "COMPLETE RITUAL" : "CONTINUE";
        UpdatePhaseUi();
    }

    private void AdvanceToNextSpin()
    {
        if (_phase != "spin_result") return;
        _spin++;
        _rotation = 0;
        if (_spin >= SpinsPerGame) Complete();
        else EnterBettingPhase(revealWheel: false);   // spins 2-3 hide until bet
    }

    private void Complete()
    {
        _phase = "completed";
        var diff = _currency - StartingCurrency;
        var efficacyPct = Math.Clamp(diff / 100.0 * 50.0, -50.0, 50.0);
        var perf = Math.Clamp(_currency / 200.0, 0.0, 1.0);
        perf = Math.Min(1.0, perf + 0.10);   // first-try bonus fires every run (quirk)
        _finalPerf = perf;
        _doneEssence.Text = $"Final Essence: {_currency}";
        _doneGift.Text = $"Spirit Gift: {diff:+0;-0;+0}";
        _donePower.Text = $"Enchantment Power: {efficacyPct:+0.0;-0.0;+0.0}%";
        UpdatePhaseUi();
    }

    protected override void OnInput(InputEvent @event)
    {
        if (_phase == "completed"
            && @event is InputEventMouseButton { Pressed: true })
            Finish(_finalPerf);
    }

    private void UpdatePhaseUi()
    {
        _essenceLabel.Text = $"Essence: {_currency}";
        _spinLabel.Text = $"Spin {Math.Min(_spin + 1, SpinsPerGame)} / {SpinsPerGame}";
        var s = Math.Min(_spin, SpinsPerGame - 1);
        _payoutLabel.Text = $"GREEN x{Payout[s, 0]:0.##}   GREY x{Payout[s, 1]:0.##}"
                            + $"   RED x{Payout[s, 2]:0.##}";
        _betBox.Visible = _phase == "betting";
        _readyBox.Visible = _phase == "ready_to_spin";
        _resultBox.Visible = _phase == "spin_result";
        _doneBox.Visible = _phase == "completed";
        _hiddenMark.Visible = _wheelHidden;
        _hintLabel.Visible = _wheelHidden && _phase == "betting";
        _wagerLabel.Text = $"Essence Wagered: {_bet}";
        WarnLabel.Text = "";
        RefreshBetLabel();
        _wheel.QueueRedraw();
    }

    private void RefreshBetLabel()
    {
        if (_phase == "betting" && _currency >= 1)
            _betLabel.Text = $"Bet: {CurrentSliderBet()} Essence";
    }

    private void DrawWheel()
    {
        var c = _wheel.Size / 2f;
        var radius = Mathf.Min(c.X, c.Y) - 6f;
        if (_wheelHidden)
        {
            var pulse = 0.30f + 0.20f * Mathf.Sin(Time.GetTicksMsec() / 300f);
            _wheel.DrawCircle(c, radius * 0.55f, new Color(0.40f, 0.60f, 0.95f, pulse));
            return;
        }
        var slices = _wheels[Math.Min(_spin, SpinsPerGame - 1)];
        const int arcSteps = 4;
        for (var i = 0; i < Slices; i++)
        {
            // pointer sits at screen -90°; rotation R aligns slice center i*18+9 with it
            var a0 = Mathf.DegToRad(i * 18f - (float)_rotation - 90f);
            var a1 = Mathf.DegToRad((i + 1) * 18f - (float)_rotation - 90f);
            var pts = new Vector2[arcSteps + 2];
            pts[0] = c;
            for (var k = 0; k <= arcSteps; k++)
            {
                var a = a0 + (a1 - a0) * k / arcSteps;
                pts[k + 1] = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * radius;
            }
            _wheel.DrawPolygon(pts, new[] { SliceColors[slices[i]] });
        }
        _wheel.DrawArc(c, radius, 0, Mathf.Tau, 64, new Color(0.85f, 0.90f, 1f), 2f);
        var tip = new Vector2(c.X, c.Y - radius + 6f);
        _wheel.DrawPolygon(
            new[] { tip, tip + new Vector2(-9f, -16f), tip + new Vector2(9f, -16f) },
            new[] { Colors.White });
    }
}
