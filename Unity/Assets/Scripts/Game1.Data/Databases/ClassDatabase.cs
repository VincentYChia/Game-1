// ============================================================================
// Game1.Data.Databases.ClassDatabase
// Migrated from: data/databases/class_db.py
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
    /// Singleton database for character class definitions.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class ClassDatabase
    {
        private static ClassDatabase _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, ClassDefinition> _classes = new();

        public static ClassDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new ClassDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private ClassDatabase() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        public int Count => _classes.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>Load classes from a JSON file.</summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[ClassDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                JArray classes = wrapper["classes"] as JArray;
                if (classes == null)
                {
                    System.Diagnostics.Debug.WriteLine($"[ClassDatabase] No 'classes' array in {relativePath}");
                    return;
                }

                foreach (var token in classes)
                {
                    var classDef = token.ToObject<ClassDefinition>();
                    if (classDef != null && !string.IsNullOrEmpty(classDef.ClassId))
                    {
                        _classes[classDef.ClassId] = classDef;
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine($"[ClassDatabase] Loaded {_classes.Count} classes from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[ClassDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get a class by ID. Returns null if not found.</summary>
        public ClassDefinition GetClass(string classId)
        {
            if (string.IsNullOrEmpty(classId)) return null;
            return _classes.TryGetValue(classId, out var cls) ? cls : null;
        }

        /// <summary>All loaded classes as a read-only dictionary.</summary>
        public IReadOnlyDictionary<string, ClassDefinition> Classes => _classes;
    }
}
