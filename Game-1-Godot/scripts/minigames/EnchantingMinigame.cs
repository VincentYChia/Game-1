using Godot;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace Game1.Godot;

/// <summary>
/// ENCHANTING â€” "Sigil Rush" (top-down, camera-follows, a rune that DRAWS ITSELF while you time clicks on it).
///
/// ROUND-4 REWORK (player feedback verbatim): "Enchanting is a bit messy still. Forking is not possible either,
/// because the clicks are now actually used for clicking targets. Instead let's have most nodes be normal and then
/// have some special color coded nodes. These color coded nodes will all have a standard effect (the size/hue/
/// intensity/maybe additional visual features) for easy readability. That way space bars are less commonly needed and
/// the primary mechanism is the clicks. In order to help the user click more accurately let's also not have the
/// viewing window move in the last 20% of distance to the node."
///
/// THE MINIGAME NOW (simplified â€” a clean LINEAR path, NO forks):
///   â€¢ The PEN HEAD travels on its own along the real sigil at the current <c>_speed</c>, drawing the rune as it goes
///     (imprinted-gold behind it, dim ahead). The camera follows the pen head â€” EXCEPT it HOLDS still during the last
///     20% of the approach to each node, so the click target is STATIONARY under the cursor when you press.
///   â€¢ CLICK is the PRIMARY, and the ONLY input most of the time: on/near each node as the line arrives. A clean
///     click â†’ big compounding speed-up (<c>speed *= GROWTH_CLICK</c>); a miss â†’ a real slowdown.
///   â€¢ MOST nodes are NORMAL (pale-gold dots) â€” you just click them. A MINORITY are SPECIAL, color-coded by effect
///     family with a STANDARDISED visual language (hue + size + glow + an extra feature) so the effect is instantly
///     readable and always looks the same. On a SPECIAL you CLICK it (as normal, for the hit/speed) AND may press
///     SPACE (timed) to FIRE its effect (a big themed burst + a stack + a small speed nudge). Missing the SPACE on a
///     special is a harmless missed flourish (tiny/no penalty) â€” SPACE is optional and rare, CLICK stays primary.
///   â€¢ SCORE stays TIME-based + effect richness: perf = 0.70*TimeScore + 0.30*EffectRichness. Bands: masher ~0.25,
///     competent ~0.60, expert ~0.95. Reaching the end ALWAYS Finish()es once.
///   â€¢ BIG UI + PERSISTENT LEGEND stating the controls, a live SPEED gauge, and the stacked-effects list. Plain ASCII.
///
/// perf âˆˆ [0,1] is produced through the sacred seam and nothing else â€” Game1.Core is 0-diff. The tagâ†’profile
/// derivation is preserved verbatim and REUSED to shape BASE_SPEED / growth / node count / WHICH nodes are special +
/// their family / timing-window tolerance so tag THEMES stay consistent across minigames. The sigil is the real
/// pattern (procedural themed glyph via BuildSigilPolyline; ExtractPatternPoints seam stays), flip-up intro included.
/// </summary>
public partial class EnchantingMinigame : MinigameOverlay
{
    protected override string Discipline => "adornments";
    protected override bool FullscreenScene => true;
    protected override bool ShowAmbient => true;
    protected override (Color Top, Color Bottom, Color Glow)? BackdropTint =>
        (new Color(0.13f, 0.09f, 0.18f), new Color(0.04f, 0.03f, 0.07f), new Color(0.72f, 0.42f, 1.0f));

    // ==================================================================== Â§1 DATA MODEL

    // Â§1.2 challenge archetype (typed by tag theme, Â§2.1) â€” PRESERVED for the tagâ†’profile derivation (it shapes
    // stroke character + timing feel). internal so a headless test can reference the enum returned by ResolveNodeKind.
    internal enum NodeKind
    {
        SpikeRun, HoldStill, Glide, HeavyLeap, MovingHazard,
        BlindDash, TightGap, SlowMoDodge, ChaosGate, Plain,
    }

    // Â§1.3 one node = a VERTEX of the sigil, in stroke order. internal so a headless test can inspect BuildCourse.
    internal struct NodeSpec
    {
        public NodeKind Kind;
        public Vector2 Pos;         // px in WORLD space (larger than the screen; the camera reveals it)
        public int IndexOnRing;     // stroke order index
        public int Family;          // 0..5 channel const â†’ colour + themed effect
        public int Tier;            // 1..4
        public double HazardWindow; // s, 0.18..1.20 â€” REUSED as the node's input TIMING TOLERANCE
        public double HazardSpeed;  // hazard tempo multiplier (kept for derivation coherence)
        public double Reward;       // per-node score weight
        public uint SeedSalt;
        public string Label;        // material name (F1 log only)
        public bool IsSpecial;      // a color-coded SPECIAL node: click as normal + optional SPACE fires its effect
    }

    // Â§3 state machine
    private enum Phase { Ready, Plan, Trace, Settle, Done }

    // input-timing grade (per node, per input) --------------------------------
    private enum Grade { None, Perfect, Good, Miss }

    // Â§1.6 the whole run (single instance, reset each OnBegin)
    private List<NodeSpec> _nodes = new();   // the LINEAR node list, in stroke order (no forks)
    private List<Edge> _edges = new();       // consecutive edges over _nodes (the traced path)
    private double _totalArc;                 // arc-length of the whole path (world px)
    private double _paceArc;                  // pen-head arc-length so far
    private int _totalMainlineNodes;          // node count the player traverses

    // Â§1.4 stroke edge between two consecutive vertices
    internal struct Edge { public int A, B; public float Length; }

    // ---- SPEED (the core resource â€” compounds) ----
    private double _speed;                    // px/s along the sigil; starts BASE_SPEED, *= growth on clean CLICKS
    private int _cleanStreak;                 // consecutive clean CLICK hits (juice)

    // node input tracking -----------
    private int _nodesResolved;               // nodes whose window has closed (attempted or auto-missed)
    private int _clickCleanHits;              // Perfect/Good clicks
    private int _clickMisses;                 // click misses (auto or bad press)
    private int _spaceCleanHits;              // Perfect/Good spaces (special effects fired)
    private int _spaceMisses;                 // space misses on specials (harmless)
    private int _nextNode;                    // index of the next node the pen head will cross

    // ---- STACKED THEMED EFFECTS ----
    // effect index 0..5 aligned with the channel constants (HEAT..AIR). Count = stacks.
    private readonly int[] _effectStacks = new int[MinigameTagEffects.N];
    private int _effectTotal;                 // Î£ stacks (drives richness + the running list)
    private double _effectFlash;              // >0 briefly after an effect stacks (juice)
    private int _lastEffectCh = -1;

    private Phase _phase = Phase.Ready;
    private double _runClock;                 // seconds spent TRACING (the score clock)
    private double _settleClock;
    private double _planClock;
    private double _anim;
    private double _sealFlash;                // >0 briefly after a good node imprint
    private Vector2 _sealFlashPos;
    private RandomNumberGenerator _rng = new();

    // Â§1.8 difficulty-interpolated params (set once in OnBegin via Interp)
    private double _windowScale;              // multiplies every node's timing tolerance (tighter with points)
    private int _nodeCountBias;
    private double _hazardSpeedGlobal;
    private double _parTime;                  // difficulty-scaled par time for the time score
    private double _baseSpeed;                // difficulty + tag scaled BASE_SPEED
    private double _growthClick;              // difficulty + tag scaled per-clean-click speed multiplier
    private double _maxSpeed;                 // clamp ceiling
    private double _specialFraction;          // ~ this fraction of nodes are color-coded specials

    // the tag-folded course character profile (Â§2)
    private MinigameModifierCommon.ModProfile _profile = new(6, 0);
    private int _dominantChannel = MinigameTagEffects.TERRA;

    // ==================================================================== Â§4.1 CONSTANTS
    private const double FLIP_DUR = 0.90;
    private const double PLAN_CAM_EASE = 1.10;   // camera eases to the sigil start over this window
    private const double PLAN_MAX_S = 5.00;      // free-look budget before auto-advance
    private const double SETTLE_DUR = 1.20;
    private const double HARD_CAP_S = 120.0;

    // SPEED tuning (the feel dials the player should tune) ----------------------------------
    private const double BASE_SPEED = 300.0;     // world px/s the pen head starts at (fast but readable)
    private const double GROWTH_CLICK = 1.14;    // clean CLICK (primary) â†’ *= this
    private const double GROWTH_SPACE = 1.05;    // clean SPACE on a special (optional flourish) â†’ small nudge
    private const double GOOD_FACTOR = 0.55;     // a GOOD (not Perfect) timing gets this fraction of the speed-up bonus
    private const double SPACE_MISS_MULT = 0.99; // a missed SPACE on a special â†’ a TINY slowdown (it's optional)
    private const double MAX_SPEED = 1150.0;     // clamp so it never becomes uncontrollable

    // per-node timing window: |timeError| bands. tol (seconds) comes from the node (tag/difficulty shaped). PERFECT is
    // the tight inner band, GOOD the full band; beyond â†’ Miss. Windows are opened as the pen head nears the node.
    private const double PERFECT_FRAC = 0.42;    // inner band = tol * this â†’ Perfect
    // click hit radius (world px, pre-scale) â€” a click must land within this of the node to count as "on the node"
    private const double CLICK_RADIUS = 82.0;

    // CAMERA HOLD (the key usability fix): freeze the camera during the LAST 20% of each segment's distance so the
    // node the player is about to click is STATIONARY. HOLD_FRAC 0.20 = "last 20% of the previousâ†’current distance".
    private const double HOLD_FRAC = 0.20;

    // Â§7 tier-gating thresholds (kept for node-count / richness scaling)
    private const double RARE_PTS = 21;

    // perf weights (Â§4 â€” TIME dominant, effect-richness rider)
    private const double W_TIME = 0.70;
    private const double W_RICHNESS = 0.30;

    // ==================================================================== Â§6.1 SURFACE
    private static readonly Vector2 DESIGN = new(1280, 720);
    private Control _surf = null!;
    private PanelContainer _readyBox = null!;
    private Label _readyLabel = null!;
    private Button _channelBtn = null!;
    private Label _hint = null!;
    private float _flip;                 // [0,1] eased flip-up transition (what DrawSurface reads)
    private float _flipRaw;              // [0,1] linear flip progress (driven in OnTick)
    private float _S = 1f;               // worldâ†’screen scale (surface fit)
    private Vector2 _origin = Vector2.Zero;
    private Vector2 _camWorld;           // WORLD point the camera centres on (eases to the pen head, HOLDS near nodes)

    // fx palette derived only from theme (Â§6)
    private static readonly Color Ink = new(1f, 0.82f, 0.32f);      // imprinted (gold) ink
    private static readonly Color Muddy = new(0.84f, 0.28f, 0.28f); // muddy (missed) inscription
    private static readonly Color NormalDot = new(0.94f, 0.86f, 0.58f); // pale-gold NORMAL node (neutral, quiet)

    // floating effect labels ("Ember!", "Frost!", ...) spawned on a fired effect ----
    private sealed class FloatLabel { public Vector2 World; public string Text = ""; public Color Col; public double Age; public double Life = 1.1; }
    private readonly List<FloatLabel> _floats = new();

    // [F1] event log + [F7] playtest notes (shared harness)
    private MinigameDevLog _dev = null!;

    // ==================================================================== Â§5.x EFFECT VOCABULARY (Â§2 Tag Theme Dictionary)
    // channel â†’ a consistent themed effect name (fire=Ember, water/ice=Frost, earth/metal=Ward, life=Vigor,
    // shadow=Hex, air=Gust). Kept a small consistent vocabulary aligned with the master plan Â§2.
    private static readonly string[] EffectName =
    { "Ember", "Frost", "Ward", "Vigor", "Hex", "Gust" };   // index == channel const HEAT..AIR

