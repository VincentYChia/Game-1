// Game1.Data.Databases.SkillDatabase
// Migrated from: data/databases/skill_db.py (123 lines)
// Phase: 2 - Data Layer
// Loads from Skills/skills-skills-1.JSON.
// CRITICAL: Has its own canonical translation tables (includes "extreme" entries).

using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for skill definitions.
    /// Contains its own inline translation tables for mana/cooldown/duration
    /// (includes "extreme" entries not in TranslationDatabase).
    /// </summary>
    public class SkillDatabase
    {
        private static SkillDatabase _instance;
        private static readonly object _lock = new object();

        public Dictionary<string, SkillDefinition> Skills { get; private set; }
        public bool Loaded { get; private set; }

        // Canonical translation tables (includes "extreme" entries)
        public readonly Dictionary<string, int> ManaCosts = new()
        {
            { "low", 30 }, { "moderate", 60 }, { "high", 100 }, { "extreme", 150 }
        };

        public readonly Dictionary<string, float> Cooldowns = new()
        {
            { "short", 120f }, { "moderate", 300f }, { "long", 600f }, { "extreme", 1200f }
        };

        public readonly Dictionary<string, float> Durations = new()
        {
            { "instant", 0f }, { "brief", 15f }, { "moderate", 30f }, { "long", 60f }, { "extended", 120f }
        };

        public static SkillDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new SkillDatabase();
                }
            }
            return _instance;
        }

        private SkillDatabase()
        {
            Skills = new Dictionary<string, SkillDefinition>();
        }

        public bool LoadFromFile(string filepath)
        {
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data == null) return false;

                var skillsArr = data["skills"] as JArray;
                if (skillsArr == null) return false;

                foreach (JObject skillData in skillsArr)
                {
                    // Parse effect
                    var effectData = skillData["effect"] as JObject;
                    var effect = new SkillEffect
                    {
                        EffectType = effectData?.Value<string>("type") ?? "",
                        Category = effectData?.Value<string>("category") ?? "",
                        Magnitude = effectData?.Value<string>("magnitude") ?? "",
                        Target = effectData?.Value<string>("target") ?? "self",
                        Duration = effectData?.Value<string>("duration") ?? "instant"
                    };
                    if (effectData?["additionalEffects"] is JArray addFx)
                    {
                        foreach (JObject fx in addFx)
                        {
                            var fxDict = new Dictionary<string, object>();
                            foreach (var p in fx.Properties())
                                fxDict[p.Name] = p.Value.ToObject<object>();
                            effect.AdditionalEffects.Add(fxDict);
                        }
                    }

                    // Parse cost
                    var costData = skillData["cost"] as JObject;
                    var cost = new SkillCost();
                    if (costData != null)
                    {
                        // Mana: can be string or number
                        var manaToken = costData["mana"];
                        cost.Mana = manaToken?.Type == JTokenType.String
                            ? manaToken.Value<string>()
                            : (object)(manaToken?.Value<float>() ?? 60f);

                        var cdToken = costData["cooldown"];
                        cost.Cooldown = cdToken?.Type == JTokenType.String
                            ? cdToken.Value<string>()
                            : (object)(cdToken?.Value<float>() ?? 300f);
                    }

                    // Parse evolution
                    var evoData = skillData["evolution"] as JObject;
                    var evolution = new SkillEvolution
                    {
                        CanEvolve = evoData?.Value<bool?>("canEvolve") ?? false,
                        NextSkillId = evoData?.Value<string>("nextSkillId"),
                        Requirement = evoData?.Value<string>("requirement") ?? ""
                    };

                    // Parse requirements
                    var reqData = skillData["requirements"] as JObject;
                    var requirements = new SkillRequirements
                    {
                        CharacterLevel = reqData?.Value<int?>("characterLevel") ?? 1
                    };
                    if (reqData?["stats"] is JObject statsObj)
                        foreach (var p in statsObj.Properties())
                            requirements.Stats[p.Name] = p.Value.Value<int>();
                    if (reqData?["titles"] is JArray titlesArr)
                        foreach (var t in titlesArr)
                            requirements.Titles.Add(t.Value<string>());

                    // Icon path
                    string skillId = skillData.Value<string>("skillId") ?? "";
                    string iconPath = skillData.Value<string>("iconPath");
                    if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(skillId))
                        iconPath = $"skills/{skillId}.png";

                    // Parse tags and categories
                    var categories = new List<string>();
                    if (skillData["categories"] is JArray catArr)
                        foreach (var c in catArr) categories.Add(c.Value<string>());

                    var tags = new List<string>();
                    if (skillData["tags"] is JArray tagsArr)
                        foreach (var t in tagsArr) tags.Add(t.Value<string>());

                    var combatTags = new List<string>();
                    if (skillData["combatTags"] is JArray ctArr)
                        foreach (var t in ctArr) combatTags.Add(t.Value<string>());

                    var combatParams = new Dictionary<string, object>();
                    if (skillData["combatParams"] is JObject cpObj)
                        foreach (var p in cpObj.Properties())
                            combatParams[p.Name] = p.Value.ToObject<object>();

                    var skill = new SkillDefinition
                    {
                        SkillId = skillId,
                        Name = skillData.Value<string>("name") ?? "",
                        Tier = skillData.Value<int?>("tier") ?? 1,
                        Rarity = skillData.Value<string>("rarity") ?? "common",
                        Categories = categories,
                        Description = skillData.Value<string>("description") ?? "",
                        Narrative = skillData.Value<string>("narrative") ?? "",
                        Tags = tags,
                        Effect = effect,
                        Cost = cost,
                        Evolution = evolution,
                        Requirements = requirements,
                        IconPath = iconPath,
                        CombatTags = combatTags,
                        CombatParams = combatParams
                    };

                    Skills[skill.SkillId] = skill;
                }

                Loaded = true;
                JsonLoader.Log($"Loaded {Skills.Count} skills");
                return true;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading skills: {ex.Message}");
                return false;
            }
        }

        public SkillDefinition GetSkill(string skillId) =>
            Skills.TryGetValue(skillId, out var skill) ? skill : null;

        /// <summary>
        /// Convert mana cost to numeric value. Supports string enums and direct numbers.
        /// </summary>
        public int GetManaCost(object costValue)
        {
            if (costValue is int i) return i;
            if (costValue is long l) return (int)l;
            if (costValue is float f) return (int)f;
            if (costValue is double d) return (int)d;
            if (costValue is string s)
                return ManaCosts.TryGetValue(s, out int cost) ? cost : 60;
            return 60;
        }

        /// <summary>
        /// Convert cooldown to seconds. Supports string enums and direct numbers.
        /// </summary>
        public float GetCooldownSeconds(object cooldownValue)
        {
            if (cooldownValue is int i) return i;
            if (cooldownValue is long l) return l;
            if (cooldownValue is float f) return f;
            if (cooldownValue is double d) return (float)d;
            if (cooldownValue is string s)
                return Cooldowns.TryGetValue(s, out float cd) ? cd : 300f;
            return 300f;
        }

        /// <summary>
        /// Convert text duration to seconds.
        /// </summary>
        public float GetDurationSeconds(string durationText)
        {
            return Durations.TryGetValue(durationText ?? "", out float dur) ? dur : 0f;
        }

        internal static void ResetInstance() => _instance = null;
    }
}
