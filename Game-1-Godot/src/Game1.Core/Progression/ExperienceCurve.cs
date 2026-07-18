namespace Game1.Core.Progression;

/// <summary>
/// Port of entities/components/leveling.py::LevelingSystem, including the
/// July-2026 cascade fix: one large grant crossing several thresholds
/// resolves every level in the same call.
/// Semantics pinned by conformance/goldens/exp_curve.json.
/// </summary>
public sealed class ExperienceCurve
{
    public const int MaxLevel = GameConstants.MaxLevel;

    private static readonly long[] Requirements = BuildRequirements();

    public int Level { get; private set; } = 1;
    public long CurrentExp { get; private set; }
    public int UnallocatedStatPoints { get; private set; }

    /// <summary>Fires once per level gained (mirrors the LEVEL_UP bus publish).</summary>
    public event Action<int>? LeveledUp;

    private static long[] BuildRequirements()
    {
        // leveling.py:9 — int(200 * 1.75 ** (lvl - 1)); IEEE-754 double both sides.
        var req = new long[MaxLevel + 1];
        for (var lvl = 1; lvl <= MaxLevel; lvl++)
            req[lvl] = (long)(GameConstants.ExpBase * Math.Pow(GameConstants.ExpGrowth, lvl - 1));
        return req;
    }

    /// <summary>The table value for a level (1..30). Note the off-by-one
    /// consumption: leveling from L to L+1 costs RequirementForLevel(L + 1).</summary>
    public static long RequirementForLevel(int level) =>
        level is < 1 or > MaxLevel
            ? throw new ArgumentOutOfRangeException(nameof(level))
            : Requirements[level];

    /// <summary>leveling.py:12-13 — 0 at max level, else requirement[level + 1].</summary>
    public long ExpForNextLevel =>
        Level >= MaxLevel ? 0 : Requirements[Level + 1];

    /// <summary>leveling.py:15-49 — returns true if at least one level resolved.</summary>
    public bool AddExp(long amount)
    {
        if (Level >= MaxLevel)
            return false;

        CurrentExp += amount;
        var leveled = false;
        while (Level < MaxLevel)
        {
            var needed = ExpForNextLevel;
            if (needed <= 0 || CurrentExp < needed)
                break;
            CurrentExp -= needed;
            Level += 1;
            UnallocatedStatPoints += 1;
            leveled = true;
            LeveledUp?.Invoke(Level);
        }
        return leveled;
    }
}
