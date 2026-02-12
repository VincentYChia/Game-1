// Game1.Entities.StatusEffects.StatusEffect
// Migrated from: entities/status_effect.py
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;

namespace Game1.Entities.StatusEffects
{
    /// <summary>
    /// Interface for entities that can receive status effects.
    /// Both Character and Enemy implement this.
    /// </summary>
    public interface IStatusTarget
    {
        string Name { get; }
        float CurrentHealth { get; set; }
        float MaxHealth { get; }
        bool IsAlive { get; }
        float DamageMultiplier { get; set; }
        float DamageTakenMultiplier { get; set; }
        float ShieldHealth { get; set; }
        bool IsFrozen { get; set; }
        bool IsStunned { get; set; }
        bool IsRooted { get; set; }
        HashSet<string> VisualEffects { get; }
    }

    /// <summary>
    /// Base class for all status effects.
    /// Status effects have duration, stacking, tick behavior, and on_apply/on_remove hooks.
    /// </summary>
    public abstract class StatusEffect
    {
        public string StatusId { get; protected set; }
        public string DisplayName { get; protected set; }
        public float Duration { get; protected set; }
        public float TimeRemaining { get; protected set; }
        public int Stacks { get; protected set; } = 1;
        public int MaxStacks { get; protected set; } = 5;
        public float TickInterval { get; protected set; } = 1.0f;
        public Dictionary<string, object> Params { get; protected set; }
        public object Source { get; protected set; }

        private float _tickTimer;

        protected StatusEffect(string statusId, string displayName, Dictionary<string, object> parameters, object source)
        {
            StatusId = statusId;
            DisplayName = displayName;
            Params = parameters ?? new Dictionary<string, object>();
            Source = source;

            Duration = GetFloatParam("duration", 5.0f);
            TimeRemaining = Duration;
            _tickTimer = 0f;
        }

        /// <summary>
        /// Called when effect is first applied.
        /// </summary>
        public virtual void OnApply(IStatusTarget target)
        {
            target.VisualEffects.Add(StatusId);
        }

        /// <summary>
        /// Called when effect is removed (expired or dispelled).
        /// </summary>
        public virtual void OnRemove(IStatusTarget target)
        {
            target.VisualEffects.Remove(StatusId);
        }

        /// <summary>
        /// Called every tick interval. Override for DoT/HoT effects.
        /// </summary>
        protected virtual void OnTick(IStatusTarget target) { }

        /// <summary>
        /// Update the effect. Returns false if expired.
        /// </summary>
        public bool Update(float dt, IStatusTarget target)
        {
            TimeRemaining -= dt;

            // Tick-based updates
            _tickTimer += dt;
            if (_tickTimer >= TickInterval)
            {
                _tickTimer -= TickInterval;
                OnTick(target);
            }

            return TimeRemaining > 0;
        }

        /// <summary>
        /// Add stacks (up to max).
        /// </summary>
        public void AddStack(int count = 1)
        {
            Stacks = Math.Min(Stacks + count, MaxStacks);
        }

        /// <summary>
        /// Refresh duration to original value.
        /// </summary>
        public void RefreshDuration()
        {
            TimeRemaining = Duration;
        }

        // Helper methods for reading params
        protected float GetFloatParam(string key, float defaultValue = 0f)
        {
            if (Params.TryGetValue(key, out var val))
            {
                try { return Convert.ToSingle(val); }
                catch { return defaultValue; }
            }
            // Also check with status_id prefix (e.g., "burn_duration")
            string prefixedKey = $"{StatusId}_{key}";
            if (Params.TryGetValue(prefixedKey, out val))
            {
                try { return Convert.ToSingle(val); }
                catch { return defaultValue; }
            }
            return defaultValue;
        }

        protected int GetIntParam(string key, int defaultValue = 0)
        {
            if (Params.TryGetValue(key, out var val))
            {
                try { return Convert.ToInt32(val); }
                catch { return defaultValue; }
            }
            return defaultValue;
        }

