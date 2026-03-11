// Game1.Data.Models.Resources
// Migrated from: data/models/resources.py (77 lines)
// Phase: 1 - Foundation
// Contains: ResourceDrop, ResourceNodeDefinition

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// A single drop from a resource node. Uses qualitative strings for quantity/chance.
    /// </summary>
    [Serializable]
    public class ResourceDrop
    {
        [JsonProperty("materialId")]
        public string MaterialId { get; set; }

        [JsonProperty("quantity")]
        public string Quantity { get; set; }

        [JsonProperty("chance")]
        public string Chance { get; set; }

        /// <summary>
        /// Convert qualitative quantity to numeric range.
        /// "few" -> (1,2), "several" -> (2,4), "many" -> (3,5), "abundant" -> (4,8), default -> (1,3)
        /// </summary>
        public (int Min, int Max) GetQuantityRange()
        {
            return Quantity switch
            {
                "few" => (1, 2),
                "several" => (2, 4),
                "many" => (3, 5),
                "abundant" => (4, 8),
                _ => (1, 3)
            };
        }

        /// <summary>
        /// Convert qualitative chance to float 0.0-1.0.
        /// "guaranteed" -> 1.0, "high" -> 0.8, "moderate" -> 0.5,
        /// "low" -> 0.25, "rare" -> 0.1, "improbable" -> 0.05, default -> 1.0
        /// </summary>
        public float GetChanceValue()
        {
            return Chance switch
            {
                "guaranteed" => 1.0f,
                "high" => 0.8f,
                "moderate" => 0.5f,
                "low" => 0.25f,
                "rare" => 0.1f,
                "improbable" => 0.05f,
                _ => 1.0f
            };
        }
    }

    /// <summary>
    /// Definition of a harvestable resource node from JSON.
    /// </summary>
    [Serializable]
    public class ResourceNodeDefinition
    {
        [JsonProperty("resourceId")]
        public string ResourceId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("category")]
        public string Category { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("requiredTool")]
        public string RequiredTool { get; set; }

        [JsonProperty("baseHealth")]
        public int BaseHealth { get; set; }

        [JsonProperty("drops")]
        public List<ResourceDrop> Drops { get; set; } = new();

        [JsonProperty("respawnTime")]
        public string RespawnTime { get; set; }

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("narrative")]
        public string Narrative { get; set; } = "";

        /// <summary>
        /// Convert qualitative respawn time to seconds. Returns null if no respawn.
        /// "fast" -> 30, "normal" -> 60, "slow" -> 120, "very_slow" -> 300, default -> 60
        /// </summary>
        public float? GetRespawnSeconds()
        {
            if (RespawnTime == null) return null;
            return RespawnTime switch
            {
                "fast" => 30.0f,
                "normal" => 60.0f,
                "slow" => 120.0f,
                "very_slow" => 300.0f,
                _ => 60.0f
            };
        }

        public bool DoesRespawn() => RespawnTime != null;

        public bool IsTree => Category == "tree";
        public bool IsOre => Category == "ore";
        public bool IsStone => Category == "stone";
    }
}
