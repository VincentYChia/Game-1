using Game1.Core.World;

namespace Game1.Core.Combat;

public enum AiState
{
    Idle, Wander, Patrol, Guard, Chase, Attack, Flee, Dead, Corpse,
}

/// <summary>
/// Port of Combat/enemy.py Enemy runtime — AI state machine (idle/wander/
/// patrol/guard/chase/attack/flee), movement with chunk clamping + collision
/// sliding + safe-zone exclusion, knockback, phased attacks (windup/active/
/// recovery), damage/flee/death, loot, and special-ability gating.
/// RNG injected (Python uses the global random module). Status-manager
/// interplay (immobilize/silence) enters via injected hooks; the status
/// system itself was certified in P2.
/// </summary>
public sealed class EnemyRuntime
{
    public const double ChunkSize = 16.0;   // core/config.py Config.CHUNK_SIZE

    public EnemyDefinition Definition;
    public double[] Position;
    public double[] SpawnPosition;
    public (long X, long Y) ChunkCoords;

    public double CurrentHealth;
    public double MaxHealth;
    public bool IsBoss;

    public AiState State;
    public double[]? TargetPosition;
    public bool LastDamagedByPlayer;

    public double WanderTimer;
    public double WanderCooldown;

    public double KnockbackVelocityX;
    public double KnockbackVelocityY;
    public double KnockbackDurationRemaining;

    public double AttackCooldown;
    public bool InCombat;

    public bool IsAlive = true;
    public double TimeSinceDeath;
    public double CorpseLifetime = 30.0;

    public string? Category;
    public double FacingAngle;
    public double HurtboxRadius;

    public double AttackAnimTimer;
    public double AttackAnimDuration = 1.0;
    public double AttackAnimAngle;
    public List<string> AttackAnimTags = new();
    public bool AttackAnimLunge;

    // Phased attack
    public string AttackPhase = "idle";
    public double AttackPhaseTimer;
    public (double X, double Y)? AttackTargetPos;
    public Dictionary<string, object?>? AttackPendingData;
    public double AttackWindupMs;
    public double AttackActiveMs;
    public double AttackRecoveryMs;
    public double AttackArcDegrees = 80.0;
    public double AttackRadius = 1.0;
    public string AttackShape = "arc";
    public bool AttackScreenShake;
    public double AttackDamageMult = 1.0;

    public readonly Dictionary<string, double> AbilityCooldowns = new();
    public readonly Dictionary<string, long> AbilityUsesThisFight = new();
    private readonly List<string> _abilityOrder = new();

    private readonly PythonRandom _rng;
    public Func<Position, bool>? IsWalkable;      // world_system.is_walkable
    public Func<bool> IsImmobilized = () => false;
    public Func<bool> IsSilenced = () => false;

    private double _aggroMultiplier = 1.0;
    private double _speedMultiplier = 1.0;
    private (double X, double Y)? _safeZoneCenter;
    private double _safeZoneRadius;

    public EnemyRuntime(EnemyDefinition definition, (double X, double Y) position,
                        (long X, long Y) chunkCoords, PythonRandom rng)
    {
        Definition = definition;
        _rng = rng;
        Position = new[] { position.X, position.Y };
        SpawnPosition = new[] { position.X, position.Y };
        ChunkCoords = chunkCoords;

        CurrentHealth = definition.MaxHealth;
        MaxHealth = definition.MaxHealth;
        IsBoss = definition.Behavior.ToLowerInvariant().Contains("boss");

        State = GetInitialState();
        WanderCooldown = _rng.Uniform(2.0, 5.0);   // draw order matches __init__

        Category = definition.Category;
        HurtboxRadius = definition.HurtboxRadius;

        foreach (var ability in definition.SpecialAbilities)
        {
            AbilityCooldowns[ability.AbilityId] = 0.0;
            AbilityUsesThisFight[ability.AbilityId] = 0;
            _abilityOrder.Add(ability.AbilityId);
        }
    }

    private AiState GetInitialState() => Definition.Ai.DefaultState switch
    {
        "idle" => AiState.Idle,
        "wander" => AiState.Wander,
        "patrol" => AiState.Patrol,
        "guard" => AiState.Guard,
        _ => AiState.Idle,
    };

