// ============================================================================
// Game1.Data.Databases.TitleDatabase
// Migrated from: data/databases/title_db.py
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
    /// Singleton database for title definitions.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class TitleDatabase
    {
        private static TitleDatabase _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, TitleDefinition> _titles = new();

        public static TitleDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new TitleDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private TitleDatabase() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        public int Count => _titles.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>Load titles from a JSON file.</summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[TitleDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                JArray titles = wrapper["titles"] as JArray;
                if (titles == null)
                {
                    System.Diagnostics.Debug.WriteLine($"[TitleDatabase] No 'titles' array in {relativePath}");
                    return;
                }

                foreach (var token in titles)
                {
                    var title = token.ToObject<TitleDefinition>();
                    if (title != null && !string.IsNullOrEmpty(title.TitleId))
                    {
                        _titles[title.TitleId] = title;
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine($"[TitleDatabase] Loaded {_titles.Count} titles from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[TitleDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get a title by ID. Returns null if not found.</summary>
        public TitleDefinition GetTitle(string titleId)
        {
            if (string.IsNullOrEmpty(titleId)) return null;
            return _titles.TryGetValue(titleId, out var title) ? title : null;
        }

        /// <summary>All loaded titles as a read-only dictionary.</summary>
        public IReadOnlyDictionary<string, TitleDefinition> Titles => _titles;
    }
}
