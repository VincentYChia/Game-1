using Godot;

namespace Game1.Godot;

/// <summary>
/// Refining — lockpicking-style tumbler alignment (refining.py). N cylinders
/// spin; press [Space] when the rotating pick is inside the green arc at the
/// top (target angle 0°). A hit freezes that cylinder and advances to the
/// next; align them all before the timer runs out with limited misses.
/// Difficulty points interpolate cylinder count (3-12), timing window
/// (0.05-0.01s), rotation speed (1.0-4.0 rev/s), time limit (45-15s) and
/// allowed misses (2-0). Acceptance = frozen base window × 0.625 while the
/// DRAWN arc uses per-cylinder effective speed (multi-speed cylinders show
/// different arc widths — Python divergence preserved). Performance =
/// aligned / total (1.0 on success, partial credit on failure).
/// </summary>
public partial class RefiningMinigame : MinigameOverlay
{
    // 0.5 half-width × 1.25 sync grace (refining.py:259-260)
    private const double AcceptanceGrace = 0.625;
    private const double FeedbackSecs = 0.3;

    private sealed class Cylinder
    {
        public double Angle;            // degrees, 0 = top
        public double Speed;            // rev/s (effective, incl. multi-speed)
        public int Direction;           // ±1
        public bool Aligned;
        public bool HasAttempt;
        public double LastAttemptAngle; // red miss mark
    }

    private readonly Random _rng = new();
    private readonly List<Cylinder> _cyls = new();

    // interpolated difficulty params (difficulty_calculator.py REFINING_PARAMS)
    private int _timeLimit;
    private int _cylinderCount;
    private double _timingWindow;
    private double _rotationSpeed;
    private int _allowedFailures;
    private bool _multiSpeed;
    private double _baseWindowDegrees;  // frozen at begin, never recomputed

    private int _current;
    private int _failed;
    private double _timeLeft;
    private double _feedbackTimer;
    private bool _feedbackGood;
    private string _phase = "intro";    // intro | playing | done
    private double _finalPerf;

    private Label _infoLabel = null!;
    private Label _timerLabel = null!;
    private Label _attemptsLabel = null!;
    private Label _feedbackLabel = null!;
    private Label _resultLabel = null!;
    private Label _hintLabel = null!;
    private Control _lockFace = null!;

    protected override void BuildUi(VBoxContainer host)
    {
        var title = new Label { Text = "REFINERY — TUMBLER ALIGNMENT" };
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
        _attemptsLabel = new Label();
        _attemptsLabel.AddThemeFontSizeOverride("font_size", 18);
        row.AddChild(_attemptsLabel);

        _lockFace = new Control
        {
            CustomMinimumSize = new Vector2(320, 340),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
        };
        _lockFace.Draw += DrawLockFace;
        host.AddChild(_lockFace);

        _feedbackLabel = new Label
        { HorizontalAlignment = HorizontalAlignment.Center };
        _feedbackLabel.AddThemeFontSizeOverride("font_size", 20);
        host.AddChild(_feedbackLabel);

        _resultLabel = new Label
        { HorizontalAlignment = HorizontalAlignment.Center };
        _resultLabel.AddThemeFontSizeOverride("font_size", 18);
        host.AddChild(_resultLabel);

        _hintLabel = new Label { Modulate = new Color(0.6f, 0.75f, 1f) };
        _hintLabel.AddThemeFontSizeOverride("font_size", 14);
        host.AddChild(_hintLabel);
    }

    protected override void OnBegin()
    {
        // normalized = clamp01((points - 1) / (80 - 1)); param = easy + span×t
        var t = Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);
        _timeLimit = (int)Math.Round(45.0 + t * (15.0 - 45.0));
        _cylinderCount = Math.Max(2, (int)Math.Round(3.0 + t * (12.0 - 3.0)));
        _timingWindow = 0.05 + t * (0.01 - 0.05);
        _rotationSpeed = 1.0 + t * (4.0 - 1.0);
        _allowedFailures = Math.Max(0, (int)Math.Round(2.0 - t * 2.0));
        _multiSpeed = DifficultyPoints >= 11;   // rare threshold

        // Frozen BEFORE any per-cylinder speed variation (refining.py:114)
        _baseWindowDegrees = _timingWindow * _rotationSpeed * 360.0;

