// Game1.Data.Databases.ResourceNodeDatabase
// Migrated from: data/databases/resource_node_db.py (258 lines)
// Phase: 2 - Data Layer
// Loads from Definitions.JSON/Resource-node-1.JSON.
// CRITICAL: ICON_NAME_MAP must be preserved exactly (22+ entries).

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for resource node definitions.
    /// Provides cached category lists and icon name mapping.
    /// </summary>
    public class ResourceNodeDatabase
    {
        private static ResourceNodeDatabase _instance;
        private static readonly object _lock = new object();

        /// <summary>
        /// Icon name mapping: JSON resource_id -> actual PNG filename (without extension).
        /// Preserves compatibility with existing PNG files.
        /// </summary>
        public static readonly Dictionary<string, string> ICON_NAME_MAP = new()
        {
            // Trees - use resource_id directly
            { "oak_tree", "oak_tree" },
            { "pine_tree", "pine_tree" },
            { "ash_tree", "ash_tree" },
            { "birch_tree", "birch_tree" },
            { "maple_tree", "maple_tree" },
            { "ironwood_tree", "ironwood_tree" },
            { "ebony_tree", "ebony_tree" },
            { "worldtree_sapling", "worldtree_sapling" },
            // Ores - map new JSON IDs to existing PNG names
            { "copper_vein", "copper_ore_node" },
            { "iron_deposit", "iron_ore_node" },
            { "tin_seam", "tin_seam" },
            { "steel_node", "steel_ore_node" },
            { "mithril_cache", "mithril_ore_node" },
            { "adamantine_lode", "adamantine_lode" },
            { "orichalcum_trove", "orichalcum_trove" },
            { "etherion_nexus", "etherion_nexus" },
            // Stones - map new JSON IDs to existing PNG names
            { "limestone_outcrop", "limestone_node" },
            { "granite_formation", "granite_node" },
            { "shale_bed", "shale_bed" },
            { "basalt_column", "basalt_column" },
            { "marble_quarry", "marble_quarry" },
            { "quartz_cluster", "quartz_cluster" },
            { "obsidian_flow", "obsidian_node" },
            { "voidstone_shard", "voidstone_shard" },
            { "diamond_geode", "diamond_geode" },
            { "eternity_monolith", "eternity_monolith" },
            { "primordial_formation", "primordial_formation" },
            { "genesis_structure", "genesis_structure" }
        };

        public Dictionary<string, ResourceNodeDefinition> Nodes { get; private set; }
        public bool Loaded { get; private set; }

        private List<ResourceNodeDefinition> _trees;
        private List<ResourceNodeDefinition> _ores;
        private List<ResourceNodeDefinition> _stones;
        private Dictionary<string, int> _tierMap;

        public static ResourceNodeDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new ResourceNodeDatabase();
                }
            }
            return _instance;
        }

        private ResourceNodeDatabase()
        {
            Nodes = new Dictionary<string, ResourceNodeDefinition>();
            _trees = new List<ResourceNodeDefinition>();
            _ores = new List<ResourceNodeDefinition>();
            _stones = new List<ResourceNodeDefinition>();
            _tierMap = new Dictionary<string, int>();
        }

        public bool LoadFromFile(string filepath)
        {
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data == null)
                {
                    CreatePlaceholders();
                    return false;
                }

                var nodesArr = data["nodes"] as JArray;
                if (nodesArr == null)
                {
                    CreatePlaceholders();
                    return false;
                }

                foreach (JObject nodeData in nodesArr)
                {
                    string resourceId = nodeData.Value<string>("resourceId") ?? "";
                    if (string.IsNullOrEmpty(resourceId)) continue;

                    // Parse drops
                    var drops = new List<ResourceDrop>();
                    if (nodeData["drops"] is JArray dropsArr)
                    {
                        foreach (JObject dropData in dropsArr)
                        {
                            drops.Add(new ResourceDrop
                            {
                                MaterialId = dropData.Value<string>("materialId") ?? "",
                                Quantity = dropData.Value<string>("quantity") ?? "several",
                                Chance = dropData.Value<string>("chance") ?? "guaranteed"
                            });
                        }
                    }

                    // Parse metadata
                    var metadata = nodeData["metadata"] as JObject;
                    var tags = new List<string>();
                    if (metadata?["tags"] is JArray tagsArr)
                        foreach (var t in tagsArr) tags.Add(t.Value<string>());
                    string narrative = metadata?.Value<string>("narrative") ?? "";

                    var node = new ResourceNodeDefinition
                    {
                        ResourceId = resourceId,
                        Name = nodeData.Value<string>("name") ?? "",
                        Category = nodeData.Value<string>("category") ?? "",
                        Tier = nodeData.Value<int?>("tier") ?? 1,
                        RequiredTool = nodeData.Value<string>("requiredTool") ?? "pickaxe",
                        BaseHealth = nodeData.Value<int?>("baseHealth") ?? 100,
                        Drops = drops,
                        RespawnTime = nodeData.Value<string>("respawnTime"),
                        Tags = tags,
                        Narrative = narrative
                    };

                    Nodes[resourceId] = node;
                    _tierMap[resourceId] = node.Tier;

                    // Cache by category
                    if (node.IsTree) _trees.Add(node);
                    else if (node.IsOre) _ores.Add(node);
                    else if (node.IsStone) _stones.Add(node);
                }

                Loaded = true;
                JsonLoader.Log($"Loaded {Nodes.Count} resource nodes ({_trees.Count} trees, {_ores.Count} ores, {_stones.Count} stones)");
                return true;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading resource nodes: {ex.Message}");
                CreatePlaceholders();
                return false;
            }
        }

        private void CreatePlaceholders()
        {
            var placeholders = new (string Id, string Name, string Cat, int Tier, string Tool, int Health,
                (string MatId, string Qty, string Chance)[] Drops, string Respawn)[]
            {
                ("oak_tree", "Oak Tree", "tree", 1, "axe", 100, new[] { ("oak_log", "many", "guaranteed") }, "normal"),
                ("birch_tree", "Birch Tree", "tree", 2, "axe", 200, new[] { ("birch_log", "several", "guaranteed") }, "slow"),
                ("maple_tree", "Maple Tree", "tree", 2, "axe", 200, new[] { ("maple_log", "several", "high") }, "very_slow"),
                ("ironwood_tree", "Ironwood Tree", "tree", 3, "axe", 400, new[] { ("ironwood_log", "few", "high") }, "very_slow"),
                ("copper_vein", "Copper Vein", "ore", 1, "pickaxe", 100, new[] { ("copper_ore", "many", "guaranteed") }, null),
                ("iron_deposit", "Iron Deposit", "ore", 1, "pickaxe", 100, new[] { ("iron_ore", "many", "guaranteed") }, null),
                ("steel_node", "Steel Node", "ore", 2, "pickaxe", 200, new[] { ("steel_ore", "several", "guaranteed") }, null),
                ("mithril_cache", "Mithril Cache", "ore", 2, "pickaxe", 200, new[] { ("mithril_ore", "few", "high") }, null),
                ("limestone_outcrop", "Limestone Outcrop", "stone", 1, "pickaxe", 100, new[] { ("limestone", "abundant", "guaranteed") }, null),
                ("granite_formation", "Granite Formation", "stone", 1, "pickaxe", 100, new[] { ("granite", "abundant", "guaranteed") }, null),
                ("obsidian_flow", "Obsidian Flow", "stone", 3, "pickaxe", 400, new[] { ("obsidian", "several", "guaranteed") }, null)
            };

            foreach (var ph in placeholders)
            {
                var drops = new List<ResourceDrop>();
                foreach (var (matId, qty, chance) in ph.Drops)
                    drops.Add(new ResourceDrop { MaterialId = matId, Quantity = qty, Chance = chance });

                var node = new ResourceNodeDefinition
                {
                    ResourceId = ph.Id,
                    Name = ph.Name,
                    Category = ph.Cat,
                    Tier = ph.Tier,
                    RequiredTool = ph.Tool,
                    BaseHealth = ph.Health,
                    Drops = drops,
                    RespawnTime = ph.Respawn
                };

                Nodes[ph.Id] = node;
                _tierMap[ph.Id] = ph.Tier;
                if (node.IsTree) _trees.Add(node);
                else if (node.IsOre) _ores.Add(node);
                else if (node.IsStone) _stones.Add(node);
            }

            Loaded = true;
            JsonLoader.Log($"Created {Nodes.Count} placeholder resource nodes");
        }

        public ResourceNodeDefinition GetNode(string resourceId) =>
            Nodes.TryGetValue(resourceId, out var node) ? node : null;

        public int GetTier(string resourceId) =>
            _tierMap.TryGetValue(resourceId, out int tier) ? tier : 1;

        public List<ResourceNodeDefinition> GetAllTrees() => _trees;
        public List<ResourceNodeDefinition> GetAllOres() => _ores;
        public List<ResourceNodeDefinition> GetAllStones() => _stones;

        public List<ResourceNodeDefinition> GetTreesByTier(int maxTier) =>
            _trees.Where(t => t.Tier <= maxTier).ToList();

        public List<ResourceNodeDefinition> GetOresByTier(int maxTier) =>
            _ores.Where(o => o.Tier <= maxTier).ToList();

        public List<ResourceNodeDefinition> GetStonesByTier(int maxTier) =>
            _stones.Where(s => s.Tier <= maxTier).ToList();

        public List<ResourceNodeDefinition> GetResourcesForChunk(string chunkType, int tierMin, int tierMax)
        {
            List<ResourceNodeDefinition> candidates;
            if (chunkType.Contains("forest"))
                candidates = _trees;
            else if (chunkType.Contains("quarry"))
                candidates = _stones;
            else
                candidates = _ores;

            return candidates.Where(r => r.Tier >= tierMin && r.Tier <= tierMax).ToList();
        }

        public List<string> GetAllResourceIds() => Nodes.Keys.ToList();

        public Dictionary<string, int> BuildTierMap() => new Dictionary<string, int>(_tierMap);

        public string GetIconName(string resourceId) =>
            ICON_NAME_MAP.TryGetValue(resourceId, out var iconName) ? iconName : resourceId;

        public string GetIconPath(string resourceId) =>
            $"resources/{GetIconName(resourceId)}.png";

        internal static void ResetInstance() => _instance = null;
    }
}
