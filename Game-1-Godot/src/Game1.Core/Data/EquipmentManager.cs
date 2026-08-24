using Game1.Core.Combat;
using Game1.Core.Progression;

namespace Game1.Core.Data;

/// <summary>
/// Port of entities/components/equipment_manager.py — 8 equipment slots + 2
/// tool slots, hand-type validation matrix (2H blocks offhand; default allows
/// shield only; versatile allows 1H or shield), defense/damage/range/attack-
/// speed/stat-bonus aggregation. Stat recalculation and the EQUIPMENT_CHANGED
/// bus publish become the Changed event.
/// </summary>
public sealed class EquipmentManager
{
    private static readonly string[] SlotNames =
    {
        "mainHand", "offHand", "helmet", "chestplate", "leggings",
        "boots", "gauntlets", "accessory", "axe", "pickaxe",
    };

    public Dictionary<string, EquipmentItem?> Slots { get; } =
        SlotNames.ToDictionary(s => s, _ => (EquipmentItem?)null);

    /// <summary>(itemId, slot, equipped) — replaces stat_tracker + bus publish.</summary>
    public event Action<string, string, bool>? Changed;

    // equipment_manager.py:23-97
    public (EquipmentItem? OldItem, string Reason) Equip(
        EquipmentItem item, ICharacterQuery character)
    {
        var (canEquip, reason) = item.CanEquip(character);
        if (!canEquip)
            return (null, reason);

        var slot = item.Slot;
        if (!Slots.ContainsKey(slot))
            return (null, $"Invalid slot: {slot}");

        if (slot == "offHand")
        {
            var mainhand = Slots["mainHand"];
            if (mainhand is not null)
            {
                if (mainhand.HandType == "2H")
                    return (null, "Cannot equip offhand - mainhand is 2H weapon");
                if (mainhand.HandType == "default" && item.ItemType != "shield")
                    return (null, "Mainhand weapon doesn't support offhand");
                if (mainhand.HandType == "versatile"
                    && item.ItemType != "shield" && item.HandType != "1H")
                    return (null, "Versatile mainhand only allows 1H or shield in offhand");
            }
            if (item.HandType != "1H" && item.ItemType != "shield")
                return (null, "Item cannot be equipped in offhand (must be 1H or shield)");
        }

        var oldItem = Slots[slot];
        Slots[slot] = item;
        Changed?.Invoke(item.ItemId, slot, true);
        return (oldItem, "OK");
    }

    // :99-123
    public EquipmentItem? Unequip(string slot)
    {
        if (!Slots.TryGetValue(slot, out var item))
            return null;
        Slots[slot] = null;
        if (item is not null)
            Changed?.Invoke(item.ItemId, slot, false);
        return item;
    }

    public bool IsEquipped(string itemId) =>
        Slots.Values.Any(i => i is not null && i.ItemId == itemId);

    // :132-140
    public int GetTotalDefense() =>
        new[] { "helmet", "chestplate", "leggings", "boots", "gauntlets" }
            .Select(s => Slots[s])
            .Where(i => i is not null)
            .Sum(i => i!.GetDefenseWithEnchantments());

    // :142-149 — unarmed mainhand (1,2); empty offhand (0,0)
    public (int Min, int Max) GetWeaponDamage(string hand = "mainHand")
    {
        var weapon = Slots.GetValueOrDefault(hand);
        if (weapon is not null)
            return weapon.GetActualDamage();
        return hand == "mainHand" ? (1, 2) : (0, 0);
    }

    // :151-171 — any held item +1 range over fists; reach tag adds on top
    public double GetWeaponRange(string hand = "mainHand")
    {
        var weapon = Slots.GetValueOrDefault(hand);
        if (weapon is not null)
        {
            var baseRange = weapon.Range + 1.0;
            var tags = weapon.Tags;
            if (tags.Count > 0)
                return baseRange + WeaponTagModifiers.GetRangeBonus(tags);
            return baseRange;
        }
        return hand == "mainHand" ? 1.0 : 0.0;
    }

    public double GetWeaponAttackSpeed(string hand = "mainHand") =>
        Slots.GetValueOrDefault(hand)?.AttackSpeed ?? 1.0;

    // :180-186 — additive across all equipped items
    public Dictionary<string, double> GetStatBonuses()
    {
        var bonuses = new Dictionary<string, double>();
        foreach (var item in Slots.Values)
        {
            if (item is null) continue;
            foreach (var kv in item.Bonuses)
            {
                var value = J.AsNum(kv.Value) ?? 0;
                bonuses[kv.Key] = bonuses.GetValueOrDefault(kv.Key, 0) + value;
            }
        }
        return bonuses;
    }
}
