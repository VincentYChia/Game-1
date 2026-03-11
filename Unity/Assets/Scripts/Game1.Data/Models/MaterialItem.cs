// Game1.Data.Models.MaterialItem
// Phase: 1 - Foundation
// Architecture Improvement: IGameItem type hierarchy (IMPROVEMENTS.md Part 4)
// Wraps MaterialDefinition as a concrete IGameItem for inventory.

using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Game1.Data.Interfaces;

namespace Game1.Data.Models
{
    /// <summary>
    /// Raw materials (ores, wood, stone, monster drops, gems, herbs).
    /// Stackable (MaxStack = 99), no special behavior beyond crafting input.
    /// </summary>
    [Serializable]
    public class MaterialItem : IGameItem
    {
        [JsonProperty("itemId")]
        public string ItemId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonIgnore]
        public string Category => "material";

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("rarity")]
        public string Rarity { get; set; }

        [JsonIgnore]
        public int MaxStack => 99;

        [JsonIgnore]
        public bool IsStackable => true;

        // Material-specific
        [JsonProperty("materialCategory")]
        public string MaterialCategory { get; set; }

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("description")]
        public string Description { get; set; } = "";

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        [JsonProperty("effectTags")]
        public List<string> EffectTags { get; set; } = new();

        [JsonProperty("effectParams")]
        public Dictionary<string, object> EffectParams { get; set; } = new();

        /// <summary>
        /// Create a MaterialItem from a MaterialDefinition.
        /// </summary>
        public static MaterialItem FromDefinition(MaterialDefinition def)
        {
            return new MaterialItem
            {
                ItemId = def.MaterialId,
                Name = def.Name,
                Tier = def.Tier,
                Rarity = def.Rarity,
                MaterialCategory = def.Category,
                Description = def.Description,
                IconPath = def.IconPath,
                EffectTags = def.EffectTags != null ? new List<string>(def.EffectTags) : new(),
                EffectParams = def.EffectParams != null ? new Dictionary<string, object>(def.EffectParams) : new()
            };
        }

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "category", Category },
                { "itemId", ItemId },
                { "name", Name },
                { "tier", Tier },
                { "rarity", Rarity },
                { "materialCategory", MaterialCategory }
            };
        }
    }
}
