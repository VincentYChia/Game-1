// ============================================================================
// Game1.Data.Databases.ResourceNodeDatabase
// Migrated from: data/databases/ (resource node loading)
// Migration phase: 2
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Game1.Core;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Resource drop definition for a node.
    /// Handles both numeric and qualitative (string) quantity/chance from JSON.
    /// </summary>
    public class ResourceDrop
    {
        [JsonProperty("materialId")]
        public string MaterialId { get; set; }

        public int QuantityMin { get; set; } = 1;
        public int QuantityMax { get; set; } = 3;
        public float Chance { get; set; } = 1.0f;

        /// <summary>
        /// Custom quantity property: handles "many", "several", "few", "abundant" strings
        /// or numeric values from JSON.
        /// </summary>
        [JsonProperty("quantity")]
        public object QuantityRaw
        {
            set
            {
                if (value is string qs)
                {
                    (QuantityMin, QuantityMax) = qs.ToLowerInvariant() switch
                    {
                        "abundant" => (8, 12),
                        "many" => (5, 8),
                        "several" => (3, 5),
                        "few" => (1, 3),
                        _ => (1, 3),
                    };
                }
                else if (value is long lv)
                {
                    QuantityMin = (int)lv;
                    QuantityMax = (int)lv;
                }
            }
        }

        /// <summary>
        /// Custom chance property: handles "guaranteed", "high", "moderate", etc.
        /// or numeric values from JSON.
        /// </summary>
        [JsonProperty("chance")]
        public object ChanceRaw
        {
            set
            {
                if (value is string cs)
                {
                    Chance = cs.ToLowerInvariant() switch
                    {
                        "guaranteed" => 1.0f,
                        "high" => 0.75f,
                        "moderate" => 0.5f,
                        "low" => 0.25f,
                        "rare" => 0.10f,
                        "improbable" => 0.05f,
                        _ => 1.0f,
                    };
                }
                else if (value is double dv)
                {
                    Chance = (float)dv;
                }
            }
        }
    }

    /// <summary>
    /// Definition for a resource node that can be harvested.
    /// JSON properties match resource-node-1.JSON format.
    /// </summary>
    public class ResourceNodeDefinition
    {
        [JsonProperty("resourceId")]
        public string NodeId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; } = 1;

        [JsonProperty("category")]
        public string Category { get; set; }

        [JsonProperty("requiredTool")]
        public string ToolRequired { get; set; }

        [JsonProperty("baseHealth")]
        public int Health { get; set; } = 100;

        [JsonProperty("respawnTime")]
        public float RespawnTime { get; set; } = 60f;

        [JsonProperty("drops")]
        public List<ResourceDrop> Drops { get; set; } = new();

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }
    }

    /// <summary>
    /// Singleton database for resource node definitions.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class ResourceNodeDatabase
    {
        private static ResourceNodeDatabase _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, ResourceNodeDefinition> _nodes = new();

        public static ResourceNodeDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new ResourceNodeDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private ResourceNodeDatabase() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        public int Count => _nodes.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>Load resource nodes from a JSON file.</summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[ResourceNodeDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                JArray nodes = wrapper["resourceNodes"] as JArray
                            ?? wrapper["resources"] as JArray
                            ?? wrapper["nodes"] as JArray;

                if (nodes == null)
                {
                    System.Diagnostics.Debug.WriteLine($"[ResourceNodeDatabase] No recognized array in {relativePath}");
                    return;
                }

                foreach (var token in nodes)
                {
                    var node = token.ToObject<ResourceNodeDefinition>();
                    if (node != null && !string.IsNullOrEmpty(node.NodeId))
                    {
                        _nodes[node.NodeId] = node;
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine($"[ResourceNodeDatabase] Loaded {_nodes.Count} resource nodes from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[ResourceNodeDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get a resource node by ID. Returns null if not found.</summary>
        public ResourceNodeDefinition GetNode(string nodeId)
        {
            if (string.IsNullOrEmpty(nodeId)) return null;
            return _nodes.TryGetValue(nodeId, out var node) ? node : null;
        }

        /// <summary>Get all resource nodes for a given category and tier range.</summary>
        public List<ResourceNodeDefinition> GetResourcesForCategory(string category, int minTier = 1, int maxTier = 4)
        {
            var results = new List<ResourceNodeDefinition>();
            foreach (var node in _nodes.Values)
            {
                if (node.Category == category && node.Tier >= minTier && node.Tier <= maxTier)
                    results.Add(node);
            }
            return results;
        }

        /// <summary>All loaded nodes.</summary>
        public IReadOnlyDictionary<string, ResourceNodeDefinition> Nodes => _nodes;
    }
}
