// ============================================================================
// Game1.Entities.Components.StatTracker
// Migrated from: entities/components/stat_tracker.py (lines 1-100)
// Migration phase: 3
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Generic statistical tracking entry for counting and aggregating numeric values.
    /// </summary>
    public class StatEntry
    {
        public int Count { get; set; }
        public double TotalValue { get; set; }
        public double MaxValue { get; set; }
        public double? LastUpdated { get; set; }

        /// <summary>Record a new occurrence with a value.</summary>
        public void Record(double value = 1.0)
        {
            Count++;
            TotalValue += value;
            if (value > MaxValue) MaxValue = value;
            LastUpdated = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        }

        /// <summary>Get average value.</summary>
        public double GetAverage()
        {
            return Count > 0 ? TotalValue / Count : 0.0;
        }

        public Dictionary<string, object> ToDict()
        {
            return new Dictionary<string, object>
            {
                ["count"] = Count,
                ["total_value"] = TotalValue,
                ["max_value"] = MaxValue,
                ["last_updated"] = LastUpdated,
            };
        }

        public static StatEntry FromDict(Dictionary<string, object> data)
        {
            return new StatEntry
            {
                Count = data.TryGetValue("count", out var c) ? Convert.ToInt32(c) : 0,
                TotalValue = data.TryGetValue("total_value", out var tv) ? Convert.ToDouble(tv) : 0.0,
                MaxValue = data.TryGetValue("max_value", out var mv) ? Convert.ToDouble(mv) : 0.0,
                LastUpdated = data.TryGetValue("last_updated", out var lu) && lu != null
                    ? Convert.ToDouble(lu) : null,
            };
        }
    }

    /// <summary>
    /// Comprehensive stat tracking component.
    /// Tracks activities like damage dealt, resources gathered, crafting stats, etc.
    /// </summary>
    public class StatTracker
    {
        /// <summary>Activity counts keyed by activity type string.</summary>
        private readonly Dictionary<string, StatEntry> _activities = new();

        /// <summary>Item management tracking.</summary>
        public Dictionary<string, Dictionary<string, int>> ItemManagement { get; } = new()
        {
            ["equipment_equipped"] = new Dictionary<string, int>(),
            ["equipment_unequipped"] = new Dictionary<string, int>(),
        };

        public int TotalEquipmentSwaps { get; set; }

        // ====================================================================
        // Activity Recording
        // ====================================================================

        /// <summary>
        /// Record an activity with an optional value.
        /// </summary>
        public void RecordActivity(string activityType, double value = 1.0)
        {
            if (!_activities.TryGetValue(activityType, out var entry))
            {
                entry = new StatEntry();
                _activities[activityType] = entry;
            }
            entry.Record(value);
        }

        /// <summary>Get the count for an activity type.</summary>
        public int GetActivityCount(string activityType)
        {
            return _activities.TryGetValue(activityType, out var entry) ? entry.Count : 0;
        }

        /// <summary>Get the total value for an activity type.</summary>
        public double GetActivityTotal(string activityType)
        {
            return _activities.TryGetValue(activityType, out var entry) ? entry.TotalValue : 0.0;
        }

        /// <summary>Get the stat entry for an activity type. Returns null if none recorded.</summary>
        public StatEntry GetActivity(string activityType)
        {
            return _activities.TryGetValue(activityType, out var entry) ? entry : null;
        }

        // ====================================================================
        // Serialization
        // ====================================================================

        public Dictionary<string, object> ToDict()
        {
            var activitiesDict = new Dictionary<string, object>();
            foreach (var kvp in _activities)
            {
                activitiesDict[kvp.Key] = kvp.Value.ToDict();
            }

            return new Dictionary<string, object>
            {
                ["activities"] = activitiesDict,
                ["total_equipment_swaps"] = TotalEquipmentSwaps,
            };
        }

        public static StatTracker FromDict(Dictionary<string, object> data)
        {
            var tracker = new StatTracker();

            if (data.TryGetValue("total_equipment_swaps", out var swaps))
                tracker.TotalEquipmentSwaps = Convert.ToInt32(swaps);

            // Activities would need more complex deserialization in practice
            return tracker;
        }
    }
}