    public double DistanceTo((double X, double Y) position)
    {
        var dx = Position[0] - position.X;
        var dy = Position[1] - position.Y;
        return Math.Sqrt(dx * dx + dy * dy);
    }

    /// <summary>enemy.py take_damage — returns true if the enemy died.</summary>
    public bool TakeDamage(double damage, string damageType = "physical",
                           bool fromPlayer = true)
    {
        CurrentHealth -= damage;
        InCombat = true;

        if (fromPlayer)
        {
            LastDamagedByPlayer = true;
            if (Definition.Ai.AggroOnDamage && State != AiState.Dead)
                State = AiState.Chase;
        }

        if (CurrentHealth <= 0)
        {
            CurrentHealth = 0;
            IsAlive = false;
            State = AiState.Dead;
            return true;
        }

        var healthPercent = CurrentHealth / MaxHealth;
        if (healthPercent <= Definition.Ai.FleeAtHealth && State != AiState.Flee)
            State = AiState.Flee;

        return false;
    }

    public List<(string MaterialId, long Quantity)> GenerateLoot() =>
        Definition.GenerateLoot(_rng);

    public void UpdateKnockback(double dt)
    {
        if (KnockbackDurationRemaining > 0)
        {
            Position[0] += KnockbackVelocityX * dt;
            Position[1] += KnockbackVelocityY * dt;
            (Position[0], Position[1]) = ClampToChunkBounds(Position[0], Position[1]);

            KnockbackDurationRemaining -= dt;
            if (KnockbackDurationRemaining <= 0)
            {
                KnockbackVelocityX = 0.0;
                KnockbackVelocityY = 0.0;
                KnockbackDurationRemaining = 0.0;
            }
        }
    }

    public void UpdateAi(double dt, (double X, double Y) playerPosition,
                         double aggroMultiplier = 1.0, double speedMultiplier = 1.0,
                         (double X, double Y)? safeZoneCenter = null,
                         double safeZoneRadius = 0.0)
    {
        _safeZoneCenter = safeZoneCenter;
        _safeZoneRadius = safeZoneRadius;

        if (!IsAlive)
        {
            if (State == AiState.Dead)
                State = AiState.Corpse;
            TimeSinceDeath += dt;
            return;
        }

        _aggroMultiplier = aggroMultiplier;
        _speedMultiplier = speedMultiplier;

        UpdateKnockback(dt);

        // (status_manager.update(dt) runs here in Python — the status system
        // lives in Progression.StatusEffects; integration lands with the
        // Character composition root)

        if (AttackCooldown > 0)
            AttackCooldown -= dt;

        if (AttackAnimTimer > 0)
            AttackAnimTimer -= dt;

        foreach (var abilityId in _abilityOrder)
            if (AbilityCooldowns[abilityId] > 0)
                AbilityCooldowns[abilityId] -= dt;

        var distToPlayer = DistanceTo(playerPosition);

        if (State is AiState.Chase or AiState.Attack)
        {
            var dx = playerPosition.X - Position[0];
            var dy = playerPosition.Y - Position[1];
            if (Math.Abs(dx) > 0.01 || Math.Abs(dy) > 0.01)
                FacingAngle = PyMath.Degrees(Math.Atan2(dy, dx));
        }

        switch (State)
        {
            case AiState.Idle: AiIdle(distToPlayer); break;
            case AiState.Wander: AiWander(dt, distToPlayer); break;
            case AiState.Patrol: AiPatrol(dt, distToPlayer); break;
            case AiState.Guard: AiGuard(dt, distToPlayer); break;
            case AiState.Chase: AiChase(dt, distToPlayer, playerPosition); break;
            case AiState.Attack: AiAttack(distToPlayer); break;
            case AiState.Flee: AiFlee(dt, distToPlayer, playerPosition); break;
        }
    }

    private double EffectiveAggro => Definition.AggroRange * _aggroMultiplier;

    private void AiIdle(double distToPlayer)
    {
        if (Definition.Ai.AggroOnProximity && distToPlayer <= EffectiveAggro)
            State = AiState.Chase;
    }

