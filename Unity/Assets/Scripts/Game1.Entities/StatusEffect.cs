// ============================================================================
// Game1.Entities.StatusEffect
// Migrated from: entities/status_effect.py, entities/status_manager.py
// Migration phase: 3
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Data.Enums;

namespace Game1.Entities
{
    /// <summary>
    /// Stacking behavior for status effects.
    /// </summary>
    public enum StackingBehavior
    {
        /// <summary>New application replaces old (duration refreshes).</summary>
        None,
        /// <summary>Stacks add together (up to max_stacks).</summary>
        Additive,
        /// <summary>Duration refreshes, stacks don't increase.</summary>
        Refresh,
    }

    /// <summary>
    /// Abstract base for all status effects.
    /// Each status type (Burn, Freeze, etc.) derives from this.
    /// </summary>
    public class StatusEffect
    {
        public StatusEffectType Type { get; }
        public string Tag { get; }
        public float Duration { get; private set; }
        public float DurationRemaining { get; private set; }
        public float Intensity { get; set; }
        public int Stacks { get; private set; } = 1;
        public int MaxStacks { get; set; } = 5;
        public object Source { get; set; }

        /// <summary>Per-tick damage (for DoT effects).</summary>
        public float DamagePerSecond { get; set; }

        /// <summary>Movement speed reduction factor (for slows, 0.0-1.0).</summary>
        public float SpeedReduction { get; set; }

        /// <summary>Whether the target can act (false for stun/freeze).</summary>
        public bool PreventsAction { get; set; }

        /// <summary>Whether the target can move (false for root/stun/freeze).</summary>
        public bool PreventsMovement { get; set; }

        public StatusEffect(StatusEffectType type, float duration, float intensity = 1.0f)
        {
            Type = type;
            Tag = type.ToJsonString();
            Duration = duration;
            DurationRemaining = duration;
            Intensity = intensity;

            // Set default behaviors per type
            switch (type)
            {
                case StatusEffectType.Burn:
                    DamagePerSecond = intensity;
                    break;
                case StatusEffectType.Bleed:
                    DamagePerSecond = intensity;
                    break;
                case StatusEffectType.Poison:
                    DamagePerSecond = intensity;
                    break;
                case StatusEffectType.Shock:
                    DamagePerSecond = intensity;
                    break;
                case StatusEffectType.Freeze:
                    PreventsAction = true;
                    PreventsMovement = true;
                    break;
                case StatusEffectType.Stun:
                    PreventsAction = true;
                    PreventsMovement = true;
                    break;
                case StatusEffectType.Root:
                    PreventsMovement = true;
                    break;
                case StatusEffectType.Slow:
                    SpeedReduction = MathF.Min(0.8f, intensity * 0.2f);
                    break;
            }
        }

        /// <summary>
        /// Tick the effect. Returns damage dealt this tick (for DoTs).
        /// </summary>
        public float Tick(float deltaTime)
        {
            DurationRemaining -= deltaTime;
            return DamagePerSecond * Stacks * deltaTime;
        }

        /// <summary>Is this effect still active?</summary>
        public bool IsActive => DurationRemaining > 0;

        /// <summary>Add stacks (for additive stacking).</summary>
        public void AddStack(int count = 1)
        {
            Stacks = Math.Min(Stacks + count, MaxStacks);
        }

        /// <summary>Refresh duration back to full.</summary>
        public void RefreshDuration()
        {
            DurationRemaining = Duration;
        }
    }

    /// <summary>
    /// Manages active status effects on an entity.
    /// Handles application, stacking, mutual exclusions, and removal.
    /// </summary>
    public class StatusEffectManager
    {
        private readonly List<StatusEffect> _activeEffects = new();

        /// <summary>Mutually exclusive status pairs (e.g., burn cancels freeze).</summary>
        private static readonly (StatusEffectType A, StatusEffectType B)[] MutualExclusions =
        {
            (StatusEffectType.Burn, StatusEffectType.Freeze),
            (StatusEffectType.Stun, StatusEffectType.Freeze),
        };

        /// <summary>Default stacking behaviors per type.</summary>
        private static readonly Dictionary<StatusEffectType, StackingBehavior> StackingRules = new()
        {
            // DoTs stack additively
            [StatusEffectType.Burn] = StackingBehavior.Additive,
            [StatusEffectType.Bleed] = StackingBehavior.Additive,
            [StatusEffectType.Poison] = StackingBehavior.Additive,
            [StatusEffectType.Shock] = StackingBehavior.Additive,

            // CC refreshes duration
            [StatusEffectType.Freeze] = StackingBehavior.Refresh,
            [StatusEffectType.Stun] = StackingBehavior.Refresh,
            [StatusEffectType.Root] = StackingBehavior.Refresh,
            [StatusEffectType.Slow] = StackingBehavior.Refresh,

            // Buffs
            [StatusEffectType.Regeneration] = StackingBehavior.Additive,
            [StatusEffectType.Shield] = StackingBehavior.Additive,
            [StatusEffectType.Haste] = StackingBehavior.Refresh,

            // Debuffs
            [StatusEffectType.Weaken] = StackingBehavior.Additive,
            [StatusEffectType.Vulnerable] = StackingBehavior.Additive,
        };

