// Game1.Data.Constants.DungeonConfig
// Migrated from: data/models/world.py (lines 470-507)
// Phase: 1 - Foundation

using System.Collections.Generic;
using Game1.Data.Enums;

namespace Game1.Data.Constants
{
    public class DungeonConfigEntry
    {
        public int SpawnWeight { get; set; }
        public int MobCount { get; set; }
        public Dictionary<int, int> TierWeights { get; set; } = new();
        public string DisplayName { get; set; } = "";
    }

    /// <summary>
    /// Hardcoded fallback dungeon configuration. JSON takes priority when loaded.
    /// </summary>
    public static class DungeonConfig
    {
        public static readonly Dictionary<DungeonRarity, DungeonConfigEntry> Config = new()
        {
            {
                DungeonRarity.Common, new DungeonConfigEntry
                {
                    SpawnWeight = 50,
                    MobCount = 20,
                    TierWeights = new Dictionary<int, int> { { 1, 80 }, { 2, 20 } },
                    DisplayName = "Common Dungeon"
                }
            },
            {
                DungeonRarity.Uncommon, new DungeonConfigEntry
                {
                    SpawnWeight = 25,
                    MobCount = 30,
                    TierWeights = new Dictionary<int, int> { { 1, 50 }, { 2, 40 }, { 3, 10 } },
                    DisplayName = "Uncommon Dungeon"
                }
            },
            {
                DungeonRarity.Rare, new DungeonConfigEntry
                {
                    SpawnWeight = 15,
                    MobCount = 40,
                    TierWeights = new Dictionary<int, int> { { 2, 60 }, { 3, 35 }, { 4, 5 } },
                    DisplayName = "Rare Dungeon"
                }
            },
            {
                DungeonRarity.Epic, new DungeonConfigEntry
                {
                    SpawnWeight = 7,
                    MobCount = 50,
                    TierWeights = new Dictionary<int, int> { { 2, 20 }, { 3, 60 }, { 4, 20 } },
                    DisplayName = "Epic Dungeon"
                }
            },
            {
                DungeonRarity.Legendary, new DungeonConfigEntry
                {
                    SpawnWeight = 2,
                    MobCount = 50,
                    TierWeights = new Dictionary<int, int> { { 3, 40 }, { 4, 60 } },
                    DisplayName = "Legendary Dungeon"
                }
            },
            {
                DungeonRarity.Unique, new DungeonConfigEntry
                {
                    SpawnWeight = 1,
                    MobCount = 50,
                    TierWeights = new Dictionary<int, int> { { 3, 10 }, { 4, 90 } },
                    DisplayName = "Unique Dungeon"
                }
            }
        };
    }
}
