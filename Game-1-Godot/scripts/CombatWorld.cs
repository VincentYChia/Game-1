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
/// <summary>A clickable villager placed from the certified village layouts.</summary>
public sealed class LiveNpc
{
    public required Node3D Node;
    public required string Name;
    public required string Role;
    public required string VillageName;
    public required string NationName;
}

public partial class CombatWorld : Node3D
{
    private sealed class LiveEnemy
    {
        public required EnemyRuntime Runtime;
        public required Node3D Node;
        public required string EntityId;
        public required Label3D Label;
        public bool CorpseShown;
        public double FlashUntil;   // white hit-flash window (FxManager era)
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
    private GatheringSystem? _gathering;
    private CraftingSystem? _crafting;
    private PythonRandom _craftRng = new(0);
    private FxManager? _fx;
    private MaterialDatabase? _matDb;
    private RecipeDatabase? _recipeDb;
    private double _now;
    private readonly List<LiveNpc> _npcs = new();
    private Label3D? _prompt;   // single shared "what would I interact with" label
    private const double MeleeReach = 1.8;   // matches the unarmed weaponRange

    /// <summary>UI screens read the certified character (inventory/equipment).</summary>
    public PlayerCharacter? Pc => _pc;
    public MaterialDatabase? MaterialDb => _matDb;
    public CraftingSystem? Crafting => _crafting;
    public RecipeDatabase? RecipeDb => _recipeDb;
    public DialogueScreen? Dialogue { get; set; }

    public void RegisterNpc(LiveNpc npc) => _npcs.Add(npc);

    /// <summary>P11: combat connects only within this height difference.</summary>
    public const double CombatHeightGate = 2.0;
    private readonly List<EnemyRuntime> _runtimes = new();
    private readonly List<(NaturalResourceRuntime Node, Node3D Visual)> _resources = new();
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
        _fx = new FxManager { Name = "Fx" };
        AddChild(_fx);

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
        _matDb = matDb;
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

        // Certified gathering path (titles DB for award churn)
        var titleDb = new TitleDatabase();
        titleDb.LoadFromFiles(contentRoot);
        var recipeDb = new RecipeDatabase();
        recipeDb.LoadFromFiles(contentRoot);
        _recipeDb = recipeDb;
        UpdateLoader.LoadAll(contentRoot, equipDb, new SkillDatabase(),
                             matDb, recipeDb, titleDb);
        _gathering = new GatheringSystem(_pc, titleDb,
                                         new PythonRandom(worldSeed ^ 303));

        // P6 core craft loop ([C] key; performance roll = minigame seam)
        _crafting = new CraftingSystem(_pc, recipeDb, equipDb, _gathering);
        _craftRng = new PythonRandom(worldSeed ^ 404);

        // P11 fall damage through the real take_damage
        player.OnHardLanding = excess =>
        {
            var dmg = excess * 8.0;
            _pc.TakeDamageFull(dmg, fromAttack: false);
            _lastEvent = $"hard landing! -{dmg:F0} hp";
            _fx?.FloatText(player.GlobalPosition, $"-{dmg:F0}",
                new Color(1f, 0.25f, 0.2f));
        };

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
                for (var i = 0; i < count && spawned < 150; i++)
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

        // Name + HP readout above the head (the game's enemy nameplates)
        var label = new Label3D
        {
            Text = def.Name,
            FontSize = 40,
            OutlineSize = 12,
            Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
            NoDepthTest = true,
            Position = new Vector3(0, 1.2f * size + 0.55f, 0),
        };
        node.AddChild(label);
        AddChild(node);

        _hitboxes.RegisterHurtbox(entityId, runtime.HurtboxRadius);

        var live = new LiveEnemy
        { Runtime = runtime, Node = node, EntityId = entityId, Label = label };
        _enemies.Add(live);
        _runtimes.Add(runtime);
        _byId[entityId] = live;
    }

