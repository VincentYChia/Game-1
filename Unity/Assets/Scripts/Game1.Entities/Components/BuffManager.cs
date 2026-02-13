// ============================================================================
// Game1.Entities.Components.BuffManager
// Migrated from: entities/components/buffs.py (lines 1-157)
// Migration phase: 3
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Core;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Represents an active buff on the character.
    /// Buffs are temporary enhancements from skills, potions, equipment, etc.
    /// </summary>
    public class ActiveBuff
    {
        public string BuffId { get; set; }
        public string Name { get; set; }
        public string EffectType { get; set; }  // empower, quicken, fortify, etc.
        public string Category { get; set; }    // mining, combat, smithing, movement, etc.
        public string Magnitude { get; set; }   // minor, moderate, major, extreme
        public float BonusValue { get; set; }
        public float Duration { get; set; }             // Original duration (for UI)
        public float DurationRemaining { get; set; }
        public string Source { get; set; } = "skill";
        public bool ConsumeOnUse { get; set; }

        /// <summary>Update timer. Returns true if buff is still active.</summary>
        public bool Update(float dt)
        {
            DurationRemaining -= dt;
            return DurationRemaining > 0;
        }

        /// <summary>Get progress percentage (0.0-1.0) for UI display.</summary>
        public float GetProgressPercent()
        {
            if (Duration <= 0) return 0f;
            return MathF.Max(0f, MathF.Min(1f, DurationRemaining / Duration));
        }
    }

    /// <summary>
    /// Manages active buffs on a character.
    /// </summary>
    public class BuffManager
    {
        private readonly List<ActiveBuff> _activeBuffs = new();

        /// <summary>Add a new buff (stacks with existing).</summary>
        public void AddBuff(ActiveBuff buff)
        {
            if (buff == null) return;
            _activeBuffs.Add(buff);
            GameEvents.RaiseBuffChanged(buff.EffectType, true);
        }

        /// <summary>
        /// Remove a specific buff by ID.
        /// </summary>
        public bool RemoveBuff(string buffId)
        {
            var buff = _activeBuffs.Find(b => b.BuffId == buffId);
            if (buff == null) return false;
            _activeBuffs.Remove(buff);
            GameEvents.RaiseBuffChanged(buff.EffectType, false);
            return true;
        }

        /// <summary>
        /// Update all buffs and remove expired ones.
        /// </summary>
        public void Update(float dt)
        {
            for (int i = _activeBuffs.Count - 1; i >= 0; i--)
            {
                if (!_activeBuffs[i].Update(dt))
                {
                    var expired = _activeBuffs[i];
                    _activeBuffs.RemoveAt(i);
                    GameEvents.RaiseBuffChanged(expired.EffectType, false);
                }
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get total bonus from all matching buffs.</summary>
        public float GetTotalBonus(string effectType, string category)
        {
            float total = 0f;
            foreach (var buff in _activeBuffs)
            {
                if (buff.EffectType == effectType && buff.Category == category)
                    total += buff.BonusValue;
            }
            return total;
        }

        /// <summary>Get damage bonus for a category (mining, combat, etc.).</summary>
        public float GetDamageBonus(string category)
        {
            return GetTotalBonus("empower", category);
        }

        /// <summary>Get defense bonus.</summary>
        public float GetDefenseBonus()
        {
            return GetTotalBonus("fortify", "defense");
        }

        /// <summary>Get movement speed bonus.</summary>
        public float GetMovementSpeedBonus()
        {
            return GetTotalBonus("quicken", "movement");
        }

        /// <summary>Get all currently active buffs (read-only).</summary>
        public IReadOnlyList<ActiveBuff> GetActiveBuffs() => _activeBuffs.AsReadOnly();

        /// <summary>Get active buff count.</summary>
        public int ActiveBuffCount => _activeBuffs.Count;

        /// <summary>
        /// Consume buffs that are marked consume_on_use for a given action type.
        /// </summary>
        public void ConsumeBuffsForAction(string actionType, string category = null)
        {
            var toRemove = new List<ActiveBuff>();

            foreach (var buff in _activeBuffs)
            {
                if (!buff.ConsumeOnUse) continue;

                bool shouldConsume = actionType switch
                {
                    "attack" => buff.Category == "combat" || buff.Category == "damage",
                    "gather" => category != null
                        ? buff.Category == category
                        : buff.Category is "mining" or "forestry" or "fishing" or "gathering",
                    "craft" => category != null
                        ? buff.Category == category
                        : buff.Category is "smithing" or "alchemy" or "engineering"
                          or "refining" or "enchanting",
                    _ => false,
                };

                if (shouldConsume)
                    toRemove.Add(buff);
            }

            foreach (var buff in toRemove)
            {
                _activeBuffs.Remove(buff);
                GameEvents.RaiseBuffChanged(buff.EffectType, false);
            }
        }
    }
}
