using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// The player's DISCOVERED recipes — persisted, and injected into the live Core databases
/// so an invention behaves EXACTLY like a base recipe: it lists as a card, its placement
/// template matches on the board, "Fill" lays it out, and crafting it consumes materials +
/// yields the item through the certified seam. Each record keeps the LLM item definition,
/// the recipe inputs, and the exact placement the player discovered it with.
///
/// Injection is glue-only: it adds runtime entries to MaterialDatabase.Materials /
/// RecipeDatabase.Recipes+RecipesByStation / PlacementDatabase.Placements. It never edits
/// Core code or the content JSON. (Invented outputs materialize as inventory items via a
/// synthesized MaterialDefinition; making an invented weapon/armor equippable is a later
/// pass.)
/// </summary>
public sealed class InventedRecipeStore
{
    private readonly string _path;
    private readonly List<JsonObject> _records = new();

    public InventedRecipeStore()
    {
        _path = System.IO.Path.Combine(OS.GetUserDataDir(), "invented_recipes.json");
        Load();
    }

    /// <summary>Re-inject every persisted discovery (call once after the DBs load).</summary>
    public void InjectAll(CombatWorld combat)
    {
        foreach (var r in _records) Inject(r, combat);
    }

    /// <summary>Persist + inject a fresh discovery; returns the now-craftable Recipe.</summary>
    public Recipe? AddDiscovery(InventionResult res, JsonObject signature, string discipline, CombatWorld combat)
    {
        var recipeId = $"invented_{res.OutputId}";
        var rec = new JsonObject
        {
            ["discipline"] = discipline,
            ["stationTier"] = res.StationTier,
            ["outputId"] = res.OutputId,
            ["recipeId"] = recipeId,
            ["item"] = res.Item?.DeepClone(),
            ["recipeInputs"] = (res.RecipeInputs ?? new JsonArray()).DeepClone(),
            ["placement"] = signature.DeepClone(),
        };
        _records.RemoveAll(r => r["recipeId"]?.GetValue<string>() == recipeId);
        _records.Add(rec);
        Save();
        return Inject(rec, combat);
    }

    // ------------------------------------------------------------- injection ----

    private static Recipe? Inject(JsonObject rec, CombatWorld combat)
    {
        var recipeDb = combat.RecipeDb;
        var placementDb = combat.PlacementDb;
        var matDb = combat.MaterialDb;
        if (recipeDb is null || placementDb is null || matDb is null) return null;

        var recipeId = rec["recipeId"]?.GetValue<string>() ?? "";
        var outputId = rec["outputId"]?.GetValue<string>() ?? "";
        var discipline = rec["discipline"]?.GetValue<string>() ?? "smithing";
        var tier = Num(rec["stationTier"], 1);
        if (recipeId.Length == 0 || outputId.Length == 0) return null;

        // 1) materialize the output so name / rarity / inventory resolve
        if (!matDb.Materials.ContainsKey(outputId))
        {
            var item = rec["item"] as JsonObject;
            matDb.Materials[outputId] = new MaterialDefinition
            {
                MaterialId = outputId,
                Name = item?["name"]?.GetValue<string>() ?? CombatWorld.Prettify(outputId),
                Tier = Num(item?["tier"], tier),
                Category = item?["category"]?.GetValue<string>() ?? "invented",
                Rarity = item?["rarity"]?.GetValue<string>() ?? "uncommon",
                Narrative = (item?["metadata"] as JsonObject)?["narrative"]?.GetValue<string>() ?? "",
            };
        }

        // 2) the recipe (skip if already live — re-inject is idempotent)
        if (recipeDb.Recipes.TryGetValue(recipeId, out var existing))
            return existing;
        var recipe = new Recipe
        {
            RecipeId = recipeId,
            OutputId = outputId,
            OutputQty = 1,
            StationType = discipline,
            StationTier = tier,
            Inputs = (rec["recipeInputs"] as JsonArray ?? new JsonArray()).DeepClone(),
        };
        recipeDb.Recipes[recipeId] = recipe;
        if (!recipeDb.RecipesByStation.TryGetValue(discipline, out var list))
            recipeDb.RecipesByStation[discipline] = list = new List<Recipe>();
        list.Add(recipe);

        // 3) the placement template (so it matches on the board + Fill works)
        if (!placementDb.Placements.ContainsKey(recipeId) && rec["placement"] is JsonObject sig)
            placementDb.Placements[recipeId] = ToPlacement(recipeId, outputId, discipline, tier, sig);

        return recipe;
    }

    private static PlacementData ToPlacement(string recipeId, string outputId, string discipline,
                                             double tier, JsonObject sig)
    {
        var pd = new PlacementData
        {
            RecipeId = recipeId,
            Discipline = discipline,
            OutputId = outputId,
            StationTier = tier,
        };
        return discipline switch
        {
            "smithing" => Clone(pd, placementMap: sig["grid"]),
            "refining" => Clone(pd, core: sig["coreInputs"], surr: sig["surroundingInputs"]),
            "alchemy" => Clone(pd, ingredients: sig["ingredients"]),
            "engineering" => Clone(pd, slots: sig["slots"]),
            "adornments" => Clone(pd, placementMap: new JsonObject
            {
                ["shapes"] = (sig["shapes"] ?? new JsonArray()).DeepClone(),
                ["vertices"] = (sig["vertices"] ?? new JsonObject()).DeepClone(),
            }),
            _ => pd,
        };
    }

    // PlacementData is init-only; rebuild with the one relevant field filled.
    private static PlacementData Clone(PlacementData p, JsonNode? placementMap = null, JsonNode? core = null,
                                       JsonNode? surr = null, JsonNode? ingredients = null, JsonNode? slots = null)
        => new()
        {
            RecipeId = p.RecipeId,
            Discipline = p.Discipline,
            OutputId = p.OutputId,
            StationTier = p.StationTier,
            PlacementMap = placementMap?.DeepClone() ?? new JsonObject(),
            CoreInputs = core?.DeepClone() ?? new JsonArray(),
            SurroundingInputs = surr?.DeepClone() ?? new JsonArray(),
            Ingredients = ingredients?.DeepClone() ?? new JsonArray(),
            Slots = slots?.DeepClone() ?? new JsonArray(),
        };

    // ----------------------------------------------------------- persistence ----

    private void Load()
    {
        try
        {
            if (!System.IO.File.Exists(_path)) return;
            if (JsonNode.Parse(System.IO.File.ReadAllText(_path)) is JsonArray arr)
                foreach (var n in arr)
                    if (n is JsonObject o) _records.Add(o);
        }
        catch { /* corrupt store is non-fatal */ }
    }

    private void Save()
    {
        try
        {
            var arr = new JsonArray();
            foreach (var r in _records) arr.Add(r.DeepClone());
            System.IO.File.WriteAllText(_path, arr.ToJsonString());
        }
        catch { /* best-effort */ }
    }

    private static double Num(JsonNode? n, double fallback)
    {
        if (n is JsonValue v)
        {
            if (v.TryGetValue<double>(out var d)) return d;
            if (v.TryGetValue<int>(out var i)) return i;
        }
        return fallback;
    }
}
