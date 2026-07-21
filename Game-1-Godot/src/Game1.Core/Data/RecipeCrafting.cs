using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of recipe_db.py can_craft / consume_materials /
/// consume_materials_partial — the inventory-mutation core of crafting.
/// Quirk preserved: consume_materials builds a {matId: qty} dict from the
/// inputs, so DUPLICATE materialIds overwrite (last wins) while can_craft
/// checks each input row independently.
/// </summary>
public static class RecipeCrafting
{
    private static IEnumerable<(string MatId, int Qty)> InputRows(Recipe recipe)
    {
        if (recipe.Inputs is not JsonArray arr) yield break;
        foreach (var node in arr)
        {
            if (node is not JsonObject o) continue;
            var matId = J.Str(o, "materialId", "");
            if (matId.Length == 0)
                matId = J.Str(o, "itemId", "");
            yield return (matId, (int)J.Num(o, "quantity", 0));
        }
    }

    public static bool CanCraft(Recipe recipe, Inventory inventory)
    {
        foreach (var node in (recipe.Inputs as JsonArray) ?? new JsonArray())
        {
            if (node is not JsonObject o) continue;
            // can_craft reads materialId ONLY (no itemId fallback), like Python
            if (inventory.GetItemCount(J.Str(o, "materialId", ""))
                < (int)J.Num(o, "quantity", 0))
                return false;
        }
        return true;
    }

    /// <summary>Failure loss: int(qty * fraction) per input, best-effort
    /// slot sweep. Returns {matId: actually consumed}.</summary>
    public static Dictionary<string, int> ConsumeMaterialsPartial(
        Recipe recipe, Inventory inventory, double fraction)
    {
        fraction = Math.Max(0.0, Math.Min(1.0, fraction));
        var consumed = new Dictionary<string, int>();
        if (fraction <= 0.0) return consumed;

        foreach (var (matId, qty) in InputRows(recipe))
        {
            var loss = (int)(qty * fraction);
            if (matId.Length == 0 || loss <= 0) continue;
            var remaining = loss;
            for (var i = 0; i < inventory.Slots.Count; i++)
            {
                var slot = inventory.Slots[i];
                if (slot is not null && slot.ItemId == matId)
                {
                    var take = Math.Min(slot.Quantity, remaining);
                    slot.Quantity -= take;
                    remaining -= take;
                    if (slot.Quantity == 0)
                        inventory.Slots[i] = null;
                    if (remaining == 0)
                        break;
                }
            }
            if (loss - remaining > 0)
                consumed[matId] = loss - remaining;
        }
        return consumed;
    }

    public static bool ConsumeMaterials(Recipe recipe, Inventory inventory)
    {
        if (!CanCraft(recipe, inventory))
            return false;

        // dict build: duplicate materialIds OVERWRITE (Python quirk)
        var toConsume = new Dictionary<string, int>();
        var order = new List<string>();
        foreach (var node in (recipe.Inputs as JsonArray) ?? new JsonArray())
        {
            if (node is not JsonObject o) continue;
            var matId = J.Str(o, "materialId", "");
            if (!toConsume.ContainsKey(matId))
                order.Add(matId);
            toConsume[matId] = (int)J.Num(o, "quantity", 0);
        }

        foreach (var matId in order)
        {
            var remaining = toConsume[matId];
            for (var i = 0; i < inventory.Slots.Count; i++)
            {
                var slot = inventory.Slots[i];
                if (slot is not null && slot.ItemId == matId)
                {
                    if (slot.Quantity >= remaining)
                    {
                        slot.Quantity -= remaining;
                        if (slot.Quantity == 0)
                            inventory.Slots[i] = null;
                        remaining = 0;
                        break;
                    }
                    remaining -= slot.Quantity;
                    inventory.Slots[i] = null;
                }
            }
            if (remaining > 0)
                return false;
        }
        return true;
    }
}
