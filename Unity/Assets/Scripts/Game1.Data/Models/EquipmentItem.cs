// ============================================================================
// Game1.Data.Models.EquipmentItem
// Migrated from: data/models/equipment.py (lines 1-361)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using Game1.Data.Enums;

namespace Game1.Data.Models
{
    /// <summary>
    /// Equipment item with stats, durability, and enchantments.
    /// Non-stackable (MaxStack = 1). Each instance is unique.
    /// Implements IGameItem for unified item pipeline.
    /// </summary>
    public class EquipmentItem : IGameItem
    {
        [JsonProperty("itemId")]
        public string ItemId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("rarity")]
        public string Rarity { get; set; } = "common";

        [JsonProperty("slot")]
        public string SlotRaw { get; set; } = "mainHand";

        [JsonProperty("damage")]
        public int[] DamageRange { get; set; } = new[] { 0, 0 };

        [JsonProperty("defense")]
        public int Defense { get; set; }

        [JsonProperty("durabilityCurrent")]
        public int DurabilityCurrent { get; set; } = 100;

        [JsonProperty("durabilityMax")]
        public int DurabilityMax { get; set; } = 100;

        [JsonProperty("attackSpeed")]
        public float AttackSpeed { get; set; } = 1.0f;

        [JsonProperty("efficiency")]
        public float Efficiency { get; set; } = 1.0f;

        [JsonProperty("weight")]
        public float Weight { get; set; } = 1.0f;

        [JsonProperty("range")]
        public float Range { get; set; } = 1.0f;

        [JsonProperty("requirements")]
        public Dictionary<string, object> Requirements { get; set; } = new();

        [JsonProperty("bonuses")]
        public Dictionary<string, float> Bonuses { get; set; } = new();

        [JsonProperty("enchantments")]
        public List<Dictionary<string, object>> Enchantments { get; set; } = new();

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        [JsonProperty("handType")]
        public string HandTypeRaw { get; set; } = "default";

        [JsonProperty("itemType")]
        public string ItemType { get; set; } = "weapon";

