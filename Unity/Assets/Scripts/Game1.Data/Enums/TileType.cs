// ============================================================================
// Game1.Data.Enums.TileType
// Migrated from: data/models/world.py (TileType)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Data.Enums
{
    /// <summary>
    /// World tile types for the chunk-based world system.
    /// </summary>
    public enum TileType
    {
        Grass,
        Water,
        Stone,
        Sand,
        DirtPath,
        Tree,
        Ore,
        CraftingStation
    }

    public static class TileTypeExtensions
    {
        private static readonly Dictionary<string, TileType> _fromJsonMap = new(StringComparer.OrdinalIgnoreCase)
        {
            ["grass"]           = TileType.Grass,
            ["water"]           = TileType.Water,
            ["stone"]           = TileType.Stone,
            ["sand"]            = TileType.Sand,
            ["dirt_path"]       = TileType.DirtPath,
            ["dirtPath"]        = TileType.DirtPath,
            ["tree"]            = TileType.Tree,
            ["ore"]             = TileType.Ore,
            ["crafting_station"] = TileType.CraftingStation,
            ["craftingStation"] = TileType.CraftingStation,
        };

        private static readonly Dictionary<TileType, string> _toJsonMap = new()
        {
            [TileType.Grass]           = "grass",
            [TileType.Water]           = "water",
            [TileType.Stone]           = "stone",
            [TileType.Sand]            = "sand",
            [TileType.DirtPath]        = "dirt_path",
            [TileType.Tree]            = "tree",
            [TileType.Ore]             = "ore",
            [TileType.CraftingStation] = "crafting_station",
        };

        public static string ToJsonString(this TileType type)
        {
            return _toJsonMap.TryGetValue(type, out var str) ? str : "grass";
        }

        public static TileType FromJsonString(string json)
        {
            if (string.IsNullOrEmpty(json)) return TileType.Grass;
            return _fromJsonMap.TryGetValue(json, out var type) ? type : TileType.Grass;
        }

        /// <summary>Check if this tile type blocks movement.</summary>
        public static bool IsBlocking(this TileType type)
        {
            return type == TileType.Water || type == TileType.Tree || type == TileType.Ore;
        }
    }
}
