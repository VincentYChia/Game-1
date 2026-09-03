using Godot;
using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Godot;

/// <summary>
/// Alchemy essence model + reaction chemistry (only consumed by <see cref="AlchemyMinigame"/>).
///
/// A reagent dissolves into SIX primary channels (fire/water/earth/life/shadow/air). ONLY primaries interact —
/// every meaningful pair (two split by heat) collapses to a NAMED <see cref="State"/> with a magnitude 0..1 that
/// scales both its chemistry and its animation. Every OTHER tag is a MODIFIER (<see cref="BuildProfile"/>): potency ×,
/// volatility ±, reaction-time ×, reaction-vigor ×. Tier is a moderate global multiplier on potency + vigor.
///
/// Raw ingredients are INERT (fixed P/V). A merge starts a reaction window (<see cref="Evolve"/>): states fire,
/// transmute channels, and bias P/V, which EASE toward composition-derived equilibria; after the window the
/// mixture settles and holds (no drift, no runaway, no waiting-out). Quality = closeness-to-target-VOLATILITY
/// (base) × resisted-POTENCY (multiplier).
/// </summary>
public static class MinigameTagEffects
{
    public const int HEAT = 0, AQUA = 1, TERRA = 2, GROVE = 3, UMBRA = 4, AIR = 5, N = 6;
    public const int FIRE = HEAT;

    public const double HOT = 55, WARM = 42, HEAT_MAX = 100;   // heat reference points (for visuals / log)
    public const double ReactionTime = 3.5;   // a fresh mixture reacts for this long, then SETTLES and holds (no drift)
    // (B-D1) "edge = faster = harder": volatility eases faster the closer it sits to the SCORED target — parking on
    // the target is unstable and must be actively held. (B-D3) a hot mixture ticks that ease up to +50% faster NOW.
    public const double EASE_V_BASE = 2.4;     // floor ease-rate for volatility (was the inline 2.4)
    public const double EDGE_GAIN = 1.8;       // up to +180% ease-rate when vol sits on the scored target
    public const double EDGE_SIGMA = 18.0;     // volatility units — REUSE the Quality σ so "edge" == the scored bell band
    public const double HEAT_TICK_GAIN = 0.5;  // hot mixture ticks its equilibrium-ease up to +50% faster

    // ============================ NAMED INTERACTION STATES ============================
    // Every meaningful pair of primaries collapses to a NAMED state (two pairs split by heat). A mixture can hold
    // several at once, each with a magnitude 0..1 that scales BOTH its chemistry and its animation. This finite list
    // is the WHOLE visual/effect vocabulary — 17 states rendered by 7 primitives (colour + magnitude vary them).
    public enum State
    {
        None = 0,
        Steam, Quench,            // FIRE+WATER  (hot / cool)
        Molten, Temper,           // FIRE+EARTH  (hot / cool)
        Scorch,                   // FIRE+LIFE
        Blaze,                    // FIRE+AIR
        Brimstone,                // FIRE+SHADOW
        Silt,                     // WATER+EARTH
        Bloom,                    // WATER+LIFE
        Mist,                     // WATER+AIR
        Brine,                    // WATER+SHADOW
        Root,                     // EARTH+LIFE
        Crystallize,              // EARTH+SHADOW
        Dust,                     // EARTH+AIR
        Decay,                    // LIFE+SHADOW
        Spore,                    // LIFE+AIR
        Smoke,                    // SHADOW+AIR
    }
    public const int StateCount = 18;   // includes None at index 0

    // Alchemy's mapping of each named State → the shared coarse StateVisual.Look (see StateVisual.cs). The fine
    // renderer picks a primitive per State directly; this table + LookOf() let a future refactor drive
    // StateVisual.DrawLook instead. The Look enum itself now lives in StateVisual so every discipline shares it.

    private static readonly string[] StateNames =
    { "—", "Steam", "Quench", "Molten", "Temper", "Scorch", "Blaze", "Brimstone", "Silt", "Bloom", "Mist", "Brine", "Root", "Crystallize", "Dust", "Decay", "Spore", "Smoke" };
    private static readonly StateVisual.Look[] StateLook =
    { StateVisual.Look.None, StateVisual.Look.Rise, StateVisual.Look.Ripple, StateVisual.Look.Lava, StateVisual.Look.Core, StateVisual.Look.Rise, StateVisual.Look.Lava, StateVisual.Look.Ring, StateVisual.Look.Veins, StateVisual.Look.Veins, StateVisual.Look.Rise, StateVisual.Look.Ripple, StateVisual.Look.Veins, StateVisual.Look.Shards, StateVisual.Look.Rise, StateVisual.Look.Veins, StateVisual.Look.Rise, StateVisual.Look.Rise };
    private static readonly (float H, float S, float V)[] StateHsv =
    {
        (0,0,0), (0.55f,0.06f,1f), (0.57f,0.60f,0.95f), (0.05f,0.90f,1f), (0.11f,0.60f,1f), (0.07f,0.18f,0.5f), (0.09f,0.85f,1f), (0.92f,0.70f,0.9f),
        (0.09f,0.50f,0.55f), (0.33f,0.70f,0.9f), (0.53f,0.15f,0.98f), (0.48f,0.50f,0.7f), (0.25f,0.55f,0.7f), (0.83f,0.55f,0.95f), (0.10f,0.40f,0.75f), (0.20f,0.65f,0.7f), (0.35f,0.45f,0.9f), (0.78f,0.40f,0.55f),
    };
    // per-state biases: PotBias adds to the potency multiplier; VolBias adds to the volatility equilibrium
    private static readonly double[] StatePot =
    { 0, -0.10, +0.05, +0.20, +0.15, -0.25, +0.10, +0.28, 0.00, +0.30, -0.05, +0.08, +0.22, +0.25, -0.05, +0.18, +0.10, +0.10 };
    private static readonly double[] StateVol =
    { 0, -14, -10, +4, -10, +10, +14, +18, -18, -6, -12, -8, -12, -16, -8, +12, -2, -10 };