    /// <summary>WorldBootstrap registers each certified chunk resource with
    /// its visual so gathering can deplete/respawn it live.</summary>
    public void RegisterResource(NaturalResourceRuntime node, Node3D visual) =>
        _resources.Add((node, visual));

    public override void _UnhandledInput(InputEvent @event)
    {
        if (UiHub.ScreenOpen) return;   // popup screens swallow world input
        if (@event is InputEventMouseButton
            { ButtonIndex: MouseButton.Left, Pressed: true } click)
            TryClickAction(click.Position);
        if (@event is InputEventKey { PhysicalKeycode: Key.E, Pressed: true, Echo: false })
            TryHarvest();
    }

    /// <summary>CraftingScreen entry: certified craft with the rolled
    /// performance (minigame seam per ADR-7, until the overlays land).</summary>
    public CraftResult? CraftRecipe(Recipe recipe)
    {
        if (_crafting is null) return null;
        var performance = 0.4 + _craftRng.NextDouble() * 0.6;
        var result = _crafting.Craft(recipe, performance);
        _lastEvent = result.Success
            ? $"{result.Message} [perf {performance:F2}]"
            : result.Message;
        if (result.Success && _player is not null)
            _fx?.FloatText(_player.GlobalPosition, result.Message,
                new Color(0.5f, 1f, 0.55f), 0.8f);
        return result;
    }

    /// <summary>Unified LMB: ray-picks NPCs / resources / enemies (nearest
    /// along the ray) — talk, gather, or attack. Empty click swings at air.</summary>
    private void TryClickAction(Vector2 mousePos)
    {
        if (_player is null || _unarmed is null || _pc is null) return;
        var camera = GetViewport().GetCamera3D();
        if (camera is null) return;

        var origin = camera.ProjectRayOrigin(mousePos);
        var dir = camera.ProjectRayNormal(mousePos);

        LiveEnemy? hitEnemy = null;
        (NaturalResourceRuntime Node, Node3D Visual)? hitRes = null;
        LiveNpc? hitNpc = null;
        var bestT = 80f;

        foreach (var e in _enemies)
        {
            if (!e.Runtime.IsAlive) continue;
            var size = (float)e.Runtime.Definition.VisualSize;
            var center = e.Node.GlobalPosition + new Vector3(0, 0.6f * size, 0);
            if (RayHit(origin, dir, center, 0.45f * size + 0.35f) is { } t && t < bestT)
            { bestT = t; hitEnemy = e; hitRes = null; hitNpc = null; }
        }
        foreach (var r in _resources)
        {
            if (r.Node.Depleted) continue;
            if (RayHit(origin, dir, r.Visual.GlobalPosition, 1.0f) is { } t && t < bestT)
            { bestT = t; hitRes = r; hitEnemy = null; hitNpc = null; }
        }
        foreach (var n in _npcs)
        {
            var center = n.Node.GlobalPosition + new Vector3(0, 0.9f, 0);
            if (RayHit(origin, dir, center, 0.8f) is { } t && t < bestT)
            { bestT = t; hitNpc = n; hitEnemy = null; hitRes = null; }
        }

        if (hitNpc is not null)
        {
            var d = hitNpc.Node.GlobalPosition.DistanceTo(_player.GlobalPosition);
            if (d <= _pc.InteractionRange + 1.0) Dialogue?.Open(hitNpc);
            else _lastEvent = $"too far to talk to {hitNpc.Name}";
            return;
        }
        if (hitRes is { } res)
        {
            HarvestNode(res.Node, res.Visual);
            return;
        }

        // Enemy or air: face the click, then the certified swing/hitbox path
        var playerSim = (X: (double)_player.Position.X, Y: (double)_player.Position.Z);
        var aim = hitEnemy is not null
            ? hitEnemy.Node.GlobalPosition - _player.GlobalPosition
            : dir;
        _playerFacingDeg = PyMath.Degrees(Math.Atan2(aim.Z, aim.X));

        if (hitEnemy is not null)
        {
            var reach = MeleeReach + hitEnemy.Runtime.HurtboxRadius + 0.5;
            if (hitEnemy.Runtime.DistanceTo(playerSim) > reach)
            {
                _lastEvent = $"{hitEnemy.Runtime.Definition.Name}: out of reach";
                return;
            }
        }
        if (_playerAttack.StartAttack(_unarmed, new Dictionary<string, object?>()))
            _lastEvent = "swing!";
    }

