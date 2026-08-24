using System.Text.Json;
using Game1.Core.Content;
using Game1.Core.Data;
using Xunit;

namespace Game1.Core.Tests;

public class VisualConfigTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/visual_config.json");

    private static VisualConfig Load()
    {
        var vc = new VisualConfig();
        vc.Load(ContentPaths.TryGetContentRoot()!);
        return vc;
    }

    private static void AssertColor(JsonElement expected, (int R, int G, int B) actual, string ctx)
    {
        Assert.True(expected[0].GetInt32() == actual.R
                    && expected[1].GetInt32() == actual.G
                    && expected[2].GetInt32() == actual.B,
            $"{ctx}: expected {expected.GetRawText()}, got ({actual.R},{actual.G},{actual.B})");
    }

    [Fact]
    public void AllAccessors_MatchPythonExecution()
    {
        var vc = Load();
        var v = G.GetProperty("values");

        var numeric = new Dictionary<string, double>
        {
            ["damage_number_lifetime_ms"] = vc.DamageNumberLifetimeMs,
            ["damage_number_velocity_y"] = vc.DamageNumberVelocityY,
            ["damage_number_horizontal_spread"] = vc.DamageNumberHorizontalSpread,
            ["damage_number_gravity"] = vc.DamageNumberGravity,
            ["damage_number_shrink_rate"] = vc.DamageNumberShrinkRate,
            ["damage_number_crit_scale"] = vc.DamageNumberCritScale,
            ["damage_number_stack_offset"] = vc.DamageNumberStackOffset,
            ["player_radius_tiles"] = vc.PlayerRadiusTiles,
            ["facing_indicator_length"] = vc.FacingIndicatorLength,
            ["shadow_alpha"] = vc.ShadowAlpha,
            ["shadow_scale"] = vc.ShadowScale,
            ["idle_bob_amplitude"] = vc.IdleBobAmplitude,
            ["idle_bob_period_ms"] = vc.IdleBobPeriodMs,
            ["death_fade_duration_ms"] = vc.DeathFadeDurationMs,
            ["death_shrink_factor"] = vc.DeathShrinkFactor,
            ["corpse_linger_ms"] = vc.CorpseLingerMs,
            ["spawn_fade_in_ms"] = vc.SpawnFadeInMs,
            ["telegraph_pulse_frequency"] = vc.TelegraphPulseFrequency,
            ["max_particles"] = vc.MaxParticles,
            ["death_burst_count"] = vc.DeathBurstCount,
            ["shake_decay_rate"] = vc.ShakeDecayRate,
            ["shake_max_offset"] = vc.ShakeMaxOffset,
            ["debug_hitbox_alpha"] = vc.DebugHitboxAlpha,
            ["debug_hurtbox_alpha"] = vc.DebugHurtboxAlpha,
        };
        foreach (var kv in numeric)
            GoldenFixture.AssertClose(v.GetProperty(kv.Key).GetDouble(), kv.Value, kv.Key);

        var bools = new Dictionary<string, bool>
        {
            ["shadow_enabled"] = vc.ShadowEnabled,
            ["debug_show_facing"] = vc.DebugShowFacing,
            ["debug_show_attack_phase"] = vc.DebugShowAttackPhase,
        };
        foreach (var kv in bools)
            Assert.Equal(v.GetProperty(kv.Key).GetBoolean(), kv.Value);

        var colors = new Dictionary<string, (int, int, int)>
        {
            ["damage_number_crit_color"] = vc.DamageNumberCritColor,
            ["player_color"] = vc.PlayerColor,
            ["player_outline_color"] = vc.PlayerOutlineColor,
            ["facing_indicator_color"] = vc.FacingIndicatorColor,
            ["boss_glow_color"] = vc.BossGlowColor,
            ["telegraph_player_color"] = vc.TelegraphPlayerColor,
            ["telegraph_enemy_color"] = vc.TelegraphEnemyColor,
            ["debug_hitbox_color"] = vc.DebugHitboxColor,
            ["debug_hurtbox_color"] = vc.DebugHurtboxColor,
            ["debug_iframe_color"] = vc.DebugIframeColor,
        };
        foreach (var kv in colors)
            AssertColor(v.GetProperty(kv.Key), kv.Value, kv.Key);

        var sparks = v.GetProperty("hit_spark_count");
        Assert.Equal(sparks[0].GetInt32(), vc.HitSparkCount.Min);
        Assert.Equal(sparks[1].GetInt32(), vc.HitSparkCount.Max);
    }

    [Fact]
    public void ParameterizedAccessors_MatchPythonExecution()
    {
        var vc = Load();

        foreach (var e in G.GetProperty("damage_type_colors").EnumerateObject())
            AssertColor(e.Value, vc.DamageTypeColor(e.Name), $"damage_type[{e.Name}]");

        foreach (var e in G.GetProperty("damage_special_text").EnumerateObject())
        {
            var (text, color) = vc.DamageSpecialText(e.Name);
            Assert.Equal(e.Value[0].GetString(), text);
            AssertColor(e.Value[1], color, $"special_color[{e.Name}]");
        }

        foreach (var e in G.GetProperty("enemy_tier_scale").EnumerateObject())
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                vc.EnemyTierScale(int.Parse(e.Name)), $"tier_scale[{e.Name}]");
        foreach (var e in G.GetProperty("enemy_tier_glow").EnumerateObject())
            Assert.Equal(e.Value.GetBoolean(), vc.EnemyTierHasGlow(int.Parse(e.Name)));
        foreach (var e in G.GetProperty("enemy_tier_glow_intensity").EnumerateObject())
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                vc.EnemyTierGlowIntensity(int.Parse(e.Name)), $"glow_intensity[{e.Name}]");

        foreach (var e in G.GetProperty("enemy_state_colors").EnumerateObject())
            AssertColor(e.Value, vc.EnemyStateColor(e.Name), $"state_color[{e.Name}]");
    }
}
