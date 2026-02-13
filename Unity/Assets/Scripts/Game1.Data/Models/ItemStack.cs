// ============================================================================
// Game1.Data.Models.ItemStack
// Migrated from: entities/components/inventory.py (ItemStack, lines 10-107)
// Migration phase: 1 (FIX-1: Factory Method, FIX-6: Single Rarity Source)
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Data.Models
{
    /// <summary>
    /// Represents a stack of items in an inventory slot.
    ///
    /// FIX-1: Constructor is pure (no database lookups). Use CreateFromDatabase() factory
    /// for runtime creation that needs DB access.
    ///
    /// FIX-6: Rarity is computed from EquipmentData when present (single source of truth).
    /// </summary>
    public class ItemStack
    {
        public string ItemId { get; set; }
        public int Quantity { get; set; }
        public int MaxStack { get; set; }
        public EquipmentItem EquipmentData { get; set; }
        public Dictionary<string, object> CraftedStats { get; set; }

        private string _baseRarity;

        /// <summary>
        /// Computed rarity: delegates to equipment data if present (FIX-6 single source of truth).
        /// </summary>
        public string Rarity
        {
            get => EquipmentData != null ? EquipmentData.Rarity : _baseRarity;
            set => _baseRarity = value;
        }

        // ====================================================================
        // Constructor (pure, no side effects — FIX-1)
        // ====================================================================

        /// <summary>
        /// Pure constructor. No database lookups.
        /// For runtime creation that needs DB, use CreateFromDatabase().
        /// </summary>
        public ItemStack(string itemId, int quantity, int maxStack = 99,
                         EquipmentItem equipmentData = null, string rarity = "common",
                         Dictionary<string, object> craftedStats = null)
        {
            ItemId = itemId;
            Quantity = quantity;
            MaxStack = maxStack;
            EquipmentData = equipmentData;
            _baseRarity = rarity;
            CraftedStats = craftedStats;
        }

        // ====================================================================
        // Factory Method (FIX-1: Database lookups here, not in constructor)
        // ====================================================================

        /// <summary>
        /// Create an ItemStack with database lookups for max stack and equipment data.
        /// This is the equivalent of Python's ItemStack.__post_init__().
        /// </summary>
        public static ItemStack CreateFromDatabase(string itemId, int quantity)
        {
            int maxStack = 99;
            EquipmentItem equipData = null;
            string rarity = "common";

            // Try material database first
            var matDb = Game1.Data.Databases.MaterialDatabase.Instance;
            if (matDb.Loaded)
            {
                var mat = matDb.GetMaterial(itemId);
                if (mat != null)
                {
                    maxStack = mat.MaxStack;
                    rarity = mat.Rarity;
                }
            }

            // Check equipment database
            var equipDb = Game1.Data.Databases.EquipmentDatabase.Instance;
            if (equipDb.Loaded && equipDb.IsEquipment(itemId))
            {
                maxStack = 1;
                equipData = equipDb.CreateEquipmentFromId(itemId);
                if (equipData != null)
                {
                    rarity = equipData.Rarity;
                }
            }

            return new ItemStack(itemId, quantity, maxStack, equipData, rarity);
        }

        // ====================================================================
        // Stack Operations
        // ====================================================================

        /// <summary>Check if more items can be added to this stack.</summary>
        public bool CanAdd(int amount)
        {
            return Quantity + amount <= MaxStack;
        }

        /// <summary>
        /// Add items to this stack. Returns the overflow (items that couldn't fit).
        /// </summary>
        public int Add(int amount)
        {
            int space = MaxStack - Quantity;
            int added = Math.Min(space, amount);
            Quantity += added;
            return amount - added;
        }

        /// <summary>Check if this item is equipment.</summary>
        public bool IsEquipment()
        {
            return EquipmentData != null;
        }

        /// <summary>
        /// Check if this stack can merge with another stack.
        /// Same item, both not equipment, matching rarity and crafted stats.
        /// </summary>
        public bool CanStackWith(ItemStack other)
        {
            if (other == null) return false;
            if (ItemId != other.ItemId) return false;
            if (IsEquipment() || other.IsEquipment()) return false;
            if (Rarity != other.Rarity) return false;

            // Normalize null/empty crafted stats
            var selfStats = CraftedStats ?? new Dictionary<string, object>();
            var otherStats = other.CraftedStats ?? new Dictionary<string, object>();

            if (selfStats.Count != otherStats.Count) return false;
            foreach (var kvp in selfStats)
            {
                if (!otherStats.TryGetValue(kvp.Key, out var otherVal)) return false;
                if (!Equals(kvp.Value, otherVal)) return false;
            }

            return true;
        }

        public override string ToString()
        {
            return $"{ItemId} x{Quantity} ({Rarity})";
        }
    }
}
