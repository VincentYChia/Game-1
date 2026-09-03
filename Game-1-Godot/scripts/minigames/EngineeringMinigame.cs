using Godot;

namespace Game1.Godot;

/// <summary>
/// ENGINEERING — "Circuit Lights" (all-in Lights-Out). A PLAN-THEN-EXECUTE logic
/// puzzle scored on a GRADIENT OF CORRECTNESS (not solved/unsolved). The player
/// reproduces a seeded target lit/dark pattern by flipping tiles; each flip toggles
/// a neighbourhood determined by the tile's tag-driven RULE VARIANT (Plus/Single/
/// Spread/Immovable/Invert/Wild). The generator guarantees the start state is
/// solvable within the move budget by generating the target BY FLIPPING (every rule
/// is a GF(2) involution), so re-applying the recorded scramble set is a guaranteed
/// solution of length ≤ _scramble.
///
/// House rule: the ONLY hard number on screen is the MOVE COUNT (a legit direct
/// scoring metric per the designer ruling). Time, correctness, and elegance are all
/// bars/feel. Tags touch the board ONLY through _ruleWeights / _timeMult / _moveMult
/// / _undoCharges / _gridBonus (§2). Consistency guard: WATER is the SOLE clock-
/// grower; FIRE => less time; ICE => fewer MOVES (never the clock).
///
/// The seam is untouched: the overlay owns only the play loop and hands a
/// performance 0..1 to <see cref="MinigameOverlay.Finish"/>. Circuit Lights NEVER
/// calls FailCraft — a botched board still delivers a coverage-floor perf (§4.5).
/// </summary>
public partial class EngineeringMinigame : MinigameOverlay
{
    protected override string Discipline => "engineering";

    // ============================================================ §1.1 ENUMS
    private enum Phase { Ready, Plan, Play, Settle, Done }

    // Per-tile RULE VARIANT — the tag-driven "character" of a tile (§2). Difficulty
    // never sets these; tags do.
    private enum TileRule : byte
    {
        Plus = 0,    // DEFAULT. Flip toggles self + 4 orthogonal neighbours (classic Lights-Out).
        Single,      // sharp/precision. Flip toggles ONLY self (no ripple).
        Spread,      // life. Flip toggles self + 8 neighbours (Moore neighbourhood).
        Immovable,   // earth heavy. Cannot be flipped directly; only toggled as a NEIGHBOUR.
        Invert,      // shadow/cursed. Self + 8 Moore + 4 orthogonal at distance 2 (13-cell curse-blast).
        Wild,        // chaos/dangerous. Self + 4 neighbours + one EXTRA telegraphed cell (seeded, shown).
    }

    // A pending planned flip during Phase.Plan (drawn as a ghost, applied on POWER ON).
    private readonly record struct GhostFlip(int R, int C, int Order);

    // ============================================================ §4 CONSTANTS
    private const double SettleDuration = 0.9;      // s — Settle freeze-frame length
    private const double MatchPulseDecay = 2.5;     // 1/s — per-cell match glow decay
    private const double LiveTravelW = 0.75;        // live-quality weight on coverage
    private const double LiveElegW = 0.15;          // live weight on move elegance
    private const double LiveTimeW = 0.10;          // live weight on time elegance
    private const double PerfCoverageW = 0.75;      // final: cells-matched fraction weight
    private const double PerfMoveW = 0.15;          // final: move elegance weight
    private const double PerfTimeW = 0.10;          // final: time elegance weight
    private const double CoverageFloorCap = 0.55;   // max perf a coverage-only run can reach
    private const double MashCoverageBaseline = 0.40;  // expected coverage from random flipping (calibration)
    private const int SlackBase = 4;                // budget slack at entry
    private const int SlackHardMin = 2;             // budget slack at legendary (before tag mult)
    private const double TargetLitFrac = 0.50;      // per-cell probability a target cell is lit
    private const int UndoBaseline = 1;             // minimum _undoLeft every recipe gets (R3 floor)

    // ================================================= §1.2 TILE GRID (parallel arrays)
    private bool[,] _state = new bool[1, 1];        // current lit state; true = lit
    private bool[,] _target = new bool[1, 1];       // goal state
    private TileRule[,] _rule = new TileRule[1, 1]; // per-tile rule variant
    private (int R, int C)[,] _wildExtra = new (int, int)[1, 1];  // Wild extra cell or (-1,-1)
    private int[,] _flipCount = new int[1, 1];      // times each cell directly flipped
    private float[,] _matchPulse = new float[1, 1]; // per-cell "just matched" glow 0..1

    // ============================================= §1.3 DIFFICULTY-INTERPOLATED PARAMS
    private int _rows, _cols;
    private int _moveBudget;
    private double _timeBudget;
    private int _scramble;
    private int _minSolution;

    // ================================================= §1.4 TAG-DERIVED KNOBS
    private double _timeMult = 1.0;                 // × on _timeBudget (0.55..1.6); water grows, fire shrinks
    private double _moveMult = 1.0;                 // × on budget SLACK (0.6..1.35); ice shrinks, water grows
    private double[] _ruleWeights = new double[6];  // weights for TileRule values [Plus..Wild]
    private int _undoCharges = UndoBaseline;        // undo-last-flip charges (UndoBaseline..2)
    private int _gridBonus;                         // earth/quality/slot additive bump (-2..+4)

    // ================================================= §1.5 RUN / ECONOMY / ANIMATION STATE
    private Phase _phase = Phase.Ready;
    private int _movesSpent;
    private readonly List<GhostFlip> _planGhosts = new();
    private double _timeLeft;
    private int _undoLeft;
    private readonly Stack<(int R, int C)> _flipHistory = new();
    private double _settleT;
    private double _finalPerf;
    private double _anim;
    private double _animAcc;
    private (int R, int C) _cursor = (0, 0);
    private RandomNumberGenerator _rng = new();

    // ============================================================ §1.6 UI NODES
    private Control _grid = null!;
    private Control _hud = null!;
    private VBoxContainer _readyBox = null!;
    private Label _readyLabel = null!;
    private Button _goButton = null!;
    private Label _hint = null!;
    private readonly MinigameDevLog _dev = new("engineering");

    // ============================================================ §6 PALETTE
    private static readonly Color Blueprint = new(0.55f, 0.78f, 0.98f);
    private static Color LitCol;         // CraftColor.Brighten(theme.Glow, 0.15) — set in OnBegin
    private static readonly Color DarkCol = new(0.10f, 0.13f, 0.19f);
    private static readonly Color MatchCol = UiTheme.Rarity["uncommon"];  // (0.45,0.9,0.45)
    private static Color MismatchCol;    // legendary.Lerp(DarkCol, 0.25) — set in OnBegin
    private static readonly Color GhostCol = new(Blueprint.R, Blueprint.G, Blueprint.B, 0.5f);
    private static readonly Color ImmovableCol = new(0.42f, 0.40f, 0.36f);
    private static readonly Color WildCol = UiTheme.Rarity["epic"];       // (0.78,0.45,0.98)
    private static readonly Color Fuse = new(1f, 0.4f, 0.32f);

    // ============================================= §2.4 THEME-DEFAULT FALLBACK SETS
    private static readonly HashSet<string> ThemeMetal = new() { "copper", "tin", "steel", "mithril", "bronze", "adamantine", "silver", "gold", "orichalcum" };
    private static readonly HashSet<string> ThemeWood = new() { "oak", "ash", "ironwood", "ebony", "worldtree", "exotic", "birch", "willow" };

    // Moore-neighbour offsets (8 diagonals+orthogonals) and orthogonal-only offsets.
    private static readonly (int Dr, int Dc)[] Ortho = { (-1, 0), (1, 0), (0, -1), (0, 1) };
    private static readonly (int Dr, int Dc)[] Moore =
    { (-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1) };
    private static readonly (int Dr, int Dc)[] Ring2 = { (-2, 0), (2, 0), (0, -2), (0, 2) };

