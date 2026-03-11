// Game1.Data.Enums.TileType
// Migrated from: data/models/world.py (lines 39-44)
// Phase: 1 - Foundation

using System.Collections.Generic;
using System.Linq;

namespace Game1.Data.Enums
{
    public enum TileType
    {
        Grass,
        Stone,
        Water,
        Dirt
    }

    public static class TileTypeExtensions
    {
        private static readonly Dictionary<TileType, string> ToStringMap = new()
        {
            { TileType.Grass, "grass" },
            { TileType.Stone, "stone" },
            { TileType.Water, "water" },
            { TileType.Dirt, "dirt" }
        };

        private static readonly Dictionary<string, TileType> FromStringMap =
            ToStringMap.ToDictionary(kvp => kvp.Value, kvp => kvp.Key);

        public static string ToJsonString(this TileType type) => ToStringMap[type];

        public static TileType TileTypeFromJsonString(string value) =>
            FromStringMap.TryGetValue(value, out var result) ? result : TileType.Grass;
    }
}
