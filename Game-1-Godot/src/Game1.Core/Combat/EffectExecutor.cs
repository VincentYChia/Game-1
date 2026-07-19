using Game1.Core.Tags;
using Game1.Core.World;

namespace Game1.Core.Combat;

/// <summary>Runtime result mirroring core/effect_context.py EffectContext.</summary>
public sealed class EffectContextResult
{
    public ICombatEntity? Source;
    public object? PrimaryTarget;
    public required EffectConfig Config;
    public List<ICombatEntity> Targets = new();
}

/// <summary>
/// Port of core/effect_executor.py — applies tag-parsed effects to targets:
/// geometry targeting, damage (crit / context behavior / enemy defense /
/// auto-apply status), healing, status effects, and special mechanics.
/// Python uses the global `random` module; RNG injected here for replay.
/// </summary>
public sealed class EffectExecutor
{
    private readonly TagRegistry _registry;
    private readonly TagParser _parser;
    private readonly TargetFinder _targetFinder = new();
    private readonly Func<double> _random;

    private ICombatEntity? _currentSource;
    private List<string> _currentTags = new();

    public EffectExecutor(TagRegistry registry, Func<double> random)
    {
        _registry = registry;
        _parser = new TagParser(registry);
        _random = random;
    }

    private static double Num(object? v, double dflt = 0.0) => TagParser.Num(v, dflt);

    private static bool Truthy(object? v) => v switch
    {
        null => false,
        bool b => b,
        double d => d != 0,
        long l => l != 0,
        string s => s.Length > 0,
        System.Collections.ICollection c => c.Count > 0,
        _ => true,
    };

    public EffectContextResult ExecuteEffect(ICombatEntity? source, object? primaryTarget,
                                             List<string> tags,
                                             Dictionary<string, object?> params_,
                                             List<ICombatEntity>? availableEntities = null)
    {
        var config = _parser.Parse(tags, params_);

        var context = new EffectContextResult
        {
            Source = source,
            PrimaryTarget = primaryTarget,
            Config = config,
        };

        availableEntities ??= new List<ICombatEntity>();

        var targets = _targetFinder.FindTargets(
            config.GeometryTag, source, primaryTarget,
            config.Params, config.Context, availableEntities);

        context.Targets = targets;

        _currentSource = source;
        _currentTags = tags;

        for (var i = 0; i < targets.Count; i++)
        {
            var target = targets[i];
            var magnitudeMult = CalculateMagnitudeMultiplier(config, i);

            if (config.BaseDamage > 0)
                ApplyDamage(source, target, config, magnitudeMult);

            if (config.BaseHealing > 0)
                ApplyHealing(target, config, magnitudeMult);

            ApplyStatusEffects(target, config);

            ApplySpecialMechanics(source, target, config, magnitudeMult);
        }

        return context;
    }

    private static double CalculateMagnitudeMultiplier(EffectConfig config, int targetIndex)
    {
        if (config.GeometryTag == "chain")
        {
            var falloff = Num(config.Params.GetValueOrDefault("chain_falloff"), 0.3);
            return Math.Pow(1.0 - falloff, targetIndex);
        }
        if (config.GeometryTag == "pierce")
        {
            var falloff = Num(config.Params.GetValueOrDefault("pierce_falloff"), 0.1);
            return Math.Pow(1.0 - falloff, targetIndex);
        }
        return 1.0;
    }

    private void ApplyDamage(ICombatEntity? source, ICombatEntity target,
                             EffectConfig config, double magnitudeMult)
    {
        var baseDamage = config.BaseDamage * magnitudeMult;

        var critMultiplier = 1.0;
        if (config.SpecialTags.Contains("critical"))
        {
            var critChance = Num(config.Params.GetValueOrDefault("crit_chance"), 0.15);
            var critMultiplierParam = Num(config.Params.GetValueOrDefault("crit_multiplier"), 2.0);
            if (_random() < critChance)
                critMultiplier = critMultiplierParam;
        }

        foreach (var damageTag in config.DamageTags)
        {
            var damage = baseDamage * critMultiplier;

            var tagDef = _registry.GetDefinition(damageTag);
            if (tagDef is not null && tagDef.ContextBehavior.Count > 0)
            {
                var targetCategory = target.Category;
                if (targetCategory is not null
                    && tagDef.ContextBehavior.TryGetValue(targetCategory, out var behaviorObj)
                    && behaviorObj is Dictionary<string, object?> behavior)
                {
                    if (behavior.TryGetValue("damage_multiplier", out var dm))
                        damage *= Num(dm, 1.0);

                    if (Truthy(behavior.GetValueOrDefault("converts_to_healing")))
                    {
                        HealTarget(target, damage);
                        return;   // Python `return` — exits the WHOLE method
                    }
                }
            }

            // F5 conformance: per-target enemy defense when the caller opts in
            if (Truthy(config.Params.GetValueOrDefault("_apply_enemy_defense")))
            {
                var targetDefense = target.DefinitionDefense;
                if (targetDefense > 0)
                {
                    var armorPen = Num(config.Params.GetValueOrDefault("_armor_penetration"), 0.0);
                    var effectiveDefense = targetDefense * (1.0 - armorPen);
                    var reduction = Math.Min(0.75, effectiveDefense * 0.01);
                    damage *= 1.0 - reduction;
                }
            }

            DamageTarget(target, damage, damageTag);

            if (tagDef?.AutoApplyStatus is not null && tagDef.AutoApplyChance > 0)
            {
                if (_random() < tagDef.AutoApplyChance)
                {
                    var statusTag = tagDef.AutoApplyStatus;
                    var statusParams = _registry.GetDefaultParams(statusTag);
                    ApplySingleStatus(target, statusTag, statusParams);
                }
            }
        }
    }

