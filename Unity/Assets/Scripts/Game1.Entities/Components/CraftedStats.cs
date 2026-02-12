// Game1.Entities.Components.CraftedStats
// Migrated from: entities/components/crafted_stats.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Stores stats that were generated during crafting minigames.
    /// Includes quality score, rarity modifiers, and any special bonuses
    /// applied during the crafting process.
    /// </summary>
    [Serializable]
    public class CraftedStats
    {
        /// <summary>
        /// Minigame quality score (0.0-1.0).
        /// </summary>
        public float QualityScore { get; set; }

        /// <summary>
        /// Quality tier derived from score:
        /// 0-25% Normal, 25-50% Fine, 50-75% Superior, 75-90% Masterwork, 90-100% Legendary.
        /// </summary>
        public string QualityTier { get; set; } = "Normal";

        /// <summary>
        /// Rarity modifier applied to the item.
        /// </summary>
        public string Rarity { get; set; } = "common";

        /// <summary>
        /// Stat modifiers from crafting (e.g., bonus damage, defense).
        /// Key = stat name, Value = modifier value.
        /// </summary>
        public Dictionary<string, float> Modifiers { get; set; } = new();

        /// <summary>
        /// Whether this was a first-try bonus craft.
        /// </summary>
        public bool FirstTryBonus { get; set; }

        /// <summary>
        /// Whether this was a perfect craft (100% score).
        /// </summary>
        public bool PerfectCraft { get; set; }

        /// <summary>
        /// Crafting discipline used.
        /// </summary>
        public string Discipline { get; set; } = "";

        /// <summary>
        /// Get the quality tier from a score.
        /// Matches Python reward_calculator.py tiers exactly.
        /// </summary>
        public static string GetQualityTierFromScore(float score)
        {
            if (score >= 0.90f) return "Legendary";
            if (score >= 0.75f) return "Masterwork";
            if (score >= 0.50f) return "Superior";
            if (score >= 0.25f) return "Fine";
            return "Normal";
        }

        /// <summary>
        /// Serialize for saving.
        /// </summary>
        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "quality_score", QualityScore },
                { "quality_tier", QualityTier },
                { "rarity", Rarity },
                { "modifiers", new Dictionary<string, float>(Modifiers) },
                { "first_try_bonus", FirstTryBonus },
                { "perfect_craft", PerfectCraft },
                { "discipline", Discipline }
            };
        }

        /// <summary>
        /// Restore from save data.
        /// </summary>
        public static CraftedStats FromSaveData(Dictionary<string, object> data)
        {
            if (data == null) return null;

            var stats = new CraftedStats();
            if (data.TryGetValue("quality_score", out var qs)) stats.QualityScore = Convert.ToSingle(qs);
            if (data.TryGetValue("quality_tier", out var qt)) stats.QualityTier = qt?.ToString() ?? "Normal";
            if (data.TryGetValue("rarity", out var r)) stats.Rarity = r?.ToString() ?? "common";
            if (data.TryGetValue("first_try_bonus", out var ftb)) stats.FirstTryBonus = Convert.ToBoolean(ftb);
            if (data.TryGetValue("perfect_craft", out var pc)) stats.PerfectCraft = Convert.ToBoolean(pc);
            if (data.TryGetValue("discipline", out var d)) stats.Discipline = d?.ToString() ?? "";

            if (data.TryGetValue("modifiers", out var mods) && mods is Dictionary<string, object> modDict)
            {
                foreach (var kvp in modDict)
                    stats.Modifiers[kvp.Key] = Convert.ToSingle(kvp.Value);
            }

            return stats;
        }
    }
}
