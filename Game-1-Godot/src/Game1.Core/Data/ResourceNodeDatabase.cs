using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/resource_node_db.py. Sacred glob
/// Definitions.JSON/resource-node-*.JSON (Python uses [rR] char class for
/// POSIX; Windows matching is case-insensitive either way), generated
/// overlay second. Category caches preserve load order (spawn-pool order
/// is gameplay-relevant). ICON_NAME_MAP ports verbatim as the Godot asset
/// remap table.
/// </summary>
public sealed class ResourceNodeDatabase
{
    public Dictionary<string, ResourceNodeDefinition> Nodes { get; } = new();
    public List<ResourceNodeDefinition> Trees { get; } = new();
    public List<ResourceNodeDefinition> Ores { get; } = new();
    public List<ResourceNodeDefinition> Stones { get; } = new();
    public Dictionary<string, double> TierMap { get; } = new();
    public bool Loaded { get; private set; }

    // resource_node_db.py:25-57
    public static readonly IReadOnlyDictionary<string, string> IconNameMap =
        new Dictionary<string, string>
        {
            ["oak_tree"] = "oak_tree", ["pine_tree"] = "pine_tree",
            ["ash_tree"] = "ash_tree", ["birch_tree"] = "birch_tree",
            ["maple_tree"] = "maple_tree", ["ironwood_tree"] = "ironwood_tree",
            ["ebony_tree"] = "ebony_tree", ["worldtree_sapling"] = "worldtree_sapling",
            ["copper_vein"] = "copper_ore_node", ["iron_deposit"] = "iron_ore_node",
            ["tin_seam"] = "tin_seam", ["steel_node"] = "steel_ore_node",
            ["mithril_cache"] = "mithril_ore_node", ["adamantine_lode"] = "adamantine_lode",
            ["orichalcum_trove"] = "orichalcum_trove", ["etherion_nexus"] = "etherion_nexus",
            ["limestone_outcrop"] = "limestone_node", ["granite_formation"] = "granite_node",
            ["shale_bed"] = "shale_bed", ["basalt_column"] = "basalt_column",
            ["marble_quarry"] = "marble_quarry", ["quartz_cluster"] = "quartz_cluster",
            ["obsidian_flow"] = "obsidian_node", ["voidstone_shard"] = "voidstone_shard",
            ["diamond_geode"] = "diamond_geode", ["eternity_monolith"] = "eternity_monolith",
            ["primordial_formation"] = "primordial_formation",
            ["genesis_structure"] = "genesis_structure",
        };

    public void LoadFromFiles(string contentRoot)
    {
        Nodes.Clear(); Trees.Clear(); Ores.Clear(); Stones.Clear(); TierMap.Clear();
        var dir = Path.Combine(contentRoot, "Definitions.JSON");
        foreach (var path in J.GlobSorted(dir, "resource-node-*.JSON"))
        {
            if (Path.GetFileName(path).ToLowerInvariant().Contains("generated"))
                continue;
            LoadFromFile(path);
        }
        foreach (var path in J.GlobSorted(dir, "resource-node-generated-*.JSON"))
            LoadFromFile(path);
        Loaded = Nodes.Count > 0;
    }

    // resource_node_db.py:149-206
    public void LoadFromFile(string filepath)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        foreach (var node in J.Arr(data, "nodes"))
        {
            if (node is not JsonObject n) continue;
            var resourceId = J.Str(n, "resourceId");
            if (string.IsNullOrEmpty(resourceId)) continue;

            var drops = new List<ResourceDrop>();
            foreach (var dropNode in J.Arr(n, "drops"))
            {
                if (dropNode is not JsonObject d) continue;
                drops.Add(new ResourceDrop
                {
                    MaterialId = J.Str(d, "materialId"),
                    Quantity = J.Str(d, "quantity", "several"),
                    Chance = J.Str(d, "chance", "guaranteed"),
                });
            }

            var metadata = J.Obj(n, "metadata");
            var respawn = J.Str(n, "respawnTime", "");
            var hasRespawn = n.TryGetPropertyValue("respawnTime", out var respawnNode)
                             && respawnNode is not null;

            var def = new ResourceNodeDefinition
            {
                ResourceId = resourceId,
                Name = J.Str(n, "name"),
                Category = J.Str(n, "category"),
                Tier = J.Num(n, "tier", 1),
                RequiredTool = J.Str(n, "requiredTool", "pickaxe"),
                BaseHealth = J.Num(n, "baseHealth", 100),
                Drops = drops,
                RespawnTime = hasRespawn ? respawn : null,
                Tags = J.Node(metadata, "tags", () => new JsonArray()),
                Narrative = J.Str(metadata, "narrative"),
            };

            Nodes[resourceId] = def;
            TierMap[resourceId] = def.Tier;
            if (def.IsTree) Trees.Add(def);
            else if (def.IsOre) Ores.Add(def);
            else if (def.IsStone) Stones.Add(def);
        }
        Loaded = true;
    }

    public string GetIconName(string resourceId) =>
        IconNameMap.GetValueOrDefault(resourceId, resourceId);

    public string GetIconPath(string resourceId) =>
        $"resources/{GetIconName(resourceId)}.png";
}
