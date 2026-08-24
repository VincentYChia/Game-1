using Godot;

namespace Game1.Godot;

/// <summary>
/// Engineering workbench — sequential cognitive puzzles. Faithful simplified
/// port of Crafting-subdisciplines/engineering.py: always exactly 2 puzzles
/// (max(2, interp(1,2)) quirk preserved), rotation-pipe gameplay — click a
/// cell to rotate its pipe 90° clockwise, connect IN (top row) to OUT (bottom
/// row); BFS accepts ANY connected route, distractor pieces included. The
/// difficulty points interpolate time limit 300→120s and grid 3→4 over the
/// certified 1..80-point domain; the wall clock keeps running while the
/// per-puzzle info overlay blocks (Python parity).
///
/// Performance = completion×0.5 + avgEfficiency×0.3 + timeRatio×0.2 + 0.05
/// first-try, with the Python bugs preserved: timeRatio is ALWAYS 0 (end()
/// deactivates before reading the clock) while an expired-but-complete run
/// gets a flat +0.1 — so timing out with both puzzles solved scores HIGHER
/// than a fast clean run; pipe efficiency is fixed at generation
/// (min(1, idealPath/actualPath) — player clicks are counted but unscored);
/// hints are dead (never incremented, penalty never fires); the first-try
/// bonus fires on every run (attempt is always 1).
///
/// Deviations: puzzle 1 is rotation-pipe too (Python uses a lights-out
/// LogicSwitchPuzzle for puzzles 1+); deprecated SlidingTile / placeholder
/// puzzles are not ported (per contract guidance); no INT / skill-buff
/// time-limit multipliers (no character stats reach the overlay).
/// </summary>
public partial class EngineeringMinigame : MinigameOverlay
{
    private const int PuzzleCount = 2;        // max(2, interp(1,2)) — always 2
    private const double NearestBias = 0.7;   // winding-walk bias toward output
    private const float CellPx = 82f;

    // sides: 0=top 1=right 2=bottom 3=left; types 0=empty 1=straight 2=L 3=T 4=cross
    private static readonly bool[][] BaseSides =
    {
        new[] { false, false, false, false },
        new[] { true, false, true, false },
        new[] { true, true, false, false },
        new[] { true, true, true, false },
        new[] { true, true, true, true },
    };
    private static readonly int[] DistractorTypes = { 1, 2, 2, 3 };
    private static readonly string[] StatNames =
    { "Durability", "Efficiency", "Accuracy", "Power" };

    private readonly Random _rng = new();
    private readonly List<double> _efficiencies = new();
    private readonly HashSet<(int, int)> _flow = new();

    private int _gridSize = 3;
    private double _timeLimit = 300;
    private ulong _startMs;
    private bool _expired;
    private int _puzzleIndex;
    private int _solvedCount;
    private int[,] _type = new int[3, 3];
    private int[,] _rot = new int[3, 3];
    private (int R, int C) _input, _output;
    private int _idealLen;
    private double _pipeEfficiency;
    private int _clicks;              // tracked but never scored (Python parity)
    private string _phase = "intro";  // intro | playing | solved | done
    private double _finalPerf;

    private Label _infoLabel = null!;
    private Label _puzzleLabel = null!;
    private Label _timerLabel = null!;
    private Control _grid = null!;
    private Label _legend = null!;
    private VBoxContainer _introBox = null!;
    private Label _introLabel = null!;
    private VBoxContainer _solvedBox = null!;
    private Label _solvedLabel = null!;
    private Button _nextButton = null!;
    private VBoxContainer _doneBox = null!;
    private Label _doneResult = null!;
    private Label _doneStats = null!;
    private Label _donePerf = null!;

