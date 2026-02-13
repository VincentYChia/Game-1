// ============================================================================
// Game1.Systems.Crafting.AlchemyMinigame
// Migrated from: Crafting-subdisciplines/alchemy.py (1052 lines)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Alchemy minigame: Reaction chain management.
//
// Process:
// 1. Start brewing with ingredient list
// 2. Each ingredient creates an AlchemyReaction that progresses through 5 stages
// 3. Player watches for visual cues (glow/size) and chains at optimal timing
// 4. Chain locks quality and starts next ingredient
// 5. Stabilize to end; explosion on stage 6 gives 10% and auto-advances
//
// Oscillation system:
// - Each ingredient has a secret value based on vowel ratio in its ID
// - 25% get 1 oscillation, 40% get 2, 35% get 3
// - Quality oscillates via sin waves with increasing amplitude
// - Max quality per ingredient based on vowel contribution to total
//
// Performance: sum of locked reaction qualities (0.0-1.0 across all ingredients)
//

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Systems.Crafting
{
    /// <summary>
    /// Individual ingredient reaction in the alchemy minigame.
    /// Progresses through 5 stages + explosion (stage 6).
    /// </summary>
    public class AlchemyReaction
    {
        // Stage durations (seconds per stage) for each ingredient type
        private static readonly float[] StableDurations = { 1.0f, 2.5f, 2.0f, 2.0f, 1.5f };
        private static readonly float[] ModerateDurations = { 0.8f, 2.0f, 1.5f, 1.5f, 1.2f };
        private static readonly float[] VolatileDurations = { 0.5f, 1.5f, 1.0f, 1.0f, 0.8f };
        private static readonly float[] LegendaryDurations = { 0.4f, 1.0f, 0.5f, 0.7f, 0.5f };

        // False peak positions in stage 2 progress (0-1)
        private static readonly float[] ModerateFalsePeaks = { 0.4f, 0.7f };
        private static readonly float[] VolatileFalsePeaks = { 0.3f, 0.5f, 0.7f, 0.9f };
        private static readonly float[] LegendaryFalsePeaks = { 0.2f, 0.4f, 0.5f, 0.6f, 0.8f };

        public string IngredientId { get; }
        public string IngredientType { get; }
        public float MaxQuality { get; }
        public int OscillationCount { get; }
        public float SecretValue { get; }

        // Reaction state
        public int Stage { get; private set; } = 1;     // 1-5, 6 = explosion
        public float Progress { get; private set; }       // 0.0-1.0 through current stage
        public float? LockedQuality { get; private set; }

        // Visual state
        public float Size { get; private set; }
        public float Glow { get; private set; }
        public float ColorShift { get; private set; }

        // Timing
        private float[] _stageDurations;
        private float[] _falsePeaks;
        private float _currentStageDuration;
        private Random _rng;

        public AlchemyReaction(
            string ingredientId,
            string ingredientType = "moderate",
            float speedBonus = 0f,
            float maxQuality = 0.30f,
            Random rng = null)
        {
            IngredientId = ingredientId;
            IngredientType = ingredientType;
            MaxQuality = maxQuality;
            _rng = rng ?? new Random();

            SecretValue = CalculateSecretValue(ingredientId);
            OscillationCount = AssignOscillationPattern(SecretValue);

            SetupTiming(speedBonus);
        }

        /// <summary>
        /// Calculate secret value based on vowel count in ingredient ID.
        /// Returns 0.0-1.0.
        /// </summary>
        private static float CalculateSecretValue(string ingredientId)
        {
            const string vowels = "aeiouAEIOU";
            int totalChars = 0;
            int vowelCount = 0;

            foreach (char c in ingredientId)
            {
                if (char.IsLetter(c))
                {
                    totalChars++;
                    if (vowels.IndexOf(c) >= 0)
                        vowelCount++;
                }
            }

            if (totalChars == 0) return 0.5f;

            float vowelRatio = (float)vowelCount / totalChars;
            return Math.Clamp((vowelRatio - 0.2f) * 2.0f, 0f, 1f);
        }

        /// <summary>
        /// Assign oscillation count: 25% get 1, 40% get 2, 35% get 3.
        /// </summary>
        private static int AssignOscillationPattern(float secretValue)
        {
            if (secretValue < 0.25f) return 1;
            if (secretValue < 0.65f) return 2;
            return 3;
        }

        private void SetupTiming(float speedBonus)
        {
            float[] baseDurations;
            float[] basePeaks;

            switch (IngredientType)
            {
                case "stable":
                    baseDurations = StableDurations;
                    basePeaks = Array.Empty<float>();
                    break;
                case "volatile":
                    baseDurations = VolatileDurations;
                    basePeaks = VolatileFalsePeaks;
                    break;
                case "legendary":
                    baseDurations = LegendaryDurations;
                    basePeaks = LegendaryFalsePeaks;
                    break;
                default: // moderate
                    baseDurations = ModerateDurations;
                    basePeaks = ModerateFalsePeaks;
                    break;
            }

            // Apply speed bonus: duration * (1.0 + bonus)
            float multiplier = 1.0f + speedBonus;
            _stageDurations = new float[baseDurations.Length];
            for (int i = 0; i < baseDurations.Length; i++)
                _stageDurations[i] = baseDurations[i] * multiplier;

            _falsePeaks = (float[])basePeaks.Clone();
            _currentStageDuration = _stageDurations[0];
        }

        /// <summary>Update reaction progress. Call every frame.</summary>
        public void Update(float deltaTime)
        {
            if (LockedQuality.HasValue) return;

            Progress += deltaTime / _currentStageDuration;

            if (Progress >= 1.0f)
            {
                Progress = 0f;
                Stage++;

                if (Stage <= 5)
                {
                    _currentStageDuration = _stageDurations[Stage - 1];
                }
                else
                {
                    // Explosion: stayed too long in stage 5
                    Stage = 6;
                    LockedQuality = 0f;
                }
            }

            UpdateVisuals();
        }

        private void UpdateVisuals()
        {
            switch (Stage)
            {
                case 1: // Initiation
                    Size = 0.2f + Progress * 0.2f;
                    Glow = 0.3f + Progress * 0.2f;
                    break;
                case 2: // Building with false peaks
                    Size = 0.4f + Progress * 0.3f;
                    float baseGlow = 0.5f + Progress * 0.3f;
                    foreach (float peakPos in _falsePeaks)
                    {
                        if (Math.Abs(Progress - peakPos) < 0.05f)
                        {
                            baseGlow += 0.2f;
                            Size += 0.1f;
                        }
                    }
                    Glow = Math.Min(1.0f, baseGlow);
                    break;
                case 3: // SWEET SPOT
                    Size = 0.7f + Progress * 0.1f;
                    Glow = 0.9f;
                    ColorShift = 1.0f;
                    break;
                case 4: // Degrading
                    Size = 0.8f + (float)(_rng.NextDouble() * 0.2 - 0.1);
                    Glow = 0.7f - Progress * 0.2f;
                    ColorShift = 0.7f - Progress * 0.3f;
                    break;
                case 5: // Critical
                    Size = 0.9f + Progress * 0.2f;
                    Glow = 0.4f - Progress * 0.3f;
                    ColorShift = 0f;
                    break;
            }
        }

        /// <summary>
        /// Get quality contribution if chained now.
        /// Oscillation system: sin waves with increasing amplitude per cycle.
        /// Max value appears on LAST oscillation peak.
        /// </summary>
        public float GetQuality()
        {
            if (Stage >= 6) return 0f;

            // Normalized progress through entire reaction (0.0 to 1.0)
            float totalProgress = (Stage - 1 + Progress) / 5.0f;

            // Oscillation cycle calculation
            float cycleProgress = totalProgress * OscillationCount;
            int currentCycle = (int)cycleProgress;
            float cycleFraction = cycleProgress - currentCycle;

            // Sine wave: 0 at 0, peak at 0.5, 0 at 1.0
            float cycleValue = (float)Math.Sin(cycleFraction * Math.PI);

            // Amplitude increases with each cycle (last peak is highest)
            float amplitude;
            if (OscillationCount == 1)
            {
                amplitude = 1.0f;
            }
            else
            {
                int cycleIndex = Math.Min(currentCycle, OscillationCount - 1);
                amplitude = 0.6f + (0.4f * cycleIndex / (OscillationCount - 1));
            }

            // Scale to dynamic max quality
            float finalPeakProgress = (OscillationCount - 0.5f) / OscillationCount;
            float baseFraction = 0.15f + (totalProgress / finalPeakProgress) * 0.30f;
            baseFraction = Math.Min(0.45f, baseFraction);
            float oscillationFraction = cycleValue * amplitude * 0.55f;
            float qualityFraction = baseFraction + oscillationFraction;

            float finalQuality = qualityFraction * MaxQuality;
            return Math.Clamp(finalQuality, 0f, MaxQuality);
        }

        /// <summary>Chain this reaction: lock quality, return locked value.</summary>
        public float Chain()
        {
            LockedQuality = GetQuality();
            return LockedQuality.Value;
        }
    }

    // =========================================================================
    // Alchemy Minigame
    // =========================================================================

    /// <summary>
    /// Alchemy crafting minigame. Extends BaseCraftingMinigame.
    /// Reaction chain management with oscillating quality system.
    /// </summary>
    public class AlchemyMinigame : BaseCraftingMinigame
    {
        // =====================================================================
        // State
        // =====================================================================

        private int _currentIngredientIndex;
        private AlchemyReaction _currentReaction;
        private List<AlchemyReaction> _lockedReactions = new();
        private float _totalProgress;
        private int _explosions;

        // Difficulty params
        private string[] _ingredientTypes;
        private float[] _ingredientMaxQualities;
        private float _speedBonus;

        // =====================================================================
        // Properties
        // =====================================================================

        public int CurrentIngredientIndex => _currentIngredientIndex;
        public AlchemyReaction CurrentReaction => _currentReaction;
        public IReadOnlyList<AlchemyReaction> LockedReactions => _lockedReactions;
        public float TotalProgress => _totalProgress;
        public int Explosions => _explosions;
        public int TotalIngredients => _inputs.Count;

        // =====================================================================
        // Constructor
        // =====================================================================

        public AlchemyMinigame(
            List<RecipeInput> inputs,
            Dictionary<string, object> recipeMeta = null,
            float buffTimeBonus = 0f,
            float buffQualityBonus = 0f,
            int intStat = 0,
            int? seed = null)
            : base(inputs, recipeMeta, buffTimeBonus, buffQualityBonus, seed)
        {
            var p = DifficultyCalculator.GetAlchemyParams(
                inputs, GetStationTier(), intStat);

            _difficultyPoints = p.DifficultyPoints;
            _difficultyTier = p.DifficultyTier;
            _totalTime = p.TimeLimit;
            _timeRemaining = p.TimeLimit;

            // Speed bonus slows reaction progression (not time limit)
            _speedBonus = buffTimeBonus;

            AssignIngredientTypes(p);
            CalculateIngredientMaxQualities();
        }

        // =====================================================================
        // Setup
        // =====================================================================

        private void AssignIngredientTypes(AlchemyDifficultyParams p)
        {
            string[] baseTypes;
            switch (_difficultyTier)
            {
                case "common":    baseTypes = new[] { "stable", "stable", "moderate" }; break;
                case "uncommon":  baseTypes = new[] { "stable", "moderate", "moderate" }; break;
                case "rare":      baseTypes = new[] { "moderate", "moderate", "volatile" }; break;
                case "epic":      baseTypes = new[] { "moderate", "volatile", "volatile" }; break;
                default:          baseTypes = new[] { "volatile", "volatile", "legendary" }; break;
            }

            _ingredientTypes = new string[_inputs.Count];
            for (int i = 0; i < _inputs.Count; i++)
            {
                if (i < baseTypes.Length)
                {
                    _ingredientTypes[i] = baseTypes[i];
                }
                else
                {
                    if (p.Volatility > 0.7f) _ingredientTypes[i] = "legendary";
                    else if (p.Volatility > 0.4f) _ingredientTypes[i] = "volatile";
                    else if (p.Volatility > 0.2f) _ingredientTypes[i] = "moderate";
                    else _ingredientTypes[i] = "stable";
                }
            }
        }

        /// <summary>
        /// Calculate dynamic max quality for each ingredient based on vowel contribution.
        /// Total max across all ingredients = 1.0 (100%).
        /// </summary>
        private void CalculateIngredientMaxQualities()
        {
            const string vowels = "aeiouAEIOU";
            var vowelCounts = new int[_inputs.Count];
            int totalVowels = 0;

            for (int i = 0; i < _inputs.Count; i++)
            {
                string id = _inputs[i].EffectiveId;
                int vc = 0;
                foreach (char c in id)
                {
                    if (vowels.IndexOf(c) >= 0) vc++;
                }
                vowelCounts[i] = vc;
                totalVowels += vc;
            }

            _ingredientMaxQualities = new float[_inputs.Count];
            if (totalVowels == 0)
            {
                float equal = 1.0f / Math.Max(1, _inputs.Count);
                for (int i = 0; i < _inputs.Count; i++)
                    _ingredientMaxQualities[i] = equal;
            }
            else
            {
                for (int i = 0; i < _inputs.Count; i++)
                    _ingredientMaxQualities[i] = (float)vowelCounts[i] / totalVowels;
            }
        }

        // =====================================================================
        // BaseCraftingMinigame Implementation
        // =====================================================================

        protected override void InitializeMinigame()
        {
            _currentIngredientIndex = 0;
            _currentReaction = null;
            _lockedReactions = new List<AlchemyReaction>();
            _totalProgress = 0f;
            _explosions = 0;
            _timeRemaining = _totalTime;

            if (_inputs.Count > 0)
                StartNextIngredient();
        }

        protected override void UpdateMinigame(float deltaTime)
        {
            if (_currentReaction == null) return;

            _currentReaction.Update(deltaTime);

            // Check for explosion: stage 6 = add 10% progress and move on
            if (_currentReaction.Stage >= 6)
            {
                _explosions++;
                _totalProgress += 0.10f;
                _lockedReactions.Add(_currentReaction);

                _currentIngredientIndex++;
                if (_currentIngredientIndex < _inputs.Count)
                    StartNextIngredient();
                else
                    Stabilize();
            }
        }

        public override bool HandleInput(MinigameInput input)
        {
            if (!IsActive) return false;

            switch (input.Type)
            {
                case MinigameInputType.Click:
                    // Chain: lock current ingredient and start next
                    return ChainReaction();

                case MinigameInputType.Confirm:
                    // Stabilize: end brewing with current progress
                    Stabilize();
                    return true;

                default:
                    return false;
            }
        }

        protected override float CalculatePerformance()
        {
            // Performance = total progress (sum of locked qualities)
            // Already in 0-1 range
            return Math.Clamp(_totalProgress, 0f, 1f);
        }

        protected override CraftingReward CalculateRewardForDiscipline()
        {
            var perf = new AlchemyPerformance
            {
                ChainsCompleted = _lockedReactions.Count,
                TotalChains = _inputs.Count,
                AvgTimingScore = _totalProgress * 100f,
                Explosions = _explosions,
                Attempt = _attempt
            };

            return RewardCalculator.CalculateAlchemyRewards(_difficultyPoints, perf);
        }

        protected override Dictionary<string, object> GetDisciplineState()
        {
            var reactionStates = new List<Dictionary<string, object>>();
            foreach (var r in _lockedReactions)
            {
                reactionStates.Add(new Dictionary<string, object>
                {
                    ["ingredient_id"] = r.IngredientId,
                    ["stage"] = r.Stage,
                    ["locked"] = true,
                    ["quality"] = r.LockedQuality ?? 0f,
                    ["oscillation_count"] = r.OscillationCount,
                    ["max_quality"] = r.MaxQuality
                });
            }

            Dictionary<string, object> currentState = null;
            if (_currentReaction != null)
            {
                currentState = new Dictionary<string, object>
                {
                    ["ingredient_id"] = _currentReaction.IngredientId,
                    ["stage"] = _currentReaction.Stage,
                    ["progress"] = _currentReaction.Progress,
                    ["locked"] = _currentReaction.LockedQuality.HasValue,
                    ["quality"] = _currentReaction.LockedQuality ?? _currentReaction.GetQuality(),
                    ["size"] = _currentReaction.Size,
                    ["glow"] = _currentReaction.Glow,
                    ["color_shift"] = _currentReaction.ColorShift,
                    ["oscillation_count"] = _currentReaction.OscillationCount,
                    ["max_quality"] = _currentReaction.MaxQuality,
                    ["secret_value"] = _currentReaction.SecretValue
                };
            }

            return new Dictionary<string, object>
            {
                ["current_ingredient_index"] = _currentIngredientIndex,
                ["total_ingredients"] = _inputs.Count,
                ["current_reaction"] = currentState,
                ["locked_reactions"] = reactionStates,
                ["total_progress"] = _totalProgress,
                ["explosions"] = _explosions
            };
        }

        protected override void OnTimeExpired()
        {
            // Time's up: stabilize with current progress (not instant fail)
            Stabilize();
        }

        // =====================================================================
        // Alchemy-Specific Methods
        // =====================================================================

        private void StartNextIngredient()
        {
            if (_currentIngredientIndex >= _inputs.Count) return;

            string ingredientId = _inputs[_currentIngredientIndex].EffectiveId;

            string ingType = _currentIngredientIndex < _ingredientTypes.Length
                ? _ingredientTypes[_currentIngredientIndex]
                : "moderate";

            float maxQuality = _currentIngredientIndex < _ingredientMaxQualities.Length
                ? _ingredientMaxQualities[_currentIngredientIndex]
                : 0.30f;

            _currentReaction = new AlchemyReaction(
                ingredientId, ingType, _speedBonus, maxQuality, _rng);
        }

        /// <summary>
        /// Chain current reaction: lock quality and start next ingredient.
        /// </summary>
        public bool ChainReaction()
        {
            if (!IsActive || _currentReaction == null) return false;

            float quality = _currentReaction.Chain();
            _lockedReactions.Add(_currentReaction);
            _totalProgress += quality;

            _currentIngredientIndex++;

            if (_currentIngredientIndex < _inputs.Count)
            {
                StartNextIngredient();
                return true;
            }
            else
            {
                Stabilize();
                return true;
            }
        }

        /// <summary>
        /// Stabilize: lock current reaction and complete brewing.
        /// </summary>
        public void Stabilize()
        {
            if (_currentReaction != null && !_currentReaction.LockedQuality.HasValue)
            {
                float quality = _currentReaction.Chain();
                _lockedReactions.Add(_currentReaction);
                _totalProgress += quality;
            }

            _currentReaction = null;
            Complete();
        }
    }
}
