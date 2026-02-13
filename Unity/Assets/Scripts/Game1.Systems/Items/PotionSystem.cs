// ============================================================================
// Game1.Systems.Items.PotionSystem
// Migrated from: systems/potion_system.py (387 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Tag-driven potion effect application system.
// Supported tags: healing, mana_restore, buff, resistance, utility.
// Tag modifiers: instant, over_time, self.
// Quality multipliers from crafting: potency (effect strength), duration.
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Systems.Items
{
    // ========================================================================
    // Potion Character Interface
    // ========================================================================

    /// <summary>
    /// Interface for character state needed by the potion system.
    /// Decouples PotionSystem from concrete Character class.
    /// </summary>
    public interface IPotionTarget
    {
        float Health { get; set; }
        float MaxHealth { get; }
        float Mana { get; set; }
        float MaxMana { get; }

        /// <summary>
        /// Add a timed buff to the character.
        /// </summary>
        void AddBuff(PotionBuff buff);
    }

    // ========================================================================
    // Potion Buff
    // ========================================================================

    /// <summary>
    /// A timed buff applied by a potion. Matches Python ActiveBuff used by potions.
    /// </summary>
    public class PotionBuff
    {
        public string BuffId { get; set; }
        public string Name { get; set; }
        public string EffectType { get; set; }     // "regenerate", "empower", "fortify"
        public string Category { get; set; }        // "health", "mana", "combat", "defense", etc.
        public string Magnitude { get; set; } = "moderate";
        public float BonusValue { get; set; }
        public float Duration { get; set; }
        public float DurationRemaining { get; set; }
        public string Source { get; set; } = "potion";
        public bool ConsumeOnUse { get; set; }
    }

    // ========================================================================
    // Potion Item Definition (subset used by this system)
    // ========================================================================

    /// <summary>
    /// Potion-relevant fields extracted from a MaterialDefinition.
    /// </summary>
    public class PotionDefinition
    {
        public string Name { get; set; }
        public List<string> EffectTags { get; set; } = new();
        public object EffectParams { get; set; } // Dictionary or List of Dictionaries
    }

    // ========================================================================
    // Potion System
    // ========================================================================

    /// <summary>
    /// Executes potion effects based on tags and parameters.
    /// Singleton pattern matches Python get_potion_executor().
    ///
    /// Supported effect tags (from Python PotionEffectExecutor):
    ///   healing + instant: Restore HP immediately
    ///   healing + over_time: HP regeneration buff
    ///   mana_restore + instant: Restore mana immediately
    ///   mana_restore + over_time: Mana regeneration buff
    ///   buff: Apply stat buff (strength, defense, speed, max_hp, attack_speed)
    ///   resistance: Elemental damage resistance (fire, ice, elemental)
    ///   utility: Tool/armor enhancements (efficiency, armor, weapon)
    /// </summary>
    public class PotionSystem
    {
        private static PotionSystem _instance;

        public static PotionSystem Instance => _instance ??= new PotionSystem();

        // ====================================================================
        // Main Entry Point
        // ====================================================================

        /// <summary>
        /// Apply potion effects to character based on tags and parameters.
        /// Returns (success, message).
        /// Matches Python apply_potion_effect() exactly.
        /// </summary>
        public (bool success, string message) UsePotion(
            IPotionTarget character,
            PotionDefinition potionDef,
            Dictionary<string, object> craftedStats = null)
        {
            if (potionDef.EffectTags == null || potionDef.EffectTags.Count == 0)
                return (false, $"{potionDef.Name} has no effect tags defined");

            // Get quality multipliers from crafting stats
            float potency = 1.0f;
            float durationMult = 1.0f;

            if (craftedStats != null)
            {
                if (craftedStats.TryGetValue("potency", out var potObj))
                    potency = Convert.ToSingle(potObj) / 100f;
                if (craftedStats.TryGetValue("duration", out var durObj))
                    durationMult = Convert.ToSingle(durObj) / 100f;
            }

            var tags = potionDef.EffectTags;
            var messages = new List<string>();
            bool success = false;

            // Support modular effectParams (array or single dict)
            if (potionDef.EffectParams is IList<object> paramsList)
            {
                foreach (var paramObj in paramsList)
                {
                    if (paramObj is Dictionary<string, object> paramSet)
                    {
                        var (s, m) = ApplySingleEffect(character, tags, paramSet, potency, durationMult);
                        if (s) { success = true; messages.Add(m); }
                    }
                }
            }
            else if (potionDef.EffectParams is Dictionary<string, object> singleParams)
            {
                var (s, m) = ApplySingleEffect(character, tags, singleParams, potency, durationMult);
                if (s) { success = true; messages.Add(m); }
            }

            string finalMessage = messages.Count > 0 ? string.Join(" | ", messages) : "No effect";

            if (success && potency > 1.0f)
                finalMessage += $" (potency: {(int)(potency * 100)}%)";

            return (success, finalMessage);
        }

        // ====================================================================
        // Single Effect Application
        // ====================================================================

        private (bool, string) ApplySingleEffect(
            IPotionTarget character,
            List<string> tags,
            Dictionary<string, object> parms,
            float potency,
            float durationMult)
        {
            if (tags.Contains("healing"))
                return ApplyHealing(character, tags, parms, potency, durationMult);
            if (tags.Contains("mana_restore"))
                return ApplyManaRestore(character, tags, parms, potency, durationMult);
            if (tags.Contains("buff"))
                return ApplyBuff(character, tags, parms, potency, durationMult);
            if (tags.Contains("resistance"))
                return ApplyResistance(character, tags, parms, potency, durationMult);
            if (tags.Contains("utility"))
                return ApplyUtility(character, tags, parms, potency, durationMult);

            return (false, "Unknown effect type");
        }

        // ====================================================================
        // Healing (instant or over_time)
        // ====================================================================

        private (bool, string) ApplyHealing(
            IPotionTarget character, List<string> tags,
            Dictionary<string, object> parms, float potency, float durationMult)
        {
            if (tags.Contains("instant"))
            {
                float baseHeal = GetFloat(parms, "heal_amount", 50f);
                float healAmount = MathF.Min(baseHeal * potency, character.MaxHealth - character.Health);
                character.Health += healAmount;
                return (true, $"Restored {healAmount:F0} HP");
            }

            if (tags.Contains("over_time"))
            {
                float baseRegen = GetFloat(parms, "heal_per_second", 5f);
                float baseDuration = GetFloat(parms, "duration", 60f);
                float actualRegen = baseRegen * potency;
                float actualDuration = baseDuration * durationMult;

                character.AddBuff(new PotionBuff
                {
                    BuffId = "potion_health_regen",
                    Name = "Health Regeneration",
                    EffectType = "regenerate",
                    Category = "health",
                    BonusValue = actualRegen,
                    Duration = actualDuration,
                    DurationRemaining = actualDuration,
                });
                return (true, $"Regenerating {actualRegen:F1} HP/s for {actualDuration:F0}s");
            }

            return (false, "Unknown healing type");
        }

        // ====================================================================
        // Mana Restore (instant or over_time)
        // ====================================================================

        private (bool, string) ApplyManaRestore(
            IPotionTarget character, List<string> tags,
            Dictionary<string, object> parms, float potency, float durationMult)
        {
            if (tags.Contains("instant"))
            {
                float baseMana = GetFloat(parms, "mana_amount", 50f);
                float manaAmount = MathF.Min(baseMana * potency, character.MaxMana - character.Mana);
                character.Mana += manaAmount;
                return (true, $"Restored {manaAmount:F0} Mana");
            }

            if (tags.Contains("over_time"))
            {
                float baseRegen = GetFloat(parms, "mana_per_second", 2f);
                float baseDuration = GetFloat(parms, "duration", 60f);
                float actualRegen = baseRegen * potency;
                float actualDuration = baseDuration * durationMult;

                character.AddBuff(new PotionBuff
                {
                    BuffId = "potion_mana_regen",
                    Name = "Mana Regeneration",
                    EffectType = "regenerate",
                    Category = "mana",
                    BonusValue = actualRegen,
                    Duration = actualDuration,
                    DurationRemaining = actualDuration,
                });
                return (true, $"Regenerating {actualRegen:F1} Mana/s for {actualDuration:F0}s");
            }

            return (false, "Unknown mana restore type");
        }

        // ====================================================================
        // Buff (stat buffs: strength, defense, speed, max_hp, attack_speed)
        // ====================================================================

        private (bool, string) ApplyBuff(
            IPotionTarget character, List<string> tags,
            Dictionary<string, object> parms, float potency, float durationMult)
        {
            string buffType = GetString(parms, "buff_type", "strength");
            float baseValue = GetFloat(parms, "buff_value", 0.2f);
            float baseDuration = GetFloat(parms, "duration", 300f);

            float actualValue = baseValue * potency;
            float actualDuration = baseDuration * durationMult;

            var categoryMap = new Dictionary<string, string>
            {
                ["strength"] = "combat",
                ["defense"] = "defense",
                ["speed"] = "movement",
                ["max_hp"] = "health",
                ["attack_speed"] = "combat",
            };
            string category = categoryMap.TryGetValue(buffType, out var c) ? c : "combat";

            var nameMap = new Dictionary<string, string>
            {
                ["strength"] = "Strength Boost",
                ["defense"] = "Defense Boost",
                ["speed"] = "Speed Boost",
                ["max_hp"] = "Vitality Boost",
                ["attack_speed"] = "Attack Speed Boost",
            };
            string buffName = nameMap.TryGetValue(buffType, out var n) ? n : $"{buffType} Buff";

            character.AddBuff(new PotionBuff
            {
                BuffId = $"potion_{buffType}",
                Name = buffName,
                EffectType = "empower",
                Category = category,
                BonusValue = actualValue,
                Duration = actualDuration,
                DurationRemaining = actualDuration,
            });

            string msg = buffType switch
            {
                "strength" => $"+{(int)(actualValue * 100)}% physical damage for {actualDuration:F0}s",
                "defense" => $"+{(int)(actualValue * 100)}% defense for {actualDuration:F0}s",
                "speed" => $"+{(int)(actualValue * 100)}% move speed for {actualDuration:F0}s",
                "attack_speed" => $"+{(int)(actualValue * 100)}% attack speed for {actualDuration:F0}s",
                "max_hp" => $"+{(int)(actualValue * 100)}% max HP for {actualDuration:F0}s",
                _ => $"{buffType} buff for {actualDuration:F0}s",
            };

            return (true, msg);
        }

        // ====================================================================
        // Resistance (fire, ice, elemental)
        // ====================================================================

        private (bool, string) ApplyResistance(
            IPotionTarget character, List<string> tags,
            Dictionary<string, object> parms, float potency, float durationMult)
        {
            string resistType = GetString(parms, "resistance_type", "fire");
            float baseReduction = GetFloat(parms, "damage_reduction", 0.5f);
            float baseDuration = GetFloat(parms, "duration", 360f);

            float actualReduction = MathF.Min(baseReduction * potency, 0.9f); // Cap at 90%
            float actualDuration = baseDuration * durationMult;

            var nameMap = new Dictionary<string, string>
            {
                ["fire"] = "Fire Resistance",
                ["ice"] = "Ice Resistance",
                ["elemental"] = "Elemental Resistance",
            };
            string buffName = nameMap.TryGetValue(resistType, out var n) ? n : $"{resistType} Resistance";

            character.AddBuff(new PotionBuff
            {
                BuffId = $"resistance_{resistType}",
                Name = buffName,
                EffectType = "fortify",
                Category = "defense",
                BonusValue = actualReduction,
                Duration = actualDuration,
                DurationRemaining = actualDuration,
            });

            string msg = resistType == "elemental"
                ? $"All elemental resistance for {actualDuration:F0}s"
                : $"{(int)(actualReduction * 100)}% {resistType} resistance for {actualDuration:F0}s";

            return (true, msg);
        }

        // ====================================================================
        // Utility (efficiency oil, armor polish, weapon oil)
        // ====================================================================

        private (bool, string) ApplyUtility(
            IPotionTarget character, List<string> tags,
            Dictionary<string, object> parms, float potency, float durationMult)
        {
            string utilType = GetString(parms, "utility_type", "efficiency");
            float baseValue = GetFloat(parms, "utility_value", 0.15f);
            float baseDuration = GetFloat(parms, "duration", 3600f);

            float actualValue = baseValue * potency;
            float actualDuration = baseDuration * durationMult;

            var categoryMap = new Dictionary<string, string>
            {
                ["efficiency"] = "gathering",
                ["armor"] = "defense",
                ["weapon"] = "combat",
            };
            string category = categoryMap.TryGetValue(utilType, out var c) ? c : "gathering";

            var nameMap = new Dictionary<string, string>
            {
                ["efficiency"] = "Efficiency Oil",
                ["armor"] = "Armor Polish",
                ["weapon"] = "Weapon Oil",
            };
            string buffName = nameMap.TryGetValue(utilType, out var n) ? n : $"{utilType} Enhancement";

            character.AddBuff(new PotionBuff
            {
                BuffId = $"utility_{utilType}",
                Name = buffName,
                EffectType = "empower",
                Category = category,
                BonusValue = actualValue,
                Duration = actualDuration,
                DurationRemaining = actualDuration,
            });

            string msg = utilType switch
            {
                "efficiency" => $"+{(int)(actualValue * 100)}% gathering speed for {actualDuration:F0}s",
                "armor" => $"+{(int)(actualValue * 100)}% armor defense for {actualDuration:F0}s",
                "weapon" => $"+{(int)(actualValue * 100)}% weapon damage for {actualDuration:F0}s",
                _ => $"{utilType} enhancement for {actualDuration:F0}s",
            };

            return (true, msg);
        }

        // ====================================================================
        // Param Helpers
        // ====================================================================

        private static float GetFloat(Dictionary<string, object> d, string key, float defaultVal)
        {
            return d.TryGetValue(key, out var v) ? Convert.ToSingle(v) : defaultVal;
        }

        private static string GetString(Dictionary<string, object> d, string key, string defaultVal)
        {
            return d.TryGetValue(key, out var v) ? v?.ToString() ?? defaultVal : defaultVal;
        }
    }
}
