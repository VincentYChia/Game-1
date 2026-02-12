// Game1.Data.Enums.DungeonRarity
// Migrated from: data/models/world.py (lines 458-465)
// Phase: 1 - Foundation

using System.Collections.Generic;
using System.Linq;

namespace Game1.Data.Enums
{
    public enum DungeonRarity
    {
        Common,
        Uncommon,
        Rare,
        Epic,
        Legendary,
        Unique
    }

    public static class DungeonRarityExtensions
    {
        private static readonly Dictionary<DungeonRarity, string> ToStringMap = new()
        {
            { DungeonRarity.Common, "common" },
            { DungeonRarity.Uncommon, "uncommon" },
            { DungeonRarity.Rare, "rare" },
            { DungeonRarity.Epic, "epic" },
            { DungeonRarity.Legendary, "legendary" },
            { DungeonRarity.Unique, "unique" }
        };

        private static readonly Dictionary<string, DungeonRarity> FromStringMap =
            ToStringMap.ToDictionary(kvp => kvp.Value, kvp => kvp.Key);

        public static string ToJsonString(this DungeonRarity rarity) => ToStringMap[rarity];

        public static DungeonRarity DungeonRarityFromJsonString(string value) =>
            FromStringMap.TryGetValue(value, out var result) ? result : DungeonRarity.Common;
    }
}