        protected string GetStringParam(string key, string defaultValue = "")
        {
            if (Params.TryGetValue(key, out var val))
                return val?.ToString() ?? defaultValue;
            return defaultValue;
        }
    }

    // ========================================================================
    // DoT EFFECTS (Damage over Time)
    // ========================================================================

    public class BurnEffect : StatusEffect
    {
        private float _damagePerSecond;

        public BurnEffect(Dictionary<string, object> parameters, object source)
            : base("burn", "Burn", parameters, source)
        {
            _damagePerSecond = GetFloatParam("burn_damage_per_second",
                GetFloatParam("damage_per_second", 8.0f));
            TickInterval = 1.0f;
        }

        public override void OnApply(IStatusTarget target)
        {
            base.OnApply(target);
        }

        protected override void OnTick(IStatusTarget target)
        {
            float damage = _damagePerSecond * Stacks;
            target.CurrentHealth -= damage;
        }
    }

    public class BleedEffect : StatusEffect
    {
        private float _damagePerSecond;

        public BleedEffect(Dictionary<string, object> parameters, object source)
            : base("bleed", "Bleed", parameters, source)
        {
            _damagePerSecond = GetFloatParam("bleed_damage_per_second",
                GetFloatParam("damage_per_second", 5.0f));
            TickInterval = 1.0f;
        }

        protected override void OnTick(IStatusTarget target)
        {
            float damage = _damagePerSecond * Stacks;
            target.CurrentHealth -= damage;
        }
    }

    public class PoisonEffect : StatusEffect
    {
        private float _damagePerSecond;

        public PoisonEffect(Dictionary<string, object> parameters, object source)
            : base("poison", "Poison", parameters, source)
        {
            _damagePerSecond = GetFloatParam("poison_damage_per_second",
                GetFloatParam("damage_per_second", 4.0f));
            TickInterval = 1.0f;
        }

        protected override void OnTick(IStatusTarget target)
        {
            float damage = _damagePerSecond * Stacks;
            target.CurrentHealth -= damage;
        }
    }

    public class PoisonStatusEffect : StatusEffect
    {
        private float _damagePerSecond;

        public PoisonStatusEffect(Dictionary<string, object> parameters, object source)
            : base("poison_status", "Poison", parameters, source)
        {
            _damagePerSecond = GetFloatParam("damage_per_second", 4.0f);
            TickInterval = 1.0f;
        }

        protected override void OnTick(IStatusTarget target)
        {
            float damage = _damagePerSecond * Stacks;
            target.CurrentHealth -= damage;
        }
    }

    public class ShockEffect : StatusEffect
    {
        private float _damagePerSecond;

        public ShockEffect(Dictionary<string, object> parameters, object source)
            : base("shock", "Shock", parameters, source)
        {
            _damagePerSecond = GetFloatParam("shock_damage_per_second",
                GetFloatParam("damage_per_second", 6.0f));
            TickInterval = 1.0f;
        }

        protected override void OnTick(IStatusTarget target)
        {
            float damage = _damagePerSecond * Stacks;
            target.CurrentHealth -= damage;
        }
    }

    // ========================================================================
    // CC EFFECTS (Crowd Control)
    // ========================================================================

    public class FreezeEffect : StatusEffect
    {
        public FreezeEffect(Dictionary<string, object> parameters, object source)
            : base("freeze", "Frozen", parameters, source)
        {
            Duration = GetFloatParam("freeze_duration", GetFloatParam("duration", 3.0f));
            TimeRemaining = Duration;
        }

        public override void OnApply(IStatusTarget target)
        {
            base.OnApply(target);
            target.IsFrozen = true;
        }

        public override void OnRemove(IStatusTarget target)
        {
            base.OnRemove(target);
            target.IsFrozen = false;
        }
    }

    public class StunEffect : StatusEffect
    {
        public StunEffect(Dictionary<string, object> parameters, object source)
            : base("stun", "Stunned", parameters, source)
        {
            Duration = GetFloatParam("stun_duration", GetFloatParam("duration", 2.0f));
            TimeRemaining = Duration;
        }

