using Game1.Core.Content;
using Game1.Core.Data;
using Game1.Core.World;
using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>
/// P3 engine entry: builds a walkable 3D world from the SAME deterministic
/// generation the conformance suite certifies. Everything is constructed in
/// code (no hand-authored scenes to drift): chunk floor tiles colored by the
/// designer's biome color table, sun, player capsule, orbit camera.
/// Simulation stays planar (ADR-6): tile (x, y) → world (x, 0, z).
/// </summary>
public partial class WorldBootstrap : Node3D
{
    [Export] public long WorldSeed { get; set; } = 12345;
    [Export] public int ChunkRadius { get; set; } = 8;
    [Export] public int ChunkSize { get; set; } = 16;

    /// <summary>Generate the full certified geographic world (nations,
    /// regions, biomes, danger, villages) and drive terrain/resources/
    /// enemies from it. Off = legacy biome-generator world.</summary>
    [Export] public bool UseGeographic { get; set; } = true;

    private WorldMap? _worldMap;
    private List<VillageRecord> _villages = new();

    // The 15 geographic chunk types → terrain colors (glue-only palette;
    // internal so MapScreen paints the world map from the same table)
    internal static readonly Dictionary<string, Color> GeoColors = new()
    {
        ["forest"] = new Color(0.24f, 0.47f, 0.24f),
        ["dense_thicket"] = new Color(0.16f, 0.35f, 0.18f),
        ["cave"] = new Color(0.41f, 0.41f, 0.43f),
        ["deep_cave"] = new Color(0.27f, 0.27f, 0.31f),
        ["quarry"] = new Color(0.59f, 0.55f, 0.49f),
        ["rocky_highlands"] = new Color(0.51f, 0.49f, 0.45f),
        ["wetland"] = new Color(0.35f, 0.51f, 0.43f),
        ["lake"] = new Color(0.27f, 0.43f, 0.71f),
        ["river"] = new Color(0.31f, 0.51f, 0.75f),
        ["flooded_cave"] = new Color(0.29f, 0.37f, 0.51f),
        ["rocky_forest"] = new Color(0.39f, 0.47f, 0.35f),
        ["crystal_cavern"] = new Color(0.55f, 0.43f, 0.71f),
        ["overgrown_ruins"] = new Color(0.47f, 0.51f, 0.39f),
        ["barren_waste"] = new Color(0.67f, 0.59f, 0.43f),
        ["cursed_marsh"] = new Color(0.39f, 0.35f, 0.47f),
    };

    public override void _Ready()
    {
        var root = ContentPaths.TryGetContentRoot();
        if (root is null)
        {
            GD.PushError("Game-1-modular content root not found — set GAME1_CONTENT_ROOT");
            return;
        }
        IconCache.Init(root);   // item/skill/etc PNG loader

        var worldGen = new WorldGenerationConfig();
        worldGen.Load(root);
        var mapConfig = new MapWaypointConfig();
        mapConfig.Load(root);
        var biomes = new BiomeGenerator(WorldSeed, worldGen);

        var resourceDb = new ResourceNodeDatabase();
        resourceDb.LoadFromFiles(root);
        var templateDb = new ChunkTemplateDatabase();
        templateDb.LoadFromFiles(root);
        var chunkGen = new ChunkGenerator(resourceDb, worldGen, templateDb);

        if (UseGeographic)
        {
            // The certified geographic pipeline — full 512x512 world in a
            // few seconds; same seed = same world as the Python game.
            var geoCfg = GeographicConfig.Load(root);
            var pipe = new WorldGeneratorPipeline(WorldSeed, geoCfg, root);
            _worldMap = pipe.Generate();
            _villages = pipe.Villages;
            GD.Print($"Geography: {_worldMap.Nations.Count} nations, " +
                     $"{_worldMap.Regions.Count} regions, {_villages.Count} villages — " +
                     string.Join(", ", _worldMap.Nations.Values.Select(n => n.Name)));
        }

        // P11 True 3D: elevation field over the certified world
        TerrainHeightField.Init(_worldMap, WorldSeed);

        BuildTerrain(biomes, mapConfig);
        BuildVillages();
        AddSun();
        var player = AddPlayer();

        var combat = new CombatWorld { Name = "CombatWorld" };
        AddChild(combat);
        combat.Build(root, WorldSeed, biomes, chunkGen, player,
                     enemyChunkRadius: 8, worldMap: _worldMap);
        BuildResources(biomes, chunkGen, resourceDb, combat);
        BuildStations(combat);
        BuildNpcs(combat);

        // The tabbed menu book (each page keeps its own keybind) + the
        // standalone popups (crafting is deliberately not a book page)
        var book = new MenuBook { Name = "MenuBook" };
        book.AddPage(new InventoryPage(combat));
        book.AddPage(new StatsPage(combat));
        book.AddPage(new SkillsPage(combat));
        book.AddPage(new QuestsPage(combat));
        book.AddPage(new EncyclopediaPage(combat));
        book.AddPage(new MapPage(_worldMap, _villages, player));
        AddChild(book);
        var crafting = new CraftingScreen(combat) { Name = "CraftingScreen" };
        AddChild(crafting);
        combat.CraftingUi = crafting;
        var dialogue = new DialogueScreen(combat) { Name = "DialogueScreen" };
        AddChild(dialogue);
        combat.Dialogue = dialogue;
        AddChild(new PauseScreen(combat, player) { Name = "PauseScreen" });

        // The six minigame overlays (ADR-7): 5 station disciplines +
        // fishing (triggered at fishing spots, not stations)
        var minigames = new (string Type, MinigameOverlay Overlay)[]
        {
            ("smithing", new SmithingMinigame()),
            ("alchemy", new AlchemyMinigame()),
            ("refining", new RefiningMinigame()),
            ("engineering", new EngineeringMinigame()),
            ("adornments", new EnchantingMinigame()),
            ("fishing", new FishingMinigame()),
        };
        foreach (var (type, overlay) in minigames)
        {
            overlay.Name = $"Minigame_{type}";
            AddChild(overlay);
            combat.Minigames[type] = overlay;
        }

        AddChild(new ClassSelectScreen(combat) { Name = "ClassSelect" });

        GD.Print($"World built: seed {WorldSeed}, {(ChunkRadius * 2 + 1) * (ChunkRadius * 2 + 1)} chunks");
    }

