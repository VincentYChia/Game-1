using System.Text.Json.Nodes;
using Game1.Core.Data;

namespace Game1.Core.Progression;

/// <summary>
/// Port of entities/status_effect.py + status_manager.py — 17 effect classes,
/// factory with aliases, and the manager (stacking rules, mutual exclusions,
/// resistance hook, cleanse/CC queries). Python duck-types the target; here
/// the mutable surface is IStatusTarget. Behavior pinned by
/// conformance/goldens/db_parity/status_effects.json — including the alias
/// quirk (applying 'chill' over 'slow' creates a second slow effect because
/// _find_effect matches by status_id, not the applied tag).
/// </summary>
public interface IStatusTarget
{
    bool HasSpeed { get; }
    double Speed { get; set; }
    bool HasMovementSpeed { get; }
    double MovementSpeed { get; set; }
    bool HasAttackSpeed { get; }
    double AttackSpeed { get; set; }

    bool HasTakeDamage { get; }
    void TakeDamage(double amount, string damageType, IReadOnlyList<string> tags);
    double CurrentHealth { get; set; }
    double MaxHealth { get; }
    bool HasHeal { get; }
    void Heal(double amount);

    double ShieldAmount { get; set; }
    double ShieldHealth { get; }

    bool IsFrozen { get; set; }
    bool IsStunned { get; set; }
    bool IsRooted { get; set; }
    bool IsPhased { get; set; }
    bool IgnoreCollisions { get; set; }
    bool IsInvisible { get; set; }

    double EmpowerDamageMultiplier { get; set; }
    double FortifyDamageReduction { get; set; }
    double DamageMultiplier { get; set; }
    double DamageTakenMultiplier { get; set; }

    ISet<string> VisualEffects { get; }

    /// <summary>Duration multiplier per status tag (Python hasattr hook;
    /// return 1.0 when no resistance system).</summary>
    double GetEffectResistance(string statusTag) => 1.0;
}

public abstract class StatusEffect
{
    public required string StatusId { get; init; }
    public required string Name { get; init; }
    public double Duration { get; set; }
    public double DurationRemaining { get; set; }
    public int Stacks { get; set; } = 1;
    public int MaxStacks { get; init; } = 1;
    public JsonObject Params { get; init; } = new();

    public bool Update(double dt, IStatusTarget target)
    {
        DurationRemaining -= dt;
        ApplyPeriodicEffect(dt, target);
        return DurationRemaining > 0;
    }

    public abstract void OnApply(IStatusTarget target);
    public abstract void OnRemove(IStatusTarget target);
    protected abstract void ApplyPeriodicEffect(double dt, IStatusTarget target);

    public void AddStack(int amount = 1) => Stacks = Math.Min(Stacks + amount, MaxStacks);

    public void RefreshDuration(double? newDuration = null)
    {
        if (newDuration is not null)
        {
            Duration = newDuration.Value;
            DurationRemaining = newDuration.Value;
        }
        else
        {
            DurationRemaining = Duration;
        }
    }

    protected double P(string key, double def) => J.Num(Params, key, def);

    protected void DealDamage(IStatusTarget target, double damage, string type, string[] tags)
    {
        if (target.HasTakeDamage)
            target.TakeDamage(damage, type, tags);
        else
            target.CurrentHealth = Math.Max(0, target.CurrentHealth - damage);
    }
}

// ── DoT ──────────────────────────────────────────────────────────────────
public sealed class BurnEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t) => t.VisualEffects.Add("burn");
    public override void OnRemove(IStatusTarget t) => t.VisualEffects.Remove("burn");
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) =>
        DealDamage(t, P("burn_damage_per_second", 5.0) * Stacks * dt, "fire",
            new[] { "burn", "fire" });
}

public sealed class BleedEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t) => t.VisualEffects.Add("bleed");
    public override void OnRemove(IStatusTarget t) => t.VisualEffects.Remove("bleed");
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) =>
        DealDamage(t, P("bleed_damage_per_second", 3.0) * Stacks * dt, "physical",
            new[] { "bleed", "physical" });
}

