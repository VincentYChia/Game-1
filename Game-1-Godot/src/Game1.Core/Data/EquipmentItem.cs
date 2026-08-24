using System.Text.Json.Nodes;
using Game1.Core.Crafting;
using Game1.Core.Progression;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/models/equipment.py::EquipmentItem — the typed, MUTABLE
/// runtime item (durability wears, enchantments accumulate). Behaviors
/// pinned by conformance/goldens/db_parity/equipment_items.json:
/// durability-effectiveness curve (never breaks; floor 0.5), repair,
/// enchant family/tier/conflict rules, damage/defense composition,
/// can-equip requirement checks via ICharacterQuery.
/// </summary>
public sealed class EquipmentItem
{
    public required string ItemId { get; init; }
    public required string Name { get; init; }
    public required double Tier { get; init; }
    public required string Rarity { get; init; }
    public required string Slot { get; init; }
    public (int Min, int Max) Damage { get; init; }
    public int Defense { get; init; }
    // Python durability_current is a FLOAT (DEF-scaled fractional losses);
    // double here keeps every read (effectiveness, repair, gates) exact.
    public double DurabilityCurrent { get; set; } = 100;
    public int DurabilityMax { get; init; } = 100;
    public double AttackSpeed { get; init; } = 1.0;
    public double Efficiency { get; set; } = 1.0;
    public double Weight { get; init; } = 1.0;
    public double Range { get; init; } = 1.0;
    public JsonObject Requirements { get; set; } = new();
    public JsonObject Bonuses { get; set; } = new();
    public List<JsonObject> Enchantments { get; } = new();
    public string? IconPath { get; init; }
    public string HandType { get; init; } = "default";
    public string ItemType { get; init; } = "weapon";
    public JsonNode StatMultipliers { get; init; } = new JsonObject();
    public List<string> Tags { get; init; } = new();
    public JsonNode EffectTags { get; init; } = new JsonArray();
    public JsonNode EffectParams { get; init; } = new JsonObject();
    public bool Soulbound { get; init; }

    // equipment.py:49-55 — sacred durability curve: 0 → 0.5, full effectiveness
    // at >= 50%, linear from 1.0 down to 0.75 as pct goes 0.5 → 0
    public double GetEffectiveness()
    {
        if (DurabilityCurrent <= 0)
            return 0.5;
        var durPct = DurabilityCurrent / DurabilityMax;
        return durPct >= 0.5 ? 1.0 : 1.0 - (0.5 - durPct) * 0.5;
    }

    // :57-80
    public double Repair(int? amount = null, double? percent = null)
    {
        var old = DurabilityCurrent;
        if (amount is not null)
            DurabilityCurrent = Math.Min(DurabilityMax, DurabilityCurrent + amount.Value);
        else if (percent is not null)
            DurabilityCurrent = Math.Min(DurabilityMax,
                DurabilityCurrent + (int)(DurabilityMax * percent.Value));
        else
            DurabilityCurrent = DurabilityMax;
        return DurabilityCurrent - old;
    }

    // :90-107
    public string GetRepairUrgency()
    {
        if (DurabilityCurrent >= DurabilityMax) return "none";
        var percent = DurabilityCurrent / DurabilityMax;
        if (percent >= 0.5) return "low";
        if (percent >= 0.2) return "medium";
        return percent > 0 ? "high" : "critical";
    }

    private double EnchantEffectSum(string effectType)
    {
        var sum = 0.0;
        foreach (var ench in Enchantments)
        {
            var effect = J.Obj(ench, "effect");
            if (J.Str(effect, "type") == effectType)
                sum += effect.TryGetPropertyValue("value", out var v)
                    ? J.AsNum(v) ?? 0.0 : 0.0;
        }
        return sum;
    }

    // :109-135 — durability first, then (1 + crafted mult [+ ench mults]) x
    // efficiency for tools; int() truncation at the end
    public (int Min, int Max) GetActualDamage()
    {
        var eff = GetEffectiveness();
        var effectiveMin = Damage.Min * eff;
        var effectiveMax = Damage.Max * eff;

        var damageMult = 1.0 + J.Num(Bonuses, "damage_multiplier", 0);
        if (ItemType == "tool")
            damageMult *= Efficiency;
        damageMult += EnchantEffectSum("damage_multiplier");

        return ((int)(effectiveMin * damageMult), (int)(effectiveMax * damageMult));
    }

    // :137-157
    public int GetDefenseWithEnchantments()
    {
        var effectiveDefense = Defense * GetEffectiveness();
        var defenseMult = 1.0 + J.Num(Bonuses, "defense_multiplier", 0)
                              + EnchantEffectSum("defense_multiplier");
        return (int)(effectiveDefense * defenseMult);
    }

    // :159-187 — stat abbreviation aliases incl. dex→agility
    private static readonly Dictionary<string, string> StatAliases = new()
    {
        ["str"] = "strength", ["strength"] = "strength",
        ["def"] = "defense", ["defense"] = "defense",
        ["vit"] = "vitality", ["vitality"] = "vitality",
        ["lck"] = "luck", ["luck"] = "luck",
        ["agi"] = "agility", ["agility"] = "agility",
        ["dex"] = "agility", ["dexterity"] = "agility",
        ["int"] = "intelligence", ["intelligence"] = "intelligence",
    };

    public (bool Ok, string Reason) CanEquip(ICharacterQuery character)
    {
        if (Requirements.TryGetPropertyValue("level", out var lvl)
            && J.AsNum(lvl) is { } level && character.Level < level)
            return (false, $"Requires level {J.PyNum(level)}");
        if (Requirements.TryGetPropertyValue("stats", out var stats)
            && stats is JsonObject statsObj)
        {
            foreach (var kv in statsObj)
            {
                var statName = StatAliases.GetValueOrDefault(
                    kv.Key.ToLowerInvariant(), kv.Key.ToLowerInvariant());
                var required = J.AsNum(kv.Value) ?? 0;
                if (character.GetStat(statName) < required)
                    return (false, $"Requires {kv.Key.ToUpperInvariant()} {J.PyNum(required)}");
            }
        }
        return (true, "OK");
    }

