// Game1.Systems.Effects.EffectExecutor
// Migrated from: core/effect_executor.py (624 lines)
// Migration phase: 4
//
// Main executor for tag-based effects.
// Coordinates tag parsing, target finding, damage/healing/status/special application.
// No UnityEngine dependency. Uses System.Random and GamePosition.

using System;
using System.Collections.Generic;
using Game1.Data.Models;
using Game1.Systems.Tags;

namespace Game1.Systems.Effects
{
    /// <summary>
    /// Main executor for tag-based effects.
    /// Coordinates all effect application: parsing, targeting, damage, healing,
    /// status effects, and special mechanics (lifesteal, knockback, etc.).
    /// </summary>
    public class EffectExecutor
    {
        private readonly TagRegistry _registry;
        private readonly TagParser _parser;
        private readonly TargetFinder _targetFinder;
        private readonly Random _random;

        // Current execution state (for advanced damage methods that need context)
        private object _currentSource;
        private List<string> _currentTags;
        private EffectContext _currentContext;

        /// <summary>Optional logging delegate for debug messages.</summary>
        public static Action<string> LogDebug { get; set; }

        /// <summary>Optional logging delegate for info messages.</summary>
        public static Action<string> LogInfo { get; set; }

        /// <summary>Optional logging delegate for warning messages.</summary>
        public static Action<string> LogWarning { get; set; }

        public EffectExecutor()
        {
            _registry = TagRegistry.Instance;
            _parser = new TagParser(_registry);
            _targetFinder = new TargetFinder();
            _random = new Random();
        }

        /// <summary>
        /// Constructor accepting explicit dependencies (useful for testing).
        /// </summary>
        public EffectExecutor(TagRegistry registry, TagParser parser,
                               TargetFinder targetFinder, Random random = null)
        {
            _registry = registry ?? throw new ArgumentNullException(nameof(registry));
            _parser = parser ?? throw new ArgumentNullException(nameof(parser));
            _targetFinder = targetFinder ?? throw new ArgumentNullException(nameof(targetFinder));
            _random = random ?? new Random();
        }

        /// <summary>
        /// Execute an effect from tags.
        /// Main entry point for the effect pipeline.
        /// </summary>
        /// <param name="source">Source entity (caster, turret, etc.).</param>
        /// <param name="primaryTarget">Primary target entity.</param>
        /// <param name="tags">List of tag strings from JSON.</param>
        /// <param name="effectParams">Effect parameters from JSON.</param>
        /// <param name="availableEntities">All entities available for geometry targeting.</param>
        /// <returns>EffectContext with execution results.</returns>
        public EffectContext ExecuteEffect(object source, object primaryTarget,
                                           List<string> tags, Dictionary<string, object> effectParams,
                                           List<object> availableEntities = null)
        {
            if (tags == null) tags = new List<string>();
            if (effectParams == null) effectParams = new Dictionary<string, object>();
            if (availableEntities == null) availableEntities = new List<object>();

            // 1. Parse tags into config
            EffectConfig config = _parser.Parse(tags, effectParams);

            // 2. Create effect context
            var context = new EffectContext(
                source: source,
                primaryTarget: primaryTarget,
                config: config,
                timestamp: 0f  // TODO: Add proper timestamp from game clock
            );

            // 3. Find all targets based on geometry
            List<object> targets = _targetFinder.FindTargets(
                geometry: config.GeometryTag,
                source: source,
                target: primaryTarget,
                parms: config.Params,
                context: config.Context,
                entities: availableEntities
            );

            context.Targets = targets;

            // Store current execution context for damage methods that need it
            _currentSource = source;
            _currentTags = tags;
            _currentContext = context;

            // 4. Apply effects to all targets
            for (int i = 0; i < targets.Count; i++)
            {
                object target = targets[i];

                // Calculate damage falloff for geometry
                float magnitudeMult = _calculateMagnitudeMultiplier(config, i, targets.Count);

                // Apply damage
                if (config.BaseDamage > 0)
                {
                    _applyDamage(source, target, config, magnitudeMult);
                }

                // Apply healing
                if (config.BaseHealing > 0)
                {
                    _applyHealing(source, target, config, magnitudeMult);
                }

                // Apply status effects
                _applyStatusEffects(target, config);

                // Apply special mechanics
                _applySpecialMechanics(source, target, config, magnitudeMult);
            }

            return context;
        }