    // ======================================================================= UI
    protected override void BuildUi(VBoxContainer host)
    {
        // §6.0 — add children top-to-bottom in this exact order.
        _hud = new Control { CustomMinimumSize = new Vector2(780, 62) };   // larger stage → bigger cells + more detail
        _hud.Draw += DrawHud;
        host.AddChild(_hud);

        _grid = new Control
        {
            CustomMinimumSize = new Vector2(780, 580),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
            FocusMode = Control.FocusModeEnum.None,
        };
        _grid.Draw += DrawGrid;
        _grid.GuiInput += OnGridInput;
        host.AddChild(_grid);

        _hint = new Label
        {
            Text = "",
            Modulate = new Color(0.78f, 0.86f, 1f),
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        _hint.AddThemeFontSizeOverride("font_size", 13);
        host.AddChild(_hint);

        _goButton = new Button { Text = "POWER ON", FocusMode = Control.FocusModeEnum.None, Visible = false };
        _goButton.AddThemeFontSizeOverride("font_size", 20);
        _goButton.Pressed += PowerOn;
        host.AddChild(_goButton);

        _readyBox = new VBoxContainer();
        _readyBox.AddThemeConstantOverride("separation", 8);
        host.AddChild(_readyBox);
        _readyLabel = new Label { HorizontalAlignment = HorizontalAlignment.Center };
        _readyLabel.AddThemeFontSizeOverride("font_size", 16);
        _readyBox.AddChild(_readyLabel);
        var begin = new Button { Text = "OPEN THE BENCH   [Space]", FocusMode = Control.FocusModeEnum.None };
        begin.AddThemeFontSizeOverride("font_size", 20);
        begin.Pressed += DismissSplash;
        _readyBox.AddChild(begin);

        // §6.0.6 — the F7 notes box is the only focusable child.
        _dev.BuildNotesPanel(_grid);
        _dev.Context = () => $"{_phase} | moves {_movesSpent}/{_moveBudget} | match {MatchedFrac():P0} | {_timeLeft:0.0}s";
        _dev.NoteSubmitted += n => _dev.Note(n, NoteSnapshot());
    }

    private IEnumerable<string> NoteSnapshot()
    {
        yield return $"phase={_phase} rows={_rows} cols={_cols} scramble={_scramble} budget={_moveBudget} timeBudget={_timeBudget:0.0}";
        yield return $"moves={_movesSpent} matched={MatchedFrac():P0} timeLeft={_timeLeft:0.0} undoLeft={_undoLeft}";
        yield return $"timeMult={_timeMult:0.00} moveMult={_moveMult:0.00} gridBonus={_gridBonus} ruleMix={DominantRuleMix()}";
    }

    // ==================================================================== BEGIN
    protected override void OnBegin()
    {
        LitCol = new Color(0.42f, 0.90f, 1.0f);         // bright electric cyan = "powered" (clear vs dark unlit)
        MismatchCol = new Color(0.98f, 0.42f, 0.36f);   // clear red so wrong cells read instantly (was a muddy gold)

        SeedRng();
        ApplyTagProfile();       // §2 — produce the tag-derived knobs
        SizeGrid();              // §7.1 — grid dimensions from difficulty + knobs
        BuildBoard();            // §4.1 — generate a solvable board

        _phase = Phase.Ready;
        _movesSpent = 0;
        _planGhosts.Clear();
        _flipHistory.Clear();
        _timeLeft = _timeBudget;
        _undoLeft = _undoCharges;
        _settleT = 0;
        _finalPerf = 0;
        _anim = 0;
        _animAcc = 0;

        _goButton.Visible = false;   // splash is up
        HideTimer();
        SetQuality(0);

        SetHeaderSub($"{_rows}×{_cols} board  ·  budget {_moveBudget}  ·  {_undoCharges} undo");
        _readyLabel.Text =
            "Reproduce the target circuit — flip tiles until every cell matches the goal.\n"
            + "A tile's badge shows how its flip spreads (the key stays on-screen below the board).\n"
            + "PLAN freely with no clock, then POWER ON.  Fewer moves and spare time make a cleaner device.";
        _readyBox.Visible = true;
        _hint.Text = "[Space] OPEN THE BENCH";

        _dev.BeginSession(DevHeader());

        _grid.QueueRedraw();
        _hud.QueueRedraw();
    }

    private IEnumerable<string> DevHeader()
    {
        var ids = Recipe != null ? string.Join(",", Recipe.Inputs.Select(i => i.Id)) : "(null recipe)";
        var tags = Recipe != null
            ? string.Join(",", Recipe.Inputs.SelectMany(i => i.Tags).Concat(Recipe.OutputTags).Distinct())
            : "engineering,metal,common,tool,utility";
        yield return $"recipe: {(Recipe?.OutputId ?? "(debug)")}  inputs=[{ids}]";
        yield return $"tags: {tags}";
        yield return $"DifficultyPoints={DifficultyPoints:0.#}  grid={_rows}×{_cols}  scramble={_scramble}";
        yield return $"moveBudget={_moveBudget} (minSolution={_minSolution})  timeBudget={_timeBudget:0.0}s";
        yield return $"knobs: timeMult={_timeMult:0.00} moveMult={_moveMult:0.00} undo={_undoCharges} gridBonus={_gridBonus}";
        yield return $"dominant rule mix: {DominantRuleMix()}";
    }

    private string DominantRuleMix()
    {
        var best = 1; for (var i = 2; i <= 5; i++) if (_ruleWeights[i] > _ruleWeights[best]) best = i;
        return _ruleWeights[best] <= 1e-6 ? "Plus-only" : $"{(TileRule)best} ({_ruleWeights[best]:0.00})";
    }

    /// <summary>Difficulty interpolation: easy at 1 pt → hard at 80 pts.</summary>
    private double DiffFrac => Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);
    private double Interp(double easy, double hard) => easy + (hard - easy) * DiffFrac;

    // ================================================================ §8 SEED
    private void SeedRng()
    {
        _rng = new RandomNumberGenerator();
        if (Recipe == null) { _rng.Seed = Time.GetTicksMsec(); return; }
        var inputIds = string.Join(",", Recipe.Inputs.Select(i => i.Id));
        var allTags = string.Join(",", Recipe.Inputs.SelectMany(i => i.Tags).Concat(Recipe.OutputTags));
        var seedStr = $"{Recipe.OutputId}|{inputIds}|{allTags}|{DifficultyPoints:0}";
        _rng.Seed = Fnv1a(seedStr);
    }

    private static ulong Fnv1a(string s)
    {
        const ulong offset = 14695981039346656037UL, prime = 1099511628211UL;
        var h = offset;
        foreach (var b in System.Text.Encoding.UTF8.GetBytes(s)) { h ^= b; h *= prime; }
        return h;
    }

    // ========================================================= §2 TAG PROFILE
    // Base table: Time = _timeMult (default 1), Rx = _moveMult (default 1). Pot=1, Vol=0 (unused).
    private static readonly Dictionary<string, (double Pot, double Vol, double Time, double Rx)> EngBase = BuildEngBase();
    private static readonly Dictionary<string, (TileRule Rule, double W)[]> RuleAdd = BuildRuleAdd();
    private static readonly Dictionary<string, double> UndoAdd = BuildUndoAdd();
    private static readonly Dictionary<string, double> GridAdd = BuildGridAdd();

    private void ApplyTagProfile()
    {
        var counts = AssembleCounts();

        // (2) Fold the two × scalars via the shared engine.
        var prof = new MinigameModifierCommon.ModProfile(6, 0);
        var amp = new Dictionary<string, double> { ["quantum"] = 1.30, ["impossible"] = 1.35, ["power"] = 1.30 };
        MinigameModifierCommon.Fold(prof, counts, EngBase, chExc: null, stExc: null, strongExc: amp);
        MinigameModifierCommon.Clamp(prof, timeLo: 0.55, timeHi: 1.6, rxLo: 0.6, rxHi: 1.35);
        _timeMult = prof.Time;
        _moveMult = prof.Rx;

        // (3) Accumulate the additive R:/U/G knobs in a manual StackFactor-weighted pass.
        double[] rw = new double[6];   // indexed by (int)TileRule; Plus(0) left 0 (residual)
        double uAcc = 0, gAcc = 0;
        foreach (var (tag, n) in counts)
        {
            var sf = MinigameModifierCommon.StackFactor(n);
            if (RuleAdd.TryGetValue(tag, out var ra)) foreach (var (rule, w) in ra) rw[(int)rule] += w * sf;
            if (UndoAdd.TryGetValue(tag, out var u)) uAcc += u * sf;
            if (GridAdd.TryGetValue(tag, out var g)) gAcc += g * sf;
            // theme-default fallback: fires ONLY for tags absent from every table.
            if (!EngBase.ContainsKey(tag) && !RuleAdd.ContainsKey(tag) && !UndoAdd.ContainsKey(tag) && !GridAdd.ContainsKey(tag))
                ThemeDefault(tag, sf, rw, ref gAcc);
        }

        // (4) Clamp / finalize R:, U (G finalized in SizeGrid step 6).
        for (var i = 1; i <= 5; i++) rw[i] = Math.Clamp(rw[i], 0, 1);
        _ruleWeights = rw;
        _undoCharges = Math.Clamp((int)Math.Round(uAcc) + UndoBaseline, 0, 2);

        // (5) Hand-rolled AmpStrongest pass: amplify the single largest NON-Plus rule weight.
        if (prof.AmpStrongest != 1.0)
        {
            int bi = 1; for (int i = 2; i <= 5; i++) if (rw[i] > rw[bi]) bi = i;
            if (rw[bi] > 0) rw[bi] = Math.Clamp(rw[bi] * prof.AmpStrongest, 0, 1);
        }

        // (6) grid bonus finalized in SizeGrid from gAcc + slot count.
        _gAcc = gAcc;
    }

