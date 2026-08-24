using System.Text.Json.Nodes;
using Game1.Core.Data;

namespace Game1.Core.Progression;

/// <summary>
/// Port of data/models/unlock_conditions.py — the tag-driven unlock condition
/// system for titles and skills. Python duck-types Character; here the
/// queried surface is explicit: ICharacterQuery (contract docs 03/04 —
/// "duck typing is the correctness surface, needs an interface in C#").
/// Pinned by conformance/goldens/db_parity/unlock_conditions.json (parse
/// to_dict/description parity + evaluation matrix vs stub characters).
/// </summary>
public interface ICharacterQuery
{
    int Level { get; }
    int GetStat(string statName);            // strength/defense/vitality/luck/agility/intelligence
    int GetActivityCount(string activityType);
    bool HasTitle(string titleId);
    bool KnowsSkill(string skillId);
    bool IsQuestCompleted(string questId);
    string? CurrentClassId { get; }

    /// <summary>Dot-path stat-tracker lookup (Python walks nested dicts/attrs
    /// itself; here the query owner resolves the path). Null = unavailable →
    /// condition evaluates false, mirroring the Python hasattr guard.</summary>
    double? GetStatTrackerValue(string statPath);
}

public abstract class UnlockCondition
{
    public abstract bool Evaluate(ICharacterQuery character);
    public abstract string GetDescription();
    public abstract JsonObject ToDict();

    /// <summary>Python str.title(): first letter of each alpha run uppercased,
    /// rest lowercased (word boundary = any non-letter).</summary>
    protected static string PyTitle(string s)
    {
        var chars = s.ToCharArray();
        var prevIsLetter = false;
        for (var i = 0; i < chars.Length; i++)
        {
            if (char.IsLetter(chars[i]))
            {
                chars[i] = prevIsLetter
                    ? char.ToLowerInvariant(chars[i])
                    : char.ToUpperInvariant(chars[i]);
                prevIsLetter = true;
            }
            else
            {
                prevIsLetter = false;
            }
        }
        return new string(chars);
    }
}

public sealed class LevelCondition : UnlockCondition
{
    public double MinLevel { get; }
    public LevelCondition(double minLevel) => MinLevel = minLevel;

    public override bool Evaluate(ICharacterQuery c) => c.Level >= MinLevel;
    public override string GetDescription() => $"Level {J.PyNum(MinLevel)}+";
    public override JsonObject ToDict() =>
        new() { ["type"] = "level", ["min_level"] = MinLevel };
}

public sealed class StatCondition : UnlockCondition
{
    public JsonObject StatRequirements { get; }
    public StatCondition(JsonObject statRequirements) => StatRequirements = statRequirements;

    public override bool Evaluate(ICharacterQuery c)
    {
        foreach (var kv in StatRequirements)
        {
            var required = kv.Value is JsonValue v && v.TryGetValue<double>(out var d) ? d : 0;
            // unlock_conditions.py:84 — unknown stat names read as 0
            if (c.GetStat(kv.Key.ToLowerInvariant()) < required)
                return false;
        }
        return true;
    }

    public override string GetDescription() =>
        string.Join(", ", StatRequirements.Select(kv =>
            $"{PyTitle(kv.Key)} {J.PyNum(kv.Value is JsonValue v && v.TryGetValue<double>(out var d) ? d : 0)}+"));

    public override JsonObject ToDict() =>
        new() { ["type"] = "stat", ["requirements"] = StatRequirements.DeepClone() };
}

public sealed class ActivityCondition : UnlockCondition
{
    public string ActivityType { get; }
    public double MinCount { get; }
    public ActivityCondition(string activityType, double minCount)
    { ActivityType = activityType; MinCount = minCount; }

    public override bool Evaluate(ICharacterQuery c) =>
        c.GetActivityCount(ActivityType) >= MinCount;
    public override string GetDescription() =>
        $"{PyTitle(ActivityType)}: {J.PyNum(MinCount)}+";
    public override JsonObject ToDict() => new()
    { ["type"] = "activity", ["activity"] = ActivityType, ["min_count"] = MinCount };
}

public sealed class StatTrackerCondition : UnlockCondition
{
    public string StatPath { get; }
    public double MinValue { get; }
    public StatTrackerCondition(string statPath, double minValue)
    { StatPath = statPath; MinValue = minValue; }

    public override bool Evaluate(ICharacterQuery c)
    {
        var value = c.GetStatTrackerValue(StatPath);
        return value is not null && value.Value >= MinValue;
    }

    // unlock_conditions.py:173-176
    public override string GetDescription()
    {
        var readable = PyTitle(StatPath.Replace("_", " ").Replace(".", " → "));
        return $"{readable}: {(long)MinValue}+";
    }

    public override JsonObject ToDict() => new()
    { ["type"] = "stat_tracker", ["stat_path"] = StatPath, ["min_value"] = MinValue };
}

public sealed class TitleCondition : UnlockCondition
{
    public List<string> RequiredTitles { get; }
    public TitleCondition(List<string> requiredTitles) => RequiredTitles = requiredTitles;

