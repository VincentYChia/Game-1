using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/recipe_db.py (loader only — can_craft/consume_
/// materials move to an inventory service in Phase 2 per contract doc 03).
/// Three output dialects: enchanting (enchantmentId), outputs-array
/// (refining), and plain outputId. Empty/whitespace output ids are skipped.
/// Default-recipe fallback is NOT ported (fail-fast; content exists).
/// </summary>
public sealed class RecipeDatabase
{
    public Dictionary<string, Recipe> Recipes { get; } = new();
    public Dictionary<string, List<Recipe>> RecipesByStation { get; } = new()
    {
        ["smithing"] = new(), ["alchemy"] = new(), ["refining"] = new(),
        ["engineering"] = new(), ["adornments"] = new(),
    };
    public bool Loaded { get; private set; }

    private static readonly (string Station, string File)[] BootFiles =
    {
        ("smithing", "recipes-smithing-3.json"),
        ("alchemy", "recipes-alchemy-1.JSON"),
        ("refining", "recipes-refining-1.JSON"),
        ("engineering", "recipes-engineering-1.JSON"),
        ("adornments", "recipes-adornments-1.json"),
    };

    public void LoadFromFiles(string contentRoot)
    {
        foreach (var (station, file) in BootFiles)
        {
            var path = Path.Combine(contentRoot, "recipes.JSON", file);
            if (File.Exists(path))
                LoadFile(path, station);
        }
        Loaded = true;
    }

    // recipe_db.py:44-97
    public int LoadFile(string filepath, string stationType)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        var loaded = 0;
        foreach (var node in J.Arr(data, "recipes"))
        {
            if (node is not JsonObject r) continue;
            var isEnchanting = r.ContainsKey("enchantmentId");

            string outputId;
            double outputQty;
            double stationTier;
            if (isEnchanting)
            {
                outputId = J.Str(r, "enchantmentId");
                outputQty = 1;
                stationTier = J.Num(r, "stationTier", 1);
            }
            else if (r.ContainsKey("outputs"))
            {
                var outputs = J.Arr(r, "outputs");
                if (outputs.Count > 0 && outputs[0] is JsonObject o0)
                {
                    outputId = J.Str(o0, "materialId", J.Str(o0, "itemId"));
                    outputQty = J.Num(o0, "quantity", 1);
                }
                else
                {
                    outputId = "";
                    outputQty = 1;
                }
                stationTier = J.Num(r, "stationTierRequired", J.Num(r, "stationTier", 1));
            }
            else
            {
                outputId = J.Str(r, "outputId");
                outputQty = J.Num(r, "outputQty", 1);
                stationTier = J.Num(r, "stationTier", 1);
            }

            if (string.IsNullOrEmpty(outputId) || outputId.Trim().Length == 0)
                continue;  // recipe_db.py:75-77

            var recipe = new Recipe
            {
                RecipeId = J.Str(r, "recipeId"),
                OutputId = outputId,
                OutputQty = outputQty,
                StationType = stationType,
                StationTier = stationTier,
                Inputs = J.Node(r, "inputs", () => new JsonArray()),
                IsEnchantment = isEnchanting,
                EnchantmentName = J.Str(r, "enchantmentName"),
                ApplicableTo = J.Node(r, "applicableTo", () => new JsonArray()),
                Effect = J.Node(r, "effect", () => new JsonObject()),
            };
            Recipes[recipe.RecipeId] = recipe;
            RecipesByStation[stationType].Add(recipe);
            loaded++;
        }
        return loaded;
    }
}
