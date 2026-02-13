// ============================================================================
// Game1.Data.Enums.EquipmentSlot
// Migrated from: entities/components/equipment_manager.py (lines 10-21)
// Migration phase: 1 (MACRO-2)
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Data.Enums
{
    /// <summary>
    /// Equipment slot types. Replaces magic strings like "mainHand", "helmet", etc.
    /// (MACRO-2: EquipmentSlot/HandType Enums replace magic strings)
    /// </summary>
    public enum EquipmentSlot
    {
        MainHand,
        OffHand,
        Helmet,
        Chestplate,
        Leggings,
        Boots,
        Gauntlets,
        Accessory,
        Axe,       // Tool slot
        Pickaxe    // Tool slot
    }

    /// <summary>
    /// Weapon hand type for equip validation.
    /// </summary>
    public enum HandType
    {
        OneHanded,   // "1H"
        TwoHanded,   // "2H"
        Versatile,   // Can be used as 1H or 2H
        Default      // Main hand only (no offhand support)
    }

    public static class EquipmentSlotExtensions
    {
        /// <summary>
        /// Maps JSON slot strings (including aliases) to EquipmentSlot enum.
        /// Handles: "mainHand", "head" -> Helmet, "chest" -> Chestplate, etc.
        /// </summary>
        private static readonly Dictionary<string, EquipmentSlot> _jsonMap = new(StringComparer.OrdinalIgnoreCase)
        {
            ["mainHand"]   = EquipmentSlot.MainHand,
            ["mainhand"]   = EquipmentSlot.MainHand,
            ["main_hand"]  = EquipmentSlot.MainHand,
            ["offHand"]    = EquipmentSlot.OffHand,
            ["offhand"]    = EquipmentSlot.OffHand,
            ["off_hand"]   = EquipmentSlot.OffHand,
            ["helmet"]     = EquipmentSlot.Helmet,
            ["head"]       = EquipmentSlot.Helmet,
            ["chestplate"] = EquipmentSlot.Chestplate,
            ["chest"]      = EquipmentSlot.Chestplate,
            ["leggings"]   = EquipmentSlot.Leggings,
            ["legs"]       = EquipmentSlot.Leggings,
            ["boots"]      = EquipmentSlot.Boots,
            ["feet"]       = EquipmentSlot.Boots,
            ["gauntlets"]  = EquipmentSlot.Gauntlets,
            ["hands"]      = EquipmentSlot.Gauntlets,
            ["gloves"]     = EquipmentSlot.Gauntlets,
            ["accessory"]  = EquipmentSlot.Accessory,
            ["axe"]        = EquipmentSlot.Axe,
            ["pickaxe"]    = EquipmentSlot.Pickaxe,
        };

        private static readonly Dictionary<EquipmentSlot, string> _toJsonMap = new()
        {
            [EquipmentSlot.MainHand]   = "mainHand",
            [EquipmentSlot.OffHand]    = "offHand",
            [EquipmentSlot.Helmet]     = "helmet",
            [EquipmentSlot.Chestplate] = "chestplate",
            [EquipmentSlot.Leggings]   = "leggings",
            [EquipmentSlot.Boots]      = "boots",
            [EquipmentSlot.Gauntlets]  = "gauntlets",
            [EquipmentSlot.Accessory]  = "accessory",
            [EquipmentSlot.Axe]        = "axe",
            [EquipmentSlot.Pickaxe]    = "pickaxe",
        };

        /// <summary>Convert enum to camelCase JSON string.</summary>
        public static string ToJsonString(this EquipmentSlot slot)
        {
            return _toJsonMap.TryGetValue(slot, out var str) ? str : "mainHand";
        }

        /// <summary>
        /// Parse a JSON string to EquipmentSlot, with alias support.
        /// Returns MainHand for unknown values.
        /// </summary>
        public static EquipmentSlot FromJson(string jsonSlot)
        {
            if (string.IsNullOrEmpty(jsonSlot)) return EquipmentSlot.MainHand;
            return _jsonMap.TryGetValue(jsonSlot, out var slot) ? slot : EquipmentSlot.MainHand;
        }

        /// <summary>Check if a slot is an armor slot (helmet, chest, legs, boots, gauntlets).</summary>
        public static bool IsArmorSlot(this EquipmentSlot slot)
        {
            return slot == EquipmentSlot.Helmet ||
                   slot == EquipmentSlot.Chestplate ||
                   slot == EquipmentSlot.Leggings ||
                   slot == EquipmentSlot.Boots ||
                   slot == EquipmentSlot.Gauntlets;
        }

        /// <summary>Check if a slot is a weapon slot (mainhand, offhand).</summary>
        public static bool IsWeaponSlot(this EquipmentSlot slot)
        {
            return slot == EquipmentSlot.MainHand || slot == EquipmentSlot.OffHand;
        }

        /// <summary>Check if a slot is a tool slot (axe, pickaxe).</summary>
        public static bool IsToolSlot(this EquipmentSlot slot)
        {
            return slot == EquipmentSlot.Axe || slot == EquipmentSlot.Pickaxe;
        }
    }

    public static class HandTypeExtensions
    {
        private static readonly Dictionary<string, HandType> _fromJsonMap = new(StringComparer.OrdinalIgnoreCase)
        {
            ["1H"]        = HandType.OneHanded,
            ["1h"]        = HandType.OneHanded,
            ["one_handed"] = HandType.OneHanded,
            ["2H"]        = HandType.TwoHanded,
            ["2h"]        = HandType.TwoHanded,
            ["two_handed"] = HandType.TwoHanded,
            ["versatile"] = HandType.Versatile,
            ["default"]   = HandType.Default,
        };

        private static readonly Dictionary<HandType, string> _toJsonMap = new()
        {
            [HandType.OneHanded] = "1H",
            [HandType.TwoHanded] = "2H",
            [HandType.Versatile] = "versatile",
            [HandType.Default]   = "default",
        };

        public static string ToJsonString(this HandType type)
        {
            return _toJsonMap.TryGetValue(type, out var str) ? str : "default";
        }

        public static HandType FromJsonString(string json)
        {
            if (string.IsNullOrEmpty(json)) return HandType.Default;
            return _fromJsonMap.TryGetValue(json, out var type) ? type : HandType.Default;
        }
    }
}