public sealed class PoisonEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t) => t.VisualEffects.Add("poison");
    public override void OnRemove(IStatusTarget t) => t.VisualEffects.Remove("poison");
    // status_effect.py:176 — superlinear stack scaling (stacks^1.2)
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) =>
        DealDamage(t, P("poison_damage_per_second", 2.0) * Math.Pow(Stacks, 1.2) * dt,
            "poison", new[] { "poison", "poison_status" });
}

// ── CC ───────────────────────────────────────────────────────────────────
public sealed class FreezeEffect : StatusEffect
{
    private double _storedSpeed;
    public override void OnApply(IStatusTarget t)
    {
        if (t.HasSpeed) { _storedSpeed = t.Speed; t.Speed = 0.0; }
        else if (t.HasMovementSpeed) { _storedSpeed = t.MovementSpeed; t.MovementSpeed = 0.0; }
        t.VisualEffects.Add("freeze");
        t.IsFrozen = true;
    }
    public override void OnRemove(IStatusTarget t)
    {
        if (t.HasSpeed) t.Speed = _storedSpeed;
        else if (t.HasMovementSpeed) t.MovementSpeed = _storedSpeed;
        t.VisualEffects.Remove("freeze");
        t.IsFrozen = false;
    }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

public sealed class SlowEffect : StatusEffect
{
    private double _storedSpeed;
    public override void OnApply(IStatusTarget t)
    {
        var slowPercent = P("slow_percent", 0.5);
        if (t.HasSpeed) { _storedSpeed = t.Speed; t.Speed *= 1.0 - slowPercent; }
        else if (t.HasMovementSpeed)
        { _storedSpeed = t.MovementSpeed; t.MovementSpeed *= 1.0 - slowPercent; }
        t.VisualEffects.Add("slow");
    }
    public override void OnRemove(IStatusTarget t)
    {
        if (t.HasSpeed) t.Speed = _storedSpeed;
        else if (t.HasMovementSpeed) t.MovementSpeed = _storedSpeed;
        t.VisualEffects.Remove("slow");
    }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

public sealed class StunEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t)
    { t.IsStunned = true; t.VisualEffects.Add("stun"); }
    public override void OnRemove(IStatusTarget t)
    { t.IsStunned = false; t.VisualEffects.Remove("stun"); }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

public sealed class RootEffect : StatusEffect
{
    private double _storedSpeed;
    public override void OnApply(IStatusTarget t)
    {
        if (t.HasSpeed) { _storedSpeed = t.Speed; t.Speed = 0.0; }
        else if (t.HasMovementSpeed) { _storedSpeed = t.MovementSpeed; t.MovementSpeed = 0.0; }
        t.IsRooted = true;
        t.VisualEffects.Add("root");
    }
    public override void OnRemove(IStatusTarget t)
    {
        if (t.HasSpeed) t.Speed = _storedSpeed;
        else if (t.HasMovementSpeed) t.MovementSpeed = _storedSpeed;
        t.IsRooted = false;
        t.VisualEffects.Remove("root");
    }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

// ── Buffs ────────────────────────────────────────────────────────────────
public sealed class RegenerationEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t) => t.VisualEffects.Add("regen");
    public override void OnRemove(IStatusTarget t) => t.VisualEffects.Remove("regen");
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t)
    {
        var healing = P("regen_heal_per_second", 5.0) * Stacks * dt;
        if (t.HasHeal) t.Heal(healing);
        else t.CurrentHealth = Math.Min(t.CurrentHealth + healing, t.MaxHealth);
    }
}

public sealed class ShieldEffect : StatusEffect
{
    private double _currentShield;
    public double ShieldValue => P("shield_amount", 50.0);
    public override void OnApply(IStatusTarget t)
    {
        _currentShield = ShieldValue;
        t.ShieldAmount += ShieldValue;
        t.VisualEffects.Add("shield");
    }
    public override void OnRemove(IStatusTarget t)
    {
        t.ShieldAmount = Math.Max(0, t.ShieldAmount - _currentShield);
        t.VisualEffects.Remove("shield");
    }
    // status_effect.py:436-440 — tracks remaining shield off shield_health
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) =>
        _currentShield = Math.Min(ShieldValue, t.ShieldHealth);
}

