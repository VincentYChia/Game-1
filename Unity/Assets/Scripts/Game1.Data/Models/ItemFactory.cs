// ============================================================================
// Game1.Data.Models.ItemFactory
// Migrated from: N/A (new architecture — FIX-13: Centralized ItemFactory)
// Migration phase: 1
// Date: 2026-02-21
//
// Single entry point for ALL item creation. Replaces 6 scattered creation
// sites in the Python codebase. Three creation paths:
//   1. CreateFromId — database lookup (for loot, crafting, shops)
//   2. FromSaveData — reconstruct from save dictionary (for load)
//   3. CreateCrafted — create with quality stats (for reward calculator)
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Databases;

namespace Game1.Data.Models
{
    /// <summary>
    /// Centralized factory for creating all item types.
    /// NEVER construct items directly — always go through ItemFactory.
    /// </summary>
    public static class ItemFactory
    {
        // ====================================================================
        // Path 1: Create from Database (loot, crafting, shops)
        // ====================================================================

        /// <summary>
        /// Create an IGameItem from its item ID by looking up the appropriate database.
        /// Returns null for unknown IDs. Equipment items are fresh copies.
        /// </summary>
        public static IGameItem CreateFromId(string itemId)
        {
            if (string.IsNullOrEmpty(itemId))
            {
                System.Diagnostics.Debug.WriteLine("[ItemFactory] CreateFromId called with null/empty ID");
                return null;
            }

            // Check equipment database first (returns a fresh copy each time)
            var equipDb = EquipmentDatabase.Instance;
            if (equipDb.Loaded && equipDb.IsEquipment(itemId))
            {
                return equipDb.CreateEquipmentFromId(itemId);
            }

            // Check material database
            var matDb = MaterialDatabase.Instance;
            if (matDb.Loaded)
            {
                var mat = matDb.GetMaterial(itemId);
                if (mat != null)
                {
                    // Distinguish placeables and consumables from generic materials
                    // by checking their itemType/placeable fields
                    if (mat.Placeable || mat.ItemType == "placeable" || mat.ItemType == "station")
                    {
                        return MaterialToPlaceable(mat);
                    }

                    if (mat.ItemType == "consumable" || mat.ItemType == "potion"
                        || mat.ItemSubtype == "potion" || mat.ItemSubtype == "food"
                        || mat.ItemSubtype == "scroll")
                    {
                        return MaterialToConsumable(mat);
                    }

                    // Default: return as material
                    return mat;
                }
            }

            System.Diagnostics.Debug.WriteLine($"[ItemFactory] Unknown item ID: {itemId}");
            return null;
        }

        /// <summary>
        /// Create an ItemStack from an item ID with the specified quantity.
        /// Convenience method combining CreateFromId with ItemStack construction.
        /// </summary>
        public static ItemStack CreateStack(string itemId, int quantity)
        {
            var item = CreateFromId(itemId);
            if (item == null) return null;

            return new ItemStack(
                itemId,
                quantity,
                item.MaxStack,
                item is EquipmentItem equip ? equip : null,
                item.Rarity
            );
        }

        // ====================================================================
        // Path 2: Reconstruct from Save Data (load game)
        // ====================================================================

