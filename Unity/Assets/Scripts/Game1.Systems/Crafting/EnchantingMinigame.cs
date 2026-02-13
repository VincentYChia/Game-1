// ============================================================================
// Game1.Systems.Crafting.EnchantingMinigame
// Migrated from: Crafting-subdisciplines/enchanting.py (1410 lines)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Enchanting minigame: Spinning wheel gambling.
//
// Mechanics:
// - 20-slice wheel with green, red, grey colors
// - 3 spins total per minigame
// - Start with 100 currency; place bet, spin, win/lose based on color
// - Each spin has different multipliers:
//     Spin 1: green=1.2, grey=1.0, red=0.66
//     Spin 2: green=1.5, grey=0.95, red=0.5
//     Spin 3: green=2.0, grey=0.8, red=0.0
// - Difficulty affects wheel distribution (more green at low diff, more red at high)
// - Each subsequent spin: -1 green, +1 red from base
// - Final currency difference / 100 * 50 = efficacy percent (capped +-50%)
// - Performance: finalCurrency / 200, clamp 0-1
//
// Enchanting is NOT affected by INT stat.
// Enchanting minigame is REQUIRED (cannot be skipped).
//

using System;
using System.Collections.Generic;

namespace Game1.Systems.Crafting
{
    /// <summary>Phases of the enchanting wheel minigame.</summary>
    public enum EnchantingPhase
    {
        Betting,
        ReadyToSpin,
        Spinning,
        SpinResult,
        Completed
    }

    /// <summary>
    /// Result of a single wheel spin.
    /// </summary>
    public class SpinResult
    {
        public int SpinNumber;      // 1-3
        public int Bet;
        public string Color;        // "green", "red", "grey"
        public float Multiplier;
        public int Winnings;
        public int Profit;
        public int CurrencyAfter;
    }

    /// <summary>
    /// Enchanting crafting minigame. Extends BaseCraftingMinigame.
    /// Spinning wheel gambling for enchantment efficacy.
    /// </summary>
    public class EnchantingMinigame : BaseCraftingMinigame
    {
        // =====================================================================
        // Constants
        // =====================================================================

        public const int TotalSlices = 20;
        public const int TotalSpins = 3;
        public const int StartingCurrency = 100;

        /// <summary>
        /// Multipliers for each spin: [green, grey, red].
        /// Spin 1: conservative (green=1.2, grey=1.0, red=0.66)
        /// Spin 2: moderate (green=1.5, grey=0.95, red=0.5)
        /// Spin 3: high-stakes (green=2.0, grey=0.8, red=0.0)
        /// </summary>
        public static readonly Dictionary<string, float>[] SpinMultipliers =
        {
            new() { ["green"] = 1.2f, ["grey"] = 1.0f, ["red"] = 0.66f },
            new() { ["green"] = 1.5f, ["grey"] = 0.95f, ["red"] = 0.5f },
            new() { ["green"] = 2.0f, ["grey"] = 0.8f, ["red"] = 0.0f }
        };

        // =====================================================================
        // Difficulty Parameters
        // =====================================================================

        private int _baseGreenSlices;
        private int _baseRedSlices;

        // =====================================================================
        // Game State
        // =====================================================================

        private int _currentCurrency;
        private int _currentBet;
        private int _currentSpinNumber;    // 0-2 for spins 1-3
        private EnchantingPhase _phase = EnchantingPhase.Betting;

        private List<string[]> _wheels = new();       // 3 wheels, each 20 colors
        private List<SpinResult> _spinResults = new();
        private int? _finalSliceIndex;

        // Wheel animation state (for UI; logic does not depend on it)
        private bool _wheelSpinning;
        private float _wheelRotation;
        private float _spinTimer;
        private const float SpinDuration = 2.0f;       // 2 seconds animation

        // =====================================================================
        // Properties
        // =====================================================================

        public int CurrentCurrency => _currentCurrency;
        public int CurrentBet => _currentBet;
        public int CurrentSpinNumber => _currentSpinNumber;
        public EnchantingPhase Phase => _phase;
        public IReadOnlyList<SpinResult> SpinResults => _spinResults;
        public float WheelRotation => _wheelRotation;
        public bool WheelSpinning => _wheelSpinning;

        /// <summary>Current wheel slice colors (20 entries).</summary>
        public string[] CurrentWheel =>
            _currentSpinNumber < _wheels.Count ? _wheels[_currentSpinNumber] : null;

        /// <summary>Current spin multipliers.</summary>
        public Dictionary<string, float> CurrentMultipliers =>
            _currentSpinNumber < SpinMultipliers.Length ? SpinMultipliers[_currentSpinNumber] : null;

        // =====================================================================
        // Constructor
        // =====================================================================

