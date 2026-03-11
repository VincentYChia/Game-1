// Game1.Data.Models.TitleDefinition
// Migrated from: data/models/titles.py (27 lines)
// Phase: 1 - Foundation
// Depends on: UnlockRequirements (intra-phase dependency)

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Definition for an achievement title. Pure data - no methods.
    /// </summary>
    [Serializable]
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
        public string BonusDescription { get; set; }

        [JsonProperty("bonuses")]
        public Dictionary<string, float> Bonuses { get; set; } = new();

        [JsonProperty("requirements")]
        public UnlockRequirements Requirements { get; set; }

        [JsonProperty("hidden")]
        public bool Hidden { get; set; }

        [JsonProperty("acquisitionMethod")]
        public string AcquisitionMethod { get; set; } = "guaranteed_milestone";

        [JsonProperty("generationChance")]
        public float GenerationChance { get; set; } = 1.0f;

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        // Legacy fields (deprecated but kept for backward compatibility)
        [JsonProperty("activityType")]
        public string ActivityType { get; set; } = "general";

        [JsonProperty("acquisitionThreshold")]
        public int AcquisitionThreshold { get; set; }

        [JsonProperty("prerequisites")]
        public List<string> Prerequisites { get; set; } = new();
    }
}