    private void AiWander(double dt, double distToPlayer)
    {
        WanderTimer += dt;

        if (WanderTimer >= WanderCooldown)
        {
            _ = _rng.Uniform(0, 6.28);   // Python draws an unused angle
            var distance = _rng.Uniform(1.0, 3.0);
            TargetPosition = new[]
            {
                SpawnPosition[0] + distance * (2 * _rng.NextDouble() - 1),
                SpawnPosition[1] + distance * (2 * _rng.NextDouble() - 1),
            };
            WanderTimer = 0;
            WanderCooldown = _rng.Uniform(2.0, 5.0);
        }

        if (TargetPosition is not null)
            MoveTowards((TargetPosition[0], TargetPosition[1]), dt);

        if (Definition.Ai.AggroOnProximity && distToPlayer <= EffectiveAggro)
            State = AiState.Chase;
    }

    private void AiPatrol(double dt, double distToPlayer)
    {
        TargetPosition ??= new[]
        {
            SpawnPosition[0] + _rng.Uniform(-5, 5),
            SpawnPosition[1] + _rng.Uniform(-5, 5),
        };

        MoveTowards((TargetPosition[0], TargetPosition[1]), dt);

        if (DistanceTo((TargetPosition[0], TargetPosition[1])) < 0.5)
        {
            TargetPosition = new[]
            {
                SpawnPosition[0] + _rng.Uniform(-5, 5),
                SpawnPosition[1] + _rng.Uniform(-5, 5),
            };
        }

        if (Definition.Ai.AggroOnProximity && distToPlayer <= EffectiveAggro)
            State = AiState.Chase;
    }

    private void AiGuard(double dt, double distToPlayer)
    {
        if (DistanceTo((SpawnPosition[0], SpawnPosition[1])) > 1.0)
            MoveTowards((SpawnPosition[0], SpawnPosition[1]), dt);

        if (Definition.Ai.AggroOnProximity && distToPlayer <= EffectiveAggro)
            State = AiState.Chase;
    }

    private void AiChase(double dt, double distToPlayer, (double X, double Y) playerPosition)
    {
        const double attackRange = 1.5;
        if (distToPlayer <= attackRange)
        {
            State = AiState.Attack;
            return;
        }

        if (distToPlayer > Definition.AggroRange * 2)
        {
            State = GetInitialState();
            TargetPosition = null;
            InCombat = false;
            return;
        }

        MoveTowards(playerPosition, dt);
    }

    private void AiAttack(double distToPlayer)
    {
        const double attackRange = 1.5;
        if (distToPlayer > attackRange * 1.5)
            State = AiState.Chase;
        // attack execution + cooldowns handled by the combat manager
    }

    private void AiFlee(double dt, double distToPlayer, (double X, double Y) playerPosition)
    {
        var dx = Position[0] - playerPosition.X;
        var dy = Position[1] - playerPosition.Y;

        var dist = Math.Sqrt(dx * dx + dy * dy);
        if (dist > 0.1)
        {
            MoveTowards((Position[0] + dx / dist * 5,
                         Position[1] + dy / dist * 5), dt);
        }

        if (distToPlayer > Definition.AggroRange * 2)
        {
            State = AiState.Wander;
            InCombat = false;
        }
    }

    /// <summary>3x3-chunk clamp centered on the spawn chunk.</summary>
    public (double X, double Y) ClampToChunkBounds(double x, double y)
    {
        var chunkMinX = (ChunkCoords.X - 1) * ChunkSize;
        var chunkMaxX = (ChunkCoords.X + 2) * ChunkSize;
        var chunkMinY = (ChunkCoords.Y - 1) * ChunkSize;
        var chunkMaxY = (ChunkCoords.Y + 2) * ChunkSize;

        x = Math.Max(chunkMinX, Math.Min(x, chunkMaxX));
        y = Math.Max(chunkMinY, Math.Min(y, chunkMaxY));
        return (x, y);
    }

