using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Game1.Core.Data;

namespace Game1.Core.Progression;

/// <summary>
/// Port of systems/title_system.py TitleSystem — earned-title tracking and
/// bonus summation. Title-award RNG (check_for_title) is not needed for the
/// combat path yet; get_total_bonus's key-resolution chain is ported exactly:
/// literal → camelCase-to-snake_case → known renames → known typo tolerance,
/// first matching candidate per title wins, non-numeric values skipped.
/// </summary>
public sealed class TitleSystem
{
    private static readonly Dictionary<string, string> BonusKeyRenames = new()
    {
        ["smithing_time"] = "smithing_speed",
        ["refining_precision"] = "refining_speed",
        ["critical_chance"] = "crit_chance",
    };

    private static readonly Dictionary<string, string> BonusKeyTypoFixes = new()
    {
        ["elemental_affinity"] = "elemental_afinity",
    };

    public List<TitleDefinition> EarnedTitles { get; } = new();

    public static string ToSnakeCase(string name) =>
        Regex.Replace(name, "(?<!^)(?=[A-Z])", "_").ToLowerInvariant();

    public double GetTotalBonus(string bonusType)
    {
        var candidates = ResolveBonusKeys(bonusType);
        var total = 0.0;
        foreach (var title in EarnedTitles)
        {
            foreach (var candidate in candidates)
            {
                if (title.Bonuses.ContainsKey(candidate))
                {
                    var value = title.Bonuses[candidate];
                    // Python isinstance((int, float)) — skips strings, but
                    // bool IS an int in Python, so JSON true sums as 1.0
                    if (value is JsonValue v)
                    {
                        if (v.TryGetValue<bool>(out var b))
                            total += b ? 1.0 : 0.0;
                        else if (v.TryGetValue<double>(out _) || v.TryGetValue<long>(out _))
                            total += J.AsNum(value) ?? 0.0;
                    }
                    break;
                }
            }
        }
        return total;
    }

    private static List<string> ResolveBonusKeys(string bonusType)
    {
        var candidates = new List<string> { bonusType };
        var snake = ToSnakeCase(bonusType);
        if (snake != bonusType)
            candidates.Add(snake);
        if (BonusKeyRenames.TryGetValue(snake, out var renamed))
            candidates.Add(renamed);
        if (BonusKeyTypoFixes.TryGetValue(snake, out var typo))
            candidates.Add(typo);
        return candidates;
    }

    public bool HasTitle(string titleId) =>
        EarnedTitles.Any(t => t.TitleId == titleId);
}
