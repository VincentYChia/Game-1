// ============================================================================
// Game1.Data.Databases.TranslationDatabase
// Migrated from: data/databases/translation_db.py
// Migration phase: 2
// Date: 2026-02-21
//
// Provides string translation for game terms, mana cost lookups,
// cooldown second values, and other text-to-value mappings.
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;
using Game1.Core;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for translations and string-to-value mappings.
    /// Provides mana cost and cooldown second lookups used by SkillDatabase.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class TranslationDatabase
    {
        private static TranslationDatabase _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, string> _translations = new(StringComparer.OrdinalIgnoreCase);

        public static TranslationDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new TranslationDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private TranslationDatabase()
        {
            // Initialize built-in mana cost and cooldown mappings
            // These match the Python translation_db.py hardcoded values
            InitializeDefaults();
        }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        // ====================================================================
        // Built-in Mappings (from Python translation_db.py)
        // ====================================================================

        /// <summary>
        /// Mana cost string to integer mapping.
        /// Matches Python: translation_db.py mana cost lookups.
        /// </summary>
        private static readonly Dictionary<string, int> _manaCosts = new(StringComparer.OrdinalIgnoreCase)
        {
            ["none"]      = 0,
            ["trivial"]   = 10,
            ["low"]       = 25,
            ["minor"]     = 30,
            ["moderate"]  = 60,
            ["major"]     = 100,
            ["high"]      = 120,
            ["extreme"]   = 200,
            ["ultimate"]  = 300,
        };

        /// <summary>
        /// Cooldown string to seconds mapping.
        /// Matches Python: translation_db.py cooldown lookups.
        /// </summary>
        private static readonly Dictionary<string, float> _cooldowns = new(StringComparer.OrdinalIgnoreCase)
        {
            ["none"]      = 0f,
            ["instant"]   = 0f,
            ["very_short"] = 30f,
            ["short"]     = 120f,
            ["medium"]    = 300f,
            ["long"]      = 600f,
            ["very_long"] = 900f,
            ["extreme"]   = 1800f,
        };

        private void InitializeDefaults()
        {
            Loaded = true;
        }

        // ====================================================================
        // Loading (optional additional translations from JSON)
        // ====================================================================

        /// <summary>
        /// Load additional translations from a JSON file.
        /// Format: { "translations": { "key": "value", ... } }
        /// </summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[TranslationDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                var translations = wrapper["translations"] as JObject;
                if (translations != null)
                {
                    foreach (var kvp in translations)
                    {
                        _translations[kvp.Key] = kvp.Value?.ToString() ?? "";
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine(
                    $"[TranslationDatabase] Loaded {_translations.Count} translations from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[TranslationDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>
        /// Get mana cost integer from a string value (e.g., "moderate" → 60).
        /// Returns 0 for unknown values.
        /// </summary>
        public int GetManaCost(string value)
        {
            if (string.IsNullOrEmpty(value)) return 0;
            return _manaCosts.TryGetValue(value, out var cost) ? cost : 0;
        }

        /// <summary>
        /// Get cooldown in seconds from a string value (e.g., "short" → 120f).
        /// Returns 0 for unknown values.
        /// </summary>
        public float GetCooldownSeconds(string value)
        {
            if (string.IsNullOrEmpty(value)) return 0f;
            return _cooldowns.TryGetValue(value, out var cd) ? cd : 0f;
        }

        /// <summary>
        /// Get a translated string. Returns the key itself if no translation found.
        /// </summary>
        public string Translate(string key)
        {
            if (string.IsNullOrEmpty(key)) return "";
            return _translations.TryGetValue(key, out var val) ? val : key;
        }

        /// <summary>
        /// Check if a translation key exists.
        /// </summary>
        public bool HasTranslation(string key)
        {
            return !string.IsNullOrEmpty(key) && _translations.ContainsKey(key);
        }
    }
}
