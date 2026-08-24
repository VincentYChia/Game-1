using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Content;
using Game1.Core.Data;
using Game1.Core.Progression;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Two-sided oracle for the unlock-condition system: PARSE parity (the
/// fixture's specs run through the real Python ConditionFactory; C# must
/// produce identical to_dict + descriptions) and EVALUATION parity (stub
/// characters × requirement matrix through the real Python classes).
/// Also closes the P1 titles-requirements exclusion and gates the 16th
/// database (skill unlocks).
/// </summary>
public class UnlockConditionTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/unlock_conditions.json");

    private sealed class StubCharacter : ICharacterQuery
    {
        private readonly JsonElement _spec;
        private readonly JsonElement? _tracker;

        public StubCharacter(JsonElement spec)
        {
            _spec = spec;
            _tracker = spec.TryGetProperty("tracker", out var t) ? t : null;
        }

        public int Level =>
            _spec.TryGetProperty("level", out var l) ? l.GetInt32() : 1;

        public int GetStat(string statName) =>
            _spec.TryGetProperty("stats", out var s)
            && s.TryGetProperty(statName, out var v) ? v.GetInt32() : 0;

        public int GetActivityCount(string activityType) =>
            _spec.TryGetProperty("activities", out var a)
            && a.TryGetProperty(activityType, out var v) ? v.GetInt32() : 0;

        public bool HasTitle(string titleId) => InList("titles", titleId);
        public bool KnowsSkill(string skillId) => InList("skills", skillId);
        public bool IsQuestCompleted(string questId) => InList("quests", questId);

        public string? CurrentClassId =>
            _spec.TryGetProperty("class_id", out var c) ? c.GetString() : null;

        public double? GetStatTrackerValue(string statPath)
        {
            if (_tracker is null) return null;  // mirrors hasattr guard
            var current = _tracker.Value;
            foreach (var part in statPath.Split('.'))
            {
                if (current.ValueKind == JsonValueKind.Object
                    && current.TryGetProperty(part, out var next))
                    current = next;
                else
                    return null;
            }
            return current.ValueKind == JsonValueKind.Number ? current.GetDouble() : null;
        }

        private bool InList(string key, string value)
        {
            if (!_spec.TryGetProperty(key, out var arr)
                || arr.ValueKind != JsonValueKind.Array)
                return false;
            foreach (var item in arr.EnumerateArray())
                if (item.GetString() == value)
                    return true;
            return false;
        }
    }

    private static UnlockRequirements ParseSpec(JsonElement spec) =>
        ConditionFactory.CreateRequirementsFromJson(
            JsonNode.Parse(spec.GetRawText())!.AsObject());

    [Fact]
    public void Parse_MatchesPythonFactory()
    {
        var specs = G.GetProperty("specs");
        var parsed = G.GetProperty("parsed");
        foreach (var spec in specs.EnumerateObject())
        {
            var req = ParseSpec(spec.Value);
            var expected = parsed.GetProperty(spec.Name);
            var diffs = JsonTreeComparer.Diff(expected.GetProperty("to_dict"), req.ToDict());
            Assert.True(diffs.Count == 0,
                $"parse[{spec.Name}]: " + string.Join("; ", diffs.Take(10)));
            Assert.Equal(expected.GetProperty("description").GetString(), req.GetDescription());
        }
    }

    [Fact]
    public void Evaluation_MatchesPythonClasses()
    {
        var specs = G.GetProperty("specs");
        var stubSpecs = G.GetProperty("stub_specs");
        var evaluations = G.GetProperty("evaluations");

        var stubs = stubSpecs.EnumerateObject()
            .ToDictionary(p => p.Name, p => new StubCharacter(p.Value));

        foreach (var spec in specs.EnumerateObject())
        {
            var req = ParseSpec(spec.Value);
            var expected = evaluations.GetProperty(spec.Name);
            foreach (var stub in stubs)
            {
                var e = expected.GetProperty(stub.Key);
                Assert.True(e.GetProperty("met").GetBoolean() == req.Evaluate(stub.Value),
                    $"eval[{spec.Name}][{stub.Key}].met mismatch");
                Assert.True(e.GetProperty("missing_count").GetInt32()
                            == req.GetMissingConditions(stub.Value).Count,
                    $"eval[{spec.Name}][{stub.Key}].missing_count mismatch");
            }
        }
    }

    [Fact]
    public void TitleRequirements_MatchPython_ClosingP1Exclusion()
    {
        var titles = BootedDatabases.All.Value.Titles;
        var expected = G.GetProperty("title_requirements");
        var count = 0;
        foreach (var e in expected.EnumerateObject())
        {
            Assert.True(titles.Titles.ContainsKey(e.Name), $"missing title {e.Name}");
            var req = ConditionFactory.CreateRequirementsFromJson(
                titles.Titles[e.Name].RequirementsRaw);
            var diffs = JsonTreeComparer.Diff(e.Value.GetProperty("to_dict"), req.ToDict());
            Assert.True(diffs.Count == 0,
                $"title_req[{e.Name}]: " + string.Join("; ", diffs.Take(10)));
            Assert.Equal(e.Value.GetProperty("description").GetString(), req.GetDescription());
            count++;
        }
        Assert.Equal(titles.Titles.Count, count);
    }

    [Fact]
    public void SkillUnlocks_MatchPythonLoaderState_SixteenthDatabase()
    {
        var root = ContentPaths.TryGetContentRoot()!;
        var db = new SkillUnlockDatabase();
        db.LoadFromFile(Path.Combine(root, "progression", "skill-unlocks.JSON"));
        UpdateLoader.LoadSkillUnlockUpdates(root, db);  // boot loads Update-N last

        var expected = G.GetProperty("skill_unlocks");
        var expectedCount = 0;
        foreach (var e in expected.EnumerateObject())
        {
            expectedCount++;
            Assert.True(db.Unlocks.ContainsKey(e.Name), $"missing unlock {e.Name}");
            var u = db.Unlocks[e.Name];
            Assert.Equal(e.Value.GetProperty("skill_id").GetString(), u.SkillId);
            Assert.Equal(e.Value.GetProperty("unlock_method").GetString(), u.UnlockMethod);
            Assert.Equal(e.Value.GetProperty("narrative").GetString(), u.Narrative);
            Assert.Equal(e.Value.GetProperty("category").GetString(), u.Category);

            var trig = e.Value.GetProperty("trigger");
            Assert.Equal(trig.GetProperty("type").GetString(), u.Trigger.Type);
            Assert.Equal(trig.GetProperty("message").GetString(), u.Trigger.Message);
            var tvDiffs = JsonTreeComparer.Diff(trig.GetProperty("trigger_value"),
                u.Trigger.TriggerValue);
            Assert.True(tvDiffs.Count == 0,
                $"trigger_value[{e.Name}]: " + string.Join("; ", tvDiffs.Take(5)));

            var cost = e.Value.GetProperty("cost");
            GoldenFixture.AssertClose(cost.GetProperty("gold").GetDouble(),
                u.Cost.Gold, $"cost.gold[{e.Name}]");
            GoldenFixture.AssertClose(cost.GetProperty("skill_points").GetDouble(),
                u.Cost.SkillPoints, $"cost.skill_points[{e.Name}]");
            var matDiffs = JsonTreeComparer.Diff(cost.GetProperty("materials"),
                u.Cost.Materials);
            Assert.True(matDiffs.Count == 0,
                $"cost.materials[{e.Name}]: " + string.Join("; ", matDiffs.Take(5)));

            var reqDiffs = JsonTreeComparer.Diff(
                e.Value.GetProperty("requirements_to_dict"), u.Requirements.ToDict());
            Assert.True(reqDiffs.Count == 0,
                $"requirements[{e.Name}]: " + string.Join("; ", reqDiffs.Take(10)));
            Assert.Equal(e.Value.GetProperty("requirements_description").GetString(),
                u.Requirements.GetDescription());
        }
        Assert.Equal(expectedCount, db.Unlocks.Count);

        foreach (var e in G.GetProperty("unlocks_by_skill").EnumerateObject())
            Assert.Equal(e.Value.GetString(), db.UnlocksBySkill[e.Name].UnlockId);
    }
}
