// Game1.Data.Models.EquipmentItem
// Migrated from: data/models/equipment.py (360 lines)
// Phase: 1 - Foundation

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using Game1.Data.Interfaces;

namespace Game1.Data.Models
{
    /// <summary>
    /// Equipment item with stats, durability, and enchantments.
    /// Most complex model in Phase 1: 24 fields, 15 methods.
    /// Implements IGameItem for type-safe inventory (IMPROVEMENTS.md Part 4).
    /// </summary>
    [Serializable]
    public class EquipmentItem : IGameItem
    {
        // IGameItem interface - equipment is non-stackable
        [JsonIgnore]
        string IGameItem.Category => "equipment";
        [JsonIgnore]
        int IGameItem.MaxStack => 1;
        [JsonIgnore]
        bool IGameItem.IsStackable => false;
        [JsonIgnore]
        string IGameItem.ItemId => ItemId;
        [JsonIgnore]
        string IGameItem.Name => Name;
        [JsonIgnore]
        int IGameItem.Tier => Tier;
        [JsonIgnore]
        string IGameItem.Rarity => Rarity;

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "category", "equipment" },
                { "itemId", ItemId },
                { "name", Name },
                { "tier", Tier },
                { "rarity", Rarity },
                { "slot", Slot },
                { "damage", Damage },
                { "defense", Defense },
                { "durabilityCurrent", DurabilityCurrent },
                { "durabilityMax", DurabilityMax },
                { "handType", HandType },
                { "itemType", ItemType }
            };
        }

        [JsonProperty("itemId")]
        public string ItemId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("rarity")]
        public string Rarity { get; set; }

        [JsonProperty("slot")]
        public string Slot { get; set; }

        [JsonProperty("damage")]
        public int[] Damage { get; set; } = new[] { 0, 0 };

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
        public string HandType { get; set; } = "default";

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

        // -- Helper for damage tuple access --
        public int DamageMin => Damage != null && Damage.Length > 0 ? Damage[0] : 0;
        public int DamageMax => Damage != null && Damage.Length > 1 ? Damage[1] : 0;

        /// <summary>
        /// Check if this item is soulbound (kept on death).
        /// Checks direct flag OR enchantment with type=="soulbound".
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
        /// Get effectiveness multiplier based on durability.
        /// CRITICAL FORMULA:
        ///   durability_current &lt;= 0  -&gt; 0.5
        ///   dur_pct &gt;= 0.5           -&gt; 1.0
        ///   dur_pct &lt; 0.5            -&gt; 1.0 - (0.5 - dur_pct) * 0.5
        /// </summary>
        public float GetEffectiveness()
        {
            if (DurabilityCurrent <= 0) return 0.5f;
            float durPct = (float)DurabilityCurrent / DurabilityMax;
            return durPct >= 0.5f ? 1.0f : 1.0f - (0.5f - durPct) * 0.5f;
        }

        /// <summary>
        /// Repair this equipment's durability. Returns actual amount repaired.
        /// </summary>
        public int Repair(int? amount = null, float? percent = null)
        {
            int oldDurability = DurabilityCurrent;

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

            return DurabilityCurrent - oldDurability;
        }

        public bool NeedsRepair() => DurabilityCurrent < DurabilityMax;

        /// <summary>
        /// Get repair urgency level.
        /// Thresholds: &gt;=100% "none", &gt;=50% "low", &gt;=20% "medium", &gt;0% "high", ==0% "critical"
        /// </summary>
        public string GetRepairUrgency()
        {
            if (DurabilityCurrent >= DurabilityMax) return "none";
            float percent = (float)DurabilityCurrent / DurabilityMax;
            if (percent >= 0.5f) return "low";
            if (percent >= 0.2f) return "medium";
            if (percent > 0f) return "high";
            return "critical";
        }

        /// <summary>
        /// Get actual damage including bonuses, durability and enchantment effects.
        /// </summary>
        public (int Min, int Max) GetActualDamage()
        {
            int baseMin = DamageMin;
            int baseMax = DamageMax;

            float eff = GetEffectiveness();
            float effectiveMin = baseMin * eff;
            float effectiveMax = baseMax * eff;

            float damageMult = 1.0f;
            if (Bonuses.TryGetValue("damage_multiplier", out float craftedMult))
                damageMult += craftedMult;

            if (ItemType == "tool")
                damageMult *= Efficiency;

            foreach (var ench in Enchantments)
            {
                if (ench.TryGetValue("effect", out var effectObj) && effectObj is Dictionary<string, object> effect)
                {
                    if (effect.TryGetValue("type", out var typeObj) && typeObj?.ToString() == "damage_multiplier")
                    {
                        if (effect.TryGetValue("value", out var valObj) && valObj is double val)
                            damageMult += (float)val;
                    }
                }
            }

            return ((int)(effectiveMin * damageMult), (int)(effectiveMax * damageMult));
        }

        /// <summary>
        /// Get defense value including bonuses and enchantment effects.
        /// </summary>
        public int GetDefenseWithEnchantments()
        {
            float effectiveDefense = Defense * GetEffectiveness();
            float defenseMult = 1.0f;

            if (Bonuses.TryGetValue("defense_multiplier", out float craftedMult))
                defenseMult += craftedMult;

            foreach (var ench in Enchantments)
            {
                if (ench.TryGetValue("effect", out var effectObj) && effectObj is Dictionary<string, object> effect)
                {
                    if (effect.TryGetValue("type", out var typeObj) && typeObj?.ToString() == "defense_multiplier")
                    {
                        if (effect.TryGetValue("value", out var valObj) && valObj is double val)
                            defenseMult += (float)val;
                    }
                }
            }

            return (int)(effectiveDefense * defenseMult);
        }

        /// <summary>
        /// Check if character meets requirements, return (can_equip, reason).
        /// Uses ICharacterStats interface to avoid circular dependency.
        /// </summary>
        public (bool CanEquip, string Reason) CanEquip(ICharacterStats character)
        {
            var statMapping = new Dictionary<string, string>
            {
                { "str", "strength" }, { "strength", "strength" },
                { "def", "defense" }, { "defense", "defense" },
                { "vit", "vitality" }, { "vitality", "vitality" },
                { "lck", "luck" }, { "luck", "luck" },
                { "agi", "agility" }, { "agility", "agility" },
                { "dex", "agility" }, { "dexterity", "agility" },
                { "int", "intelligence" }, { "intelligence", "intelligence" }
            };

            if (Requirements.TryGetValue("level", out var levelObj))
            {
                int reqLevel = Convert.ToInt32(levelObj);
                if (character.Level < reqLevel)
                    return (false, $"Requires level {reqLevel}");
            }

            if (Requirements.TryGetValue("stats", out var statsObj) && statsObj is Dictionary<string, object> stats)
            {
                foreach (var kvp in stats)
                {
                    string statKey = kvp.Key.ToLower();
                    int reqVal = Convert.ToInt32(kvp.Value);

                    string statName = statMapping.TryGetValue(statKey, out var mapped) ? mapped : statKey;
                    int currentVal = GetStatValue(character, statName);

                    if (currentVal < reqVal)
                        return (false, $"Requires {kvp.Key.ToUpper()} {reqVal}");
                }
            }

            return (true, "OK");
        }

        private static int GetStatValue(ICharacterStats stats, string statName)
        {
            return statName switch
            {
                "strength" => stats.Strength,
                "defense" => stats.Defense,
                "vitality" => stats.Vitality,
                "luck" => stats.Luck,
                "agility" => stats.Agility,
                "intelligence" => stats.Intelligence,
                _ => 0
            };
        }

        /// <summary>
        /// Create a deep copy of this equipment item.
        /// Deep-copies enchantments list with new Dictionary instances.
        /// </summary>
        public EquipmentItem Copy()
        {
            return new EquipmentItem
            {
                ItemId = ItemId,
                Name = Name,
                Tier = Tier,
                Rarity = Rarity,
                Slot = Slot,
                Damage = (int[])Damage.Clone(),
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
                HandType = HandType,
                ItemType = ItemType,
                StatMultipliers = new Dictionary<string, float>(StatMultipliers),
                Tags = new List<string>(Tags),
                EffectTags = new List<string>(EffectTags),
                EffectParams = new Dictionary<string, object>(EffectParams),
                Soulbound = Soulbound
            };
        }

        /// <summary>
        /// Check if an enchantment can be applied to this item.
        /// Uses IEnchantmentValidator for tag-based validation (injected).
        /// Falls back to legacy applicable_to list.
        /// </summary>
        public (bool CanApply, string Reason) CanApplyEnchantment(
            string enchantmentId,
            List<string> applicableTo = null,
            Dictionary<string, object> effect = null,
            List<string> tags = null,
            IEnchantmentValidator validator = null)
        {
            string itemType = GetItemTypeForEnchanting();

            // Use tag-based validation if tags provided (new system)
            if (tags != null && tags.Count > 0)
            {
                validator ??= new StubEnchantmentValidator();
                var (canApply, reason) = validator.CanApplyToItem(tags, itemType);
                if (!canApply) return (false, reason);
                return (true, "OK");
            }

            // Fallback to legacy applicable_to list
            if (applicableTo != null && applicableTo.Count > 0)
            {
                if (!applicableTo.Contains(itemType))
                    return (false, $"Cannot apply to {itemType} items");
                return (true, "OK");
            }

            // No validation data - allow by default (graceful)
            return (true, "OK (no applicability rules provided)");
        }

        /// <summary>
        /// Apply an enchantment effect to this item with comprehensive rules.
        /// Handles duplicate checks, family/tier extraction, conflict removal.
        /// </summary>
        public (bool Success, string Reason) ApplyEnchantment(
            string enchantmentId,
            string enchantmentName,
            Dictionary<string, object> effect,
            List<string> metadataTags = null)
        {
            // Check for exact duplicate
            if (Enchantments.Any(e =>
                e.TryGetValue("enchantment_id", out var id) && id?.ToString() == enchantmentId))
            {
                return (false, "This enchantment is already applied");
            }

            var (newFamily, newTier) = GetEnchantmentInfo(enchantmentId);

            // Check if a higher tier of the same family already exists
            foreach (var existingEnch in Enchantments)
            {
                if (existingEnch.TryGetValue("enchantment_id", out var existingIdObj))
                {
                    var (existingFamily, existingTier) = GetEnchantmentInfo(existingIdObj?.ToString() ?? "");
                    if (existingFamily == newFamily && existingTier > newTier)
                    {
                        string existingName = existingEnch.TryGetValue("name", out var nameObj) ? nameObj?.ToString() : existingIdObj?.ToString();
                        return (false, $"Cannot apply {enchantmentName} - {existingName} (higher tier) is already applied");
                    }
                }
            }

            // Remove conflicting enchantments
            var conflictsWith = new List<string>();
            if (effect.TryGetValue("conflictsWith", out var conflictsObj))
            {
                if (conflictsObj is List<object> conflictList)
                    conflictsWith = conflictList.Select(c => c.ToString()).ToList();
                else if (conflictsObj is string[] conflictArray)
                    conflictsWith = conflictArray.ToList();
            }

            Enchantments = Enchantments.Where(ench =>
            {
                string enchId = ench.TryGetValue("enchantment_id", out var idObj) ? idObj?.ToString() ?? "" : "";
                if (conflictsWith.Contains(enchId)) return false;

                if (ench.TryGetValue("effect", out var efObj) && efObj is Dictionary<string, object> ef)
                {
                    if (ef.TryGetValue("conflictsWith", out var cwObj))
                    {
                        if (cwObj is List<object> cwList && cwList.Any(c => c.ToString() == enchantmentId))
                            return false;
                    }
                }
                return true;
            }).ToList();

            // Apply the new enchantment
            var enchantmentData = new Dictionary<string, object>
            {
                { "enchantment_id", enchantmentId },
                { "name", enchantmentName },
                { "effect", effect }
            };
            if (metadataTags != null)
                enchantmentData["metadata_tags"] = metadataTags;

            Enchantments.Add(enchantmentData);
            return (true, "OK");
        }

        /// <summary>
        /// Extract enchantment family and tier from enchantment_id.
        /// E.g., "sharpness_3" -> ("sharpness", 3)
        /// </summary>
        private static (string Family, int Tier) GetEnchantmentInfo(string enchantmentId)
        {
            int lastUnderscore = enchantmentId.LastIndexOf('_');
            if (lastUnderscore > 0 && int.TryParse(enchantmentId[(lastUnderscore + 1)..], out int tier))
                return (enchantmentId[..lastUnderscore], tier);
            return (enchantmentId, 1);
        }

        /// <summary>
        /// Determine the item type for enchantment compatibility.
        /// Slot-based fallback logic when item_type is not set.
        /// </summary>
        public string GetItemTypeForEnchanting()
        {
            if (!string.IsNullOrEmpty(ItemType) &&
                new[] { "weapon", "tool", "armor", "shield", "accessory" }.Contains(ItemType))
            {
                return ItemType == "shield" ? "armor" : ItemType;
            }

            string[] weaponSlots = { "mainHand", "offHand" };
            string[] toolSlots = { "tool" };
            string[] armorSlots = { "helmet", "chestplate", "leggings", "boots", "gauntlets" };

            if (weaponSlots.Contains(Slot) && (DamageMin != 0 || DamageMax != 0))
                return "weapon";
            if (toolSlots.Contains(Slot))
                return "tool";
            if (armorSlots.Contains(Slot))
                return "armor";
            if (weaponSlots.Contains(Slot))
                return "tool";
            return "accessory";
        }

        public List<string> GetMetadataTags() => Tags ?? new List<string>();

        public List<string> GetEffectTags() => EffectTags ?? new List<string>();

        public Dictionary<string, object> GetEffectParams() => EffectParams ?? new Dictionary<string, object>();
    }
}
