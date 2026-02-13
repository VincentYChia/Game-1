// ============================================================================
// Game1.Systems.Crafting.SmithingMinigame
// Migrated from: Crafting-subdisciplines/smithing.py (749 lines)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Smithing minigame: Temperature management + hammer timing.
// Two phases: HEATING (fan to maintain temperature) + HAMMERING (click at right time).
//
// Temperature system:
// - currentTemp decays per tick at TEMP_DECAY rate
// - Fan (spacebar) adds TEMP_FAN_INCREMENT
// - Ideal range centered around 70 degrees
// - Exponential falloff outside ideal: mult = e^(-0.0433 * deviation^2)
//
// Hammer system:
// - Oscillating bar (position 0 to HAMMER_BAR_WIDTH at hammerSpeed per frame)
// - BINNED scoring: 100/90/80/70/60/50/30/0 based on distance from center
// - Final score = hammerTimingScore * temperatureMultiplier
//
// Performance: avgHammerScore * tempBonus(1.2 if ideal) / 120, clamp 0-1
//

using System;
using System.Collections.Generic;

namespace Game1.Systems.Crafting
{
    /// <summary>
    /// Smithing crafting minigame. Extends BaseCraftingMinigame.
    /// </summary>
    public class SmithingMinigame : BaseCraftingMinigame
    {
        // =====================================================================
        // Constants
        // =====================================================================

        /// <summary>Width of the hammer oscillation bar in logical pixels.</summary>
        public const float HammerBarWidth = 400f;

        /// <summary>Temperature decay constant: k = ln(2)/16 for 0.5 multiplier at 4 degrees off.</summary>
        private const float TempDecayK = 0.0433f;

        /// <summary>Minimum temperature multiplier (prevents complete zeroing).</summary>
        private const float MinTempMultiplier = 0.1f;

        /// <summary>Temperature decay interval in seconds (every 100ms).</summary>
        private const float TempDecayInterval = 0.1f;

        // =====================================================================
        // Difficulty Parameters
        // =====================================================================

        private float _tempIdealMin;
        private float _tempIdealMax;
        private float _tempDecayRate;
        private float _tempFanIncrement;
        private float _hammerSpeed;
        private int _requiredHits;
        private float _targetWidth;
        private float _perfectWidth;

        // =====================================================================
        // Game State
        // =====================================================================

        private float _temperature = 50f;
        private int _hammerHits;
        private float _hammerPosition;
        private int _hammerDirection = 1;
        private List<int> _hammerScores = new();
        private float _tempDecayAccumulator;

        // Strike feedback (for UI)
        private int? _lastStrikeScore;
        private bool _lastStrikeTempOk = true;
        private float _lastStrikeTempMult = 1.0f;
        private int _lastStrikeHammerScore;

        // Detailed stats tracking
        private int _perfectStrikes;
        private int _excellentStrikes;
        private int _goodStrikes;
        private int _fairStrikes;
        private int _poorStrikes;
        private int _missStrikes;
        private List<float> _tempReadings = new();
        private List<int> _hammerTimingScores = new();
        private List<float> _tempMultipliers = new();
        private float _timeInIdealTemp;

        // =====================================================================
        // Properties
        // =====================================================================

        public float Temperature => _temperature;
        public int HammerHits => _hammerHits;
        public int RequiredHits => _requiredHits;
        public float HammerPosition => _hammerPosition;
        public float TempIdealMin => _tempIdealMin;
        public float TempIdealMax => _tempIdealMax;
        public IReadOnlyList<int> HammerScores => _hammerScores;
        public int? LastStrikeScore => _lastStrikeScore;
        public bool LastStrikeTempOk => _lastStrikeTempOk;
        public float LastStrikeTempMult => _lastStrikeTempMult;
        public int LastStrikeHammerScore => _lastStrikeHammerScore;

        // =====================================================================
        // Constructor
        // =====================================================================

        public SmithingMinigame(
            List<RecipeInput> inputs,
            Dictionary<string, object> recipeMeta = null,
            float buffTimeBonus = 0f,
            float buffQualityBonus = 0f,
            int intStat = 0,
            int? seed = null)
            : base(inputs, recipeMeta, buffTimeBonus, buffQualityBonus, seed)
        {
            // Get smithing difficulty parameters
            var p = DifficultyCalculator.GetSmithingParams(
                inputs, GetStationTier(), intStat);

            _difficultyPoints = p.DifficultyPoints;
            _difficultyTier = p.DifficultyTier;

            _tempIdealMin = p.TempIdealMin;
            _tempIdealMax = p.TempIdealMax;
            _tempDecayRate = p.TempDecayRate;
            _tempFanIncrement = p.TempFanIncrement;
            _hammerSpeed = p.HammerSpeed;
            _requiredHits = p.RequiredHits;
            _targetWidth = p.TargetWidth;
            _perfectWidth = p.PerfectWidth;
            _totalTime = p.TimeLimit;
            _timeRemaining = p.TimeLimit;
        }