        // ====================================================================
        // Magnitude Calculation
        // ====================================================================

        /// <summary>
        /// Calculate damage/healing multiplier based on geometry and target position in list.
        /// Chain: (1 - falloff)^index, default falloff 0.3 (70% -> 49% -> 34%...)
        /// Pierce: (1 - falloff)^index, default falloff 0.1 (90% -> 81% -> 73%...)
        /// Others: 1.0 (no falloff).
        /// </summary>
        private float _calculateMagnitudeMultiplier(EffectConfig config, int targetIndex, int totalTargets)
        {
            if (config.GeometryTag == "chain")
            {
                float falloff = _getFloat(config.Params, "chain_falloff", 0.3f);
                return MathF.Pow(1f - falloff, targetIndex);
            }

            if (config.GeometryTag == "pierce")
            {
                float falloff = _getFloat(config.Params, "pierce_falloff", 0.1f);
                return MathF.Pow(1f - falloff, targetIndex);
            }

            // No falloff for other geometries
            return 1f;
        }

        // ====================================================================
        // Damage Application
        // ====================================================================

        /// <summary>
        /// Apply damage to a target for all damage tags in the config.
        /// Handles critical hits, context behavior (type bonuses, heal conversion),
        /// and auto-apply status effects from damage tags.
        /// </summary>
        private void _applyDamage(object source, object target, EffectConfig config, float magnitudeMult)
        {
            float baseDamage = config.BaseDamage * magnitudeMult;

            // Check for critical hit mechanic
            float critMultiplier = 1f;
            if (config.SpecialTags.Contains("critical"))
            {
                float critChance = _getFloat(config.Params, "crit_chance", 0.15f);
                float critMultParam = _getFloat(config.Params, "crit_multiplier", 2f);

                if ((float)_random.NextDouble() < critChance)
                {
                    critMultiplier = critMultParam;
                    LogDebug?.Invoke($"Critical hit! Multiplier: {critMultiplier}x");
                }
            }

            // Apply damage for each damage type
            foreach (string damageTag in config.DamageTags)
            {
                float damage = baseDamage * critMultiplier;

                // Check for type-specific bonuses
                TagDefinition tagDef = _registry.GetDefinition(damageTag);
                if (tagDef != null && tagDef.ContextBehavior != null && tagDef.ContextBehavior.Count > 0)
                {
                    string targetCategory = _getStringProp(target, "Category");
                    if (targetCategory != null && tagDef.ContextBehavior.ContainsKey(targetCategory))
                    {
                        object behaviorObj = tagDef.ContextBehavior[targetCategory];
                        if (behaviorObj is Dictionary<string, object> behavior)
                        {
                            // Check for damage multiplier
                            if (behavior.ContainsKey("damage_multiplier"))
                            {
                                float dmgMult = _convertToFloat(behavior["damage_multiplier"]);
                                damage *= dmgMult;
                                LogInfo?.Invoke(
                                    $"{damageTag} damage bonus vs {targetCategory}: multiplier={dmgMult}"
                                );
                            }

                            // Check for conversion to healing
                            if (behavior.ContainsKey("converts_to_healing") &&
                                _convertToBool(behavior["converts_to_healing"]))
                            {
                                _healTarget(target, damage);
                                LogInfo?.Invoke($"{damageTag} damage converted to healing for ally");
                                return;
                            }
                        }
                    }
                }

                // Actually apply damage
                _damageTarget(target, damage, damageTag);

                // Auto-apply status chance from damage tag
                if (tagDef != null && tagDef.AutoApplyStatus != null && tagDef.AutoApplyChance > 0)
                {
                    if ((float)_random.NextDouble() < tagDef.AutoApplyChance)
                    {
                        string statusTag = tagDef.AutoApplyStatus;
                        var statusParams = _registry.GetDefaultParams(statusTag);
                        _applySingleStatus(target, statusTag, statusParams);
                    }
                }
            }
        }

