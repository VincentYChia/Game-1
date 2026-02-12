// Game1.Data.Models.Recipes
// Migrated from: data/models/recipes.py (52 lines)
// Phase: 1 - Foundation
// Contains: Recipe, PlacementData

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Crafting recipe definition. Pure data - no methods.
    /// </summary>
    [Serializable]
    public class Recipe
    {
        [JsonProperty("recipeId")]
        public string RecipeId { get; set; }

        [JsonProperty("outputId")]
        public string OutputId { get; set; }

        [JsonProperty("outputQty")]
        public int OutputQty { get; set; }

        [JsonProperty("stationType")]
        public string StationType { get; set; }

        [JsonProperty("stationTier")]
        public int StationTier { get; set; }

        [JsonProperty("inputs")]
        public List<Dictionary<string, object>> Inputs { get; set; } = new();

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
    }

    /// <summary>
    /// Universal placement data structure for all crafting disciplines.
    /// Supports smithing (grid), refining (hub-and-spoke), alchemy (sequential),
    /// engineering (slot types), and enchanting (pattern-based).
    /// </summary>
    [Serializable]
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
    }
}
