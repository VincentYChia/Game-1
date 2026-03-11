// Game1.Data.Databases.TranslationDatabase
// Migrated from: data/databases/translation_db.py (53 lines)
// Phase: 2 - Data Layer
// Manages skill translation tables (mana costs, cooldowns, durations, magnitudes).

using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Translation tables for converting human-readable text to numeric game values.
    /// Loads from Definitions.JSON/skills-translation-table.JSON.
    /// Falls back to hardcoded defaults on load failure.
    /// Note: SkillDatabase has its own canonical inline tables that include "extreme" entries.
    /// </summary>
    public class TranslationDatabase
    {
        private static TranslationDatabase _instance;
        private static readonly object _lock = new object();

        public Dictionary<string, float> MagnitudeValues { get; private set; }
        public Dictionary<string, float> DurationSeconds { get; private set; }
        public Dictionary<string, int> ManaCosts { get; private set; }
        public Dictionary<string, float> CooldownSeconds { get; private set; }
        public bool Loaded { get; private set; }

        public static TranslationDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new TranslationDatabase();
                }
            }
            return _instance;
        }

        private TranslationDatabase()
        {
            MagnitudeValues = new Dictionary<string, float>();
            DurationSeconds = new Dictionary<string, float>();
            ManaCosts = new Dictionary<string, int>();
            CooldownSeconds = new Dictionary<string, float>();
        }

        public void LoadFromFiles(string basePath = "")
        {
            var data = JsonLoader.LoadRawJson("Definitions.JSON/skills-translation-table.JSON");

            if (data != null)
            {
                try
                {
                    if (data["durationTranslations"] is JObject durations)
                    {
                        foreach (var prop in durations.Properties())
                        {
                            DurationSeconds[prop.Name] = prop.Value.Value<float>("seconds");
                        }
                    }

                    if (data["manaCostTranslations"] is JObject manaCosts)
                    {
                        foreach (var prop in manaCosts.Properties())
                        {
                            ManaCosts[prop.Name] = prop.Value.Value<int>("cost");
                        }
                    }

                    JsonLoader.Log("Loaded translations from skills-translation-table.JSON");
                    Loaded = true;
                    return;
                }
                catch (Exception ex)
                {
                    JsonLoader.LogWarning($"Error parsing translation table: {ex.Message}");
                }
            }

            CreateDefaults();
            Loaded = true;
        }

        private void CreateDefaults()
        {
            MagnitudeValues = new Dictionary<string, float>
            {
                { "minor", 0.5f },
                { "moderate", 1.0f },
                { "major", 2.0f },
                { "extreme", 4.0f }
            };

            DurationSeconds = new Dictionary<string, float>
            {
                { "instant", 0f },
                { "brief", 15f },
                { "moderate", 30f },
                { "long", 60f }
            };

            ManaCosts = new Dictionary<string, int>
            {
                { "low", 30 },
                { "moderate", 60 },
                { "high", 100 }
            };

            CooldownSeconds = new Dictionary<string, float>
            {
                { "short", 120f },
                { "moderate", 300f },
                { "long", 600f }
            };
        }

        internal static void ResetInstance() => _instance = null;
    }
}
