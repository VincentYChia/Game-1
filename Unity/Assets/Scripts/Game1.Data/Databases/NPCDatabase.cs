// Game1.Data.Databases.NPCDatabase
// Migrated from: data/databases/npc_db.py (147 lines)
// Phase: 2 - Data Layer
// Loads from progression/npcs-enhanced.JSON (fallback: npcs-1.JSON)
// and progression/quests-enhanced.JSON (fallback: quests-1.JSON).
// CRITICAL: Supports BOTH v1.0 and v2.0 JSON formats (dual-format).

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for NPCs and quests.
    /// Tries enhanced format first, falls back to v1.0 format.
    /// </summary>
    public class NPCDatabase
    {
        private static NPCDatabase _instance;
        private static readonly object _lock = new object();

        public Dictionary<string, NPCDefinition> NPCs { get; private set; }
        public Dictionary<string, QuestDefinition> Quests { get; private set; }
        public bool Loaded { get; private set; }

        public static NPCDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new NPCDatabase();
                }
            }
            return _instance;
        }

        private NPCDatabase()
        {
            NPCs = new Dictionary<string, NPCDefinition>();
            Quests = new Dictionary<string, QuestDefinition>();
        }

        public void LoadFromFiles()
        {
            try
            {
                // Try enhanced NPCs first, fallback to v1.0
                string[] npcFiles = { "progression/npcs-enhanced.JSON", "progression/npcs-1.JSON" };
                foreach (string file in npcFiles)
                {
                    string path = JsonLoader.GetContentPath(file);
                    if (System.IO.File.Exists(path))
                    {
                        LoadNPCs(path);
                        break;
                    }
                }

                // Try enhanced quests first, fallback to v1.0
                string[] questFiles = { "progression/quests-enhanced.JSON", "progression/quests-1.JSON" };
                foreach (string file in questFiles)
                {
                    string path = JsonLoader.GetContentPath(file);
                    if (System.IO.File.Exists(path))
                    {
                        LoadQuests(path);
                        break;
                    }
                }

                Loaded = true;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Failed to load NPCs/Quests: {ex.Message}");
            }
        }

        private void LoadNPCs(string filepath)
        {
            var data = JsonLoader.LoadRawJsonAbsolute(filepath);
            if (data?["npcs"] is not JArray npcsArr) return;

            foreach (JObject npcData in npcsArr)
            {
                // Parse position
                var posData = npcData["position"] as JObject;
                var position = new GamePosition(
                    posData?.Value<float?>("x") ?? 0,
                    posData?.Value<float?>("y") ?? 0,
                    posData?.Value<float?>("z") ?? 0
                );

                // Dialogue: support both old and enhanced format
                var dialogueLines = new List<string>();
                if (npcData["dialogue_lines"] is JArray dlArr)
                {
                    foreach (var l in dlArr) dialogueLines.Add(l.Value<string>());
                }
                else if (npcData["dialogue"] is JObject dialogueObj)
                {
                    if (dialogueObj["dialogue_lines"] is JArray dlArr2)
                    {
                        foreach (var l in dlArr2) dialogueLines.Add(l.Value<string>());
                    }
                    else
                    {
                        var greeting = dialogueObj["greeting"] as JObject;
                        dialogueLines.Add(greeting?.Value<string>("default") ?? "Hello!");
                        dialogueLines.Add(greeting?.Value<string>("questInProgress") ?? "How goes your task?");
                        dialogueLines.Add(greeting?.Value<string>("questComplete") ?? "Well done!");
                    }
                }

                // Interaction radius: support both old and behavior.interactionRange
                float interactionRadius = npcData.Value<float?>("interaction_radius") ?? 3.0f;
                if (npcData["behavior"] is JObject behavior)
                    interactionRadius = behavior.Value<float?>("interactionRange") ?? interactionRadius;

                // Sprite color
                var spriteColor = new[] { 0, 0, 0 };
                if (npcData["sprite_color"] is JArray colorArr && colorArr.Count >= 3)
                    spriteColor = new[] { colorArr[0].Value<int>(), colorArr[1].Value<int>(), colorArr[2].Value<int>() };

                // Quests
                var quests = new List<string>();
                if (npcData["quests"] is JArray questsArr)
                    foreach (var q in questsArr) quests.Add(q.Value<string>());

                var npcDef = new NPCDefinition
                {
                    NpcId = npcData.Value<string>("npc_id") ?? "",
                    Name = npcData.Value<string>("name") ?? "",
                    Position = position,
                    SpriteColor = spriteColor,
                    InteractionRadius = interactionRadius,
                    DialogueLines = dialogueLines,
                    Quests = quests
                };

                NPCs[npcDef.NpcId] = npcDef;
            }

            JsonLoader.Log($"Loaded {NPCs.Count} NPCs");
        }

        private void LoadQuests(string filepath)
        {
            var data = JsonLoader.LoadRawJsonAbsolute(filepath);
            if (data?["quests"] is not JArray questsArr) return;

            foreach (JObject questData in questsArr)
            {
                // Objectives (support both "type" and "objective_type")
                var objData = questData["objectives"] as JObject;
                string objType = objData?.Value<string>("type")
                    ?? objData?.Value<string>("objective_type") ?? "gather";

                var items = new List<Dictionary<string, object>>();
                if (objData?["items"] is JArray itemsArr)
                {
                    foreach (JObject item in itemsArr)
                    {
                        var dict = new Dictionary<string, object>();
                        foreach (var p in item.Properties())
                            dict[p.Name] = p.Value.ToObject<object>();
                        items.Add(dict);
                    }
                }

                var objective = new QuestObjective
                {
                    ObjectiveType = objType,
                    Items = items,
                    EnemiesKilled = objData?.Value<int?>("enemies_killed") ?? 0
                };

                // Rewards (support both formats)
                var rewData = questData["rewards"] as JObject;
                var skills = new List<string>();
                if (rewData?["skills"] is JArray skillsArr)
                    foreach (var s in skillsArr) skills.Add(s.Value<string>());

                var rewardItems = new List<Dictionary<string, object>>();
                if (rewData?["items"] is JArray riArr)
                {
                    foreach (JObject ri in riArr)
                    {
                        var dict = new Dictionary<string, object>();
                        foreach (var p in ri.Properties())
                            dict[p.Name] = p.Value.ToObject<object>();
                        rewardItems.Add(dict);
                    }
                }

                var rewards = new QuestRewards
                {
                    Experience = rewData?.Value<int?>("experience") ?? 0,
                    Gold = rewData?.Value<int?>("gold") ?? 0,
                    HealthRestore = rewData?.Value<int?>("health_restore") ?? 0,
                    ManaRestore = rewData?.Value<int?>("mana_restore") ?? 0,
                    Skills = skills,
                    Items = rewardItems,
                    Title = rewData?.Value<string>("title") ?? "",
                    StatPoints = rewData?.Value<int?>("statPoints") ?? rewData?.Value<int?>("stat_points") ?? 0
                };

                // Quest ID (support both "quest_id" and "questId")
                string questId = questData.Value<string>("quest_id")
                    ?? questData.Value<string>("questId") ?? "";

                // Title (support both "title" and "name")
                string title = questData.Value<string>("title")
                    ?? questData.Value<string>("name") ?? "Untitled Quest";

                // Description (support both simple string and complex dict)
                string description = "";
                var descToken = questData["description"];
                if (descToken?.Type == JTokenType.String)
                    description = descToken.Value<string>();
                else if (descToken is JObject descObj)
                    description = descObj.Value<string>("long") ?? descObj.Value<string>("short") ?? "";

                // NPC ID (support both "npc_id" and "givenBy")
                string npcId = questData.Value<string>("npc_id")
                    ?? questData.Value<string>("givenBy") ?? "";

                var completionDialogue = new List<string>();
                if (questData["completion_dialogue"] is JArray cdArr)
                    foreach (var l in cdArr) completionDialogue.Add(l.Value<string>());

                var questDef = new QuestDefinition
                {
                    QuestId = questId,
                    Title = title,
                    Description = description,
                    NpcId = npcId,
                    Objectives = objective,
                    Rewards = rewards,
                    CompletionDialogue = completionDialogue
                };

                Quests[questDef.QuestId] = questDef;
            }

            JsonLoader.Log($"Loaded {Quests.Count} quests");
        }

        internal static void ResetInstance() => _instance = null;
    }
}
