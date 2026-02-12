// Game1.Entities.Components.Inventory
// Migrated from: entities/components/inventory.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Data.Databases;
using Game1.Data.Interfaces;
using Game1.Data.Models;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Represents a stack of items in an inventory slot.
    /// Equipment items always have max_stack = 1.
    /// Materials can stack up to their defined max_stack (default 99).
    /// </summary>
    [Serializable]
    public class ItemStack
    {
        public string ItemId { get; set; }
        public int Quantity { get; set; }
        public int MaxStack { get; set; } = 99;
        public EquipmentItem EquipmentData { get; set; }
        public string Rarity { get; set; } = "common";
        public CraftedStats CraftedStats { get; set; }

        public ItemStack() { }

        public ItemStack(string itemId, int quantity, int maxStack = 99,
            EquipmentItem equipmentData = null, string rarity = "common",
            CraftedStats craftedStats = null)
        {
            ItemId = itemId;
            Quantity = quantity;
            MaxStack = maxStack;
            EquipmentData = equipmentData;
            Rarity = rarity;
            CraftedStats = craftedStats;

            // Auto-detect max stack from material DB
            var matDb = MaterialDatabase.GetInstance();
            if (matDb.Loaded)
            {
                var mat = matDb.GetMaterial(itemId);
                if (mat != null)
                    MaxStack = mat.MaxStack;
            }

            // Equipment items don't stack
            var equipDb = EquipmentDatabase.GetInstance();
            if (equipDb.IsEquipment(itemId))
            {
                MaxStack = 1;
                if (EquipmentData == null)
                    EquipmentData = equipDb.CreateEquipmentFromId(itemId);
            }
        }

        public bool CanAdd(int amount) => Quantity + amount <= MaxStack;

        /// <summary>
        /// Add items to this stack. Returns remaining items that didn't fit.
        /// </summary>
        public int Add(int amount)
        {
            int space = MaxStack - Quantity;
            int added = Math.Min(space, amount);
            Quantity += added;
            return amount - added;
        }

        public bool IsEquipment()
        {
            if (EquipmentData != null) return true;
            return EquipmentDatabase.GetInstance().IsEquipment(ItemId);
        }

        public EquipmentItem GetEquipment()
        {
            if (EquipmentData != null) return EquipmentData;
            if (!EquipmentDatabase.GetInstance().IsEquipment(ItemId)) return null;
            return EquipmentDatabase.GetInstance().CreateEquipmentFromId(ItemId);
        }

        public MaterialDefinition GetMaterial()
        {
            return MaterialDatabase.GetInstance().GetMaterial(ItemId);
        }

        /// <summary>
        /// Check if this item can stack with another.
        /// Same item_id, both not equipment, same rarity, same crafted_stats.
        /// </summary>
        public bool CanStackWith(ItemStack other)
        {
            if (ItemId != other.ItemId) return false;
            if (IsEquipment() || other.IsEquipment()) return false;
            if (Rarity != other.Rarity) return false;

            // Check crafted stats compatibility
            bool selfEmpty = CraftedStats == null;
            bool otherEmpty = other.CraftedStats == null;
            if (selfEmpty && otherEmpty) return true;
            if (selfEmpty != otherEmpty) return false;

            // Both have crafted stats - must be identical (simplified comparison)
            return true; // Phase 3: deep comparison deferred to Phase 4 crafting integration
        }
    }

    /// <summary>
    /// Player inventory with slot-based item storage.
    /// Supports drag-and-drop, stacking, and item management.
    /// </summary>
    public class Inventory
    {
        public ItemStack[] Slots { get; set; }
        public int MaxSlots { get; }

        // Drag state (Phase 6 will use these for UI)
        public int? DraggingSlot { get; set; }
        public ItemStack DraggingStack { get; set; }
        public bool DraggingFromEquipment { get; set; }

        public Inventory(int maxSlots = 30)
        {
            MaxSlots = maxSlots;
            Slots = new ItemStack[maxSlots];
        }

        /// <summary>
        /// Add items to inventory. Returns true if all items were added.
        /// </summary>
        public bool AddItem(string itemId, int quantity,
            EquipmentItem equipmentInstance = null,
            string rarity = "common", CraftedStats craftedStats = null)
        {
            int remaining = quantity;
            var equipDb = EquipmentDatabase.GetInstance();

            // Equipment or provided equipment instance
            bool isEquip = equipmentInstance != null || equipDb.IsEquipment(itemId);

            if (isEquip)
            {
                for (int i = 0; i < quantity; i++)
                {
                    int? empty = GetEmptySlot();
                    if (empty == null) return false;

                    var equipData = equipmentInstance ?? equipDb.CreateEquipmentFromId(itemId);
                    if (equipData == null) return false;

                    Slots[empty.Value] = new ItemStack(itemId, 1, 1, equipData, rarity, craftedStats);
                }
                return true;
            }

            // Normal materials can stack
            var matDb = MaterialDatabase.GetInstance();
            var mat = matDb.GetMaterial(itemId);
            int maxStack = mat?.MaxStack ?? 99;

            // Create temp stack for stacking compatibility check
            var tempStack = new ItemStack(itemId, 1, maxStack, rarity: rarity, craftedStats: craftedStats);

            // Try to add to existing stacks
            for (int i = 0; i < MaxSlots && remaining > 0; i++)
            {
                if (Slots[i] != null && tempStack.CanStackWith(Slots[i]))
                    remaining = Slots[i].Add(remaining);
            }

            // Create new stacks for remaining
            while (remaining > 0)
            {
                int? empty = GetEmptySlot();
                if (empty == null) return false;

                int stackSize = Math.Min(remaining, maxStack);
                Slots[empty.Value] = new ItemStack(itemId, stackSize, maxStack, rarity: rarity, craftedStats: craftedStats);
                remaining -= stackSize;
            }

            return true;
        }

        public int? GetEmptySlot()
        {
            for (int i = 0; i < MaxSlots; i++)
            {
                if (Slots[i] == null) return i;
            }
            return null;
        }

        public int GetItemCount(string itemId)
        {
            return Slots.Where(s => s != null && s.ItemId == itemId).Sum(s => s.Quantity);
        }

        public bool HasItem(string itemId, int quantity = 1)
        {
            return GetItemCount(itemId) >= quantity;
        }

        /// <summary>
        /// Remove items from inventory. Returns true if successful.
        /// </summary>
        public bool RemoveItem(string itemId, int quantity = 1)
        {
            if (!HasItem(itemId, quantity)) return false;

            int remaining = quantity;
            for (int i = 0; i < MaxSlots && remaining > 0; i++)
            {
                if (Slots[i] != null && Slots[i].ItemId == itemId)
                {
                    if (Slots[i].Quantity <= remaining)
                    {
                        remaining -= Slots[i].Quantity;
                        Slots[i] = null;
                    }
                    else
                    {
                        Slots[i].Quantity -= remaining;
                        remaining = 0;
                    }
                }
            }

            return remaining == 0;
        }

        // Drag-and-drop operations (logic preserved, UI handled in Phase 6)
        public void StartDrag(int slotIndex)
        {
            if (slotIndex >= 0 && slotIndex < MaxSlots && Slots[slotIndex] != null)
            {
                DraggingSlot = slotIndex;
                DraggingStack = Slots[slotIndex];
                Slots[slotIndex] = null;
                DraggingFromEquipment = false;
            }
        }

        public void EndDrag(int targetSlot)
        {
            if (DraggingStack == null) return;

            if (targetSlot >= 0 && targetSlot < MaxSlots)
            {
                if (Slots[targetSlot] == null)
                {
                    Slots[targetSlot] = DraggingStack;
                }
                else if (DraggingStack.CanStackWith(Slots[targetSlot]))
                {
                    int overflow = Slots[targetSlot].Add(DraggingStack.Quantity);
                    if (overflow > 0 && DraggingSlot.HasValue)
                    {
                        DraggingStack.Quantity = overflow;
                        Slots[DraggingSlot.Value] = DraggingStack;
                    }
                }
                else
                {
                    // Swap
                    var temp = Slots[targetSlot];
                    Slots[targetSlot] = DraggingStack;
                    if (DraggingSlot.HasValue)
                        Slots[DraggingSlot.Value] = temp;
                }
            }
            else if (DraggingSlot.HasValue)
            {
                Slots[DraggingSlot.Value] = DraggingStack;
            }

            DraggingSlot = null;
            DraggingStack = null;
            DraggingFromEquipment = false;
        }

        public void CancelDrag()
        {
            if (DraggingStack != null && DraggingSlot.HasValue && !DraggingFromEquipment)
                Slots[DraggingSlot.Value] = DraggingStack;

            DraggingSlot = null;
            DraggingStack = null;
            DraggingFromEquipment = false;
        }
    }
}