        // =====================================================================
        // BaseCraftingMinigame Implementation
        // =====================================================================

        protected override void InitializeMinigame()
        {
            _temperature = 50f;
            _hammerHits = 0;
            _hammerPosition = 0f;
            _hammerDirection = 1;
            _hammerScores = new List<int>();
            _tempDecayAccumulator = 0f;
            _timeRemaining = _totalTime;

            _lastStrikeScore = null;
            _lastStrikeTempOk = true;
            _lastStrikeTempMult = 1.0f;
            _lastStrikeHammerScore = 0;

            _perfectStrikes = 0;
            _excellentStrikes = 0;
            _goodStrikes = 0;
            _fairStrikes = 0;
            _poorStrikes = 0;
            _missStrikes = 0;
            _tempReadings = new List<float>();
            _hammerTimingScores = new List<int>();
            _tempMultipliers = new List<float>();
            _timeInIdealTemp = 0f;
        }

        protected override void UpdateMinigame(float deltaTime)
        {
            // Track time in ideal temperature range
            if (_temperature >= _tempIdealMin && _temperature <= _tempIdealMax)
                _timeInIdealTemp += deltaTime;

            // Temperature decay per 100ms tick
            _tempDecayAccumulator += deltaTime;
            while (_tempDecayAccumulator >= TempDecayInterval)
            {
                _tempDecayAccumulator -= TempDecayInterval;

                // Apply speed bonus from skill buffs (slows decay)
                float effectiveDecay = ApplySpeedBonus(_tempDecayRate);
                _temperature = Math.Max(0f, _temperature - effectiveDecay);
            }

            // Hammer movement - speed scales with difficulty
            if (_hammerHits < _requiredHits)
            {
                _hammerPosition += _hammerDirection * _hammerSpeed;
                if (_hammerPosition <= 0f || _hammerPosition >= HammerBarWidth)
                {
                    _hammerDirection *= -1;
                    _hammerPosition = Math.Clamp(_hammerPosition, 0f, HammerBarWidth);
                }
            }
        }

        public override bool HandleInput(MinigameInput input)
        {
            if (!IsActive) return false;

            switch (input.Type)
            {
                case MinigameInputType.Confirm:
                    // Spacebar: Fan flames
                    HandleFan();
                    return true;

                case MinigameInputType.Click:
                    // Mouse click: Hammer strike
                    HandleHammer();
                    return true;

                default:
                    return false;
            }
        }

        protected override float CalculatePerformance()
        {
            if (_hammerScores.Count == 0) return 0f;

            float avgScore = 0f;
            foreach (var s in _hammerScores) avgScore += s;
            avgScore /= _hammerScores.Count;

            bool inIdeal = _temperature >= _tempIdealMin && _temperature <= _tempIdealMax;
            float tempBonus = inIdeal ? 1.2f : 1.0f;

            // Max possible: 100 * 1.2 = 120
            return Math.Min(1.0f, (avgScore * tempBonus) / 120f);
        }

        protected override CraftingReward CalculateRewardForDiscipline()
        {
            float avgScore = 0f;
            if (_hammerScores.Count > 0)
            {
                foreach (var s in _hammerScores) avgScore += s;
                avgScore /= _hammerScores.Count;
            }

            bool inIdeal = _temperature >= _tempIdealMin && _temperature <= _tempIdealMax;

            var perf = new SmithingPerformance
            {
                AvgHammerScore = avgScore,
                TempInIdeal = inIdeal,
                Attempt = _attempt
            };

            return RewardCalculator.CalculateSmithingRewards(_difficultyPoints, perf);
        }

        protected override Dictionary<string, object> GetDisciplineState()
        {
            return new Dictionary<string, object>
            {
                ["temperature"] = _temperature,
                ["hammer_hits"] = _hammerHits,
                ["required_hits"] = _requiredHits,
                ["hammer_position"] = _hammerPosition,
                ["hammer_bar_width"] = HammerBarWidth,
                ["target_width"] = _targetWidth,
                ["perfect_width"] = _perfectWidth,
                ["temp_ideal_min"] = _tempIdealMin,
                ["temp_ideal_max"] = _tempIdealMax,
                ["last_strike_score"] = _lastStrikeScore,
                ["last_strike_temp_ok"] = _lastStrikeTempOk,
                ["last_strike_temp_mult"] = _lastStrikeTempMult,
                ["last_strike_hammer_score"] = _lastStrikeHammerScore,
                ["hammer_scores"] = new List<int>(_hammerScores)
            };
        }

        // =====================================================================
        // Smithing-Specific Methods
        // =====================================================================

        /// <summary>Handle fan action (spacebar) -- increases temperature.</summary>
        public void HandleFan()
        {
            if (IsActive)
                _temperature = Math.Min(100f, _temperature + _tempFanIncrement);
        }

