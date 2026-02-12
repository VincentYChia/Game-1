// Game1.Entities.Components.BuffManager
// Migrated from: entities/components/buffs.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Entities.Components
{
    /// <summary>
    /// An active buff applied to the character.
    /// Buffs come from skills (empower, quicken, fortify, pierce, enrich, elevate, devastate, transcend, regenerate).
    /// </summary>
    [Serializable]
    public class ActiveBuff
    {
        public string BuffId { get; set; }
        public string Name { get; set; }
        public string EffectType { get; set; }    // empower, quicken, fortify, pierce, enrich, elevate, devastate, transcend, regenerate
        public string Category { get; set; }       // mining, forestry, combat, movement, defense, etc.
        public string Magnitude { get; set; }      // minor, moderate, major, extreme
        public float BonusValue { get; set; }      // The actual bonus value
        public float Duration { get; set; }        // Total duration in seconds
        public float DurationRemaining { get; set; }
        public bool ConsumeOnUse { get; set; }     // If true, consumed after first matching action

        public bool IsExpired => DurationRemaining <= 0;

        /// <summary>
        /// Update buff duration. Returns false if expired.
        /// </summary>
        public bool Update(float dt)
        {
            DurationRemaining -= dt;
            return DurationRemaining > 0;
        }
    }

    /// <summary>
    /// Manages active buffs on a character.
    /// Provides methods to add/remove/query buffs and get aggregate bonuses.
    /// </summary>
    public class BuffManager
    {
        public List<ActiveBuff> ActiveBuffs { get; private set; } = new();

        /// <summary>
        /// Add a buff. Replaces existing buff with same BuffId.
        /// </summary>
        public void AddBuff(ActiveBuff buff)
        {
            // Remove existing buff with same ID (refresh)
            ActiveBuffs.RemoveAll(b => b.BuffId == buff.BuffId);
            ActiveBuffs.Add(buff);
        }

        /// <summary>
        /// Remove a specific buff by ID.
        /// </summary>
        public bool RemoveBuff(string buffId)
        {
            return ActiveBuffs.RemoveAll(b => b.BuffId == buffId) > 0;
        }

        /// <summary>
        /// Update all buff durations and remove expired ones.
        /// </summary>
        public void Update(float dt)
        {
            ActiveBuffs.RemoveAll(b => !b.Update(dt));
        }

        /// <summary>
        /// Get total damage bonus for a specific activity category.
        /// Sums all "empower" buffs matching the category.
        /// </summary>
        public float GetDamageBonus(string category)
        {
            return ActiveBuffs
                .Where(b => b.EffectType == "empower" && MatchesCategory(b.Category, category))
                .Sum(b => b.BonusValue);
        }

        /// <summary>
        /// Get total movement speed bonus from "quicken" buffs with movement category.
        /// </summary>
        public float GetMovementSpeedBonus()
        {
            return ActiveBuffs
                .Where(b => b.EffectType == "quicken" && b.Category == "movement")
                .Sum(b => b.BonusValue);
        }

        /// <summary>
        /// Get total bonus of a specific effect type for a specific category.
        /// </summary>
        public float GetTotalBonus(string effectType, string category)
        {
            return ActiveBuffs
                .Where(b => b.EffectType == effectType && MatchesCategory(b.Category, category))
                .Sum(b => b.BonusValue);
        }

        /// <summary>
        /// Check if there's an active devastate buff for a category.
        /// Returns the radius value if found, 0 otherwise.
        /// </summary>
        public int GetDevastateRadius(string category)
        {
            var buff = ActiveBuffs.FirstOrDefault(
                b => b.EffectType == "devastate" && MatchesCategory(b.Category, category));
            return buff != null ? (int)buff.BonusValue : 0;
        }

        /// <summary>
        /// Consume buffs that match an action. Used for consume_on_use buffs.
        /// </summary>
        public void ConsumeBuffsForAction(string actionType, string category = null)
        {
            var toConsume = ActiveBuffs
                .Where(b => b.ConsumeOnUse && MatchesCategory(b.Category, category ?? actionType))
                .ToList();

            foreach (var buff in toConsume)
                ActiveBuffs.Remove(buff);
        }

        /// <summary>
        /// Get all active buff names (for UI display).
        /// </summary>
        public List<string> GetActiveBuffNames()
        {
            return ActiveBuffs.Select(b => b.Name).ToList();
        }

        /// <summary>
        /// Check if category matches (handles "damage" matching "combat", etc.).
        /// </summary>
        private static bool MatchesCategory(string buffCategory, string queryCategory)
        {
            if (string.IsNullOrEmpty(buffCategory) || string.IsNullOrEmpty(queryCategory))
                return true; // Null/empty = matches all

            if (buffCategory == queryCategory) return true;

            // Aliases
            if (buffCategory == "damage" && queryCategory == "combat") return true;
            if (buffCategory == "combat" && queryCategory == "damage") return true;

            return false;
        }

        /// <summary>
        /// Clear all buffs.
        /// </summary>
        public void ClearAll()
        {
            ActiveBuffs.Clear();
        }

        /// <summary>
        /// Serialize for saving.
        /// </summary>
        public List<Dictionary<string, object>> ToSaveData()
        {
            return ActiveBuffs.Select(b => new Dictionary<string, object>
            {
                { "buff_id", b.BuffId },
                { "name", b.Name },
                { "effect_type", b.EffectType },
                { "category", b.Category },
                { "magnitude", b.Magnitude },
                { "bonus_value", b.BonusValue },
                { "duration", b.Duration },
                { "duration_remaining", b.DurationRemaining },
                { "consume_on_use", b.ConsumeOnUse }
            }).ToList();
        }

        /// <summary>
        /// Restore from save data.
        /// </summary>
        public void RestoreFromSaveData(List<Dictionary<string, object>> data)
        {
            ActiveBuffs.Clear();
            if (data == null) return;

            foreach (var buffData in data)
            {
                var buff = new ActiveBuff
                {
                    BuffId = buffData.GetValueOrDefault("buff_id")?.ToString() ?? "",
                    Name = buffData.GetValueOrDefault("name")?.ToString() ?? "",
                    EffectType = buffData.GetValueOrDefault("effect_type")?.ToString() ?? "",
                    Category = buffData.GetValueOrDefault("category")?.ToString() ?? "",
                    Magnitude = buffData.GetValueOrDefault("magnitude")?.ToString() ?? "",
                    BonusValue = Convert.ToSingle(buffData.GetValueOrDefault("bonus_value", 0f)),
                    Duration = Convert.ToSingle(buffData.GetValueOrDefault("duration", 0f)),
                    DurationRemaining = Convert.ToSingle(buffData.GetValueOrDefault("duration_remaining", 0f)),
                    ConsumeOnUse = Convert.ToBoolean(buffData.GetValueOrDefault("consume_on_use", false))
                };
                ActiveBuffs.Add(buff);
            }
        }
    }
}
