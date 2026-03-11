// Game1.Data.Models.ConsumableItem
// Phase: 1 - Foundation
// Architecture Improvement: IGameItem type hierarchy (IMPROVEMENTS.md Part 4)
// Potions and consumable items.

using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Game1.Data.Interfaces;

namespace Game1.Data.Models
{
    /// <summary>
    /// Potions and consumable items.
    /// Stackable (MaxStack = 20). Consumed on use, applying effects via tags.
    /// </summary>
    [Serializable]
    public class ConsumableItem : IGameItem
    {
        [JsonProperty("itemId")]
        public string ItemId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonIgnore]
        public string Category => "consumable";

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("rarity")]
        public string Rarity { get; set; }

        [JsonIgnore]
        public int MaxStack => 20;

        [JsonIgnore]
        public bool IsStackable => true;

        // Consumable-specific
        [JsonProperty("effectTags")]
        public List<string> EffectTags { get; set; } = new();

        [JsonProperty("effectParams")]
        public Dictionary<string, float> EffectParams { get; set; } = new();

        [JsonProperty("description")]
        public string Description { get; set; } = "";

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "category", Category },
                { "itemId", ItemId },
                { "name", Name },
                { "tier", Tier },
                { "rarity", Rarity }
            };
        }
    }
}
