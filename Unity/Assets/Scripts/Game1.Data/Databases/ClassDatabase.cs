// Game1.Data.Databases.ClassDatabase
// Migrated from: data/databases/class_db.py (109 lines)
// Phase: 2 - Data Layer
// Loads from progression/classes-1.JSON.
// CRITICAL: Bonus key mapping (20 entries) must be preserved exactly.

using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for character class definitions.
    /// 6 classes with tag-driven bonuses and identity.
    /// </summary>
    public class ClassDatabase
    {
        private static ClassDatabase _instance;
        private static readonly object _lock = new object();

        public Dictionary<string, ClassDefinition> Classes { get; private set; }
        public bool Loaded { get; private set; }

        // Bonus key mapping: JSON camelCase -> internal snake_case
        private static readonly Dictionary<string, string> BonusMapping = new()
        {
            { "baseHP", "max_health" },
            { "baseMana", "max_mana" },
            { "meleeDamage", "melee_damage" },
            { "inventorySlots", "inventory_slots" },
            { "carryCapacity", "carry_capacity" },
            { "movementSpeed", "movement_speed" },
            { "critChance", "crit_chance" },
            { "forestryBonus", "forestry_damage" },
            { "recipeDiscovery", "recipe_discovery" },
            { "skillExpGain", "skill_exp" },
            { "allCraftingTime", "crafting_speed" },
            { "firstTryBonus", "first_try_bonus" },
            { "itemDurability", "durability_bonus" },
            { "rareDropRate", "rare_drops" },
            { "resourceQuality", "resource_quality" },
            { "allGathering", "gathering_bonus" },
            { "allCrafting", "crafting_bonus" },
            { "defense", "defense_bonus" },
            { "miningBonus", "mining_damage" },
            { "attackSpeed", "attack_speed" }
        };

        public static ClassDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new ClassDatabase();
                }
            }
            return _instance;
        }

        private ClassDatabase()
        {
            Classes = new Dictionary<string, ClassDefinition>();
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

                var classesArr = data["classes"] as JArray;
                if (classesArr == null)
                {
                    CreatePlaceholders();
                    return false;
                }

                foreach (JObject classData in classesArr)
                {
                    var startingBonuses = classData["startingBonuses"] as JObject;
                    var bonuses = MapBonuses(startingBonuses);

                    // startingSkill can be dict or string
                    string startingSkill = "";
                    var skillData = classData["startingSkill"];
                    if (skillData is JObject skillObj)
                        startingSkill = skillObj.Value<string>("skillId") ?? "";
                    else if (skillData != null && skillData.Type == JTokenType.String)
                        startingSkill = skillData.Value<string>() ?? "";

                    // recommendedStats can be dict or list
                    var recStats = new List<string>();
                    var recStatsData = classData["recommendedStats"];
                    if (recStatsData is JObject recObj)
                    {
                        var primary = recObj["primary"] as JArray;
                        if (primary != null)
                        {
                            foreach (var s in primary)
                                recStats.Add(s.Value<string>());
                        }
                    }
                    else if (recStatsData is JArray recArr)
                    {
                        foreach (var s in recArr)
                            recStats.Add(s.Value<string>());
                    }

                    var tags = new List<string>();
                    if (classData["tags"] is JArray tagsArr)
                        foreach (var t in tagsArr) tags.Add(t.Value<string>());

                    var prefDmgTypes = new List<string>();
                    if (classData["preferredDamageTypes"] is JArray dmgArr)
                        foreach (var d in dmgArr) prefDmgTypes.Add(d.Value<string>());

                    var clsDef = new ClassDefinition
                    {
                        ClassId = classData.Value<string>("classId") ?? "",
                        Name = classData.Value<string>("name") ?? "",
                        Description = classData.Value<string>("description") ?? "",
                        Bonuses = bonuses,
                        StartingSkill = startingSkill,
                        RecommendedStats = recStats,
                        Tags = tags,
                        PreferredDamageTypes = prefDmgTypes,
                        PreferredArmorType = classData.Value<string>("preferredArmorType") ?? ""
                    };

                    Classes[clsDef.ClassId] = clsDef;
                }

                Loaded = true;
                JsonLoader.Log($"Loaded {Classes.Count} classes");
                return true;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading classes: {ex.Message}");
                CreatePlaceholders();
                return false;
            }
        }

        private Dictionary<string, float> MapBonuses(JObject startingBonuses)
        {
            var bonuses = new Dictionary<string, float>();
            if (startingBonuses == null) return bonuses;

            foreach (var prop in startingBonuses.Properties())
            {
                string internalKey = BonusMapping.TryGetValue(prop.Name, out var mapped)
                    ? mapped
                    : prop.Name.ToLower().Replace(" ", "_");
                bonuses[internalKey] = prop.Value.Value<float>();
            }

            return bonuses;
        }

        private void CreatePlaceholders()
        {
            var classesData = new (string Id, string Name, string Desc, Dictionary<string, float> Bonuses,
                string Skill, List<string> Stats, List<string> Tags, List<string> DmgTypes, string Armor)[]
            {
                ("warrior", "Warrior", "A melee fighter with high health and damage",
                    new() { { "max_health", 30 }, { "melee_damage", 0.10f }, { "carry_capacity", 20 } },
                    "battle_rage", new() { "STR", "VIT", "DEF" },
                    new() { "warrior", "melee", "physical", "tanky" },
                    new() { "physical", "slashing" }, "heavy"),
                ("ranger", "Ranger", "A nimble hunter specializing in speed and precision",
                    new() { { "movement_speed", 0.15f }, { "crit_chance", 0.10f }, { "forestry_damage", 0.10f } },
                    "forestry_frenzy", new() { "AGI", "LCK", "VIT" },
                    new() { "ranger", "ranged", "agile", "nature" },
                    new() { "physical", "piercing" }, "light"),
                ("scholar", "Scholar", "A learned mage with vast knowledge",
                    new() { { "max_mana", 100 }, { "recipe_discovery", 0.10f }, { "skill_exp", 0.05f } },
                    "alchemist_touch", new() { "INT", "LCK", "AGI" },
                    new() { "scholar", "magic", "alchemy", "arcane" },
                    new() { "arcane", "fire", "frost" }, "robes"),
                ("artisan", "Artisan", "A master craftsman creating quality goods",
                    new() { { "crafting_speed", 0.10f }, { "first_try_bonus", 0.10f }, { "durability_bonus", 0.05f } },
                    "smithing_focus", new() { "AGI", "INT", "LCK" },
                    new() { "artisan", "crafting", "smithing", "utility" },
                    new() { "physical" }, "medium"),
                ("scavenger", "Scavenger", "A treasure hunter with keen eyes",
                    new() { { "rare_drops", 0.20f }, { "resource_quality", 0.10f }, { "carry_capacity", 100 } },
                    "treasure_luck", new() { "LCK", "STR", "VIT" },
                    new() { "scavenger", "luck", "gathering", "treasure" },
                    new() { "physical" }, "light"),
                ("adventurer", "Adventurer", "A balanced jack-of-all-trades",
                    new() { { "gathering_bonus", 0.05f }, { "crafting_bonus", 0.05f }, { "max_health", 50 }, { "max_mana", 50 } },
                    "", new() { "Balanced" },
                    new() { "adventurer", "balanced", "versatile", "generalist" },
                    new() { "physical", "arcane" }, "medium")
            };

            foreach (var (id, name, desc, bonuses, skill, stats, tags, dmgTypes, armor) in classesData)
            {
                Classes[id] = new ClassDefinition
                {
                    ClassId = id,
                    Name = name,
                    Description = desc,
                    Bonuses = bonuses,
                    StartingSkill = skill,
                    RecommendedStats = stats,
                    Tags = tags,
                    PreferredDamageTypes = dmgTypes,
                    PreferredArmorType = armor
                };
            }

            Loaded = true;
            JsonLoader.Log($"Created {Classes.Count} placeholder classes");
        }

        internal static void ResetInstance() => _instance = null;
    }
}
