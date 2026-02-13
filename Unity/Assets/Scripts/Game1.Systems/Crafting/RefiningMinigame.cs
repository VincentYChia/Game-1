// ============================================================================
// Game1.Systems.Crafting.RefiningMinigame
// Migrated from: Crafting-subdisciplines/refining.py (820 lines)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Refining minigame: Lockpicking-style cylinder alignment.
//
// Mechanics:
// - Multiple rotating cylinders (3-12 based on difficulty)
// - Each cylinder rotates at its own speed/direction
// - Player must click when cylinder angle is within timing window of target (0 deg)
// - All-or-nothing per cylinder: hit or miss
// - Allowed failures: 2 (easy) to 0 (hard)
// - Multi-speed: Rare+ enables varied rotation speeds
//
// Angular window is DECOUPLED from rotation speed:
// - base_window_degrees = timing_window * rotation_speed * 360
// - INT stat slows rotation without shrinking acceptance window
// - 25% larger effective range (window * 0.625) to fix sync issues
//
// Performance: success/fail binary (refining is all-or-nothing)
//

using System;
using System.Collections.Generic;

namespace Game1.Systems.Crafting
{
    /// <summary>
    /// State of a single rotating cylinder in the refining minigame.
    /// </summary>
    public class RefiningCylinder
    {
        public float Angle;           // Current angle (0-360)
        public float Speed;           // Rotation speed (degrees per second factor)
        public int Direction;          // 1 = clockwise, -1 = counter-clockwise
        public bool Aligned;           // Successfully aligned?
        public float TargetZone;       // Target angle (always 0 = top)
        public float? LastAttemptAngle; // Angle when player pressed button (for UI feedback)
    }

    /// <summary>
    /// Refining crafting minigame. Extends BaseCraftingMinigame.
    /// Lockpicking-style cylinder alignment timing game.
    /// </summary>
    public class RefiningMinigame : BaseCraftingMinigame
    {
        // =====================================================================
        // Difficulty Parameters
        // =====================================================================

        private int _cylinderCount;
        private float _timingWindow;
        private float _rotationSpeed;
        private int _allowedFailures;
        private bool _multiSpeed;
        private float _baseWindowDegrees;

        // =====================================================================
        // Game State
        // =====================================================================

        private List<RefiningCylinder> _cylinders = new();
        private int _currentCylinder;
        private List<int> _alignedCylinders = new();
        private int _failedAttempts;
        private float _feedbackTimer;

        // =====================================================================
        // Properties
        // =====================================================================

        public int CylinderCount => _cylinderCount;
        public int CurrentCylinder => _currentCylinder;
        public int AlignedCount => _alignedCylinders.Count;
        public int FailedAttempts => _failedAttempts;
        public int AllowedFailures => _allowedFailures;
        public float FeedbackTimer => _feedbackTimer;
        public IReadOnlyList<RefiningCylinder> Cylinders => _cylinders;
        public float BaseWindowDegrees => _baseWindowDegrees;

        // =====================================================================
        // Constructor
        // =====================================================================

        public RefiningMinigame(
            List<RecipeInput> inputs,
            Dictionary<string, object> recipeMeta = null,
            float buffTimeBonus = 0f,
            float buffQualityBonus = 0f,
            int intStat = 0,
            int? seed = null)
            : base(inputs, recipeMeta, buffTimeBonus, buffQualityBonus, seed)
        {
            var p = DifficultyCalculator.GetRefiningParams(
                inputs, GetStationTier(), intStat);

            _difficultyPoints = p.DifficultyPoints;
            _difficultyTier = p.DifficultyTier;

            _cylinderCount = p.CylinderCount;
            _timingWindow = p.TimingWindow;
            _rotationSpeed = p.RotationSpeed;
            _allowedFailures = p.AllowedFailures;
            _multiSpeed = p.MultiSpeed;
            _totalTime = p.TimeLimit;
            _timeRemaining = p.TimeLimit;

            // Fixed angular window (decoupled from rotation speed)
            _baseWindowDegrees = _timingWindow * _rotationSpeed * 360f;
        }

        // =====================================================================
        // BaseCraftingMinigame Implementation
        // =====================================================================

        protected override void InitializeMinigame()
        {
            _currentCylinder = 0;
            _alignedCylinders = new List<int>();
            _failedAttempts = 0;
            _feedbackTimer = 0f;
            _timeRemaining = _totalTime;

            // Initialize cylinders
            _cylinders = new List<RefiningCylinder>();
            for (int i = 0; i < _cylinderCount; i++)
            {
                float startAngle = (float)(_rng.NextDouble() * 360);

                // For multi-speed: vary rotation speeds
                float baseSpeed;
                if (_multiSpeed && i % 2 == 0)
                    baseSpeed = _rotationSpeed * 0.7f;
                else if (_multiSpeed && i % 3 == 0)
                    baseSpeed = _rotationSpeed * 1.3f;
                else
                    baseSpeed = _rotationSpeed;

                // Apply speed bonus (slows rotation)
                float speed = ApplySpeedBonus(baseSpeed);

                // Random direction
                int direction = _rng.Next(2) == 0 ? 1 : -1;

                _cylinders.Add(new RefiningCylinder
                {
                    Angle = startAngle,
                    Speed = speed,
                    Direction = direction,
                    Aligned = false,
                    TargetZone = 0f,
                    LastAttemptAngle = null
                });
            }
        }

