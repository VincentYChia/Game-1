using Game1.Core.Content;
using Game1.Core.Data;
using Game1.Core.World;
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

    public override void _Ready()
    {
        var root = ContentPaths.TryGetContentRoot();
        if (root is null)
        {
            GD.PushError("Game-1-modular content root not found — set GAME1_CONTENT_ROOT");
            return;
        }

        var worldGen = new WorldGenerationConfig();
        worldGen.Load(root);
        var mapConfig = new MapWaypointConfig();
        mapConfig.Load(root);
        var biomes = new BiomeGenerator(WorldSeed, worldGen);

        BuildTerrain(biomes, mapConfig);
        AddSun();
        AddPlayer();
        GD.Print($"World built: seed {WorldSeed}, {(ChunkRadius * 2 + 1) * (ChunkRadius * 2 + 1)} chunks");
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
                var chunkType = biomes.GetChunkType(cx, cy);
                if (!materials.TryGetValue(chunkType, out var material))
                {
                    var (r, g, b) = mapConfig.GetBiomeColor(chunkType);
                    material = new StandardMaterial3D
                    {
                        AlbedoColor = new Color(r / 255f, g / 255f, b / 255f),
                    };
                    materials[chunkType] = material;
                }

                var mesh = new MeshInstance3D
                {
                    Name = $"Chunk_{cx}_{cy}",
                    Mesh = new BoxMesh { Size = new Vector3(ChunkSize, 1f, ChunkSize) },
                    MaterialOverride = material,
                    Position = new Vector3(
                        cx * ChunkSize + ChunkSize / 2f, -0.5f,
                        cy * ChunkSize + ChunkSize / 2f),
                };
                terrain.AddChild(mesh);

                var body = new StaticBody3D();
                var shape = new CollisionShape3D
                {
                    Shape = new BoxShape3D { Size = new Vector3(ChunkSize, 1f, ChunkSize) },
                };
                body.AddChild(shape);
                mesh.AddChild(body);
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

    private void AddPlayer()
    {
        var player = new PlayerController { Name = "Player", Position = new Vector3(8, 2, 8) };

        var capsule = new MeshInstance3D
        {
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
    }
}