        public override void OnApply(IStatusTarget target)
        {
            base.OnApply(target);
            target.IsStunned = true;
        }

        public override void OnRemove(IStatusTarget target)
        {
            base.OnRemove(target);
            target.IsStunned = false;
        }
    }

    public class RootEffect : StatusEffect
    {
        public RootEffect(Dictionary<string, object> parameters, object source)
            : base("root", "Rooted", parameters, source)
        {
            Duration = GetFloatParam("root_duration", GetFloatParam("duration", 3.0f));
            TimeRemaining = Duration;
        }

        public override void OnApply(IStatusTarget target)
        {
            base.OnApply(target);
            target.IsRooted = true;
        }

        public override void OnRemove(IStatusTarget target)
        {
            base.OnRemove(target);
            target.IsRooted = false;
        }
    }

    public class SlowEffect : StatusEffect
    {
        public SlowEffect(Dictionary<string, object> parameters, object source)
            : base("slow", "Slowed", parameters, source)
        {
            Duration = GetFloatParam("slow_duration", GetFloatParam("duration", 5.0f));
            TimeRemaining = Duration;
        }

        public override void OnApply(IStatusTarget target) => base.OnApply(target);
        public override void OnRemove(IStatusTarget target) => base.OnRemove(target);
    }

    public class ChillEffect : StatusEffect
    {
        public ChillEffect(Dictionary<string, object> parameters, object source)
            : base("chill", "Chilled", parameters, source)
        {
            Duration = GetFloatParam("chill_duration", GetFloatParam("duration", 5.0f));
            TimeRemaining = Duration;
        }

        public override void OnApply(IStatusTarget target) => base.OnApply(target);
        public override void OnRemove(IStatusTarget target) => base.OnRemove(target);
    }

    // ========================================================================
    // BUFF EFFECTS
    // ========================================================================

    public class RegenerationEffect : StatusEffect
    {
        private float _healPerSecond;

        public RegenerationEffect(Dictionary<string, object> parameters, object source)
            : base("regeneration", "Regeneration", parameters, source)
        {
            _healPerSecond = GetFloatParam("heal_per_second",
                GetFloatParam("regen_amount", 5.0f));
            TickInterval = 1.0f;
        }

        protected override void OnTick(IStatusTarget target)
        {
            float heal = _healPerSecond * Stacks;
            target.CurrentHealth = Math.Min(target.MaxHealth, target.CurrentHealth + heal);
        }
    }

    public class RegenEffect : StatusEffect
    {
        private float _healPerSecond;

        public RegenEffect(Dictionary<string, object> parameters, object source)
            : base("regen", "Regen", parameters, source)
        {
            _healPerSecond = GetFloatParam("heal_per_second", 5.0f);
            TickInterval = 1.0f;
        }

        protected override void OnTick(IStatusTarget target)
        {
            float heal = _healPerSecond * Stacks;
            target.CurrentHealth = Math.Min(target.MaxHealth, target.CurrentHealth + heal);
        }
    }

    public class ShieldEffect : StatusEffect
    {
        private float _shieldAmount;

        public ShieldEffect(Dictionary<string, object> parameters, object source)
            : base("shield", "Shield", parameters, source)
        {
            _shieldAmount = GetFloatParam("shield_amount", 50.0f);
        }

        public override void OnApply(IStatusTarget target)
        {
            base.OnApply(target);
            target.ShieldHealth += _shieldAmount * Stacks;
        }

        public override void OnRemove(IStatusTarget target)
        {
            base.OnRemove(target);
            // Don't remove shield health on expire — it was already consumed or decayed
        }
    }

    public class BarrierEffect : StatusEffect
    {
        private float _barrierAmount;

        public BarrierEffect(Dictionary<string, object> parameters, object source)
            : base("barrier", "Barrier", parameters, source)
        {
            _barrierAmount = GetFloatParam("barrier_amount", 50.0f);
        }