    private void ApplyHealing(ICombatEntity target, EffectConfig config, double magnitudeMult)
    {
        HealTarget(target, config.BaseHealing * magnitudeMult);
    }

    private void ApplyStatusEffects(ICombatEntity target, EffectConfig config)
    {
        foreach (var statusTag in config.StatusTags)
        {
            var statusParams = new Dictionary<string, object?>();
            var tagDef = _registry.GetDefinition(statusTag);
            if (tagDef is not null)
            {
                statusParams = new Dictionary<string, object?>(tagDef.DefaultParams);
                foreach (var paramKey in statusParams.Keys.ToList())
                    if (config.Params.ContainsKey(paramKey))
                        statusParams[paramKey] = config.Params[paramKey];
            }
            ApplySingleStatus(target, statusTag, statusParams);
        }
    }

    private void ApplySingleStatus(ICombatEntity target, string statusTag,
                                   Dictionary<string, object?> statusParams,
                                   ICombatEntity? source = null)
    {
        var tagDef = _registry.GetDefinition(statusTag);
        if (tagDef is not null && tagDef.Immunity.Count > 0)
        {
            var targetCategory = target.Category;
            if (targetCategory is not null && tagDef.Immunity.Contains(targetCategory))
                return;
        }

        if (target.HasStatusManager)
            target.ApplyStatus(statusTag, statusParams, source);
    }

    private void ApplySpecialMechanics(ICombatEntity? source, ICombatEntity target,
                                       EffectConfig config, double magnitudeMult)
    {
        foreach (var specialTag in config.SpecialTags)
        {
            if (specialTag is "lifesteal" or "vampiric")
                ApplyLifesteal(source, config.BaseDamage * magnitudeMult, config.Params);
            else if (specialTag == "knockback")
                ApplyKnockback(source, target, config.Params);
            else if (specialTag == "pull")
                ApplyPull(source, target, config.Params);
            else if (specialTag == "execute")
                ApplyExecute(target, config, magnitudeMult);
            else if (specialTag == "critical")
            {
                // handled in ApplyDamage
            }
            else if (specialTag is "teleport" or "blink")
                ApplyTeleport(source, target, config.Params);
            else if (specialTag is "dash" or "charge")
                ApplyDash(source, target, config.Params);
            else if (specialTag is "phase" or "ethereal" or "intangible")
                ApplyPhase(source, config.Params);
        }
    }

    private void ApplyLifesteal(ICombatEntity? source, double damageDealt,
                                Dictionary<string, object?> params_)
    {
        var lifestealPercent = Num(params_.GetValueOrDefault("lifesteal_percent"), 0.15);
        if (source is not null)
            HealTarget(source, damageDealt * lifestealPercent);
    }

    private static Position? EntityPosition(ICombatEntity? entity)
    {
        if (entity is null) return null;
        return entity.GetPosition();
    }

    /// <summary>combat_manager.py _apply_weapon_enchantment_effects calls the
    /// executor's private _apply_knockback directly for knockback enchants.</summary>
    public void ApplyKnockbackDirect(ICombatEntity? source, ICombatEntity target,
                                     Dictionary<string, object?> params_)
        => ApplyKnockback(source, target, params_);

    private void ApplyKnockback(ICombatEntity? source, ICombatEntity target,
                                Dictionary<string, object?> params_)
    {
        var knockbackDistance = Num(params_.GetValueOrDefault("knockback_distance"), 2.0);
        var knockbackDuration = Num(params_.GetValueOrDefault("knockback_duration"), 0.5);

        var sourcePos = EntityPosition(source);
        var targetPos = EntityPosition(target);
        if (sourcePos is null || targetPos is null) return;

        var dx = targetPos.Value.X - sourcePos.Value.X;
        var dy = targetPos.Value.Y - sourcePos.Value.Y;

        var distance = Math.Sqrt(dx * dx + dy * dy);
        if (distance < 0.1)
        {
            dx = 1.0;
            dy = 0.0;
        }
        else
        {
            dx /= distance;
            dy /= distance;
        }

        var velocityMagnitude = knockbackDistance / knockbackDuration;
        if (target.HasKnockbackFields)
            target.SetKnockback(dx * velocityMagnitude, dy * velocityMagnitude,
                                knockbackDuration);
    }

