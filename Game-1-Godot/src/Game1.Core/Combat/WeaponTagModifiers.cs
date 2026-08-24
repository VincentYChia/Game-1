namespace Game1.Core.Combat;

/// <summary>
/// Full port of entities/components/weapon_tag_calculator.py::WeaponTagModifiers.
/// Pinned by conformance/goldens/db_parity/equipment_items.json (tag grid
/// executed through the real Python class).
/// </summary>
public static class WeaponTagModifiers
{
    // weapon_tag_calculator.py:19-37 — 2H +20%; versatile +10% only without offhand
    public static double GetDamageMultiplier(IReadOnlyCollection<string> tags, bool hasOffhand = false)
    {
        var multiplier = 1.0;
        if (tags.Contains("2H"))
            multiplier *= 1.2;
        else if (tags.Contains("versatile") && !hasOffhand)
            multiplier *= 1.1;
        return multiplier;
    }

    // :40-54
    public static double GetAttackSpeedBonus(IReadOnlyCollection<string> tags) =>
        tags.Contains("fast") ? 0.15 : 0.0;

    // :57-71
    public static double GetCritChanceBonus(IReadOnlyCollection<string>? tags)
    {
        var bonus = 0.0;
        if (tags is not null && tags.Contains("precision"))
            bonus += 0.10;
        return bonus;
    }

    // :74-88
    public static double GetRangeBonus(IReadOnlyCollection<string> tags) =>
        tags.Contains("reach") ? 1.0 : 0.0;

    // :91-102
    public static double GetArmorPenetration(IReadOnlyCollection<string> tags) =>
        tags.Contains("armor_breaker") ? 0.25 : 0.0;

    // :105-116
    public static double GetDamageVsArmoredBonus(IReadOnlyCollection<string> tags) =>
        tags.Contains("crushing") ? 0.20 : 0.0;

    // :119-128
    public static bool HasCleaving(IReadOnlyCollection<string> tags) =>
        tags.Contains("cleaving");
}
