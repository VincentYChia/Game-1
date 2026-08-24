using System.Text.Json.Nodes;
using Game1.Core.Crafting;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/equipment_db.py at the LOADER level: stores raw
/// JSON dicts keyed by itemId, filtering to category == "equipment" only.
/// EquipmentItem materialization (create_equipment_from_id — weapon/armor/
/// durability formulas + SmithingTagProcessor slot inference) is Phase 2.
/// </summary>
public sealed class EquipmentDatabase
{
    public Dictionary<string, JsonObject> Items { get; } = new();
    public bool Loaded { get; private set; }

    // equipment_db.py:22-73 — all list sections except 'metadata';
    // itemId non-empty AND category == 'equipment'; raw dict stored (overwrite).
    public void LoadFromFile(string filepath)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        var count = 0;
        foreach (var kv in data)
        {
            if (kv.Key == "metadata" || kv.Value is not JsonArray items) continue;
            foreach (var node in items)
            {
                if (node is not JsonObject item) continue;
                var itemId = J.Str(item, "itemId");
                var category = J.Str(item, "category");
                if (!string.IsNullOrEmpty(itemId) && category == "equipment")
                {
                    Items[itemId] = (JsonObject)item.DeepClone();
                    count++;
                }
            }
        }
        if (count > 0) Loaded = true;
    }

    public bool IsEquipment(string itemId) => Items.ContainsKey(itemId);

    // ── Materialization (equipment_db.py:136-389) ────────────────────────

    private static readonly Dictionary<int, double> TierMults = new()
    { [1] = 1.0, [2] = 2.0, [3] = 4.0, [4] = 8.0 };

    // equipment_db.py:225 — NOTE: 'shield' is NOT in this set; shields fall
    // through to the generic tag-based slot branch
    private static readonly HashSet<string> WeaponTypes = new()
    { "weapon", "sword", "axe", "mace", "dagger", "spear", "bow", "staff" };

    private static readonly HashSet<string> ArmorTypes = new()
    { "armor", "helmet", "chestplate", "leggings", "boots", "gauntlets" };

    private static readonly Dictionary<string, string> SlotMapping = new()
    {
        ["head"] = "helmet", ["chest"] = "chestplate", ["legs"] = "leggings",
        ["feet"] = "boots", ["hands"] = "gauntlets",
        ["mainHand"] = "mainHand", ["offHand"] = "offHand",
        ["helmet"] = "helmet", ["chestplate"] = "chestplate",
        ["leggings"] = "leggings", ["boots"] = "boots",
        ["gauntlets"] = "gauntlets", ["accessory"] = "accessory",
    };

    // equipment_db.py:136-167 — base 10 x tier x type x subtype x item, ±15%
    private static (int, int) CalculateWeaponDamage(
        int tier, string itemType, string subtype, JsonObject statMultipliers)
    {
        var typeMults = new Dictionary<string, double>
        {
            ["sword"] = 1.0, ["axe"] = 1.1, ["spear"] = 1.05, ["mace"] = 1.15,
            ["dagger"] = 0.8, ["bow"] = 1.0, ["staff"] = 0.9, ["shield"] = 1.0,
        };
        var subtypeMults = new Dictionary<string, double>
        {
            ["shortsword"] = 0.9, ["longsword"] = 1.0, ["greatsword"] = 1.4,
            ["dagger"] = 1.0, ["spear"] = 1.0, ["pike"] = 1.2, ["halberd"] = 1.4,
            ["mace"] = 1.0, ["warhammer"] = 1.3, ["maul"] = 1.5,
        };
        var baseDamage = 10.0 * TierMults.GetValueOrDefault(tier, 1.0)
                         * typeMults.GetValueOrDefault(itemType, 1.0)
                         * subtypeMults.GetValueOrDefault(subtype, 1.0)
                         * J.Num(statMultipliers, "damage", 1.0);
        return ((int)(baseDamage * 0.85), (int)(baseDamage * 1.15));
    }

    // :169-187 — base 10 x tier x slot x item
    private static int CalculateArmorDefense(int tier, string slot, JsonObject statMultipliers)
    {
        var slotMults = new Dictionary<string, double>
        {
            ["helmet"] = 0.8, ["chestplate"] = 1.5, ["leggings"] = 1.2,
            ["boots"] = 0.7, ["gauntlets"] = 0.6,
        };
        return (int)(10.0 * TierMults.GetValueOrDefault(tier, 1.0)
                     * slotMults.GetValueOrDefault(slot, 1.0)
                     * J.Num(statMultipliers, "defense", 1.0));
    }

    // :189-209 — base 250 x tier x item (T1=250 ... T4=2000)
    private static int CalculateDurability(int tier, JsonObject statMultipliers) =>
        (int)(250.0 * TierMults.GetValueOrDefault(tier, 1.0)
              * J.Num(statMultipliers, "durability", 1.0));

    // :211-389
    public EquipmentItem? CreateEquipmentFromId(string itemId)
    {
        if (!Items.TryGetValue(itemId, out var data))
            return null;

        var tier = J.Int(data, "tier", 1);
        var itemType = J.Str(data, "type");
        var subtype = J.Str(data, "subtype");
        var statMultipliers = J.Obj(data, "statMultipliers");
        var stats = J.Obj(data, "stats");

        // Damage: formula for weapon types; legacy stats fallback otherwise
        var damage = (0, 0);
        if (WeaponTypes.Contains(itemType))
            damage = CalculateWeaponDamage(tier, itemType, subtype, statMultipliers);
        else if (stats.ContainsKey("damage"))
        {
            if (stats["damage"] is JsonArray da && da.Count >= 2)
                damage = ((int)da[0]!.GetValue<double>(), (int)da[1]!.GetValue<double>());
            else if (stats["damage"] is JsonValue dv && dv.TryGetValue<double>(out var d))
                damage = ((int)d, (int)d);
        }

        var metadata = J.Obj(data, "metadata");
        var tags = new List<string>();
        if (metadata.TryGetPropertyValue("tags", out var tg) && tg is JsonArray tga)
            foreach (var t in tga)
                if (t is JsonValue tv && tv.TryGetValue<string>(out var ts))
                    tags.Add(ts);

        // Slot resolution priority (equipment_db.py:247-301)
        string? mappedSlot;
        if (WeaponTypes.Contains(itemType))
        {
            var jsonSlot = J.Str(data, "slot", "mainHand");
            mappedSlot = SlotMapping.GetValueOrDefault(jsonSlot, jsonSlot);
        }
        else if (itemType == "tool")
        {
            mappedSlot = subtype is "axe" or "pickaxe" ? subtype : "mainHand";
        }
        else if (ArmorTypes.Contains(itemType))
        {
            mappedSlot = SmithingTagProcessor.GetEquipmentSlot(tags);
            if (mappedSlot is null)
            {
                var jsonSlot = J.Str(data, "slot", "helmet");
                mappedSlot = SlotMapping.GetValueOrDefault(jsonSlot, jsonSlot);
            }
        }
        else
        {
            mappedSlot = SmithingTagProcessor.GetEquipmentSlot(tags);
            if (mappedSlot is null)
            {
                var jsonSlot = J.Str(data, "slot", "mainHand");
                mappedSlot = SlotMapping.GetValueOrDefault(jsonSlot, jsonSlot);
            }
        }

        var defense = 0;
        if (ArmorTypes.Contains(itemType))
            defense = CalculateArmorDefense(tier, mappedSlot, statMultipliers);
        else if (stats.TryGetPropertyValue("defense", out var df)
                 && df is JsonValue dfv && dfv.TryGetValue<double>(out var dfd))
            defense = (int)dfd;

        // Durability: explicit stats value wins; else tier formula
        int durMax;
        if (stats.TryGetPropertyValue("durability", out var dur) && dur is not null)
        {
            if (dur is JsonArray durArr)
                durMax = (int)(durArr.Count > 1 ? durArr[1]! : durArr[0]!).GetValue<double>();
            else
                durMax = (int)dur.GetValue<double>();
        }
        else
        {
            durMax = CalculateDurability(tier, statMultipliers);
        }

        // Icon autogen (:321-337)
        var iconPath = J.Str(data, "iconPath", "");
        if (string.IsNullOrEmpty(iconPath) && itemId.Length > 0)
        {
            string subdir;
            if (mappedSlot is "mainHand" or "offHand" && damage != (0, 0))
                subdir = "weapons";
            else if (mappedSlot is "helmet" or "chestplate" or "leggings" or "boots" or "gauntlets")
                subdir = "armor";
            else if (mappedSlot is "tool" or "axe" or "pickaxe" || itemType == "tool")
                subdir = "tools";
            else if (mappedSlot == "accessory" || itemType == "accessory")
                subdir = "accessories";
            else if (itemType == "station")
                subdir = "stations";
            else
                subdir = "weapons";
            iconPath = $"{subdir}/{itemId}.png";
        }

        // Hand type from tags (:339-347)
        var handType = "default";
        if (tags.Contains("1H")) handType = "1H";
        else if (tags.Contains("2H")) handType = "2H";
        else if (tags.Contains("versatile")) handType = "versatile";

        // Parsed item type (:349-360)
        var parsedItemType = itemType switch
        {
            "shield" => "shield", "tool" => "tool", "armor" => "armor",
            "accessory" => "accessory", "station" => "station", _ => "weapon",
        };

        // Effect tags/params: snake_case wins over camelCase (:362-365)
        var effectTags = J.NodeOrNull(data, "effect_tags")
                         ?? J.Node(data, "effectTags", () => new JsonArray());
        var effectParams = J.NodeOrNull(data, "effect_params")
                           ?? J.Node(data, "effectParams", () => new JsonObject());

        return new EquipmentItem
        {
            ItemId = itemId,
            Name = J.Str(data, "name", itemId),
            Tier = tier,
            Rarity = J.Str(data, "rarity", "common"),
            Slot = mappedSlot,
            Damage = damage,
            Defense = defense,
            DurabilityCurrent = durMax,
            DurabilityMax = durMax,
            AttackSpeed = J.Num(stats, "attackSpeed", 1.0),
            Weight = J.Num(stats, "weight", 1.0),
            Range = J.Num(data, "range", 1.0),
            Requirements = J.Obj(data, "requirements"),
            Bonuses = J.Obj(stats, "bonuses"),
            IconPath = string.IsNullOrEmpty(iconPath) ? null : iconPath,
            HandType = handType,
            ItemType = parsedItemType,
            StatMultipliers = statMultipliers.DeepClone(),
            Tags = tags,
            EffectTags = effectTags,
            EffectParams = effectParams,
        };
    }
}