    public override bool Evaluate(ICharacterQuery c) =>
        RequiredTitles.All(c.HasTitle);
    public override string GetDescription() =>
        RequiredTitles.Count == 1
            ? $"Title: {RequiredTitles[0]}"
            : $"Titles: {string.Join(", ", RequiredTitles)}";
    public override JsonObject ToDict()
    {
        var arr = new JsonArray();
        foreach (var t in RequiredTitles) arr.Add(t);
        return new JsonObject { ["type"] = "title", ["required_titles"] = arr };
    }
}

public sealed class SkillCondition : UnlockCondition
{
    public List<string> RequiredSkills { get; }
    public SkillCondition(List<string> requiredSkills) => RequiredSkills = requiredSkills;

    public override bool Evaluate(ICharacterQuery c) =>
        RequiredSkills.All(c.KnowsSkill);
    public override string GetDescription() =>
        RequiredSkills.Count == 1
            ? $"Skill: {RequiredSkills[0]}"
            : $"Skills: {string.Join(", ", RequiredSkills)}";
    public override JsonObject ToDict()
    {
        var arr = new JsonArray();
        foreach (var s in RequiredSkills) arr.Add(s);
        return new JsonObject { ["type"] = "skill", ["required_skills"] = arr };
    }
}

public sealed class QuestCondition : UnlockCondition
{
    public List<string> RequiredQuests { get; }
    public QuestCondition(List<string> requiredQuests) => RequiredQuests = requiredQuests;

    public override bool Evaluate(ICharacterQuery c) =>
        RequiredQuests.All(c.IsQuestCompleted);
    public override string GetDescription() =>
        RequiredQuests.Count == 1
            ? $"Quest: {RequiredQuests[0]}"
            : $"Quests: {string.Join(", ", RequiredQuests)}";
    public override JsonObject ToDict()
    {
        var arr = new JsonArray();
        foreach (var q in RequiredQuests) arr.Add(q);
        return new JsonObject { ["type"] = "quest", ["required_quests"] = arr };
    }
}

public sealed class ClassCondition : UnlockCondition
{
    public string RequiredClass { get; }
    public ClassCondition(string requiredClass) => RequiredClass = requiredClass;

    public override bool Evaluate(ICharacterQuery c) =>
        c.CurrentClassId is not null && c.CurrentClassId == RequiredClass;
    public override string GetDescription() => $"Class: {RequiredClass}";
    public override JsonObject ToDict() =>
        new() { ["type"] = "class", ["required_class"] = RequiredClass };
}

public sealed class UnlockRequirements
{
    public List<UnlockCondition> Conditions { get; } = new();

    public bool Evaluate(ICharacterQuery character) =>
        Conditions.All(c => c.Evaluate(character));

    public List<UnlockCondition> GetMissingConditions(ICharacterQuery character) =>
        Conditions.Where(c => !c.Evaluate(character)).ToList();

    public string GetDescription() =>
        Conditions.Count == 0
            ? "No requirements"
            : string.Join(" AND ", Conditions.Select(c => c.GetDescription()));

    public JsonObject ToDict()
    {
        var arr = new JsonArray();
        foreach (var c in Conditions) arr.Add(c.ToDict());
        return new JsonObject { ["conditions"] = arr };
    }
}

public static class ConditionFactory
{
    private static readonly Dictionary<string, string> StatNameMap = new()
    {
        ["str"] = "strength", ["def"] = "defense", ["vit"] = "vitality",
        ["lck"] = "luck", ["agi"] = "agility", ["int"] = "intelligence",
        ["strength"] = "strength", ["defense"] = "defense", ["vitality"] = "vitality",
        ["luck"] = "luck", ["agility"] = "agility", ["intelligence"] = "intelligence",
    };

    // unlock_conditions.py:463-479 — NOTE: lacks areasExplored (differs from
    // title_db's map; faithful to the code)
    private static readonly Dictionary<string, string> LegacyActivityMap = new()
    {
        ["oresMined"] = "mining", ["treesChopped"] = "forestry",
        ["itemsSmithed"] = "smithing", ["materialsRefined"] = "refining",
        ["potionsBrewed"] = "alchemy", ["itemsEnchanted"] = "enchanting",
        ["devicesCreated"] = "engineering", ["enemiesDefeated"] = "combat",
        ["bossesDefeated"] = "combat",
    };

