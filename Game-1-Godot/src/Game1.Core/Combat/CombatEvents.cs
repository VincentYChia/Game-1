namespace Game1.Core.Combat;

/// <summary>Port of Combat/combat_event.py — the contract between combat
/// subsystems (state machine, hitboxes, projectiles, orchestration).</summary>
public sealed class CombatEvent
{
    public string EventType;   // "phase_change", "hit_landed", "attack_start", "projectile_spawn"
    public string SourceId;
    public string? TargetId;
    public Dictionary<string, object?> Data;

    public CombatEvent(string eventType, string sourceId,
                       string? targetId = null,
                       Dictionary<string, object?>? data = null)
    {
        EventType = eventType;
        SourceId = sourceId;
        TargetId = targetId;
        Data = data ?? new Dictionary<string, object?>();
    }
}

public sealed class HitEvent
{
    public string AttackerId;
    public string TargetId;
    public Dictionary<string, object?> DamageContext;
    public (double X, double Y) HitPosition;
    public bool IsProjectile;

    public HitEvent(string attackerId, string targetId,
                    Dictionary<string, object?> damageContext,
                    (double, double) hitPosition = default,
                    bool isProjectile = false)
    {
        AttackerId = attackerId;
        TargetId = targetId;
        DamageContext = damageContext;
        HitPosition = hitPosition;
        IsProjectile = isProjectile;
    }
}