    protected override void BuildUi(VBoxContainer host)
    {
        var title = new Label { Text = "ENGINEERING WORKBENCH" };
        title.AddThemeFontSizeOverride("font_size", 26);
        host.AddChild(title);

        _infoLabel = new Label { Modulate = new Color(1, 1, 1, 0.75f) };
        _infoLabel.AddThemeFontSizeOverride("font_size", 14);
        host.AddChild(_infoLabel);

        var row = new HBoxContainer();
        row.AddThemeConstantOverride("separation", 40);
        host.AddChild(row);
        _puzzleLabel = new Label();
        _puzzleLabel.AddThemeFontSizeOverride("font_size", 18);
        row.AddChild(_puzzleLabel);
        _timerLabel = new Label();
        _timerLabel.AddThemeFontSizeOverride("font_size", 18);
        row.AddChild(_timerLabel);

        // per-puzzle info overlay (blocking; the clock keeps running) --------
        _introBox = new VBoxContainer();
        _introBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_introBox);
        _introLabel = new Label();
        _introLabel.AddThemeFontSizeOverride("font_size", 15);
        _introBox.AddChild(_introLabel);
        var start = new Button { Text = "START PUZZLE" };
        start.Pressed += StartPuzzle;
        _introBox.AddChild(start);

        // play surface -------------------------------------------------------
        _grid = new Control
        {
            CustomMinimumSize = new Vector2(3 * CellPx, 3 * CellPx),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
        };
        _grid.Draw += DrawGrid;
        _grid.GuiInput += OnGridInput;
        host.AddChild(_grid);

        _legend = new Label
        {
            Text = "IN (green, top) -> OUT (orange, bottom) · click a cell to rotate 90° CW",
            Modulate = new Color(0.6f, 0.75f, 1f),
        };
        _legend.AddThemeFontSizeOverride("font_size", 13);
        host.AddChild(_legend);