public sealed class HasteEffect : StatusEffect
{
    private double _originalSpeed, _originalAttackSpeed;
    public override void OnApply(IStatusTarget t)
    {
        var bonus = P("haste_speed_bonus", 0.3);
        if (t.HasSpeed) { _originalSpeed = t.Speed; t.Speed *= 1.0 + bonus; }
        else if (t.HasMovementSpeed)
        { _originalSpeed = t.MovementSpeed; t.MovementSpeed *= 1.0 + bonus; }
        if (t.HasAttackSpeed)
        { _originalAttackSpeed = t.AttackSpeed; t.AttackSpeed *= 1.0 + bonus; }
        t.VisualEffects.Add("haste");
    }
    public override void OnRemove(IStatusTarget t)
    {
        if (t.HasSpeed) t.Speed = _originalSpeed;
        else if (t.HasMovementSpeed) t.MovementSpeed = _originalSpeed;
        if (t.HasAttackSpeed) t.AttackSpeed = _originalAttackSpeed;
        t.VisualEffects.Remove("haste");
    }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

public sealed class EmpowerEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t)
    {
        t.EmpowerDamageMultiplier += P("empower_damage_bonus", 0.25);
        t.VisualEffects.Add("empower");
    }
    public override void OnRemove(IStatusTarget t)
    {
        t.EmpowerDamageMultiplier -= P("empower_damage_bonus", 0.25);
        t.VisualEffects.Remove("empower");
    }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

public sealed class FortifyEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t)
    {
        t.FortifyDamageReduction += P("fortify_defense_bonus", 0.20);
        t.VisualEffects.Add("fortify");
    }
    public override void OnRemove(IStatusTarget t)
    {
        t.FortifyDamageReduction -= P("fortify_defense_bonus", 0.20);
        t.VisualEffects.Remove("fortify");
    }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

// ── Debuffs ──────────────────────────────────────────────────────────────
public sealed class WeakenEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t)
    {
        t.DamageMultiplier *= 1.0 - P("weaken_percent", 0.25);
        t.VisualEffects.Add("weaken");
    }
    public override void OnRemove(IStatusTarget t)
    {
        t.DamageMultiplier /= 1.0 - P("weaken_percent", 0.25);
        t.VisualEffects.Remove("weaken");
    }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

public sealed class VulnerableEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t)
    {
        t.DamageTakenMultiplier *= 1.0 + P("vulnerable_percent", 0.25);
        t.VisualEffects.Add("vulnerable");
    }
    public override void OnRemove(IStatusTarget t)
    {
        t.DamageTakenMultiplier /= 1.0 + P("vulnerable_percent", 0.25);
        t.VisualEffects.Remove("vulnerable");
    }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

public sealed class ShockEffect : StatusEffect
{
    private double _timeSinceLastTick;
    public override void OnApply(IStatusTarget t) => t.VisualEffects.Add("shock");
    public override void OnRemove(IStatusTarget t) => t.VisualEffects.Remove("shock");
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t)
    {
        _timeSinceLastTick += dt;
        var tickRate = P("shock_tick_rate", P("tick_rate", 2.0));
        if (_timeSinceLastTick >= tickRate)
        {
            var damage = P("shock_damage_per_tick", P("damage_per_tick", 5.0)) * Stacks;
            DealDamage(t, damage, "lightning", new[] { "shock", "lightning" });
            _timeSinceLastTick = 0.0;
        }
    }
}

public sealed class PhaseEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t)
    {
        t.IsPhased = true;
        if (J.Bool(Params, "can_pass_walls", false))
            t.IgnoreCollisions = true;
        t.VisualEffects.Add("phase");
    }
    public override void OnRemove(IStatusTarget t)
    {
        t.IsPhased = false;
        if (J.Bool(Params, "can_pass_walls", false))
            t.IgnoreCollisions = false;
        t.VisualEffects.Remove("phase");
    }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

