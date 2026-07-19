using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core;
using Game1.Core.Combat;
using Game1.Core.Content;
using Game1.Core.Data;
using Xunit;

namespace Game1.Core.Tests;

public class EnemyTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/enemies.json");

    private static EnemyDatabase Load()
    {
        var root = ContentPaths.TryGetContentRoot()!;
        var db = new EnemyDatabase();
        db.LoadFromFiles(root);
        UpdateLoader.LoadEnemyUpdates(root, db);
        return db;
    }

    private static JsonObject EnemyRow(EnemyDefinition e)
    {
        static JsonArray Strings(IEnumerable<string> xs)
        {
            var a = new JsonArray();
            foreach (var x in xs) a.Add(x);
            return a;
        }
        var drops = new JsonArray();
        foreach (var d in e.Drops)
            drops.Add(new JsonObject
            {
                ["material_id"] = d.MaterialId, ["quantity_min"] = d.QuantityMin,
                ["quantity_max"] = d.QuantityMax, ["chance"] = d.Chance,
            });
        var attacks = new JsonArray();
        foreach (var a in e.Attacks)
            attacks.Add(new JsonObject
            {
                ["attack_id"] = a.AttackId, ["shape"] = a.Shape, ["arc"] = a.Arc,
                ["range"] = a.Range, ["windup"] = a.Windup, ["active"] = a.Active,
                ["recovery"] = a.Recovery, ["weight"] = a.Weight,
                ["tags"] = Strings(a.Tags), ["screen_shake"] = a.ScreenShake,
                ["damage_multiplier"] = a.DamageMultiplier,
                ["status_tags"] = Strings(a.StatusTags),
            });
        return new JsonObject
        {
            ["enemy_id"] = e.EnemyId, ["name"] = e.Name, ["tier"] = e.Tier,
            ["category"] = e.Category, ["behavior"] = e.Behavior,
            ["max_health"] = e.MaxHealth, ["damage_min"] = e.DamageMin,
            ["damage_max"] = e.DamageMax, ["defense"] = e.Defense,
            ["speed"] = e.Speed, ["aggro_range"] = e.AggroRange,
            ["attack_speed"] = e.AttackSpeed,
            ["drops"] = drops,
            ["ai_pattern"] = new JsonObject
            {
                ["default_state"] = e.Ai.DefaultState,
                ["aggro_on_damage"] = e.Ai.AggroOnDamage,
                ["aggro_on_proximity"] = e.Ai.AggroOnProximity,
                ["flee_at_health"] = e.Ai.FleeAtHealth,
                ["call_for_help_radius"] = e.Ai.CallForHelpRadius,
                ["pack_coordination"] = e.Ai.PackCoordination,
                ["special_abilities"] = Strings(e.Ai.SpecialAbilities),
            },
            ["special_ability_ids"] = Strings(e.SpecialAbilities.Select(a => a.AbilityId)),
            ["narrative"] = e.Narrative, ["tags"] = Strings(e.Tags),
            ["icon_path"] = e.IconPath is null ? null : JsonValue.Create(e.IconPath),
            ["visual_size"] = e.VisualSize, ["hurtbox_radius"] = e.HurtboxRadius,
            ["attacks"] = attacks,
        };
    }

    [Fact]
    public void Definitions_And_GeneratedAttackProfiles_MatchPython()
    {
        var db = Load();
        Assert.Equal(G.GetProperty("count").GetInt32(), db.Enemies.Count);

        var actual = new JsonObject();
        foreach (var kv in db.Enemies)
            actual[kv.Key] = EnemyRow(kv.Value);
        var diffs = JsonTreeComparer.Diff(G.GetProperty("enemies"), actual);
        Assert.True(diffs.Count == 0,
            $"enemies: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(20)));

        foreach (var e in G.GetProperty("by_tier").EnumerateObject())
            Assert.Equal(
                e.Value.EnumerateArray().Select(x => x.GetString()),
                db.EnemiesByTier[long.Parse(e.Name)].Select(d => d.EnemyId));
    }

    [Fact]
    public void LootStreams_MatchPython_SeededGlobalRandom()
    {
        var db = Load();
        var lootEnemies = G.GetProperty("loot_enemies").EnumerateArray()
            .Select(x => x.GetString()!).ToList();

        foreach (var seedCase in G.GetProperty("loot_streams").EnumerateObject())
        {
            var rng = new PythonRandom(long.Parse(seedCase.Name));
            var expected = seedCase.Value.EnumerateArray().ToList();
            var idx = 0;
            foreach (var eid in lootEnemies)
            {
                var def = db.Enemies[eid];
                for (var i = 0; i < 4; i++)
                {
                    var loot = def.GenerateLoot(rng);
                    var exp = expected[idx++];
                    Assert.Equal(exp.GetProperty("enemy").GetString(), eid);
                    var expLoot = exp.GetProperty("loot").EnumerateArray()
                        .Select(l => (l[0].GetString()!, l[1].GetInt64())).ToList();
                    Assert.True(expLoot.SequenceEqual(
                            loot.Select(l => (l.MaterialId, l.Quantity))),
                        $"loot[{seedCase.Name}][{eid}#{i}] mismatch");
                }
            }
        }
    }
}
