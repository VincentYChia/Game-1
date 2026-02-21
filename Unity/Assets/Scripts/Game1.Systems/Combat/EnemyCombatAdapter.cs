// ============================================================================
// Game1.Systems.Combat.EnemyCombatAdapter
// Migrated from: N/A (new architecture — bridges Enemy to ICombatEnemy)
// Migration phase: 4-6 bridge
// Date: 2026-02-21
//
// Adapter that makes Enemy compatible with CombatManager's ICombatEnemy
// interface without modifying the Enemy class directly.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Core;
using Game1.Data.Models;
using Game1.Entities;

namespace Game1.Systems.Combat
{
    /// <summary>
    /// Adapter wrapping an Enemy to satisfy ICombatEnemy.
    /// Created by EnemySpawner or GameManager when spawning enemies.
    /// </summary>
    public class EnemyCombatAdapter : ICombatEnemy
    {
        private readonly Enemy _enemy;
        private float _timeSinceDeath;

        public EnemyCombatAdapter(Enemy enemy)
        {
            _enemy = enemy ?? throw new ArgumentNullException(nameof(enemy));
        }

        /// <summary>Access the underlying Enemy instance.</summary>
        public Enemy Inner => _enemy;

        // ====================================================================
        // Identity
        // ====================================================================

        public string EnemyId => _enemy.EnemyId;
        public string DefinitionName => _enemy.Name;
        public int Tier => _enemy.Tier;
        public bool IsBoss => _enemy.Definition.Category == "boss";
        public string DamageType => _enemy.Definition.Tags?.Count > 0
            ? _enemy.Definition.Tags[0]
            : "physical";
        public bool IsDungeonEnemy { get; set; }

        // ====================================================================
        // State (interface requires getters and setters)
        // ====================================================================

        public bool IsAlive
        {
            get => _enemy.IsAlive;
            set { /* Enemy.IsAlive is computed from health/state */ }
        }

        public float CurrentHealth
        {
            get => _enemy.CurrentHealth;
            set => _enemy.CurrentHealth = value;
        }

        public float MaxHealth => _enemy.MaxHealth;
        public float PositionX => _enemy.Position.X;
        public float PositionY => _enemy.Position.Z; // Z maps to 2D Y
        public float Defense => _enemy.Definition.Defense;
        public float AttackSpeed => _enemy.Definition.AttackSpeed;
        public float DamageMin => _enemy.Definition.DamageMin;
        public float DamageMax => _enemy.Definition.DamageMax;

        public bool InCombat
        {
            get => _enemy.State == AIState.Chase || _enemy.State == AIState.Attack;
            set { /* Combat state managed by AI */ }
        }

        public (int X, int Y) ChunkCoords
        {
            get
            {
                int cx = (int)(_enemy.Position.X / GameConfig.ChunkSize);
                int cy = (int)(_enemy.Position.Z / GameConfig.ChunkSize);
                return (cx, cy);
            }
        }

        public string AiState
        {
            get => _enemy.State.ToString();
            set
            {
                if (Enum.TryParse<AIState>(value, true, out var state))
                    _enemy.State = state;
            }
        }

        public float TimeSinceDeath
        {
            get => _timeSinceDeath;
            set => _timeSinceDeath = value;
        }

        public float CorpseLifetime { get; set; } = 30f;

        // ====================================================================
        // Combat Actions
        // ====================================================================

        public float PerformAttack()
        {
            return _enemy.GetDamage();
        }

        public bool TakeDamage(float amount, bool fromPlayer = false)
        {
            float actual = _enemy.TakeDamage(amount);
            return !_enemy.IsAlive; // Returns true if enemy died
        }

        public bool CanAttack()
        {
            return _enemy.IsAlive && _enemy.AttackCooldown <= 0;
        }

        public float DistanceTo(float x, float y)
        {
            float dx = _enemy.Position.X - x;
            float dz = _enemy.Position.Z - y; // y maps to Z
            return MathF.Sqrt(dx * dx + dz * dz);
        }

        public void UpdateAi(float dt, float playerX, float playerY,
            float aggroMultiplier = 1.0f, float speedMultiplier = 1.0f,
            float safeZoneCenterX = 0f, float safeZoneCenterY = 0f,
            float safeZoneRadius = 15f)
        {
            var playerPos = GamePosition.FromXZ(playerX, playerY);
            _enemy.Update(dt, playerPos);
        }

        // ====================================================================
        // Loot
        // ====================================================================

        public List<(string MaterialId, int Quantity)> GenerateLoot()
        {
            return _enemy.RollLoot();
        }
    }
}