    private void MoveTowards((double X, double Y) target, double dt)
    {
        if (IsImmobilized())
            return;

        var dx = target.X - Position[0];
        var dy = target.Y - Position[1];
        var dist = Math.Sqrt(dx * dx + dy * dy);

        if (dist > 0.1)
        {
            var moveSpeed = Definition.Speed * dt * 2 * _speedMultiplier;
            var moveDx = dx / dist * moveSpeed;
            var moveDy = dy / dist * moveSpeed;
            var (newX, newY) = ClampToChunkBounds(Position[0] + moveDx, Position[1] + moveDy);

            if (_safeZoneCenter is { } sz && _safeZoneRadius > 0)
            {
                var dxSafe = newX - sz.X;
                var dySafe = newY - sz.Y;
                if (Math.Sqrt(dxSafe * dxSafe + dySafe * dySafe) <= _safeZoneRadius)
                    return;
            }

            if (IsWalkable is not null)
            {
                if (IsWalkable(new Position(newX, newY, 0)))
                {
                    Position[0] = newX;
                    Position[1] = newY;
                }
                else
                {
                    // collision sliding: X-only, then Y-only
                    var (xOnlyX, xOnlyY) = ClampToChunkBounds(Position[0] + moveDx, Position[1]);
                    if (IsWalkable(new Position(xOnlyX, xOnlyY, 0)))
                    {
                        Position[0] = xOnlyX;
                        Position[1] = xOnlyY;
                    }
                    else
                    {
                        var (yOnlyX, yOnlyY) = ClampToChunkBounds(Position[0], Position[1] + moveDy);
                        if (IsWalkable(new Position(yOnlyX, yOnlyY, 0)))
                        {
                            Position[0] = yOnlyX;
                            Position[1] = yOnlyY;
                        }
                    }
                }
            }
            else
            {
                Position[0] = newX;
                Position[1] = newY;
            }
        }
    }

    public bool CanAttack()
    {
        if (IsSilenced()) return false;
        if (AttackPhase != "idle") return false;
        return AttackCooldown <= 0 && State == AiState.Attack;
    }

    public EnemyAttackDef? SelectAttack()
    {
        var attacks = Definition.Attacks;
        if (attacks.Count == 0) return null;
        var weights = attacks.Select(a => (double)a.Weight).ToList();
        return CombatGen.WeightedChoice(attacks, weights, _rng);
    }

    public bool StartPhasedAttack((double X, double Y) targetPos,
                                  List<string>? tags = null,
                                  bool isAbility = false,
                                  SpecialAbility? ability = null)
    {
        if (AttackPhase != "idle") return false;

        var selectedAttack = isAbility ? null : SelectAttack();
        List<string> attackTags;

        if (selectedAttack is not null)
        {
            var speedFactor = 1.0 / Math.Max(0.3, Definition.AttackSpeed);
            var tierSpeed = Definition.Tier switch
            { 1 => 1.0, 2 => 0.95, 3 => 0.9, 4 => 0.85, _ => 1.0 };

            AttackWindupMs = selectedAttack.Windup * speedFactor * tierSpeed;
            AttackActiveMs = selectedAttack.Active * speedFactor * tierSpeed;
            AttackRecoveryMs = selectedAttack.Recovery * speedFactor * tierSpeed;

            AttackArcDegrees = selectedAttack.Shape == "arc" ? selectedAttack.Arc : 360;
            AttackRadius = selectedAttack.Range;
            AttackShape = selectedAttack.Shape;
            AttackScreenShake = selectedAttack.ScreenShake;
            AttackDamageMult = selectedAttack.DamageMultiplier;

            attackTags = selectedAttack.Tags;
        }
        else
        {
            var primary = Definition.Attacks.Count > 0 ? Definition.Attacks[0] : null;
            if (primary is not null)
            {
                var speedFactor = 1.0 / Math.Max(0.3, Definition.AttackSpeed);
                var tierSpeed = Definition.Tier switch
                { 1 => 1.0, 2 => 0.95, 3 => 0.9, 4 => 0.85, _ => 1.0 };

                AttackWindupMs = primary.Windup * speedFactor * tierSpeed;
                AttackActiveMs = primary.Active * speedFactor * tierSpeed;
                AttackRecoveryMs = primary.Recovery * speedFactor * tierSpeed;

                AttackArcDegrees = primary.Shape == "arc" ? primary.Arc : 360;
                AttackRadius = primary.Range;
                AttackShape = primary.Shape;
                AttackScreenShake = false;
                AttackDamageMult = 1.0;
            }
            else
            {
                AttackWindupMs = 600;
                AttackActiveMs = 240;
                AttackRecoveryMs = 400;
                AttackArcDegrees = 80;
                AttackRadius = 1.5;
                AttackShape = "arc";
                AttackScreenShake = false;
                AttackDamageMult = 1.0;
            }

            attackTags = tags ?? new List<string> { "physical" };
        }

        AttackPhase = "windup";
        AttackPhaseTimer = AttackWindupMs;
        AttackTargetPos = targetPos;

        var fdx = targetPos.X - Position[0];
        var fdy = targetPos.Y - Position[1];
        FacingAngle = PyMath.Degrees(Math.Atan2(fdy, fdx));

        AttackPendingData = new Dictionary<string, object?>
        {
            ["tags"] = attackTags,
            ["is_ability"] = isAbility,
            ["ability"] = ability,
            ["damage_multiplier"] = AttackDamageMult,
            ["screen_shake"] = AttackScreenShake,
        };

        AttackAnimAngle = FacingAngle;
        AttackAnimTags = new List<string>(attackTags);
        AttackAnimLunge = ability is not null
            && ability.AbilityId is "leap_attack" or "charge_attack" or "pounce";
        var totalDur = (AttackWindupMs + AttackActiveMs + AttackRecoveryMs) / 1000.0;
        AttackAnimTimer = totalDur;
        AttackAnimDuration = totalDur;

        AttackCooldown = totalDur + 1.0 / Definition.AttackSpeed;

        return true;
    }