        // ====================================================================
        // Healing Application
        // ====================================================================

        /// <summary>Apply healing to target scaled by magnitude.</summary>
        private void _applyHealing(object source, object target, EffectConfig config, float magnitudeMult)
        {
            float healing = config.BaseHealing * magnitudeMult;
            _healTarget(target, healing);
        }

        // ====================================================================
        // Status Effects
        // ====================================================================

        /// <summary>Apply all status effects from the config to the target.</summary>
        private void _applyStatusEffects(object target, EffectConfig config)
        {
            foreach (string statusTag in config.StatusTags)
            {
                // Get parameters for this status
                var statusParams = new Dictionary<string, object>();
                TagDefinition tagDef = _registry.GetDefinition(statusTag);

                if (tagDef != null)
                {
                    // Merge defaults with config params
                    statusParams = new Dictionary<string, object>(tagDef.DefaultParams ?? new Dictionary<string, object>());

                    // Override with specific params from config
                    var keysToCheck = new List<string>(statusParams.Keys);
                    foreach (string paramKey in keysToCheck)
                    {
                        if (config.Params.ContainsKey(paramKey))
                        {
                            statusParams[paramKey] = config.Params[paramKey];
                        }
                    }
                }

                _applySingleStatus(target, statusTag, statusParams);
            }
        }

        /// <summary>
        /// Apply a single status effect to a target.
        /// Checks immunity and delegates to target's StatusManager.
        /// </summary>
        private void _applySingleStatus(object target, string statusTag, Dictionary<string, object> statusParams)
        {
            // Check immunity
            TagDefinition tagDef = _registry.GetDefinition(statusTag);
            if (tagDef != null && tagDef.Immunity != null && tagDef.Immunity.Count > 0)
            {
                string targetCategory = _getStringProp(target, "Category");
                if (targetCategory != null && tagDef.Immunity.Contains(targetCategory))
                {
                    LogDebug?.Invoke($"Target immune to {statusTag} (category: {targetCategory})");
                    return;
                }
            }

            // Check for StatusManager on target
            var statusManagerProp = target?.GetType().GetProperty("StatusManager");
            if (statusManagerProp != null)
            {
                object statusManager = statusManagerProp.GetValue(target);
                if (statusManager != null)
                {
                    // Call ApplyStatus(string, Dictionary<string, object>)
                    var applyMethod = statusManager.GetType().GetMethod("ApplyStatus",
                        new[] { typeof(string), typeof(Dictionary<string, object>) });

                    if (applyMethod != null)
                    {
                        applyMethod.Invoke(statusManager, new object[] { statusTag, statusParams });
                        LogDebug?.Invoke($"Applied {statusTag} to {_getName(target)}");
                        return;
                    }
                }
            }

            LogWarning?.Invoke(
                $"Target {_getName(target)} has no StatusManager, cannot apply {statusTag}"
            );
        }

        // ====================================================================
        // Special Mechanics
        // ====================================================================

        /// <summary>
        /// Apply special mechanics for each special tag in the config.
        /// Dispatches to specific handlers: lifesteal, knockback, pull, execute,
        /// teleport, dash, phase.
        /// </summary>
        private void _applySpecialMechanics(object source, object target,
                                             EffectConfig config, float magnitudeMult)
        {
            foreach (string specialTag in config.SpecialTags)
            {
                switch (specialTag)
                {
                    case "lifesteal":
                    case "vampiric":
                        _applyLifesteal(source, config.BaseDamage * magnitudeMult, config.Params);
                        break;

                    case "knockback":
                        _applyKnockback(source, target, config.Params);
                        break;

                    case "pull":
                        _applyPull(source, target, config.Params);
                        break;

                    case "execute":
                        _applyExecute(source, target, config, magnitudeMult);
                        break;

                    case "critical":
                        // Critical is handled in _applyDamage as a damage multiplier
                        break;

                    case "teleport":
                    case "blink":
                        _applyTeleport(source, target, config.Params);
                        break;

                    case "dash":
                    case "charge":
                        _applyDash(source, target, config.Params);
                        break;

                    case "phase":
                    case "ethereal":
                    case "intangible":
                        _applyPhase(source, config.Params);
                        break;

                    default:
                        // Unknown special tag - no handler
                        LogDebug?.Invoke($"No handler for special tag: {specialTag}");
                        break;
                }
            }
        }

