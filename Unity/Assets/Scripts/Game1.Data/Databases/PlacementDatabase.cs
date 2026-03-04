// ============================================================================
// Game1.Data.Databases.PlacementDatabase
// Migrated from: data/databases/placement_db.py
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
    /// Singleton database for crafting placement data.
    /// Loads from multiple placement JSON files (one per discipline).
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class PlacementDatabase
    {
        private static PlacementDatabase _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, PlacementData> _placements = new();

        public static PlacementDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new PlacementDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private PlacementDatabase() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        public int Count => _placements.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>Load all placement files. Returns total count loaded.</summary>
        public int LoadFromFiles()
        {
            string[] placementFiles = new[]
            {
                "placements.JSON/placements-smithing-1.json",
                "placements.JSON/placements-alchemy-1.JSON",
                "placements.JSON/placements-refining-1.JSON",
                "placements.JSON/placements-engineering-1.JSON",
                "placements.JSON/placements-adornments-1.JSON",
            };

            int total = 0;
            foreach (var file in placementFiles)
            {
                total += LoadFromFile(file);
            }

            Loaded = true;
            System.Diagnostics.Debug.WriteLine($"[PlacementDatabase] Total placements loaded: {_placements.Count}");
            return total;
        }

        /// <summary>Load placements from a single JSON file. Returns count loaded.</summary>
        public int LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[PlacementDatabase] File not found: {fullPath}");
                return 0;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                JArray placements = wrapper["placements"] as JArray;
                if (placements == null)
                {
                    System.Diagnostics.Debug.WriteLine($"[PlacementDatabase] No 'placements' array in {relativePath}");
                    return 0;
                }

                int count = 0;
                foreach (var token in placements)
                {
                    var placement = token.ToObject<PlacementData>();
                    if (placement != null && !string.IsNullOrEmpty(placement.RecipeId))
                    {
                        _placements[placement.RecipeId] = placement;
                        count++;
                    }
                }

                System.Diagnostics.Debug.WriteLine($"[PlacementDatabase] Loaded {count} placements from {relativePath}");
                return count;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[PlacementDatabase] Error loading {relativePath}: {ex.Message}");
                return 0;
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get placement data by recipe ID. Returns null if not found.</summary>
        public PlacementData GetPlacement(string recipeId)
        {
            if (string.IsNullOrEmpty(recipeId)) return null;
            return _placements.TryGetValue(recipeId, out var placement) ? placement : null;
        }

        /// <summary>Check if a placement exists for a recipe.</summary>
        public bool HasPlacement(string recipeId)
        {
            return !string.IsNullOrEmpty(recipeId) && _placements.ContainsKey(recipeId);
        }
    }
}
