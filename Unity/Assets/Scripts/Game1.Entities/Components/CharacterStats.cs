// Game1.Entities.Components.CharacterStats
// Migrated from: entities/components/stats.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Core character stats component.
    /// 6 stats, all start at 0, gain 1 point per level (max 30).
    /// Provides bonus calculation methods per stat.
    /// </summary>
    [Serializable]
    public class CharacterStats
    {
        // 6 core stats — all start at 0
        public int Strength { get; set; }
        public int Defense { get; set; }
        public int Vitality { get; set; }
        public int Luck { get; set; }
        public int Agility { get; set; }
        public int Intelligence { get; set; }

        // === Stat Bonus Methods ===
        // These mirror the Python get_bonus() / get_flat_bonus() logic exactly.

        /// <summary>
        /// Get the multiplicative bonus for a stat.
        /// STR: +5% mining/melee damage per point
        /// DEF: +2% damage reduction per point
        /// VIT: (no multiplicative bonus — flat only)
        /// LCK: +2% crit chance per point
        /// AGI: +5% forestry damage per point
        /// INT: -2% minigame difficulty per point (returns negative)
        /// </summary>
        public float GetBonus(string statName)
        {
            return statName.ToLower() switch
            {
                "strength" or "str" => Strength * 0.05f,
                "defense" or "def" => Defense * 0.02f,
                "vitality" or "vit" => 0f,
                "luck" or "lck" => Luck * 0.02f,
                "agility" or "agi" => Agility * 0.05f,
                "intelligence" or "int" => Intelligence * -0.02f,
                _ => 0f
            };
        }

        /// <summary>
        /// Get flat bonus for a stat.
        /// VIT + max_health: +15 HP per point
        /// INT + mana: +20 mana per point
        /// STR + inventory: +10 inventory slots per point
        /// </summary>
        public float GetFlatBonus(string statName, string bonusType)
        {
            string key = $"{statName.ToLower()}_{bonusType.ToLower()}";
            return key switch
            {
                "vitality_max_health" or "vit_max_health" => Vitality * 15f,
                "intelligence_mana" or "int_mana" => Intelligence * 20f,
                "strength_inventory" or "str_inventory" => Strength * 10f,
                _ => 0f
            };
        }

        /// <summary>
        /// Get durability loss multiplier from DEF stat.
        /// DEF: -1% durability loss per point (minimum 0.5x loss).
        /// </summary>
        public float GetDurabilityLossMultiplier()
        {
            float reduction = Defense * 0.01f;
            return Math.Max(0.5f, 1.0f - reduction);
        }

        /// <summary>
        /// Get the stat value by name.
        /// </summary>
        public int GetStatByName(string statName)
        {
            return statName.ToUpper() switch
            {
                "STR" or "STRENGTH" => Strength,
                "DEF" or "DEFENSE" => Defense,
                "VIT" or "VITALITY" => Vitality,
                "LCK" or "LUCK" => Luck,
                "AGI" or "AGILITY" => Agility,
                "INT" or "INTELLIGENCE" => Intelligence,
                _ => 0
            };
        }

        /// <summary>
        /// Set a stat value by name.
        /// Returns true if the stat was found and set.
        /// </summary>
        public bool SetStatByName(string statName, int value)
        {
            switch (statName.ToUpper())
            {
                case "STR": case "STRENGTH": Strength = value; return true;
                case "DEF": case "DEFENSE": Defense = value; return true;
                case "VIT": case "VITALITY": Vitality = value; return true;
                case "LCK": case "LUCK": Luck = value; return true;
                case "AGI": case "AGILITY": Agility = value; return true;
                case "INT": case "INTELLIGENCE": Intelligence = value; return true;
                default: return false;
            }
        }

        /// <summary>
        /// Serialize stats to dictionary for save data.
        /// </summary>
        public Dictionary<string, int> ToSaveData()
        {
            return new Dictionary<string, int>
            {
                { "strength", Strength },
                { "defense", Defense },
                { "vitality", Vitality },
                { "luck", Luck },
                { "agility", Agility },
                { "intelligence", Intelligence }
            };
        }

        /// <summary>
        /// Restore stats from save data.
        /// </summary>
        public void RestoreFromSaveData(Dictionary<string, int> data)
        {
            if (data == null) return;
            if (data.TryGetValue("strength", out int str)) Strength = str;
            if (data.TryGetValue("defense", out int def)) Defense = def;
            if (data.TryGetValue("vitality", out int vit)) Vitality = vit;
            if (data.TryGetValue("luck", out int lck)) Luck = lck;
            if (data.TryGetValue("agility", out int agi)) Agility = agi;
            if (data.TryGetValue("intelligence", out int intel)) Intelligence = intel;
        }
    }
}
