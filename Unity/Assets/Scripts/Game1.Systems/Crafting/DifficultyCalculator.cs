// ============================================================================
// Game1.Systems.Crafting.DifficultyCalculator
// Migrated from: core/difficulty_calculator.py
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Systems.Crafting
{
    // =========================================================================
    // Difficulty Parameter Classes
    // =========================================================================

    /// <summary>
    /// Smithing minigame difficulty parameters.
    /// Temperature management + hammer timing.
    /// </summary>
    public class SmithingDifficultyParams
    {
        public float DifficultyPoints;
        public string DifficultyTier;
        public int TierFallback;

        public float TimeLimit;
        public float TempIdealRange;
        public float TempIdealMin;
        public float TempIdealMax;
        public float TempDecayRate;
        public float TempFanIncrement;
        public int RequiredHits;
        public float TargetWidth;
        public float PerfectWidth;
        public float HammerSpeed;
    }

    /// <summary>
    /// Refining minigame difficulty parameters.
    /// Lockpicking-style cylinder alignment.
    /// </summary>
    public class RefiningDifficultyParams
    {
        public float DifficultyPoints;
        public string DifficultyTier;
        public float DiversityMultiplier;
        public float StationMultiplier;
        public int TierFallback;

        public int TimeLimit;
        public int CylinderCount;
        public float TimingWindow;
        public float RotationSpeed;
        public int AllowedFailures;
        public bool MultiSpeed;
    }

    /// <summary>
    /// Alchemy minigame difficulty parameters.
    /// Reaction chain management.
    /// </summary>
    public class AlchemyDifficultyParams
    {
        public float DifficultyPoints;
        public string DifficultyTier;
        public float DiversityMultiplier;
        public float TierModifier;
        public float Volatility;
        public float AvgTier;
        public int TierFallback;

        public int TimeLimit;
        public int ReactionCount;
        public float SweetSpotDuration;
        public float StageDuration;
        public int FalsePeaks;
    }

    /// <summary>
    /// Engineering minigame difficulty parameters.
    /// Sequential cognitive puzzles.
    /// </summary>
    public class EngineeringDifficultyParams
    {
        public float DifficultyPoints;
        public string DifficultyTier;
        public float DiversityMultiplier;
        public float SlotModifier;
        public int TotalSlots;
        public int TierFallback;

        public int TimeLimit;
        public int PuzzleCount;
        public int GridSize;
        public int Complexity;
        public int HintsAllowed;
        public int IdealMoves;
    }

    /// <summary>
    /// Enchanting minigame difficulty parameters.
    /// Spinning wheel gambling.
    /// </summary>
    public class EnchantingDifficultyParams
    {
        public float DifficultyPoints;
        public string DifficultyTier;
        public float DiversityMultiplier;
        public int TierFallback;

        public int StartingCurrency;
        public int GreenSlices;
        public int RedSlices;
        public int GreySlices;
        public float GreenMultiplier;
        public float RedMultiplier;
        public int SpinCount;
    }

    // =========================================================================
    // Difficulty Calculator
    // =========================================================================

    /// <summary>
    /// Centralized difficulty calculation for crafting minigames based on material
    /// tier point values. Full port from core/difficulty_calculator.py.
    ///
    /// Core Principle: Difficulty = f(material_tiers, material_count, discipline_modifiers)
    ///
    /// Material Point System (Linear):
    ///   T1=1, T2=2, T3=3, T4=4 points per item
    /// </summary>
    public static class DifficultyCalculator
    {
        // =====================================================================
        // CONSTANTS (preserved exactly from Python)
        // =====================================================================

        /// <summary>Tier point values (LINEAR scaling): T1=1, T2=2, T3=3, T4=4</summary>
        public static readonly Dictionary<int, int> TierPoints = new()
        {
            { 1, 1 },
            { 2, 2 },
            { 3, 3 },
            { 4, 4 }
        };

        /// <summary>
        /// Difficulty thresholds matching rarity naming.
        /// Adjusted based on actual recipe difficulty distribution analysis.
        /// </summary>
        public static readonly Dictionary<string, (int Min, int Max)> DifficultyThresholds = new()
        {
            { "common",    (0, 4) },
            { "uncommon",  (5, 10) },
            { "rare",      (11, 20) },
            { "epic",      (21, 40) },
            { "legendary", (41, 150) }
        };

        /// <summary>Default scaling range for interpolation.</summary>
        public const float MinPoints = 1.0f;
        public const float MaxPoints = 80.0f;

        // =====================================================================
        // SMITHING PARAMETERS - Forge/Anvil minigame
        // (easy_value, hard_value)
        // =====================================================================
        private static readonly Dictionary<string, (float Easy, float Hard)> SmithingParams = new()
        {
            { "time_limit",         (60f, 25f) },
            { "temp_ideal_range",   (25f, 3f) },
            { "temp_decay_rate",    (0.3f, 0.6f) },
            { "temp_fan_increment", (4f, 1.5f) },
            { "required_hits",      (3f, 12f) },
            { "target_width",       (100f, 30f) },
            { "perfect_width",      (50f, 10f) },
            { "hammer_speed",       (3.0f, 14.0f) }
        };

        // =====================================================================
        // REFINING PARAMETERS - Lock/Tumbler minigame
        // =====================================================================
        private static readonly Dictionary<string, (float Easy, float Hard)> RefiningParams = new()
        {
            { "time_limit",       (45f, 15f) },
            { "cylinder_count",   (3f, 12f) },
            { "timing_window",    (0.05f, 0.01f) },
            { "rotation_speed",   (1.0f, 4.0f) },
            { "allowed_failures", (2f, 0f) }
        };

        // =====================================================================
        // ALCHEMY PARAMETERS - Reaction chain minigame
        // =====================================================================
        private static readonly Dictionary<string, (float Easy, float Hard)> AlchemyParams = new()
        {
            { "time_limit",           (60f, 20f) },
            { "reaction_count",       (2f, 6f) },
            { "sweet_spot_duration",  (2.0f, 0.4f) },
            { "stage_duration",       (2.5f, 0.8f) },
            { "false_peaks",          (0f, 5f) },
            { "volatility",           (0.0f, 1.0f) }
        };

        // =====================================================================
        // ENGINEERING PARAMETERS - Puzzle minigame
        // =====================================================================
        private static readonly Dictionary<string, (float Easy, float Hard)> EngineeringParams = new()
        {
            { "time_limit",     (300f, 120f) },
            { "puzzle_count",   (1f, 2f) },
            { "grid_size",      (3f, 4f) },
            { "complexity",     (1f, 3f) },
            { "hints_allowed",  (4f, 1f) },
            { "ideal_moves",    (6f, 8f) }
        };

        // =====================================================================
        // ENCHANTING PARAMETERS - Wheel spin minigame
        // =====================================================================
        private static readonly Dictionary<string, (float Easy, float Hard)> EnchantingParams = new()
        {
            { "starting_currency", (100f, 100f) },
            { "green_slices",      (12f, 6f) },
            { "red_slices",        (3f, 10f) },
            { "green_multiplier",  (1.5f, 1.2f) },
            { "red_multiplier",    (0.8f, 0.0f) },
            { "spin_count",        (3f, 3f) }
        };

        // =====================================================================
        // ENGINEERING IDEAL MOVES - 12-tier thresholds
        // Maps difficulty_points ranges to ideal_moves (6, 7, or 8)
        // =====================================================================
        private static readonly (float MaxPoints, int IdealMoves)[] EngineeringIdealMovesTiers =
        {
            (8f, 6),
            (13f, 6),
            (18f, 6),
            (23f, 6),
            (35f, 7),
            (44f, 7),
            (50f, 7),
            (56f, 7),
            (68f, 8),
            (76f, 8),
            (100f, 8),
            (999f, 8)
        };

        // =====================================================================
        // CORE CALCULATION FUNCTIONS
        // =====================================================================

        /// <summary>
        /// Calculate total difficulty points from recipe inputs.
        /// Each material contributes: tier * quantity (LINEAR).
        /// </summary>
        /// <param name="inputs">List of recipe inputs with MaterialId, Quantity, and Tier.</param>
        /// <param name="materialTierLookup">
        /// Optional function to look up material tier by ID.
        /// If null, defaults tier to 1.
        /// </param>
        /// <returns>Total difficulty points (minimum 1.0).</returns>
        public static float CalculateMaterialPoints(
            List<RecipeInput> inputs,
            Func<string, int> materialTierLookup = null)
        {
            if (inputs == null || inputs.Count == 0)
                return 1.0f;

            float totalPoints = 0f;

            foreach (var inp in inputs)
            {
                string materialId = inp.MaterialId ?? inp.ItemId ?? "";
                int quantity = inp.Quantity > 0 ? inp.Quantity : 1;

                int tier = 1;
                if (materialTierLookup != null)
                {
                    tier = materialTierLookup(materialId);
                    if (tier <= 0) tier = 1;
                }
                else if (inp.Tier > 0)
                {
                    tier = inp.Tier;
                }

                int tierPts = TierPoints.TryGetValue(tier, out var pts) ? pts : tier;
                totalPoints += tierPts * quantity;
            }

            return Math.Max(1.0f, totalPoints);
        }

        /// <summary>
        /// Calculate difficulty multiplier based on unique material count.
        /// Formula: 1.0 + (unique_count - 1) * 0.1
        /// </summary>
        public static float CalculateDiversityMultiplier(List<RecipeInput> inputs)
        {
            if (inputs == null || inputs.Count == 0)
                return 1.0f;

            var uniqueMaterials = new HashSet<string>();
            foreach (var inp in inputs)
            {
                string materialId = inp.MaterialId ?? inp.ItemId ?? "";
                if (!string.IsNullOrEmpty(materialId))
                    uniqueMaterials.Add(materialId);
            }

            int uniqueCount = uniqueMaterials.Count;
            return 1.0f + (uniqueCount - 1) * 0.1f;
        }

        /// <summary>
        /// Calculate weighted average tier of materials.
        /// Used for alchemy tier exponential modifier (1.2^avg_tier).
        /// </summary>
        public static float CalculateAverageTier(
            List<RecipeInput> inputs,
            Func<string, int> materialTierLookup = null)
        {
            if (inputs == null || inputs.Count == 0)
                return 1.0f;

            float totalTier = 0f;
            int totalQuantity = 0;

            foreach (var inp in inputs)
            {
                string materialId = inp.MaterialId ?? inp.ItemId ?? "";
                int quantity = inp.Quantity > 0 ? inp.Quantity : 1;

                int tier = 1;
                if (materialTierLookup != null)
                {
                    tier = materialTierLookup(materialId);
                    if (tier <= 0) tier = 1;
                }
                else if (inp.Tier > 0)
                {
                    tier = inp.Tier;
                }

                totalTier += tier * quantity;
                totalQuantity += quantity;
            }

            if (totalQuantity == 0) return 1.0f;
            return totalTier / totalQuantity;
        }

        /// <summary>
        /// Get the rarity-style difficulty tier name.
        /// </summary>
        public static string GetDifficultyTier(float points)
        {
            foreach (var kvp in DifficultyThresholds)
            {
                if (points >= kvp.Value.Min && points <= kvp.Value.Max)
                    return kvp.Key;
            }

            // If above all thresholds, legendary
            if (points > DifficultyThresholds["legendary"].Max)
                return "legendary";

            return "common";
        }

        /// <summary>
        /// Get a human-readable difficulty description (capitalized tier name).
        /// </summary>
        public static string GetDifficultyDescription(float points)
        {
            string tier = GetDifficultyTier(points);
            if (string.IsNullOrEmpty(tier)) return "Common";
            return char.ToUpper(tier[0]) + tier.Substring(1);
        }

        /// <summary>
        /// Normalize points to 0-1 range.
        /// Range: MinPoints=1 to MaxPoints=80.
        /// </summary>
        public static float CalculateNormalizedDifficulty(float points)
        {
            return Math.Clamp((points - MinPoints) / (MaxPoints - MinPoints), 0f, 1f);
        }

        /// <summary>
        /// Linear interpolation between easy and hard values.
        /// Formula: easy + (hard - easy) * normalized
        /// </summary>
        public static float InterpolateParam(float easy, float hard, float normalized)
        {
            return easy + (hard - easy) * normalized;
        }

        /// <summary>
        /// Map difficulty points to parameter values via linear interpolation.
        /// </summary>
        private static Dictionary<string, float> InterpolateDifficulty(
            float points,
            Dictionary<string, (float Easy, float Hard)> paramRanges,
            float? minPts = null,
            float? maxPts = null)
        {
            float minP = minPts ?? MinPoints;
            float maxP = maxPts ?? MaxPoints;

            float normalized = Math.Clamp((points - minP) / (maxP - minP), 0f, 1f);

            var result = new Dictionary<string, float>();
            foreach (var kvp in paramRanges)
            {
                result[kvp.Key] = kvp.Value.Easy + (kvp.Value.Hard - kvp.Value.Easy) * normalized;
            }
            return result;
        }

        // =====================================================================
        // DISCIPLINE-SPECIFIC DIFFICULTY FUNCTIONS
        // =====================================================================

        /// <summary>
        /// Calculate smithing difficulty based on material points.
        /// Smithing does NOT use diversity multiplier (single-focus craft).
        /// INT stat: -2% difficulty per point (multiply normalized by 1 - INT*0.02).
        /// </summary>
        public static SmithingDifficultyParams GetSmithingParams(
            List<RecipeInput> inputs,
            int stationTier = 1,
            int intStat = 0,
            Func<string, int> materialTierLookup = null)
        {
            float totalPoints = CalculateMaterialPoints(inputs, materialTierLookup);

            // Apply INT stat: reduce normalized difficulty
            float normalized = CalculateNormalizedDifficulty(totalPoints);
            float intReduction = 1.0f - intStat * 0.02f;
            normalized = Math.Clamp(normalized * intReduction, 0f, 1f);

            // Interpolate parameters using modified normalized value
            var p = new SmithingDifficultyParams();
            p.DifficultyPoints = totalPoints;
            p.DifficultyTier = GetDifficultyTier(totalPoints);
            p.TierFallback = stationTier;

            p.TimeLimit = InterpolateParam(SmithingParams["time_limit"].Easy, SmithingParams["time_limit"].Hard, normalized);
            p.TempIdealRange = InterpolateParam(SmithingParams["temp_ideal_range"].Easy, SmithingParams["temp_ideal_range"].Hard, normalized);
            p.TempDecayRate = InterpolateParam(SmithingParams["temp_decay_rate"].Easy, SmithingParams["temp_decay_rate"].Hard, normalized);
            p.TempFanIncrement = InterpolateParam(SmithingParams["temp_fan_increment"].Easy, SmithingParams["temp_fan_increment"].Hard, normalized);
            p.RequiredHits = (int)Math.Round(InterpolateParam(SmithingParams["required_hits"].Easy, SmithingParams["required_hits"].Hard, normalized));
            p.TargetWidth = InterpolateParam(SmithingParams["target_width"].Easy, SmithingParams["target_width"].Hard, normalized);
            p.PerfectWidth = InterpolateParam(SmithingParams["perfect_width"].Easy, SmithingParams["perfect_width"].Hard, normalized);
            p.HammerSpeed = InterpolateParam(SmithingParams["hammer_speed"].Easy, SmithingParams["hammer_speed"].Hard, normalized);

            // Convert temp_ideal_range to min/max values, centered around 70 degrees
            float tempRange = p.TempIdealRange;
            float centerTemp = 70f;
            p.TempIdealMin = Math.Clamp(centerTemp - tempRange / 2f, 55f, 75f);
            p.TempIdealMax = Math.Clamp(centerTemp + tempRange / 2f, p.TempIdealMin + 3f, 85f);

            return p;
        }

        /// <summary>
        /// Calculate refining difficulty based on material points x station tier x diversity.
        /// Station tier multiplier: 1.0 + (stationTier * 0.5).
        /// INT stat: -2% difficulty per point.
        /// </summary>
        public static RefiningDifficultyParams GetRefiningParams(
            List<RecipeInput> inputs,
            int stationTier = 1,
            int intStat = 0,
            Func<string, int> materialTierLookup = null)
        {
            float basePoints = CalculateMaterialPoints(inputs, materialTierLookup);
            float diversityMult = CalculateDiversityMultiplier(inputs);

            // Station tier multiplier: T1=1.5x, T2=2.5x, T3=3.5x, T4=4.5x
            float stationMult = 1.0f + (stationTier * 0.5f);
            float totalPoints = basePoints * diversityMult * stationMult;

            // Apply INT stat
            float normalized = CalculateNormalizedDifficulty(totalPoints);
            float intReduction = 1.0f - intStat * 0.02f;
            normalized = Math.Clamp(normalized * intReduction, 0f, 1f);

            var p = new RefiningDifficultyParams();
            p.DifficultyPoints = totalPoints;
            p.DifficultyTier = GetDifficultyTier(totalPoints);
            p.DiversityMultiplier = diversityMult;
            p.StationMultiplier = stationMult;
            p.TierFallback = stationTier;

            p.CylinderCount = Math.Max(2, (int)Math.Round(InterpolateParam(RefiningParams["cylinder_count"].Easy, RefiningParams["cylinder_count"].Hard, normalized)));
            p.TimingWindow = InterpolateParam(RefiningParams["timing_window"].Easy, RefiningParams["timing_window"].Hard, normalized);
            p.RotationSpeed = InterpolateParam(RefiningParams["rotation_speed"].Easy, RefiningParams["rotation_speed"].Hard, normalized);
            p.AllowedFailures = Math.Max(0, (int)Math.Round(InterpolateParam(RefiningParams["allowed_failures"].Easy, RefiningParams["allowed_failures"].Hard, normalized)));
            p.TimeLimit = (int)Math.Round(InterpolateParam(RefiningParams["time_limit"].Easy, RefiningParams["time_limit"].Hard, normalized));

            // Enable multi-speed for Rare+ difficulty
            p.MultiSpeed = totalPoints >= DifficultyThresholds["rare"].Min;

            return p;
        }

        /// <summary>
        /// Calculate alchemy difficulty based on material points x diversity x volatility.
        /// Alchemy-specific modifiers:
        /// - Tier exponential: 1.2^avg_tier modifier
        /// - Vowel-based volatility modifier
        /// INT stat: -2% difficulty per point.
        /// </summary>
        public static AlchemyDifficultyParams GetAlchemyParams(
            List<RecipeInput> inputs,
            int stationTier = 1,
            int intStat = 0,
            Func<string, int> materialTierLookup = null)
        {
            float basePoints = CalculateMaterialPoints(inputs, materialTierLookup);
            float diversityMult = CalculateDiversityMultiplier(inputs);
            float avgTier = CalculateAverageTier(inputs, materialTierLookup);

            // Alchemy tier exponential modifier
            float tierModifier = (float)Math.Pow(1.2, avgTier - 1.0);

            // Calculate volatility from material names
            float volatility = CalculateVolatility(inputs);

            // Total difficulty with alchemy modifiers
            float totalPoints = basePoints * diversityMult * tierModifier * (1f + volatility * 0.3f);

            // Apply INT stat
            float normalized = CalculateNormalizedDifficulty(totalPoints);
            float intReduction = 1.0f - intStat * 0.02f;
            normalized = Math.Clamp(normalized * intReduction, 0f, 1f);

            var p = new AlchemyDifficultyParams();
            p.DifficultyPoints = totalPoints;
            p.DifficultyTier = GetDifficultyTier(totalPoints);
            p.DiversityMultiplier = diversityMult;
            p.TierModifier = tierModifier;
            p.Volatility = volatility;
            p.AvgTier = avgTier;
            p.TierFallback = stationTier;

            p.ReactionCount = Math.Max(2, (int)Math.Round(InterpolateParam(AlchemyParams["reaction_count"].Easy, AlchemyParams["reaction_count"].Hard, normalized)));
            p.SweetSpotDuration = InterpolateParam(AlchemyParams["sweet_spot_duration"].Easy, AlchemyParams["sweet_spot_duration"].Hard, normalized);
            p.StageDuration = InterpolateParam(AlchemyParams["stage_duration"].Easy, AlchemyParams["stage_duration"].Hard, normalized);
            p.FalsePeaks = Math.Max(0, (int)Math.Round(InterpolateParam(AlchemyParams["false_peaks"].Easy, AlchemyParams["false_peaks"].Hard, normalized)));
            p.TimeLimit = (int)Math.Round(InterpolateParam(AlchemyParams["time_limit"].Easy, AlchemyParams["time_limit"].Hard, normalized));

            return p;
        }

        /// <summary>
        /// Calculate engineering difficulty based on slot count x diversity.
        /// INT stat: -2% difficulty per point.
        /// </summary>
        public static EngineeringDifficultyParams GetEngineeringParams(
            List<RecipeInput> inputs,
            int stationTier = 1,
            int intStat = 0,
            Func<string, int> materialTierLookup = null)
        {
            float basePoints = CalculateMaterialPoints(inputs, materialTierLookup);
            float diversityMult = CalculateDiversityMultiplier(inputs);

            // Count total slots used (sum of quantities)
            int totalSlots = 0;
            if (inputs != null)
            {
                foreach (var inp in inputs)
                    totalSlots += inp.Quantity > 0 ? inp.Quantity : 1;
            }

            // Slot modifier: 1.0 + (total_slots - 1) * 0.05
            float slotModifier = 1.0f + (totalSlots - 1) * 0.05f;
            float totalPoints = basePoints * diversityMult * slotModifier;

            // Apply INT stat
            float normalized = CalculateNormalizedDifficulty(totalPoints);
            float intReduction = 1.0f - intStat * 0.02f;
            normalized = Math.Clamp(normalized * intReduction, 0f, 1f);

            var p = new EngineeringDifficultyParams();
            p.DifficultyPoints = totalPoints;
            p.DifficultyTier = GetDifficultyTier(totalPoints);
            p.DiversityMultiplier = diversityMult;
            p.SlotModifier = slotModifier;
            p.TotalSlots = totalSlots;
            p.TierFallback = stationTier;

            p.PuzzleCount = Math.Max(1, (int)Math.Round(InterpolateParam(EngineeringParams["puzzle_count"].Easy, EngineeringParams["puzzle_count"].Hard, normalized)));
            p.GridSize = Math.Max(3, (int)Math.Round(InterpolateParam(EngineeringParams["grid_size"].Easy, EngineeringParams["grid_size"].Hard, normalized)));
            p.Complexity = Math.Clamp((int)Math.Round(InterpolateParam(EngineeringParams["complexity"].Easy, EngineeringParams["complexity"].Hard, normalized)), 1, 4);
            p.HintsAllowed = Math.Max(0, (int)Math.Round(InterpolateParam(EngineeringParams["hints_allowed"].Easy, EngineeringParams["hints_allowed"].Hard, normalized)));
            p.TimeLimit = (int)Math.Round(InterpolateParam(EngineeringParams["time_limit"].Easy, EngineeringParams["time_limit"].Hard, normalized));

            // Use 12-tier system for ideal moves (6-8 range)
            p.IdealMoves = GetEngineeringIdealMoves(totalPoints);

            return p;
        }

        /// <summary>
        /// Calculate enchanting difficulty for wheel spin minigame.
        /// Enchanting is NOT affected by INT stat.
        /// </summary>
        public static EnchantingDifficultyParams GetEnchantingParams(
            List<RecipeInput> inputs,
            int stationTier = 1,
            Func<string, int> materialTierLookup = null)
        {
            float basePoints = CalculateMaterialPoints(inputs, materialTierLookup);
            float diversityMult = CalculateDiversityMultiplier(inputs);
            float totalPoints = basePoints * diversityMult;

            // Enchanting: no INT reduction
            var rawParams = InterpolateDifficulty(totalPoints, EnchantingParams);

            var p = new EnchantingDifficultyParams();
            p.DifficultyPoints = totalPoints;
            p.DifficultyTier = GetDifficultyTier(totalPoints);
            p.DiversityMultiplier = diversityMult;
            p.TierFallback = stationTier;

            // Round slice counts (must total 20)
            int green = Math.Clamp((int)Math.Round(rawParams["green_slices"]), 4, 14);
            int red = Math.Clamp((int)Math.Round(rawParams["red_slices"]), 2, 12);

            // Ensure total is 20
            int grey = 20 - green - red;
            if (grey < 2)
            {
                int excess = 2 - grey;
                if (green > red)
                    green -= excess;
                else
                    red -= excess;
                grey = 2;
            }

            p.GreenSlices = green;
            p.RedSlices = red;
            p.GreySlices = grey;
            p.SpinCount = 3;
            p.StartingCurrency = 100;
            p.GreenMultiplier = rawParams["green_multiplier"];
            p.RedMultiplier = rawParams["red_multiplier"];

            return p;
        }

        // =====================================================================
        // HELPER FUNCTIONS
        // =====================================================================

        /// <summary>
        /// Get ideal moves for logic switch puzzle based on 12-tier difficulty system.
        /// Maps difficulty_points to ideal_moves (6, 7, or 8).
        /// </summary>
        public static int GetEngineeringIdealMoves(float difficultyPoints)
        {
            foreach (var tier in EngineeringIdealMovesTiers)
            {
                if (difficultyPoints <= tier.MaxPoints)
                    return tier.IdealMoves;
            }
            return 8; // Default to max
        }

        /// <summary>
        /// Calculate volatility based on vowel ratio in material names.
        /// More vowels = more volatile/unpredictable reactions.
        /// Returns 0.0 to 1.0.
        /// </summary>
        public static float CalculateVolatility(List<RecipeInput> inputs)
        {
            if (inputs == null || inputs.Count == 0)
                return 0f;

            const string vowels = "aeiouAEIOU";
            int totalChars = 0;
            int vowelCount = 0;

            foreach (var inp in inputs)
            {
                string materialId = inp.MaterialId ?? inp.ItemId ?? "";
                foreach (char c in materialId)
                {
                    if (char.IsLetter(c))
                    {
                        totalChars++;
                        if (vowels.IndexOf(c) >= 0)
                            vowelCount++;
                    }
                }
            }

            if (totalChars == 0)
                return 0f;

            // Normal vowel ratio is ~40%, normalize around that
            float vowelRatio = (float)vowelCount / totalChars;
            float volatility = Math.Clamp((vowelRatio - 0.3f) * 2.5f, 0f, 1f);
            return volatility;
        }

        /// <summary>
        /// Estimate expected completion time in seconds based on difficulty.
        /// </summary>
        public static int EstimateCompletionTime(float points, string discipline)
        {
            switch (discipline.ToLowerInvariant())
            {
                case "smithing":
                {
                    var p = InterpolateDifficulty(points, SmithingParams);
                    return (int)(p["time_limit"] * 0.8f);
                }
                case "refining":
                {
                    var p = InterpolateDifficulty(points, RefiningParams);
                    return (int)(p["cylinder_count"] * 2.5f);
                }
                default:
                    return 30;
            }
        }

        // =====================================================================
        // LEGACY FALLBACK (for recipes without proper material data)
        // =====================================================================

        /// <summary>Legacy smithing params by station tier.</summary>
        public static SmithingDifficultyParams GetLegacySmithingParams(int tier)
        {
            var p = new SmithingDifficultyParams();
            switch (Math.Clamp(tier, 1, 4))
            {
                case 1:
                    p.TimeLimit = 50; p.TempIdealMin = 60; p.TempIdealMax = 80;
                    p.TempDecayRate = 0.4f; p.TempFanIncrement = 3.5f; p.RequiredHits = 4;
                    p.TargetWidth = 90; p.PerfectWidth = 40; p.HammerSpeed = 2.5f;
                    p.DifficultyPoints = 4; p.DifficultyTier = "common";
                    break;
                case 2:
                    p.TimeLimit = 40; p.TempIdealMin = 62; p.TempIdealMax = 78;
                    p.TempDecayRate = 0.6f; p.TempFanIncrement = 2.8f; p.RequiredHits = 6;
                    p.TargetWidth = 70; p.PerfectWidth = 30; p.HammerSpeed = 3.5f;
                    p.DifficultyPoints = 12; p.DifficultyTier = "uncommon";
                    break;
                case 3:
                    p.TimeLimit = 32; p.TempIdealMin = 66; p.TempIdealMax = 74;
                    p.TempDecayRate = 0.9f; p.TempFanIncrement = 2f; p.RequiredHits = 9;
                    p.TargetWidth = 50; p.PerfectWidth = 18; p.HammerSpeed = 4.8f;
                    p.DifficultyPoints = 30; p.DifficultyTier = "rare";
                    break;
                case 4:
                    p.TimeLimit = 25; p.TempIdealMin = 68; p.TempIdealMax = 72;
                    p.TempDecayRate = 1.1f; p.TempFanIncrement = 1.5f; p.RequiredHits = 11;
                    p.TargetWidth = 38; p.PerfectWidth = 14; p.HammerSpeed = 5.8f;
                    p.DifficultyPoints = 60; p.DifficultyTier = "epic";
                    break;
            }
            p.TierFallback = tier;
            return p;
        }

        /// <summary>Legacy refining params by station tier.</summary>
        public static RefiningDifficultyParams GetLegacyRefiningParams(int tier)
        {
            var p = new RefiningDifficultyParams();
            switch (Math.Clamp(tier, 1, 4))
            {
                case 1:
                    p.TimeLimit = 40; p.CylinderCount = 3; p.TimingWindow = 0.35f;
                    p.RotationSpeed = 0.7f; p.AllowedFailures = 2; p.MultiSpeed = false;
                    p.DifficultyPoints = 4; p.DifficultyTier = "common"; p.DiversityMultiplier = 1.0f;
                    break;
                case 2:
                    p.TimeLimit = 30; p.CylinderCount = 5; p.TimingWindow = 0.25f;
                    p.RotationSpeed = 1.0f; p.AllowedFailures = 1; p.MultiSpeed = false;
                    p.DifficultyPoints = 12; p.DifficultyTier = "uncommon"; p.DiversityMultiplier = 1.0f;
                    break;
                case 3:
                    p.TimeLimit = 22; p.CylinderCount = 8; p.TimingWindow = 0.15f;
                    p.RotationSpeed = 1.5f; p.AllowedFailures = 1; p.MultiSpeed = true;
                    p.DifficultyPoints = 30; p.DifficultyTier = "rare"; p.DiversityMultiplier = 1.0f;
                    break;
                case 4:
                    p.TimeLimit = 18; p.CylinderCount = 10; p.TimingWindow = 0.10f;
                    p.RotationSpeed = 2.0f; p.AllowedFailures = 0; p.MultiSpeed = true;
                    p.DifficultyPoints = 60; p.DifficultyTier = "epic"; p.DiversityMultiplier = 1.0f;
                    break;
            }
            p.TierFallback = tier;
            return p;
        }
    }

    // =========================================================================
    // Recipe Input - Lightweight struct for difficulty calculation
    // =========================================================================

    /// <summary>
    /// Lightweight recipe input representation for difficulty/reward calculations.
    /// Compatible with Game1.Data.Models.Recipe once that exists.
    /// </summary>
    public class RecipeInput
    {
        public string MaterialId { get; set; }
        public string ItemId { get; set; }
        public int Quantity { get; set; } = 1;
        public int Tier { get; set; } = 1;

        /// <summary>Get the effective ID (MaterialId preferred, falls back to ItemId).</summary>
        public string EffectiveId => MaterialId ?? ItemId ?? "";
    }
}