    public static UnlockCondition? CreateFromJson(JsonObject data)
    {
        var conditionType = J.Str(data, "type").ToLowerInvariant();
        switch (conditionType)
        {
            case "level":
                return new LevelCondition(J.Num(data, "min_level", 1));

            case "stat":
                if (data.TryGetPropertyValue("requirements", out var reqNode)
                    && reqNode is JsonObject reqObj)
                    return new StatCondition((JsonObject)reqObj.DeepClone());
                if (data.ContainsKey("stat_name"))
                {
                    var statName = J.Str(data, "stat_name").ToLowerInvariant();
                    var fullName = StatNameMap.GetValueOrDefault(statName, statName);
                    return new StatCondition(new JsonObject
                    { [fullName] = J.Node(data, "min_value", () => JsonValue.Create(0)!) });
                }
                return new StatCondition(new JsonObject());

            case "activity":
                return new ActivityCondition(
                    J.Str(data, "activity", "mining"), J.Num(data, "min_count", 0));

            case "stat_tracker":
                return new StatTrackerCondition(
                    J.Str(data, "stat_path"), J.Num(data, "min_value", 0));

            case "title":
                if (data.TryGetPropertyValue("required_titles", out var titles)
                    && titles is JsonArray titleArr)
                    return new TitleCondition(Strings(titleArr));
                if (data.ContainsKey("required_title"))
                {
                    var titleId = J.Str(data, "required_title");
                    return new TitleCondition(
                        titleId.Length > 0 ? new List<string> { titleId } : new List<string>());
                }
                return null;  // Python falls off the elif with no return

            case "skill":
                return new SkillCondition(Strings(
                    data.TryGetPropertyValue("required_skills", out var sk)
                    && sk is JsonArray ska ? ska : new JsonArray()));

            case "quest":
                return new QuestCondition(Strings(
                    data.TryGetPropertyValue("required_quests", out var q)
                    && q is JsonArray qa ? qa : new JsonArray()));

            case "class":
                return new ClassCondition(J.Str(data, "required_class"));

            default:
                return null;
        }

        static List<string> Strings(JsonArray arr) =>
            arr.OfType<JsonValue>()
               .Select(v => v.TryGetValue<string>(out var s) ? s : null)
               .Where(s => s is not null).Cast<string>().ToList();
    }

    // unlock_conditions.py:386-481
    public static UnlockRequirements CreateRequirementsFromJson(JsonObject json)
    {
        var requirements = new UnlockRequirements();

        if (json.TryGetPropertyValue("conditions", out var condNode)
            && condNode is JsonArray condArr)
        {
            foreach (var node in condArr)
                if (node is JsonObject c && CreateFromJson(c) is { } condition)
                    requirements.Conditions.Add(condition);
            return requirements;
        }

        // Legacy format
        if (json.ContainsKey("characterLevel") && J.Num(json, "characterLevel", 0) > 0)
            requirements.Conditions.Add(new LevelCondition(J.Num(json, "characterLevel", 0)));

        if (json.TryGetPropertyValue("stats", out var stats)
            && stats is JsonObject statsObj && statsObj.Count > 0)
            requirements.Conditions.Add(new StatCondition((JsonObject)statsObj.DeepClone()));

        if (json.TryGetPropertyValue("titles", out var t)
            && t is JsonArray ta && ta.Count > 0)
            requirements.Conditions.Add(new TitleCondition(StringList(ta)));

        if (json.TryGetPropertyValue("requiredTitles", out var rt)
            && rt is JsonArray rta && rta.Count > 0)
            requirements.Conditions.Add(new TitleCondition(StringList(rta)));

        if (json.TryGetPropertyValue("completedQuests", out var cq)
            && cq is JsonArray cqa && cqa.Count > 0)
            requirements.Conditions.Add(new QuestCondition(StringList(cqa)));

        if (json.TryGetPropertyValue("activityMilestones", out var am)
            && am is JsonArray milestones)
        {
            foreach (var node in milestones)
            {
                if (node is not JsonObject milestone) continue;
                var mType = J.Str(milestone, "type");
                var count = J.Num(milestone, "count", 0);
                switch (mType)
                {
                    case "craft_count":
                        var discipline = J.Str(milestone, "discipline", "smithing");
                        requirements.Conditions.Add(new StatTrackerCondition(
                            $"crafting_by_discipline.{discipline}.total_crafts", count));
                        break;
                    case "kill_count":
                        requirements.Conditions.Add(
                            new StatTrackerCondition("combat_kills.total_kills", count));
                        break;
                    case "gather_count":
                        // py :452-460 — approximate mining/forestry split (floor div)
                        requirements.Conditions.Add(
                            new ActivityCondition("mining", Math.Floor(count / 2)));
                        requirements.Conditions.Add(
                            new ActivityCondition("forestry", Math.Floor(count / 2)));
                        break;
                }
            }
        }

        if (json.TryGetPropertyValue("activities", out var act)
            && act is JsonObject actObj && actObj.Count > 0)
        {
            foreach (var kv in actObj)
            {
                var activityType = LegacyActivityMap.GetValueOrDefault(kv.Key, kv.Key);
                var count = kv.Value is JsonValue v && v.TryGetValue<double>(out var d) ? d : 0;
                requirements.Conditions.Add(new ActivityCondition(activityType, count));
            }
        }

        return requirements;

        static List<string> StringList(JsonArray arr) =>
            arr.OfType<JsonValue>()
               .Select(v => v.TryGetValue<string>(out var s) ? s : null)
               .Where(s => s is not null).Cast<string>().ToList();
    }
}
