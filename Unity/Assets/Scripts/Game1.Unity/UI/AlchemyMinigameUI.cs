// ============================================================================
// Game1.Unity.UI.AlchemyMinigameUI
// Migrated from: Crafting-subdisciplines/alchemy.py (1,052 lines)
// Migration phase: 6
// Date: 2026-02-13
//
// Alchemy minigame: reaction chain stabilization.
// Player manages reaction stages, keeping stability in green zone.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.World;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Alchemy minigame — reaction chain stabilization.
    /// Keep the reaction stability within the green zone across stages.
    /// </summary>
    public class AlchemyMinigameUI : MinigameUI
    {
        [Header("Alchemy-Specific")]
        [SerializeField] private Image _stabilityBar;
        [SerializeField] private Image _sweetSpot;
        [SerializeField] private TextMeshProUGUI _stageText;
        [SerializeField] private Image[] _stageIndicators;

        private float _stability;
        private float _driftSpeed = 0.3f;
        private float _driftDirection = 1f;
        private int _currentStage;
        private int _totalStages = 5;
        private int _stagesCompleted;
        private float _stageTimer;
        private float _stageInterval = 3f;

        protected override void OnStart()
        {
            _stability = 0.5f;
            _currentStage = 0;
            _stagesCompleted = 0;
            _stageTimer = 0f;
            _driftDirection = 1f;
        }

        protected override void OnUpdate(float deltaTime)
        {
            // Stability drifts randomly
            _stability += _driftDirection * _driftSpeed * deltaTime;

            // Random drift changes
            if (Random.value < 0.02f)
                _driftDirection = -_driftDirection;

            _stability = Mathf.Clamp01(_stability);

            // Update stability bar
            if (_stabilityBar != null)
            {
                _stabilityBar.fillAmount = _stability;
                bool inZone = _stability >= 0.35f && _stability <= 0.65f;
                _stabilityBar.color = inZone
                    ? new Color(0f, 0.8f, 0f)
                    : new Color(0.8f, 0f, 0f);
            }

            // Stage progression
            _stageTimer += deltaTime;
            if (_stageTimer >= _stageInterval)
            {
                _stageTimer = 0f;
                bool wasStable = _stability >= 0.35f && _stability <= 0.65f;
                if (wasStable) _stagesCompleted++;
                _currentStage++;

                if (_currentStage >= _totalStages)
                {
                    Complete((float)_stagesCompleted / _totalStages);
                    return;
                }

                // Increase difficulty each stage
                _driftSpeed += 0.05f;
            }

            if (_stageText != null)
                _stageText.text = $"Stage {_currentStage + 1}/{_totalStages}";

            _performance = (float)_stagesCompleted / Mathf.Max(_currentStage, 1);
        }

        protected override void OnCraftAction()
        {
            // Stabilize: push stability toward center
            if (_stability < 0.5f) _stability += 0.1f;
            else _stability -= 0.1f;

            ParticleEffects.Instance?.PlayBubbles(Vector3.zero, 10);
        }
    }
}
