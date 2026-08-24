using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Data;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>Replays the recipe consume-semantics scenarios (real Python
/// recipe_db + real Inventory) through RecipeCrafting.</summary>
public class RecipeConsumeTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/recipe_consume.json");

    [Fact]
    public void ConsumeSemantics_MatchPython()
    {
        var dbs = BootedDatabases.All.Value;
        var rid = G.GetProperty("recipe").GetString()!;
        var recipe = dbs.Recipes.Recipes[rid];
        var inputs = ((JsonArray)recipe.Inputs)
            .Select(n => (JsonObject)n!)
            .Select(o => (Mat: J2.Str(o, "materialId", J2.Str(o, "itemId", "")),
                          Need: (int)(J2.Num(o, "quantity")))).ToList();

        foreach (var caseEl in G.GetProperty("cases").EnumerateArray())
        {
            var id = caseEl.GetProperty("id").GetString()!;
            var inv = new Inventory(dbs.Materials, dbs.Equipment, 30);
            // starting tools mirror (build_attack_char slots don't touch inventory)
            for (var idx = 0; idx < inputs.Count; idx++)
            {
                var (mat, need) = inputs[idx];
                if (id == "insufficient" && idx == 0)
                {
                    if (need > 1) inv.AddItem(mat, need - 1);
                }
                else if (id == "split_slots")
                {
                    var half = Math.Max(1, need / 2);
                    inv.AddItem(mat, half);
                    inv.AddItem(mat, need - half + 1);
                }
                else
                {
                    inv.AddItem(mat, need + 1);
                }
            }

            var can = RecipeCrafting.CanCraft(recipe, inv);
            var actual = new JsonObject { ["id"] = id, ["recipe"] = rid, ["can"] = can };
            if (caseEl.TryGetProperty("consumed", out _))
            {
                var fraction = id == "partial_loss_060" ? 0.6 : 0.3;
                var consumed = RecipeCrafting.ConsumeMaterialsPartial(recipe, inv, fraction);
                var cObj = new JsonObject();
                foreach (var kv in consumed) cObj[kv.Key] = kv.Value;
                actual["consumed"] = cObj;
            }
            else
            {
                actual["ok"] = RecipeCrafting.ConsumeMaterials(recipe, inv);
            }
            var invRows = new JsonArray();
            foreach (var s in inv.Slots)
                invRows.Add(s is null ? null : new JsonArray { s.ItemId, s.Quantity });
            actual["inventory"] = invRows;

            var diffs = JsonTreeComparer.Diff(caseEl, actual);
            Assert.True(diffs.Count == 0,
                $"case[{id}]: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(15)));
        }
    }

    private static class J2
    {
        public static string Str(JsonObject o, string key, string dflt) =>
            o[key] is JsonValue v && v.TryGetValue<string>(out var s) ? s : dflt;

        public static double Num(JsonObject o, string key) =>
            o[key] is JsonValue v && v.TryGetValue<double>(out var d) ? d : 0;
    }
}
