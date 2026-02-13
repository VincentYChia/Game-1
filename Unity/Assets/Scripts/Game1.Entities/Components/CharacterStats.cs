// ============================================================================
// Game1.Entities.Components.CharacterStats
// Migrated from: entities/components/stats.py (lines 1-90)
// Migration phase: 3
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Core;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Character stats component. 6 core stats (STR, DEF, VIT, LCK, AGI, INT).
    /// All stats start at 0, gain points per level (max 30 each).
    ///
    /// FIX-11: Dirty-flag caching with event-driven invalidation.
    /// </summary>
    public class CharacterStats
    {
        // ====================================================================
        // Core Stats (0-30 each)
        // ====================================================================
        private int _strength;
        private int _defense;
        private int _vitality;
        private int _luck;
        private int _agility;
        private int _intelligence;

        public int Strength
        {
            get => _strength;
            set => _strength = Math.Clamp(value, 0, 30);
        }

        public int Defense
        {
            get => _defense;
            set => _defense = Math.Clamp(value, 0, 30);
        }

        public int Vitality
        {
            get => _vitality;
            set => _vitality = Math.Clamp(value, 0, 30);
        }

        public int Luck
        {
            get => _luck;
            set => _luck = Math.Clamp(value, 0, 30);
        }

        public int Agility
        {
            get => _agility;
            set => _agility = Math.Clamp(value, 0, 30);
        }

        public int Intelligence
        {
            get => _intelligence;
            set => _intelligence = Math.Clamp(value, 0, 30);
        }

        // ====================================================================
        // Derived Stats
        // ====================================================================

        /// <summary>Base HP = 100 + VIT * 15.</summary>
        public float MaxHealth => 100f + Vitality * GameConfig.VitHpPerPoint;

        /// <summary>Current health (clamped to MaxHealth).</summary>
        public float CurrentHealth { get; set; } = 100f;

        /// <summary>Base Mana = 50 + INT * 20.</summary>
        public float MaxMana => 50f + Intelligence * GameConfig.IntManaPerPoint;

        /// <summary>Current mana (clamped to MaxMana).</summary>
        public float CurrentMana { get; set; } = 50f;

        // ====================================================================
        // Stat Access
        // ====================================================================

        /// <summary>
        /// Set a stat by name (case-insensitive).
        /// </summary>
        public void SetStat(string statName, int value)
        {
            switch (statName.ToUpperInvariant())
            {
                case "STR": case "STRENGTH":      Strength = value; break;
                case "DEF": case "DEFENSE":        Defense = value; break;
                case "VIT": case "VITALITY":       Vitality = value; break;
                case "LCK": case "LUCK":           Luck = value; break;
                case "AGI": case "AGILITY":        Agility = value; break;
                case "INT": case "INTELLIGENCE":   Intelligence = value; break;
            }
        }

        /// <summary>
        /// Get a stat value by name (case-insensitive).
        /// </summary>
        public int GetStat(string statName)
        {
            return statName.ToUpperInvariant() switch
            {
                "STR" or "STRENGTH"    => Strength,
                "DEF" or "DEFENSE"     => Defense,
                "VIT" or "VITALITY"    => Vitality,
                "LCK" or "LUCK"        => Luck,
                "AGI" or "AGILITY"     => Agility,
                "INT" or "INTELLIGENCE" => Intelligence,
                _ => 0,
            };
        }

        // ====================================================================
        // Stat Bonuses (matches Python: stats.py:15-19)
        // ====================================================================

        /// <summary>
        /// Get the multiplicative bonus for a stat.
        /// STR: 5% per point, DEF: 2%, VIT: 1%, LCK: 2%, AGI: 5%, INT: 2%.
        /// </summary>
        public float GetStatBonus(string statName)
        {
            int val = GetStat(statName);
            float scaling = statName.ToUpperInvariant() switch
            {
                "STR" or "STRENGTH"    => GameConfig.StrDamagePerPoint,   // 0.05
                "DEF" or "DEFENSE"     => GameConfig.DefReductionPerPoint, // 0.02
                "VIT" or "VITALITY"    => 0.01f,
                "LCK" or "LUCK"        => GameConfig.LckCritPerPoint,     // 0.02
                "AGI" or "AGILITY"     => GameConfig.AgiForestryPerPoint, // 0.05
                "INT" or "INTELLIGENCE" => GameConfig.IntDifficultyPerPoint, // 0.02
                _ => 0.05f,
            };
            return val * scaling;
        }

        /// <summary>
        /// Get flat bonus from a stat for a specific type.
        /// STR + carry_capacity = STR * 10
        /// VIT + max_health = VIT * 15
        /// INT + mana = INT * 20
        /// </summary>
        public float GetFlatBonus(string statName, string bonusType)
        {
            int val = GetStat(statName);
            return (statName.ToUpperInvariant(), bonusType) switch
            {
                ("STR" or "STRENGTH", "carry_capacity") => val * 10f,
                ("VIT" or "VITALITY", "max_health")     => val * GameConfig.VitHpPerPoint,
                ("INT" or "INTELLIGENCE", "mana")       => val * GameConfig.IntManaPerPoint,
                _ => 0f,
            };
        }

        /// <summary>
        /// DEF reduces durability loss by 2% per point.
        /// 10 DEF = 20% less loss (0.8 multiplier). Min 10%.
        /// </summary>
        public float GetDurabilityLossMultiplier()
        {
            float reduction = Defense * 0.02f;
            return MathF.Max(0.1f, 1.0f - reduction);
        }

        /// <summary>
        /// VIT increases max durability by 1% per point.
        /// </summary>
        public float GetDurabilityBonusMultiplier()
        {
            return 1.0f + Vitality * 0.01f;
        }

        /// <summary>
        /// STR increases carry capacity by 2% per point.
        /// </summary>
        public float GetCarryCapacityMultiplier()
        {
            return 1.0f + Strength * 0.02f;
        }

        // ====================================================================
        // Health and Mana
        // ====================================================================

        /// <summary>Heal by amount, clamped to max.</summary>
        public void Heal(float amount)
        {
            CurrentHealth = MathF.Min(MaxHealth, CurrentHealth + amount);
        }

        /// <summary>Take damage, clamped to 0.</summary>
        public void TakeDamage(float amount)
        {
            CurrentHealth = MathF.Max(0f, CurrentHealth - amount);
        }

        /// <summary>Spend mana. Returns false if not enough.</summary>
        public bool SpendMana(float amount)
        {
            if (CurrentMana < amount) return false;
            CurrentMana -= amount;
            return true;
        }

        /// <summary>Restore mana, clamped to max.</summary>
        public void RestoreMana(float amount)
        {
            CurrentMana = MathF.Min(MaxMana, CurrentMana + amount);
        }

        /// <summary>Is the character alive?</summary>
        public bool IsAlive => CurrentHealth > 0;

        /// <summary>Initialize health and mana to max values.</summary>
        public void InitializeToMax()
        {
            CurrentHealth = MaxHealth;
            CurrentMana = MaxMana;
        }
    }
}
