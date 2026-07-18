using System.Text.Json;
using Game1.Core.Stats;
using Xunit;

namespace Game1.Core.Tests;

public class StatScalingTests
{
    private static readonly JsonElement G = GoldenFixture.Load("stat_scaling.json");

    [Fact]
    public void ResolvedScaling_MatchesPython()
    {
        // The golden was generated with stats-calculations.JSON present; the
        // C# loader reads the same file through ContentPaths.
        foreach (var prop in G.GetProperty("resolved_scaling").EnumerateObject())
        {
            Assert.True(StatScaling.Default.Scaling.ContainsKey(prop.Name),
                        $"missing stat '{prop.Name}'");
            GoldenFixture.AssertClose(prop.Value.GetDouble(),
                                      StatScaling.Default.Scaling[prop.Name],
                                      $"scaling[{prop.Name}]");
        }
    }

    [Fact]
    public void ResolvedFlatBonuses_MatchPython()
    {
        foreach (var stat in G.GetProperty("resolved_flat_bonuses").EnumerateObject())
        {
            Assert.True(StatScaling.Default.FlatBonuses.ContainsKey(stat.Name),
                        $"missing flat stat '{stat.Name}'");
            foreach (var bonus in stat.Value.EnumerateObject())
                GoldenFixture.AssertClose(
                    bonus.Value.GetDouble(),
                    StatScaling.Default.FlatBonuses[stat.Name][bonus.Name],
                    $"flat[{stat.Name}][{bonus.Name}]");
        }
    }

    [Fact]
    public void PercentBonus_MatchesPython()
    {
        foreach (var stat in G.GetProperty("percent_bonus").EnumerateObject())
            foreach (var entry in stat.Value.EnumerateObject())
                GoldenFixture.AssertClose(
                    entry.Value.GetDouble(),
                    StatScaling.Default.GetBonus(stat.Name, int.Parse(entry.Name)),
                    $"percent_bonus[{stat.Name}][{entry.Name}]");
    }

    [Fact]
    public void FlatBonus_MatchesPython()
    {
        foreach (var stat in G.GetProperty("flat_bonus").EnumerateObject())
            foreach (var bonusType in stat.Value.EnumerateObject())
                foreach (var entry in bonusType.Value.EnumerateObject())
                    GoldenFixture.AssertClose(
                        entry.Value.GetDouble(),
                        StatScaling.Default.GetFlatBonus(stat.Name, bonusType.Name,
                                                         int.Parse(entry.Name)),
                        $"flat_bonus[{stat.Name}][{bonusType.Name}][{entry.Name}]");
    }

    [Fact]
    public void Multipliers_MatchPython()
    {
        var m = G.GetProperty("multipliers");
        foreach (var e in m.GetProperty("durability_loss_by_def").EnumerateObject())
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                StatScaling.DurabilityLossMultiplier(int.Parse(e.Name)),
                $"durability_loss[{e.Name}]");
        foreach (var e in m.GetProperty("durability_bonus_by_vit").EnumerateObject())
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                StatScaling.DurabilityBonusMultiplier(int.Parse(e.Name)),
                $"durability_bonus[{e.Name}]");
        foreach (var e in m.GetProperty("carry_capacity_by_str").EnumerateObject())
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                StatScaling.CarryCapacityMultiplier(int.Parse(e.Name)),
                $"carry_capacity[{e.Name}]");
    }

    [Fact]
    public void EffectiveLuck_MatchesPython()
    {
        foreach (var c in G.GetProperty("effective_luck").EnumerateArray())
            GoldenFixture.AssertClose(
                c.GetProperty("effective").GetDouble(),
                StatScaling.EffectiveLuck(
                    c.GetProperty("luck").GetInt32(),
                    c.GetProperty("title").GetDouble(),
                    c.GetProperty("skill").GetDouble(),
                    c.GetProperty("rare_drop").GetDouble()),
                "effective_luck");
    }
}