        protected override void UpdateMinigame(float deltaTime)
        {
            // Update feedback timer
            if (_feedbackTimer > 0)
                _feedbackTimer -= deltaTime;

            // Rotate unaligned cylinders
            foreach (var cyl in _cylinders)
            {
                if (!cyl.Aligned)
                {
                    float degreesPerSecond = cyl.Speed * 360f;
                    cyl.Angle += cyl.Direction * degreesPerSecond * deltaTime;
                    cyl.Angle = ((cyl.Angle % 360f) + 360f) % 360f; // Wrap 0-360
                }
            }
        }

        public override bool HandleInput(MinigameInput input)
        {
            if (!IsActive) return false;

            if (input.Type == MinigameInputType.Click || input.Type == MinigameInputType.Confirm)
            {
                return HandleAlignment();
            }

            return false;
        }

        protected override float CalculatePerformance()
        {
            // Refining is binary: success or fail
            if (_alignedCylinders.Count >= _cylinderCount)
                return 1.0f;
            else
                return (float)_alignedCylinders.Count / Math.Max(1, _cylinderCount);
        }

        protected override CraftingReward CalculateRewardForDiscipline()
        {
            // Calculate total input quantity for rarity upgrade
            int totalInputQty = 0;
            foreach (var inp in _inputs)
                totalInputQty += inp.Quantity;

            bool success = _alignedCylinders.Count >= _cylinderCount;

            var perf = new RefiningPerformance
            {
                Success = success,
                InputQuantity = totalInputQty
            };

            return RewardCalculator.CalculateRefiningRewards(_difficultyPoints, perf);
        }

        protected override Dictionary<string, object> GetDisciplineState()
        {
            var cylinderStates = new List<Dictionary<string, object>>();
            foreach (var cyl in _cylinders)
            {
                cylinderStates.Add(new Dictionary<string, object>
                {
                    ["angle"] = cyl.Angle,
                    ["speed"] = cyl.Speed,
                    ["direction"] = cyl.Direction,
                    ["aligned"] = cyl.Aligned,
                    ["target_zone"] = cyl.TargetZone,
                    ["last_attempt_angle"] = (object)cyl.LastAttemptAngle
                });
            }

            return new Dictionary<string, object>
            {
                ["cylinders"] = cylinderStates,
                ["current_cylinder"] = _currentCylinder,
                ["aligned_count"] = _alignedCylinders.Count,
                ["total_cylinders"] = _cylinderCount,
                ["failed_attempts"] = _failedAttempts,
                ["allowed_failures"] = _allowedFailures,
                ["feedback_timer"] = _feedbackTimer,
                ["timing_window"] = _timingWindow,
                ["window_degrees"] = _baseWindowDegrees
            };
        }

        protected override void OnTimeExpired()
        {
            // Time's up = fail
            Fail();
        }

        // =====================================================================
        // Refining-Specific Methods
        // =====================================================================

        /// <summary>
        /// Handle alignment attempt (spacebar press).
        /// Uses fixed angular window with 25% larger effective range.
        /// </summary>
        public bool HandleAlignment()
        {
            if (!IsActive || _currentCylinder >= _cylinderCount)
                return false;

            var cylinder = _cylinders[_currentCylinder];

            float angle = cylinder.Angle;
            cylinder.LastAttemptAngle = angle;

            float target = cylinder.TargetZone;

            // Angular distance (accounting for wraparound)
            float distance = Math.Min(Math.Abs(angle - target), 360f - Math.Abs(angle - target));

            // Use fixed angular window with 25% larger effective range (0.5 * 1.25 = 0.625)
            float windowDegrees = _baseWindowDegrees;

            if (distance <= windowDegrees * 0.625f)
            {
                // SUCCESS
                cylinder.Aligned = true;
                _alignedCylinders.Add(_currentCylinder);
                _currentCylinder++;
                _feedbackTimer = 0.3f;

                if (_currentCylinder >= _cylinderCount)
                    Complete();

                return true;
            }
            else
            {
                // FAILURE
                _failedAttempts++;
                _feedbackTimer = 0.3f;

                if (_failedAttempts > _allowedFailures)
                    Fail();

                return false;
            }
        }
    }
}
