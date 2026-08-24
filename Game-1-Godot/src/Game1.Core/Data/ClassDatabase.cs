using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/class_db.py. Bonus keys remapped via the exact
/// table (unmapped keys: lower + spaces→underscores). startingSkill.skillId
/// and recommendedStats.primary extracted defensively like the Python.
/// </summary>
public sealed class ClassDatabase
{
    public Dictionary<string, ClassDefinition> Classes { get; } = new();
    public bool Loaded { get; private set; }

    // class_db.py:58-74
    private static readonly Dictionary<string, string> BonusKeyMap = new()
    {
        ["baseHP"] = "max_health", ["baseMana"] = "max_mana",
        ["meleeDamage"] = "melee_damage", ["inventorySlots"] = "inventory_slots",
        ["carryCapacity"] = "carry_capacity", ["movementSpeed"] = "movement_speed",
        ["critChance"] = "crit_chance", ["forestryBonus"] = "forestry_damage",
        ["recipeDiscovery"] = "recipe_discovery", ["skillExpGain"] = "skill_exp",
        ["allCraftingTime"] = "crafting_speed", ["firstTryBonus"] = "first_try_bonus",
        ["itemDurability"] = "durability_bonus", ["rareDropRate"] = "rare_drops",
        ["resourceQuality"] = "resource_quality", ["allGathering"] = "gathering_bonus",
        ["allCrafting"] = "crafting_bonus", ["defense"] = "defense_bonus",
        ["miningBonus"] = "mining_damage", ["attackSpeed"] = "attack_speed",
    };

    // class_db.py:21-56
    public void LoadFromFile(string filepath)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        foreach (var node in J.Arr(data, "classes"))
        {
            if (node is not JsonObject c) continue;

            var bonuses = new JsonObject();
            foreach (var kv in J.Obj(c, "startingBonuses"))
            {
                var key = BonusKeyMap.GetValueOrDefault(
                    kv.Key, kv.Key.ToLowerInvariant().Replace(' ', '_'));
                bonuses[key] = kv.Value?.DeepClone();
            }

            var startingSkill = "";
            if (c.TryGetPropertyValue("startingSkill", out var skillNode)
                && skillNode is JsonObject skillObj)
                startingSkill = J.Str(skillObj, "skillId");

            JsonNode recStats = new JsonArray();
            if (c.TryGetPropertyValue("recommendedStats", out var recNode)
                && recNode is JsonObject recObj)
                recStats = J.Node(recObj, "primary", () => new JsonArray());

            var def = new ClassDefinition
            {
                ClassId = J.Str(c, "classId"),
                Name = J.Str(c, "name"),
                Description = J.Str(c, "description"),
                Bonuses = bonuses,
                StartingSkill = startingSkill,
                RecommendedStats = recStats,
                Tags = J.Node(c, "tags", () => new JsonArray()),
                PreferredDamageTypes = J.Node(c, "preferredDamageTypes", () => new JsonArray()),
                PreferredArmorType = J.Str(c, "preferredArmorType"),
            };
            Classes[def.ClassId] = def;
        }
        Loaded = true;
    }
}
