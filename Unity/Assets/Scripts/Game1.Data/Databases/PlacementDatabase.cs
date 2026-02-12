// Game1.Data.Databases.PlacementDatabase
// Migrated from: data/databases/placement_db.py (217 lines)
// Phase: 2 - Data Layer
// Loads from placements.JSON/ (5 files, one per discipline).
// Each discipline has a different placement format.

using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for crafting placement templates.
    /// Each discipline has its own format:
    ///   Smithing: grid (placementMap + gridSize)
    ///   Refining: hub-and-spoke (coreInputs + surroundingInputs)
    ///   Alchemy: sequential (ingredients)
    ///   Engineering: slot types (slots)
    ///   Enchanting/Adornments: pattern-based (pattern + optional grid)
    /// </summary>
    public class PlacementDatabase
    {
        private static PlacementDatabase _instance;
        private static readonly object _lock = new object();

        public Dictionary<string, PlacementData> Placements { get; private set; }
        public bool Loaded { get; private set; }

        public static PlacementDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new PlacementDatabase();
                }
            }
            return _instance;
        }

        private PlacementDatabase()
        {
            Placements = new Dictionary<string, PlacementData>();
        }

        public int LoadFromFiles()
        {
            int total = 0;
            total += LoadSmithing(JsonLoader.GetContentPath("placements.JSON/placements-smithing-1.JSON"));
            total += LoadRefining(JsonLoader.GetContentPath("placements.JSON/placements-refining-1.JSON"));
            total += LoadAlchemy(JsonLoader.GetContentPath("placements.JSON/placements-alchemy-1.JSON"));
            total += LoadEngineering(JsonLoader.GetContentPath("placements.JSON/placements-engineering-1.JSON"));
            total += LoadEnchanting(JsonLoader.GetContentPath("placements.JSON/placements-adornments-1.JSON"));

            Loaded = true;
            JsonLoader.Log($"Loaded {total} placement templates");
            return total;
        }

        private int LoadSmithing(string filepath)
        {
            if (!System.IO.File.Exists(filepath)) return 0;
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data?["placements"] is not JArray arr) return 0;

                int count = 0;
                foreach (JObject p in arr)
                {
                    string recipeId = p.Value<string>("recipeId") ?? "";
                    if (string.IsNullOrEmpty(recipeId)) continue;

                    var metadata = p["metadata"] as JObject;
                    var placementMap = new Dictionary<string, string>();
                    if (p["placementMap"] is JObject pmObj)
                        foreach (var prop in pmObj.Properties())
                            placementMap[prop.Name] = prop.Value.Value<string>();

                    Placements[recipeId] = new PlacementData
                    {
                        RecipeId = recipeId,
                        Discipline = "smithing",
                        GridSize = metadata?.Value<string>("gridSize") ?? "3x3",
                        PlacementMap = placementMap,
                        Narrative = metadata?.Value<string>("narrative") ?? ""
                    };
                    count++;
                }
                return count;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading smithing placements: {ex.Message}");
                return 0;
            }
        }

        private int LoadRefining(string filepath)
        {
            if (!System.IO.File.Exists(filepath)) return 0;
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data?["placements"] is not JArray arr) return 0;

                int count = 0;
                foreach (JObject p in arr)
                {
                    string recipeId = p.Value<string>("recipeId") ?? "";
                    if (string.IsNullOrEmpty(recipeId)) continue;

                    Placements[recipeId] = new PlacementData
                    {
                        RecipeId = recipeId,
                        Discipline = "refining",
                        CoreInputs = ParseObjectArray(p["coreInputs"] as JArray),
                        SurroundingInputs = ParseObjectArray(p["surroundingInputs"] as JArray),
                        OutputId = p.Value<string>("outputId") ?? "",
                        StationTier = p.Value<int?>("stationTier") ?? 1,
                        Narrative = p.Value<string>("narrative") ?? ""
                    };
                    count++;
                }
                return count;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading refining placements: {ex.Message}");
                return 0;
            }
        }

        private int LoadAlchemy(string filepath)
        {
            if (!System.IO.File.Exists(filepath)) return 0;
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data?["placements"] is not JArray arr) return 0;

                int count = 0;
                foreach (JObject p in arr)
                {
                    string recipeId = p.Value<string>("recipeId") ?? "";
                    if (string.IsNullOrEmpty(recipeId)) continue;

                    Placements[recipeId] = new PlacementData
                    {
                        RecipeId = recipeId,
                        Discipline = "alchemy",
                        Ingredients = ParseObjectArray(p["ingredients"] as JArray),
                        OutputId = p.Value<string>("outputId") ?? "",
                        StationTier = p.Value<int?>("stationTier") ?? 1,
                        Narrative = p.Value<string>("narrative") ?? ""
                    };
                    count++;
                }
                return count;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading alchemy placements: {ex.Message}");
                return 0;
            }
        }

        private int LoadEngineering(string filepath)
        {
            if (!System.IO.File.Exists(filepath)) return 0;
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data?["placements"] is not JArray arr) return 0;

                int count = 0;
                foreach (JObject p in arr)
                {
                    string recipeId = p.Value<string>("recipeId") ?? "";
                    if (string.IsNullOrEmpty(recipeId)) continue;

                    Placements[recipeId] = new PlacementData
                    {
                        RecipeId = recipeId,
                        Discipline = "engineering",
                        Slots = ParseObjectArray(p["slots"] as JArray),
                        OutputId = p.Value<string>("outputId") ?? "",
                        StationTier = p.Value<int?>("stationTier") ?? 1,
                        Narrative = p.Value<string>("narrative") ?? ""
                    };
                    count++;
                }
                return count;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading engineering placements: {ex.Message}");
                return 0;
            }
        }

        private int LoadEnchanting(string filepath)
        {
            if (!System.IO.File.Exists(filepath)) return 0;
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data?["placements"] is not JArray arr) return 0;

                int count = 0;
                foreach (JObject p in arr)
                {
                    string recipeId = p.Value<string>("recipeId") ?? "";
                    if (string.IsNullOrEmpty(recipeId)) continue;

                    var metadata = p["metadata"] as JObject;
                    var placementMap = new Dictionary<string, string>();
                    if (p["placementMap"] is JObject pmObj)
                        foreach (var prop in pmObj.Properties())
                            placementMap[prop.Name] = prop.Value.Value<string>();

                    Placements[recipeId] = new PlacementData
                    {
                        RecipeId = recipeId,
                        Discipline = "adornments",
                        Pattern = ParseObjectArray(p["pattern"] as JArray),
                        PlacementMap = placementMap,
                        GridSize = metadata?.Value<string>("gridSize") ?? "3x3",
                        OutputId = p.Value<string>("outputId") ?? "",
                        StationTier = p.Value<int?>("stationTier") ?? 1,
                        Narrative = p.Value<string>("narrative") ?? ""
                    };
                    count++;
                }
                return count;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading enchanting placements: {ex.Message}");
                return 0;
            }
        }

        public PlacementData GetPlacement(string recipeId) =>
            Placements.TryGetValue(recipeId, out var p) ? p : null;

        public bool HasPlacement(string recipeId) => Placements.ContainsKey(recipeId);

        private static List<Dictionary<string, object>> ParseObjectArray(JArray arr)
        {
            var result = new List<Dictionary<string, object>>();
            if (arr == null) return result;

            foreach (JObject obj in arr)
            {
                var dict = new Dictionary<string, object>();
                foreach (var p in obj.Properties())
                    dict[p.Name] = p.Value.ToObject<object>();
                result.Add(dict);
            }
            return result;
        }

        internal static void ResetInstance() => _instance = null;
    }
}