    // :215-249
    public (bool Ok, string Reason) CanApplyEnchantment(
        IReadOnlyList<string>? tags = null, JsonArray? applicableTo = null)
    {
        var itemType = ResolveItemType();
        if (tags is { Count: > 0 })
            return EnchantingTagProcessor.CanApplyToItem(tags, itemType);
        if (applicableTo is not null)
        {
            var types = applicableTo.OfType<JsonValue>()
                .Select(v => v.TryGetValue<string>(out var s) ? s : "").ToList();
            return types.Contains(itemType)
                ? (true, "OK")
                : (false, $"Cannot apply to {itemType} items");
        }
        return (true, "OK (no applicability rules provided)");
    }

    // :251-310 — dup check, higher-tier-of-family blocks, conflictsWith prune
    // (both directions), then append. NOTE: applying a HIGHER tier does NOT
    // remove the lower tier unless conflictsWith says so — bug-compatible.
    public (bool Ok, string Reason) ApplyEnchantment(
        string enchantmentId, string enchantmentName, JsonObject effect,
        IReadOnlyList<string>? metadataTags = null)
    {
        if (Enchantments.Any(e => J.Str(e, "enchantment_id") == enchantmentId))
            return (false, "This enchantment is already applied");

        static (string Family, int Tier) Info(string id)
        {
            var idx = id.LastIndexOf('_');
            if (idx > 0 && int.TryParse(id[(idx + 1)..], out var tier)
                && id[(idx + 1)..].All(char.IsDigit))
                return (id[..idx], tier);
            return (id, 1);
        }

        var (newFamily, newTier) = Info(enchantmentId);
        foreach (var existing in Enchantments)
        {
            var existingId = J.Str(existing, "enchantment_id");
            var (family, tier) = Info(existingId);
            if (family == newFamily && tier > newTier)
                return (false, $"Cannot apply {enchantmentName} - "
                               + $"{J.Str(existing, "name")} (higher tier) is already applied");
        }

        var conflictsWith = effect.TryGetPropertyValue("conflictsWith", out var cw)
                            && cw is JsonArray cwa
            ? cwa.OfType<JsonValue>()
                 .Select(v => v.TryGetValue<string>(out var s) ? s : "").ToHashSet()
            : new HashSet<string>();
        Enchantments.RemoveAll(e =>
        {
            var eid = J.Str(e, "enchantment_id");
            if (conflictsWith.Contains(eid)) return true;
            var theirConflicts = J.Obj(e, "effect")
                .TryGetPropertyValue("conflictsWith", out var tc) && tc is JsonArray tca
                ? tca.OfType<JsonValue>()
                     .Select(v => v.TryGetValue<string>(out var s) ? s : "")
                : Enumerable.Empty<string>();
            return theirConflicts.Contains(enchantmentId);
        });

        var data = new JsonObject
        {
            ["enchantment_id"] = enchantmentId,
            ["name"] = enchantmentName,
            ["effect"] = effect.DeepClone(),
        };
        if (metadataTags is not null)
        {
            var arr = new JsonArray();
            foreach (var t in metadataTags) arr.Add(t);
            data["metadata_tags"] = arr;
        }
        Enchantments.Add(data);
        return (true, "OK");
    }

    // :312-336
    public string ResolveItemType()
    {
        if (ItemType is "weapon" or "tool" or "armor" or "shield" or "accessory")
            return ItemType == "shield" ? "armor" : ItemType;

        var weaponSlots = new[] { "mainHand", "offHand" };
        var armorSlots = new[] { "helmet", "chestplate", "leggings", "boots", "gauntlets" };
        if (weaponSlots.Contains(Slot) && Damage != (0, 0)) return "weapon";
        if (Slot == "tool") return "tool";
        if (armorSlots.Contains(Slot)) return "armor";
        return weaponSlots.Contains(Slot) ? "tool" : "accessory";
    }

    public JsonObject ToParityNode()
    {
        static JsonArray Strings(IEnumerable<string> xs)
        {
            var a = new JsonArray();
            foreach (var x in xs) a.Add(x);
            return a;
        }
        var enchArr = new JsonArray();
        foreach (var e in Enchantments) enchArr.Add(e.DeepClone());
        return new JsonObject
        {
            ["item_id"] = ItemId,
            ["name"] = Name,
            ["tier"] = Tier,
            ["rarity"] = Rarity,
            ["slot"] = Slot,
            ["damage"] = new JsonArray(Damage.Min, Damage.Max),
            ["defense"] = Defense,
            ["durability_current"] = DurabilityCurrent,
            ["durability_max"] = DurabilityMax,
            ["attack_speed"] = AttackSpeed,
            ["efficiency"] = Efficiency,
            ["weight"] = Weight,
            ["range"] = Range,
            ["requirements"] = Requirements.DeepClone(),
            ["bonuses"] = Bonuses.DeepClone(),
            ["enchantments"] = enchArr,
            ["icon_path"] = IconPath is null ? null : JsonValue.Create(IconPath),
            ["hand_type"] = HandType,
            ["item_type"] = ItemType,
            ["stat_multipliers"] = StatMultipliers.DeepClone(),
            ["tags"] = Strings(Tags),
            ["effect_tags"] = EffectTags.DeepClone(),
            ["effect_params"] = EffectParams.DeepClone(),
            ["soulbound"] = Soulbound,
        };
    }
}
