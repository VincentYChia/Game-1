namespace Game1.Core.Crafting;

/// <summary>
/// P0 slice of core/difficulty_calculator.py: material points, diversity,
/// average tier, and the rarity-band mapping. The per-discipline minigame
/// parameter interpolation ports in Phase 6 (its outputs are already pinned
/// in conformance/goldens/difficulty.json).
/// Tier lookup is injected (the Python code consults MaterialDatabase; the
/// data layer arrives in Phase 1).
/// </summary>
public readonly record struct MaterialInput(string MaterialId, int Quantity, int Tier);

public static class DifficultyCalculator
{
    // difficulty_calculator.py:35-40 — LINEAR tier points
    public static readonly IReadOnlyDictionary<int, int> TierPoints =
        new Dictionary<int, int> { [1] = 1, [2] = 2, [3] = 3, [4] = 4 };

    // :56-59 — single source of truth shared with the reward calculator
    public const double MinPoints = 1.0;
    public const double MaxPoints = 80.0;

    // :130-175 — sum(tierPoints x quantity), minimum 1.0; empty input → 1.0
    public static double MaterialPoints(IReadOnlyList<MaterialInput> inputs)
    {
        if (inputs.Count == 0)
            return 1.0;
        var total = 0.0;
        foreach (var inp in inputs)
        {
            var tierPoints = TierPoints.GetValueOrDefault(inp.Tier, inp.Tier);
            total += tierPoints * inp.Quantity;
        }
        return Math.Max(1.0, total);
    }

    // :178-204 — 1.0 + (unique_non_empty_ids - 1) x 0.1
    public static double DiversityMultiplier(IReadOnlyList<MaterialInput> inputs)
    {
        if (inputs.Count == 0)
            return 1.0;
        var unique = new HashSet<string>();
        foreach (var inp in inputs)
            if (!string.IsNullOrEmpty(inp.MaterialId))
                unique.Add(inp.MaterialId);
        return 1.0 + (unique.Count - 1) * 0.1;
    }

    // :207-250 — quantity-weighted average tier; empty or zero quantity → 1.0
    public static double AverageTier(IReadOnlyList<MaterialInput> inputs)
    {
        if (inputs.Count == 0)
            return 1.0;
        var totalTier = 0.0;
        var totalQuantity = 0;
        foreach (var inp in inputs)
        {
            totalTier += inp.Tier * inp.Quantity;
            totalQuantity += inp.Quantity;
        }
        return totalQuantity == 0 ? 1.0 : totalTier / totalQuantity;
    }

    // :47-53 + :754-772 — inclusive bands; gaps between bands (e.g. 4 < p < 5)
    // fall through to 'common' exactly as the Python loop does.
    public static string GetDifficultyTier(double points)
    {
        if (points is >= 0 and <= 4) return "common";
        if (points is >= 5 and <= 10) return "uncommon";
        if (points is >= 11 and <= 20) return "rare";
        if (points is >= 21 and <= 40) return "epic";
        if (points is >= 41 and <= 150) return "legendary";
        if (points > 150) return "legendary";
        return "common";
    }
}