        [JsonProperty("statMultipliers")]
        public Dictionary<string, float> StatMultipliers { get; set; } = new();

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("effectTags")]
        public List<string> EffectTags { get; set; } = new();

        [JsonProperty("effectParams")]
        public Dictionary<string, object> EffectParams { get; set; } = new();

        [JsonProperty("soulbound")]
        public bool Soulbound { get; set; }

        [JsonProperty("craftedStats")]
        public Dictionary<string, object> CraftedStats { get; set; }

        // ====================================================================
        // Computed Properties
        // ====================================================================

        /// <summary>Parsed equipment slot enum.</summary>
        [JsonIgnore]
        public EquipmentSlot Slot => EquipmentSlotExtensions.FromJson(SlotRaw);

        /// <summary>Parsed hand type enum.</summary>
        [JsonIgnore]
        public HandType HandType => HandTypeExtensions.FromJsonString(HandTypeRaw);

        /// <summary>Minimum damage.</summary>
        [JsonIgnore]
        public int DamageMin => DamageRange != null && DamageRange.Length > 0 ? DamageRange[0] : 0;

        /// <summary>Maximum damage.</summary>
        [JsonIgnore]
        public int DamageMax => DamageRange != null && DamageRange.Length > 1 ? DamageRange[1] : 0;

        // ====================================================================
        // IGameItem Implementation
        // ====================================================================

        [JsonIgnore]
        public string Category => "equipment";

        [JsonIgnore]
        public int MaxStack => 1;

        [JsonIgnore]
        public bool IsStackable => false;

        // ====================================================================
        // Methods (ported from equipment.py)
        // ====================================================================

        /// <summary>
        /// Get effectiveness multiplier based on durability.
        /// At 0% durability = 50% effectiveness. Items never break.
        /// Matches Python: equipment.py:49-55
        /// </summary>
        public float GetEffectiveness()
        {
            if (DurabilityCurrent <= 0) return 0.5f;
            float durPercent = (float)DurabilityCurrent / DurabilityMax;
            return durPercent >= 0.5f ? 1.0f : 1.0f - (0.5f - durPercent) * 0.5f;
        }

        /// <summary>
        /// Check if this item is soulbound (kept on death).
        /// </summary>
        public bool IsSoulbound()
        {
            if (Soulbound) return true;
            foreach (var ench in Enchantments)
            {
                if (ench.TryGetValue("effect", out var effectObj) && effectObj is Dictionary<string, object> effect)
                {
                    if (effect.TryGetValue("type", out var typeObj) && typeObj?.ToString() == "soulbound")
                        return true;
                }
            }
            return false;
        }

        /// <summary>
        /// Repair equipment durability.
        /// Returns amount of durability actually restored.
        /// </summary>
        public int Repair(int? amount = null, float? percent = null)
        {
            int old = DurabilityCurrent;
            if (amount.HasValue)
            {
                DurabilityCurrent = Math.Min(DurabilityMax, DurabilityCurrent + amount.Value);
            }
            else if (percent.HasValue)
            {
                int repairAmount = (int)(DurabilityMax * percent.Value);
                DurabilityCurrent = Math.Min(DurabilityMax, DurabilityCurrent + repairAmount);
            }
            else
            {
                DurabilityCurrent = DurabilityMax;
            }
            return DurabilityCurrent - old;
        }

        /// <summary>Check if equipment needs repair.</summary>
        public bool NeedsRepair() => DurabilityCurrent < DurabilityMax;

        /// <summary>
        /// Create a deep copy of this equipment item.
        /// Matches Python: equipment.py:189-213
        /// </summary>
        public EquipmentItem Copy()
        {
            return new EquipmentItem
            {
                ItemId = ItemId,
                Name = Name,
                Tier = Tier,
                Rarity = Rarity,
                SlotRaw = SlotRaw,
                DamageRange = DamageRange != null ? (int[])DamageRange.Clone() : new[] { 0, 0 },
                Defense = Defense,
                DurabilityCurrent = DurabilityCurrent,
                DurabilityMax = DurabilityMax,
                AttackSpeed = AttackSpeed,
                Efficiency = Efficiency,
                Weight = Weight,
                Range = Range,
                Requirements = new Dictionary<string, object>(Requirements),
                Bonuses = new Dictionary<string, float>(Bonuses),
                Enchantments = Enchantments.Select(e =>
                    new Dictionary<string, object>(e)).ToList(),
                IconPath = IconPath,
                HandTypeRaw = HandTypeRaw,
                ItemType = ItemType,
                StatMultipliers = new Dictionary<string, float>(StatMultipliers),
                Tags = new List<string>(Tags),
                EffectTags = new List<string>(EffectTags),
                EffectParams = new Dictionary<string, object>(EffectParams),
                Soulbound = Soulbound,
                CraftedStats = CraftedStats != null
                    ? new Dictionary<string, object>(CraftedStats)
                    : null,
            };
        }

        /// <summary>
        /// Serialize to dictionary for save data. (FIX-2: Equipment owns its serialization)
        /// </summary>
        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                ["item_id"] = ItemId,
                ["name"] = Name,
                ["category"] = "equipment",
                ["tier"] = Tier,
                ["rarity"] = Rarity,
                ["slot"] = SlotRaw,
                ["damage"] = DamageRange,
                ["defense"] = Defense,
                ["durability_current"] = DurabilityCurrent,
                ["durability_max"] = DurabilityMax,
                ["attack_speed"] = AttackSpeed,
                ["efficiency"] = Efficiency,
                ["weight"] = Weight,
                ["range"] = Range,
                ["hand_type"] = HandTypeRaw,
                ["item_type"] = ItemType,
                ["soulbound"] = Soulbound,
                ["tags"] = Tags,
                ["effect_tags"] = EffectTags,
                ["enchantments"] = Enchantments,
                ["bonuses"] = Bonuses,
                ["requirements"] = Requirements,
                ["crafted_stats"] = CraftedStats,
            };
        }

        /// <summary>Alias for ToSaveData() matching Python convention.</summary>
        public Dictionary<string, object> ToDict() => ToSaveData();

        /// <summary>
        /// Reconstruct an EquipmentItem from save data dictionary.
        /// </summary>
        public static EquipmentItem FromDict(Dictionary<string, object> data)
        {
            var item = new EquipmentItem
            {
                ItemId = data.TryGetValue("item_id", out var id) ? id?.ToString() : "",
                Name = data.TryGetValue("name", out var name) ? name?.ToString() : "",
                Tier = data.TryGetValue("tier", out var tier) ? Convert.ToInt32(tier) : 1,
                Rarity = data.TryGetValue("rarity", out var rarity) ? rarity?.ToString() : "common",
                SlotRaw = data.TryGetValue("slot", out var slot) ? slot?.ToString() : "mainHand",
                Defense = data.TryGetValue("defense", out var def) ? Convert.ToInt32(def) : 0,
                DurabilityCurrent = data.TryGetValue("durability_current", out var dc)
                    ? Convert.ToInt32(dc) : 100,
                DurabilityMax = data.TryGetValue("durability_max", out var dm)
                    ? Convert.ToInt32(dm) : 100,
                AttackSpeed = data.TryGetValue("attack_speed", out var atkSpd)
                    ? Convert.ToSingle(atkSpd) : 1.0f,
                Efficiency = data.TryGetValue("efficiency", out var eff)
                    ? Convert.ToSingle(eff) : 1.0f,
                Weight = data.TryGetValue("weight", out var wt)
                    ? Convert.ToSingle(wt) : 1.0f,
                Range = data.TryGetValue("range", out var rng)
                    ? Convert.ToSingle(rng) : 1.0f,
                HandTypeRaw = data.TryGetValue("hand_type", out var ht) ? ht?.ToString() : "default",
                ItemType = data.TryGetValue("item_type", out var it) ? it?.ToString() : "weapon",
                Soulbound = data.TryGetValue("soulbound", out var sb) && Convert.ToBoolean(sb),
            };

            // Parse damage array
            if (data.TryGetValue("damage", out var dmgObj))
            {
                if (dmgObj is IEnumerable<object> dmgList)
                {
                    var arr = dmgList.Select(x => Convert.ToInt32(x)).ToArray();
                    if (arr.Length >= 2) item.DamageRange = new[] { arr[0], arr[1] };
                }
            }

            return item;
        }

        public override string ToString()
        {
            return $"{Name} (T{Tier} {Rarity}) [{SlotRaw}]";
        }
    }
}
