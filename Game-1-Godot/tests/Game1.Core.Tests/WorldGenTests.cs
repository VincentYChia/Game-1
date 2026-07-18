using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Game1.Core;
using Game1.Core.Content;
using Game1.Core.Data;
using Game1.Core.World;
using Xunit;

namespace Game1.Core.Tests;

public class PythonRandomTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/python_rng.json")
        .GetProperty("cases");

    [Fact]
    public void AllStreams_BitExact_AgainstCPython()
    {
        foreach (var seedCase in G.EnumerateObject())
        {
            var seed = System.Numerics.BigInteger.Parse(seedCase.Name);
            var v = seedCase.Value;

            var r = new PythonRandom(seed);
            foreach (var e in v.GetProperty("random").EnumerateArray())
                Assert.Equal(e.GetDouble(), r.NextDouble());

            r = new PythonRandom(seed);
            foreach (var e in v.GetProperty("getrandbits_5").EnumerateArray())
                Assert.Equal(e.GetUInt64(), r.GetRandBits(5));

            r = new PythonRandom(seed);
            foreach (var e in v.GetProperty("getrandbits_32").EnumerateArray())
                Assert.Equal(e.GetUInt64(), r.GetRandBits(32));

            r = new PythonRandom(seed);
            foreach (var e in v.GetProperty("getrandbits_64").EnumerateArray())
                Assert.Equal(ulong.Parse(e.GetString()!), r.GetRandBits(64));

            r = new PythonRandom(seed);
            foreach (var e in v.GetProperty("randint_3_17").EnumerateArray())
                Assert.Equal(e.GetInt64(), r.RandInt(3, 17));

            r = new PythonRandom(seed);
            var range7 = Enumerable.Range(0, 7).ToList();
            foreach (var e in v.GetProperty("choice_range7").EnumerateArray())
                Assert.Equal(e.GetInt32(), r.Choice(range7));

            r = new PythonRandom(seed);
            foreach (var e in v.GetProperty("uniform_m5_5").EnumerateArray())
                Assert.Equal(e.GetDouble(), r.Uniform(-5.0, 5.0));

            r = new PythonRandom(seed);
            var toShuffle = Enumerable.Range(0, 10).ToList();
            r.Shuffle(toShuffle);
            Assert.Equal(
                v.GetProperty("shuffle_10").EnumerateArray().Select(x => x.GetInt32()),
                toShuffle);
        }
    }
}

public class BiomeGeneratorTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/biome_generator.json")
        .GetProperty("cases");

    private static BiomeGenerator Make(long seed)
    {
        var cfg = new WorldGenerationConfig();
        cfg.Load(ContentPaths.TryGetContentRoot()!);
        return new BiomeGenerator(seed, cfg);
    }

    [Fact]
    public void ChunkGrid_And_Sha256_MatchPython_PerSeed()
    {
        foreach (var seedCase in G.EnumerateObject())
        {
            var gen = Make(long.Parse(seedCase.Name));
            var v = seedCase.Value;

            var grid = new SortedDictionary<string, string>(StringComparer.Ordinal);
            for (var cy = -12; cy <= 12; cy++)
                for (var cx = -12; cx <= 12; cx++)
                    grid[$"{cx},{cy}"] = gen.GetChunkType(cx, cy);

            var mismatches = new List<string>();
            foreach (var e in v.GetProperty("grid").EnumerateObject())
                if (grid[e.Name] != e.Value.GetString())
                    mismatches.Add($"{e.Name}: {e.Value.GetString()} != {grid[e.Name]}");
            Assert.True(mismatches.Count == 0,
                $"seed {seedCase.Name}: {mismatches.Count} grid mismatches: "
                + string.Join("; ", mismatches.Take(10)));

            var canon = string.Join(";", grid.Select(kv => $"{kv.Key}:{kv.Value}"));
            var sha = Convert.ToHexString(
                SHA256.HashData(Encoding.UTF8.GetBytes(canon))).ToLowerInvariant();
            Assert.Equal(v.GetProperty("grid_sha256").GetString(), sha);

            foreach (var e in v.GetProperty("water").EnumerateObject())
            {
                var parts = e.Name.Split(',');
                Assert.Equal(e.Value.GetBoolean(),
                    gen.IsWaterChunk(int.Parse(parts[0]), int.Parse(parts[1])));
            }
            foreach (var e in v.GetProperty("dungeon").EnumerateObject())
            {
                var parts = e.Name.Split(',');
                Assert.Equal(e.Value.GetBoolean(),
                    gen.ShouldSpawnDungeon(int.Parse(parts[0]), int.Parse(parts[1])));
            }
            foreach (var e in v.GetProperty("chunk_seeds").EnumerateObject())
            {
                var parts = e.Name.Split(',');
                Assert.Equal(e.Value.GetInt64(),
                    gen.GetChunkSeed(int.Parse(parts[0]), int.Parse(parts[1])));
            }
            foreach (var e in v.GetProperty("hash2d_samples").EnumerateObject())
            {
                var parts = e.Name.Split(',');
                GoldenFixture.AssertClose(e.Value.GetDouble(),
                    gen.Hash2D(int.Parse(parts[0]), int.Parse(parts[1]), int.Parse(parts[2])),
                    $"hash2d[{e.Name}]");
            }
        }
    }
}
