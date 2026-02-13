// ============================================================================
// Game1.Data.Enums.CraftingDiscipline
// Migrated from: Crafting-subdisciplines/ (5 minigame files + fishing)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Data.Enums
{
    /// <summary>
    /// Crafting discipline types. Each discipline has its own minigame and recipes.
    /// </summary>
    public enum CraftingDiscipline
    {
        Smithing,
        Alchemy,
        Refining,
        Engineering,
        Enchanting,
        Fishing
    }

    public static class CraftingDisciplineExtensions
    {
        private static readonly Dictionary<string, CraftingDiscipline> _fromJsonMap = new(StringComparer.OrdinalIgnoreCase)
        {
            ["smithing"]    = CraftingDiscipline.Smithing,
            ["alchemy"]     = CraftingDiscipline.Alchemy,
            ["refining"]    = CraftingDiscipline.Refining,
            ["engineering"] = CraftingDiscipline.Engineering,
            ["enchanting"]  = CraftingDiscipline.Enchanting,
            ["adornments"]  = CraftingDiscipline.Enchanting,  // alias
            ["fishing"]     = CraftingDiscipline.Fishing,
        };

        private static readonly Dictionary<CraftingDiscipline, string> _toJsonMap = new()
        {
            [CraftingDiscipline.Smithing]    = "smithing",
            [CraftingDiscipline.Alchemy]     = "alchemy",
            [CraftingDiscipline.Refining]    = "refining",
            [CraftingDiscipline.Engineering] = "engineering",
            [CraftingDiscipline.Enchanting]  = "enchanting",
            [CraftingDiscipline.Fishing]     = "fishing",
        };

        public static string ToJsonString(this CraftingDiscipline discipline)
        {
            return _toJsonMap.TryGetValue(discipline, out var str) ? str : "smithing";
        }

        public static CraftingDiscipline FromJsonString(string json)
        {
            if (string.IsNullOrEmpty(json)) return CraftingDiscipline.Smithing;
            return _fromJsonMap.TryGetValue(json, out var discipline) ? discipline : CraftingDiscipline.Smithing;
        }

        /// <summary>
        /// Get the station type string used in recipe JSON for this discipline.
        /// </summary>
        public static string GetStationType(this CraftingDiscipline discipline)
        {
            return discipline.ToJsonString();
        }
    }
}
