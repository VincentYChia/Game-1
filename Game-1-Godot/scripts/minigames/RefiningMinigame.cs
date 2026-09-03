using Godot;
using System;
using System.Collections.Generic;
using System.Linq;
using static Game1.Godot.MinigameTagEffects;   // for HEAT/AQUA/TERRA/GROVE/UMBRA/AIR/N (public consts)

namespace Game1.Godot;

/// <summary>
/// REFINING — "Impurity Folds". A TWO-LANE rhythm game (Click + Space). Beat the impurities
/// out of the metal across successive folds/gates; each gate is a fixed, tag-determined pattern
/// of 8-20 strikes that scroll right-to-left down a horizontal fold rail. A moving hit line grades
/// every strike Perfect / Close / Okay / Miss. The game NEVER stops — misses just cost points and
/// leave slag. Each gate speeds the tick up while the error WINDOW stays constant (the only
/// escalation dial). A streak bonus supplies the high ceiling.
///
/// The seam is sacred: this overlay owns ONLY the play loop and produces perf ∈ [0,1] through
/// MinigameOverlay.Finish (or FailCraft() if the whole round is degenerate). Game1.Core is 0-diff.
/// Tags resolve their per-tag channel through Refining's OWN <see cref="RefChannelOf"/> +
/// <see cref="KnobTable"/> and the pool-dominant theme through the PUBLIC Brew/Dominant — no private
/// MinigameTagEffects member is touched.
/// </summary>
public partial class RefiningMinigame : MinigameOverlay
{
    protected override string Discipline => "refining";

    // ============================================================ §1.3 ENUMS
    // Lanes are now KEYBOARD lanes, 2..5 of them, scaling with tier. Lane 0..(primary-1) are the
    // primary finger lanes (keys W/D/O/K, assigned by PrimaryKeysFor); the LAST lane is the SPACE
    // accent — the downbeat "spine", sparse and emphasised, never part of the primary rotation.
    // (The old two-lane Click+Space mouse scheme is gone: mouse clicks were swallowed by the overlay's
    //  GUI panel before ever reaching gameplay input, which is why only Space registered.)
    private enum Grade { Miss = 0, Okay = 1, Close = 2, Perfect = 3 }   // per-strike verdict
    private enum Phase { Ready, Play, Settle, Done }                    // state machine (§3)

    // ============================================================ §1.4 STRUCTS / CLASSES
    /// <summary>One scheduled strike on the fold rail. Immutable after gate build except Result/Judged.</summary>
    private sealed class Strike
    {
        public int Lane;             // which lane index the player must hit (0..laneCount-1; last = Space accent)
        public double Beat;          // scheduled hit time in BEATS from the gate's start (>=0, monotonic non-decreasing)
        public bool DoubleTap;       // sharp-tag: a tight second tap follows (rendered as a paired glyph)
        public bool IsAccent;        // Space downbeat accent (bigger glyph, heavier feel, +streak on a clean hit)
        public Grade Result;         // filled when judged (default Miss)
        public bool Judged;          // set true once scored (hit or auto-missed by passing the window)
        public double HitAtBeat = -1;// beat at which the player actually pressed (for the F1 log; -1 = never)
    }

    /// <summary>One gate/fold. Built once at gate-entry from the tag pattern; tempo baked in.</summary>
    private sealed class Gate
    {
        public int Index;                       // 0-based
        public List<Strike> Strikes = new();    // 8..20, ordered by Beat
        public double BeatsPerSecond;           // TEMPO for this gate (see §4.2). Increases per gate.
        public string PatternName = "";         // theme label for the HUD + log
        public Color LaneTint;                  // gate's theme colour (from the dominant pool theme), tints the rail
        public bool TempoDip;                   // temporal rider (§2.3/§4.2): this gate slows then snaps back
        public double AvgGap = 1.0;             // mean beat-gap between consecutive strikes (cached at build; §4.2 ease)
    }

    // ============================================================ §2.5 PROFILE
    private sealed class RefiningProfile : MinigameModifierCommon.ModProfile
    {
        public RefiningProfile() : base(6, 0) { }   // 6 elemental channels; Refining uses NO named-state array (states=0)
        public double Dens, LaneBias, Inter, Dbl, Imp = 1.0, Rich = 1.0;   // resolved knobs (post-fold)
        public bool WaterForgive;                    // WATER-dominant: first Miss of each gate skips the slag add
    }

    // ============================================================ §4.0 NAMED CONSTANTS
    private const double SettleDur = 1.0;          // s — length of the Settle flourish
    private const double TimeBackstop = 90.0;      // s — hard cap on total play time (safety)
    private const double WindowBase = 0.105;       // s — the constant ± error window (Miss threshold). NEVER scaled. (tightened from 0.13 — was too easy)
    private const double CloseFrac = 0.45;         // |Δ| ≤ 0.45·window → Close
    private const double OkayFrac = 1.00;          // 0.45·window < |Δ| ≤ 1.00·window → Okay; beyond → Miss
    private const double PerfectFrac = 0.18;       // |Δ| ≤ 0.18·window → Perfect
    private const double PtsPerfect = 1.00;
    private const double PtsClose = 0.70;
    private const double PtsOkay = 0.40;
    private const double PtsMiss = 0.00;
    private const double StreakStep = 0.04;        // streak multiplier growth per consecutive perfect/close
    private const double StreakCap = 0.60;         // max streak bonus (multiplier caps at 1.60)
    private const double ImpDrainPerfect = 0.055;  // impurity removed per Perfect
    private const double ImpDrainClose = 0.040;    // per Close
    private const double ImpDrainOkay = 0.020;     // per Okay
    private const double ImpBumpMiss = 0.030;      // impurity ADDED per Miss (leaves slag)
    private const double ImpLeakPerBeat = 0.010;   // toxic corrupt-gate only: impurity regrown per beat (§4.5a)
    private const double SharpPerfectBonus = 0.10; // extra Perfect points if sharp in pool
    private const double RailScrollBeats = 2.5;    // beats of rail visible ahead of the hit line (lead-in runway)
    private const double BreatherBeats = 1.0;      // silent lead-in beats at the start of each gate (count-in)
    private const double BpsMax = 4.2;             // anti-unhittable tempo clamp (§9 roadblock 5)
    private const double MinGapBeats = 0.35;       // strike-gap floor (§8) — strikes never overlap unreadably
    private const int BaseStrikes = 8;             // §4.1 strike-count floor
    private const double AccentPeriodBeats = 4.0;  // Space accent cadence — one downbeat "spine" note per measure
    private const double AccentPerfectStreak = 1;  // a clean accent hit adds this extra to the combo (emphasis reward)

    // ============================================================ §6.1 LAYOUT CONSTANTS
    // LARGER stage (≈1.4×) — more px per beat = the token's timing is far easier to read.
    private const float RailW = 920f, RailH = 400f;
    private static readonly Rect2 IngotRect = new(30, 54, 150, 292);
    private static readonly Rect2 RailRect = new(210, 92, 640, 200);   // larger, taller band → up to 5 stacked lanes
    private const float HitLineX = 210f + 120f;                        // = 330f (120px lead-in runway)
    private const float RailUsableW = (210f + 640f) - HitLineX;        // = 520f
    private const float BeatPx = RailUsableW / (float)RailScrollBeats;  // = 208 px per beat (was 148.8)
    private const float LanePadY = 24f;                                // vertical inset for the lane band
    private static readonly Rect2 ImpBarRect = new(210, 306, 640, 18);
    private const float HudY = 352f;

    // ============================================================ §6 COLOURS
    private static readonly Color ClickLaneCol = new(0.55f, 0.9f, 1.0f);   // cool cyan (legacy alias for primary lane 0)
    // per-lane hues so up to four finger lanes read apart at a glance; the accent (Space) uses Accent brass.
    private static readonly Color[] PrimaryLaneCols =
    {
        new(0.55f, 0.90f, 1.00f),   // cyan
        new(0.70f, 0.85f, 0.55f),   // green
        new(0.95f, 0.72f, 0.85f),   // rose
        new(0.75f, 0.78f, 1.00f),   // periwinkle
    };
    private static readonly Color MissRed = new(1.0f, 0.4f, 0.34f);        // Miss / slag
    private static readonly Color GlowCol = new(0.95f, 0.70f, 0.30f);      // refining glow
    private static readonly Color EmberCol = new(0.92f, 0.80f, 0.50f);
    private static readonly Color ImpFillCol = new(0.5f, 0.42f, 0.3f);     // muddy slag
    private static readonly Color ToxicCol = new(0.34f, 0.55f, 0.24f);     // sickly green corrupt tell