    /// <summary>Village walls + buildings from the certified layouts, for
    /// villages whose footprint intersects the rendered radius.</summary>
    private void BuildVillages()
    {
        if (_worldMap is null || _villages.Count == 0) return;
        var parent = new Node3D { Name = "Villages" };
        AddChild(parent);

        var wallMat = new StandardMaterial3D { AlbedoColor = new Color(0.55f, 0.53f, 0.5f) };
        var buildingMat = new StandardMaterial3D { AlbedoColor = new Color(0.45f, 0.33f, 0.24f) };
        var rendered = 0;

        foreach (var v in _villages)
        {
            var inRange = v.Chunks.Any(c =>
                Math.Abs(c.X) <= ChunkRadius && Math.Abs(c.Y) <= ChunkRadius);
            if (!inRange) continue;
            rendered++;

            foreach (var (tx, ty) in VillageGenerator.GetVillageWallTiles(v))
            {
                var h = TerrainHeightField.H(tx + 0.5, ty + 0.5);
                parent.AddChild(new MeshInstance3D
                {
                    Mesh = new BoxMesh { Size = new Vector3(1f, 1.6f, 1f) },
                    MaterialOverride = wallMat,
                    Position = new Vector3(tx + 0.5f, h + 0.8f, ty + 0.5f),
                });
            }

            foreach (var building in VillageGenerator.GetVillageBuildingTiles(v, WorldSeed))
            {
                foreach (var (tx, ty) in building)
                {
                    var h = TerrainHeightField.H(tx + 0.5, ty + 0.5);
                    parent.AddChild(new MeshInstance3D
                    {
                        Mesh = new BoxMesh { Size = new Vector3(1f, 1.2f, 1f) },
                        MaterialOverride = buildingMat,
                        Position = new Vector3(tx + 0.5f, h + 0.6f, ty + 0.5f),
                    });
                }
            }
        }
        if (rendered > 0)
            GD.Print($"Villages in view: {rendered}");
    }