public sealed class InvisibleEffect : StatusEffect
{
    public override void OnApply(IStatusTarget t)
    { t.IsInvisible = true; t.VisualEffects.Add("invisible"); }
    public override void OnRemove(IStatusTarget t)
    { t.IsInvisible = false; t.VisualEffects.Remove("invisible"); }
    protected override void ApplyPeriodicEffect(double dt, IStatusTarget t) { }
}

// ── Factory + Manager ────────────────────────────────────────────────────
public static class StatusEffectFactory
{
    // status_effect.py:776-803 — alias → canonical (status_id, name, max stacks)
    private static (string Id, string Name, int MaxStacks)? Meta(string tag, JsonObject p) => tag switch
    {
        "burn" => ("burn", "Burning", (int)J.Num(p, "burn_max_stacks", 3)),
        "bleed" => ("bleed", "Bleeding", (int)J.Num(p, "bleed_max_stacks", 5)),
        "poison" or "poison_status" => ("poison", "Poisoned", (int)J.Num(p, "poison_max_stacks", 10)),
        "freeze" => ("freeze", "Frozen", 1),
        "slow" or "chill" => ("slow", "Slowed", (int)J.Num(p, "slow_max_stacks", 1)),
        "stun" => ("stun", "Stunned", 1),
        "root" => ("root", "Rooted", 1),
        "shock" => ("shock", "Shocked", (int)J.Num(p, "shock_max_stacks", 3)),
        "regeneration" or "regen" => ("regeneration", "Regenerating", (int)J.Num(p, "regen_max_stacks", 3)),
        "shield" or "barrier" => ("shield", "Shielded", 1),
        "haste" or "quicken" => ("haste", "Hasted", 1),
        "empower" => ("empower", "Empowered", 1),
        "fortify" => ("fortify", "Fortified", 1),
        "phase" or "ethereal" or "intangible" => ("phase", "Phased", 1),
        "invisible" or "stealth" or "hidden" => ("invisible", "Invisible", 1),
        "weaken" => ("weaken", "Weakened", (int)J.Num(p, "weaken_max_stacks", 3)),
        "vulnerable" => ("vulnerable", "Vulnerable", (int)J.Num(p, "vulnerable_max_stacks", 3)),
        _ => null,
    };

    public static StatusEffect? Create(string statusTag, JsonObject prms)
    {
        var meta = Meta(statusTag, prms);
        if (meta is null) return null;
        var (id, name, maxStacks) = meta.Value;
        // status_effect.py:824 — duration: '<tag>_duration' > 'duration' > 5.0
        var duration = J.Num(prms, $"{statusTag}_duration", J.Num(prms, "duration", 5.0));
        StatusEffect effect = id switch
        {
            "burn" => new BurnEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "bleed" => new BleedEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "poison" => new PoisonEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "freeze" => new FreezeEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "slow" => new SlowEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "stun" => new StunEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "root" => new RootEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "shock" => new ShockEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "regeneration" => new RegenerationEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "shield" => new ShieldEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "haste" => new HasteEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "empower" => new EmpowerEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "fortify" => new FortifyEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "phase" => new PhaseEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "invisible" => new InvisibleEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "weaken" => new WeakenEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            "vulnerable" => new VulnerableEffect { StatusId = id, Name = name, MaxStacks = maxStacks, Params = prms },
            _ => throw new InvalidOperationException(id),
        };
        effect.Duration = duration;
        effect.DurationRemaining = duration;
        return effect;
    }
}

public sealed class StatusEffectManager
{
    private static readonly (string A, string B)[] MutualExclusions =
    { ("burn", "freeze"), ("stun", "freeze") };

