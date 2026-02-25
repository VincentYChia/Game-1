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
using Game1.Unity.Utilities;

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

        // Fallback text references (programmatic UI)
        private Text _alignmentsTextFallback;
        private Text _speedDisplayText;

        // ====================================================================
        // Programmatic UI Construction
        // ====================================================================

        /// <summary>
        /// Build refining-specific UI: cylinder alignment display (center),
        /// target zone indicator, aligned count text, speed display.
        /// </summary>
        protected override void _buildUI()
        {
            base._buildUI();
            var parent = _contentArea != null ? _contentArea : _panel.transform;

            // --- Cylinder alignment display (center) ---
            var cylinderContainerRt = UIHelper.CreatePanel(parent, "CylinderContainer",
                new Color(0.10f, 0.10f, 0.15f, 1f),
                new Vector2(0.20f, 0.15f), new Vector2(0.80f, 0.75f));

            // Outer ring (background circle)
            var outerRing = UIHelper.CreateImage(cylinderContainerRt, "OuterRing",
                new Color(0.20f, 0.22f, 0.30f, 1f));
            var outerRingRt = outerRing.rectTransform;
            outerRingRt.anchorMin = new Vector2(0.1f, 0.05f);
            outerRingRt.anchorMax = new Vector2(0.9f, 0.95f);
            outerRingRt.offsetMin = Vector2.zero;
            outerRingRt.offsetMax = Vector2.zero;

            // Target zone indicator (arc/wedge on the ring)
            _targetZone = UIHelper.CreateImage(outerRing.rectTransform, "TargetZone",
                new Color(0f, 1f, 0f, 0.4f));
            var targetZoneRt = _targetZone.rectTransform;
            targetZoneRt.anchorMin = new Vector2(0.05f, 0.05f);
            targetZoneRt.anchorMax = new Vector2(0.95f, 0.95f);
            targetZoneRt.offsetMin = Vector2.zero;
            targetZoneRt.offsetMax = Vector2.zero;
            // Rotation set dynamically in _setNewTarget

            // Rotation indicator (the spinning needle/arrow)
            _rotationIndicator = UIHelper.CreateImage(outerRing.rectTransform, "RotationIndicator",
                new Color(1f, 0.85f, 0.2f, 1f));
            var rotIndicatorRt = _rotationIndicator.rectTransform;
            rotIndicatorRt.anchorMin = new Vector2(0.47f, 0.47f);
            rotIndicatorRt.anchorMax = new Vector2(0.53f, 0.95f);
            rotIndicatorRt.offsetMin = Vector2.zero;
            rotIndicatorRt.offsetMax = Vector2.zero;
            rotIndicatorRt.pivot = new Vector2(0.5f, 0f); // Pivot at bottom for rotation

            // Center dot
            var centerDot = UIHelper.CreateImage(outerRing.rectTransform, "CenterDot",
                new Color(0.5f, 0.5f, 0.6f, 1f));
            var centerDotRt = centerDot.rectTransform;
            centerDotRt.anchorMin = new Vector2(0.42f, 0.42f);
            centerDotRt.anchorMax = new Vector2(0.58f, 0.58f);
            centerDotRt.offsetMin = Vector2.zero;
            centerDotRt.offsetMax = Vector2.zero;

            // --- Aligned count text (above cylinder) ---
            _alignmentsTextFallback = UIHelper.CreateText(parent, "AlignmentsText",
                "Alignments: 0/6", 20, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);
            var alignTxtRt = _alignmentsTextFallback.rectTransform;
            alignTxtRt.anchorMin = new Vector2(0.20f, 0.78f);
            alignTxtRt.anchorMax = new Vector2(0.80f, 0.88f);
            alignTxtRt.offsetMin = Vector2.zero;
            alignTxtRt.offsetMax = Vector2.zero;

            // --- Speed display (below cylinder) ---
            _speedDisplayText = UIHelper.CreateText(parent, "SpeedDisplay",
                "Speed: 120 deg/s", 14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            var speedTxtRt = _speedDisplayText.rectTransform;
            speedTxtRt.anchorMin = new Vector2(0.25f, 0.05f);
            speedTxtRt.anchorMax = new Vector2(0.75f, 0.12f);
            speedTxtRt.offsetMin = Vector2.zero;
            speedTxtRt.offsetMax = Vector2.zero;

            // --- Instruction text ---
            var instructionText = UIHelper.CreateText(parent, "InstructionText",
                "Press SPACE when the indicator is in the green zone",
                14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            var instrTxtRt = instructionText.rectTransform;
            instrTxtRt.anchorMin = new Vector2(0.15f, 0.88f);
            instrTxtRt.anchorMax = new Vector2(0.85f, 0.95f);
            instrTxtRt.offsetMin = Vector2.zero;
            instrTxtRt.offsetMax = Vector2.zero;
        }

        // ====================================================================
        // Minigame Logic
        // ====================================================================

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

            _setAlignmentsText($"Alignments: {_alignmentsMade}/{_alignmentsNeeded}");

            // Update speed display
            if (_speedDisplayText != null)
                _speedDisplayText.text = $"Speed: {_rotationSpeed:F0} deg/s";

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

        private void _setAlignmentsText(string text)
        {
            if (_alignmentsText != null) _alignmentsText.text = text;
            else if (_alignmentsTextFallback != null) _alignmentsTextFallback.text = text;
        }
    }
}
