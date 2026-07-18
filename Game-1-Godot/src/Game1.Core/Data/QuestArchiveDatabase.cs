using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/quest_archive_db.py — the completed-quest prose-
/// history substrate (Phase 7). This is a SIDECAR-BOUNDARY object (ADR-3):
/// the game writes on quest turn-in; the WNS/WES sidecar reads. ToDict is
/// therefore also the IPC serialization shape. In-memory canonical store,
/// matching the Python v4 posture (persistence is a future enhancement).
/// Insertion order preserved (Python dict semantics — query iteration and
/// the tag-query limit break depend on it).
/// </summary>
public sealed class ArchivedQuestRecord
{
    public required string QuestId { get; init; }
    public JsonObject OriginalQuestDefJson { get; init; } = new();
    public double TimeStarted { get; init; }
    public double TimeCompleted { get; init; }
    public double Duration { get; init; }
    public string ActualResult { get; init; } = "succeeded";
    public JsonObject ActualRewardsGranted { get; init; } = new();
    public List<string> ParticipatingNpcs { get; init; } = new();
    public List<string> ParticipatingEntities { get; init; } = new();
    public List<string> ArchivedNarrativeTags { get; init; } = new();
    public string? WnsThreadId { get; init; }
    public long ArchivedAtGameDay { get; init; }

    public JsonObject ToDict()
    {
        static JsonArray Strings(List<string> xs)
        {
            var a = new JsonArray();
            foreach (var x in xs) a.Add(x);
            return a;
        }
        return new JsonObject
        {
            ["quest_id"] = QuestId,
            ["original_quest_def_json"] = OriginalQuestDefJson.DeepClone(),
            ["time_started"] = TimeStarted,
            ["time_completed"] = TimeCompleted,
            ["duration"] = Duration,
            ["actual_result"] = ActualResult,
            ["actual_rewards_granted"] = ActualRewardsGranted.DeepClone(),
            ["participating_npcs"] = Strings(ParticipatingNpcs),
            ["participating_entities"] = Strings(ParticipatingEntities),
            ["archived_narrative_tags"] = Strings(ArchivedNarrativeTags),
            ["wns_thread_id"] = WnsThreadId is null ? null : JsonValue.Create(WnsThreadId),
            ["archived_at_game_day"] = ArchivedAtGameDay,
        };
    }

    public static ArchivedQuestRecord FromDict(JsonObject d)
    {
        static List<string> Strings(JsonObject o, string key)
        {
            var list = new List<string>();
            if (o.TryGetPropertyValue(key, out var n) && n is JsonArray a)
                foreach (var item in a)
                    if (item is JsonValue v && v.TryGetValue<string>(out var s))
                        list.Add(s);
            return list;
        }
        var wnsThread = d.TryGetPropertyValue("wns_thread_id", out var wt)
                        && wt is JsonValue wtv && wtv.TryGetValue<string>(out var wts)
            ? wts : null;
        return new ArchivedQuestRecord
        {
            QuestId = J.Str(d, "quest_id"),
            OriginalQuestDefJson = J.Obj(d, "original_quest_def_json"),
            TimeStarted = J.Num(d, "time_started", 0.0),
            TimeCompleted = J.Num(d, "time_completed", 0.0),
            Duration = J.Num(d, "duration", 0.0),
            ActualResult = J.Str(d, "actual_result", "succeeded"),
            ActualRewardsGranted = J.Obj(d, "actual_rewards_granted"),
            ParticipatingNpcs = Strings(d, "participating_npcs"),
            ParticipatingEntities = Strings(d, "participating_entities"),
            ArchivedNarrativeTags = Strings(d, "archived_narrative_tags"),
            WnsThreadId = wnsThread,
            ArchivedAtGameDay = (long)J.Num(d, "archived_at_game_day", 0),
        };
    }
}

public sealed class QuestArchiveDatabase
{
    private readonly Dictionary<string, ArchivedQuestRecord> _records = new();
    private readonly List<string> _insertionOrder = new();

    public void Archive(ArchivedQuestRecord record)
    {
        if (!_records.ContainsKey(record.QuestId))
            _insertionOrder.Add(record.QuestId);
        _records[record.QuestId] = record;
    }

    public ArchivedQuestRecord? Get(string questId) => _records.GetValueOrDefault(questId);

    public List<ArchivedQuestRecord> AllRecords() =>
        _insertionOrder.Select(id => _records[id]).ToList();

    // quest_archive_db.py:166-191 — limit break AFTER append, insertion order
    public List<ArchivedQuestRecord> QueryByTags(
        IReadOnlyList<string> tags, bool matchAll = true, int limit = 100)
    {
        if (tags.Count == 0) return new List<ArchivedQuestRecord>();
        var tagSet = new HashSet<string>(tags);
        var results = new List<ArchivedQuestRecord>();
        foreach (var record in AllRecords())
        {
            var recordTags = new HashSet<string>(record.ArchivedNarrativeTags);
            if (matchAll ? tagSet.IsSubsetOf(recordTags) : tagSet.Overlaps(recordTags))
                results.Add(record);
            if (results.Count >= limit)
                break;
        }
        return results;
    }

    // :193-201 — stable sort by time_completed desc (Python sorted is stable)
    public List<ArchivedQuestRecord> RecentArchived(int limit = 5) =>
        AllRecords().OrderByDescending(r => r.TimeCompleted).Take(limit).ToList();

    public List<ArchivedQuestRecord> QueryByNpc(string npcId) =>
        AllRecords().Where(r => r.ParticipatingNpcs.Contains(npcId)).ToList();

    public List<ArchivedQuestRecord> QueryByEntity(string entityId) =>
        AllRecords().Where(r => r.ParticipatingEntities.Contains(entityId)).ToList();

    public List<ArchivedQuestRecord> QueryByResult(string resultKind) =>
        AllRecords().Where(r => r.ActualResult == resultKind).ToList();

    public int Count => _records.Count;
}
