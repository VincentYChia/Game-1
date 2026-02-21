// ============================================================================
// Game1.Systems.Combat.WeaponTagCalculator
// Migrated from: entities/components/weapon_tag_calculator logic (scattered in
//   combat_manager.py lines 684-982)
// Migration phase: 3/4
// Date: 2026-02-21
//
// Extracts weapon tag analysis into a dedicated calculator.
// Analyzes EquipmentItem tags to produce WeaponTagModifiers for combat.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;
using Game1.Data.Enums;

namespace Game1.Systems.Combat
{
    /// <summary>
    /// Calculates combat modifiers from weapon tags and properties.
    /// Takes an EquipmentItem (weapon) and produces WeaponTagModifiers
    /// used by DamageCalculator in the damage pipeline.
    ///
    /// Tag effects (from Python combat_manager.py):
    ///   - Hand type: 2H = +20%, versatile no offhand = +10%
    ///   - "crushing": +20% vs armored (defense > 10)
    ///   - "precision": +10% crit chance
    ///   - "armor_breaker": ignore 25% of enemy defense
    ///   - "swift": +15% attack speed
    ///   - "heavy": +10% damage, -10% attack speed
    ///   - "light": -5% damage, +10% attack speed
    /// </summary>
    public static class WeaponTagCalculator
    {
        /// <summary>
        /// Calculate all combat modifiers from a weapon's tags and properties.
        /// Returns default modifiers (1.0x damage, no bonuses) for null weapons.
        /// </summary>
        public static WeaponTagModifiers Calculate(EquipmentItem weapon, bool hasOffhand)
        {
            var mods = new WeaponTagModifiers();

            if (weapon == null) return mods;

            // Step 1: Hand type bonus
            // Matches Python: combat_manager.py hand type calculation
            mods.DamageMultiplier = CalculateHandTypeBonus(weapon, hasOffhand);

            // Step 2: Process weapon tags
            if (weapon.Tags != null)
            {
                foreach (var tag in weapon.Tags)
                {
                    ApplyTag(tag, mods);
                }
            }

            // Step 3: Process effect tags
            if (weapon.EffectTags != null)
            {
                foreach (var tag in weapon.EffectTags)
                {
                    ApplyTag(tag, mods);
                }
            }

            return mods;
        }

        /// <summary>
        /// Calculate hand type bonus multiplier.
        /// Matches Python: combat_manager.py:738-751
        ///   - Two-handed: 1.2x (20% bonus)
        ///   - Versatile without offhand: 1.1x (10% bonus)
        ///   - One-handed / default: 1.0x
        /// </summary>
        public static float CalculateHandTypeBonus(EquipmentItem weapon, bool hasOffhand)
        {
            if (weapon == null) return 1.0f;

            string handType = weapon.HandTypeRaw?.ToLowerInvariant() ?? "default";

            return handType switch
            {
                "twohanded" or "two_handed" or "2h" => 1.2f,
                "versatile" when !hasOffhand => 1.1f,
                _ => 1.0f,
            };
        }

        /// <summary>
        /// Apply a single tag's effect to the modifiers.
        /// </summary>
        private static void ApplyTag(string tag, WeaponTagModifiers mods)
        {
            if (string.IsNullOrEmpty(tag)) return;

            switch (tag.ToLowerInvariant())
            {
                // Crushing: +20% damage vs armored enemies (defense > 10)
                case "crushing":
                    mods.CrushingBonus = 0.2f;
                    break;

                // Precision: +10% crit chance
                case "precision":
                    mods.CritBonus += 0.10f;
                    break;

                // Armor breaker: Ignore 25% of enemy defense
                case "armor_breaker":
                case "armor_piercing":
                    mods.ArmorPenetration = Math.Max(mods.ArmorPenetration, 0.25f);
                    break;

                // Swift: +15% attack speed (stored in speed modifier)
                case "swift":
                    mods.AttackSpeedMultiplier += 0.15f;
                    break;

                // Heavy: +10% damage, -10% attack speed
                case "heavy":
                    mods.DamageMultiplier *= 1.1f;
                    mods.AttackSpeedMultiplier -= 0.1f;
                    break;

                // Light: -5% damage, +10% attack speed
                case "light":
                    mods.DamageMultiplier *= 0.95f;
                    mods.AttackSpeedMultiplier += 0.1f;
                    break;

                // Vampiric: applies lifesteal (stored as flag)
                case "vampiric":
                case "lifesteal":
                    mods.HasLifesteal = true;
                    mods.LifestealFraction = 0.1f;
                    break;

                // Knockback: applies knockback on hit
                case "knockback":
                    mods.HasKnockback = true;
                    mods.KnockbackForce = 3.0f;
                    break;
            }
        }

        /// <summary>
        /// Calculate effective crit chance including weapon tag bonuses.
        /// Base crit = LCK * 0.02 (2% per luck point).
        /// Precision adds +10%.
        /// Matches Python: combat_manager.py:910-920
        /// </summary>
        public static float CalculateCritChance(int luck, WeaponTagModifiers mods)
        {
            float baseCrit = luck * 0.02f;
            float weaponBonus = mods?.CritBonus ?? 0f;
            return Math.Min(baseCrit + weaponBonus, 1.0f);
        }

        /// <summary>
        /// Calculate effective defense after armor penetration.
        /// Matches Python: combat_manager.py:935-945
        /// </summary>
        public static float CalculateEffectiveDefense(float enemyDefense, WeaponTagModifiers mods)
        {
            float penetration = mods?.ArmorPenetration ?? 0f;
            return enemyDefense * (1.0f - penetration);
        }
    }

}
