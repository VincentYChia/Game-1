using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Progression;
using Xunit;

namespace Game1.Core.Tests;

public class StatusEffectTests
{
    private static readonly JsonElement S = GoldenFixture.Load("db_parity/status_effects.json")
        .GetProperty("scenarios");

    /// <summary>Mirrors the Python SimpleNamespace stub: has speed +
    /// attack_speed + current_health; no take_damage/heal/movement_speed.</summary>
    private sealed class Stub : IStatusTarget
    {
        public double ResistanceMultiplier { get; init; } = 1.0;
        public bool HasSpeed => true;
        public double Speed { get; set; } = 5.0;
        public bool HasMovementSpeed => false;
        public double MovementSpeed { get; set; }
        public bool HasAttackSpeed => true;
        public double AttackSpeed { get; set; } = 1.0;
        public bool HasTakeDamage => false;
        public void TakeDamage(double a, string t, IReadOnlyList<string> tags) =>
            throw new InvalidOperationException();
        public double CurrentHealth { get; set; } = 200.0;
        public double MaxHealth { get; init; } = 200.0;
        public bool HasHeal => false;
        public void Heal(double amount) => throw new InvalidOperationException();
        public double ShieldAmount { get; set; }
        public double ShieldHealth => 0.0;  // add_status_manager default
        public bool IsFrozen { get; set; }
        public bool IsStunned { get; set; }
        public bool IsRooted { get; set; }
        public bool IsPhased { get; set; }
        public bool IgnoreCollisions { get; set; }
        public bool IsInvisible { get; set; }
        public double EmpowerDamageMultiplier { get; set; } = 1.0;
        public double FortifyDamageReduction { get; set; }
        public double DamageMultiplier { get; set; } = 1.0;
        public double DamageTakenMultiplier { get; set; } = 1.0;
        public ISet<string> VisualEffects { get; } = new HashSet<string>();
        public double GetEffectResistance(string statusTag) => ResistanceMultiplier;
    }

    private static JsonObject P(params (string, double)[] entries)
    {
        var o = new JsonObject();
        foreach (var (k, v) in entries) o[k] = v;
        return o;
    }

    private static void AssertEffects(JsonElement expected, StatusEffectManager m, string ctx)
    {
        var arr = new JsonArray();
        foreach (var e in m.ActiveEffects)
            arr.Add(new JsonObject
            {
                ["status_id"] = e.StatusId, ["stacks"] = e.Stacks,
                ["duration"] = e.Duration,
                ["duration_remaining"] = e.DurationRemaining,
            });
        var diffs = JsonTreeComparer.Diff(expected, arr);
        Assert.True(diffs.Count == 0, $"{ctx}: " + string.Join("; ", diffs.Take(10)));
    }

    [Fact]
    public void ClassAffinity_MatchesPython()
    {
        var classes = BootedDatabases.All.Value.Classes;
        foreach (var e in S.GetProperty("class_affinity").EnumerateObject())
        {
            var cdef = classes.Classes[e.Name];
            var ownTags = ((System.Text.Json.Nodes.JsonArray)cdef.Tags)
                .Select(t => t!.GetValue<string>()).ToList();
            GoldenFixture.AssertClose(e.Value.GetProperty("own_tags").GetDouble(),
                cdef.GetSkillAffinityBonus(ownTags), $"{e.Name}.own_tags");
            GoldenFixture.AssertClose(e.Value.GetProperty("one_match").GetDouble(),
                cdef.GetSkillAffinityBonus(ownTags.Count > 0
                    ? new List<string> { ownTags[0].ToUpperInvariant() }
                    : new List<string>()), $"{e.Name}.one_match");
            GoldenFixture.AssertClose(e.Value.GetProperty("no_match").GetDouble(),
                cdef.GetSkillAffinityBonus(new List<string> { "zzz_not_a_tag" }),
                $"{e.Name}.no_match");
            GoldenFixture.AssertClose(e.Value.GetProperty("empty").GetDouble(),
                cdef.GetSkillAffinityBonus(new List<string>()), $"{e.Name}.empty");
        }
    }

