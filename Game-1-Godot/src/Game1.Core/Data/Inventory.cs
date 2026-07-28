using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of entities/components/inventory.py — ItemStack + Inventory (30 slots
/// default, stacking split by rarity + crafted_stats, equipment never stacks,
/// drag/merge/swap semantics). Python resolves databases via singletons; here
/// they are injected. The ITEM_ACQUIRED bus publish becomes an event hook.
/// Pinned by conformance/goldens/db_parity/inventory_buffs.json (scenarios
/// executed through the real Python classes with the booted databases).
/// </summary>
public sealed class ItemStack
{
    private readonly EquipmentDatabase? _equipDb;

    public string ItemId { get; }
    public int Quantity { get; set; }
    public int MaxStack { get; }
    public EquipmentItem? EquipmentData { get; }
    public string Rarity { get; }
    public JsonObject? CraftedStats { get; }

    // inventory.py:19-34 (__post_init__): material max_stack lookup; equipment
    // forces max_stack 1 + materializes equipment data
    public ItemStack(MaterialDatabase? matDb, EquipmentDatabase? equipDb,
                     string itemId, int quantity, int maxStack = 99,
                     EquipmentItem? equipmentData = null,
                     string rarity = "common", JsonObject? craftedStats = null)
    {
        _equipDb = equipDb;
        ItemId = itemId;
        Quantity = quantity;
        MaxStack = maxStack;
        EquipmentData = equipmentData;
        Rarity = rarity;
        CraftedStats = craftedStats;

        if (matDb is { Loaded: true } && matDb.GetMaterial(itemId) is { } mat)
            MaxStack = (int)mat.MaxStack;
        if (equipDb is not null && equipDb.IsEquipment(itemId))
        {
            MaxStack = 1;
            EquipmentData ??= equipDb.CreateEquipmentFromId(itemId);
        }
    }

    public int Add(int amount)
    {
        var space = MaxStack - Quantity;
        var added = Math.Min(space, amount);
        Quantity += added;
        return amount - added;
    }

    public bool IsEquipment() =>
        EquipmentData is not null || (_equipDb?.IsEquipment(ItemId) ?? false);

    // inventory.py:66-106 — same id, neither equipment, same rarity,
    // crafted_stats equal (null and empty are equivalent)
    public bool CanStackWith(ItemStack other)
    {
        if (ItemId != other.ItemId) return false;
        if (IsEquipment() || other.IsEquipment()) return false;
        if (Rarity != other.Rarity) return false;
        var mine = CraftedStats is { Count: > 0 } ? CraftedStats : new JsonObject();
        var theirs = other.CraftedStats is { Count: > 0 } ? other.CraftedStats : new JsonObject();
        return JsonNode.DeepEquals(mine, theirs);
    }
}

public sealed class Inventory
{
    private readonly MaterialDatabase _matDb;
    private readonly EquipmentDatabase _equipDb;

    public List<ItemStack?> Slots { get; }
    public int MaxSlots { get; }
    public int? DraggingSlot { get; private set; }
    public ItemStack? DraggingStack { get; private set; }

    /// <summary>Debug "ghost inventory" (F1): when on, the player is treated
    /// as holding an unlimited amount of every MATERIAL — GetItemCount reports
    /// a huge count and RecipeCrafting skips consumption — without using any
    /// visible slot. Off by default; never set in conformance.</summary>
    public bool DebugInfiniteMaterials;

    /// <summary>Replaces the ITEM_ACQUIRED GameEventBus publish (inventory.py:127-138).</summary>
    public event Action<string, int, string, string>? ItemAcquired;

    public Inventory(MaterialDatabase matDb, EquipmentDatabase equipDb, int maxSlots = 30)
    {
        _matDb = matDb;
        _equipDb = equipDb;
        MaxSlots = maxSlots;
        Slots = Enumerable.Repeat<ItemStack?>(null, maxSlots).ToList();
    }

    // inventory.py:117-175
    public bool AddItem(string itemId, int quantity,
                        EquipmentItem? equipmentInstance = null,
                        string rarity = "common", JsonObject? craftedStats = null)
    {
        var isEquip = equipmentInstance is not null || _equipDb.IsEquipment(itemId);
        ItemAcquired?.Invoke(itemId, quantity, isEquip ? "equipment" : "material", rarity);

        if (isEquip)
        {
            for (var i = 0; i < quantity; i++)
            {
                var empty = GetEmptySlot();
                if (empty is null) return false;
                var equipData = equipmentInstance ?? _equipDb.CreateEquipmentFromId(itemId);
                if (equipData is null) return false;
                Slots[empty.Value] = new ItemStack(_matDb, _equipDb, itemId, 1, 1,
                    equipData, rarity, craftedStats);
            }
            return true;
        }

        var remaining = quantity;
        var maxStack = _matDb.GetMaterial(itemId) is { } mat ? (int)mat.MaxStack : 99;
        var tempStack = new ItemStack(_matDb, _equipDb, itemId, 1, maxStack,
            rarity: rarity, craftedStats: craftedStats);

        foreach (var slot in Slots)
            if (slot is not null && remaining > 0 && tempStack.CanStackWith(slot))
                remaining = slot.Add(remaining);

        while (remaining > 0)
        {
            var empty = GetEmptySlot();
            if (empty is null) return false;
            var stackSize = Math.Min(remaining, maxStack);
            Slots[empty.Value] = new ItemStack(_matDb, _equipDb, itemId, stackSize,
                maxStack, rarity: rarity, craftedStats: craftedStats);
            remaining -= stackSize;
        }
        return true;
    }

    public int? GetEmptySlot()
    {
        for (var i = 0; i < Slots.Count; i++)
            if (Slots[i] is null)
                return i;
        return null;
    }

    public int GetItemCount(string itemId)
    {
        // Ghost inventory (F1 debug): unlimited of every material, no slots
        if (DebugInfiniteMaterials && _matDb.GetMaterial(itemId) is not null)
            return 999_999;
        return Slots.Where(s => s is not null && s.ItemId == itemId).Sum(s => s!.Quantity);
    }

    public bool HasItem(string itemId, int quantity = 1) =>
        GetItemCount(itemId) >= quantity;

    // inventory.py:186-191
    public void StartDrag(int slotIndex)
    {
        if (slotIndex >= 0 && slotIndex < MaxSlots && Slots[slotIndex] is not null)
        {
            DraggingSlot = slotIndex;
            DraggingStack = Slots[slotIndex];
            Slots[slotIndex] = null;
        }
    }

    // :193-215 — empty → place; stackable → merge (overflow returns to
    // origin); else swap; out-of-range → return to origin
    public void EndDrag(int targetSlot)
    {
        if (DraggingStack is null) return;
        if (targetSlot >= 0 && targetSlot < MaxSlots)
        {
            if (Slots[targetSlot] is null)
            {
                Slots[targetSlot] = DraggingStack;
            }
            else if (DraggingStack.CanStackWith(Slots[targetSlot]!))
            {
                var overflow = Slots[targetSlot]!.Add(DraggingStack.Quantity);
                if (overflow > 0)
                {
                    DraggingStack.Quantity = overflow;
                    Slots[DraggingSlot!.Value] = DraggingStack;
                }
            }
            else
            {
                var displaced = Slots[targetSlot];
                Slots[targetSlot] = DraggingStack;
                if (displaced is not null && DraggingSlot is not null)
                    Slots[DraggingSlot.Value] = displaced;
            }
        }
        else if (DraggingSlot is not null)
        {
            Slots[DraggingSlot.Value] = DraggingStack;
        }
        DraggingSlot = null;
        DraggingStack = null;
    }

    public void CancelDrag()
    {
        if (DraggingStack is not null && DraggingSlot is not null)
            Slots[DraggingSlot.Value] = DraggingStack;
        DraggingSlot = null;
        DraggingStack = null;
    }

    // :228-244
    public bool RemoveItem(string itemId, int quantity = 1)
    {
        if (!HasItem(itemId, quantity)) return false;
        var remaining = quantity;
        for (var i = 0; i < Slots.Count; i++)
        {
            var slot = Slots[i];
            if (slot is not null && slot.ItemId == itemId && remaining > 0)
            {
                if (slot.Quantity <= remaining)
                {
                    remaining -= slot.Quantity;
                    Slots[i] = null;
                }
                else
                {
                    slot.Quantity -= remaining;
                    remaining = 0;
                    break;
                }
            }
        }
        return remaining == 0;
    }
}
