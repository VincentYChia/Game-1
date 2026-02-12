// Game1.Data.Models.MaterialDefinition
// Migrated from: data/models/materials.py (24 lines)
// Phase: 1 - Foundation

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Definition for a material item (stackable resources, consumables, etc.).
    /// Pure data - no methods to port.
    /// </summary>
    [Serializable]
    public class MaterialDefinition
    {
        [JsonProperty("materialId")]
        public string MaterialId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("category")]
        public string Category { get; set; }

        [JsonProperty("rarity")]
        public string Rarity { get; set; }

        [JsonProperty("description")]
        public string Description { get; set; } = "";

        [JsonProperty("maxStack")]
        public int MaxStack { get; set; } = 99;

        [JsonProperty("properties")]
        public Dictionary<string, object> Properties { get; set; } = new();

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        [JsonProperty("placeable")]
        public bool Placeable { get; set; }

        [JsonProperty("itemType")]
        public string ItemType { get; set; } = "";

        [JsonProperty("itemSubtype")]
        public string ItemSubtype { get; set; } = "";

        [JsonProperty("effect")]
        public string Effect { get; set; } = "";

        [JsonProperty("effectTags")]
        public List<string> EffectTags { get; set; } = new();

        [JsonProperty("effectParams")]
        public Dictionary<string, object> EffectParams { get; set; } = new();
    }
}
