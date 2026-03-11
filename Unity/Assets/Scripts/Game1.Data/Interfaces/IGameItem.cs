// Game1.Data.Interfaces.IGameItem
// Phase: 1 - Foundation
// Architecture Improvement: Type-safe item hierarchy replacing dict-based items
// See: IMPROVEMENTS.md Part 4

using System.Collections.Generic;

namespace Game1.Data.Interfaces
{
    /// <summary>
    /// Common interface for all item types in the game.
    /// Every item that can exist in inventory implements this.
    /// Categories: "material", "equipment", "consumable", "placeable"
    /// </summary>
    public interface IGameItem
    {
        string ItemId { get; }
        string Name { get; }
        string Category { get; }
        int Tier { get; }
        string Rarity { get; }
        int MaxStack { get; }
        bool IsStackable { get; }

        Dictionary<string, object> ToSaveData();
    }
}