    // ============================================================ §1.5 RUNTIME PLAY STATE
    private readonly List<Gate> _gates = new();
    private int _gateIdx;
    private Gate _gate = null!;
    private double _gateClock;
    private double _gateBeat;
    private double _gateBeatPrev;
    private bool _gateForgaveMiss;
    private int _nextStrike;
    private Dictionary<string, int> _pool = new();
    private Dictionary<string, int> _outCounts = new();
    private RefiningProfile _profile = null!;
    private RefiningProfile _outProfile = null!;
    private ulong _seed;
    private double _score;
    private double _scoreMax = 1;
    private int _streak;
    private int _maxStreak;
    private double _impurity = 1;
    private double _purity;
    private double _settleT;
    private double _anim;
    private Phase _phase = Phase.Ready;
    private readonly double[] _flashLane = new double[5];       // one per possible lane (max 5)
    private int _laneCount = 2;                                 // 2..5 (primary count + 1 accent), set per tier in OnBegin
    private Key[] _laneKeys = System.Array.Empty<Key>();        // lane index → physical key (last is always Space)
    private Color _lastGradeCol = Colors.White;
    private bool _sharpInPool;
    private bool _temporalInPool;
    private bool _toxicInPool;
    private double _patternJitter = 0.15;
    private double _gradeInit;
    private MinigameDevLog _dev = null!;
    private int _domChannel;                       // pool dominant channel (0..5), cached for draw
    private Color _ingotBodyCol;                   // de-muddied dominant-family colour for the ingot

    // derived / difficulty-interpolated params (set once in OnBegin, §4 + §7)
    private double _bps0;
    private double _tempoRamp;
    private double _windowSec;
    private double _closeFrac;
    private double _okayFrac;
    private int _nFolds;
    private double _windowBeats;                   // recomputed per gate (constant seconds → variable beats)

    // ============================================================ §1.6 UI NODES
    private Control _rail = null!;
    private VBoxContainer _readyBox = null!;
    private Label _readyLabel = null!;
    private Button _beginBtn = null!;
    private Label _hint = null!;

    // ============================================================ §1.1 TIER PARSE + DEBUG TABLE
    private static int TierIntOf(string tier) => tier switch
    {
        "common" => 1,
        "uncommon" => 2,
        "rare" => 3,
        "epic" => 4,
        "legendary" => 5,
        _ => 1,          // unknown/empty → treat as common
    };

    private static readonly string[][] DebugTierTags =
    {
        /* [0] unused */ new[] { "iron", "common" },
        /* T1 */         new[] { "iron", "hard", "common" },
        /* T2 */         new[] { "steel", "strong", "uncommon" },
        /* T3 */         new[] { "mithril", "sharp", "rare" },
        /* T4 */         new[] { "adamantine", "dense", "epic" },
        /* T5 */         new[] { "orichalcum", "arcane", "legendary" },
    };
    private static string[] SampleTagsFromTier(int tierInt) => DebugTierTags[Math.Clamp(tierInt, 1, 5)];

    // ============================================================ §2.2 KNOB TABLE (the full material vocabulary)
    // tag → (Pot, Vol, Time, Rx) — the SAME 4-tuple MinigameModifierCommon.Fold consumes.
    internal static readonly Dictionary<string, (double Pot, double Vol, double Time, double Rx)> KnobTable = new()
    {
        // ---------- FIRE / HEAT ----------
        ["fire"] = (1.05, +10, 0.85, 1.40), ["flame"] = (1.04, +9, 0.90, 1.35), ["ember"] = (1.02, +6, 0.92, 1.25),
        ["molten"] = (1.05, +11, 0.82, 1.42), ["forge"] = (1.03, +5, 0.92, 1.22), ["volcanic"] = (1.06, +12, 0.80, 1.45),
        ["lightning"] = (1.04, +12, 0.72, 1.50), ["storm"] = (1.04, +9, 0.78, 1.35), ["radiant"] = (1.04, +4, 0.95, 1.15),
        ["chaos"] = (1.02, +16, 0.68, 1.55), ["light"] = (1.03, -2, 0.98, 1.10),

        // ---------- WATER ----------
        ["water"] = (1.00, -5, 1.12, 0.95), ["aqua"] = (1.00, -5, 1.12, 0.95), ["liquid"] = (1.00, -4, 1.10, 0.95),
        ["solvent"] = (0.98, -3, 1.05, 1.05),

        // ---------- COLD / ICE ----------
        ["ice"] = (1.00, -7, 1.28, 0.70), ["frost"] = (1.00, -6, 1.22, 0.74), ["frozen"] = (1.00, -8, 1.32, 0.66),
        ["chill"] = (1.00, -5, 1.15, 0.80),

        // ---------- EARTH / TERRA + structural metals ----------
        ["earth"] = (1.00, -5, 1.25, 0.78), ["stone"] = (1.00, -6, 1.28, 0.75), ["sand"] = (1.00, -3, 1.10, 0.92),
        ["mineral"] = (1.00, -4, 1.22, 0.80), ["crystal"] = (1.05, -4, 1.20, 0.82), ["gem"] = (1.06, -3, 1.18, 0.84),
        ["metal"] = (1.02, -4, 1.20, 0.82), ["metallic"] = (1.04, -2, 1.05, 0.95), ["iron"] = (1.02, -4, 1.22, 0.80),
        ["steel"] = (1.05, -4, 1.20, 0.82), ["bronze"] = (1.03, -3, 1.20, 0.82), ["copper"] = (1.02, -3, 1.18, 0.84),
        ["tin"] = (1.01, -3, 1.16, 0.86), ["alloy"] = (1.10, -3, 1.10, 0.92), ["silver"] = (1.06, -2, 1.14, 0.88),
        ["gold"] = (1.08, -2, 1.12, 0.90), ["mithril"] = (1.14, -2, 1.10, 0.98), ["adamantine"] = (1.18, -4, 1.24, 0.86),
        ["orichalcum"] = (1.16, +2, 1.10, 1.02),

        // ---------- LIFE / GROVE + feral ----------
        ["wood"] = (1.00, -2, 1.08, 1.00), ["oak"] = (1.00, -2, 1.08, 1.00), ["ash"] = (1.01, -1, 1.05, 1.02),
        ["ironwood"] = (1.05, -2, 1.10, 1.00), ["ebony"] = (1.04, -2, 1.10, 0.98), ["birch"] = (1.00, -1, 1.05, 1.02),
        ["willow"] = (1.00, -2, 1.06, 1.02), ["worldtree"] = (1.10, 0, 1.08, 1.05), ["exotic"] = (1.08, +2, 1.02, 1.08),
        ["plant"] = (1.02, -1, 1.02, 1.02), ["herb"] = (1.03, -2, 1.02, 1.03), ["living"] = (1.04, +1, 1.00, 1.05),
        ["leather"] = (1.00, -2, 1.08, 0.94), ["monster"] = (1.05, +4, 0.98, 1.08), ["fang"] = (1.05, +5, 0.94, 1.10),
        ["scales"] = (1.03, -2, 1.06, 0.96), ["bone"] = (1.02, -3, 1.10, 0.90), ["gel"] = (0.98, -1, 1.04, 0.98),
        ["carapace"] = (1.04, -4, 1.10, 0.90), ["blood"] = (1.06, +6, 0.92, 1.18),

        // ---------- SHADOW / UMBRA + toxic + mystic ----------
        ["void"] = (1.06, +7, 1.05, 0.95), ["dark"] = (1.03, +5, 1.02, 0.95), ["shadow"] = (1.04, +4, 1.00, 1.00),
        ["spectral"] = (0.95, +5, 1.20, 0.88), ["poison"] = (1.08, +6, 0.98, 1.12), ["venom"] = (1.08, +6, 0.96, 1.12),
        ["toxic"] = (1.08, +6, 1.00, 1.12), ["acid"] = (1.06, +7, 0.92, 1.28), ["arcane"] = (1.16, +2, 1.05, 1.00),
        ["magical"] = (1.12, +2, 1.02, 1.02), ["essence"] = (1.14, +4, 1.02, 1.05),

        // ---------- AIR / WIND ----------
        ["air"] = (1.00, -3, 0.75, 1.28), ["wind"] = (1.00, -3, 0.76, 1.24), ["vapor"] = (1.00, -2, 0.78, 1.18),
        ["gas"] = (1.00, -2, 0.74, 1.24),

        // ---------- QUALITY / GRADE ----------
        ["starter"] = (0.88, +3, 1.05, 0.92), ["basic"] = (0.92, +2, 1.02, 0.98), ["common"] = (0.95, +1, 1.00, 1.00),
        ["standard"] = (1.00, 0, 1.02, 0.98), ["uncommon"] = (1.05, -1, 1.02, 1.02), ["fine"] = (1.08, -2, 1.02, 1.02),
        ["quality"] = (1.11, -3, 1.04, 1.00), ["refined"] = (1.13, -5, 1.04, 0.98), ["rare"] = (1.16, -5, 1.02, 1.02),
        ["advanced"] = (1.19, -6, 1.00, 1.04), ["epic"] = (1.22, -7, 1.02, 1.02), ["precious"] = (1.22, -8, 1.06, 0.98),
        ["legendary"] = (1.28, -9, 1.02, 1.02), ["mythical"] = (1.32, -11, 1.04, 1.00), ["ancient"] = (1.25, -10, 1.20, 0.82),
        ["superior"] = (1.14, -4, 1.02, 1.00), ["pure"] = (1.10, -12, 1.02, 0.98), ["holy"] = (1.15, -4, 1.02, 1.02),
        ["mundane"] = (0.86, 0, 1.00, 0.90), ["material"] = (1.00, -1, 1.04, 0.96), ["elemental"] = (1.10, +5, 0.92, 1.18),

        // ---------- PHYSICAL / STRUCTURAL ----------
        ["durable"] = (1.00, -3, 1.18, 0.90), ["strong"] = (1.10, -2, 1.02, 1.08), ["hard"] = (1.00, -5, 1.10, 0.90),
        ["solid"] = (1.00, -7, 1.22, 0.76), ["dense"] = (1.00, -6, 1.26, 0.72), ["heavy"] = (1.00, -4, 1.26, 0.76),
        ["sharp"] = (1.05, +3, 0.86, 1.24), ["layered"] = (1.00, -2, 1.24, 0.86), ["flexible"] = (1.00, -3, 1.16, 0.96),
        ["versatile"] = (1.05, -1, 1.02, 1.04), ["memory"] = (1.05, -3, 1.14, 0.96),

        // ---------- ENERGY / EXOTIC ----------
        ["temporal"] = (1.10, -6, 1.35, 0.72), ["quantum"] = (1.00, +4, 0.92, 1.14), ["impossible"] = (1.20, +6, 1.04, 1.10),
        ["dangerous"] = (1.10, +12, 0.76, 1.44), ["harmony"] = (1.10, -8, 1.12, 0.90), ["power"] = (1.24, +3, 1.04, 1.14),

        // ---------- FUNCTION / OUTPUT ----------
        ["weapon"] = (1.08, +4, 0.94, 1.14), ["combat"] = (1.06, +5, 0.92, 1.18), ["explosive"] = (1.10, +14, 0.72, 1.48),
        ["armor"] = (1.04, -8, 1.22, 0.82), ["protection"] = (1.05, -8, 1.20, 0.84), ["defense"] = (1.02, -8, 1.18, 0.84),
        ["resistance"] = (1.00, -7, 1.14, 0.90), ["tool"] = (1.03, -5, 1.18, 0.86), ["utility"] = (1.00, -2, 1.04, 0.96),
        ["healing"] = (1.05, -6, 1.10, 0.86), ["regeneration"] = (1.05, -6, 1.30, 0.78), ["buff"] = (1.10, +2, 0.96, 1.10),
        ["enhancement"] = (1.12, -3, 1.04, 1.00), ["strength"] = (1.15, +3, 0.96, 1.10), ["agility"] = (1.04, +3, 0.82, 1.20),
        ["speed"] = (1.05, +4, 0.72, 1.30), ["potion"] = (1.02, -2, 1.04, 0.96), ["consumable"] = (1.00, -3, 1.04, 0.96),
        ["crafting"] = (1.02, -4, 1.14, 0.90), ["engineering"] = (1.04, -6, 1.18, 0.86), ["fishing"] = (1.00, -4, 1.14, 0.86),
    };

