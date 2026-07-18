namespace Game1.Core.Combat;

/// <summary>
/// Port of Combat/combat_manager.py::_player_crit_chance — the single source
/// of truth for player crit (FINDINGS F3/F6). Composition:
/// LCK_per_point x effective_luck + pierce buffs + Precision weapon tag +
/// title criticalChance. Pinned by conformance/goldens/crit_chance.json.
/// </summary>
public static class CritChance
{
    public static double Compute(
        double effectiveLuck,
        double pierceBuffBonus = 0.0,
        double titleCritBonus = 0.0,
        IReadOnlyCollection<string>? weaponTags = null)
    {
        var chance = GameConstants.LckCritPerPoint * effectiveLuck;
        chance += pierceBuffBonus;
        if (weaponTags is not null)
            chance += WeaponTagModifiers.GetCritChanceBonus(weaponTags);
        chance += titleCritBonus;
        return chance;
    }
}