    /// <summary>The 20 free starter stations near origin (world_system.py:
    /// 671-692): columns x = -8 smithing, -4 refining, 0 adornments,
    /// 4 alchemy, 8 engineering; tiers 1-4 at y = -10/-12/-14/-16.
    /// Python station colors (world.py:303-311).</summary>
    private void BuildStations(CombatWorld combat)
    {
        var parent = new Node3D { Name = "Stations" };
        AddChild(parent);
        var colors = new Dictionary<string, Color>
        {
            ["smithing"] = new(180 / 255f, 60 / 255f, 60 / 255f),
            ["alchemy"] = new(60 / 255f, 180 / 255f, 60 / 255f),
            ["refining"] = new(180 / 255f, 120 / 255f, 60 / 255f),
            ["engineering"] = new(60 / 255f, 120 / 255f, 180 / 255f),
            ["adornments"] = new(180 / 255f, 60 / 255f, 180 / 255f),
        };
        // Station discipline → item-name for the icon PNG
        var iconName = new Dictionary<string, string>
        {
            ["smithing"] = "forge", ["refining"] = "refinery",
            ["adornments"] = "enchanting_table", ["alchemy"] = "alchemy_table",
            ["engineering"] = "engineering_bench",
        };
        var columns = new (string Type, int X)[]
        {
            ("smithing", -8), ("refining", -4), ("adornments", 0),
            ("alchemy", 4), ("engineering", 8),
        };
        foreach (var (type, x) in columns)
        {
            for (var tier = 1; tier <= 4; tier++)
            {
                var y = -10 - (tier - 1) * 2;
                var h = TerrainHeightField.H(x + 0.5, y + 0.5);
                var node = new Node3D
                { Position = new Vector3(x + 0.5f, h, y + 0.5f) };
                // Cube with the station PNG on each face (else colored cube)
                var stMat = new StandardMaterial3D { AlbedoColor = colors[type] };
                if (IconCache.Get($"stations/{iconName[type]}_t{tier}.png") is { } stex)
                {
                    stMat.AlbedoTexture = stex;
                    stMat.AlbedoColor = Colors.White;
                    stMat.Transparency = BaseMaterial3D.TransparencyEnum.AlphaScissor;
                    stMat.AlphaScissorThreshold = 0.5f;
                    stMat.TextureFilter = BaseMaterial3D.TextureFilterEnum.Nearest;
                }
                node.AddChild(new MeshInstance3D
                {
                    Mesh = new BoxMesh
                    { Size = new Vector3(1.1f, 0.9f + 0.2f * tier, 1.1f) },
                    MaterialOverride = stMat,
                    Position = new Vector3(0, (0.9f + 0.2f * tier) / 2f, 0),
                });
                node.AddChild(new Label3D
                {
                    Text = $"{CombatWorld.Prettify(type)} T{tier}",
                    FontSize = 34,
                    OutlineSize = 10,
                    Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
                    Position = new Vector3(0, 1.7f + 0.2f * tier, 0),
                });
                parent.AddChild(node);
                combat.RegisterStation(type, tier, node);
            }
        }
    }

