// Game1.Data.Models.ItemFactory
// Phase: 1 - Foundation
// Architecture Improvement: Centralized item creation (FIX-13, IMPROVEMENTS.md Part 4)
// Replaces 6 scattered creation sites with 1 entry point.
// Full database integration in Phase 2.

using System;
using System.Collections.Generic;
using Game1.Data.Interfaces;

namespace Game1.Data.Models
{
    /// <summary>
    /// Centralized factory for creating all game items.
    /// All item creation MUST go through this factory.
    /// Phase 1: Provides structure and FromSaveData.
    /// Phase 2: CreateFromId uses database lookups.
    /// </summary>
    public static class ItemFactory
    {
        /// <summary>
        /// Create an item from its ID by looking up the appropriate database.
        /// Phase 1 stub - full implementation in Phase 2 when databases are available.
        /// </summary>
        public static IGameItem CreateFromId(string itemId)
        {
            // Phase 2 will implement:
            // 1. Check MaterialDatabase for material items
            // 2. Check EquipmentDatabase for equipment items
            // 3. Check consumable/placeable categories
            // 4. Return appropriate typed IGameItem
            throw new NotImplementedException(
                $"ItemFactory.CreateFromId('{itemId}') requires database access (Phase 2)");
        }

        /// <summary>
        /// Reconstruct an item from save data. Dispatches on "category" field.
        /// </summary>
        public static IGameItem FromSaveData(Dictionary<string, object> data)
        {
            if (data == null) throw new ArgumentNullException(nameof(data));

            string category = data.TryGetValue("category", out var catObj)
                ? catObj?.ToString() ?? ""
                : "";

            return category switch
            {
                "material" => DeserializeMaterial(data),
                "equipment" => DeserializeEquipment(data),
                "consumable" => DeserializeConsumable(data),
                "placeable" => DeserializePlaceable(data),
                _ => throw new ArgumentException($"Unknown item category: '{category}'")
            };
        }

        /// <summary>
        /// Create a crafted item with quality and bonus stats.
        /// Phase 1 stub - full implementation in Phase 4 (crafting system).
        /// </summary>
        public static IGameItem CreateCrafted(string itemId, string quality, Dictionary<string, float> stats)
        {
            throw new NotImplementedException(
                $"ItemFactory.CreateCrafted requires crafting system (Phase 4)");
        }

        private static MaterialItem DeserializeMaterial(Dictionary<string, object> data)
        {
            return new MaterialItem
            {
                ItemId = data.TryGetValue("itemId", out var id) ? id?.ToString() : "",
                Name = data.TryGetValue("name", out var name) ? name?.ToString() : "",
                Tier = data.TryGetValue("tier", out var tier) ? Convert.ToInt32(tier) : 1,
                Rarity = data.TryGetValue("rarity", out var rarity) ? rarity?.ToString() : "common",
                MaterialCategory = data.TryGetValue("materialCategory", out var mc) ? mc?.ToString() : ""
            };
        }

        private static EquipmentItem DeserializeEquipment(Dictionary<string, object> data)
        {
            var item = new EquipmentItem
            {
                ItemId = data.TryGetValue("itemId", out var id) ? id?.ToString() : "",
                Name = data.TryGetValue("name", out var name) ? name?.ToString() : "",
                Tier = data.TryGetValue("tier", out var tier) ? Convert.ToInt32(tier) : 1,
                Rarity = data.TryGetValue("rarity", out var rarity) ? rarity?.ToString() : "common",
                Slot = data.TryGetValue("slot", out var slot) ? slot?.ToString() : "mainHand",
                Defense = data.TryGetValue("defense", out var def) ? Convert.ToInt32(def) : 0,
                DurabilityCurrent = data.TryGetValue("durabilityCurrent", out var dc) ? Convert.ToInt32(dc) : 100,
                DurabilityMax = data.TryGetValue("durabilityMax", out var dm) ? Convert.ToInt32(dm) : 100,
                HandType = data.TryGetValue("handType", out var ht) ? ht?.ToString() : "default",
                ItemType = data.TryGetValue("itemType", out var it) ? it?.ToString() : "weapon"
            };

            // Handle damage array
            if (data.TryGetValue("damage", out var damageObj))
            {
                if (damageObj is int[] dmgArr)
                    item.Damage = dmgArr;
                else if (damageObj is List<object> dmgList && dmgList.Count >= 2)
                    item.Damage = new[] { Convert.ToInt32(dmgList[0]), Convert.ToInt32(dmgList[1]) };
            }

            return item;
        }

        private static ConsumableItem DeserializeConsumable(Dictionary<string, object> data)
        {
            return new ConsumableItem
            {
                ItemId = data.TryGetValue("itemId", out var id) ? id?.ToString() : "",
                Name = data.TryGetValue("name", out var name) ? name?.ToString() : "",
                Tier = data.TryGetValue("tier", out var tier) ? Convert.ToInt32(tier) : 1,
                Rarity = data.TryGetValue("rarity", out var rarity) ? rarity?.ToString() : "common"
            };
        }

        private static PlaceableItem DeserializePlaceable(Dictionary<string, object> data)
        {
            return new PlaceableItem
            {
                ItemId = data.TryGetValue("itemId", out var id) ? id?.ToString() : "",
                Name = data.TryGetValue("name", out var name) ? name?.ToString() : "",
                Tier = data.TryGetValue("tier", out var tier) ? Convert.ToInt32(tier) : 1,
                Rarity = data.TryGetValue("rarity", out var rarity) ? rarity?.ToString() : "common",
                PlaceableType = data.TryGetValue("placeableType", out var pt) ? pt?.ToString() : "",
                StationTier = data.TryGetValue("stationTier", out var st) ? Convert.ToInt32(st) : 1
            };
        }
    }
}
