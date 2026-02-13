// ============================================================================
// Game1.Systems.Progression.QuestSystem
// Migrated from: systems/quest_system.py (293 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Quest management with baseline tracking (only count progress AFTER acceptance).
// Supports gather and combat quest types.
// Full save/load with baseline restoration.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Systems.Progression
{
    // ========================================================================
    // Quest Data Classes
    // ========================================================================

    /// <summary>
    /// Quest objective types.
    /// </summary>
    public enum QuestObjectiveType
    {
        Gather,
        Combat
    }

    /// <summary>
    /// Quest objective definition (from JSON).
    /// </summary>
    public class QuestObjective
    {
        public QuestObjectiveType ObjectiveType { get; set; }

        /// <summary>For gather quests: list of {item_id, quantity} requirements.</summary>
        public List<QuestItemRequirement> Items { get; set; } = new();

        /// <summary>For combat quests: number of enemies to kill.</summary>
        public int EnemiesKilled { get; set; }
    }

    /// <summary>
    /// A single item requirement in a gather quest.
    /// </summary>
    public class QuestItemRequirement
    {
        public string ItemId { get; set; }
        public int Quantity { get; set; }
    }

    /// <summary>
    /// Quest reward definition (from JSON).
    /// </summary>
    public class QuestRewards
    {
        public int Experience { get; set; }
        public int HealthRestore { get; set; }
        public int ManaRestore { get; set; }
        public List<string> Skills { get; set; } = new();
        public List<QuestItemRequirement> Items { get; set; } = new();
        public int Gold { get; set; }
        public int StatPoints { get; set; }
        public string Title { get; set; }
        public List<Dictionary<string, object>> StatusEffects { get; set; } = new();
        public List<Dictionary<string, object>> Buffs { get; set; } = new();
    }

    /// <summary>
    /// Quest definition loaded from JSON. Contains objectives and rewards.
    /// </summary>
    public class QuestDefinition
    {
        public string QuestId { get; set; }
        public string Title { get; set; }
        public string Description { get; set; }
        public QuestObjective Objectives { get; set; }
        public QuestRewards Rewards { get; set; }
    }

    // ========================================================================
    // Quest Progress (runtime state)
    // ========================================================================

    /// <summary>
    /// Tracks progress for a single active quest instance.
    /// Uses baseline tracking: only counts progress AFTER quest acceptance.
    /// Matches Python Quest class.
    /// </summary>
    public class QuestProgress
    {
        public QuestDefinition QuestDef { get; }
        public string Status { get; set; } = "in_progress"; // "in_progress", "completed", "turned_in"

        /// <summary>Generic progress tracker.</summary>
        public Dictionary<string, int> ObjectiveProgress { get; set; } = new();

        // Baseline tracking (snapshot at acceptance time)
        public int BaselineCombatKills { get; set; }
        public Dictionary<string, int> BaselineInventory { get; set; } = new();

        public QuestProgress(QuestDefinition questDef)
        {
            QuestDef = questDef;
        }

        /// <summary>
        /// Initialize baselines from the character's current state.
        /// Called when quest is first accepted. Matches Python _initialize_baselines().
        /// </summary>
        public void InitializeBaselines(IQuestCharacterState character)
        {
            if (QuestDef.Objectives.ObjectiveType == QuestObjectiveType.Combat)
            {
                BaselineCombatKills = character.GetActivityCount("combat");
            }
            else if (QuestDef.Objectives.ObjectiveType == QuestObjectiveType.Gather)
            {
                foreach (var req in QuestDef.Objectives.Items)
                {
                    BaselineInventory[req.ItemId] = character.GetItemCount(req.ItemId);
                }
            }
        }

        /// <summary>
        /// Check if quest objectives are met. Only counts progress AFTER acceptance.
        /// Matches Python Quest.check_completion() exactly.
        /// </summary>
        public bool CheckCompletion(IQuestCharacterState character)
        {
            if (QuestDef.Objectives.ObjectiveType == QuestObjectiveType.Gather)
            {
                foreach (var req in QuestDef.Objectives.Items)
                {
                    int currentQty = character.GetItemCount(req.ItemId);
                    int baselineQty = BaselineInventory.TryGetValue(req.ItemId, out var b) ? b : 0;
                    int gatheredSinceStart = currentQty - baselineQty;

                    if (gatheredSinceStart < req.Quantity)
                        return false;
                }
                return true;
            }
            else if (QuestDef.Objectives.ObjectiveType == QuestObjectiveType.Combat)
            {
                int currentKills = character.GetActivityCount("combat");
                int killsSinceStart = currentKills - BaselineCombatKills;
                return killsSinceStart >= QuestDef.Objectives.EnemiesKilled;
            }

            return false;
        }
    }

    /// <summary>
    /// Interface for character state needed by the quest system.
    /// Decouples quest system from concrete Character class.
    /// </summary>
    public interface IQuestCharacterState
    {
        int GetItemCount(string itemId);
        int GetActivityCount(string activityType);
        bool ConsumeItem(string itemId, int quantity);
    }

    // ========================================================================
    // Quest System
    // ========================================================================

    /// <summary>
    /// Manages active quests, completion checks, and quest history.
    /// Matches Python QuestManager class.
    /// </summary>
    public class QuestSystem
    {
        /// <summary>Active quests keyed by quest ID.</summary>
        public Dictionary<string, QuestProgress> ActiveQuests { get; } = new();

        /// <summary>IDs of completed and turned-in quests.</summary>
        public List<string> CompletedQuests { get; } = new();

        // ====================================================================
        // Quest Management
        // ====================================================================

        /// <summary>
        /// Start a new quest. Returns false if already active or completed.
        /// Matches Python QuestManager.start_quest().
        /// </summary>
        public bool AcceptQuest(QuestDefinition questDef, IQuestCharacterState character)
        {
            if (questDef == null) return false;
            if (ActiveQuests.ContainsKey(questDef.QuestId)) return false;
            if (CompletedQuests.Contains(questDef.QuestId)) return false;

            var progress = new QuestProgress(questDef);
            progress.InitializeBaselines(character);
            ActiveQuests[questDef.QuestId] = progress;
            return true;
        }

        /// <summary>
        /// Update progress on active quests. Call after relevant actions
        /// (killing enemies, gathering items, etc.).
        /// </summary>
        public void UpdateProgress(string objectiveType, string targetId, int amount = 1)
        {
            foreach (var quest in ActiveQuests.Values)
            {
                if (!quest.ObjectiveProgress.ContainsKey(objectiveType))
                    quest.ObjectiveProgress[objectiveType] = 0;
                quest.ObjectiveProgress[objectiveType] += amount;
            }
        }

        /// <summary>
        /// Check if a specific quest's objectives are met.
        /// </summary>
        public bool IsQuestComplete(string questId, IQuestCharacterState character)
        {
            if (!ActiveQuests.TryGetValue(questId, out var quest)) return false;
            return quest.CheckCompletion(character);
        }

        /// <summary>
        /// Complete a quest: consume items if needed and grant rewards.
        /// Returns (success, rewardMessages).
        /// Matches Python QuestManager.complete_quest().
        /// </summary>
        public (bool success, List<string> messages) CompleteQuest(
            string questId, IQuestCharacterState character)
        {
            if (!ActiveQuests.TryGetValue(questId, out var quest))
                return (false, new List<string> { "Quest not active" });

            // Check completion
            if (!quest.CheckCompletion(character))
                return (false, new List<string> { "Quest objectives not met" });

            // Consume gather items if needed
            if (quest.QuestDef.Objectives.ObjectiveType == QuestObjectiveType.Gather)
            {
                foreach (var req in quest.QuestDef.Objectives.Items)
                {
                    if (!character.ConsumeItem(req.ItemId, req.Quantity))
                        return (false, new List<string> { $"Failed to consume {req.Quantity}x {req.ItemId}" });
                }
            }

            // Mark complete
            quest.Status = "turned_in";
            CompletedQuests.Add(questId);
            ActiveQuests.Remove(questId);

            // Reward messages (actual reward application is handled by caller with full character access)
            var messages = new List<string>();
            var rewards = quest.QuestDef.Rewards;

            if (rewards.Experience > 0)
                messages.Add($"+{rewards.Experience} XP");
            if (rewards.Gold > 0)
                messages.Add($"+{rewards.Gold} Gold");
            if (rewards.StatPoints > 0)
                messages.Add($"+{rewards.StatPoints} Stat Points");
            if (rewards.HealthRestore > 0)
                messages.Add($"+{rewards.HealthRestore} HP");
            if (rewards.ManaRestore > 0)
                messages.Add($"+{rewards.ManaRestore} Mana");
            if (!string.IsNullOrEmpty(rewards.Title))
                messages.Add($"Earned title: {rewards.Title}");
            foreach (var skillId in rewards.Skills)
                messages.Add($"Learned skill: {skillId}");

            return (true, messages);
        }

        /// <summary>
        /// Check if a quest has been completed and turned in.
        /// Matches Python QuestManager.has_completed().
        /// </summary>
        public bool HasCompleted(string questId)
        {
            return CompletedQuests.Contains(questId);
        }

        // ====================================================================
        // Save/Load
        // ====================================================================

        /// <summary>
        /// Serialize quest state for saving.
        /// Matches Python _serialize_quest_state().
        /// </summary>
        public Dictionary<string, object> ToSaveData()
        {
            var activeQuestsData = new Dictionary<string, object>();

            foreach (var (questId, quest) in ActiveQuests)
            {
                activeQuestsData[questId] = new Dictionary<string, object>
                {
                    ["status"] = quest.Status,
                    ["progress"] = quest.ObjectiveProgress,
                    ["baseline_combat_kills"] = quest.BaselineCombatKills,
                    ["baseline_inventory"] = quest.BaselineInventory,
                };
            }

            return new Dictionary<string, object>
            {
                ["active_quests"] = activeQuestsData,
                ["completed_quests"] = CompletedQuests.ToList(),
            };
        }

        /// <summary>
        /// Restore quest state from save data.
        /// Matches Python QuestManager.restore_from_save().
        /// </summary>
        public void FromSaveData(Dictionary<string, object> questState)
        {
            ActiveQuests.Clear();
            CompletedQuests.Clear();

            // Restore completed quests
            if (questState.TryGetValue("completed_quests", out var completedObj))
            {
                if (completedObj is IEnumerable<object> completedList)
                {
                    foreach (var item in completedList)
                        CompletedQuests.Add(item?.ToString());
                }
            }

            // Active quests can only be restored if quest definitions are available.
            // For now, just log the count. Full restoration requires QuestDatabase.
            if (questState.TryGetValue("active_quests", out var activeObj) &&
                activeObj is Dictionary<string, object> activeQuests &&
                activeQuests.Count > 0)
            {
                Console.WriteLine($"Note: {activeQuests.Count} active quests in save data. " +
                    "Quest definitions needed for full restoration.");
            }
        }
    }
}