    private double _gAcc;   // tag-side grid accumulator (feeds §7.1 with slot count)

    /// <summary>§2.4 step 1 — assemble tag counts with per-ingredient precedence 4/3/2/1,
    /// scaled by qty; OutputTags fold in at rank-1 weight.</summary>
    private Dictionary<string, int> AssembleCounts()
    {
        var counts = new Dictionary<string, int>();
        void Add(string tag, int add) { counts.TryGetValue(tag, out var v); counts[tag] = v + Math.Max(1, add); }

        if (Recipe != null)
        {
            foreach (var ing in Recipe.Inputs)
            {
                var rank = 0;
                foreach (var t in ing.Tags)
                {
                    var rankW = rank switch { 0 => 4.0, 1 => 3.0, 2 => 2.0, _ => 1.0 };
                    rank++;
                    Add(t, (int)Math.Round(rankW * Math.Max(1, ing.Qty)));
                }
            }
            foreach (var t in Recipe.OutputTags) Add(t, 1);
        }
        else
        {
            // Synthesize a plausible pool so the board is always playable (§1.7).
            foreach (var t in new[] { "engineering", "metal", "common" }) Add(t, 1);
            foreach (var t in new[] { "tool", "utility" }) Add(t, 1);
        }
        return counts;
    }

    /// <summary>§2.4 theme default — a tag with no entry in ANY table resolves to its
    /// elemental-theme default (Engineering's own classifier; NOT the private toolkit).</summary>
    private void ThemeDefault(string tag, double sf, double[] rw, ref double gAcc)
    {
        if (ThemeMetal.Contains(tag)) { rw[(int)TileRule.Immovable] += 0.14 * sf; gAcc += 1 * sf; }
        else if (ThemeWood.Contains(tag)) { rw[(int)TileRule.Spread] += 0.20 * sf; }
        // else: mild Plus bias (no change, still playable).
    }

    // ============================================= §7.1 GRID SIZING
    private void SizeGrid()
    {
        int slots = CountSlotFamilies();   // 0..5
        _gridBonus = Math.Clamp((int)Math.Round(_gAcc) + slots, -2, 4);
        int baseRows = (int)Math.Round(Interp(3, 8));
        int baseCols = (int)Math.Round(Interp(3, 8));
        _rows = Math.Clamp(baseRows + _gridBonus, 3, 9);
        _cols = Math.Clamp(baseCols + _gridBonus, 3, 9);
    }

    /// <summary>§2.3 — count of the 5 slot families present in OutputTags.</summary>
    private int CountSlotFamilies()
    {
        var outTags = new HashSet<string>(Recipe?.OutputTags ?? new List<string> { "tool", "utility" });
        int slots = 0;
        if (outTags.Overlaps(new[] { "armor", "protection", "defense", "resistance", "tool", "crafting" })) slots++;       // Frames
        if (outTags.Overlaps(new[] { "weapon", "combat", "utility", "fishing", "potion", "consumable" })) slots++;         // Function
        if (outTags.Overlaps(new[] { "explosive", "strength", "lightning", "energy", "power" })) slots++;                  // Power
        if (outTags.Overlaps(new[] { "buff", "enhancement", "healing", "regeneration", "speed", "agility", "resistance" })) slots++; // Modifier
        if (outTags.Overlaps(new[] { "utility", "engineering", "crafting", "harmony" })) slots++;                          // Utility
        return slots;
    }

    // ======================================================= §4.1 BOARD BUILD
    private void BuildBoard()
    {
        // §7.2 scramble depth = # generator flips = puzzle depth.
        _scramble = (int)Math.Round(Interp(2, 14));

        _state = new bool[_rows, _cols];
        _target = new bool[_rows, _cols];
        _rule = new TileRule[_rows, _cols];
        _wildExtra = new (int, int)[_rows, _cols];
        _flipCount = new int[_rows, _cols];
        _matchPulse = new float[_rows, _cols];

        // (1) Seed a NON-TRIVIAL target: per-cell coin-flip at TargetLitFrac.
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
                _target[r, c] = _rng.Randf() < (float)TargetLitFrac;

        // FEWER RULES: keep Plus + Single always, but cap the side-effect specials (Spread / Immovable /
        // Invert / Wild) to the top 1–2 by weight, so each board only ever teaches a couple of them.
        CapComplexRules((int)Math.Round(Interp(1, 2)));

        // (2) Seed _rule from _ruleWeights (weighted pick per cell); set _wildExtra.
        double nonPlusChance = Interp(0.08, 0.26);   // most tiles are plain now (was 0.12→0.40) — specials are a sprinkle
        double W = 0; for (var i = 1; i <= 5; i++) W += _ruleWeights[i];
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
            {
                _wildExtra[r, c] = (-1, -1);
                _rule[r, c] = PickRule(W, nonPlusChance);
                if (_rule[r, c] == TileRule.Wild) _wildExtra[r, c] = PickWildExtra(r, c);
            }

        // record which rules actually appear → the legend shows only those (less to memorise).
        _presentRules.Clear();
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
                _presentRules.Add(_rule[r, c]);

        // (3) _state = copy(_target) — start AT the goal.
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
                _state[r, c] = _target[r, c];

        // (4) Pick _scramble distinct FLIPPABLE cells (Fisher–Yates, exclude Immovable);
        //     apply ApplyFlip on each into _state (NOT counting moves).
        var candidates = new List<(int R, int C)>();
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
                if (_rule[r, c] != TileRule.Immovable) candidates.Add((r, c));
        ShuffleInPlace(candidates);
        int want = Math.Min(_scramble, candidates.Count);
        int applied = 0;
        for (var i = 0; i < want; i++)
        {
            var (sr, sc) = candidates[i];
            if (ApplyFlip(sr, sc, countMove: false)) applied++;   // flippable by construction
        }

        // (5) _minSolution = # of scramble flips on flippable tiles (upper bound on solve).
        _minSolution = applied;

        // (6) _moveBudget = _minSolution + slack (§4.3 / §7.2).
        double slackRaw = Interp(SlackBase, SlackHardMin);   // 4 → 2 across difficulty
        int slack = Math.Max(1, (int)Math.Round(slackRaw * _moveMult));   // ice tightens, water loosens
        _moveBudget = _minSolution + slack;

        // Clear match pulses seeded during scramble application.
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
                _matchPulse[r, c] = 0f;

        // Seeded cursor start (in-bounds).
        _cursor = ((int)(_rng.Randi() % (uint)_rows), (int)(_rng.Randi() % (uint)_cols));

        // Recompute _timeBudget (§4.4) — deterministic from points + tags.
        double timeRaw = Interp(40, 16);
        _timeBudget = Math.Clamp(timeRaw * _timeMult, 8, 60);
    }

    /// <summary>Keep Plus+Single always; zero all but the top-<paramref name="maxComplex"/> side-effect
    /// rules (Spread/Immovable/Invert/Wild) by weight, so a board never asks the player to track more than
    /// a couple of special behaviours at once.</summary>
    private void CapComplexRules(int maxComplex)
    {
        int[] complex = { (int)TileRule.Spread, (int)TileRule.Immovable, (int)TileRule.Invert, (int)TileRule.Wild };
        var kept = complex.OrderByDescending(i => _ruleWeights[i]).Take(Math.Max(0, maxComplex)).ToHashSet();
        foreach (var i in complex) if (!kept.Contains(i)) _ruleWeights[i] = 0;
    }

    /// <summary>§7.4 per-cell rule selection over the non-normalized additive weights.</summary>
    private TileRule PickRule(double W, double nonPlusChance)
    {
        if (W <= 1e-6) return TileRule.Plus;
        if (_rng.Randf() >= (float)nonPlusChance) return TileRule.Plus;
        double roll = _rng.Randf() * W;
        double acc = 0;
        for (var i = 1; i <= 5; i++) { acc += _ruleWeights[i]; if (roll < acc) return (TileRule)i; }
        return TileRule.Plus;
    }

    /// <summary>Wild extra cell: an in-bounds non-self cell within Chebyshev distance 2.</summary>
    private (int R, int C) PickWildExtra(int r, int c)
    {
        var opts = new List<(int R, int C)>();
        for (var dr = -2; dr <= 2; dr++)
            for (var dc = -2; dc <= 2; dc++)
            {
                if (dr == 0 && dc == 0) continue;
                int nr = r + dr, nc = c + dc;
                if (InBounds(nr, nc)) opts.Add((nr, nc));
            }
        if (opts.Count == 0) return (-1, -1);
        return opts[(int)(_rng.Randi() % (uint)opts.Count)];
    }

