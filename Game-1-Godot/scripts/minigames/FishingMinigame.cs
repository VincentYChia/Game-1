using Godot;

namespace Game1.Godot;

/// <summary>
/// Fishing — OSU-style ripple timing (Crafting-subdisciplines/fishing.py).
/// Ripples spawn at random pond positions (max 2 concurrent); each has a
/// fixed cyan target ring (r=40) and an expanding ring (80 px/s base).
/// Simplification: each ripple is bound to a key ([F]/[J], shown at its
/// center) instead of mouse position — press it while the expanding ring
/// overlaps the target. Score bands by |ring − target|: ≤5 → 100 (perfect),
/// ≤10 → 75, ≤15 → 50, else partial max(25, 50·(1−d/tol)); a wrong-time
/// press consumes the ripple as a 0, and a ring past 2.5× target auto-misses.
/// Performance = (avgScore/100) · hitRate (misses count as 0s in BOTH terms —
/// double punishment preserved). Difficulty points stand in for spot tier:
/// +25% ripples / +20% ring speed per pseudo-tier (clamped 4..15 ripples).
/// Python parity: the result overlay requires a click/key to finalize.
/// </summary>
public partial class FishingMinigame : MinigameOverlay
{
    private const float PondW = 500f;
    private const float PondH = 400f;
    private const float SpawnMargin = 50f;
    private const double TargetRadius = 40.0;    // fixed (fishing.py:375)
    private const double MaxRadiusMult = 2.5;    // auto-miss at 100px
    private const double BaseExpandSpeed = 80.0; // px/s
    private const double HitTolerance = 15.0;    // no STR in overlay context
    private const double SpawnDelay = 1.5;       // s (no rod mult → clamp is a no-op)
    private const int MaxActiveRipples = 2;
    private const int BaseRipples = 8;
    private const double FeedbackFade = 1.0;     // s (game_engine.py:11785)

    private static readonly Key[] SlotKeys = { Key.F, Key.J };
    private static readonly string[] SlotNames = { "F", "J" };

    private sealed class Ripple
    {
        public Vector2 Pos;
        public double Radius;
        public bool Active = true;
        public bool Hit;
        public int Slot;
        public double ResolvedAge;
    }

    private sealed class Feedback
    {
        public Vector2 Pos;
        public string Text = "";
        public Color Color;
        public double Age;
    }

    private readonly Random _rng = new();
    private readonly List<Ripple> _ripples = new();
    private readonly List<Feedback> _feedback = new();
    private readonly List<int> _scores = new();

    private int _required;
    private double _expandSpeed;
    private int _spawned;
    private double _sinceSpawn;
    private int _hits;
    private int _misses;
    private int _perfectHits;
    private int _totalScore;
    private bool _resultShown;
    private double _finalPerf;

    private Label _infoLabel = null!;
    private Label _scoreLabel = null!;
    private ProgressBar _progress = null!;
    private Control _pond = null!;
    private VBoxContainer _resultBox = null!;
    private Label _resultTitle = null!;
    private Label _resultStats = null!;

