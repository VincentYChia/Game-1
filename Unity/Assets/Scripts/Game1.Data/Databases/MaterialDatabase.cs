// ============================================================================
// Game1.Data.Databases.MaterialDatabase
// Migrated from: data/databases/material_db.py
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
    /// Singleton database for material definitions.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class MaterialDatabase
    {
        private static MaterialDatabase _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, MaterialDefinition> _materials = new();

        public static MaterialDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new MaterialDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private MaterialDatabase() { }

        /// <summary>Reset singleton for testing only. Never call in production.</summary>
        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        /// <summary>Number of loaded materials.</summary>
        public int Count => _materials.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>
        /// Load materials from a JSON file.
        /// File format: { "materials": [ { materialId, name, tier, ... }, ... ] }
        /// </summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[MaterialDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                var materialsArray = wrapper["materials"] as JArray;
                if (materialsArray == null)
                {
                    System.Diagnostics.Debug.WriteLine($"[MaterialDatabase] No 'materials' array in {relativePath}");
                    return;
                }

                foreach (var token in materialsArray)
                {
                    var mat = token.ToObject<MaterialDefinition>();
                    if (mat != null && !string.IsNullOrEmpty(mat.MaterialId))
                    {
                        _materials[mat.MaterialId] = mat;
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine($"[MaterialDatabase] Loaded {_materials.Count} materials from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[MaterialDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        /// <summary>
        /// Load additional stackable items (refining, alchemy, engineering, tools).
        /// These files may use different JSON structures.
        /// </summary>
        public void LoadStackableItems(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[MaterialDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                // Try various array names
                JArray items = wrapper["materials"] as JArray
                            ?? wrapper["items"] as JArray
                            ?? wrapper["consumables"] as JArray;

                if (items == null)
                {
                    System.Diagnostics.Debug.WriteLine($"[MaterialDatabase] No recognized array in {relativePath}");
                    return;
                }

                int count = 0;
                foreach (var token in items)
                {
                    var mat = token.ToObject<MaterialDefinition>();
                    if (mat != null && !string.IsNullOrEmpty(mat.MaterialId))
                    {
                        if (!_materials.ContainsKey(mat.MaterialId))
                        {
                            _materials[mat.MaterialId] = mat;
                            count++;
                        }
                    }
                }

                System.Diagnostics.Debug.WriteLine($"[MaterialDatabase] Loaded {count} additional items from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[MaterialDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        /// <summary>Alias for LoadStackableItems for refining outputs.</summary>
        public void LoadRefiningItems(string relativePath) => LoadStackableItems(relativePath);

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>
        /// Get a material by ID. Returns null if not found (never throws).
        /// </summary>
        public MaterialDefinition GetMaterial(string materialId)
        {
            if (string.IsNullOrEmpty(materialId))
            {
                System.Diagnostics.Debug.WriteLine("[MaterialDatabase] GetMaterial called with null/empty ID");
                return null;
            }

            return _materials.TryGetValue(materialId, out var mat) ? mat : null;
        }

        /// <summary>Get all loaded materials as a read-only dictionary.</summary>
        public IReadOnlyDictionary<string, MaterialDefinition> Materials => _materials;

        /// <summary>Check if a material ID exists in the database.</summary>
        public bool HasMaterial(string materialId)
        {
            return !string.IsNullOrEmpty(materialId) && _materials.ContainsKey(materialId);
        }
    }
}
