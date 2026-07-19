using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core;
using Game1.Core.Combat;
using Game1.Core.Content;
using Game1.Core.Data;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Replays the exact AI scripts dump_databases.py ran on REAL Python Enemy
/// objects (seeded global rng) through EnemyRuntime and requires identical
/// state at every step: movement, aggro, chase/attack transitions, knockback,
/// phased attacks, flee/death, ability gating, night modifiers + safe zone.
/// </summary>
public class EnemyAiTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/enemy_ai.json");

    private static EnemyDatabase LoadEnemies()
    {
        var root = ContentPaths.TryGetContentRoot()!;
        var db = new EnemyDatabase();
        db.LoadFromFiles(root);
        UpdateLoader.LoadEnemyUpdates(root, db);
        return db;
    }

    private static string StateName(AiState s) => s switch
    {
        AiState.Idle => "idle",
        AiState.Wander => "wander",
        AiState.Patrol => "patrol",
        AiState.Guard => "guard",
        AiState.Chase => "chase",
        AiState.Attack => "attack",
        AiState.Flee => "flee",
        AiState.Dead => "dead",
        _ => "corpse",
    };

    private static JsonObject StateRow(EnemyRuntime e) => new()
    {
        ["pos"] = new JsonArray { e.Position[0], e.Position[1] },
        ["state"] = StateName(e.State),
        ["health"] = e.CurrentHealth,
        ["alive"] = e.IsAlive,
        ["facing"] = e.FacingAngle,
        ["attack_cooldown"] = e.AttackCooldown,
        ["in_combat"] = e.InCombat,
        ["wander_timer"] = e.WanderTimer,
        ["wander_cooldown"] = e.WanderCooldown,
        ["target"] = e.TargetPosition is null
            ? null : new JsonArray { e.TargetPosition[0], e.TargetPosition[1] },
        ["phase"] = e.AttackPhase,
        ["phase_timer"] = e.AttackPhaseTimer,
        ["windup_ms"] = e.AttackWindupMs,
        ["active_ms"] = e.AttackActiveMs,
        ["recovery_ms"] = e.AttackRecoveryMs,
        ["arc"] = e.AttackArcDegrees,
        ["radius"] = e.AttackRadius,
        ["shape"] = e.AttackShape,
        ["anim_timer"] = e.AttackAnimTimer,
        ["anim_tags"] = new JsonArray(e.AttackAnimTags.Select(t => (JsonNode?)t).ToArray()),
        ["anim_lunge"] = e.AttackAnimLunge,
        ["attack_target"] = e.AttackTargetPos is null
            ? null : new JsonArray { e.AttackTargetPos.Value.X, e.AttackTargetPos.Value.Y },
        ["knockback"] = new JsonArray
        {
            e.KnockbackVelocityX, e.KnockbackVelocityY, e.KnockbackDurationRemaining,
        },
        ["time_since_death"] = e.TimeSinceDeath,
        ["windup_progress"] = e.WindupProgress,
    };

    private static void Merge(JsonObject into, JsonObject extra)
    {
        foreach (var kv in extra.ToList())
        {
            extra.Remove(kv.Key);
            into[kv.Key] = kv.Value;
        }
    }

    private static void AssertMatch(JsonElement expected, JsonNode actual, string label)
    {
        var diffs = JsonTreeComparer.Diff(expected, actual);
        Assert.True(diffs.Count == 0,
            $"{label}: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(20)));
    }

    private static JsonArray RunEnemyAi(EnemyDefinition edef)
    {
        var rng = new PythonRandom(20240);
        var e = new EnemyRuntime(edef, (10.0, 10.0), (0, 0), rng);
        var rows = new JsonArray { StateRow(e) };
        var playerX = 30.0;
        for (var i = 0; i < 40; i++)
        {
            if (playerX > 11.0) playerX -= 1.0;
            e.UpdateAi(0.1, (playerX, 10.0));
            rows.Add(StateRow(e));
        }

        var d1 = e.TakeDamage(e.MaxHealth * 0.4);
        var damagedRow = new JsonObject { ["event"] = "damaged", ["died"] = d1 };
        Merge(damagedRow, StateRow(e));
        rows.Add(damagedRow);

        e.KnockbackVelocityX = 4.0;
        e.KnockbackVelocityY = -2.0;
        e.KnockbackDurationRemaining = 0.5;
        for (var i = 0; i < 6; i++)
        {
            e.UpdateAi(0.1, (playerX, 10.0));
            rows.Add(StateRow(e));
        }

        var can1 = e.CanAttack();
        var started = e.StartPhasedAttack((playerX, 10.0));
        var transitions = new JsonArray();
        for (var i = 0; i < 30; i++)
        {
            var t = e.UpdateAttackPhase(100.0);
            transitions.Add(t is null ? null : JsonValue.Create(t));
        }
        var dmg = e.PerformAttack();
        var attackRow = new JsonObject
        {
            ["event"] = "attack", ["can_before"] = can1, ["started"] = started,
            ["transitions"] = transitions, ["damage"] = dmg,
        };
        Merge(attackRow, StateRow(e));
        rows.Add(attackRow);

        var abil0 = e.CanUseSpecialAbility(2.0);
        e.CurrentHealth = e.MaxHealth * 0.15;
        var abilByDist = new JsonObject();
        foreach (var dist in new[] { 0.5, 2.0, 10.0, 100.0 })
        {
            var a = e.CanUseSpecialAbility(dist);
            // Python str(float) keys: 0.5 / 2.0 / 10.0 / 100.0
            var key = dist == Math.Floor(dist)
                ? $"{(long)dist}.0" : dist.ToString("R");
            abilByDist[key] = a is null ? null : JsonValue.Create(a.AbilityId);
        }
        var d2 = e.TakeDamage(999999.0);
        e.UpdateAi(0.5, (playerX, 10.0));
        e.UpdateAi(0.5, (playerX, 10.0));
        var deathRow = new JsonObject
        {
            ["event"] = "death", ["died"] = d2,
            ["abil_full_hp"] = abil0 is null ? null : JsonValue.Create(abil0.AbilityId),
            ["abil_by_dist"] = abilByDist,
        };
        Merge(deathRow, StateRow(e));
        rows.Add(deathRow);
        return rows;
    }

    private static JsonArray RunEnemyNight(EnemyDefinition edef)
    {
        var rng = new PythonRandom(555);
        var e = new EnemyRuntime(edef, (5.0, 5.0), (0, 0), rng);
        var rows = new JsonArray();
        for (var i = 0; i < 25; i++)
        {
            e.UpdateAi(0.1, (12.0, 5.0), aggroMultiplier: 1.3,
                       speedMultiplier: 1.15,
                       safeZoneCenter: (10.0, 5.0), safeZoneRadius: 2.0);
            rows.Add(StateRow(e));
        }
        return rows;
    }

    [Fact]
    public void EnemyAi_Scenarios_MatchPython()
    {
        var db = LoadEnemies();
        var aiIds = G.GetProperty("ai_ids").EnumerateArray()
            .Select(x => x.GetString()!).ToList();

        var scenarios = G.GetProperty("scenarios");
        foreach (var eid in aiIds)
            AssertMatch(scenarios.GetProperty(eid), RunEnemyAi(db.Enemies[eid]),
                        $"scenario[{eid}]");

        var night = G.GetProperty("night");
        foreach (var eid in aiIds.Take(3))
            AssertMatch(night.GetProperty(eid), RunEnemyNight(db.Enemies[eid]),
                        $"night[{eid}]");
    }
}
