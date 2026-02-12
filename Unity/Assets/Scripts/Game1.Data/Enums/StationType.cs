// Game1.Data.Enums.StationType
// Migrated from: data/models/world.py (lines 247-253)
// Phase: 1 - Foundation

using System.Collections.Generic;
using System.Linq;

namespace Game1.Data.Enums
{
    public enum StationType
    {
        Smithing,
        Alchemy,
        Refining,
        Engineering,
        Adornments
    }

    public static class StationTypeExtensions
    {
        private static readonly Dictionary<StationType, string> ToStringMap = new()
        {
            { StationType.Smithing, "smithing" },
            { StationType.Alchemy, "alchemy" },
            { StationType.Refining, "refining" },
            { StationType.Engineering, "engineering" },
            { StationType.Adornments, "adornments" }
        };

        private static readonly Dictionary<string, StationType> FromStringMap =
            ToStringMap.ToDictionary(kvp => kvp.Value, kvp => kvp.Key);

        public static string ToJsonString(this StationType type) => ToStringMap[type];

        public static StationType StationTypeFromJsonString(string value) =>
            FromStringMap.TryGetValue(value, out var result) ? result : StationType.Smithing;
    }
}