    private void ShuffleInPlace<T>(List<T> list)
    {
        for (var i = list.Count - 1; i > 0; i--)
        {
            var j = (int)(_rng.Randi() % (uint)(i + 1));
            (list[i], list[j]) = (list[j], list[i]);
        }
    }

    // ======================================================= §4.2 FLIP SEMANTICS
    /// <summary>Apply a flip at (r,c) per its rule. Returns false (no move) for a direct
    /// Immovable flip. Toggles each affected cell once (a GF(2) involution).</summary>
    private bool ApplyFlip(int r, int c, bool countMove)
    {
        if (!InBounds(r, c)) return false;
        var rule = _rule[r, c];
        if (rule == TileRule.Immovable) return false;   // direct flip forbidden

        var cells = new List<(int R, int C)> { (r, c) };
        switch (rule)
        {
            case TileRule.Single:
                break;   // self only
            case TileRule.Plus:
                foreach (var (dr, dc) in Ortho) if (InBounds(r + dr, c + dc)) cells.Add((r + dr, c + dc));
                break;
            case TileRule.Spread:
                foreach (var (dr, dc) in Moore) if (InBounds(r + dr, c + dc)) cells.Add((r + dr, c + dc));
                break;
            case TileRule.Invert:
                foreach (var (dr, dc) in Moore) if (InBounds(r + dr, c + dc)) cells.Add((r + dr, c + dc));
                foreach (var (dr, dc) in Ring2) if (InBounds(r + dr, c + dc)) cells.Add((r + dr, c + dc));
                break;
            case TileRule.Wild:
                foreach (var (dr, dc) in Ortho) if (InBounds(r + dr, c + dc)) cells.Add((r + dr, c + dc));
                var (wr, wc) = _wildExtra[r, c];
                if (wr >= 0 && InBounds(wr, wc)) cells.Add((wr, wc));
                break;
        }

        // Distinct set — each affected cell toggled exactly once.
        var seen = new HashSet<(int, int)>();
        foreach (var (cr, cc) in cells)
        {
            if (!seen.Add((cr, cc))) continue;
            bool before = _state[cr, cc] == _target[cr, cc];
            _state[cr, cc] = !_state[cr, cc];
            bool after = _state[cr, cc] == _target[cr, cc];
            if (!before && after) _matchPulse[cr, cc] = 1f;   // just became matched
        }
        // caller increments _movesSpent (keeps Plan-ghost + Play commit uniform)
        _ = countMove;
        return true;
    }

    private bool AllMatched()
    {
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
                if (_state[r, c] != _target[r, c]) return false;
        return true;
    }

    private double MatchedFrac()
    {
        int m = 0;
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
                if (_state[r, c] == _target[r, c]) m++;
        return (double)m / Math.Max(1, _rows * _cols);
    }

    private int MatchedCount()
    {
        int m = 0;
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
                if (_state[r, c] == _target[r, c]) m++;
        return m;
    }

    // ===================================================================== TICK
    protected override void OnTick(double delta)
    {
        _anim += delta;

        // decay match pulses
        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
                if (_matchPulse[r, c] > 0f)
                    _matchPulse[r, c] = (float)Math.Max(0, _matchPulse[r, c] - MatchPulseDecay * delta);

        if (_phase == Phase.Play)
        {
            _timeLeft -= delta;
            SetTimer(_timeLeft, warnAt: Math.Min(8, _timeBudget * 0.25));
            _hud.QueueRedraw();
            if (_timeLeft <= 0) { _timeLeft = 0; EnterSettle(); }
        }
        else if (_phase == Phase.Settle)
        {
            _settleT += delta;
            if (_settleT >= SettleDuration) { EnterDone(); return; }
            _grid.QueueRedraw();
        }

        // §6.5 redraw throttle — cap animated repaints at ~20 Hz.
        _animAcc += delta;
        if (_animAcc >= 0.05) { _animAcc = 0; _grid.QueueRedraw(); }
    }

    // ================================================================ §3 STATE MACHINE
    private void DismissSplash()
    {
        if (_phase != Phase.Ready) return;
        _readyBox.Visible = false;
        _phase = Phase.Plan;
        _goButton.Visible = true;
        _hint.Text = "PLAN — click a tile (or arrows + Enter) to queue a flip.    Space / POWER ON when ready.";
        SetHeaderSub($"{_rows}×{_cols} board  ·  budget {_moveBudget}");
        _grid.QueueRedraw();
        _hud.QueueRedraw();
    }

    private void PowerOn()
    {
        if (_phase != Phase.Plan) return;
        // Apply all queued ghosts in order, each = one committed flip.
        foreach (var g in _planGhosts.OrderBy(x => x.Order))
        {
            if (_movesSpent >= _moveBudget) break;
            if (ApplyFlip(g.R, g.C, countMove: true))
            {
                _flipHistory.Push((g.R, g.C));
                _movesSpent++;
                _flipCount[g.R, g.C]++;
            }
        }
        _planGhosts.Clear();
        _phase = Phase.Play;
        _timeLeft = _timeBudget;
        _undoLeft = _undoCharges;
        _goButton.Visible = false;
        _hint.Text = "RUN — flip tiles to match the goal.    Z = undo.";
        SetHeaderSub("POWER ON — match the circuit!");
        SetTimer(_timeLeft, warnAt: Math.Min(8, _timeBudget * 0.25));
        _dev.Log($"POWER ON — committed {_movesSpent} planned flip(s)");
        CraftFx.Burst(_grid, CellCenter(_cursor.R, _cursor.C), LitCol, 16, 160f, 0.6f, 3f, 40f);

        UpdateLiveQuality();
        if (AllMatched()) EnterSettle();
        _grid.QueueRedraw();
        _hud.QueueRedraw();
    }

    private void EnterSettle()
    {
        if (_phase == Phase.Settle || _phase == Phase.Done) return;
        _finalPerf = ComputeFinalPerf();
        _phase = Phase.Settle;
        _settleT = 0;
        HideTimer();
        SetQuality(_finalPerf);

        if (AllMatched())
        {
            Shake(13f);
            CraftFx.Burst(_grid, BoardCenter(), MatchCol, 48, 340f, 1.0f, 5f, 120f);
            FlashQuality();
            Popup(_grid, BoardCenter() + new Vector2(0, -32), "POWERED!", CraftStyle.Get("engineering").Glow, 32);
            _dev.Log($"SOLVED — perf {_finalPerf * 100:0}%  (moves {_movesSpent}/{_moveBudget}, {_timeLeft:0.0}s left)");
        }
        else
        {
            Shake(6f);
            _dev.Log($"SETTLE (partial) — perf {_finalPerf * 100:0}%  (match {MatchedFrac():P0}, moves {_movesSpent}/{_moveBudget})");
        }
        _grid.QueueRedraw();
    }

    private void EnterDone()
    {
        _phase = Phase.Done;
        var band = CraftFx.Band(_finalPerf);
        Popup(_grid, BoardCenter(), band.Name, band.Col, 28);
        _dev.Log($"DONE — Finish({_finalPerf:0.000})");
        Finish(_finalPerf);
    }

    // ================================================================ §5 INPUT
    public override void _Input(InputEvent e)
    {
        if (!Running) return;
        if (e is not InputEventKey { Pressed: true, Echo: false } k) return;
        // claim F1/F7 at the EARLIEST input stage so they never reach the world's global debug handler
        if (_dev.HandleKey(k.PhysicalKeycode)) { _grid.QueueRedraw(); GetViewport().SetInputAsHandled(); }
    }

    protected override void OnInput(InputEvent e)
    {
        if (e is not InputEventKey { Pressed: true, Echo: false } k) return;
        if (_dev.NotesEditHasFocus) return;   // let the notes LineEdit type freely
        switch (k.PhysicalKeycode)
        {
            case Key.Space:
                if (_phase == Phase.Ready) DismissSplash();
                else if (_phase == Phase.Plan) PowerOn();
                GetViewport().SetInputAsHandled(); break;
            case Key.Z: if (_phase == Phase.Play) TryUndo(); GetViewport().SetInputAsHandled(); break;
            case Key.Left: MoveCursor(0, -1); GetViewport().SetInputAsHandled(); break;
            case Key.Right: MoveCursor(0, 1); GetViewport().SetInputAsHandled(); break;
            case Key.Up: MoveCursor(-1, 0); GetViewport().SetInputAsHandled(); break;
            case Key.Down: MoveCursor(1, 0); GetViewport().SetInputAsHandled(); break;
            case Key.Enter: case Key.KpEnter: FlipAtCursor(); GetViewport().SetInputAsHandled(); break;
        }
    }