    /// <summary>Clickable villagers at the certified NPC positions of every
    /// in-range village (name labels; dialogue via CombatWorld click-pick).</summary>
    private void BuildNpcs(CombatWorld combat)
    {
        if (_villages.Count == 0) return;
        var parent = new Node3D { Name = "Npcs" };
        AddChild(parent);
        var npcMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.9f, 0.75f, 0.55f) };
        var placed = 0;

        // Canonical NPCs (npcs-3.JSON) at their JSON positions — the quest
        // givers with real speechbanks
        if (combat.NpcDb is { } npcDb)
        {
            foreach (var def in npcDb.Npcs.Values)
            {
                var (nx, ny) = ((float)def.PosX, (float)def.PosY);
                var color = new Color(0.78f, 0.59f, 1f);
                if (def.SpriteColor is System.Text.Json.Nodes.JsonArray
                    { Count: >= 3 } c)
                    color = new Color(
                        (float)(c[0]?.GetValue<double>() ?? 200) / 255f,
                        (float)(c[1]?.GetValue<double>() ?? 150) / 255f,
                        (float)(c[2]?.GetValue<double>() ?? 255) / 255f);
                var h = TerrainHeightField.H(nx + 0.5, ny + 0.5);
                var node = new Node3D
                { Position = new Vector3(nx + 0.5f, h, ny + 0.5f) };
                node.AddChild(new MeshInstance3D
                {
                    Mesh = new CapsuleMesh { Radius = 0.32f, Height = 1.7f },
                    MaterialOverride = new StandardMaterial3D { AlbedoColor = color },
                    Position = new Vector3(0, 0.85f, 0),
                });
                node.AddChild(new Label3D
                {
                    Text = def.Title.Length > 0
                        ? $"{def.Name}\n{def.Title}" : def.Name,
                    FontSize = 38,
                    OutlineSize = 10,
                    Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
                    Modulate = new Color(1f, 0.95f, 0.7f),
                    Position = new Vector3(0, 2.2f, 0),
                });
                parent.AddChild(node);
                combat.RegisterNpc(new LiveNpc
                {
                    Node = node,
                    Name = def.Name,
                    Role = def.Title,
                    VillageName = "",
                    NationName = "",
                    Def = def,
                });
                placed++;
            }
        }

        foreach (var v in _villages)
        {
            var inRange = v.Chunks.Any(c =>
                Math.Abs(c.X) <= ChunkRadius && Math.Abs(c.Y) <= ChunkRadius);
            if (!inRange) continue;

            for (var i = 0; i < v.NpcPositions.Count; i++)
            {
                var (nx, ny) = v.NpcPositions[i];
                var tmpl = i < v.NpcTemplates.Count ? v.NpcTemplates[i] : null;
                var npcName = tmpl?["name"]?.GetValue<string>() ?? "Villager";
                var h = TerrainHeightField.H(nx + 0.5, ny + 0.5);

                var node = new Node3D
                { Position = new Vector3(nx + 0.5f, h, ny + 0.5f) };
                node.AddChild(new MeshInstance3D
                {
                    Mesh = new CapsuleMesh { Radius = 0.3f, Height = 1.6f },
                    MaterialOverride = npcMat,
                    Position = new Vector3(0, 0.8f, 0),
                });
                node.AddChild(new Label3D
                {
                    Text = npcName,
                    FontSize = 36,
                    OutlineSize = 10,
                    Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
                    Position = new Vector3(0, 2.0f, 0),
                });
                parent.AddChild(node);

                combat.RegisterNpc(new LiveNpc
                {
                    Node = node,
                    Name = npcName,
                    Role = npcName,
                    VillageName = v.Name,
                    NationName = string.IsNullOrEmpty(v.Nation)
                        ? "frontier" : v.Nation,
                });
                placed++;
            }
        }
        if (placed > 0) GD.Print($"NPCs placed: {placed}");
    }

    /// <summary>Certified per-chunk resource spawns rendered as simple 3D
    /// markers: trees = green cylinders, stones/ores = gray boxes, fishing
    /// spots = blue discs. Same placements the conformance suite pins.
    /// Each spawn also gets a certified NaturalResourceRuntime registered
    /// with CombatWorld so [E] harvesting works live.</summary>
    private void BuildResources(BiomeGenerator biomes, ChunkGenerator chunkGen,
                                ResourceNodeDatabase resourceDb, CombatWorld combat)
    {
        var parent = new Node3D { Name = "Resources" };
        AddChild(parent);

        var treeMat = new StandardMaterial3D { AlbedoColor = new Color(0.15f, 0.5f, 0.15f) };
        var rockMat = new StandardMaterial3D { AlbedoColor = new Color(0.45f, 0.45f, 0.48f) };
        var fishMat = new StandardMaterial3D { AlbedoColor = new Color(0.2f, 0.5f, 0.9f) };

        var radius = Math.Min(ChunkRadius, 5);
        for (var cy = -radius; cy <= radius; cy++)
        {
            for (var cx = -radius; cx <= radius; cx++)
            {
                // Geographic mode: chunk content from the certified geo
                // dispatch (same as the Python game's live path)
                var chunk = _worldMap?.GetChunkData(cx, cy) is { } geo
                    ? chunkGen.Generate(cx, cy, seed: biomes.GetChunkSeed(cx, cy),
                                        geoChunkType: geo.ChunkType,
                                        geoDangerLevel: (int)geo.DangerLevel)
                    : chunkGen.Generate(cx, cy, biomeGenerator: biomes);
                foreach (var res in chunk.Resources)
                {
                    var isTree = res.ResourceType.Contains("tree")
                                 || res.ResourceType.Contains("sapling");
                    var isFish = res.ResourceType.Contains("fishing");
                    var scale = 0.6f + 0.25f * res.Tier;

                    var mesh = new MeshInstance3D
                    {
                        Mesh = isTree
                            ? new CylinderMesh { TopRadius = 0.12f, BottomRadius = 0.3f, Height = 2.2f * scale }
                            : isFish
                                ? new CylinderMesh { TopRadius = 0.5f, BottomRadius = 0.5f, Height = 0.08f }
                                : new BoxMesh { Size = new Vector3(0.8f * scale, 0.6f * scale, 0.8f * scale) },
                        MaterialOverride = isTree ? treeMat : isFish ? fishMat : rockMat,
                        Position = new Vector3(res.X + 0.5f,
                            TerrainHeightField.H(res.X + 0.5, res.Y + 0.5)
                            + (isTree ? 1.1f * scale : isFish ? 0.05f : 0.3f * scale),
                            res.Y + 0.5f),
                    };
                    parent.AddChild(mesh);

                    // Rotating icon above the node so it reads from a distance
                    if (IconCache.Get($"resources/{res.ResourceType}.png") is { } rtex)
                        mesh.AddChild(new SpinSprite
                        {
                            Texture = rtex,
                            PixelSize = 0.012f,
                            Position = new Vector3(0,
                                (isTree ? 1.4f : isFish ? 1.2f : 1.0f) * scale + 0.6f, 0),
                        });

                    combat.RegisterResource(new NaturalResourceRuntime(
                        new Game1.Core.World.Position(res.X + 0.5, res.Y + 0.5, 0),
                        res.ResourceType, (int)res.Tier, resourceDb), mesh);
                }
            }
        }
    }

    private void BuildTerrain(BiomeGenerator biomes, MapWaypointConfig mapConfig)
    {
        var terrain = new Node3D { Name = "Terrain" };
        AddChild(terrain);

        // One StandardMaterial3D per chunk type (shared across chunks)
        var materials = new Dictionary<string, StandardMaterial3D>();

        for (var cy = -ChunkRadius; cy <= ChunkRadius; cy++)
        {
            for (var cx = -ChunkRadius; cx <= ChunkRadius; cx++)
            {
                string chunkType;
                if (_worldMap?.GetChunkData(cx, cy) is { } geo)
                    chunkType = geo.ChunkType;   // certified geographic type
                else
                    chunkType = biomes.GetChunkType(cx, cy);

                if (!materials.TryGetValue(chunkType, out var material))
                {
                    Color color;
                    if (GeoColors.TryGetValue(chunkType, out var geoColor))
                    {
                        color = geoColor;
                    }
                    else
                    {
                        var (r, g, b) = mapConfig.GetBiomeColor(chunkType);
                        color = new Color(r / 255f, g / 255f, b / 255f);
                    }
                    material = new StandardMaterial3D { AlbedoColor = color };
                    materials[chunkType] = material;
                }

                // P11 True 3D: each chunk = 4x4 elevation quads sampled from
                // the deterministic height field; chunk-type base steps form
                // natural cliffs, jumpable ledges within chunks.
                const int quad = 4;
                for (var qy = 0; qy < ChunkSize / quad; qy++)
                {
                    for (var qx = 0; qx < ChunkSize / quad; qx++)
                    {
                        var wx = cx * ChunkSize + qx * quad + quad / 2f;
                        var wz = cy * ChunkSize + qy * quad + quad / 2f;
                        var h = TerrainHeightField.H(wx, wz);
                        var boxH = h + 3f;   // solid down to y=-3

                        var mesh = new MeshInstance3D
                        {
                            Mesh = new BoxMesh { Size = new Vector3(quad, boxH, quad) },
                            MaterialOverride = material,
                            Position = new Vector3(wx, h - boxH / 2f, wz),
                        };
                        terrain.AddChild(mesh);

                        var body = new StaticBody3D();
                        body.AddChild(new CollisionShape3D
                        {
                            Shape = new BoxShape3D { Size = new Vector3(quad, boxH, quad) },
                        });
                        mesh.AddChild(body);
                    }
                }
            }
        }
    }

    private void AddSun()
    {
        var sun = new DirectionalLight3D
        {
            Name = "Sun",
            ShadowEnabled = true,
            Rotation = new Vector3(Mathf.DegToRad(-50), Mathf.DegToRad(30), 0),
        };
        AddChild(sun);

        var env = new WorldEnvironment
        {
            Environment = new global::Godot.Environment
            {
                BackgroundMode = global::Godot.Environment.BGMode.Sky,
                Sky = new Sky { SkyMaterial = new ProceduralSkyMaterial() },
                AmbientLightSource = global::Godot.Environment.AmbientSource.Sky,
            },
        };
        AddChild(env);
    }

    private PlayerController AddPlayer()
    {
        var player = new PlayerController
        {
            Name = "Player",
            Position = new Vector3(8, TerrainHeightField.H(8, 8) + 2f, 8),
        };

        var capsule = new MeshInstance3D
        {
            Name = "Body",
            Mesh = new CapsuleMesh { Radius = 0.33f, Height = 1.7f },
            MaterialOverride = new StandardMaterial3D
            {
                // entityVisuals.playerColor — same designer data as 2D
                AlbedoColor = new Color(80 / 255f, 180 / 255f, 1f),
            },
            Position = new Vector3(0, 0.85f, 0),
        };
        player.AddChild(capsule);

        var collider = new CollisionShape3D
        {
            Shape = new CapsuleShape3D { Radius = 0.33f, Height = 1.7f },
            Position = new Vector3(0, 0.85f, 0),
        };
        player.AddChild(collider);

        var camera = new OrbitCamera { Name = "OrbitCamera" };
        player.AddChild(camera);

        AddChild(player);
        return player;
    }
}
