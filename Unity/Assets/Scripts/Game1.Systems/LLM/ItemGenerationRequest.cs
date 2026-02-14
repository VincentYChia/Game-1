// ============================================================================
// Game1.Systems.LLM.ItemGenerationRequest
// Migrated from: systems/llm_item_generator.py (recipe_context extraction)
// Migration phase: 7
// Date: 2026-02-14
//
// Encapsulates all information needed to generate an invented item.
// Built from the crafting UI state after ML classifier validation.
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Systems.LLM
{
    /// <summary>
    /// Encapsulates all information needed to generate an invented item.
    /// Built from the crafting UI state after ML classifier validation.
    /// </summary>
    [Serializable]
    public class ItemGenerationRequest
    {
        /// <summary>Crafting discipline (smithing, alchemy, refining, engineering, enchanting).</summary>
        public string Discipline { get; set; }

        /// <summary>Station tier used for crafting (1-4).</summary>
        public int StationTier { get; set; }

        /// <summary>Materials placed in the crafting grid with their quantities.</summary>
        public List<MaterialPlacement> Materials { get; set; } = new();

        /// <summary>ML classifier confidence score (0.0-1.0).</summary>
        public float ClassifierConfidence { get; set; }

        /// <summary>
        /// Hash of the placement for recipe lookup and caching.
        /// Computed from sorted material IDs + quantities + positions.
        /// </summary>
        public string PlacementHash { get; set; }
    }

    /// <summary>
    /// A single material placement within a crafting grid.
    /// </summary>
    [Serializable]
    public class MaterialPlacement
    {
        /// <summary>Material identifier (e.g., "iron_ingot").</summary>
        public string MaterialId { get; set; }

        /// <summary>Quantity of this material placed.</summary>
        public int Quantity { get; set; }

        /// <summary>Slot type for engineering: FRAME, POWER, etc. Empty for other disciplines.</summary>
        public string SlotType { get; set; } = "";

        /// <summary>Slot index in the crafting grid.</summary>
        public int SlotIndex { get; set; }
    }
}