        /// <summary>
        /// Handle hammer strike with binned timing score and exponential temperature multiplier.
        /// </summary>
        public void HandleHammer()
        {
            if (!IsActive || _hammerHits >= _requiredHits) return;

            float center = HammerBarWidth / 2f;
            float distance = Math.Abs(_hammerPosition - center);

            // Calculate raw hammer timing score (0-100 binned)
            int hammerTimingScore = CalculateHammerTimingScore(distance);

            // Calculate temperature multiplier (exponential, max 1.0, 0.5 at 4 degrees off)
            float tempMult = CalculateTempMultiplier();

            // Final score = timing * temp multiplier
            int finalScore = (int)Math.Round(hammerTimingScore * tempMult);

            bool tempInIdeal = _temperature >= _tempIdealMin && _temperature <= _tempIdealMax;

            // Store detailed stats
            _tempReadings.Add(_temperature);
            _hammerTimingScores.Add(hammerTimingScore);
            _tempMultipliers.Add(tempMult);

            // Categorize the strike
            if (finalScore >= 100) _perfectStrikes++;
            else if (finalScore >= 90) _excellentStrikes++;
            else if (finalScore >= 70) _goodStrikes++;
            else if (finalScore >= 50) _fairStrikes++;
            else if (finalScore >= 30) _poorStrikes++;
            else _missStrikes++;

            _hammerScores.Add(finalScore);
            _hammerHits++;

            // Store strike result for UI feedback
            _lastStrikeScore = finalScore;
            _lastStrikeTempOk = tempInIdeal;
            _lastStrikeTempMult = tempMult;
            _lastStrikeHammerScore = hammerTimingScore;

            if (_hammerHits >= _requiredHits)
                Complete();
        }

        /// <summary>
        /// Calculate hammer timing score using binned system.
        ///
        /// Pattern: 0-30-50-60-70-80-90-100-90-80-70-60-50-30-0
        /// Zone widths: w = half_width / 9.0
        /// - Center (0.3w): 100 points
        /// - 1w: 90 points
        /// - 2w: 80 points
        /// - 3w: 70 points
        /// - 4w: 60 points
        /// - 6w (2w zone): 50 points
        /// - 9w (3w zone): 30 points
        /// - Beyond: 0 points
        /// </summary>
        private int CalculateHammerTimingScore(float distanceFromCenter)
        {
            float halfWidth = HammerBarWidth / 2f;
            float w = halfWidth / 9.0f;

            float perfectThreshold = w * 0.3f;
            float zone90 = w * 1.0f;
            float zone80 = w * 2.0f;
            float zone70 = w * 3.0f;
            float zone60 = w * 4.0f;
            float zone50 = w * 6.0f;
            float zone30 = w * 9.0f;

            if (distanceFromCenter <= perfectThreshold) return 100;
            if (distanceFromCenter <= zone90) return 90;
            if (distanceFromCenter <= zone80) return 80;
            if (distanceFromCenter <= zone70) return 70;
            if (distanceFromCenter <= zone60) return 60;
            if (distanceFromCenter <= zone50) return 50;
            if (distanceFromCenter <= zone30) return 30;
            return 0;
        }

        /// <summary>
        /// Calculate temperature multiplier using exponential falloff.
        /// - In ideal range: 1.0
        /// - At 4 degrees off: 0.5
        /// - Formula: mult = e^(-0.0433 * deviation^2)
        /// - Minimum: 0.1
        /// </summary>
        private float CalculateTempMultiplier()
        {
            if (_temperature >= _tempIdealMin && _temperature <= _tempIdealMax)
                return 1.0f;

            float deviation;
            if (_temperature < _tempIdealMin)
                deviation = _tempIdealMin - _temperature;
            else
                deviation = _temperature - _tempIdealMax;

            float tempMult = (float)Math.Exp(-TempDecayK * deviation * deviation);
            return Math.Max(MinTempMultiplier, Math.Min(1.0f, tempMult));
        }

        /// <summary>
        /// Get detailed stats for analytics/backwards compatibility.
        /// </summary>
        public Dictionary<string, object> GetDetailedStats()
        {
            return new Dictionary<string, object>
            {
                ["perfect_strikes"] = _perfectStrikes,
                ["excellent_strikes"] = _excellentStrikes,
                ["good_strikes"] = _goodStrikes,
                ["fair_strikes"] = _fairStrikes,
                ["poor_strikes"] = _poorStrikes,
                ["miss_strikes"] = _missStrikes,
                ["time_in_ideal_temp"] = _timeInIdealTemp,
                ["temp_readings"] = new List<float>(_tempReadings),
                ["hammer_timing_scores"] = new List<int>(_hammerTimingScores),
                ["temp_multipliers"] = new List<float>(_tempMultipliers)
            };
        }
    }
}
