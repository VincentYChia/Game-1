using System.Text.Json;
using Game1.Core.Progression;
using Xunit;

namespace Game1.Core.Tests;

public class ExperienceCurveTests
{
    private static readonly JsonElement G = GoldenFixture.Load("exp_curve.json");

    [Fact]
    public void RequirementTable_MatchesPython()
    {
        Assert.Equal(G.GetProperty("max_level").GetInt32(), ExperienceCurve.MaxLevel);
        foreach (var prop in G.GetProperty("requirements_to_reach_level").EnumerateObject())
        {
            var level = int.Parse(prop.Name);
            Assert.Equal(prop.Value.GetInt64(), ExperienceCurve.RequirementForLevel(level));
        }
    }

    [Fact]
    public void CumulativeTable_MatchesPython()
    {
        foreach (var prop in G.GetProperty("cumulative_from_level_1").EnumerateObject())
        {
            var level = int.Parse(prop.Name);
            long total = 0;
            for (var l = 2; l <= level; l++)
                total += ExperienceCurve.RequirementForLevel(l);
            Assert.Equal(prop.Value.GetInt64(), total);
        }
    }

    private static void ReplayScenario(JsonElement steps)
    {
        var curve = new ExperienceCurve();
        foreach (var step in steps.EnumerateArray())
        {
            var leveled = curve.AddExp(step.GetProperty("grant").GetInt64());
            Assert.Equal(step.GetProperty("leveled").GetBoolean(), leveled);
            Assert.Equal(step.GetProperty("level").GetInt32(), curve.Level);
            Assert.Equal(step.GetProperty("current_exp").GetInt64(), curve.CurrentExp);
            Assert.Equal(step.GetProperty("unallocated_stat_points").GetInt32(),
                         curve.UnallocatedStatPoints);
        }
    }

    [Fact]
    public void SingleGrantScenarios_MatchPython()
    {
        foreach (var scenario in G.GetProperty("cascade_scenarios")
                                  .GetProperty("single_grants").EnumerateArray())
            ReplayScenario(scenario);
    }

    [Fact]
    public void SequentialGrants_MatchPython() =>
        ReplayScenario(G.GetProperty("cascade_scenarios").GetProperty("sequential"));

    [Fact]
    public void MaxLevelClamp_MatchesPython() =>
        ReplayScenario(G.GetProperty("cascade_scenarios").GetProperty("max_level_clamp"));
}