    private static float? RayHit(Vector3 origin, Vector3 dir, Vector3 center,
                                 float radius)
    {
        var to = center - origin;
        var t = to.Dot(dir);
        if (t < 0.5f || t > 80f) return null;
        return (to - dir * t).Length() <= radius ? t : null;
    }

    private void TryHarvest()
    {
        if (_pc is null || _player is null) return;
        var playerSim = (X: (double)_player.Position.X, Y: (double)_player.Position.Z);

        NaturalResourceRuntime? nearest = null;
        Node3D? nearestVis = null;
        var nearestDist = double.PositiveInfinity;
        foreach (var (node, visual) in _resources)
        {
            if (node.Depleted) continue;
            var d = node.Position.DistanceTo(new Game1.Core.World.Position(
                playerSim.X, playerSim.Y, 0));
            if (d < nearestDist)
            {
                nearestDist = d;
                nearest = node;
                nearestVis = visual;
            }
        }
        if (nearest is null || nearestVis is null
            || nearestDist > _pc.InteractionRange)
        {
            _lastEvent = "no resource in range";
            return;
        }
        HarvestNode(nearest, nearestVis);
    }

    private void HarvestNode(NaturalResourceRuntime node, Node3D visual)
    {
        if (_pc is null || _gathering is null || _player is null) return;
        var playerSim = (X: (double)_player.Position.X, Y: (double)_player.Position.Z);
        _pc.SetPositionXY(playerSim.X, playerSim.Y);

        var dist = node.Position.DistanceTo(new Game1.Core.World.Position(
            playerSim.X, playerSim.Y, 0));
        if (dist > _pc.InteractionRange)
        {
            _lastEvent = $"{Prettify(node.ResourceType)}: too far away";
            return;
        }

        var allNodes = _resources.Select(r => r.Node).ToList();
        var result = _gathering.HarvestResource(node, allNodes);
        _fx?.PunchScale(visual, 1.12f);
        if (result is { } r)
        {
            _lastEvent = $"harvested {node.ResourceType}: " + string.Join(", ",
                r.Loot.Select(l => $"{l.Qty}x {l.ItemId}")) + (r.Crit ? " CRIT!" : "");
            _fx?.FloatText(visual.GlobalPosition,
                string.Join("\n", r.Loot.Select(l => $"+{l.Qty} {Prettify(l.ItemId)}")),
                new Color(0.5f, 1f, 0.55f), r.Crit ? FxManager.CritScale * 0.6f : 0.8f);
        }
        else
        {
            var (ok, reason) = _gathering.CanHarvestResource(node);
            _lastEvent = ok
                ? $"chopping {node.ResourceType} ({node.CurrentHp:F0}/{node.MaxHp:F0})"
                : reason;
            if (ok)
                _fx?.FloatText(visual.GlobalPosition,
                    $"{node.CurrentHp:F0}/{node.MaxHp:F0}",
                    new Color(1f, 1f, 1f, 0.85f), 0.6f);
        }
    }

    /// <summary>"iron_deposit" → "Iron Deposit" for player-facing text.</summary>
    public static string Prettify(string id) =>
        string.Join(" ", id.Split('_', StringSplitOptions.RemoveEmptyEntries)
            .Select(w => char.ToUpperInvariant(w[0]) + w[1..]));

