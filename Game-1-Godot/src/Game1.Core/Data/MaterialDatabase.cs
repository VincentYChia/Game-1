using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/material_db.py. Replays the sacred 7-file load
/// sequence + generated overlay. Parity-critical semantics preserved:
/// LoadFromFile OVERWRITES on id collision; LoadRefiningItems and
/// LoadStackableItems are FIRST-WINS; refining uses itemId + stackSize
/// default 256; description sources differ per loader. Placeholder fallback
/// is NOT ported (per contract doc 03: fail-fast in Godot; revisit in P2).
/// </summary>
public sealed class MaterialDatabase
{
    public Dictionary<string, MaterialDefinition> Materials { get; } = new();
    public bool Loaded { get; private set; }

    private static readonly (string Rel, string Method, string[]? Categories)[] SacredLoadSequence =
    {
        ("items.JSON/items-materials-1.JSON", "load_from_file", null),
        ("items.JSON/items-refining-1.JSON", "load_refining_items", null),
        ("items.JSON/items-alchemy-1.JSON", "load_stackable_items", new[] { "consumable" }),
        ("items.JSON/items-engineering-1.JSON", "load_stackable_items", new[] { "device" }),
        ("items.JSON/items-testing-tags.JSON", "load_stackable_items", new[] { "device", "weapon" }),
        ("items.JSON/items-smithing-2.JSON", "load_stackable_items", new[] { "station" }),
        ("Definitions.JSON/crafting-stations-1.JSON", "load_stackable_items", new[] { "station" }),
    };

    public const string GeneratedDir = "items.JSON";
    public const string GeneratedGlob = "items-materials-generated-*.JSON";

    public void LoadFromFiles(string contentRoot)
    {
        Materials.Clear();
        foreach (var (rel, method, categories) in SacredLoadSequence)
        {
            var path = Path.Combine(contentRoot, rel);
            if (!File.Exists(path)) continue;
            switch (method)
            {
                case "load_from_file": LoadFromFile(path); break;
                case "load_refining_items": LoadRefiningItems(path); break;
                case "load_stackable_items": LoadStackableItems(path, categories); break;
            }
        }
        foreach (var path in J.GlobSorted(Path.Combine(contentRoot, GeneratedDir), GeneratedGlob))
            LoadFromFile(path);
        Loaded = Materials.Count > 0;
    }

    private static string IconSubdir(string category) => category switch
    {
        "consumable" => "consumables",
        "device" => "devices",
        "station" => "stations",
        _ => "materials",
    };

    // material_db.py:132-182
    public void LoadFromFile(string filepath)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        foreach (var node in J.Arr(data, "materials"))
        {
            if (node is not JsonObject m) continue;
            var materialId = J.Str(m, "materialId");
            var category = J.Str(m, "category", "unknown");

            var iconPath = J.Str(m, "iconPath", "");
            if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(materialId))
                iconPath = $"{IconSubdir(category)}/{materialId}.png";