        /// <summary>
        /// Apply lifesteal: heal source for a percentage of damage dealt.
        /// Default lifesteal_percent = 0.15 (15%).
        /// </summary>
        private void _applyLifesteal(object source, float damageDealt, Dictionary<string, object> parms)
        {
            float lifestealPercent = _getFloat(parms, "lifesteal_percent", 0.15f);
            float healAmount = damageDealt * lifestealPercent;
            _healTarget(source, healAmount);
            LogDebug?.Invoke(
                $"Lifesteal: {healAmount:F1} HP to {_getName(source)} " +
                $"({lifestealPercent * 100f:F0}% of {damageDealt:F1} damage)"
            );
        }

        /// <summary>
        /// Apply knockback: push target away from source as smooth forced movement.
        /// Sets knockback velocity on target for duration-based movement.
        /// Default distance=2.0, duration=0.5s.
        /// </summary>
        private void _applyKnockback(object source, object target, Dictionary<string, object> parms)
        {
            float knockbackDistance = _getFloat(parms, "knockback_distance", 2f);
            float knockbackDuration = _getFloat(parms, "knockback_duration", 0.5f);

            GamePosition sourcePos = _getPosition(source);
            GamePosition targetPos = _getPosition(target);

            if (sourcePos == GamePosition.Zero && targetPos == GamePosition.Zero)
            {
                LogWarning?.Invoke("Cannot apply knockback: missing position");
                return;
            }

            // Calculate knockback direction (away from source)
            float dx = targetPos.X - sourcePos.X;
            float dz = targetPos.Z - sourcePos.Z;

            // Normalize direction
            float distance = MathF.Sqrt(dx * dx + dz * dz);
            if (distance < 0.1f)
            {
                // Too close, use default direction
                dx = 1f;
                dz = 0f;
            }
            else
            {
                dx /= distance;
                dz /= distance;
            }

            // Calculate velocity: distance / time
            float velocityMagnitude = knockbackDistance / knockbackDuration;
            float velocityX = dx * velocityMagnitude;
            float velocityZ = dz * velocityMagnitude;

            // Apply knockback velocity to target
            if (_setFloatProp(target, "KnockbackVelocityX", velocityX) &&
                _setFloatProp(target, "KnockbackVelocityZ", velocityZ) &&
                _setFloatProp(target, "KnockbackDurationRemaining", knockbackDuration))
            {
                LogDebug?.Invoke(
                    $"Knockback: {_getName(target)} - velocity ({velocityX:F1}, {velocityZ:F1}) " +
                    $"for {knockbackDuration:F2}s"
                );
            }
            else
            {
                LogWarning?.Invoke("Target has no knockback velocity fields - cannot apply smooth knockback");
            }
        }

        /// <summary>
        /// Apply pull: move target toward source.
        /// Does not pull past the source position.
        /// Default distance=2.0 (or pull_strength).
        /// </summary>
        private void _applyPull(object source, object target, Dictionary<string, object> parms)
        {
            float pullDistance = parms.ContainsKey("pull_distance")
                ? _getFloat(parms, "pull_distance", 2f)
                : _getFloat(parms, "pull_strength", 2f);

            GamePosition sourcePos = _getPosition(source);
            GamePosition targetPos = _getPosition(target);

            // Calculate pull direction (toward source)
            float dx = sourcePos.X - targetPos.X;
            float dz = sourcePos.Z - targetPos.Z;

            float distance = MathF.Sqrt(dx * dx + dz * dz);
            if (distance < 0.1f)
                return; // Already at source, no pull needed

            // Don't pull past the source
            float actualPull = MathF.Min(pullDistance, distance);

            dx /= distance;
            dz /= distance;

            // Calculate new position
            float newX = targetPos.X + dx * actualPull;
            float newZ = targetPos.Z + dz * actualPull;

            // Apply pull by setting position directly
            if (_setPosition(target, new GamePosition(newX, targetPos.Y, newZ)))
            {
                LogDebug?.Invoke($"Pull: {_getName(target)} pulled {actualPull:F1} tiles");
            }
            else
            {
                LogWarning?.Invoke("Target has no position attribute for pull");
            }
        }