    protected override void BuildUi(VBoxContainer host)
    {
        var title = new Label { Text = "FISHING" };
        title.AddThemeFontSizeOverride("font_size", 26);
        host.AddChild(title);

        _infoLabel = new Label { Modulate = new Color(1, 1, 1, 0.75f) };
        _infoLabel.AddThemeFontSizeOverride("font_size", 14);
        host.AddChild(_infoLabel);

        var row = new HBoxContainer();
        row.AddThemeConstantOverride("separation", 20);
        host.AddChild(row);
        _scoreLabel = new Label();
        _scoreLabel.AddThemeFontSizeOverride("font_size", 18);
        row.AddChild(_scoreLabel);
        _progress = new ProgressBar
        {
            ShowPercentage = false,
            CustomMinimumSize = new Vector2(220, 18),
            SizeFlagsVertical = Control.SizeFlags.ShrinkCenter,
        };
        row.AddChild(_progress);

        _pond = new Control
        {
            CustomMinimumSize = new Vector2(PondW, PondH),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
        };
        _pond.Draw += DrawPond;
        host.AddChild(_pond);

        var hint = new Label
        {
            Text = "press a ripple's key ([F] / [J]) when its expanding ring"
                   + " overlaps the cyan target ring!",
            Modulate = new Color(0.6f, 0.85f, 1f),
        };
        hint.AddThemeFontSizeOverride("font_size", 14);
        host.AddChild(hint);

        _resultBox = new VBoxContainer { Visible = false };
        _resultBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_resultBox);
        _resultTitle = new Label();
        _resultTitle.AddThemeFontSizeOverride("font_size", 22);
        _resultBox.AddChild(_resultTitle);
        _resultStats = new Label();
        _resultStats.AddThemeFontSizeOverride("font_size", 15);
        _resultBox.AddChild(_resultStats);
        var cont = new Label
        {
            Text = "click or press [Space] to continue",
            Modulate = new Color(1, 1, 1, 0.6f),
        };
        cont.AddThemeFontSizeOverride("font_size", 13);
        _resultBox.AddChild(cont);
    }

    protected override void OnBegin()
    {
        _ripples.Clear();
        _feedback.Clear();
        _scores.Clear();
        _spawned = 0;
        _hits = _misses = _perfectHits = _totalScore = 0;
        _resultShown = false;
        _resultBox.Visible = false;

        // Difficulty points → pseudo spot tier 1..4 (contract: +25% ripples,
        // +20% expand speed per tier above 1; ripple clamp [4,15]).
        var t = Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);
        var tier = 1.0 + t * 3.0;
        _required = Math.Clamp(
            (int)(BaseRipples * (1.0 + (tier - 1.0) * 0.25)), 4, 15);
        _expandSpeed = BaseExpandSpeed * (1.0 + (tier - 1.0) * 0.2);
        _sinceSpawn = SpawnDelay;   // first ripple spawns on first tick

        _progress.MinValue = 0;
        _progress.MaxValue = _required;
        _infoLabel.Text = $"fishing · {DifficultyTier} ({DifficultyPoints:0.#} pts)"
                          + $" · ripples: {_required} · ring speed {_expandSpeed:0} px/s";
        RefreshHud();
    }

    protected override void OnTick(double delta)
    {
        foreach (var f in _feedback) f.Age += delta;
        _feedback.RemoveAll(f => f.Age >= FeedbackFade);

        if (!_resultShown)
        {
            _sinceSpawn += delta;
            var active = _ripples.Count(r => r.Active);
            if (active < MaxActiveRipples && _spawned < _required
                && _sinceSpawn >= SpawnDelay)
                SpawnRipple();

            foreach (var r in _ripples)
            {
                if (!r.Active) { r.ResolvedAge += delta; continue; }
                r.Radius += _expandSpeed * delta;
                if (r.Radius >= TargetRadius * MaxRadiusMult)
                    ResolveMiss(r, "MISS");
            }

            if (_ripples.Count(r => !r.Active) >= _required)
                ShowResult();
        }

        _pond.QueueRedraw();
    }

    protected override void OnInput(InputEvent @event)
    {
        if (_resultShown)
        {
            if (@event is InputEventMouseButton { Pressed: true }
                || @event is InputEventKey
                { Pressed: true, Echo: false, PhysicalKeycode: Key.Space or Key.Enter })
                Finish(_finalPerf);
            return;
        }

        if (@event is not InputEventKey { Pressed: true, Echo: false } key)
            return;
        var slot = Array.IndexOf(SlotKeys, key.PhysicalKeycode);
        if (slot < 0) return;
        // Press with no live ripple on that key is a free whiff (parity with
        // clicking open water — fishing.py:495-496).
        var ripple = _ripples.FirstOrDefault(r => r.Active && r.Slot == slot);
        if (ripple is not null) ScoreRipple(ripple);
    }

    private void SpawnRipple()
    {
        var occupied = _ripples.Where(r => r.Active).Select(r => r.Slot).ToHashSet();
        var slot = occupied.Contains(0) ? 1 : 0;
        _ripples.Add(new Ripple
        {
            Pos = new Vector2(
                (float)(SpawnMargin + _rng.NextDouble() * (PondW - 2 * SpawnMargin)),
                (float)(SpawnMargin + _rng.NextDouble() * (PondH - 2 * SpawnMargin))),
            Radius = 0,
            Slot = slot,
        });
        _spawned++;
        _sinceSpawn = 0;
    }

    /// <summary>Score bands by |ring − target| (fishing.py:498-534).</summary>
    private void ScoreRipple(Ripple r)
    {
        var d = Math.Abs(r.Radius - TargetRadius);
        var early = r.Radius < TargetRadius;
        if (d > HitTolerance)
        {
            ResolveMiss(r, early ? "EARLY" : "LATE");   // consumed, no retry
            return;
        }

        int score;
        string text;
        Color color;
        if (d <= 5) { score = 100; _perfectHits++; text = "PERFECT!"; color = new Color(1f, 0.85f, 0.2f); }
        else if (d <= 10) { score = 75; text = "GOOD!"; color = new Color(0.4f, 1f, 0.4f); }
        else if (d <= 15) { score = 50; text = "OK"; color = Colors.White; }
        else
        {
            score = Math.Max(25, (int)(50 * (1 - d / HitTolerance)));
            text = early ? "EARLY" : "LATE";
            color = new Color(1f, 0.6f, 0.2f);
        }

        r.Hit = true;
        r.Active = false;
        _hits++;
        _totalScore += score;
        _scores.Add(score);
        _feedback.Add(new Feedback { Pos = r.Pos, Text = $"{text} ({score})", Color = color });
        RefreshHud();
    }

    private void ResolveMiss(Ripple r, string text)
    {
        r.Active = false;
        _misses++;
        _scores.Add(0);
        _feedback.Add(new Feedback
        { Pos = r.Pos, Text = text, Color = new Color(1f, 0.35f, 0.35f) });
        RefreshHud();
    }

    /// <summary>hit_rate·avg both include miss zeros (fishing.py:552-576).</summary>
    private void ShowResult()
    {
        _resultShown = true;
        var hitRate = _hits > 0 ? _hits / (double)_required : 0.0;
        var avg = _scores.Count > 0 ? _scores.Average() : 0.0;
        _finalPerf = Math.Min(1.0, avg / 100.0 * hitRate);
        var success = hitRate >= 0.5 && avg >= 40.0;   // raw gate, no bonuses

        var quality = _finalPerf switch
        {
            >= 0.9 => "LEGENDARY",
            >= 0.75 => "MASTERWORK",
            >= 0.6 => "SUPERIOR",
            >= 0.4 => "FINE",
            _ => "NORMAL",
        };
        _resultTitle.Text = success ? $"{quality} CATCH!" : "FISH ESCAPED!";
        _resultTitle.Modulate = success
            ? new Color(0.4f, 1f, 0.4f)
            : new Color(1f, 0.35f, 0.35f);
        _resultStats.Text = $"Hits: {_hits}/{_required}   Perfect: {_perfectHits}"
                            + $"   Misses: {_misses}\nAvg Score: {avg:0.0}"
                            + $"   Performance: {_finalPerf:P0}";
        _resultBox.Visible = true;
    }

    private void RefreshHud()
    {
        _scoreLabel.Text = $"Score: {_totalScore}";
        _progress.Value = _hits + _misses;
    }

    private void DrawPond()
    {
        // Water gradient bands (deep → lighter blue), then border.
        const int bands = 8;
        for (var i = 0; i < bands; i++)
        {
            var f = i / (float)(bands - 1);
            var c = new Color(0.02f, 0.12f, 0.28f).Lerp(new Color(0.05f, 0.30f, 0.50f), f);
            _pond.DrawRect(new Rect2(0, PondH * i / bands, PondW, PondH / bands + 1), c);
        }
        _pond.DrawRect(new Rect2(0, 0, PondW, PondH),
            new Color(0f, 0.75f, 1f, 0.8f), filled: false, width: 2f);

        var font = _pond.GetThemeDefaultFont();
        foreach (var r in _ripples)
        {
            if (!r.Active && (!r.Hit || r.ResolvedAge >= FeedbackFade)) continue;
            if (r.Hit)
            {
                var a = r.Active ? 1f : 1f - (float)(r.ResolvedAge / FeedbackFade);
                _pond.DrawArc(r.Pos, (float)r.Radius, 0, Mathf.Tau, 48,
                    new Color(0.3f, 1f, 0.3f, a), 3f);
                continue;
            }
            // Static cyan target ring + 5px center dot.
            _pond.DrawArc(r.Pos, (float)TargetRadius, 0, Mathf.Tau, 48,
                new Color(0f, 0.85f, 1f), 2f);
            _pond.DrawCircle(r.Pos, 5f, new Color(0f, 0.85f, 1f));
            // Expanding ring: white/cyan, red past 1.5× target (about to miss).
            var ringColor = r.Radius > TargetRadius * 1.5
                ? new Color(1f, 0.3f, 0.3f)
                : new Color(0.85f, 0.97f, 1f);
            if (r.Radius > 1)
                _pond.DrawArc(r.Pos, (float)r.Radius, 0, Mathf.Tau, 48, ringColor, 3f);
            _pond.DrawString(font, r.Pos + new Vector2(-6f, -10f),
                SlotNames[r.Slot], HorizontalAlignment.Center, 12f, 18,
                new Color(1f, 1f, 0.5f));
        }

        foreach (var f in _feedback)
        {
            var a = 1f - (float)(f.Age / FeedbackFade);
            var pos = f.Pos + new Vector2(-40f, -(float)TargetRadius - 8f
                                                - 12f * (float)f.Age);
            _pond.DrawString(font, pos, f.Text, HorizontalAlignment.Center, 80f, 16,
                new Color(f.Color.R, f.Color.G, f.Color.B, a));
        }
    }
}