        public override void OnApply(IStatusTarget target)
        {
            base.OnApply(target);
            target.ShieldHealth += _barrierAmount * Stacks;
        }

        public override void OnRemove(IStatusTarget target) => base.OnRemove(target);
    }

    public class HasteEffect : StatusEffect
    {
        public HasteEffect(Dictionary<string, object> parameters, object source)
            : base("haste", "Haste", parameters, source) { }

        public override void OnApply(IStatusTarget target) => base.OnApply(target);
        public override void OnRemove(IStatusTarget target) => base.OnRemove(target);
    }

    public class QuickenEffect : StatusEffect
    {
        public QuickenEffect(Dictionary<string, object> parameters, object source)
            : base("quicken", "Quickened", parameters, source) { }

        public override void OnApply(IStatusTarget target) => base.OnApply(target);
        public override void OnRemove(IStatusTarget target) => base.OnRemove(target);
    }

    // ========================================================================
    // DEBUFF EFFECTS
    // ========================================================================

    public class WeakenEffect : StatusEffect
    {
        private float _damageReduction;

        public WeakenEffect(Dictionary<string, object> parameters, object source)
            : base("weaken", "Weakened", parameters, source)
        {
            _damageReduction = GetFloatParam("damage_reduction", 0.25f);
        }

        public override void OnApply(IStatusTarget target)
        {
            base.OnApply(target);
            target.DamageMultiplier *= (1.0f - _damageReduction * Stacks);
        }

        public override void OnRemove(IStatusTarget target)
        {
            base.OnRemove(target);
            target.DamageMultiplier /= (1.0f - _damageReduction * Stacks);
        }
    }

    public class VulnerableEffect : StatusEffect
    {
        private float _damageTakenIncrease;

        public VulnerableEffect(Dictionary<string, object> parameters, object source)
            : base("vulnerable", "Vulnerable", parameters, source)
        {
            _damageTakenIncrease = GetFloatParam("damage_taken_increase", 0.25f);
        }

        public override void OnApply(IStatusTarget target)
        {
            base.OnApply(target);
            target.DamageTakenMultiplier *= (1.0f + _damageTakenIncrease * Stacks);
        }

        public override void OnRemove(IStatusTarget target)
        {
            base.OnRemove(target);
            target.DamageTakenMultiplier /= (1.0f + _damageTakenIncrease * Stacks);
        }
    }

    // ========================================================================
    // FACTORY
    // ========================================================================

    /// <summary>
    /// Factory for creating status effects from tag strings.
    /// Matches Python create_status_effect() function.
    /// </summary>
    public static class StatusEffectFactory
    {
        public static StatusEffect Create(string statusTag, Dictionary<string, object> parameters, object source = null)
        {
            return statusTag.ToLower() switch
            {
                "burn"          => new BurnEffect(parameters, source),
                "bleed"         => new BleedEffect(parameters, source),
                "poison"        => new PoisonEffect(parameters, source),
                "poison_status" => new PoisonStatusEffect(parameters, source),
                "shock"         => new ShockEffect(parameters, source),
                "freeze"        => new FreezeEffect(parameters, source),
                "stun"          => new StunEffect(parameters, source),
                "root"          => new RootEffect(parameters, source),
                "slow"          => new SlowEffect(parameters, source),
                "chill"         => new ChillEffect(parameters, source),
                "regeneration"  => new RegenerationEffect(parameters, source),
                "regen"         => new RegenEffect(parameters, source),
                "shield"        => new ShieldEffect(parameters, source),
                "barrier"       => new BarrierEffect(parameters, source),
                "haste"         => new HasteEffect(parameters, source),
                "quicken"       => new QuickenEffect(parameters, source),
                "weaken"        => new WeakenEffect(parameters, source),
                "vulnerable"    => new VulnerableEffect(parameters, source),
                _               => null
            };
        }
    }
}
