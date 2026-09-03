using System;
using System.Collections.Generic;

namespace Game1.Godot;

/// <summary>
/// SHARED MODIFIER-PROFILE mechanism for the crafting minigames (extracted from the Alchemy chemistry).
///
/// The pattern: a discipline has a few PRIMARY/PROCESS channels that drive its core simulation, and every OTHER tag
/// is a pure MODIFIER — a mild uniform BASE (potency ×, volatility ±, reaction-time ×, reaction-vigor ×) plus a small
/// set of narrative EXCEPTIONS that only fire when a condition holds (a channel present, a named state active, the
/// strongest state, …). Modifiers STACK across a mixture with DIMINISHING RETURNS (<see cref="StackFactor"/>) so a
/// deliberate double-dose beats spamming and LAYERING (separate merges) beats BATCHING (all at once).
///
/// This class owns only the MECHANISM: the stack curve, a channel/state-count-parameterised <see cref="ModProfile"/>,
/// and the <see cref="Fold"/> / <see cref="Clamp"/> routines. Each discipline declares its OWN tables (channels and
/// the meaning of "sharp" differ per discipline) and calls these — see <c>MinigameTagEffects.BuildProfile</c> for the
/// Alchemy consumer. Do NOT try to share one giant cross-discipline tag bank.
/// </summary>
public static class MinigameModifierCommon
{
    /// <summary>The modifier profile a reagent/mixture carries. A discipline either subclasses this fixing its channel
    /// and state counts, or constructs one directly with <c>new ModProfile(channels, states)</c>. All multipliers init
    /// to identity (1); <see cref="Vol"/> and the Pri* deltas init to 0.</summary>
    public class ModProfile
    {
        public double Pot = 1, Vol = 0, Time = 1, Rx = 1, AmpStrongest = 1;
        public readonly double[] Ch;      // per-channel reactivity multiplier
        public readonly double[] St;      // per-state magnitude multiplier
        public readonly double[] PriPot;  // +pot added when that channel is present in the mixture
        public readonly double[] PriVol;  // +vol added when that channel is present in the mixture

        public ModProfile(int channels, int states)
        {
            channels = Math.Max(0, channels); states = Math.Max(0, states);
            Ch = new double[channels]; PriPot = new double[channels]; PriVol = new double[channels];
            for (var i = 0; i < channels; i++) Ch[i] = 1;
            St = new double[states];
            for (var i = 0; i < states; i++) St[i] = 1;
        }
    }

    /// <summary>Diminishing-returns stack scale: the 2nd copy adds ~40% more, the 4th barely anything. Rewards a
    /// deliberate double-dose over spamming, and makes LAYERING (separate merges) beat BATCHING (all at once).</summary>
    public static double StackFactor(int n) => n <= 1 ? 1 : (1 - Math.Pow(0.4, n)) / 0.6;

    /// <summary>
    /// Fold all modifier tags (with COUNTS, for stacking) into an existing profile. The base table sets the uniform
    /// scalars; each exception table applies only where its condition indexes (channel / state / primary). Every
    /// effect is scaled by the tag's <see cref="StackFactor"/>. Out-of-range indices are skipped defensively so a
    /// discipline's table can't crash on a mismatched channel/state count. Does NOT clamp — call <see cref="Clamp"/>.
    /// </summary>
    public static void Fold(ModProfile p, IReadOnlyDictionary<string, int>? counts,
        IReadOnlyDictionary<string, (double Pot, double Vol, double Time, double Rx)>? baseTable,
        IReadOnlyDictionary<string, (int Ch, double Mul)[]>? chExc = null,
        IReadOnlyDictionary<string, (int St, double Mul)[]>? stExc = null,
        IReadOnlyDictionary<string, double>? strongExc = null,
        IReadOnlyDictionary<string, (int Pri, double Pot, double Vol)[]>? pvExc = null)
    {
        if (p == null || counts == null) return;
        foreach (var kv in counts)
        {
            var tag = kv.Key; var sf = StackFactor(kv.Value);
            if (baseTable != null && baseTable.TryGetValue(tag, out var b))
            { p.Pot *= 1 + (b.Pot - 1) * sf; p.Vol += b.Vol * sf; p.Time *= 1 + (b.Time - 1) * sf; p.Rx *= 1 + (b.Rx - 1) * sf; }
            if (chExc != null && chExc.TryGetValue(tag, out var ce))
                foreach (var (ch, mul) in ce) if (ch >= 0 && ch < p.Ch.Length) p.Ch[ch] *= 1 + (mul - 1) * sf;
            if (stExc != null && stExc.TryGetValue(tag, out var se))
                foreach (var (st, mul) in se) if (st >= 0 && st < p.St.Length) p.St[st] *= 1 + (mul - 1) * sf;
            if (strongExc != null && strongExc.TryGetValue(tag, out var sm)) p.AmpStrongest *= 1 + (sm - 1) * sf;
            if (pvExc != null && pvExc.TryGetValue(tag, out var pe))
                foreach (var (pri, ap, av) in pe) if (pri >= 0 && pri < p.PriPot.Length) { p.PriPot[pri] += ap * sf; p.PriVol[pri] += av * sf; }
        }
    }

    /// <summary>Clamp every field of a profile to sane ranges (defaults match the Alchemy tuning). Call after
    /// <see cref="Fold"/> and any post-fold adjustments (e.g. a tier vigor bump).</summary>
    public static void Clamp(ModProfile p,
        double potLo = 0.5, double potHi = 2.3, double volLo = -28, double volHi = 28,
        double timeLo = 0.5, double timeHi = 2.2, double rxLo = 0.35, double rxHi = 2.5,
        double chLo = 0.35, double chHi = 2.5, double stLo = 0.35, double stHi = 2.5)
    {
        if (p == null) return;
        p.Pot = Math.Clamp(p.Pot, potLo, potHi); p.Vol = Math.Clamp(p.Vol, volLo, volHi);
        p.Time = Math.Clamp(p.Time, timeLo, timeHi); p.Rx = Math.Clamp(p.Rx, rxLo, rxHi);
        for (var i = 0; i < p.Ch.Length; i++) p.Ch[i] = Math.Clamp(p.Ch[i], chLo, chHi);
        for (var i = 0; i < p.St.Length; i++) p.St[i] = Math.Clamp(p.St[i], stLo, stHi);
    }
}
