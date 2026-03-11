// Game1.Data.Enums.ChunkType
// Migrated from: data/models/world.py (lines 230-244)
// Phase: 1 - Foundation

using System.Collections.Generic;
using System.Linq;

namespace Game1.Data.Enums
{
    public enum ChunkType
    {
        // Land biomes (9)
        PeacefulForest,
        PeacefulQuarry,
        PeacefulCave,
        DangerousForest,
        DangerousQuarry,
        DangerousCave,
        RareHiddenForest,
        RareAncientQuarry,
        RareDeepCave,
        // Water biomes (3)
        WaterLake,
        WaterRiver,
        WaterCursedSwamp
    }

    public static class ChunkTypeExtensions
    {
        private static readonly Dictionary<ChunkType, string> ToStringMap = new()
        {
            { ChunkType.PeacefulForest, "peaceful_forest" },
            { ChunkType.PeacefulQuarry, "peaceful_quarry" },
            { ChunkType.PeacefulCave, "peaceful_cave" },
            { ChunkType.DangerousForest, "dangerous_forest" },
            { ChunkType.DangerousQuarry, "dangerous_quarry" },
            { ChunkType.DangerousCave, "dangerous_cave" },
            { ChunkType.RareHiddenForest, "rare_hidden_forest" },
            { ChunkType.RareAncientQuarry, "rare_ancient_quarry" },
            { ChunkType.RareDeepCave, "rare_deep_cave" },
            { ChunkType.WaterLake, "water_lake" },
            { ChunkType.WaterRiver, "water_river" },
            { ChunkType.WaterCursedSwamp, "water_cursed_swamp" }
        };

        private static readonly Dictionary<string, ChunkType> FromStringMap =
            ToStringMap.ToDictionary(kvp => kvp.Value, kvp => kvp.Key);

        public static string ToJsonString(this ChunkType type) => ToStringMap[type];

        public static ChunkType ChunkTypeFromJsonString(string value) =>
            FromStringMap.TryGetValue(value, out var result) ? result : ChunkType.PeacefulForest;
    }
}
