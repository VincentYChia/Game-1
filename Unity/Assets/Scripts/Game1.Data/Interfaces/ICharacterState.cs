// Game1.Data.Interfaces.ICharacterState
// Phase: 1 - Foundation
// Interface for unlock conditions to evaluate character state.
// Implemented by Character in Phase 3.

namespace Game1.Data.Interfaces
{
    /// <summary>
    /// Character state interface used by unlock conditions.
    /// Decouples Phase 1 data models from Phase 3 Character class.
    /// </summary>
    public interface ICharacterState : ICharacterStats
    {
        int GetActivityCount(string activityType);
        bool HasTitle(string titleId);
        bool HasSkill(string skillId);
        bool IsQuestCompleted(string questId);
        string CurrentClassId { get; }
        float GetStatTrackerValue(string statPath);
    }
}