        public EnchantingMinigame(
            List<RecipeInput> inputs,
            Dictionary<string, object> recipeMeta = null,
            float buffTimeBonus = 0f,
            float buffQualityBonus = 0f,
            int? seed = null)
            : base(inputs, recipeMeta, buffTimeBonus, buffQualityBonus, seed)
        {
            // Enchanting is NOT affected by INT stat
            var p = DifficultyCalculator.GetEnchantingParams(
                inputs, GetStationTier());

            _difficultyPoints = p.DifficultyPoints;
            _difficultyTier = p.DifficultyTier;

            _baseGreenSlices = p.GreenSlices;
            _baseRedSlices = p.RedSlices;

            // Enchanting has no time limit (event-driven)
            _totalTime = float.MaxValue;
            _timeRemaining = float.MaxValue;
        }

        // =====================================================================
        // BaseCraftingMinigame Implementation
        // =====================================================================

        protected override void InitializeMinigame()
        {
            _currentCurrency = StartingCurrency;
            _currentBet = 0;
            _currentSpinNumber = 0;
            _phase = EnchantingPhase.Betting;
            _spinResults = new List<SpinResult>();
            _finalSliceIndex = null;
            _wheelSpinning = false;
            _wheelRotation = 0f;
            _spinTimer = 0f;

            // Generate all 3 wheels upfront
            _wheels = new List<string[]>();
            for (int i = 0; i < TotalSpins; i++)
                _wheels.Add(GenerateSingleWheel(i));
        }

        protected override void UpdateMinigame(float deltaTime)
        {
            // Handle wheel spinning animation
            if (_wheelSpinning)
            {
                _spinTimer += deltaTime;

                if (_spinTimer < SpinDuration)
                {
                    // Ease-out cubic deceleration
                    float progress = _spinTimer / SpinDuration;
                    float easeProgress = 1f - (float)Math.Pow(1f - progress, 3);

                    if (_finalSliceIndex.HasValue)
                    {
                        // Target angle: center of target slice
                        float sliceAngle = _finalSliceIndex.Value * 18f + 9f;
                        float totalRotation = 360f * 5f + sliceAngle; // 5 full rotations + final
                        _wheelRotation = easeProgress * totalRotation;
                    }
                }
                else
                {
                    // Animation complete
                    _wheelSpinning = false;
                    ProcessSpinResult();
                }
            }
        }

        public override bool HandleInput(MinigameInput input)
        {
            if (!IsActive) return false;

            switch (input.Type)
            {
                case MinigameInputType.Select:
                    // Place bet (Value = bet amount)
                    return PlaceBet((int)input.Value);

                case MinigameInputType.Click:
                case MinigameInputType.Confirm:
                    if (_phase == EnchantingPhase.ReadyToSpin)
                        return SpinWheel();
                    if (_phase == EnchantingPhase.SpinResult)
                        return AdvanceToNextSpin();
                    return false;

                default:
                    return false;
            }
        }

        protected override float CalculatePerformance()
        {
            // Performance: finalCurrency / 200, clamp 0-1
            float basePerformance = Math.Clamp(_currentCurrency / 200f, 0f, 1f);

            // First-try bonus
            if (_attempt == 1)
                basePerformance = Math.Min(1.0f, basePerformance + 0.10f);

            return basePerformance;
        }

        protected override CraftingReward CalculateRewardForDiscipline()
        {
            int greenHits = 0;
            int redHits = 0;
            foreach (var r in _spinResults)
            {
                if (r.Color == "green") greenHits++;
                if (r.Color == "red") redHits++;
            }

            var perf = new EnchantingPerformance
            {
                FinalCurrency = _currentCurrency,
                SpinsCompleted = _spinResults.Count,
                GreenHits = greenHits,
                RedHits = redHits
            };

            return RewardCalculator.CalculateEnchantingRewards(_difficultyPoints, perf);
        }

        protected override Dictionary<string, object> GetDisciplineState()
        {
            var spinResultDicts = new List<Dictionary<string, object>>();
            foreach (var sr in _spinResults)
            {
                spinResultDicts.Add(new Dictionary<string, object>
                {
                    ["spin_number"] = sr.SpinNumber,
                    ["bet"] = sr.Bet,
                    ["color"] = sr.Color,
                    ["multiplier"] = sr.Multiplier,
                    ["winnings"] = sr.Winnings,
                    ["profit"] = sr.Profit,
                    ["currency_after"] = sr.CurrencyAfter
                });
            }

            return new Dictionary<string, object>
            {
                ["phase"] = _phase.ToString(),
                ["current_spin_number"] = _currentSpinNumber,
                ["current_currency"] = _currentCurrency,
                ["current_bet"] = _currentBet,
                ["wheel_spinning"] = _wheelSpinning,
                ["wheel_rotation"] = _wheelRotation,
                ["final_slice_index"] = (object)_finalSliceIndex,
                ["spin_results"] = spinResultDicts,
                ["base_green_slices"] = _baseGreenSlices,
                ["base_red_slices"] = _baseRedSlices
            };
        }

        protected override void OnTimeExpired()
        {
            // Enchanting has no time limit, this should not be called
        }

