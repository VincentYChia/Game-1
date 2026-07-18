namespace Game1.Core;

/// <summary>
/// Sacred balance constants. Values are pinned by golden fixtures generated
/// from the Python reference build (conformance/goldens/) — change them there
/// first, regenerate, and let the tests tell you what moved.
/// Provenance is cited per constant; the CODE is the source of truth, not docs.
/// </summary>
public static class GameConstants
{
    // EXP curve — entities/components/leveling.py:9
    // requirement[level] = (long)(200 * 1.75^(level-1)); consumption is
    // offset by one: leveling from L to L+1 costs requirement[L+1]
    // (leveling.py:13). The first level-up therefore costs 350, not 200.
    public const double ExpBase = 200.0;
    public const double ExpGrowth = 1.75;
    public const int MaxLevel = 30;

    // Damage pipeline — Combat/combat_manager.py:17,24 (env-overridable in
    // Python via CRUX_STR_DMG_PER_POINT / CRUX_LCK_CRIT_PER_POINT; these are
    // the shipped defaults, LCK retuned 0.02 -> 0.12 in July 2026).
    public const double StrDamagePerPoint = 0.05;
    public const double LckCritPerPoint = 0.12;
    // INT elemental damage — combat_manager.py:1656 (tag-gated)
    public const double IntElementalPerPoint = 0.05;
    public const double CritMultiplier = 2.0;
    // Enemy defense — core/effect_executor.py:166-168
    public const double DefenseReductionPerPoint = 0.01;
    public const double DefenseReductionCap = 0.75;

    // Tier multipliers — docs/GAME_MECHANICS_V6.md; T1..T4
    public static readonly IReadOnlyDictionary<int, double> TierMultipliers =
        new Dictionary<int, double> { [1] = 1.0, [2] = 2.0, [3] = 4.0, [4] = 8.0 };

    // Durability floor — items never break; 0% durability = 50% effectiveness
    public const double DurabilityFloorEffectiveness = 0.5;
}
