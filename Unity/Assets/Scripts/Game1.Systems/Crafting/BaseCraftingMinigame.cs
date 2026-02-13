// ============================================================================
// Game1.Systems.Crafting.BaseCraftingMinigame
// Migrated from: NEW (MACRO-8 architecture improvement from IMPROVEMENTS.md)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// This base class eliminates ~1,240 lines of duplication across the 5 crafting
// minigames by centralizing shared state, timing, buff logic, and the
// template-method Update pattern.
//

using System;
using System.Collections.Generic;

namespace Game1.Systems.Crafting
{
    // =========================================================================
    // Input Types
    // =========================================================================

    /// <summary>Types of minigame input actions.</summary>
    public enum MinigameInputType
    {
        Click,
        Release,
        Move,
        Rotate,
        Select,
        Confirm,
        Cancel
    }

    /// <summary>
    /// Generic input event for minigames.
    /// Interpreted differently by each discipline.
    /// </summary>
    public class MinigameInput
    {
        public MinigameInputType Type;
        public float Value;      // Optional numeric value (e.g., bet amount)
        public int Index;        // Optional index (e.g., row/col)
        public int Index2;       // Optional secondary index (e.g., column)
        public string StringValue; // Optional string data
    }

    /// <summary>
    /// Serializable minigame state snapshot for rendering/UI.
    /// Each discipline adds its own fields via dictionary.
    /// </summary>
    public class MinigameState
    {
        public bool Active;
        public bool IsComplete;
        public bool IsFailed;
        public float TimeRemaining;
        public float TotalTime;
        public float PerformanceScore;
        public string QualityTier;
        public int Attempt;
        public float DifficultyPoints;
        public string DifficultyTier;
        public Dictionary<string, object> DisciplineState;

        public MinigameState()
        {
            DisciplineState = new Dictionary<string, object>();
        }
    }

    // =========================================================================
    // Base Class
    // =========================================================================

    /// <summary>
    /// Abstract base class for all 5 crafting minigames (MACRO-8 improvement).
    ///
    /// Provides:
    /// - Shared state management (time, performance, attempts, buffs)
    /// - Difficulty point calculation via DifficultyCalculator
    /// - Template-method Update pattern (time tick + discipline-specific logic)
    /// - Buff application (time bonus slows mechanics, quality bonus boosts score)
    /// - Reward calculation delegation
    ///
    /// Subclasses implement:
    /// - InitializeMinigame(): Set up discipline-specific state
    /// - UpdateMinigame(deltaTime): Per-frame logic
    /// - HandleInput(input): Process player input
    /// - CalculatePerformance(): Compute 0-1 performance score
    /// - CalculateRewardForDiscipline(): Produce CraftingReward
    /// - GetDisciplineState(): Return discipline-specific state dict
    /// </summary>
    public abstract class BaseCraftingMinigame
    {
        // =====================================================================
        // Shared State
        // =====================================================================

        /// <summary>The recipe being crafted.</summary>
        protected List<RecipeInput> _inputs;

        /// <summary>Recipe metadata (stationType, stationTier, recipeId, etc.).</summary>
        protected Dictionary<string, object> _recipeMeta;

        /// <summary>Remaining time in seconds.</summary>
        protected float _timeRemaining;

        /// <summary>Total time limit for the minigame.</summary>
        protected float _totalTime;

        /// <summary>Whether the minigame has completed successfully.</summary>
        protected bool _isComplete;

        /// <summary>Whether the minigame has failed.</summary>
        protected bool _isFailed;

        /// <summary>Performance score from 0.0 (worst) to 1.0 (perfect).</summary>
        protected float _performanceScore;

        /// <summary>Current attempt number (1 = first try).</summary>
        protected int _attempt = 1;

        /// <summary>Buff: time/speed bonus (0.0-1.0+). Slows mechanics, does NOT add time.</summary>
        protected float _buffTimeBonus;

        /// <summary>Buff: quality bonus (0.0-1.0+). Added to final performance.</summary>
        protected float _buffQualityBonus;

        /// <summary>Thread-safe random number generator.</summary>
        protected Random _rng;

        /// <summary>Calculated difficulty points from material inputs.</summary>
        protected float _difficultyPoints;

        /// <summary>Normalized difficulty (0-1).</summary>
        protected float _normalizedDifficulty;

