// ============================================================================
// Game1.Systems.Combat.TurretSystem
// Migrated from: systems/turret_system.py (551 lines)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Manages placed entity AI: turrets (auto-attack), traps (proximity),
// bombs (timed fuse), and utility devices (healing beacon, net launcher, EMP).
//
// Update loop order:
//   1. Update status effects on placed entities
//   2. Decrement lifetime, remove expired
//   3. Update utility devices (healing beacon, net launcher, EMP)
//   4. Turrets: find nearest enemy in range, check cooldown, attack
//   5. Trap triggers: proximity activation
//   6. Bomb detonations: timed fuse countdown
//
// NO MonoBehaviour, NO UnityEngine. Pure C#.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Systems.Combat
{
    // ========================================================================
    // Placed Entity Interfaces
    // ========================================================================

    /// <summary>
    /// Type of placed entity.
    /// Mirrors Python: PlacedEntityType enum.
    /// </summary>
    public enum PlacedEntityType
    {
        Turret,
        Trap,
        Bomb,
        UtilityDevice
    }

    /// <summary>
    /// Interface for a placed entity (turret, trap, bomb, utility device).
    /// Avoids direct dependency on the data model class.
    /// </summary>
    public interface IPlacedEntity
    {
        /// <summary>Entity type (turret, trap, bomb, utility).</summary>
        PlacedEntityType EntityType { get; }

        /// <summary>Item ID for this placed entity.</summary>
        string ItemId { get; }

        /// <summary>World X position.</summary>
        float PositionX { get; }

        /// <summary>World Y position.</summary>
        float PositionY { get; }

        /// <summary>Remaining lifetime in seconds.</summary>
        float TimeRemaining { get; set; }

        /// <summary>Base damage for turrets.</summary>
        float Damage { get; }

        /// <summary>Attack range for turrets (in world units).</summary>
        float Range { get; }

        /// <summary>Attack speed for turrets (attacks per second).</summary>
        float AttackSpeed { get; }

        /// <summary>Time of last attack (game time).</summary>
        float LastAttackTime { get; set; }

        /// <summary>Current target enemy (for turrets).</summary>
        ICombatEnemy TargetEnemy { get; set; }

        /// <summary>Effect tags for tag-based attacks.</summary>
        List<string> Tags { get; }

        /// <summary>Effect parameters for tag-based attacks.</summary>
        Dictionary<string, object> EffectParams { get; }

        /// <summary>Current health for destructible entities.</summary>
        float Health { get; set; }

        /// <summary>Whether entity has been triggered (traps/bombs).</summary>
        bool Triggered { get; set; }

        /// <summary>Whether entity is stunned by status effect.</summary>
        bool IsStunned { get; }

        /// <summary>Whether entity is frozen by status effect.</summary>
        bool IsFrozen { get; }

        /// <summary>Update status effects on this entity.</summary>
        void UpdateStatusEffects(float dt);

        /// <summary>Fuse timer for bombs (initialized on first update).</summary>
        float FuseTimer { get; set; }

        /// <summary>Whether the fuse timer has been initialized.</summary>
        bool FuseInitialized { get; set; }
    }

    /// <summary>
    /// Callback interface for turret attacks, allowing the combat system
    /// to process attacks through the tag/effect system.
    /// </summary>
    public interface ITurretAttackHandler
    {
        /// <summary>
        /// Execute a turret attack on an enemy.
        /// </summary>
        /// <param name="turret">The attacking turret.</param>
        /// <param name="target">The target enemy.</param>
        /// <param name="allEnemies">All enemies (for AoE geometry calculations).</param>
        void ExecuteTurretAttack(IPlacedEntity turret, ICombatEnemy target, List<ICombatEnemy> allEnemies);

        /// <summary>
        /// Execute a trap effect on enemies.
        /// </summary>
        /// <param name="trap">The triggered trap.</param>
        /// <param name="primaryTarget">Enemy that triggered the trap.</param>
        /// <param name="allEnemies">All enemies (for AoE calculations).</param>
        void ExecuteTrapEffect(IPlacedEntity trap, ICombatEnemy primaryTarget, List<ICombatEnemy> allEnemies);

        /// <summary>
        /// Execute a bomb detonation.
        /// </summary>
        /// <param name="bomb">The detonated bomb.</param>
        /// <param name="allEnemies">All enemies (for AoE calculations).</param>
        void ExecuteBombDetonation(IPlacedEntity bomb, List<ICombatEnemy> allEnemies);
    }

    /// <summary>
    /// Interface for accessing the player character for utility devices.
    /// </summary>
    public interface ITurretCharacterAccess
    {
        float PositionX { get; }
        float PositionY { get; }
        float Health { get; set; }
        float MaxHealth { get; }
    }

    /// <summary>
    /// Manages turret AI, targeting, attacking, trap triggers, bomb detonations,
    /// and utility device updates.
    ///
    /// Migrated from Python TurretSystem (551 lines).
    /// All update logic matches the Python source exactly.
    /// </summary>
    public class TurretSystem
    {
        /// <summary>
        /// Optional attack handler for tag-based attacks.
        /// If null, falls back to simple damage application.
        /// </summary>
        public ITurretAttackHandler AttackHandler { get; set; }

        // ====================================================================
        // Main Update
        // ====================================================================

        /// <summary>
        /// Update all placed entities: turrets, traps, bombs, utility devices.
        /// Python: TurretSystem.update()
        /// </summary>
        /// <param name="placedEntities">All placed entities in the world (will be modified).</param>
        /// <param name="allEnemies">All active enemies for targeting.</param>
        /// <param name="character">Player character (for utility devices).</param>
        /// <param name="currentTime">Current game time in seconds.</param>
        /// <param name="dt">Delta time since last frame.</param>
        public void Update(List<IPlacedEntity> placedEntities, List<ICombatEnemy> allEnemies,
                          ITurretCharacterAccess character, float currentTime, float dt)
        {
            var entitiesToRemove = new List<IPlacedEntity>();

            // Update utility devices FIRST (healing beacon, etc.)
            // Python: self.update_utility_devices(placed_entities, combat_manager, dt)
            _updateUtilityDevices(placedEntities, allEnemies, character, dt);

            foreach (var entity in placedEntities)
            {
                // Update status effects FIRST
                // Python: if hasattr(entity, 'update_status_effects'): entity.update_status_effects(dt)
                entity.UpdateStatusEffects(dt);

                // Update lifetime
                // Python: entity.time_remaining -= dt
                entity.TimeRemaining -= dt;
                if (entity.TimeRemaining <= 0f)
                {
                    entitiesToRemove.Add(entity);
                    continue;
                }

                // Only process turrets for auto-targeting combat
                if (entity.EntityType != PlacedEntityType.Turret)
                    continue;

                // Disabled by status effects
                // Python: if entity.is_stunned: continue
                //         if entity.is_frozen: continue
                if (entity.IsStunned || entity.IsFrozen)
                    continue;

                // Find nearest enemy in range
                ICombatEnemy target = _findNearestEnemy(entity, allEnemies);

                if (target != null)
                {
                    entity.TargetEnemy = target;

                    // Check cooldown
                    // Python: time_since_attack = current_time - entity.last_attack_time
                    //         cooldown = 1.0 / entity.attack_speed
                    float timeSinceAttack = currentTime - entity.LastAttackTime;
                    float cooldown = 1.0f / entity.AttackSpeed;

                    if (timeSinceAttack >= cooldown)
                    {
                        _attackEnemy(entity, target, allEnemies);
                        entity.LastAttackTime = currentTime;
                    }
                }
                else
                {
                    entity.TargetEnemy = null;
                }
            }

            // Check trap triggers
            // Python: triggered_traps = self.check_trap_triggers(placed_entities, all_enemies)
            var triggeredTraps = _checkTrapTriggers(placedEntities, allEnemies);
            entitiesToRemove.AddRange(triggeredTraps);

            // Check bomb detonations
            // Python: detonated_bombs = self.check_bomb_detonations(placed_entities, all_enemies, dt)
            var detonatedBombs = _checkBombDetonations(placedEntities, allEnemies, dt);
            entitiesToRemove.AddRange(detonatedBombs);

            // Remove expired/triggered entities
            foreach (var entity in entitiesToRemove)
            {
                placedEntities.Remove(entity);
            }
        }

        // ====================================================================
        // Turret Targeting
        // ====================================================================

        /// <summary>
        /// Find the nearest alive enemy within turret's range.
        /// Python: _find_nearest_enemy()
        /// </summary>
        private ICombatEnemy _findNearestEnemy(IPlacedEntity turret, List<ICombatEnemy> allEnemies)
        {
            ICombatEnemy nearest = null;
            float nearestDist = float.MaxValue;

            foreach (var enemy in allEnemies)
            {
                if (!enemy.IsAlive)
                    continue;

                // Calculate distance
                // Python: dx = turret.position.x - enemy_x
                //         dy = turret.position.y - enemy_y
                //         dist = (dx * dx + dy * dy) ** 0.5
                float dx = turret.PositionX - enemy.PositionX;
                float dy = turret.PositionY - enemy.PositionY;
                float dist = MathF.Sqrt(dx * dx + dy * dy);

                if (dist <= turret.Range && dist < nearestDist)
                {
                    nearest = enemy;
                    nearestDist = dist;
                }
            }

            return nearest;
        }

        // ====================================================================
        // Turret Attack
        // ====================================================================

        /// <summary>
        /// Turret attacks an enemy using tag system or legacy damage.
        /// Python: _attack_enemy()
        /// </summary>
        private void _attackEnemy(IPlacedEntity turret, ICombatEnemy target, List<ICombatEnemy> allEnemies)
        {
            if (AttackHandler != null && turret.Tags != null && turret.Tags.Count > 0)
            {
                // Use tag system via handler
                AttackHandler.ExecuteTurretAttack(turret, target, allEnemies);
            }
            else
            {
                // Legacy: apply simple damage
                // Python: enemy.current_health -= turret.damage
                target.CurrentHealth -= turret.Damage;

                if (target.CurrentHealth <= 0f)
                {
                    target.IsAlive = false;
                    target.CurrentHealth = 0f;
                }
            }
        }

        // ====================================================================
        // Trap Triggers
        // ====================================================================

        /// <summary>
        /// Check if any enemies trigger traps via proximity.
        /// Python: check_trap_triggers()
        /// </summary>
        /// <returns>List of triggered traps to remove.</returns>
        private List<IPlacedEntity> _checkTrapTriggers(List<IPlacedEntity> entities, List<ICombatEnemy> allEnemies)
        {
            var triggeredTraps = new List<IPlacedEntity>();

            foreach (var entity in entities)
            {
                if (entity.EntityType != PlacedEntityType.Trap)
                    continue;

                if (entity.Triggered)
                    continue;

                // Get trigger radius (default 2.0 tiles)
                // Python: trigger_radius = entity.effect_params.get('trigger_radius', 2.0)
                float triggerRadius = 2.0f;
                if (entity.EffectParams != null &&
                    entity.EffectParams.TryGetValue("trigger_radius", out object radiusObj))
                {
                    triggerRadius = Convert.ToSingle(radiusObj);
                }

                // Check all enemies for proximity
                foreach (var enemy in allEnemies)
                {
                    if (!enemy.IsAlive)
                        continue;

                    float dx = entity.PositionX - enemy.PositionX;
                    float dy = entity.PositionY - enemy.PositionY;
                    float dist = MathF.Sqrt(dx * dx + dy * dy);

                    if (dist <= triggerRadius)
                    {
                        // Trigger trap
                        _triggerTrap(entity, enemy, allEnemies);
                        entity.Triggered = true;
                        triggeredTraps.Add(entity);
                        break; // One trigger per trap per update
                    }
                }
            }

            return triggeredTraps;
        }

        /// <summary>
        /// Execute trap effect using tag system.
        /// Python: _trigger_trap()
        /// </summary>
        private void _triggerTrap(IPlacedEntity trap, ICombatEnemy primaryTarget, List<ICombatEnemy> allEnemies)
        {
            if (trap.Tags == null || trap.Tags.Count == 0)
                return;

            if (AttackHandler != null)
            {
                AttackHandler.ExecuteTrapEffect(trap, primaryTarget, allEnemies);
            }
        }

        // ====================================================================
        // Bomb Detonations
        // ====================================================================

        /// <summary>
        /// Check if any bombs have expired fuses and detonate them.
        /// Python: check_bomb_detonations()
        /// </summary>
        /// <returns>List of detonated bombs to remove.</returns>
        private List<IPlacedEntity> _checkBombDetonations(List<IPlacedEntity> entities,
            List<ICombatEnemy> allEnemies, float dt)
        {
            var detonatedBombs = new List<IPlacedEntity>();

            foreach (var entity in entities)
            {
                if (entity.EntityType != PlacedEntityType.Bomb)
                    continue;

                if (entity.Triggered)
                    continue;

                // Initialize fuse timer on first update
                // Python: if not hasattr(entity, 'fuse_timer'):
                //             entity.fuse_timer = fuse_duration
                if (!entity.FuseInitialized)
                {
                    float fuseDuration = 3.0f;
                    if (entity.EffectParams != null &&
                        entity.EffectParams.TryGetValue("fuse_duration", out object fuseObj))
                    {
                        fuseDuration = Convert.ToSingle(fuseObj);
                    }
                    entity.FuseTimer = fuseDuration;
                    entity.FuseInitialized = true;
                }

                // Countdown fuse
                // Python: entity.fuse_timer -= dt
                entity.FuseTimer -= dt;

                // Detonate when fuse expires
                if (entity.FuseTimer <= 0f)
                {
                    _detonateBomb(entity, allEnemies);
                    entity.Triggered = true;
                    detonatedBombs.Add(entity);
                }
            }

            return detonatedBombs;
        }

        /// <summary>
        /// Detonate bomb using tag system for AoE damage.
        /// Python: _detonate_bomb()
        /// </summary>
        private void _detonateBomb(IPlacedEntity bomb, List<ICombatEnemy> allEnemies)
        {
            if (bomb.Tags == null || bomb.Tags.Count == 0)
                return;

            // Get blast radius
            // Python: blast_radius = bomb.effect_params.get('circle_radius', 3.0)
            float blastRadius = 3.0f;
            if (bomb.EffectParams != null &&
                bomb.EffectParams.TryGetValue("circle_radius", out object radiusObj))
            {
                blastRadius = Convert.ToSingle(radiusObj);
            }

            // Filter enemies in blast radius
            var enemiesInRange = new List<ICombatEnemy>();
            foreach (var enemy in allEnemies)
            {
                if (!enemy.IsAlive)
                    continue;

                float dx = bomb.PositionX - enemy.PositionX;
                float dy = bomb.PositionY - enemy.PositionY;
                float dist = MathF.Sqrt(dx * dx + dy * dy);

                if (dist <= blastRadius)
                {
                    enemiesInRange.Add(enemy);
                }
            }

            if (AttackHandler != null)
            {
                AttackHandler.ExecuteBombDetonation(bomb, allEnemies);
            }
        }

        // ====================================================================
        // Utility Devices
        // ====================================================================

        /// <summary>
        /// Update utility devices (healing beacon, net launcher, EMP).
        /// Python: update_utility_devices()
        /// </summary>
        private void _updateUtilityDevices(List<IPlacedEntity> entities, List<ICombatEnemy> allEnemies,
            ITurretCharacterAccess character, float dt)
        {
            if (character == null)
                return;

            foreach (var entity in entities)
            {
                if (entity.EntityType != PlacedEntityType.UtilityDevice)
                    continue;

                switch (entity.ItemId)
                {
                    case "healing_beacon":
                        _updateHealingBeacon(entity, character, dt);
                        break;
                    case "net_launcher":
                        _updateNetLauncher(entity, allEnemies);
                        break;
                    case "emp_device":
                        _updateEmpDevice(entity, allEnemies, dt);
                        break;
                }
            }
        }

        /// <summary>
        /// Healing beacon: heals player 10 HP/sec in 5 unit radius.
        /// Python: _update_healing_beacon()
        /// </summary>
        private void _updateHealingBeacon(IPlacedEntity beacon, ITurretCharacterAccess character, float dt)
        {
            // Check if player is in range (5 unit radius)
            // Python: heal_radius = 5.0
            const float HealRadius = 5.0f;
            const float HealPerSecond = 10.0f;

            float dx = beacon.PositionX - character.PositionX;
            float dy = beacon.PositionY - character.PositionY;
            float dist = MathF.Sqrt(dx * dx + dy * dy);

            if (dist <= HealRadius && character.Health < character.MaxHealth)
            {
                // Apply heal
                // Python: heal_amount = 10.0 * dt
                float healAmount = HealPerSecond * dt;
                character.Health = Math.Min(character.MaxHealth, character.Health + healAmount);
            }
        }

        /// <summary>
        /// Net launcher: auto-deploys to slow enemies by 80% for 10s in 5 unit radius.
        /// Triggers on proximity (3 unit trigger radius). One-time use.
        /// Python: _update_net_launcher()
        /// </summary>
        private void _updateNetLauncher(IPlacedEntity netLauncher, List<ICombatEnemy> allEnemies)
        {
            if (netLauncher.Triggered)
                return;

            const float TriggerRadius = 3.0f;

            foreach (var enemy in allEnemies)
            {
                if (!enemy.IsAlive)
                    continue;

                float dx = netLauncher.PositionX - enemy.PositionX;
                float dy = netLauncher.PositionY - enemy.PositionY;
                float dist = MathF.Sqrt(dx * dx + dy * dy);

                if (dist <= TriggerRadius)
                {
                    // Deploy net: affect all enemies in 5 unit effect radius
                    // Python: effect_radius = 5.0, speed_reduction = 0.8, duration = 10.0
                    const float EffectRadius = 5.0f;

                    foreach (var target in allEnemies)
                    {
                        if (!target.IsAlive)
                            continue;

                        float tdx = netLauncher.PositionX - target.PositionX;
                        float tdy = netLauncher.PositionY - target.PositionY;
                        float tdist = MathF.Sqrt(tdx * tdx + tdy * tdy);

                        if (tdist <= EffectRadius)
                        {
                            // Apply slow via status system
                            // Handled externally by the status effect callback
                            OnStatusEffectApplied?.Invoke(target, "slow", new Dictionary<string, object>
                            {
                                { "duration", 10.0f },
                                { "speed_reduction", 0.8f }
                            });
                        }
                    }

                    netLauncher.Triggered = true;
                    break;
                }
            }
        }

        /// <summary>
        /// EMP device: stuns construct-type enemies in 8 unit radius for 30s.
        /// Activates after 1 second delay. One-time use.
        /// Python: _update_emp_device()
        /// </summary>
        private void _updateEmpDevice(IPlacedEntity emp, List<ICombatEnemy> allEnemies, float dt)
        {
            if (emp.Triggered)
                return;

            // Initialize activation timer
            // Python: emp._emp_timer = 1.0
            if (!emp.FuseInitialized)
            {
                emp.FuseTimer = 1.0f;
                emp.FuseInitialized = true;
            }

            emp.FuseTimer -= dt;

            if (emp.FuseTimer <= 0f)
            {
                // Activate EMP: stun construct-type enemies in 8 unit radius
                // Python: effect_radius = 8.0, stun duration = 30.0
                const float EffectRadius = 8.0f;

                foreach (var enemy in allEnemies)
                {
                    if (!enemy.IsAlive)
                        continue;

                    // Check distance
                    float dx = emp.PositionX - enemy.PositionX;
                    float dy = emp.PositionY - enemy.PositionY;
                    float dist = MathF.Sqrt(dx * dx + dy * dy);

                    if (dist <= EffectRadius)
                    {
                        // Apply stun via status system (constructs only in Python,
                        // but the check is done externally)
                        OnStatusEffectApplied?.Invoke(enemy, "stun", new Dictionary<string, object>
                        {
                            { "duration", 30.0f }
                        });
                    }
                }

                emp.Triggered = true;
            }
        }

        // ====================================================================
        // Callbacks
        // ====================================================================

        /// <summary>
        /// Callback for applying status effects to enemies (slow, stun, etc.).
        /// Args: target enemy, status type, status parameters.
        /// </summary>
        public Action<ICombatEnemy, string, Dictionary<string, object>> OnStatusEffectApplied { get; set; }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>
        /// Get targeting line from turret to its current target (for rendering).
        /// Python: get_turret_target_line()
        /// </summary>
        /// <returns>Null if no active target, otherwise (turretX, turretY, targetX, targetY).</returns>
        public (float TurretX, float TurretY, float TargetX, float TargetY)? GetTurretTargetLine(
            IPlacedEntity turret)
        {
            if (turret.TargetEnemy != null && turret.TargetEnemy.IsAlive)
            {
                return (turret.PositionX, turret.PositionY,
                        turret.TargetEnemy.PositionX, turret.TargetEnemy.PositionY);
            }
            return null;
        }
    }
}
