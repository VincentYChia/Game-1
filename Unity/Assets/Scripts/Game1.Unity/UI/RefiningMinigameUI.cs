// ============================================================================
// Game1.Unity.UI.RefiningMinigameUI
// Migrated from: Crafting-subdisciplines/refining.py (820 lines)
// Migration phase: 6
// Date: 2026-02-13
//
// Refining minigame: cylinder rotation alignment.
// Player aligns rotating cylinders to target positions.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.World;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Refining minigame — cylinder rotation alignment.
    /// Align rotating rings to target positions within timing windows.
    /// </summary>
    public class RefiningMinigameUI : MinigameUI
    {
        [Header("Refining-Specific")]
        [SerializeField] private Image _rotationIndicator;
        [SerializeField] private Image _targetZone;
        [SerializeField] private TextMeshProUGUI _alignmentsText;

        private float _rotation; // 0-360
        private float _rotationSpeed = 120f; // degrees per second
        private float _targetAngle;
        private float _targetRange = 30f; // degrees of acceptable zone
        private int _alignmentsMade;
        private int _alignmentsNeeded = 6;
        private bool _waitingForStrike;

        protected override void OnStart()
        {
            _rotation = 0f;
            _rotationSpeed = 120f;
            _alignmentsMade = 0;
            _waitingForStrike = true;
            _setNewTarget();
        }

        protected override void OnUpdate(float deltaTime)
        {
            // Rotate the indicator
            _rotation = (_rotation + _rotationSpeed * deltaTime) % 360f;

            if (_rotationIndicator != null)
            {
                _rotationIndicator.transform.localRotation = Quaternion.Euler(0, 0, -_rotation);
            }

            // Check if in target zone
            float angleDiff = Mathf.Abs(Mathf.DeltaAngle(_rotation, _targetAngle));
            bool inZone = angleDiff <= _targetRange / 2f;

            if (_targetZone != null)
            {
                _targetZone.color = inZone
                    ? new Color(0f, 1f, 0f, 0.4f)
                    : new Color(1f, 0f, 0f, 0.2f);
            }

            if (_alignmentsText != null)
                _alignmentsText.text = $"Alignments: {_alignmentsMade}/{_alignmentsNeeded}";

            _performance = (float)_alignmentsMade / _alignmentsNeeded;
        }

        protected override void OnCraftAction()
        {
            if (!_waitingForStrike) return;

            float angleDiff = Mathf.Abs(Mathf.DeltaAngle(_rotation, _targetAngle));
            if (angleDiff <= _targetRange / 2f)
            {
                _alignmentsMade++;
                ParticleEffects.Instance?.PlayEmbers(Vector3.zero, 15);

                if (_alignmentsMade >= _alignmentsNeeded)
                {
                    Complete((float)_alignmentsMade / _alignmentsNeeded);
                    return;
                }

                _setNewTarget();
                _rotationSpeed += 10f; // Speed up each success
            }
        }

        private void _setNewTarget()
        {
            _targetAngle = Random.Range(0f, 360f);

            if (_targetZone != null)
            {
                _targetZone.transform.localRotation = Quaternion.Euler(0, 0, -_targetAngle);
            }
        }
    }
}
