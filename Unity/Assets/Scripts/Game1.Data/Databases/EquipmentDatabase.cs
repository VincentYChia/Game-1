// Game1.Data.Databases.EquipmentDatabase
// Migrated from: data/databases/equipment_db.py (401 lines)
// Phase: 2 - Data Layer
// Loads from items.JSON/items-smithing-2.JSON, items.JSON/items-tools-1.JSON.
// CRITICAL: Accumulative loading (multiple files loaded into same dict).
// CRITICAL: Equipment stat formulas: globalBase(10) x tierMult x typeMult x subtypeMult x variance(0.85-1.15)

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for equipment items (weapons, armor, tools).
    /// Stores raw JSON data and constructs EquipmentItem on demand.
    /// CRITICAL: Only loads items with category == "equipment".
    /// CRITICAL: Stat calculation formulas must match Python exactly.
    /// </summary>
    public class EquipmentDatabase
    {
        private static EquipmentDatabase _instance;
        private static readonly object _lock = new object();

        // Stores raw JSON data per item (same as Python's self.items)
        public Dictionary<string, JObject> Items { get; private set; }
        public bool Loaded { get; private set; }

        // Stat calculation constants
        private const int GLOBAL_BASE_DAMAGE = 10;
        private const int GLOBAL_BASE_DEFENSE = 10;
        private const int GLOBAL_BASE_DURABILITY = 250;

        private static readonly Dictionary<int, float> TIER_MULTS = new()
        {
            { 1, 1.0f }, { 2, 2.0f }, { 3, 4.0f }, { 4, 8.0f }
        };

        private static readonly Dictionary<string, float> TYPE_MULTS = new()
        {
            { "sword", 1.0f }, { "axe", 1.1f }, { "spear", 1.05f }, { "mace", 1.15f },
            { "dagger", 0.8f }, { "bow", 1.0f }, { "staff", 0.9f }, { "shield", 1.0f }
        };

        private static readonly Dictionary<string, float> SUBTYPE_MULTS = new()
        {
            { "shortsword", 0.9f }, { "longsword", 1.0f }, { "greatsword", 1.4f },
            { "dagger", 1.0f }, { "spear", 1.0f }, { "pike", 1.2f }, { "halberd", 1.4f },
            { "mace", 1.0f }, { "warhammer", 1.3f }, { "maul", 1.5f }
        };

        private static readonly Dictionary<string, float> SLOT_DEFENSE_MULTS = new()
        {
            { "helmet", 0.8f }, { "chestplate", 1.5f }, { "leggings", 1.2f },
            { "boots", 0.7f }, { "gauntlets", 0.6f }
        };

        private static readonly HashSet<string> WEAPON_TYPES = new()
        {
            "weapon", "sword", "axe", "mace", "dagger", "spear", "bow", "staff"
        };

        private static readonly HashSet<string> ARMOR_TYPES = new()
        {
            "armor", "helmet", "chestplate", "leggings", "boots", "gauntlets"
        };

        private static readonly Dictionary<string, string> SLOT_MAPPING = new()
        {
            { "head", "helmet" }, { "chest", "chestplate" }, { "legs", "leggings" },
            { "feet", "boots" }, { "hands", "gauntlets" },
            { "mainHand", "mainHand" }, { "offHand", "offHand" },
            { "helmet", "helmet" }, { "chestplate", "chestplate" },
            { "leggings", "leggings" }, { "boots", "boots" },
            { "gauntlets", "gauntlets" }, { "accessory", "accessory" }
        };

        public static EquipmentDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new EquipmentDatabase();
                }
            }
            return _instance;
        }

        private EquipmentDatabase()
        {
            Items = new Dictionary<string, JObject>();
        }

        /// <summary>
        /// Load equipment from a JSON file. Accumulative - can be called multiple times.
        /// ONLY loads items where category == "equipment".
        /// </summary>
        public bool LoadFromFile(string filepath)
        {
            int count = 0;
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data == null)
                {
                    if (!Loaded) CreatePlaceholders();
                    return false;
                }

                foreach (var prop in data.Properties())
                {
                    if (prop.Name == "metadata") continue;
                    if (prop.Value is not JArray sectionData) continue;

                    foreach (JObject itemData in sectionData)
                    {
                        string itemId = itemData.Value<string>("itemId") ?? "";
                        string category = itemData.Value<string>("category") ?? "";

                        if (!string.IsNullOrEmpty(itemId) && category == "equipment")
                        {
                            Items[itemId] = itemData;
                            count++;
                        }
                    }
                }

                if (count > 0) Loaded = true;
                JsonLoader.Log($"Loaded {count} equipment items (total: {Items.Count})");
                return true;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading equipment: {ex.Message}");
                if (!Loaded) CreatePlaceholders();
                return false;
            }
        }

        /// <summary>
        /// Create an EquipmentItem from raw JSON data.
        /// Applies stat calculation formulas for damage, defense, and durability.
        /// </summary>
        public EquipmentItem CreateEquipmentFromId(string itemId)
        {
            if (!Items.TryGetValue(itemId, out var data))
                return null;

            int tier = data.Value<int?>("tier") ?? 1;
            string itemType = data.Value<string>("type") ?? "";
            string subtype = data.Value<string>("subtype") ?? "";

            var statMultipliers = new Dictionary<string, float>();
            if (data["statMultipliers"] is JObject smObj)
                foreach (var p in smObj.Properties())
                    statMultipliers[p.Name] = p.Value.Value<float>();

            var stats = data["stats"] as JObject;

            // Calculate damage for weapons
            int[] damage = new[] { 0, 0 };
            if (WEAPON_TYPES.Contains(itemType))
            {
                var (min, max) = CalculateWeaponDamage(tier, itemType, subtype, statMultipliers);
                damage = new[] { min, max };
            }
            else if (stats?["damage"] != null)
            {
                if (stats["damage"] is JArray dmgArr && dmgArr.Count >= 2)
                    damage = new[] { dmgArr[0].Value<int>(), dmgArr[1].Value<int>() };
                else if (stats["damage"].Type == JTokenType.Integer || stats["damage"].Type == JTokenType.Float)
                {
                    int d = stats.Value<int>("damage");
                    damage = new[] { d, d };
                }
            }

            // Determine slot
            var metadata = data["metadata"] as JObject;
            var tags = new List<string>();
            if (metadata?["tags"] is JArray tagsArr)
                foreach (var t in tagsArr) tags.Add(t.Value<string>());

            string mappedSlot = DetermineSlot(data, itemType, subtype, tags);

            // Calculate defense for armor
            int defense = 0;
            if (ARMOR_TYPES.Contains(itemType))
            {
                defense = CalculateArmorDefense(tier, mappedSlot, statMultipliers);
            }
            else if (stats?.Value<int?>("defense") != null)
            {
                defense = stats.Value<int>("defense");
            }

            // Calculate durability
            int durMax;
            if (stats?["durability"] != null)
            {
                if (stats["durability"] is JArray durArr && durArr.Count > 0)
                    durMax = durArr.Count > 1 ? durArr[1].Value<int>() : durArr[0].Value<int>();
                else
                    durMax = stats.Value<int>("durability");
            }
            else
            {
                durMax = CalculateDurability(tier, statMultipliers);
            }

            // Icon path
            string iconPath = data.Value<string>("iconPath");
            if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(itemId))
            {
                string subdir = GetIconSubdir(mappedSlot, itemType, damage[0] != 0 || damage[1] != 0);
                iconPath = $"{subdir}/{itemId}.png";
            }

            // Hand type from metadata tags
            string handType = "default";
            if (tags.Contains("1H")) handType = "1H";
            else if (tags.Contains("2H")) handType = "2H";
            else if (tags.Contains("versatile")) handType = "versatile";

            // Parsed item type
            string parsedItemType = itemType switch
            {
                "shield" => "shield",
                "tool" => "tool",
                "armor" => "armor",
                "accessory" => "accessory",
                "station" => "station",
                _ => "weapon"
            };

            // Effect tags (both snake_case and camelCase)
            var effectTags = new List<string>();
            var etArr2 = data["effect_tags"] as JArray ?? data["effectTags"] as JArray;
            if (etArr2 != null) foreach (var t in etArr2) effectTags.Add(t.Value<string>());

            var effectParams = new Dictionary<string, object>();
            var epObj2 = data["effect_params"] as JObject ?? data["effectParams"] as JObject;
            if (epObj2 != null) foreach (var p in epObj2.Properties()) effectParams[p.Name] = p.Value.ToObject<object>();

            var requirements = new Dictionary<string, object>();
            if (data["requirements"] is JObject reqObj)
                foreach (var p in reqObj.Properties()) requirements[p.Name] = p.Value.ToObject<object>();

            var bonuses = new Dictionary<string, float>();
            if (stats?["bonuses"] is JObject bonusObj)
                foreach (var p in bonusObj.Properties()) bonuses[p.Name] = p.Value.Value<float>();

            return new EquipmentItem
            {
                ItemId = itemId,
                Name = data.Value<string>("name") ?? itemId,
                Tier = tier,
                Rarity = data.Value<string>("rarity") ?? "common",
                Slot = mappedSlot,
                Damage = damage,
                Defense = defense,
                DurabilityCurrent = durMax,
                DurabilityMax = durMax,
                AttackSpeed = stats?.Value<float?>("attackSpeed") ?? 1.0f,
                Weight = stats?.Value<float?>("weight") ?? 1.0f,
                Range = data.Value<float?>("range") ?? 1.0f,
                Requirements = requirements,
                Bonuses = bonuses,
                IconPath = iconPath,
                HandType = handType,
                ItemType = parsedItemType,
                StatMultipliers = statMultipliers,
                Tags = tags,
                EffectTags = effectTags,
                EffectParams = effectParams
            };
        }

        public bool IsEquipment(string itemId) => Items.ContainsKey(itemId);

        // -- Stat Calculation Methods (must match Python exactly) --

        private static (int Min, int Max) CalculateWeaponDamage(int tier, string itemType, string subtype,
            Dictionary<string, float> statMultipliers)
        {
            float tierMult = TIER_MULTS.GetValueOrDefault(tier, 1.0f);
            float typeMult = TYPE_MULTS.GetValueOrDefault(itemType, 1.0f);
            float subtypeMult = SUBTYPE_MULTS.GetValueOrDefault(subtype, 1.0f);
            float itemMult = statMultipliers.GetValueOrDefault("damage", 1.0f);

            float baseDamage = GLOBAL_BASE_DAMAGE * tierMult * typeMult * subtypeMult * itemMult;

            int minDamage = (int)(baseDamage * 0.85f);
            int maxDamage = (int)(baseDamage * 1.15f);

            return (minDamage, maxDamage);
        }

        private static int CalculateArmorDefense(int tier, string slot, Dictionary<string, float> statMultipliers)
        {
            float tierMult = TIER_MULTS.GetValueOrDefault(tier, 1.0f);
            float slotMult = SLOT_DEFENSE_MULTS.GetValueOrDefault(slot, 1.0f);
            float itemMult = statMultipliers.GetValueOrDefault("defense", 1.0f);

            return (int)(GLOBAL_BASE_DEFENSE * tierMult * slotMult * itemMult);
        }

        private static int CalculateDurability(int tier, Dictionary<string, float> statMultipliers)
        {
            float tierMult = TIER_MULTS.GetValueOrDefault(tier, 1.0f);
            float itemMult = statMultipliers.GetValueOrDefault("durability", 1.0f);

            return (int)(GLOBAL_BASE_DURABILITY * tierMult * itemMult);
        }

        private static string DetermineSlot(JObject data, string itemType, string subtype, List<string> tags)
        {
            if (WEAPON_TYPES.Contains(itemType))
            {
                string jsonSlot = data.Value<string>("slot") ?? "mainHand";
                return SLOT_MAPPING.GetValueOrDefault(jsonSlot, jsonSlot);
            }
            else if (itemType == "tool")
            {
                if (subtype == "axe" || subtype == "pickaxe")
                    return subtype;
                return "mainHand";
            }
            else if (ARMOR_TYPES.Contains(itemType))
            {
                string tagSlot = GetSlotFromTags(tags);
                if (tagSlot != null) return tagSlot;
                string jsonSlot = data.Value<string>("slot") ?? "helmet";
                return SLOT_MAPPING.GetValueOrDefault(jsonSlot, jsonSlot);
            }
            else
            {
                string tagSlot = GetSlotFromTags(tags);
                if (tagSlot != null) return tagSlot;
                string jsonSlot = data.Value<string>("slot") ?? "mainHand";
                return SLOT_MAPPING.GetValueOrDefault(jsonSlot, jsonSlot);
            }
        }

        private static string GetSlotFromTags(List<string> tags)
        {
            // Simple tag-based slot inference (replaces SmithingTagProcessor dependency)
            if (tags == null || tags.Count == 0) return null;

            var tagSet = new HashSet<string>(tags, StringComparer.OrdinalIgnoreCase);
            if (tagSet.Contains("helmet") || tagSet.Contains("head")) return "helmet";
            if (tagSet.Contains("chestplate") || tagSet.Contains("chest")) return "chestplate";
            if (tagSet.Contains("leggings") || tagSet.Contains("legs")) return "leggings";
            if (tagSet.Contains("boots") || tagSet.Contains("feet")) return "boots";
            if (tagSet.Contains("gauntlets") || tagSet.Contains("hands")) return "gauntlets";
            if (tagSet.Contains("mainHand")) return "mainHand";
            if (tagSet.Contains("offHand")) return "offHand";
            if (tagSet.Contains("accessory")) return "accessory";
            return null;
        }

        private static string GetIconSubdir(string slot, string itemType, bool hasDamage)
        {
            if ((slot == "mainHand" || slot == "offHand") && hasDamage) return "weapons";
            if (slot is "helmet" or "chestplate" or "leggings" or "boots" or "gauntlets") return "armor";
            if (slot is "tool" or "axe" or "pickaxe" || itemType == "tool") return "tools";
            if (slot == "accessory" || itemType == "accessory") return "accessories";
            if (itemType == "station") return "stations";
            return "weapons";
        }

        private void CreatePlaceholders()
        {
            var placeholders = new[]
            {
                new JObject { ["itemId"] = "copper_sword", ["name"] = "Copper Sword", ["tier"] = 1, ["rarity"] = "common",
                    ["slot"] = "mainHand", ["category"] = "equipment",
                    ["stats"] = new JObject { ["damage"] = new JArray(8, 12), ["durability"] = new JArray(400, 400), ["attackSpeed"] = 1.0 } },
                new JObject { ["itemId"] = "iron_sword", ["name"] = "Iron Sword", ["tier"] = 2, ["rarity"] = "common",
                    ["slot"] = "mainHand", ["category"] = "equipment",
                    ["stats"] = new JObject { ["damage"] = new JArray(15, 22), ["durability"] = new JArray(600, 600), ["attackSpeed"] = 1.0 } },
                new JObject { ["itemId"] = "copper_helmet", ["name"] = "Copper Helmet", ["tier"] = 1, ["rarity"] = "common",
                    ["slot"] = "helmet", ["category"] = "equipment",
                    ["stats"] = new JObject { ["defense"] = 8, ["durability"] = new JArray(400, 400) } },
                new JObject { ["itemId"] = "copper_chestplate", ["name"] = "Copper Chestplate", ["tier"] = 1, ["rarity"] = "common",
                    ["slot"] = "chestplate", ["category"] = "equipment",
                    ["stats"] = new JObject { ["defense"] = 15, ["durability"] = new JArray(500, 500) } }
            };

            foreach (var ph in placeholders)
                Items[ph.Value<string>("itemId")] = ph;

            Loaded = true;
            JsonLoader.Log($"Created {Items.Count} placeholder equipment");
        }

        internal static void ResetInstance() => _instance = null;
    }
}