        /// <summary>
        /// Apply execute mechanic: bonus damage when target HP is below threshold.
        /// Default threshold=20% HP, bonus=2.0x multiplier.
        /// </summary>
        private void _applyExecute(object source, object target, EffectConfig config, float magnitudeMult)
        {
            float thresholdHp = _getFloat(config.Params, "threshold_hp", 0.2f);
            float bonusDamage = _getFloat(config.Params, "bonus_damage", 2f);

            // Check if target has HP tracking
            float currentHealth = _getFloatProp(target, "CurrentHealth", -1f);
            float maxHealth = _getFloatProp(target, "MaxHealth", -1f);

            if (currentHealth < 0 || maxHealth <= 0)
                return;

            float hpPercent = currentHealth / maxHealth;

            if (hpPercent <= thresholdHp)
            {
                // Target is below threshold - apply execute bonus damage
                float baseDmg = config.BaseDamage * magnitudeMult;
                float executeDamage = baseDmg * (bonusDamage - 1f); // Bonus portion only

                _damageTarget(target, executeDamage, "execute");

                LogDebug?.Invoke(
                    $"Execute: {_getName(target)} below {thresholdHp * 100f:F0}% HP, " +
                    $"+{executeDamage:F1} bonus damage ({bonusDamage}x)"
                );
            }
        }

        /// <summary>
        /// Apply teleport: instant movement to target position.
        /// Default range=10.0, type="targeted".
        /// </summary>
        private void _applyTeleport(object source, object target, Dictionary<string, object> parms)
        {
            float teleportRange = _getFloat(parms, "teleport_range", 10f);
            string teleportType = _getString(parms, "teleport_type", "targeted");

            GamePosition sourcePos = _getPosition(source);
            if (sourcePos == GamePosition.Zero)
                return;

            GamePosition targetPos;
            if (teleportType == "targeted" && target != null)
            {
                targetPos = _getPosition(target);
            }
            else
            {
                // Forward teleport not implemented
                LogWarning?.Invoke("Forward teleport not implemented yet");
                return;
            }

            // Calculate distance
            float dx = targetPos.X - sourcePos.X;
            float dz = targetPos.Z - sourcePos.Z;
            float distance = MathF.Sqrt(dx * dx + dz * dz);

            // Check range
            if (distance > teleportRange)
            {
                LogDebug?.Invoke($"Teleport failed: target too far ({distance:F1} > {teleportRange:F1})");
                return;
            }

            // Apply teleport
            if (_setPosition(source, targetPos))
            {
                LogDebug?.Invoke($"Teleport: {_getName(source)} teleported {distance:F1} tiles");
            }
            else
            {
                LogWarning?.Invoke("Source has no position attribute for teleport");
            }
        }

