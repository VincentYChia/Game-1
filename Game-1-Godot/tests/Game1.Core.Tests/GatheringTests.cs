using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core;
using Game1.Core.Combat;
using Game1.Core.Content;
using Game1.Core.Data;
using Game1.Core.Progression;
using Game1.Core.World;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Replays the gathering + enemy→player damage scenarios dump_databases.py
/// ran through the REAL Character / NaturalResource / CombatManager:
/// harvest damage composition, crits, DEF-scaled fractional durability,
/// LCK/Fortune loot processing, title-award churn, the fishing-activity
/// drop bug, devastate Chain Harvest, and the full defense pipeline with
/// shields / Protection / fortify / Thorns / lethal respawn.
/// </summary>
public class GatheringTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/gathering_damage.json");

    private static PlayerCharacter BuildChar(JsonElement spec)
    {
        var root = ContentPaths.TryGetContentRoot()!;
        var dbs = BootedDatabases.All.Value;
        var scaling = StatScalingConfig.Load(root);
        var ch = new PlayerCharacter(new CharacterStats(scaling),
                                     new Inventory(dbs.Materials, dbs.Equipment, 30),
                                     (0.0, 0.0))
        { Health = 100, MaxHealthValue = 100 };

        ch.Equipment.Slots["axe"] = dbs.Equipment.CreateEquipmentFromId("copper_axe");
        ch.Equipment.Slots["pickaxe"] = dbs.Equipment.CreateEquipmentFromId("copper_pickaxe");

        // shieldMechanics caps from combat-config.JSON (Python _get_combat_config)
        var combatCfg = JsonNode.Parse(File.ReadAllText(
            Path.Combine(root, "Definitions.JSON", "combat-config.JSON"))) as JsonObject;
        if (combatCfg?["shieldMechanics"] is JsonObject shield)
        {
            ch.ShieldMinReduction =
                shield["minDamageReduction"]?.GetValue<double>() ?? 0.0;
            ch.ShieldMaxReduction =
                shield["maxDamageReduction"]?.GetValue<double>() ?? 0.75;
        }

        if (spec.ValueKind == JsonValueKind.Undefined) return ch;

        if (spec.TryGetProperty("stats", out var st))
        {
            foreach (var p in st.EnumerateObject())
            {
                var v = p.Value.GetInt32();
                switch (p.Name)
                {
                    case "strength": ch.Stats.Strength = v; break;
                    case "defense": ch.Stats.Defense = v; break;
                    case "vitality": ch.Stats.Vitality = v; break;
                    case "luck": ch.Stats.Luck = v; break;
                    case "agility": ch.Stats.Agility = v; break;
                    case "intelligence": ch.Stats.Intelligence = v; break;
                }
            }
        }
        if (spec.TryGetProperty("health", out var hp))
            ch.Health = hp.GetDouble();
        if (spec.TryGetProperty("selected_slot", out var sel))
            ch.SelectedSlot = sel.GetString();
        if (spec.TryGetProperty("titles", out var titles))
        {
            foreach (var tspec in titles.EnumerateArray())
            {
                ch.Titles.EarnedTitles.Add(new TitleDefinition
                {
                    TitleId = tspec.GetProperty("title_id").GetString()!,
                    Name = tspec.GetProperty("title_id").GetString()!,
                    Tier = "novice", Category = "combat", BonusDescription = "",
                    Bonuses = (JsonObject)JsonNode.Parse(
                        tspec.GetProperty("bonuses").GetRawText())!,
                });
            }
        }
        if (spec.TryGetProperty("buffs", out var buffs))
        {
            foreach (var b in buffs.EnumerateArray())
            {
                var duration = b.TryGetProperty("duration", out var d)
                    ? d.GetDouble() : 30.0;
                ch.Buffs.AddBuff(new ActiveBuff
                {
                    BuffId = b.GetProperty("buff_id").GetString()!,
                    Name = b.GetProperty("buff_id").GetString()!,
                    EffectType = b.GetProperty("effect_type").GetString()!,
                    Category = b.GetProperty("category").GetString()!,
                    Magnitude = "moderate",
                    BonusValue = b.GetProperty("bonus_value").GetDouble(),
                    Duration = duration,
                    DurationRemaining = duration,
                    ConsumeOnUse = b.TryGetProperty("consume_on_use", out var c)
                                   && c.GetBoolean(),
                });
            }
        }
        if (spec.TryGetProperty("weapons", out var weapons))
        {
            foreach (var w in weapons.EnumerateObject())
            {
                var ws = w.Value;
                var dmg = ws.TryGetProperty("damage", out var dmEl)
                    ? (dmEl[0].GetInt32(), dmEl[1].GetInt32()) : (0, 0);
                var item = new EquipmentItem
                {
                    ItemId = ws.GetProperty("item_id").GetString()!,
                    Name = ws.GetProperty("item_id").GetString()!,
                    Tier = ws.TryGetProperty("tier", out var t) ? t.GetDouble() : 1,
                    Rarity = "common",
                    Slot = w.Name,
                    Damage = dmg,
                    Defense = ws.TryGetProperty("defense", out var def)
                        ? def.GetInt32() : 0,
                    AttackSpeed = ws.TryGetProperty("attack_speed", out var asd)
                        ? asd.GetDouble() : 1.0,
                    Range = ws.TryGetProperty("range", out var rg)
                        ? rg.GetDouble() : 1.5,
                    HandType = ws.TryGetProperty("hand_type", out var ht)
                        ? ht.GetString()! : "default",
                    ItemType = ws.TryGetProperty("item_type", out var it)
                        ? it.GetString()! : "weapon",
                    StatMultipliers = ws.TryGetProperty("stat_multipliers", out var sm)
                        ? JsonNode.Parse(sm.GetRawText())! : new JsonObject(),
                    Tags = ws.TryGetProperty("tags", out var tg)
                        ? tg.EnumerateArray().Select(x => x.GetString()!).ToList()
                        : new List<string>(),
                };
                if (ws.TryGetProperty("bonuses", out var bon))
                    item.Bonuses = (JsonObject)JsonNode.Parse(bon.GetRawText())!;
                if (ws.TryGetProperty("enchantments", out var enchs))
                    foreach (var e in enchs.EnumerateArray())
                        item.Enchantments.Add(
                            (JsonObject)JsonNode.Parse(e.GetRawText())!);
                ch.Equipment.Slots[w.Name] = item;
            }
        }
        if (spec.TryGetProperty("activities", out var acts))
            foreach (var p in acts.EnumerateObject())
                if (ch.Activities.ActivityCounts.ContainsKey(p.Name))
                    ch.Activities.ActivityCounts[p.Name] = p.Value.GetInt32();
        return ch;
    }

    private static JsonObject CharRow(PlayerCharacter ch)
    {
        var activities = new JsonObject();
        foreach (var k in ch.Activities.ActivityCounts.Keys.OrderBy(k => k, StringComparer.Ordinal))
            activities[k] = ch.Activities.ActivityCounts[k];

        var inventory = new JsonArray();
        foreach (var s in ch.Inventory.Slots)
            inventory.Add(s is null ? null : new JsonArray { s.ItemId, s.Quantity });

        var durability = new JsonObject();
        foreach (var kv in ch.Equipment.Slots.OrderBy(kv => kv.Key, StringComparer.Ordinal))
            if (kv.Value is { } item)
                durability[kv.Key] = new JsonArray
                { ch.ExactDurability(item), item.DurabilityMax };

        return new JsonObject
        {
            ["health"] = ch.Health,
            ["exp"] = ch.Leveling.CurrentExp,
            ["level"] = ch.Leveling.Level,
            ["shield_amount"] = ch.ShieldAmount,
            ["activities"] = activities,
            ["titles"] = new JsonArray(ch.Titles.EarnedTitles
                .Select(t => (JsonNode?)JsonValue.Create(t.TitleId)).ToArray()),
            ["inventory"] = inventory,
            ["durability"] = durability,
        };
    }

    private static JsonObject ResourceRow(NaturalResourceRuntime r)
    {
        var lootTable = new JsonArray();
        foreach (var ld in r.LootTable)
            lootTable.Add(new JsonArray
            { ld.ItemId, ld.MinQuantity, ld.MaxQuantity, ld.Chance });
        return new JsonObject
        {
            ["hp"] = r.CurrentHp, ["max_hp"] = r.MaxHp,
            ["depleted"] = r.Depleted, ["respawns"] = r.Respawns,
            ["respawn_timer"] = r.RespawnTimer is { } t ? t : null,
            ["time_until_respawn"] = r.TimeUntilRespawn,
            ["required_tool"] = r.RequiredTool,
            ["loot_table"] = lootTable,
        };
    }

    private static void AssertMatch(JsonElement expected, JsonNode actual, string label)
    {
        var diffs = JsonTreeComparer.Diff(expected, actual);
        Assert.True(diffs.Count == 0,
            $"{label}: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(20)));
    }

    [Fact]
    public void Gathering_Scenarios_MatchPython()
    {
        var dbs = BootedDatabases.All.Value;
        var cases = G.GetProperty("gather_cases").EnumerateArray().ToList();
        var results = G.GetProperty("gather_results").EnumerateArray().ToList();

        for (var i = 0; i < cases.Count; i++)
        {
            var caseEl = cases[i];
            var id = caseEl.GetProperty("id").GetString();
            var ch = BuildChar(caseEl.TryGetProperty("char", out var cs) ? cs : default);
            var rng = new PythonRandom(31000 + i);
            var gathering = new GatheringSystem(ch, dbs.Titles, rng);

            var resources = new List<NaturalResourceRuntime>();
            foreach (var rs in caseEl.GetProperty("resources").EnumerateArray())
            {
                var pos = rs.GetProperty("pos");
                resources.Add(new NaturalResourceRuntime(
                    new Position(pos[0].GetDouble(), pos[1].GetDouble(), 0.0),
                    rs.GetProperty("type").GetString()!,
                    rs.GetProperty("tier").GetInt32(),
                    dbs.ResourceNodes));
            }
            var target = resources[caseEl.GetProperty("target").GetInt32()];
            var nearby = resources.Count > 1 ? resources : null;

            var harvests = new JsonArray();
            var swings = caseEl.GetProperty("swings").GetInt32();
            for (var s = 0; s < swings; s++)
            {
                if (target.Depleted) break;
                var result = gathering.HarvestResource(target, nearby);
                if (result is { } r)
                {
                    var loot = new JsonArray();
                    foreach (var (m, q) in r.Loot)
                        loot.Add(new JsonArray { m, q });
                    harvests.Add(new JsonObject
                    {
                        ["loot"] = loot, ["damage"] = r.Damage, ["crit"] = r.Crit,
                    });
                }
                else
                {
                    harvests.Add(null);
                }
            }
            target.Update(20.0);

            var actual = new JsonObject
            {
                ["id"] = id,
                ["harvests"] = harvests,
                ["char"] = CharRow(ch),
                ["resources"] = new JsonArray(
                    resources.Select(r => (JsonNode?)ResourceRow(r)).ToArray()),
                ["rng_global"] = rng.NextDouble(),
            };
            AssertMatch(results[i], actual, $"gather[{id}]");
        }
    }

    [Fact]
    public void EnemyHits_MatchPython()
    {
        var root = ContentPaths.TryGetContentRoot()!;
        var enemyDb = new EnemyDatabase();
        enemyDb.LoadFromFiles(root);
        UpdateLoader.LoadEnemyUpdates(root, enemyDb);

        var cases = G.GetProperty("enemy_hit_cases").EnumerateArray().ToList();
        var results = G.GetProperty("enemy_hit_results").EnumerateArray().ToList();

        for (var i = 0; i < cases.Count; i++)
        {
            var caseEl = cases[i];
            var id = caseEl.GetProperty("id").GetString();
            var ch = BuildChar(caseEl.TryGetProperty("char", out var cs) ? cs : default);
            var globalRng = new PythonRandom(51000 + i);
            var enemy = new EnemyRuntime(
                enemyDb.Enemies[caseEl.GetProperty("enemy").GetString()!],
                (2.0, 0.0), (0, 0), globalRng);
            var shieldBlocking = caseEl.GetProperty("shield_blocking").GetBoolean();

            var hits = new JsonArray();
            var attacks = caseEl.GetProperty("attacks").GetInt32();
            for (var a = 0; a < attacks; a++)
            {
                enemy.AttackPhase = "idle";
                enemy.StartPhasedAttack((0.0, 0.0));
                EnemyAttackResolver.Resolve(enemy, ch, shieldBlocking);
                hits.Add(new JsonObject
                {
                    ["player_health"] = ch.Health,
                    ["enemy_health"] = enemy.CurrentHealth,
                    ["enemy_alive"] = enemy.IsAlive,
                });
            }

            var actual = new JsonObject
            {
                ["id"] = id,
                ["hits"] = hits,
                ["char"] = CharRow(ch),
                ["rng_global"] = globalRng.NextDouble(),
            };
            AssertMatch(results[i], actual, $"enemy_hit[{id}]");
        }
    }
}