    /// <summary>Returns "active_start" / "recovery_start" / "idle" / null.</summary>
    public string? UpdateAttackPhase(double dtMs)
    {
        if (AttackPhase == "idle") return null;

        AttackPhaseTimer -= dtMs;
        if (AttackPhaseTimer <= 0)
        {
            if (AttackPhase == "windup")
            {
                AttackPhase = "active";
                AttackPhaseTimer = AttackActiveMs;
                return "active_start";
            }
            if (AttackPhase == "active")
            {
                AttackPhase = "recovery";
                AttackPhaseTimer = AttackRecoveryMs;
                return "recovery_start";
            }
            if (AttackPhase == "recovery")
            {
                AttackPhase = "idle";
                AttackPhaseTimer = 0;
                AttackPendingData = null;
                AttackTargetPos = null;
                return "idle";
            }
        }
        return null;
    }

    public double WindupProgress
    {
        get
        {
            if (AttackPhase != "windup" || AttackWindupMs <= 0) return 0.0;
            var elapsed = AttackWindupMs - AttackPhaseTimer;
            return Math.Min(1.0, elapsed / AttackWindupMs);
        }
    }

    public bool IsInWindup => AttackPhase == "windup";
    public bool IsInRecovery => AttackPhase == "recovery";

    public double PerformAttack()
    {
        AttackCooldown = 1.0 / Definition.AttackSpeed;
        return _rng.Uniform(Definition.DamageMin, Definition.DamageMax);
    }

    public SpecialAbility? CanUseSpecialAbility(double distToTarget = 0.0)
    {
        if (Definition.SpecialAbilities.Count == 0) return null;
        if (IsSilenced()) return null;

        // Python sorted(..., reverse=True) is stable; OrderByDescending too
        var sortedAbilities = Definition.SpecialAbilities
            .OrderByDescending(a => a.Priority).ToList();

        var healthPercent = CurrentHealth / MaxHealth;
        foreach (var ability in sortedAbilities)
        {
            if (healthPercent > ability.HealthThreshold) continue;
            if (AbilityCooldowns.GetValueOrDefault(ability.AbilityId, 0) > 0) continue;
            if (ability.DistanceMin > 0 && distToTarget < ability.DistanceMin) continue;
            if (ability.DistanceMax < 999 && distToTarget > ability.DistanceMax) continue;
            if (ability.OncePerFight
                && AbilityUsesThisFight.GetValueOrDefault(ability.AbilityId, 0) > 0) continue;
            if (ability.MaxUsesPerFight > 0
                && AbilityUsesThisFight.GetValueOrDefault(ability.AbilityId, 0)
                   >= ability.MaxUsesPerFight) continue;

            return ability;
        }
        return null;
    }
}