        /// <summary>
        /// Apply dash: rapid movement toward target.
        /// Uses knockback velocity system for smooth movement, or instant fallback.
        /// Default distance=5.0, speed=20.0.
        /// </summary>
        private void _applyDash(object source, object target, Dictionary<string, object> parms)
        {
            float dashDistance = _getFloat(parms, "dash_distance", 5f);
            float dashSpeed = _getFloat(parms, "dash_speed", 20f);

            GamePosition sourcePos = _getPosition(source);

            if (target == null)
            {
                LogWarning?.Invoke("Dash without target not implemented yet");
                return;
            }

            GamePosition targetPos = _getPosition(target);

            // Calculate direction toward target
            float dx = targetPos.X - sourcePos.X;
            float dz = targetPos.Z - sourcePos.Z;

            float distance = MathF.Sqrt(dx * dx + dz * dz);
            if (distance == 0)
                return;

            float normDx = dx / distance;
            float normDz = dz / distance;

            // Actual dash distance (capped)
            float actualDash = MathF.Min(dashDistance, distance);

            // Calculate duration from speed
            float dashDuration = actualDash / dashSpeed;

            // Try to apply via velocity system (smooth movement)
            if (_setFloatProp(source, "KnockbackVelocityX", normDx * dashSpeed) &&
                _setFloatProp(source, "KnockbackVelocityZ", normDz * dashSpeed) &&
                _setFloatProp(source, "KnockbackDurationRemaining", dashDuration))
            {
                LogDebug?.Invoke($"Dash: {_getName(source)} dashing {actualDash:F1} tiles");
            }
            else
            {
                // Fallback to instant movement
                float newX = sourcePos.X + normDx * actualDash;
                float newZ = sourcePos.Z + normDz * actualDash;
                _setPosition(source, new GamePosition(newX, sourcePos.Y, newZ));
                LogDebug?.Invoke($"Dash (instant): {_getName(source)} moved {actualDash:F1} tiles");
            }
        }

        /// <summary>
        /// Apply phase: temporary intangibility via status effect.
        /// Default duration=2.0, can_pass_walls=false.
        /// </summary>
        private void _applyPhase(object source, Dictionary<string, object> parms)
        {
            float phaseDuration = _getFloat(parms, "phase_duration", 2f);
            bool canPassWalls = _getBool(parms, "can_pass_walls", false);

            // Apply phase as a status effect
            var statusManagerProp = source?.GetType().GetProperty("StatusManager");
            if (statusManagerProp != null)
            {
                object statusManager = statusManagerProp.GetValue(source);
                if (statusManager != null)
                {
                    var phaseParams = new Dictionary<string, object>
                    {
                        ["duration"] = (double)phaseDuration,
                        ["can_pass_walls"] = canPassWalls
                    };

                    var applyMethod = statusManager.GetType().GetMethod("ApplyStatus",
                        new[] { typeof(string), typeof(Dictionary<string, object>) });

                    if (applyMethod != null)
                    {
                        applyMethod.Invoke(statusManager, new object[] { "phase", phaseParams });
                        LogDebug?.Invoke(
                            $"Phase: {_getName(source)} is intangible for {phaseDuration:F1}s" +
                            (canPassWalls ? " (can pass walls)" : "")
                        );
                        return;
                    }
                }
            }

            LogWarning?.Invoke("Source has no StatusManager for phase");
        }

        // ====================================================================
        // Low-Level Damage/Heal
        // ====================================================================

        /// <summary>
        /// Apply damage to a target entity.
        /// Tries TakeDamage method (with context overloads), then falls back to
        /// decrementing CurrentHealth directly.
        /// </summary>
        private void _damageTarget(object target, float damage, string damageType)
        {
            if (target == null) return;

            var type = target.GetType();

            // Try TakeDamage(float, string, source, tags, context) - enhanced signature
            var enhancedMethod = type.GetMethod("TakeDamage", new[]
            {
                typeof(float), typeof(string), typeof(object), typeof(List<string>), typeof(EffectContext)
            });
            if (enhancedMethod != null)
            {
                enhancedMethod.Invoke(target, new object[]
                {
                    damage, damageType, _currentSource, _currentTags, _currentContext
                });
                return;
            }

            // Try TakeDamage(float, string) - basic signature
            var basicMethod = type.GetMethod("TakeDamage", new[] { typeof(float), typeof(string) });
            if (basicMethod != null)
            {
                basicMethod.Invoke(target, new object[] { damage, damageType });
                return;
            }

            // Fallback: decrement CurrentHealth directly
            var healthProp = type.GetProperty("CurrentHealth");
            if (healthProp != null && healthProp.CanWrite)
            {
                float currentHealth = Convert.ToSingle(healthProp.GetValue(target));
                currentHealth -= damage;
                if (currentHealth < 0) currentHealth = 0;
                healthProp.SetValue(target, currentHealth);

                // Set IsAlive = false if health reached 0
                if (currentHealth <= 0)
                {
                    var aliveProp = type.GetProperty("IsAlive");
                    if (aliveProp != null && aliveProp.CanWrite)
                    {
                        aliveProp.SetValue(target, false);
                    }
                }
                return;
            }

            LogWarning?.Invoke($"Cannot apply damage to {type.Name} - no damage method");
        }

