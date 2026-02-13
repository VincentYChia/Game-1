// ============================================================================
// Game1.Data.Models.PlacementData
// Migrated from: data/models/recipes.py (PlacementData, lines 27-53)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Universal placement data structure for all crafting disciplines.
    /// Each discipline uses different fields:
    /// - Smithing/Enchanting: grid_size + placement_map
    /// - Refining: core_inputs + surrounding_inputs
    /// - Alchemy: ingredients (sequential)
    /// - Engineering: slots (typed)
    /// - Enchanting: pattern
    /// </summary>
    public class PlacementData
    {
        [JsonProperty("recipeId")]
        public string RecipeId { get; set; }

        [JsonProperty("discipline")]
        public string Discipline { get; set; }

        // Smithing & Enchanting: Grid-based placement
        [JsonProperty("gridSize")]
        public string GridSize { get; set; } = "";

        [JsonProperty("placementMap")]
        public Dictionary<string, string> PlacementMap { get; set; } = new();

        // Refining: Hub-and-spoke
        [JsonProperty("coreInputs")]
        public List<Dictionary<string, object>> CoreInputs { get; set; } = new();

        [JsonProperty("surroundingInputs")]
        public List<Dictionary<string, object>> SurroundingInputs { get; set; } = new();

        // Alchemy: Sequential
        [JsonProperty("ingredients")]
        public List<Dictionary<string, object>> Ingredients { get; set; } = new();

        // Engineering: Slot types
        [JsonProperty("slots")]
        public List<Dictionary<string, object>> Slots { get; set; } = new();

        // Enchanting: Pattern-based
        [JsonProperty("pattern")]
        public List<Dictionary<string, object>> Pattern { get; set; } = new();

        // Metadata
        [JsonProperty("narrative")]
        public string Narrative { get; set; } = "";

        [JsonProperty("outputId")]
        public string OutputId { get; set; } = "";

        [JsonProperty("stationTier")]
        public int StationTier { get; set; } = 1;

        public override string ToString()
        {
            return $"Placement({RecipeId} [{Discipline}])";
        }
    }
}
