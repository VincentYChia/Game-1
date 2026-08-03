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

    // --- vibrancy dials (live-tunable; "punchy storybook" defaults) ---
    [Export] public float Saturation { get; set; } = 1.18f;
    [Export] public float Contrast { get; set; } = 1.06f;
    [Export] public float GlowStrength { get; set; } = 1.1f;
    [Export] public bool EnableVolumetricFog { get; set; } = true;
    [Export] public bool EnableDayNight { get; set; } = true;
    /// <summary>Heaviest GPU effect — off by default (perf toggle, not needed
    /// for correctness; SSIL already gives the color-bleed "alive" read).</summary>
    [Export] public bool EnableSdfgi { get; set; } = false;

    private WorldMap? _worldMap;
    private List<VillageRecord> _villages = new();
    // Kept for RecenterWorld (the F5/F6 landscape tour rebuilds terrain+scatter
    // around a far-away destination chunk).
    private BiomeGenerator? _biomes;
    private MapWaypointConfig? _mapConfig;

    // Atmosphere refs retained so DayNightCycle can drive them each frame.
    private DirectionalLight3D? _sun;
    private ProceduralSkyMaterial? _skyMat;
    private global::Godot.Environment? _env;
    private DayNightCycle? _dayNight;

    /// <summary>Chunk → biome type (geo chunk type, else legacy biome) — shared
    /// by scatter and AmbientLife so ambience matches the ground.</summary>
    internal string BiomeTypeAt(int cx, int cy) =>
        _worldMap?.GetChunkData(cx, cy)?.ChunkType
        ?? _biomes?.GetChunkType(cx, cy) ?? "forest";

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
        _biomes = biomes;
        _mapConfig = mapConfig;

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
        // The living layer — particles + wildlife that follow the player and
        // cross-fade by biome/time. Parented to the player: no recenter rebuild.
        player.AddChild(new AmbientLife(BiomeTypeAt, () => _dayNight?.Fraction ?? 0.5f)
        { Name = "AmbientLife" });

        var combat = new CombatWorld { Name = "CombatWorld" };
        AddChild(combat);
        combat.Build(root, WorldSeed, biomes, chunkGen, player,
                     enemyChunkRadius: 8, worldMap: _worldMap);
        combat.RecenterWorld = RecenterWorld;   // F5/F6 landscape tour
        BuildResources(biomes, chunkGen, resourceDb, combat);
        BuildScatter(biomes);
        BuildCaves();
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
        var controls = new ControlsScreen { Name = "ControlsScreen" };
        AddChild(controls);
        AddChild(new PauseScreen(combat, player)
        { Name = "PauseScreen", Controls = controls });

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

        var wallMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.58f, 0.56f, 0.52f), Roughness = 0.9f };   // stone
        var buildingMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.66f, 0.56f, 0.44f), Roughness = 0.85f };  // warm plaster/timber
        var roofMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.5f, 0.28f, 0.22f), Roughness = 0.8f };    // clay-tile roof
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
                AddSolidBox(parent, wallMat, new Vector3(1f, 2.5f, 1f),
                            new Vector3(tx + 0.5f, h + 1.25f, ty + 0.5f));
            }

            // One HOUSE per building (not per tile) — grander than a person:
            // the footprint is spread ×1.5 and raised to ~3.2 tall (player is
            // 1.7), with a pitched roof. Same building COUNT.
            foreach (var building in VillageGenerator.GetVillageBuildingTiles(v, WorldSeed))
            {
                var tiles = building.ToList();
                if (tiles.Count == 0) continue;
                var minX = tiles.Min(t => t.Item1);
                var maxX = tiles.Max(t => t.Item1);
                var minY = tiles.Min(t => t.Item2);
                var maxY = tiles.Max(t => t.Item2);
                var cxw = (minX + maxX) / 2.0 + 0.5;
                var czw = (minY + maxY) / 2.0 + 0.5;
                var sizeX = (maxX - minX + 1) * 1.5f;
                var sizeZ = (maxY - minY + 1) * 1.5f;
                const float wallH = 3.2f;
                var h = TerrainHeightField.H(cxw, czw);
                AddSolidBox(parent, buildingMat, new Vector3(sizeX, wallH, sizeZ),
                            new Vector3((float)cxw, h + wallH * 0.5f, (float)czw));
                parent.AddChild(new MeshInstance3D
                {
                    Mesh = new CylinderMesh
                    {
                        TopRadius = 0f,
                        BottomRadius = Mathf.Max(sizeX, sizeZ) * 0.72f,
                        Height = 1.5f, RadialSegments = 4,
                    },
                    MaterialOverride = roofMat,
                    Position = new Vector3((float)cxw, h + wallH + 0.75f, (float)czw),
                    RotationDegrees = new Vector3(0, 45, 0),
                });
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
                // Full station PNG on each side face (top/bottom stay colored)
                var stex = IconCache.Get($"stations/{iconName[type]}_t{tier}.png");
                BillboardCube.Build(node, 1.1f + 0.12f * tier, colors[type], stex);
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

        var treeMat = new StandardMaterial3D { AlbedoColor = new Color(0.17f, 0.44f, 0.19f), Roughness = 0.9f };
        var trunkMat = new StandardMaterial3D { AlbedoColor = new Color(0.34f, 0.24f, 0.14f), Roughness = 0.95f };
        var rockMat = new StandardMaterial3D { AlbedoColor = new Color(0.45f, 0.45f, 0.48f), Roughness = 0.85f };
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

                    var groundH = TerrainHeightField.H(res.X + 0.5, res.Y + 0.5);
                    var trunkH = 1.5f * scale;
                    // Rocks: ~2x bigger, irregular dims + a random spin so a
                    // cluster reads as a boulder field, not a grid of cubes.
                    var rtx = (int)Math.Floor((double)res.X);
                    var rty = (int)Math.Floor((double)res.Y);
                    var rockSize = new Vector3(
                        1.3f + (float)GeoNoise.Hash2D(rtx, rty, WorldSeed + 11) * 0.9f,
                        1.0f + (float)GeoNoise.Hash2D(rtx, rty, WorldSeed + 22) * 1.0f,
                        1.3f + (float)GeoNoise.Hash2D(rtx, rty, WorldSeed + 33) * 0.9f) * scale;
                    var mesh = new MeshInstance3D
                    {
                        Mesh = isTree
                            ? new CylinderMesh { TopRadius = 0.1f * scale, BottomRadius = 0.16f * scale, Height = trunkH }
                            : isFish
                                ? new CylinderMesh { TopRadius = 0.5f, BottomRadius = 0.5f, Height = 0.08f }
                                : new BoxMesh { Size = rockSize },
                        MaterialOverride = isTree ? trunkMat : isFish ? fishMat : rockMat,
                        Position = new Vector3(res.X + 0.5f,
                            groundH + (isTree ? trunkH * 0.5f : isFish ? 0.05f : rockSize.Y * 0.45f),
                            res.Y + 0.5f),
                    };
                    if (!isTree && !isFish)
                        mesh.RotationDegrees = new Vector3(0,
                            (float)GeoNoise.Hash2D(rtx, rty, WorldSeed + 44) * 360f, 0);
                    parent.AddChild(mesh);

                    // Trees: a rounded foliage crown above the trunk so a
                    // forest reads as a forest from any distance.
                    if (isTree)
                        mesh.AddChild(new MeshInstance3D
                        {
                            Mesh = new SphereMesh
                            { Radius = 0.85f * scale, Height = 1.7f * scale },
                            MaterialOverride = treeMat,
                            Position = new Vector3(0, trunkH * 0.5f + 0.55f * scale, 0),
                        });

                    // Floating icon + name so EVERY resource (all tiers) is
                    // identifiable from a distance. The icon tries a couple of
                    // filename variants; the text nameplate is the guaranteed
                    // fallback (fixes "only tier 1 had labels").
                    var labelY = (isTree ? 1.4f : isFish ? 1.2f : 1.0f) * scale + 0.8f;
                    var rtex = IconCache.Get($"resources/{res.ResourceType}.png")
                               ?? IconCache.Get($"resources/{res.ResourceType}_node.png");
                    if (rtex is not null)
                    {
                        var texH = Math.Max(1, rtex.GetHeight());
                        mesh.AddChild(new SpinSprite
                        {
                            Texture = rtex,
                            PixelSize = 1.3f / texH,
                            Position = new Vector3(0, labelY, 0),
                        });
                    }
                    else
                    {
                        // No PNG for this type → guaranteed text nameplate so it
                        // still reads (fixes "only tier 1 had labels").
                        mesh.AddChild(new Label3D
                        {
                            Text = $"{CombatWorld.Prettify(res.ResourceType)}  T{res.Tier}",
                            FontSize = 36,
                            OutlineSize = 10,
                            Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
                            Modulate = new Color(0.82f, 1f, 0.85f),
                            Position = new Vector3(0, labelY, 0),
                        });
                    }

                    combat.RegisterResource(new NaturalResourceRuntime(
                        new Game1.Core.World.Position(res.X + 0.5, res.Y + 0.5, 0),
                        res.ResourceType, (int)res.Tier, resourceDb), mesh);
                }
            }
        }
    }

    /// <summary>Rebuild the terrain + scatter window around a far destination
    /// chunk so the F5/F6 landscape tour has ground at every region. Villages/
    /// resources/enemies stay near origin — this is a look-at-the-land tour; the
    /// "Spawn — home" stop (0,0) restores the populated world.</summary>
    public void RecenterWorld(int centerCX, int centerCY)
    {
        GetNodeOrNull("Terrain")?.Free();
        GetNodeOrNull("Scatter")?.Free();
        GetNodeOrNull("Caves")?.Free();
        if (_biomes is null || _mapConfig is null) return;
        BuildTerrain(_biomes, _mapConfig, centerCX, centerCY);
        BuildScatter(_biomes, centerCX, centerCY);
        BuildCaves(centerCX, centerCY);
    }

    /// <summary>Explorable cave interiors over the carved grotto chunks in the
    /// window (roofed domes with a mouth, formations, crystals, interior glow).</summary>
    private void BuildCaves(int cCX = 0, int cCY = 0) =>
        CaveSystem.Build(this, _worldMap, WorldSeed, cCX, cCY, ChunkRadius);

    /// <summary>Decorative environment art — deterministic, per-chunk, CLUSTERED
    /// (a low-frequency clump field gates placement so props gather in patches,
    /// not a uniform sprinkle). Purely visual (no gameplay nodes/colliders).
    /// The prop MIX is chosen by biome HERE (the tuning surface); the prop ART
    /// lives in the modular EnvironmentArt library, which batches everything
    /// into a handful of MultiMeshes.</summary>
    private void BuildScatter(BiomeGenerator biomes, int cCX = 0, int cCY = 0)
    {
        var art = new EnvironmentArt();
        string TypeAt(int cx, int cy) =>
            _worldMap?.GetChunkData(cx, cy) is { } geo
                ? geo.ChunkType : biomes.GetChunkType(cx, cy);
        float HashF(int a, int b, long salt) => (float)GeoNoise.Hash2D(a, b, WorldSeed + salt);
        (double X, double Z) HashPos(int cx, int cy, int k, int salt)
        {
            var hx = GeoNoise.Hash2D(cx * 131 + k, cy * 131 + salt, WorldSeed + 71);
            var hy = GeoNoise.Hash2D(cx * 131 + k + 1, cy * 131 + salt + 3, WorldSeed + 72);
            return (cx * ChunkSize + hx * ChunkSize, cy * ChunkSize + hy * ChunkSize);
        }
        float Slope(double x, double z)
        {
            var hl = TerrainHeightField.H(x - 1, z);
            var hr = TerrainHeightField.H(x + 1, z);
            var hd = TerrainHeightField.H(x, z - 1);
            var hu = TerrainHeightField.H(x, z + 1);
            return 1f - new Vector3((float)(hl - hr), 2f, (float)(hd - hu)).Normalized().Y;
        }
        Vector3 BoulderSize(int cx, int cy, int k, float sc) => new Vector3(
            0.6f + HashF(k + 1, cx, 500) * 0.8f,
            0.5f + HashF(k + 2, cy, 501) * 0.6f,
            0.6f + HashF(k + 4, cx + cy, 502) * 0.8f) * sc;

        var radius = Math.Min(ChunkRadius, 7);
        for (var cy = cCY - radius; cy <= cCY + radius; cy++)
        {
            for (var cx = cCX - radius; cx <= cCX + radius; cx++)
            {
                var type = TypeAt(cx, cy);
                if (type.Contains("lake") || type.Contains("river") || type.Contains("flooded"))
                    continue;   // open water — no scatter
                var rocky = type.Contains("rock") || type.Contains("quarry")
                            || type.Contains("barren") || type.Contains("cave");
                var woody = type.Contains("forest") || type.Contains("thicket")
                            || type.Contains("overgrown");
                var crystal = type.Contains("crystal");
                var marsh = type.Contains("wetland") || type.Contains("marsh");

                // --- ground cover: grass tufts + occasional wildflowers (lush on
                // green land, sparse on rock/barren) — the "peaceful" read ---
                var grassN = rocky ? 5 : woody ? 20 : marsh ? 12 : 16;
                for (var k = 0; k < grassN; k++)
                {
                    var (wx, wz) = HashPos(cx, cy, k, 200);
                    if (TerrainHeightField.IsWater(wx, wz) || Slope(wx, wz) > 0.5f) continue;
                    var h = TerrainHeightField.H(wx, wz);
                    if (h > 16f) continue;   // no grass up on bare rock
                    var g = new Vector3((float)wx, h, (float)wz);
                    var yaw = HashF(k, cx + cy, 301) * Mathf.Tau;
                    var sc = 0.6f + HashF(k, cx - cy, 302) * 0.7f;
                    var pick = HashF(k, cx * 3 + cy, 303);
                    if (!rocky && pick < 0.14f)       // flower meadows
                        art.PlaceFlower(g, sc, yaw, HashF(k, cy, 304) < 0.5f);
                    else if (!rocky && pick < 0.24f)  // taller grass clumps
                        art.PlaceTallGrass(g, sc, yaw);
                    else
                        art.PlaceGrass(g, sc, yaw);
                }

                // --- clustered props: trees / boulders / bushes / crystals ---
                for (var k = 0; k < 16; k++)
                {
                    var (wx, wz) = HashPos(cx, cy, k, 400);
                    if (TerrainHeightField.IsWater(wx, wz)) continue;
                    var clump = GeoNoise.FractalNoise2D(wx * 0.09, wz * 0.09, WorldSeed + 7777, 2);
                    var thresh = rocky ? 0.0 : woody ? -0.15 : 0.35;
                    if (clump < thresh) continue;
                    var slope = Slope(wx, wz);
                    var g = new Vector3((float)wx, TerrainHeightField.H(wx, wz), (float)wz);
                    var yaw = HashF(k, cx + cy, 401) * Mathf.Tau;
                    var sc = 0.7f + HashF(k, cx - cy, 402) * 0.9f;
                    var r = HashF(k, cx * 5 + cy, 403);
                    var h = g.Y;

                    if (slope > 0.5f)   // steep faces: only boulders / scree cling
                    {
                        if (r < 0.7f) art.PlaceBoulder(g, BoulderSize(cx, cy, k, sc), yaw);
                        continue;
                    }
                    if (h > 22f)        // above the tree line: bare rock only
                    {
                        if (r < 0.55f) art.PlaceBoulder(g, BoulderSize(cx, cy, k, sc), yaw);
                        continue;
                    }
                    if (h < TerrainHeightField.WaterLevel + 1.2f && !rocky)
                    {                    // shoreline reeds / bushes at the water's edge
                        art.PlaceBush(g, 0.5f + HashF(k, cx, 404) * 0.5f, yaw);
                        continue;
                    }
                    if (crystal)
                    {
                        if (r < 0.5f) art.PlaceCrystal(g, sc, yaw);
                        else art.PlaceBoulder(g, BoulderSize(cx, cy, k, sc), yaw);
                    }
                    else if (rocky)
                    {
                        if (r < 0.7f) art.PlaceBoulder(g, BoulderSize(cx, cy, k, sc), yaw);
                        else art.PlaceBush(g, 0.5f * sc, yaw);
                    }
                    else if (woody)   // rich forest floor
                    {
                        if (r < 0.34f) art.PlacePine(g, sc, yaw);
                        else if (r < 0.56f) art.PlaceBroadleaf(g, sc, yaw);
                        else if (r < 0.68f) art.PlaceBush(g, 0.6f * sc, yaw);
                        else if (r < 0.78f) art.PlaceFern(g, sc, yaw);
                        else if (r < 0.86f) art.PlaceMushroom(g, sc, yaw);
                        else if (r < 0.92f) art.PlaceLog(g, sc, yaw);
                        else if (r < 0.97f) art.PlaceMossRock(g, BoulderSize(cx, cy, k, sc), yaw);
                        else art.PlaceTallGrass(g, sc, yaw);
                    }
                    else   // plains / meadow / marsh edge
                    {
                        if (r < 0.38f) art.PlaceBush(g, 0.6f * sc, yaw);
                        else if (r < 0.58f) art.PlaceTallGrass(g, sc, yaw);
                        else if (r < 0.73f) art.PlaceBroadleaf(g, sc * 0.85f, yaw);
                        else if (r < 0.85f) art.PlaceFlower(g, sc, yaw, HashF(k, cy, 405) < 0.5f);
                        else art.PlaceBoulder(g, BoulderSize(cx, cy, k, sc), yaw);
                    }
                }
            }
        }

        var parent = new Node3D { Name = "Scatter" };
        AddChild(parent);
        art.Commit(parent);
    }

    private void BuildTerrain(BiomeGenerator biomes, MapWaypointConfig mapConfig,
                              int cCX = 0, int cCY = 0)
    {
        var terrain = new Node3D { Name = "Terrain" };
        AddChild(terrain);

        // ONE inline SURFACE SHADER for the whole terrain: it READS the baked
        // per-vertex colour (biome/altitude/slope bands, with a cavity-AO term
        // in alpha) and enriches it with procedural fBm variation so the ground
        // stops reading as flat matte. Single draw state; two-sided.
        var terrainMat = ShaderLib.TerrainSurface();

        // Biome base color (geo palette, else the designer biome table).
        var colorCache = new Dictionary<string, Color>();
        Color BiomeColor(string type)
        {
            if (colorCache.TryGetValue(type, out var c)) return c;
            Color col;
            if (GeoColors.TryGetValue(type, out var geoColor)) col = geoColor;
            else
            {
                var (r, g, b) = mapConfig.GetBiomeColor(type);
                col = new Color(r / 255f, g / 255f, b / 255f);
            }
            colorCache[type] = col;
            return col;
        }
        string TypeAt(int cx, int cy) =>
            _worldMap?.GetChunkData(cx, cy) is { } geo
                ? geo.ChunkType : biomes.GetChunkType(cx, cy);

        // Continuous biome color — bilinearly blended across chunk centers so
        // there are NO chunk seams (the "quilt"). The color field links across
        // chunks, so the world can be sculpted freely over borders.
        Color BlendedBiomeColor(double wx, double wz)
        {
            var fx = wx / 16.0 - 0.5;
            var fy = wz / 16.0 - 0.5;
            var cx0 = (int)Math.Floor(fx);
            var cy0 = (int)Math.Floor(fy);
            var tx = (float)(fx - cx0);
            var ty = (float)(fy - cy0);
            var c00 = BiomeColor(TypeAt(cx0, cy0));
            var c10 = BiomeColor(TypeAt(cx0 + 1, cy0));
            var c01 = BiomeColor(TypeAt(cx0, cy0 + 1));
            var c11 = BiomeColor(TypeAt(cx0 + 1, cy0 + 1));
            return c00.Lerp(c10, tx).Lerp(c01.Lerp(c11, tx), ty);
        }

        var grassCol = new Color(0.30f, 0.45f, 0.22f);   // meadow green
        var forestCol = new Color(0.19f, 0.34f, 0.17f);  // deep slope forest
        var stoneCol = new Color(0.42f, 0.40f, 0.38f);   // warm grey stone
        var screeCol = new Color(0.55f, 0.53f, 0.49f);   // pale high scree
        var snowCol = new Color(0.93f, 0.95f, 0.98f);
        var sandCol = new Color(0.78f, 0.72f, 0.52f);
        var bedCol = new Color(0.24f, 0.31f, 0.27f);     // damp lakebed

        // Altitude + slope bands over the CONTINUOUS field give a cohesive read:
        // shore-sand → meadow → deep forest on mid flanks → stone on steeps &
        // altitude → pale scree → snow only on TRUE peaks (now ~40u+, not 10).
        // Biome tint is light (regional character, not per-chunk patchwork).
        Color VertexColor(double wx, double wz, float h, float slope)
        {
            var c = grassCol.Lerp(BlendedBiomeColor(wx, wz), 0.20f);
            var tex = 1f
                + (float)GeoNoise.ValueNoise2D(wx * 0.10, wz * 0.10, WorldSeed + 4242) * 0.08f
                + (float)GeoNoise.ValueNoise2D(wx * 0.45, wz * 0.45, WorldSeed + 9191) * 0.05f;
            c = new Color(c.R * tex, c.G * tex, c.B * tex);

            // deep forest green on gentle mid-elevation flanks (adds depth)
            c = c.Lerp(forestCol, Mathf.Clamp((h - 3f) / 12f, 0f, 1f) * 0.35f);
            // exposed stone on steep faces at any altitude
            var sl = Mathf.Clamp((slope - 0.28f) / 0.30f, 0f, 1f);
            c = c.Lerp(stoneCol, sl * 0.9f);
            // stone takes over with altitude, then pale scree up high
            c = c.Lerp(stoneCol, Mathf.Clamp((h - 14f) / 12f, 0f, 1f) * 0.7f);
            c = c.Lerp(screeCol, Mathf.Clamp((h - 26f) / 10f, 0f, 1f) * 0.7f);
            // snow caps only near true peaks
            c = c.Lerp(snowCol, Mathf.Clamp((h - 40f) / 8f, 0f, 1f));
            // shoreline + lakebed
            if (h >= TerrainHeightField.WaterLevel
                && h < TerrainHeightField.WaterLevel + 0.8f && slope < 0.3f)
                c = c.Lerp(sandCol, 0.5f);
            if (h < TerrainHeightField.WaterLevel)
                c = c.Lerp(bedCol, 0.55f);
            return new Color(Mathf.Clamp(c.R, 0, 1), Mathf.Clamp(c.G, 0, 1),
                             Mathf.Clamp(c.B, 0, 1));
        }

        var n = ChunkSize;
        var stride = n + 1;
        for (var cy = cCY - ChunkRadius; cy <= cCY + ChunkRadius; cy++)
        {
            for (var cx = cCX - ChunkRadius; cx <= cCX + ChunkRadius; cx++)
            {
                var surf = new SurfaceTool();
                surf.Begin(Mesh.PrimitiveType.Triangles);
                var mapData = new float[stride * stride];   // solid-collider heights

                // Sample H once over a bordered (n+3)² grid, then derive normals
                // from that grid (no extra H calls) — ~4× cheaper than sampling
                // 4 neighbours per vertex, which matters now the field is richer.
                var gstride = n + 3;
                var hgrid = new float[gstride * gstride];
                for (var gz = -1; gz <= n + 1; gz++)
                    for (var gx = -1; gx <= n + 1; gx++)
                        hgrid[(gz + 1) * gstride + (gx + 1)] =
                            TerrainHeightField.H(cx * ChunkSize + gx, cy * ChunkSize + gz);

                for (var gz = 0; gz <= n; gz++)
                {
                    for (var gx = 0; gx <= n; gx++)
                    {
                        double wx = cx * ChunkSize + gx;
                        double wz = cy * ChunkSize + gz;
                        var h = hgrid[(gz + 1) * gstride + (gx + 1)];
                        mapData[gz * stride + gx] = h;
                        // smooth up-normal from the bordered grid gradient
                        var hl = hgrid[(gz + 1) * gstride + gx];
                        var hr = hgrid[(gz + 1) * gstride + (gx + 2)];
                        var hd = hgrid[gz * gstride + (gx + 1)];
                        var hu = hgrid[(gz + 2) * gstride + (gx + 1)];
                        var normal = new Vector3(hl - hr, 2f, hd - hu).Normalized();
                        // pack a cheap cavity-AO term into vertex-colour alpha:
                        // hollows (below their neighbours) read a touch darker.
                        var avgN = (hl + hr + hd + hu) * 0.25f;
                        var ao = Mathf.Clamp(1f + (h - avgN) * 0.12f, 0.6f, 1f);
                        var vcol = VertexColor(wx, wz, h, 1f - normal.Y);
                        vcol.A = ao;
                        surf.SetColor(vcol);
                        surf.SetNormal(normal);
                        surf.SetUV(new Vector2((float)wx * 0.25f, (float)wz * 0.25f));
                        surf.AddVertex(new Vector3((float)wx, h, (float)wz));
                    }
                }
                for (var gz = 0; gz < n; gz++)
                {
                    for (var gx = 0; gx < n; gx++)
                    {
                        var i00 = gz * stride + gx;
                        var i10 = i00 + 1;
                        var i01 = i00 + stride;
                        var i11 = i01 + 1;
                        surf.AddIndex(i00); surf.AddIndex(i01); surf.AddIndex(i11);
                        surf.AddIndex(i00); surf.AddIndex(i11); surf.AddIndex(i10);
                    }
                }

                terrain.AddChild(new MeshInstance3D
                {
                    Mesh = surf.Commit(),
                    MaterialOverride = terrainMat,
                });
                // SOLID heightfield collider (not a thin trimesh): everything
                // below the surface is solid, so the player can't embed, stick,
                // or fall through — and no per-frame clamp is needed, so no
                // jitter. Grid is odd (n+1=17) → centered on the chunk.
                var body = new StaticBody3D
                {
                    Position = new Vector3(cx * ChunkSize + n * 0.5f, 0,
                                           cy * ChunkSize + n * 0.5f),
                };
                body.AddChild(new CollisionShape3D
                {
                    Shape = new HeightMapShape3D
                    {
                        MapWidth = stride,
                        MapDepth = stride,
                        MapData = mapData,
                    },
                });
                terrain.AddChild(body);
            }
        }

        AddWater(terrain, cCX, cCY);
    }

    /// <summary>A single translucent water plane at sea level, centered on the
    /// rendered window. Terrain that dips below WaterLevel reads as water.</summary>
    private void AddWater(Node3D parent, int cCX = 0, int cCY = 0)
    {
        var span = (ChunkRadius * 2 + 4) * ChunkSize;
        parent.AddChild(new MeshInstance3D
        {
            Name = "Water",
            Mesh = new PlaneMesh
            {
                Size = new Vector2(span, span),
                SubdivideWidth = 160,   // enough tessellation for the wave motion
                SubdivideDepth = 160,
            },
            Position = new Vector3(cCX * ChunkSize + ChunkSize * 0.5f,
                                   TerrainHeightField.WaterLevel,
                                   cCY * ChunkSize + ChunkSize * 0.5f),
            // living water: Gerstner waves + depth-tinted colour + shore foam
            MaterialOverride = ShaderLib.Water(),
            // waves lift verts off the flat plane; grow the cull box so the sheet
            // isn't frustum-culled when the camera skims the surface
            CustomAabb = new Aabb(new Vector3(-span * 0.5f, -2f, -span * 0.5f),
                                  new Vector3(span, 4f, span)),
        });
    }

    /// <summary>A colored box mesh with a matching solid box collider — used
    /// for village walls and buildings so the player can't walk through them.</summary>
    private static void AddSolidBox(Node3D parent, StandardMaterial3D mat,
                                    Vector3 size, Vector3 position)
    {
        var mesh = new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = size },
            MaterialOverride = mat,
            Position = position,
        };
        var body = new StaticBody3D();
        body.AddChild(new CollisionShape3D { Shape = new BoxShape3D { Size = size } });
        mesh.AddChild(body);
        parent.AddChild(mesh);
    }

    private void AddSun()
    {
        _sun = new DirectionalLight3D
        {
            Name = "Sun",
            ShadowEnabled = true,
            LightColor = new Color(1f, 0.96f, 0.87f),   // warm afternoon sun
            LightEnergy = 1.25f,
            Rotation = new Vector3(Mathf.DegToRad(-48), Mathf.DegToRad(35), 0),
            LightVolumetricFogEnergy = 1.0f,            // the sun casts god-rays
        };
        AddChild(_sun);

        _skyMat = new ProceduralSkyMaterial
        {
            SkyTopColor = new Color(0.28f, 0.48f, 0.78f),
            SkyHorizonColor = new Color(0.72f, 0.80f, 0.86f),
            GroundHorizonColor = new Color(0.68f, 0.72f, 0.74f),
            GroundBottomColor = new Color(0.30f, 0.33f, 0.35f),
            SunAngleMax = 12f,
        };

        _env = new global::Godot.Environment
        {
            BackgroundMode = global::Godot.Environment.BGMode.Sky,
            // Realtime so sky-derived AMBIENT tracks the day/night sky colours.
            Sky = new Sky { SkyMaterial = _skyMat, ProcessMode = Sky.ProcessModeEnum.Realtime },
            AmbientLightSource = global::Godot.Environment.AmbientSource.Sky,
            AmbientLightEnergy = 0.6f,
            TonemapMode = global::Godot.Environment.ToneMapper.Filmic,
            TonemapExposure = 1.0f,

            // Light aerial haze — thin so huge distant ranges stay legible.
            FogEnabled = true,
            FogLightColor = new Color(0.76f, 0.83f, 0.90f),
            FogDensity = 0.00045f,
            FogSkyAffect = 0.1f,

            // --- colour grade: re-grades the ENTIRE frame every frame ---
            AdjustmentEnabled = true,
            AdjustmentSaturation = Saturation,
            AdjustmentContrast = Contrast,
            AdjustmentBrightness = 1.0f,

            // --- bloom on bright highlights (crystals, water glints, snow) ---
            GlowEnabled = true,
            GlowIntensity = 0.9f,
            GlowStrength = GlowStrength,
            GlowBloom = 0.15f,
            GlowBlendMode = global::Godot.Environment.GlowBlendModeEnum.Softlight,
            GlowHdrThreshold = 1.0f,

            // --- grounding contact shadows + colour bleed (the cheap "alive") ---
            SsaoEnabled = true,
            SsaoRadius = 1.4f,
            SsaoIntensity = 2.0f,
            SsaoPower = 1.5f,
            SsilEnabled = true,
            SsilRadius = 3.0f,
            SsilIntensity = 1.0f,
        };
        // Glow contribution per blur level (indexed setter — there are no
        // GlowLevel1..7 properties on Environment).
        _env.SetGlowLevel(0, 1.0f);
        _env.SetGlowLevel(1, 1.0f);
        _env.SetGlowLevel(2, 0.6f);

        if (EnableVolumetricFog)
        {
            _env.VolumetricFogEnabled = true;
            _env.VolumetricFogDensity = 0.015f;
            _env.VolumetricFogAlbedo = new Color(0.90f, 0.93f, 1f);
            _env.VolumetricFogLength = 120f;
            _env.VolumetricFogAnisotropy = 0.3f;
        }
        if (EnableSdfgi)
        {
            _env.SdfgiEnabled = true;
            _env.SdfgiUseOcclusion = true;
        }

        AddChild(new WorldEnvironment { Environment = _env });

        if (EnableDayNight)
        {
            _dayNight = new DayNightCycle(_sun, _skyMat, _env) { Name = "DayNightCycle" };
            AddChild(_dayNight);
        }
    }

    private PlayerController AddPlayer()
    {
        var player = new PlayerController
        {
            Name = "Player",
            Position = new Vector3(8, TerrainHeightField.H(8, 8) + 3f, 8),
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
