// Game1.Entities.Components.LevelingSystem
// Migrated from: entities/components/leveling.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Character leveling system.
    /// EXP formula: 200 × 1.75^(level-1), max level 30.
    /// 1 stat point per level.
    /// </summary>
    public class LevelingSystem
    {
        public const int MaxLevel = 30;
        public const float BaseExp = 200f;
        public const float ExpGrowthRate = 1.75f;

        public int Level { get; set; } = 1;
        public int CurrentExp { get; set; }
        public int UnallocatedStatPoints { get; set; }

        /// <summary>
        /// Get EXP required for a specific level.
        /// Formula: 200 × 1.75^(level-1)
        /// </summary>
        public static int GetExpForLevel(int level)
        {
            if (level <= 1) return 0;
            return (int)(BaseExp * Math.Pow(ExpGrowthRate, level - 1));
        }

        /// <summary>
        /// Get EXP required to reach the next level from current level.
        /// </summary>
        public int GetExpToNextLevel()
        {
            if (Level >= MaxLevel) return 0;
            return GetExpForLevel(Level + 1);
        }

        /// <summary>
        /// Add experience points. Returns (didLevelUp, newLevel).
        /// </summary>
        public (bool LeveledUp, int NewLevel) AddExp(int amount)
        {
            if (Level >= MaxLevel) return (false, Level);

            CurrentExp += amount;
            bool leveledUp = false;

            while (Level < MaxLevel && CurrentExp >= GetExpToNextLevel())
            {
                CurrentExp -= GetExpToNextLevel();
                Level++;
                UnallocatedStatPoints++;
                leveledUp = true;
            }

            // Clamp exp at max level
            if (Level >= MaxLevel)
            {
                CurrentExp = 0;
            }

            return (leveledUp, Level);
        }

        /// <summary>
        /// Get EXP progress as fraction 0.0-1.0 toward next level.
        /// </summary>
        public float GetExpProgress()
        {
            int required = GetExpToNextLevel();
            if (required <= 0) return 1.0f;
            return (float)CurrentExp / required;
        }

        /// <summary>
        /// Serialize for saving.
        /// </summary>
        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "level", Level },
                { "current_exp", CurrentExp },
                { "unallocated_stat_points", UnallocatedStatPoints }
            };
        }

        /// <summary>
        /// Restore from save data.
        /// </summary>
        public void RestoreFromSaveData(Dictionary<string, object> data)
        {
            if (data == null) return;
            if (data.TryGetValue("level", out var lvl)) Level = Convert.ToInt32(lvl);
            if (data.TryGetValue("current_exp", out var exp)) CurrentExp = Convert.ToInt32(exp);
            if (data.TryGetValue("unallocated_stat_points", out var pts)) UnallocatedStatPoints = Convert.ToInt32(pts);
        }
    }
}
