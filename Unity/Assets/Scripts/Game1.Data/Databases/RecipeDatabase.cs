// ============================================================================
// Game1.Data.Databases.RecipeDatabase
// Migrated from: data/databases/recipe_db.py
// Migration phase: 2
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;
using Game1.Core;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for crafting recipes.
    /// Loads from multiple recipe JSON files (one per discipline).
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class RecipeDatabase
    {
        private static RecipeDatabase _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, Recipe> _recipes = new();
        private readonly Dictionary<string, List<Recipe>> _byStation = new();

        public static RecipeDatabase Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new RecipeDatabase();
                        }
                    }
                }
                return _instance;
            }
        }

        private RecipeDatabase() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }

        public int Count => _recipes.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>
        /// Load all recipe files from the recipes.JSON directory.
        /// </summary>
        public void LoadFromFiles()
        {
            string[] recipeFiles = new[]
            {
                "recipes.JSON/recipes-smithing-3.json",
                "recipes.JSON/recipes-alchemy-1.JSON",
                "recipes.JSON/recipes-refining-1.JSON",
                "recipes.JSON/recipes-engineering-1.JSON",
                "recipes.JSON/recipes-enchanting-1.JSON",
                "recipes.JSON/recipes-adornments-1.json",
            };

            foreach (var file in recipeFiles)
            {
                LoadFromFile(file);
            }

            Loaded = true;
            System.Diagnostics.Debug.WriteLine($"[RecipeDatabase] Total recipes loaded: {_recipes.Count}");
        }

        /// <summary>Load recipes from a single JSON file.</summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[RecipeDatabase] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var wrapper = JObject.Parse(json);

                JArray recipes = wrapper["recipes"] as JArray;
                if (recipes == null)
                {
                    System.Diagnostics.Debug.WriteLine($"[RecipeDatabase] No 'recipes' array in {relativePath}");
                    return;
                }

                int count = 0;
                foreach (var token in recipes)
                {
                    var recipe = token.ToObject<Recipe>();
                    if (recipe != null && !string.IsNullOrEmpty(recipe.RecipeId))
                    {
                        _recipes[recipe.RecipeId] = recipe;
                        _addToStationIndex(recipe);
                        count++;
                    }
                }

                System.Diagnostics.Debug.WriteLine($"[RecipeDatabase] Loaded {count} recipes from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[RecipeDatabase] Error loading {relativePath}: {ex.Message}");
            }
        }

        /// <summary>Add a recipe (e.g., invented recipe) at runtime.</summary>
        public void AddRecipe(Recipe recipe)
        {
            if (recipe == null || string.IsNullOrEmpty(recipe.RecipeId)) return;
            _recipes[recipe.RecipeId] = recipe;
            _addToStationIndex(recipe);
        }

        private void _addToStationIndex(Recipe recipe)
        {
            string key = recipe.StationType ?? "";
            if (!_byStation.ContainsKey(key))
                _byStation[key] = new List<Recipe>();
            _byStation[key].Add(recipe);
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get a recipe by ID. Returns null if not found.</summary>
        public Recipe GetRecipe(string recipeId)
        {
            if (string.IsNullOrEmpty(recipeId)) return null;
            return _recipes.TryGetValue(recipeId, out var recipe) ? recipe : null;
        }

        /// <summary>
        /// Get all recipes for a station type and tier.
        /// Returns recipes where stationTier is less than or equal to the given tier.
        /// </summary>
        public List<Recipe> GetRecipesForStation(string stationType, int tier = 999)
        {
            if (string.IsNullOrEmpty(stationType)) return new List<Recipe>();

            if (!_byStation.TryGetValue(stationType, out var recipes))
                return new List<Recipe>();

            return recipes.Where(r => r.StationTier <= tier).ToList();
        }

        /// <summary>
        /// Check if a recipe can be crafted with the given inventory item counts.
        /// </summary>
        public bool CanCraft(Recipe recipe, Func<string, int> getItemCount)
        {
            if (recipe == null || recipe.Inputs == null) return false;

            foreach (var input in recipe.Inputs)
            {
                int available = getItemCount(input.MaterialId);
                if (available < input.Quantity)
                    return false;
            }
            return true;
        }

        /// <summary>All loaded recipes as a read-only dictionary.</summary>
        public IReadOnlyDictionary<string, Recipe> Recipes => _recipes;
    }
}
