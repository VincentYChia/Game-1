using System.Text.Json;
using Game1.Core.World;
using Xunit;

namespace Game1.Core.Tests;

public class GeoNoiseTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/geo_noise.json");

    private static HashSet<(int, int)> Territory()
    {
        var territory = new HashSet<(int, int)>();
        for (var ty = 0; ty < 20; ty++)
            for (var tx = 0; tx < 30; tx++)
                if (!(tx is >= 12 and <= 17 && ty is >= 8 and <= 11))
                    territory.Add((tx, ty));
        return territory;
    }

    private static HashSet<(int, int)> TwoPart()
    {
        var t = Territory();
        t.Add((50, 50));
        t.Add((51, 50));
        t.Add((50, 51));
        return t;
    }

    private static List<List<List<int>>> SortedRegions(
        List<HashSet<(int X, int Y)>> regions) =>
        regions
            .Select(r => r.OrderBy(c => c.Item1).ThenBy(c => c.Item2)
                          .Select(c => new List<int> { c.Item1, c.Item2 }).ToList())
            .OrderBy(r => r.Count == 0 ? int.MinValue : r[0][0])
            .ThenBy(r => r.Count == 0 ? int.MinValue : r[0][1])
            .ToList();

    private static void AssertRegions(JsonElement expected, List<List<List<int>>> actual, string ctx)
    {
        Assert.Equal(expected.GetArrayLength(), actual.Count);
        var exp = expected.EnumerateArray()
            .Select(r => r.EnumerateArray()
                .Select(c => (c[0].GetInt32(), c[1].GetInt32())).ToList())
            .OrderBy(r => r.Count == 0 ? int.MinValue : r[0].Item1)
            .ThenBy(r => r.Count == 0 ? int.MinValue : r[0].Item2)
            .ToList();
        for (var i = 0; i < exp.Count; i++)
        {
            var act = actual[i].Select(c => (c[0], c[1])).ToList();
            Assert.True(exp[i].SequenceEqual(act),
                $"{ctx} region {i}: {exp[i].Count} vs {act.Count} chunks or ordering diff");
        }
    }

    [Fact]
    public void HashAndNoise_MatchPython()
    {
        foreach (var e in G.GetProperty("hash_2d").EnumerateObject())
        {
            var p = e.Name.Split(',').Select(long.Parse).ToArray();
            Assert.Equal(e.Value.GetDouble(),
                GeoNoise.Hash2D((int)p[0], (int)p[1], p[2]));
        }
        foreach (var e in G.GetProperty("hash_2d_int").EnumerateObject())
        {
            var p = e.Name.Split(',').Select(long.Parse).ToArray();
            Assert.Equal(e.Value.GetInt32(),
                GeoNoise.Hash2DInt((int)p[0], (int)p[1], p[2], (int)p[3]));
        }
        foreach (var e in G.GetProperty("value_noise").EnumerateObject())
        {
            var p = e.Name.Split(',');
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                GeoNoise.ValueNoise2D(double.Parse(p[0]), double.Parse(p[1]),
                    long.Parse(p[2])), $"value_noise[{e.Name}]");
        }
        foreach (var e in G.GetProperty("fractal_noise").EnumerateObject())
        {
            var p = e.Name.Split(',');
            GoldenFixture.AssertClose(e.Value.GetDouble(),
                GeoNoise.FractalNoise2D(double.Parse(p[0]), double.Parse(p[1]),
                    long.Parse(p[2])), $"fractal[{e.Name}]");
        }
    }

    [Fact]
    public void Contiguity_Components_Corridor_MatchPython()
    {
        Assert.Equal(G.GetProperty("contiguous_true").GetBoolean(),
            GeoNoise.IsContiguous(Territory()));
        Assert.Equal(G.GetProperty("contiguous_false").GetBoolean(),
            GeoNoise.IsContiguous(TwoPart()));

        var components = GeoNoise.FindComponents(TwoPart())
            .OrderByDescending(c => c.Count).ToList();
        var expected = G.GetProperty("components").EnumerateArray().ToList();
        Assert.Equal(expected.Count, components.Count);
        for (var i = 0; i < expected.Count; i++)
        {
            var exp = expected[i].EnumerateArray()
                .Select(c => (c[0].GetInt32(), c[1].GetInt32()))
                .OrderBy(c => c).ToList();
            var act = components[i].Select(c => ((int, int))c).OrderBy(c => c).ToList();
            Assert.True(exp.SequenceEqual(act), $"component {i} mismatch");
        }

        Assert.Equal(G.GetProperty("corridor_width").GetInt32(),
            GeoNoise.MeasureMinCorridorWidth(Territory()));
    }

    [Fact]
    public void VoronoiSubdivision_MatchesPython()
    {
        AssertRegions(G.GetProperty("voronoi_plain"),
            SortedRegions(GeoNoise.VoronoiSubdivide(Territory(), 5, 4242)),
            "plain");
        AssertRegions(G.GetProperty("voronoi_noisy"),
            SortedRegions(GeoNoise.VoronoiSubdivide(Territory(), 5, 4242,
                noiseAmplitude: 1.5, noiseFrequency: 0.05)),
            "noisy");
    }
}
