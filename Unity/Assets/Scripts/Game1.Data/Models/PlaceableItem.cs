// Game1.Data.Models.PlaceableItem
// Phase: 1 - Foundation
// Architecture Improvement: IGameItem type hierarchy (IMPROVEMENTS.md Part 4)
// Placeable tools (crafting stations, turrets, traps, bombs).

using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Game1.Data.Interfaces;

namespace Game1.Data.Models
{
    /// <summary>
    /// Placeable tools (crafting stations, turrets, traps, bombs).
    /// Stackable (MaxStack = 10) but with special placement behavior.
    /// </summary>
    [Serializable]
    public class PlaceableItem : IGameItem
    {
        [JsonProperty("itemId")]
        public string ItemId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonIgnore]
        public string Category => "placeable";

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("rarity")]
        public string Rarity { get; set; }

        [JsonIgnore]
        public int MaxStack => 10;

        [JsonIgnore]
        public bool IsStackable => true;

        // Placeable-specific
        [JsonProperty("placeableType")]
        public string PlaceableType { get; set; }

        [JsonProperty("stationTier")]
        public int StationTier { get; set; }

        [JsonProperty("description")]
        public string Description { get; set; } = "";

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        [JsonProperty("effectTags")]
        public List<string> EffectTags { get; set; } = new();

        [JsonProperty("effectParams")]
        public Dictionary<string, object> EffectParams { get; set; } = new();

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "category", Category },
                { "itemId", ItemId },
                { "name", Name },
                { "tier", Tier },
                { "rarity", Rarity },
                { "placeableType", PlaceableType },
                { "stationTier", StationTier }
            };
        }
    }
}