    private void OnGridInput(InputEvent e)
    {
        if (e is not InputEventMouseButton { Pressed: true, ButtonIndex: MouseButton.Left } mb) return;
        if (_phase != Phase.Plan && _phase != Phase.Play) return;
        var cell = CellAt(mb.Position);
        if (cell is not { } rc) return;
        if (_phase == Phase.Plan) QueueGhost(rc.R, rc.C);
        else CommitFlip(rc.R, rc.C);
    }

    private void MoveCursor(int dr, int dc)
    {
        if (_phase != Phase.Plan && _phase != Phase.Play) return;
        int nr = Math.Clamp(_cursor.R + dr, 0, _rows - 1);
        int nc = Math.Clamp(_cursor.C + dc, 0, _cols - 1);
        _cursor = (nr, nc);
        _grid.QueueRedraw();
    }

    private void FlipAtCursor()
    {
        if (_phase == Phase.Plan) QueueGhost(_cursor.R, _cursor.C);
        else if (_phase == Phase.Play) CommitFlip(_cursor.R, _cursor.C);
    }

    /// <summary>Plan: toggle a GhostFlip in the queue. Immovable cells rejected.</summary>
    private void QueueGhost(int r, int c)
    {
        if (_rule[r, c] == TileRule.Immovable)
        {
            CraftFx.Burst(_grid, CellCenter(r, c), Fuse, 5, 70f, 0.4f, 2.5f, 40f);
            Popup(_grid, CellCenter(r, c) + new Vector2(0, -22), "locked", Fuse, 15);
            return;
        }
        int idx = _planGhosts.FindIndex(g => g.R == r && g.C == c);
        if (idx >= 0)
        {
            _planGhosts.RemoveAt(idx);
            // renumber Order to stay contiguous
            for (var i = 0; i < _planGhosts.Count; i++) _planGhosts[i] = _planGhosts[i] with { Order = i };
        }
        else
        {
            _planGhosts.Add(new GhostFlip(r, c, _planGhosts.Count));
            CraftFx.Burst(_grid, CellCenter(r, c), Blueprint, 4, 60f, 0.35f, 2f, 40f);
        }
        _grid.QueueRedraw();
    }

    /// <summary>Play: commit a live flip if flippable and moves remain.</summary>
    private void CommitFlip(int r, int c)
    {
        if (_phase != Phase.Play || !Running) return;
        if (_rule[r, c] == TileRule.Immovable)
        {
            CraftFx.Burst(_grid, CellCenter(r, c), Fuse, 5, 70f, 0.4f, 2.5f, 40f);
            Popup(_grid, CellCenter(r, c) + new Vector2(0, -22), "locked", Fuse, 15);
            return;
        }
        if (_movesSpent >= _moveBudget)
        {
            CraftFx.Burst(_grid, CellCenter(r, c), Fuse, 5, 70f, 0.4f, 2.5f, 40f);
            Popup(_grid, CellCenter(r, c) + new Vector2(0, -22), "no moves", Fuse, 15);
            return;
        }

        int before = MatchedCount();
        if (!ApplyFlip(r, c, countMove: true)) return;
        _flipHistory.Push((r, c));
        _movesSpent++;
        _flipCount[r, c]++;
        CraftFx.Burst(_grid, CellCenter(r, c), LitCol, 6, 120f, 0.4f, 3f, 60f);

        int gained = MatchedCount() - before;
        if (gained >= 2)
        {
            Shake(5f);
            Popup(_grid, CellCenter(r, c) - new Vector2(0, 26), $"+{gained}", MatchCol, 20);
        }

        UpdateLiveQuality();
        _dev.Log($"FLIP ({r},{c}) {_rule[r, c]} Δmatch {gained:+0;-0;0}");
        _grid.QueueRedraw();
        _hud.QueueRedraw();

        if (AllMatched()) { EnterSettle(); return; }
        if (_movesSpent >= _moveBudget) EnterSettle();
    }

    /// <summary>Z in Play: spend 1 undo charge, pop history, re-apply that flip to invert it.</summary>
    private void TryUndo()
    {
        if (_phase != Phase.Play) return;
        if (_undoLeft <= 0 || _flipHistory.Count == 0)
        {
            Popup(_grid, BoardCenter() + new Vector2(0, -40), "no undo", Fuse, 15);
            return;
        }
        var (r, c) = _flipHistory.Pop();
        ApplyFlip(r, c, countMove: false);   // re-applying inverts (involution)
        _undoLeft--;
        _movesSpent = Math.Max(0, _movesSpent - 1);
        if (_flipCount[r, c] > 0) _flipCount[r, c]--;
        CraftFx.Burst(_grid, CellCenter(r, c), Blueprint, 6, 100f, 0.4f, 2.5f, 40f);
        Popup(_grid, CellCenter(r, c) - new Vector2(0, 24), "undo", Blueprint, 16);
        UpdateLiveQuality();
        _dev.Log($"UNDO ({r},{c}) — undoLeft {_undoLeft}");
        _grid.QueueRedraw();
        _hud.QueueRedraw();
    }

    // ================================================================ §4.5 SCORING
    private void UpdateLiveQuality()
    {
        double coverage = MatchedFrac();
        double moveEleg = Math.Clamp((double)(_moveBudget - _movesSpent) / Math.Max(1, _moveBudget), 0, 1);
        double timeEleg = Math.Clamp(_timeLeft / Math.Max(1e-6, _timeBudget), 0, 1);
        double live = LiveTravelW * coverage + LiveElegW * moveEleg + LiveTimeW * timeEleg;
        SetQuality(Math.Clamp(live, 0, 0.97));   // cap <1 until Settle confirms
    }

    private double ComputeFinalPerf()
    {
        double coverage = MatchedFrac();
        bool solved = AllMatched();
        double moveEleg = Math.Clamp((double)(_moveBudget - _movesSpent) / Math.Max(1, _moveBudget), 0, 1);
        double timeEleg = Math.Clamp(_timeLeft / Math.Max(1e-6, _timeBudget), 0, 1);
        double perf = PerfCoverageW * coverage + PerfMoveW * moveEleg + PerfTimeW * timeEleg;
        if (!solved) perf = Math.Min(perf, CoverageFloorCap);   // elegance only pays off on a solve
        return Math.Clamp(perf, 0, 1);
    }

    // =============================================================== §6.1 GEOMETRY
    private const float LegendBand = 52f;   // reserved strip at the bottom so the rule key ALWAYS has room
    private float Cell() => Mathf.Min((_grid.Size.X - 44) / _cols, (_grid.Size.Y - 44 - LegendBand) / _rows);
    private Vector2 Origin() { var s = Cell(); return new Vector2((_grid.Size.X - _cols * s) * 0.5f, Mathf.Max(10f, (_grid.Size.Y - LegendBand - _rows * s) * 0.5f)); }
    private Rect2 CellRect(int r, int c) { var s = Cell(); return new Rect2(Origin() + new Vector2(c * s, r * s) + new Vector2(3, 3), new Vector2(s - 6, s - 6)); }
    private Vector2 CellCenter(int r, int c) { var s = Cell(); return Origin() + new Vector2(c * s + s / 2, r * s + s / 2); }
    private Vector2 BoardCenter() => new(_grid.Size.X * 0.5f, _grid.Size.Y * 0.5f);
    private (int R, int C)? CellAt(Vector2 p)
    {
        var s = Cell(); var o = Origin();
        var c = (int)Mathf.Floor((p.X - o.X) / s);
        var r = (int)Mathf.Floor((p.Y - o.Y) / s);
        return InBounds(r, c) ? (r, c) : null;
    }
    private bool InBounds(int r, int c) => r >= 0 && r < _rows && c >= 0 && c < _cols;

