// Game1.Data.Databases.RecipeDatabase
// Migrated from: data/databases/recipe_db.py (212 lines)
// Phase: 2 - Data Layer
// Loads from recipes.JSON/ (5 files: smithing, alchemy, refining, engineering, adornments).
// CRITICAL: Three different output formats:
//   1. enchantmentId (enchanting recipes)
//   2. outputs[] array (refining recipes)
//   3. outputId (standard recipes)
// can_craft/consume_materials deferred to Phase 3 (needs inventory).

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for crafting recipes across all 5 disciplines.
    /// Indexed by recipeId and organized by stationType.
    /// </summary>
    public class RecipeDatabase
    {
        private static RecipeDatabase _instance;
        private static readonly object _lock = new object();

        public Dictionary<string, Recipe> Recipes { get; private set; }
        public Dictionary<string, List<Recipe>> RecipesByStation { get; private set; }
        public bool Loaded { get; private set; }

        public static RecipeDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new RecipeDatabase();
                }
            }
            return _instance;
        }

        private RecipeDatabase()
        {
            Recipes = new Dictionary<string, Recipe>();
            RecipesByStation = new Dictionary<string, List<Recipe>>
            {
                { "smithing", new List<Recipe>() },
                { "alchemy", new List<Recipe>() },
                { "refining", new List<Recipe>() },
                { "engineering", new List<Recipe>() },
                { "adornments", new List<Recipe>() }
            };
        }

        public void LoadFromFiles()
        {
            int total = 0;
            var files = new (string StationType, string Filename)[]
            {
                ("smithing", "recipes-smithing-3.json"),
                ("alchemy", "recipes-alchemy-1.JSON"),
                ("refining", "recipes-refining-1.JSON"),
                ("engineering", "recipes-engineering-1.JSON"),
                ("adornments", "recipes-adornments-1.json")
            };

            foreach (var (stationType, filename) in files)
            {
                string path = JsonLoader.GetContentPath($"recipes.JSON/{filename}");
                if (System.IO.File.Exists(path))
                    total += LoadFile(path, stationType);
            }

            if (total == 0)
            {
                CreateDefaultRecipes();
                total = Recipes.Count;
            }

            Loaded = true;
            JsonLoader.Log($"Loaded {total} recipes");
        }

        private int LoadFile(string filepath, string stationType)
        {
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data == null) return 0;

                var recipesArr = data["recipes"] as JArray;
                if (recipesArr == null) return 0;

                int count = 0;
                foreach (JObject recipeData in recipesArr)
                {
                    bool isEnchanting = recipeData["enchantmentId"] != null;

                    string outputId;
                    int outputQty;
                    int stationTier;

                    if (isEnchanting)
                    {
                        // Format 1: Enchanting - uses enchantmentId
                        outputId = recipeData.Value<string>("enchantmentId") ?? "";
                        outputQty = 1;
                        stationTier = recipeData.Value<int?>("stationTier") ?? 1;
                    }
                    else if (recipeData["outputs"] is JArray outputsArr && outputsArr.Count > 0)
                    {
                        // Format 2: Outputs array (refining recipes)
                        var firstOutput = outputsArr[0] as JObject;
                        outputId = firstOutput?.Value<string>("materialId")
                            ?? firstOutput?.Value<string>("itemId") ?? "";
                        outputQty = firstOutput?.Value<int?>("quantity") ?? 1;
                        stationTier = recipeData.Value<int?>("stationTierRequired")
                            ?? recipeData.Value<int?>("stationTier") ?? 1;
                    }
                    else
                    {
                        // Format 3: Standard - uses outputId
                        outputId = recipeData.Value<string>("outputId") ?? "";
                        outputQty = recipeData.Value<int?>("outputQty") ?? 1;
                        stationTier = recipeData.Value<int?>("stationTier") ?? 1;
                    }

                    if (string.IsNullOrWhiteSpace(outputId)) continue;

                    // Parse inputs
                    var inputs = new List<Dictionary<string, object>>();
                    if (recipeData["inputs"] is JArray inputsArr)
                    {
                        foreach (JObject inp in inputsArr)
                        {
                            var inputDict = new Dictionary<string, object>();
                            foreach (var p in inp.Properties())
                                inputDict[p.Name] = p.Value.ToObject<object>();
                            inputs.Add(inputDict);
                        }
                    }

                    // Parse enchanting-specific fields
                    var applicableTo = new List<string>();
                    if (recipeData["applicableTo"] is JArray appArr)
                        foreach (var a in appArr) applicableTo.Add(a.Value<string>());

                    var effect = new Dictionary<string, object>();
                    if (recipeData["effect"] is JObject effectObj)
                        foreach (var p in effectObj.Properties())
                            effect[p.Name] = p.Value.ToObject<object>();

                    var recipe = new Recipe
                    {
                        RecipeId = recipeData.Value<string>("recipeId") ?? "",
                        OutputId = outputId,
                        OutputQty = outputQty,
                        StationType = stationType,
                        StationTier = stationTier,
                        Inputs = inputs,
                        IsEnchantment = isEnchanting,
                        EnchantmentName = recipeData.Value<string>("enchantmentName") ?? "",
                        ApplicableTo = applicableTo,
                        Effect = effect
                    };

                    Recipes[recipe.RecipeId] = recipe;
                    if (!RecipesByStation.ContainsKey(stationType))
                        RecipesByStation[stationType] = new List<Recipe>();
                    RecipesByStation[stationType].Add(recipe);
                    count++;
                }

                return count;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading recipes from {filepath}: {ex.Message}");
                return 0;
            }
        }

        public List<Recipe> GetRecipesForStation(string stationType, int tier = 1)
        {
            if (!RecipesByStation.TryGetValue(stationType, out var recipes))
                return new List<Recipe>();
            return recipes.Where(r => r.StationTier <= tier).ToList();
        }

        private void CreateDefaultRecipes()
        {
            var defaults = new (string Id, string OutId, int OutQty, string Station, int Tier,
                List<Dictionary<string, object>> Inputs)[]
            {
                ("copper_ingot_recipe", "copper_ingot", 1, "refining", 1,
                    new() { new() { { "materialId", "copper_ore" }, { "quantity", 3 } } }),
                ("iron_ingot_recipe", "iron_ingot", 1, "refining", 1,
                    new() { new() { { "materialId", "iron_ore" }, { "quantity", 3 } } }),
                ("copper_sword_recipe", "copper_sword", 1, "smithing", 1,
                    new() { new() { { "materialId", "copper_ingot" }, { "quantity", 3 } },
                            new() { { "materialId", "oak_log" }, { "quantity", 1 } } }),
                ("iron_sword_recipe", "iron_sword", 1, "smithing", 1,
                    new() { new() { { "materialId", "iron_ingot" }, { "quantity", 3 } },
                            new() { { "materialId", "birch_log" }, { "quantity", 1 } } }),
                ("copper_helmet_recipe", "copper_helmet", 1, "smithing", 1,
                    new() { new() { { "materialId", "copper_ingot" }, { "quantity", 4 } } }),
                ("copper_chestplate_recipe", "copper_chestplate", 1, "smithing", 1,
                    new() { new() { { "materialId", "copper_ingot" }, { "quantity", 7 } } })
            };

            foreach (var (id, outId, outQty, station, tier, inputs) in defaults)
            {
                var recipe = new Recipe
                {
                    RecipeId = id, OutputId = outId, OutputQty = outQty,
                    StationType = station, StationTier = tier, Inputs = inputs
                };
                Recipes[recipe.RecipeId] = recipe;
                RecipesByStation[station].Add(recipe);
            }

            JsonLoader.Log($"Created {defaults.Length} default recipes");
        }

        internal static void ResetInstance() => _instance = null;
    }
}
