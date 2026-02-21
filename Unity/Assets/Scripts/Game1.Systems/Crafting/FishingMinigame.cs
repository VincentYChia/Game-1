// ============================================================================
// Game1.Systems.Crafting.FishingMinigame
// Migrated from: Crafting-subdisciplines/fishing.py (lines 142-687)
// Migration phase: 4
// Date: 2026-02-21
//
// Fishing minigame: Click expanding ripples at the right moment.
// DOES NOT use DifficultyCalculator/RewardCalculator — has own formulas.
//
// Key formulas preserved exactly from Python:
//   required_ripples = max(4, int(8 - luck * 0.1)) * (1 + (tier-1)*0.25)
//   hit_tolerance = min(30, 15 + STR * 0.5 + accuracy_bonus)
//   expand_speed = 80 * rod_speed * spot_speed * (1 - speed_bonus * 0.5)
//   XP = 100 * 4^(tier-1)
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Systems.Crafting
{
    /// <summary>
    /// Individual ripple expanding on the pond surface.
    /// Player must click when current_radius matches target_radius.
    /// </summary>
    public class Ripple
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float TargetRadius { get; set; }
        public float CurrentRadius { get; set; }
        public float MaxRadius { get; set; }
        public float ExpandSpeed { get; set; } = 60f;
        public bool Hit { get; set; }
        public int Score { get; set; }
        public bool Active { get; set; } = true;
        public float SpawnTime { get; set; }
    }

    /// <summary>
    /// Fishing minigame: Click expanding ripples to catch fish.
    /// Self-contained difficulty and reward system (not using base class calculators).
    /// Extends BaseCraftingMinigame for consistent lifecycle.
    /// </summary>
    public class FishingMinigame : BaseCraftingMinigame
    {
        // =====================================================================
        // Fishing-specific state
        // =====================================================================

        private List<Ripple> _ripples = new();
        private int _requiredRipples;
        private int _ripplesSpawned;
        private int _ripplesHit;
        private int _ripplesMissed;
        private float _totalScore;
        private float _hitTolerance;
        private float _expandSpeed;
        private float _timeSinceLastSpawn;
        private float _spawnInterval;
        private float _elapsedTime;
        private bool _gameSuccess;

        // Difficulty parameters (from Python fishing.py)
        private int _spotTier;
        private int _rodTier;
        private int _playerLuck;
        private int _playerStrength;
        private float _speedBonus;
        private float _accuracyBonus;

        // Pond dimensions (from Python FishingConfig defaults)
        private float _pondWidth = 400f;
        private float _pondHeight = 300f;

        // =====================================================================
        // Constructor
        // =====================================================================

        /// <summary>
        /// Create a fishing minigame.
        /// </summary>
        /// <param name="inputs">Material inputs (fishing spot resources).</param>
        /// <param name="recipeMeta">
        /// Expected keys: "spotTier" (int), "rodTier" (int), "playerLuck" (int),
        /// "playerStrength" (int), "speedBonus" (float), "accuracyBonus" (float).
        /// </param>
        /// <param name="buffTimeBonus">Speed buff from skills.</param>
        /// <param name="buffQualityBonus">Quality buff from skills.</param>
        /// <param name="seed">Optional RNG seed.</param>
        public FishingMinigame(
            List<RecipeInput> inputs,
            Dictionary<string, object> recipeMeta = null,
            float buffTimeBonus = 0f,
            float buffQualityBonus = 0f,
            int? seed = null)
            : base(inputs, recipeMeta, buffTimeBonus, buffQualityBonus, seed)
        {
            _spotTier = GetMeta("spotTier", 1);
            _rodTier = GetMeta("rodTier", 1);
            _playerLuck = GetMeta("playerLuck", 0);
            _playerStrength = GetMeta("playerStrength", 0);
            _speedBonus = GetMeta("speedBonus", 0f);
            _accuracyBonus = GetMeta("accuracyBonus", 0f);
        }

        // =====================================================================
        // BaseCraftingMinigame Abstract Methods
        // =====================================================================

        protected override void InitializeMinigame()
        {
            _ripples.Clear();
            _ripplesSpawned = 0;
            _ripplesHit = 0;
            _ripplesMissed = 0;
            _totalScore = 0;
            _timeSinceLastSpawn = 0;
            _elapsedTime = 0;
            _gameSuccess = false;

            CalculateDifficulty();

            // Time limit scales with required ripples
            _totalTime = 5f + _requiredRipples * 3f;
            _timeRemaining = _totalTime;

            // Spawn interval: time between ripples
            _spawnInterval = Math.Max(1.0f, _totalTime / (_requiredRipples + 2));
        }

        protected override void UpdateMinigame(float deltaTime)
        {
            _elapsedTime += deltaTime;
            _timeSinceLastSpawn += deltaTime;

            // Spawn new ripples
            if (_ripplesSpawned < _requiredRipples && _timeSinceLastSpawn >= _spawnInterval)
            {
                SpawnRipple();
                _timeSinceLastSpawn = 0f;
            }

            // Update active ripples
            for (int i = _ripples.Count - 1; i >= 0; i--)
            {
                var ripple = _ripples[i];
                if (!ripple.Active) continue;

                ripple.CurrentRadius += ripple.ExpandSpeed * deltaTime;

                // Check if ripple expanded beyond max (missed)
                if (ripple.CurrentRadius >= ripple.MaxRadius)
                {
                    ripple.Active = false;
                    if (!ripple.Hit)
                    {
                        _ripplesMissed++;
                    }
                }
            }

            // Check end condition: all ripples spawned and resolved
            if (_ripplesSpawned >= _requiredRipples)
            {
                bool allResolved = true;
                foreach (var r in _ripples)
                {
                    if (r.Active) { allResolved = false; break; }
                }
                if (allResolved)
                {
                    EndGame();
                }
            }
        }

        public override bool HandleInput(MinigameInput input)
        {
            if (input.Type != MinigameInputType.Click) return false;
            if (_isComplete || _isFailed) return false;

            float clickX = input.Value;
            float clickY = input.Index;

            // Find closest active ripple to click
            Ripple closest = null;
            float closestDist = float.MaxValue;

            foreach (var ripple in _ripples)
            {
                if (!ripple.Active || ripple.Hit) continue;

                float dx = clickX - ripple.X;
                float dy = clickY - ripple.Y;
                float dist = MathF.Sqrt(dx * dx + dy * dy);

                // Check if click is near the ripple ring
                float ringDist = MathF.Abs(dist - ripple.CurrentRadius);
                if (ringDist < closestDist)
                {
                    closestDist = ringDist;
                    closest = ripple;
                }
            }

            if (closest == null) return false;

            // Calculate score based on ring distance
            // Matches Python: fishing.py handle_click scoring
            float ringDistance = MathF.Abs(closestDist);
            int score = CalculateClickScore(ringDistance);

            closest.Hit = true;
            closest.Score = score;
            closest.Active = false;

            if (score > 0)
            {
                _ripplesHit++;
                _totalScore += score;
            }
            else
            {
                _ripplesMissed++;
            }

            return true;
        }

        protected override float CalculatePerformance()
        {
            int totalResolved = _ripplesHit + _ripplesMissed;
            if (totalResolved == 0) return 0f;

            float hitRate = (float)_ripplesHit / totalResolved;
            float avgScore = totalResolved > 0 ? _totalScore / totalResolved : 0f;

            // Performance is combination of hit rate and average score
            // Normalized to 0-1 range (avgScore max is 100)
            return Math.Clamp(hitRate * 0.5f + (avgScore / 100f) * 0.5f, 0f, 1f);
        }

        protected override CraftingReward CalculateRewardForDiscipline()
        {
            // Fishing has its own reward system
            // XP = 100 * 4^(tier-1)
            // Matches Python: fishing.py _end_game()
            int baseXP = (int)(100 * Math.Pow(4, _spotTier - 1));
            string quality = GetFishingQualityTier(_performanceScore);
            float qualityMult = GetQualityMultiplier(quality);

            return new CraftingReward
            {
                Quality = quality,
                PerformanceScore = _performanceScore,
                ExperienceReward = (int)(baseXP * qualityMult),
                BonusMultiplier = qualityMult,
                Success = _gameSuccess,
            };
        }

        protected override Dictionary<string, object> GetDisciplineState()
        {
            var activeRipples = new List<Dictionary<string, object>>();
            foreach (var r in _ripples)
            {
                if (r.Active)
                {
                    activeRipples.Add(new Dictionary<string, object>
                    {
                        ["x"] = r.X,
                        ["y"] = r.Y,
                        ["currentRadius"] = r.CurrentRadius,
                        ["targetRadius"] = r.TargetRadius,
                        ["maxRadius"] = r.MaxRadius,
                    });
                }
            }

            return new Dictionary<string, object>
            {
                ["ripples"] = activeRipples,
                ["ripplesSpawned"] = _ripplesSpawned,
                ["ripplesHit"] = _ripplesHit,
                ["ripplesMissed"] = _ripplesMissed,
                ["requiredRipples"] = _requiredRipples,
                ["totalScore"] = _totalScore,
                ["hitTolerance"] = _hitTolerance,
                ["pondWidth"] = _pondWidth,
                ["pondHeight"] = _pondHeight,
                ["spotTier"] = _spotTier,
                ["gameSuccess"] = _gameSuccess,
            };
        }

        // =====================================================================
        // Fishing-specific methods
        // =====================================================================

        /// <summary>
        /// Calculate difficulty parameters from player stats and spot/rod tiers.
        /// Matches Python: fishing.py _calculate_difficulty()
        /// </summary>
        private void CalculateDifficulty()
        {
            // Required ripples: base 8, reduced by LCK, scaled by tier
            // Python: max(4, int(8 - luck * 0.1)) * (1 + (tier-1) * 0.25)
            int baseRipples = Math.Max(4, (int)(8 - _playerLuck * 0.1));
            _requiredRipples = (int)(baseRipples * (1.0 + (_spotTier - 1) * 0.25));
            _requiredRipples = Math.Max(4, _requiredRipples);

            // Hit tolerance: base 15px + STR bonus, capped at 30
            // Python: min(30, 15 + STR * 0.5 + accuracy_bonus)
            _hitTolerance = Math.Min(30f, 15f + _playerStrength * 0.5f + _accuracyBonus);

            // Expand speed: base 80, modified by rod tier and spot tier
            // Python: 80 * rod_speed_mult * spot_speed_mult * (1 - speed_bonus * 0.5)
            float rodSpeedMult = 1.0f - (_rodTier - 1) * 0.15f;   // T1=1.0, T2=0.85, T3=0.70, T4=0.55
            float spotSpeedMult = 1.0f + (_spotTier - 1) * 0.2f;  // T1=1.0, T2=1.2, T3=1.4, T4=1.6
            _expandSpeed = 80f * rodSpeedMult * spotSpeedMult * (1.0f - _speedBonus * 0.5f);
        }

        /// <summary>
        /// Spawn a new ripple at a random position on the pond.
        /// </summary>
        private void SpawnRipple()
        {
            float x = (float)_rng.NextDouble() * (_pondWidth - 60f) + 30f;
            float y = (float)_rng.NextDouble() * (_pondHeight - 60f) + 30f;
            float targetRadius = 20f + (float)_rng.NextDouble() * 30f; // 20-50 px
            float maxRadius = targetRadius + _hitTolerance + 20f;

            var ripple = new Ripple
            {
                X = x,
                Y = y,
                TargetRadius = targetRadius,
                CurrentRadius = 0f,
                MaxRadius = maxRadius,
                ExpandSpeed = _expandSpeed,
                SpawnTime = _elapsedTime,
            };

            _ripples.Add(ripple);
            _ripplesSpawned++;
        }

        /// <summary>
        /// Calculate click score based on ring distance.
        /// Matches Python: fishing.py handle_click scoring
        /// </summary>
        private int CalculateClickScore(float ringDistance)
        {
            if (ringDistance <= 5f) return 100;                    // Perfect
            if (ringDistance <= 10f) return 75;                    // Good
            if (ringDistance <= 15f) return 50;                    // Fair
            if (ringDistance <= _hitTolerance)                     // Partial
                return Math.Max(25, (int)(50 * (1f - ringDistance / _hitTolerance)));
            return 0;                                              // Miss
        }

        /// <summary>
        /// End the fishing minigame and determine success.
        /// Matches Python: fishing.py _end_game()
        /// Success requires hit_rate >= 0.5 AND avg_score >= 40
        /// </summary>
        private void EndGame()
        {
            int totalResolved = _ripplesHit + _ripplesMissed;
            float hitRate = totalResolved > 0 ? (float)_ripplesHit / totalResolved : 0f;
            float avgScore = totalResolved > 0 ? _totalScore / totalResolved : 0f;

            _gameSuccess = hitRate >= 0.5f && avgScore >= 40f;

            if (_gameSuccess)
            {
                Complete();
            }
            else
            {
                Fail();
            }
        }

        /// <summary>
        /// Get quality tier for fishing results.
        /// Matches Python: fishing.py quality tier thresholds
        /// </summary>
        private static string GetFishingQualityTier(float performance)
        {
            if (performance >= 0.9f) return "legendary";
            if (performance >= 0.75f) return "masterwork";
            if (performance >= 0.6f) return "superior";
            if (performance >= 0.4f) return "fine";
            return "normal";
        }

        /// <summary>
        /// Get quality multiplier for XP/loot.
        /// Matches Python: fishing.py quality bonus_mult values
        /// </summary>
        private static float GetQualityMultiplier(string quality)
        {
            return quality switch
            {
                "legendary" => 1.5f,
                "masterwork" => 1.3f,
                "superior" => 1.15f,
                "fine" => 1.0f,
                _ => 0.8f,
            };
        }

        /// <summary>
        /// Override time expired: fishing ends game rather than failing
        /// </summary>
        protected override void OnTimeExpired()
        {
            EndGame();
        }
    }

    /// <summary>
    /// Manages fishing resource validation and loot processing.
    /// Migrated from: Crafting-subdisciplines/fishing.py FishingManager (lines 689-872)
    /// </summary>
    public class FishingManager
    {
        private static FishingManager _instance;
        private static readonly object _lock = new object();

        private FishingMinigame _activeMinigame;

        public static FishingManager Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new FishingManager();
                        }
                    }
                }
                return _instance;
            }
        }

        private FishingManager() { }

        public FishingMinigame ActiveMinigame => _activeMinigame;
        public bool IsActive => _activeMinigame != null && _activeMinigame.IsActive;

        /// <summary>
        /// Start a fishing minigame for the given spot tier and player stats.
        /// </summary>
        public FishingMinigame StartFishing(
            int spotTier, int rodTier,
            int playerLuck, int playerStrength,
            float speedBonus = 0f, float accuracyBonus = 0f)
        {
            var meta = new Dictionary<string, object>
            {
                ["spotTier"] = spotTier,
                ["rodTier"] = rodTier,
                ["playerLuck"] = playerLuck,
                ["playerStrength"] = playerStrength,
                ["speedBonus"] = speedBonus,
                ["accuracyBonus"] = accuracyBonus,
            };

            _activeMinigame = new FishingMinigame(
                new List<RecipeInput>(), meta);
            _activeMinigame.Start();

            return _activeMinigame;
        }

        /// <summary>
        /// Process fishing result: apply loot, XP, durability.
        /// Returns the reward. Caller handles inventory/XP application.
        /// </summary>
        public CraftingReward ProcessResult()
        {
            if (_activeMinigame == null) return null;

            var reward = _activeMinigame.GetReward();
            _activeMinigame = null;
            return reward;
        }
    }
}
