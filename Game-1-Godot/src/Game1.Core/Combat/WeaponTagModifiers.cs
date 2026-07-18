namespace Game1.Core.Combat;

/// <summary>
/// Port of entities/components/weapon_tag_calculator.py::WeaponTagModifiers.
/// P0 slice: crit-chance bonus only. The remaining modifiers (hand-requirement
/// damage multiplier, armor penetration, crushing-vs-armored, attack speed,
/// reach) port in Phase 2 with the equipment component.
/// </summary>
public static class WeaponTagModifiers
{
    /// <summary>weapon_tag_calculator.py:57-71 — precision grants +10% crit.</summary>
    public static double GetCritChanceBonus(IReadOnlyCollection<string>? tags)
    {
        var bonus = 0.0;
        if (tags is not null && tags.Contains("precision"))
            bonus += 0.10;
        return bonus;
    }
}
