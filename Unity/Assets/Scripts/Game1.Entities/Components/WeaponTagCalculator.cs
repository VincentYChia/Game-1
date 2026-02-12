// Game1.Entities.Components.WeaponTagCalculator
// Migrated from: entities/components/weapon_tag_calculator.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Calculates weapon tag modifiers for combat.
    /// Weapon tags (from metadata) provide bonuses to damage, speed, range, and crit.
    /// </summary>
    public static class WeaponTagModifiers
    {
        // Tag → damage multiplier (additive)
        private static readonly Dictionary<string, float> DamageMultipliers = new()
        {
            { "heavy", 0.15f },       // +15% damage
            { "light", -0.10f },      // -10% damage (but faster)
            { "balanced", 0.0f },     // No damage change
            { "sharp", 0.10f },       // +10% damage
            { "blunt", 0.05f },       // +5% damage
            { "piercing", 0.08f },    // +8% damage
            { "magical", 0.0f },      // No physical bonus
            { "venomous", 0.0f },     // No direct damage bonus (applies poison)
            { "flaming", 0.05f },     // +5% fire damage bonus
            { "frozen", 0.05f },      // +5% ice damage bonus
            { "electrified", 0.05f }, // +5% lightning damage bonus
        };

        // Tag → attack speed multiplier (additive)
        private static readonly Dictionary<string, float> SpeedMultipliers = new()
        {
            { "heavy", -0.15f },   // -15% speed
            { "light", 0.20f },    // +20% speed
            { "balanced", 0.0f },  // No speed change
            { "quick", 0.15f },    // +15% speed
            { "slow", -0.20f },    // -20% speed
        };

        // Tag → range bonus (additive, in tiles)
        private static readonly Dictionary<string, float> RangeBonuses = new()
        {
            { "reach", 0.5f },    // +0.5 tile range
            { "long", 1.0f },     // +1.0 tile range
            { "short", -0.5f },   // -0.5 tile range
        };

        // Tag → crit chance bonus (additive)
        private static readonly Dictionary<string, float> CritBonuses = new()
        {
            { "sharp", 0.05f },    // +5% crit chance
            { "precise", 0.08f },  // +8% crit chance
            { "lucky", 0.03f },    // +3% crit chance
        };

        /// <summary>
        /// Calculate total damage multiplier from weapon tags.
        /// </summary>
        public static float GetDamageMultiplier(List<string> tags)
        {
            if (tags == null || tags.Count == 0) return 0f;
            return tags.Sum(tag => DamageMultipliers.GetValueOrDefault(tag.ToLower(), 0f));
        }

        /// <summary>
        /// Calculate total speed multiplier from weapon tags.
        /// </summary>
        public static float GetSpeedMultiplier(List<string> tags)
        {
            if (tags == null || tags.Count == 0) return 0f;
            return tags.Sum(tag => SpeedMultipliers.GetValueOrDefault(tag.ToLower(), 0f));
        }

        /// <summary>
        /// Calculate total range bonus from weapon tags.
        /// </summary>
        public static float GetRangeBonus(List<string> tags)
        {
            if (tags == null || tags.Count == 0) return 0f;
            return tags.Sum(tag => RangeBonuses.GetValueOrDefault(tag.ToLower(), 0f));
        }

        /// <summary>
        /// Calculate total crit chance bonus from weapon tags.
        /// </summary>
        public static float GetCritBonus(List<string> tags)
        {
            if (tags == null || tags.Count == 0) return 0f;
            return tags.Sum(tag => CritBonuses.GetValueOrDefault(tag.ToLower(), 0f));
        }
    }
}
