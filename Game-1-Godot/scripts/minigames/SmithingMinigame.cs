using Godot;

namespace Game1.Godot;

/// <summary>
/// Forge (smithing) — two-channel dexterity minigame. Channel 1: temperature
/// starts at 50 and decays every 100ms of wall clock; [Space] fans it up
/// toward a difficulty-narrowed ideal band centered on 70°. Channel 2: a
/// hammer indicator sweeps a 400px logical bar; STRIKE scores a binned 0-100
/// timing score × an exponential temperature multiplier (k=0.0433, floor 0.1).
/// Land the required strikes before the timer expires.
///
/// Performance = min(1, avgStrike × (1.2 if final temp in band) / 120) + 0.10
/// first-try bonus — which the Python original applies on EVERY run (attempt
/// is never incremented); quirk preserved. Timeout finishes at 0.
///
/// Python parity notes: the hammer sweep is px-per-frame at a fixed 60 FPS in
/// pygame, so here it is dt-scaled by ×60 to keep identical real-time speed;
/// the metadata splash freezes the countdown until dismissed (BEGIN FORGING).
/// </summary>
public partial class SmithingMinigame : MinigameOverlay
{
    private const double BarWidth = 400.0;              // smithing.py:124
    private const double BarCenter = 200.0;
    private const double BinWidth = BarCenter / 9.0;    // ≈22.22px timing bins
    private const double TempK = 0.0433;                // ln2/16 — 0.5 at 4° off
    private const double DecayIntervalMs = 100.0;       // wall-clock decay tick
    private const double SimFps = 60.0;                 // pygame fixed framerate

    // play state ----------------------------------------------------------
    private readonly List<int> _scores = new();
    private double _temperature;
    private double _hammerPos;
    private int _hammerDir = 1;
    private int _hits;
    private double _timeLeft;
    private ulong _lastDecayMs;
    private bool _playing;

    // difficulty-interpolated params (SMITHING_PARAMS, points 1..80) -------
    private double _timeLimit;
    private double _idealMin, _idealMax;
    private double _decayRate;                          // per 100ms tick
    private double _fanIncrement;
    private double _hammerSpeed;                        // logical px per frame
    private int _requiredHits;

    private Label _infoLabel = null!;
    private Label _timerLabel = null!;
    private Label _tempLabel = null!;
    private Label _strikeLabel = null!;
    private Label _scoresLabel = null!;
    private Control _forge = null!;
    private ProgressBar _strikeBar = null!;
    private Button _strikeButton = null!;
    private VBoxContainer _readyBox = null!;
    private Label _readyLabel = null!;

