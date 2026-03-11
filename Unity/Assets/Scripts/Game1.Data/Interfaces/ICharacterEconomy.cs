// Game1.Data.Interfaces.ICharacterEconomy
// Phase: 1 - Foundation
// Interface for skill unlock cost checks.
// Implemented by Character in Phase 3.

namespace Game1.Data.Interfaces
{
    /// <summary>
    /// Character economy interface used by UnlockCost.
    /// Provides gold, skill points, and inventory item checks.
    /// </summary>
    public interface ICharacterEconomy
    {
        int Gold { get; set; }
        int SkillPoints { get; set; }
        bool HasItem(string materialId, int quantity);
        void RemoveItem(string materialId, int quantity);
    }
}