        /// <summary>
        /// Reconstruct an IGameItem from save data dictionary.
        /// Dispatches on the "category" field to the correct concrete type.
        /// </summary>
        public static IGameItem FromSaveData(Dictionary<string, object> data)
        {
            if (data == null)
            {
                System.Diagnostics.Debug.WriteLine("[ItemFactory] FromSaveData called with null data");
                return null;
            }

            string category = "material";
            if (data.TryGetValue("category", out var catObj) && catObj != null)
            {
                category = catObj.ToString();
            }

            try
            {
                return category switch
                {
                    "equipment" => EquipmentItem.FromDict(data),
                    "consumable" => ConsumableItem.FromSaveData(data),
                    "placeable" => PlaceableItem.FromSaveData(data),
                    _ => MaterialDefinition.FromSaveData(data),
                };
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[ItemFactory] Error reconstructing {category} item from save data: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Reconstruct an ItemStack from save data dictionary.
        /// </summary>
        public static ItemStack StackFromSaveData(Dictionary<string, object> data)
        {
            if (data == null) return null;

            string itemId = data.TryGetValue("item_id", out var idObj) ? idObj?.ToString() : "";
            int quantity = data.TryGetValue("quantity", out var qtyObj) ? Convert.ToInt32(qtyObj) : 1;
            string rarity = data.TryGetValue("rarity", out var rarObj) ? rarObj?.ToString() : "common";
            int maxStack = data.TryGetValue("max_stack", out var msObj) ? Convert.ToInt32(msObj) : 99;

            EquipmentItem equipData = null;
            if (data.TryGetValue("equipment_data", out var equipObj)
                && equipObj is Dictionary<string, object> equipDict)
            {
                equipData = EquipmentItem.FromDict(equipDict);
            }

            Dictionary<string, object> craftedStats = null;
            if (data.TryGetValue("crafted_stats", out var csObj)
                && csObj is Dictionary<string, object> csDict)
            {
                craftedStats = csDict;
            }

            return new ItemStack(itemId, quantity, maxStack, equipData, rarity, craftedStats);
        }

        // ====================================================================
        // Path 3: Create Crafted Item (reward calculator)
        // ====================================================================

        /// <summary>
        /// Create an equipment item with quality stats from crafting.
        /// Used by RewardCalculator after a crafting minigame completes.
        /// </summary>
        public static EquipmentItem CreateCrafted(string itemId, CraftedStats stats)
        {
            var baseItem = CreateFromId(itemId) as EquipmentItem;
            if (baseItem == null)
            {
                System.Diagnostics.Debug.WriteLine($"[ItemFactory] CreateCrafted: {itemId} is not equipment");
                return null;
            }

            if (stats != null)
            {
                baseItem.Rarity = stats.Quality ?? baseItem.Rarity;
                baseItem.CraftedStats = stats.ToDict();

                // Apply crafted bonuses
                if (stats.BonusDamage > 0 && baseItem.DamageRange != null && baseItem.DamageRange.Length >= 2)
                {
                    baseItem.DamageRange[0] += stats.BonusDamage;
                    baseItem.DamageRange[1] += stats.BonusDamage;
                }
                if (stats.BonusDefense > 0)
                {
                    baseItem.Defense += stats.BonusDefense;
                }
                if (stats.BonusDurability > 0)
                {
                    baseItem.DurabilityMax += stats.BonusDurability;
                    baseItem.DurabilityCurrent = baseItem.DurabilityMax;
                }
                if (stats.BonusEfficiency > 0)
                {
                    baseItem.Efficiency += stats.BonusEfficiency;
                }
            }

            return baseItem;
        }

        // ====================================================================
        // Internal Helpers
        // ====================================================================

        /// <summary>
        /// Convert a MaterialDefinition flagged as placeable into a PlaceableItem.
        /// </summary>
        private static PlaceableItem MaterialToPlaceable(MaterialDefinition mat)
        {
            return new PlaceableItem
            {
                ItemId = mat.MaterialId,
                Name = mat.Name,
                Tier = mat.Tier,
                Rarity = mat.Rarity,
                Description = mat.Description,
                MaxStack = mat.MaxStack > 0 ? mat.MaxStack : 10,
                IconPath = mat.IconPath,
                PlaceableType = mat.ItemSubtype ?? "station",
                StationType = mat.ItemType ?? "",
                Tags = mat.Tags != null ? new List<string>(mat.Tags) : new(),
                EffectTags = mat.EffectTags != null ? new List<string>(mat.EffectTags) : new(),
                EffectParams = mat.EffectParams != null
                    ? new Dictionary<string, object>(mat.EffectParams) : new(),
            };
        }

        /// <summary>
        /// Convert a MaterialDefinition flagged as consumable into a ConsumableItem.
        /// </summary>
        private static ConsumableItem MaterialToConsumable(MaterialDefinition mat)
        {
            float duration = 0f;
            if (mat.EffectParams != null && mat.EffectParams.TryGetValue("duration", out var durObj))
            {
                duration = Convert.ToSingle(durObj);
            }

            float cooldown = 0f;
            if (mat.EffectParams != null && mat.EffectParams.TryGetValue("cooldown", out var cdObj))
            {
                cooldown = Convert.ToSingle(cdObj);
            }

            return new ConsumableItem
            {
                ItemId = mat.MaterialId,
                Name = mat.Name,
                Tier = mat.Tier,
                Rarity = mat.Rarity,
                Description = mat.Description,
                MaxStack = mat.MaxStack > 0 ? mat.MaxStack : 20,
                IconPath = mat.IconPath,
                EffectTags = mat.EffectTags != null ? new List<string>(mat.EffectTags) : new(),
                EffectParams = mat.EffectParams != null
                    ? new Dictionary<string, object>(mat.EffectParams) : new(),
                Duration = duration,
                Cooldown = cooldown,
                ItemSubtype = mat.ItemSubtype ?? "potion",
            };
        }
    }
}
