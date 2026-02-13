// ============================================================================
// Game1.Data.Models.IGameItem
// Migrated from: N/A (new architecture — Part 4: IGameItem Type Hierarchy)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System.Collections.Generic;

namespace Game1.Data.Models
{
    /// <summary>
    /// Common interface for all item types in the game.
    /// Every item that can exist in inventory implements this.
    ///
    /// Concrete types: MaterialDefinition, EquipmentItem, ConsumableItem, PlaceableItem.
    /// Replaces the Python dict-based approach with type-safe polymorphism.
    /// </summary>
    public interface IGameItem
    {
        /// <summary>Unique item identifier (e.g., "iron_ore", "iron_sword").</summary>
        string ItemId { get; }

        /// <summary>Display name (e.g., "Iron Ore", "Iron Sword").</summary>
        string Name { get; }

        /// <summary>Category string: "material", "equipment", "consumable", "placeable".</summary>
        string Category { get; }

        /// <summary>Tier 1-4. Higher tier = rarer/stronger.</summary>
        int Tier { get; }

        /// <summary>Rarity string: "common", "uncommon", "rare", "epic", "legendary", "artifact".</summary>
        string Rarity { get; }

        /// <summary>Maximum stack size. Equipment = 1, materials = 99, consumables = 20.</summary>
        int MaxStack { get; }

        /// <summary>Whether this item can stack (MaxStack > 1).</summary>
        bool IsStackable { get; }

        /// <summary>
        /// Serialize this item to a dictionary for save data.
        /// Every item type implements its own serialization.
        /// </summary>
        Dictionary<string, object> ToSaveData();
    }
}