    [Fact]
    public void DoT_Stacking_Cadence_MatchPython()
    {
        var s = S.GetProperty("burn_dot");
        var t = new Stub();
        var m = new StatusEffectManager(t);
        m.ApplyStatus("burn", P(("burn_duration", 4.0), ("burn_damage_per_second", 10.0)));
        var hp = s.GetProperty("hp_ticks");
        for (var i = 0; i < 3; i++)
        {
            m.Update(1.0);
            GoldenFixture.AssertClose(hp[i].GetDouble(), t.CurrentHealth, $"burn tick {i}");
        }
        m.Update(1.5);
        GoldenFixture.AssertClose(s.GetProperty("hp_final").GetDouble(), t.CurrentHealth, "burn final");
        AssertEffects(s.GetProperty("effects_after_expiry"), m, "burn expiry");

        s = S.GetProperty("burn_stacking");
        t = new Stub();
        m = new StatusEffectManager(t);
        for (var i = 0; i < 5; i++)
            m.ApplyStatus("burn", P(("burn_duration", 4.0), ("burn_damage_per_second", 10.0)));
        m.Update(1.0);
        AssertEffects(s.GetProperty("effects"), m, "burn stacks");
        GoldenFixture.AssertClose(s.GetProperty("hp").GetDouble(), t.CurrentHealth, "burn stack hp");

        s = S.GetProperty("poison_superlinear");
        t = new Stub();
        m = new StatusEffectManager(t);
        for (var i = 0; i < 3; i++)
            m.ApplyStatus("poison", P(("poison_duration", 6.0)));
        m.Update(1.0);
        AssertEffects(s.GetProperty("effects"), m, "poison stacks");
        GoldenFixture.AssertClose(s.GetProperty("hp").GetDouble(), t.CurrentHealth, "poison hp");

        s = S.GetProperty("shock_cadence");
        t = new Stub();
        m = new StatusEffectManager(t);
        m.ApplyStatus("shock", P(("shock_duration", 6.0), ("shock_damage_per_tick", 6.0),
            ("shock_tick_rate", 2.0)));
        var steps = new[] { 1.0, 1.0, 0.5, 1.5, 1.0 };
        var expectedHp = s.GetProperty("hp_after_steps");
        for (var i = 0; i < steps.Length; i++)
        {
            m.Update(steps[i]);
            GoldenFixture.AssertClose(expectedHp[i].GetDouble(), t.CurrentHealth, $"shock step {i}");
        }
    }

    [Fact]
    public void CC_Aliases_Exclusions_MatchPython()
    {
        var s = S.GetProperty("freeze_restore");
        var t = new Stub();
        var m = new StatusEffectManager(t);
        m.ApplyStatus("freeze", P(("freeze_duration", 2.0)));
        GoldenFixture.AssertClose(s.GetProperty("speed_during").GetDouble(), t.Speed, "frozen speed");
        Assert.Equal(s.GetProperty("flag_during").GetBoolean(), t.IsFrozen);
        m.Update(2.5);
        GoldenFixture.AssertClose(s.GetProperty("speed_after").GetDouble(), t.Speed, "thawed speed");
        Assert.Equal(s.GetProperty("flag_after").GetBoolean(), t.IsFrozen);

        s = S.GetProperty("slow_then_chill_alias");
        t = new Stub();
        m = new StatusEffectManager(t);
        m.ApplyStatus("slow", P(("slow_duration", 5.0), ("slow_percent", 0.4)));
        GoldenFixture.AssertClose(s.GetProperty("speed_after_slow").GetDouble(), t.Speed, "slowed");
        m.ApplyStatus("chill", P(("chill_duration", 5.0), ("slow_percent", 0.4)));
        GoldenFixture.AssertClose(s.GetProperty("speed_after_chill").GetDouble(), t.Speed, "chilled");
        AssertEffects(s.GetProperty("effects"), m, "alias duplicate");

        s = S.GetProperty("mutual_exclusion");
        t = new Stub();
        m = new StatusEffectManager(t);
        m.ApplyStatus("burn", P(("burn_duration", 5.0)));
        m.ApplyStatus("freeze", P(("freeze_duration", 2.0)));
        Assert.Equal(
            s.GetProperty("after_freeze").EnumerateArray().Select(x => x.GetString()),
            m.ActiveEffects.Select(e => e.StatusId));
        m.ApplyStatus("burn", P(("burn_duration", 5.0)));
        Assert.Equal(
            s.GetProperty("after_reburn").EnumerateArray().Select(x => x.GetString()),
            m.ActiveEffects.Select(e => e.StatusId));
        GoldenFixture.AssertClose(s.GetProperty("speed_after_reburn").GetDouble(), t.Speed,
            "speed after exclusion");

        s = S.GetProperty("stun_refresh");
        t = new Stub();
        m = new StatusEffectManager(t);
        m.ApplyStatus("stun", P(("stun_duration", 2.0)));
        m.Update(1.5);
        m.ApplyStatus("stun", P(("stun_duration", 2.0)));
        AssertEffects(s.GetProperty("effects"), m, "stun refresh");
        Assert.Equal(s.GetProperty("cc").GetBoolean(), m.IsCrowdControlled());
        Assert.Equal(s.GetProperty("immobilized").GetBoolean(), m.IsImmobilized());
        Assert.Equal(s.GetProperty("silenced").GetBoolean(), m.IsSilenced());
    }