        /// <summary>
        /// Apply healing to a target entity.
        /// Tries Heal method, then falls back to incrementing Health/CurrentHealth
        /// (capped at MaxHealth).
        /// </summary>
        private void _healTarget(object target, float healing)
        {
            if (target == null) return;

            var type = target.GetType();

            // Try Heal(float) method
            var healMethod = type.GetMethod("Heal", new[] { typeof(float) });
            if (healMethod != null)
            {
                healMethod.Invoke(target, new object[] { healing });
                return;
            }

            // Try Health + MaxHealth properties (Character/Player style)
            var healthProp = type.GetProperty("Health");
            var maxHealthProp = type.GetProperty("MaxHealth");
            if (healthProp != null && healthProp.CanWrite && maxHealthProp != null)
            {
                float health = Convert.ToSingle(healthProp.GetValue(target));
                float maxHealth = Convert.ToSingle(maxHealthProp.GetValue(target));
                health = MathF.Min(health + healing, maxHealth);
                healthProp.SetValue(target, health);
                return;
            }

            // Try CurrentHealth + MaxHealth properties (Enemy style)
            var curHealthProp = type.GetProperty("CurrentHealth");
            if (curHealthProp != null && curHealthProp.CanWrite && maxHealthProp != null)
            {
                float currentHealth = Convert.ToSingle(curHealthProp.GetValue(target));
                float maxHealth = Convert.ToSingle(maxHealthProp.GetValue(target));
                currentHealth = MathF.Min(currentHealth + healing, maxHealth);
                curHealthProp.SetValue(target, currentHealth);
                return;
            }

            LogWarning?.Invoke($"Cannot apply healing to {type.Name} - no healing method");
        }

        // ====================================================================
        // Position Helpers
        // ====================================================================

        /// <summary>
        /// Get GamePosition from an entity. Delegates to TargetFinder.GetPosition.
        /// </summary>
        private GamePosition _getPosition(object entity)
        {
            return TargetFinder.GetPosition(entity);
        }

        /// <summary>
        /// Set the Position property on an entity to a new GamePosition.
        /// Returns true if successful.
        /// </summary>
        private bool _setPosition(object entity, GamePosition newPos)
        {
            if (entity == null) return false;

            var prop = entity.GetType().GetProperty("Position");
            if (prop != null && prop.CanWrite)
            {
                // If the property type is GamePosition
                if (prop.PropertyType == typeof(GamePosition))
                {
                    prop.SetValue(entity, newPos);
                    return true;
                }

                // If the property type has X, Y, Z setters
                object posObj = prop.GetValue(entity);
                if (posObj != null)
                {
                    var posType = posObj.GetType();
                    var xProp = posType.GetProperty("X");
                    var yProp = posType.GetProperty("Y");
                    var zProp = posType.GetProperty("Z");
                    if (xProp?.CanWrite == true && zProp?.CanWrite == true)
                    {
                        xProp.SetValue(posObj, newPos.X);
                        yProp?.SetValue(posObj, newPos.Y);
                        zProp.SetValue(posObj, newPos.Z);
                        return true;
                    }
                }
            }

            return false;
        }

        // ====================================================================
        // Reflection Helpers
        // ====================================================================

        /// <summary>Get a string property value from an entity via reflection.</summary>
        private static string _getStringProp(object entity, string propName)
        {
            if (entity == null) return null;
            var prop = entity.GetType().GetProperty(propName);
            return prop?.GetValue(entity)?.ToString();
        }

