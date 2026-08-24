namespace Game1.Core.Progression;

/// <summary>
/// Port of entities/components/buffs.py — ActiveBuff + BuffManager. Buffs
/// stack additively per (effect_type, category); consume-on-use matrix per
/// action. The regenerate-tick side effects (health/mana/durability) hook in
/// with the character assembly; the bookkeeping here is what the fixture pins.
/// </summary>
public sealed class ActiveBuff
{
    public required string BuffId { get; init; }
    public required string Name { get; init; }
    public required string EffectType { get; init; }
    public required string Category { get; init; }
    public string Magnitude { get; init; } = "moderate";
    public double BonusValue { get; init; }
    public double Duration { get; init; }
    public double DurationRemaining { get; set; }
    public string Source { get; init; } = "skill";
    public bool ConsumeOnUse { get; init; }

    /// <summary>buffs.py:25-28 — returns true while still active.</summary>
    public bool Update(double dt)
    {
        DurationRemaining -= dt;
        return DurationRemaining > 0;
    }

    public double GetProgressPercent() =>
        Duration <= 0 ? 0.0 : Math.Max(0.0, Math.Min(1.0, DurationRemaining / Duration));
}

public sealed class BuffManager
{
    public List<ActiveBuff> ActiveBuffs { get; } = new();

    public void AddBuff(ActiveBuff buff) => ActiveBuffs.Add(buff);

    /// <summary>Tick durations and drop expired buffs (regenerate side
    /// effects are applied by the character-level tick, wired in later).</summary>
    public void Update(double dt) =>
        ActiveBuffs.RemoveAll(b => !b.Update(dt));

    public double GetTotalBonus(string effectType, string category) =>
        ActiveBuffs.Where(b => b.EffectType == effectType && b.Category == category)
                   .Sum(b => b.BonusValue);

    public double GetMovementSpeedBonus() => GetTotalBonus("quicken", "movement");
    public double GetDamageBonus(string category) => GetTotalBonus("empower", category);
    public double GetDefenseBonus() => GetTotalBonus("fortify", "defense");

    // buffs.py:108-156
    public void ConsumeBuffsForAction(string actionType, string? category = null)
    {
        var toRemove = new List<ActiveBuff>();
        foreach (var buff in ActiveBuffs)
        {
            if (!buff.ConsumeOnUse) continue;
            var shouldConsume = actionType switch
            {
                "attack" => buff.Category is "combat" or "damage",
                "gather" => category is not null
                    ? buff.Category == category
                    : buff.Category is "mining" or "forestry" or "fishing" or "gathering",
                "craft" => category is not null
                    ? buff.Category == category
                    : buff.Category is "smithing" or "alchemy" or "engineering"
                        or "refining" or "enchanting",
                _ => false,
            };
            if (shouldConsume)
                toRemove.Add(buff);
        }
        foreach (var buff in toRemove)
            ActiveBuffs.Remove(buff);
    }
}
