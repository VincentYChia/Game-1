// Game1.Data.Interfaces.ICharacterStats
// Phase: 1 - Foundation
// Minimal interface for EquipmentItem.CanEquip to avoid circular dependency with Character

namespace Game1.Data.Interfaces
{
    /// <summary>
    /// Minimal character stats interface used by equipment requirement checks.
    /// Decouples data models from the full Character class (Phase 3).
    /// </summary>
    public interface ICharacterStats
    {
        int Level { get; }
        int Strength { get; }
        int Defense { get; }
        int Vitality { get; }
        int Luck { get; }
        int Agility { get; }
        int Intelligence { get; }
    }
}
