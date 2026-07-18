namespace Game1.Core.Combat;

/// <summary>
/// Port of the per-target enemy-defense seam in core/effect_executor.py:162-168
/// (FINDINGS F5): reduction = min(0.75, defense x (1 - armorPen) x 0.01).
/// Pinned by conformance/goldens/defense_reduction.json.
/// </summary>
public static class DefenseReduction
{
    public static double Reduction(double defense, double armorPenetration = 0.0)
    {
        var effectiveDefense = defense * (1.0 - armorPenetration);
        return Math.Min(GameConstants.DefenseReductionCap,
                        effectiveDefense * GameConstants.DefenseReductionPerPoint);
    }

    public static double Apply(double damage, double defense, double armorPenetration = 0.0) =>
        damage * (1.0 - Reduction(defense, armorPenetration));
}