    // ============================================================ §2.2a RefChannelOf (Refining's OWN tag→channel map)
    internal static readonly Dictionary<string, int> RefChannelOf = new()
    {
        // FIRE/HEAT — BODY tags only (lightning/storm/radiant/light/chaos are riders, deliberately ABSENT).
        ["fire"] = HEAT, ["flame"] = HEAT, ["ember"] = HEAT, ["molten"] = HEAT, ["forge"] = HEAT, ["volcanic"] = HEAT,
        // WATER + ICE (all AQUA — ice is the still pole of water)
        ["water"] = AQUA, ["aqua"] = AQUA, ["liquid"] = AQUA, ["solvent"] = AQUA, ["ice"] = AQUA, ["frost"] = AQUA, ["frozen"] = AQUA, ["chill"] = AQUA,
        // EARTH + structural metals
        ["earth"] = TERRA, ["stone"] = TERRA, ["sand"] = TERRA, ["mineral"] = TERRA, ["crystal"] = TERRA, ["gem"] = TERRA,
        ["metal"] = TERRA, ["metallic"] = TERRA, ["iron"] = TERRA, ["steel"] = TERRA, ["bronze"] = TERRA, ["copper"] = TERRA, ["tin"] = TERRA,
        ["alloy"] = TERRA, ["silver"] = TERRA, ["gold"] = TERRA, ["mithril"] = TERRA, ["adamantine"] = TERRA, ["orichalcum"] = TERRA,
        // LIFE + woods + feral
        ["wood"] = GROVE, ["oak"] = GROVE, ["ash"] = GROVE, ["ironwood"] = GROVE, ["ebony"] = GROVE, ["birch"] = GROVE, ["willow"] = GROVE, ["worldtree"] = GROVE, ["exotic"] = GROVE,
        ["plant"] = GROVE, ["herb"] = GROVE, ["living"] = GROVE, ["leather"] = GROVE, ["monster"] = GROVE, ["fang"] = GROVE, ["scales"] = GROVE, ["bone"] = GROVE, ["gel"] = GROVE, ["carapace"] = GROVE, ["blood"] = GROVE,
        // SHADOW + toxic + mystic
        ["void"] = UMBRA, ["dark"] = UMBRA, ["shadow"] = UMBRA, ["spectral"] = UMBRA, ["poison"] = UMBRA, ["venom"] = UMBRA, ["toxic"] = UMBRA, ["acid"] = UMBRA, ["arcane"] = UMBRA, ["magical"] = UMBRA, ["essence"] = UMBRA,
        // AIR
        ["air"] = AIR, ["wind"] = AIR, ["vapor"] = AIR, ["gas"] = AIR,
    };

    // The seven theme-default rows (§2.2 table), indexed by channel constant 0..5.
    private static readonly (double Pot, double Vol, double Time, double Rx)[] ThemeDefault =
    {
        /*HEAT */ (1.05, +10, 0.85, 1.35),
        /*AQUA */ (1.00, -4, 1.15, 0.95),
        /*TERRA*/ (1.00, -4, 1.25, 0.80),
        /*GROVE*/ (1.04, +2, 1.05, 1.05),
        /*UMBRA*/ (1.05, +6, 1.00, 1.05),
        /*AIR  */ (1.00, -3, 0.75, 1.25),
    };

    // §4.1 life-family (GROVE-channel) tags — detected by NAME for the ExtraFold trigger.
    private static readonly HashSet<string> LifeFamily = new()
    {
        "wood", "oak", "ash", "ironwood", "ebony", "birch", "willow", "worldtree", "exotic",
        "plant", "herb", "living", "leather", "monster", "fang", "scales", "bone", "gel", "carapace", "blood",
    };

    // ============================================================ §8 RANDOMNESS
    /// <summary>One SplitMix64 step: advances the state in place and returns it. Deterministic, no GD.Randf.</summary>
    private static ulong SplitMix64(ref ulong s)
    {
        s += 0x9E3779B97F4A7C15UL;
        ulong z = s;
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
        return z ^ (z >> 31);
    }

    /// <summary>One deterministic 0..1 keyed by (gate, index, salt) WITHOUT consuming the base seed.</summary>
    private double Hash01(ulong seed, int gate, int index, int salt = 0)
    {
        ulong h = seed ^ ((ulong)(uint)gate * 0x100000001B3UL) ^ ((ulong)(uint)index << 21) ^ ((ulong)(uint)salt << 43);
        return (SplitMix64(ref h) >> 11) * (1.0 / 9007199254740992.0);   // 53-bit mantissa → [0,1)
    }

    private static ulong SeedBit(ref ulong s) => SplitMix64(ref s) & 1UL;   // consumes one step; low bit = ± sign / coin flip

    /// <summary>FNV-1a over the recipe's identity — same recipe+materials → same seed → reproducible.</summary>
    private static ulong SeedFrom(RecipeContext? recipe, string difficultyTier, int tierInt)
    {
        const ulong offset = 14695981039346656037UL;
        const ulong prime = 1099511628211UL;
        ulong h = offset;
        void Mix(string s)
        {
            if (s == null) return;
            foreach (var ch in s) { h ^= ch; h *= prime; }
        }
        if (recipe != null)
        {
            Mix(recipe.OutputId);
            Mix("|");
            Mix(string.Join(",", recipe.OutputTags));
            Mix("|");
            foreach (var ing in recipe.Inputs)
            {
                Mix(ing.Id); Mix(":"); Mix(string.Join(",", ing.Tags)); Mix(":"); Mix(ing.Qty.ToString());
            }
            Mix("|");
            Mix(recipe.Tier);
        }
        else
        {
            // Null recipe: seed from DifficultyTier + a fixed salt so debug launches are deterministic per tier.
            Mix("refining_debug|"); Mix(difficultyTier); Mix("|"); Mix(tierInt.ToString());
        }
        if (h == 0) h = 0x1234567890ABCDEFUL;   // avoid a degenerate all-zero state
        return h;
    }

