// ============================================================================
// Game1.Data.Enums.Rarity
// Migrated from: core/config.py (RARITY_COLORS), data/models/*.py (rarity fields)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Data.Enums
{
    /// <summary>
    /// Item rarity tiers. Order matches progression from least to most rare.
    /// </summary>
    public enum Rarity
    {
        Common,
        Uncommon,
        Rare,
        Epic,
        Legendary,
        Artifact
    }

    public static class RarityExtensions
    {
        private static readonly Dictionary<string, Rarity> _fromJsonMap = new(StringComparer.OrdinalIgnoreCase)
        {
            ["common"]    = Rarity.Common,
            ["uncommon"]  = Rarity.Uncommon,
            ["rare"]      = Rarity.Rare,
            ["epic"]      = Rarity.Epic,
            ["legendary"] = Rarity.Legendary,
            ["artifact"]  = Rarity.Artifact,
        };

        private static readonly Dictionary<Rarity, string> _toJsonMap = new()
        {
            [Rarity.Common]    = "common",
            [Rarity.Uncommon]  = "uncommon",
            [Rarity.Rare]      = "rare",
            [Rarity.Epic]      = "epic",
            [Rarity.Legendary] = "legendary",
            [Rarity.Artifact]  = "artifact",
        };

        /// <summary>Convert enum to lowercase JSON string.</summary>
        public static string ToJsonString(this Rarity rarity)
        {
            return _toJsonMap.TryGetValue(rarity, out var str) ? str : "common";
        }

        /// <summary>Parse a JSON string to Rarity. Returns Common for unknown values.</summary>
        public static Rarity FromJsonString(string json)
        {
            if (string.IsNullOrEmpty(json)) return Rarity.Common;
            return _fromJsonMap.TryGetValue(json, out var rarity) ? rarity : Rarity.Common;
        }
    }
}
