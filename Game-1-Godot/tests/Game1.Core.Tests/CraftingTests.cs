using System.Text.Json;
using Game1.Core.Crafting;
using Xunit;

namespace Game1.Core.Tests;

public class DifficultyTests
{
    private static readonly JsonElement G = GoldenFixture.Load("difficulty.json");

    private static List<MaterialInput> Inputs(JsonElement arr) =>
        arr.EnumerateArray()
           .Select(i => new MaterialInput(
               i.GetProperty("materialId").GetString()!,
               i.GetProperty("quantity").GetInt32(),
               i.GetProperty("tier").GetInt32()))
           .ToList();

    [Fact]
    public void CoreCalculations_MatchPython()
    {
        foreach (var set in G.GetProperty("core_calculations").EnumerateObject())
        {
            var inputs = Inputs(set.Value.GetProperty("inputs"));
            GoldenFixture.AssertClose(
                set.Value.GetProperty("material_points").GetDouble(),
                DifficultyCalculator.MaterialPoints(inputs),
                $"material_points[{set.Name}]");
            GoldenFixture.AssertClose(
                set.Value.GetProperty("diversity_multiplier").GetDouble(),
                DifficultyCalculator.DiversityMultiplier(inputs),
                $"diversity[{set.Name}]");
            GoldenFixture.AssertClose(
                set.Value.GetProperty("average_tier").GetDouble(),
                DifficultyCalculator.AverageTier(inputs),
                $"average_tier[{set.Name}]");
        }
    }

    [Fact]
    public void TierBands_MatchPython()
    {
        foreach (var e in G.GetProperty("difficulty_tier_bands").EnumerateObject())
            Assert.Equal(e.Value.GetString(),
                DifficultyCalculator.GetDifficultyTier(
                    double.Parse(e.Name, System.Globalization.CultureInfo.InvariantCulture)));
    }
}

public class RewardTests
{
    private static readonly JsonElement G = GoldenFixture.Load("rewards.json");

    [Fact]
    public void QualityTiers_MatchPython()
    {
        foreach (var e in G.GetProperty("quality_tier_by_performance").EnumerateObject())
            Assert.Equal(e.Value.GetString(),
                RewardCalculator.QualityTier(
                    double.Parse(e.Name, System.Globalization.CultureInfo.InvariantCulture)));
    }

    [Fact]
    public void MaxMultiplier_MatchesPython()
    {
        foreach (var e in G.GetProperty("max_multiplier_by_points").EnumerateObject())
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                RewardCalculator.MaxRewardMultiplier(
                    double.Parse(e.Name, System.Globalization.CultureInfo.InvariantCulture)),
                $"max_multiplier[{e.Name}]");
    }

    [Fact]
    public void BonusAndStatMultiplierGrid_MatchesPython()
    {
        foreach (var c in G.GetProperty("bonus_and_stat_multiplier_grid").EnumerateArray())
        {
            var perf = c.GetProperty("performance").GetDouble();
            var mm = c.GetProperty("max_multiplier").GetDouble();
            Assert.Equal(c.GetProperty("bonus_pct").GetInt32(),
                         RewardCalculator.BonusPct(perf, mm));
            GoldenFixture.AssertClose(c.GetProperty("stat_multiplier").GetDouble(),
                                      RewardCalculator.StatMultiplier(perf, mm),
                                      $"stat_multiplier(perf={perf})");
        }
    }

    [Fact]
    public void FailurePenalty_MatchesPython()
    {
        foreach (var e in G.GetProperty("failure_penalty_by_points").EnumerateObject())
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                RewardCalculator.FailurePenalty(
                    double.Parse(e.Name, System.Globalization.CultureInfo.InvariantCulture)),
                $"failure_penalty[{e.Name}]");
    }

    [Fact]
    public void MaterialLoss_MatchesPython()
    {
        var expected = G.GetProperty("material_loss_sample_at_25pts");
        var actual = RewardCalculator.MaterialLoss(
            new List<MaterialInput>
            {
                new("iron_ore", 10, 1), new("oak_wood", 3, 1), new("coal", 1, 1),
            }, 25.0);
        var expectedCount = 0;
        foreach (var e in expected.EnumerateObject())
        {
            expectedCount++;
            Assert.True(actual.ContainsKey(e.Name), $"missing loss entry {e.Name}");
            Assert.Equal(e.Value.GetInt32(), actual[e.Name]);
        }
        Assert.Equal(expectedCount, actual.Count);
    }

    [Fact]
    public void FirstTryBonus_MatchesPython()
    {
        foreach (var e in G.GetProperty("first_try_bonus_by_discipline").EnumerateObject())
        {
            var discipline = e.Name == "default" ? "" : e.Name;
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                RewardCalculator.FirstTryBonus(discipline),
                $"first_try[{e.Name}]");
        }
    }
}
