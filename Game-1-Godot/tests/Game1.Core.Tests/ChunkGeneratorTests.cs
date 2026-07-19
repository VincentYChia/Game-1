using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Content;
using Game1.Core.Data;
using Game1.Core.World;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Replays every chunk-generation case from chunks.json (REAL Python Chunk
/// objects: biome-generator, legacy explicit-seed, and geographic-dispatch
/// modes) through ChunkGenerator: chunk type, full 256-tile grid, and every
/// seeded resource/fishing-spot placement must be identical.
/// </summary>
public class ChunkGeneratorTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/chunks.json");

    [Fact]
    public void ChunkGeneration_AllModes_MatchPython()
    {
        var root = ContentPaths.TryGetContentRoot()!;
        var resourceDb = new ResourceNodeDatabase();
        resourceDb.LoadFromFiles(root);
        var worldConfig = new WorldGenerationConfig();
        worldConfig.Load(root);
        var templateDb = new ChunkTemplateDatabase();
        templateDb.LoadFromFiles(root);
        var gen = new ChunkGenerator(resourceDb, worldConfig, templateDb);

        var biomeGens = new Dictionary<long, BiomeGenerator>();

        foreach (var caseEl in G.GetProperty("cases").EnumerateArray())
        {
            var mode = caseEl.GetProperty("mode").GetString()!;
            var cx = caseEl.GetProperty("cx").GetInt32();
            var cy = caseEl.GetProperty("cy").GetInt32();

            GeneratedChunk chunk;
            string label;
            if (mode == "biome")
            {
                var worldSeed = caseEl.GetProperty("world_seed").GetInt64();
                if (!biomeGens.TryGetValue(worldSeed, out var bg))
                {
                    bg = new BiomeGenerator(worldSeed, worldConfig);
                    biomeGens[worldSeed] = bg;
                }
                chunk = gen.Generate(cx, cy, biomeGenerator: bg);
                label = $"biome[{worldSeed}]({cx},{cy})";
            }
            else if (mode == "legacy")
            {
                var seed = caseEl.GetProperty("seed").GetInt64();
                chunk = gen.Generate(cx, cy, seed: seed);
                label = $"legacy[{seed}]({cx},{cy})";
            }
            else
            {
                var seed = caseEl.GetProperty("seed").GetInt64();
                var geo = caseEl.GetProperty("geo_type").GetString()!;
                var danger = caseEl.GetProperty("danger").GetInt64();
                chunk = gen.Generate(cx, cy, seed: seed,
                                     geoChunkType: geo, geoDangerLevel: danger);
                label = $"geo[{geo},{danger}]({cx},{cy})";
            }

            var tiles = new JsonArray();
            foreach (var t in chunk.Tiles)
                tiles.Add(new JsonArray { t.X, t.Y, t.TileType, t.Walkable });
            var resources = new JsonArray();
            foreach (var r in chunk.Resources)
                resources.Add(new JsonArray { r.X, r.Y, r.ResourceType, r.Tier });

            var actual = new JsonObject
            {
                ["chunk_type"] = chunk.ChunkType,
                ["seed"] = chunk.Seed,
                ["tiles"] = tiles,
                ["resources"] = resources,
            };

            var diffs = JsonTreeComparer.Diff(caseEl.GetProperty("row"), actual);
            Assert.True(diffs.Count == 0,
                $"{label}: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(15)));
        }
    }
}