    // ==================================================================== Â§2.2 BASE TABLE
    // OUR OWN sigil-reinterpreted magnitude table (full vocabulary â€” every entry authored to Â§2).
    // Fields reinterpreted: Pot=Reward mult, Vol=timing-tolerance delta, Time=pace-speed mult, Rx=hazard tempo.
    private static readonly Dictionary<string, (double Pot, double Vol, double Time, double Rx)> _baseTable = new()
    {
        // ---- FIRE bodies (haste+aggression+volatility â†’ tighten tolerance, quicken pace, high tempo) ----
        ["fire"] = (1.00, -10, 1.15, 1.30), ["flame"] = (1.00, -9, 1.14, 1.25), ["ember"] = (1.00, -6, 1.10, 1.18),
        ["molten"] = (1.02, -12, 1.10, 1.35), ["forge"] = (1.02, -5, 1.08, 1.18), ["volcanic"] = (1.03, -13, 1.10, 1.40),
        // ---- ENERGETIC RIDERS on the fire axis (amplifier/wildcard riders, milder than a raw fire body) ----
        ["lightning"] = (1.02, -11, 1.25, 1.45), ["storm"] = (1.02, -9, 1.20, 1.30), ["radiant"] = (1.05, -4, 1.10, 1.12),
        ["chaos"] = (1.00, -16, 1.05, 1.55), ["light"] = (1.06, -4, 1.06, 1.10),
        // ---- WATER (flow, forgiving pole) ----
        ["water"] = (1.00, +8, 0.95, 0.85), ["aqua"] = (1.00, +8, 0.95, 0.85), ["liquid"] = (1.00, +6, 0.96, 0.88), ["solvent"] = (0.98, +5, 0.98, 0.95),
        // ---- COLD/ICE (still pole, largest tolerance-widen, slower pace + tempo) ----
        ["ice"] = (1.00, +12, 0.85, 0.68), ["frost"] = (1.00, +11, 0.86, 0.72), ["frozen"] = (1.00, +13, 0.83, 0.62), ["chill"] = (1.00, +9, 0.88, 0.78),
        // ---- EARTH/TERRA (solidity/resistance/mass) ----
        ["earth"] = (1.00, +6, 0.90, 0.80), ["stone"] = (1.00, +8, 0.88, 0.78), ["sand"] = (1.00, +4, 0.94, 0.90), ["mineral"] = (1.00, +6, 0.90, 0.80),
        // ---- metals (EARTH + hardness) ----
        ["metal"] = (1.02, +6, 0.90, 0.85), ["metallic"] = (1.05, +2, 0.95, 1.05), ["iron"] = (1.02, +6, 0.90, 0.90), ["steel"] = (1.06, +5, 0.90, 0.90),
        ["bronze"] = (1.04, +5, 0.91, 0.85), ["copper"] = (1.03, +5, 0.92, 0.90), ["tin"] = (1.02, +5, 0.92, 0.88), ["alloy"] = (1.10, +4, 0.94, 0.95),
        ["mithril"] = (1.14, +3, 0.98, 1.0), ["adamantine"] = (1.18, +7, 0.88, 0.90), ["silver"] = (1.08, +3, 0.94, 0.95), ["gold"] = (1.10, +3, 0.94, 0.95),
        ["orichalcum"] = (1.18, +2, 0.98, 1.05), ["crystal"] = (1.08, +5, 0.92, 0.88), ["gem"] = (1.10, +4, 0.93, 0.88),
        // ---- LIFE/GROVE (growth/vitality/spread â†’ livelier tempo, neutral tolerance) ----
        ["wood"] = (1.00, +2, 0.98, 1.02), ["oak"] = (1.00, +2, 0.98, 1.02), ["ash"] = (1.00, +2, 0.98, 1.02), ["ironwood"] = (1.04, +2, 0.96, 1.02),
        ["ebony"] = (1.03, +1, 0.97, 1.03), ["birch"] = (1.00, +2, 0.99, 1.02), ["willow"] = (1.00, +3, 0.99, 1.00), ["worldtree"] = (1.14, +1, 0.98, 1.05),
        ["exotic"] = (1.10, 0, 0.98, 1.08), ["plant"] = (1.02, +2, 0.98, 1.02), ["herb"] = (1.04, +2, 0.98, 1.02), ["living"] = (1.03, +1, 0.99, 1.05),
        ["leather"] = (1.00, +2, 0.97, 0.98), ["monster"] = (1.04, -2, 1.00, 1.08), ["fang"] = (1.03, -2, 1.02, 1.08), ["scales"] = (1.03, +2, 0.98, 0.95),
        ["bone"] = (1.02, +3, 0.97, 0.92), ["gel"] = (0.98, +3, 0.98, 0.95), ["carapace"] = (1.03, +4, 0.96, 0.90), ["blood"] = (1.06, -4, 1.02, 1.20),
        // ---- SHADOW/UMBRA (entropy/risk/hidden â†’ asymmetric; pure bodies Rx<1, toxic riders Rx>1) ----
        ["void"] = (1.04, -4, 1.06, 0.96), ["dark"] = (1.00, -3, 1.02, 0.98), ["shadow"] = (1.02, -2, 1.02, 0.98), ["spectral"] = (0.92, -3, 1.10, 0.94),
        ["poison"] = (1.06, -5, 1.0, 1.12), ["venom"] = (1.06, -5, 1.0, 1.12), ["toxic"] = (1.06, -5, 1.0, 1.12), ["acid"] = (1.05, -6, 0.98, 1.25),
        ["arcane"] = (1.16, -4, 1.05, 0.98), ["magical"] = (1.14, -2, 1.03, 1.02), ["essence"] = (1.16, -1, 1.02, 1.05),
        // ---- AIR/WIND (speed/lightness/evasion â†’ sweeping arcs; fast+light, slight widen) ----
        ["air"] = (1.00, +3, 1.15, 1.10), ["wind"] = (1.00, +3, 1.15, 1.10), ["vapor"] = (1.00, +2, 1.12, 1.08), ["gas"] = (1.00, +1, 1.12, 1.12),
        // ---- Quality/Grade (magnitude) ----
        ["starter"] = (0.90, +3, 0.98, 0.98), ["basic"] = (0.92, +2, 0.99, 1.0), ["common"] = (0.95, +1, 1.0, 1.0), ["standard"] = (1.00, 0, 1.0, 1.0),
        ["uncommon"] = (1.05, -1, 1.0, 1.0), ["fine"] = (1.08, +1, 1.0, 1.0), ["quality"] = (1.11, +1, 1.0, 1.0), ["refined"] = (1.13, +2, 1.0, 1.0),
        ["rare"] = (1.16, +1, 1.0, 1.0), ["advanced"] = (1.19, +1, 1.0, 1.02), ["precious"] = (1.22, +2, 1.0, 1.0), ["epic"] = (1.22, +2, 1.0, 1.02),
        ["legendary"] = (1.28, +3, 1.0, 1.02), ["mythical"] = (1.32, +3, 1.0, 1.0), ["ancient"] = (1.25, +3, 1.0, 0.98),
        ["superior"] = (1.14, +2, 1.0, 1.0), ["pure"] = (1.10, +4, 1.0, 0.98), ["holy"] = (1.15, +3, 1.0, 1.02), ["material"] = (1.00, 0, 1.0, 1.0), ["mundane"] = (0.85, 0, 1.0, 0.95),
        // ---- Physical/Structural ----
        ["durable"] = (1.00, +4, 0.95, 0.90), ["strong"] = (1.10, +2, 1.0, 1.05), ["hard"] = (1.00, +5, 0.94, 0.90), ["solid"] = (1.00, +6, 0.92, 0.85),
        ["dense"] = (1.00, +5, 0.90, 0.82), ["heavy"] = (1.00, +4, 0.88, 0.85),
        ["sharp"] = (1.05, -6, 1.05, 1.20),
        ["layered"] = (1.00, +2, 0.98, 0.95), ["flexible"] = (1.00, +3, 1.02, 0.98), ["versatile"] = (1.05, +1, 1.0, 1.02), ["memory"] = (1.05, +2, 0.98, 0.98),
        // ---- Exotic/Rule-benders ----
        ["quantum"] = (1.00, -4, 1.05, 1.15), ["impossible"] = (1.20, -6, 1.05, 1.10), ["power"] = (1.25, -3, 1.05, 1.15),
        ["temporal"] = (1.10, +8, 0.85, 0.70),
        ["harmony"] = (1.10, +8, 0.98, 0.90),
        ["dangerous"] = (1.10, -12, 1.02, 1.45),
        ["elemental"] = (1.10, -3, 1.02, 1.15),
        // ---- Function/Output ----
        ["weapon"] = (1.08, -6, 1.05, 1.20), ["combat"] = (1.06, -5, 1.02, 1.20), ["explosive"] = (1.10, -14, 1.05, 1.50), ["strength"] = (1.15, -3, 1.0, 1.10),
        ["armor"] = (1.04, +9, 0.90, 0.80), ["protection"] = (1.05, +8, 0.92, 0.82), ["defense"] = (1.02, +8, 0.92, 0.82), ["resistance"] = (1.00, +7, 0.94, 0.85),
        ["healing"] = (1.05, +6, 0.95, 0.85), ["regeneration"] = (1.05, +7, 0.95, 0.82), ["buff"] = (1.10, +2, 1.0, 1.05),
        ["enhancement"] = (1.12, +2, 1.0, 1.02), ["utility"] = (1.00, +2, 1.0, 1.0), ["tool"] = (1.03, +4, 0.96, 0.90), ["potion"] = (1.02, +2, 1.0, 0.98),
        ["consumable"] = (1.00, +2, 1.0, 0.98), ["crafting"] = (1.02, +3, 0.98, 0.95), ["engineering"] = (1.04, +4, 0.96, 0.90), ["fishing"] = (1.00, +3, 0.98, 0.90),
        ["speed"] = (1.05, -3, 1.20, 1.30), ["agility"] = (1.04, -2, 1.15, 1.25),
    };

    // Â§2.2 exception table (channel emphasis for tie-break/tint reads only)
    private static readonly Dictionary<string, (int Ch, double Mul)[]> _chExc = new()
    {
        ["lightning"] = new[] { (MinigameTagEffects.HEAT, 1.5) }, ["radiant"] = new[] { (MinigameTagEffects.HEAT, 1.4) },
        ["chaos"] = new[] { (MinigameTagEffects.HEAT, 1.5) }, ["void"] = new[] { (MinigameTagEffects.UMBRA, 1.5) },
        ["dark"] = new[] { (MinigameTagEffects.UMBRA, 1.3) }, ["arcane"] = new[] { (MinigameTagEffects.UMBRA, 1.25) },
        ["essence"] = new[] { (MinigameTagEffects.GROVE, 1.3), (MinigameTagEffects.UMBRA, 1.25) }, ["spectral"] = new[] { (MinigameTagEffects.UMBRA, 1.35) },
        ["blood"] = new[] { (MinigameTagEffects.GROVE, 1.3), (MinigameTagEffects.UMBRA, 1.25) },
        ["metallic"] = new[] { (MinigameTagEffects.TERRA, 1.3) }, ["alloy"] = new[] { (MinigameTagEffects.TERRA, 1.3) },
        ["strong"] = new[] { (MinigameTagEffects.TERRA, 1.3) }, ["sharp"] = new[] { (MinigameTagEffects.TERRA, 1.25) }, ["hard"] = new[] { (MinigameTagEffects.TERRA, 1.2) },
        ["speed"] = new[] { (MinigameTagEffects.AIR, 1.3) }, ["agility"] = new[] { (MinigameTagEffects.AIR, 1.25) }, ["flexible"] = new[] { (MinigameTagEffects.AIR, 1.2) },
        ["elemental"] = new[] { (MinigameTagEffects.HEAT, 1.25), (MinigameTagEffects.AIR, 1.25) },
        ["armor"] = new[] { (MinigameTagEffects.TERRA, 1.3) }, ["protection"] = new[] { (MinigameTagEffects.TERRA, 1.3) },
        ["defense"] = new[] { (MinigameTagEffects.TERRA, 1.3) }, ["solvent"] = new[] { (MinigameTagEffects.AQUA, 1.3) },
    };

    // Â§2.2 per-channel theme-default character (the "plain body" of each family), for the no-op guard
    private static readonly Dictionary<int, (double Pot, double Vol, double Time, double Rx)> _channelDefault = new()
    {
        [MinigameTagEffects.HEAT] = (1.00, -8, 1.12, 1.25),
        [MinigameTagEffects.AQUA] = (1.00, +7, 0.94, 0.82),
        [MinigameTagEffects.TERRA] = (1.00, +6, 0.90, 0.82),
        [MinigameTagEffects.GROVE] = (1.00, +2, 0.98, 1.03),
        [MinigameTagEffects.UMBRA] = (1.02, -3, 1.02, 0.98),
        [MinigameTagEffects.AIR] = (1.00, +3, 1.14, 1.10),
    };