    private static readonly Dictionary<string, string> StackingRules = new()
    {
        ["burn"] = "additive", ["bleed"] = "additive", ["poison"] = "additive",
        ["poison_status"] = "additive",
        ["freeze"] = "refresh", ["stun"] = "refresh", ["root"] = "refresh",
        ["slow"] = "refresh", ["chill"] = "refresh",
        ["regeneration"] = "additive", ["regen"] = "additive",
        ["shield"] = "additive", ["barrier"] = "additive",
        ["haste"] = "refresh", ["quicken"] = "refresh",
        ["weaken"] = "additive", ["vulnerable"] = "additive",
    };

    private readonly IStatusTarget _entity;
    public List<StatusEffect> ActiveEffects { get; } = new();

    public StatusEffectManager(IStatusTarget entity) => _entity = entity;

    // status_manager.py:72-165 — NOTE: _find_effect matches the APPLIED tag
    // against canonical status_id, so aliases (chill/regen/quicken/...) miss
    // existing effects and create duplicates. Bug-compatible.
    public bool ApplyStatus(string statusTag, JsonObject prms)
    {
        var existing = FindEffect(statusTag);
        if (existing is not null)
        {
            var behavior = StackingRules.GetValueOrDefault(statusTag, "none");
            if (behavior == "additive")
            {
                existing.AddStack(1);
                existing.RefreshDuration();
                return true;
            }
            if (behavior == "refresh")
            {
                existing.RefreshDuration();
                return true;
            }
            RemoveEffect(existing);
        }

        foreach (var (a, b) in MutualExclusions)
        {
            if (statusTag == a && FindEffect(b) is { } conflictB)
                RemoveEffect(conflictB);
            else if (statusTag == b && FindEffect(a) is { } conflictA)
                RemoveEffect(conflictA);
        }

        // Resistance scales only duration keys PRESENT in params (py :132-146)
        var modified = (JsonObject)prms.DeepClone();
        var resistance = _entity.GetEffectResistance(statusTag);
        if (Math.Abs(resistance - 1.0) > 1e-12)
        {
            if (modified.ContainsKey("duration"))
                modified["duration"] = J.Num(modified, "duration", 0) * resistance;
            var durationKey = $"{statusTag}_duration";
            if (modified.ContainsKey(durationKey))
                modified[durationKey] = J.Num(modified, durationKey, 0) * resistance;
        }

        var effect = StatusEffectFactory.Create(statusTag, modified);
        if (effect is null) return false;
        effect.OnApply(_entity);
        ActiveEffects.Add(effect);
        return true;
    }

    public bool RemoveStatus(string statusTag)
    {
        if (FindEffect(statusTag) is { } effect)
        {
            RemoveEffect(effect);
            return true;
        }
        return false;
    }

    public bool HasStatus(string statusTag) => FindEffect(statusTag) is not null;

    public void Update(double dt)
    {
        var expired = ActiveEffects.Where(e => !e.Update(dt, _entity)).ToList();
        foreach (var effect in expired)
            RemoveEffect(effect);
    }

    public void ClearAll()
    {
        foreach (var effect in ActiveEffects.ToList())
            RemoveEffect(effect);
    }

    private static readonly string[] DebuffTags =
    {
        "burn", "bleed", "poison", "poison_status",
        "freeze", "stun", "root", "slow", "chill", "weaken", "vulnerable",
    };

    public void ClearDebuffs()
    {
        foreach (var effect in ActiveEffects.ToList())
            if (DebuffTags.Contains(effect.StatusId))
                RemoveEffect(effect);
    }

    public bool IsCrowdControlled() =>
        new[] { "freeze", "stun", "root", "slow", "chill" }.Any(t => FindEffect(t) is not null);

    public bool IsImmobilized() =>
        new[] { "freeze", "stun", "root" }.Any(t => FindEffect(t) is not null);

    public bool IsSilenced() =>
        new[] { "stun", "silence" }.Any(t => FindEffect(t) is not null);

    private StatusEffect? FindEffect(string statusTag) =>
        ActiveEffects.FirstOrDefault(e => e.StatusId == statusTag);

    private void RemoveEffect(StatusEffect effect)
    {
        if (ActiveEffects.Remove(effect))
            effect.OnRemove(_entity);
    }
}
