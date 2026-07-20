using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/title_db.py. Sacred glob progression/titles-*.JSON
/// (skip names containing "generated"), then titles-generated-*.JSON overlay.
/// Bonus keys remapped camelCase→snake_case via the exact table; legacy
/// activity/threshold extracted from the FIRST key of prerequisites.activities
/// (JSON document order). The UnlockRequirements condition graph is kept raw
/// (Phase-2 typing).
/// </summary>
public sealed class TitleDatabase
{
    public Dictionary<string, TitleDefinition> Titles { get; } = new();

    /// <summary>Insertion order of Titles (Python dict order) — load-bearing
    /// for check_for_title's award order and rng draw sequence.</summary>
    public List<string> TitleOrder { get; } = new();

    public bool Loaded { get; private set; }

    public const string SacredDir = "progression";
    public const string SacredGlob = "titles-*.JSON";
    public const string GeneratedGlob = "titles-generated-*.JSON";

    // title_db.py:186-208
    private static readonly Dictionary<string, string> BonusKeyMap = new()
    {
        ["miningDamage"] = "mining_damage", ["miningSpeed"] = "mining_speed",
        ["forestryDamage"] = "forestry_damage", ["forestrySpeed"] = "forestry_speed",
        ["smithingTime"] = "smithing_speed", ["smithingQuality"] = "smithing_quality",
        ["refiningPrecision"] = "refining_speed", ["meleeDamage"] = "melee_damage",
        ["criticalChance"] = "crit_chance", ["attackSpeed"] = "attack_speed",
        ["firstTryBonus"] = "first_try_bonus", ["rareOreChance"] = "rare_ore_chance",
        ["rareWoodChance"] = "rare_wood_chance", ["fireOreChance"] = "fire_ore_chance",
        ["alloyQuality"] = "alloy_quality", ["materialYield"] = "material_yield",
        ["combatSkillExp"] = "combat_skill_exp", ["counterChance"] = "counter_chance",
        ["durabilityBonus"] = "durability_bonus", ["legendaryChance"] = "legendary_chance",
        ["dragonDamage"] = "dragon_damage", ["fireResistance"] = "fire_resistance",
        ["legendaryDropRate"] = "legendary_drop_rate", ["luckStat"] = "luck_stat",
        ["rareDropRate"] = "rare_drop_rate",
        ["fishingSpeed"] = "fishing_speed", ["fishingAccuracy"] = "fishing_accuracy",
        ["rareFishChance"] = "rare_fish_chance", ["fishingYield"] = "fishing_yield",
    };

    // title_db.py:171-184
    private static readonly Dictionary<string, string> ActivityMap = new()
    {
        ["oresMined"] = "mining", ["treesChopped"] = "forestry",
        ["itemsSmithed"] = "smithing", ["materialsRefined"] = "refining",
        ["potionsBrewed"] = "alchemy", ["itemsEnchanted"] = "enchanting",
        ["devicesCreated"] = "engineering", ["enemiesDefeated"] = "combat",
        ["bossesDefeated"] = "combat", ["areasExplored"] = "exploration",
    };

    public void LoadFromFiles(string contentRoot)
    {
        Titles.Clear();
        var dir = Path.Combine(contentRoot, SacredDir);
        foreach (var path in J.GlobSorted(dir, SacredGlob))
        {
            if (Path.GetFileName(path).ToLowerInvariant().Contains("generated"))
                continue;
            LoadFromFile(path);
        }
        foreach (var path in J.GlobSorted(dir, GeneratedGlob))
            LoadFromFile(path);
        Loaded = true;
    }

    // title_db.py:110-169
    public void LoadFromFile(string filepath)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        foreach (var node in J.Arr(data, "titles"))
        {
            if (node is not JsonObject t) continue;
            var title = ParseTitle(t);
            if (!Titles.ContainsKey(title.TitleId))
                TitleOrder.Add(title.TitleId);   // dict overwrite keeps slot
            Titles[title.TitleId] = title;
        }
        Loaded = true;
    }

    private static TitleDefinition ParseTitle(JsonObject t)
    {
        var bonuses = MapBonuses(J.Obj(t, "bonuses"));

        var titleId = J.Str(t, "titleId");
        var iconPath = J.Str(t, "iconPath", "");
        if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(titleId))
            iconPath = $"titles/{titleId}.png";

        var prereqs = J.Obj(t, "prerequisites");
        var activities = J.Obj(prereqs, "activities");
        var (activityType, threshold) = ParseActivity(activities);

        return new TitleDefinition
        {
            TitleId = titleId,
            Name = J.Str(t, "name"),
            Tier = J.Str(t, "difficultyTier", "novice"),
            Category = J.Str(t, "titleType", "general"),
            BonusDescription = CreateBonusDescription(bonuses),
            Bonuses = bonuses,
            RequirementsRaw = prereqs,
            Hidden = J.Bool(t, "isHidden", false),
            AcquisitionMethod = J.Str(t, "acquisitionMethod", "guaranteed_milestone"),
            GenerationChance = J.Node(t, "generationChance", () => JsonValue.Create(1.0)!),
            IconPath = string.IsNullOrEmpty(iconPath) ? null : iconPath,
            ActivityType = activityType,
            AcquisitionThreshold = threshold,
            Prerequisites = J.Node(prereqs, "requiredTitles", () => new JsonArray()),
        };
    }

    private static (string, JsonNode) ParseActivity(JsonObject activities)
    {
        foreach (var kv in activities)  // first key wins, document order
        {
            var activityType = ActivityMap.GetValueOrDefault(kv.Key, "general");
            return (activityType, kv.Value?.DeepClone() ?? JsonValue.Create(0)!);
        }
        return ("general", JsonValue.Create(0)!);
    }

    private static JsonObject MapBonuses(JsonObject raw)
    {
        var mapped = new JsonObject();
        foreach (var kv in raw)
        {
            var key = BonusKeyMap.GetValueOrDefault(kv.Key, kv.Key.ToLowerInvariant());
            mapped[key] = kv.Value?.DeepClone();
        }
        return mapped;
    }

    // title_db.py:210-217 — first bonus only; int() truncation; snake→Title Case
    private static string CreateBonusDescription(JsonObject bonuses)
    {
        foreach (var kv in bonuses)
        {
            var value = kv.Value is JsonValue v && v.TryGetValue<double>(out var d) ? d : 0.0;
            var percent = $"+{(int)(value * 100)}%";
            var readable = string.Join(" ",
                kv.Key.Replace('_', ' ').Split(' ').Select(
                    w => w.Length == 0 ? w : char.ToUpperInvariant(w[0]) + w[1..].ToLowerInvariant()));
            return $"{percent} {readable}";
        }
        return "No bonuses";
    }
}