    [Fact]
    public void Buffs_Debuffs_Shield_Resistance_Factory_MatchPython()
    {
        var s = S.GetProperty("haste");
        var t = new Stub();
        var m = new StatusEffectManager(t);
        m.ApplyStatus("haste", P(("haste_duration", 3.0), ("haste_speed_bonus", 0.3)));
        GoldenFixture.AssertClose(s.GetProperty("speed").GetDouble(), t.Speed, "haste speed");
        GoldenFixture.AssertClose(s.GetProperty("attack_speed").GetDouble(), t.AttackSpeed, "haste as");
        m.RemoveStatus("haste");
        GoldenFixture.AssertClose(s.GetProperty("speed_after").GetDouble(), t.Speed, "haste off");
        GoldenFixture.AssertClose(s.GetProperty("attack_speed_after").GetDouble(),
            t.AttackSpeed, "haste as off");

        s = S.GetProperty("stat_modifiers");
        t = new Stub();
        m = new StatusEffectManager(t);
        m.ApplyStatus("empower", P(("empower_duration", 3.0), ("empower_damage_bonus", 0.25)));
        m.ApplyStatus("fortify", P(("fortify_duration", 3.0), ("fortify_defense_bonus", 0.2)));
        m.ApplyStatus("weaken", P(("weaken_duration", 3.0), ("weaken_percent", 0.25)));
        m.ApplyStatus("vulnerable", P(("vulnerable_duration", 3.0), ("vulnerable_percent", 0.25)));
        GoldenFixture.AssertClose(s.GetProperty("empower_mult").GetDouble(),
            t.EmpowerDamageMultiplier, "empower");
        GoldenFixture.AssertClose(s.GetProperty("fortify_reduction").GetDouble(),
            t.FortifyDamageReduction, "fortify");
        GoldenFixture.AssertClose(s.GetProperty("damage_mult").GetDouble(),
            t.DamageMultiplier, "weaken");
        GoldenFixture.AssertClose(s.GetProperty("damage_taken_mult").GetDouble(),
            t.DamageTakenMultiplier, "vulnerable");
        m.ClearDebuffs();
        var after = s.GetProperty("after_cleanse");
        GoldenFixture.AssertClose(after.GetProperty("damage_mult").GetDouble(),
            t.DamageMultiplier, "cleansed dmg");
        GoldenFixture.AssertClose(after.GetProperty("damage_taken_mult").GetDouble(),
            t.DamageTakenMultiplier, "cleansed taken");
        Assert.Equal(after.GetProperty("remaining").EnumerateArray().Select(x => x.GetString()),
            m.ActiveEffects.Select(e => e.StatusId));

        s = S.GetProperty("shield_and_regen");
        t = new Stub { CurrentHealth = 100.0 };
        m = new StatusEffectManager(t);
        m.ApplyStatus("shield", P(("shield_duration", 5.0), ("shield_amount", 40.0)));
        m.ApplyStatus("regeneration", P(("regen_duration", 5.0), ("regen_heal_per_second", 30.0)));
        m.Update(1.0);
        GoldenFixture.AssertClose(s.GetProperty("shield_amount").GetDouble(),
            t.ShieldAmount, "shield amount");
        GoldenFixture.AssertClose(s.GetProperty("hp_after_regen").GetDouble(),
            t.CurrentHealth, "regen hp");
        m.Update(4.5);
        GoldenFixture.AssertClose(s.GetProperty("hp_capped").GetDouble(), t.CurrentHealth, "capped");
        GoldenFixture.AssertClose(s.GetProperty("shield_after_expiry").GetDouble(),
            t.ShieldAmount, "shield expiry");

        s = S.GetProperty("resistance_halves_duration");
        t = new Stub { ResistanceMultiplier = 0.5 };
        m = new StatusEffectManager(t);
        m.ApplyStatus("burn", P(("burn_duration", 8.0)));
        AssertEffects(s.GetProperty("effects"), m, "resistance");

        s = S.GetProperty("factory_durations");
        t = new Stub();
        m = new StatusEffectManager(t);
        var okUnknown = m.ApplyStatus("nonsense_status", P(("duration", 5.0)));
        Assert.Equal(s.GetProperty("unknown_ok").GetBoolean(), okUnknown);
        m.ApplyStatus("bleed", P(("duration", 7.0)));
        m.ApplyStatus("root", new JsonObject());
        AssertEffects(s.GetProperty("effects"), m, "factory durations");
    }
}
