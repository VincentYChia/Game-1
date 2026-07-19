namespace Game1.Core.Combat;

/// <summary>
/// Port of Combat/attack_state_machine.py — IDLE → WINDUP → ACTIVE →
/// RECOVERY → COOLDOWN cycle. Timing only; damage runs elsewhere when
/// hit events fire.
/// </summary>
public enum AttackPhase
{
    Idle,
    Windup,
    Active,
    Recovery,
    Cooldown,
}

/// <summary>attack_state_machine.py AttackDefinition. hitbox_params stays a
/// loose dict in Python; here typed nullable fields — only keys the generator
/// actually sets are non-null, so dumps can match key-presence exactly.</summary>
public sealed class HitboxParams
{
    public double OffsetForward = 0.8;
    public double? OffsetLateral;
    public string? Shape;
    public double? Radius;
    public double? ArcDegrees;
    public double? Width;
    public double? Height;
    public double? Length;
    public bool? Piercing;
}

public sealed class AttackDefinition
{
    public string AttackId = "";
    public double WindupMs;
    public double ActiveMs;
    public double RecoveryMs;
    public double CooldownMs;

    public string HitboxShape = "arc";
    public HitboxParams HitboxParamsData = new();

    public double DamageMultiplier = 1.0;
    public double MovementMultiplier = 0.7;
    public bool CanBeInterrupted = true;

    public string AnimationId = "swing_medium";
    public string? ProjectileId;

    public List<string> StatusTags = new();
    public bool ScreenShake;
    public List<int> TelegraphColor = new() { 255, 100, 100 };

    public string? ComboNext;
    public double ComboWindowMs;

    public List<string> Tags = new();

    public double TotalDurationMs => WindupMs + ActiveMs + RecoveryMs + CooldownMs;

    // attack_state_machine.py property defaults: .get('radius', 1.5) etc.
    public double HitboxRadius => HitboxParamsData.Radius ?? 1.5;
    public double HitboxArcDegrees => HitboxParamsData.ArcDegrees ?? 90.0;
    public double HitboxOffsetForward => HitboxParamsData.OffsetForward;
}

/// <summary>One instance per entity (player, each enemy).</summary>
public sealed class AttackStateMachine
{
    public string EntityId;
    public AttackPhase Phase = AttackPhase.Idle;
    public double PhaseTimer;
    public AttackDefinition? CurrentAttack;
    public HashSet<string> HitsThisSwing = new();
    public int ComboCount;
    public double ComboTimer;
    public Dictionary<string, object?> DamageContext = new();

    public AttackStateMachine(string entityId)
    {
        EntityId = entityId;
    }

    /// <summary>Can start from IDLE, or from COOLDOWN inside the combo window.</summary>
    public bool StartAttack(AttackDefinition attackDef,
                            Dictionary<string, object?> damageContext)
    {
        if (Phase == AttackPhase.Idle)
        {
            // always allowed
        }
        else if (Phase == AttackPhase.Cooldown && ComboTimer > 0)
        {
            ComboCount += 1;
        }
        else
        {
            return false;
        }

        CurrentAttack = attackDef;
        DamageContext = damageContext;
        Phase = AttackPhase.Windup;
        PhaseTimer = attackDef.WindupMs;
        HitsThisSwing.Clear();
        return true;
    }

    public List<CombatEvent> Update(double dtMs)
    {
        var events = new List<CombatEvent>();

        if (Phase == AttackPhase.Idle)
        {
            if (ComboTimer > 0)
            {
                ComboTimer -= dtMs;
                if (ComboTimer <= 0)
                {
                    ComboCount = 0;
                    ComboTimer = 0;
                }
            }
            return events;
        }

        PhaseTimer -= dtMs;

        if (PhaseTimer <= 0)
        {
            if (Phase == AttackPhase.Windup)
            {
                Phase = AttackPhase.Active;
                PhaseTimer = CurrentAttack!.ActiveMs;
                HitsThisSwing.Clear();
                events.Add(new CombatEvent("phase_change", EntityId,
                    data: new Dictionary<string, object?>
                    {
                        ["phase"] = "active",
                        ["attack"] = CurrentAttack,
                    }));
            }
            else if (Phase == AttackPhase.Active)
            {
                Phase = AttackPhase.Recovery;
                PhaseTimer = CurrentAttack!.RecoveryMs;
                events.Add(new CombatEvent("phase_change", EntityId,
                    data: new Dictionary<string, object?> { ["phase"] = "recovery" }));
            }
            else if (Phase == AttackPhase.Recovery)
            {
                Phase = AttackPhase.Cooldown;
                PhaseTimer = CurrentAttack!.CooldownMs;
                if (CurrentAttack.ComboNext is not null)
                    ComboTimer = CurrentAttack.ComboWindowMs;
                events.Add(new CombatEvent("phase_change", EntityId,
                    data: new Dictionary<string, object?> { ["phase"] = "cooldown" }));
            }
            else if (Phase == AttackPhase.Cooldown)
            {
                Phase = AttackPhase.Idle;
                CurrentAttack = null;
                DamageContext = new Dictionary<string, object?>();
                events.Add(new CombatEvent("phase_change", EntityId,
                    data: new Dictionary<string, object?> { ["phase"] = "idle" }));
            }
        }

        return events;
    }

    /// <summary>Cancel during WINDUP (e.g. stunned).</summary>
    public bool Interrupt()
    {
        if (Phase == AttackPhase.Windup && CurrentAttack is not null
            && CurrentAttack.CanBeInterrupted)
        {
            Phase = AttackPhase.Idle;
            PhaseTimer = 0;
            CurrentAttack = null;
            DamageContext = new Dictionary<string, object?>();
            return true;
        }
        return false;
    }

    public void ForceReset()
    {
        Phase = AttackPhase.Idle;
        PhaseTimer = 0;
        CurrentAttack = null;
        DamageContext = new Dictionary<string, object?>();
        HitsThisSwing.Clear();
        ComboCount = 0;
        ComboTimer = 0;
    }

    /// <summary>False if this target was already hit this swing.</summary>
    public bool RecordHit(string targetId)
    {
        if (HitsThisSwing.Contains(targetId)) return false;
        HitsThisSwing.Add(targetId);
        return true;
    }

    public bool IsInActivePhase => Phase == AttackPhase.Active;
    public bool IsAttacking => Phase != AttackPhase.Idle;
    public bool IsInWindup => Phase == AttackPhase.Windup;
    public bool IsVulnerable => Phase == AttackPhase.Recovery;

    public double MovementMultiplier =>
        CurrentAttack is not null &&
        Phase is AttackPhase.Windup or AttackPhase.Active or AttackPhase.Recovery
            ? CurrentAttack.MovementMultiplier
            : 1.0;

    public double WindupProgress
    {
        get
        {
            if (Phase != AttackPhase.Windup || CurrentAttack is null) return 0.0;
            var elapsed = CurrentAttack.WindupMs - PhaseTimer;
            return Math.Min(1.0, elapsed / Math.Max(1.0, CurrentAttack.WindupMs));
        }
    }
}