        _cyls.Clear();
        for (var i = 0; i < _cylinderCount; i++)
        {
            var speed = _rotationSpeed;
            if (_multiSpeed)
            {
                // i%2 tested first, so only odd multiples of 3 get 1.3x
                if (i % 2 == 0) speed *= 0.7;
                else if (i % 3 == 0) speed *= 1.3;
            }
            _cyls.Add(new Cylinder
            {
                Angle = _rng.NextDouble() * 360.0,
                Speed = speed,
                Direction = _rng.Next(2) == 0 ? 1 : -1,
            });
        }

        _current = 0;
        _failed = 0;
        _timeLeft = _timeLimit;
        _feedbackTimer = 0;
        _phase = "intro";
        var maxBonus = 1.0 + DifficultyPoints * 0.012;   // display-only parity
        _infoLabel.Text =
            $"refining · {DifficultyTier} ({DifficultyPoints:0.#} pts)"
            + $" · {_timeLimit}s · max bonus x{maxBonus:0.00}"
            + $" · tumblers: {_cylinderCount}";
        _resultLabel.Text = "";
        _feedbackLabel.Text = "";
        _hintLabel.Text = "[Space] to begin";
        RefreshHud();
    }

    protected override void OnTick(double delta)
    {
        if (_phase == "playing")
        {
            _timeLeft -= delta;
            if (_timeLeft <= 0)
            {
                _timeLeft = 0;
                EndGame(false, "Time's up!");
            }
            foreach (var cyl in _cyls)
            {
                if (cyl.Aligned) continue;
                cyl.Angle += cyl.Direction * cyl.Speed * 360.0 * delta;
                cyl.Angle = ((cyl.Angle % 360.0) + 360.0) % 360.0;
            }
        }
        if (_feedbackTimer > 0)
        {
            _feedbackTimer -= delta;
            if (_feedbackTimer <= 0) _feedbackLabel.Text = "";
        }
        RefreshHud();
        _lockFace.QueueRedraw();   // pulse + rotation animate every frame
    }

    protected override void OnInput(InputEvent @event)
    {
        if (@event is not InputEventKey
            { Pressed: true, Echo: false, PhysicalKeycode: Key.Space })
            return;
        switch (_phase)
        {
            case "intro":       // metadata overlay pauses the countdown
                _phase = "playing";
                _hintLabel.Text = "[Space] Align when pick reaches green zone";
                break;
            case "playing":
                Attempt();
                break;
            case "done":
                Finish(_finalPerf);
                break;
        }
        GetViewport().SetInputAsHandled();
    }

    private void Attempt()
    {
        var cyl = _cyls[_current];
        var dist = Math.Abs(cyl.Angle);              // target angle is 0 (top)
        dist = Math.Min(dist, 360.0 - dist);
        if (dist <= _baseWindowDegrees * AcceptanceGrace)
        {
            cyl.Aligned = true;
            _feedbackGood = true;
            _feedbackTimer = FeedbackSecs;
            _feedbackLabel.Text = "ALIGNED!";
            _feedbackLabel.Modulate = new Color(0.4f, 1f, 0.5f);
            _current++;
            if (_current >= _cylinderCount)
                EndGame(true, "All tumblers aligned!");
        }
        else
        {
            cyl.HasAttempt = true;
            cyl.LastAttemptAngle = cyl.Angle;
            _failed++;
            _feedbackGood = false;
            _feedbackTimer = FeedbackSecs;
            _feedbackLabel.Text = "MISSED!";
            _feedbackLabel.Modulate = new Color(1f, 0.4f, 0.4f);
            // strictly-greater tolerance: N allowed → N misses survive
            if (_failed > _allowedFailures)
                EndGame(false, "Too many failed attempts!");
        }
    }

    private void EndGame(bool success, string message)
    {
        if (_phase == "done") return;
        _phase = "done";
        var aligned = _cyls.Count(c => c.Aligned);
        _finalPerf = _cylinderCount > 0 ? (double)aligned / _cylinderCount : 0;
        _resultLabel.Text = $"{message}   ({aligned}/{_cylinderCount} aligned)";
        _resultLabel.Modulate = success
            ? new Color(0.4f, 1f, 0.5f)
            : new Color(1f, 0.4f, 0.4f);
        _hintLabel.Text = "[Space] to continue";
    }

    private void RefreshHud()
    {
        _timerLabel.Text = $"Time: {_timeLeft:0.0}s";
        _attemptsLabel.Text = $"Misses: {_failed} / {_allowedFailures} allowed";
    }

    private void DrawLockFace()
    {
        var size = _lockFace.Size;
        var c = new Vector2(size.X / 2f, (size.Y - 40f) / 2f);
        var radius = Mathf.Min(c.X, (size.Y - 40f) / 2f) - 8f;
        var inner = radius - 40f;

        // brass lock body + inner ring
        _lockFace.DrawCircle(c, radius, new Color(0.45f, 0.36f, 0.20f));
        _lockFace.DrawArc(c, radius, 0, Mathf.Tau, 64,
            new Color(0.78f, 0.65f, 0.34f), 3f);
        _lockFace.DrawCircle(c, inner, new Color(0.16f, 0.13f, 0.09f));

        var cyl = _cyls.Count > 0
            ? _cyls[Math.Min(_current, _cyls.Count - 1)]
            : null;
        if (cyl is not null)
        {
            // DRAWN arc uses per-cylinder EFFECTIVE speed (visual/logic
            // divergence preserved); acceptance uses frozen base window.
            var halfW = (float)(_timingWindow * cyl.Speed * 360.0 * 0.5);
            _lockFace.DrawArc(c, radius - 10f,
                Mathf.DegToRad(-90f - halfW), Mathf.DegToRad(-90f + halfW),
                24, new Color(0.30f, 0.85f, 0.40f), 9f);

            // red miss mark at the exact angle pressed
            if (cyl.HasAttempt && !cyl.Aligned)
            {
                var ma = Mathf.DegToRad((float)cyl.LastAttemptAngle - 90f);
                var md = new Vector2(Mathf.Cos(ma), Mathf.Sin(ma));
                _lockFace.DrawLine(c + md * (radius - 18f), c + md * radius,
                    new Color(0.9f, 0.2f, 0.2f), 4f);
            }

            // rotating pick line + triangular tip (0° = top, -90° offset)
            var a = Mathf.DegToRad((float)cyl.Angle - 90f);
            var dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
            var tip = c + dir * (radius - 14f);
            var pickColor = cyl.Aligned
                ? new Color(0.4f, 1f, 0.5f)
                : new Color(0.92f, 0.90f, 0.80f);
            _lockFace.DrawLine(c, tip, pickColor, 3f);
            var side = new Vector2(-dir.Y, dir.X) * 7f;
            _lockFace.DrawPolygon(
                new[] { c + dir * radius, tip + side, tip - side },
                new[] { pickColor });
        }

        // tumbler progress dots: green done / pulsing current / dim pending
        var dotY = size.Y - 16f;
        var spacing = Mathf.Min(30f, size.X / Math.Max(1, _cylinderCount + 1));
        var x0 = size.X / 2f - spacing * (_cylinderCount - 1) / 2f;
        for (var i = 0; i < _cylinderCount; i++)
        {
            Color dot;
            if (_cyls[i].Aligned)
                dot = new Color(0.30f, 0.85f, 0.40f);
            else if (i == _current && _phase != "done")
            {
                var pulse = 0.6f + 0.4f * Mathf.Sin(Time.GetTicksMsec() / 150f);
                dot = new Color(0.95f, 0.85f, 0.30f, pulse);
            }
            else
                dot = new Color(1, 1, 1, 0.25f);
            _lockFace.DrawCircle(new Vector2(x0 + i * spacing, dotY), 7f, dot);
        }

        // brief feedback ring flash around the lock (0.3s, both outcomes)
        if (_feedbackTimer > 0)
        {
            var flash = _feedbackGood
                ? new Color(0.3f, 1f, 0.4f, (float)(_feedbackTimer / FeedbackSecs))
                : new Color(1f, 0.3f, 0.3f, (float)(_feedbackTimer / FeedbackSecs));
            _lockFace.DrawArc(c, radius + 5f, 0, Mathf.Tau, 64, flash, 4f);
        }
    }
}
