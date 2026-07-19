using Game1.Core;
using Game1.Core.Combat;
using Game1.Core.Data;
using Game1.Core.Progression;
using Game1.Core.Tags;
using Game1.Core.World;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Playable combat slice: runs the CERTIFIED sim (EnemyRuntime AI, attack
/// state machine, hitbox system, chunk resource spawns) inside the 3D scene.
/// This node is glue only — every rule it executes is covered by the
/// conformance suite; presentation maps sim (x, y) → world (x, 0, z).
/// </summary>
public partial class CombatWorld : Node3D
{
    private sealed class LiveEnemy
    {
        public required EnemyRuntime Runtime;
        public required Node3D Node;
        public required string EntityId;
        public bool CorpseShown;
    }

    private readonly HitboxSystem _hitboxes = new();
    private readonly CombatDataLoader _combatData = new();
    private readonly List<LiveEnemy> _enemies = new();
    private readonly Dictionary<string, LiveEnemy> _byId = new();
    private PythonRandom _rng = new(0);

    private PlayerController? _player;
    private AttackStateMachine _playerAttack = new("player");
    private AttackDefinition? _unarmed;
    private double _playerFacingDeg;
    private PlayerCharacter? _pc;
    private TagAttackOrchestrator? _orch;
    private readonly List<EnemyRuntime> _runtimes = new();
    private Label? _hud;
    private string _lastEvent = "";

    private static readonly Dictionary<string, Color> CategoryColors = new()
    {
        ["beast"] = new Color(0.65f, 0.42f, 0.2f),
        ["ooze"] = new Color(0.35f, 0.8f, 0.35f),
        ["insect"] = new Color(0.55f, 0.5f, 0.25f),
        ["construct"] = new Color(0.6f, 0.6f, 0.7f),
        ["undead"] = new Color(0.75f, 0.75f, 0.65f),
        ["elemental"] = new Color(0.4f, 0.6f, 1f),
        ["aberration"] = new Color(0.7f, 0.3f, 0.8f),
        ["dragon"] = new Color(0.9f, 0.25f, 0.2f),
        ["humanoid"] = new Color(0.85f, 0.65f, 0.5f),
    };

    public void Build(string contentRoot, long worldSeed, BiomeGenerator biomes,
                      ChunkGenerator chunkGen, PlayerController player,
                      int enemyChunkRadius,
                      Game1.Core.World.Geography.WorldMap? worldMap = null)
    {
        _player = player;
        _rng = new PythonRandom(worldSeed ^ 0x5DEECE66D);

        var enemyDb = new EnemyDatabase();
        enemyDb.LoadFromFiles(contentRoot);
        UpdateLoader.LoadEnemyUpdates(contentRoot, enemyDb);

        // Certified damage pipeline: real PlayerCharacter + orchestrator
        var registry = TagRegistry.LoadFrom(contentRoot);
        var scaling = StatScalingConfig.Load(contentRoot);
        var matDb = new MaterialDatabase();
        matDb.LoadFromFiles(contentRoot);
        var equipDb = new EquipmentDatabase();
        foreach (var f in new[] { "items-tools-1.JSON", "items-smithing-2.JSON" })
        {
            var p = System.IO.Path.Combine(contentRoot, "items.JSON", f);
            if (File.Exists(p)) equipDb.LoadFromFile(p);
        }
        _pc = new PlayerCharacter(new CharacterStats(scaling),
                                  new Inventory(matDb, equipDb, 30), (8.0, 8.0))
        { Health = 100, MaxHealthValue = 100 };
        _pc.Equipment.Slots["axe"] = equipDb.CreateEquipmentFromId("copper_axe");
        _pc.Equipment.Slots["pickaxe"] = equipDb.CreateEquipmentFromId("copper_pickaxe");
        _orch = new TagAttackOrchestrator(_pc, registry,
                                          new PythonRandom(worldSeed ^ 101),
                                          new PythonRandom(worldSeed ^ 202));
        _orch.Config.LoadFromFile(System.IO.Path.Combine(
            contentRoot, "Definitions.JSON", "combat-config.JSON"));
        _orch.ActiveEnemies = _runtimes;

        _unarmed = _combatData.GetWeaponAttack("unarmed", weaponRange: 1.8);
        _hitboxes.RegisterHurtbox("player", 0.4);

        var spawned = 0;
        for (var cy = -enemyChunkRadius; cy <= enemyChunkRadius; cy++)
        {
            for (var cx = -enemyChunkRadius; cx <= enemyChunkRadius; cx++)
            {
                int tier;
                if (worldMap?.GetChunkData(cx, cy) is { } geo)
                {
                    // Geographic danger drives spawns (Tranquil/Peaceful skip)
                    var danger = (int)geo.DangerLevel;
                    if (danger <= 2) continue;
                    tier = danger <= 4 ? 1 : 2;
                }
                else
                {
                    var chunkType = biomes.GetChunkType(cx, cy);
                    if (!chunkType.Contains("dangerous") && !chunkType.Contains("rare"))
                        continue;
                    tier = chunkType.Contains("rare") ? 2 : 1;
                }
                var pool = enemyDb.EnemiesByTier.GetValueOrDefault(tier)
                           ?? enemyDb.EnemiesByTier.GetValueOrDefault(1);
                if (pool is null || pool.Count == 0) continue;

                var count = _rng.RandInt(1, 3);
                for (var i = 0; i < count && spawned < 60; i++)
                {
                    var def = _rng.Choice(pool);
                    var ex = cx * 16 + (double)_rng.RandInt(2, 13);
                    var ey = cy * 16 + (double)_rng.RandInt(2, 13);
                    SpawnEnemy(def, (ex, ey), (cx, cy));
                    spawned++;
                }
            }
        }

        BuildHud();
        GD.Print($"CombatWorld: {spawned} enemies live");
    }

    private void SpawnEnemy(EnemyDefinition def, (double X, double Y) pos,
                            (long X, long Y) chunk)
    {
        var runtime = new EnemyRuntime(def, pos, chunk, _rng);
        var entityId = $"enemy_{_enemies.Count}_{def.EnemyId}";

        var size = (float)def.VisualSize;
        var color = CategoryColors.GetValueOrDefault(def.Category,
            new Color(0.8f, 0.3f, 0.3f));
        var node = new Node3D { Name = entityId };
        node.AddChild(new MeshInstance3D
        {
            Mesh = new CapsuleMesh { Radius = 0.35f * size, Height = 1.2f * size },
            MaterialOverride = new StandardMaterial3D { AlbedoColor = color },
            Position = new Vector3(0, 0.6f * size, 0),
        });
        node.Position = new Vector3((float)pos.X, 0, (float)pos.Y);
        AddChild(node);

        _hitboxes.RegisterHurtbox(entityId, runtime.HurtboxRadius);

        var live = new LiveEnemy { Runtime = runtime, Node = node, EntityId = entityId };
        _enemies.Add(live);
        _runtimes.Add(runtime);
        _byId[entityId] = live;
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is InputEventMouseButton { ButtonIndex: MouseButton.Left, Pressed: true })
            TryPlayerAttack();
    }

    private void TryPlayerAttack()
    {
        if (_player is null || _unarmed is null) return;

        // Facing from the camera's flattened forward, mapped to sim angle
        var camera = GetViewport().GetCamera3D();
        if (camera is not null)
        {
            var fwd = -camera.GlobalTransform.Basis.Z;
            _playerFacingDeg = PyMath.Degrees(Math.Atan2(fwd.Z, fwd.X));
        }

        if (_playerAttack.StartAttack(_unarmed, new Dictionary<string, object?>()))
            _lastEvent = "swing!";
    }

    public override void _PhysicsProcess(double delta)
    {
        if (_player is null) return;
        var dtMs = delta * 1000.0;
        var playerSim = (X: (double)_player.Position.X, Y: (double)_player.Position.Z);

        _hitboxes.UpdateHurtboxPosition("player", playerSim.X, playerSim.Y);

        // Player attack phases → hitbox on active start
        foreach (var ev in _playerAttack.Update(dtMs))
        {
            if (ev.Data.TryGetValue("phase", out var ph) && ph is "active"
                && _playerAttack.CurrentAttack is { } atk)
            {
                var hbDef = CombatDataLoader.HitboxDefFromAttack(atk);
                var world = hbDef.ComputeWorldPosition(playerSim.X, playerSim.Y,
                                                       _playerFacingDeg);
                _hitboxes.SpawnHitbox(hbDef, world, _playerFacingDeg, "player",
                                      atk.ActiveMs, new Dictionary<string, object?>());
            }
        }

        // Hitbox collisions → certified enemy damage path
        foreach (var hit in _hitboxes.Update(dtMs))
        {
            if (hit.AttackerId == "player" && _byId.TryGetValue(hit.TargetId, out var target)
                && target.Runtime.IsAlive && _orch is not null)
            {
                // The CERTIFIED path: full composition + defense + loot + EXP
                var res = _orch.PlayerAttackEnemyWithTags(
                    target.Runtime, new List<string> { "physical" },
                    new Dictionary<string, object?> { ["baseDamage"] = 10.0 });
                var name = target.Runtime.Definition.Name;
                if (!target.Runtime.IsAlive)
                {
                    _lastEvent = $"killed {name}!" + (res.Loot.Count > 0
                        ? " loot: " + string.Join(", ",
                            res.Loot.Select(l => $"{l.Quantity}x {l.MaterialId}"))
                        : "");
                    _hitboxes.UnregisterHurtbox(target.EntityId);
                }
                else
                {
                    _lastEvent = $"hit {name} ({target.Runtime.CurrentHealth:F0} hp)"
                                 + (res.IsCrit ? " CRIT!" : "");
                }
            }
        }

        // Enemy AI + phased attacks (all certified EnemyRuntime logic)
        foreach (var e in _enemies)
        {
            var rt = e.Runtime;
            rt.UpdateAi(delta, playerSim);

            if (!rt.IsAlive)
            {
                if (!e.CorpseShown)
                {
                    e.CorpseShown = true;
                    if (e.Node.GetChild(0) is MeshInstance3D m)
                        m.MaterialOverride = new StandardMaterial3D
                        { AlbedoColor = new Color(0.3f, 0.3f, 0.3f) };
                    e.Node.RotateZ(Mathf.DegToRad(80));
                }
                continue;
            }

            if (rt.CanAttack() && rt.DistanceTo(playerSim) <= 1.5)
                rt.StartPhasedAttack(playerSim);

            var transition = rt.UpdateAttackPhase(dtMs);
            if (transition == "active_start" && rt.DistanceTo(playerSim) <= rt.AttackRadius + 0.6)
            {
                var dmg = rt.PerformAttack() * rt.AttackDamageMult;
                if (_pc is not null)
                    _pc.Health = Math.Max(0, _pc.Health - dmg);
                _lastEvent = $"{rt.Definition.Name} hits you for {dmg:F0}";
            }

            _hitboxes.UpdateHurtboxPosition(e.EntityId,
                rt.Position[0], rt.Position[1]);
            e.Node.Position = new Vector3(
                (float)rt.Position[0], 0, (float)rt.Position[1]);

            // Telegraph: flash red during windup
            if (e.Node.GetChild(0) is MeshInstance3D mesh
                && mesh.MaterialOverride is StandardMaterial3D mat)
            {
                var baseColor = CategoryColors.GetValueOrDefault(
                    rt.Definition.Category, new Color(0.8f, 0.3f, 0.3f));
                mat.AlbedoColor = rt.IsInWindup
                    ? baseColor.Lerp(new Color(1, 0.1f, 0.1f),
                        (float)rt.WindupProgress)
                    : baseColor;
            }
        }

        if (_hud is not null && _pc is not null)
        {
            var alive = _enemies.Count(x => x.Runtime.IsAlive);
            _hud.Text = $"HP {(int)_pc.Health}/{(int)_pc.MaxHealthValue}   " +
                        $"Lv {_pc.Leveling.Level} ({_pc.Leveling.CurrentExp} exp)   " +
                        $"enemies {alive}/{_enemies.Count}   {_lastEvent}";
        }
    }

    private void BuildHud()
    {
        var layer = new CanvasLayer();
        _hud = new Label
        {
            Position = new Vector2(16, 12),
            Text = "…",
        };
        _hud.AddThemeFontSizeOverride("font_size", 20);
        layer.AddChild(_hud);
        AddChild(layer);
    }
}
