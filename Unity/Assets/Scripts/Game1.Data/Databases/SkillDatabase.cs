// ============================================================================
// Game1.Data.Databases.SkillDatabase
// Migrated from: data/databases/skill_db.py (lines 1-80+)
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
    /// Singleton database for skill definitions.
    /// Includes translation tables for mana costs and cooldown strings.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class SkillDatabase
    {
        private static SkillDatabase _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, SkillDefinition> _skills = new();

        /// <summary>Text -> numeric mana cost translation. Matches Python: skill_db.py:15.</summary>
        public static readonly Dictionary<string, int> ManaCosts = new(StringComparer.OrdinalIgnoreCase)
        {
            ["low"] = 30,
            ["moderate"] = 60,
            ["high"] = 100,
            ["extreme"] = 150,
        };

        /// <summary>Text -> numeric cooldown (seconds) translation. Matches Python: skill_db.py:16.</summary>
        public static readonly Dictionary<string, float> Cooldowns = new(StringComparer.OrdinalIgnoreCase)
        {
            ["short"] = 120f,
            ["moderate"] = 300f,
            ["long"] = 600f,
            ["extreme"] = 1200f,
        };

        /// <summary>Text -> numeric duration (seconds) translation. Matches Python: skill_db.py:17.</summary>
        public static readonly Dictionary<string, float> Durations = new(StringComparer.OrdinalIgnoreCase)
        {
            ["instant"] = 0f,
            ["brief"] = 15f,
            ["moderate"] = 30f,
            ["long"] = 60f,
            ["extended"] = 120f,
        };

        public static SkillDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new SkillDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private SkillDatabase() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        public int Count => _skills.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>Load skills from a JSON file.</summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[SkillDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);
                var skillsArray = wrapper["skills"] as JArray;

                if (skillsArray == null)
                {
                    System.Diagnostics.Debug.WriteLine($"[SkillDatabase] No 'skills' array in {relativePath}");
                    return;
                }

                foreach (var token in skillsArray)
                {
                    try
                    {
                        var skill = token.ToObject<SkillDefinition>();
                        if (skill != null && !string.IsNullOrEmpty(skill.SkillId))
                        {
                            _skills[skill.SkillId] = skill;
                        }
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"[SkillDatabase] Error parsing skill: {ex.Message}");
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine($"[SkillDatabase] Loaded {_skills.Count} skills from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[SkillDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get a skill by ID. Returns null if not found.</summary>
        public SkillDefinition GetSkill(string skillId)
        {
            if (string.IsNullOrEmpty(skillId)) return null;
            return _skills.TryGetValue(skillId, out var skill) ? skill : null;
        }

        /// <summary>
        /// Resolve mana cost from a skill's cost value.
        /// Accepts string ("moderate" -> 60) or numeric (60 -> 60).
        /// </summary>
        public int GetManaCost(object costValue)
        {
            if (costValue == null) return 60;

            if (costValue is string str)
            {
                return ManaCosts.TryGetValue(str, out var cost) ? cost : 60;
            }

            try
            {
                return Convert.ToInt32(costValue);
            }
            catch
            {
                return 60;
            }
        }

        /// <summary>
        /// Resolve cooldown from a skill's cooldown value.
        /// Accepts string ("short" -> 120) or numeric (120 -> 120).
        /// </summary>
        public float GetCooldownSeconds(object cooldownValue)
        {
            if (cooldownValue == null) return 300f;

            if (cooldownValue is string str)
            {
                return Cooldowns.TryGetValue(str, out var cd) ? cd : 300f;
            }

            try
            {
                return Convert.ToSingle(cooldownValue);
            }
            catch
            {
                return 300f;
            }
        }

        /// <summary>
        /// Resolve duration from a skill's duration value.
        /// Accepts string ("brief" -> 15) or numeric (15 -> 15).
        /// </summary>
        public float GetDurationSeconds(object durationValue)
        {
            if (durationValue == null) return 0f;

            if (durationValue is string str)
            {
                return Durations.TryGetValue(str, out var dur) ? dur : 0f;
            }

            try
            {
                return Convert.ToSingle(durationValue);
            }
            catch
            {
                return 0f;
            }
        }

        /// <summary>All loaded skills as a read-only dictionary.</summary>
        public IReadOnlyDictionary<string, SkillDefinition> Skills => _skills;
    }
}
