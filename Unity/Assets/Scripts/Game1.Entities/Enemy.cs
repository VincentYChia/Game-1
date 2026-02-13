// ============================================================================
// Game1.Entities.Enemy
// Migrated from: Combat/enemy.py (lines 1-120)
// Migration phase: 3 (MACRO-6: GamePosition)
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using Game1.Core;
using Game1.Data.Models;

namespace Game1.Entities
{
    /// <summary>
    /// Enemy AI states.
    /// </summary>
    public enum AIState
    {
        Idle,
        Wander,
        Patrol,
        Guard,
        Chase,
        Attack,
        Flee,
        Dead,
        Corpse
    }

    /// <summary>
    /// Loot drop definition for an enemy.
    /// </summary>
    public class DropDefinition
    {
        [JsonProperty("materialId")]
        public string MaterialId { get; set; }

        [JsonProperty("quantityMin")]
        public int QuantityMin { get; set; } = 1;

        [JsonProperty("quantityMax")]
        public int QuantityMax { get; set; } = 1;

        [JsonProperty("chance")]
        public float Chance { get; set; } = 1.0f;
    }

    /// <summary>
    /// Special ability definition for enemies.
    /// </summary>
    public class SpecialAbility
    {
        [JsonProperty("abilityId")]
        public string AbilityId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("cooldown")]
        public float Cooldown { get; set; }

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("params")]
        public Dictionary<string, object> Params { get; set; } = new();

        [JsonProperty("healthThreshold")]
        public float HealthThreshold { get; set; } = 1.0f;

        [JsonProperty("distanceMin")]
        public float DistanceMin { get; set; }

        [JsonProperty("distanceMax")]
        public float DistanceMax { get; set; } = 999f;

        [JsonProperty("priority")]
        public int Priority { get; set; }
    }

    /// <summary>
    /// Enemy definition loaded from JSON.
    /// </summary>
    public class EnemyDefinition
    {
        [JsonProperty("enemyId")]
        public string EnemyId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("category")]
        public string Category { get; set; }

        [JsonProperty("behavior")]
        public string Behavior { get; set; }

        [JsonProperty("maxHealth")]
        public float MaxHealth { get; set; }

        [JsonProperty("damageMin")]
        public float DamageMin { get; set; }

        [JsonProperty("damageMax")]
        public float DamageMax { get; set; }

        [JsonProperty("defense")]
        public float Defense { get; set; }

        [JsonProperty("speed")]
        public float Speed { get; set; }

        [JsonProperty("aggroRange")]
        public float AggroRange { get; set; }

        [JsonProperty("attackSpeed")]
        public float AttackSpeed { get; set; } = 1.0f;

        [JsonProperty("drops")]
        public List<DropDefinition> Drops { get; set; } = new();

        [JsonProperty("specialAbilities")]
        public List<SpecialAbility> SpecialAbilities { get; set; } = new();

        [JsonProperty("narrative")]
        public string Narrative { get; set; } = "";

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }
    }

    /// <summary>
    /// Live enemy instance in the game world.
    /// Uses GamePosition (MACRO-6) for all spatial operations.
    /// </summary>
    public class Enemy
    {
        private static readonly Random _rng = new();

        // Definition
        public EnemyDefinition Definition { get; }
        public string EnemyId => Definition.EnemyId;
        public string Name => Definition.Name;
        public int Tier => Definition.Tier;

        // State
        public float CurrentHealth { get; set; }
        public float MaxHealth { get; }
        public GamePosition Position { get; set; }
        public AIState State { get; set; } = AIState.Idle;
        public float AttackCooldown { get; set; }
        public float RespawnTimer { get; set; }

        // Target
        public GamePosition? TargetPosition { get; set; }
        public float AggroRange => Definition.AggroRange;

        /// <summary>
        /// Create a live enemy from a definition at a position.
        /// Health is multiplied by GameConfig.EnemyHealthMultiplier (0.1).
        /// </summary>
        public Enemy(EnemyDefinition definition, GamePosition position)
        {
            Definition = definition ?? throw new ArgumentNullException(nameof(definition));
            Position = position;

            // Apply enemy health multiplier (Python: health * 0.1)
            MaxHealth = definition.MaxHealth * GameConfig.EnemyHealthMultiplier;
            CurrentHealth = MaxHealth;
        }

        // ====================================================================
        // Combat
        // ====================================================================

        /// <summary>
        /// Take damage. Returns actual damage dealt.
        /// </summary>
        public float TakeDamage(float amount)
        {
            float defense = Definition.Defense;
            float reduction = MathF.Min(defense * GameConfig.DefReductionPerPoint,
                                        GameConfig.MaxDefenseReduction);
            float actual = amount * (1f - reduction);
            actual = MathF.Max(1f, actual); // Minimum 1 damage

            CurrentHealth -= actual;
            if (CurrentHealth <= 0)
            {
                CurrentHealth = 0;
                State = AIState.Dead;
                GameEvents.RaiseEnemyKilled(this);
            }

            return actual;
        }

        /// <summary>
        /// Get random damage from this enemy's range.
        /// </summary>
        public float GetDamage()
        {
            float min = Definition.DamageMin;
            float max = Definition.DamageMax;
            return min + (float)_rng.NextDouble() * (max - min);
        }

        /// <summary>Is this enemy alive?</summary>
        public bool IsAlive => CurrentHealth > 0 && State != AIState.Dead && State != AIState.Corpse;

        /// <summary>Health as fraction (0.0-1.0).</summary>
        public float HealthPercent => MaxHealth > 0 ? CurrentHealth / MaxHealth : 0f;

        // ====================================================================
        // AI Update
        // ====================================================================

        /// <summary>
        /// Update enemy AI and cooldowns.
        /// </summary>
        public void Update(float deltaTime, GamePosition playerPosition)
        {
            if (!IsAlive) return;

            // Update attack cooldown
            if (AttackCooldown > 0)
                AttackCooldown -= deltaTime;

            float distToPlayer = Position.HorizontalDistanceTo(playerPosition);

            switch (State)
            {
                case AIState.Idle:
                case AIState.Wander:
                case AIState.Patrol:
                case AIState.Guard:
                    // Check aggro range
                    if (distToPlayer <= AggroRange)
                    {
                        State = AIState.Chase;
                        TargetPosition = playerPosition;
                    }
                    break;

                case AIState.Chase:
                    TargetPosition = playerPosition;
                    if (distToPlayer > AggroRange * 2.0f)
                    {
                        // Lost target
                        State = AIState.Idle;
                        TargetPosition = null;
                    }
                    else if (distToPlayer <= GameConfig.MeleeRange)
                    {
                        State = AIState.Attack;
                    }
                    break;

                case AIState.Attack:
                    if (distToPlayer > GameConfig.MeleeRange * 1.5f)
                    {
                        State = AIState.Chase;
                    }
                    // Flee check
                    if (Definition.Behavior == "flee_low_health" || Definition.Behavior == "defensive")
                    {
                        if (HealthPercent <= 0.2f)
                            State = AIState.Flee;
                    }
                    break;

                case AIState.Flee:
                    if (HealthPercent > 0.3f || distToPlayer > AggroRange * 3.0f)
                        State = AIState.Idle;
                    break;
            }

            // Move toward target during Chase
            if (State == AIState.Chase && TargetPosition.HasValue)
            {
                var target = TargetPosition.Value;
                float dx = target.X - Position.X;
                float dz = target.Z - Position.Z;
                float dist = MathF.Sqrt(dx * dx + dz * dz);

                if (dist > 0.1f)
                {
                    float moveSpeed = Definition.Speed * deltaTime;
                    Position = new GamePosition(
                        Position.X + (dx / dist) * moveSpeed,
                        Position.Y,
                        Position.Z + (dz / dist) * moveSpeed
                    );
                }
            }

            // Move away during Flee
            if (State == AIState.Flee)
            {
                float dx = Position.X - playerPosition.X;
                float dz = Position.Z - playerPosition.Z;
                float dist = MathF.Sqrt(dx * dx + dz * dz);

                if (dist > 0.1f)
                {
                    float moveSpeed = Definition.Speed * 1.2f * deltaTime;
                    Position = new GamePosition(
                        Position.X + (dx / dist) * moveSpeed,
                        Position.Y,
                        Position.Z + (dz / dist) * moveSpeed
                    );
                }
            }
        }

        /// <summary>
        /// Roll loot drops for this enemy.
        /// </summary>
        public List<(string MaterialId, int Quantity)> RollLoot()
        {
            var loot = new List<(string, int)>();
            foreach (var drop in Definition.Drops)
            {
                if (_rng.NextDouble() <= drop.Chance)
                {
                    int qty = _rng.Next(drop.QuantityMin, drop.QuantityMax + 1);
                    loot.Add((drop.MaterialId, qty));
                }
            }
            return loot;
        }

        public override string ToString()
        {
            return $"Enemy({Name} T{Tier}, HP:{CurrentHealth:F0}/{MaxHealth:F0}, {State})";
        }
    }
}
