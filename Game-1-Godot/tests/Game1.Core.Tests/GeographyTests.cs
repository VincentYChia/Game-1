using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Content;
using Game1.Core.World.Geography;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Regenerates two full 512x512 worlds through the C# geography pipeline
/// and compares against the REAL Python WorldGenerator dump (post
/// determinism patch): tier metadata + names, sha256 canons over all 262k
/// chunks / ecosystems / biomes / villages, dense windows incl. setting
/// resolution, village NPC placements, and wall/building tile layouts.
/// </summary>
public class GeographyTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/geography.json");

    private static string Sha(string canon)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(canon));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private static object[] GeoRow(WorldMap wm, int cx, int cy)
    {
        var g = wm.ChunkData[(cx, cy)];
        return new object[]
        {
            cx, cy, g.NationId, g.RegionId, g.ProvinceId, g.DistrictId,
            g.ChunkType, g.BiomeId, g.EcosystemId, (int)g.DangerLevel,
            g.LocalityId, SettingResolver.ResolveSetting(g, wm),
        };
    }

    private static JsonObject BuildWorld(long seed, string root)
    {
        var config = GeographicConfig.Load(root);
        var pipe = new WorldGeneratorPipeline(seed, config, root);
        var wm = pipe.Generate();
        var villages = pipe.Villages;

        var chunkCanon = string.Join(";",
            wm.ChunkData.Keys.OrderBy(k => k.X).ThenBy(k => k.Y)
                .Select(k => string.Join(",",
                    GeoRow(wm, k.X, k.Y).Take(11).Select(v => v!.ToString()))));

        var ecoCanon = string.Join(";",
            wm.Ecosystems.Keys.OrderBy(k => k).Select(k =>
                $"{k},{(int)wm.Ecosystems[k].DangerLevel}," +
                $"{wm.Ecosystems[k].EcoX},{wm.Ecosystems[k].EcoY}"));

        var biomeCanon = string.Join(";",
            wm.Biomes.Keys.OrderBy(k => k).Select(k =>
                $"{k},{wm.Biomes[k].DominantChunkType}," +
                $"{wm.Biomes[k].RegionIdentity},{wm.Biomes[k].ChunkCount}," +
                $"{wm.Biomes[k].Bounds.MinX},{wm.Biomes[k].Bounds.MinY}," +
                $"{wm.Biomes[k].Bounds.MaxX},{wm.Biomes[k].Bounds.MaxY}"));

        var villageCanon = string.Join(";",
            villages.Select(v =>
                $"{v.LocalityId},{v.Name},{v.CenterChunk.X},{v.CenterChunk.Y}," +
                $"{v.Size},{v.Tier},{v.Nation},{v.NpcPositions.Count}"));

        JsonArray Ints(IEnumerable<int> xs)
        {
            var a = new JsonArray();
            foreach (var x in xs) a.Add(x);
            return a;
        }

        JsonArray RowNode(object[] row)
        {
            var a = new JsonArray();
            foreach (var v in row)
                a.Add(v is string s ? JsonValue.Create(s) : JsonValue.Create((int)v));
            return a;
        }

        var windows = new JsonObject();
        foreach (var (wx, wy, halfW) in new[]
                 { (0, 0, 12), (-250, -250, 8), (100, -80, 8), (200, 200, 8) })
        {
            var rows = new JsonArray();
            for (var cy = wy - halfW; cy < wy + halfW; cy++)
                for (var cx = wx - halfW; cx < wx + halfW; cx++)
                    if (wm.ChunkData.ContainsKey((cx, cy)))
                        rows.Add(RowNode(GeoRow(wm, cx, cy)));
            windows[$"{wx},{wy}"] = rows;
        }

        var villagesHead = new JsonArray();
        foreach (var v in villages.Take(30))
        {
            villagesHead.Add(new JsonObject
            {
                ["locality_id"] = v.LocalityId,
                ["name"] = v.Name,
                ["center"] = Ints(new[] { v.CenterChunk.X, v.CenterChunk.Y }),
                ["size"] = v.Size,
                ["tier"] = v.Tier,
                ["nation"] = v.Nation,
                ["chunks"] = new JsonArray(v.Chunks
                    .Select(c => (JsonNode?)Ints(new[] { c.X, c.Y })).ToArray()),
                ["npc_positions"] = new JsonArray(v.NpcPositions
                    .Select(p => (JsonNode?)Ints(new[] { p.X, p.Y })).ToArray()),
                ["npc_prefixes"] = new JsonArray(v.NpcTemplates
                    .Select(t => (JsonNode?)JsonValue.Create(
                        t["npc_id_prefix"]?.GetValue<string>())).ToArray()),
            });
        }

        var villageTiles = new JsonArray();
        foreach (var v in villages.Take(5))
        {
            villageTiles.Add(new JsonObject
            {
                ["locality_id"] = v.LocalityId,
                ["walls"] = new JsonArray(VillageGenerator.GetVillageWallTiles(v)
                    .Select(t => (JsonNode?)Ints(new[] { t.X, t.Y })).ToArray()),
                ["buildings"] = new JsonArray(
                    VillageGenerator.GetVillageBuildingTiles(v, seed)
                        .Select(b => (JsonNode?)new JsonArray(b
                            .Select(t => (JsonNode?)Ints(new[] { t.X, t.Y }))
                            .ToArray())).ToArray()),
            });
        }

        var nations = new JsonObject();
        foreach (var k in wm.Nations.Keys.OrderBy(k => k))
        {
            var n = wm.Nations[k];
            nations[k.ToString()] = new JsonObject
            {
                ["name"] = n.Name, ["flavor"] = n.NamingFlavor,
                ["chunk_count"] = n.ChunkCount,
                ["region_ids"] = Ints(n.RegionIds),
                ["color"] = Ints(new[] { n.Color.R, n.Color.G, n.Color.B }),
            };
        }

        var regions = new JsonObject();
        foreach (var k in wm.Regions.Keys.OrderBy(k => k))
        {
            var r = wm.Regions[k];
            regions[k.ToString()] = new JsonObject
            {
                ["name"] = r.Name, ["nation"] = r.NationId,
                ["identity"] = r.Identity, ["chunk_count"] = r.ChunkCount,
                ["province_ids"] = Ints(r.ProvinceIds),
                ["bounds"] = Ints(new[]
                { r.Bounds.MinX, r.Bounds.MinY, r.Bounds.MaxX, r.Bounds.MaxY }),
            };
        }

        var provinces = new JsonObject();
        foreach (var k in wm.Provinces.Keys.OrderBy(k => k))
        {
            var p = wm.Provinces[k];
            provinces[k.ToString()] = new JsonObject
            {
                ["name"] = p.Name, ["region"] = p.RegionId,
                ["nation"] = p.NationId, ["chunk_count"] = p.ChunkCount,
                ["district_ids"] = Ints(p.DistrictIds),
                ["bounds"] = Ints(new[]
                { p.Bounds.MinX, p.Bounds.MinY, p.Bounds.MaxX, p.Bounds.MaxY }),
            };
        }

        var districts = new JsonObject();
        foreach (var k in wm.Districts.Keys.OrderBy(k => k))
        {
            var d = wm.Districts[k];
            districts[k.ToString()] = new JsonObject
            {
                ["name"] = d.Name, ["province"] = d.ProvinceId,
                ["region"] = d.RegionId, ["nation"] = d.NationId,
                ["chunk_count"] = d.ChunkCount,
                ["bounds"] = Ints(new[]
                { d.Bounds.MinX, d.Bounds.MinY, d.Bounds.MaxX, d.Bounds.MaxY }),
            };
        }

        return new JsonObject
        {
            ["seed"] = seed,
            ["world_size"] = wm.WorldSize,
            ["chunk_sha"] = Sha(chunkCanon),
            ["eco_sha"] = Sha(ecoCanon),
            ["biome_sha"] = Sha(biomeCanon),
            ["village_sha"] = Sha(villageCanon),
            ["counts"] = new JsonObject
            {
                ["chunks"] = wm.ChunkData.Count,
                ["nations"] = wm.Nations.Count,
                ["regions"] = wm.Regions.Count,
                ["provinces"] = wm.Provinces.Count,
                ["districts"] = wm.Districts.Count,
                ["biomes"] = wm.Biomes.Count,
                ["ecosystems"] = wm.Ecosystems.Count,
                ["localities"] = wm.Localities.Count,
                ["villages"] = villages.Count,
            },
            ["nations"] = nations,
            ["regions"] = regions,
            ["provinces"] = provinces,
            ["districts"] = districts,
            ["windows"] = windows,
            ["villages_head"] = villagesHead,
            ["village_tiles"] = villageTiles,
        };
    }

    [Fact]
    public void Geography_Worlds_MatchPython()
    {
        var root = ContentPaths.TryGetContentRoot()!;
        foreach (var expected in G.GetProperty("worlds").EnumerateArray())
        {
            VillageGenerator.ResetConfigCache();
            var seed = expected.GetProperty("seed").GetInt64();
            var actual = BuildWorld(seed, root);
            var diffs = JsonTreeComparer.Diff(expected, actual);
            Assert.True(diffs.Count == 0,
                $"world[{seed}]: {diffs.Count} diffs:\n  "
                + string.Join("\n  ", diffs.Take(25)));
        }
    }
}
