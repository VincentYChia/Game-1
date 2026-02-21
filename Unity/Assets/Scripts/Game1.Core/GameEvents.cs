// ============================================================================
// Game1.Core.GameEvents
// Migrated from: N/A (new architecture — MACRO-1)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System;

namespace Game1.Core
{
    /// <summary>
    /// Lightweight static event bus for component decoupling (MACRO-1).
    /// No Unity dependency. Components emit events instead of calling parent methods directly.
    ///
    /// Flow example:
    ///   EquipmentManager.Equip() -> GameEvents.RaiseEquipmentChanged(item, slot)
    ///     -> CharacterStats.OnEquipmentChanged()    (recalculates)
    ///     -> StatTracker.OnEquipmentChanged()        (records)
    ///     -> CombatManager.OnEquipmentChanged()      (updates damage cache)
    /// </summary>
    public static class GameEvents
    {
        // ====================================================================
        // Equipment Events
        // ====================================================================

        /// <summary>Raised when equipment is placed into a slot. Args: item, slot.</summary>
        public static event Action<object, int> OnEquipmentChanged;

        /// <summary>Raised when equipment is removed from a slot. Args: item, slot.</summary>
        public static event Action<object, int> OnEquipmentRemoved;

        public static void RaiseEquipmentChanged(object item, int slot)
            => OnEquipmentChanged?.Invoke(item, slot);

        public static void RaiseEquipmentRemoved(object item, int slot)
            => OnEquipmentRemoved?.Invoke(item, slot);

        // ====================================================================
        // Character Events
        // ====================================================================

        /// <summary>Raised when a character dies. Args: character.</summary>
        public static event Action<object> OnCharacterDied;

        /// <summary>Raised when a character levels up. Args: character, newLevel.</summary>
        public static event Action<object, int> OnLevelUp;

        /// <summary>Raised when a class is selected. Args: character, classId.</summary>
        public static event Action<object, string> OnClassSelected;

        /// <summary>Raised when a title is earned. Args: character, titleId.</summary>
        public static event Action<object, string> OnTitleEarned;

        public static void RaiseCharacterDied(object character)
            => OnCharacterDied?.Invoke(character);

        public static void RaiseLevelUp(object character, int newLevel)
            => OnLevelUp?.Invoke(character, newLevel);

        public static void RaiseClassSelected(object character, string classId)
            => OnClassSelected?.Invoke(character, classId);

        public static void RaiseTitleEarned(object character, string titleId)
            => OnTitleEarned?.Invoke(character, titleId);

        // ====================================================================
        // Combat Events
        // ====================================================================

        /// <summary>Raised when damage is dealt. Args: attacker, target, amount.</summary>
        public static event Action<object, object, float> OnDamageDealt;

        /// <summary>Raised when an enemy is killed. Args: enemy.</summary>
        public static event Action<object> OnEnemyKilled;

        public static void RaiseDamageDealt(object attacker, object target, float amount)
            => OnDamageDealt?.Invoke(attacker, target, amount);

        public static void RaiseEnemyKilled(object enemy)
            => OnEnemyKilled?.Invoke(enemy);

        // ====================================================================
        // Crafting Events
        // ====================================================================

        /// <summary>Raised when an item is crafted. Args: discipline, itemId.</summary>
        public static event Action<string, string> OnItemCrafted;

        public static void RaiseItemCrafted(string discipline, string itemId)
            => OnItemCrafted?.Invoke(discipline, itemId);

        // ====================================================================
        // Skill Events
        // ====================================================================

        /// <summary>Raised when a skill is learned. Args: skillId.</summary>
        public static event Action<string> OnSkillLearned;

        /// <summary>Raised when a skill is used. Args: skillId.</summary>
        public static event Action<string> OnSkillUsed;

        public static void RaiseSkillLearned(string skillId)
            => OnSkillLearned?.Invoke(skillId);

        public static void RaiseSkillUsed(string skillId)
            => OnSkillUsed?.Invoke(skillId);

        // ====================================================================
        // Buff Events
        // ====================================================================

        /// <summary>Raised when a buff is added or removed. Args: buffType, isAdded.</summary>
        public static event Action<string, bool> OnBuffChanged;

        public static void RaiseBuffChanged(string buffType, bool isAdded)
            => OnBuffChanged?.Invoke(buffType, isAdded);

        // ====================================================================
        // LLM / Invented Item Events (Phase 7)
        // ====================================================================

        /// <summary>Raised when an invented item is generated. Args: discipline, itemId, isStub.</summary>
        public static event Action<string, string, bool> OnItemInvented;

        /// <summary>Raised when LLM generation starts. Args: discipline.</summary>
        public static event Action<string> OnItemGenerationStarted;

        /// <summary>Raised when LLM generation completes. Args: discipline, success.</summary>
        public static event Action<string, bool> OnItemGenerationCompleted;

        public static void RaiseItemInvented(string discipline, string itemId, bool isStub)
            => OnItemInvented?.Invoke(discipline, itemId, isStub);

        public static void RaiseItemGenerationStarted(string discipline)
            => OnItemGenerationStarted?.Invoke(discipline);

        public static void RaiseItemGenerationCompleted(string discipline, bool success)
            => OnItemGenerationCompleted?.Invoke(discipline, success);

        // ====================================================================
        // Interaction Events
        // ====================================================================

        /// <summary>Raised when the player interacts with the world. Args: position, facing.</summary>
        public static event Action<object, string> OnPlayerInteracted;

        public static void RaisePlayerInteracted(object position, string facing)
            => OnPlayerInteracted?.Invoke(position, facing);

        // ====================================================================
        // Notification Events (Phase 7)
        // ====================================================================

        /// <summary>Raised when a notification is shown. Args: message, typeString.</summary>
        public static event Action<string, string> OnNotificationShown;

        public static void RaiseNotificationShown(string message, string typeString)
            => OnNotificationShown?.Invoke(message, typeString);

        // ====================================================================
        // Testing Support
        // ====================================================================

        /// <summary>
        /// Clear all event subscribers. Call in test teardown to prevent cross-test leaks.
        /// NEVER call in production code.
        /// </summary>
        public static void ClearAll()
        {
            OnEquipmentChanged = null;
            OnEquipmentRemoved = null;
            OnCharacterDied = null;
            OnLevelUp = null;
            OnClassSelected = null;
            OnTitleEarned = null;
            OnDamageDealt = null;
            OnEnemyKilled = null;
            OnItemCrafted = null;
            OnSkillLearned = null;
            OnSkillUsed = null;
            OnBuffChanged = null;
            OnItemInvented = null;
            OnItemGenerationStarted = null;
            OnItemGenerationCompleted = null;
            OnPlayerInteracted = null;
            OnNotificationShown = null;
        }
    }
}
