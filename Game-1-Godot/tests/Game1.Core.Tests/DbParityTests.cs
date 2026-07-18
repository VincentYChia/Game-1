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
        ClassDatabase Classes, SkillDatabase Skills, PlacementDatabase Placements,
        ResourceNodeDatabase ResourceNodes, NpcDatabase Npcs,
        ChunkTemplateDatabase ChunkTemplates)> All = new(() =>
    {
        var root = ContentPaths.TryGetContentRoot()
                   ?? throw new InvalidOperationException("Game-1-modular content root not found");

        // game_engine.py:135 — resource nodes FIRST
        var resourceNodes = new ResourceNodeDatabase();
        resourceNodes.LoadFromFiles(root);

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

        var npcs = new NpcDatabase();
        npcs.LoadFromFiles(root);  // boot state: no generated merge

        var chunkTemplates = new ChunkTemplateDatabase();
        chunkTemplates.LoadFromFiles(root);

        UpdateLoader.LoadAll(root, equipment, skills, materials, recipes, titles);

        return (materials, translations, recipes, equipment, titles, classes, skills,
                placements, resourceNodes, npcs, chunkTemplates);
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
    public void ResourceNodes_MatchPythonLoaderState()
    {
        var db = BootedDatabases.All.Value.ResourceNodes;
        var actual = new JsonObject();
        foreach (var kv in db.Nodes)
            actual[kv.Key] = kv.Value.ToParityNode();
        AssertParity("resource_nodes.json", "nodes", actual, db.Nodes.Count);
    }

    [Fact]
    public void ResourceNodes_CategoryCachesAndTierMap_MatchPython()
    {
        var db = BootedDatabases.All.Value.ResourceNodes;
        var golden = GoldenFixture.Load("db_parity/resource_nodes.json");

        static JsonArray Ids(List<ResourceNodeDefinition> list)
        {
            var arr = new JsonArray();
            foreach (var n in list) arr.Add(n.ResourceId);
            return arr;
        }

        var caches = new JsonObject
        {
            ["trees"] = Ids(db.Trees), ["ores"] = Ids(db.Ores), ["stones"] = Ids(db.Stones),
        };
        var cacheDiffs = JsonTreeComparer.Diff(golden.GetProperty("category_caches"), caches);
        Assert.True(cacheDiffs.Count == 0,
            "category_caches: " + string.Join("; ", cacheDiffs.Take(10)));

        var tierMap = new JsonObject();
        foreach (var kv in db.TierMap) tierMap[kv.Key] = kv.Value;
        var tierDiffs = JsonTreeComparer.Diff(golden.GetProperty("tier_map"), tierMap);
        Assert.True(tierDiffs.Count == 0,
            "tier_map: " + string.Join("; ", tierDiffs.Take(10)));
    }

    [Fact]
    public void ResourceConversionTables_MatchPythonModel()
    {
        var golden = GoldenFixture.Load("db_parity/resource_nodes.json");

        foreach (var e in golden.GetProperty("quantity_ranges").EnumerateObject())
        {
            var drop = new ResourceDrop { MaterialId = "x", Quantity = e.Name, Chance = "guaranteed" };
            var (min, max) = drop.GetQuantityRange();
            Assert.Equal(e.Value[0].GetInt32(), min);
            Assert.Equal(e.Value[1].GetInt32(), max);
        }
        foreach (var e in golden.GetProperty("chance_values").EnumerateObject())
        {
            var drop = new ResourceDrop { MaterialId = "x", Quantity = "few", Chance = e.Name };
            GoldenFixture.AssertClose(e.Value.GetDouble(), drop.GetChanceValue(), $"chance[{e.Name}]");
        }
        foreach (var e in golden.GetProperty("respawn_seconds").EnumerateObject())
        {
            var def = new ResourceNodeDefinition
            {
                ResourceId = "x", Name = "x", Category = "tree", Tier = 1,
                RequiredTool = "axe", BaseHealth = 100, RespawnTime = e.Name,
            };
            GoldenFixture.AssertClose(e.Value.GetDouble(), def.GetRespawnSeconds()!.Value,
                $"respawn[{e.Name}]");
        }
        Assert.True(golden.GetProperty("no_respawn_when_null").GetBoolean());
        var noRespawn = new ResourceNodeDefinition
        {
            ResourceId = "x", Name = "x", Category = "tree", Tier = 1,
            RequiredTool = "axe", BaseHealth = 100, RespawnTime = null,
        };
        Assert.Null(noRespawn.GetRespawnSeconds());
    }

    [Fact]
    public void Npcs_MatchPythonLoaderState()
    {
        var db = BootedDatabases.All.Value.Npcs;
        var golden = GoldenFixture.Load("db_parity/npcs_quests.json");
        Assert.Equal(golden.GetProperty("npc_count").GetInt32(), db.Npcs.Count);
        Assert.Equal(golden.GetProperty("source_version").GetString(), db.SourceVersion);

        var actual = new JsonObject();
        foreach (var kv in db.Npcs)
            actual[kv.Key] = kv.Value.ToParityNode();
        var diffs = JsonTreeComparer.Diff(golden.GetProperty("npcs"), actual);
        Assert.True(diffs.Count == 0,
            $"npcs: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(25)));
    }

    [Fact]
    public void Quests_MatchPythonLoaderState()
    {
        var db = BootedDatabases.All.Value.Npcs;
        var golden = GoldenFixture.Load("db_parity/npcs_quests.json");
        Assert.Equal(golden.GetProperty("quest_count").GetInt32(), db.Quests.Count);
        Assert.Equal(golden.GetProperty("quest_source_version").GetString(), db.QuestSourceVersion);

        var actual = new JsonObject();
        foreach (var kv in db.Quests)
            actual[kv.Key] = kv.Value.ToParityNode();
        var diffs = JsonTreeComparer.Diff(golden.GetProperty("quests"), actual);
        Assert.True(diffs.Count == 0,
            $"quests: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(25)));
    }

    [Fact]
    public void ChunkTemplates_MatchPythonLoaderState()
    {
        var db = BootedDatabases.All.Value.ChunkTemplates;
        var actual = new JsonObject();
        foreach (var kv in db.Templates)
            actual[kv.Key] = kv.Value.ToParityNode();
        AssertParity("chunk_templates.json", "templates", actual, db.Templates.Count);
    }

    [Fact]
    public void ChunkTemplates_GeoDispatchAndConstants_MatchPython()
    {
        var db = BootedDatabases.All.Value.ChunkTemplates;
        var golden = GoldenFixture.Load("db_parity/chunk_templates.json");

        var dispatch = new JsonObject();
        foreach (var kv in db.GeoDispatch) dispatch[kv.Key] = kv.Value;
        var diffs = JsonTreeComparer.Diff(golden.GetProperty("geo_dispatch"), dispatch);
        Assert.True(diffs.Count == 0, "geo_dispatch: " + string.Join("; ", diffs.Take(10)));

        foreach (var e in golden.GetProperty("density_weights").EnumerateObject())
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                ChunkTemplateDatabase.DensityWeights[e.Name], $"density[{e.Name}]");
        foreach (var e in golden.GetProperty("tier_bias_order").EnumerateObject())
            Assert.Equal(e.Value.GetInt32(), ChunkTemplateDatabase.TierBiasOrder[e.Name]);

        var stats = golden.GetProperty("stats");
        var (total, sacred, generated, geoEntries) = db.Stats();
        Assert.Equal(stats.GetProperty("total").GetInt32(), total);
        Assert.Equal(stats.GetProperty("sacred").GetInt32(), sacred);
        Assert.Equal(stats.GetProperty("generated").GetInt32(), generated);
        Assert.Equal(stats.GetProperty("geo_dispatch_entries").GetInt32(), geoEntries);
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
