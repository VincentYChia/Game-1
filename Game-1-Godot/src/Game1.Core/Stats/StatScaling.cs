using System.Text.Json;
using Game1.Core.Content;

namespace Game1.Core.Stats;

/// <summary>
/// Port of entities/components/stats.py — per-stat scaling loads from
/// Definitions.JSON/stats-calculations.JSON (characterStatModifiers.*) with
/// the same hardcoded fallbacks when the JSON is missing or malformed.
/// Pinned by conformance/goldens/stat_scaling.json.
/// </summary>
public sealed class StatScaling
{
    private static readonly IReadOnlyDictionary<string, double> FallbackScaling =
        new Dictionary<string, double>
        {
            ["strength"] = 0.05, ["defense"] = 0.02, ["vitality"] = 0.01,
            ["luck"] = 0.02, ["agility"] = 0.05, ["intelligence"] = 0.02,
        };

    private static readonly IReadOnlyDictionary<string, IReadOnlyDictionary<string, double>> FallbackFlat =
        new Dictionary<string, IReadOnlyDictionary<string, double>>
        {
            ["strength"] = new Dictionary<string, double>
                { ["carry_capacity"] = 10.0, ["inventory_slots"] = 10.0 },
            ["vitality"] = new Dictionary<string, double> { ["max_health"] = 15.0 },
            ["intelligence"] = new Dictionary<string, double> { ["mana"] = 20.0 },
        };

    public IReadOnlyDictionary<string, double> Scaling { get; }
    public IReadOnlyDictionary<string, IReadOnlyDictionary<string, double>> FlatBonuses { get; }

    private static readonly Lazy<StatScaling> Loaded = new(() => LoadFromContent());

    /// <summary>Instance resolved from content JSON (or fallbacks), like the module-level load in stats.py.</summary>
    public static StatScaling Default => Loaded.Value;

    private StatScaling(
        IReadOnlyDictionary<string, double> scaling,
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, double>> flat)
    {
        Scaling = scaling;
        FlatBonuses = flat;
    }

    /// <summary>stats.py::_load_stat_config — any failure returns the fallbacks.</summary>
    public static StatScaling LoadFromContent(string? explicitPath = null)
    {
        var scaling = new Dictionary<string, double>(FallbackScaling);
        var flat = FallbackFlat.ToDictionary(
            kv => kv.Key,
            kv => (IReadOnlyDictionary<string, double>)new Dictionary<string, double>(kv.Value));
        try
        {
            var path = explicitPath
                       ?? ContentPaths.TryGetResource("Definitions.JSON/stats-calculations.JSON");
            if (path is null || !File.Exists(path))
                return new StatScaling(scaling, flat);

            using var doc = JsonDocument.Parse(File.ReadAllText(path));
            if (!doc.RootElement.TryGetProperty("characterStatModifiers", out var mods)
                || mods.ValueKind != JsonValueKind.Object)
                return new StatScaling(scaling, flat);

            void ReadScaling(string stat, string key)
            {
                if (mods.TryGetProperty(stat, out var s)
                    && s.TryGetProperty(key, out var v) && v.TryGetDouble(out var d))
                    scaling[stat] = d;
            }

            ReadScaling("strength", "meleeDamagePerPoint");
            ReadScaling("defense", "damageReductionPerPoint");
            ReadScaling("vitality", "healthRegenPerPoint");
            ReadScaling("luck", "critChancePerPoint");
            ReadScaling("agility", "forestryDamagePerPoint");
            ReadScaling("intelligence", "reductionPerPoint");

            if (mods.TryGetProperty("strength", out var str)
                && str.TryGetProperty("inventorySlotsPerPoint", out var slots)
                && slots.TryGetDouble(out var slotsD))
                flat["strength"] = new Dictionary<string, double>
                    { ["carry_capacity"] = slotsD, ["inventory_slots"] = slotsD };

            if (mods.TryGetProperty("vitality", out var vit)
                && vit.TryGetProperty("maxHPPerPoint", out var hp)
                && hp.TryGetDouble(out var hpD))
                flat["vitality"] = new Dictionary<string, double> { ["max_health"] = hpD };

            if (mods.TryGetProperty("intelligence", out var intel)
                && intel.TryGetProperty("maxManaPerPoint", out var mana)
                && mana.TryGetDouble(out var manaD))
                flat["intelligence"] = new Dictionary<string, double> { ["mana"] = manaD };
        }
        catch
        {
            return new StatScaling(
                new Dictionary<string, double>(FallbackScaling),
                FallbackFlat.ToDictionary(
                    kv => kv.Key,
                    kv => (IReadOnlyDictionary<string, double>)new Dictionary<string, double>(kv.Value)));
        }
        return new StatScaling(scaling, flat);
    }

    // stats.py:111-113 — unknown stat name scales at the 0.05 default.
    public double GetBonus(string statName, int value) =>
        value * Scaling.GetValueOrDefault(statName.ToLowerInvariant(), 0.05);

    // stats.py:115-118
    public double GetFlatBonus(string statName, string bonusType, int value) =>
        FlatBonuses.TryGetValue(statName.ToLowerInvariant(), out var bonuses)
            ? value * bonuses.GetValueOrDefault(bonusType, 0.0)
            : 0.0;

    // stats.py:120-130 — DEF reduces durability loss 2%/pt, floor 10%.
    public static double DurabilityLossMultiplier(int defense) =>
        Math.Max(0.1, 1.0 - defense * 0.02);

    // stats.py:132-142 — VIT +1%/pt max durability.
    public static double DurabilityBonusMultiplier(int vitality) =>
        1.0 + vitality * 0.01;

    // stats.py:144-154 — STR +2%/pt carry capacity.
    public static double CarryCapacityMultiplier(int strength) =>
        1.0 + strength * 0.02;

    // stats.py:156-178 — rare-drop bonus converts to luck equivalent at 2%/pt.
    public static double EffectiveLuck(
        int luck, double titleBonus = 0.0, double skillBonus = 0.0, double rareDropBonus = 0.0)
    {
        var luckFromRareDrops = rareDropBonus > 0 ? rareDropBonus / 0.02 : 0.0;
        return luck + titleBonus + skillBonus + luckFromRareDrops;
    }
}