    protected override void BuildUi(VBoxContainer host)
    {
        var title = new Label { Text = "FORGE" };
        title.AddThemeFontSizeOverride("font_size", 26);
        host.AddChild(title);

        _infoLabel = new Label { Modulate = new Color(1, 1, 1, 0.75f) };
        _infoLabel.AddThemeFontSizeOverride("font_size", 14);
        host.AddChild(_infoLabel);

        var row = new HBoxContainer();
        row.AddThemeConstantOverride("separation", 40);
        host.AddChild(row);
        _timerLabel = new Label();
        _timerLabel.AddThemeFontSizeOverride("font_size", 18);
        row.AddChild(_timerLabel);
        _tempLabel = new Label();
        _tempLabel.AddThemeFontSizeOverride("font_size", 18);
        row.AddChild(_tempLabel);
        _strikeLabel = new Label();
        _strikeLabel.AddThemeFontSizeOverride("font_size", 18);
        row.AddChild(_strikeLabel);

        _forge = new Control
        {
            CustomMinimumSize = new Vector2(520, 220),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
        };
        _forge.Draw += DrawForge;
        host.AddChild(_forge);

        _strikeBar = new ProgressBar
        {
            MinValue = 0, MaxValue = 1, ShowPercentage = false,
            CustomMinimumSize = new Vector2(400, 12),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
        };
        host.AddChild(_strikeBar);

        _scoresLabel = new Label { Text = "" };
        _scoresLabel.AddThemeFontSizeOverride("font_size", 15);
        host.AddChild(_scoresLabel);

        var hint = new Label
        {
            Text = "[Space] fan the bellows · STRIKE when the hammer crosses the gold line",
            Modulate = new Color(0.6f, 0.75f, 1f),
        };
        hint.AddThemeFontSizeOverride("font_size", 13);
        host.AddChild(hint);

        _strikeButton = new Button
        {
            Text = "STRIKE",
            FocusMode = Control.FocusModeEnum.None,   // Space must stay on the bellows
        };
        _strikeButton.Pressed += Strike;
        host.AddChild(_strikeButton);

        // metadata splash — countdown frozen until dismissed (Python parity)
        _readyBox = new VBoxContainer();
        _readyBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_readyBox);
        _readyLabel = new Label();
        _readyLabel.AddThemeFontSizeOverride("font_size", 15);
        _readyBox.AddChild(_readyLabel);
        var begin = new Button
        { Text = "BEGIN FORGING", FocusMode = Control.FocusModeEnum.None };
        begin.Pressed += StartForging;
        _readyBox.AddChild(begin);
    }

    protected override void OnBegin()
    {
        // SMITHING_PARAMS easy→hard interpolation (difficulty_calculator.py:66-97)
        _timeLimit = Interp(60.0, 25.0);
        _decayRate = Interp(0.3, 0.6);
        _fanIncrement = Interp(4.0, 1.5);
        _hammerSpeed = Interp(3.0, 14.0);
        _requiredHits = (int)Math.Round(Interp(3.0, 12.0));
        var band = Interp(25.0, 3.0);   // centered at 70, clamped (dc.py:309-318)
        _idealMin = Math.Clamp(70.0 - band / 2.0, 55.0, 75.0);
        _idealMax = Math.Clamp(70.0 + band / 2.0, _idealMin + 3.0, 85.0);

        _temperature = 50.0;
        _hammerPos = 0;
        _hammerDir = 1;
        _hits = 0;
        _scores.Clear();
        _timeLeft = _timeLimit;
        _playing = false;

        _infoLabel.Text = $"smithing · {DifficultyTier} ({DifficultyPoints:0.#} pts)";
        _readyLabel.Text = $"Time limit: {_timeLimit:0}s   Required strikes: {_requiredHits}\n"
                           + $"Ideal temperature: {_idealMin:0}-{_idealMax:0}°";
        _readyBox.Visible = true;
        _strikeButton.Disabled = true;
        RefreshHud();
        _forge.QueueRedraw();
    }

    private void StartForging()
    {
        if (_playing) return;
        _readyBox.Visible = false;
        _strikeButton.Disabled = false;
        _lastDecayMs = Time.GetTicksMsec();
        _playing = true;
        RefreshHud();
    }

    protected override void OnTick(double delta)
    {
        if (!_playing) return;

        // temperature decays on a wall-clock 100ms tick (smithing.py:210-219)
        var now = Time.GetTicksMsec();
        while (now - _lastDecayMs >= (ulong)DecayIntervalMs)
        {
            _temperature = Math.Max(0.0, _temperature - _decayRate);
            _lastDecayMs += (ulong)DecayIntervalMs;
        }

        // hammer sweep: Python is px/frame @60 FPS; dt-scaled here for parity
        if (_hits < _requiredHits)
        {
            _hammerPos += _hammerDir * _hammerSpeed * SimFps * delta;
            if (_hammerPos <= 0) { _hammerPos = 0; _hammerDir = 1; }
            else if (_hammerPos >= BarWidth) { _hammerPos = BarWidth; _hammerDir = -1; }
        }

        _timeLeft -= delta;
        if (_timeLeft <= 0)
        {
            _timeLeft = 0;
            EndGame(completed: false);
            return;
        }
        RefreshHud();
        _forge.QueueRedraw();
    }

    protected override void OnInput(InputEvent @event)
    {
        if (@event is InputEventKey
            { Pressed: true, Echo: false, PhysicalKeycode: Key.Space })
        {
            if (_playing)   // fan: temp = min(100, temp + increment)
                _temperature = Math.Min(100.0, _temperature + _fanIncrement);
            GetViewport().SetInputAsHandled();
        }
    }

    /// <summary>Any STRIKE consumes a hit — a 0-score spam click still counts.</summary>
    private void Strike()
    {
        if (!_playing || _hits >= _requiredHits) return;
        var timing = TimingScore(Math.Abs(_hammerPos - BarCenter));
        var final = (int)Math.Round(timing * TempMultiplier());
        _scores.Add(final);
        _hits++;
        if (_hits >= _requiredHits) EndGame(completed: true);
        else RefreshHud();
    }

    private static int TimingScore(double d)
    {
        if (d <= 0.3 * BinWidth) return 100;
        if (d <= 1.0 * BinWidth) return 90;
        if (d <= 2.0 * BinWidth) return 80;
        if (d <= 3.0 * BinWidth) return 70;
        if (d <= 4.0 * BinWidth) return 60;
        if (d <= 6.0 * BinWidth) return 50;
        if (d <= 9.0 * BinWidth) return 30;
        return 0;
    }

    private double TempMultiplier()
    {
        if (_temperature >= _idealMin && _temperature <= _idealMax) return 1.0;
        var dev = _temperature < _idealMin
            ? _idealMin - _temperature
            : _temperature - _idealMax;
        return Math.Clamp(Math.Exp(-TempK * dev * dev), 0.1, 1.0);
    }

    private void EndGame(bool completed)
    {
        _playing = false;
        if (!completed)
        {
            Finish(0.0);   // timeout — caller handles the material burn
            return;
        }
        // per-strike scores already carry the temp multiplier; the ×1.2 here is
        // a SECOND, end-moment temperature reward (smithing.py:409; rc.py:196)
        var avg = _scores.Count > 0 ? _scores.Average() : 0.0;
        var inBand = _temperature >= _idealMin && _temperature <= _idealMax;
        var perf = Math.Min(1.0, avg * (inBand ? 1.2 : 1.0) / 120.0);
        perf = Math.Min(1.0, perf + 0.10);   // first-try bonus fires every run (quirk)
        Finish(perf);
    }

    private double Interp(double easy, double hard)
    {
        var t = Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);
        return easy + (hard - easy) * t;
    }

    private void RefreshHud()
    {
        _timerLabel.Text = $"Time: {_timeLeft:0.0}s";
        _timerLabel.Modulate = _timeLeft <= 10
            ? new Color(1f, 0.25f, 0.25f,
                        0.6f + 0.4f * Mathf.Sin(Time.GetTicksMsec() / 120f))
            : _timeLeft <= 20 ? new Color(1f, 0.9f, 0.3f) : Colors.White;
        _tempLabel.Text = $"Temp: {_temperature:0}°";
        _strikeLabel.Text = $"Strikes: {_hits}/{_requiredHits}";
        _strikeBar.MaxValue = Math.Max(1, _requiredHits);
        _strikeBar.Value = _hits;
        if (_scores.Count == 0)
        {
            _scoresLabel.Text = "scores: —";
            _scoresLabel.Modulate = new Color(1, 1, 1, 0.6f);
        }
        else
        {
            var recent = _scores.Skip(Math.Max(0, _scores.Count - 6));
            _scoresLabel.Text = "scores: " + string.Join("  ", recent);
            _scoresLabel.Modulate = _scores[^1] >= 100
                ? new Color(1f, 0.85f, 0.2f)      // gold on a perfect strike
                : new Color(1, 1, 1, 0.85f);
        }
    }

    private void DrawForge()
    {
        // furnace gauge (vertical, 0-100°) -------------------------------
        const float gx = 20f, gy = 10f, gw = 40f, gh = 200f;
        _forge.DrawRect(new Rect2(gx, gy, gw, gh), new Color(0.12f, 0.12f, 0.15f));
        var bandTop = gy + gh - (float)(_idealMax / 100.0) * gh;
        var bandH = (float)((_idealMax - _idealMin) / 100.0) * gh;
        _forge.DrawRect(new Rect2(gx, bandTop, gw, bandH),
                        new Color(0.3f, 0.8f, 0.4f, 0.35f));
        var fillH = (float)(_temperature / 100.0) * gh;
        _forge.DrawRect(new Rect2(gx, gy + gh - fillH, gw, fillH), FlameColor());
        _forge.DrawRect(new Rect2(gx, gy, gw, gh),
                        new Color(0.7f, 0.7f, 0.8f), false, 2f);

        // hammer bar over the anvil --------------------------------------
        const float bx = 100f, by = 95f, bh = 34f;
        _forge.DrawRect(new Rect2(bx, by + bh, (float)BarWidth, 24f),
                        new Color(0.22f, 0.22f, 0.26f));   // anvil block
        _forge.DrawRect(new Rect2(bx, by, (float)BarWidth, bh),
                        new Color(0.20f, 0.16f, 0.13f));
        var cx = bx + (float)BarCenter;
        foreach (var (mult, alpha) in new[] { (2f, 0.25f), (1f, 0.5f), (0.3f, 0.9f) })
        {
            var off = (float)BinWidth * mult;   // real scoring bins, not vestigial widths
            var guide = new Color(1f, 0.85f, 0.2f, alpha);
            _forge.DrawLine(new Vector2(cx - off, by), new Vector2(cx - off, by + bh), guide, 1f);
            _forge.DrawLine(new Vector2(cx + off, by), new Vector2(cx + off, by + bh), guide, 1f);
        }
        _forge.DrawLine(new Vector2(cx, by - 6f), new Vector2(cx, by + bh + 6f),
                        new Color(1f, 0.85f, 0.2f), 2f);
        var ix = bx + (float)Math.Clamp(_hammerPos, 0.0, BarWidth);
        _forge.DrawRect(new Rect2(ix - 2f, by - 4f, 4f, bh + 8f), Colors.White);
    }

    private Color FlameColor()
    {
        var t = (float)(_temperature / 100.0);
        return t < 0.4f
            ? new Color(0.25f, 0.35f, 0.9f).Lerp(new Color(0.95f, 0.55f, 0.15f), t / 0.4f)
            : new Color(0.95f, 0.55f, 0.15f).Lerp(new Color(1f, 0.15f, 0.1f), (t - 0.4f) / 0.6f);
    }
}
