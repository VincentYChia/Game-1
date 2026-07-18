namespace Game1.Core.Crafting;

/// <summary>
/// Port of core/reward_calculator.py (core functions). Pinned by
/// conformance/goldens/rewards.json. The per-discipline reward assemblers
/// (calculate_smithing_rewards etc.) port in Phase 6.
/// </summary>
public static class RewardCalculator
{
    // reward_calculator.py:28-31
    public const double RewardMultiplierMin = 1.0;
    public const double RewardMultiplierMax = 2.5;

    // :43-46
    public const double FailureMinLoss = 0.30;
    public const double FailureMaxLoss = 0.90;

    // :52-62 — per-discipline first-try boost, default 0.10
    private static readonly IReadOnlyDictionary<string, double> FirstTryPerDiscipline =
        new Dictionary<string, double>
        {
            ["smithing"] = 0.10, ["enchanting"] = 0.10, ["engineering"] = 0.05,
            ["alchemy"] = 0.10, ["refining"] = 0.10,
        };

    public static double FirstTryBonus(string discipline = "") =>
        FirstTryPerDiscipline.GetValueOrDefault(discipline.ToLowerInvariant(), 0.10);

    private static double NormalizedDifficulty(double difficultyPoints)
    {
        var normalized = (difficultyPoints - DifficultyCalculator.MinPoints)
                         / (DifficultyCalculator.MaxPoints - DifficultyCalculator.MinPoints);
        return Math.Max(0.0, Math.Min(1.0, normalized));
    }

    // :81-104
    public static double MaxRewardMultiplier(double difficultyPoints) =>
        RewardMultiplierMin
        + NormalizedDifficulty(difficultyPoints) * (RewardMultiplierMax - RewardMultiplierMin);

    // :34-40, :107-120 — bands are min <= p < max; Legendary band runs to 1.01
    // so 1.0 lands in-band; anything else falls back to Legendary.
    public static string QualityTier(double performanceScore)
    {
        if (performanceScore is >= 0.00 and < 0.25) return "Normal";
        if (performanceScore is >= 0.25 and < 0.50) return "Fine";
        if (performanceScore is >= 0.50 and < 0.75) return "Superior";
        if (performanceScore is >= 0.75 and < 0.90) return "Masterwork";
        if (performanceScore is >= 0.90 and < 1.01) return "Legendary";
        return "Legendary";
    }

    // :123-143 — int() truncation, matching Python
    public static int BonusPct(double performanceScore, double maxMultiplier) =>
        (int)(performanceScore * (maxMultiplier - 1.0) * 20);

    // :146-160
    public static double StatMultiplier(double performanceScore, double maxMultiplier) =>
        1.0 + BonusPct(performanceScore, maxMultiplier) / 100.0;

    // :497-519 — 30% loss at min difficulty scaling to 90% at max
    public static double FailurePenalty(double difficultyPoints) =>
        FailureMinLoss + NormalizedDifficulty(difficultyPoints) * (FailureMaxLoss - FailureMinLoss);

    // :522-546 — per-material int truncation; zero-loss entries omitted
    public static Dictionary<string, int> MaterialLoss(
        IReadOnlyList<MaterialInput> inputs, double difficultyPoints)
    {
        var lossFraction = FailurePenalty(difficultyPoints);
        var losses = new Dictionary<string, int>();
        foreach (var inp in inputs)
        {
            var lost = (int)(inp.Quantity * lossFraction);
            if (lost > 0)
                losses[inp.MaterialId] = lost;
        }
        return losses;
    }
}
