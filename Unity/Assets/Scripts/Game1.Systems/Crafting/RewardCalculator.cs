// ============================================================================
// Game1.Systems.Crafting.RewardCalculator
// Migrated from: core/reward_calculator.py
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Systems.Crafting
{
    // =========================================================================
    // Performance Data Classes
    // =========================================================================

    /// <summary>Smithing performance metrics for reward calculation.</summary>
    public class SmithingPerformance
    {
        public float AvgHammerScore;   // 0-100
        public bool TempInIdeal;
        public int Attempt = 1;        // 1 = first try
    }

    /// <summary>Alchemy performance metrics for reward calculation.</summary>
    public class AlchemyPerformance
    {
        public int ChainsCompleted;
        public int TotalChains = 1;
        public float AvgTimingScore;   // 0-100
        public int Explosions;
        public int Attempt = 1;
    }

    /// <summary>Refining performance metrics (binary success/fail).</summary>
    public class RefiningPerformance
    {
        public bool Success;
        public int InputQuantity = 1;
    }

    /// <summary>Engineering performance metrics for reward calculation.</summary>
    public class EngineeringPerformance
    {
        public int PuzzlesSolved;
        public int TotalPuzzles = 1;
        public int HintsUsed;
        public float TimeRemaining;    // Fraction of time left (0-1)
        public int Attempt = 1;
    }

    /// <summary>Enchanting performance metrics for reward calculation.</summary>
    public class EnchantingPerformance
    {
        public int FinalCurrency = 100;
        public int SpinsCompleted;
        public int GreenHits;
        public int RedHits;
    }

    /// <summary>
    /// Crafting reward result. All discipline reward methods produce this.
    /// </summary>
    public class CraftingReward
    {
        public float StatMultiplier = 1.0f;
        public string QualityTier = "Normal";
        public int BonusPct;
        public float PerformanceScore;
        public float MaxMultiplier = 1.0f;
        public bool FirstTryEligible;
        public bool FirstTryBonusApplied;

        // Alchemy-specific
        public float PotencyMultiplier = 1.0f;
        public float DurationMultiplier = 1.0f;

        // Refining-specific
        public bool Success = true;
        public int MaxRarityUpgrade;
        public float QualityMultiplier = 1.0f;
        public float MaterialLoss;

        // Engineering-specific
        public float EfficiencyMultiplier = 1.0f;
        public int DurabilityBonus;

        // Enchanting-specific
        public float EfficacyMultiplier = 1.0f;
        public int CurrencyChange;

        // Fishing-specific
        public string Quality = "Normal";
        public int ExperienceReward;
        public float BonusMultiplier = 1.0f;
    }

    // =========================================================================
    // Reward Calculator
    // =========================================================================

    /// <summary>
    /// Centralized reward calculation for crafting minigames that scales with difficulty.
    /// Full port from core/reward_calculator.py.
    ///
    /// Core Principle:
    ///   Reward Potential = f(difficulty, performance)
    ///   - Higher difficulty = higher maximum achievable bonus
    ///   - Better performance = closer to that maximum
    ///   - First-try bonus feeds into performance calculation
    /// </summary>
    public static class RewardCalculator
    {
        // =====================================================================
        // CONSTANTS (preserved exactly from Python)
        // =====================================================================

        /// <summary>Difficulty scaling ranges for max reward calculation.</summary>
        public static readonly (float Min, float Max) DifficultyRange = (1.0f, 80.0f);

        /// <summary>Reward multiplier range.</summary>
        public static readonly (float Min, float Max) RewardMultiplierRange = (1.0f, 2.5f);

        /// <summary>Failure penalty scaling.</summary>
        public static readonly (float Min, float Max) FailurePenalty = (0.30f, 0.90f);

        /// <summary>First-try performance boost: +10%.</summary>
        public const float FirstTryBoost = 0.10f;

        /// <summary>First-try eligible threshold: must achieve 50%+ performance.</summary>
        public const float FirstTryThreshold = 0.50f;

        /// <summary>Quality tier thresholds: (minScore, maxScore, tierName).</summary>
        public static readonly (float Min, float Max, string Name)[] QualityTiers =
        {
            (0.00f, 0.25f, "Normal"),
            (0.25f, 0.50f, "Fine"),
            (0.50f, 0.75f, "Superior"),
            (0.75f, 0.90f, "Masterwork"),
            (0.90f, 1.01f, "Legendary")     // 1.01 to include 1.0 exactly
        };

        // =====================================================================
        // CORE REWARD FUNCTIONS
        // =====================================================================

        /// <summary>
        /// Calculate maximum achievable reward multiplier based on difficulty.
        /// Formula: 1.0 + (normalized_difficulty * 1.5)
        /// Range: 1.0 to 2.5.
        /// </summary>
        public static float CalculateMaxRewardMultiplier(float difficultyPoints)
        {
            float minPts = DifficultyRange.Min;
            float maxPts = DifficultyRange.Max;

            float normalized = Math.Clamp((difficultyPoints - minPts) / (maxPts - minPts), 0f, 1f);

            float multRange = RewardMultiplierRange.Max - RewardMultiplierRange.Min;
            return RewardMultiplierRange.Min + (normalized * multRange);
        }

        /// <summary>
        /// Map performance score (0-1) to quality tier name.
        /// </summary>
        public static string GetQualityTier(float performanceScore)
        {
            foreach (var tier in QualityTiers)
            {
                if (performanceScore >= tier.Min && performanceScore < tier.Max)
                    return tier.Name;
            }
            return "Legendary"; // Fallback for 1.0 exactly
        }

        /// <summary>
        /// Calculate percentage bonus for crafted item stats.
        /// Formula: int(performance * (maxMultiplier - 1.0) * 20)
        /// </summary>
        public static int CalculateBonusPct(float performance, float maxMultiplier)
        {
            return (int)(performance * (maxMultiplier - 1.0f) * 20f);
        }

        /// <summary>
        /// Calculate stat multiplier for crafted item.
        /// Formula: 1.0 + (bonusPct / 100.0)
        /// </summary>
        public static float CalculateStatMultiplier(float performance, float maxMultiplier)
        {
            int bonusPct = CalculateBonusPct(performance, maxMultiplier);
            return 1.0f + (bonusPct / 100.0f);
        }

        // =====================================================================
        // FAILURE PENALTY
        // =====================================================================

        /// <summary>
        /// Calculate material loss on minigame failure.
        /// Scales from 30% (easy) to 90% (hard).
        /// Formula: 0.3 + (normalized_difficulty * 0.6)
        /// </summary>
        public static float CalculateFailurePenalty(float difficultyPoints)
        {
            float minPts = DifficultyRange.Min;
            float maxPts = DifficultyRange.Max;

            float normalized = Math.Clamp((difficultyPoints - minPts) / (maxPts - minPts), 0f, 1f);

            float lossRange = FailurePenalty.Max - FailurePenalty.Min;
            return FailurePenalty.Min + (normalized * lossRange);
        }

        /// <summary>
        /// Calculate specific material quantities lost on failure.
        /// </summary>
        public static Dictionary<string, int> CalculateMaterialLoss(
            List<RecipeInput> inputs,
            float difficultyPoints)
        {
            float lossFraction = CalculateFailurePenalty(difficultyPoints);
            var losses = new Dictionary<string, int>();

            if (inputs == null) return losses;

            foreach (var inp in inputs)
            {
                string materialId = inp.MaterialId ?? inp.ItemId ?? "";
                int quantity = inp.Quantity;
                int lost = (int)(quantity * lossFraction);
                if (lost > 0)
                    losses[materialId] = lost;
            }

            return losses;
        }

        // =====================================================================
        // DISCIPLINE-SPECIFIC REWARD FUNCTIONS
        // =====================================================================

        /// <summary>
        /// Calculate smithing rewards based on performance.
        /// Performance: avgHammerScore * tempBonus(1.2 if ideal) / 120, clamp 0-1.
        /// </summary>
        public static CraftingReward CalculateSmithingRewards(
            float difficultyPoints,
            SmithingPerformance perf)
        {
            float maxMultiplier = CalculateMaxRewardMultiplier(difficultyPoints);

            float avgScore = perf.AvgHammerScore;
            float tempBonus = perf.TempInIdeal ? 1.2f : 1.0f;

            // Max possible score: 100 * 1.2 = 120
            float basePerformance = Math.Min(1.0f, (avgScore * tempBonus) / 120f);

            // Apply first-try bonus
            bool firstTryApplied = false;
            if (perf.Attempt == 1)
            {
                basePerformance = Math.Min(1.0f, basePerformance + FirstTryBoost);
                firstTryApplied = true;
            }

            int bonusPct = CalculateBonusPct(basePerformance, maxMultiplier);
            float statMult = CalculateStatMultiplier(basePerformance, maxMultiplier);
            string qualityTier = GetQualityTier(basePerformance);

            bool firstTryEligible = perf.Attempt == 1 && basePerformance >= FirstTryThreshold;

            return new CraftingReward
            {
                StatMultiplier = statMult,
                QualityTier = qualityTier,
                BonusPct = bonusPct,
                PerformanceScore = basePerformance,
                MaxMultiplier = maxMultiplier,
                FirstTryEligible = firstTryEligible,
                FirstTryBonusApplied = firstTryApplied
            };
        }

        /// <summary>
        /// Calculate alchemy rewards based on reaction chain performance.
        /// </summary>
        public static CraftingReward CalculateAlchemyRewards(
            float difficultyPoints,
            AlchemyPerformance perf)
        {
            float maxMultiplier = CalculateMaxRewardMultiplier(difficultyPoints);

            // Chain completion ratio
            float chainScore = (float)perf.ChainsCompleted / Math.Max(1, perf.TotalChains);

            // Timing precision
            float timingScore = perf.AvgTimingScore / 100f;

            // Explosion penalty
            float explosionPenalty = perf.Explosions * 0.15f;

            // Base performance
            float basePerformance = (chainScore * 0.6f + timingScore * 0.4f) - explosionPenalty;
            basePerformance = Math.Clamp(basePerformance, 0f, 1f);

            // First-try bonus
            bool firstTryApplied = false;
            if (perf.Attempt == 1)
            {
                basePerformance = Math.Min(1.0f, basePerformance + FirstTryBoost);
                firstTryApplied = true;
            }

            int bonusPct = CalculateBonusPct(basePerformance, maxMultiplier);
            string qualityTier = GetQualityTier(basePerformance);

            // Potency and duration scale with performance
            float potencyMult = 1.0f + (basePerformance - 0.5f) * (maxMultiplier - 1.0f);
            float durationMult = 1.0f + (basePerformance - 0.5f) * (maxMultiplier - 1.0f) * 0.6f;

            // Clamp to reasonable bounds (25% to 200%)
            potencyMult = Math.Clamp(potencyMult, 0.25f, 2.0f);
            durationMult = Math.Clamp(durationMult, 0.25f, 2.0f);

            return new CraftingReward
            {
                QualityTier = qualityTier,
                BonusPct = bonusPct,
                PerformanceScore = basePerformance,
                MaxMultiplier = maxMultiplier,
                FirstTryBonusApplied = firstTryApplied,
                PotencyMultiplier = potencyMult,
                DurationMultiplier = durationMult
            };
        }

        /// <summary>
        /// Calculate refining rewards.
        /// Refining uses rarity upgrade based on difficulty + input quantity.
        /// </summary>
        public static CraftingReward CalculateRefiningRewards(
            float difficultyPoints,
            RefiningPerformance perf)
        {
            if (!perf.Success)
            {
                float materialLoss = CalculateFailurePenalty(difficultyPoints);
                return new CraftingReward
                {
                    Success = false,
                    MaxRarityUpgrade = 0,
                    QualityMultiplier = 1.0f,
                    MaterialLoss = materialLoss
                };
            }

            float maxMultiplier = CalculateMaxRewardMultiplier(difficultyPoints);

            // Rarity upgrade tiers based on difficulty
            int difficultyBasedMax = (int)(1 + (maxMultiplier - 1.0f) * 2);

            // Input-based limit (4:1 ratio per tier)
            int quantityBasedMax;
            if (perf.InputQuantity >= 256)
                quantityBasedMax = 4;
            else if (perf.InputQuantity >= 64)
                quantityBasedMax = 3;
            else if (perf.InputQuantity >= 16)
                quantityBasedMax = 2;
            else if (perf.InputQuantity >= 4)
                quantityBasedMax = 1;
            else
                quantityBasedMax = 0;

            int maxRarityUpgrade = Math.Min(difficultyBasedMax, quantityBasedMax);

            return new CraftingReward
            {
                Success = true,
                MaxRarityUpgrade = maxRarityUpgrade,
                QualityMultiplier = maxMultiplier,
                MaterialLoss = 0f
            };
        }

        /// <summary>
        /// Calculate engineering rewards based on puzzle completion.
        /// </summary>
        public static CraftingReward CalculateEngineeringRewards(
            float difficultyPoints,
            EngineeringPerformance perf)
        {
            float maxMultiplier = CalculateMaxRewardMultiplier(difficultyPoints);

            // Puzzle completion is primary
            float completionScore = (float)perf.PuzzlesSolved / Math.Max(1, perf.TotalPuzzles);

            // Time bonus for finishing early
            float timeBonus = perf.TimeRemaining * 0.2f;

            // Hint penalty
            float hintPenalty = perf.HintsUsed * 0.1f;

            float basePerformance = completionScore + timeBonus - hintPenalty;
            basePerformance = Math.Clamp(basePerformance, 0f, 1f);

            // First-try bonus
            bool firstTryApplied = false;
            if (perf.Attempt == 1)
            {
                basePerformance = Math.Min(1.0f, basePerformance + FirstTryBoost);
                firstTryApplied = true;
            }

            int bonusPct = CalculateBonusPct(basePerformance, maxMultiplier);
            string qualityTier = GetQualityTier(basePerformance);

            // Efficiency and durability bonuses
            float efficiencyMult = 1.0f + (basePerformance * (maxMultiplier - 1.0f) * 0.4f);
            int durabilityBonus = (int)(basePerformance * 50); // Up to +50

            return new CraftingReward
            {
                QualityTier = qualityTier,
                BonusPct = bonusPct,
                PerformanceScore = basePerformance,
                MaxMultiplier = maxMultiplier,
                FirstTryBonusApplied = firstTryApplied,
                EfficiencyMultiplier = efficiencyMult,
                DurabilityBonus = durabilityBonus
            };
        }

        /// <summary>
        /// Calculate enchanting rewards based on wheel spin outcomes.
        /// Performance: finalCurrency / 200, clamp 0-1.
        /// </summary>
        public static CraftingReward CalculateEnchantingRewards(
            float difficultyPoints,
            EnchantingPerformance perf)
        {
            float maxMultiplier = CalculateMaxRewardMultiplier(difficultyPoints);

            int finalCurrency = perf.FinalCurrency;
            int starting = 100;

            // Currency difference determines efficacy
            int currencyDiff = finalCurrency - starting;
            float efficacyModifier = currencyDiff / 200f; // -0.5 to +0.5

            // Performance score based on final currency
            // 0 currency = 0%, 100 = 50%, 200 = 100%
            float basePerformance = Math.Clamp(finalCurrency / 200f, 0f, 1f);

            int bonusPct = CalculateBonusPct(basePerformance, maxMultiplier);
            string qualityTier = GetQualityTier(basePerformance);

            // Efficacy multiplier affects enchantment power
            float efficacyMult = 1.0f + efficacyModifier;

            return new CraftingReward
            {
                QualityTier = qualityTier,
                BonusPct = bonusPct,
                PerformanceScore = basePerformance,
                MaxMultiplier = maxMultiplier,
                EfficacyMultiplier = efficacyMult,
                CurrencyChange = currencyDiff
            };
        }

        // =====================================================================
        // UTILITY FUNCTIONS
        // =====================================================================

        /// <summary>
        /// Get a human-readable reward description.
        /// </summary>
        public static string GetRewardDescription(int bonusPct, string qualityTier)
        {
            if (bonusPct == 0)
                return $"{qualityTier} quality (base stats)";
            else
                return $"{qualityTier} quality (+{bonusPct}% bonus)";
        }

        /// <summary>
        /// Estimate potential rewards for a given difficulty at various performance levels.
        /// </summary>
        public static Dictionary<string, object> EstimateRewardPotential(float difficultyPoints)
        {
            float maxMult = CalculateMaxRewardMultiplier(difficultyPoints);

            return new Dictionary<string, object>
            {
                ["max_multiplier"] = maxMult,
                ["at_50_percent"] = new Dictionary<string, object>
                {
                    ["bonus_pct"] = CalculateBonusPct(0.5f, maxMult),
                    ["quality"] = GetQualityTier(0.5f)
                },
                ["at_75_percent"] = new Dictionary<string, object>
                {
                    ["bonus_pct"] = CalculateBonusPct(0.75f, maxMult),
                    ["quality"] = GetQualityTier(0.75f)
                },
                ["at_100_percent"] = new Dictionary<string, object>
                {
                    ["bonus_pct"] = CalculateBonusPct(1.0f, maxMult),
                    ["quality"] = GetQualityTier(1.0f)
                },
                ["failure_penalty"] = CalculateFailurePenalty(difficultyPoints)
            };
        }
    }
}
