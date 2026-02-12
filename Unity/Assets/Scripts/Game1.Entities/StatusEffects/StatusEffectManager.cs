// Game1.Entities.StatusEffects.StatusEffectManager
// Migrated from: entities/status_manager.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Entities.StatusEffects
{
    /// <summary>
    /// Stacking behavior types for status effects.
    /// </summary>
    public enum StackingBehavior
    {
        None,      // New application replaces old (duration refreshes)
        Additive,  // Stacks add together (up to max_stacks)
        Refresh    // Duration refreshes, stacks don't add
    }

    /// <summary>
    /// Manages active status effects on an entity.
    /// Handles applying, updating, removing, stacking rules, and mutual exclusions.
    /// </summary>
    public class StatusEffectManager
    {
        private readonly IStatusTarget _entity;
        private readonly List<StatusEffect> _activeEffects = new();

        // Mutually exclusive status pairs (burn/freeze, stun/freeze)
        private static readonly (string, string)[] MutualExclusions =
        {
            ("burn", "freeze"),
            ("stun", "freeze"),
        };

        // Default stacking behaviors per status
        private static readonly Dictionary<string, StackingBehavior> StackingRules = new()
        {
            // DoT effects - stack additively
            { "burn", StackingBehavior.Additive },
            { "bleed", StackingBehavior.Additive },
            { "poison", StackingBehavior.Additive },
            { "poison_status", StackingBehavior.Additive },

            // CC effects - refresh duration, don't stack
            { "freeze", StackingBehavior.Refresh },
            { "stun", StackingBehavior.Refresh },
            { "root", StackingBehavior.Refresh },
            { "slow", StackingBehavior.Refresh },
            { "chill", StackingBehavior.Refresh },

            // Buffs
            { "regeneration", StackingBehavior.Additive },
            { "regen", StackingBehavior.Additive },
            { "shield", StackingBehavior.Additive },
            { "barrier", StackingBehavior.Additive },
            { "haste", StackingBehavior.Refresh },
            { "quicken", StackingBehavior.Refresh },

            // Debuffs - stack additively
            { "weaken", StackingBehavior.Additive },
            { "vulnerable", StackingBehavior.Additive },
        };

        public StatusEffectManager(IStatusTarget entity)
        {
            _entity = entity;
        }

        /// <summary>
        /// Apply a status effect. Returns true if applied, false if blocked.
        /// </summary>
        public bool ApplyStatus(string statusTag, Dictionary<string, object> parameters, object source = null)
        {
            // Check for existing effect of the same type
            var existing = FindEffect(statusTag);

            if (existing != null)
            {
                var behavior = StackingRules.GetValueOrDefault(statusTag, StackingBehavior.None);

                if (behavior == StackingBehavior.Additive)
                {
                    existing.AddStack(1);
                    existing.RefreshDuration();
                    return true;
                }
                else if (behavior == StackingBehavior.Refresh)
                {
                    existing.RefreshDuration();
                    return true;
                }
                else // None - replace
                {
                    RemoveEffect(existing);
                }
            }

            // Check mutual exclusions
            foreach (var (statusA, statusB) in MutualExclusions)
            {
                if (statusTag == statusA)
                {
                    var conflicting = FindEffect(statusB);
                    if (conflicting != null)
                        RemoveEffect(conflicting);
                }
                else if (statusTag == statusB)
                {
                    var conflicting = FindEffect(statusA);
                    if (conflicting != null)
                        RemoveEffect(conflicting);
                }
            }

            // Apply resistance to duration if entity has resistance method
            var modifiedParams = new Dictionary<string, object>(parameters);

            // Create new effect
            var effect = StatusEffectFactory.Create(statusTag, modifiedParams, source);
            if (effect == null)
                return false;

            effect.OnApply(_entity);
            _activeEffects.Add(effect);
            return true;
        }

        /// <summary>
        /// Remove a specific status effect by tag.
        /// </summary>
        public bool RemoveStatus(string statusTag)
        {
            var effect = FindEffect(statusTag);
            if (effect != null)
            {
                RemoveEffect(effect);
                return true;
            }
            return false;
        }

        /// <summary>
        /// Check if entity has a specific status effect.
        /// </summary>
        public bool HasStatus(string statusTag)
        {
            return FindEffect(statusTag) != null;
        }

        /// <summary>
        /// Get a specific status effect if active.
        /// </summary>
        public StatusEffect GetStatus(string statusTag)
        {
            return FindEffect(statusTag);
        }

        /// <summary>
        /// Update all active status effects. Remove expired ones.
        /// </summary>
        public void Update(float dt)
        {
            var expired = new List<StatusEffect>();

            foreach (var effect in _activeEffects)
            {
                if (!effect.Update(dt, _entity))
                    expired.Add(effect);
            }

            foreach (var effect in expired)
                RemoveEffect(effect);
        }

        /// <summary>
        /// Remove all status effects.
        /// </summary>
        public void ClearAll()
        {
            foreach (var effect in _activeEffects.ToList())
                RemoveEffect(effect);
        }

        /// <summary>
        /// Remove all negative status effects (cleanse).
        /// </summary>
        public void ClearDebuffs()
        {
            string[] debuffTags = { "burn", "bleed", "poison", "poison_status",
                "freeze", "stun", "root", "slow", "chill", "weaken", "vulnerable" };

            foreach (var effect in _activeEffects.ToList())
            {
                if (debuffTags.Contains(effect.StatusId))
                    RemoveEffect(effect);
            }
        }

        /// <summary>
        /// Get all active effects (for UI).
        /// </summary>
        public List<StatusEffect> GetAllActiveEffects()
        {
            return new List<StatusEffect>(_activeEffects);
        }

        /// <summary>
        /// Check if entity is under any crowd control.
        /// </summary>
        public bool IsCrowdControlled()
        {
            string[] ccTags = { "freeze", "stun", "root", "slow", "chill" };
            return ccTags.Any(tag => FindEffect(tag) != null);
        }

        /// <summary>
        /// Check if entity cannot move (hard CC).
        /// </summary>
        public bool IsImmobilized()
        {
            string[] immobilizeTags = { "freeze", "stun", "root" };
            return immobilizeTags.Any(tag => FindEffect(tag) != null);
        }

        /// <summary>
        /// Check if entity cannot use abilities.
        /// </summary>
        public bool IsSilenced()
        {
            string[] silenceTags = { "stun", "silence" };
            return silenceTags.Any(tag => FindEffect(tag) != null);
        }

        private StatusEffect FindEffect(string statusTag)
        {
            return _activeEffects.FirstOrDefault(e => e.StatusId == statusTag);
        }

        private void RemoveEffect(StatusEffect effect)
        {
            if (_activeEffects.Remove(effect))
                effect.OnRemove(_entity);
        }
    }
}
