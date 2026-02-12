// Game1.Entities.Enemy
// Migrated from: Combat/enemy.py (867 lines)
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Data.Enums;
using Game1.Data.Models;
using Game1.Entities.StatusEffects;

namespace Game1.Entities
{
    /// <summary>
    /// Enemy definition data loaded from JSON (hostiles-1.JSON).
    /// Immutable template; Enemy instances are spawned from definitions.
    /// </summary>
    [Serializable]
    public class EnemyDefinition
    {
        public string EnemyId { get; set; }
        public string Name { get; set; }
        public string EnemyType { get; set; } = "normal"; // normal, elite, miniboss, boss
        public int Tier { get; set; } = 1;
        public int BaseHealth { get; set; } = 50;
        public int BaseDamage { get; set; } = 10;
        public int BaseDefense { get; set; } = 5;
        public float AttackSpeed { get; set; } = 1.0f;
        public float MovementSpeed { get; set; } = 1.0f;
        public float AttackRange { get; set; } = 1.0f;
        public float DetectionRange { get; set; } = 5.0f;
        public int ExpReward { get; set; } = 25;
        public int GoldReward { get; set; }
        public string DamageType { get; set; } = "physical";
        public List<string> Tags { get; set; } = new();
        public List<string> Resistances { get; set; } = new();
        public List<string> Weaknesses { get; set; } = new();
        public List<Dictionary<string, object>> LootTable { get; set; } = new();
        public Dictionary<string, object> Abilities { get; set; } = new();
        public string IconPath { get; set; }
        public string SpritePath { get; set; }

        // Tier multipliers: T1=1.0, T2=2.0, T3=4.0, T4=8.0
        public float GetTierMultiplier()
        {
            return Tier switch
            {
                1 => 1.0f,
                2 => 2.0f,
                3 => 4.0f,
                4 => 8.0f,
                _ => 1.0f
            };
        }
    }

    /// <summary>
    /// Database for loading enemy definitions from JSON.
    /// Singleton pattern matching Phase 2 databases.
    /// </summary>
    public class EnemyDatabase
    {
        private static EnemyDatabase _instance;
        public Dictionary<string, EnemyDefinition> Enemies { get; set; } = new();
        public bool Loaded { get; private set; }

        private EnemyDatabase() { }

        public static EnemyDatabase GetInstance()
        {
            _instance ??= new EnemyDatabase();
            return _instance;
        }

        public void LoadFromJson(string jsonContent)
        {
            try
            {
                var enemies = Newtonsoft.Json.JsonConvert.DeserializeObject<List<EnemyDefinition>>(jsonContent);
                if (enemies != null)
                {
                    foreach (var enemy in enemies)
                    {
                        if (!string.IsNullOrEmpty(enemy.EnemyId))
                            Enemies[enemy.EnemyId] = enemy;
                    }
                }
                Loaded = true;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Failed to load enemy database: {ex.Message}");
            }
        }

        public EnemyDefinition GetDefinition(string enemyId)
        {
            return Enemies.GetValueOrDefault(enemyId);
        }

        public List<EnemyDefinition> GetEnemiesByTier(int tier)
        {
            return Enemies.Values.Where(e => e.Tier == tier).ToList();
        }

        public List<EnemyDefinition> GetEnemiesByType(string enemyType)
        {
            return Enemies.Values.Where(e => e.EnemyType == enemyType).ToList();
        }
    }

    /// <summary>
    /// Runtime enemy instance spawned from an EnemyDefinition.
    /// Has position, health, AI state, and combat behavior.
    /// Implements IStatusTarget for status effect system.
    /// </summary>
    public class Enemy : IStatusTarget
    {
        // Identity
        public string EnemyId { get; set; }
        public string Name { get; set; }
        public EnemyDefinition Definition { get; private set; }

        // Position
        public GamePosition Position { get; set; }
        public string Facing { get; set; } = "down";
        public GamePosition SpawnPosition { get; set; }

        // Health
        public float MaxHealth { get; set; }
        public float CurrentHealth { get; set; }
        public bool IsAlive => CurrentHealth > 0;

        // Combat stats
        public int BaseDamage { get; set; }
        public int BaseDefense { get; set; }
        public float AttackSpeed { get; set; }
        public float AttackRange { get; set; }
        public float DetectionRange { get; set; }
        public float MovementSpeed { get; set; }

        // AI
        public AIState CurrentState { get; set; } = AIState.Idle;
        public float StateTimer { get; set; }
        public float AttackCooldown { get; set; }
        public GamePosition? PatrolTarget { get; set; }

        // Rewards
        public int ExpReward { get; set; }
        public int GoldReward { get; set; }
        public List<Dictionary<string, object>> LootTable { get; set; } = new();

        // Status effect system
        public StatusEffectManager StatusManager { get; private set; }
        public float DamageMultiplier { get; set; } = 1.0f;
        public float DamageTakenMultiplier { get; set; } = 1.0f;
        public float ShieldHealth { get; set; }
        public bool IsFrozen { get; set; }
        public bool IsStunned { get; set; }
        public bool IsRooted { get; set; }
        public HashSet<string> VisualEffects { get; set; } = new();

        // Corpse handling
        public float CorpseTimer { get; set; }
        public const float CorpseDuration = 5.0f;

