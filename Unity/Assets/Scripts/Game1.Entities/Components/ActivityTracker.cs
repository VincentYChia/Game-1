// Game1.Entities.Components.ActivityTracker
// Migrated from: entities/components/activity_tracker.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Tracks activity counts for title/unlock conditions.
    /// Simple counter per activity type (e.g., "mining", "smithing_craft").
    /// Used by UnlockCondition.Evaluate() via ICharacterState.GetActivityCount().
    /// </summary>
    public class ActivityTracker
    {
        /// <summary>
        /// Activity type → count (e.g., "trees_chopped" → 150).
        /// </summary>
        public Dictionary<string, int> ActivityCounts { get; private set; } = new();

        /// <summary>
        /// Record an activity occurrence.
        /// </summary>
        public void RecordActivity(string activityType, int count = 1)
        {
            if (!ActivityCounts.ContainsKey(activityType))
                ActivityCounts[activityType] = 0;
            ActivityCounts[activityType] += count;
        }

        /// <summary>
        /// Get current count for an activity type.
        /// </summary>
        public int GetCount(string activityType)
        {
            return ActivityCounts.TryGetValue(activityType, out int count) ? count : 0;
        }

        /// <summary>
        /// Check if activity count meets or exceeds threshold.
        /// </summary>
        public bool HasReached(string activityType, int threshold)
        {
            return GetCount(activityType) >= threshold;
        }

        /// <summary>
        /// Serialize for saving.
        /// </summary>
        public Dictionary<string, int> ToSaveData()
        {
            return new Dictionary<string, int>(ActivityCounts);
        }

        /// <summary>
        /// Restore from save data.
        /// </summary>
        public void RestoreFromSaveData(Dictionary<string, int> data)
        {
            if (data == null) return;
            ActivityCounts = new Dictionary<string, int>(data);
        }
    }
}
