// ============================================================================
// Game1.Data.Enums.DamageType
// Migrated from: docs/tag-system/TAG-GUIDE.md (damage type tags)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Data.Enums
{
    /// <summary>
    /// Damage types for combat, skills, and enchantments.
    /// Maps to JSON tag strings: "physical", "fire", "ice", etc.
    /// </summary>
    public enum DamageType
    {
        Physical,
        Fire,
        Ice,
        Lightning,
        Poison,
        Arcane,
        Shadow,
        Holy
    }

    public static class DamageTypeExtensions
    {
        private static readonly Dictionary<string, DamageType> _fromJsonMap = new(StringComparer.OrdinalIgnoreCase)
        {
            ["physical"]  = DamageType.Physical,
            ["fire"]      = DamageType.Fire,
            ["ice"]       = DamageType.Ice,
            ["lightning"] = DamageType.Lightning,
            ["poison"]    = DamageType.Poison,
            ["arcane"]    = DamageType.Arcane,
            ["shadow"]    = DamageType.Shadow,
            ["holy"]      = DamageType.Holy,
        };

        private static readonly Dictionary<DamageType, string> _toJsonMap = new()
        {
            [DamageType.Physical]  = "physical",
            [DamageType.Fire]      = "fire",
            [DamageType.Ice]       = "ice",
            [DamageType.Lightning] = "lightning",
            [DamageType.Poison]    = "poison",
            [DamageType.Arcane]    = "arcane",
            [DamageType.Shadow]    = "shadow",
            [DamageType.Holy]      = "holy",
        };

        /// <summary>Convert enum to lowercase JSON string.</summary>
        public static string ToJsonString(this DamageType type)
        {
            return _toJsonMap.TryGetValue(type, out var str) ? str : "physical";
        }

        /// <summary>Parse a JSON string to DamageType. Returns Physical for unknown values.</summary>
        public static DamageType FromJsonString(string json)
        {
            if (string.IsNullOrEmpty(json)) return DamageType.Physical;
            return _fromJsonMap.TryGetValue(json, out var type) ? type : DamageType.Physical;
        }
    }
}
