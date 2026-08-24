using Game1.Core.World;

namespace Game1.Core.Combat;

/// <summary>
/// Capability surface for entities passing through the effect executor and
/// target finder. Python duck-types (hasattr chains) over Character / Enemy;
/// this interface makes each hasattr branch an explicit capability flag —
/// same pattern as ICharacterQuery / IStatusTarget from P1/P2.
/// </summary>
public interface ICombatEntity
{
    string Name { get; }

    /// <summary>Python type(entity).__name__.lower() — drives context checks
    /// ("character", "enemy", "placedentity", ...).</summary>
    string TypeNameLower { get; }

    /// <summary>getattr(entity, 'category', None).</summary>
    string? Category { get; }

    /// <summary>hasattr(definition) and hasattr(is_alive) — Enemy-shaped.</summary>
    bool IsEnemyLike { get; }

    Position GetPosition();
    void SetPositionXY(double x, double y);

    /// <summary>Python last_move_direction if set (any tuple is truthy).</summary>
    (double Dx, double Dy)? LastMoveDirection { get; }

    bool HasCurrentHealth { get; }
    double CurrentHealth { get; set; }
    bool HasMaxHealth { get; }
    double MaxHealth { get; }
    bool HasIsAlive { get; }
    bool Alive { get; set; }
    bool HasHealthField { get; }
    double Health { get; set; }

    /// <summary>getattr(target.definition, 'defense', 0) or 0.</summary>
    double DefinitionDefense { get; }

    bool SupportsTakeDamage { get; }
    void TakeDamage(double damage, string damageType,
                    ICombatEntity? source, IReadOnlyList<string> tags);
    bool SupportsHeal { get; }
    void Heal(double amount);

    bool HasStatusManager { get; }
    void ApplyStatus(string statusTag, Dictionary<string, object?> statusParams,
                     ICombatEntity? source = null);

    bool HasKnockbackFields { get; }
    void SetKnockback(double vx, double vy, double durationRemaining);
}