        // solved interstitial --------------------------------------------------
        _solvedBox = new VBoxContainer();
        _solvedBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_solvedBox);
        _solvedLabel = new Label();
        _solvedLabel.AddThemeFontSizeOverride("font_size", 16);
        _solvedBox.AddChild(_solvedLabel);
        _nextButton = new Button { Text = "NEXT PUZZLE" };
        _nextButton.Pressed += AdvancePuzzle;
        _solvedBox.AddChild(_nextButton);

        // completion -----------------------------------------------------------
        _doneBox = new VBoxContainer();
        _doneBox.AddThemeConstantOverride("separation", 6);
        host.AddChild(_doneBox);
        _doneResult = new Label();
        _doneResult.AddThemeFontSizeOverride("font_size", 18);
        _doneBox.AddChild(_doneResult);
        _doneStats = new Label();
        _doneBox.AddChild(_doneStats);
        _donePerf = new Label();
        _doneBox.AddChild(_donePerf);
        var collect = new Button { Text = "COLLECT DEVICE" };
        collect.Pressed += () => Finish(_finalPerf);
        _doneBox.AddChild(collect);
    }

    protected override void OnBegin()
    {
        // certified interpolation: t = clamp01((points-1)/79)
        var t = Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);
        _timeLimit = Math.Round(300.0 + (120.0 - 300.0) * t);
        _gridSize = Math.Max(3, (int)Math.Round(3.0 + (4.0 - 3.0) * t));

        _startMs = Time.GetTicksMsec();   // wall clock, runs through overlays
        _expired = false;
        _puzzleIndex = 0;
        _solvedCount = 0;
        _efficiencies.Clear();
        _finalPerf = 0;

        var maxBonus = 1.0 + DifficultyPoints * 0.02;   // display only (Python parity)
        _infoLabel.Text = $"engineering · {DifficultyTier} ({DifficultyPoints:0.#} pts)"
                          + $" · max bonus x{maxBonus:0.00} · {PuzzleCount} puzzles"
                          + $" · {_timeLimit:0}s";
        GeneratePuzzle();
        _phase = "intro";
        UpdatePhaseUi();
    }

    /// <summary>Winding-path pipe grid (engineering.py:69-194, scramble incl.).</summary>
    private void GeneratePuzzle()
    {
        var n = _gridSize;
        _type = new int[n, n];
        _rot = new int[n, n];
        _input = (0, _rng.Next(n));
        _output = (n - 1, _rng.Next(n));
        _idealLen = (n - 1) + Math.Abs(_output.C - _input.C) + 1;   // Manhattan + 1

        // biased walk: nearest-to-output neighbor with p=0.7, else random
        // unvisited neighbor; backtrack on dead-end
        var path = new List<(int R, int C)> { _input };
        var visited = new HashSet<(int, int)> { _input };
        var guard = 0;
        while (path.Count > 0 && path[^1] != _output && guard++ < 4000)
        {
            var (r, c) = path[^1];
            var nbrs = new List<(int R, int C)>();
            for (var s = 0; s < 4; s++)
            {
                var (nr, nc) = Step(r, c, s);
                if (nr >= 0 && nr < n && nc >= 0 && nc < n
                    && !visited.Contains((nr, nc)))
                    nbrs.Add((nr, nc));
            }
            if (nbrs.Count == 0) { path.RemoveAt(path.Count - 1); continue; }
            nbrs.Sort((a, b) => Manhattan(a, _output).CompareTo(Manhattan(b, _output)));
            var next = _rng.NextDouble() < NearestBias
                ? nbrs[0] : nbrs[_rng.Next(nbrs.Count)];
            visited.Add(next);
            path.Add(next);
        }
        if (path.Count == 0 || path[^1] != _output)
        {
            // safety net (unreachable in practice): plain L-shaped path
            path.Clear();
            for (var r = 0; r < n; r++) path.Add((r, _input.C));
            var step = Math.Sign(_output.C - _input.C);
            if (step != 0)
                for (var c = _input.C + step; c != _output.C + step; c += step)
                    path.Add((n - 1, c));
        }

        // efficiency fixed at generation: min(1, ideal/actual) — clicks unscored
        _pipeEfficiency = Math.Min(1.0, _idealLen / (double)path.Count);

        var onPath = new HashSet<(int, int)>();
        for (var i = 0; i < path.Count; i++)
        {
            var (r, c) = path[i];
            onPath.Add((r, c));
            if (i == 0 || i == path.Count - 1) { _type[r, c] = 1; continue; }
            var dPrev = DirBetween(path[i], path[i - 1]);
            var dNext = DirBetween(path[i], path[i + 1]);
            _type[r, c] = (dPrev + 2) % 4 == dNext ? 1 : 2;   // straight or L-bend
        }
        for (var r = 0; r < n; r++)
            for (var c = 0; c < n; c++)
            {
                if (!onPath.Contains((r, c)))
                    _type[r, c] = DistractorTypes[_rng.Next(DistractorTypes.Length)];
                _rot[r, c] = _rng.Next(4);   // scramble ALL pieces (none empty/cross)
            }

        _clicks = 0;
        _flow.Clear();
        _grid.CustomMinimumSize = new Vector2(n * CellPx, n * CellPx);
        _introLabel.Text =
            $"Puzzle {_puzzleIndex + 1}/{PuzzleCount} — ROTATION PIPES\n"
            + $"grid {n}x{n} · ideal path {_idealLen} cells\n"
            + "Click a cell to rotate its pipe 90° clockwise.\n"
            + "Connect the green IN (top row) to the orange OUT (bottom row).";
    }

    private void StartPuzzle()
    {
        if (_phase != "intro") return;
        _phase = "playing";
        // scramble can leave the grid already solved (Python parity: the
        // per-frame get_state() solve check would flag it immediately)
        if (CheckSolved()) PuzzleSolved();
        else UpdatePhaseUi();
    }

    private void OnGridInput(InputEvent @event)
    {
        if (_phase != "playing") return;
        if (@event is not InputEventMouseButton
            { Pressed: true, ButtonIndex: MouseButton.Left } mb) return;
        var n = _gridSize;
        var cs = Mathf.Min(_grid.Size.X, _grid.Size.Y) / n;
        var c = (int)(mb.Position.X / cs);
        var r = (int)(mb.Position.Y / cs);
        if (r < 0 || r >= n || c < 0 || c >= n) return;
        if (_type[r, c] is 0 or 4) return;   // empty and cross pieces don't rotate
        _rot[r, c] = (_rot[r, c] + 1) % 4;   // 90° clockwise
        _clicks++;
        if (CheckSolved()) PuzzleSolved();   // solve check after every rotate
        else UpdatePhaseUi();
    }

    /// <summary>BFS over mutually-linked sides; ANY route counts (py:222-285).</summary>
    private bool CheckSolved()
    {
        _flow.Clear();
        var queue = new Queue<(int R, int C)>();
        queue.Enqueue(_input);
        _flow.Add(_input);
        while (queue.Count > 0)
        {
            var (r, c) = queue.Dequeue();
            for (var s = 0; s < 4; s++)
            {
                if (!SideOpen(r, c, s)) continue;
                var (nr, nc) = Step(r, c, s);
                if (nr < 0 || nr >= _gridSize || nc < 0 || nc >= _gridSize) continue;
                if (_flow.Contains((nr, nc))) continue;
                if (!SideOpen(nr, nc, (s + 2) % 4)) continue;   // mutual link
                _flow.Add((nr, nc));
                queue.Enqueue((nr, nc));
            }
        }
        return _flow.Contains(_output);
    }

    private void PuzzleSolved()
    {
        _solvedCount++;
        _efficiencies.Add(_pipeEfficiency);
        _phase = "solved";
        _solvedLabel.Text = $"Circuit connected!  Efficiency: {_pipeEfficiency * 100:0}%"
                            + $"   (clicks: {_clicks})";
        _nextButton.Text = _puzzleIndex >= PuzzleCount - 1
            ? "COMPLETE DEVICE" : "NEXT PUZZLE";
        UpdatePhaseUi();
    }

    private void AdvancePuzzle()
    {
        if (_phase != "solved") return;
        _puzzleIndex++;
        if (_puzzleIndex >= PuzzleCount) { EndGame(); return; }
        GeneratePuzzle();
        _phase = "intro";
        UpdatePhaseUi();
    }

    private void EndGame()
    {
        if (_phase == "done") return;
        _phase = "done";
        var completion = _solvedCount / (double)PuzzleCount;
        var avgEff = _efficiencies.Count > 0 ? _efficiencies.Average() : 1.0;
        var perf = completion * 0.5 + avgEff * 0.3;
        const double timeRatio = 0.0;   // BUG PRESERVED: read after deactivation → 0
        if (_solvedCount == PuzzleCount && !_expired) perf += timeRatio * 0.2;  // +0
        else if (_solvedCount == PuzzleCount) perf += 0.1;   // expired-but-complete
        // hint penalty (0.05 each) never fires — hints_used never increments
        perf = Math.Clamp(perf, 0.0, 1.0);
        perf = Math.Min(1.0, perf + 0.05);   // first-try bonus, attempt always 1
        _finalPerf = perf;

        var stats = new[] { 100, 100, 100, 100 };
        for (var i = 0; i < _efficiencies.Count; i++)
            stats[i % 4] += (int)(5 + 15 * _efficiencies[i]);
        var parts = new string[4];
        for (var i = 0; i < 4; i++) parts[i] = $"{StatNames[i]} {stats[i]}";

        _doneResult.Text = (_expired ? "Time's up!  " : "")
            + $"Device created! Solved {_solvedCount}/{PuzzleCount} puzzles."
            + $" Efficiency: {avgEff * 100:0}%";
        _doneStats.Text = string.Join(" · ", parts)
                          + $"   (quality {stats.Sum() / 4.0:0}%)";
        _donePerf.Text = $"Performance: {perf * 100:0}%";
        UpdatePhaseUi();
    }

    protected override void OnTick(double delta)
    {
        if (_phase == "done") return;
        var remaining = _timeLimit - (Time.GetTicksMsec() - _startMs) / 1000.0;
        _timerLabel.Text = $"Time: {Math.Max(0, remaining):0}s";
        _timerLabel.Modulate = remaining < 30 ? new Color(1f, 0.45f, 0.4f) : Colors.White;
        if (remaining <= 0)
        {
            _expired = true;   // auto-end with partial credit — no hard fail
            EndGame();
        }
    }

    private void UpdatePhaseUi()
    {
        _puzzleLabel.Text =
            $"Puzzle {Math.Min(_puzzleIndex + 1, PuzzleCount)}/{PuzzleCount}"
            + $"   clicks: {_clicks}";
        _introBox.Visible = _phase == "intro";
        _grid.Visible = _phase is "playing" or "solved";
        _legend.Visible = _grid.Visible;
        _solvedBox.Visible = _phase == "solved";
        _doneBox.Visible = _phase == "done";
        _grid.QueueRedraw();
    }

    private void DrawGrid()
    {
        var n = _gridSize;
        var cs = Mathf.Min(_grid.Size.X, _grid.Size.Y) / n;
        for (var r = 0; r < n; r++)
            for (var c = 0; c < n; c++)
            {
                var origin = new Vector2(c * cs, r * cs);
                var inFlow = _flow.Contains((r, c));
                _grid.DrawRect(
                    new Rect2(origin + Vector2.One, new Vector2(cs - 2, cs - 2)),
                    inFlow ? new Color(0.16f, 0.30f, 0.34f) : new Color(0.13f, 0.14f, 0.17f));
                _grid.DrawRect(
                    new Rect2(origin + Vector2.One, new Vector2(cs - 2, cs - 2)),
                    new Color(0.35f, 0.38f, 0.45f), false, 1f);
                var center = origin + new Vector2(cs / 2f, cs / 2f);
                var pipe = inFlow
                    ? new Color(0.88f, 0.62f, 0.30f)    // energized copper
                    : new Color(0.55f, 0.58f, 0.64f);   // cold steel
                var any = false;
                for (var s = 0; s < 4; s++)
                {
                    if (!SideOpen(r, c, s)) continue;
                    any = true;
                    var edge = s switch
                    {
                        0 => origin + new Vector2(cs / 2f, 0),
                        1 => origin + new Vector2(cs, cs / 2f),
                        2 => origin + new Vector2(cs / 2f, cs),
                        _ => origin + new Vector2(0, cs / 2f),
                    };
                    _grid.DrawLine(center, edge, pipe, 7f);
                }
                if (any) _grid.DrawCircle(center, 6f, pipe);
            }

        var inX = _input.C * cs + cs / 2f;
        _grid.DrawPolygon(
            new[] { new Vector2(inX, 15f), new Vector2(inX - 9f, 3f), new Vector2(inX + 9f, 3f) },
            new[] { new Color(0.30f, 0.85f, 0.42f) });
        var outX = _output.C * cs + cs / 2f;
        var outY = n * cs;
        _grid.DrawPolygon(
            new[]
            {
                new Vector2(outX, outY - 3f),
                new Vector2(outX - 9f, outY - 15f),
                new Vector2(outX + 9f, outY - 15f),
            },
            new[] { new Color(0.95f, 0.60f, 0.25f) });
    }

    /// <summary>Side open after rotation: base side rotated CW by _rot.</summary>
    private bool SideOpen(int r, int c, int side)
        => BaseSides[_type[r, c]][((side - _rot[r, c]) % 4 + 4) % 4];

    private static (int, int) Step(int r, int c, int side) => side switch
    {
        0 => (r - 1, c),
        1 => (r, c + 1),
        2 => (r + 1, c),
        _ => (r, c - 1),
    };

    private static int Manhattan((int R, int C) a, (int R, int C) b)
        => Math.Abs(a.R - b.R) + Math.Abs(a.C - b.C);

    /// <summary>Side of cell a facing adjacent cell b.</summary>
    private static int DirBetween((int R, int C) a, (int R, int C) b)
        => b.R < a.R ? 0 : b.C > a.C ? 1 : b.R > a.R ? 2 : 3;
}