    public static StateVisual.Look LookOf(State s) => StateLook[(int)s];
    public static string StateName(State s) => StateNames[(int)s];
    public static Color StateColor(State s) { var h = StateHsv[(int)s]; return Color.FromHsv(h.H, h.S, h.V); }

    // ============================ PER-TAG MODIFIERS ============================
    // Every non-primary tag is a pure MODIFIER: a mild uniform BASE (pot ×, vol ±, time ×, rx ×) plus 1-3
    // narrative EXCEPTIONS (boost/suppress a primary channel, amplify/damp a state, or add pot/vol when a primary
    // is present). Modifiers STACK across merged reagents with diminishing returns. See docs/ALCHEMY_MODIFIER_BANK.md.

    // BASE table — grades follow INCREASING RETURNS (higher tier = more potency, LESS volatility, accelerating).
    private static readonly Dictionary<string, (double Pot, double Vol, double Time, double Rx)> ModTable = new()
    {
        // quality & grade (monotone: pot up, vol down with tier)
        ["starter"] = (0.86, +4, 1.05, 0.90), ["basic"] = (0.90, +3, 1.0, 1.0), ["common"] = (0.95, +1, 1.0, 1.0), ["standard"] = (1.00, 0, 1.05, 0.98),
        ["uncommon"] = (1.05, -1, 1.0, 1.05), ["fine"] = (1.08, -2, 1.05, 1.0), ["quality"] = (1.11, -3, 1.05, 1.0), ["refined"] = (1.13, -5, 1.05, 0.95),
        ["rare"] = (1.16, -5, 1.0, 1.05), ["advanced"] = (1.19, -7, 0.95, 1.10), ["precious"] = (1.22, -9, 1.10, 0.95), ["ancient"] = (1.25, -11, 1.35, 0.80),
        ["legendary"] = (1.28, -11, 1.0, 1.05), ["mythical"] = (1.32, -14, 1.05, 1.0),
        ["superior"] = (1.14, -4, 1.0, 1.0), ["epic"] = (1.22, -8, 1.0, 1.05), ["pure"] = (1.10, -12, 1.0, 0.95), ["mundane"] = (0.85, 0, 1.0, 0.85), ["holy"] = (1.15, -4, 1.0, 1.05),
        ["material"] = (1.00, -1, 1.05, 0.95), ["elemental"] = (1.10, +5, 0.90, 1.20),
        // energy & essence
        ["magical"] = (1.15, -2, 1.05, 1.0), ["arcane"] = (1.20, -4, 1.10, 0.95), ["essence"] = (1.20, +1, 1.05, 1.05), ["radiant"] = (1.18, +2, 1.0, 1.10),
        ["light"] = (1.10, -3, 1.0, 1.05), ["spectral"] = (0.90, +4, 1.30, 0.85), ["blood"] = (1.12, +5, 0.90, 1.20), ["chaos"] = (1.00, +14, 0.70, 1.55),
        ["lightning"] = (1.05, +9, 0.75, 1.50), ["temporal"] = (1.10, -6, 1.40, 0.70),
        // toxic / bodily
        ["venom"] = (1.10, +3, 0.95, 1.1), ["poison"] = (1.10, +3, 1.0, 1.1), ["toxic"] = (1.10, +3, 1.0, 1.1), ["acid"] = (1.08, +4, 0.9, 1.3),   // (C.2-b) trimmed base Vol; degrade-over-time via Decay StExc
        ["monster"] = (1.06, +3, 1.0, 1.05), ["fang"] = (1.05, +2, 0.95, 1.05), ["scales"] = (1.05, -2, 1.05, 0.95), ["bone"] = (1.04, -3, 1.1, 0.9), ["gel"] = (0.96, -2, 1.05, 0.95), ["carapace"] = (1.05, -4, 1.1, 0.9),
        // fiery / shadow variants (void/dark also carry a BODY; these are their rider effects)
        ["volcanic"] = (1.05, +10, 0.85, 1.4), ["molten"] = (1.05, +10, 0.85, 1.4), ["storm"] = (1.05, +8, 0.8, 1.3), ["ember"] = (1.0, +4, 0.95, 1.2), ["forge"] = (1.02, +3, 0.95, 1.2), ["flame"] = (1.0, +4, 0.95, 1.15),
        ["void"] = (1.05, +5, 1.10, 0.80), ["dark"] = (1.00, +4, 1.05, 0.90), ["shadow"] = (1.03, +3, 1.0, 1.02),
        // cold / stabilising / slow
        ["frozen"] = (1.0, -8, 1.3, 0.5), ["ice"] = (1.0, -6, 1.2, 0.7), ["frost"] = (1.0, -6, 1.15, 0.75), ["chill"] = (1.0, -5, 1.1, 0.8),
        ["stone"] = (1.0, -5, 1.25, 0.8), ["mineral"] = (1.0, -4, 1.2, 0.8), ["sand"] = (1.0, -3, 1.05, 0.95),
        ["metal"] = (1.02, -4, 1.2, 0.85), ["metallic"] = (1.05, +2, 0.95, 1.20), ["iron"] = (1.02, -4, 1.2, 0.85), ["alloy"] = (1.15, -3, 1.05, 1.0), ["steel"] = (1.06, -4, 1.2, 0.85), ["bronze"] = (1.04, -3, 1.2, 0.85),
        ["mithril"] = (1.15, -2, 1.1, 1), ["adamantine"] = (1.20, -4, 1.25, 0.9), ["orichalcum"] = (1.20, +2, 1.1, 1.05), ["gold"] = (1.10, -2, 1.1, 0.95), ["silver"] = (1.08, -2, 1.1, 0.95),
        ["gem"] = (1.10, -3, 1.2, 0.85), ["crystal"] = (1.08, -4, 1.2, 0.85),
        // physical & structural
        ["durable"] = (1.0, -3, 1.20, 0.90), ["strong"] = (1.10, -2, 1.0, 1.10), ["sharp"] = (1.05, +3, 0.85, 1.25), ["hard"] = (1.0, -5, 1.10, 0.90),
        ["layered"] = (1.0, -2, 1.30, 0.85), ["versatile"] = (1.05, -1, 1.0, 1.05), ["flexible"] = (1.0, -4, 1.20, 0.95), ["memory"] = (1.05, -4, 1.15, 0.95),
        ["solid"] = (1.0, -8, 1.25, 0.75), ["dense"] = (1.0, -6, 1.3, 0.7), ["heavy"] = (1.0, -4, 1.3, 0.75),
        // airy / quick
        ["wind"] = (1.0, 0, 0.8, 1.15), ["gas"] = (1.0, +2, 0.75, 1.2), ["vapor"] = (1.0, 0, 0.8, 1.1),
        // life
        ["herb"] = (1.06, -2, 1.0, 1.05), ["plant"] = (1.04, -2, 1.0, 1.0), ["living"] = (1.05, 0, 1.0, 1.05), ["leather"] = (1.0, -2, 1.1, 0.9), ["wood"] = (1.0, -2, 1.1, 0.9),
        // exotic & special
        ["quantum"] = (1.0, +4, 0.90, 1.15), ["impossible"] = (1.20, +6, 1.05, 1.10), ["dangerous"] = (1.10, +11, 0.75, 1.45), ["harmony"] = (1.10, -8, 1.15, 0.90), ["power"] = (1.25, +3, 1.05, 1.15),
        // function / output (light treatment, by role)
        ["potion"] = (1.02, -2, 1.05, 0.95), ["healing"] = (1.05, -6, 1.10, 0.85), ["buff"] = (1.10, +2, 0.95, 1.10), ["protection"] = (1.05, -8, 1.20, 0.85),
        ["resistance"] = (1.00, -7, 1.15, 0.90), ["enhancement"] = (1.12, -3, 1.05, 1.0), ["utility"] = (1.00, -2, 1.05, 0.95), ["tool"] = (1.03, -5, 1.20, 0.85),
        ["weapon"] = (1.08, +4, 0.95, 1.15), ["armor"] = (1.04, -9, 1.25, 0.80), ["combat"] = (1.06, +5, 0.90, 1.20), ["consumable"] = (1.00, -3, 1.05, 0.95),
        ["crafting"] = (1.02, -4, 1.15, 0.90), ["engineering"] = (1.04, -6, 1.20, 0.85), ["explosive"] = (1.10, +14, 0.70, 1.50), ["solvent"] = (0.98, -2, 0.95, 1.05),   // (C.2-e) WATER verb: dilute/forgive, not destabilise
        ["fishing"] = (1.00, -4, 1.15, 0.85), ["regeneration"] = (1.05, -6, 1.35, 0.75), ["strength"] = (1.15, +3, 0.95, 1.10), ["defense"] = (1.02, -8, 1.20, 0.85),
        ["speed"] = (1.05, +4, 0.70, 1.30), ["agility"] = (1.04, +3, 0.80, 1.20),
    };