        /// <summary>Difficulty tier name (common/uncommon/rare/epic/legendary).</summary>
        protected string _difficultyTier;

        // =====================================================================
        // Properties
        // =====================================================================

        /// <summary>Whether the minigame completed successfully.</summary>
        public bool IsComplete => _isComplete;

        /// <summary>Whether the minigame has failed.</summary>
        public bool IsFailed => _isFailed;

        /// <summary>Whether the minigame is still active (not complete and not failed).</summary>
        public bool IsActive => !_isComplete && !_isFailed;

        /// <summary>Remaining time in seconds.</summary>
        public float TimeRemaining => _timeRemaining;

        /// <summary>Total time limit.</summary>
        public float TotalTime => _totalTime;

        /// <summary>Current performance score (0-1).</summary>
        public float PerformanceScore => _performanceScore;

        /// <summary>Quality tier based on current performance.</summary>
        public string QualityTier => RewardCalculator.GetQualityTier(_performanceScore);

        /// <summary>Current attempt number.</summary>
        public int Attempt => _attempt;

        /// <summary>Difficulty points of the recipe.</summary>
        public float DifficultyPoints => _difficultyPoints;

        /// <summary>Difficulty tier name.</summary>
        public string DifficultyTier => _difficultyTier;

        // =====================================================================
        // Constructor
        // =====================================================================

        /// <summary>
        /// Initialize a crafting minigame with recipe inputs and optional buffs.
        /// </summary>
        /// <param name="inputs">Recipe material inputs.</param>
        /// <param name="recipeMeta">
        /// Recipe metadata dictionary. Expected keys:
        /// "stationType" (string), "stationTier" (int), "recipeId" (string).
        /// </param>
        /// <param name="buffTimeBonus">Speed/time buff (0.0-1.0+). Slows mechanics.</param>
        /// <param name="buffQualityBonus">Quality buff (0.0-1.0+). Boosts final score.</param>
        /// <param name="seed">Optional RNG seed for deterministic testing.</param>
        protected BaseCraftingMinigame(
            List<RecipeInput> inputs,
            Dictionary<string, object> recipeMeta = null,
            float buffTimeBonus = 0f,
            float buffQualityBonus = 0f,
            int? seed = null)
        {
            _inputs = inputs ?? new List<RecipeInput>();
            _recipeMeta = recipeMeta ?? new Dictionary<string, object>();
            _buffTimeBonus = buffTimeBonus;
            _buffQualityBonus = buffQualityBonus;
            _rng = seed.HasValue ? new Random(seed.Value) : new Random();

            // Calculate base difficulty
            _difficultyPoints = DifficultyCalculator.CalculateMaterialPoints(_inputs);
            _normalizedDifficulty = DifficultyCalculator.CalculateNormalizedDifficulty(_difficultyPoints);
            _difficultyTier = DifficultyCalculator.GetDifficultyTier(_difficultyPoints);
        }

        // =====================================================================
        // Template Method: Update
        // =====================================================================

        /// <summary>
        /// Main update loop. Called every frame with delta time in seconds.
        /// Handles time tracking, then delegates to discipline-specific UpdateMinigame.
        /// </summary>
        /// <param name="deltaTime">Time elapsed since last frame, in seconds.</param>
        public void Update(float deltaTime)
        {
            if (_isComplete || _isFailed) return;

            _timeRemaining -= deltaTime;
            if (_timeRemaining <= 0f)
            {
                _timeRemaining = 0f;
                OnTimeExpired();
                return;
            }

            UpdateMinigame(deltaTime);
        }

        // =====================================================================
        // Abstract Methods (subclass must implement)
        // =====================================================================

        /// <summary>
        /// Initialize discipline-specific minigame state.
        /// Called when Start() is invoked.
        /// </summary>
        protected abstract void InitializeMinigame();

        /// <summary>
        /// Per-frame update logic for the specific discipline.
        /// Called by Update() after time tracking.
        /// </summary>
        /// <param name="deltaTime">Time elapsed since last frame, in seconds.</param>
        protected abstract void UpdateMinigame(float deltaTime);

        /// <summary>
        /// Handle player input for the specific discipline.
        /// </summary>
        /// <param name="input">Input event to process.</param>
        /// <returns>True if the input was consumed/handled.</returns>
        public abstract bool HandleInput(MinigameInput input);

