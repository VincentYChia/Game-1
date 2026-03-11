// Game1.Data.Models.ClassDefinition
// Migrated from: data/models/classes.py (46 lines)
// Phase: 1 - Foundation

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Character class definition with tag-driven identity.
    /// Critical Constants: bonus_per_tag = 0.05 (5%), max_bonus = 0.20 (20%)
    /// </summary>
    [Serializable]
    public class ClassDefinition
    {
        [JsonProperty("classId")]
        public string ClassId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("description")]
        public string Description { get; set; }

        [JsonProperty("bonuses")]
        public Dictionary<string, float> Bonuses { get; set; } = new();

        [JsonProperty("startingSkill")]
        public string StartingSkill { get; set; } = "";

        [JsonProperty("recommendedStats")]
        public List<string> RecommendedStats { get; set; } = new();

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("preferredDamageTypes")]
        public List<string> PreferredDamageTypes { get; set; } = new();

        [JsonProperty("preferredArmorType")]
        public string PreferredArmorType { get; set; } = "";

        /// <summary>
        /// Check if class has a specific tag (case-insensitive).
        /// </summary>
        public bool HasTag(string tag)
        {
            return Tags.Any(t => t.Equals(tag, StringComparison.OrdinalIgnoreCase));
        }

        /// <summary>
        /// Calculate skill affinity bonus based on tag overlap.
        /// Each matching tag adds 5% bonus, up to 20% max.
        /// </summary>
        public float GetSkillAffinityBonus(List<string> skillTags)
        {
            if (skillTags == null || skillTags.Count == 0 || Tags == null || Tags.Count == 0)
                return 0.0f;

            var classTags = new HashSet<string>(Tags.Select(t => t.ToLower()));
            var matchCount = skillTags.Count(st => classTags.Contains(st.ToLower()));

            const float bonusPerTag = 0.05f;
            const float maxBonus = 0.20f;

            return Math.Min(matchCount * bonusPerTag, maxBonus);
        }
    }
}