    // EXCEPTION tables — self-conditioned: a channel boost only matters if that primary is present; a state
    // amplify only if that state is active. Values are the FULL-STRENGTH (one copy) multiplier; stacking scales them.
    private static readonly Dictionary<string, (int Ch, double Mul)[]> ChExc = new()
    {
        ["lightning"] = new[] { (HEAT, 1.5), (AQUA, 1.35) }, ["light"] = new[] { (UMBRA, 0.65), (GROVE, 1.3) }, ["radiant"] = new[] { (HEAT, 1.4), (UMBRA, 0.6) },
        ["arcane"] = new[] { (UMBRA, 1.25) }, ["essence"] = new[] { (GROVE, 1.35), (HEAT, 1.3), (UMBRA, 1.3) }, ["spectral"] = new[] { (UMBRA, 1.4), (GROVE, 0.75) },
        ["blood"] = new[] { (GROVE, 1.3), (UMBRA, 1.35) }, ["chaos"] = new[] { (HEAT, 1.5) }, ["void"] = new[] { (HEAT, 0.6), (UMBRA, 1.5) }, ["dark"] = new[] { (UMBRA, 1.3), (GROVE, 0.75) },
        ["impossible"] = new[] { (TERRA, 0.65) }, ["dangerous"] = new[] { (HEAT, 1.5) }, ["power"] = new[] { (HEAT, 1.4) }, ["quantum"] = new[] { (UMBRA, 1.3) },
        ["strong"] = new[] { (TERRA, 1.3) }, ["sharp"] = new[] { (TERRA, 1.25) }, ["hard"] = new[] { (HEAT, 0.85) }, ["durable"] = new[] { (HEAT, 0.8) },
        ["metallic"] = new[] { (TERRA, 1.3) }, ["alloy"] = new[] { (TERRA, 1.3), (UMBRA, 0.8) }, ["flexible"] = new[] { (AIR, 1.2) }, ["layered"] = new[] { (TERRA, 1.25) },
        ["elemental"] = new[] { (HEAT, 1.2), (AQUA, 1.2), (TERRA, 1.2), (GROVE, 1.2), (UMBRA, 1.2), (AIR, 1.2) },   // (C.2-d) all-element touch
        ["refined"] = new[] { (TERRA, 1.2), (UMBRA, 0.8) }, ["precious"] = new[] { (TERRA, 1.2), (UMBRA, 0.8) },
        ["ancient"] = new[] { (TERRA, 1.3) }, ["quality"] = new[] { (UMBRA, 0.85) }, ["strength"] = new[] { (HEAT, 1.25), (TERRA, 1.2) }, ["protection"] = new[] { (TERRA, 1.3) },
        ["armor"] = new[] { (TERRA, 1.3) }, ["defense"] = new[] { (TERRA, 1.3) }, ["speed"] = new[] { (AIR, 1.3) }, ["agility"] = new[] { (AIR, 1.25) }, ["solvent"] = new[] { (AQUA, 1.3), (TERRA, 0.8) },
    };
    private static readonly Dictionary<string, (int St, double Mul)[]> StExc = new()
    {
        ["lightning"] = new[] { ((int)State.Blaze, 1.4), ((int)State.Brimstone, 1.4) },
        ["light"] = new[] { ((int)State.Brimstone, 0.7), ((int)State.Brine, 0.7), ((int)State.Decay, 0.6), ((int)State.Crystallize, 0.7), ((int)State.Bloom, 1.3), ((int)State.Spore, 1.3) },
        ["radiant"] = new[] { ((int)State.Bloom, 1.35) }, ["essence"] = new[] { ((int)State.Bloom, 1.25), ((int)State.Root, 1.25), ((int)State.Decay, 1.25) },
        ["spectral"] = new[] { ((int)State.Brine, 1.3), ((int)State.Decay, 1.3), ((int)State.Mist, 1.35), ((int)State.Smoke, 1.35) },
        ["blood"] = new[] { ((int)State.Bloom, 1.25), ((int)State.Root, 1.25), ((int)State.Decay, 1.3) },
        ["chaos"] = new[] { ((int)State.Blaze, 1.4), ((int)State.Brimstone, 1.4), ((int)State.Decay, 1.35) }, ["temporal"] = new[] { ((int)State.Decay, 1.4), ((int)State.Crystallize, 1.3) },
        ["void"] = new[] { ((int)State.Decay, 1.4) }, ["dark"] = new[] { ((int)State.Bloom, 0.7) }, ["sharp"] = new[] { ((int)State.Decay, 1.4), ((int)State.Scorch, 1.3) },
        ["hard"] = new[] { ((int)State.Crystallize, 1.3) }, ["metallic"] = new[] { ((int)State.Molten, 1.35) }, ["alloy"] = new[] { ((int)State.Temper, 1.4) },
        ["memory"] = new[] { ((int)State.Temper, 1.35), ((int)State.Quench, 1.3), ((int)State.Decay, 0.7) },
        ["harmony"] = new[] { ((int)State.Brimstone, 0.6), ((int)State.Decay, 0.6), ((int)State.Bloom, 1.25) }, ["dangerous"] = new[] { ((int)State.Brimstone, 1.5) },
        ["flexible"] = new[] { ((int)State.Brimstone, 0.7), ((int)State.Blaze, 0.75) }, ["layered"] = new[] { ((int)State.Brimstone, 0.75) },
        ["versatile"] = new[] { ((int)State.Decay, 0.8), ((int)State.Brimstone, 0.8) }, ["durable"] = new[] { ((int)State.Decay, 0.7) }, ["strong"] = new[] { ((int)State.Decay, 0.75) },
        ["precious"] = new[] { ((int)State.Crystallize, 1.3), ((int)State.Decay, 0.8) }, ["ancient"] = new[] { ((int)State.Crystallize, 1.3), ((int)State.Decay, 1.3) },
        ["fine"] = new[] { ((int)State.Decay, 0.85) }, ["arcane"] = new[] { ((int)State.Crystallize, 1.2) }, ["refined"] = new[] { ((int)State.Decay, 0.8), ((int)State.Brine, 0.8), ((int)State.Crystallize, 0.8) },
        ["healing"] = new[] { ((int)State.Bloom, 1.3), ((int)State.Decay, 0.55) }, ["regeneration"] = new[] { ((int)State.Bloom, 1.3), ((int)State.Decay, 0.55) },
        ["metal"] = new[] { ((int)State.Temper, 1.2) }, ["explosive"] = new[] { ((int)State.Blaze, 1.5), ((int)State.Brimstone, 1.4) }, ["combat"] = new[] { ((int)State.Blaze, 1.25) },
        // (C.2-b) toxic = degrade-OVER-TIME: amplify Decay (the life→shadow rot that ramps across the reaction window)
        ["poison"] = new[] { ((int)State.Decay, 1.35) }, ["venom"] = new[] { ((int)State.Decay, 1.35) }, ["toxic"] = new[] { ((int)State.Decay, 1.35) }, ["acid"] = new[] { ((int)State.Decay, 1.45) },
    };
    // strongest-active-state amplifier (quantum/impossible/power): higher-volatility state wins ties
    private static readonly Dictionary<string, double> StrongExc = new() { ["quantum"] = 1.35, ["impossible"] = 1.40, ["power"] = 1.30 };
    // pot/vol added only when a primary is present in the mixture
    private static readonly Dictionary<string, (int Pri, double Pot, double Vol)[]> PvExc = new()
    {
        ["radiant"] = new[] { (HEAT, 0.12, 0.0), (UMBRA, 0.0, 5.0) }, ["essence"] = new[] { (HEAT, 0.10, 0.0) }, ["blood"] = new[] { (UMBRA, 0.0, 5.0), (HEAT, 0.0, 4.0) },
        ["magical"] = new[] { (UMBRA, 0.10, 4.0) }, ["chaos"] = new[] { (HEAT, 0.0, 6.0), (UMBRA, 0.0, 5.0) }, ["lightning"] = new[] { (AQUA, 0.0, 6.0) },
        ["metallic"] = new[] { (AIR, 0.0, 4.0) }, ["void"] = new[] { (UMBRA, 0.0, 6.0) }, ["dangerous"] = new[] { (HEAT, 0.0, 6.0) }, ["power"] = new[] { (HEAT, 0.10, 0.0) },
        ["strong"] = new[] { (TERRA, 0.05, 0.0) }, ["sharp"] = new[] { (TERRA, 0.05, 0.0) }, ["elemental"] = new[] { (HEAT, 0.0, 2.0) }, ["strength"] = new[] { (TERRA, 0.05, 0.0) },
    };