        // =====================================================================
        // Enchanting-Specific Methods
        // =====================================================================

        /// <summary>
        /// Generate a single wheel with difficulty-based distribution.
        /// Each subsequent spin: -1 green, +1 red from base.
        /// </summary>
        private string[] GenerateSingleWheel(int spinNum)
        {
            // Base distribution modified per spin
            int green = Math.Max(3, _baseGreenSlices - spinNum);
            int red = Math.Min(12, _baseRedSlices + spinNum);

            // Ensure total doesn't exceed 20
            if (green + red > 17)
            {
                int overflow = (green + red) - 17;
                green = Math.Max(3, green - overflow);
            }

            int grey = TotalSlices - green - red;

            // Build wheel
            var wheel = new string[TotalSlices];
            int idx = 0;
            for (int i = 0; i < green; i++) wheel[idx++] = "green";
            for (int i = 0; i < red; i++) wheel[idx++] = "red";
            for (int i = 0; i < grey; i++) wheel[idx++] = "grey";

            // Fisher-Yates shuffle
            for (int i = wheel.Length - 1; i > 0; i--)
            {
                int j = _rng.Next(i + 1);
                (wheel[i], wheel[j]) = (wheel[j], wheel[i]);
            }

            return wheel;
        }

        /// <summary>Place a bet for the current spin.</summary>
        public bool PlaceBet(int amount)
        {
            if (_phase != EnchantingPhase.Betting) return false;
            if (amount <= 0 || amount > _currentCurrency) return false;

            _currentBet = amount;
            _phase = EnchantingPhase.ReadyToSpin;
            return true;
        }

        /// <summary>Start spinning the wheel.</summary>
        public bool SpinWheel()
        {
            if (_phase != EnchantingPhase.ReadyToSpin) return false;
            if (_currentBet <= 0) return false;

            _wheelSpinning = true;
            _wheelRotation = 0f;
            _spinTimer = 0f;

            // Randomly select result slice
            _finalSliceIndex = _rng.Next(TotalSlices);

            _phase = EnchantingPhase.Spinning;
            return true;
        }

        /// <summary>
        /// Instantly resolve a spin (skip animation). For testing / headless mode.
        /// </summary>
        public bool SpinInstant()
        {
            if (_phase != EnchantingPhase.ReadyToSpin) return false;
            if (_currentBet <= 0) return false;

            _finalSliceIndex = _rng.Next(TotalSlices);
            _phase = EnchantingPhase.Spinning;
            ProcessSpinResult();
            return true;
        }

        /// <summary>Process spin result after animation completes.</summary>
        private void ProcessSpinResult()
        {
            if (!_finalSliceIndex.HasValue || _currentSpinNumber >= _wheels.Count)
                return;

            string[] currentWheel = _wheels[_currentSpinNumber];
            string resultColor = currentWheel[_finalSliceIndex.Value];

            // Get multiplier
            float multiplier = SpinMultipliers[_currentSpinNumber][resultColor];

            // Calculate winnings
            int winnings = (int)(_currentBet * multiplier);
            int profit = winnings - _currentBet;

            // Update currency
            _currentCurrency = _currentCurrency - _currentBet + winnings;

            // Record result
            _spinResults.Add(new SpinResult
            {
                SpinNumber = _currentSpinNumber + 1,
                Bet = _currentBet,
                Color = resultColor,
                Multiplier = multiplier,
                Winnings = winnings,
                Profit = profit,
                CurrencyAfter = _currentCurrency
            });

            _phase = EnchantingPhase.SpinResult;
            _currentBet = 0;
        }

        /// <summary>Advance to next spin or complete the minigame.</summary>
        public bool AdvanceToNextSpin()
        {
            if (_phase != EnchantingPhase.SpinResult) return false;

            _currentSpinNumber++;

            if (_currentSpinNumber >= TotalSpins)
            {
                // All spins complete
                _phase = EnchantingPhase.Completed;
                Complete();
                return true;
            }
            else
            {
                _phase = EnchantingPhase.Betting;
                _finalSliceIndex = null;
                return true;
            }
        }

        /// <summary>
        /// Get the enchantment efficacy as a decimal (-0.5 to +0.5).
        /// Based on currency difference from starting.
        /// </summary>
        public float GetEfficacy()
        {
            int currencyDiff = _currentCurrency - StartingCurrency;
            float efficacyPercent = (currencyDiff / 100f) * 50f;
            efficacyPercent = Math.Clamp(efficacyPercent, -50f, 50f);
            return efficacyPercent / 100f;
        }

        /// <summary>
        /// Get the enchantment efficacy as a percentage (-50 to +50).
        /// </summary>
        public float GetEfficacyPercent()
        {
            int currencyDiff = _currentCurrency - StartingCurrency;
            float efficacyPercent = (currencyDiff / 100f) * 50f;
            return Math.Clamp(efficacyPercent, -50f, 50f);
        }
    }
}
