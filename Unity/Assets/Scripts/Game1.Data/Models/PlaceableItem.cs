// ============================================================================
// Game1.Data.Models.PlaceableItem
// Migrated from: N/A (new architecture — Part 4: IGameItem Type Hierarchy)
// Migration phase: 1
// Date: 2026-02-21
// ============================================================================

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Placeable item (crafting stations, turrets, traps, bombs).
    /// Items that can be placed in the game world.
    /// Stackable (MaxStack = 10). Implements IGameItem for unified item pipeline.
    /// </summary>
    public class PlaceableItem : IGameItem
    {
        [JsonProperty("itemId")]
        public string ItemId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; } = 1;

        [JsonProperty("rarity")]
        public string Rarity { get; set; } = "common";

        [JsonProperty("description")]
        public string Description { get; set; } = "";

        [JsonProperty("maxStack")]
        public int MaxStack { get; set; } = 10;

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        [JsonProperty("placeableType")]
        public string PlaceableType { get; set; } = "station";

        [JsonProperty("stationType")]
        public string StationType { get; set; } = "";

        [JsonProperty("stationTier")]
        public int StationTier { get; set; } = 1;

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("effectTags")]
        public List<string> EffectTags { get; set; } = new();

        [JsonProperty("effectParams")]
        public Dictionary<string, object> EffectParams { get; set; } = new();

        [JsonProperty("placementRadius")]
        public float PlacementRadius { get; set; } = 1.0f;

        // ====================================================================
        // IGameItem Implementation
        // ====================================================================

        [JsonIgnore]
        public string Category => "placeable";

        [JsonIgnore]
        public bool IsStackable => MaxStack > 1;

        /// <summary>
        /// Serialize to dictionary for save data.
        /// </summary>
        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                ["item_id"] = ItemId,
                ["name"] = Name,
                ["category"] = "placeable",
                ["tier"] = Tier,
                ["rarity"] = Rarity,
                ["max_stack"] = MaxStack,
                ["description"] = Description,
                ["placeable_type"] = PlaceableType,
                ["station_type"] = StationType,
                ["station_tier"] = StationTier,
                ["tags"] = Tags,
            };
        }

        /// <summary>
        /// Reconstruct a PlaceableItem from save data dictionary.
        /// </summary>
        public static PlaceableItem FromSaveData(Dictionary<string, object> data)
        {
            var item = new PlaceableItem
            {
                ItemId = data.TryGetValue("item_id", out var id) ? id?.ToString() : "",
                Name = data.TryGetValue("name", out var name) ? name?.ToString() : "",
                Tier = data.TryGetValue("tier", out var tier) ? Convert.ToInt32(tier) : 1,
                Rarity = data.TryGetValue("rarity", out var rarity) ? rarity?.ToString() : "common",
                MaxStack = data.TryGetValue("max_stack", out var ms) ? Convert.ToInt32(ms) : 10,
                Description = data.TryGetValue("description", out var desc) ? desc?.ToString() : "",
                PlaceableType = data.TryGetValue("placeable_type", out var pt) ? pt?.ToString() : "station",
                StationType = data.TryGetValue("station_type", out var st) ? st?.ToString() : "",
                StationTier = data.TryGetValue("station_tier", out var stier) ? Convert.ToInt32(stier) : 1,
            };

            if (data.TryGetValue("tags", out var tagsObj) && tagsObj is IEnumerable<object> tagsList)
            {
                item.Tags = new List<string>();
                foreach (var tag in tagsList)
                    item.Tags.Add(tag?.ToString() ?? "");
            }

            return item;
        }

        /// <summary>Alias for FromSaveData matching Python convention.</summary>
        public static PlaceableItem FromDict(Dictionary<string, object> data) => FromSaveData(data);

        public override string ToString()
        {
            return $"{Name} (T{Tier} {Rarity}) [{PlaceableType}]";
        }
    }
}
