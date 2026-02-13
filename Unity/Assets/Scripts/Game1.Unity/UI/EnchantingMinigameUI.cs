// ============================================================================
// Game1.Unity.UI.EnchantingMinigameUI
// Migrated from: Crafting-subdisciplines/enchanting.py (1,410 lines)
// Migration phase: 6
// Date: 2026-02-13
//
// Enchanting minigame: spinning wheel with 20 slices.
// Player spins and stops on bonus zones for better results.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.World;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Enchanting minigame — spinning wheel with 20 slices.
    /// Bonus zones (green), penalty zones (red), neutral zones (gray).
    /// Player presses action to spin, then again to stop.
    /// </summary>
    public class EnchantingMinigameUI : MinigameUI
    {
        [Header("Enchanting-Specific")]
        [SerializeField] private Image _wheelImage;
        [SerializeField] private Image _pointerImage;
        [SerializeField] private TextMeshProUGUI _spinResultText;
        [SerializeField] private TextMeshProUGUI _spinsRemainingText;

        [Header("Wheel Settings")]
        [SerializeField] private int _sliceCount = 20;
        [SerializeField] private float _maxSpinSpeed = 720f;
        [SerializeField] private float _deceleration = 120f;

        private float _wheelAngle;
        private float _spinSpeed;
        private bool _isSpinning;
        private int _spinsRemaining = 3;
        private int _totalSpins = 3;
        private float _accumulatedScore;

        // Slice types: 0 = neutral, 1 = bonus, -1 = penalty
        private int[] _sliceTypes;

        protected override void OnStart()
        {
            _wheelAngle = 0f;
            _spinSpeed = 0f;
            _isSpinning = false;
            _spinsRemaining = _totalSpins;
            _accumulatedScore = 0f;

            _generateWheel();
        }

        protected override void OnUpdate(float deltaTime)
        {
            if (_isSpinning)
            {
                // Decelerate
                _spinSpeed = Mathf.Max(0f, _spinSpeed - _deceleration * deltaTime);
                _wheelAngle = (_wheelAngle + _spinSpeed * deltaTime) % 360f;

                if (_wheelImage != null)
                    _wheelImage.transform.localRotation = Quaternion.Euler(0, 0, -_wheelAngle);

                // Stopped spinning
                if (_spinSpeed <= 0f)
                {
                    _isSpinning = false;
                    _evaluateSpin();
                }
            }

            if (_spinsRemainingText != null)
                _spinsRemainingText.text = $"Spins: {_spinsRemaining}/{_totalSpins}";

            _performance = _accumulatedScore / Mathf.Max(_totalSpins - _spinsRemaining, 1);
        }

        protected override void OnCraftAction()
        {
            if (_isSpinning)
            {
                // Stop the wheel (apply brake)
                _spinSpeed *= 0.3f; // Quick brake
                return;
            }

            if (_spinsRemaining <= 0) return;

            // Start spinning
            _isSpinning = true;
            _spinSpeed = _maxSpinSpeed * Random.Range(0.8f, 1.2f);
            _spinsRemaining--;

            ParticleEffects.Instance?.PlayRuneGlow(Vector3.zero, 8);
        }

        private void _generateWheel()
        {
            _sliceTypes = new int[_sliceCount];

            // Place bonus and penalty zones
            for (int i = 0; i < _sliceCount; i++)
            {
                float roll = Random.value;
                if (roll < 0.25f) _sliceTypes[i] = 1;   // 25% bonus
                else if (roll < 0.40f) _sliceTypes[i] = -1; // 15% penalty
                else _sliceTypes[i] = 0;                    // 60% neutral
            }
        }

        private void _evaluateSpin()
        {
            // Determine which slice the pointer landed on
            float sliceAngle = 360f / _sliceCount;
            int sliceIndex = Mathf.FloorToInt(_wheelAngle / sliceAngle) % _sliceCount;
            int sliceType = _sliceTypes[sliceIndex];

            float spinScore = sliceType switch
            {
                1 => 1f,    // Bonus
                -1 => 0f,   // Penalty
                _ => 0.5f   // Neutral
            };

            _accumulatedScore += spinScore;

            string result = sliceType switch
            {
                1 => "BONUS!",
                -1 => "Penalty...",
                _ => "Neutral"
            };

            if (_spinResultText != null)
                _spinResultText.text = result;

            // Check if all spins used
            if (_spinsRemaining <= 0 && !_isSpinning)
            {
                Complete(_accumulatedScore / _totalSpins);
            }
        }
    }
}
