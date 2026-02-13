// ============================================================================
// Game1.Data.Databases.EquipmentDatabase
// Migrated from: data/databases/equipment_db.py
// Migration phase: 2
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;
using Game1.Core;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for equipment definitions.
    /// Stores raw JObjects for flexible equipment creation (supports crafted stats, etc.).
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class EquipmentDatabase
    {
        private static EquipmentDatabase _instance;
        private static readonly object _lock = new object();

        /// <summary>Raw JObject definitions keyed by item ID.</summary>
        private readonly Dictionary<string, JObject> _definitions = new();

        /// <summary>Set of known equipment IDs for fast lookup.</summary>
        private readonly HashSet<string> _equipmentIds = new();

        public static EquipmentDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new EquipmentDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private EquipmentDatabase() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        public int Count => _definitions.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>
        /// Load equipment definitions from a JSON file.
        /// Supports various formats: { "equipment": [...] }, { "items": [...] }, { "weapons": [...] }
        /// </summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[EquipmentDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                JArray items = wrapper["equipment"] as JArray
                            ?? wrapper["items"] as JArray
                            ?? wrapper["weapons"] as JArray
                            ?? wrapper["armor"] as JArray;

                if (items == null)
                {
                    System.Diagnostics.Debug.WriteLine($"[EquipmentDatabase] No equipment array in {relativePath}");
                    return;
                }

                int count = 0;
                foreach (var token in items)
                {
                    if (token is JObject obj)
                    {
                        string itemId = obj["itemId"]?.ToString()
                                     ?? obj["item_id"]?.ToString();
                        if (!string.IsNullOrEmpty(itemId))
                        {
                            _definitions[itemId] = obj;
                            _equipmentIds.Add(itemId);
                            count++;
                        }
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine($"[EquipmentDatabase] Loaded {count} equipment from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[EquipmentDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>
        /// Check if an item ID is a known equipment item.
        /// </summary>
        public bool IsEquipment(string itemId)
        {
            return !string.IsNullOrEmpty(itemId) && _equipmentIds.Contains(itemId);
        }

        /// <summary>
        /// Create a new EquipmentItem instance from a definition.
        /// Returns a fresh copy each time (equipment instances are mutable).
        /// Returns null if not found.
        /// </summary>
        public EquipmentItem CreateEquipmentFromId(string itemId)
        {
            if (string.IsNullOrEmpty(itemId))
            {
                System.Diagnostics.Debug.WriteLine("[EquipmentDatabase] CreateEquipmentFromId called with null/empty ID");
                return null;
            }

            if (!_definitions.TryGetValue(itemId, out var definition))
            {
                System.Diagnostics.Debug.WriteLine($"[EquipmentDatabase] Equipment not found: {itemId}");
                return null;
            }

            try
            {
                var item = definition.ToObject<EquipmentItem>();
                return item;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[EquipmentDatabase] Error creating equipment {itemId}: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Get the raw JObject definition for an equipment item.
        /// Useful for accessing fields not in the EquipmentItem model.
        /// </summary>
        public JObject GetRawDefinition(string itemId)
        {
            if (string.IsNullOrEmpty(itemId)) return null;
            return _definitions.TryGetValue(itemId, out var def) ? def : null;
        }

        /// <summary>Get all equipment IDs.</summary>
        public IReadOnlyCollection<string> AllEquipmentIds => _equipmentIds;
    }
}
