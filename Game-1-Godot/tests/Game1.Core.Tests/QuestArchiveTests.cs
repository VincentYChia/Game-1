using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Data;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Behavioral parity for the quest archive (sidecar-boundary substrate):
/// the fixture was produced by pushing synthetic records through the REAL
/// Python class and executing its queries. The C# port replays the same
/// records and must produce identical round-trips and query results.
/// </summary>
public class QuestArchiveTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/quest_archive_behavior.json");

    private static QuestArchiveDatabase Build(out List<ArchivedQuestRecord> records)
    {
        records = new List<ArchivedQuestRecord>();
        var db = new QuestArchiveDatabase();
        foreach (var rec in G.GetProperty("records_in").EnumerateArray())
        {
            var node = JsonNode.Parse(rec.GetRawText())!.AsObject();
            var record = ArchivedQuestRecord.FromDict(node);
            records.Add(record);
            db.Archive(record);
        }
        return db;
    }

    [Fact]
    public void RoundTrip_MatchesPython()
    {
        Build(out var records);
        var expected = G.GetProperty("roundtrip").EnumerateArray().ToList();
        Assert.Equal(expected.Count, records.Count);
        for (var i = 0; i < records.Count; i++)
        {
            var diffs = JsonTreeComparer.Diff(expected[i], records[i].ToDict());
            Assert.True(diffs.Count == 0,
                $"roundtrip[{i}]: " + string.Join("; ", diffs.Take(10)));
        }
    }

    [Fact]
    public void Queries_MatchPython()
    {
        var db = Build(out _);

        static List<string> Ids(List<ArchivedQuestRecord> rs) =>
            rs.Select(r => r.QuestId).ToList();

        static List<string> Expected(JsonElement g, string key) =>
            g.GetProperty(key).EnumerateArray().Select(e => e.GetString()!).ToList();

        Assert.Equal(Expected(G, "query_by_tags_all"),
            Ids(db.QueryByTags(new[] { "vendetta", "moors" }, matchAll: true)));
        Assert.Equal(Expected(G, "query_by_tags_any"),
            Ids(db.QueryByTags(new[] { "vendetta", "moors" }, matchAll: false)));
        Assert.Equal(Expected(G, "query_by_tags_empty"),
            Ids(db.QueryByTags(Array.Empty<string>())));
        Assert.Equal(Expected(G, "query_by_tags_limit1"),
            Ids(db.QueryByTags(new[] { "moors" }, matchAll: false, limit: 1)));
        Assert.Equal(Expected(G, "recent_archived_2"), Ids(db.RecentArchived(2)));
        Assert.Equal(Expected(G, "query_by_npc"), Ids(db.QueryByNpc("captain_vell")));
        Assert.Equal(Expected(G, "query_by_entity"), Ids(db.QueryByEntity("frost_wyrmling")));
        Assert.Equal(Expected(G, "query_by_result_succeeded"),
            Ids(db.QueryByResult("succeeded")));
        Assert.Equal(G.GetProperty("count").GetInt32(), db.Count);
    }
}