        /// <summary>
        /// Calculate the final performance score (0.0 to 1.0) based on
        /// discipline-specific metrics. Called by GetReward().
        /// </summary>
        /// <returns>Performance score from 0.0 (worst) to 1.0 (perfect).</returns>
        protected abstract float CalculatePerformance();

        /// <summary>
        /// Produce a CraftingReward using the discipline-specific reward method
        /// from RewardCalculator.
        /// </summary>
        /// <returns>Crafting reward result.</returns>
        protected abstract CraftingReward CalculateRewardForDiscipline();

        /// <summary>
        /// Get discipline-specific state for rendering/UI.
        /// </summary>
        /// <returns>Dictionary of state key-value pairs.</returns>
        protected abstract Dictionary<string, object> GetDisciplineState();

        // =====================================================================
        // Virtual Methods (overridable)
        // =====================================================================

        /// <summary>
        /// Called when time expires. Default behavior: mark as failed.
        /// Override for disciplines where timeout has different behavior
        /// (e.g., alchemy auto-stabilizes).
        /// </summary>
        protected virtual void OnTimeExpired()
        {
            _isFailed = true;
        }

        // =====================================================================
        // Public Methods
        // =====================================================================

        /// <summary>
        /// Start the minigame. Resets state and calls InitializeMinigame().
        /// </summary>
        public void Start()
        {
            _isComplete = false;
            _isFailed = false;
            _performanceScore = 0f;
            InitializeMinigame();
        }

        /// <summary>
        /// Set the attempt number (for first-try bonus tracking).
        /// </summary>
        public void SetAttempt(int attempt)
        {
            _attempt = Math.Max(1, attempt);
        }

        /// <summary>
        /// Calculate final performance and produce a CraftingReward.
        /// Applies buff quality bonus to performance before reward calculation.
        /// </summary>
        public CraftingReward GetReward()
        {
            _performanceScore = CalculatePerformance();

            // Apply buff quality bonus
            _performanceScore = Math.Min(1.0f, _performanceScore + _buffQualityBonus);

            return CalculateRewardForDiscipline();
        }

        /// <summary>
        /// Get the full minigame state snapshot for rendering/UI.
        /// Combines base state with discipline-specific state.
        /// </summary>
        public MinigameState GetState()
        {
            return new MinigameState
            {
                Active = IsActive,
                IsComplete = _isComplete,
                IsFailed = _isFailed,
                TimeRemaining = _timeRemaining,
                TotalTime = _totalTime,
                PerformanceScore = _performanceScore,
                QualityTier = QualityTier,
                Attempt = _attempt,
                DifficultyPoints = _difficultyPoints,
                DifficultyTier = _difficultyTier,
                DisciplineState = GetDisciplineState()
            };
        }

        // =====================================================================
        // Utility Methods (for subclasses)
        // =====================================================================

        /// <summary>
        /// Mark the minigame as successfully completed.
        /// </summary>
        protected void Complete()
        {
            _isComplete = true;
        }

        /// <summary>
        /// Mark the minigame as failed with an optional reason.
        /// </summary>
        protected void Fail()
        {
            _isFailed = true;
        }

        /// <summary>
        /// Get a recipe metadata value, with a default fallback.
        /// </summary>
        protected T GetMeta<T>(string key, T defaultValue = default)
        {
            if (_recipeMeta != null && _recipeMeta.TryGetValue(key, out var val) && val is T typed)
                return typed;
            return defaultValue;
        }

        /// <summary>
        /// Get the station tier from recipe metadata (defaults to 1).
        /// </summary>
        protected int GetStationTier()
        {
            return GetMeta("stationTier", 1);
        }

        /// <summary>
        /// Apply speed bonus to a rate value (slows it down).
        /// Formula: effectiveRate = baseRate / (1.0 + speedBonus)
        /// </summary>
        protected float ApplySpeedBonus(float baseRate)
        {
            return baseRate / (1.0f + _buffTimeBonus);
        }

        /// <summary>
        /// Apply speed bonus to a duration value (extends it).
        /// Formula: effectiveDuration = baseDuration * (1.0 + speedBonus)
        /// </summary>
        protected float ApplySpeedBonusToDuration(float baseDuration)
        {
            return baseDuration * (1.0f + _buffTimeBonus);
        }
    }
}