        // ====================================================================
        // Apply
        // ====================================================================

        /// <summary>
        /// Apply a status effect. Handles stacking and mutual exclusions.
        /// Returns true if the status was applied.
        /// </summary>
        public bool ApplyStatus(StatusEffectType type, float duration, float intensity = 1.0f,
                               object source = null)
        {
            // Check for existing effect
            var existing = _findEffect(type);
            if (existing != null)
            {
                var stacking = StackingRules.GetValueOrDefault(type, StackingBehavior.None);
                switch (stacking)
                {
                    case StackingBehavior.Additive:
                        existing.AddStack(1);
                        existing.RefreshDuration();
                        return true;
                    case StackingBehavior.Refresh:
                        existing.RefreshDuration();
                        return true;
                    case StackingBehavior.None:
                        _removeEffect(existing);
                        break;
                }
            }

            // Handle mutual exclusions
            foreach (var (a, b) in MutualExclusions)
            {
                if (type == a)
                {
                    var conflict = _findEffect(b);
                    if (conflict != null) _removeEffect(conflict);
                }
                else if (type == b)
                {
                    var conflict = _findEffect(a);
                    if (conflict != null) _removeEffect(conflict);
                }
            }

            // Create and apply new effect
            var effect = new StatusEffect(type, duration, intensity)
            {
                Source = source
            };
            _activeEffects.Add(effect);
            return true;
        }

        /// <summary>
        /// Apply a status by tag string (for JSON-driven effects).
        /// </summary>
        public bool ApplyStatusFromTag(string tag, float duration, float intensity = 1.0f,
                                       object source = null)
        {
            var type = StatusEffectTypeExtensions.FromJsonString(tag);
            return ApplyStatus(type, duration, intensity, source);
        }

        // ====================================================================
        // Tick / Update
        // ====================================================================

        /// <summary>
        /// Update all effects. Returns total DoT damage dealt this tick.
        /// Removes expired effects.
        /// </summary>
        public float TickAll(float deltaTime)
        {
            float totalDamage = 0f;

            for (int i = _activeEffects.Count - 1; i >= 0; i--)
            {
                var effect = _activeEffects[i];
                totalDamage += effect.Tick(deltaTime);

                if (!effect.IsActive)
                {
                    _activeEffects.RemoveAt(i);
                }
            }

            return totalDamage;
        }

        // ====================================================================
        // Remove
        // ====================================================================

        /// <summary>Remove all effects of a given type.</summary>
        public void RemoveStatus(StatusEffectType type)
        {
            _activeEffects.RemoveAll(e => e.Type == type);
        }

        /// <summary>Remove all active effects.</summary>
        public void ClearAll()
        {
            _activeEffects.Clear();
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Check if a specific status type is active.</summary>
        public bool HasStatus(StatusEffectType type)
        {
            return _activeEffects.Any(e => e.Type == type && e.IsActive);
        }

        /// <summary>Check if the entity is stunned (cannot act).</summary>
        public bool IsStunned => _activeEffects.Any(e => e.PreventsAction && e.IsActive);

        /// <summary>Check if the entity is rooted (cannot move).</summary>
        public bool IsRooted => _activeEffects.Any(e => e.PreventsMovement && e.IsActive);

        /// <summary>Get the total speed reduction (0.0-1.0) from slow effects.</summary>
        public float GetSpeedReduction()
        {
            float total = 0f;
            foreach (var e in _activeEffects)
            {
                if (e.IsActive && e.SpeedReduction > 0)
                    total += e.SpeedReduction;
            }
            return MathF.Min(0.9f, total); // Cap at 90% reduction
        }

        /// <summary>Get all currently active effects (read-only).</summary>
        public IReadOnlyList<StatusEffect> ActiveEffects => _activeEffects.AsReadOnly();

        // ====================================================================
        // Private Helpers
        // ====================================================================

        private StatusEffect _findEffect(StatusEffectType type)
        {
            return _activeEffects.Find(e => e.Type == type && e.IsActive);
        }

        private void _removeEffect(StatusEffect effect)
        {
            _activeEffects.Remove(effect);
        }
    }
}
