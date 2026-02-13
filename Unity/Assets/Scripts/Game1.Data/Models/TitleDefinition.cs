// ============================================================================
// Game1.Data.Models.TitleDefinition
// Migrated from: data/models/titles.py (lines 1-28)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Definition for an achievement title.
    /// Loaded from titles-1.JSON.
    /// </summary>
    public class TitleDefinition
    {
        [JsonProperty("titleId")]
        public string TitleId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public string Tier { get; set; }

        [JsonProperty("category")]
        public string Category { get; set; }

        [JsonProperty("bonusDescription")]
        public string BonusDescription { get; set; } = "";

        [JsonProperty("bonuses")]
        public Dictionary<string, float> Bonuses { get; set; } = new();

        [JsonProperty("requirements")]
        public Dictionary<string, object> Requirements { get; set; } = new();

        [JsonProperty("hidden")]
        public bool Hidden { get; set; }

        [JsonProperty("acquisitionMethod")]
        public string AcquisitionMethod { get; set; } = "guaranteed_milestone";

        [JsonProperty("generationChance")]
        public float GenerationChance { get; set; } = 1.0f;

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        // Legacy fields
        [JsonProperty("activityType")]
        public string ActivityType { get; set; } = "general";

        [JsonProperty("acquisitionThreshold")]
        public int AcquisitionThreshold { get; set; }

        [JsonProperty("prerequisites")]
        public List<string> Prerequisites { get; set; } = new();

        public override string ToString()
        {
            return $"Title({TitleId}: {Name} [{Tier}])";
        }
    }
}
