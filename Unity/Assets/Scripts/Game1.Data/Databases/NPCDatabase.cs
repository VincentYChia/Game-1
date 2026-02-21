// ============================================================================
// Game1.Data.Databases.NPCDatabase
// Migrated from: data/databases/npc_db.py
// Migration phase: 2
// Date: 2026-02-21
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
    /// Singleton database for NPC definitions.
    /// Loads from progression/npcs-1.JSON.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class NPCDatabase
    {
        private static NPCDatabase _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, NPCData> _npcs = new();
        private readonly Dictionary<string, QuestData> _quests = new();

        public static NPCDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new NPCDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private NPCDatabase() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }
        public int NPCCount => _npcs.Count;
        public int QuestCount => _quests.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>
        /// Load NPC definitions from a JSON file.
        /// Expected format: { "npcs": [ { "npcId": ..., "name": ..., ... } ] }
        /// </summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[NPCDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                var npcsArray = wrapper["npcs"] as JArray;
                if (npcsArray != null)
                {
                    foreach (var token in npcsArray)
                    {
                        var npc = token.ToObject<NPCData>();
                        if (npc != null && !string.IsNullOrEmpty(npc.NpcId))
                        {
                            _npcs[npc.NpcId] = npc;
                        }
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine($"[NPCDatabase] Loaded {_npcs.Count} NPCs from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[NPCDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        /// <summary>
        /// Load quest definitions from a JSON file.
        /// Expected format: { "quests": [ { "questId": ..., ... } ] }
        /// </summary>
        public void LoadQuestsFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[NPCDatabase] Quest file not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                var questsArray = wrapper["quests"] as JArray;
                if (questsArray != null)
                {
                    foreach (var token in questsArray)
                    {
                        var quest = token.ToObject<QuestData>();
                        if (quest != null && !string.IsNullOrEmpty(quest.QuestId))
                        {
                            _quests[quest.QuestId] = quest;
                        }
                    }
                }

                System.Diagnostics.Debug.WriteLine($"[NPCDatabase] Loaded {_quests.Count} quests from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[NPCDatabase] Error loading quests {relativePath}: {ex.Message}");
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get an NPC by ID. Returns null if not found.</summary>
        public NPCData GetNPC(string npcId)
        {
            if (string.IsNullOrEmpty(npcId)) return null;
            return _npcs.TryGetValue(npcId, out var npc) ? npc : null;
        }

        /// <summary>Get a quest by ID. Returns null if not found.</summary>
        public QuestData GetQuest(string questId)
        {
            if (string.IsNullOrEmpty(questId)) return null;
            return _quests.TryGetValue(questId, out var quest) ? quest : null;
        }

        /// <summary>Get all quests offered by a specific NPC.</summary>
        public List<QuestData> GetQuestsForNPC(string npcId)
        {
            var result = new List<QuestData>();
            foreach (var quest in _quests.Values)
            {
                if (quest.GiverId == npcId)
                    result.Add(quest);
            }
            return result;
        }

        /// <summary>Get all NPCs as a read-only dictionary.</summary>
        public IReadOnlyDictionary<string, NPCData> AllNPCs => _npcs;

        /// <summary>Get all quests as a read-only dictionary.</summary>
        public IReadOnlyDictionary<string, QuestData> AllQuests => _quests;
    }

    // ====================================================================
    // Data Classes
    // ====================================================================

    /// <summary>NPC definition loaded from JSON.</summary>
    public class NPCData
    {
        [JsonProperty("npcId")]
        public string NpcId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("role")]
        public string Role { get; set; } = "merchant";

        [JsonProperty("positionX")]
        public float PositionX { get; set; }

        [JsonProperty("positionZ")]
        public float PositionZ { get; set; }

        [JsonProperty("dialogue")]
        public List<string> Dialogue { get; set; } = new();

        [JsonProperty("shopItems")]
        public List<string> ShopItems { get; set; } = new();

        [JsonProperty("questIds")]
        public List<string> QuestIds { get; set; } = new();

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        [JsonProperty("interactionRadius")]
        public float InteractionRadius { get; set; } = 2.0f;
    }

    /// <summary>Quest definition loaded from JSON.</summary>
    public class QuestData
    {
        [JsonProperty("questId")]
        public string QuestId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("description")]
        public string Description { get; set; } = "";

        [JsonProperty("giverId")]
        public string GiverId { get; set; }

        [JsonProperty("objectives")]
        public List<QuestObjective> Objectives { get; set; } = new();

        [JsonProperty("rewards")]
        public QuestRewards Rewards { get; set; }

        [JsonProperty("levelRequirement")]
        public int LevelRequirement { get; set; } = 1;

        [JsonProperty("prerequisiteQuestId")]
        public string PrerequisiteQuestId { get; set; }
    }

    /// <summary>Individual quest objective.</summary>
    public class QuestObjective
    {
        [JsonProperty("type")]
        public string Type { get; set; } = "collect";

        [JsonProperty("targetId")]
        public string TargetId { get; set; }

        [JsonProperty("quantity")]
        public int Quantity { get; set; } = 1;

        [JsonProperty("description")]
        public string Description { get; set; } = "";
    }

    /// <summary>Quest rewards on completion.</summary>
    public class QuestRewards
    {
        [JsonProperty("experience")]
        public int Experience { get; set; }

        [JsonProperty("items")]
        public List<QuestRewardItem> Items { get; set; } = new();

        [JsonProperty("gold")]
        public int Gold { get; set; }

        [JsonProperty("titleId")]
        public string TitleId { get; set; }
    }

    /// <summary>Individual item reward.</summary>
    public class QuestRewardItem
    {
        [JsonProperty("itemId")]
        public string ItemId { get; set; }

        [JsonProperty("quantity")]
        public int Quantity { get; set; } = 1;
    }
}
