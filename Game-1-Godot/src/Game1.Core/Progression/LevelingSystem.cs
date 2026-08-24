namespace Game1.Core.Progression;

/// <summary>
/// Port of entities/components/leveling.py — EXP with immediate level-up
/// cascades (2026-07 audit fix). The requirements table is int(200 *
/// 1.75^(lvl-1)) keyed by level; the NEXT level's entry is consumed, so the
/// first level-up costs 350 EXP (pinned P0 finding).
/// </summary>
public sealed class LevelingSystem
{
    public int Level = 1;
    public long CurrentExp;
    public const int MaxLevel = 30;
    public int UnallocatedStatPoints;

    private static readonly Dictionary<int, long> ExpRequirements =
        Enumerable.Range(1, MaxLevel)
            .ToDictionary(lvl => lvl, lvl => (long)(200 * Math.Pow(1.75, lvl - 1)));

    public long GetExpForNextLevel() =>
        Level >= MaxLevel ? 0 : ExpRequirements.GetValueOrDefault(Level + 1, 0);

    /// <summary>Returns true if at least one level-up resolved.</summary>
    public bool AddExp(long amount)
    {
        if (Level >= MaxLevel) return false;
        CurrentExp += amount;
        var leveled = false;
        while (Level < MaxLevel)
        {
            var expNeeded = GetExpForNextLevel();
            if (expNeeded <= 0 || CurrentExp < expNeeded)
                break;
            CurrentExp -= expNeeded;
            Level += 1;
            UnallocatedStatPoints += 1;
            leveled = true;
        }
        return leveled;
    }
}
