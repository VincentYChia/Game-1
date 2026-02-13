// ============================================================================
// Game1.Data.Models.MaterialDefinition
// Migrated from: data/models/materials.py (lines 1-25)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Definition for a material item (stackable resources, consumables, etc.).
    /// Loaded from items-materials-1.JSON and other item JSON files.
    /// Implements IGameItem for unified item pipeline.
    /// </summary>
    public class MaterialDefinition : IGameItem
    {
        [JsonProperty("materialId")]
        public string MaterialId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("category")]
        public string MaterialCategory { get; set; }

        [JsonProperty("rarity")]
        public string Rarity { get; set; } = "common";

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

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("resourceCategory")]
        public string ResourceCategory { get; set; } = "";

        // ====================================================================
        // IGameItem Implementation
        // ====================================================================

        [JsonIgnore]
        public string ItemId => MaterialId;

        [JsonIgnore]
        public string Category => "material";

        [JsonIgnore]
        public bool IsStackable => MaxStack > 1;

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                ["item_id"] = MaterialId,
                ["name"] = Name,
                ["category"] = "material",
                ["tier"] = Tier,
                ["rarity"] = Rarity,
                ["material_category"] = MaterialCategory,
                ["max_stack"] = MaxStack,
            };
        }

        public static MaterialDefinition FromSaveData(Dictionary<string, object> data)
        {
            return new MaterialDefinition
            {
                MaterialId = data.TryGetValue("item_id", out var id) ? id?.ToString() : "",
                Name = data.TryGetValue("name", out var name) ? name?.ToString() : "",
                Tier = data.TryGetValue("tier", out var tier) ? System.Convert.ToInt32(tier) : 1,
                Rarity = data.TryGetValue("rarity", out var rarity) ? rarity?.ToString() : "common",
                MaterialCategory = data.TryGetValue("material_category", out var cat) ? cat?.ToString() : "",
                MaxStack = data.TryGetValue("max_stack", out var ms) ? System.Convert.ToInt32(ms) : 99,
            };
        }
    }
}
