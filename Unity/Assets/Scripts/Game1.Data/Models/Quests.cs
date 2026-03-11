// Game1.Data.Models.Quests
// Migrated from: data/models/quests.py (46 lines)
// Phase: 1 - Foundation
// Contains: QuestObjective, QuestRewards, QuestDefinition

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    [Serializable]
    public class QuestObjective
    {
        [JsonProperty("objectiveType")]
        public string ObjectiveType { get; set; }

        [JsonProperty("items")]
        public List<Dictionary<string, object>> Items { get; set; } = new();

        [JsonProperty("enemiesKilled")]
        public int EnemiesKilled { get; set; }
    }

    /// <summary>
    /// Comprehensive quest rewards - supports multiple reward types.
    /// </summary>
    [Serializable]
    public class QuestRewards
    {
        [JsonProperty("experience")]
        public int Experience { get; set; }

        [JsonProperty("gold")]
        public int Gold { get; set; }

        [JsonProperty("healthRestore")]
        public int HealthRestore { get; set; }

        [JsonProperty("manaRestore")]
        public int ManaRestore { get; set; }

        [JsonProperty("skills")]
        public List<string> Skills { get; set; } = new();

        [JsonProperty("items")]
        public List<Dictionary<string, object>> Items { get; set; } = new();

        [JsonProperty("title")]
        public string Title { get; set; } = "";

        [JsonProperty("statPoints")]
        public int StatPoints { get; set; }

        [JsonProperty("statusEffects")]
        public List<Dictionary<string, object>> StatusEffects { get; set; } = new();

        [JsonProperty("buffs")]
        public List<Dictionary<string, object>> Buffs { get; set; } = new();
    }

    /// <summary>
    /// Quest template from JSON. Pure data - no methods.
    /// </summary>
    [Serializable]
    public class QuestDefinition
    {
        [JsonProperty("questId")]
        public string QuestId { get; set; }

        [JsonProperty("title")]
        public string Title { get; set; }

        [JsonProperty("description")]
        public string Description { get; set; }

        [JsonProperty("npcId")]
        public string NpcId { get; set; }

        [JsonProperty("objectives")]
        public QuestObjective Objectives { get; set; }

        [JsonProperty("rewards")]
        public QuestRewards Rewards { get; set; }

        [JsonProperty("completionDialogue")]
        public List<string> CompletionDialogue { get; set; } = new();
    }
}