            var flags = J.Obj(m, "flags");
            var metadata = J.Obj(m, "metadata");
            var mat = new MaterialDefinition
            {
                MaterialId = materialId,
                Name = J.Str(m, "name"),
                Tier = J.Num(m, "tier", 1),
                Category = category,
                Rarity = J.Str(m, "rarity", "common"),
                Description = J.Str(m, "description"),
                MaxStack = J.Num(m, "maxStack", 99),
                // Pass-through fields keep the RAW node (Python .get()):
                // e.g. four alchemy consumables carry effectParams as an ARRAY
                Properties = J.Node(m, "properties", () => new JsonObject()),
                IconPath = string.IsNullOrEmpty(iconPath) ? null : iconPath,
                Placeable = J.Bool(flags, "placeable", false),
                ItemType = J.Str(m, "type"),
                ItemSubtype = J.Str(m, "subtype"),
                Effect = J.Str(m, "effect"),
                EffectTags = J.Node(m, "effectTags", () => new JsonArray()),
                EffectParams = J.Node(m, "effectParams", () => new JsonObject()),
                Narrative = J.Str(metadata, "narrative"),
                Tags = J.Node(metadata, "tags", () => new JsonArray()),
            };
            Materials[mat.MaterialId] = mat;  // OVERWRITE semantics (Python :175)
        }
        Loaded = true;
    }

    // material_db.py:208-248 — sections basic_ingots/alloys/wood_planks; itemId key
    public void LoadRefiningItems(string filepath)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        foreach (var section in new[] { "basic_ingots", "alloys", "wood_planks" })
        {
            if (!data.TryGetPropertyValue(section, out var sectionNode)
                || sectionNode is not JsonArray items) continue;
            foreach (var node in items)
            {
                if (node is not JsonObject m) continue;
                var materialId = J.Str(m, "itemId");
                var category = J.Str(m, "type", "unknown");

                var iconPath = J.Str(m, "iconPath", "");
                if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(materialId))
                    iconPath = $"materials/{materialId}.png";

                var metadata = J.Obj(m, "metadata");
                var narrative = J.Str(metadata, "narrative");
                var mat = new MaterialDefinition
                {
                    MaterialId = materialId,
                    Name = J.Str(m, "name"),
                    Tier = J.Num(m, "tier", 1),
                    Category = category,
                    Rarity = J.Str(m, "rarity", "common"),
                    Description = narrative,
                    MaxStack = J.Num(m, "stackSize", 256),
                    Properties = new JsonObject(),
                    IconPath = string.IsNullOrEmpty(iconPath) ? null : iconPath,
                    Narrative = narrative,
                    Tags = J.Node(metadata, "tags", () => new JsonArray()),
                };
                if (!string.IsNullOrEmpty(mat.MaterialId)
                    && !Materials.ContainsKey(mat.MaterialId))
                    Materials[mat.MaterialId] = mat;  // FIRST-WINS (Python :240)
            }
        }
    }

    // material_db.py:250-325 — all list sections except 'metadata'
    public void LoadStackableItems(string filepath, string[]? categories = null)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        foreach (var kv in data)
        {
            if (kv.Key == "metadata" || kv.Value is not JsonArray items) continue;
            foreach (var node in items)
            {
                if (node is not JsonObject m) continue;
                var category = J.Str(m, "category");
                var flags = J.Obj(m, "flags");
                var isStackable = J.Bool(flags, "stackable", false);
                var isPlaceable = J.Bool(flags, "placeable", false);

                var shouldLoad = (isStackable || isPlaceable)
                                 && (categories is null || categories.Contains(category));
                if (!shouldLoad) continue;

                var materialId = J.Str(m, "itemId");
                var iconPath = J.Str(m, "iconPath", "");
                if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(materialId))
                    iconPath = $"{IconSubdir(category)}/{materialId}.png";

                var metadata = J.Obj(m, "metadata");
                var narrative = J.Str(metadata, "narrative");
                var mat = new MaterialDefinition
                {
                    MaterialId = materialId,
                    Name = J.Str(m, "name"),
                    Tier = J.Num(m, "tier", 1),
                    Category = category,
                    Rarity = J.Str(m, "rarity", "common"),
                    Description = narrative,
                    MaxStack = J.Num(m, "stackSize", 99),
                    Properties = new JsonObject(),
                    IconPath = string.IsNullOrEmpty(iconPath) ? null : iconPath,
                    Placeable = isPlaceable,
                    ItemType = J.Str(m, "type"),
                    ItemSubtype = J.Str(m, "subtype"),
                    Effect = J.Str(m, "effect"),
                    EffectTags = J.Node(m, "effectTags", () => new JsonArray()),
                    EffectParams = J.Node(m, "effectParams", () => new JsonObject()),
                    Narrative = narrative,
                    Tags = J.Node(metadata, "tags", () => new JsonArray()),
                };
                if (!string.IsNullOrEmpty(mat.MaterialId)
                    && !Materials.ContainsKey(mat.MaterialId))
                    Materials[mat.MaterialId] = mat;  // FIRST-WINS (Python :317)
            }
        }
    }

    public MaterialDefinition? GetMaterial(string materialId) =>
        Materials.GetValueOrDefault(materialId);
}
