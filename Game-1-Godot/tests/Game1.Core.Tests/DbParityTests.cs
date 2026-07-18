using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Content;
using Game1.Core.Data;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Phase-1 loader-parity gate: the C# databases load the SAME content files
/// as the Python reference build and must reproduce the Python loaders'
/// normalized in-memory state (conformance/goldens/db_parity/, produced by
/// dump_databases.py replaying the game_engine.py:135-182 boot).
/// </summary>
public static class BootedDatabases
{
    public static readonly Lazy<(MaterialDatabase Materials, TranslationDatabase Translations,
        RecipeDatabase Recipes, EquipmentDatabase Equipment, TitleDatabase Titles,
        ClassDatabase Classes, SkillDatabase Skills, PlacementDatabase Placements)> All = new(() =>
    {
        var root = ContentPaths.TryGetContentRoot()
                   ?? throw new InvalidOperationException("Game-1-modular content root not found");

        // game_engine.py:135-182 boot order (tranche-1 subset)
        var materials = new MaterialDatabase();
        materials.LoadFromFiles(root);

        var translations = new TranslationDatabase();
        translations.LoadFromFiles(root);

        var recipes = new RecipeDatabase();
        recipes.LoadFromFiles(root);

        var placements = new PlacementDatabase();
        placements.LoadFromFiles(root);

        var equipment = new EquipmentDatabase();
        foreach (var f in new[]
                 {
                     "items-engineering-1.JSON", "items-smithing-2.JSON",
                     "items-tools-1.JSON", "items-alchemy-1.JSON",
                     "items-testing-tags.JSON",
                 })
        {
            var p = Path.Combine(root, "items.JSON", f);
            if (File.Exists(p)) equipment.LoadFromFile(p);
        }

        var titles = new TitleDatabase();
        titles.LoadFromFiles(root);

        var classes = new ClassDatabase();
        classes.LoadFromFile(Path.Combine(root, "progression", "classes-1.JSON"));

        var skills = new SkillDatabase();
        skills.LoadFromFiles(root);

        UpdateLoader.LoadAll(root, equipment, skills, materials, recipes, titles);

        return (materials, translations, recipes, equipment, titles, classes, skills, placements);
    });
}

public class DbParityTests
{
    private static void AssertParity(string fixture, string collectionKey,
                                     JsonObject actual, int actualCount)
    {
        var golden = GoldenFixture.Load($"db_parity/{fixture}");
        Assert.Equal(golden.GetProperty("count").GetInt32(), actualCount);
        var diffs = JsonTreeComparer.Diff(golden.GetProperty(collectionKey), actual);
        Assert.True(diffs.Count == 0,
            $"{fixture}: {diffs.Count} diffs vs Python loader state:\n  " +
            string.Join("\n  ", diffs.Take(25)));
    }

    [Fact]
    public void Materials_MatchPythonLoaderState()
    {
        var db = BootedDatabases.All.Value.Materials;
        var actual = new JsonObject();
        foreach (var kv in db.Materials)
            actual[kv.Key] = kv.Value.ToParityNode();
        AssertParity("materials.json", "materials", actual, db.Materials.Count);
    }

    [Fact]
    public void Equipment_MatchesPythonRawStore()
    {
        var db = BootedDatabases.All.Value.Equipment;
        var actual = new JsonObject();
        foreach (var kv in db.Items)
            actual[kv.Key] = kv.Value.DeepClone();
        AssertParity("equipment.json", "items", actual, db.Items.Count);
    }

    [Fact]
    public void Recipes_MatchPythonLoaderState()
    {
        var db = BootedDatabases.All.Value.Recipes;
        var actual = new JsonObject();
        foreach (var kv in db.Recipes)
            actual[kv.Key] = kv.Value.ToParityNode();
        AssertParity("recipes.json", "recipes", actual, db.Recipes.Count);
    }

    [Fact]
    public void RecipesByStation_OrderMatchesPython()
    {
        var db = BootedDatabases.All.Value.Recipes;
        var golden = GoldenFixture.Load("db_parity/recipes.json").GetProperty("by_station");
        var actual = new JsonObject();
        foreach (var kv in db.RecipesByStation)
        {
            var arr = new JsonArray();
            foreach (var r in kv.Value) arr.Add(r.RecipeId);
            actual[kv.Key] = arr;
        }
        var diffs = JsonTreeComparer.Diff(golden, actual);
        Assert.True(diffs.Count == 0,
            $"by_station: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(25)));
    }

    [Fact]
    public void Skills_MatchPythonLoaderState()
    {
        var db = BootedDatabases.All.Value.Skills;
        var actual = new JsonObject();
        foreach (var kv in db.Skills)
            actual[kv.Key] = kv.Value.ToParityNode();
        AssertParity("skills.json", "skills", actual, db.Skills.Count);
    }

    [Fact]
    public void Titles_MatchPythonLoaderState_ExceptRequirements()
    {
        var db = BootedDatabases.All.Value.Titles;
        var actual = new JsonObject();
        foreach (var kv in db.Titles)
            actual[kv.Key] = kv.Value.ToParityNode();
        AssertParity("titles.json", "titles", actual, db.Titles.Count);
    }

    [Fact]
    public void Classes_MatchPythonLoaderState()
    {
        var db = BootedDatabases.All.Value.Classes;
        var actual = new JsonObject();
        foreach (var kv in db.Classes)
            actual[kv.Key] = kv.Value.ToParityNode();
        AssertParity("classes.json", "classes", actual, db.Classes.Count);
    }

    [Fact]
    public void Placements_MatchPythonLoaderState()
    {
        var db = BootedDatabases.All.Value.Placements;
        var actual = new JsonObject();
        foreach (var kv in db.Placements)
            actual[kv.Key] = kv.Value.ToParityNode();
        AssertParity("placements.json", "placements", actual, db.Placements.Count);
    }

    [Fact]
    public void Translations_MatchPython()
    {
        var db = BootedDatabases.All.Value.Translations;
        var golden = GoldenFixture.Load("db_parity/translations.json");

        static JsonObject FromLongs(Dictionary<string, long> d)
        {
            var o = new JsonObject();
            foreach (var kv in d) o[kv.Key] = kv.Value;
            return o;
        }

        foreach (var (key, actual) in new (string, JsonObject)[]
                 {
                     ("mana_costs", FromLongs(db.ManaCosts)),
                     ("cooldown_seconds", FromLongs(db.CooldownSeconds)),
                     ("duration_seconds", FromLongs(db.DurationSeconds)),
                 })
        {
            var diffs = JsonTreeComparer.Diff(golden.GetProperty(key), actual);
            Assert.True(diffs.Count == 0,
                $"{key}: " + string.Join("; ", diffs.Take(10)));
        }

        var magActual = new JsonObject();
        foreach (var kv in db.MagnitudeValues)
            magActual[kv.Key] = kv.Value.DeepClone();
        var magDiffs = JsonTreeComparer.Diff(golden.GetProperty("magnitude_values"), magActual);
        Assert.True(magDiffs.Count == 0,
            "magnitude_values: " + string.Join("; ", magDiffs.Take(10)));
    }
}
