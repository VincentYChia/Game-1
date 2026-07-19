using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core;
using Game1.Core.Combat;
using Game1.Core.Content;
using Game1.Core.Data;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Replays the exact scripts dump_databases.py ran through the REAL Python
/// classes (attack state machine, hitbox system, projectile system, combat
/// data loader) and requires identical state at every step.
/// </summary>
public class ActionCombatTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/action_combat.json");

    /// <summary>Python str(float) for fixture keys: integral values keep ".0".</summary>
    private static string PyStr(double v) =>
        v == Math.Floor(v) && Math.Abs(v) < 1e16
            ? ((long)v).ToString(CultureInfo.InvariantCulture) + ".0"
            : v.ToString("R", CultureInfo.InvariantCulture);

    private static void AssertMatch(JsonElement expected, JsonNode actual, string label)
    {
        var diffs = JsonTreeComparer.Diff(expected, actual);
        Assert.True(diffs.Count == 0,
            $"{label}: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(20)));
    }

    private static JsonArray Strings(IEnumerable<string> xs)
    {
        var a = new JsonArray();
        foreach (var x in xs) a.Add(x);
        return a;
    }

    private static JsonArray Ints(IEnumerable<int> xs)
    {
        var a = new JsonArray();
        foreach (var x in xs) a.Add(x);
        return a;
    }

    private static JsonObject AttackRow(AttackDefinition a)
    {
        var p = a.HitboxParamsData;
        var hp = new JsonObject { ["offset_forward"] = p.OffsetForward };
        if (p.Shape is not null) hp["shape"] = p.Shape;
        if (p.Radius is not null) hp["radius"] = p.Radius;
        if (p.ArcDegrees is not null) hp["arc_degrees"] = p.ArcDegrees;
        if (p.Length is not null) hp["length"] = p.Length;
        if (p.Width is not null) hp["width"] = p.Width;
        if (p.Height is not null) hp["height"] = p.Height;
        if (p.OffsetLateral is not null) hp["offset_lateral"] = p.OffsetLateral;
        if (p.Piercing is not null) hp["piercing"] = p.Piercing;
        return new JsonObject
        {
            ["attack_id"] = a.AttackId,
            ["windup_ms"] = a.WindupMs, ["active_ms"] = a.ActiveMs,
            ["recovery_ms"] = a.RecoveryMs, ["cooldown_ms"] = a.CooldownMs,
            ["hitbox_shape"] = a.HitboxShape, ["hitbox_params"] = hp,
            ["damage_multiplier"] = a.DamageMultiplier,
            ["movement_multiplier"] = a.MovementMultiplier,
            ["can_be_interrupted"] = a.CanBeInterrupted,
            ["animation_id"] = a.AnimationId,
            ["projectile_id"] = a.ProjectileId is null ? null : JsonValue.Create(a.ProjectileId),
            ["status_tags"] = Strings(a.StatusTags),
            ["screen_shake"] = a.ScreenShake,
            ["telegraph_color"] = Ints(a.TelegraphColor),
            ["combo_next"] = a.ComboNext is null ? null : JsonValue.Create(a.ComboNext),
            ["combo_window_ms"] = a.ComboWindowMs,
            ["tags"] = Strings(a.Tags),
        };
    }

    private static string PhaseName(AttackPhase p) => p switch
    {
        AttackPhase.Idle => "idle",
        AttackPhase.Windup => "windup",
        AttackPhase.Active => "active",
        AttackPhase.Recovery => "recovery",
        _ => "cooldown",
    };

    // ── 1) Attack state machine timeline ─────────────────────────────────

    private static JsonObject AsmSnapshot(AttackStateMachine sm,
                                          List<CombatEvent> events,
                                          List<bool>? results = null)
    {
        var evs = new JsonArray();
        foreach (var ev in events)
        {
            evs.Add(new JsonObject
            {
                ["type"] = ev.EventType,
                ["source"] = ev.SourceId,
                ["phase"] = ev.Data.TryGetValue("phase", out var ph) && ph is string s
                    ? s : null,
                ["attack"] = ev.Data.TryGetValue("attack", out var atk)
                             && atk is AttackDefinition ad
                    ? ad.AttackId : null,
            });
        }
        var res = new JsonArray();
        foreach (var r in results ?? new List<bool>()) res.Add(r);
        return new JsonObject
        {
            ["phase"] = PhaseName(sm.Phase),
            ["timer"] = sm.PhaseTimer,
            ["combo_count"] = sm.ComboCount,
            ["combo_timer"] = sm.ComboTimer,
            ["movement_multiplier"] = sm.MovementMultiplier,
            ["windup_progress"] = sm.WindupProgress,
            ["is_attacking"] = sm.IsAttacking,
            ["is_active"] = sm.IsInActivePhase,
            ["is_vulnerable"] = sm.IsVulnerable,
            ["current_attack"] = sm.CurrentAttack?.AttackId is null
                ? null : JsonValue.Create(sm.CurrentAttack.AttackId),
            ["hits"] = Strings(sm.HitsThisSwing.OrderBy(x => x, StringComparer.Ordinal)),
            ["events"] = evs,
            ["results"] = res,
        };
    }

    [Fact]
    public void StateMachine_Timeline_MatchesPython()
    {
        var atkA = new AttackDefinition
        {
            AttackId = "combo_a", WindupMs = 300, ActiveMs = 200,
            RecoveryMs = 240, CooldownMs = 400, MovementMultiplier = 0.6,
            ComboNext = "combo_a2", ComboWindowMs = 250,
        };
        var atkB = new AttackDefinition
        {
            AttackId = "locked_b", WindupMs = 200, ActiveMs = 150,
            RecoveryMs = 100, CooldownMs = 300, CanBeInterrupted = false,
        };
        var atkC = new AttackDefinition
        {
            AttackId = "soft_c", WindupMs = 500, ActiveMs = 100,
            RecoveryMs = 100, CooldownMs = 100,
        };

        var sm = new AttackStateMachine("player");
        var steps = new JsonArray();
        var none = new List<CombatEvent>();
        steps.Add(AsmSnapshot(sm, none, new List<bool> { sm.StartAttack(atkA, new()) }));
        steps.Add(AsmSnapshot(sm, sm.Update(100)));
        steps.Add(AsmSnapshot(sm, sm.Update(250)));
        steps.Add(AsmSnapshot(sm, none, new List<bool>
        {
            sm.RecordHit("e1"), sm.RecordHit("e1"), sm.RecordHit("e2"),
        }));
        steps.Add(AsmSnapshot(sm, sm.Update(200)));
        steps.Add(AsmSnapshot(sm, sm.Update(240)));
        steps.Add(AsmSnapshot(sm, none, new List<bool> { sm.StartAttack(atkA, new()) }));
        foreach (var big in new[] { 5000, 5000, 5000, 5000 })
            steps.Add(AsmSnapshot(sm, sm.Update(big)));
        steps.Add(AsmSnapshot(sm, sm.Update(100)));
        steps.Add(AsmSnapshot(sm, sm.Update(200)));
        steps.Add(AsmSnapshot(sm, none, new List<bool>
        {
            sm.StartAttack(atkB, new()), sm.Interrupt(),
        }));
        sm.ForceReset();
        steps.Add(AsmSnapshot(sm, none));
        steps.Add(AsmSnapshot(sm, none, new List<bool> { sm.StartAttack(atkC, new()) }));
        steps.Add(AsmSnapshot(sm, sm.Update(50)));
        steps.Add(AsmSnapshot(sm, none, new List<bool> { sm.Interrupt() }));

        AssertMatch(G.GetProperty("state_machine"), steps, "state_machine");
    }

    // ── 2) Hitbox collision matrix + event flow ──────────────────────────

    private static JsonArray HitRows(List<HitEvent> hits)
    {
        var arr = new JsonArray();
        foreach (var h in hits)
        {
            arr.Add(new JsonObject
            {
                ["attacker"] = h.AttackerId,
                ["target"] = h.TargetId,
                ["pos"] = new JsonArray { h.HitPosition.X, h.HitPosition.Y },
                ["proj"] = h.IsProjectile,
            });
        }
        return arr;
    }

    [Fact]
    public void Hitbox_Matrix_WorldPos_And_Flow_MatchPython()
    {
        var shapes = new[]
        {
            new HitboxDefinition { Shape = "arc", Radius = 2.0, ArcDegrees = 90.0 },
            new HitboxDefinition { Shape = "arc", Radius = 2.6, ArcDegrees = 55.0 },
            new HitboxDefinition { Shape = "circle", Radius = 1.2 },
            new HitboxDefinition { Shape = "rect", Width = 1.0, Height = 3.0 },
            new HitboxDefinition { Shape = "line", Length = 4.0 },
        };
        var facings = new[] { 0.0, 37.0, 217.0, -60.0 };
        var coords = new[] { -3.05, -1.85, -0.65, 0.55, 1.75, 2.95 };

        var probe = new HitboxSystem();
        var matrix = new JsonObject();
        for (var si = 0; si < shapes.Length; si++)
        {
            foreach (var facing in facings)
            {
                var live = new ActiveHitbox(shapes[si], 0.0, 0.0, facing,
                                            "probe", 1000.0, new());
                foreach (var hx in coords)
                {
                    foreach (var hy in coords)
                    {
                        var hb = probe.RegisterHurtbox("m", 0.5);
                        hb.WorldX = hx;
                        hb.WorldY = hy;
                        matrix[$"{si}|{PyStr(facing)}|{PyStr(hx)},{PyStr(hy)}"] =
                            probe.CheckCollision(live, hb);
                    }
                }
            }
        }
        AssertMatch(G.GetProperty("hitbox_matrix"), matrix, "hitbox_matrix");

        var worldPos = new JsonObject();
        var offsetDefs = new[]
        {
            new HitboxDefinition { OffsetForward = 0.8 },
            new HitboxDefinition { OffsetForward = 1.5, OffsetLateral = 0.7 },
            new HitboxDefinition { OffsetForward = 0.0, OffsetLateral = -1.2 },
        };
        foreach (var od in offsetDefs)
        {
            foreach (var facing in facings)
            {
                var (wx, wy) = od.ComputeWorldPosition(3.0, -2.0, facing);
                worldPos[$"{PyStr(od.OffsetForward)},{PyStr(od.OffsetLateral)}|{PyStr(facing)}"] =
                    new JsonArray { wx, wy };
            }
        }
        AssertMatch(G.GetProperty("hitbox_world_pos"), worldPos, "hitbox_world_pos");

        var hsys = new HitboxSystem();
        hsys.RegisterHurtbox("p1", 0.5);
        hsys.RegisterHurtbox("p2", 0.4);
        hsys.RegisterHurtbox("p3", 0.3);
        hsys.RegisterHurtbox("p2", 0.45);
        hsys.RegisterHurtbox("player", 0.5);
        hsys.UpdateHurtboxPosition("p1", 2.0, 0.0);
        hsys.UpdateHurtboxPosition("p2", 2.6, 0.9);
        hsys.UpdateHurtboxPosition("p3", -1.0, 0.0);
        hsys.UpdateHurtboxPosition("player", 0.0, 0.0);
        hsys.GetHurtbox("p3")!.Invulnerable = true;
        hsys.SpawnHitbox(new HitboxDefinition { Shape = "arc", Radius = 2.4, ArcDegrees = 100.0 },
                         (0.75, 0.27), 20.0, "player", 300.0, new());
        hsys.SpawnHitbox(new HitboxDefinition { Shape = "line", Length = 3.0, Piercing = true },
                         (0.0, 0.0), 0.0, "player", 250.0, new());
        var flow = new JsonArray();
        for (var i = 0; i < 4; i++)
        {
            var hits = hsys.Update(100.0);
            flow.Add(new JsonObject
            {
                ["hits"] = HitRows(hits),
                ["active"] = hsys.ActiveHitboxes.Count,
            });
        }
        hsys.GetHurtbox("p3")!.Invulnerable = false;
        hsys.SpawnHitbox(new HitboxDefinition { Shape = "circle", Radius = 5.0 },
                         (0.0, 0.0), 0.0, "npc", 150.0, new());
        flow.Add(new JsonObject
        {
            ["hits"] = HitRows(hsys.Update(100.0)),
            ["active"] = hsys.ActiveHitboxes.Count,
        });
        AssertMatch(G.GetProperty("hitbox_flow"), flow, "hitbox_flow");
    }

    // ── 3) Projectiles ───────────────────────────────────────────────────

    private static JsonObject ProjRow(Projectile p) => new()
    {
        ["x"] = p.X, ["y"] = p.Y, ["vx"] = p.Vx, ["vy"] = p.Vy,
        ["facing"] = p.FacingAngle, ["traveled"] = p.DistanceTraveled,
        ["alive"] = p.Alive,
    };

    private static JsonArray RunProj(ProjectileDefinition pdef,
                                     (double, double) start, double angle,
                                     (string Id, double R, double X, double Y)[] hurts,
                                     int steps,
                                     (double, double)? target = null)
    {
        var hs = new HitboxSystem();
        foreach (var (id, r, x, y) in hurts)
        {
            var hb = hs.RegisterHurtbox(id, r);
            hb.WorldX = x;
            hb.WorldY = y;
        }
        var ps = new ProjectileSystem(hs);
        var proj = ps.Spawn(pdef, start, angle, "player", new(), target);
        var rows = new JsonArray();
        for (var i = 0; i < steps; i++)
        {
            var hits = ps.Update(100.0);
            var aoeHits = hs.Update(100.0);
            rows.Add(new JsonObject
            {
                ["proj"] = ProjRow(proj),
                ["hits"] = HitRows(hits),
                ["aoe_hits"] = HitRows(aoeHits),
                ["count"] = ps.Count,
                ["active_hitboxes"] = hs.ActiveHitboxes.Count,
            });
        }
        return rows;
    }

    [Fact]
    public void Projectiles_MatchPython()
    {
        var cases = new JsonObject
        {
            ["straight"] = RunProj(
                new ProjectileDefinition { ProjectileId = "s", Speed = 10.0, MaxRange = 12.0, HitboxRadius = 0.3 },
                (0.0, 0.0), 30.0,
                new[] { ("t1", 0.5, 6.0, 3.5), ("t2", 0.5, 9.0, 5.4) }, 15),
            ["homing"] = RunProj(
                new ProjectileDefinition { ProjectileId = "h", Speed = 8.0, MaxRange = 25.0, Homing = 0.6 },
                (0.0, 0.0), 90.0,
                new[] { ("t1", 0.6, 5.0, -4.0) }, 20, (5.0, -4.0)),
            ["gravity"] = RunProj(
                new ProjectileDefinition { ProjectileId = "g", Speed = 12.0, MaxRange = 20.0, Gravity = 9.0 },
                (0.0, 0.0), -30.0,
                new[] { ("t1", 0.5, 8.0, -1.0) }, 18),
            ["piercing"] = RunProj(
                new ProjectileDefinition { ProjectileId = "p", Speed = 10.0, MaxRange = 14.0, Piercing = true },
                (0.0, 0.0), 0.0,
                new[] { ("t1", 0.5, 4.0, 0.1), ("t2", 0.5, 8.0, -0.2) }, 15),
            ["aoe"] = RunProj(
                new ProjectileDefinition
                {
                    ProjectileId = "a", Speed = 10.0, MaxRange = 14.0,
                    AoeOnHit = new Dictionary<string, object?>
                    { ["shape"] = "circle", ["radius"] = 2.0 },
                    AoeDurationMs = 250.0,
                },
                (0.0, 0.0), 0.0,
                new[] { ("t1", 0.5, 5.0, 0.0), ("t2", 0.5, 6.2, 1.1) }, 10),
        };
        AssertMatch(G.GetProperty("projectiles"), cases, "projectiles");
    }

    // ── 4) Combat data loader generation ─────────────────────────────────

    private static EnemyDatabase LoadEnemies()
    {
        var root = ContentPaths.TryGetContentRoot()!;
        var db = new EnemyDatabase();
        db.LoadFromFiles(root);
        UpdateLoader.LoadEnemyUpdates(root, db);
        return db;
    }

    [Fact]
    public void DataLoader_WeaponAttacks_MatchPython()
    {
        var rows = new JsonObject();
        var tagSets = new[]
        {
            new List<string>(),
            new List<string> { "fire", "burn" },
            new List<string> { "ice", "slow", "pierce" },
        };
        foreach (var wtype in CombatGen.WeaponProfiles.Keys.OrderBy(x => x, StringComparer.Ordinal))
        {
            foreach (var (wrange, wspeed) in new[] { (1.5, 1.0), (3.25, 1.6), (2.0, 0.25) })
            {
                for (var ti = 0; ti < tagSets.Length; ti++)
                {
                    rows[$"{wtype}|{PyStr(wrange)}|{PyStr(wspeed)}|{ti}"] =
                        AttackRow(CombatGen.GenerateWeaponAttack(
                            wtype, wrange, wspeed, tagSets[ti]));
                }
            }
        }
        AssertMatch(G.GetProperty("weapon_attacks"), rows, "weapon_attacks");
    }

    [Fact]
    public void DataLoader_EnemyAttacks_And_Select_MatchPython()
    {
        var db = LoadEnemies();

        var rng = new PythonRandom(31337);
        var rows = new JsonObject();
        foreach (var eid in db.Enemies.Keys.OrderBy(x => x, StringComparer.Ordinal))
            rows[eid] = AttackRow(CombatGen.GenerateEnemyAttack(db.Enemies[eid], 0, rng));

        var dragonStub = new EnemyDefinition
        {
            EnemyId = "synthetic_dragon", Name = "synthetic_dragon", Tier = 3,
            Category = "dragon", Behavior = "aggressive",
            Ai = new AiPattern("wander", true, true, 0.0, 0.0, false, new()),
            Tags = new List<string> { "fire" },
        };
        var unknownStub = new EnemyDefinition
        {
            EnemyId = "synthetic_unknown", Name = "synthetic_unknown", Tier = 9,
            Category = "slimeking", Behavior = "aggressive",
            Ai = new AiPattern("wander", true, true, 0.0, 0.0, false, new()),
        };
        rows["synthetic_dragon"] = AttackRow(CombatGen.GenerateEnemyAttack(dragonStub, 2, rng));
        rows["synthetic_unknown"] = AttackRow(CombatGen.GenerateEnemyAttack(unknownStub, 2, rng));
        AssertMatch(G.GetProperty("enemy_attacks_seed_31337"), rows, "enemy_attacks");

        var selRng = new PythonRandom(991);
        var selects = new JsonObject();
        foreach (var eid in db.Enemies.Keys.OrderBy(x => x, StringComparer.Ordinal).Take(4))
        {
            var loader = new CombatDataLoader();
            var picks = new JsonArray();
            foreach (var dist in new[] { 0.5, 1.4, 2.2, 5.0, 999.0 })
            {
                var sel = loader.SelectEnemyAttack(eid, dist, db.Enemies[eid], selRng);
                picks.Add(sel is null ? null : JsonValue.Create(sel.AttackId));
            }
            selects[eid] = picks;
        }
        AssertMatch(G.GetProperty("enemy_attack_select_seed_991"), selects, "enemy_attack_select");
    }

    [Fact]
    public void DataLoader_ProjectileDefs_MatchPython()
    {
        var tagSets = new[]
        {
            new List<string> { "physical" },
            new List<string> { "bow", "arrow" },
            new List<string> { "fire" },
            new List<string> { "ice", "pierce" },
            new List<string> { "lightning", "beam" },
            new List<string> { "homing", "arcane" },
            new List<string> { "seeking" },
            new List<string> { "crystal", "frost" },
        };
        var rows = new JsonObject();
        for (var ti = 0; ti < tagSets.Length; ti++)
        {
            var p = CombatGen.GenerateProjectileFromTags("bow", tagSets[ti]);
            var visual = new JsonObject
            {
                ["shape"] = (string)p.Visual["shape"]!,
                ["color"] = Ints((List<int>)p.Visual["color"]!),
                ["glow"] = (bool)p.Visual["glow"]!,
                ["glow_color"] = Ints((List<int>)p.Visual["glow_color"]!),
                ["length_px"] = (int)p.Visual["length_px"]!,
                ["width_px"] = (int)p.Visual["width_px"]!,
            };
            rows[ti.ToString()] = new JsonObject
            {
                ["projectile_id"] = p.ProjectileId,
                ["speed"] = p.Speed,
                ["max_range"] = p.MaxRange,
                ["hitbox_radius"] = p.HitboxRadius,
                ["sprite_id"] = p.SpriteId,
                ["trail_type"] = p.TrailType is null ? null : JsonValue.Create(p.TrailType),
                ["homing"] = p.Homing,
                ["gravity"] = p.Gravity,
                ["piercing"] = p.Piercing,
                ["visual"] = visual,
                ["tags"] = Strings(p.Tags),
            };
        }
        AssertMatch(G.GetProperty("projectile_defs"), rows, "projectile_defs");
    }
}