    /// <summary>Modifier profile a reagent/mixture carries — base (stacked) + per-channel / per-state / per-primary
    /// exception multipliers, all resolved against tag counts. Built once per merge, applied every tick in Evolve.
    /// An Alchemy-typed handle on the shared <see cref="MinigameModifierCommon.ModProfile"/> (6 channels, 18 states).</summary>
    public sealed class ModProfile : MinigameModifierCommon.ModProfile
    {
        public ModProfile() : base(N, StateCount) { }
    }

    /// <summary>Diminishing-returns stack scale (delegates to <see cref="MinigameModifierCommon.StackFactor"/>): the
    /// 2nd copy adds ~40% more, the 4th barely anything — layering (separate merges) beats batching. Kept for API stability.</summary>
    public static double StackFactor(int n) => MinigameModifierCommon.StackFactor(n);

    /// <summary>Fold all modifier tags (with COUNTS, for stacking) into one profile; tier lightly boosts vigor.
    /// Uses the shared <see cref="MinigameModifierCommon"/> mechanism over Alchemy's own tables (below).</summary>
    public static ModProfile BuildProfile(IReadOnlyDictionary<string, int> counts, int tier)
    {
        var p = new ModProfile();
        MinigameModifierCommon.Fold(p, counts, ModTable, ChExc, StExc, StrongExc, PvExc);
        p.Rx *= 1 + (Math.Max(1, tier) - 1) * 0.05;   // tier = a moderate vigor bump (potency-by-tier lives in BasePotency)
        MinigameModifierCommon.Clamp(p);
        return p;
    }

