using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/placement_db.py — five per-discipline parsers into
/// PlacementData keyed by recipeId. Note the smithing file's lowercase .json
/// extension (git-tracked that way; matters on case-sensitive filesystems).
/// </summary>
public sealed class PlacementDatabase
{
    public Dictionary<string, PlacementData> Placements { get; } = new();
    public bool Loaded { get; private set; }

    public void LoadFromFiles(string contentRoot)
    {
        string P(string file) => Path.Combine(contentRoot, "placements.JSON", file);
        LoadSmithing(P("placements-smithing-1.json"));
        LoadRefining(P("placements-refining-1.JSON"));
        LoadAlchemy(P("placements-alchemy-1.JSON"));
        LoadEngineering(P("placements-engineering-1.JSON"));
        LoadEnchanting(P("placements-adornments-1.JSON"));
        Loaded = true;
    }

    private static IEnumerable<JsonObject> Rows(string filepath)
    {
        if (!File.Exists(filepath)) yield break;
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        foreach (var node in J.Arr(data, "placements"))
            if (node is JsonObject p && !string.IsNullOrEmpty(J.Str(p, "recipeId")))
                yield return p;
    }

    private void LoadSmithing(string filepath)
    {
        foreach (var p in Rows(filepath))
        {
            var metadata = J.Obj(p, "metadata");
            var rid = J.Str(p, "recipeId");
            Placements[rid] = new PlacementData
            {
                RecipeId = rid,
                Discipline = "smithing",
                GridSize = J.Str(metadata, "gridSize", "3x3"),
                PlacementMap = J.Node(p, "placementMap", () => new JsonObject()),
                Narrative = J.Str(metadata, "narrative"),
            };
        }
    }

    private void LoadRefining(string filepath)
    {
        foreach (var p in Rows(filepath))
        {
            var rid = J.Str(p, "recipeId");
            Placements[rid] = new PlacementData
            {
                RecipeId = rid,
                Discipline = "refining",
                CoreInputs = J.Node(p, "coreInputs", () => new JsonArray()),
                SurroundingInputs = J.Node(p, "surroundingInputs", () => new JsonArray()),
                OutputId = J.Str(p, "outputId"),
                StationTier = J.Num(p, "stationTier", 1),
                Narrative = J.Str(p, "narrative"),
            };
        }
    }

    private void LoadAlchemy(string filepath)
    {
        foreach (var p in Rows(filepath))
        {
            var rid = J.Str(p, "recipeId");
            Placements[rid] = new PlacementData
            {
                RecipeId = rid,
                Discipline = "alchemy",
                Ingredients = J.Node(p, "ingredients", () => new JsonArray()),
                OutputId = J.Str(p, "outputId"),
                StationTier = J.Num(p, "stationTier", 1),
                Narrative = J.Str(p, "narrative"),
            };
        }
    }

    private void LoadEngineering(string filepath)
    {
        foreach (var p in Rows(filepath))
        {
            var rid = J.Str(p, "recipeId");
            Placements[rid] = new PlacementData
            {
                RecipeId = rid,
                Discipline = "engineering",
                Slots = J.Node(p, "slots", () => new JsonArray()),
                OutputId = J.Str(p, "outputId"),
                StationTier = J.Num(p, "stationTier", 1),
                Narrative = J.Str(p, "narrative"),
            };
        }
    }

    private void LoadEnchanting(string filepath)
    {
        foreach (var p in Rows(filepath))
        {
            var metadata = J.Obj(p, "metadata");
            var rid = J.Str(p, "recipeId");
            Placements[rid] = new PlacementData
            {
                RecipeId = rid,
                Discipline = "adornments",
                Pattern = J.Node(p, "pattern", () => new JsonArray()),
                PlacementMap = J.Node(p, "placementMap", () => new JsonObject()),
                GridSize = J.Str(metadata, "gridSize", "3x3"),
                OutputId = J.Str(p, "outputId"),
                StationTier = J.Num(p, "stationTier", 1),
                Narrative = J.Str(p, "narrative"),
            };
        }
    }

    public PlacementData? GetPlacement(string recipeId) =>
        Placements.GetValueOrDefault(recipeId);

    public bool HasPlacement(string recipeId) => Placements.ContainsKey(recipeId);
}
