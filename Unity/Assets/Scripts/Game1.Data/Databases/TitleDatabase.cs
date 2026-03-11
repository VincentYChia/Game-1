// Game1.Data.Databases.TitleDatabase
// Migrated from: data/databases/title_db.py (176 lines)
// Phase: 2 - Data Layer
// Loads from progression/titles-1.JSON.
// CRITICAL: Bonus key mapping (29+ entries) must be preserved exactly.
// CRITICAL: Uses ConditionFactory for parsing prerequisites.

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for title definitions.
    /// 40+ achievement titles with tag-driven bonuses.
    /// </summary>
    public class TitleDatabase
    {
        private static TitleDatabase _instance;
        private static readonly object _lock = new object();

        public Dictionary<string, TitleDefinition> Titles { get; private set; }
        public bool Loaded { get; private set; }

        // Bonus key mapping: JSON camelCase -> internal snake_case (29+ entries)
        private static readonly Dictionary<string, string> BonusMapping = new()
        {
            { "miningDamage", "mining_damage" }, { "miningSpeed", "mining_speed" },
            { "forestryDamage", "forestry_damage" }, { "forestrySpeed", "forestry_speed" },
            { "smithingTime", "smithing_speed" }, { "smithingQuality", "smithing_quality" },
            { "refiningPrecision", "refining_speed" }, { "meleeDamage", "melee_damage" },
            { "criticalChance", "crit_chance" }, { "attackSpeed", "attack_speed" },
            { "firstTryBonus", "first_try_bonus" }, { "rareOreChance", "rare_ore_chance" },
            { "rareWoodChance", "rare_wood_chance" }, { "fireOreChance", "fire_ore_chance" },
            { "alloyQuality", "alloy_quality" }, { "materialYield", "material_yield" },
            { "combatSkillExp", "combat_skill_exp" }, { "counterChance", "counter_chance" },
            { "durabilityBonus", "durability_bonus" }, { "legendaryChance", "legendary_chance" },
            { "dragonDamage", "dragon_damage" }, { "fireResistance", "fire_resistance" },
            { "legendaryDropRate", "legendary_drop_rate" }, { "luckStat", "luck_stat" },
            { "rareDropRate", "rare_drop_rate" },
            // Fishing bonuses
            { "fishingSpeed", "fishing_speed" }, { "fishingAccuracy", "fishing_accuracy" },
            { "rareFishChance", "rare_fish_chance" }, { "fishingYield", "fishing_yield" }
        };

        // Activity mapping: JSON key -> internal activity type
        private static readonly Dictionary<string, string> ActivityMapping = new()
        {
            { "oresMined", "mining" }, { "treesChopped", "forestry" },
            { "itemsSmithed", "smithing" }, { "materialsRefined", "refining" },
            { "potionsBrewed", "alchemy" }, { "itemsEnchanted", "enchanting" },
            { "devicesCreated", "engineering" }, { "enemiesDefeated", "combat" },
            { "bossesDefeated", "combat" }, { "areasExplored", "exploration" }
        };

        public static TitleDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new TitleDatabase();
                }
            }
            return _instance;
        }

        private TitleDatabase()
        {
            Titles = new Dictionary<string, TitleDefinition>();
        }

        public bool LoadFromFile(string filepath)
        {
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data == null)
                {
                    CreatePlaceholders();
                    return false;
                }

                var titlesArr = data["titles"] as JArray;
                if (titlesArr == null)
                {
                    CreatePlaceholders();
                    return false;
                }

                foreach (JObject titleData in titlesArr)
                {
                    var title = ParseTitleDefinition(titleData);
                    Titles[title.TitleId] = title;
                }

                Loaded = true;
                JsonLoader.Log($"Loaded {Titles.Count} titles");
                return true;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading titles: {ex.Message}");
                CreatePlaceholders();
                return false;
            }
        }

        private TitleDefinition ParseTitleDefinition(JObject titleData)
        {
            // Parse bonuses
            var bonusesData = titleData["bonuses"] as JObject;
            var bonuses = MapBonuses(bonusesData);

            // Title ID and icon path
            string titleId = titleData.Value<string>("titleId") ?? "";
            string iconPath = titleData.Value<string>("iconPath");
            if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(titleId))
                iconPath = $"titles/{titleId}.png";

            // Parse requirements using ConditionFactory
            var prereqs = titleData["prerequisites"] as JObject ?? new JObject();
            var requirements = ConditionFactory.CreateRequirementsFromJson(prereqs);

            // Legacy activity type and threshold
            var activities = prereqs["activities"] as JObject;
            var (activityType, threshold) = ParseActivity(activities);

            var prereqTitles = new List<string>();
            if (prereqs["requiredTitles"] is JArray reqTArr)
                foreach (var t in reqTArr) prereqTitles.Add(t.Value<string>());

            string acquisitionMethod = titleData.Value<string>("acquisitionMethod") ?? "guaranteed_milestone";
            float generationChance = titleData.Value<float?>("generationChance") ?? 1.0f;

            return new TitleDefinition
            {
                TitleId = titleId,
                Name = titleData.Value<string>("name") ?? "",
                Tier = titleData.Value<string>("difficultyTier") ?? "novice",
                Category = titleData.Value<string>("titleType") ?? "general",
                BonusDescription = CreateBonusDescription(bonuses),
                Bonuses = bonuses,
                Requirements = requirements,
                Hidden = titleData.Value<bool?>("isHidden") ?? false,
                AcquisitionMethod = acquisitionMethod,
                GenerationChance = generationChance,
                IconPath = iconPath,
                // Legacy fields
                ActivityType = activityType,
                AcquisitionThreshold = threshold,
                Prerequisites = prereqTitles
            };
        }

        private static Dictionary<string, float> MapBonuses(JObject bonusesData)
        {
            var bonuses = new Dictionary<string, float>();
            if (bonusesData == null) return bonuses;

            foreach (var prop in bonusesData.Properties())
            {
                string internalKey = BonusMapping.TryGetValue(prop.Name, out var mapped)
                    ? mapped
                    : prop.Name.ToLower();
                bonuses[internalKey] = prop.Value.Value<float>();
            }

            return bonuses;
        }

        private static (string ActivityType, int Threshold) ParseActivity(JObject activities)
        {
            if (activities == null) return ("general", 0);

            foreach (var prop in activities.Properties())
            {
                string activityType = ActivityMapping.TryGetValue(prop.Name, out var mapped)
                    ? mapped
                    : "general";
                return (activityType, prop.Value.Value<int>());
            }

            return ("general", 0);
        }

        private static string CreateBonusDescription(Dictionary<string, float> bonuses)
        {
            if (bonuses == null || bonuses.Count == 0) return "No bonuses";

            var first = bonuses.First();
            string percent = $"+{(int)(first.Value * 100)}%";
            string readable = string.Join(" ", first.Key.Split('_').Select(
                w => char.ToUpper(w[0]) + w[1..]));
            return $"{percent} {readable}";
        }

        private void CreatePlaceholders()
        {
            var placeholders = new (string Id, string Name, string Activity, int Threshold,
                string BonusKey, float BonusVal)[]
            {
                ("novice_miner", "Novice Miner", "mining", 100, "mining_damage", 0.10f),
                ("novice_lumberjack", "Novice Lumberjack", "forestry", 100, "forestry_damage", 0.10f),
                ("novice_smith", "Novice Smith", "smithing", 50, "smithing_speed", 0.10f),
                ("novice_refiner", "Novice Refiner", "refining", 50, "refining_speed", 0.10f),
                ("novice_alchemist", "Novice Alchemist", "alchemy", 50, "alchemy_speed", 0.10f)
            };

            foreach (var (id, name, activity, threshold, bonusKey, bonusVal) in placeholders)
            {
                var conditions = new List<UnlockCondition>
                {
                    new ActivityCondition { ActivityType = activity, Threshold = threshold }
                };

                Titles[id] = new TitleDefinition
                {
                    TitleId = id,
                    Name = name,
                    Tier = "novice",
                    Category = activity == "mining" || activity == "forestry" ? "gathering" : "crafting",
                    BonusDescription = $"+{(int)(bonusVal * 100)}% {bonusKey.Replace('_', ' ')}",
                    Bonuses = new Dictionary<string, float> { { bonusKey, bonusVal } },
                    Requirements = new UnlockRequirements { Conditions = conditions },
                    ActivityType = activity,
                    AcquisitionThreshold = threshold,
                    AcquisitionMethod = "guaranteed_milestone",
                    GenerationChance = 1.0f,
                    IconPath = $"titles/{id}.png"
                };
            }

            Loaded = true;
            JsonLoader.Log($"Created {Titles.Count} placeholder titles");
        }

        internal static void ResetInstance() => _instance = null;
    }
}
