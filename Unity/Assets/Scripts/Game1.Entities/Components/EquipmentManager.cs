// Game1.Entities.Components.EquipmentManager
// Migrated from: entities/components/equipment_manager.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Data.Models;
using Game1.Entities;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Manages equipped items in 10 slots.
    /// Handles equip/unequip with hand type validation, stat recalculation,
    /// and defense/damage queries.
    /// </summary>
    public class EquipmentManager
    {
        /// <summary>
        /// Equipment slots: mainHand, offHand, helmet, chestplate, leggings,
        /// boots, gauntlets, accessory, axe, pickaxe.
        /// </summary>
        public Dictionary<string, EquipmentItem> Slots { get; set; } = new()
        {
            { "mainHand", null },
            { "offHand", null },
            { "helmet", null },
            { "chestplate", null },
            { "leggings", null },
            { "boots", null },
            { "gauntlets", null },
            { "accessory", null },
            { "axe", null },
            { "pickaxe", null },
        };

        // All armor slot names for defense calculations
        private static readonly string[] ArmorSlots = { "helmet", "chestplate", "leggings", "boots", "gauntlets" };

        /// <summary>
        /// Equip an item. Returns (previousItem, statusMessage).
        /// The character parameter is used for requirement checks and stat recalculation.
        /// </summary>
        public (EquipmentItem PreviousItem, string Status) Equip(EquipmentItem item, Character character)
        {
            // Check equip requirements
            var (canEquip, reason) = item.CanEquip(character);
            if (!canEquip)
                return (null, reason);

            string slot = item.Slot;
            if (!Slots.ContainsKey(slot))
                return (null, $"Invalid slot: {slot}");

            // Hand type validation
            if (slot == "mainHand" && item.HandType == "2H" && Slots["offHand"] != null)
            {
                // 2H weapon: caller should auto-unequip offhand before calling this
            }
            else if (slot == "offHand")
            {
                var mainhand = Slots["mainHand"];
                if (mainhand != null)
                {
                    if (mainhand.HandType == "2H")
                        return (null, "Cannot equip offhand - mainhand is 2H weapon");
                    if (mainhand.HandType == "default" && item.ItemType != "shield")
                        return (null, "Mainhand weapon doesn't support offhand");
                    if (mainhand.HandType == "versatile" && item.ItemType != "shield" && item.HandType != "1H")
                        return (null, "Versatile mainhand only allows 1H or shield in offhand");
                }

                if (item.HandType != "1H" && item.ItemType != "shield")
                    return (null, "Item cannot be equipped in offhand (must be 1H or shield)");
            }

            var oldItem = Slots[slot];
            Slots[slot] = item;

            // Recalculate character stats
            character.RecalculateStats();

            // Track in stat tracker
            if (character.StatTracker != null)
            {
                string equipKey = $"{slot}_{item.ItemId}";
                character.StatTracker.RecordEquipmentSwap(equipKey, true);
            }

            return (oldItem, "OK");
        }

        /// <summary>
        /// Unequip item from slot.
        /// </summary>
        public EquipmentItem Unequip(string slot, Character character)
        {
            if (!Slots.ContainsKey(slot)) return null;

            var item = Slots[slot];
            Slots[slot] = null;

            character.RecalculateStats();

            if (item != null && character.StatTracker != null)
            {
                string equipKey = $"{slot}_{item.ItemId}";
                character.StatTracker.RecordEquipmentSwap(equipKey, false);
            }

            return item;
        }

        /// <summary>
        /// Check if an item is currently equipped.
        /// </summary>
        public bool IsEquipped(string itemId)
        {
            return Slots.Values.Any(item => item != null && item.ItemId == itemId);
        }

        /// <summary>
        /// Get total defense from all armor pieces (includes enchantment effects).
        /// </summary>
        public int GetTotalDefense()
        {
            int total = 0;
            foreach (string slot in ArmorSlots)
            {
                var item = Slots.GetValueOrDefault(slot);
                if (item != null)
                    total += item.GetDefenseWithEnchantments();
            }
            return total;
        }

        /// <summary>
        /// Get damage range from specified hand (mainHand or offHand).
        /// Returns (min, max) damage. Unarmed mainhand = (1, 2).
        /// </summary>
        public (int Min, int Max) GetWeaponDamage(string hand = "mainHand")
        {
            var weapon = Slots.GetValueOrDefault(hand);
            if (weapon != null)
                return weapon.GetActualDamage();
            if (hand == "mainHand")
                return (1, 2); // Unarmed damage
            return (0, 0); // No offhand
        }

        /// <summary>
        /// Get range of equipped weapon. Default to 1.0 for unarmed.
        /// </summary>
        public float GetWeaponRange(string hand = "mainHand")
        {
            var weapon = Slots.GetValueOrDefault(hand);
            if (weapon != null)
            {
                float baseRange = weapon.Range;
                var weaponTags = weapon.GetMetadataTags();
                if (weaponTags != null && weaponTags.Count > 0)
                {
                    float rangeBonus = WeaponTagModifiers.GetRangeBonus(weaponTags);
                    return baseRange + rangeBonus;
                }
                return baseRange;
            }
            if (hand == "mainHand") return 1.0f;
            return 0f;
        }

        /// <summary>
        /// Get attack speed multiplier of weapon in specified hand.
        /// </summary>
        public float GetWeaponAttackSpeed(string hand = "mainHand")
        {
            var weapon = Slots.GetValueOrDefault(hand);
            return weapon?.AttackSpeed ?? 1.0f;
        }

        /// <summary>
        /// Get aggregate stat bonuses from all equipped items.
        /// </summary>
        public Dictionary<string, float> GetStatBonuses()
        {
            var bonuses = new Dictionary<string, float>();
            foreach (var item in Slots.Values)
            {
                if (item?.Bonuses == null) continue;
                foreach (var (stat, value) in item.Bonuses)
                {
                    bonuses[stat] = bonuses.GetValueOrDefault(stat, 0f) + value;
                }
            }
            return bonuses;
        }
    }
}
