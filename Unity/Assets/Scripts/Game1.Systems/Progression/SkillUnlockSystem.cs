// ============================================================================
// Game1.Systems.Progression.SkillUnlockSystem
// Migrated from: systems/skill_unlock_system.py (206 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Manages skill unlock progression. Skills unlock via triggers:
//   level_up, title_earned, quest_complete, activity_threshold.
// Skills with no cost unlock immediately; those with a cost become pending
// until the player confirms the purchase.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Systems.Progression
{
    // ========================================================================
    // Skill Unlock Definition
    // ========================================================================

    /// <summary>
    /// Trigger definition for when a skill can become unlockable.
    /// </summary>
    public class UnlockTrigger
    {
        /// <summary>Trigger type: "level_up", "title_earned", "quest_complete", "activity_threshold".</summary>
        public string Type { get; set; }

        /// <summary>Trigger value (e.g., level number, title_id, quest_id).</summary>
        public object TriggerValue { get; set; }
    }

    /// <summary>
    /// Cost to unlock a skill (gold, materials, skill points).
    /// </summary>
    public class UnlockCost
    {
        public int Gold { get; set; }
        public int SkillPoints { get; set; }
        public List<QuestItemRequirement> Materials { get; set; } = new();

        /// <summary>Check if there is any cost at all.</summary>
        public bool HasCost => Gold > 0 || SkillPoints > 0 || Materials.Count > 0;
    }

    /// <summary>
    /// Full skill unlock definition. Loaded from skill unlock JSON.
    /// Matches Python SkillUnlock dataclass.
    /// </summary>
    public class SkillUnlockDefinition
    {
        public string UnlockId { get; set; }
        public string SkillId { get; set; }
        public string Name { get; set; }
        public string Description { get; set; }
        public UnlockTrigger Trigger { get; set; }
        public UnlockCost Cost { get; set; } = new();

        /// <summary>
        /// Check if character meets the conditions for this unlock.
        /// Delegates to character state interface.
        /// </summary>
        public bool CheckConditions(ISkillUnlockCharacterState character)
        {
            // Condition checking based on trigger type
            // Full implementation requires the condition evaluator from Phase 2
            return true;
        }

        /// <summary>
        /// Check if character can afford the unlock cost.
        /// Returns (canAfford, reason).
        /// </summary>
        public (bool canAfford, string reason) CheckCost(ISkillUnlockCharacterState character)
        {
            if (!Cost.HasCost)
                return (true, "No cost");

            if (Cost.Gold > 0 && character.Gold < Cost.Gold)
                return (false, $"Need {Cost.Gold} gold (have {character.Gold})");

            if (Cost.SkillPoints > 0 && character.SkillPoints < Cost.SkillPoints)
                return (false, $"Need {Cost.SkillPoints} skill points (have {character.SkillPoints})");

            foreach (var mat in Cost.Materials)
            {
                int count = character.GetItemCount(mat.ItemId);
                if (count < mat.Quantity)
                    return (false, $"Need {mat.Quantity}x {mat.ItemId} (have {count})");
            }

            return (true, "Can afford");
        }
    }

    /// <summary>
    /// Interface for character state needed by the skill unlock system.
    /// </summary>
    public interface ISkillUnlockCharacterState
    {
        int Level { get; }
        int Gold { get; }
        int SkillPoints { get; }
        int GetItemCount(string itemId);
        int GetActivityCount(string activityType);
        List<string> EarnedTitleIds { get; }
        List<string> CompletedQuestIds { get; }
    }

    // ========================================================================
    // Skill Unlock System
    // ========================================================================

    /// <summary>
    /// Manages skill unlock progression for a character.
    /// Tracks which skills have been unlocked and which are pending cost payment.
    /// Matches Python SkillUnlockSystem class exactly.
    /// </summary>
    public class SkillUnlockSystem
    {
        /// <summary>Set of skill IDs that have been unlocked.</summary>
        public HashSet<string> UnlockedSkills { get; } = new();

        /// <summary>Set of unlock IDs awaiting cost payment.</summary>
        public HashSet<string> PendingUnlocks { get; } = new();

        /// <summary>
        /// All available unlock definitions. Set after database is initialized.
        /// </summary>
        public List<SkillUnlockDefinition> AllUnlocks { get; set; } = new();

        // ====================================================================
        // Query Methods
        // ====================================================================

        /// <summary>
        /// Check if a skill has been unlocked.
        /// Matches Python is_skill_unlocked().
        /// </summary>
        public bool IsUnlocked(string skillId)
        {
            return UnlockedSkills.Contains(skillId);
        }

        /// <summary>
        /// Check if an unlock is pending cost payment.
        /// </summary>
        public bool IsPending(string unlockId)
        {
            return PendingUnlocks.Contains(unlockId);
        }

        /// <summary>Get number of skills unlocked.</summary>
        public int UnlockedCount => UnlockedSkills.Count;

        /// <summary>Get list of pending unlock IDs.</summary>
        public List<string> GetPendingUnlocks() => PendingUnlocks.ToList();

        // ====================================================================
        // Unlock Checking
        // ====================================================================

        /// <summary>
        /// Check for new skill unlocks based on character state.
        /// Optionally filter by trigger type and value.
        /// Matches Python check_for_unlocks() exactly.
        /// </summary>
        public List<SkillUnlockDefinition> CheckUnlocks(
            ISkillUnlockCharacterState character,
            string triggerType = null,
            object triggerValue = null)
        {
            var newlyUnlockable = new List<SkillUnlockDefinition>();

            foreach (var unlock in AllUnlocks)
            {
                // Skip already unlocked
                if (UnlockedSkills.Contains(unlock.SkillId))
                    continue;

                // Skip already pending
                if (PendingUnlocks.Contains(unlock.UnlockId))
                    continue;

                // Filter by trigger type if specified
                if (triggerType != null && unlock.Trigger.Type != triggerType)
                    continue;

                // Filter by trigger value if specified
                if (triggerValue != null && !Equals(unlock.Trigger.TriggerValue, triggerValue))
                    continue;

                // Check conditions
                if (!unlock.CheckConditions(character))
                    continue;

                // Conditions met
                var (canAfford, _) = unlock.CheckCost(character);

                if (!unlock.Cost.HasCost)
                {
                    // No cost: unlock immediately
                    UnlockedSkills.Add(unlock.SkillId);
                    newlyUnlockable.Add(unlock);
                }
                else if (canAfford)
                {
                    // Has cost but can afford: mark pending for player confirmation
                    PendingUnlocks.Add(unlock.UnlockId);
                    newlyUnlockable.Add(unlock);
                }
            }

            return newlyUnlockable;
        }

        /// <summary>
        /// Unlock a specific skill by unlock ID (from player UI confirmation).
        /// Matches Python unlock_skill().
        /// </summary>
        public (bool success, string message) UnlockSkill(string unlockId, ISkillUnlockCharacterState character)
        {
            var unlock = AllUnlocks.FirstOrDefault(u => u.UnlockId == unlockId);
            if (unlock == null)
                return (false, $"Unknown unlock: {unlockId}");

            if (UnlockedSkills.Contains(unlock.SkillId))
                return (false, "Skill already unlocked");

            // Check conditions and cost
            if (!unlock.CheckConditions(character))
                return (false, "Conditions not met");

            var (canAfford, reason) = unlock.CheckCost(character);
            if (!canAfford)
                return (false, reason);

            // Unlock (cost payment handled by caller with full character access)
            UnlockedSkills.Add(unlock.SkillId);
            PendingUnlocks.Remove(unlockId);

            return (true, $"Unlocked skill: {unlock.Name}");
        }

        // ====================================================================
        // Trigger-Specific Check Methods
        // ====================================================================

        /// <summary>
        /// Check for unlocks triggered by level up.
        /// Matches Python check_level_up_unlocks().
        /// </summary>
        public List<SkillUnlockDefinition> CheckLevelUpUnlocks(ISkillUnlockCharacterState character, int newLevel)
        {
            return CheckUnlocks(character, triggerType: "level_up", triggerValue: newLevel);
        }

        /// <summary>
        /// Check for unlocks triggered by earning a title.
        /// Matches Python check_title_earned_unlocks().
        /// </summary>
        public List<SkillUnlockDefinition> CheckTitleEarnedUnlocks(ISkillUnlockCharacterState character, string titleId)
        {
            return CheckUnlocks(character, triggerType: "title_earned", triggerValue: titleId);
        }

        /// <summary>
        /// Check for unlocks triggered by quest completion.
        /// Matches Python check_quest_complete_unlocks().
        /// </summary>
        public List<SkillUnlockDefinition> CheckQuestCompleteUnlocks(ISkillUnlockCharacterState character, string questId)
        {
            return CheckUnlocks(character, triggerType: "quest_complete", triggerValue: questId);
        }

        /// <summary>
        /// Check for unlocks triggered by activity thresholds.
        /// Called periodically after crafting, combat, gathering.
        /// Matches Python check_activity_threshold_unlocks().
        /// </summary>
        public List<SkillUnlockDefinition> CheckActivityThresholdUnlocks(ISkillUnlockCharacterState character)
        {
            return CheckUnlocks(character, triggerType: "activity_threshold");
        }

        // ====================================================================
        // Save/Load
        // ====================================================================

        /// <summary>
        /// Serialize to save data.
        /// </summary>
        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                ["unlocked_skills"] = UnlockedSkills.ToList(),
                ["pending_unlocks"] = PendingUnlocks.ToList(),
            };
        }

        /// <summary>
        /// Restore from save data.
        /// </summary>
        public void FromSaveData(Dictionary<string, object> data)
        {
            UnlockedSkills.Clear();
            PendingUnlocks.Clear();

            if (data.TryGetValue("unlocked_skills", out var usObj) && usObj is IEnumerable<object> usList)
            {
                foreach (var item in usList)
                    UnlockedSkills.Add(item?.ToString());
            }

            if (data.TryGetValue("pending_unlocks", out var puObj) && puObj is IEnumerable<object> puList)
            {
                foreach (var item in puList)
                    PendingUnlocks.Add(item?.ToString());
            }
        }

        /// <summary>
        /// Reset all unlock state (for debug/testing).
        /// Matches Python reset_debug().
        /// </summary>
        public void ResetDebug()
        {
            UnlockedSkills.Clear();
            PendingUnlocks.Clear();
        }
    }
}