    // ==================================================================== Â§2.4 ResolveChannel
    // Inline mirror of MinigameTagEffects.Resolve (which is private). Only the channel int is needed.
    private static readonly Dictionary<string, int> _tagChannel = new()
    {
        ["fire"] = MinigameTagEffects.HEAT, ["flame"] = MinigameTagEffects.HEAT, ["ember"] = MinigameTagEffects.HEAT,
        ["molten"] = MinigameTagEffects.HEAT, ["forge"] = MinigameTagEffects.HEAT, ["volcanic"] = MinigameTagEffects.HEAT,
        ["lightning"] = MinigameTagEffects.HEAT, ["storm"] = MinigameTagEffects.HEAT, ["radiant"] = MinigameTagEffects.HEAT,
        ["chaos"] = MinigameTagEffects.HEAT, ["light"] = MinigameTagEffects.HEAT,
        ["water"] = MinigameTagEffects.AQUA, ["aqua"] = MinigameTagEffects.AQUA, ["ice"] = MinigameTagEffects.AQUA,
        ["frost"] = MinigameTagEffects.AQUA, ["frozen"] = MinigameTagEffects.AQUA, ["liquid"] = MinigameTagEffects.AQUA, ["chill"] = MinigameTagEffects.AQUA,
        ["earth"] = MinigameTagEffects.TERRA, ["stone"] = MinigameTagEffects.TERRA, ["metal"] = MinigameTagEffects.TERRA,
        ["iron"] = MinigameTagEffects.TERRA, ["crystal"] = MinigameTagEffects.TERRA, ["gem"] = MinigameTagEffects.TERRA,
        ["mineral"] = MinigameTagEffects.TERRA, ["sand"] = MinigameTagEffects.TERRA, ["sharp"] = MinigameTagEffects.TERRA,
        ["alloy"] = MinigameTagEffects.TERRA, ["durable"] = MinigameTagEffects.TERRA, ["strong"] = MinigameTagEffects.TERRA,
        ["wood"] = MinigameTagEffects.GROVE, ["plant"] = MinigameTagEffects.GROVE, ["herb"] = MinigameTagEffects.GROVE,
        ["leather"] = MinigameTagEffects.GROVE, ["living"] = MinigameTagEffects.GROVE, ["monster"] = MinigameTagEffects.GROVE,
        ["fang"] = MinigameTagEffects.GROVE, ["scales"] = MinigameTagEffects.GROVE, ["bone"] = MinigameTagEffects.GROVE, ["gel"] = MinigameTagEffects.GROVE, ["carapace"] = MinigameTagEffects.GROVE,
        ["void"] = MinigameTagEffects.UMBRA, ["dark"] = MinigameTagEffects.UMBRA, ["shadow"] = MinigameTagEffects.UMBRA,
        ["spectral"] = MinigameTagEffects.UMBRA, ["blood"] = MinigameTagEffects.GROVE, ["poison"] = MinigameTagEffects.UMBRA,
        ["venom"] = MinigameTagEffects.UMBRA, ["toxic"] = MinigameTagEffects.UMBRA, ["acid"] = MinigameTagEffects.UMBRA,
        ["arcane"] = MinigameTagEffects.UMBRA, ["magical"] = MinigameTagEffects.UMBRA, ["essence"] = MinigameTagEffects.UMBRA,
        ["air"] = MinigameTagEffects.AIR, ["wind"] = MinigameTagEffects.AIR, ["vapor"] = MinigameTagEffects.AIR, ["gas"] = MinigameTagEffects.AIR,
    };
    private static readonly HashSet<string> _metalSet = new() { "copper", "tin", "steel", "mithril", "bronze", "adamantine", "silver", "gold", "orichalcum" };
    private static readonly HashSet<string> _woodSet = new() { "oak", "ash", "ironwood", "ebony", "worldtree", "exotic", "birch", "willow" };

    internal static int? ResolveChannel(string tag)
    {
        if (tag == null) return null;
        if (_tagChannel.TryGetValue(tag, out var ch)) return ch;
        if (_metalSet.Contains(tag)) return MinigameTagEffects.TERRA;
        if (_woodSet.Contains(tag)) return MinigameTagEffects.GROVE;
        return null;
    }

    // cold-tag set that disambiguates AQUA (water flows vs ice controls) â€” Â§2.1(A)
    private static readonly HashSet<string> _coldTags = new() { "ice", "frost", "frozen", "chill" };

