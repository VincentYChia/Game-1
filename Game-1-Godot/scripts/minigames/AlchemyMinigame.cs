using Godot;
using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Godot;

/// <summary>
/// ALCHEMY — fresh rebuild (2026-08-16). Each reagent is a glossy GLASS MARBLE with living fluid inside;
/// drag one onto another to MERGE them into one live mixture that keeps reacting (fire builds heat, water
/// boils to steam, earth damps the fire, life chars, shadow corrupts — see MinigameTagEffects.Evolve).
/// Every reaction TRANSLATES into two gauges: POTENCY (a quality multiplier) and VOLATILITY (the scored axis).
/// Each recipe wants a TARGET VOLATILITY (mostly from tags) and RESISTS raw potency (scales with tier). You
/// steer VOLATILITY into the target band while building POTENCY, then drop your marble in the WELL to cast.
/// Live state (composition, heat, boiling, reacting) is read from the marble itself; only IDENTITY (name /
/// tier / rarity / tags) is shown as text. Rendering is pure 2D (no shader). Press F1 for a reaction log.
/// </summary>
// (B-D8) Randomness posture (master plan §0 rule 3): Alchemy is INTENTIONALLY deterministic. Replayability comes from
// ingredient permutations + merge-order choices + the timing skill of holding volatility on the target as it destabilises
// near the band (B-D1) — NOT bounded RNG. The telegraphed-RNG pattern is owned by Refining / Engineering / Enchanting.
public partial class AlchemyMinigame : MinigameOverlay
{
    protected override string Discipline => "alchemy";
    protected override bool FullscreenScene => true;
    protected override bool ShowAmbient => false;
    protected override (Color, Color, Color)? BackdropTint =>
        (new Color(0.11f, 0.09f, 0.10f), new Color(0.05f, 0.04f, 0.05f), new Color(0.5f, 0.32f, 0.42f));

    private static readonly Color Ink = new(0.93f, 0.90f, 0.85f);
    private static readonly Color Sub = new(0.93f, 0.90f, 0.85f, 0.55f);
    private static readonly Color Faint = new(0.93f, 0.90f, 0.85f, 0.30f);
    private static readonly Color Gold = new(0.97f, 0.78f, 0.34f);
    private static readonly Color GoodC = new(0.45f, 0.92f, 0.55f);
    private static readonly Color BadC = new(1.0f, 0.42f, 0.30f);
    private static readonly int Nc = MinigameTagEffects.N;
    private static readonly int[] DrawOrder = { MinigameTagEffects.TERRA, MinigameTagEffects.AQUA, MinigameTagEffects.GROVE, MinigameTagEffects.UMBRA, MinigameTagEffects.HEAT, MinigameTagEffects.AIR };

    private const float FuseOverlap = 0.62f;

    private sealed class Orb
    {
        public string Name = "";
        public List<string> Tags = new();
        public int Tier = 1;
        public double[] E = new double[MinigameTagEffects.N];
        public double Heat, Turb, Reson, Grade, Age, P, V, PAnchor;   // P = potency (quality multiplier), V = volatility (scored axis)
        public bool Raw = true;   // a raw ingredient is INERT — fixed P/V, no reaction; only merged mixtures evolve
        public double ReactTime = MinigameTagEffects.ReactionTime;
        public Dictionary<string, int> Counts = new();                       // modifier-tag counts (stack across merges)
        public MinigameTagEffects.ModProfile Prof = new();                   // base + exceptions, rebuilt each merge
        public readonly double[] State = new double[MinigameTagEffects.StateCount];      // this tick's state magnitudes
        public readonly double[] PrevState = new double[MinigameTagEffects.StateCount];  // last tick's (for log edges)
        public Vector2 Pos, Vel;
        public float Wob;
        public double Mass => E.Sum();
        public float R => Mathf.Clamp(32f + Mathf.Sqrt((float)Mass) * 4.4f, 38f, 104f);
        public float HeatT => (float)Math.Clamp(Heat / MinigameTagEffects.HOT, 0, 1.5);
        public float TurbT => (float)Math.Clamp(Turb / 100.0, 0, 1);
        public bool Reacting => Active || (!Raw && Age < ReactTime);
        public bool Active { get { foreach (var m in State) if (m > 0.06) return true; return false; } }
        public bool Boiling => State[(int)MinigameTagEffects.State.Steam] > 0.05 || HeatT >= 1f;
        public MinigameTagEffects.State Top   // the strongest active state (drives aura colour + log)
        {
            get { var b = MinigameTagEffects.State.None; var bv = 0.06; for (var i = 1; i < State.Length; i++) if (State[i] > bv) { bv = State[i]; b = (MinigameTagEffects.State)i; } return b; }
        }
    }

    private readonly List<Orb> _orbs = new();
    private double _targetV, _resistance; private int _tier = 1;

    private Orb? _drag, _hover, _fuseCand;
    private Vector2 _dragVel;
    private double _timeLeft, _timeLimit, _anim, _playT, _shownQuality, _bestQuality;
    private double _committed = -1, _commitAnim; private Vector2 _castFrom; private Orb? _castOrb;

    // [F1] reaction log + [F7] playtest notes — the shared harness (writes res://playtest_logs/alchemy_playtest.log)
    private MinigameDevLog _dev = null!;

    private enum Phase { Ready, Playing, Casting, Done }
    private Phase _phase = Phase.Ready;
    private Control _scene = null!, _glow = null!, _bg = null!;