    // =================================================================== §6 DRAW
    private void DrawGrid()
    {
        var font = _grid.GetThemeDefaultFont();
        var s = Cell();
        bool showMatch = _phase == Phase.Play || _phase == Phase.Settle;

        // #0 board backing panel
        var boardRect = new Rect2(Origin() - new Vector2(8, 8), new Vector2(_cols * s + 16, _rows * s + 16));
        CraftFx.RoundRect(_grid, boardRect, new Color(0.05f, 0.08f, 0.13f, 0.85f),
            new Color(Blueprint.R, Blueprint.G, Blueprint.B, 0.35f), 2, 12);

        for (var r = 0; r < _rows; r++)
            for (var c = 0; c < _cols; c++)
            {
                var rect = CellRect(r, c);
                var ctr = CellCenter(r, c);
                bool lit = _state[r, c];
                bool matched = _state[r, c] == _target[r, c];

                // #1 tile fill
                CraftFx.RoundRect(_grid, rect, lit ? LitCol : DarkCol, null, 0, 8);

                // #2 match/mismatch edge (only in Play/Settle; neutral in Plan)
                if (showMatch)
                {
                    var edge = matched ? MatchCol : MismatchCol;
                    CraftFx.RoundRect(_grid, rect, new Color(0, 0, 0, 0), new Color(edge.R, edge.G, edge.B, 0.7f), 2, 8);
                }
                else
                {
                    CraftFx.RoundRect(_grid, rect, new Color(0, 0, 0, 0), new Color(0.3f, 0.33f, 0.4f), 1, 8);
                }

                // #3 lit glow (idle shimmer radius from the free-running clock)
                if (lit)
                {
                    float shimmer = s * 0.42f * (0.9f + 0.1f * Mathf.Sin((float)_anim * 3f + r + c));
                    CraftFx.Glow(_grid, ctr, shimmer, new Color(LitCol.R, LitCol.G, LitCol.B, 0.25f), 3);
                }

                // #4 match pulse ring
                if (_matchPulse[r, c] > 0.02f)
                    CraftFx.RingPulse(_grid, ctr, s * 0.3f, 1f - _matchPulse[r, c], MatchCol, 2.5f, 0.6f);

                // #5 rule glyph badge (persistent tell)
                DrawRuleBadge(font, r, c, rect, ctr, s);

                // #6 wild tether (Plan+Play only)
                if (_rule[r, c] == TileRule.Wild && (_phase == Phase.Plan || _phase == Phase.Play))
                {
                    var (wr, wc) = _wildExtra[r, c];
                    if (wr >= 0)
                        CraftFx.Streak(_grid, ctr, CellCenter(wr, wc),
                            new Color(WildCol.R, WildCol.G, WildCol.B, 0.5f), 2f, 8);
                }

                // #9 target pip (bottom-right corner where the goal wants this cell LIT) — brighter/clearer
                if (_target[r, c])
                {
                    var gp = rect.End - new Vector2(8, 8);
                    _grid.DrawCircle(gp, 4.5f, new Color(Blueprint.R, Blueprint.G, Blueprint.B, 0.75f));
                    _grid.DrawCircle(gp, 2f, new Color(1, 1, 1, 0.9f));
                }
            }

        // #7 plan ghosts (queued flips, Plan only)
        if (_phase == Phase.Plan)
            foreach (var g in _planGhosts)
            {
                var ctr = CellCenter(g.R, g.C);
                CraftFx.Ring(_grid, ctr, s * 0.28f, GhostCol, 2f);
                _grid.DrawString(font, ctr - new Vector2(4, -4), (g.Order + 1).ToString(),
                    HorizontalAlignment.Left, 40, 12, GhostCol);
            }

        // #8 cursor (Plan/Play)
        if (_phase == Phase.Plan || _phase == Phase.Play)
            CraftFx.RoundRect(_grid, CellRect(_cursor.R, _cursor.C), new Color(0, 0, 0, 0), UiTheme.Accent, 3, 8);

        // Settle energise sweep (left→right across matched cells)
        if (_phase == Phase.Settle)
        {
            float sweepX = Origin().X + (float)(_settleT / SettleDuration) * (_cols * s);
            CraftFx.Streak(_grid, new Vector2(sweepX, Origin().Y), new Vector2(sweepX, Origin().Y + _rows * s),
                new Color(LitCol.R, LitCol.G, LitCol.B, 0.7f), 3f, 8);
        }

        // persistent rule key (below the board)
        DrawLegend(font);

        // F1 on-screen log
        if (_dev.ShowLog)
            _dev.DrawLog(_grid, new Rect2(_grid.Size.X - 250, 6, 244, _grid.Size.Y - 12), font, PinnedStatus());
    }

    private IReadOnlyList<(string, Color)> PinnedStatus() => new (string, Color)[]
    {
        ($"phase {_phase}", Blueprint),
        ($"moves {_movesSpent}/{_moveBudget}  undo {_undoLeft}", new Color(0.7f, 0.82f, 1f)),
        ($"match {MatchedFrac():P0}  time {_timeLeft:0.0}s", MatchCol),
        ($"grid {_rows}x{_cols}  scramble {_scramble}", GhostCol),
    };

    // §6.3 rule badge — a LARGE distinct colour-block per rule (colour = the tell, shape disambiguates).
    private void DrawRuleBadge(Font font, int r, int c, Rect2 rect, Vector2 ctr, float s)
    {
        var rule = _rule[r, c];
        float chip = Mathf.Clamp(s * 0.34f, 20f, 34f);
        DrawRuleChip(rule, rect.Position + new Vector2(4, 4), chip);
        // tile-scale extra tells (kept from before)
        if (rule == TileRule.Immovable)
            CraftFx.RoundRect(_grid, rect, new Color(0, 0, 0, 0), new Color(0.88f, 0.74f, 0.46f, 0.5f), 2, 8);
    }

    // Shared rule icon: a rounded colour chip with a distinct shape. Used BOTH on tiles and in the legend,
    // so a badge and its key entry always look identical. Large + colour-first for readability.
    private void DrawRuleChip(TileRule rule, Vector2 topLeft, float size)
    {
        var col = RuleKeyColor(rule);
        var plaque = new Rect2(topLeft, new Vector2(size, size));
        CraftFx.RoundRect(_grid, plaque, new Color(0.04f, 0.05f, 0.08f, 0.92f), col, 2, 5);
        var c = plaque.GetCenter();
        float r = size * 0.30f;
        switch (rule)
        {
            case TileRule.Plus:        // cross
                _grid.DrawRect(new Rect2(c.X - r, c.Y - r * 0.34f, r * 2, r * 0.68f), col);
                _grid.DrawRect(new Rect2(c.X - r * 0.34f, c.Y - r, r * 0.68f, r * 2), col);
                break;
            case TileRule.Single:      // solid dot
                _grid.DrawCircle(c, r * 0.78f, col);
                break;
            case TileRule.Spread:      // four spreading pips
                foreach (var d in new[] { new Vector2(1, 1), new Vector2(-1, 1), new Vector2(1, -1), new Vector2(-1, -1) })
                    _grid.DrawCircle(c + d * (r * 0.72f), r * 0.34f, col);
                break;
            case TileRule.Immovable:   // solid filled block (locked)
                _grid.DrawRect(new Rect2(c.X - r * 0.85f, c.Y - r * 0.85f, r * 1.7f, r * 1.7f), col);
                break;
            case TileRule.Invert:      // diamond
                _grid.DrawColoredPolygon(new[] { new Vector2(c.X, c.Y - r), new Vector2(c.X + r, c.Y), new Vector2(c.X, c.Y + r), new Vector2(c.X - r, c.Y) }, col);
                break;
            case TileRule.Wild:        // quartered multi-block
                float h = r * 0.82f;
                _grid.DrawRect(new Rect2(c.X - h, c.Y - h, h, h), col);
                _grid.DrawRect(new Rect2(c.X, c.Y, h, h), col);
                _grid.DrawRect(new Rect2(c.X - h, c.Y, h, h), new Color(col.R * 0.6f, col.G * 0.7f, col.B * 1.0f));
                _grid.DrawRect(new Rect2(c.X, c.Y - h, h, h), new Color(col.R * 1.0f, col.G * 0.7f, col.B * 0.6f));
                break;
        }
    }

    // §6.3b persistent rule key — a clean centred legend in the letterbox below the board, so the
    // badges never have to be memorised. Shows ONLY the rules actually present on THIS board (less to read).
    private static readonly (TileRule Rule, string Glyph, string Name, string Desc)[] _legend =
    {
        (TileRule.Plus,      "+", "ripple", "Flips this tile and its 4 side-neighbours."),
        (TileRule.Single,    ".", "single", "Flips only this tile."),
        (TileRule.Spread,    "S", "spread", "Flips this tile and all 8 around it (3x3)."),
        (TileRule.Immovable, "X", "locked", "Can't be flipped directly - only a neighbour's ripple changes it."),
        (TileRule.Invert,    "!", "blast",  "Flips a 5x5 area centred on this tile."),
        (TileRule.Wild,      "?", "wild",   "Flips this tile, its 4 side-neighbours, and one linked tile."),
    };
    private readonly HashSet<TileRule> _presentRules = new();   // rules that appear on the current board