    private static readonly Color[] FamCol =
    {
        Color.FromHsv(0.03f, 0.85f, 1.00f), // heat  — red-orange
        Color.FromHsv(0.57f, 0.72f, 0.98f), // aqua  — blue
        Color.FromHsv(0.09f, 0.55f, 0.80f), // terra — earthy gold
        Color.FromHsv(0.32f, 0.66f, 0.85f), // grove — green
        Color.FromHsv(0.78f, 0.60f, 0.85f), // umbra — violet
        Color.FromHsv(0.53f, 0.20f, 0.98f), // air   — pale cyan
    };
    public static Color FamilyColor(int ch) => FamCol[ch];
    public static string ChannelName(int ch) => ch switch
    { HEAT => "fire", AQUA => "water", TERRA => "earth", GROVE => "life", UMBRA => "shadow", AIR => "air", _ => "essence" };

    // tag -> channel + a distinct display hue (so lightning != fire even though both are HEAT) -----------
    private static readonly Dictionary<string, (int Ch, float H, float S, float V)> Tags = new()
    {
        ["fire"] = (HEAT, 0.03f, 0.85f, 1f), ["flame"] = (HEAT, 0.05f, 0.85f, 1f), ["ember"] = (HEAT, 0.06f, 0.80f, 0.95f),
        ["molten"] = (HEAT, 0.02f, 0.9f, 1f), ["forge"] = (HEAT, 0.07f, 0.7f, 0.9f), ["volcanic"] = (HEAT, 0.02f, 0.88f, 0.95f),
        ["lightning"] = (HEAT, 0.55f, 0.55f, 1f), ["storm"] = (HEAT, 0.58f, 0.45f, 0.95f), ["radiant"] = (HEAT, 0.13f, 0.5f, 1f),
        ["chaos"] = (HEAT, 0.88f, 0.7f, 0.95f), ["light"] = (HEAT, 0.14f, 0.25f, 1f),
        ["water"] = (AQUA, 0.57f, 0.72f, 0.98f), ["aqua"] = (AQUA, 0.55f, 0.7f, 0.98f), ["ice"] = (AQUA, 0.52f, 0.45f, 1f),
        ["frost"] = (AQUA, 0.52f, 0.5f, 1f), ["frozen"] = (AQUA, 0.53f, 0.55f, 1f), ["liquid"] = (AQUA, 0.56f, 0.55f, 0.95f), ["chill"] = (AQUA, 0.54f, 0.4f, 0.98f),
        ["earth"] = (TERRA, 0.09f, 0.6f, 0.75f), ["stone"] = (TERRA, 0.08f, 0.3f, 0.7f), ["metal"] = (TERRA, 0.6f, 0.12f, 0.8f),
        ["iron"] = (TERRA, 0.6f, 0.1f, 0.75f), ["crystal"] = (TERRA, 0.5f, 0.35f, 0.95f), ["gem"] = (TERRA, 0.85f, 0.45f, 0.95f),
        ["mineral"] = (TERRA, 0.09f, 0.4f, 0.75f), ["sand"] = (TERRA, 0.12f, 0.45f, 0.85f), ["sharp"] = (TERRA, 0.58f, 0.15f, 0.9f),
        ["alloy"] = (TERRA, 0.6f, 0.12f, 0.82f), ["durable"] = (TERRA, 0.6f, 0.1f, 0.7f), ["strong"] = (TERRA, 0.6f, 0.1f, 0.7f),
        ["wood"] = (GROVE, 0.09f, 0.55f, 0.6f), ["plant"] = (GROVE, 0.33f, 0.6f, 0.7f), ["herb"] = (GROVE, 0.3f, 0.6f, 0.75f),
        ["leather"] = (GROVE, 0.08f, 0.5f, 0.55f), ["living"] = (GROVE, 0.3f, 0.6f, 0.7f), ["monster"] = (GROVE, 0.33f, 0.5f, 0.6f),
        ["fang"] = (GROVE, 0.05f, 0.3f, 0.8f), ["scales"] = (GROVE, 0.4f, 0.45f, 0.65f), ["bone"] = (GROVE, 0.11f, 0.15f, 0.9f), ["gel"] = (GROVE, 0.33f, 0.55f, 0.85f), ["carapace"] = (GROVE, 0.09f, 0.25f, 0.7f),
        ["void"] = (UMBRA, 0.78f, 0.7f, 0.55f), ["dark"] = (UMBRA, 0.76f, 0.55f, 0.45f), ["shadow"] = (UMBRA, 0.77f, 0.5f, 0.45f),
        ["spectral"] = (UMBRA, 0.72f, 0.35f, 0.9f), ["blood"] = (GROVE, 0.99f, 0.75f, 0.6f), ["poison"] = (UMBRA, 0.28f, 0.75f, 0.7f),
        ["venom"] = (UMBRA, 0.3f, 0.75f, 0.68f), ["toxic"] = (UMBRA, 0.26f, 0.7f, 0.7f), ["acid"] = (UMBRA, 0.2f, 0.8f, 0.85f),
        ["arcane"] = (UMBRA, 0.79f, 0.6f, 0.9f), ["magical"] = (UMBRA, 0.78f, 0.58f, 0.9f), ["essence"] = (UMBRA, 0.72f, 0.55f, 0.92f),
        ["air"] = (AIR, 0.53f, 0.2f, 0.98f), ["wind"] = (AIR, 0.53f, 0.18f, 0.98f), ["vapor"] = (AIR, 0.55f, 0.15f, 0.98f), ["gas"] = (AIR, 0.3f, 0.3f, 0.9f),
    };
    private static readonly HashSet<string> Metal = new() { "copper", "tin", "steel", "mithril", "bronze", "adamantine", "silver", "gold", "orichalcum" };
    private static readonly HashSet<string> Wood = new() { "oak", "ash", "ironwood", "ebony", "worldtree", "exotic", "birch", "willow" };
    private static readonly Dictionary<string, double> QualityGrade = new()
    {
        ["basic"] = 0.1, ["starter"] = 0.1, ["common"] = 0.1, ["standard"] = 0.25, ["refined"] = 0.3, ["uncommon"] = 0.4,
        ["fine"] = 0.4, ["quality"] = 0.45, ["rare"] = 0.6, ["advanced"] = 0.6, ["epic"] = 0.75, ["legendary"] = 0.9, ["mythical"] = 1.0, ["ancient"] = 1.0,
    };

