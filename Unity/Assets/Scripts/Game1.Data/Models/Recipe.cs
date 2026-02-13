// ============================================================================
// Game1.Data.Models.Recipe
// Migrated from: data/models/recipes.py (lines 1-24)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Crafting recipe input requirement.
    /// </summary>
    public class RecipeInput
    {
        [JsonProperty("materialId")]
        public string MaterialId { get; set; }

        [JsonProperty("qty")]
        public int Quantity { get; set; }

        [JsonProperty("slot")]
        public string Slot { get; set; }

        [JsonProperty("type")]
        public string Type { get; set; }
    }

    /// <summary>
    /// Crafting recipe definition.
    /// Loaded from recipes-*.JSON files.
    /// </summary>
    public class Recipe
    {
        [JsonProperty("recipeId")]
        public string RecipeId { get; set; }

        [JsonProperty("outputId")]
        public string OutputId { get; set; }

        [JsonProperty("outputQty")]
        public int OutputQty { get; set; } = 1;

        [JsonProperty("stationType")]
        public string StationType { get; set; }

        [JsonProperty("stationTier")]
        public int StationTier { get; set; } = 1;

        [JsonProperty("inputs")]
        public List<RecipeInput> Inputs { get; set; } = new();

        [JsonProperty("gridSize")]
        public string GridSize { get; set; } = "3x3";

        [JsonProperty("miniGameType")]
        public string MiniGameType { get; set; } = "";

        [JsonProperty("metadata")]
        public Dictionary<string, object> Metadata { get; set; } = new();

        // Enchanting-specific fields
        [JsonProperty("isEnchantment")]
        public bool IsEnchantment { get; set; }

        [JsonProperty("enchantmentName")]
        public string EnchantmentName { get; set; } = "";

        [JsonProperty("applicableTo")]
        public List<string> ApplicableTo { get; set; } = new();

        [JsonProperty("effect")]
        public Dictionary<string, object> Effect { get; set; } = new();

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        /// <summary>
        /// Placement ID linking to PlacementDatabase.
        /// May be set externally during recipe loading.
        /// </summary>
        [JsonProperty("placementId")]
        public string PlacementId { get; set; }

        public override string ToString()
        {
            return $"Recipe({RecipeId} -> {OutputId} x{OutputQty})";
        }
    }
}
