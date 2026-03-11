// Game1.Data.Databases.SkillUnlockDatabase
// Migrated from: data/databases/skill_unlock_db.py (138 lines)
// Phase: 2 - Data Layer
// Loads from progression/skill-unlocks.JSON.
// Uses ConditionFactory for parsing conditions.

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for skill unlock definitions.
    /// Indexed by both unlockId and skillId.
    /// </summary>
    public class SkillUnlockDatabase
    {
        private static SkillUnlockDatabase _instance;
        private static readonly object _lock = new object();

        public Dictionary<string, SkillUnlock> Unlocks { get; private set; }
        public Dictionary<string, SkillUnlock> UnlocksBySkill { get; private set; }
        public bool Loaded { get; private set; }

        public static SkillUnlockDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new SkillUnlockDatabase();
                }
            }
            return _instance;
        }

        private SkillUnlockDatabase()
        {
            Unlocks = new Dictionary<string, SkillUnlock>();
            UnlocksBySkill = new Dictionary<string, SkillUnlock>();
        }

        public void LoadFromFile(string filepath)
        {
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data == null) return;

                var unlocksArr = data["skillUnlocks"] as JArray;
                if (unlocksArr == null) return;

                foreach (JObject unlockData in unlocksArr)
                {
                    var unlock = ParseSkillUnlock(unlockData);
                    if (unlock != null)
                    {
                        Unlocks[unlock.UnlockId] = unlock;
                        UnlocksBySkill[unlock.SkillId] = unlock;
                    }
                }

                Loaded = true;
                JsonLoader.Log($"Loaded {Unlocks.Count} skill unlocks");
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading skill unlocks: {ex.Message}");
            }
        }

        private SkillUnlock ParseSkillUnlock(JObject data)
        {
            try
            {
                string unlockId = data.Value<string>("unlockId");
                string skillId = data.Value<string>("skillId");
                string unlockMethod = data.Value<string>("unlockMethod");

                if (string.IsNullOrEmpty(unlockId) || string.IsNullOrEmpty(skillId) ||
                    string.IsNullOrEmpty(unlockMethod))
                    return null;

                // Parse conditions using ConditionFactory
                var conditionsData = data["conditions"] as JArray;
                var prereqObj = new JObject();
                if (conditionsData != null)
                    prereqObj["conditions"] = conditionsData;
                var requirements = ConditionFactory.CreateRequirementsFromJson(prereqObj);

                // Parse trigger
                var triggerData = data["unlockTrigger"] as JObject;
                var trigger = new UnlockTrigger
                {
                    Type = triggerData?.Value<string>("type") ?? "unknown",
                    TriggerValue = triggerData?["triggerValue"]?.ToObject<object>(),
                    Message = triggerData?.Value<string>("message") ?? $"Unlocked {skillId}!"
                };

                // Parse cost
                var costData = data["cost"] as JObject;
                var cost = new UnlockCost
                {
                    Gold = costData?.Value<int?>("gold") ?? 0,
                    SkillPoints = costData?.Value<int?>("skillPoints") ?? 0
                };

                if (costData?["materials"] is JArray matArr)
                {
                    foreach (JObject m in matArr)
                    {
                        var matDict = new Dictionary<string, object>();
                        foreach (var p in m.Properties())
                            matDict[p.Name] = p.Value.ToObject<object>();
                        cost.Materials.Add(matDict);
                    }
                }

                // Parse metadata
                var metadata = data["metadata"] as JObject;
                string narrative = metadata?.Value<string>("narrative") ?? "";
                string category = metadata?.Value<string>("category") ?? "";

                return new SkillUnlock
                {
                    UnlockId = unlockId,
                    SkillId = skillId,
                    UnlockMethod = unlockMethod,
                    Requirements = requirements,
                    Trigger = trigger,
                    Cost = cost,
                    Narrative = narrative,
                    Category = category
                };
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error parsing skill unlock: {ex.Message}");
                return null;
            }
        }

        public SkillUnlock GetUnlock(string unlockId) =>
            Unlocks.TryGetValue(unlockId, out var u) ? u : null;

        public SkillUnlock GetUnlockForSkill(string skillId) =>
            UnlocksBySkill.TryGetValue(skillId, out var u) ? u : null;

        public List<SkillUnlock> GetUnlocksByMethod(string unlockMethod) =>
            Unlocks.Values.Where(u => u.UnlockMethod == unlockMethod).ToList();

        public List<SkillUnlock> GetUnlocksByTriggerType(string triggerType) =>
            Unlocks.Values.Where(u => u.Trigger?.Type == triggerType).ToList();

        public List<SkillUnlock> GetAllUnlocks() => Unlocks.Values.ToList();

        internal static void ResetInstance() => _instance = null;
    }
}