    private static (int, float, float, float)? Resolve(string tag)
    {
        if (Tags.TryGetValue(tag, out var v)) return v;
        if (Metal.Contains(tag)) return (TERRA, 0.6f, 0.12f, 0.8f);
        if (Wood.Contains(tag)) return (GROVE, 0.09f, 0.55f, 0.6f);
        return null;
    }

    /// <summary>Dissolve a reagent unit into six channels. 15 mass at tier 1 (19/23/27 at t2/t3/t4).</summary>
    public static double[] Brew(IReadOnlyList<string> tags, int tier, int qty)
    {
        var e = new double[N]; var rank = 0; double wsum = 0;
        foreach (var t in tags)
        {
            var r = Resolve(t); if (r == null) continue;
            var w = rank switch { 0 => 4.0, 1 => 3.0, 2 => 2.0, _ => 1.0 }; rank++;
            e[r.Value.Item1] += w; wsum += w;
        }
        if (wsum <= 0) { e[TERRA] = 1; wsum = 1; }
        var mass = (11.0 + 4.0 * Math.Max(1, tier)) * Math.Max(1, qty);
        for (var i = 0; i < N; i++) e[i] = e[i] / wsum * mass;
        return e;
    }

    /// <summary>The composition's own volatility (0..100): a mass-weighted blend of per-channel volatility, plus a
    /// heat term. This is the equilibrium V a mixture EASES toward — and the fixed V of an inert raw ingredient
    /// (call with heat 0). Fire/shadow are inherently volatile; earth/water are calm; heat adds volatility.</summary>
    public static double ComposeVolatility(double[] e, double heat)
    {
        double m = 0; for (var i = 0; i < N; i++) m += Math.Max(0, e[i]);
        if (m < 1e-4) return 0;
        var vc = (e[HEAT] * 0.85 + e[AQUA] * 0.20 + e[TERRA] * 0.12 + e[GROVE] * 0.45 + e[UMBRA] * 0.80 + e[AIR] * 0.40) / m;
        return Math.Clamp(vc * 62 + heat / HOT * 34, 0, 100);
    }

    private static void Shift(double[] A, int from, int to, double frac)
    { frac = Math.Clamp(frac, 0, 0.5); var c = A[from] * frac; A[from] -= c; A[to] += c; }

