// ============================================================================
// Game1.Entities.Components.LevelingSystem
// Migrated from: entities/components/leveling.py (lines 1-27)
// Migration phase: 3
// Date: 2026-02-13
// ============================================================================

using System;
using Game1.Core;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Character leveling component.
    /// EXP formula: 200 * 1.75^(level - 1)
    /// Max level: 30
    /// </summary>
    public class LevelingSystem
    {
        public int Level { get; private set; } = 1;
        public int CurrentExp { get; private set; }
        public int UnallocatedStatPoints { get; set; }

        /// <summary>
        /// EXP required to reach a specific level.
        /// Formula: 200 * 1.75^(level - 1)
        /// </summary>
        public static int GetExpForLevel(int level)
        {
            return GameConfig.GetExpForLevel(level);
        }

        /// <summary>
        /// EXP required to reach the next level from current.
        /// Returns 0 if already at max level.
        /// </summary>
        public int GetExpForNextLevel()
        {
            if (Level >= GameConfig.MaxLevel) return 0;
            return GetExpForLevel(Level + 1);
        }

        /// <summary>
        /// Check if the character can level up with current EXP.
        /// </summary>
        public bool CanLevelUp()
        {
            if (Level >= GameConfig.MaxLevel) return false;
            return CurrentExp >= GetExpForNextLevel();
        }

        /// <summary>
        /// Add experience points. Triggers level up if threshold is reached.
        /// Returns true if a level up occurred.
        /// </summary>
        public bool GainExperience(int amount, object character = null)
        {
            if (Level >= GameConfig.MaxLevel) return false;

            CurrentExp += amount;
            int expNeeded = GetExpForNextLevel();

            if (CurrentExp >= expNeeded)
            {
                CurrentExp -= expNeeded;
                LevelUp(character);
                return true;
            }
            return false;
        }

        /// <summary>
        /// Perform a level up. Awards 1 stat point.
        /// </summary>
        public void LevelUp(object character = null)
        {
            if (Level >= GameConfig.MaxLevel) return;

            Level++;
            UnallocatedStatPoints++;

            GameEvents.RaiseLevelUp(character, Level);
        }

        /// <summary>
        /// Set level directly (for loading saves or debug).
        /// </summary>
        public void SetLevel(int level)
        {
            Level = Math.Clamp(level, 1, GameConfig.MaxLevel);
        }

        /// <summary>
        /// Set current EXP directly (for loading saves).
        /// </summary>
        public void SetExp(int exp)
        {
            CurrentExp = Math.Max(0, exp);
        }
    }
}