    private void DrawLegend(Font font)
    {
        var items = _legend.Where(e => _presentRules.Count == 0 || _presentRules.Contains(e.Rule)).ToArray();
        if (items.Length == 0) return;

        // ALWAYS drawn in the reserved bottom band (LegendBand) — no longer depends on letterbox clearance.
        const float chip = 26f, itemW = 132f;
        float y = _grid.Size.Y - LegendBand + (LegendBand - chip) * 0.5f;
        float x0 = Mathf.Max(8f, (_grid.Size.X - items.Length * itemW) * 0.5f);
        var mouse = _grid.GetLocalMousePosition();

        int hover = -1;
        for (var i = 0; i < items.Length; i++)
        {
            var (rule, _, name, _) = items[i];
            float x = x0 + i * itemW;
            DrawRuleChip(rule, new Vector2(x, y), chip);
            var col = RuleKeyColor(rule);
            _grid.DrawString(font, new Vector2(x + chip + 7, y + chip * 0.74f), name, HorizontalAlignment.Left,
                (int)(itemW - chip - 12), 16, new Color(col.R, col.G, col.B, 0.95f));
            if (new Rect2(x, y - 4, itemW - 8, chip + 8).HasPoint(mouse)) hover = i;
        }

        // hover tooltip — the effect description for the pointed-at rule (drawn last, above the band)
        if (hover >= 0)
        {
            var (hr, _, hname, hdesc) = items[hover];
            DrawTooltip(font, new Vector2(x0 + hover * itemW, y - 10), hname, hdesc, RuleKeyColor(hr));
        }
    }

    private void DrawTooltip(Font font, Vector2 anchorBottomLeft, string title, string desc, Color titleCol)
    {
        const int titleSize = 15, descSize = 14, pad = 9;
        float tw = font.GetStringSize(title, HorizontalAlignment.Left, -1, titleSize).X;
        float dw = font.GetStringSize(desc, HorizontalAlignment.Left, -1, descSize).X;
        float w = Mathf.Max(tw, dw) + pad * 2;
        float h = titleSize + descSize + pad * 2 + 6;
        float bx = Mathf.Clamp(anchorBottomLeft.X, 4f, _grid.Size.X - w - 4f);
        float by = anchorBottomLeft.Y - h;
        var box = new Rect2(bx, by, w, h);
        CraftFx.RoundRect(_grid, box, new Color(0.04f, 0.06f, 0.10f, 0.97f), new Color(titleCol.R, titleCol.G, titleCol.B, 0.85f), 2, 6);
        _grid.DrawString(font, new Vector2(bx + pad, by + pad + titleSize - 3), title, HorizontalAlignment.Left, (int)(w - pad * 2), titleSize, titleCol);
        _grid.DrawString(font, new Vector2(bx + pad, by + pad + titleSize + descSize + 1), desc, HorizontalAlignment.Left, (int)(w - pad * 2), descSize, new Color(0.9f, 0.93f, 0.98f, 0.95f));
    }

    // distinct, saturated, high-contrast hue per rule — COLOUR is the primary readable tell.
    private Color RuleKeyColor(TileRule rule) => rule switch
    {
        TileRule.Plus => new Color(0.42f, 0.72f, 1.00f),      // blue   — ripple
        TileRule.Single => new Color(0.55f, 0.95f, 0.92f),    // cyan   — single
        TileRule.Spread => new Color(0.55f, 0.92f, 0.50f),    // green  — spread
        TileRule.Immovable => new Color(0.88f, 0.74f, 0.46f), // amber  — locked
        TileRule.Invert => new Color(1.00f, 0.55f, 0.34f),    // orange — blast
        _ => new Color(0.82f, 0.54f, 1.00f),                  // purple — wild
    };

    // §6.4 HUD — move-count number + pips + time bar + correctness bar.
    private void DrawHud()
    {
        var font = _hud.GetThemeDefaultFont();
        float w = _hud.Size.X;

        // move-count NUMBER (the allowed direct-scoring number)
        int remaining = _moveBudget - _movesSpent;
        var numCol = remaining > 0 ? new Color(0.7f, 0.82f, 1f) : Fuse;
        _hud.DrawString(font, new Vector2(6, 20), $"moves {remaining}/{_moveBudget}", HorizontalAlignment.Left, 220, 16, numCol);

        // move pip row (spent / available), one per budget slot from x=6 every 15px
        for (var i = 0; i < _moveBudget; i++)
        {
            float cx = 6 + i * 15f + 5f;
            if (cx > w * 0.30f) break;   // keep pips off the correctness/time bars
            var pc = i < _movesSpent ? new Color(0.28f, 0.30f, 0.36f) : Blueprint;
            _hud.DrawCircle(new Vector2(cx, 36), 4.5f, pc);
        }

        var track = new Color(0.12f, 0.13f, 0.18f);

        // correctness bar (center)
        CraftFx.Bar(_hud, new Rect2(w * 0.32f, 14, w * 0.26f, 12), (float)MatchedFrac(), track, MatchCol);

        // time bar (right third): green→Fuse by 1-timeEleg
        float timeEleg = (float)Math.Clamp(_timeLeft / Math.Max(1e-6, _timeBudget), 0, 1);
        var timeFill = new Color(0.45f, 0.9f, 0.45f).Lerp(Fuse, 1f - timeEleg);
        CraftFx.Bar(_hud, new Rect2(w * 0.62f, 14, w * 0.34f, 12), timeEleg, track, timeFill);
    }

    // ================================================= §2 TAG TABLES
    // Base table: Time = _timeMult contribution, Rx = _moveMult contribution.
    // Pot=1, Vol=0 always (unused). One COMBINED entry per tag (double-role tags resolved here).
    private static Dictionary<string, (double Pot, double Vol, double Time, double Rx)> BuildEngBase()
    {
        (double, double, double, double) T(double time) => (1.0, 0.0, time, 1.0);
        (double, double, double, double) M(double move) => (1.0, 0.0, 1.0, move);
        (double, double, double, double) TM(double time, double move) => (1.0, 0.0, time, move);
        return new()
        {
            // --- FIRE / HEAT (less time) ---
            ["fire"] = T(0.80), ["flame"] = T(0.80), ["ember"] = T(0.80), ["forge"] = T(0.80),
            ["molten"] = T(0.72), ["volcanic"] = T(0.72),
            ["lightning"] = T(0.78), ["storm"] = T(0.78),
            ["radiant"] = T(0.88), ["light"] = T(0.88),
            ["chaos"] = T(0.82),
            // --- WATER (extra time + undo) ---
            ["water"] = T(1.25), ["aqua"] = T(1.25), ["liquid"] = T(1.25),
            ["solvent"] = TM(1.25, 1.10),
            // --- ICE (fewer moves; NO time knob) ---
            ["ice"] = M(0.72), ["frost"] = M(0.72), ["chill"] = M(0.72),
            ["frozen"] = M(0.66),
            // --- EARTH / structural (mass; no time) ---
            ["mithril"] = M(1.05), ["adamantine"] = M(1.05), ["orichalcum"] = M(1.05),
            // (void carries an M×0.92 rider — negation costs planning)
            ["void"] = M(0.92),
            // --- QUALITY / GRADE (move slack riders) ---
            ["rare"] = M(1.05), ["advanced"] = M(1.05), ["epic"] = M(1.05), ["precious"] = M(1.05),
            ["legendary"] = M(1.05), ["mythical"] = M(1.05), ["ancient"] = M(1.05),
            ["pure"] = M(1.10), ["holy"] = M(1.10),
            // --- AIR (slight move rider only; NO time knob) ---
            ["air"] = M(1.04), ["wind"] = M(1.04), ["vapor"] = M(1.04), ["gas"] = M(1.04),
            // --- physical / structural riders ---
            ["layered"] = M(1.05), ["flexible"] = M(1.05), ["versatile"] = M(1.05), ["memory"] = M(1.05),
            // --- energy / essence ---
            ["blood"] = T(0.95),
            // --- exotic / rule-benders (M / T knobs; amp handled via strongExc) ---
            ["temporal"] = M(1.15),
            ["harmony"] = M(1.12),
            ["dangerous"] = TM(0.85, 1.0),
            // --- Function / Output slot-family time/move knobs ---
            // Power slot (aggressive/volatile goal) → tighter clock:
            ["explosive"] = T(0.90), ["strength"] = T(0.90), ["energy"] = T(0.90), ["power"] = T(0.90),
            ["weapon"] = T(0.90), ["combat"] = T(0.90),
            // Modifier / gentle goals → a little move slack:
            ["buff"] = M(1.05), ["enhancement"] = M(1.05), ["speed"] = M(1.05), ["agility"] = M(1.05),
            ["healing"] = M(1.10), ["regeneration"] = M(1.10),
        };
    }