    // ============================================================ HELPERS
    private double Interp(double easy, double hard)
        => easy + (hard - easy) * Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);

    // ---- lane geometry / identity ------------------------------------------------------------
    // Primary finger keys by count. Left hand (W,D) grows first, right hand (O,K) joins at 3/4 lanes.
    private static Key[] PrimaryKeysFor(int p) => p switch
    {
        1 => new[] { Key.D },
        2 => new[] { Key.D, Key.K },
        3 => new[] { Key.W, Key.D, Key.K },
        _ => new[] { Key.W, Key.D, Key.O, Key.K },
    };

    private bool IsAccentLane(int lane) => lane == _laneCount - 1;   // last lane is always the Space accent

    // vertical centre of lane i, spread evenly across the padded RailRect band
    private float LaneY(int i)
    {
        float top = RailRect.Position.Y + LanePadY;
        float bot = RailRect.Position.Y + RailRect.Size.Y - LanePadY;
        if (_laneCount <= 1) return (top + bot) * 0.5f;
        return top + (bot - top) * i / (_laneCount - 1);
    }

    private Color LaneColor(int lane) => IsAccentLane(lane) ? Accent : PrimaryLaneCols[Math.Min(lane, PrimaryLaneCols.Length - 1)];

    private static string KeyGlyph(Key k) => k switch
    {
        Key.Space => "SPACE",
        Key.W => "W", Key.D => "D", Key.O => "O", Key.K => "K",
        _ => k.ToString(),
    };

    // start lane for a gate's first strike (LaneBias nudges toward an outer "home" lane on TERRA/UMBRA)
    private int PickStartLane(int g, int primaryLanes)
    {
        if (primaryLanes <= 1) return 0;
        double r = Hash01(_seed, g, 0, 's');
        double bias = _profile.LaneBias;
        if (Math.Abs(bias) > 0.25 && r < Math.Abs(bias)) return bias > 0 ? primaryLanes - 1 : 0;
        return Math.Min((int)(r * primaryLanes), primaryLanes - 1);
    }

    // pick a DIFFERENT primary lane, preferring adjacent lanes (small jumps stay playable)
    private int PickOtherLane(int cur, int primaryLanes, int g, int i)
    {
        if (primaryLanes <= 1) return 0;
        if (primaryLanes == 2) return 1 - cur;
        double r = Hash01(_seed, g, i, 'l');
        int step = r < 0.35 ? -1 : r < 0.70 ? +1 : r < 0.85 ? -2 : +2;   // adjacency-weighted
        int next = cur + step;
        if (next < 0 || next > primaryLanes - 1) next = cur - step;       // reflect off the edge
        next = Math.Clamp(next, 0, primaryLanes - 1);
        if (next == cur) next = (cur + 1) % primaryLanes;
        return next;
    }

    // ============================================================ §6.6 BUILD UI
    protected override void BuildUi(VBoxContainer host)
    {
        _rail = new Control
        {
            CustomMinimumSize = new Vector2(RailW, RailH),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
            MouseFilter = Control.MouseFilterEnum.Ignore,
        };
        _rail.Draw += DrawRail;
        host.AddChild(_rail);

        _hint = new Label
        {
            Text = "Hit each lane's key as its token reaches the line.",   // real key list is filled in per-tier in OnBegin
            Modulate = new Color(0.95f, 0.86f, 0.62f),
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        _hint.AddThemeFontSizeOverride("font_size", 13);
        host.AddChild(_hint);

        _readyBox = new VBoxContainer();
        _readyBox.AddThemeConstantOverride("separation", 10);
        host.AddChild(_readyBox);

        _readyLabel = new Label
        {
            Text = "Beat the impurities out of the metal.\n"
                 + "Keep the rhythm as each fold speeds up — Perfect / Close / Okay / Miss per strike.\n"
                 + "Misses leave slag; long streaks purify faster. The forge never stops.",
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        _readyLabel.AddThemeFontSizeOverride("font_size", 16);
        _readyBox.AddChild(_readyLabel);

        _beginBtn = new Button { Text = "BEGIN FOLDING   [Space]", FocusMode = Control.FocusModeEnum.None };
        _beginBtn.AddThemeFontSizeOverride("font_size", 20);
        _beginBtn.Pressed += StartPlay;
        _readyBox.AddChild(_beginBtn);

        // shared F1/F7 dev harness — builds its own notes box; fed the live context bracket
        _dev = new MinigameDevLog("refining");
        _dev.Context = () => $"g={_gateIdx + 1}/{_nFolds} beat={_gateBeat,5:0.0} combo={_streak} q={(_score / Math.Max(1e-6, _scoreMax)) * 100,3:0}%";
        _dev.NoteSubmitted += OnDevNote;
        _dev.BuildNotesPanel(host);
    }

    // ============================================================ §3 STATE MACHINE — OnBegin
    protected override void OnBegin()
    {
        int tierInt = TierIntOf(Recipe?.Tier ?? DifficultyTier);

        // --- lanes: W/D/O/K primary finger lanes scale 1→4 with tier; Space accent spine is always present ---
        int primaryCount = Math.Clamp(tierInt, 1, 4);          // T1→1 … T4/T5→4 primaries
        _laneKeys = PrimaryKeysFor(primaryCount).Append(Key.Space).ToArray();
        _laneCount = _laneKeys.Length;                         // 2..5

        // --- gather ingredients (null-recipe degrade, §1.1) ---
        var inputs = new List<RecipeContext.Ingredient>();
        List<string> outputTags;
        if (Recipe?.Inputs is { Count: > 0 })
        {
            inputs = Recipe.Inputs;
            outputTags = Recipe.OutputTags ?? new List<string>();
        }
        else
        {
            inputs.Add(new RecipeContext.Ingredient
            {
                Tags = SampleTagsFromTier(tierInt).ToList(),
                Qty = 1,
                MaterialTier = Math.Min(tierInt, 4),
            });
            outputTags = new List<string> { "refined", "metal" };
        }

        // --- seed (§8) ---
        _seed = SeedFrom(Recipe, DifficultyTier, tierInt);

        // --- build pools + essences (§2.4) ---
        _pool = new Dictionary<string, int>();
        var poolEssence = new double[N];
        var allPoolTags = new List<string>();
        foreach (var ing in inputs)
        {
            int mtier = Math.Max(1, ing.MaterialTier);
            int qty = Math.Max(1, ing.Qty);
            var e = Brew(ing.Tags, mtier, qty);
            for (var i = 0; i < N; i++) poolEssence[i] += e[i];
            foreach (var t in ing.Tags)
            {
                _pool[t] = _pool.GetValueOrDefault(t) + 1;
                allPoolTags.Add(t);
            }
        }

        _outCounts = new Dictionary<string, int>();
        var outEssence = new double[N];
        foreach (var t in outputTags)
        {
            _outCounts[t] = _outCounts.GetValueOrDefault(t) + 1;
            var e = Brew(new List<string> { t }, tierInt, 1);
            for (var i = 0; i < N; i++) outEssence[i] += e[i];
        }

        // --- reset jitter BEFORE the ingredient BuildProfile (its riders bump it) ---
        _patternJitter = 0.15;
        _sharpInPool = false;
        _temporalInPool = false;
        _toxicInPool = false;

        // --- fold profiles (§2.5). Ingredient profile drives structure/riders; output profile → #folds/Rich only. ---
        _profile = BuildProfile(_pool, poolEssence, tierInt);
        // output riders are IGNORED (its Dens/LaneBias/etc. unused except Rich). Snapshot + restore rider state.
        bool sharpSnap = _sharpInPool, tempSnap = _temporalInPool, toxSnap = _toxicInPool;
        double jitterSnap = _patternJitter;
        _outProfile = BuildProfile(_outCounts, outEssence, tierInt);
        _sharpInPool = sharpSnap; _temporalInPool = tempSnap; _toxicInPool = toxSnap; _patternJitter = jitterSnap;

        _domChannel = Dominant(poolEssence);
        _ingotBodyCol = CraftColor.DeMuddy(FamilyColor(_domChannel), FamilyColor(_domChannel));

        // --- difficulty-interpolated params (§4.0/§7) ---
        _bps0 = Interp(2.0, 3.0);   // faster base tempo (was 1.6→2.6) — Refining played too easy
        _tempoRamp = Interp(1.10, 1.16);
        _windowSec = WindowBase;    // NO interp — constant
        _closeFrac = CloseFrac;
        _okayFrac = OkayFrac;

        // --- #folds (§4.1) — by TAG NAME, never by Dominant() ---
        int outTagCount = outputTags.Count;
        bool extra = _pool.ContainsKey("chaos") || LifeFamily.Any(_pool.ContainsKey);
        int extraFold = extra ? 1 : 0;
        _nFolds = Math.Clamp(1 + tierInt + outTagCount + extraFold, 2, 9);

        // --- build all gates (deterministic) ---
        _gates.Clear();
        _score = 0;
        _scoreMax = 0;
        for (var g = 0; g < _nFolds; g++)
        {
            var gate = BuildGate(g);
            _gates.Add(gate);
            foreach (var s in gate.Strikes) _scoreMax += PtsPerfect;   // one Perfect per strike (double-taps are separate strikes)
        }
        if (_scoreMax <= 0) _scoreMax = 1;   // guard the denominator (empty-recipe path FailCrafts below)

        // --- empty-recipe guard (§3): pathological all-empty pool produced no strikes ---
        int total = 0;
        foreach (var gg in _gates) total += gg.Strikes.Count;
        if (total == 0) { FailCraft(); return; }

        // --- quality grade → seed the impurity (§3 Ready row) ---
        _gradeInit = MinigameTagEffects.Grade(allPoolTags);
        _impurity = Math.Clamp(0.7 * _profile.Imp * (1 - 0.15 * _gradeInit), 0.35, 1.0);
        _purity = 1 - _impurity;

        _streak = 0;
        _maxStreak = 0;
        _gateIdx = 0;
        _gate = _gates[0];
        _gateClock = 0;
        _gateBeat = 0;
        _gateBeatPrev = 0;
        _nextStrike = 0;
        _gateForgaveMiss = false;
        System.Array.Clear(_flashLane, 0, _flashLane.Length);
        _settleT = 0;
        _settleTimeAccum = 0;
        _anim = 0;
        _phase = Phase.Ready;

        var primaryGlyphs = string.Join(" · ", _laneKeys.Take(_laneCount - 1).Select(KeyGlyph));
        _hint.Text = $"Fingers: {primaryGlyphs}      Accent: SPACE (downbeat spine)      ·      hit each lane's key as its token reaches the line";
        SetHeaderSub($"{_nFolds} folds · {_laneCount} lanes · {ChannelName(_domChannel)} · bps {_bps0:0.0}");
        SetQuality(0);
        SetTimer(TimeBackstop, 12);
        _readyBox.Visible = true;
        _dev.BeginSession(BuildLogHeader());
        _dev.Log($"READY folds={_nFolds} dom={ChannelName(_domChannel)} bps0={_bps0:0.00} imp0={_impurity:0.00} grade={_gradeInit:0.00}");
        _rail.QueueRedraw();
    }

    // ============================================================ §2.5 PROFILE BUILD
    private RefiningProfile BuildProfile(IReadOnlyDictionary<string, int> counts, double[] poolEssence, int tier)
    {
        var p = new RefiningProfile();

        // Build the EFFECTIVE table: KnobTable rows verbatim + a theme-default row for any counted tag that has no
        // explicit row but DOES have a RefChannelOf channel (§2.2/§2.2a).
        var table = new Dictionary<string, (double Pot, double Vol, double Time, double Rx)>(KnobTable);
        foreach (var tag in counts.Keys)
            if (!table.ContainsKey(tag) && RefChannelOf.TryGetValue(tag, out var ch))
                table[tag] = ThemeDefault[ch];

        MinigameModifierCommon.Fold(p, counts, table, chExc: null, stExc: null, strongExc: null, pvExc: null);
        p.Rx *= 1 + (Math.Max(1, tier) - 1) * 0.04;              // tier lightly raises density
        MinigameModifierCommon.Clamp(p);                         // shared clamp: Pot .5..2.3, Vol ±28, Time .5..2.2, Rx .35..2.5

        // map shared fields → Refining knobs (§2 top)
        p.Dens = Math.Clamp(p.Rx * Math.Clamp(2 - p.Time, 0.7, 1.2), 0.6, 1.6);
        p.Dbl = Math.Clamp(0.12 + p.Vol / 60.0, 0.0, 0.6);
        p.Imp = Math.Clamp(1.0 + p.Vol / 40.0, 0.5, 1.4);
        p.Rich = Math.Clamp(0.75 + 0.35 * p.Pot, 0.9, 1.25);

        var dom = Dominant(poolEssence);                         // 0..5 channel index
        (p.LaneBias, p.Inter) = ThemeStructure(dom, ref _seed);  // §2.3 table (+ seed sign for EARTH/SHADOW)
        p.WaterForgive = dom == AQUA;                            // WATER-dominant → forgive first Miss/gate
        ApplyRiders(p, counts, ref _seed);                       // sharp/chaos/temporal/layered deltas (§2.3)
        return p;
    }

    // §2.3 structural table (dominant channel → base LaneBias/Inter, with the seed-signed EARTH/SHADOW magnitudes).
    private (double LaneBias, double Inter) ThemeStructure(int dom, ref ulong seed)
    {
        double sign = (SplitMix64(ref seed) & 1UL) == 0 ? +1.0 : -1.0;   // consumes one seed step
        return dom switch
        {
            HEAT => (+0.15, 0.55),
            AQUA => (0.00, 0.35),                 // WATER (ice/frost share this channel; sparse feel comes from KnobTable Dens)
            TERRA => (sign * 0.55, 0.10),         // EARTH: one dominant lane, seed-signed
            GROVE => (-0.10, 0.40),
            UMBRA => (sign * 0.30, 0.35),         // SHADOW: seed-signed lane (hidden); RISK via impurity swing, NOT speed
            AIR => (+0.20, 0.60),
            _ => (0.00, 0.35),
        };
    }

    // §2.3 modifier riders — presence-tested against the pool counts; deltas clamped to the §2 field ranges.
    private void ApplyRiders(RefiningProfile p, IReadOnlyDictionary<string, int> counts, ref ulong seed)
    {
        bool Has(string t) => counts.ContainsKey(t);
        if (Has("sharp")) { p.Dbl = Math.Clamp(p.Dbl + 0.15, 0, 0.6); _sharpInPool = true; }
        if (Has("chaos") || Has("dangerous"))
        {
            p.Inter = Math.Clamp(p.Inter + 0.15, 0, 1);
            p.Dbl = Math.Clamp(p.Dbl + 0.10, 0, 0.6);
            _patternJitter = Math.Min(0.45, _patternJitter + 0.15);
        }
        if (Has("layered")) p.Inter = Math.Clamp(p.Inter + 0.20, 0, 1);
        _temporalInPool = Has("temporal");     // consumed per-gate in BuildGate (seed-chosen ~half gates get TempoDip)
        _toxicInPool = Has("poison") || Has("venom") || Has("toxic") || Has("acid");   // corrupt gate: impurity leaks (§4.5a)
        // seed threaded through so per-gate TempoDip choices stay deterministic (they are consumed in BuildGate).
    }

    // ============================================================ §4.1 GATE BUILD
    private Gate BuildGate(int g)
    {
        var gate = new Gate
        {
            Index = g,
            BeatsPerSecond = Math.Min(_bps0 * Math.Pow(_tempoRamp, g), BpsMax),
            LaneTint = _ingotBodyCol,
            PatternName = PatternNameFor(_domChannel),
            TempoDip = _temporalInPool && (SeedBit(ref _seed) == 0UL),   // temporal marks ~half the gates (deterministic per gate)
        };

        // strikeCount = round(clamp(BaseStrikes + DensTerm + GateTerm, 8, 20))
        double densTerm = 6 * (_profile.Dens - 0.6);
        double gateTerm = 1.2 * g;
        int strikeCount = (int)Math.Round(Math.Clamp(BaseStrikes + densTerm + gateTerm, 8, 20));

        int primaryLanes = _laneCount - 1;               // last lane (Space accent) is NOT part of the finger rotation
        int accentLane = _laneCount - 1;

        double baseGap = Math.Clamp(1.0 / Math.Max(1e-6, _profile.Dens), 0.55, 1.5);
        double b = BreatherBeats;
        int curLane = 0;
        int runLen = 0;
        for (var i = 0; i < strikeCount; i++)
        {
            // gap for THIS strike (strike 0 sits at BreatherBeats, no preceding gap)
            if (i > 0)
            {
                double gap = baseGap * (1 + _patternJitter * (Hash01(_seed, g, i) - 0.5));
                gap = Math.Clamp(gap, MinGapBeats, 1.6);
                b += gap;
            }

            // lane assignment (§4.1 — now across 1..4 primary finger lanes)
            if (i == 0)
            {
                curLane = PickStartLane(g, primaryLanes);
                runLen = 1;
            }
            else
            {
                bool flip = Hash01(_seed, g, i) < _profile.Inter;   // interleave roll
                if (runLen >= 4) flip = true;                       // FORCED flip: never a 5th identical-lane in a row
                if (flip) { curLane = PickOtherLane(curLane, primaryLanes, g, i); runLen = 1; }
                else runLen++;
            }

            var strike = new Strike { Lane = curLane, Beat = b };

            // DoubleTap: schedule a paired sub-strike at Beat + 0.25, SAME lane.
            if (Hash01(_seed, g, i, 'd') < _profile.Dbl)
            {
                strike.DoubleTap = true;
                gate.Strikes.Add(strike);
                gate.Strikes.Add(new Strike { Lane = curLane, Beat = b + 0.25 });
            }
            else
            {
                gate.Strikes.Add(strike);
            }
        }

        // AvgGap (primary span) computed BEFORE accents are folded in, so tempo maths ignore the spine.
        gate.AvgGap = (b - BreatherBeats) / Math.Max(1, strikeCount - 1);
        if (gate.AvgGap <= 0) gate.AvgGap = baseGap;

        // --- Space accent spine: one downbeat note per measure, snapped clear of any finger note ---
        double lastBeat = b;
        for (double t = BreatherBeats + AccentPeriodBeats; t <= lastBeat + 0.01; t += AccentPeriodBeats)
        {
            bool clear = true;
            foreach (var s in gate.Strikes)
                if (Math.Abs(s.Beat - t) < MinGapBeats) { clear = false; break; }
            if (clear) gate.Strikes.Add(new Strike { Lane = accentLane, Beat = t, IsAccent = true });
        }

        gate.Strikes.Sort((x, y) => x.Beat.CompareTo(y.Beat));
        return gate;
    }

    private static string PatternNameFor(int ch) => ch switch
    {
        HEAT => "Ember Burst",
        AQUA => "Cleansing Flow",
        TERRA => "Anvil Steady",
        GROVE => "Verdant Weave",
        UMBRA => "Umbral Corrupt",
        AIR => "Zephyr Taps",
        _ => "Fold",
    };

    // ============================================================ START PLAY
    private void StartPlay()
    {
        if (_phase != Phase.Ready) return;
        _readyBox.Visible = false;
        _phase = Phase.Play;
        _gateClock = 0;
        EnterGate(0);
    }

    private void EnterGate(int idx)
    {
        _gateIdx = idx;
        _gate = _gates[idx];
        _gateClock = 0;
        _gateBeat = 0;
        _gateBeatPrev = 0;
        _gateForgaveMiss = false;
        _nextStrike = 0;
        _windowBeats = _windowSec * _gate.BeatsPerSecond;
        if (idx > 0)
            Popup(_rail, new Vector2(RailW * 0.5f, 60f), $"FOLD {idx + 1}", Accent, 24);
        _dev.Log($"FOLD {idx + 1} · pattern={_gate.PatternName} · bps={_gate.BeatsPerSecond:0.00} · strikes={_gate.Strikes.Count}{(_gate.TempoDip ? " · dip" : "")}");
    }

    // ============================================================ §4.2/§4.3/§4.5a TICK
    protected override void OnTick(double delta)
    {
        _anim += delta;
        for (var l = 0; l < _flashLane.Length; l++) _flashLane[l] = Math.Max(0, _flashLane[l] - delta * 4);

        if (_phase == Phase.Settle)
        {
            _settleT -= delta;
            if (_settleT <= 0)
            {
                _phase = Phase.Done;
                double raw = _score / Math.Max(1e-6, _scoreMax);
                double perf = Math.Clamp(raw, 0, 1);
                _dev.Log($"RESULT: {MinigameTagEffects.RarityFromPerf(perf).Name} — perf {perf * 100:0}%  maxStreak={_maxStreak}  imp={_impurity:0.00}");
                Finish(perf);
                return;
            }
            _rail.QueueRedraw();
            return;
        }

        if (_phase != Phase.Play) { _rail.QueueRedraw(); return; }

        // safety backstop (a normal run ends by strike exhaustion well under this)
        _settleTimeAccum += delta;
        if (_settleTimeAccum >= TimeBackstop) { EnterSettle(); return; }
        SetTimer(Math.Max(0, TimeBackstop - _settleTimeAccum), 12);

        _gateClock += delta;
        double bps = _gate.BeatsPerSecond;
        if (_gate.TempoDip)
        {
            double dipSpan = 0.4 * (_gate.Strikes.Count - 1) * _gate.AvgGap;
            bps *= Mathf.Lerp(0.8f, 1.0f, (float)Math.Clamp(_gateBeat / Math.Max(0.001, dipSpan), 0, 1));
        }
        _gateBeat = _gateClock * bps;
        _windowBeats = _windowSec * bps;

        // --- §4.3 auto-miss sweep (before input) ---
        while (_nextStrike < _gate.Strikes.Count)
        {
            var s = _gate.Strikes[_nextStrike];
            if (s.Judged) { _nextStrike++; continue; }
            if (_gateBeat > s.Beat + _windowBeats) { Judge(s, Grade.Miss, input: false); _nextStrike++; }
            else break;
        }

        // --- §4.5a toxic corrupt gate: impurity leaks over time (reads _gateBeatPrev; does NOT advance it) ---
        if (_toxicInPool)
        {
            double beatsThisFrame = Math.Max(0.0, _gateBeat - _gateBeatPrev);
            _impurity = Math.Clamp(_impurity + ImpLeakPerBeat * beatsThisFrame, 0, 1);
            _purity = 1 - _impurity;
        }

        // --- §9 roadblock 4: metronome click on every integer-beat crossing (advances _gateBeatPrev ONCE) ---
        if (Math.Floor(_gateBeat) != Math.Floor(_gateBeatPrev)) PlayBeatTick();
        _gateBeatPrev = _gateBeat;

        // --- advance / settle when every strike of the gate is judged ---
        if (AllJudged()) AdvanceGateOrSettle();

        SetHeaderSub($"FOLD {_gateIdx + 1}/{_nFolds} · combo {_streak} · {_gate.PatternName}");
        _rail.QueueRedraw();
    }

    private double _settleTimeAccum;

    private bool AllJudged()
    {
        for (var i = 0; i < _gate.Strikes.Count; i++) if (!_gate.Strikes[i].Judged) return false;
        return true;
    }

    private void AdvanceGateOrSettle()
    {
        if (_gateIdx + 1 >= _nFolds) { EnterSettle(); return; }
        _dev.Log($"CLEAR fold {_gateIdx + 1}  score={_score:0.0}/{_scoreMax:0.0}  imp={_impurity:0.00}");
        EnterGate(_gateIdx + 1);
    }

    private void EnterSettle()
    {
        _phase = Phase.Settle;
        _settleT = SettleDur;
        HideTimer();
        var ingotC = IngotRect.GetCenter();
        Burst(_rail, ingotC, Accent, 36, 260f);
        Burst(_rail, ingotC, Colors.White, 20, 200f);
        FlashQuality();
        Shake(8f);
        _dev.Log($"SETTLE  score={_score:0.0}/{_scoreMax:0.0}  purity={_purity:0.00}");
    }

    // ============================================================ §5 INPUT
    // F1/F7 MUST be claimed in _Input — it is the FIRST input phase, ahead of _UnhandledInput, where CombatWorld's
    // global debug handler eats F1 (the ghost-inventory toggle) + SetInputAsHandled. Using _UnhandledKeyInput here
    // (a LATER phase) let the world swallow F1 first — the reaction log never toggled. This matches the other four minigames.
    public override void _Input(InputEvent @event)
    {
        if (!Running) return;   // the overlay is a persistent (hidden) node — WITHOUT this, its _Input claims F1/F7
                                // even when this minigame isn't active, stealing F1 from the world's global debug handler.
        if (@event is not InputEventKey { Pressed: true, Echo: false } k) return;
        if (_dev.HandleKey(k.PhysicalKeycode)) { _rail.QueueRedraw(); GetViewport().SetInputAsHandled(); }
    }

    protected override void OnInput(InputEvent @event)
    {
        if (_dev.NotesEditHasFocus) return;   // typing a note must NOT judge strikes
        if (@event is not InputEventKey { Pressed: true, Echo: false } k) return;
        Key key = k.PhysicalKeycode;

        if (_phase == Phase.Ready)
        {
            if (key == Key.Space) { StartPlay(); GetViewport().SetInputAsHandled(); }
            return;
        }
        if (_phase != Phase.Play) return;

        // KEYBOARD ONLY — mouse is gone (its clicks were eaten by the overlay's GUI panel before
        // reaching gameplay). Each physical key drives its lane; Space plays the accent lane.
        for (var i = 0; i < _laneCount; i++)
            if (_laneKeys[i] == key) { JudgeLane(i); GetViewport().SetInputAsHandled(); return; }
    }

    // ============================================================ §4.4 INPUT JUDGING
    private void JudgeLane(int lane)
    {
        double grabMargin = 0.5 * _windowBeats;
        Strike? best = null;
        double bestD = double.PositiveInfinity;
        foreach (var s in _gate.Strikes)
        {
            if (s.Judged || s.Lane != lane) continue;
            double d = Math.Abs(_gateBeat - s.Beat);
            if (d <= _windowBeats + grabMargin && d < bestD) { best = s; bestD = d; }
        }

        if (best == null)
        {
            // ghost tap — no score change, dull burst, streak reset (anti-spam)
            _streak = 0;
            Burst(_rail, new Vector2(HitLineX, LaneY(lane)), new Color(0.45f, 0.42f, 0.4f), 5, 70f);
            return;
        }

        double r = bestD / Math.Max(1e-6, _windowBeats);   // 0 at dead-centre, 1 at window edge
        Grade grade = r <= PerfectFrac ? Grade.Perfect : r <= _closeFrac ? Grade.Close : r <= _okayFrac ? Grade.Okay : Grade.Miss;
        best.HitAtBeat = _gateBeat;
        Judge(best, grade, input: true);
    }

    // ============================================================ §4.5 SCORING A JUDGED STRIKE
    private void Judge(Strike s, Grade grade, bool input)
    {
        s.Judged = true;
        s.Result = grade;

        double pts = grade switch
        {
            Grade.Perfect => PtsPerfect + (_sharpInPool ? SharpPerfectBonus : 0),
            Grade.Close => PtsClose,
            Grade.Okay => PtsOkay,
            _ => PtsMiss,
        };

        if (grade is Grade.Perfect or Grade.Close)
        {
            _streak++;
            if (s.IsAccent) _streak += (int)AccentPerfectStreak;   // a clean downbeat accent drives the combo harder
        }
        else if (grade == Grade.Okay) { /* hold streak, no growth */ }
        else _streak = 0;   // Miss (input or auto) breaks it
        _maxStreak = Math.Max(_maxStreak, _streak);

        double streakMul = 1 + Math.Min(_streak * StreakStep, StreakCap);   // 1.00 .. 1.60
        _score += pts * streakMul * _profile.Rich;

        // impurity
        double impDelta = grade switch
        {
            Grade.Perfect => -ImpDrainPerfect,
            Grade.Close => -ImpDrainClose,
            Grade.Okay => -ImpDrainOkay,
            _ => +ImpBumpMiss,
        };
        if (grade == Grade.Miss && _profile.WaterForgive && !_gateForgaveMiss) { impDelta = 0; _gateForgaveMiss = true; }
        _impurity = Math.Clamp(_impurity + impDelta, 0, 1);
        _purity = 1 - _impurity;

        SetQuality(Math.Clamp(_score / Math.Max(1e-6, _scoreMax), 0, 1));
        PlayHitSfx(grade);

        // feedback (§6.5)
        var (col, name) = GradeVisual(grade);
        _lastGradeCol = col;
        int lane = s.Lane;
        float y = LaneY(lane);
        var hitAt = new Vector2(HitLineX, y);
        if (grade != Grade.Miss)
        {
            _flashLane[lane] = s.IsAccent ? 1.4 : 1.0;   // accents flash brighter
            Popup(_rail, new Vector2(HitLineX, y - 24), name, col, grade == Grade.Perfect ? 26 : 20);
            int baseCount = grade == Grade.Perfect ? 12 : 8;
            Burst(_rail, hitAt, col, s.IsAccent ? baseCount + 8 : baseCount, 150f + (int)grade * 30f + (s.IsAccent ? 60f : 0f));
            if (grade == Grade.Perfect || s.IsAccent)
            {
                Burst(_rail, hitAt, Colors.White, s.IsAccent ? 20 : 16, 200f);
                FlashQuality();
                Shake(s.IsAccent ? 6f : 4f);
            }
        }
        else
        {
            Shake(3f);
            if (input) _dev.Log($"MISS {(s.IsAccent ? "accent" : "lane " + KeyGlyph(_laneKeys[s.Lane]))} beat={s.Beat:0.0}");
        }
    }

    private static (Color Col, string Name) GradeVisual(Grade g) => g switch
    {
        Grade.Perfect => (UiTheme.Rarity["legendary"], "PERFECT"),
        Grade.Close => (UiTheme.Rarity["rare"], "CLOSE"),
        Grade.Okay => (new Color(0.98f, 0.78f, 0.42f), "OKAY"),
        _ => (MissRed, "MISS"),
    };

    // ============================================================ §9 AUDIO HOOKS (empty today)
    private void PlayHitSfx(Grade grade) { /* TODO: AudioStreamPlayer per-grade */ }
    private void PlayBeatTick() { /* TODO: metronome click */ }

    // ============================================================ §6 DRAW
    private void DrawRail()
    {
        var font = _rail.GetThemeDefaultFont();

        // (1) rail backdrop plate — a dark warm trough (RailRect grown 10px each side)
        var plate = new Rect2(RailRect.Position - new Vector2(10, 10), RailRect.Size + new Vector2(20, 20));
        CraftFx.RoundRect(_rail, plate, new Color(0.10f, 0.08f, 0.06f), new Color(Accent.R, Accent.G, Accent.B, 0.5f), 2, 10);

        float railLeft = RailRect.Position.X;
        float railRight = RailRect.Position.X + RailRect.Size.X;
        float railTop = RailRect.Position.Y;
        float railBottom = RailRect.Position.Y + RailRect.Size.Y;
        float railMidY = (railTop + railBottom) * 0.5f;

        // (2) one guide per lane + a KEY badge at the far left (W/D/O/K … SPACE accent, brighter)
        for (var i = 0; i < _laneCount; i++)
        {
            float ly = LaneY(i);
            var lc = LaneColor(i);
            bool accent = IsAccentLane(i);
            _rail.DrawLine(new Vector2(railLeft, ly), new Vector2(railRight, ly),
                new Color(lc.R, lc.G, lc.B, accent ? 0.40f : 0.22f), accent ? 4f : 3f);
            string glyph = KeyGlyph(_laneKeys[i]);
            float bw = accent ? 52f : 26f;
            var badge = new Rect2(railLeft - bw - 8, ly - 11, bw, 22);
            CraftFx.RoundRect(_rail, badge, new Color(lc.R * 0.22f, lc.G * 0.22f, lc.B * 0.22f, 0.92f), lc, accent ? 2 : 1, 5);
            _rail.DrawString(font, new Vector2(badge.Position.X + 5, ly + 5), glyph, HorizontalAlignment.Left, (int)bw, accent ? 11 : 14, lc);
        }

        // (3) gate LaneTint wash over RailRect
        if (_phase == Phase.Play || _phase == Phase.Settle)
        {
            var t = _gate.LaneTint;
            _rail.DrawRect(RailRect, new Color(t.R, t.G, t.B, 0.06f));
        }

        // (3.5) GHOST BEAT GRID — faint vertical bars at EVERY integer beat, scrolling with the rail, so the
        // player can see & feel the tempo and read patterns. Notes need NOT sit on these; it's a reference only.
        // Downbeats (start of each measure) are brighter to anchor the pulse.
        if (_phase == Phase.Play)
        {
            for (int bg = (int)Math.Floor(_gateBeat); bg <= _gateBeat + RailScrollBeats + 1; bg++)
            {
                if (bg < 0) continue;
                float gx = HitLineX + (float)((bg - _gateBeat) * BeatPx);
                if (gx < railLeft - 1 || gx > railRight + 1) continue;
                bool downbeat = ((bg - (int)BreatherBeats) % (int)AccentPeriodBeats) == 0;
                var gcol = downbeat ? new Color(1f, 1f, 1f, 0.16f) : new Color(1f, 1f, 1f, 0.06f);
                _rail.DrawLine(new Vector2(gx, railTop + 2), new Vector2(gx, railBottom - 2), gcol, downbeat ? 2f : 1f);
            }
        }

        // (4) hit line + soft glow + drawn markers (procedural triangles — no glyph fonts to go tofu)
        _rail.DrawLine(new Vector2(HitLineX, railTop), new Vector2(HitLineX, railBottom), new Color(1, 1, 1, 0.9f), 3f);
        float breatheR = 22f + 3f * Mathf.Sin((float)_anim * 6f);
        CraftFx.Glow(_rail, new Vector2(HitLineX, railMidY), breatheR, new Color(Accent.R, Accent.G, Accent.B, 0.5f));
        _rail.DrawColoredPolygon(new[] { new Vector2(HitLineX - 7, railTop - 9), new Vector2(HitLineX + 7, railTop - 9), new Vector2(HitLineX, railTop + 1) }, new Color(1, 1, 1, 0.8f));
        _rail.DrawColoredPolygon(new[] { new Vector2(HitLineX - 7, railBottom + 9), new Vector2(HitLineX + 7, railBottom + 9), new Vector2(HitLineX, railBottom - 1) }, new Color(1, 1, 1, 0.8f));

        // combo HEAT — the hit line burns hotter as the streak climbs (visual only)
        float heat = Mathf.Clamp(_streak / 14f, 0f, 1f);
        if (heat > 0.01f)
        {
            var hot = new Color(1f, 0.55f + 0.2f * heat, 0.25f, 0.35f + 0.4f * heat);
            _rail.DrawLine(new Vector2(HitLineX, railTop), new Vector2(HitLineX, railBottom), hot, 3f + 3f * heat);
            CraftFx.Glow(_rail, new Vector2(HitLineX, railMidY), breatheR + 14f * heat, new Color(1f, 0.6f, 0.3f, 0.3f * heat));
        }
        // on-beat metronome pulse (visual only) — a ring that fires each integer beat and decays
        if (_phase == Phase.Play)
        {
            float beatFrac = (float)(_gateBeat - Math.Floor(_gateBeat));
            float pulse = 1f - Math.Clamp(beatFrac / 0.35f, 0f, 1f);
            if (pulse > 0.02f)
                CraftFx.Ring(_rail, new Vector2(HitLineX, railMidY), 16f + 40f * (1f - pulse), new Color(1f, 1f, 1f, 0.28f * pulse), 2f);
        }

        // (5) upcoming strikes + (6) window bracket
        if (_phase == Phase.Play)
        {
            // window bracket at the hit line for the current strike's lane
            if (_nextStrike < _gate.Strikes.Count)
            {
                float wy = LaneY(_gate.Strikes[_nextStrike].Lane);
                float wx = (float)(_windowBeats * BeatPx);
                _rail.DrawLine(new Vector2(HitLineX - wx, wy - 10), new Vector2(HitLineX - wx, wy + 10), new Color(1, 1, 1, 0.18f), 2f);
                _rail.DrawLine(new Vector2(HitLineX + wx, wy - 10), new Vector2(HitLineX + wx, wy + 10), new Color(1, 1, 1, 0.18f), 2f);
            }

            foreach (var s in _gate.Strikes)
            {
                if (s.Judged) continue;
                double ahead = s.Beat - _gateBeat;
                if (ahead > RailScrollBeats || ahead < -0.5) continue;   // cull off-runway
                float x = HitLineX + (float)(ahead * BeatPx);
                if (x < railLeft || x > railRight) continue;
                float y = LaneY(s.Lane);
                var laneCol = LaneColor(s.Lane);
                float alpha = (float)Math.Clamp((RailScrollBeats - ahead) / (RailScrollBeats * 0.2), 0, 1);
                // Tokens are VERTICAL BARS (not circles): the bar's bright core line marks the EXACT beat,
                // so the moment it overlaps the hit line = hit-now. Same read for every token = learnable timing.
                var barCol = new Color(laneCol.R, laneCol.G, laneCol.B, alpha);
                // motion trail behind the bar (scrolls toward the hit line → it came from higher x)
                float trailLen = 20f + 12f * (float)Math.Min(1.0, _gate.BeatsPerSecond / BpsMax);
                CraftFx.Streak(_rail, new Vector2(x + trailLen, y), new Vector2(x, y), new Color(laneCol.R, laneCol.G, laneCol.B, 0.16f * alpha), 4f);
                if (s.IsAccent)
                {
                    const float halfH = 20f, barW = 8f;   // accent = wider/taller bar (still a bar — consistent read)
                    _rail.DrawRect(new Rect2(x - barW * 0.5f, y - halfH, barW, halfH * 2), barCol);
                    _rail.DrawLine(new Vector2(x, y - halfH), new Vector2(x, y + halfH), new Color(1, 1, 1, 0.85f * alpha), 2f);
                }
                else
                {
                    const float halfH = 15f, barW = 5f;
                    _rail.DrawRect(new Rect2(x - barW * 0.5f, y - halfH, barW, halfH * 2), barCol);
                    _rail.DrawLine(new Vector2(x, y - halfH), new Vector2(x, y + halfH), new Color(1, 1, 1, 0.7f * alpha), 1.5f);
                }
                if (s.DoubleTap)
                {
                    float p2x = x + 0.25f * BeatPx;
                    CraftFx.Streak(_rail, new Vector2(x, y), new Vector2(p2x, y), barCol, 1.5f);
                    _rail.DrawRect(new Rect2(p2x - 2f, y - 10f, 4f, 20f), new Color(laneCol.R, laneCol.G, laneCol.B, alpha * 0.8f));
                }
            }
        }

        // (8) lane hit flash
        for (var l = 0; l < _laneCount; l++)
        {
            if (_flashLane[l] <= 0) continue;
            float y = LaneY(l);
            float rad = 18f + 10f * (float)_flashLane[l];
            CraftFx.Glow(_rail, new Vector2(HitLineX, y), rad,
                new Color(_lastGradeCol.R, _lastGradeCol.G, _lastGradeCol.B, 0.5f * (float)Math.Min(1.0, _flashLane[l])));
        }

        // (9) impurity bar
        DrawImpurityBar(font);

        // (10) the ingot
        DrawIngot();

        // (11) HUD row
        DrawHud(font);

        // (12) F1 dev log overlay (painted LAST, top z-order)
        if (_dev.ShowLog)
        {
            var logRect = new Rect2(RailW - 250, 8, 244, RailH - 16);
            _dev.DrawLog(_rail, logRect, font, BuildPinned());
        }
    }

    private void DrawImpurityBar(Font font)
    {
        var fillCol = _toxicInPool ? ToxicCol : ImpFillCol;
        CraftFx.Bar(_rail, ImpBarRect, (float)_impurity, new Color(0.06f, 0.05f, 0.04f), fillCol);
        string label = _toxicInPool ? "IMPURITY (!)" : "IMPURITY";   // spec §6.2 warn tell; ASCII marker honours the no-emoji rule
        var labCol = _toxicInPool ? new Color(ToxicCol.R, ToxicCol.G, ToxicCol.B, 0.9f) : new Color(Accent.R, Accent.G, Accent.B, 0.8f);
        _rail.DrawString(font, new Vector2(ImpBarRect.Position.X, ImpBarRect.Position.Y - 4), label, HorizontalAlignment.Left, 200, 12, labCol);
        if (_toxicInPool)
        {
            float fillRightX = ImpBarRect.Position.X + ImpBarRect.Size.X * (float)_impurity;
            float barMidY = ImpBarRect.Position.Y + ImpBarRect.Size.Y * 0.5f;
            CraftFx.Wisp(_rail, new Vector2(fillRightX, barMidY), Vector2.Up, 14f,
                new Color(ToxicCol.R, ToxicCol.G, ToxicCol.B, 0.35f), (float)_anim);
        }
    }

    private void DrawIngot()
    {
        var c = IngotRect.GetCenter();
        float rad = Math.Min(IngotRect.Size.X, IngotRect.Size.Y) * 0.45f;
        var dark = CraftColor.Darken(_ingotBodyCol, 0.6f);
        var light = CraftColor.Brighten(_ingotBodyCol, 0.3f * (float)_purity);
        CraftColor.RadialGrad(_rail, c, rad, new Vector2(-rad * 0.3f, -rad * 0.35f), dark, light);

        // fold-by-fold: each cleared gate adds a subtle fold-line highlight across the ingot
        int cleared = _phase == Phase.Settle ? _nFolds : _gateIdx;
        for (var i = 0; i < cleared && i < _nFolds; i++)
        {
            float fy = IngotRect.Position.Y + 26 + i * (IngotRect.Size.Y - 40) / Math.Max(1, _nFolds);
            _rail.DrawLine(new Vector2(IngotRect.Position.X + 12, fy), new Vector2(IngotRect.Position.X + IngotRect.Size.X - 12, fy),
                new Color(Accent.R, Accent.G, Accent.B, 0.4f), 1.5f);
        }

        // high-purity halo pulse
        if (_purity > 0.7)
        {
            float pulse = 0.3f * Mathf.Abs(Mathf.Sin((float)_anim * 3f));
            CraftFx.Glow(_rail, c, rad * 1.1f, new Color(Accent.R, Accent.G, Accent.B, pulse * (float)_purity));
        }

        // settle flourish ring
        if (_phase == Phase.Settle)
        {
            float phase = (float)(1 - _settleT / SettleDur);
            CraftFx.RingPulse(_rail, c, 40, phase, Accent);
        }
    }

    private void DrawHud(Font font)
    {
        // left: FOLD n / N
        int foldShow = _phase == Phase.Settle ? _nFolds : _gateIdx + 1;
        _rail.DrawString(font, new Vector2(RailRect.Position.X, HudY), $"FOLD {foldShow} / {_nFolds}", HorizontalAlignment.Left, 160, 15, Accent);

        // centre: COMBO ×k (glows when streak >= 3)
        if (_streak >= 1)
        {
            var comboCol = Accent.Lerp(Colors.White, Math.Clamp(_streak / 25f, 0f, 1f));
            float glowPulse = _streak >= 5 ? 0.5f + 0.5f * Mathf.Sin((float)_anim * 8f) : 1f;
            if (_streak >= 3)
                CraftFx.Glow(_rail, new Vector2(RailW * 0.5f, HudY + 6), 12f * glowPulse, new Color(comboCol.R, comboCol.G, comboCol.B, 0.4f));
            _rail.DrawString(font, new Vector2(RailW * 0.5f - 60, HudY), $"COMBO ×{_streak}", HorizontalAlignment.Center, 120, 15, comboCol);
        }
    }

    // ============================================================ DEV LOG GLUE
    private IEnumerable<string> BuildLogHeader()
    {
        yield return $"output={Recipe?.OutputId ?? "(debug sampler)"}  tier={Recipe?.Tier ?? DifficultyTier}  points={Recipe?.Points ?? DifficultyPoints:0.#}";
        yield return $"folds={_nFolds}  bps0={_bps0:0.00}  ramp={_tempoRamp:0.000}  window={_windowSec:0.000}s  dominant={ChannelName(_domChannel)}";
        yield return $"knobs: Dens={_profile.Dens:0.00} LaneBias={_profile.LaneBias:0.00} Inter={_profile.Inter:0.00} Dbl={_profile.Dbl:0.00} Imp={_profile.Imp:0.00} Rich={_profile.Rich:0.00}";
        yield return $"riders: sharp={_sharpInPool} temporal={_temporalInPool} toxic={_toxicInPool} waterForgive={_profile.WaterForgive} jitter={_patternJitter:0.00}";
        yield return "ingredients:";
        if (Recipe?.Inputs is { Count: > 0 } inp)
            foreach (var ing in inp) yield return $"  {ing.Name}  t{ing.MaterialTier} x{ing.Qty}  [{string.Join(",", ing.Tags)}]";
        else
            yield return "  (synthetic debug ingredient)";
    }

    private void OnDevNote(string text)
    {
        var snap = new List<string>
        {
            $"phase={_phase} fold={_gateIdx + 1}/{_nFolds} beat={_gateBeat:0.0} window={_windowBeats:0.00}b",
            $"score={_score:0.0}/{_scoreMax:0.0}  combo={_streak} (max {_maxStreak})  impurity={_impurity:0.00}",
        };
        _dev.Note(text, snap);
    }

    private IReadOnlyList<(string, Color)> BuildPinned()
    {
        return new List<(string, Color)>
        {
            ($"fold {_gateIdx + 1}/{_nFolds}  {_gate?.PatternName}", Accent),
            ($"bps {(_gate?.BeatsPerSecond ?? 0):0.00}  win {_windowBeats:0.00}b", EmberCol),
            ($"score {_score:0.0}/{_scoreMax:0.0}  combo {_streak}", UiTheme.Rarity["rare"]),
            ($"impurity {_impurity:0.00}{(_toxicInPool ? " (toxic leak)" : "")}", _toxicInPool ? ToxicCol : ImpFillCol),
        };
    }
}
