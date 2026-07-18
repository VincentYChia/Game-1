using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/equipment_db.py at the LOADER level: stores raw
/// JSON dicts keyed by itemId, filtering to category == "equipment" only.
/// EquipmentItem materialization (create_equipment_from_id — weapon/armor/
/// durability formulas + SmithingTagProcessor slot inference) is Phase 2.
/// </summary>
public sealed class EquipmentDatabase
{
    public Dictionary<string, JsonObject> Items { get; } = new();
    public bool Loaded { get; private set; }

    // equipment_db.py:22-73 — all list sections except 'metadata';
    // itemId non-empty AND category == 'equipment'; raw dict stored (overwrite).
    public void LoadFromFile(string filepath)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        var count = 0;
        foreach (var kv in data)
        {
            if (kv.Key == "metadata" || kv.Value is not JsonArray items) continue;
            foreach (var node in items)
            {
                if (node is not JsonObject item) continue;
                var itemId = J.Str(item, "itemId");
                var category = J.Str(item, "category");
                if (!string.IsNullOrEmpty(itemId) && category == "equipment")
                {
                    Items[itemId] = (JsonObject)item.DeepClone();
                    count++;
                }
            }
        }
        if (count > 0) Loaded = true;
    }

    public bool IsEquipment(string itemId) => Items.ContainsKey(itemId);
}
