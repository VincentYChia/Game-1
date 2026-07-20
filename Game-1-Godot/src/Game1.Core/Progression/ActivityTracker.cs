namespace Game1.Core.Progression;

/// <summary>
/// Port of entities/components/activity_tracker.py — fixed-key counters.
/// BUG-COMPATIBLE: record_activity only increments KNOWN keys, so
/// 'fishing' (absent from the dict) is silently dropped, exactly like
/// Python. get_count returns 0 for unknown keys.
/// </summary>
public sealed class ActivityTracker
{
    public readonly Dictionary<string, int> ActivityCounts = new()
    {
        ["mining"] = 0, ["forestry"] = 0, ["smithing"] = 0, ["refining"] = 0,
        ["alchemy"] = 0, ["engineering"] = 0, ["enchanting"] = 0, ["combat"] = 0,
    };

    public void RecordActivity(string activityType, int amount = 1)
    {
        if (ActivityCounts.ContainsKey(activityType))
            ActivityCounts[activityType] += amount;
    }

    public int GetCount(string activityType) =>
        ActivityCounts.GetValueOrDefault(activityType, 0);
}
