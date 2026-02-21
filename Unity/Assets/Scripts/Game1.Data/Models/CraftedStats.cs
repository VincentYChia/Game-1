// ============================================================================
// Game1.Data.Models.CraftedStats
// Migrated from: data/models/equipment.py (crafted_stats fields)
// Migration phase: 1
// Date: 2026-02-21
// ============================================================================

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Represents stats applied to an item during crafting.
    /// Quality, performance score, and discipline-specific stats from the minigame.
    /// </summary>
    public class CraftedStats
    {
        [JsonProperty("quality")]
        public string Quality { get; set; } = "normal";

        [JsonProperty("performanceScore")]
        public float PerformanceScore { get; set; }

        [JsonProperty("discipline")]
        public string Discipline { get; set; } = "";

        [JsonProperty("craftedBy")]
        public string CraftedBy { get; set; } = "";

        [JsonProperty("bonusDamage")]
        public int BonusDamage { get; set; }

        [JsonProperty("bonusDefense")]
        public int BonusDefense { get; set; }

        [JsonProperty("bonusDurability")]
        public int BonusDurability { get; set; }

        [JsonProperty("bonusEfficiency")]
        public float BonusEfficiency { get; set; }

        [JsonProperty("specialTraits")]
        public List<string> SpecialTraits { get; set; } = new();

        /// <summary>
        /// Serialize to dictionary for save data.
        /// </summary>
        public Dictionary<string, object> ToDict()
        {
            return new Dictionary<string, object>
            {
                ["quality"] = Quality,
                ["performance_score"] = PerformanceScore,
                ["discipline"] = Discipline,
                ["crafted_by"] = CraftedBy,
                ["bonus_damage"] = BonusDamage,
                ["bonus_defense"] = BonusDefense,
                ["bonus_durability"] = BonusDurability,
                ["bonus_efficiency"] = BonusEfficiency,
                ["special_traits"] = SpecialTraits,
            };
        }

        /// <summary>
        /// Reconstruct CraftedStats from a save data dictionary.
        /// </summary>
        public static CraftedStats FromDict(Dictionary<string, object> data)
        {
            if (data == null) return null;

            var stats = new CraftedStats
            {
                Quality = data.TryGetValue("quality", out var q) ? q?.ToString() : "normal",
                PerformanceScore = data.TryGetValue("performance_score", out var ps)
                    ? Convert.ToSingle(ps) : 0f,
                Discipline = data.TryGetValue("discipline", out var disc) ? disc?.ToString() : "",
                CraftedBy = data.TryGetValue("crafted_by", out var cb) ? cb?.ToString() : "",
                BonusDamage = data.TryGetValue("bonus_damage", out var bd) ? Convert.ToInt32(bd) : 0,
                BonusDefense = data.TryGetValue("bonus_defense", out var bdf) ? Convert.ToInt32(bdf) : 0,
                BonusDurability = data.TryGetValue("bonus_durability", out var bdu) ? Convert.ToInt32(bdu) : 0,
                BonusEfficiency = data.TryGetValue("bonus_efficiency", out var be)
                    ? Convert.ToSingle(be) : 0f,
            };

            if (data.TryGetValue("special_traits", out var traitsObj) && traitsObj is IEnumerable<object> traitsList)
            {
                stats.SpecialTraits = new List<string>();
                foreach (var trait in traitsList)
                    stats.SpecialTraits.Add(trait?.ToString() ?? "");
            }

            return stats;
        }
    }
}
