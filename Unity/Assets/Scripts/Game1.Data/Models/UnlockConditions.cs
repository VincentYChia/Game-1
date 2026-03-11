// Game1.Data.Models.UnlockConditions
// Migrated from: data/models/unlock_conditions.py (481 lines)
// Phase: 1 - Foundation
// Contains: UnlockCondition (abstract), 8 concrete implementations,
//           UnlockRequirements (composite), ConditionFactory
//
// Note: evaluate() methods reference ICharacterContext (Phase 1 interface)
// instead of concrete Character class (Phase 3) to avoid circular dependency.
// Full evaluation logic deferred to Phase 3 when Character is available.

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Abstract base class for unlock conditions.
    /// Tag-driven design: Each condition has a type tag and can be composed with others.
    /// Evaluate() takes an object context - concrete Character checking deferred to Phase 3.
    /// </summary>
    public abstract class UnlockCondition
    {
        public abstract bool Evaluate(object characterContext);
        public abstract string GetDescription();
        public abstract Dictionary<string, object> ToDict();
    }

    public class LevelCondition : UnlockCondition
    {
        public int MinLevel { get; }

        public LevelCondition(int minLevel)
        {
            MinLevel = minLevel;
        }

        public override bool Evaluate(object characterContext)
        {
            // Full implementation in Phase 3 when Character is available
            // Will check: character.Leveling.Level >= MinLevel
            return false;
        }

        public override string GetDescription() => $"Level {MinLevel}+";

        public override Dictionary<string, object> ToDict() => new()
        {
            { "type", "level" },
            { "min_level", MinLevel }
        };
    }

    public class StatCondition : UnlockCondition
    {
        public Dictionary<string, int> StatRequirements { get; }

        public StatCondition(Dictionary<string, int> statRequirements)
        {
            StatRequirements = statRequirements ?? new Dictionary<string, int>();
        }

        public override bool Evaluate(object characterContext)
        {
            // Full implementation in Phase 3
            return false;
        }

        public override string GetDescription()
        {
            var parts = StatRequirements.Select(kvp =>
                $"{System.Globalization.CultureInfo.CurrentCulture.TextInfo.ToTitleCase(kvp.Key)} {kvp.Value}+");
            return string.Join(", ", parts);
        }

        public override Dictionary<string, object> ToDict() => new()
        {
            { "type", "stat" },
            { "requirements", StatRequirements }
        };
    }

    public class ActivityCondition : UnlockCondition
    {
        public string ActivityType { get; }
        public int MinCount { get; }

        public ActivityCondition(string activityType, int minCount)
        {
            ActivityType = activityType;
            MinCount = minCount;
        }

        public override bool Evaluate(object characterContext)
        {
            // Full implementation in Phase 3
            return false;
        }

        public override string GetDescription() =>
            $"{System.Globalization.CultureInfo.CurrentCulture.TextInfo.ToTitleCase(ActivityType)}: {MinCount}+";

        public override Dictionary<string, object> ToDict() => new()
        {
            { "type", "activity" },
            { "activity", ActivityType },
            { "min_count", MinCount }
        };
    }

    public class StatTrackerCondition : UnlockCondition
    {
        public string StatPath { get; }
        public float MinValue { get; }

        public StatTrackerCondition(string statPath, float minValue)
        {
            StatPath = statPath;
            MinValue = minValue;
        }

        public override bool Evaluate(object characterContext)
        {
            // Full implementation in Phase 3 - will navigate nested dot-notation path
            return false;
        }

        public override string GetDescription()
        {
            string readable = StatPath.Replace('_', ' ').Replace('.', '\u2192');
            return $"{System.Globalization.CultureInfo.CurrentCulture.TextInfo.ToTitleCase(readable)}: {(int)MinValue}+";
        }

        public override Dictionary<string, object> ToDict() => new()
        {
            { "type", "stat_tracker" },
            { "stat_path", StatPath },
            { "min_value", MinValue }
        };
    }

    public class TitleCondition : UnlockCondition
    {
        public List<string> RequiredTitles { get; }

        public TitleCondition(List<string> requiredTitles)
        {
            RequiredTitles = requiredTitles ?? new List<string>();
        }

        public override bool Evaluate(object characterContext)
        {
            // Full implementation in Phase 3
            return false;
        }

        public override string GetDescription() =>
            RequiredTitles.Count == 1
                ? $"Title: {RequiredTitles[0]}"
                : $"Titles: {string.Join(", ", RequiredTitles)}";

        public override Dictionary<string, object> ToDict() => new()
        {
            { "type", "title" },
            { "required_titles", RequiredTitles }
        };
    }

    public class SkillCondition : UnlockCondition
    {
        public List<string> RequiredSkills { get; }

        public SkillCondition(List<string> requiredSkills)
        {
            RequiredSkills = requiredSkills ?? new List<string>();
        }

        public override bool Evaluate(object characterContext)
        {
            // Full implementation in Phase 3
            return false;
        }

        public override string GetDescription() =>
            RequiredSkills.Count == 1
                ? $"Skill: {RequiredSkills[0]}"
                : $"Skills: {string.Join(", ", RequiredSkills)}";

        public override Dictionary<string, object> ToDict() => new()
        {
            { "type", "skill" },
            { "required_skills", RequiredSkills }
        };
    }

    public class QuestCondition : UnlockCondition
    {
        public List<string> RequiredQuests { get; }

        public QuestCondition(List<string> requiredQuests)
        {
            RequiredQuests = requiredQuests ?? new List<string>();
        }

        public override bool Evaluate(object characterContext)
        {
            // Full implementation in Phase 3
            return false;
        }

        public override string GetDescription() =>
            RequiredQuests.Count == 1
                ? $"Quest: {RequiredQuests[0]}"
                : $"Quests: {string.Join(", ", RequiredQuests)}";

        public override Dictionary<string, object> ToDict() => new()
        {
            { "type", "quest" },
            { "required_quests", RequiredQuests }
        };
    }

    public class ClassCondition : UnlockCondition
    {
        public string RequiredClass { get; }

        public ClassCondition(string requiredClass)
        {
            RequiredClass = requiredClass;
        }

        public override bool Evaluate(object characterContext)
        {
            // Full implementation in Phase 3
            return false;
        }

        public override string GetDescription() => $"Class: {RequiredClass}";

        public override Dictionary<string, object> ToDict() => new()
        {
            { "type", "class" },
            { "required_class", RequiredClass }
        };
    }

    /// <summary>
    /// Composite unlock requirements (AND logic). All conditions must be met.
    /// </summary>
    [Serializable]
    public class UnlockRequirements
    {
        public List<UnlockCondition> Conditions { get; set; } = new();

        public bool Evaluate(object characterContext)
        {
            return Conditions.All(c => c.Evaluate(characterContext));
        }

        public List<UnlockCondition> GetMissingConditions(object characterContext)
        {
            return Conditions.Where(c => !c.Evaluate(characterContext)).ToList();
        }

        public string GetDescription()
        {
            if (Conditions.Count == 0) return "No requirements";
            return string.Join(" AND ", Conditions.Select(c => c.GetDescription()));
        }

        public Dictionary<string, object> ToDict()
        {
            return new Dictionary<string, object>
            {
                { "conditions", Conditions.Select(c => c.ToDict()).ToList() }
            };
        }
    }

    /// <summary>
    /// Factory for creating UnlockCondition objects from JSON data.
    /// Tag-driven: Looks at the "type" tag to determine which condition class to create.
    /// </summary>
    public static class ConditionFactory
    {
        private static readonly Dictionary<string, string> StatMapping = new()
        {
            { "str", "strength" }, { "def", "defense" }, { "vit", "vitality" },
            { "lck", "luck" }, { "agi", "agility" }, { "int", "intelligence" },
            { "strength", "strength" }, { "defense", "defense" }, { "vitality", "vitality" },
            { "luck", "luck" }, { "agility", "agility" }, { "intelligence", "intelligence" }
        };

        private static readonly Dictionary<string, string> ActivityMapping = new()
        {
            { "oresMined", "mining" }, { "treesChopped", "forestry" },
            { "itemsSmithed", "smithing" }, { "materialsRefined", "refining" },
            { "potionsBrewed", "alchemy" }, { "itemsEnchanted", "enchanting" },
            { "devicesCreated", "engineering" }, { "enemiesDefeated", "combat" },
            { "bossesDefeated", "combat" }
        };

        public static UnlockCondition CreateFromJson(Dictionary<string, object> data)
        {
            string conditionType = data.TryGetValue("type", out var typeObj)
                ? typeObj?.ToString()?.ToLower() ?? ""
                : "";

            switch (conditionType)
            {
                case "level":
                    return new LevelCondition(Convert.ToInt32(data.GetValueOrDefault("min_level", 1)));

                case "stat":
                    if (data.TryGetValue("requirements", out var reqObj) && reqObj is Dictionary<string, object> reqs)
                    {
                        var statReqs = reqs.ToDictionary(kvp => kvp.Key, kvp => Convert.ToInt32(kvp.Value));
                        return new StatCondition(statReqs);
                    }
                    if (data.TryGetValue("stat_name", out var statNameObj))
                    {
                        string statName = statNameObj?.ToString()?.ToLower() ?? "";
                        string fullName = StatMapping.GetValueOrDefault(statName, statName);
                        int minVal = Convert.ToInt32(data.GetValueOrDefault("min_value", 0));
                        return new StatCondition(new Dictionary<string, int> { { fullName, minVal } });
                    }
                    return new StatCondition(new Dictionary<string, int>());

                case "activity":
                    return new ActivityCondition(
                        data.GetValueOrDefault("activity", "mining")?.ToString() ?? "mining",
                        Convert.ToInt32(data.GetValueOrDefault("min_count", 0)));

                case "stat_tracker":
                    return new StatTrackerCondition(
                        data.GetValueOrDefault("stat_path", "")?.ToString() ?? "",
                        Convert.ToSingle(data.GetValueOrDefault("min_value", 0)));

                case "title":
                    if (data.TryGetValue("required_titles", out var titlesObj) && titlesObj is List<object> titleList)
                        return new TitleCondition(titleList.Select(t => t.ToString()).ToList());
                    if (data.TryGetValue("required_title", out var titleObj))
                        return new TitleCondition(new List<string> { titleObj?.ToString() ?? "" });
                    return new TitleCondition(new List<string>());

                case "skill":
                    if (data.TryGetValue("required_skills", out var skillsObj) && skillsObj is List<object> skillList)
                        return new SkillCondition(skillList.Select(s => s.ToString()).ToList());
                    return new SkillCondition(new List<string>());

                case "quest":
                    if (data.TryGetValue("required_quests", out var questsObj) && questsObj is List<object> questList)
                        return new QuestCondition(questList.Select(q => q.ToString()).ToList());
                    return new QuestCondition(new List<string>());

                case "class":
                    return new ClassCondition(data.GetValueOrDefault("required_class", "")?.ToString() ?? "");

                default:
                    return null;
            }
        }

        /// <summary>
        /// Create UnlockRequirements from JSON. Supports both new (conditions list)
        /// and legacy (flat requirements) formats.
        /// </summary>
        public static UnlockRequirements CreateRequirementsFromJson(Dictionary<string, object> jsonData)
        {
            var requirements = new UnlockRequirements();

            // New format: explicit conditions list
            if (jsonData.TryGetValue("conditions", out var conditionsObj) && conditionsObj is List<object> condList)
            {
                foreach (var condObj in condList)
                {
                    if (condObj is Dictionary<string, object> condData)
                    {
                        var condition = CreateFromJson(condData);
                        if (condition != null)
                            requirements.Conditions.Add(condition);
                    }
                }
                return requirements;
            }

            // Legacy format: parse from top-level fields
            if (jsonData.TryGetValue("characterLevel", out var lvlObj))
            {
                int lvl = Convert.ToInt32(lvlObj);
                if (lvl > 0) requirements.Conditions.Add(new LevelCondition(lvl));
            }

            if (jsonData.TryGetValue("stats", out var statsObj) && statsObj is Dictionary<string, object> stats && stats.Count > 0)
            {
                var statReqs = stats.ToDictionary(kvp => kvp.Key, kvp => Convert.ToInt32(kvp.Value));
                requirements.Conditions.Add(new StatCondition(statReqs));
            }

            if (jsonData.TryGetValue("titles", out var titlesObjLeg) && titlesObjLeg is List<object> titlesLeg && titlesLeg.Count > 0)
                requirements.Conditions.Add(new TitleCondition(titlesLeg.Select(t => t.ToString()).ToList()));

            if (jsonData.TryGetValue("requiredTitles", out var reqTitles) && reqTitles is List<object> reqTitlesList && reqTitlesList.Count > 0)
                requirements.Conditions.Add(new TitleCondition(reqTitlesList.Select(t => t.ToString()).ToList()));

            if (jsonData.TryGetValue("completedQuests", out var cqObj) && cqObj is List<object> cqList && cqList.Count > 0)
                requirements.Conditions.Add(new QuestCondition(cqList.Select(q => q.ToString()).ToList()));

            if (jsonData.TryGetValue("activityMilestones", out var milObj) && milObj is List<object> milestones)
            {
                foreach (var msObj in milestones)
                {
                    if (msObj is Dictionary<string, object> milestone)
                    {
                        string msType = milestone.GetValueOrDefault("type", "")?.ToString() ?? "";
                        int count = Convert.ToInt32(milestone.GetValueOrDefault("count", 0));

                        switch (msType)
                        {
                            case "craft_count":
                                string discipline = milestone.GetValueOrDefault("discipline", "smithing")?.ToString() ?? "smithing";
                                requirements.Conditions.Add(new StatTrackerCondition(
                                    $"crafting_by_discipline.{discipline}.total_crafts", count));
                                break;
                            case "kill_count":
                                requirements.Conditions.Add(new StatTrackerCondition("combat_kills.total_kills", count));
                                break;
                            case "gather_count":
                                requirements.Conditions.Add(new ActivityCondition("mining", count / 2));
                                requirements.Conditions.Add(new ActivityCondition("forestry", count / 2));
                                break;
                        }
                    }
                }
            }

            if (jsonData.TryGetValue("activities", out var actObj) && actObj is Dictionary<string, object> activities)
            {
                foreach (var kvp in activities)
                {
                    string activityType = ActivityMapping.GetValueOrDefault(kvp.Key, kvp.Key);
                    requirements.Conditions.Add(new ActivityCondition(activityType, Convert.ToInt32(kvp.Value)));
                }
            }

            return requirements;
        }

        /// <summary>
        /// JObject overload for Phase 2 database loading.
        /// Converts JObject to Dictionary for the main method.
        /// </summary>
        public static UnlockRequirements CreateRequirementsFromJson(Newtonsoft.Json.Linq.JObject jsonObj)
        {
            if (jsonObj == null) return new UnlockRequirements();
            var dict = jsonObj.ToObject<Dictionary<string, object>>() ?? new Dictionary<string, object>();
            return CreateRequirementsFromJson(dict);
        }
    }
}