    public override void _PhysicsProcess(double delta)
    {
        if (_player is null) return;
        _now += delta;
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
            // P11 height gate: swings can't connect across cliffs
            var heightOk = true;
            if (hit.AttackerId == "player" && _byId.TryGetValue(hit.TargetId, out var hTarget))
            {
                var enemyH = TerrainHeightField.H(hTarget.Runtime.Position[0],
                                                  hTarget.Runtime.Position[1]);
                heightOk = Math.Abs(_player.Position.Y - enemyH) <= CombatHeightGate;
                if (!heightOk) _lastEvent = "too high/low to hit!";
            }

            if (heightOk && hit.AttackerId == "player"
                && _byId.TryGetValue(hit.TargetId, out var target)
                && target.Runtime.IsAlive && _orch is not null)
            {
                // The CERTIFIED path: full composition + defense + loot + EXP
                var res = _orch.PlayerAttackEnemyWithTags(
                    target.Runtime, new List<string> { "physical" },
                    new Dictionary<string, object?> { ["baseDamage"] = 10.0 });
                var name = target.Runtime.Definition.Name;

                // Impact feedback: white flash + punch + damage number
                target.FlashUntil = _now + 0.13;
                _fx?.PunchScale(target.Node);
                _fx?.FloatText(target.Node.GlobalPosition,
                    $"{res.TotalDamage:F0}" + (res.IsCrit ? "!" : ""),
                    res.IsCrit ? new Color(1f, 0.85f, 0.2f) : new Color(1f, 1f, 1f),
                    res.IsCrit ? FxManager.CritScale : 1f);

                if (!target.Runtime.IsAlive)
                {
                    _lastEvent = $"killed {name}!" + (res.Loot.Count > 0
                        ? " loot: " + string.Join(", ",
                            res.Loot.Select(l => $"{l.Quantity}x {l.MaterialId}"))
                        : "");
                    _hitboxes.UnregisterHurtbox(target.EntityId);
                    if (res.Loot.Count > 0)
                        _fx?.FloatText(target.Node.GlobalPosition + new Vector3(0, 0.6f, 0),
                            string.Join("\n", res.Loot.Select(
                                l => $"+{l.Quantity} {l.MaterialId}")),
                            new Color(0.5f, 1f, 0.55f), 0.8f);
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
                    e.Label.Visible = false;
                    if (e.Node.GetChild(0) is MeshInstance3D m)
                        m.MaterialOverride = new StandardMaterial3D
                        { AlbedoColor = new Color(0.3f, 0.3f, 0.3f) };
                    e.Node.RotateZ(Mathf.DegToRad(80));
                }
                continue;
            }

            // Nameplate: name + HP, whitening → red as health drops
            var hpFrac = (float)Math.Clamp(rt.CurrentHealth / rt.MaxHealth, 0, 1);
            e.Label.Text = $"{rt.Definition.Name}\n{rt.CurrentHealth:F0}/{rt.MaxHealth:F0}";
            e.Label.Modulate = new Color(1f, 0.35f + 0.65f * hpFrac, 0.3f + 0.7f * hpFrac);

            if (rt.CanAttack() && rt.DistanceTo(playerSim) <= 1.5)
                rt.StartPhasedAttack(playerSim);

            var transition = rt.UpdateAttackPhase(dtMs);
            if (transition == "active_start" && rt.DistanceTo(playerSim) <= rt.AttackRadius + 0.6)
            {
                // Certified defense pipeline: DEF + armor eff + Protection +
                // shield + fortify + min-1 + Thorns. P11: height-gated.
                var enemyH = TerrainHeightField.H(rt.Position[0], rt.Position[1]);
                if (_pc is not null
                    && Math.Abs(_player.Position.Y - enemyH) <= CombatHeightGate)
                {
                    var dmg = EnemyAttackResolver.Resolve(rt, _pc);
                    _lastEvent = $"{rt.Definition.Name} hits you for {dmg:F0}";
                    _fx?.FloatText(_player.GlobalPosition, $"-{dmg:F0}",
                        new Color(1f, 0.25f, 0.2f));
                }
            }

            _hitboxes.UpdateHurtboxPosition(e.EntityId,
                rt.Position[0], rt.Position[1]);
            // P11: enemies stand on the terrain
            e.Node.Position = new Vector3(
                (float)rt.Position[0],
                TerrainHeightField.H(rt.Position[0], rt.Position[1]),
                (float)rt.Position[1]);

            // Telegraph: flash red during windup; hit flash overrides in white
            if (e.Node.GetChild(0) is MeshInstance3D mesh
                && mesh.MaterialOverride is StandardMaterial3D mat)
            {
                var baseColor = CategoryColors.GetValueOrDefault(
                    rt.Definition.Category, new Color(0.8f, 0.3f, 0.3f));
                if (_now < e.FlashUntil)
                    mat.AlbedoColor = new Color(1f, 1f, 1f);
                else
                    mat.AlbedoColor = rt.IsInWindup
                        ? baseColor.Lerp(new Color(1, 0.1f, 0.1f),
                            (float)rt.WindupProgress)
                        : baseColor;
            }
        }

