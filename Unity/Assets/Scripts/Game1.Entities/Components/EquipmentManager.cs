// ============================================================================
// Game1.Entities.Components.EquipmentManager
// Migrated from: entities/components/equipment_manager.py (lines 1-172)
// Migration phase: 3 (MACRO-1: event-driven, MACRO-2: enum slots)
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;
using Game1.Data.Enums;
using Game1.Core;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Equipment management component.
    /// MACRO-1: Raises GameEvents instead of calling character methods directly.
    /// MACRO-2: Uses EquipmentSlot enum instead of magic strings.
    /// </summary>
    public class EquipmentManager
    {
        private readonly Dictionary<EquipmentSlot, EquipmentItem> _slots = new();

        public EquipmentManager()
        {
            // Initialize all slots to empty
            foreach (EquipmentSlot slot in Enum.GetValues(typeof(EquipmentSlot)))
            {
                _slots[slot] = null;
            }
        }

        // ====================================================================
        // Equip / Unequip (MACRO-1: event-driven)
        // ====================================================================

        /// <summary>
        /// Equip an item to its designated slot.
        /// Returns the previously equipped item (null if slot was empty), and status message.
        /// Raises GameEvents.OnEquipmentChanged.
        /// </summary>
        public (EquipmentItem PreviousItem, string Status) Equip(EquipmentItem item)
        {
            if (item == null) return (null, "No item");

            EquipmentSlot slot = item.Slot;

            // Hand type validation for weapon slots
            if (slot == EquipmentSlot.MainHand && item.HandType == HandType.TwoHanded)
            {
                // 2H weapon: auto-warn if offhand occupied (caller should handle unequip)
                if (_slots[EquipmentSlot.OffHand] != null)
                {
                    System.Diagnostics.Debug.WriteLine("[EquipmentManager] Warning: 2H weapon with offhand occupied");
                }
            }
            else if (slot == EquipmentSlot.OffHand)
            {
                var mainhand = _slots[EquipmentSlot.MainHand];
                if (mainhand != null)
                {
                    if (mainhand.HandType == HandType.TwoHanded)
                        return (null, "Cannot equip offhand - mainhand is 2H weapon");
                    if (mainhand.HandType == HandType.Default && item.ItemType != "shield")
                        return (null, "Mainhand weapon doesn't support offhand");
                }
            }

            var oldItem = _slots[slot];
            _slots[slot] = item;

            // Raise event (MACRO-1: decoupled from character)
            GameEvents.RaiseEquipmentChanged(item, (int)slot);

            return (oldItem, "OK");
        }

        /// <summary>
        /// Unequip item from a slot.
        /// Returns the unequipped item (null if slot was empty).
        /// Raises GameEvents.OnEquipmentRemoved.
        /// </summary>
        public EquipmentItem Unequip(EquipmentSlot slot)
        {
            if (!_slots.ContainsKey(slot)) return null;

            var item = _slots[slot];
            _slots[slot] = null;

            if (item != null)
            {
                GameEvents.RaiseEquipmentRemoved(item, (int)slot);
            }

            return item;
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get the item equipped in a slot. Returns null if empty.</summary>
        public EquipmentItem GetEquipped(EquipmentSlot slot)
        {
            return _slots.TryGetValue(slot, out var item) ? item : null;
        }

        /// <summary>Check if a specific item ID is currently equipped in any slot.</summary>
        public bool IsEquipped(string itemId)
        {
            foreach (var item in _slots.Values)
            {
                if (item != null && item.ItemId == itemId)
                    return true;
            }
            return false;
        }

        /// <summary>
        /// Get total defense from all armor pieces including enchantments.
        /// </summary>
        public int GetTotalDefense()
        {
            int total = 0;
            EquipmentSlot[] armorSlots = {
                EquipmentSlot.Helmet, EquipmentSlot.Chestplate,
                EquipmentSlot.Leggings, EquipmentSlot.Boots,
                EquipmentSlot.Gauntlets
            };

            foreach (var slot in armorSlots)
            {
                var item = _slots[slot];
                if (item != null)
                    total += item.Defense; // Full defense calculation could include enchantments
            }
            return total;
        }

        /// <summary>
        /// Get weapon damage from a hand slot.
        /// Returns (min, max). Unarmed mainhand = (1, 2).
        /// </summary>
        public (int Min, int Max) GetWeaponDamage(EquipmentSlot hand = EquipmentSlot.MainHand)
        {
            var weapon = _slots.TryGetValue(hand, out var item) ? item : null;
            if (weapon != null)
                return (weapon.DamageMin, weapon.DamageMax);

            return hand == EquipmentSlot.MainHand ? (1, 2) : (0, 0);
        }

        /// <summary>Get all stat bonuses from all equipped items.</summary>
        public Dictionary<string, float> GetStatBonuses()
        {
            var bonuses = new Dictionary<string, float>();
            foreach (var item in _slots.Values)
            {
                if (item?.Bonuses != null)
                {
                    foreach (var kvp in item.Bonuses)
                    {
                        bonuses[kvp.Key] = bonuses.GetValueOrDefault(kvp.Key) + kvp.Value;
                    }
                }
            }
            return bonuses;
        }

        /// <summary>Get all equipped items as a dictionary (non-null entries only).</summary>
        public Dictionary<EquipmentSlot, EquipmentItem> GetAllEquipped()
        {
            var result = new Dictionary<EquipmentSlot, EquipmentItem>();
            foreach (var kvp in _slots)
            {
                if (kvp.Value != null)
                    result[kvp.Key] = kvp.Value;
            }
            return result;
        }
    }
}