        /// <summary>Get a float property value from an entity via reflection. Returns defaultValue if not found.</summary>
        private static float _getFloatProp(object entity, string propName, float defaultValue)
        {
            if (entity == null) return defaultValue;
            var prop = entity.GetType().GetProperty(propName);
            if (prop == null) return defaultValue;
            try { return Convert.ToSingle(prop.GetValue(entity)); }
            catch { return defaultValue; }
        }

        /// <summary>Set a float property on an entity via reflection. Returns true if successful.</summary>
        private static bool _setFloatProp(object entity, string propName, float value)
        {
            if (entity == null) return false;
            var prop = entity.GetType().GetProperty(propName);
            if (prop == null || !prop.CanWrite) return false;
            try
            {
                prop.SetValue(entity, value);
                return true;
            }
            catch { return false; }
        }

        /// <summary>Get name from entity for logging. Tries Name property, falls back to type name.</summary>
        private static string _getName(object entity)
        {
            if (entity == null) return "null";
            var prop = entity.GetType().GetProperty("Name");
            return prop?.GetValue(entity)?.ToString() ?? entity.GetType().Name;
        }

        // ====================================================================
        // Dictionary Parameter Helpers
        // ====================================================================

        private static float _getFloat(Dictionary<string, object> dict, string key, float defaultValue)
        {
            if (dict == null || !dict.TryGetValue(key, out object val))
                return defaultValue;
            return _convertToFloat(val, defaultValue);
        }

        private static string _getString(Dictionary<string, object> dict, string key, string defaultValue)
        {
            if (dict == null || !dict.TryGetValue(key, out object val))
                return defaultValue;
            return val?.ToString() ?? defaultValue;
        }

        private static bool _getBool(Dictionary<string, object> dict, string key, bool defaultValue)
        {
            if (dict == null || !dict.TryGetValue(key, out object val))
                return defaultValue;
            return _convertToBool(val, defaultValue);
        }

        private static float _convertToFloat(object val, float defaultValue = 0f)
        {
            if (val is float f) return f;
            if (val is double d) return (float)d;
            if (val is int i) return i;
            if (val is long l) return l;
            if (val is decimal dec) return (float)dec;
            if (val is string s && float.TryParse(s,
                System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out float parsed))
                return parsed;
            return defaultValue;
        }

        private static bool _convertToBool(object val, bool defaultValue = false)
        {
            if (val is bool b) return b;
            if (val is string s)
            {
                if (s.Equals("true", StringComparison.OrdinalIgnoreCase)) return true;
                if (s.Equals("false", StringComparison.OrdinalIgnoreCase)) return false;
            }
            if (val is int i) return i != 0;
            if (val is long l) return l != 0;
            return defaultValue;
        }
    }

    // ====================================================================
    // Convenience Function (mirrors Python module-level execute_effect)
    // ====================================================================

    /// <summary>
    /// Static convenience wrapper around EffectExecutor for simple effect execution.
    /// Mirrors Python: execute_effect(source, target, tags, params, entities).
    /// </summary>
    public static class Effects
    {
        private static EffectExecutor _executor;
        private static readonly object _lock = new object();

        /// <summary>
        /// Execute an effect using a shared executor instance.
        /// Thread-safe lazy initialization.
        /// </summary>
        public static EffectContext ExecuteEffect(object source, object target,
                                                   List<string> tags, Dictionary<string, object> effectParams,
                                                   List<object> availableEntities = null)
        {
            if (_executor == null)
            {
                lock (_lock)
                {
                    if (_executor == null)
                    {
                        _executor = new EffectExecutor();
                    }
                }
            }
            return _executor.ExecuteEffect(source, target, tags, effectParams, availableEntities);
        }

        /// <summary>
        /// Reset the shared executor (for testing only).
        /// </summary>
        public static void ResetInstance()
        {
            lock (_lock)
            {
                _executor = null;
            }
        }
    }
}