        // Resource respawn ticking + depleted visuals (certified runtime)
        foreach (var (node, visual) in _resources)
        {
            var wasDepleted = node.Depleted;
            node.Update(delta);
            if (node.Depleted && visual.Visible)
                visual.Visible = false;
            else if (!node.Depleted && wasDepleted && !visual.Visible)
                visual.Visible = true;
            else if (!node.Depleted && !visual.Visible)
                visual.Visible = true;   // respawned this frame
        }

        UpdateInteractionPrompt();

        if (_hud is not null && _pc is not null)
        {
            var alive = _enemies.Count(x => x.Runtime.IsAlive);
            _hud.Text = $"HP {(int)_pc.Health}/{(int)_pc.MaxHealthValue}   " +
                        $"Lv {_pc.Leveling.Level} ({_pc.Leveling.CurrentExp} exp)   " +
                        $"enemies {alive}/{_enemies.Count}   " +
                        $"click: attack/gather/talk  [C] craft  [I] inventory  [M] map   " +
                        $"{_lastEvent}";
        }
    }

    /// <summary>One shared floating hint over whatever is in interaction
    /// range — tells the player the world is clickable.</summary>
    private void UpdateInteractionPrompt()
    {
        if (_player is null || _pc is null) return;
        _prompt ??= CreatePrompt();

        var pos = _player.GlobalPosition;
        string? text = null;
        Vector3 at = default;
        var best = _pc.InteractionRange;

        foreach (var (node, visual) in _resources)
        {
            if (node.Depleted) continue;
            var d = visual.GlobalPosition.DistanceTo(pos);
            if (d < best)
            {
                best = d;
                text = $"{Prettify(node.ResourceType)} (T{node.Tier})\nclick to gather";
                at = visual.GlobalPosition + new Vector3(0, 1.6f, 0);
            }
        }
        foreach (var n in _npcs)
        {
            var d = n.Node.GlobalPosition.DistanceTo(pos);
            if (d < best)
            {
                best = d;
                text = $"{n.Name}\nclick to talk";
                at = n.Node.GlobalPosition + new Vector3(0, 2.2f, 0);
            }
        }

        _prompt.Visible = text is not null;
        if (text is not null)
        {
            _prompt.Text = text;
            _prompt.GlobalPosition = at;
        }
    }

    private Label3D CreatePrompt()
    {
        var prompt = new Label3D
        {
            FontSize = 34,
            OutlineSize = 10,
            Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
            NoDepthTest = true,
            Modulate = new Color(1f, 1f, 0.75f),
            Visible = false,
        };
        AddChild(prompt);
        return prompt;
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
