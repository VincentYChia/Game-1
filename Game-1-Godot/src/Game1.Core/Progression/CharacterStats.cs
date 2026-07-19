using System.Text.Json.Nodes;
using Game1.Core.Data;

namespace Game1.Core.Progression;

/// <summary>
/// Port of entities/components/stats.py — the six core stats with
/// JSON-driven scaling (§15 trap 6: values load from
/// Definitions.JSON/stats-calculations.JSON; hardcoded fallbacks preserved
/// for when the JSON is missing/malformed, byte-matching Python).
/// </summary>
public sealed class StatScalingConfig
{
    public Dictionary<string, double> Scaling = new()
    {
        ["strength"] = 0.05, ["defense"] = 0.02, ["vitality"] = 0.01,
        ["luck"] = 0.02, ["agility"] = 0.05, ["intelligence"] = 0.02,
    };

    public Dictionary<string, Dictionary<string, double>> Flat = new()
    {
        ["strength"] = new() { ["carry_capacity"] = 10.0, ["inventory_slots"] = 10.0 },
        ["vitality"] = new() { ["max_health"] = 15.0 },
        ["intelligence"] = new() { ["mana"] = 20.0 },
    };

    /// <summary>stats.py _load_stat_config — any failure keeps fallbacks.</summary>
    public static StatScalingConfig Load(string contentRoot)
    {
        var cfg = new StatScalingConfig();
        try
        {
            var path = Path.Combine(contentRoot, "Definitions.JSON", "stats-calculations.JSON");
            if (!File.Exists(path)) return cfg;
            var data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
            var mods = data["characterStatModifiers"] as JsonObject ?? new JsonObject();

            void Scale(string stat, string key)
            {
                if (mods[stat] is JsonObject m && m.ContainsKey(key))
                    cfg.Scaling[stat] = J.AsNum(m[key]) ?? cfg.Scaling[stat];
            }

            Scale("strength", "meleeDamagePerPoint");
            Scale("defense", "damageReductionPerPoint");
            Scale("vitality", "healthRegenPerPoint");
            Scale("luck", "critChancePerPoint");
            Scale("agility", "forestryDamagePerPoint");
            Scale("intelligence", "reductionPerPoint");

            if (mods["strength"] is JsonObject str && str.ContainsKey("inventorySlotsPerPoint"))
            {
                var slots = J.AsNum(str["inventorySlotsPerPoint"]) ?? 10.0;
                cfg.Flat["strength"]["carry_capacity"] = slots;
                cfg.Flat["strength"]["inventory_slots"] = slots;
            }
            if (mods["vitality"] is JsonObject vit && vit.ContainsKey("maxHPPerPoint"))
                cfg.Flat["vitality"]["max_health"] = J.AsNum(vit["maxHPPerPoint"]) ?? 15.0;
            if (mods["intelligence"] is JsonObject intel && intel.ContainsKey("maxManaPerPoint"))
                cfg.Flat["intelligence"]["mana"] = J.AsNum(intel["maxManaPerPoint"]) ?? 20.0;
        }
        catch
        {
            return new StatScalingConfig();
        }
        return cfg;
    }
}

public sealed class CharacterStats
{
    public int Strength;
    public int Defense;
    public int Vitality;
    public int Luck;
    public int Agility;
    public int Intelligence;

    private readonly StatScalingConfig _config;

    public CharacterStats(StatScalingConfig config)
    {
        _config = config;
    }

    private int Value(string statName) => statName.ToLowerInvariant() switch
    {
        "strength" => Strength,
        "defense" => Defense,
        "vitality" => Vitality,
        "luck" => Luck,
        "agility" => Agility,
        "intelligence" => Intelligence,
        _ => 0,
    };

    public double GetBonus(string statName) =>
        Value(statName) * _config.Scaling.GetValueOrDefault(statName.ToLowerInvariant(), 0.05);

    public double GetFlatBonus(string statName, string bonusType)
    {
        var bonuses = _config.Flat.GetValueOrDefault(statName.ToLowerInvariant());
        return Value(statName) * (bonuses?.GetValueOrDefault(bonusType, 0.0) ?? 0.0);
    }

    public double GetDurabilityLossMultiplier() =>
        Math.Max(0.1, 1.0 - Defense * 0.02);

    public double GetDurabilityBonusMultiplier() => 1.0 + Vitality * 0.01;

    public double GetCarryCapacityMultiplier() => 1.0 + Strength * 0.02;

    /// <summary>stats.py get_effective_luck — rare-drop bonuses convert to
    /// equivalent luck at 2% per point.</summary>
    public double GetEffectiveLuck(double titleBonus = 0.0, double skillBonus = 0.0,
                                   double rareDropBonus = 0.0)
    {
        var luckFromRareDrops = rareDropBonus > 0 ? rareDropBonus / 0.02 : 0;
        return Luck + titleBonus + skillBonus + luckFromRareDrops;
    }
}
