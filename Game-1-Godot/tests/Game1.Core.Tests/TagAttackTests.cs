using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core;
using Game1.Core.Combat;
using Game1.Core.Content;
using Game1.Core.Data;
using Game1.Core.Progression;
using Game1.Core.Tags;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Replays the player_attack_enemy_with_tags scenarios that dump_databases.py
/// ran through the REAL Python Character + CombatManager (spec-built
/// loadouts, dual rng streams) via the C# composition root
/// (PlayerCharacter + TagAttackOrchestrator + EnemyRuntime + status system):
/// full damage composition, crits, statuses, enchants, kills/loot/EXP
/// cascades, durability — every end-state must be identical.
/// </summary>
public class TagAttackTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/tag_attack.json");

    private static string StateName(AiState s) => s switch
    {
        AiState.Idle => "idle", AiState.Wander => "wander",
        AiState.Patrol => "patrol", AiState.Guard => "guard",
        AiState.Chase => "chase", AiState.Attack => "attack",
        AiState.Flee => "flee", AiState.Dead => "dead", _ => "corpse",
    };

    private static PlayerCharacter BuildChar(JsonElement spec,
                                             EquipmentDatabase equipDb,
                                             MaterialDatabase matDb,
                                             StatScalingConfig scaling)
    {
        var stats = new CharacterStats(scaling);
        var inventory = new Inventory(matDb, equipDb, 30);
        var ch = new PlayerCharacter(stats, inventory, (0.0, 0.0))
        {
            Health = 100,
            MaxHealthValue = 100,
        };

        // character.py _give_starting_tools
        ch.Equipment.Slots["axe"] = equipDb.CreateEquipmentFromId("copper_axe");
        ch.Equipment.Slots["pickaxe"] = equipDb.CreateEquipmentFromId("copper_pickaxe");

        if (spec.TryGetProperty("stats", out var st))
        {
            foreach (var p in st.EnumerateObject())
            {
                var v = p.Value.GetInt32();
                switch (p.Name)
                {
                    case "strength": stats.Strength = v; break;
                    case "defense": stats.Defense = v; break;
                    case "vitality": stats.Vitality = v; break;
                    case "luck": stats.Luck = v; break;
                    case "agility": stats.Agility = v; break;
                    case "intelligence": stats.Intelligence = v; break;
                }
            }
        }

        if (spec.TryGetProperty("health", out var hp))
            ch.Health = hp.GetDouble();
        if (spec.TryGetProperty("exp", out var exp))
            ch.Leveling.CurrentExp = exp.GetInt64();
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
                var dmg = ws.TryGetProperty("damage", out var dm)
                    ? (dm[0].GetInt32(), dm[1].GetInt32()) : (0, 0);
                var item = new EquipmentItem
                {
                    ItemId = ws.GetProperty("item_id").GetString()!,
                    Name = ws.GetProperty("item_id").GetString()!,
                    Tier = ws.TryGetProperty("tier", out var t) ? t.GetDouble() : 1,
                    Rarity = "common",
                    Slot = w.Name,
                    Damage = dmg,
                    AttackSpeed = ws.TryGetProperty("attack_speed", out var asd)
                        ? asd.GetDouble() : 1.0,
                    Range = ws.TryGetProperty("range", out var rg)
                        ? rg.GetDouble() : 1.5,
                    HandType = ws.TryGetProperty("hand_type", out var ht)
                        ? ht.GetString()! : "default",
                    Tags = ws.TryGetProperty("tags", out var tg)
                        ? tg.EnumerateArray().Select(x => x.GetString()!).ToList()
                        : new List<string>(),
                };
                if (ws.TryGetProperty("enchantments", out var enchs))
                    foreach (var e in enchs.EnumerateArray())
                        item.Enchantments.Add(
                            (JsonObject)JsonNode.Parse(e.GetRawText())!);
                ch.Equipment.Slots[w.Name] = item;
            }
        }

        return ch;
    }

    private static JsonObject CharRow(PlayerCharacter ch)
    {
        var inventory = new JsonArray();
        foreach (var s in ch.Inventory.Slots)
            inventory.Add(s is null
                ? null
                : new JsonArray { s.ItemId, s.Quantity });

        var durability = new JsonObject();
        foreach (var kv in ch.Equipment.Slots
                     .OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            if (kv.Value is { } it)
                durability[kv.Key] = new JsonArray
                { it.DurabilityCurrent, it.DurabilityMax };
        }

        return new JsonObject
        {
            ["health"] = ch.Health,
            ["max_health"] = ch.MaxHealthValue,
            ["level"] = ch.Leveling.Level,
            ["exp"] = ch.Leveling.CurrentExp,
            ["stat_points"] = ch.Leveling.UnallocatedStatPoints,
            ["inventory"] = inventory,
            ["durability"] = durability,
        };
    }

    private static JsonObject EnemyRow(EnemyRuntime e)
    {
        var statuses = new JsonArray();
        foreach (var s in e.StatusManager.ActiveEffects)
            statuses.Add(new JsonObject
            {
                ["id"] = s.StatusId,
                ["stacks"] = s.Stacks,
                ["remaining"] = s.DurationRemaining,
            });

        return new JsonObject
        {
            ["health"] = e.CurrentHealth,
            ["alive"] = e.IsAlive,
            ["state"] = StateName(e.State),
            ["in_combat"] = e.InCombat,
            ["pos"] = new JsonArray { e.Position[0], e.Position[1] },
            ["knockback"] = new JsonArray
            {
                e.KnockbackVelocityX, e.KnockbackVelocityY,
                e.KnockbackDurationRemaining,
            },
            ["statuses"] = statuses,
        };
    }

    [Fact]
    public void PlayerAttackEnemyWithTags_Scenarios_MatchPython()
    {
        var root = ContentPaths.TryGetContentRoot()!;
        var dbs = BootedDatabases.All.Value;
        var registry = TagRegistry.LoadFrom(root);
        var scaling = StatScalingConfig.Load(root);

        var enemyDb = new EnemyDatabase();
        enemyDb.LoadFromFiles(root);
        UpdateLoader.LoadEnemyUpdates(root, enemyDb);

        var cases = G.GetProperty("cases").EnumerateArray().ToList();
        var results = G.GetProperty("results").EnumerateArray().ToList();
        Assert.Equal(cases.Count, results.Count);

        for (var i = 0; i < cases.Count; i++)
        {
            var caseEl = cases[i];
            var id = caseEl.GetProperty("id").GetString();

            var charSpec = caseEl.TryGetProperty("char", out var cs)
                ? cs : default;
            var ch = BuildChar(charSpec, dbs.Equipment, dbs.Materials, scaling);

            var managerRng = new PythonRandom(9000 + i);
            var globalRng = new PythonRandom(13000 + i);

            var orch = new TagAttackOrchestrator(ch, registry, managerRng, globalRng);
            orch.Config.LoadFromFile(
                Path.Combine(root, "Definitions.JSON", "combat-config.JSON"));

            var enemies = new List<EnemyRuntime>();
            foreach (var es in caseEl.GetProperty("enemies").EnumerateArray())
            {
                var pos = es.GetProperty("pos");
                enemies.Add(new EnemyRuntime(
                    enemyDb.Enemies[es.GetProperty("enemy_id").GetString()!],
                    (pos[0].GetDouble(), pos[1].GetDouble()), (0, 0), globalRng));
            }
            orch.ActiveEnemies = enemies;

            var attack = caseEl.GetProperty("attack");
            var target = enemies[attack.GetProperty("target").GetInt32()];
            var tags = attack.GetProperty("tags").EnumerateArray()
                .Select(t => t.GetString()!).ToList();
            var params_ = TagRegistry.ToPlain(
                    JsonNode.Parse(attack.GetProperty("params").GetRawText()))
                as Dictionary<string, object?>;

            var res = orch.PlayerAttackEnemyWithTags(target, tags, params_);

            var loot = new JsonArray();
            foreach (var (m, q) in res.Loot)
                loot.Add(new JsonArray { m, q });

            var actual = new JsonObject
            {
                ["id"] = id,
                ["damage"] = res.TotalDamage,
                ["crit"] = res.IsCrit,
                ["loot"] = loot,
                ["char"] = CharRow(ch),
                ["enemies"] = new JsonArray(
                    enemies.Select(e => (JsonNode?)EnemyRow(e)).ToArray()),
                ["rng_manager"] = managerRng.NextDouble(),
                ["rng_global"] = globalRng.NextDouble(),
            };

            var diffs = JsonTreeComparer.Diff(results[i], actual);
            Assert.True(diffs.Count == 0,
                $"case[{id}]: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(20)));
        }
    }
}
