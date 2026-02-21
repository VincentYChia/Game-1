// ============================================================================
// Game1.Data.Models.ConsumableItem
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
    /// Consumable item (potions, food, scrolls) that applies effects on use.
    /// Stackable (MaxStack = 20). Consumed on use.
    /// Implements IGameItem for unified item pipeline.
    /// </summary>
    public class ConsumableItem : IGameItem
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
        public int MaxStack { get; set; } = 20;

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        [JsonProperty("effectTags")]
        public List<string> EffectTags { get; set; } = new();

        [JsonProperty("effectParams")]
        public Dictionary<string, object> EffectParams { get; set; } = new();

        [JsonProperty("duration")]
        public float Duration { get; set; }

        [JsonProperty("cooldown")]
        public float Cooldown { get; set; }

        [JsonProperty("itemSubtype")]
        public string ItemSubtype { get; set; } = "potion";

        // ====================================================================
        // IGameItem Implementation
        // ====================================================================

        [JsonIgnore]
        public string Category => "consumable";

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
                ["category"] = "consumable",
                ["tier"] = Tier,
                ["rarity"] = Rarity,
                ["max_stack"] = MaxStack,
                ["description"] = Description,
                ["effect_tags"] = EffectTags,
                ["effect_params"] = EffectParams,
                ["duration"] = Duration,
                ["cooldown"] = Cooldown,
                ["item_subtype"] = ItemSubtype,
            };
        }

        /// <summary>
        /// Reconstruct a ConsumableItem from save data dictionary.
        /// </summary>
        public static ConsumableItem FromSaveData(Dictionary<string, object> data)
        {
            var item = new ConsumableItem
            {
                ItemId = data.TryGetValue("item_id", out var id) ? id?.ToString() : "",
                Name = data.TryGetValue("name", out var name) ? name?.ToString() : "",
                Tier = data.TryGetValue("tier", out var tier) ? Convert.ToInt32(tier) : 1,
                Rarity = data.TryGetValue("rarity", out var rarity) ? rarity?.ToString() : "common",
                MaxStack = data.TryGetValue("max_stack", out var ms) ? Convert.ToInt32(ms) : 20,
                Description = data.TryGetValue("description", out var desc) ? desc?.ToString() : "",
                Duration = data.TryGetValue("duration", out var dur) ? Convert.ToSingle(dur) : 0f,
                Cooldown = data.TryGetValue("cooldown", out var cd) ? Convert.ToSingle(cd) : 0f,
                ItemSubtype = data.TryGetValue("item_subtype", out var sub) ? sub?.ToString() : "potion",
            };

            if (data.TryGetValue("effect_tags", out var tagsObj) && tagsObj is IEnumerable<object> tagsList)
            {
                item.EffectTags = new List<string>();
                foreach (var tag in tagsList)
                    item.EffectTags.Add(tag?.ToString() ?? "");
            }

            return item;
        }

        /// <summary>Alias for FromSaveData matching Python convention.</summary>
        public static ConsumableItem FromDict(Dictionary<string, object> data) => FromSaveData(data);

        public override string ToString()
        {
            return $"{Name} (T{Tier} {Rarity}) [consumable]";
        }
    }
}