    /// <summary>
    /// Advance ONE MIXTURE one tick (raw ingredients are inert and never call this). A fresh combine reacts for
    /// <paramref name="reactTime"/> seconds, then the mixture SETTLES and holds. Each tick we read which NAMED states
    /// the primaries are in (with a magnitude), apply their transmutations + P/V biases scaled by magnitude · vigor ·
    /// remaining-window, and EASE V and P toward composition-derived equilibria (stable: no runaway, no collapse, no
    /// waiting-out). <paramref name="outState"/> is filled with each state's magnitude for the renderer + log.
    /// </summary>
    public static void Evolve(double[] A, double pAnchor, ModProfile mp, double age, double reactTime,
                              ref double heat, ref double turb, ref double pot, ref double vol, double dt, double[] outState, double vTarget)
    {
        Array.Clear(outState, 0, outState.Length);
        if (A == null || A.Length < N || outState.Length < StateCount || dt <= 0) return;
        if (dt > 0.1) dt = 0.1;
        double mass = 0; for (var i = 0; i < N; i++) { if (A[i] < 0) A[i] = 0; mass += A[i]; }
        if (mass < 1e-4) return;

        // past the reaction window the mixture is SETTLED — hold P/V steady, no states (reads as "static")
        if (age >= reactTime) { turb = Math.Max(0, turb - 25 * dt); return; }
        var w = 1 - age / reactTime;          // remaining reaction intensity (bounds every effect → converges)
        var rx = Math.Clamp(mp?.Rx ?? 1, 0.2, 3);  // reaction vigor from tags/tier

        // effective (reactivity-weighted) composition: a modifier's channel exception emphasises/suppresses how
        // much a primary "counts" for reactions (e.g. lightning makes FIRE count more) without changing the real mass.
        var eff = new double[N]; double em = 0;
        for (var i = 0; i < N; i++) { eff[i] = A[i] * (mp?.Ch[i] ?? 1); em += eff[i]; }
        if (em < 1e-4) em = 1;
        double fire = eff[HEAT] / em, water = eff[AQUA] / em, earth = eff[TERRA] / em, life = eff[GROVE] / em, umbra = eff[UMBRA] / em, air = eff[AIR] / em;
        double Pair(double a, double b) => Math.Clamp(4 * a * b, 0, 1);   // peaks when both primaries are balanced

        // --- read the NAMED states (two pairs split by heat) ---
        var fw = Pair(fire, water); if (fw > 0) outState[(int)(heat >= 45 ? State.Steam : State.Quench)] = fw;
        var fe = Pair(fire, earth); if (fe > 0) outState[(int)(heat >= HOT ? State.Molten : State.Temper)] = fe;
        if (heat > WARM) outState[(int)State.Scorch] = Pair(fire, life);
        outState[(int)State.Blaze] = Pair(fire, air);
        outState[(int)State.Brimstone] = Pair(fire, umbra);
        outState[(int)State.Silt] = Pair(water, earth);
        if (heat <= WARM) outState[(int)State.Bloom] = Pair(water, life);
        outState[(int)State.Mist] = Pair(water, air);
        outState[(int)State.Brine] = Pair(water, umbra);
        outState[(int)State.Root] = Pair(earth, life);
        outState[(int)State.Crystallize] = Pair(earth, umbra);
        outState[(int)State.Dust] = Pair(earth, air);
        outState[(int)State.Decay] = Pair(life, umbra);
        outState[(int)State.Spore] = Pair(life, air);
        outState[(int)State.Smoke] = Pair(umbra, air);
        for (var i = 1; i < StateCount; i++) if (outState[i] < 0.05) outState[i] = 0;

        // --- modifier EXCEPTIONS on states: per-state amplify/damp, then the strongest-state amplifier (higher-V wins) ---
        if (mp != null)
        {
            for (var i = 1; i < StateCount; i++) if (outState[i] > 0) outState[i] = Math.Clamp(outState[i] * mp.St[i], 0, 1);
            if (mp.AmpStrongest != 1)
            {
                var bi = 0; var bv = 0.0;
                for (var i = 1; i < StateCount; i++) { var m = outState[i]; if (m <= 0) continue; var key = m * (1 + StateVol[i] / 40.0); if (key > bv) { bv = key; bi = i; } }
                if (bi > 0) outState[bi] = Math.Clamp(outState[bi] * mp.AmpStrongest, 0, 1);
            }
        }

        double M(State s) => outState[(int)s];

        // --- heat: fire builds (damped by water+earth), fanned by BLAZE ---
        var heatTarget = Math.Clamp(fire * 150.0 / (1 + water * 3.5 + earth * 1.6) * (1 + M(State.Blaze) * 0.6), 0, HEAT_MAX);
        heat += (heatTarget - heat) * 1.6 * rx * dt;

        // --- transmutations (channel moves), each scaled by magnitude · vigor · remaining window ---
        Shift(A, AQUA, AIR, M(State.Steam) * 0.6 * rx * w * dt);        heat -= M(State.Steam) * 22 * dt;      // steam boils off + cools
        Shift(A, HEAT, AIR, M(State.Quench) * 0.5 * rx * w * dt);       heat -= M(State.Quench) * 26 * dt;     // water subdues fire (2× loss)
        Shift(A, GROVE, HEAT, M(State.Scorch) * 0.5 * rx * w * dt);                                            // life burns to feed fire
        Shift(A, GROVE, UMBRA, M(State.Decay) * 0.4 * rx * w * dt);                                            // life rots to shadow
        Shift(A, UMBRA, AIR, M(State.Smoke) * 0.4 * rx * w * dt);                                              // shadow smokes off
        Shift(A, AIR, HEAT, M(State.Blaze) * 0.3 * rx * w * dt);                                               // air feeds the blaze
        heat = Math.Clamp(heat, 0, HEAT_MAX);
        var heatTick = 1 + HEAT_TICK_GAIN * (heat / HEAT_MAX);   // (B-D3) settled-heat tick multiplier: 1.0 .. 1.5

        // --- EQUILIBRIA — V and P ease toward composition targets biased by states + modifier profile ---
        // CANON (base ± / ×mult, master plan §2.3-2): per-ingredient/state BASE ± adds on VOLATILITY (the SCORED axis,
        // kept additive so the bell stays legible); the ×MULTIPLIER compounds on POTENCY (the un-scored axis). Every
        // other minigame mirrors this split — add on the scored axis, multiply the un-scored one.
        double vEq = ComposeVolatility(A, heat) + (mp?.Vol ?? 0), pMult = 1;
        for (var i = 1; i < StateCount; i++) { var m = outState[i]; if (m <= 0) continue; vEq += StateVol[i] * m; pMult += StatePot[i] * m; }
        if (mp != null)
            for (var i = 0; i < N; i++) if (eff[i] / em > 0.08) { pMult += mp.PriPot[i]; vEq += mp.PriVol[i]; }   // primary-present exceptions
        // (B-D1) accelerate the SAME ease-toward-vEq motion by how close vol sits to the SCORED target (vTarget):
        // direction stays vEq-vol, only the RATE scales. heat (B-D3) scales the rate too — never writes vol (I2/M5).
        var edge = Math.Exp(-0.5 * Math.Pow((vol - vTarget) / EDGE_SIGMA, 2));   // 1 at the target, →0 far away
        var easeV = EASE_V_BASE * (1 + EDGE_GAIN * edge);                        // 2.4 (far) .. 6.72 (dead on target)
        vol += (Math.Clamp(vEq, 0, 100) - vol) * easeV * heatTick * dt;
        var pEq = pAnchor * Math.Clamp(pMult, 0.3, 2.4);
        pot += (pEq - pot) * 2.0 * heatTick * dt;

        // turbulence: fed by fierce states, calmed by Crystallize/Silt
        var stir = M(State.Blaze) + M(State.Brimstone) + M(State.Steam) + M(State.Decay);
        turb = Math.Clamp(turb + (stir * 30 + Math.Max(0, heat - 60) * 0.3) * dt - (12 + (M(State.Crystallize) + M(State.Silt)) * 20) * dt, 0, 100);
        vol = Math.Clamp(vol, 0, 100); pot = Math.Clamp(pot, 0, 150);
    }

    // ---- potency / volatility scoring ------------------------------------------------
    private static double TagVolatility(string tag) => tag switch
    {
        "chaos" or "volcanic" or "lightning" => 0.95, "void" or "molten" => 0.9, "fire" or "flame" or "blood" or "acid" => 0.8,
        // (C.2-g) Function/Output ROLE tags set the TARGET's character: aggressive outputs want a volatile target, defensive a calm one
        "weapon" or "combat" or "explosive" or "strength" => 0.7,
        "armor" or "defense" or "protection" or "resistance" => 0.18, "healing" or "regeneration" or "harmony" => 0.25,
        "poison" or "venom" or "toxic" or "ember" or "forge" => 0.7, "shadow" or "dark" or "radiant" or "arcane" or "magical" => 0.62,
        "spectral" or "essence" or "air" or "wind" or "monster" => 0.5, "vapor" or "gas" or "living" or "gel" => 0.42,
        "herb" or "plant" or "wood" or "crystal" or "gem" => 0.3, "water" or "aqua" or "liquid" or "metal" or "leather" or "bone" => 0.2,
        "earth" or "stone" or "sand" or "ice" or "frost" or "mineral" => 0.13, _ => 0.35,
    };

