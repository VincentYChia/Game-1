// ============================================================================
// Game1.Data.Models.ClassDefinition
// Migrated from: data/models/classes.py (lines 1-47)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Game1.Data.Models
{
    /// <summary>
    /// Definition for a character class with tag-driven identity.
    /// Tags define class identity for skill affinity bonuses.
    /// Loaded from classes-1.JSON.
    ///
    /// JSON schema notes:
    ///   - "startingBonuses" is a dict of bonus_name -> float (not "bonuses")
    ///   - "startingSkill" is a complex object { skillId, skillName, ... } (not a plain string)
    ///   - "recommendedStats" is a complex object { primary: [...], secondary: [...], avoid: [...] }
    /// </summary>
    public class ClassDefinition
    {
        [JsonProperty("classId")]
        public string ClassId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("description")]
        public string Description { get; set; } = "";

        // JSON key is "startingBonuses", mapped to Bonuses for internal use
        [JsonProperty("startingBonuses")]
        public Dictionary<string, float> Bonuses { get; set; } = new();

        // JSON has startingSkill as { "skillId": "...", "skillName": "...", ... }
        // We extract just the skillId string
        [JsonIgnore]
        public string StartingSkill { get; set; } = "";

        [JsonProperty("startingSkill")]
        private JToken StartingSkillRaw
        {
            set
            {
                if (value == null) return;
                if (value.Type == JTokenType.String)
                    StartingSkill = value.ToString();
                else if (value.Type == JTokenType.Object)
                    StartingSkill = value["skillId"]?.ToString() ?? "";
            }
        }

        // JSON has recommendedStats as { "primary": [...], "secondary": [...], "avoid": [...] }
        // We flatten primary + secondary into a single list
        [JsonIgnore]
        public List<string> RecommendedStats { get; set; } = new();

        [JsonProperty("recommendedStats")]
        private JToken RecommendedStatsRaw
        {
            set
            {
                RecommendedStats = new List<string>();
                if (value == null) return;
                if (value.Type == JTokenType.Array)
                {
                    RecommendedStats = value.ToObject<List<string>>() ?? new List<string>();
                }
                else if (value.Type == JTokenType.Object)
                {
                    var primary = value["primary"]?.ToObject<List<string>>();
                    var secondary = value["secondary"]?.ToObject<List<string>>();
                    if (primary != null) RecommendedStats.AddRange(primary);
                    if (secondary != null) RecommendedStats.AddRange(secondary);
                }
            }
        }

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("preferredDamageTypes")]
        public List<string> PreferredDamageTypes { get; set; } = new();

        [JsonProperty("preferredArmorType")]
        public string PreferredArmorType { get; set; } = "";

        /// <summary>Check if class has a specific tag (case-insensitive).</summary>
        public bool HasTag(string tag)
        {
            if (string.IsNullOrEmpty(tag) || Tags == null) return false;
            return Tags.Any(t => string.Equals(t, tag, StringComparison.OrdinalIgnoreCase));
        }

        /// <summary>
        /// Calculate skill affinity bonus based on tag overlap.
        /// Each matching tag adds 5% bonus, up to 20% max.
        /// Matches Python: classes.py:33-46
        /// </summary>
        public float GetSkillAffinityBonus(List<string> skillTags)
        {
            if (skillTags == null || skillTags.Count == 0 || Tags == null || Tags.Count == 0)
                return 0.0f;

            var classTags = new HashSet<string>(Tags.Select(t => t.ToLowerInvariant()));
            var matchCount = skillTags.Count(st => classTags.Contains(st.ToLowerInvariant()));

            const float bonusPerTag = 0.05f;
            const float maxBonus = 0.20f;

            return MathF.Min(matchCount * bonusPerTag, maxBonus);
        }

        public override string ToString()
        {
            return $"Class({ClassId}: {Name})";
        }
    }
}