    // Additive R:<rule> weights (full-strength, one copy). One combined entry per tag.
    private static Dictionary<string, (TileRule Rule, double W)[]> BuildRuleAdd()
    {
        (TileRule, double) R(TileRule rule, double w) => (rule, w);
        return new()
        {
            // FIRE riders
            ["lightning"] = new[] { R(TileRule.Wild, 0.20) },
            ["storm"] = new[] { R(TileRule.Wild, 0.20) },
            ["radiant"] = new[] { R(TileRule.Single, 0.10) },
            ["light"] = new[] { R(TileRule.Single, 0.10) },
            ["chaos"] = new[] { R(TileRule.Wild, 0.35) },
            // EARTH / structural (Immovable)
            ["earth"] = new[] { R(TileRule.Immovable, 0.22) },
            ["stone"] = new[] { R(TileRule.Immovable, 0.22) },
            ["mineral"] = new[] { R(TileRule.Immovable, 0.22) },
            ["sand"] = new[] { R(TileRule.Immovable, 0.12) },
            ["metal"] = new[] { R(TileRule.Immovable, 0.16) },
            ["metallic"] = new[] { R(TileRule.Immovable, 0.16) },
            ["iron"] = new[] { R(TileRule.Immovable, 0.16) },
            ["steel"] = new[] { R(TileRule.Immovable, 0.16) },
            ["bronze"] = new[] { R(TileRule.Immovable, 0.16) },
            ["copper"] = new[] { R(TileRule.Immovable, 0.16) },
            ["tin"] = new[] { R(TileRule.Immovable, 0.16) },
            ["silver"] = new[] { R(TileRule.Immovable, 0.16) },
            ["gold"] = new[] { R(TileRule.Immovable, 0.16) },
            ["alloy"] = new[] { R(TileRule.Immovable, 0.16) },
            ["mithril"] = new[] { R(TileRule.Immovable, 0.18) },
            ["adamantine"] = new[] { R(TileRule.Immovable, 0.18) },
            ["orichalcum"] = new[] { R(TileRule.Immovable, 0.18) },
            ["crystal"] = new[] { R(TileRule.Single, 0.12), R(TileRule.Immovable, 0.08) },
            ["gem"] = new[] { R(TileRule.Single, 0.12), R(TileRule.Immovable, 0.08) },
            // LIFE / GROVE (Spread)
            ["wood"] = new[] { R(TileRule.Spread, 0.24) },
            ["oak"] = new[] { R(TileRule.Spread, 0.24) },
            ["ash"] = new[] { R(TileRule.Spread, 0.24) },
            ["ironwood"] = new[] { R(TileRule.Spread, 0.24) },
            ["ebony"] = new[] { R(TileRule.Spread, 0.24) },
            ["birch"] = new[] { R(TileRule.Spread, 0.24) },
            ["willow"] = new[] { R(TileRule.Spread, 0.24) },
            ["exotic"] = new[] { R(TileRule.Spread, 0.24) },
            ["worldtree"] = new[] { R(TileRule.Spread, 0.34) },
            ["plant"] = new[] { R(TileRule.Spread, 0.20) },
            ["herb"] = new[] { R(TileRule.Spread, 0.20) },
            ["leather"] = new[] { R(TileRule.Spread, 0.20) },
            ["living"] = new[] { R(TileRule.Spread, 0.20) },
            ["monster"] = new[] { R(TileRule.Spread, 0.16), R(TileRule.Wild, 0.08) },
            ["fang"] = new[] { R(TileRule.Spread, 0.16), R(TileRule.Wild, 0.08) },
            ["scales"] = new[] { R(TileRule.Spread, 0.16), R(TileRule.Wild, 0.08) },
            ["bone"] = new[] { R(TileRule.Spread, 0.16), R(TileRule.Wild, 0.08) },
            ["gel"] = new[] { R(TileRule.Spread, 0.16), R(TileRule.Wild, 0.08) },
            ["carapace"] = new[] { R(TileRule.Spread, 0.16), R(TileRule.Wild, 0.08) },
            ["blood"] = new[] { R(TileRule.Spread, 0.12) },
            // SHADOW / UMBRA (Invert)
            ["dark"] = new[] { R(TileRule.Invert, 0.26) },
            ["shadow"] = new[] { R(TileRule.Invert, 0.26) },
            ["spectral"] = new[] { R(TileRule.Invert, 0.26), R(TileRule.Single, 0.12) },
            ["void"] = new[] { R(TileRule.Invert, 0.34) },
            ["poison"] = new[] { R(TileRule.Invert, 0.18), R(TileRule.Spread, 0.06) },
            ["venom"] = new[] { R(TileRule.Invert, 0.18), R(TileRule.Spread, 0.06) },
            ["toxic"] = new[] { R(TileRule.Invert, 0.18), R(TileRule.Spread, 0.06) },
            ["acid"] = new[] { R(TileRule.Invert, 0.18), R(TileRule.Spread, 0.06) },
            ["arcane"] = new[] { R(TileRule.Invert, 0.14), R(TileRule.Wild, 0.08) },
            ["magical"] = new[] { R(TileRule.Invert, 0.14), R(TileRule.Wild, 0.08) },
            ["essence"] = new[] { R(TileRule.Invert, 0.14), R(TileRule.Wild, 0.08) },
            // AIR (Single — the dispersing light tile is the PRIMARY effect)
            ["air"] = new[] { R(TileRule.Single, 0.26) },
            ["wind"] = new[] { R(TileRule.Single, 0.26) },
            ["vapor"] = new[] { R(TileRule.Single, 0.26) },
            ["gas"] = new[] { R(TileRule.Single, 0.26) },
            // physical / structural riders
            ["durable"] = new[] { R(TileRule.Immovable, 0.16) },
            ["hard"] = new[] { R(TileRule.Immovable, 0.16) },
            ["solid"] = new[] { R(TileRule.Immovable, 0.16) },
            ["dense"] = new[] { R(TileRule.Immovable, 0.22) },
            ["heavy"] = new[] { R(TileRule.Immovable, 0.22) },
            ["sharp"] = new[] { R(TileRule.Single, 0.30) },
            ["layered"] = new[] { R(TileRule.Spread, 0.10) },
            ["flexible"] = new[] { R(TileRule.Spread, 0.10) },
            ["versatile"] = new[] { R(TileRule.Spread, 0.10) },
            ["memory"] = new[] { R(TileRule.Spread, 0.10) },
            // energy riders
            ["chaos"] = new[] { R(TileRule.Wild, 0.35) },   // T×0.82 via EngBase; Wild weight here
            // exotic
            ["temporal"] = new[] { R(TileRule.Single, 0.10) },
            ["harmony"] = new[] { R(TileRule.Invert, -0.10), R(TileRule.Wild, -0.10) },
            ["dangerous"] = new[] { R(TileRule.Wild, 0.30) },
            ["elemental"] = new[] { R(TileRule.Spread, 0.06), R(TileRule.Single, 0.06), R(TileRule.Invert, 0.06) },
            // §2.3 slot-family rule leans
            ["armor"] = new[] { R(TileRule.Immovable, 0.06) },
            ["protection"] = new[] { R(TileRule.Immovable, 0.06) },
            ["defense"] = new[] { R(TileRule.Immovable, 0.06) },
            ["resistance"] = new[] { R(TileRule.Immovable, 0.06) },
        };
    }

    // Additive U (undo) knobs.
    private static Dictionary<string, double> BuildUndoAdd() => new()
    {
        ["water"] = 1, ["aqua"] = 1, ["liquid"] = 1, ["solvent"] = 1,
        ["harmony"] = 1,   // §2.3 Utility slot: harmony grants an undo
    };

    // Additive G (grid) knobs.
    private static Dictionary<string, double> BuildGridAdd() => new()
    {
        // EARTH / structural
        ["earth"] = 1, ["stone"] = 1, ["mineral"] = 1,
        ["metal"] = 1, ["metallic"] = 1, ["iron"] = 1, ["steel"] = 1, ["bronze"] = 1,
        ["copper"] = 1, ["tin"] = 1, ["silver"] = 1, ["gold"] = 1, ["alloy"] = 1,
        ["mithril"] = 1, ["adamantine"] = 1, ["orichalcum"] = 1,
        ["crystal"] = 1, ["gem"] = 1, ["strong"] = 1,
        // Quality / Grade
        ["uncommon"] = 1, ["fine"] = 1, ["quality"] = 1, ["refined"] = 1, ["superior"] = 1,
        ["rare"] = 1, ["advanced"] = 1, ["epic"] = 1, ["precious"] = 1,
        ["legendary"] = 2, ["mythical"] = 2, ["ancient"] = 2,
        ["pure"] = 1, ["holy"] = 1,
        ["mundane"] = -1,
    };
}