    // ==================================================================== BUILD UI (Â§6.1)
    protected override void BuildUi(VBoxContainer host)
    {
        var wrap = new Control
        {
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        wrap.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        host.AddChild(wrap);

        // The play surface uses MouseFilter=Stop and a GuiInput handler for the LEFT-CLICK â€” the robust, proven pattern
        // (Alchemy uses exactly this). Routing the click through GuiInput on a Stop-filter Control that covers the whole
        // scene guarantees the click REACHES us: it can't be swallowed by a parent GUI panel (the trap that broke
        // Refining's mouse). mb.Position here is already in _surf-local space, which is exactly what S2W expects.
        _surf = new Control { MouseFilter = Control.MouseFilterEnum.Stop };
        _surf.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _surf.Draw += DrawSurface;
        _surf.GuiInput += OnSurfaceInput;
        wrap.AddChild(_surf);

        // Ready prompt box (element #14) â€” a PanelContainer centred on screen
        _readyBox = new PanelContainer();
        _readyBox.AddThemeStyleboxOverride("panel", UiTheme.Box(new Color(0.06f, 0.04f, 0.10f, 0.95f), Accent, 3, 14));
        _readyBox.SetAnchorsPreset(Control.LayoutPreset.Center);
        wrap.AddChild(_readyBox);

        var pad = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" }) pad.AddThemeConstantOverride($"margin_{side}", 20);
        _readyBox.AddChild(pad);

        var col = new VBoxContainer();
        col.AddThemeConstantOverride("separation", 12);
        pad.AddChild(col);

        _readyLabel = new Label { HorizontalAlignment = HorizontalAlignment.Center };
        _readyLabel.AddThemeFontSizeOverride("font_size", 16);
        _readyLabel.AddThemeColorOverride("font_color", UiTheme.Text);
        col.AddChild(_readyLabel);

        _channelBtn = new Button { Text = "CHANNEL   [Space]", FocusMode = Control.FocusModeEnum.None };
        _channelBtn.AddThemeFontSizeOverride("font_size", 20);
        _channelBtn.Pressed += StartFlip;
        col.AddChild(_channelBtn);

        // Persistent legend (element #15) â€” bottom centre. Plain ASCII, the NEW controls.
        _hint = new Label
        {
            Text = "CLICK each node as the line arrives   -   SPACE on a glowing SPECIAL node to fire its effect",
            Modulate = new Color(0.86f, 0.8f, 0.98f),
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        _hint.AddThemeFontSizeOverride("font_size", 15);
        _hint.SetAnchorsPreset(Control.LayoutPreset.CenterBottom);
        _hint.OffsetTop = -34; _hint.OffsetBottom = -10; _hint.OffsetLeft = -620; _hint.OffsetRight = 620;
        wrap.AddChild(_hint);

        // shared F1/F7 dev harness
        _dev = new MinigameDevLog("adornments");
        _dev.Context = () => $"t={_runClock,5:0.0} | {_phase,-6} | spd x{SpeedMult():0.0} | click {_clickCleanHits}/{_nodesResolved} | fx {_effectTotal}";
        _dev.NoteSubmitted += OnDevNote;
        _dev.BuildNotesPanel(wrap);
    }

    private void OnDevNote(string note)
    {
        _dev.Note(note, new[]
        {
            $"phase={_phase} clock={_runClock:0.0} par={_parTime:0.0}",
            $"speed={_speed:0} x{SpeedMult():0.00} clicks {_clickCleanHits}/{_clickMisses} spaces {_spaceCleanHits}/{_spaceMisses}",
            $"paceArc={_paceArc:0}/{_totalArc:0} nextNode={_nextNode}",
            $"effects=[{EffectListString()}] richness={EffectRichness():0.00}",
        });
    }

    // ==================================================================== Â§1.8 Interp
    internal static double Interp(double easy, double hard, double points)
        => easy + (hard - easy) * Math.Clamp((points - 1.0) / 79.0, 0.0, 1.0);

    private double Interp(double easy, double hard) => Interp(easy, hard, DifficultyPoints);

    // ==================================================================== ON BEGIN
    protected override void OnBegin()
    {
        // difficulty-interpolated params (Â§1.8 / Â§7)
        _windowScale = Interp(1.05, 0.62);         // tighter node timing tolerance with points
        _nodeCountBias = (int)Math.Round(Interp(1, 5));
        _hazardSpeedGlobal = Interp(0.85, 1.35);
        _specialFraction = Interp(0.28, 0.36);     // fraction of nodes that are color-coded specials (a minority)

        // build the sigil (deterministic from craft + tags) â€” Â§2 / Â§6.2 / Â§7 / Â§8
        var built = BuildCourse(Recipe, DifficultyPoints, DifficultyTier, out var prof, out var dom, out var totalMain);
        _nodes = built.Nodes;
        _edges = built.Edges;
        _profile = prof;
        _dominantChannel = dom;
        _totalMainlineNodes = totalMain;
        _rng = built.Rng;

        // arc length of the whole path
        RecomputeArc();

        // ---- SPEED tuning: tag pace (Time) + difficulty fold BASE_SPEED / growth / MAX / PAR ----
        var tagPace = Math.Clamp(_profile.Time, 0.75, 1.35);   // fire fast, ice slow
        _baseSpeed = BASE_SPEED * Interp(0.85, 1.20) * tagPace;
        // fire compounds harder/faster; water/ice a touch gentler. growth stays close to the canonical click dial.
        _growthClick = GROWTH_CLICK * (dom == MinigameTagEffects.HEAT ? 1.02 : dom == MinigameTagEffects.AQUA ? 0.985 : 1.0);
        _maxSpeed = MAX_SPEED * tagPace;
        _speed = _baseSpeed;
        _cleanStreak = 0;

        // PAR_TIME â€” the yardstick the time score measures against. It is what a COMPETENT run (~60% of clicks clean)
        // takes: distance / a par speed that sits above base but below a perfect compounding run.
        var parSpeed = _baseSpeed * 1.45;                        // par pace ~ a modest compounding run
        _parTime = Math.Max(2.0, _totalArc / parSpeed) * Interp(1.10, 0.95);  // slightly generous, tighter at high diff

        // reset run state
        _paceArc = 0;
        _nodesResolved = 0;
        _clickCleanHits = 0; _clickMisses = 0; _spaceCleanHits = 0; _spaceMisses = 0;
        _nextNode = 1;   // node 0 is the start (pen head begins there)
        _clickResolved.Clear();
        _spaceResolved.Clear();
        _countedResolved.Clear();
        _cleanHitSet.Clear();
        _floats.Clear();
        Array.Clear(_effectStacks, 0, _effectStacks.Length);
        _effectTotal = 0; _effectFlash = 0; _lastEffectCh = -1;
        _runClock = 0; _settleClock = 0; _planClock = 0; _anim = 0; _sealFlash = 0;
        _phase = Phase.Ready;
        _flip = 0f; _flipRaw = 0f;

        _camWorld = _nodes[0].Pos;

        SetHeaderSub("the sigil lifts - the line draws itself; time your clicks");
        SetQuality(0);
        HideTimer();

        _readyLabel.Text =
            "The placement pattern flips UP and a rune inscribes ITSELF along the sigil.\n"
            + "The pen head moves on its own - it SPEEDS UP with every well-timed CLICK (compounding!).\n"
            + "CLICK each node as the line reaches it - that's the whole game and the main speed driver.\n"
            + "GLOWING COLOR-CODED nodes are SPECIAL: click them too, and press Space to FIRE their effect\n"
            + "(a themed burst + a stack + a small speed nudge). Missing a special's Space just skips a flourish.";
        _readyBox.Visible = true;
        _hint.Visible = true;

        // F1 session header (Â§10)
        var specials = _nodes.Count(n => n.IsSpecial);
        var header = new List<string>
        {
            $"output={Recipe?.OutputId ?? "debug"} tier={DifficultyTier} pts={DifficultyPoints:0.#}",
            $"nodes={_nodes.Count} specials={specials} arc={_totalArc:0} dominant={MinigameTagEffects.ChannelName(_dominantChannel)}",
            $"baseSpeed={_baseSpeed:0} growthClick={_growthClick:0.000} growthSpace={GROWTH_SPACE:0.000} maxSpeed={_maxSpeed:0} parTime={_parTime:0.0} holdFrac={HOLD_FRAC:0.00}",
        };
        for (var i = 0; i < _nodes.Count; i++)
            header.Add($"n{i} {(_nodes[i].IsSpecial ? "SPECIAL" : "normal")} {_nodes[i].Kind} fam{_nodes[i].Family}({EffectName[Math.Clamp(_nodes[i].Family, 0, 5)]}) tier{_nodes[i].Tier} tol{_nodes[i].HazardWindow:0.00}");
        _dev.BeginSession(header);

        _surf.QueueRedraw();
    }

    private void StartFlip()
    {
        if (_phase != Phase.Ready) return;
        _readyBox.Visible = false;
        _phase = Phase.Plan;
        _dev.Log("FLIP-UP start");

        _flipRaw = 0f;
        _flip = 0f;
    }

    // ==================================================================== SIGIL BUILD (Â§2/Â§6.2/Â§7/Â§8)
    internal sealed class Course
    {
        public List<NodeSpec> Nodes = new();
        public List<Edge> Edges = new();
        public RandomNumberGenerator Rng = new();
    }

    // Â§8 FNV-1a hash over UTF-8 bytes (deterministic, no wall-clock / System.Random)
    internal static ulong Hash64(string s)
    {
        ulong h = 14695981039346656037UL;
        var bytes = Encoding.UTF8.GetBytes(s ?? "");
        foreach (var b in bytes) { h ^= b; h *= 1099511628211UL; }
        return h;
    }

    // Â§2.6 build the tag-folded course-character profile (with the Â§2.2 no-op guard) â€” PRESERVED verbatim
    internal static MinigameModifierCommon.ModProfile BuildCourseProfile(Dictionary<string, int> counts, int maxTier)
    {
        var p = new MinigameModifierCommon.ModProfile(6, 0);

        // NO-OP GUARD (Â§2.2): working table = _baseTable + a theme-default entry for every unkeyed tag
        var table = new Dictionary<string, (double Pot, double Vol, double Time, double Rx)>(_baseTable);
        foreach (var tag in counts.Keys)
            if (!table.ContainsKey(tag))
                table[tag] = _channelDefault[ResolveChannel(tag) ?? MinigameTagEffects.TERRA];

        MinigameModifierCommon.Fold(p, counts, table, _chExc);
        p.Rx *= 1 + (Math.Max(1, maxTier) - 1) * 0.05;   // tier vigor bump (alchemy parity)
        MinigameModifierCommon.Clamp(p,
            potLo: 0.6, potHi: 1.6,
            volLo: -24, volHi: 24,
            timeLo: 0.75, timeHi: 1.35,
            rxLo: 0.6, rxHi: 1.6,
            chLo: 0.35, chHi: 2.5);
        return p;
    }

    // Â§2.1(A) resolve the NodeKind for one ingredient's ordered tag list â€” PRESERVED (shapes stroke character)
    internal static NodeKind ResolveNodeKind(IReadOnlyList<string> tags)
    {
        if (tags == null || tags.Count == 0) return NodeKind.Plain;

        var set = new HashSet<string>(tags);
        if (set.Contains("chaos") || set.Contains("dangerous")) return NodeKind.ChaosGate;
        if (set.Contains("temporal")) return NodeKind.SlowMoDodge;
        if (set.Contains("sharp")) return NodeKind.TightGap;

        var rank = 0; var any = false;
        var w = new double[MinigameTagEffects.N];
        foreach (var t in tags)
        {
            var ch = ResolveChannel(t);
            var weight = rank switch { 0 => 4.0, 1 => 3.0, 2 => 2.0, _ => 1.0 };
            rank++;
            if (ch == null) continue;
            w[ch.Value] += weight; any = true;
        }
        if (!any) return NodeKind.Plain;

        var dom = 0;
        for (var i = 1; i < MinigameTagEffects.N; i++) if (w[i] > w[dom]) dom = i;

        switch (dom)
        {
            case MinigameTagEffects.HEAT: return NodeKind.SpikeRun;
            case MinigameTagEffects.AQUA:
                return _coldTags.Overlaps(set) ? NodeKind.HoldStill : NodeKind.Glide;
            case MinigameTagEffects.AIR: return NodeKind.Glide;
            case MinigameTagEffects.TERRA: return NodeKind.HeavyLeap;
            case MinigameTagEffects.GROVE: return NodeKind.MovingHazard;
            case MinigameTagEffects.UMBRA: return NodeKind.BlindDash;
            default: return NodeKind.Plain;
        }
    }

    // Â§4.3 base timing tolerance per kind (REUSED as the input window; fire tight, ice/water wide)
    private static double BaseWin(NodeKind k) => k switch
    {
        NodeKind.SpikeRun => 0.42, NodeKind.TightGap => 0.34, NodeKind.MovingHazard => 0.55, NodeKind.BlindDash => 0.50,
        NodeKind.Glide => 0.90, NodeKind.HeavyLeap => 0.70, NodeKind.HoldStill => 0.80, NodeKind.SlowMoDodge => 0.65,
        NodeKind.ChaosGate => 0.44, NodeKind.Plain => 1.0, _ => 0.5,
    };
    private static double BaseSpeed(NodeKind k) => k switch
    {
        NodeKind.SpikeRun => 1.4, NodeKind.TightGap => 1.0, NodeKind.MovingHazard => 1.1, NodeKind.BlindDash => 1.0,
        NodeKind.Glide => 0.8, NodeKind.HeavyLeap => 0.9, NodeKind.HoldStill => 1.0, NodeKind.SlowMoDodge => 0.6,
        NodeKind.ChaosGate => 1.3, NodeKind.Plain => 1.0, _ => 1.0,
    };

    private Course BuildCourse(RecipeContext? recipe, double points, string tier,
        out MinigameModifierCommon.ModProfile profile, out int dominantChannel, out int totalMainline)
    {
        var course = new Course();

        // ---- gather inputs (synthesize a debug recipe if null, Â§8.4) ----
        var inputs = new List<(string Id, string Name, List<string> Tags, int Qty, int Tier)>();
        var outputTags = new List<string>();
        var craftId = recipe?.OutputId ?? "debug";
        if (recipe?.Inputs is { Count: > 0 })
        {
            foreach (var ing in recipe.Inputs)
                inputs.Add((ing.Id, ing.Name, ing.Tags ?? new List<string>(), Math.Max(1, ing.Qty), Math.Max(1, ing.MaterialTier)));
            outputTags = recipe.OutputTags ?? new List<string>();
        }
        else
        {
            inputs.Add(("oak", "Oak", new List<string> { "wood" }, 1, 1));
            inputs.Add(("iron", "Iron", new List<string> { "iron", "metal" }, 1, 1));
            inputs.Add(("ember", "Ember", new List<string> { "fire", "ember" }, 1, 1));
            outputTags = new List<string> { "utility", "wood" };
        }

        // ---- seed the run RNG (Â§8) ----
        var allTags = new List<string>();
        foreach (var i in inputs) allTags.AddRange(i.Tags);
        allTags.AddRange(outputTags);
        var tagSig = string.Join(",", allTags.OrderBy(t => t, StringComparer.Ordinal));
        course.Rng.Seed = Hash64(craftId + "|" + tagSig + "|" + tier);

        // ---- (B) course-character profile over the tag pool (Â§2.6) ----
        var counts = new Dictionary<string, int>();
        foreach (var i in inputs)
            foreach (var t in i.Tags)
                counts[t] = counts.GetValueOrDefault(t) + i.Qty;
        foreach (var t in outputTags)
            counts[t] = counts.GetValueOrDefault(t) + 1;
        var maxTier = inputs.Count > 0 ? inputs.Max(i => i.Tier) : 1;
        profile = BuildCourseProfile(counts, maxTier);

        // dominant loadout channel (for the glow tint / stroke character) â€” strongest _profile.Ch
        var domCh = 0;
        for (var c = 1; c < profile.Ch.Length; c++) if (profile.Ch[c] > profile.Ch[domCh]) domCh = c;
        if (Math.Abs(profile.Ch[domCh] - 1.0) < 1e-6)
        {
            var brew = MinigameTagEffects.Brew(allTags, Math.Max(1, maxTier), 1);
            domCh = MinigameTagEffects.Dominant(brew);
        }
        dominantChannel = domCh;

        // ---- node kinds + families per ingredient (Â§2.3) ----
        var pending = new List<(NodeKind Kind, int Family, int Tier, string Label)>();
        foreach (var ing in inputs)
        {
            var kind = ResolveNodeKind(ing.Tags);
            var famBrew = MinigameTagEffects.Brew(ing.Tags, ing.Tier, 1);
            var family = MinigameTagEffects.Dominant(famBrew);
            var nCount = Math.Clamp(ing.Qty, 1, 3);
            for (var q = 0; q < nCount; q++)
                pending.Add((kind, family, ing.Tier, ing.Name));
        }

        // ---- Â§7 vertex count â€” a nice long linear stroke (player wants "max length way longer") ----
        var distinctOut = new HashSet<string>(outputTags).Count;
        var baseN = 6 + distinctOut * 2;
        var sumFromIngredient = pending.Count * 2;   // each ingredient contributes more presence on a longer stroke
        totalMainline = Math.Clamp(baseN + _nodeCountBias + sumFromIngredient, 10, 30);
        var n = totalMainline;

        // ---- Â§6.2 lay out the sigil as an ANGULAR GLYPH in a LARGE world space (never a circle) ----
        var worldPts = BuildSigilPolyline(recipe, course.Rng, dominantChannel, n);
        n = worldPts.Count;
        totalMainline = n;

        // ---- pick WHICH nodes are SPECIAL (a minority, tag/seed-driven). Never node 0 (the start) or node n-1 (the
        // end), never two specials adjacent (so SPACE presses never overlap), spaced by a deterministic seed roll. ----
        var special = new HashSet<int>();
        var wantSpecials = (int)Math.Round(Math.Clamp(_specialFraction, 0.0, 0.5) * (n - 2));
        wantSpecials = Math.Clamp(wantSpecials, n >= 8 ? 2 : 1, Math.Max(1, (n - 2) / 2));
        var lastSpecial = -2;
        // walk interior nodes; place a special when the seed rolls AND it isn't adjacent to the previous special.
        for (var i = 1; i < n - 1 && special.Count < wantSpecials; i++)
        {
            if (i - lastSpecial < 2) continue;                  // keep specials non-adjacent
            var remainingSlots = 0;
            for (var j = i; j < n - 1; j++) if (j - (special.Count > 0 ? lastSpecial : -2) >= 2) remainingSlots++;
            var need = wantSpecials - special.Count;
            // bias: place if we still need more than the room allows, else roll against the special fraction
            if (need >= remainingSlots || course.Rng.Randf() < (float)Math.Clamp(_specialFraction * 1.6, 0.2, 0.7))
            {
                special.Add(i); lastSpecial = i;
            }
        }

        // ---- assign each vertex its kind/family/tier + special flag ----
        for (var i = 0; i < n; i++)
        {
            var slot = i < pending.Count ? pending[i]
                     : (NodeKind.Plain, pending.Count > 0 ? pending[i % pending.Count].Item2 : MinigameTagEffects.TERRA, 1, "path");
            var kind = slot.Item1; var family = slot.Item2; var mtier = slot.Item3; var label = slot.Item4;

            var node = MakeNode(kind, worldPts[i], i, family, mtier, label, profile, craftId, special.Contains(i));
            course.Nodes.Add(node);
        }

        // stroke edges over the whole linear path
        for (var i = 0; i < n - 1; i++)
            course.Edges.Add(MakeEdge(course.Nodes, i, i + 1));

        return course;
    }

    // Â§6.2 Build the sigil VERTEX polyline in world space (deterministic angular glyph, themed by channel).
    private List<Vector2> BuildSigilPolyline(RecipeContext? recipe, RandomNumberGenerator rng, int dom, int n)
    {
        var pattern = ExtractPatternPoints(recipe);
        if (pattern is { Count: >= 2 })
            return NormalizeToWorld(pattern);

        var pts = new List<Vector2> { Vector2.Zero };
        var heading = -Mathf.Pi / 2f;
        var step = 190f;
        float turnMag, jitter, asym; bool rightAngle, curve;
        switch (dom)
        {
            case MinigameTagEffects.HEAT:  turnMag = 2.15f; jitter = 0.85f; rightAngle = false; asym = 0f;    curve = false; break;
            case MinigameTagEffects.AQUA:  turnMag = 0.95f; jitter = 0.25f; rightAngle = false; asym = 0f;    curve = true;  break;
            case MinigameTagEffects.TERRA: turnMag = Mathf.Pi / 2f; jitter = 0.05f; rightAngle = true; asym = 0f; curve = false; break;
            case MinigameTagEffects.AIR:   turnMag = 0.7f;  jitter = 0.2f;  rightAngle = false; asym = 0f;    curve = true;  break;
            case MinigameTagEffects.UMBRA: turnMag = 1.7f;  jitter = 0.6f;  rightAngle = false; asym = 0.6f;  curve = false; break;
            case MinigameTagEffects.GROVE: turnMag = 1.25f; jitter = 0.5f;  rightAngle = false; asym = 0.25f; curve = true;  break;
            default:                       turnMag = 1.3f;  jitter = 0.4f;  rightAngle = false; asym = 0.1f;  curve = false; break;
        }

        for (var i = 1; i < n; i++)
        {
            var altSign = (i % 2 == 0) ? 1f : -1f;
            var r = rng.Randf() * 2f - 1f;
            var turn = altSign * turnMag + r * jitter + asym * turnMag * 0.5f;
            if (rightAngle)
            {
                var q = Mathf.Round(turn / (Mathf.Pi / 2f)) * (Mathf.Pi / 2f);
                turn = Mathf.Lerp(turn, q, 0.85f);
            }
            heading += turn;
            var thisStep = step * (0.8f + rng.Randf() * 0.5f);
            var next = pts[^1] + new Vector2(Mathf.Cos(heading), Mathf.Sin(heading)) * thisStep;
            pts.Add(next);
        }

        if (curve && pts.Count >= 3)
            pts = SoftenCorners(pts);

        return NormalizeToWorld(pts);
    }

    private static List<Vector2> SoftenCorners(List<Vector2> pts)
    {
        var outp = new List<Vector2> { pts[0] };
        for (var i = 0; i < pts.Count - 1; i++)
        {
            var a = pts[i]; var b = pts[i + 1];
            var prev = i > 0 ? pts[i - 1] : a;
            var mid = a.Lerp(b, 0.5f) + (b - prev).Normalized().Rotated(Mathf.Pi / 2f) * a.DistanceTo(b) * 0.10f;
            outp.Add(mid);
            outp.Add(b);
        }
        return outp;
    }

    // Fit a raw point cloud into a consistent large WORLD box (bigger than the screen so the camera must move).
    private static List<Vector2> NormalizeToWorld(List<Vector2> raw)
    {
        const float worldW = 3600f, worldH = 2100f, pad = 240f;
        float minX = float.MaxValue, minY = float.MaxValue, maxX = float.MinValue, maxY = float.MinValue;
        foreach (var p in raw) { minX = Mathf.Min(minX, p.X); minY = Mathf.Min(minY, p.Y); maxX = Mathf.Max(maxX, p.X); maxY = Mathf.Max(maxY, p.Y); }
        var spanX = Mathf.Max(1f, maxX - minX); var spanY = Mathf.Max(1f, maxY - minY);
        var sc = Mathf.Min((worldW - 2 * pad) / spanX, (worldH - 2 * pad) / spanY);
        var offX = (worldW - spanX * sc) * 0.5f; var offY = (worldH - spanY * sc) * 0.5f;
        var outp = new List<Vector2>(raw.Count);
        foreach (var p in raw)
            outp.Add(new Vector2((p.X - minX) * sc + offX, (p.Y - minY) * sc + offY));
        return outp;
    }

    private static List<Vector2>? ExtractPatternPoints(RecipeContext? recipe)
    {
        _ = recipe;
        return null;
    }

    private NodeSpec MakeNode(NodeKind kind, Vector2 pos, int index,
        int family, int tier, string label, MinigameModifierCommon.ModProfile prof, string craftId, bool isSpecial)
    {
        var windowMulTags = Math.Clamp(1 - prof.Vol / 120.0, 0.6, 1.4);
        var hazardWindow = BaseWin(kind) * _windowScale * windowMulTags;
        var hazardSpeed = BaseSpeed(kind) * _hazardSpeedGlobal * Math.Clamp(prof.Rx, 0.6, 1.6) * (1 + (tier - 1) * 0.06);

        var reward = 1.0 * Math.Clamp(prof.Pot, 0.6, 1.6) * (1 + (tier - 1) * 0.10);
        reward = Math.Clamp(reward, 0.6, 1.6);

        if (kind == NodeKind.Glide && family == MinigameTagEffects.AQUA)
            hazardWindow *= 1.25;

        return new NodeSpec
        {
            Kind = kind,
            Pos = pos,
            IndexOnRing = index,
            Family = Math.Clamp(family, 0, 5),
            Tier = Math.Clamp(tier, 1, 4),
            HazardWindow = Math.Clamp(hazardWindow, 0.18, 1.20),
            HazardSpeed = Math.Clamp(hazardSpeed, 0.5, 2.5),
            Reward = reward,
            SeedSalt = (uint)Hash64(craftId + label + index),
            Label = label,
            IsSpecial = isSpecial,
        };
    }

    private static Edge MakeEdge(List<NodeSpec> nodes, int a, int b)
        => new() { A = a, B = b, Length = Math.Max(1f, nodes[a].Pos.DistanceTo(nodes[b].Pos)) };

    // recompute total arc-length over the edge list
    private void RecomputeArc()
    {
        _totalArc = 0;
        foreach (var e in _edges) _totalArc += e.Length;
        _totalArc = Math.Max(1.0, _totalArc);
    }

    // ==================================================================== Â§6.1 surface helpers
    private void RecomputeSurface()
    {
        var size = _surf != null && _surf.Size.X > 1f && _surf.Size.Y > 1f
            ? _surf.Size
            : GetViewport().GetVisibleRect().Size;
        var w = size.X < 1f ? DESIGN.X : size.X;
        var h = size.Y < 1f ? DESIGN.Y : size.Y;
        _S = Mathf.Max(0.1f, Mathf.Min(w / DESIGN.X, h / DESIGN.Y));
        var screenCenter = new Vector2(w, h) * 0.5f;
        _origin = screenCenter - _camWorld * _S;
    }

    private Vector2 W2S(Vector2 world) => _origin + world * _S;
    // screen â†’ world (inverse of W2S) â€” used to test whether a mouse CLICK landed on a node.
    private Vector2 S2W(Vector2 screen) => (screen - _origin) / Math.Max(0.01f, _S);

    // ==================================================================== ON TICK (Â§4)
    protected override void OnTick(double delta)
    {
        if (delta > 0.05) delta = 0.05;   // spiral-of-death guard
        var dt = delta;
        _anim += dt;
        _sealFlash = Math.Max(0, _sealFlash - dt);
        _effectFlash = Math.Max(0, _effectFlash - dt * 1.6);
        TickFloats(dt);

        switch (_phase)
        {
            case Phase.Plan:
                _planClock += dt;
                _flipRaw = (float)Math.Clamp(_planClock / FLIP_DUR, 0, 1);
                _flip = 1f - Mathf.Pow(1f - _flipRaw, 3f);
                var camEaseT = (float)Math.Clamp((_planClock - FLIP_DUR) / PLAN_CAM_EASE, 0, 1);
                var eased = camEaseT * camEaseT * (3 - 2 * camEaseT);
                _camWorld = SigilCentroid().Lerp(_nodes[0].Pos, eased);
                if (_planClock >= PLAN_MAX_S) EnterTrace();
                break;

            case Phase.Trace:
                _runClock += dt;
                TickTrace(dt);
                if (_runClock > HARD_CAP_S) EnterSettle();
                break;

            case Phase.Settle:
                _settleClock += dt;
                if (_settleClock >= SETTLE_DUR)
                {
                    _phase = Phase.Done;
                    var perf = ComputePerf();
                    _dev.Log($"SEAL perf {perf * 100:0}% (time {_runClock:0.0}/{_parTime:0.0} rich {EffectRichness():0.00})");
                    Finish(perf);
                    return;
                }
                break;
        }

        SetHeaderSub($"speed x{SpeedMult():0.0}   -   clicks {_clickCleanHits}/{_nodesResolved}   -   effects {_effectTotal}");
        UpdateLiveQuality();
        _surf.QueueRedraw();
    }

    private Vector2 SigilCentroid()
    {
        var c = Vector2.Zero;
        foreach (var nn in _nodes) c += nn.Pos;
        return _nodes.Count > 0 ? c / _nodes.Count : Vector2.Zero;
    }

    private void EnterTrace()
    {
        if (_phase != Phase.Trace)
        {
            _phase = Phase.Trace;
            _flip = 1f;
            _camWorld = _nodes[0].Pos;
            _dev.Log("TRACE start");
        }
    }

    private void EnterSettle()
    {
        if (_phase == Phase.Trace) { _phase = Phase.Settle; _settleClock = 0; _dev.Log("SETTLE"); }
    }

    // ---- Â§4 the tracing loop: the pen head advances at compounding speed on its own; the camera follows EXCEPT it
    // HOLDS still during the last 20% of the approach to the next node so the click target is stationary. Node input
    // windows open/close as the head passes each vertex. ----
    private void TickTrace(double dt)
    {
        // advance the pen head along arc-length at the COMPOUNDING speed (no player-controlled position)
        _speed = Math.Clamp(_speed, _baseSpeed, _maxSpeed);
        _paceArc = Math.Min(_totalArc, _paceArc + _speed * dt);

        // ---- CAMERA: normally eases toward the pen head with a little look-ahead; but during the LAST 20% of the
        // current segment it HOLDS at the node position so the click target does not slide under the cursor. ----
        var camTarget = CameraTarget();
        var follow = (float)Math.Clamp(9.0 * dt, 0, 1);   // smooth ease (never a snap)
        _camWorld = _camWorld.Lerp(camTarget, follow);

        // ---- node input windows: as the pen head crosses each vertex, close its windows (auto-miss unpressed) ----
        while (_nextNode < _nodes.Count)
        {
            var nodeArc = NodeArc(_nextNode);
            if (_paceArc + 1e-3 >= nodeArc)
            {
                if (!_clickResolved.Contains(_nextNode)) ResolveClickMiss(_nextNode, auto: true);
                // a normal node has no space input; a special that got no space by the time it's passed is a harmless
                // skipped flourish (recorded as a soft miss, not a slowdown).
                if (_nodes[_nextNode].IsSpecial && !_spaceResolved.Contains(_nextNode)) ResolveSpaceMiss(_nextNode, auto: true);
                _nextNode++;
            }
            else break;
        }

        // reaching the end ALWAYS ends the run (screen always progresses â†’ no soft-lock)
        if (_paceArc >= _totalArc - 1e-6)
            EnterSettle();
    }

    // The WORLD point the camera should centre on this frame. Implements the LAST-20%-of-segment HOLD:
    //   â€¢ Find the segment the pen head is on (the one leading INTO _nextNode).
    //   â€¢ If the head is in the first 80% of that segment: follow the head with a small look-ahead (slides normally).
    //   â€¢ If the head is in the last 20% (nearing the node): return the NODE position (camera locks so the click
    //     target is stationary). It stays locked on the node until the head crosses it and the next segment begins.
    private Vector2 CameraTarget()
    {
        if (_nextNode >= _nodes.Count)
            return _nodes.Count > 0 ? _nodes[^1].Pos : Vector2.Zero;

        var target = _nodes[_nextNode].Pos;
        var prevArc = NodeArc(_nextNode - 1);
        var nodeArc = NodeArc(_nextNode);
        var segLen = Math.Max(1e-3, nodeArc - prevArc);
        var into = Math.Clamp((_paceArc - prevArc) / segLen, 0, 1);   // 0 = just left prev node, 1 = at target node

        // HOLD zone: last HOLD_FRAC of the segment â†’ lock the camera on the (stationary) target node.
        if (into >= 1.0 - HOLD_FRAC)
            return target;

        // Approach zone (first 80%): follow the head with a mild look-ahead toward the target so it stays framed,
        // but ease OUT the look-ahead as we near the hold boundary so the transition into the lock is seamless.
        var (paceWorld, _, _) = ArcToWorld(_paceArc);
        // remap intoâˆˆ[0, 0.8] â†’ tâˆˆ[0,1] for how much of the way through the "moving" part we are
        var t = (float)Math.Clamp(into / (1.0 - HOLD_FRAC), 0, 1);
        // look-ahead fraction shrinks to 0 as we reach the hold boundary, so camTarget converges to `target`.
        var lookAhead = 0.35f * (1f - t);
        return paceWorld.Lerp(target, lookAhead + t * (1f - lookAhead));
    }

    // arc-length â†’ (world pos, segment (A,B) world endpoints, segment index)
    private (Vector2 pos, (Vector2 A, Vector2 B) seg, int idx) ArcToWorld(double arc)
    {
        if (_edges.Count == 0) return (_nodes.Count > 0 ? _nodes[0].Pos : Vector2.Zero, (Vector2.Zero, Vector2.Zero), 0);
        double acc = 0;
        for (var i = 0; i < _edges.Count; i++)
        {
            var e = _edges[i];
            if (arc <= acc + e.Length || i == _edges.Count - 1)
            {
                var a = _nodes[e.A].Pos; var b = _nodes[e.B].Pos;
                var t = (float)Math.Clamp((arc - acc) / Math.Max(1e-3, e.Length), 0, 1);
                return (a.Lerp(b, t), (a, b), i);
            }
            acc += e.Length;
        }
        var last = _edges[^1];
        return (_nodes[last.B].Pos, (_nodes[last.A].Pos, _nodes[last.B].Pos), _edges.Count - 1);
    }

    // arc-length position of node k (Î£ edge lengths up to k)
    private double NodeArc(int k)
    {
        if (k <= 0) return 0;
        double acc = 0;
        for (var i = 0; i < k && i < _edges.Count; i++) acc += _edges[i].Length;
        return acc;
    }

    // ==================================================================== Â§4 INPUT RESOLUTION (speed + effects)
    // per-node, per-input attempt tracking (both inputs graded independently against the pen head's arrival timing).
    private readonly HashSet<int> _clickResolved = new();
    private readonly HashSet<int> _spaceResolved = new();

    // grade an input by TIMING: arc error between the pen head and the node, converted to a Perfect/Good/Miss band via
    // the node's timing tolerance (scaled by CURRENT speed so the window stays fair in TIME as px/s climbs).
    private Grade GradeTiming(int node)
    {
        var nodeArc = NodeArc(node);
        var tolArc = Math.Max(1.0, _nodes[node].HazardWindow * _speed);
        var arcErr = Math.Abs(_paceArc - nodeArc);
        if (arcErr <= tolArc * PERFECT_FRAC) return Grade.Perfect;
        if (arcErr <= tolArc) return Grade.Good;
        return Grade.Miss;
    }

    // return the node index the CLICK is aiming at: the nearest un-clicked, still-live node whose SCREEN position is
    // within CLICK_RADIUS of the click point. Returns -1 if the click isn't near any node.
    private int PickClickTarget(Vector2 clickWorld)
    {
        var best = -1; var bestD = double.MaxValue;
        // scan a small window of nodes around _nextNode (the only ones whose input windows can be open)
        var lo = Math.Max(0, _nextNode - 1);
        var hi = Math.Min(_nodes.Count - 1, _nextNode + 2);
        for (var i = lo; i <= hi; i++)
        {
            if (_clickResolved.Contains(i)) continue;
            var d = clickWorld.DistanceTo(_nodes[i].Pos);
            if (d <= CLICK_RADIUS && d < bestD) { bestD = d; best = i; }
        }
        return best;
    }

    // CLICK (primary): a well-timed click on/near the node â†’ big speed-up; a miss â†’ real slowdown.
    private void ResolveClick(int node)
    {
        if (node < 0 || node >= _nodes.Count) return;
        if (_clickResolved.Contains(node)) return;

        var g = GradeTiming(node);
        _clickResolved.Add(node);
        BumpResolved(node);

        if (g == Grade.Miss)
        {
            ResolveClickMiss(node, auto: false);
            return;
        }

        _clickCleanHits++;
        _cleanStreak = g == Grade.Perfect ? _cleanStreak + 1 : 0;
        _cleanHitSet.Add(node);

        // EXPONENTIAL compounding speed-up (Perfect = full, Good = a fraction of the bonus)
        var bonus = _growthClick - 1.0;
        if (g == Grade.Good) bonus *= GOOD_FACTOR;
        _speed = Math.Min(_maxSpeed, _speed * (1.0 + bonus));

        _sealFlash = 0.6; _sealFlashPos = _nodes[node].Pos;
        Burst(_surf, W2S(_nodes[node].Pos), NodeColor(_nodes[node].Family), g == Grade.Perfect ? 24 : 16, 260f);
        FlashQuality();
        Shake(2.5f + (float)Math.Min(4, _cleanStreak * 0.4));
        _dev.Log($"CLICK {g} n{node}{(_nodes[node].IsSpecial ? " [special]" : "")} spd x{SpeedMult():0.00} streak{_cleanStreak}");
    }

    private void ResolveClickMiss(int node, bool auto)
    {
        if (!_clickResolved.Contains(node)) { _clickResolved.Add(node); }
        BumpResolved(node);
        _clickMisses++;
        _cleanStreak = 0;
        // missed CLICK â†’ a REAL slowdown: speed / GROWTH_CLICK^2, floored at base.
        var dropped = _speed / (_growthClick * _growthClick);
        _speed = Math.Max(_baseSpeed, dropped);
        Shake(3.5f);
        _dev.Log($"CLICK MISS n{node}{(auto ? " (auto)" : "")} spd -> x{SpeedMult():0.00}");
    }

    // SPACE (only on SPECIALS): a well-timed space FIRES the node's effect (big themed burst) + a small speed nudge;
    // a miss is a harmless skipped flourish (tiny slowdown only).
    private void ResolveSpace(int node)
    {
        if (node < 0 || node >= _nodes.Count) return;
        if (_spaceResolved.Contains(node)) return;
        if (!_nodes[node].IsSpecial) { _dev.Log($"SPACE ignored n{node} (normal node, no effect)"); return; }

        var g = GradeTiming(node);
        _spaceResolved.Add(node);

        if (g == Grade.Miss)
        {
            ResolveSpaceMiss(node, auto: false);
            return;
        }

        _spaceCleanHits++;
        // small compounding speed-up (Perfect = full GROWTH_SPACE, Good = a fraction of the bonus)
        var bonus = GROWTH_SPACE - 1.0;
        if (g == Grade.Good) bonus *= GOOD_FACTOR;
        _speed = Math.Min(_maxSpeed, _speed * (1.0 + bonus));

        // ---- FIRE THE EFFECT (the visible payoff of a special node) ----
        FireEffect(node, g);
    }

    private void ResolveSpaceMiss(int node, bool auto)
    {
        if (!_spaceResolved.Contains(node)) { _spaceResolved.Add(node); }
        _spaceMisses++;
        // missed SPACE on an OPTIONAL special â†’ only a TINY slowdown (don't punish skipping a flourish).
        _speed = Math.Max(_baseSpeed, _speed * SPACE_MISS_MULT);
        _dev.Log($"SPACE MISS n{node}{(auto ? " (auto/skip)" : "")} spd -> x{SpeedMult():0.00}");
    }

    // count a node as "resolved" for scoring ONCE (when its CLICK is graded â€” click drives the count now).
    private readonly HashSet<int> _countedResolved = new();
    private void BumpResolved(int node)
    {
        if (_countedResolved.Contains(node)) return;
        _countedResolved.Add(node);
        _nodesResolved++;
    }

    // FIRE a special node's themed effect: a big family-coloured burst + expanding ring + a floating effect-name label
    // + the on-screen stacked-effects list increments with a flash. Impossible to miss visually.
    private void FireEffect(int node, Grade g)
    {
        var ch = Math.Clamp(_nodes[node].Family, 0, MinigameTagEffects.N - 1);
        StackEffect(ch);

        var world = _nodes[node].Pos;
        var col = NodeColor(ch);
        var screen = W2S(world);

        // 1) a LARGE themed particle burst, family-coloured (fire=orange, ice=cyan, earth=amber, life=green, shadow=violet, air=pale)
        var count = g == Grade.Perfect ? 34 : 22;
        var spd = g == Grade.Perfect ? 340f : 240f;
        Burst(_surf, screen, col, count, spd);
        Burst(_surf, screen, CraftColor.Brighten(col, 0.25f), count / 2, spd * 0.6f);

        // 2) a bright expanding ring at the node (drawn in DrawSurface via _sealFlash; also pop one immediately here)
        _sealFlash = 0.6; _sealFlashPos = world;

        // 3) a FLOATING LABEL of the effect name ("Ember!", "Frost!", ...) rising off the node
        _floats.Add(new FloatLabel { World = world + new Vector2(0, -22f), Text = $"{EffectName[ch]}!", Col = CraftColor.Brighten(col, 0.2f), Age = 0, Life = 1.15 });

        // 4) the stacked list flashes (handled by _effectFlash + _lastEffectCh in DrawEffectStack)
        FlashQuality();
        Shake(2.0f);

        // PROVABLE in the F1 log: the effect trigger path is reached.
        _dev.Log($"EFFECT {EffectName[ch]} x{_effectStacks[ch]}  (SPACE {g} n{node} spd x{SpeedMult():0.00})");
    }

    private void StackEffect(int channel)
    {
        channel = Math.Clamp(channel, 0, MinigameTagEffects.N - 1);
        _effectStacks[channel]++;
        _effectTotal++;
        _effectFlash = 0.7;
        _lastEffectCh = channel;
    }

    private void TickFloats(double dt)
    {
        for (var i = _floats.Count - 1; i >= 0; i--)
        {
            _floats[i].Age += dt;
            if (_floats[i].Age >= _floats[i].Life) _floats.RemoveAt(i);
        }
    }

    // ==================================================================== Â§4.6 SCORING (TIME-based + richness)
    // effectRichness âˆˆ [0,1]: rewards BOTH volume (effects fired vs the number of specials available) and VARIETY.
    internal static double EffectRichness(int effectTotal, int distinctKinds, int nodesTraversed)
    {
        if (nodesTraversed <= 0) return 0;
        var volume = Math.Clamp((double)effectTotal / Math.Max(1, nodesTraversed), 0, 1);
        volume = Math.Sqrt(volume);   // ease-out so partial runs still register
        var variety = Math.Clamp(distinctKinds / 4.0, 0, 1);
        return Math.Clamp(0.68 * volume + 0.32 * variety, 0, 1);
    }

    private double EffectRichness()
    {
        var distinct = 0;
        for (var i = 0; i < _effectStacks.Length; i++) if (_effectStacks[i] > 0) distinct++;
        // richness is judged against how many SPECIALS the run offered (not every node), so firing most specials
        // reads as "rich" even though specials are a minority.
        var specialsSeen = Math.Max(1, _nodes.Take(Math.Min(_nodes.Count, Math.Max(_nextNode, 1))).Count(n => n.IsSpecial));
        return EffectRichness(_effectTotal, distinct, specialsSeen);
    }

    // TIME score âˆˆ [0,1]: PAR_TIME / actualTime, shaped so the calibration bands spread (exponent 1.5 makes faster pay
    // off steeply). At par â†’ ~0.60; a fast expert run â†’ ~0.95-1.0; a slow masher (well over par) â†’ ~0.35.
    internal static double TimeScore(double actualTime, double parTime)
    {
        if (actualTime <= 1e-3) return 1.0;
        var ratio = parTime / actualTime;                 // 1.0 == exactly par
        var s = 0.60 * Math.Pow(ratio, 1.5);
        return Math.Clamp(s, 0.0, 1.0);
    }

    // perf = 0.70*time + 0.30*richness. Bands: masher ~0.25, competent ~0.60, expert ~0.95.
    internal static double ComputePerf(double actualTime, double parTime,
        int effectTotal, int distinctKinds, int specialsSeen)
    {
        var time = TimeScore(actualTime, parTime);
        var rich = EffectRichness(effectTotal, distinctKinds, specialsSeen);
        return Math.Clamp(W_TIME * time + W_RICHNESS * rich, 0.0, 1.0);
    }

    private double ComputePerf()
    {
        var distinct = 0;
        for (var i = 0; i < _effectStacks.Length; i++) if (_effectStacks[i] > 0) distinct++;
        var specialsTotal = Math.Max(1, _nodes.Count(n => n.IsSpecial));
        return ComputePerf(_runClock, _parTime, _effectTotal, distinct, specialsTotal);
    }

    // Â§4.7 live quality meter (mirrors the perf blend so the meter reads true moment-to-moment). During the run we
    // PROJECT the finish time from the current pace so the meter climbs as the player goes fast, not only at the end.
    private void UpdateLiveQuality()
    {
        double projTime;
        if (_paceArc <= 1e-3) projTime = _parTime;
        else
        {
            var remaining = Math.Max(0, _totalArc - _paceArc);
            var projRemain = remaining / Math.Max(1.0, _speed);   // finish the rest at current speed (optimistic)
            projTime = _runClock + projRemain;
        }
        var distinct = 0;
        for (var i = 0; i < _effectStacks.Length; i++) if (_effectStacks[i] > 0) distinct++;
        var specialsSoFar = Math.Max(1, _nodes.Take(Math.Min(_nodes.Count, Math.Max(_nextNode, 1))).Count(n => n.IsSpecial));
        var q = ComputePerf(projTime, _parTime, _effectTotal, distinct, specialsSoFar);
        SetQuality(q);
    }

    // ==================================================================== Â§5 INPUT
    public override void _Input(InputEvent @event)
    {
        if (!Running) return;
        if (@event is not InputEventKey { Pressed: true, Echo: false } k) return;
        if (_dev.HandleKey(k.PhysicalKeycode)) { _surf.QueueRedraw(); GetViewport().SetInputAsHandled(); }
    }

    // MOUSE input arrives here via _surf.GuiInput (a Stop-filter Control) â€” the click can't be swallowed upstream.
    // Left-click on/near a node = the timed click; in Ready/Plan it advances the intro.
    private void OnSurfaceInput(InputEvent @event)
    {
        if (!Running) return;
        if (_dev.NotesEditHasFocus) return;
        if (@event is not InputEventMouseButton { Pressed: true, ButtonIndex: MouseButton.Left } mb) return;

        switch (_phase)
        {
            case Phase.Ready: StartFlip(); break;
            case Phase.Plan: EnterTrace(); break;
            case Phase.Trace: HandleClickAt(mb.Position); break;
        }
        _surf.AcceptEvent();
    }

    protected override void OnInput(InputEvent @event)
    {
        if (_dev.NotesEditHasFocus) return;

        if (@event is not InputEventKey k) return;
        var down = k.Pressed;
        if (!down || k.Echo) return;

        switch (k.PhysicalKeycode)
        {
            // SPACE fires a SPECIAL node's effect. J / Enter are keyboard fallbacks for the same.
            case Key.Space:
            case Key.J:
            case Key.Enter:
            case Key.KpEnter:
                switch (_phase)
                {
                    case Phase.Ready: StartFlip(); GetViewport().SetInputAsHandled(); break;
                    case Phase.Plan: EnterTrace(); GetViewport().SetInputAsHandled(); break;
                    case Phase.Trace: TrySpace(); GetViewport().SetInputAsHandled(); break;
                }
                break;

            // K = keyboard FALLBACK for the click (in case the mouse ever doesn't reach us). Mouse is primary.
            case Key.K:
                if (_phase == Phase.Trace) { HandleClickFallback(); GetViewport().SetInputAsHandled(); }
                break;
        }
    }

    // a mouse CLICK at a screen point during TRACE: treat it as the timed node-click on the nearest live node.
    private void HandleClickAt(Vector2 screenPos)
    {
        if (_phase != Phase.Trace) return;
        var world = S2W(screenPos);

        var target = PickClickTarget(world);
        if (target >= 0) { ResolveClick(target); return; }

        // Clicked well OFF any node. If the next live node's input window is already OPEN, a spatially-off click is a
        // MISS on that node. Outside any open window it's a harmless early stray click (the node still gets its fair
        // timing chance as the head arrives).
        var next = _nextNode;
        while (next < _nodes.Count && _clickResolved.Contains(next)) next++;
        if (next < _nodes.Count)
        {
            var toGo = NodeArc(next) - _paceArc;
            var tolArc = Math.Max(1.0, _nodes[next].HazardWindow * _speed);
            if (toGo <= tolArc) { ResolveClickMiss(next, auto: false); return; }   // window open + off-target â†’ miss
        }
        _dev.Log($"CLICK (stray, no target) at world {world.X:0},{world.Y:0}");
    }

    // K fallback: aim the click at the next live node (no screen position â€” treat as an on-node click).
    private void HandleClickFallback()
    {
        var target = _nextNode;
        while (target < _nodes.Count && _clickResolved.Contains(target)) target++;
        if (target < _nodes.Count) ResolveClick(target);
    }

    // SPACE during TRACE: fire the current SPECIAL node's effect (the next un-spaced live SPECIAL whose window is
    // open). Only specials respond; on a normal-only stretch SPACE is a harmless no-op.
    private void TrySpace()
    {
        if (_phase != Phase.Trace) return;
        var target = _nextNode;
        while (target < _nodes.Count && (!_nodes[target].IsSpecial || _spaceResolved.Contains(target))) target++;
        // only fire if that special's window is within reach (don't let SPACE reach far-ahead specials)
        if (target < _nodes.Count)
        {
            var toGo = NodeArc(target) - _paceArc;
            var tolArc = Math.Max(1.0, _nodes[target].HazardWindow * _speed);
            if (toGo <= tolArc * 1.5) { ResolveSpace(target); return; }
        }
        _dev.Log("SPACE (no special in window)");
    }

    // ==================================================================== Â§6 DRAW
    private void DrawSurface()
    {
        RecomputeSurface();
        var font = _surf.GetThemeDefaultFont();

        var dom = _dominantChannel;
        var domCol = FamilyColor(dom);

        if (_flip > 0.01f)
        {
            var flipAlpha = Mathf.Lerp(0.35f, 1f, _flip);

            DrawSigilInk(flipAlpha);
            DrawNodes(flipAlpha);

            if (_phase is Phase.Trace or Phase.Settle)
                DrawPacePoint(domCol);
        }

        if (_sealFlash > 0)
        {
            var ph = (float)(1 - _sealFlash / 0.6);
            CraftFx.RingPulse(_surf, W2S(_sealFlashPos), 26f * _S, ph, new Color(Ink.R, Ink.G, Ink.B, 0.85f), 3.5f * _S, 1.2f);
        }

        // floating effect labels ("Ember!", ...) â€” screen-space via W2S, rise + fade
        DrawFloats(font);

        if (_phase == Phase.Settle)
            DrawSealFlourish();

        // big HUD: speed gauge + effect stack list + progress â€” screen-space (not camera-relative)
        DrawHud(font);

        if (_phase == Phase.Plan && _flip < 1f)
            CraftFx.RingPulse(_surf, W2S(SigilCentroid()), 90f * _S, _flip, new Color(Accent.R, Accent.G, Accent.B, 0.6f), 3f * _S, 0.8f);

        // #16 F1 log gutter
        if (_dev.ShowLog)
        {
            var size = _surf.Size;
            var rect = new Rect2(size.X - 250, 8, 242, size.Y - 16);
            _dev.DrawLog(_surf, rect, font, new List<(string, Color)>
            {
                ($"speed x{SpeedMult():0.0}  click {_clickCleanHits}/{_clickMisses}", UiTheme.Text),
                ($"space {_spaceCleanHits}/{_spaceMisses}  pace {_paceArc / _totalArc * 100:0}%", new Color(0.86f, 0.8f, 0.98f)),
                ($"effects {_effectTotal}  rich {EffectRichness() * 100:0}%", Accent),
                ($"phase {_phase}", Accent),
            });
        }
    }

    // #1 draw the sigil polyline: split at the pen head â€” behind = imprinted gold, ahead = dim unwritten ink.
    private void DrawSigilInk(float alpha)
    {
        var dimCol = new Color(Accent.R * 0.6f, Accent.G * 0.6f, Accent.B * 0.7f, 0.30f * alpha);
        var goldTint = Ink;
        double acc = 0;
        for (var ei = 0; ei < _edges.Count; ei++)
        {
            var e = _edges[ei];
            var a = W2S(_nodes[e.A].Pos); var b = W2S(_nodes[e.B].Pos);
            var segStart = acc; var segEnd = acc + e.Length;

            if (_paceArc >= segEnd)
                DrawInkSegment(a, b, goldTint, alpha, true);
            else if (_paceArc <= segStart)
                _surf.DrawLine(a, b, dimCol, 3f * _S);
            else
            {
                var t = (float)Math.Clamp((_paceArc - segStart) / Math.Max(1e-3, e.Length), 0, 1);
                var mid = a.Lerp(b, t);
                DrawInkSegment(a, mid, goldTint, alpha, true);
                _surf.DrawLine(mid, b, dimCol, 3f * _S);
            }
            acc = segEnd;
        }
    }

    private void DrawInkSegment(Vector2 a, Vector2 b, Color col, float alpha, bool glow)
    {
        if (glow)
        {
            _surf.DrawLine(a, b, new Color(col.R, col.G, col.B, 0.18f * alpha), 8f * _S);
            _surf.DrawLine(a, b, new Color(col.R, col.G, col.B, 0.35f * alpha), 5f * _S);
        }
        _surf.DrawLine(a, b, new Color(col.R, col.G, col.B, 0.95f * alpha), 3f * _S);
    }

    // draw every node through the single standardized DrawNode() so NORMAL vs SPECIAL reads consistently everywhere.
    private void DrawNodes(float alpha)
    {
        for (var i = 0; i < _nodes.Count; i++)
        {
            var node = _nodes[i];
            var passed = _paceArc >= NodeArc(i) - 1e-3;
            var clicked = _clickResolved.Contains(i);
            var wasClean = _cleanHitSet.Contains(i);
            DrawNode(W2S(node.Pos), node.IsSpecial, node.Family, alpha, passed, clicked, wasClean);
        }
    }

    // ---- THE SINGLE STANDARDIZED NODE RENDERER ----
    // NORMAL: a small, neutral pale-gold dot (quiet â€” you just click it).
    // SPECIAL: color-coded by effect family with a STANDARD visual language so the same family ALWAYS looks the same:
    //   hue      = family colour (fire=orange, ice=cyan, earth=amber, life=green, shadow=violet, air=pale)
    //   size     = family size scale (fire biggest, ice medium, earth blocky, ... learnable)
    //   glow     = family glow intensity (a soft additive halo whose strength encodes the family)
    //   feature  = an extra readable marker per family (pulse ring / spikes / square / cross / etc.)
    // Enforcing the standard in ONE place means every special of a family is instantly recognisable.
    private void DrawNode(Vector2 pos, bool special, int family, float alpha,
                          bool passed, bool clicked, bool wasClean)
    {
        if (!special)
        {
            // ---- NORMAL node: small neutral dot ----
            var nr = 12f * _S;
            if (wasClean)
            {
                var gold = UiTheme.Rarity["legendary"];
                CraftFx.Glow(_surf, pos, nr * 1.5f, new Color(gold.R, gold.G, gold.B, 0.45f * alpha), 4);
                _surf.DrawCircle(pos, nr, new Color(gold.R, gold.G, gold.B, 0.92f * alpha));
            }
            else if (clicked)  // clicked but off-timing â†’ muddy
            {
                _surf.DrawCircle(pos, nr * 0.9f, new Color(Muddy.R, Muddy.G, Muddy.B, 0.7f * alpha));
                CraftFx.Ring(_surf, pos, nr, new Color(Muddy.R, Muddy.G, Muddy.B, 0.5f * alpha), 2f * _S);
            }
            else if (passed)
            {
                _surf.DrawCircle(pos, nr * 0.8f, new Color(NormalDot.R * 0.6f, NormalDot.G * 0.6f, NormalDot.B * 0.6f, 0.55f * alpha));
            }
            else
            {
                _surf.DrawCircle(pos, nr, new Color(NormalDot.R, NormalDot.G, NormalDot.B, 0.75f * alpha));
                CraftFx.Ring(_surf, pos, nr, new Color(NormalDot.R, NormalDot.G, NormalDot.B, 0.55f * alpha), 1.6f * _S);
            }
            return;
        }

        // ---- SPECIAL node: the standardized color-coded language ----
        var fam = Math.Clamp(family, 0, 5);
        var col = NodeColor(fam);
        var sizeScale = SpecialSize(fam);         // family-fixed size
        var glowScale = SpecialGlow(fam);         // family-fixed glow intensity
        var baseR = 16f * sizeScale * _S;

        // a gentle idle pulse so specials read as "alive / do something here"; frozen once passed/consumed
        var live = !passed && !clicked;
        var pulse = live ? 1f + 0.10f * Mathf.Sin((float)_anim * 4f + fam) : 1f;
        var r = baseR * pulse;

        if (wasClean)
        {
            var gold = UiTheme.Rarity["legendary"];
            // keep the family read even on a clean hit (tint the gold toward the family so it stays recognisable)
            var mixed = new Color(gold.R, gold.G, gold.B).Lerp(col, 0.35f);
            CraftFx.Glow(_surf, pos, r * 1.9f, new Color(mixed.R, mixed.G, mixed.B, 0.55f * alpha * glowScale), 5);
            _surf.DrawCircle(pos, r, new Color(mixed.R, mixed.G, mixed.B, 0.95f * alpha));
            DrawSpecialFeature(pos, fam, r, new Color(mixed.R, mixed.G, mixed.B, 0.9f * alpha));
            return;
        }
        if (clicked && !wasClean)  // clicked but off-timing â†’ muddy but keep the family shape/size so it stays readable
        {
            _surf.DrawCircle(pos, r * 0.9f, new Color(Muddy.R, Muddy.G, Muddy.B, 0.7f * alpha));
            DrawSpecialFeature(pos, fam, r, new Color(Muddy.R, Muddy.G, Muddy.B, 0.6f * alpha));
            return;
        }

        var a = passed ? 0.5f : 0.9f;
        // the defining halo â€” its size + intensity are the family's glow signature
        CraftFx.Glow(_surf, pos, r * (1.7f + 0.5f * glowScale), new Color(col.R, col.G, col.B, (passed ? 0.28f : 0.5f) * alpha * glowScale), 5);
        _surf.DrawCircle(pos, r, new Color(col.R, col.G, col.B, a * alpha));
        _surf.DrawCircle(pos, r * 0.55f, new Color(CraftColor.Brighten(col, 0.28f).R, CraftColor.Brighten(col, 0.28f).G, CraftColor.Brighten(col, 0.28f).B, a * alpha));
        DrawSpecialFeature(pos, fam, r, new Color(col.R, col.G, col.B, (passed ? 0.5f : 0.95f) * alpha));
    }

    // family-fixed SIZE scale (part of the standard visual language) â€” fire biggest, air smallest, earth blocky-mid.
    private static float SpecialSize(int fam) => fam switch
    {
        MinigameTagEffects.HEAT => 1.30f,   // fire â€” large
        MinigameTagEffects.AQUA => 1.05f,   // ice  â€” medium
        MinigameTagEffects.TERRA => 1.15f,  // earth â€” blocky mid
        MinigameTagEffects.GROVE => 1.10f,  // life â€” mid
        MinigameTagEffects.UMBRA => 1.00f,  // shadow â€” compact
        MinigameTagEffects.AIR => 0.95f,    // air â€” small/light
        _ => 1.0f,
    };
    // family-fixed GLOW intensity (part of the standard visual language) â€” fire hottest, earth dullest.
    private static float SpecialGlow(int fam) => fam switch
    {
        MinigameTagEffects.HEAT => 1.35f,
        MinigameTagEffects.AQUA => 1.05f,
        MinigameTagEffects.TERRA => 0.80f,
        MinigameTagEffects.GROVE => 1.00f,
        MinigameTagEffects.UMBRA => 1.20f,
        MinigameTagEffects.AIR => 0.90f,
        _ => 1.0f,
    };

    // the EXTRA readable feature per family (the "additional visual features" the player asked for). One per family,
    // always the same, drawn with plain 2D primitives (no shaders, ASCII-only where text is used):
    //   fire   = spikes (radiating flame tongues)
    //   ice    = a crisp outer ring (frost halo)
    //   earth  = a square (blocky, solid)
    //   life   = a plus/cross (growth)
    //   shadow = a dim inner void (dark core)
    //   air    = light orbiting motes (fast/light)
    private void DrawSpecialFeature(Vector2 pos, int fam, float r, Color col)
    {
        switch (fam)
        {
            case MinigameTagEffects.HEAT:   // spikes
                for (var s = 0; s < 8; s++)
                {
                    var ang = Mathf.Tau * s / 8f + (float)_anim * 0.6f;
                    var d = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang));
                    _surf.DrawLine(pos + d * r * 0.9f, pos + d * r * 1.5f, col, 2.2f * _S);
                }
                break;
            case MinigameTagEffects.AQUA:   // frost ring
                CraftFx.Ring(_surf, pos, r * 1.4f, col, 2.4f * _S);
                break;
            case MinigameTagEffects.TERRA:  // square (blocky)
            {
                var s = r * 1.05f;
                var rect = new Rect2(pos.X - s, pos.Y - s, s * 2, s * 2);
                _surf.DrawRect(rect, col, false, 2.4f * _S);
                break;
            }
            case MinigameTagEffects.GROVE:  // plus / cross (growth)
                _surf.DrawLine(pos + new Vector2(-r * 1.4f, 0), pos + new Vector2(r * 1.4f, 0), col, 2.4f * _S);
                _surf.DrawLine(pos + new Vector2(0, -r * 1.4f), pos + new Vector2(0, r * 1.4f), col, 2.4f * _S);
                break;
            case MinigameTagEffects.UMBRA:  // dark void core
                _surf.DrawCircle(pos, r * 0.35f, new Color(0.05f, 0.02f, 0.08f, col.A));
                CraftFx.Ring(_surf, pos, r * 1.35f, col, 2f * _S);
                break;
            case MinigameTagEffects.AIR:    // orbiting motes
                for (var s = 0; s < 3; s++)
                {
                    var ang = Mathf.Tau * s / 3f + (float)_anim * 2.2f;
                    var d = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang));
                    _surf.DrawCircle(pos + d * r * 1.5f, 2.4f * _S, col);
                }
                break;
        }
    }

    // #11 pen-head marker + the CONTRACTING timing ring around the next node (the visual timing tell)
    private void DrawPacePoint(Color domCol)
    {
        var (paceWorld, _, _) = ArcToWorld(_paceArc);
        var pp = W2S(paceWorld);

        // draw a timing ring around the NEXT live node (the one the player is timing toward). It CONTRACTS toward the
        // node and turns gold when the input window is OPEN, so the click reads as "now".
        if (_nextNode < _nodes.Count)
        {
            var nodeArc = NodeArc(_nextNode);
            var tolArc = Math.Max(1.0, _nodes[_nextNode].HazardWindow * _speed);
            var toGo = nodeArc - _paceArc;
            if (toGo <= tolArc * 3.5)
            {
                var np = W2S(_nodes[_nextNode].Pos);
                var contract = (float)Math.Clamp(toGo / (tolArc * 3.5), 0, 1);
                var ringR = (18f + contract * 46f) * _S;
                var inWindow = Math.Abs(toGo) <= tolArc;
                var stillOpen = !_clickResolved.Contains(_nextNode);
                var col = inWindow && stillOpen ? new Color(Ink.R, Ink.G, Ink.B, 0.95f) : new Color(domCol.R, domCol.G, domCol.B, 0.55f);
                CraftFx.Ring(_surf, np, ringR, col, (inWindow ? 3.5f : 2f) * _S);
                if (inWindow && stillOpen)
                    CraftFx.Glow(_surf, np, 14f * _S, new Color(Ink.R, Ink.G, Ink.B, 0.5f), 4);
            }
        }

        // the pen head itself â€” a bright travelling scribe head; a faster head glows brighter
        var speedGlow = 16f + 10f * (float)Math.Clamp((SpeedMult() - 1) / 3.0, 0, 1);
        CraftFx.Glow(_surf, pp, speedGlow * _S, new Color(domCol.R, domCol.G, domCol.B, 0.6f), 5);
        _surf.DrawCircle(pp, 6f * _S, CraftColor.Brighten(Ink, 0.15f));
        CraftFx.Ring(_surf, pp, 9f * _S, new Color(1, 1, 1, 0.6f), 1.5f * _S);
    }

    private void DrawFloats(Font font)
    {
        foreach (var fl in _floats)
        {
            var t = (float)Math.Clamp(fl.Age / fl.Life, 0, 1);
            var rise = -46f * t * _S;
            var a = 1f - t;
            var pos = W2S(fl.World) + new Vector2(-30f * _S, rise);
            var c = new Color(fl.Col.R, fl.Col.G, fl.Col.B, a);
            // shadow for legibility
            _surf.DrawString(font, pos + new Vector2(1.5f, 1.5f), fl.Text, HorizontalAlignment.Center, 120f * _S, (int)(20 * _S), new Color(0, 0, 0, a * 0.8f));
            _surf.DrawString(font, pos, fl.Text, HorizontalAlignment.Center, 120f * _S, (int)(20 * _S), c);
        }
    }

    private void DrawSealFlourish()
    {
        var perf = ComputePerf();
        var band = CraftFx.Band(perf);
        var gold = UiTheme.Rarity["legendary"];
        var seals = _cleanHitSet.Where(i => i < _nodes.Count).OrderBy(i => i).ToList();
        for (var i = 0; i < seals.Count; i++)
        {
            if (_settleClock >= i * 0.04)
            {
                var p = W2S(_nodes[seals[i]].Pos);
                var phase = (float)Math.Clamp((_settleClock - i * 0.04) / 0.4, 0, 1);
                CraftFx.RingPulse(_surf, p, 18f * _S, phase, new Color(gold.R, gold.G, gold.B, 0.7f), 3f * _S, 1.0f);
            }
        }
        var cphase = (float)Math.Clamp(_settleClock / SETTLE_DUR, 0, 1);
        if (_nodes.Count > 0)
            CraftFx.RingPulse(_surf, W2S(_nodes[^1].Pos), 60f * _S, cphase, new Color(band.Col.R, band.Col.G, band.Col.B, 0.6f), 4f * _S, 1.2f);
    }

    // ==================================================================== BIG HUD (Â§6, larger + persistent legend)
    // A left SPEED gauge (filling, colour-graded), a right STACKED-EFFECTS list, a top progress bar + node pips.
    private void DrawHud(Font font)
    {
        var size = _surf.Size;

        // --- top: pace/arc progress bar (wide) ---
        var barW = Mathf.Min(720f, size.X * 0.55f);
        var barX = (size.X - barW) * 0.5f;
        var progR = new Rect2(barX, 26f, barW, 12f);
        CraftFx.Bar(_surf, progR, (float)(_paceArc / _totalArc),
            new Color(0.10f, 0.09f, 0.14f, 0.8f), new Color(Ink.R, Ink.G, Ink.B, 0.85f));
        _surf.DrawString(font, new Vector2(barX, 20f), "RUNE PROGRESS", HorizontalAlignment.Left, -1, 12, new Color(0.8f, 0.78f, 0.95f, 0.8f));

        // node pips row (clean = gold, clicked-miss = muddy, passed = faint, ahead = faint; specials ringed) â€” top-left
        var gold = UiTheme.Rarity["legendary"];
        var dim = new Color(Accent.R, Accent.G, Accent.B, 0.22f);
        for (var i = 0; i < _nodes.Count; i++)
        {
            var row = i / 20; var colu = i % 20;
            var pos = new Vector2(30 + colu * 20, 52 + row * 18);
            Color c;
            if (_cleanHitSet.Contains(i)) c = new Color(gold.R, gold.G, gold.B, 0.95f);
            else if (_clickResolved.Contains(i)) c = new Color(Muddy.R, Muddy.G, Muddy.B, 0.6f);
            else if (_paceArc >= NodeArc(i) - 1e-3) c = new Color(0.8f, 0.6f, 0.35f, 0.45f);
            else c = _nodes[i].IsSpecial ? new Color(NodeColor(_nodes[i].Family).R, NodeColor(_nodes[i].Family).G, NodeColor(_nodes[i].Family).B, 0.85f) : dim;
            _surf.DrawCircle(pos, 5f, c);
            if (_nodes[i].IsSpecial) CraftFx.Ring(_surf, pos, 7f, new Color(NodeColor(_nodes[i].Family).R, NodeColor(_nodes[i].Family).G, NodeColor(_nodes[i].Family).B, 0.6f), 1.4f);
        }

        // --- LEFT: big SPEED GAUGE (a vertical filling meter, colour-graded by how fast you're going) ---
        DrawSpeedGauge(font, size);

        // --- RIGHT: STACKED EFFECTS list (the tactile payoff) ---
        DrawEffectStack(font, size);
    }

    // the speed gauge â€” a tall vertical bar on the left that fills toward MAX as the pen head compounds. Colour graded
    // (cool â†’ hot) so "I am flying" is felt. A tiny "xN" tick is the only number, and it's a light read.
    private void DrawSpeedGauge(Font font, Vector2 size)
    {
        var gx = 24f; var gTop = 110f; var gH = Mathf.Min(300f, size.Y * 0.42f); var gW = 22f;
        var track = new Rect2(gx, gTop, gW, gH);
        CraftFx.RoundRect(_surf, track, new Color(0.06f, 0.06f, 0.09f, 0.85f), new Color(1, 1, 1, 0.1f), 1, 6);

        // fill fraction: how far between base and max the current speed sits
        var frac = (float)Math.Clamp((_speed - _baseSpeed) / Math.Max(1.0, _maxSpeed - _baseSpeed), 0, 1);
        // colour: cool blue at base â†’ gold â†’ hot red-orange near max
        var lo = new Color(0.4f, 0.7f, 1f); var mid = Ink; var hi = new Color(1f, 0.45f, 0.2f);
        var fillCol = frac < 0.5f ? lo.Lerp(mid, frac * 2f) : mid.Lerp(hi, (frac - 0.5f) * 2f);
        var fillH = gH * frac;
        if (fillH > 1)
        {
            var fr = new Rect2(gx, gTop + gH - fillH, gW, fillH);
            CraftFx.RoundRect(_surf, fr, new Color(fillCol.R, fillCol.G, fillCol.B, 0.9f), null, 0, 6);
            var edge = new Vector2(gx + gW * 0.5f, gTop + gH - fillH);
            CraftFx.Glow(_surf, edge, 12f + 6f * (float)Math.Min(1, _cleanStreak * 0.2f), new Color(fillCol.R, fillCol.G, fillCol.B, 0.7f));
        }

        _surf.DrawString(font, new Vector2(gx - 2, gTop - 8), "SPEED", HorizontalAlignment.Left, -1, 13, new Color(0.9f, 0.85f, 1f, 0.9f));
        // light multiplier tick (the only allowed number; the gauge fill is the primary read)
        _surf.DrawString(font, new Vector2(gx - 2, gTop + gH + 18), $"x{SpeedMult():0.0}", HorizontalAlignment.Left, -1, 15,
            new Color(fillCol.R, fillCol.G, fillCol.B, 0.95f));
    }

    // the stacked-effects list â€” one line per active theme with its count, colour-coded to its channel. Building this
    // up is the payoff for firing SPACE on SPECIAL nodes.
    private void DrawEffectStack(Font font, Vector2 size)
    {
        var x = size.X - 210f; var y = 110f;
        _surf.DrawString(font, new Vector2(x, y), "ENCHANTS", HorizontalAlignment.Left, -1, 15, new Color(0.92f, 0.85f, 1f, 0.95f));
        y += 26f;
        var any = false;
        for (var ch = 0; ch < MinigameTagEffects.N; ch++)
        {
            var count = _effectStacks[ch];
            if (count <= 0) continue;
            any = true;
            var col = NodeColor(ch);
            // a fresh stack pops brighter for a beat
            var pop = (_lastEffectCh == ch && _effectFlash > 0) ? 1f + 0.6f * (float)_effectFlash : 1f;
            var c = new Color(Mathf.Min(1, col.R * pop), Mathf.Min(1, col.G * pop), Mathf.Min(1, col.B * pop), 0.95f);
            _surf.DrawCircle(new Vector2(x + 8, y - 5), 7f, c);
            _surf.DrawString(font, new Vector2(x + 22, y), $"{EffectName[ch]}  x{count}", HorizontalAlignment.Left, -1, 15, c);
            y += 24f;
        }
        if (!any)
            _surf.DrawString(font, new Vector2(x, y), "(Space on a glowing special to fire)", HorizontalAlignment.Left, -1, 13, new Color(0.7f, 0.7f, 0.8f, 0.6f));
    }

    // ---- colour helpers (Â§2.4) ----
    private static Color FamilyColor(int ch) => MinigameTagEffects.FamilyColor(Math.Clamp(ch, 0, 5));

    private static Color NodeColor(int family)
    {
        var fc = FamilyColor(Math.Clamp(family, 0, 5));
        var demud = CraftColor.DeMuddy(fc, fc, 0.0f, 0.55f, 0.62f);
        return CraftColor.Brighten(demud, 0.05f);
    }

    // ---- small readouts ----
    private double SpeedMult() => _baseSpeed > 1e-3 ? _speed / _baseSpeed : 1.0;

    // track which resolved nodes were CLEAN click hits (for the pip / node colour) â€” cheap set kept in sync
    private readonly HashSet<int> _cleanHitSet = new();

    private string EffectListString()
    {
        var parts = new List<string>();
        for (var ch = 0; ch < MinigameTagEffects.N; ch++)
            if (_effectStacks[ch] > 0) parts.Add($"{EffectName[ch]}x{_effectStacks[ch]}");
        return string.Join(", ", parts);
    }
}