        // Death drop tracking
        public bool HasDroppedLoot { get; set; }

        public Enemy(EnemyDefinition definition, GamePosition spawnPosition)
        {
            Definition = definition;
            EnemyId = definition.EnemyId;
            Name = definition.Name;
            Position = spawnPosition;
            SpawnPosition = spawnPosition;

            float tierMult = definition.GetTierMultiplier();
            MaxHealth = definition.BaseHealth * tierMult;
            CurrentHealth = MaxHealth;
            BaseDamage = (int)(definition.BaseDamage * tierMult);
            BaseDefense = (int)(definition.BaseDefense * tierMult);
            AttackSpeed = definition.AttackSpeed;
            AttackRange = definition.AttackRange;
            DetectionRange = definition.DetectionRange;
            MovementSpeed = definition.MovementSpeed;

            ExpReward = (int)(definition.ExpReward * tierMult);
            GoldReward = (int)(definition.GoldReward * tierMult);
            LootTable = definition.LootTable;

            StatusManager = new StatusEffectManager(this);
        }

        /// <summary>
        /// Take damage. Returns actual damage dealt after defense.
        /// Defense reduces damage by DEF * 2% (max 75%).
        /// </summary>
        public float TakeDamage(float rawDamage)
        {
            if (!IsAlive) return 0f;

            // Apply damage taken multiplier (from vulnerable etc.)
            float modifiedDamage = rawDamage * DamageTakenMultiplier;

            // Defense reduction: DEF * 2%, max 75%
            float defReduction = Math.Min(0.75f, BaseDefense * 0.02f);
            float afterDefense = modifiedDamage * (1.0f - defReduction);

            // Apply shield first
            if (ShieldHealth > 0)
            {
                if (ShieldHealth >= afterDefense)
                {
                    ShieldHealth -= afterDefense;
                    return 0f;
                }
                afterDefense -= ShieldHealth;
                ShieldHealth = 0;
            }

            CurrentHealth -= afterDefense;
            if (CurrentHealth <= 0)
            {
                CurrentHealth = 0;
                OnDeath();
            }

            return afterDefense;
        }

        /// <summary>
        /// Deal damage from this enemy. Returns (min, max) damage range.
        /// </summary>
        public (int Min, int Max) GetDamageRange()
        {
            int baseDmg = (int)(BaseDamage * DamageMultiplier);
            int min = Math.Max(1, (int)(baseDmg * 0.8f));
            int max = Math.Max(1, (int)(baseDmg * 1.2f));
            return (min, max);
        }

        /// <summary>
        /// Update AI, status effects, and cooldowns.
        /// Full AI behavior (chase, attack, flee, wander) is here in skeleton form.
        /// Complex pathfinding/targeting deferred to Phase 4 (CombatManager integration).
        /// </summary>
        public void Update(float dt)
        {
            if (!IsAlive)
            {
                if (CurrentState == AIState.Dead)
                {
                    CurrentState = AIState.Corpse;
                    CorpseTimer = CorpseDuration;
                }
                else if (CurrentState == AIState.Corpse)
                {
                    CorpseTimer -= dt;
                }
                return;
            }

            // Update status effects
            StatusManager.Update(dt);

            // Update attack cooldown
            if (AttackCooldown > 0)
                AttackCooldown -= dt;

            // Update state timer
            StateTimer -= dt;

            // AI state machine — skeleton.
            // Full targeting/pathfinding integrated in Phase 4 CombatManager.
            switch (CurrentState)
            {
                case AIState.Idle:
                    if (StateTimer <= 0)
                    {
                        CurrentState = AIState.Wander;
                        StateTimer = 3.0f + (float)(new Random().NextDouble() * 4.0);
                    }
                    break;

                case AIState.Wander:
                    if (StateTimer <= 0)
                    {
                        CurrentState = AIState.Idle;
                        StateTimer = 2.0f + (float)(new Random().NextDouble() * 3.0);
                    }
                    break;

                case AIState.Chase:
                    // Phase 4: Move toward target via TargetFinder/IPathfinder
                    break;

                case AIState.Attack:
                    // Phase 4: Execute attack on target via CombatManager
                    break;

                case AIState.Flee:
                    if (StateTimer <= 0)
                    {
                        CurrentState = AIState.Idle;
                        StateTimer = 2.0f;
                    }
                    break;
            }
        }

        private void OnDeath()
        {
            CurrentState = AIState.Dead;
            StatusManager.ClearAll();
        }

        /// <summary>
        /// Check if this enemy should be removed (corpse timer expired).
        /// </summary>
        public bool ShouldDespawn()
        {
            return CurrentState == AIState.Corpse && CorpseTimer <= 0;
        }

        /// <summary>
        /// Distance to a position.
        /// </summary>
        public float DistanceTo(GamePosition target)
        {
            return Position.DistanceTo(target);
        }

        /// <summary>
        /// Check if a position is within detection range.
        /// </summary>
        public bool CanDetect(GamePosition target)
        {
            return DistanceTo(target) <= DetectionRange;
        }

        /// <summary>
        /// Check if a position is within attack range.
        /// </summary>
        public bool CanAttack(GamePosition target)
        {
            return DistanceTo(target) <= AttackRange && AttackCooldown <= 0;
        }
    }
}
