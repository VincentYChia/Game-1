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
/// <summary>A clickable NPC: canonical (npcs-3.JSON, with speechbank +
/// quests) or a village-template flavor villager.</summary>
public sealed class LiveNpc
{
    public required Node3D Node;
    public required string Name;
    public required string Role;
    public required string VillageName;
    public required string NationName;
    /// <summary>Set for canonical NPCs only.</summary>
    public NpcDefinition? Def;
    public NpcDialogueState Dialogue { get; } = new();
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
        /// <summary>The 4 textured side-face materials (empty = untextured,
        /// tint the body box instead).</summary>
        public List<StandardMaterial3D> SideMats = new();
        public StandardMaterial3D? BodyMat;
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
    private ViewModelHands? _hands;
    private MaterialDatabase? _matDb;
    private RecipeDatabase? _recipeDb;
    private double _now;
    private readonly List<LiveNpc> _npcs = new();
    /// <summary>(type, tier, node) — the 20 starter stations (world_system
    /// .py:671-692). Native stations are indestructible fixtures.</summary>
    private readonly List<(string Type, int Tier, Node3D Node)> _stations = new();
    private Label3D? _prompt;   // single shared "what would I interact with" label
    private const double MeleeReach = 1.8;   // matches the unarmed weaponRange

    /// <summary>UI screens read the certified character (inventory/equipment).</summary>
    public PlayerCharacter? Pc => _pc;
    public MaterialDatabase? MaterialDb => _matDb;
    public CraftingSystem? Crafting => _crafting;
    public RecipeDatabase? RecipeDb => _recipeDb;
    public TitleDatabase? TitleDb { get; private set; }
    public SkillDatabase? SkillDb { get; private set; }
    public EquipmentDatabase? EquipDb { get; private set; }
    public SkillManager? SkillMgr { get; private set; }
    public NpcDatabase? NpcDb { get; private set; }
    public ClassDatabase? ClassDb { get; private set; }
    public QuestManager? QuestMgr { get; private set; }
    public IReadOnlyList<(NaturalResourceRuntime Node, Node3D Visual)> Resources
        => _resources;
    public DialogueScreen? Dialogue { get; set; }
    public IReadOnlyList<LiveNpc> Npcs => _npcs;

    public void RegisterNpc(LiveNpc npc) => _npcs.Add(npc);
    public void RegisterStation(string type, int tier, Node3D node) =>
        _stations.Add((type, tier, node));

    /// <summary>Station-click gate → CraftingScreen (the ONLY way to open
    /// crafting, character.py:1412-1419).</summary>
    public CraftingScreen? CraftingUi { get; set; }

    /// <summary>Discipline → minigame overlay ('adornments' = enchanting).</summary>
    public Dictionary<string, MinigameOverlay> Minigames { get; } = new();

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
        _hands = new ViewModelHands { Name = "Hands" };
        player.AddChild(_hands);   // world-space arms on the body

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
        var skillDb = new SkillDatabase();
        skillDb.LoadFromFiles(contentRoot);
        UpdateLoader.LoadAll(contentRoot, equipDb, skillDb,
                             matDb, recipeDb, titleDb);
        TitleDb = titleDb;
        SkillDb = skillDb;
        EquipDb = equipDb;

        // Skills runtime (skill_manager.py port): shares the orchestrator's
        // effect executor so skill combat effects use the same RNG stream.
        SkillMgr = new SkillManager(_pc, skillDb, SkillTranslation.Load(contentRoot))
        {
            Executor = _orch.Executor,
            LiveEnemies = () => _runtimes.Where(r => r.IsAlive)
                                         .Cast<ICombatEntity>().ToList(),
            OnSkillKill = t => { if (t is EnemyRuntime rt) HandleSkillKill(rt); },
        };
        // NPC/quest runtime over the certified v3 database
        var npcDb = new NpcDatabase();
        npcDb.LoadFromFiles(contentRoot);
        NpcDb = npcDb;
        var classDb = new ClassDatabase();
        classDb.LoadFromFile(System.IO.Path.Combine(
            contentRoot, "progression", "classes-1.JSON"));
        ClassDb = classDb;
        QuestMgr = new QuestManager(_pc, titleDb, SkillMgr);