    /// <summary>The volatility a recipe wants the finished brew to sit at (0..100) — mostly from tags, nudged by tier.</summary>
    public static double TargetVolatility(IReadOnlyList<string> tags, int tier)
    {
        double s = 0; var n = 0; foreach (var t in tags) { s += TagVolatility(t); n++; }
        var basis = n > 0 ? s / n : 0.4;
        return Math.Clamp(basis * 92 + tier * 2, 5, 98);
    }

    /// <summary>A recipe's resistance (0..0.8) to raw potency — scales with tier to balance potent high-tier reagents.</summary>
    public static double PotencyResistance(IReadOnlyList<string> tags, int tier)
    {
        var r = Math.Clamp((tier - 1) * 0.22, 0, 0.7);
        foreach (var t in tags) if (t is "pure" or "refined" or "precious" or "quality") r = Math.Max(0, r - 0.08);
        return Math.Clamp(r, 0, 0.8);
    }

    /// <summary>A reagent unit's inherent TIER potency (t1 26 .. t4 68). Tag potency is applied separately via
    /// <see cref="BuildProfile"/> (ModProfile.Pot) so it isn't double-counted.</summary>
    public static double BasePotency(int tier) => 12 + Math.Max(1, tier) * 14;

    /// <summary>Quality = closeness-to-target-volatility (BASE) × resisted-potency (MULTIPLIER). 0..1.</summary>
    public static double Quality(double vol, double pot, double vTarget, double resistance)
    {
        var z = (vol - vTarget) / 18.0;
        var baseScore = Math.Exp(-0.5 * z * z);                       // volatility distance
        var pEff = pot / (1 + resistance * 2.0);                       // resistance dampens potency
        var potMult = Math.Clamp(0.55 + 0.6 * (pEff / 60.0), 0.55, 1.4);
        return Math.Clamp(baseScore * potMult, 0, 1);
    }

    // ---- reads ------------------------------------------------------------------------
    public static int Dominant(double[] e) { var d = 0; for (var i = 1; i < N; i++) if (e[i] > e[d]) d = i; return d; }

    public static Color BlendColor(double[] e)
    {
        double r = 0, g = 0, b = 0, s = 0;
        for (var i = 0; i < N; i++) { if (e[i] <= 0) continue; var c = FamCol[i]; r += c.R * e[i]; g += c.G * e[i]; b += c.B * e[i]; s += e[i]; }
        return s <= 0 ? new Color(0.5f, 0.5f, 0.5f) : new Color((float)(r / s), (float)(g / s), (float)(b / s));
    }

    /// <summary>Display colour from the reagent's actual TAGS (distinct per tag), leaned toward the channel blend.</summary>
    public static Color DisplayColor(IReadOnlyList<string> tags, double[] e)
    {
        float r = 0, g = 0, b = 0; var w = 0f; var rank = 0;
        foreach (var t in tags)
        {
            var rr = Resolve(t); if (rr == null) continue;
            var ww = rank switch { 0 => 4f, 1 => 3f, 2 => 2f, _ => 1f }; rank++;
            var c = Color.FromHsv(rr.Value.Item2, rr.Value.Item3, rr.Value.Item4);
            r += c.R * ww; g += c.G * ww; b += c.B * ww; w += ww;
        }
        var tagCol = w <= 0 ? BlendColor(e) : new Color(r / w, g / w, b / w);
        var mixed = tagCol.Lerp(BlendColor(e), 0.25f);
        // DE-MUDDY (shared helper) — bias toward the dominant channel + floor saturation/value so complex,
        // heavily-merged brews stay vivid and distinct instead of averaging out to grey.
        return CraftColor.DeMuddy(mixed, FamCol[Dominant(e)]);
    }

    /// <summary>Cosine similarity of an essence's character to a target (0..1).</summary>
    public static double DirMatch(double[] a, double[] t)
    {
        double dot = 0, na = 0, nt = 0;
        for (var i = 0; i < N; i++) { dot += a[i] * t[i]; na += a[i] * a[i]; nt += t[i] * t[i]; }
        return na <= 1e-9 || nt <= 1e-9 ? 0 : Math.Clamp(dot / Math.Sqrt(na * nt), 0, 1);
    }

    public static double Grade(IEnumerable<string> tags)
    { double g = 0.1; foreach (var t in tags) if (QualityGrade.TryGetValue(t, out var q)) g = Math.Max(g, q); return g; }

    /// <summary>Item rarity from tier + quality tags → name + colour.</summary>
    public static (string Name, Color Col) Rarity(int tier, double grade)
    {
        var rank = Math.Max(Math.Clamp(tier - 1, 0, 4), grade >= 0.9 ? 4 : grade >= 0.72 ? 3 : grade >= 0.55 ? 2 : grade >= 0.38 ? 1 : 0);
        return RarityByRank(rank);
    }

    /// <summary>Craft-outcome rarity from performance 0..1.</summary>
    public static (string Name, Color Col) RarityFromPerf(double perf)
        => RarityByRank(perf >= 0.9 ? 4 : perf >= 0.72 ? 3 : perf >= 0.5 ? 2 : perf >= 0.28 ? 1 : 0);

    private static readonly string[] RarityNames = { "Common", "Uncommon", "Rare", "Epic", "Legendary" };
    private static readonly string[] RarityKeys = { "common", "uncommon", "rare", "epic", "legendary" };
    public static (string, Color) RarityByRank(int rank)
    {
        rank = Math.Clamp(rank, 0, 4);
        var col = UiTheme.Rarity.TryGetValue(RarityKeys[rank], out var c) ? c : Colors.White;
        return (RarityNames[rank], col);
    }
}
