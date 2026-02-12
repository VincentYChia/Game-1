// Game1.Data.Models.SkillUnlocks
// Migrated from: data/models/skill_unlocks.py (182 lines)
// Phase: 1 - Foundation
// Contains: UnlockCost, UnlockTrigger, SkillUnlock
// Note: Methods referencing Character use object parameter, deferred to Phase 3.

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Cost to unlock a skill after conditions are met.
    /// </summary>
    [Serializable]
    public class UnlockCost
    {
        [JsonProperty("gold")]
        public int Gold { get; set; }

        [JsonProperty("materials")]
        public List<Dictionary<string, object>> Materials { get; set; } = new();

        [JsonProperty("skillPoints")]
        public int SkillPoints { get; set; }

        /// <summary>
        /// Check if character can afford the unlock cost.
        /// Uses object parameter; concrete Character checking deferred to Phase 3.
        /// </summary>
        public (bool CanAfford, string Reason) CanAfford(object character)
        {
            // Phase 3 will implement concrete Character-based checks:
            // - Gold check: character.Gold >= Gold
            // - Material check: character.Inventory.HasItem(matId, qty)
            // - Skill point check: character.SkillPoints >= SkillPoints
            return (true, "OK");
        }

        /// <summary>
        /// Pay the unlock cost. Returns true if successfully paid.
        /// Concrete implementation deferred to Phase 3.
        /// </summary>
        public bool Pay(object character)
        {
            var (canAfford, _) = CanAfford(character);
            if (!canAfford) return false;
            // Phase 3 will implement actual deduction
            return true;
        }
    }

    /// <summary>
    /// Defines when/how a skill unlock actually happens.
    /// </summary>
    [Serializable]
    public class UnlockTrigger
    {
        [JsonProperty("type")]
        public string Type { get; set; }

        [JsonProperty("triggerValue")]
        public object TriggerValue { get; set; }

        [JsonProperty("message")]
        public string Message { get; set; }
    }

    /// <summary>
    /// Defines how a skill becomes available to the player.
    /// Uses tag-driven UnlockRequirements for conditions.
    /// </summary>
    [Serializable]
    public class SkillUnlock
    {
        [JsonProperty("unlockId")]
        public string UnlockId { get; set; }

        [JsonProperty("skillId")]
        public string SkillId { get; set; }

        [JsonProperty("unlockMethod")]
        public string UnlockMethod { get; set; }

        [JsonProperty("requirements")]
        public UnlockRequirements Requirements { get; set; }

        [JsonProperty("trigger")]
        public UnlockTrigger Trigger { get; set; }

        [JsonProperty("cost")]
        public UnlockCost Cost { get; set; }

        [JsonProperty("narrative")]
        public string Narrative { get; set; } = "";

        [JsonProperty("category")]
        public string Category { get; set; } = "";

        /// <summary>
        /// Validate unlock definition. Throws if required fields are missing.
        /// </summary>
        public void Validate()
        {
            if (string.IsNullOrEmpty(UnlockId))
                throw new ArgumentException("unlockId is required");
            if (string.IsNullOrEmpty(SkillId))
                throw new ArgumentException("skillId is required");
            if (string.IsNullOrEmpty(UnlockMethod))
                throw new ArgumentException("unlockMethod is required");
        }

        public bool CheckConditions(object character) =>
            Requirements?.Evaluate(character) ?? true;

        public (bool CanAfford, string Reason) CheckCost(object character) =>
            Cost?.CanAfford(character) ?? (true, "OK");

        public (bool CanUnlock, string Reason) CanUnlock(object character)
        {
            if (!CheckConditions(character))
                return (false, "Conditions not met");

            var (canAfford, reason) = CheckCost(character);
            if (!canAfford) return (false, reason);

            return (true, "OK");
        }

        /// <summary>
        /// Unlock the skill for the character. Concrete implementation in Phase 3.
        /// </summary>
        public (bool Success, string Message) Unlock(object character)
        {
            var (canUnlock, reason) = CanUnlock(character);
            if (!canUnlock) return (false, reason);

            if (Cost != null && !Cost.Pay(character))
                return (false, "Failed to pay cost");

            // Phase 3 will add skill to character's SkillManager
            return (true, Trigger?.Message ?? "Skill unlocked!");
        }
    }
}
