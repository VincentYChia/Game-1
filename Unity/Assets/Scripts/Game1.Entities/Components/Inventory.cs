// ============================================================================
// Game1.Entities.Components.Inventory
// Migrated from: entities/components/inventory.py (Inventory class, lines 109-231)
// Migration phase: 3 (MACRO-3: UI state separated, FIX-4: count cache)
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;
using Game1.Core;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Inventory component. Pure data operations only (MACRO-3: no UI state).
    /// FIX-4: Maintains a count cache for O(1) item count lookups.
    /// </summary>
    public class Inventory
    {
        private readonly ItemStack[] _slots;
        private readonly Dictionary<string, int> _countCache = new();

        public int MaxSlots { get; }

        public Inventory(int maxSlots = 30)
        {
            MaxSlots = maxSlots;
            _slots = new ItemStack[maxSlots];
        }

        // ====================================================================
        // Add / Remove (FIX-4: maintains count cache)
        // ====================================================================

        /// <summary>
        /// Add items to inventory. For equipment, pass the equipment instance.
        /// Returns true if all items were added.
        /// </summary>
        public bool AddItem(string itemId, int quantity, EquipmentItem equipmentInstance = null,
                           string rarity = "common", Dictionary<string, object> craftedStats = null)
        {
            bool isEquipment = equipmentInstance != null;

            // Check equipment database if no instance provided
            if (!isEquipment)
            {
                var equipDb = Game1.Data.Databases.EquipmentDatabase.Instance;
                if (equipDb.Loaded)
                    isEquipment = equipDb.IsEquipment(itemId);
            }

            if (isEquipment)
            {
                // Equipment items: one per slot
                for (int i = 0; i < quantity; i++)
                {
                    int empty = _getEmptySlot();
                    if (empty < 0) return false;

                    var equipData = equipmentInstance
                        ?? Game1.Data.Databases.EquipmentDatabase.Instance.CreateEquipmentFromId(itemId);
                    if (equipData == null) return false;

                    _slots[empty] = new ItemStack(itemId, 1, 1, equipData, rarity, craftedStats);
                    _updateCacheAdd(itemId, 1);
                }
                return true;
            }

            // Normal stackable items
            var matDb = Game1.Data.Databases.MaterialDatabase.Instance;
            int maxStack = matDb.Loaded ? (matDb.GetMaterial(itemId)?.MaxStack ?? 99) : 99;

            int remaining = quantity;

            // Try to add to existing stacks with matching properties
            for (int i = 0; i < _slots.Length && remaining > 0; i++)
            {
                var slot = _slots[i];
                if (slot != null && slot.ItemId == itemId && !slot.IsEquipment()
                    && slot.Rarity == rarity && slot.Quantity < slot.MaxStack)
                {
                    // Check crafted stats match
                    var slotStats = slot.CraftedStats ?? new Dictionary<string, object>();
                    var addStats = craftedStats ?? new Dictionary<string, object>();
                    if (_dictEquals(slotStats, addStats))
                    {
                        int overflow = slot.Add(remaining);
                        int added = remaining - overflow;
                        remaining = overflow;
                        _updateCacheAdd(itemId, added);
                    }
                }
            }

            // Create new stacks for remaining
            while (remaining > 0)
            {
                int empty = _getEmptySlot();
                if (empty < 0) return false;

                int stackSize = Math.Min(remaining, maxStack);
                _slots[empty] = new ItemStack(itemId, stackSize, maxStack, null, rarity, craftedStats);
                _updateCacheAdd(itemId, stackSize);
                remaining -= stackSize;
            }

            return true;
        }

        /// <summary>
        /// Remove quantity of item from inventory. Returns true if successful.
        /// </summary>
        public bool RemoveItem(string itemId, int quantity = 1)
        {
            if (GetItemCount(itemId) < quantity) return false;

            int remaining = quantity;
            for (int i = 0; i < _slots.Length && remaining > 0; i++)
            {
                var slot = _slots[i];
                if (slot != null && slot.ItemId == itemId)
                {
                    if (slot.Quantity <= remaining)
                    {
                        remaining -= slot.Quantity;
                        _updateCacheRemove(itemId, slot.Quantity);
                        _slots[i] = null;
                    }
                    else
                    {
                        slot.Quantity -= remaining;
                        _updateCacheRemove(itemId, remaining);
                        remaining = 0;
                    }
                }
            }

            return remaining == 0;
        }

        // ====================================================================
        // Queries (FIX-4: O(1) count lookups)
        // ====================================================================

        /// <summary>Check if inventory has at least quantity of item.</summary>
        public bool HasItem(string itemId, int quantity = 1)
        {
            return GetItemCount(itemId) >= quantity;
        }

        /// <summary>Get total quantity of an item across all slots. O(1) via cache.</summary>
        public int GetItemCount(string itemId)
        {
            return _countCache.TryGetValue(itemId, out int count) ? count : 0;
        }

        /// <summary>Get the item stack at a specific slot index. Returns null if empty.</summary>
        public ItemStack GetSlot(int index)
        {
            if (index < 0 || index >= _slots.Length) return null;
            return _slots[index];
        }

        /// <summary>Set the item stack at a specific slot index.</summary>
        public void SetSlot(int index, ItemStack stack)
        {
            if (index < 0 || index >= _slots.Length) return;

            // Remove old item from cache
            var old = _slots[index];
            if (old != null) _updateCacheRemove(old.ItemId, old.Quantity);

            _slots[index] = stack;

            // Add new item to cache
            if (stack != null) _updateCacheAdd(stack.ItemId, stack.Quantity);
        }

        /// <summary>Swap two inventory slots.</summary>
        public void SwapSlots(int a, int b)
        {
            if (a < 0 || a >= _slots.Length || b < 0 || b >= _slots.Length) return;
            (_slots[a], _slots[b]) = (_slots[b], _slots[a]);
            // Cache doesn't change on swap (same items, same counts)
        }

        /// <summary>Get all non-null slots as an array.</summary>
        public ItemStack[] GetAllSlots()
        {
            return (ItemStack[])_slots.Clone();
        }

        /// <summary>Get total number of occupied slots.</summary>
        public int OccupiedSlotCount
        {
            get
            {
                int count = 0;
                for (int i = 0; i < _slots.Length; i++)
                    if (_slots[i] != null) count++;
                return count;
            }
        }

        /// <summary>
        /// Rebuild the count cache from scratch.
        /// Call after bulk operations or save loading.
        /// </summary>
        public void RebuildCountCache()
        {
            _countCache.Clear();
            foreach (var slot in _slots)
            {
                if (slot != null)
                {
                    _countCache[slot.ItemId] = _countCache.GetValueOrDefault(slot.ItemId) + slot.Quantity;
                }
            }
        }

        // ====================================================================
        // Private Helpers
        // ====================================================================

        private int _getEmptySlot()
        {
            for (int i = 0; i < _slots.Length; i++)
                if (_slots[i] == null) return i;
            return -1;
        }

        private void _updateCacheAdd(string itemId, int qty)
        {
            _countCache[itemId] = _countCache.GetValueOrDefault(itemId) + qty;
        }

        private void _updateCacheRemove(string itemId, int qty)
        {
            if (_countCache.TryGetValue(itemId, out int current))
            {
                int newVal = current - qty;
                if (newVal <= 0)
                    _countCache.Remove(itemId);
                else
                    _countCache[itemId] = newVal;
            }
        }

        private static bool _dictEquals(Dictionary<string, object> a, Dictionary<string, object> b)
        {
            if (a.Count != b.Count) return false;
            foreach (var kvp in a)
            {
                if (!b.TryGetValue(kvp.Key, out var val)) return false;
                if (!Equals(kvp.Value, val)) return false;
            }
            return true;
        }
    }
}