    protected override void BuildUi(VBoxContainer host)
    {
        var wrap = new Control { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill, SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        wrap.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        host.AddChild(wrap);

        // clean STATIC apothecary background (covers the base backdrop's animated fog — no noise, no motion)
        _bg = new Control { MouseFilter = Control.MouseFilterEnum.Ignore };
        _bg.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _bg.Draw += DrawBackground;
        wrap.AddChild(_bg);

        _glow = new Control { MouseFilter = Control.MouseFilterEnum.Ignore, Material = new CanvasItemMaterial { BlendMode = CanvasItemMaterial.BlendModeEnum.Add } };
        _glow.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _glow.Draw += DrawGlow;
        wrap.AddChild(_glow);

        _scene = new Control { MouseFilter = Control.MouseFilterEnum.Stop };
        _scene.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _scene.Draw += DrawScene;
        _scene.GuiInput += OnSceneInput;
        wrap.AddChild(_scene);

        // shared F1/F7 dev harness — builds its own notes box into the scene, fed the live context bracket
        _dev = new MinigameDevLog("alchemy");
        _dev.Context = () => $"t={_playT,5:0.0} | {_phase,-7} | {_bestQuality * 100,3:0}%";
        _dev.NoteSubmitted += OnDevNote;
        _dev.BuildNotesPanel(wrap);
    }

    protected override void OnBegin()
    {
        _orbs.Clear();
        _drag = _hover = _fuseCand = _castOrb = null; _anim = _playT = 0; _committed = -1; _commitAnim = 0;
        _shownQuality = _bestQuality = 0; _phase = Phase.Ready;

        var src = Recipe?.Inputs is { Count: > 0 } inp
            ? inp.Select(i => (i.Name, i.Tags, Math.Max(1, i.Qty), Math.Max(1, i.MaterialTier)))
            : new[] { ("Emberdust", new List<string> { "fire", "ember" }, 2, 1), ("Springwater", new List<string> { "water" }, 1, 1),
                      ("Iron Filings", new List<string> { "metal", "sharp" }, 1, 2), ("Dawn Sage", new List<string> { "herb", "radiant" }, 1, 1) };

        var l = GetLayout();
        var units = new List<(string, List<string>, int)>();
        foreach (var (name, tags, qty, tier) in src) for (var q = 0; q < qty; q++) units.Add((name, tags, tier));
        for (var k = 0; k < Math.Min(units.Count, 26); k++)
        {
            var (name, tags, tier) = units[k];
            var e = MinigameTagEffects.Brew(tags, tier, 1);
            var ang = -Mathf.Pi / 2f + Mathf.Tau * k / Math.Max(1, Math.Min(units.Count, 26));
            var rad = Mathf.Min(l.Field.Size.X, l.Field.Size.Y) * 0.32f;
            var counts = new Dictionary<string, int>();
            foreach (var t in tags) counts[t] = counts.GetValueOrDefault(t) + 1;
            var prof = MinigameTagEffects.BuildProfile(counts, tier);
            var p0 = MinigameTagEffects.BasePotency(tier) * prof.Pot;   // tier potency × tag-modifier potency
            _orbs.Add(new Orb
            {
                Name = name, Tags = tags, Tier = tier, E = e, Counts = counts, Prof = prof, Grade = MinigameTagEffects.Grade(tags),
                Raw = true, P = p0, PAnchor = p0, V = Math.Clamp(MinigameTagEffects.ComposeVolatility(e, 0) + prof.Vol, 0, 100),   // INERT: fixed potency + composition volatility
                ReactTime = Math.Clamp(MinigameTagEffects.ReactionTime * prof.Time, 2, 7),
                Wob = Hash(k) * 6.28f, Pos = l.Field.GetCenter() + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * rad,
            });
        }
        // the recipe sets the TARGET VOLATILITY (mostly from tags) + a POTENCY RESISTANCE (scales with tier to
        // balance the greater potency of higher-tier reagents). You steer V to the target while building P.
        // (B-D5) target from OUTPUT tags; a REAL recipe with no output tags gets a NEUTRAL target (no input leakage) —
        // the input-union fallback is only for the null debug sampler (Recipe==null).
        List<string> goalTags =
            Recipe?.OutputTags is { Count: > 0 } ot ? ot                       // real recipe WITH output tags
            : Recipe != null ? new List<string>()                              // real recipe, NO output tags → neutral ~40 V
            : _orbs.SelectMany(o => o.Tags).Distinct().ToList();               // debug sampler → input character
        _tier = Recipe?.Inputs is { Count: > 0 } inp2 ? inp2.Max(i => Math.Max(1, i.MaterialTier)) : 1;
        _targetV = MinigameTagEffects.TargetVolatility(goalTags, _tier);
        _resistance = MinigameTagEffects.PotencyResistance(goalTags, _tier);
        _timeLimit = 60 + 6 * _orbs.Count; _timeLeft = _timeLimit;
        Recompute();
        _dev.BeginSession(BuildLogHeader());
        _scene.QueueRedraw(); _bg.QueueRedraw();
    }

    // quality = closeness-to-target-VOLATILITY (base) × resisted-POTENCY (multiplier)
    private double CommitScore(Orb o) => MinigameTagEffects.Quality(o.V, o.P, _targetV, _resistance);
    private void Recompute()
    {
        foreach (var o in _orbs) o.Reson = CommitScore(o);
        _bestQuality = _orbs.Count > 0 ? _orbs.Max(CommitScore) : 0;
        SetQuality(_bestQuality);
    }

    // ------------------------------------------------------------------ loop
    protected override void OnTick(double delta)
    {
        _anim += delta;
        if (_phase == Phase.Casting) { _commitAnim += delta; if (_commitAnim > 1.0) End(); _scene.QueueRedraw(); _glow.QueueRedraw(); return; }
        if (_phase != Phase.Playing) { _scene.QueueRedraw(); _glow.QueueRedraw(); return; }
        _playT += delta;
        _dragVel *= 0.82f;
        var l = GetLayout();

        foreach (var o in _orbs)
        {
            Array.Copy(o.State, o.PrevState, o.State.Length);
            // raw ingredients are INERT (fixed P/V, static); only merged mixtures react — and only within their window
            if (o.Raw) Array.Clear(o.State, 0, o.State.Length);
            else { MinigameTagEffects.Evolve(o.E, o.PAnchor, o.Prof, o.Age, o.ReactTime, ref o.Heat, ref o.Turb, ref o.P, ref o.V, delta, o.State, _targetV); o.Age += delta; }
            LogEdges(o);
            o.Wob += (float)delta * (1f + o.HeatT * 1.2f);
            if (o == _drag) continue;
            foreach (var q in _orbs) { if (q == o || q == _drag) continue; var to = o.Pos - q.Pos; var d = to.Length(); var min = o.R + q.R + 8; if (d > 0.1 && d < min) o.Vel += to.Normalized() * (min - d) * 3.5f * (float)delta; }
            o.Vel += new Vector2(Mathf.Sin(o.Wob * 0.7f), Mathf.Cos(o.Wob * 0.5f)) * 4f * (float)delta;
            o.Vel = o.Vel.LimitLength(55f) * 0.88f;
            o.Pos = ClampField(o.Pos + o.Vel * (float)delta, o.R, l);
        }
        if (_hover != null && !_orbs.Contains(_hover)) _hover = null;
        _fuseCand = _drag != null ? Nearest(_drag) : null;
        Recompute();
        _shownQuality = Mathf.Lerp((float)_shownQuality, (float)_bestQuality, (float)Math.Clamp(delta * 6, 0, 1));
        SetQuality(_shownQuality);

        if (_orbs.Count == 0 && _drag == null) { _phase = Phase.Done; FailCraft(); return; }
        _timeLeft -= delta;
        if (_timeLeft <= 0) { var best = _orbs.Where(o => o != _drag).OrderByDescending(CommitScore).FirstOrDefault(); if (best != null) BeginCast(best); else { _phase = Phase.Done; FailCraft(); return; } }
        _scene.QueueRedraw(); _glow.QueueRedraw(); _bg.QueueRedraw();
    }

    private Orb? Nearest(Orb drag)
    { Orb? best = null; var bd = float.MaxValue; foreach (var o in _orbs) { if (o == drag) continue; var d = drag.Pos.DistanceTo(o.Pos); if (d < (drag.R + o.R) * (FuseOverlap + 0.35f) && d < bd) { bd = d; best = o; } } return best; }

    private void Merge(Orb a, Orb b)
    {
        var e = new double[Nc]; for (var i = 0; i < Nc; i++) e[i] = a.E[i] + b.E[i];
        var ma = a.Mass; var mb = b.Mass; var mm = Math.Max(1e-4, ma + mb);
        var heat = (a.Heat * ma + b.Heat * mb) / mm;
        var blendP = (a.P * ma + b.P * mb) / mm;
        var tags = a.Tags.Concat(b.Tags).Distinct().Take(6).ToList();
        var tier = Math.Max(a.Tier, b.Tier);
        var counts = new Dictionary<string, int>(a.Counts);
        foreach (var kv in b.Counts) counts[kv.Key] = counts.GetValueOrDefault(kv.Key) + kv.Value;   // STACK modifiers across the merge
        var prof = MinigameTagEffects.BuildProfile(counts, tier);
        // INSTANT interaction at the moment of contact: water quenches fire (the over-time steam then plays out in Evolve)
        if (e[MinigameTagEffects.AQUA] > 0.5 && e[MinigameTagEffects.HEAT] > 0.5) heat *= 0.5;
        var child = new Orb   // a fresh mixture: Raw=false, Age=0 restarts the reaction window; then it settles and holds
        {
            Raw = false, Age = 0, E = e, Heat = heat, Turb = Math.Max(a.Turb, b.Turb) * 0.5 + 8, Pos = (a.Pos + b.Pos) / 2f, Wob = (float)_anim,
            P = blendP, PAnchor = blendP, V = Math.Clamp(MinigameTagEffects.ComposeVolatility(e, heat) + prof.Vol, 0, 100),   // V jumps to the new composition (instant), then eases as heat builds
            Tier = tier, Grade = Math.Max(a.Grade, b.Grade), Tags = tags, Counts = counts, Prof = prof, ReactTime = Math.Clamp(MinigameTagEffects.ReactionTime * prof.Time, 2, 7), Name = MixName(e),
        };
        _orbs.Remove(a); _orbs.Remove(b); _orbs.Add(child); _drag = null; _fuseCand = null;
        _dev.Log($"MERGE -> {MinigameTagEffects.ChannelName(MinigameTagEffects.Dominant(e))} heat{heat:0} V{child.V:0} P{blendP:0} rx{prof.Rx:0.00} t{child.ReactTime:0.0}");
        Recompute(); _scene.QueueRedraw();
    }

    private static string MixName(double[] e) => MinigameTagEffects.Dominant(e) switch
    {
        MinigameTagEffects.HEAT => "Fervent Draught", MinigameTagEffects.AQUA => "Cool Tincture",
        MinigameTagEffects.TERRA => "Mineral Brew", MinigameTagEffects.GROVE => "Verdant Elixir",
        MinigameTagEffects.UMBRA => "Umbral Philtre", _ => "Airy Essence",
    };

    private void BeginCast(Orb o)
    {
        if (_phase != Phase.Playing) return;
        _committed = CommitScore(o); _castFrom = o.Pos; _castOrb = o; _drag = null; _fuseCand = null;
        _orbs.Clear(); _orbs.Add(o); _phase = Phase.Casting; _commitAnim = 0;
        _dev.Log($"CAST {MinigameTagEffects.RarityFromPerf(_committed).Name} {_committed * 100:0}%");
    }
    private void End()
    {
        _phase = Phase.Done;
        if (_committed < 0.12) { _dev.Log($"RESULT: FAIL (committed {_committed * 100:0}%)"); FailCraft(); return; }
        var perf = Math.Pow(_committed, 1.02);
        _dev.Log($"RESULT: {MinigameTagEffects.RarityFromPerf(_committed).Name} — perf {perf * 100:0}%");
        Finish(perf);
    }

    // ------------------------------------------------------------------ input
    public override void _Input(InputEvent @event)
    {
        if (!Running) return;
        if (@event is not InputEventKey { Pressed: true, Echo: false } k) return;
        // claim F1/F7 here (the earliest input stage) so they never reach the world's global debug handler
        if (_dev.HandleKey(k.PhysicalKeycode)) { _scene.QueueRedraw(); GetViewport().SetInputAsHandled(); }
    }

    protected override void OnInput(InputEvent @event)
    {
        if (@event is not InputEventKey { Pressed: true, Echo: false } k) return;
        if (k.PhysicalKeycode == Key.Space && _phase == Phase.Ready) { _phase = Phase.Playing; GetViewport().SetInputAsHandled(); }
        // [Enter] casts the best mixture — a reliable path that doesn't depend on dragging onto the well
        else if (k.PhysicalKeycode is Key.Enter or Key.KpEnter && _phase == Phase.Playing && !_dev.NotesEditHasFocus)
        { var best = BestOrb(); if (best != null) { BeginCast(best); GetViewport().SetInputAsHandled(); } }
    }
    private Orb? BestOrb() { Orb? b = null; var bq = -1.0; foreach (var o in _orbs) { if (o == _drag) continue; var q = CommitScore(o); if (q > bq) { bq = q; b = o; } } return b; }
    private void OnSceneInput(InputEvent @event)
    {
        switch (@event)
        {
            case InputEventMouseButton { Pressed: true, ButtonIndex: MouseButton.Left } mb:
                if (_phase == Phase.Ready) { _phase = Phase.Playing; return; }
                if (_phase == Phase.Playing)
                {
                    // clicking the WELL casts the best mixture directly (no drag needed)
                    if (mb.Position.DistanceTo(GetLayout().Well) < GetLayout().WellR + 14f) { var best = BestOrb(); if (best != null) BeginCast(best); return; }
                    _drag = Pick(mb.Position);
                }
                return;
            case InputEventMouseButton { Pressed: false, ButtonIndex: MouseButton.Left }:
                if (_drag != null && _phase == Phase.Playing)
                {
                    var l = GetLayout();
                    if (_drag.Pos.DistanceTo(l.Well) < l.WellR + _drag.R * 0.55f) { BeginCast(_drag); return; }
                    var cand = Nearest(_drag); if (cand != null) { Merge(_drag, cand); return; }
                }
                _drag = null; _fuseCand = null; return;
            case InputEventMouseMotion mm:
                if (_drag != null)
                { _dragVel = mm.Relative / (float)Math.Max(1e-3, GetProcessDeltaTime()); _drag.Pos = ClampField(mm.Position, _drag.R, GetLayout()); _drag.Vel = Vector2.Zero; _fuseCand = Nearest(_drag); }
                else _hover = _phase == Phase.Playing ? Pick(mm.Position) : null;
                _scene.QueueRedraw(); return;
        }
    }
    private Orb? Pick(Vector2 p) { Orb? best = null; var bd = float.MaxValue; foreach (var o in _orbs) { var d = o.Pos.DistanceTo(p); if (d < o.R + 8 && d < bd) { bd = d; best = o; } } return best; }

    // ------------------------------------------------------------------ layout
    private struct Lay { public float W, H; public Rect2 Field; public Rect2 PotBar, VolBar; public Vector2 Well; public float WellR; public Rect2 Log; }
    private Lay GetLayout()
    {
        var s = _scene.Size; var W = Mathf.Max(s.X, 800f); var H = Mathf.Max(s.Y, 500f);
        var logW = _dev.ShowLog ? 250f : 0f;
        var barY = H * 0.24f; var barH = H * 0.50f; var barW = 22f;
        return new Lay
        {
            W = W, H = H,
            Field = new Rect2(W * 0.11f, H * 0.10f, W * 0.84f - logW, H * 0.80f),
            PotBar = new Rect2(W * 0.022f, barY, barW, barH),
            VolBar = new Rect2(W * 0.022f + barW + 30f, barY, barW, barH),
            Well = new Vector2(W * 0.90f - logW, H * 0.86f), WellR = Mathf.Min(W, H) * 0.07f,
            Log = new Rect2(W - logW + 8f, H * 0.14f, logW - 16f, H * 0.78f),
        };
    }
    private Vector2 ClampField(Vector2 p, float r, Lay l)
    { var c = l.Field; var m = r + 6; return new Vector2(Mathf.Clamp(p.X, c.Position.X + m, c.Position.X + c.Size.X - m), Mathf.Clamp(p.Y, c.Position.Y + m, c.Position.Y + c.Size.Y - m)); }

    // ================================================================== DRAW
    private void DrawScene()
    {
        var font = _scene.GetThemeDefaultFont(); var l = GetLayout();
        DrawSliders(l, font);
        DrawWell(l, font);
        if (_drag != null && _fuseCand != null) DrawGhost(l);
        if (_phase != Phase.Casting)
            // draw settled reagents first, then reacting ones on top so the live chemistry reads over the calm tokens
            foreach (var o in _orbs.OrderBy(o => o.Reacting ? 1 : 0)) DrawMarble(o, o.Pos, DrawR(o));
        if (_phase == Phase.Casting && _castOrb != null) { var p = _castFrom.Lerp(l.Well, Ease((float)Math.Clamp(_commitAnim, 0, 1))); DrawMarble(_castOrb, p, _castOrb.R * (1 - 0.3f * (float)_commitAnim)); }
        // identity: a small name under each orb, the live state readout under reacting ones, + a full card on hover
        foreach (var o in _orbs) if (_phase != Phase.Casting) { DrawName(o, font); DrawStateLabels(o, font); }
        if (_hover != null && _drag == null) DrawCard(_hover, l, font);
        DrawHud(l, font);
        if (_dev.ShowLog) DrawLog(l, font);
        if (_phase == Phase.Ready) DrawReady(l, font);
    }

    // a REACTING mixture swells with a heartbeat so the eye is drawn to where the chemistry is happening
    private float DrawR(Orb o)
    { if (!o.Reacting) return o.R; var pulse = 0.5f + 0.5f * Mathf.Sin(o.Wob * 6f); return o.R * (1.14f + 0.08f * pulse); }

    // clean, STATIC, higher-fidelity apothecary backdrop (smooth gradient + soft lamp + shelves + bench; no noise)
    private void DrawBackground()
    {
        var s = _bg.Size; var W = Mathf.Max(s.X, 800f); var H = Mathf.Max(s.Y, 500f);
        var top = new Color(0.15f, 0.11f, 0.10f); var bot = new Color(0.055f, 0.04f, 0.05f);
        const int bands = 64;
        for (var i = 0; i < bands; i++) { var t = i / (float)bands; var st = t * t * (3 - 2 * t); _bg.DrawRect(new Rect2(0, H * t, W, H / bands + 1.5f), top.Lerp(bot, st)); }
        // soft warm lamp light (static, upper-left)
        var lamp = new Vector2(W * 0.2f, H * 0.22f);
        for (var i = 9; i >= 1; i--) { var t = i / 9f; _bg.DrawCircle(lamp, W * 0.36f * t, new Color(1f, 0.7f, 0.42f, 0.045f * (1 - t))); }
        // two shelves with bottle silhouettes (clean, low-contrast, static)
        foreach (var sy in new[] { 0.20f, 0.44f })
        {
            var y = H * sy;
            _bg.DrawRect(new Rect2(0, y, W, 5), new Color(0.22f, 0.15f, 0.10f));
            _bg.DrawRect(new Rect2(0, y + 5, W, 3), new Color(0, 0, 0, 0.25f));
            for (var b = 0; b < 10; b++)
            {
                var bx = W * (0.05f + b * 0.096f) + (sy > 0.3f ? W * 0.03f : 0f); var bw = W * (0.018f + Hash(b + (int)(sy * 30)) * 0.014f); var bh = H * (0.06f + Hash(b * 3) * 0.05f);
                _bg.DrawRect(new Rect2(bx, y - bh, bw, bh), new Color(0.10f, 0.08f, 0.09f, 0.75f));
                var tint = MinigameTagEffects.FamilyColor(b % 6);
                _bg.DrawRect(new Rect2(bx + 1, y - bh + bh * 0.35f, bw - 2, bh * 0.6f), new Color(tint.R, tint.G, tint.B, 0.14f));
            }
        }
        // bench slab
        _bg.DrawRect(new Rect2(0, H * 0.73f, W, H * 0.27f), new Color(0.17f, 0.115f, 0.08f));
        _bg.DrawRect(new Rect2(0, H * 0.73f, W, 4), new Color(0.34f, 0.24f, 0.16f));
        _bg.DrawRect(new Rect2(0, H * 0.73f + 4, W, 3), new Color(0, 0, 0, 0.25f));
        for (var i = 0; i < 5; i++) _bg.DrawLine(new Vector2(W * (0.1f + i * 0.2f), H * 0.73f + 8), new Vector2(W * (0.1f + i * 0.2f) + 8, H), new Color(0, 0, 0, 0.10f), 1.5f);
        // gentle vignette
        for (var i = 6; i >= 1; i--) { var t = i / 6f; _bg.DrawRect(new Rect2(0, 0, W, H * 0.04f * t), new Color(0, 0, 0, 0.05f)); _bg.DrawRect(new Rect2(0, H * (1 - 0.05f * t), W, H * 0.05f * t), new Color(0, 0, 0, 0.05f)); }
    }

    // ---- THE GLASS MARBLE (the star) ----------------------------------------
    private void DrawMarble(Orb b, Vector2 c, float R)
    {
        var col = MinigameTagEffects.DisplayColor(b.Tags, b.E);
        // DYNAMIC HUE — a reacting brew visibly TAKES ON its dominant reaction's colour (decay→green, blaze→orange)
        var top = b.Top;
        if (top != MinigameTagEffects.State.None) col = col.Lerp(MinigameTagEffects.StateColor(top), Mathf.Clamp((float)b.State[(int)top] * 0.55f, 0, 0.55f));
        var anim = b.Wob; var heat = b.HeatT;
        c += new Vector2(Mathf.Sin(anim * 22f), Mathf.Cos(anim * 18f)) * b.TurbT * 3.5f;   // turbulence shakes the marble

        // ground shadow
        _scene.DrawColoredPolygon(Ellipse(new Vector2(c.X, c.Y + R * 1.02f), R * 0.85f, R * 0.2f, 20), new Color(0, 0, 0, 0.22f));

        // spherical body — a SMOOTH radial gradient (dense concentric discs, light shifted upper-left = a lit ball)
        CraftColor.RadialGrad(_scene, c, R, new Vector2(-R * 0.16f, -R * 0.20f), Darken(col, 0.55f), Lighten(col, 0.30f), 16);

        // living fluid inside (clipped roughly within 0.8R) — tinted toward the reagent's own tag colour so
        // two same-channel reagents (e.g. lightning Storm Heart vs fire Phoenix Ash) read visibly different
        DrawInterior(c, R * 0.8f, b, anim, col);

        // crystalline FACETS — count scales with TIER (higher tier = more ornate cut), hue from the tags
        var facets = 3 + b.Tier * 3; var accent = Lighten(col, 0.3f);
        for (var i = 0; i < facets; i++)
        {
            var fa = anim * 0.15f + Mathf.Tau * i / facets;
            _scene.DrawLine(c + new Vector2(Mathf.Cos(fa), Mathf.Sin(fa)) * R * 0.6f, c + new Vector2(Mathf.Cos(fa), Mathf.Sin(fa)) * R * 0.92f, new Color(accent.R, accent.G, accent.B, 0.16f), 1.4f);
        }
        if (b.Tier >= 3) _scene.DrawArc(c, R * 0.7f, 0, Mathf.Tau, 40, new Color(accent.R, accent.G, accent.B, 0.28f), 1.5f);
        if (b.Tier >= 4) _scene.DrawArc(c, R * 0.5f, 0, Mathf.Tau, 32, new Color(accent.R, accent.G, accent.B, 0.22f), 1.5f);

        // hot core — warms + whitens with heat; bubbles when boiling
        if (heat > 0.05f)
        {
            var hot = new Color(1f, 0.55f, 0.2f).Lerp(new Color(1f, 0.96f, 0.75f), Mathf.Clamp(heat - 1f, 0, 0.5f) * 2f);
            for (var i = 0; i < 10; i++) { var t = i / 10f; _scene.DrawCircle(c + new Vector2(0, R * 0.1f), R * 0.6f * (1f - t), new Color(hot.R, hot.G, hot.B, heat * 0.16f * (1f - t))); }
        }
        if (b.Boiling)
        {
            for (var i = 0; i < 9; i++)
            { var ph = Mathf.PosMod(anim * 1.3f + Hash(i) * 3.1f, 1f); var bx = c.X + (Hash(i * 2) - 0.5f) * R * 1.0f; var by = c.Y + R * 0.55f - ph * R * 1.25f; if ((bx - c.X) * (bx - c.X) + (by - c.Y) * (by - c.Y) < R * R * 0.7f) _scene.DrawCircle(new Vector2(bx, by), (1.3f + ph * 2.2f), new Color(1f, 1f, 0.95f, (1 - ph) * 0.6f)); }
            // rising STEAM wisps above the marble — the visible over-time water+fire gradient
            for (var i = 0; i < 4; i++)
            { var ph = Mathf.PosMod(anim * 0.7f + i * 0.25f, 1f); var sx = c.X + Mathf.Sin(anim * 2f + i * 1.7f) * R * 0.3f; var sy = c.Y - R - ph * R * 1.25f; _scene.DrawCircle(new Vector2(sx, sy), 2f + ph * 4.5f, new Color(0.9f, 0.93f, 0.96f, (1 - ph) * 0.22f)); }
        }

        // GLASS FINISH — this is what sells the marble
        _scene.DrawColoredPolygon(Ellipse(c + new Vector2(-R * 0.32f, -R * 0.36f), R * 0.30f, R * 0.19f, 18), new Color(1, 1, 1, 0.5f)); // soft specular
        _scene.DrawCircle(c + new Vector2(-R * 0.4f, -R * 0.42f), R * 0.075f, new Color(1, 1, 1, 0.85f));                                 // sharp glint
        _scene.DrawArc(c, R * 0.93f, Mathf.Pi * 0.12f, Mathf.Pi * 0.55f, 22, new Color(1, 1, 1, 0.22f), 3f);                              // rim light
        _scene.DrawArc(c, R, 0, Mathf.Tau, 44, new Color(Darken(col, 0.25f).R, Darken(col, 0.25f).G, Darken(col, 0.25f).B, 0.8f), 2f);   // glass edge

        // the NAMED interaction states (resonance cue lives here now — single source, no duplicate ring)
        DrawStates(b, c, R, anim);
    }

    // Each of the 17 states renders as a DISTINCT big signature — form + colour + screen-region — so several can
    // fire at once and still read (rising vapours above, flames off the top, sediment/drips low, crystals on the rim,
    // vines radiating, cores glowing). No numbers anywhere: the brew is read purely by what it is visibly doing.
    private void DrawStates(Orb b, Vector2 c, float R, float anim)
    {
        for (var i = 1; i < b.State.Length; i++)
        {
            var m = (float)b.State[i]; if (m < 0.06f) continue;
            var st = (MinigameTagEffects.State)i; var col = MinigameTagEffects.StateColor(st);
            // dispatch each named state to a SHARED StateVisual primitive (extracted; every discipline uses these)
            switch (st)
            {
                case MinigameTagEffects.State.Steam: StateVisual.Plume(_scene, c, R, col, m, anim, 1.0f, 1.0f, false); break;
                case MinigameTagEffects.State.Smoke: StateVisual.Plume(_scene, c, R, col, m, anim, 0.6f, 0.7f, true); break;
                case MinigameTagEffects.State.Spore: StateVisual.Spore(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Mist: StateVisual.Mist(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Dust: StateVisual.Dust(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Blaze: StateVisual.Flame(_scene, c, R, col, m, anim, 1.0f, false); break;
                case MinigameTagEffects.State.Brimstone: StateVisual.Flame(_scene, c, R, col, m, anim, 0.85f, true); break;
                case MinigameTagEffects.State.Molten: StateVisual.Molten(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Scorch: StateVisual.Scorch(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Quench: StateVisual.RippleOut(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Silt: StateVisual.Sediment(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Bloom: StateVisual.Vines(_scene, c, R, col, m, anim, false, true); break;
                case MinigameTagEffects.State.Root: StateVisual.Vines(_scene, c, R, col, m, anim, true, false); break;
                case MinigameTagEffects.State.Decay: StateVisual.Rot(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Crystallize: StateVisual.Crystals(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Brine: StateVisual.Swirl(_scene, c, R, col, m, anim); break;
                case MinigameTagEffects.State.Temper: StateVisual.CoreGlow(_scene, c, R, col, m, anim); break;
            }
        }
        // a breathing halo in the dominant state's colour (reacting) or a faint steady ring (settled/inert)
        var top = b.Top;
        if (top != MinigameTagEffects.State.None)
        {
            var mag = (float)b.State[(int)top]; var ac = MinigameTagEffects.StateColor(top); var pulse = 0.5f + 0.5f * Mathf.Sin(anim * 7f);
            _scene.DrawArc(c, R * (1.06f + pulse * 0.12f * mag), 0, Mathf.Tau, 48, new Color(ac.R, ac.G, ac.B, (0.18f + 0.30f * pulse) * mag), 3.5f);
        }
        else _scene.DrawArc(c, R * 1.04f, 0, Mathf.Tau, 44, new Color(1, 1, 1, 0.05f), 1.5f);
        // RESONANCE — a soft golden harmonic bloom + orbiting motes when the brew settles into a genuinely good
        // state. This is the only success cue (qualitative, no number); the real quality lands at the cast ceremony.
        if (!b.Raw && b.Reson > 0.7)
        {
            var g = ((float)b.Reson - 0.7f) / 0.3f; var pulse = 0.6f + 0.4f * Mathf.Sin(anim * 3f);
            for (var i = 3; i >= 1; i--) { var t = i / 3f; _scene.DrawArc(c, R * (1.12f + t * 0.32f), 0, Mathf.Tau, 48, new Color(1f, 0.86f, 0.45f, 0.4f * g * pulse * (1 - t)), 2.5f); }
            for (var i = 0; i < 6; i++) { var a = anim * 1.4f + i * Mathf.Tau / 6f; _scene.DrawCircle(c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * R * (1.22f + 0.08f * pulse), 2f + 1.6f * g, new Color(1f, 0.9f, 0.55f, 0.7f * g)); }
        }
    }

    // The per-state signatures (plume / flame / molten / ripple / crystals / vines / …) now live in the shared
    // StateVisual toolkit (StateVisual.cs) so every crafting minigame draws from one set. DrawStates dispatches the
    // 17 named states to 15 distinct primitives (Steam/Smoke→Plume, Blaze/Brimstone→Flame, Bloom/Root→Vines share).

    private void DrawInterior(Vector2 c, float rr, Orb b, float anim, Color accent)
    {
        var mass = b.Mass; if (mass <= 1e-4) return;
        foreach (var ch in DrawOrder)
        {
            var p = (float)(b.E[ch] / mass); if (p < 0.14f) continue;
            var col = MinigameTagEffects.FamilyColor(ch).Lerp(accent, 0.45f);   // lean each motif toward the tag colour
            switch (ch)
            {
                case MinigameTagEffects.TERRA:   // settled mound + facets at the bottom
                    _scene.DrawColoredPolygon(Ellipse(new Vector2(c.X, c.Y + rr * 0.45f), rr * 0.85f, rr * 0.5f * p + rr * 0.2f, 18), new Color(col.R * 0.7f, col.G * 0.6f, col.B * 0.5f, 0.6f));
                    for (var k = 0; k < 3; k++) { var x = c.X + (k - 1) * rr * 0.4f; var h = rr * (0.25f + p * 0.35f); _scene.DrawColoredPolygon(new[] { new Vector2(x - rr * 0.12f, c.Y + rr * 0.55f), new Vector2(x, c.Y + rr * 0.55f - h), new Vector2(x + rr * 0.12f, c.Y + rr * 0.55f) }, Brighten(col, 0.15f)); }
                    break;
                case MinigameTagEffects.AQUA:    // undulating translucent bands
                    for (var k = 0; k < 3; k++) { var y = c.Y + (k - 1) * rr * 0.4f + Mathf.Sin(anim * 2f + k) * rr * 0.08f; _scene.DrawColoredPolygon(Ellipse(new Vector2(c.X, y), rr * 0.9f, rr * 0.14f, 16), new Color(col.R, col.G, col.B, 0.28f + p * 0.25f)); }
                    break;
                case MinigameTagEffects.GROVE:   // curling veins from the centre
                    for (var v = 0; v < 3; v++) { var a0 = anim * 0.5f + v * 2.1f; var prev = c; for (var t = 1; t <= 6; t++) { var tt = t / 6f; var pt = c + new Vector2(Mathf.Cos(a0 + tt * 3f), Mathf.Sin(a0 + tt * 3f)) * rr * tt * (0.6f + p * 0.4f); _scene.DrawLine(prev, pt, new Color(col.R, col.G, col.B, 0.5f), 2.5f - tt); prev = pt; } _scene.DrawCircle(prev, rr * 0.08f, Brighten(col, 0.1f)); }
                    break;
                case MinigameTagEffects.UMBRA:   // dark inward spiral + darkening
                    _scene.DrawCircle(c, rr * (0.5f + p * 0.4f), new Color(0.06f, 0.02f, 0.09f, 0.35f + p * 0.3f));
                    { var prev = c; for (var t = 1; t <= 20; t++) { var tt = t / 20f; var a = anim * 1.5f + tt * 10f; var pt = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * rr * (1 - tt) * 0.85f; _scene.DrawLine(prev, pt, new Color(col.R, col.G, col.B, (1 - tt) * 0.5f), 2f); prev = pt; } }
                    break;
                case MinigameTagEffects.HEAT:    // rising warm plume + flicker
                    for (var k = 0; k < 3; k++) { var bx = c.X + (Hash(k + (int)b.Wob) - 0.5f) * rr * 0.7f; var h = rr * (0.7f + p * 0.7f) * (0.8f + 0.3f * Mathf.Sin(anim * 8f + k)); var w = rr * 0.22f; _scene.DrawColoredPolygon(new[] { new Vector2(bx - w, c.Y + rr * 0.35f), new Vector2(bx, c.Y + rr * 0.35f - h), new Vector2(bx + w, c.Y + rr * 0.35f) }, new Color(1f, 0.5f, 0.15f, 0.5f)); _scene.DrawColoredPolygon(new[] { new Vector2(bx - w * 0.5f, c.Y + rr * 0.35f), new Vector2(bx, c.Y + rr * 0.35f - h * 0.7f), new Vector2(bx + w * 0.5f, c.Y + rr * 0.35f) }, new Color(1f, 0.85f, 0.35f, 0.7f)); }
                    break;
                default:                          // AIR — pale drifting wisps
                    for (var k = 0; k < 3; k++) { var prev = Vector2.Zero; var has = false; for (var t = 0; t <= 10; t++) { var tt = t / 10f; var a = anim * (1f + k * 0.3f) + tt * 3f; var pt = c + new Vector2(Mathf.Cos(a) * rr * 0.5f, -tt * rr * 0.9f + k * rr * 0.2f); if (has) _scene.DrawLine(prev, pt, new Color(col.R, col.G, col.B, 0.25f), 1.5f); prev = pt; has = true; } }
                    break;
            }
        }
    }

    private void DrawGhost(Lay l)
    {
        if (_drag == null || _fuseCand == null) return;
        var e = new double[Nc]; for (var i = 0; i < Nc; i++) e[i] = _drag.E[i] + _fuseCand.E[i];
        var mid = (_drag.Pos + _fuseCand.Pos) / 2f;
        // preview: mass-weighted merge of VOLATILITY — green if the blend lands nearer the target than either parent
        var ma = _drag.Mass; var mb = _fuseCand.Mass; var mv = (_drag.V * ma + _fuseCand.V * mb) / Math.Max(1e-4, ma + mb);
        var closer = Math.Abs(mv - _targetV) < Math.Min(Math.Abs(_drag.V - _targetV), Math.Abs(_fuseCand.V - _targetV)) + 0.5;
        var lc = closer ? new Color(GoodC.R, GoodC.G, GoodC.B, 0.55f) : new Color(Gold.R, Gold.G, Gold.B, 0.4f);
        _scene.DrawLine(_drag.Pos, _fuseCand.Pos, lc, 2.5f);
        var ghost = new Orb { E = e, Tags = _drag.Tags.Concat(_fuseCand.Tags).Distinct().ToList(), Wob = (float)_anim };
        var gr = ghost.R; var gc = MinigameTagEffects.DisplayColor(ghost.Tags, e);
        _scene.DrawCircle(mid, gr, new Color(gc.R, gc.G, gc.B, 0.28f));
        _scene.DrawArc(mid, gr, 0, Mathf.Tau, 40, new Color(lc.R, lc.G, lc.B, 0.7f), 1.5f);
    }

    // ---- POTENCY + VOLATILITY sliders — VISUAL bars only (no digits): fill height reads the value, the volatility
    // bar shows the recipe's target band + marker so you can steer V into it. Colour = how close V is to target.
    private void DrawSliders(Lay l, Font font)
    {
        var best = BestOrb();
        var pot = best?.P ?? 0.0; var vol = best?.V ?? 0.0;
        var acting = best != null && best.Active;
        var near = (float)Math.Exp(-0.5 * Math.Pow((vol - _targetV) / 18.0, 2));
        var volCol = BadC.Lerp(GoodC, near);
        DrawGauge(l.VolBar, font, "VOL", (float)(vol / 100.0), volCol, acting, (float)(_targetV / 100.0), 18f / 100f);
        DrawGauge(l.PotBar, font, "POT", (float)(pot / 150.0), Gold, acting, -1f, 0f);
    }

    // one vertical slider: frame, sweet-band (volatility only), bottom-up fill, moving surface line, target marker
    private void DrawGauge(Rect2 q, Font font, string label, float fill, Color fillCol, bool acting, float targetFrac, float bandFrac)
    {
        CraftRoundRect(new Rect2(q.Position.X - 3, q.Position.Y - 3, q.Size.X + 6, q.Size.Y + 6), new Color(0.05f, 0.05f, 0.07f, 0.9f), new Color(0.35f, 0.32f, 0.30f, 0.6f));
        if (targetFrac >= 0 && bandFrac > 0)   // the sweet band you want VOLATILITY to sit inside
        {
            var y0 = q.Position.Y + q.Size.Y * (1 - Mathf.Clamp(targetFrac + bandFrac, 0, 1));
            var y1 = q.Position.Y + q.Size.Y * (1 - Mathf.Clamp(targetFrac - bandFrac, 0, 1));
            _scene.DrawRect(new Rect2(q.Position.X, y0, q.Size.X, y1 - y0), new Color(GoodC.R, GoodC.G, GoodC.B, 0.15f));
        }
        var fy = q.Position.Y + q.Size.Y * (1 - Mathf.Clamp(fill, 0, 1));
        var aGlow = acting ? 0.12f + 0.13f * Mathf.Sin((float)_anim * 7f) : 0f;   // fill pulses while reacting
        _scene.DrawRect(new Rect2(q.Position.X, fy, q.Size.X, q.Position.Y + q.Size.Y - fy), new Color(fillCol.R, fillCol.G, fillCol.B, 0.72f + aGlow));
        _scene.DrawLine(new Vector2(q.Position.X - 2, fy), new Vector2(q.Position.X + q.Size.X + 2, fy), Lighten(fillCol, 0.3f), 2f);
        if (targetFrac >= 0)   // target marker + arrow (volatility)
        {
            var ty = q.Position.Y + q.Size.Y * (1 - Mathf.Clamp(targetFrac, 0, 1));
            _scene.DrawLine(new Vector2(q.Position.X - 5, ty), new Vector2(q.Position.X + q.Size.X + 5, ty), GoodC, 2.5f);
            _scene.DrawColoredPolygon(new[] { new Vector2(q.Position.X - 5, ty), new Vector2(q.Position.X - 12, ty - 4), new Vector2(q.Position.X - 12, ty + 4) }, GoodC);
        }
        _scene.DrawString(font, new Vector2(q.Position.X - 5, q.Position.Y - 10), label, HorizontalAlignment.Left, 80, 11, Sub);
        if (acting) { var pr = 3f + 2f * Mathf.Abs(Mathf.Sin((float)_anim * 6f)); _scene.DrawCircle(new Vector2(q.Position.X + q.Size.X / 2f, q.Position.Y - 16), pr, new Color(1f, 0.9f, 0.5f, 0.9f)); }
    }

    private void DrawWell(Lay l, Font font)
    {
        var w = l.Well; var R = l.WellR;
        var best = BestOrb(); var bq = best != null ? CommitScore(best) : 0;
        var armed = _drag != null || best != null;
        var (_, rc) = MinigameTagEffects.RarityFromPerf(bq);
        var pulse = 0.5f + 0.5f * Mathf.Sin((float)_anim * 3f);
        if (armed) for (var i = 5; i >= 1; i--) _scene.DrawCircle(w, R * (i / 5f) * (1f + pulse * 0.05f), new Color(rc.R, rc.G, rc.B, 0.05f + 0.04f * pulse));
        _scene.DrawArc(w, R, 0, Mathf.Tau, 40, new Color(0.6f, 0.5f, 0.3f, armed ? 0.9f : 0.5f), 3f);
        _scene.DrawCircle(w, R * 0.85f, new Color(0.04f, 0.03f, 0.05f, 0.6f));
        if (armed) { var cy = w.Y - R * 0.1f + pulse * 3f; _scene.DrawColoredPolygon(new[] { new Vector2(w.X - 11, cy - 6), new Vector2(w.X + 11, cy - 6), new Vector2(w.X, cy + 7) }, new Color(rc.R, rc.G, rc.B, 0.85f)); }
        var label = _drag != null ? "DROP TO CAST" : best != null ? "click / [Enter] to cast" : "the well";
        _scene.DrawString(font, new Vector2(w.X - 100, w.Y + R + 16), label, HorizontalAlignment.Center, 200, 12, armed ? rc : Sub);
    }

    private void DrawName(Orb o, Font font)
    {
        var (_, rc) = MinigameTagEffects.Rarity(o.Tier, o.Grade);
        _scene.DrawString(font, new Vector2(o.Pos.X - 70, o.Pos.Y + o.R + 14), o.Name, HorizontalAlignment.Center, 140, 12, new Color(rc.R, rc.G, rc.B, 0.9f));
    }

    // active states, strongest first (a mixture's live "what it's doing"); empty for a raw/inert reagent
    private List<(int idx, double mag)> ActiveStatesOrdered(Orb o)
    {
        var act = new List<(int idx, double mag)>();
        if (o.Raw) return act;
        for (var i = 1; i < o.State.Length; i++) if (o.State[i] > 0.08) act.Add((i, o.State[i]));
        act.Sort((a, b) => b.mag.CompareTo(a.mag));
        return act;
    }

    // the live ELEMENT-STATE readout under a reacting marble (so the player LEARNS the states): named, ordered
    // strongest-first; each grows/shrinks to show it is a moving transient; the pulse SLOWS as the reaction fades.
    private void DrawStateLabels(Orb o, Font font)
    {
        var act = ActiveStatesOrdered(o);
        if (act.Count == 0) return;
        var w = (float)Math.Clamp(1 - o.Age / Math.Max(0.1, o.ReactTime), 0, 1);   // reaction remaining → pulse SPEED
        var rate = 1.2f + 7f * w;                                                  // fast while active, slow as it fades
        var y = o.Pos.Y + o.R + 30f;
        for (var k = 0; k < Math.Min(act.Count, 3); k++)
        {
            var st = (MinigameTagEffects.State)act[k].idx; var mag = (float)act[k].mag; var col = MinigameTagEffects.StateColor(st);
            var pulse = 0.5f + 0.5f * Mathf.Sin((float)_anim * rate + k * 0.9f);
            var sz = (int)(12f + 5f * mag * (0.55f + 0.45f * pulse));              // size grows/shrinks with magnitude + pulse
            _scene.DrawString(font, new Vector2(o.Pos.X - 70, y), MinigameTagEffects.StateName(st).ToUpperInvariant(), HorizontalAlignment.Center, 140, sz, new Color(col.R, col.G, col.B, 0.55f + 0.4f * mag));
            y += sz + 3f;
        }
    }

    // hover card — name + tier/rarity, then the ELEMENT STATES in order (what it's DOING) for a reacting mixture,
    // falling back to identity TAGS for a raw/inert reagent. So hovering teaches the states over the abstract tags.
    private void DrawCard(Orb o, Lay l, Font font)
    {
        var (rn, rc) = MinigameTagEffects.Rarity(o.Tier, o.Grade);
        var act = ActiveStatesOrdered(o);
        const float w = 250f; var h = 74f + ((act.Count > 0 || o.Tags.Count > 0) ? 16f : 0f);
        var x = Mathf.Clamp(o.Pos.X - w / 2f, 8f, l.W - w - 8f); var y = Mathf.Clamp(o.Pos.Y - o.R - h - 12f, 8f, l.H - h - 8f);
        CraftRoundRect(new Rect2(x, y, w, h), new Color(0.09f, 0.08f, 0.10f, 0.97f), rc);
        _scene.DrawString(font, new Vector2(x + 12, y + 22), o.Name, HorizontalAlignment.Left, w - 20, 15, Ink);
        _scene.DrawString(font, new Vector2(x + 12, y + 42), $"Tier {o.Tier}  -  {rn}", HorizontalAlignment.Left, w - 20, 12, rc);
        if (act.Count > 0)
            _scene.DrawString(font, new Vector2(x + 12, y + 62), string.Join("  ·  ", act.Take(4).Select(a => MinigameTagEffects.StateName((MinigameTagEffects.State)a.idx))), HorizontalAlignment.Left, w - 20, 11, new Color(0.85f, 0.85f, 0.7f, 0.9f));
        else if (o.Tags.Count > 0)
            _scene.DrawString(font, new Vector2(x + 12, y + 62), string.Join("  ", o.Tags.Take(6)), HorizontalAlignment.Left, w - 20, 11, Sub);
    }

    private void DrawHud(Lay l, Font font)
    {
        // TIME as a quiet visual (no digits): a thin bar draining along the very top edge, reddening as it runs out
        if (_phase == Phase.Playing && _timeLimit > 0)
        {
            var frac = (float)Mathf.Clamp(_timeLeft / _timeLimit, 0, 1);
            var tc = _timeLeft < 12 ? BadC : new Color(0.8f, 0.72f, 0.55f, 0.5f);
            _scene.DrawRect(new Rect2(0, 0, l.W * frac, 3f), new Color(tc.R, tc.G, tc.B, _timeLeft < 12 ? 0.5f + 0.4f * Mathf.Abs(Mathf.Sin((float)_anim * 6f)) : 0.4f));
        }
        _scene.DrawString(font, new Vector2(l.W * 0.05f, 30), "merge marbles to react (raw ones are inert)  ·  click the well / [Enter] to cast  ·  [F1] log  ·  [F7] notes", HorizontalAlignment.Left, 800, 13, Sub);
        if (_phase == Phase.Casting && _castOrb != null)
        { var (rn, rc) = MinigameTagEffects.RarityFromPerf(_committed); _scene.DrawString(font, new Vector2(l.W / 2f - 150, l.H * 0.44f), rn.ToUpperInvariant(), HorizontalAlignment.Center, 300, 34, rc); }
    }

    private void DrawGlow()
    {
        if (_phase == Phase.Casting || _phase == Phase.Done) return;
        foreach (var o in _orbs)
        {
            var col = MinigameTagEffects.DisplayColor(o.Tags, o.E);
            var s = 0.22f + o.HeatT * 0.35f + (float)o.Reson * 0.25f;
            for (var i = 4; i >= 1; i--) { var t = i / 4f; _glow.DrawCircle(o.Pos, o.R * (1.15f + t * 0.6f), new Color(col.R, col.G, col.B, s * (1f - t) * 0.5f)); }
            if (o.HeatT > 0.5f) _glow.DrawCircle(o.Pos, o.R * 1.4f, new Color(1f, 0.5f, 0.2f, (o.HeatT - 0.5f) * 0.3f));
            // ACTIONING: an extra breathing bloom in the effect's colour so a reacting orb reads brighter than a still one
            var top = o.Top;
            if (top != MinigameTagEffects.State.None)
            { var ac = MinigameTagEffects.StateColor(top); var mag = (float)o.State[(int)top]; var pulse = 0.5f + 0.5f * Mathf.Sin((float)_anim * 7f + o.Wob); _glow.DrawCircle(o.Pos, o.R * (1.5f + pulse * 0.5f), new Color(ac.R, ac.G, ac.B, (0.14f + 0.14f * pulse) * mag)); }
        }
    }

    // the F1 overlay: build the discipline's live per-orb status block (heat-coloured), then let the shared harness
    // draw the panel frame + title + this block + the rolling event tail.
    private void DrawLog(Lay l, Font font)
    {
        var pinned = new List<(string, Color)>();
        foreach (var o in _orbs.Take(8))
        {
            var st = o.Boiling ? "BOIL" : o.Heat >= MinigameTagEffects.WARM ? "hot" : o.Heat >= MinigameTagEffects.HOT - 12 ? "warm" : "cool";
            var hc = o.Boiling ? BadC : o.Heat >= MinigameTagEffects.WARM ? new Color(1f, 0.6f, 0.2f) : Sub;
            pinned.Add(($"{Trim(o.Name, 9)} h{o.Heat:0} t{o.Turb:0} {st}", hc));
            pinned.Add(($"[F{o.E[0]:0} W{o.E[1]:0} E{o.E[2]:0} L{o.E[3]:0} S{o.E[4]:0} A{o.E[5]:0}]", Faint));
        }
        _dev.DrawLog(_scene, l.Log, font, pinned);
    }

    private void DrawReady(Lay l, Font font)
    {
        _scene.DrawRect(new Rect2(0, 0, l.W, l.H), new Color(0.02f, 0.02f, 0.03f, 0.55f));
        const float w = 560, h = 172; var x = l.W / 2f - w / 2f; var y = l.H * 0.36f;
        CraftRoundRect(new Rect2(x, y, w, h), new Color(0.09f, 0.08f, 0.10f, 0.97f), Gold);
        _scene.DrawString(font, new Vector2(x, y + 32), "THE ALCHEMY BENCH", HorizontalAlignment.Center, w, 20, Ink);
        _scene.DrawMultilineString(font, new Vector2(x + 26, y + 58),
            "Raw reagents are INERT - what you see is what you get. MERGE two and the combination REACTS for a few seconds (fire heats, water+fire steams, life blooms), moving POTENCY and VOLATILITY, then it SETTLES and holds. Steer VOLATILITY into the green band while building POTENCY, then click the well / [Enter] to cast.",
            HorizontalAlignment.Center, w - 52, 13, -1, Sub);
        _scene.DrawString(font, new Vector2(x, y + h - 28), "click  /  [Space]  to begin", HorizontalAlignment.Center, w, 18, Gold);
    }

    // ------------------------------------------------------------------ helpers
    private void CraftRoundRect(Rect2 r, Color bg, Color? border = null) => CraftFx.RoundRect(_scene, r, bg, border, border == null ? 0 : 2, 8);

    // ---- playtest harness glue (F1 log + F7 notes live in the shared MinigameDevLog) ----------------------------
    // the session header the dev-log frames each run with (metadata + the ingredient list)
    private IEnumerable<string> BuildLogHeader()
    {
        yield return $"output={Recipe?.OutputId ?? "(default sampler)"}  tier={_tier}  targetVolatility={_targetV:0.0}  potencyResistance={_resistance:0.00}";
        yield return "ingredients:";
        foreach (var o in _orbs) yield return $"  {o.Name}  t{o.Tier}  P0={o.P:0} V0={o.V:0}  [{string.Join(",", o.Tags)}]";
    }

    // an F7 note: a rich snapshot of every orb so the dev sees exactly what state the note describes
    private void OnDevNote(string text)
    {
        var snap = new List<string> { $"targetV={_targetV:0.0}  resist={_resistance:0.00}  orbs={_orbs.Count}" };
        foreach (var o in _orbs.OrderByDescending(CommitScore).Take(8))
            snap.Add($"{Trim(o.Name, 16),-16} P{o.P,3:0} V{o.V,3:0} heat{o.Heat,3:0} turb{o.Turb,3:0} Q{CommitScore(o) * 100,3:0}% {StatesStr(o),-30} E[F{o.E[0]:0} W{o.E[1]:0} E{o.E[2]:0} L{o.E[3]:0} S{o.E[4]:0} A{o.E[5]:0}]");
        _dev.Note(text, snap);
    }

    // the active states + magnitudes, compactly (for the F1 log + note snapshots)
    private static string StatesStr(Orb o)
    {
        if (o.Raw) return "inert";
        var p = new List<string>();
        for (var i = 1; i < o.State.Length; i++) if (o.State[i] > 0.06) p.Add($"{MinigameTagEffects.StateName((MinigameTagEffects.State)i)}{o.State[i] * 100:0}");
        return p.Count == 0 ? "settled" : string.Join(" ", p);
    }
    // log a reaction state the moment it becomes strong (rising edge past 0.35), so the F1 log narrates the brew
    private void LogEdges(Orb o)
    {
        if (o.Raw) return;
        for (var i = 1; i < o.State.Length; i++)
            if (o.State[i] >= 0.35 && o.PrevState[i] < 0.35)
                _dev.Log($"{MinigameTagEffects.StateName((MinigameTagEffects.State)i).ToUpperInvariant()} {o.State[i] * 100:0}%  heat{o.Heat:0} V{o.V:0} P{o.P:0}");
    }
    private static string Trim(string s, int n) => s.Length <= n ? s : s[..n];
    // geometry + colour helpers now route through the shared toolkit (CraftFx / CraftColor) — one set for all disciplines
    private static Vector2[] Ellipse(Vector2 c, float rx, float ry, int n) => CraftFx.Ellipse(c, rx, ry, n);
    private static Color Darken(Color c, float a) => CraftColor.Darken(c, a);
    private static Color Lighten(Color c, float a) => CraftColor.Lighten(c, a);
    private static Color Brighten(Color c, float a) => CraftColor.Brighten(c, a);
    private static float Ease(float t) => t * t * (3 - 2 * t);
    private static float Hash(int i) => CraftFx.Hash01(i);
}