    private void ApplyPull(ICombatEntity? source, ICombatEntity target,
                           Dictionary<string, object?> params_)
    {
        var pullDistance = Num(
            params_.GetValueOrDefault("pull_distance"),
            Num(params_.GetValueOrDefault("pull_strength"), 2.0));

        var sourcePos = EntityPosition(source);
        var targetPos = EntityPosition(target);
        if (sourcePos is null || targetPos is null) return;

        var dx = sourcePos.Value.X - targetPos.Value.X;
        var dy = sourcePos.Value.Y - targetPos.Value.Y;

        var distance = Math.Sqrt(dx * dx + dy * dy);
        if (distance < 0.1) return;

        var actualPull = Math.Min(pullDistance, distance);
        dx /= distance;
        dy /= distance;

        target.SetPositionXY(targetPos.Value.X + dx * actualPull,
                             targetPos.Value.Y + dy * actualPull);
    }

    private void ApplyExecute(ICombatEntity target, EffectConfig config,
                              double magnitudeMult)
    {
        var thresholdHp = Num(config.Params.GetValueOrDefault("threshold_hp"), 0.2);
        var bonusDamage = Num(config.Params.GetValueOrDefault("bonus_damage"), 2.0);

        if (!target.HasCurrentHealth || !target.HasMaxHealth) return;

        var hpPercent = target.MaxHealth > 0
            ? target.CurrentHealth / target.MaxHealth
            : 0.0;

        if (hpPercent <= thresholdHp)
        {
            var baseDamage = config.BaseDamage * magnitudeMult;
            var executeDamage = baseDamage * (bonusDamage - 1.0);
            DamageTarget(target, executeDamage, "execute");
        }
    }

    private void ApplyTeleport(ICombatEntity? source, ICombatEntity? target,
                               Dictionary<string, object?> params_)
    {
        var teleportRange = Num(params_.GetValueOrDefault("teleport_range"), 10.0);
        var teleportType = params_.GetValueOrDefault("teleport_type") as string ?? "targeted";

        var sourcePos = EntityPosition(source);
        if (sourcePos is null) return;

        Position targetPos;
        if (teleportType == "targeted" && target is not null)
            targetPos = target.GetPosition();
        else
            return;   // forward teleport not implemented in Python either

        var dx = targetPos.X - sourcePos.Value.X;
        var dy = targetPos.Y - sourcePos.Value.Y;
        var distance = Math.Sqrt(dx * dx + dy * dy);
        if (distance > teleportRange) return;

        source!.SetPositionXY(targetPos.X, targetPos.Y);
    }

    private void ApplyDash(ICombatEntity? source, ICombatEntity? target,
                           Dictionary<string, object?> params_)
    {
        var dashDistance = Num(params_.GetValueOrDefault("dash_distance"), 5.0);
        var dashSpeed = Num(params_.GetValueOrDefault("dash_speed"), 20.0);

        var sourcePos = EntityPosition(source);
        if (sourcePos is null) return;
        if (target is null) return;

        var targetPos = target.GetPosition();
        var dx = targetPos.X - sourcePos.Value.X;
        var dy = targetPos.Y - sourcePos.Value.Y;

        var distance = Math.Sqrt(dx * dx + dy * dy);
        if (distance == 0) return;

        var normDx = dx / distance;
        var normDy = dy / distance;
        var actualDash = Math.Min(dashDistance, distance);
        var newX = sourcePos.Value.X + normDx * actualDash;
        var newY = sourcePos.Value.Y + normDy * actualDash;
        var dashDuration = actualDash / dashSpeed;

        if (source!.HasKnockbackFields)
        {
            source.SetKnockback(normDx * dashSpeed, normDy * dashSpeed, dashDuration);
        }
        else
        {
            source.SetPositionXY(newX, newY);
        }
    }

    private void ApplyPhase(ICombatEntity? source, Dictionary<string, object?> params_)
    {
        var phaseDuration = Num(params_.GetValueOrDefault("phase_duration"), 2.0);
        var canPassWalls = Truthy(params_.GetValueOrDefault("can_pass_walls"));

        if (source is not null && source.HasStatusManager)
        {
            var phaseParams = new Dictionary<string, object?>
            {
                ["duration"] = phaseDuration,
                ["can_pass_walls"] = canPassWalls,
            };
            source.ApplyStatus("phase", phaseParams, source);
        }
    }

    private void DamageTarget(ICombatEntity target, double damage, string damageType)
    {
        if (target.SupportsTakeDamage)
        {
            target.TakeDamage(damage, damageType, _currentSource, _currentTags);
        }
        else if (target.HasCurrentHealth)
        {
            target.CurrentHealth -= damage;
            if (target.CurrentHealth < 0)
            {
                target.CurrentHealth = 0;
                if (target.HasIsAlive)
                    target.Alive = false;
            }
        }
    }

    private void HealTarget(ICombatEntity target, double healing)
    {
        if (target.SupportsHeal)
        {
            target.Heal(healing);
        }
        else if (target.HasHealthField && target.HasMaxHealth)
        {
            target.Health = Math.Min(target.Health + healing, target.MaxHealth);
        }
        else if (target.HasCurrentHealth && target.HasMaxHealth)
        {
            target.CurrentHealth = Math.Min(target.CurrentHealth + healing, target.MaxHealth);
        }
    }
}