        SkillMgr.InstantAoe = radius =>
        {
            if (_player is null || _orch is null) return 0;
            var psim = (X: (double)_player.Position.X, Y: (double)_player.Position.Z);
            var hits = 0;
            foreach (var e in _enemies)
            {
                if (!e.Runtime.IsAlive) continue;
                if (e.Runtime.DistanceTo(psim) > radius) continue;
                _orch.PlayerAttackEnemyWithTags(e.Runtime,
                    new List<string> { "physical" },
                    new Dictionary<string, object?> { ["baseDamage"] = 10.0 });
                e.FlashUntil = _now + 0.13;
                _fx?.PunchScale(e.Node);
                hits++;
            }
            return hits;
        };
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

        // Guaranteed starter cluster near the player spawn (8,8) so hostiles
        // are visible immediately regardless of the local danger level
        var tier1 = enemyDb.EnemiesByTier.GetValueOrDefault(1);
        if (tier1 is { Count: > 0 })
            for (var i = 0; i < 6; i++)
            {
                var def = _rng.Choice(tier1);
                var ex = 8 + _rng.RandInt(-9, 9);
                var ey = 8 + _rng.RandInt(-9, 9);
                SpawnEnemy(def, ((double)ex, (double)ey), (0, 0));
                spawned++;
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
        var tex = IconCache.Get(def.IconPath);
        var s = 1.0f * size;

        // Colored body cube — its top/bottom show (no sprite there, by
        // request) and it backs the sides when untextured.
        var bodyMat = new StandardMaterial3D { AlbedoColor = color };
        node.AddChild(new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = new Vector3(s, s, s) },
            MaterialOverride = bodyMat,
            Position = new Vector3(0, 0.5f * s, 0),
        });

        // The enemy PNG on the 4 SIDE faces only (front/back/left/right) —
        // top and bottom stay the plain colored body.
        var sideMats = new List<StandardMaterial3D>();
        if (tex is not null)
        {
            var half = s / 2f + 0.01f;
            var faces = new (Vector3 Pos, float YawDeg)[]
            {
                (new Vector3(0, 0.5f * s, half), 0f),
                (new Vector3(0, 0.5f * s, -half), 180f),
                (new Vector3(half, 0.5f * s, 0), 90f),
                (new Vector3(-half, 0.5f * s, 0), -90f),
            };
            foreach (var (fpos, yaw) in faces)
            {
                var m = new StandardMaterial3D
                {
                    AlbedoTexture = tex,
                    AlbedoColor = Colors.White,
                    TextureFilter = BaseMaterial3D.TextureFilterEnum.Linear,
                };
                node.AddChild(new MeshInstance3D
                {
                    Mesh = new QuadMesh { Size = new Vector2(s, s) },
                    MaterialOverride = m,
                    Position = fpos,
                    RotationDegrees = new Vector3(0, yaw, 0),
                });
                sideMats.Add(m);
            }
        }
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
        {
            Runtime = runtime, Node = node, EntityId = entityId, Label = label,
            SideMats = sideMats, BodyMat = bodyMat,
        };
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
        // Debug keys work anytime (before the menu guard)
        if (@event is InputEventKey { Pressed: true, Echo: false } dbg
            && dbg.PhysicalKeycode is Key.F1 or Key.F2 or Key.F3
                or Key.F4 or Key.F7)
        {
            HandleDebugKey(dbg.PhysicalKeycode);
            return;
        }

        if (UiHub.ScreenOpen) return;   // popup screens swallow world input
        if (@event is InputEventMouseButton
            { ButtonIndex: MouseButton.Left, Pressed: true } click)
            TryClickAction(click.Position);
        if (@event is InputEventKey { PhysicalKeycode: Key.E, Pressed: true, Echo: false })
            TryHarvest();
        if (@event is InputEventKey { Pressed: true, Echo: false } sk
            && sk.PhysicalKeycode is >= Key.Key1 and <= Key.Key5)
            UseSkillSlot((int)sk.PhysicalKeycode - (int)Key.Key1);
        if (@event is InputEventKey { PhysicalKeycode: Key.F, Pressed: true, Echo: false }
            && TalkToNearestNpc())
            // Consume so the SAME F doesn't reach DialogueScreen and close it
            GetViewport().SetInputAsHandled();
    }

    /// <summary>[F] talks to the nearest NPC within its interaction radius
    /// (game_engine.py:916-929; Euclidean, default 3.0). Returns true when a
    /// conversation was opened.</summary>
    private bool TalkToNearestNpc()
    {
        if (_player is null) return false;
        LiveNpc? nearest = null;
        var best = double.PositiveInfinity;
        foreach (var n in _npcs)
        {
            var d = n.Node.GlobalPosition.DistanceTo(_player.GlobalPosition);
            var radius = n.Def?.InteractionRadius ?? 3.0;
            if (d <= radius && d < best)
            {
                best = d;
                nearest = n;
            }
        }
        if (nearest is null) return false;
        Dialogue?.Open(nearest);
        return true;
    }

    /// <summary>Debug cheats (game_engine.py:1016-1229): F1 test materials,
    /// F2 learn all skills, F3 all titles, F4 max level+stats, F7 toggle
    /// infinite durability.</summary>
    private void HandleDebugKey(Key key)
    {
        if (_pc is null) return;
        switch (key)
        {
            case Key.F1:
                foreach (var id in new[]
                {
                    "oak_log", "iron_ore", "iron_ingot", "copper_ore",
                    "copper_ingot", "limestone", "granite", "pine_log",
                    "steel_ingot", "leather",
                })
                    _pc.Inventory.AddItem(id, 50);
                _lastEvent = "DEBUG: +50 of common materials";
                break;
            case Key.F2:
                if (SkillDb is not null && SkillMgr is not null)
                {
                    foreach (var id in SkillDb.Skills.Keys)
                        SkillMgr.Learn(id, skipChecks: true);
                    var eq = 0;
                    foreach (var id in SkillDb.Skills.Keys)
                    {
                        if (eq >= SkillManager.HotbarSlots) break;
                        SkillMgr.Equip(id, eq++);
                    }
                    _lastEvent = "DEBUG: learned all skills";
                }
                break;
            case Key.F3:
                if (TitleDb is not null)
                {
                    foreach (var t in TitleDb.Titles.Values)
                        if (_pc.Titles.EarnedTitles.All(e => e.TitleId != t.TitleId))
                            _pc.Titles.EarnedTitles.Add(t);
                    _lastEvent = "DEBUG: granted all titles";
                }
                break;
            case Key.F4:
                _pc.Leveling.Level = 30;
                _pc.Leveling.UnallocatedStatPoints += 30;
                _pc.Stats.Strength = _pc.Stats.Defense = _pc.Stats.Vitality =
                    _pc.Stats.Luck = _pc.Stats.Agility = _pc.Stats.Intelligence = 30;
                _pc.MaxHealthValue = 100 + 30 * 15;
                _pc.Health = _pc.MaxHealthValue;
                _pc.Mana = _pc.MaxMana;
                _lastEvent = "DEBUG: max level + stats";
                break;
            case Key.F7:
                if (_orch is not null)
                {
                    _orch.DebugInfiniteDurability = !_orch.DebugInfiniteDurability;
                    _lastEvent = $"DEBUG: infinite durability "
                                 + (_orch.DebugInfiniteDurability ? "ON" : "OFF");
                }
                break;
        }
    }

    /// <summary>Keys 1-5: activate hotbar slot, aiming at the mouse's world
    /// position (game_engine.py:974-1015).</summary>
    private void UseSkillSlot(int slot)
    {
        if (SkillMgr is null || _player is null || _pc is null) return;

        (double X, double Y)? mouseWorld = null;
        var cam = GetViewport().GetCamera3D();
        if (cam is not null)
        {
            var mp = GetViewport().GetMousePosition();
            var o = cam.ProjectRayOrigin(mp);
            var d = cam.ProjectRayNormal(mp);
            if (Math.Abs(d.Y) > 1e-4)
            {
                var t = (_player.Position.Y - o.Y) / d.Y;
                if (t is > 0 and < 120)
                {
                    var p = o + d * (float)t;
                    mouseWorld = (p.X, p.Z);
                }
            }
        }

        _pc.SetPositionXY(_player.Position.X, _player.Position.Z);
        var (ok, msg) = SkillMgr.UseSkill(slot, mouseWorld);
        _lastEvent = msg;
        _fx?.FloatText(_player.GlobalPosition, msg,
            ok ? new Color(0.6f, 1f, 0.6f) : new Color(1f, 0.6f, 0.6f), 0.8f);
    }

    /// <summary>Skill kills: EXP via the certified reward calc + loot to
    /// inventory (skill_manager.py:1023-1049).</summary>
    private void HandleSkillKill(EnemyRuntime rt)
    {
        if (_orch is null || _pc is null) return;
        var exp = _orch.CalculateExpReward(rt);
        _pc.Leveling.AddExp((int)exp);
        foreach (var (materialId, qty) in rt.GenerateLoot())
            _pc.Inventory.AddItem(materialId, (int)qty);
        _lastEvent = $"killed {rt.Definition.Name} by skill! +{exp} exp";
    }

    /// <summary>Rolled-performance fallback for disciplines with no
    /// minigame overlay registered.</summary>
    public CraftResult? CraftRecipe(Recipe recipe) =>
        CraftRecipe(recipe, 0.4 + _craftRng.NextDouble() * 0.6);

    /// <summary>Certified craft with an explicit minigame performance.</summary>
    public CraftResult? CraftRecipe(Recipe recipe, double performance)
    {
        if (_crafting is null) return null;
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
        (string Type, int Tier, Node3D Node)? hitStation = null;
        foreach (var s in _stations)
        {
            var center = s.Node.GlobalPosition + new Vector3(0, 0.7f, 0);
            if (RayHit(origin, dir, center, 1.0f) is { } t && t < bestT)
            { bestT = t; hitStation = s; hitNpc = null; hitEnemy = null; hitRes = null; }
        }

        if (hitStation is { } st)
        {
            // Out-of-range station clicks are SILENT (character.py:1412-1415)
            var d = st.Node.GlobalPosition.DistanceTo(_player.GlobalPosition);
            if (d <= _pc.InteractionRange)
            {
                CraftingUi?.OpenAtStation(st.Type, st.Tier);
                GetViewport().SetInputAsHandled();
            }
            return;
        }
        if (hitNpc is not null)
        {
            var d = hitNpc.Node.GlobalPosition.DistanceTo(_player.GlobalPosition);
            if (d <= _pc.InteractionRange + 1.0)
            {
                Dialogue?.Open(hitNpc);
                // Consume so the opening click doesn't also advance dialogue
                GetViewport().SetInputAsHandled();
            }
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
        {
            _lastEvent = "swing!";
            _hands?.PlayAttack();
        }
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

        // Fishing spots run the fishing minigame; performance >= 0.5 lands
        // the catch (then the certified harvest resolves the loot)
        if (node.ResourceType.Contains("fishing")
            && Minigames.GetValueOrDefault("fishing") is { Running: false } fishing)
        {
            fishing.Begin(2.0 + node.Tier * 2.0, $"T{node.Tier}",
                performance =>
                {
                    if (performance >= 0.5) DoHarvest(node, visual);
                    else _lastEvent = "the fish got away...";
                },
                () => _lastEvent = "stopped fishing");
            return;
        }

        DoHarvest(node, visual);
    }

    private void DoHarvest(NaturalResourceRuntime node, Node3D visual)
    {
        if (_pc is null || _gathering is null || _player is null) return;
        _hands?.PlayGather();

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

        // Skills/mana/buff ticks (character.py update loop)
        SkillMgr?.UpdateCooldowns(delta);
        _pc?.TickManaAndBuffs(delta);

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
                    // Single kill-count site for ALL kill paths (weapon,
                    // skill, AoE, DoT) — feeds combat-quest baselines
                    _pc?.Activities.RecordActivity("combat", 1);
                    e.Label.Visible = false;
                    var grey = new Color(0.3f, 0.3f, 0.3f);
                    if (e.BodyMat is not null) e.BodyMat.AlbedoColor = grey;
                    foreach (var sm in e.SideMats) sm.AlbedoColor = grey;
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

            // Telegraph: flash red during windup; hit flash overrides in white.
            // Tint the textured SIDE faces (white base) when present, else the
            // colored body box.
            Color Tint(Color baseColor) =>
                _now < e.FlashUntil ? new Color(1f, 1f, 1f)
                : rt.IsInWindup
                    ? baseColor.Lerp(new Color(1, 0.1f, 0.1f), (float)rt.WindupProgress)
                    : baseColor;
            if (e.SideMats.Count > 0)
                foreach (var sm in e.SideMats) sm.AlbedoColor = Tint(Colors.White);
            else if (e.BodyMat is not null)
                e.BodyMat.AlbedoColor = Tint(CategoryColors.GetValueOrDefault(
                    rt.Definition.Category, new Color(0.8f, 0.3f, 0.3f)));
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

            var hpFrac = (float)Math.Clamp(
                _pc.Health / Math.Max(1, _pc.MaxHealthValue), 0, 1);
            _hpFill.Size = new Vector2(BarW * hpFrac, _hpFill.Size.Y);
            _hpLabel.Text = $"HP  {(int)_pc.Health} / {(int)_pc.MaxHealthValue}";

            var mpFrac = (float)Math.Clamp(_pc.Mana / Math.Max(1, _pc.MaxMana), 0, 1);
            _mpFill.Size = new Vector2(BarW * mpFrac, _mpFill.Size.Y);
            _mpLabel.Text = $"MP  {(int)_pc.Mana} / {(int)_pc.MaxMana}";

            var need = _pc.Leveling.GetExpForNextLevel();
            var xpFrac = need > 0
                ? (float)Math.Clamp((double)_pc.Leveling.CurrentExp / need, 0, 1) : 1f;
            _xpFill.Size = new Vector2(BarW * xpFrac, _xpFill.Size.Y);

            var buffs = string.Join("  ", _pc.Buffs.ActiveBuffs.Select(
                b => $"{b.Name} {b.DurationRemaining:F0}s"));
            _infoLabel.Text = $"Lv {_pc.Leveling.Level}   ·   {_pc.Leveling.CurrentExp} xp"
                              + $"   ·   enemies {alive}/{_enemies.Count}"
                              + (buffs.Length > 0 ? $"\nbuffs: {buffs}" : "");
            _hud.Text = _lastEvent;
        }
        UpdateHotbar();
    }

    private readonly List<Label> _hotbarSlots = new();

    private void UpdateHotbar()
    {
        if (SkillMgr is null || _pc is null || _hotbarSlots.Count == 0) return;
        for (var i = 0; i < SkillManager.HotbarSlots; i++)
        {
            var label = _hotbarSlots[i];
            var icon = _hotbarIcons[i];
            var id = SkillMgr.Equipped[i];
            if (id is null || SkillDb?.Skills.GetValueOrDefault(id) is not { } def)
            {
                label.Text = $"[{i + 1}]\n—";
                label.Modulate = new Color(1, 1, 1, 0.45f);
                icon.Texture = null;
                continue;
            }
            icon.Texture = IconCache.Get(def.IconPath);
            var ps = SkillMgr.Known[id];
            if (ps.CurrentCooldown > 0)
            {
                label.Text = $"[{i + 1}]\n{ps.CurrentCooldown:F1}s";
                label.Modulate = new Color(1f, 0.45f, 0.4f);
                icon.Modulate = new Color(0.5f, 0.5f, 0.5f);   // dim on cooldown
            }
            else
            {
                var cost = SkillMgr.ManaCostOf(def);
                label.Text = $"[{i + 1}]\n{(int)cost} MP";
                label.Modulate = _pc.Mana >= cost
                    ? new Color(0.7f, 0.9f, 1f)
                    : new Color(1f, 0.5f, 0.45f);
                icon.Modulate = _pc.Mana >= cost
                    ? Colors.White : new Color(0.6f, 0.6f, 0.6f);
            }
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
        foreach (var s in _stations)
        {
            var d = s.Node.GlobalPosition.DistanceTo(pos);
            if (d < best)
            {
                best = d;
                text = $"{Prettify(s.Type)} Station (T{s.Tier})\nclick to craft";
                at = s.Node.GlobalPosition + new Vector3(0, 1.9f, 0);
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

    private ColorRect _hpFill = null!, _mpFill = null!, _xpFill = null!;
    private Label _hpLabel = null!, _mpLabel = null!, _infoLabel = null!;
    private readonly List<TextureRect> _hotbarIcons = new();
    private const float BarW = 440f;

    private void BuildHud()
    {
        var layer = new CanvasLayer();

        // -- HP / MP / XP bars, top-left (renderer.py:3173-3193) --
        _hpFill = BuildBar(layer, 16, 36, new Color(0.14f, 0.03f, 0.03f),
            new Color(0.86f, 0.22f, 0.2f), out _hpLabel, 18);
        _mpFill = BuildBar(layer, 58, 28, new Color(0.03f, 0.05f, 0.14f),
            new Color(0.3f, 0.5f, 1f), out _mpLabel, 16);
        _xpFill = BuildBar(layer, 92, 12, new Color(0.05f, 0.05f, 0.05f),
            new Color(0.95f, 0.82f, 0.3f), out var xpLbl, 10);
        xpLbl.Visible = false;

        _infoLabel = new Label { Position = new Vector2(18, 110) };
        _infoLabel.AddThemeFontSizeOverride("font_size", 18);
        _infoLabel.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
        _infoLabel.AddThemeConstantOverride("outline_size", 4);
        layer.AddChild(_infoLabel);

        // Event / buffs line (kept as text)
        _hud = new Label { Position = new Vector2(18, 142) };
        _hud.AddThemeFontSizeOverride("font_size", 16);
        _hud.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
        _hud.AddThemeConstantOverride("outline_size", 4);
        layer.AddChild(_hud);

        // -- Skill hotbar: 5 bigger icon slots bottom-center --
        var bar = new HBoxContainer();
        bar.AddThemeConstantOverride("separation", 10);
        bar.SetAnchorsPreset(Control.LayoutPreset.CenterBottom);
        bar.GrowHorizontal = Control.GrowDirection.Both;
        bar.Position = new Vector2(0, -16);
        for (var i = 0; i < SkillManager.HotbarSlots; i++)
        {
            var slot = new PanelContainer { CustomMinimumSize = new Vector2(140, 92) };
            var holder = new Control { CustomMinimumSize = new Vector2(140, 92) };
            var icon = new TextureRect
            {
                ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
                StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                MouseFilter = Control.MouseFilterEnum.Ignore,
            };
            icon.SetAnchorsPreset(Control.LayoutPreset.FullRect);
            var label = new Label
            {
                Text = $"[{i + 1}]\n—",
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Bottom,
                MouseFilter = Control.MouseFilterEnum.Ignore,
                ClipText = true,
            };
            label.SetAnchorsPreset(Control.LayoutPreset.FullRect);
            label.AddThemeFontSizeOverride("font_size", 16);
            label.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
            label.AddThemeConstantOverride("outline_size", 4);
            holder.AddChild(icon);
            holder.AddChild(label);
            slot.AddChild(holder);
            bar.AddChild(slot);
            _hotbarSlots.Add(label);
            _hotbarIcons.Add(icon);
        }
        layer.AddChild(bar);
        AddChild(layer);
    }

    /// <summary>Background + fill + centered label bar; returns the fill
    /// (whose width is set to fraction*BarW each frame).</summary>
    private static ColorRect BuildBar(CanvasLayer layer, float y, float h,
                                      Color bg, Color fg, out Label label,
                                      int fontSize)
    {
        layer.AddChild(new ColorRect
        { Position = new Vector2(16, y), Size = new Vector2(BarW, h), Color = bg });
        var fill = new ColorRect
        { Position = new Vector2(16, y), Size = new Vector2(BarW, h), Color = fg };
        layer.AddChild(fill);
        label = new Label
        {
            Position = new Vector2(16, y - 2),
            Size = new Vector2(BarW, h),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };
        label.AddThemeFontSizeOverride("font_size", fontSize);
        label.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
        label.AddThemeConstantOverride("outline_size", 4);
        layer.AddChild(label);
        return fill;
    }
}
