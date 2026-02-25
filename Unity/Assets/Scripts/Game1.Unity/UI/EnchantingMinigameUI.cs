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
using Game1.Unity.Utilities;

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

        // Fallback text references (programmatic UI)
        private Text _spinResultTextFallback;
        private Text _spinsRemainingTextFallback;
        private Text _currencyDisplayText;
        private Text _betDisplayText;

        // Programmatic UI references
        private Button _spinButton;
        private Image[] _sliceImages;

        // ====================================================================
        // Programmatic UI Construction
        // ====================================================================

        /// <summary>
        /// Build enchanting-specific UI: spinning wheel (center, 20 colored slices),
        /// bet controls, currency display, spin counter, spin button.
        /// </summary>
        protected override void _buildUI()
        {
            base._buildUI();
            var parent = _contentArea != null ? _contentArea : _panel.transform;

            // --- Wheel container (center) ---
            var wheelContainerRt = UIHelper.CreatePanel(parent, "WheelContainer",
                UIHelper.COLOR_TRANSPARENT,
                new Vector2(0.15f, 0.10f), new Vector2(0.75f, 0.82f));

            // Wheel background circle
            var wheelBg = UIHelper.CreateImage(wheelContainerRt, "WheelBackground",
                new Color(0.12f, 0.12f, 0.18f, 1f));
            var wheelBgRt = wheelBg.rectTransform;
            wheelBgRt.anchorMin = new Vector2(0.05f, 0.02f);
            wheelBgRt.anchorMax = new Vector2(0.95f, 0.98f);
            wheelBgRt.offsetMin = Vector2.zero;
            wheelBgRt.offsetMax = Vector2.zero;

            // Wheel image (the rotating element with colored slices)
            _wheelImage = UIHelper.CreateImage(wheelBg.rectTransform, "Wheel",
                new Color(0.25f, 0.25f, 0.35f, 1f));
            var wheelImgRt = _wheelImage.rectTransform;
            wheelImgRt.anchorMin = new Vector2(0.03f, 0.03f);
            wheelImgRt.anchorMax = new Vector2(0.97f, 0.97f);
            wheelImgRt.offsetMin = Vector2.zero;
            wheelImgRt.offsetMax = Vector2.zero;

            // Create 20 colored slice wedges on the wheel
            _sliceImages = new Image[_sliceCount];
            float sliceAngle = 360f / _sliceCount;
            for (int i = 0; i < _sliceCount; i++)
            {
                var sliceImg = UIHelper.CreateImage(_wheelImage.rectTransform,
                    $"Slice_{i}", Color.gray);
                var sliceRt = sliceImg.rectTransform;
                // Each slice is a thin wedge positioned radially
                // We approximate wedges as thin rectangles rotated around center
                sliceRt.anchorMin = new Vector2(0.48f, 0.48f);
                sliceRt.anchorMax = new Vector2(0.52f, 0.95f);
                sliceRt.offsetMin = Vector2.zero;
                sliceRt.offsetMax = Vector2.zero;
                sliceRt.pivot = new Vector2(0.5f, 0f);
                sliceRt.localRotation = Quaternion.Euler(0, 0, -i * sliceAngle);

                _sliceImages[i] = sliceImg;
            }

            // Center hub
            var centerHub = UIHelper.CreateImage(_wheelImage.rectTransform, "CenterHub",
                new Color(0.18f, 0.18f, 0.25f, 1f));
            var centerHubRt = centerHub.rectTransform;
            centerHubRt.anchorMin = new Vector2(0.38f, 0.38f);
            centerHubRt.anchorMax = new Vector2(0.62f, 0.62f);
            centerHubRt.offsetMin = Vector2.zero;
            centerHubRt.offsetMax = Vector2.zero;

            // --- Pointer (fixed, pointing at the wheel from the top) ---
            _pointerImage = UIHelper.CreateImage(wheelContainerRt, "Pointer",
                new Color(1f, 0.85f, 0.1f, 1f));
            var pointerRt = _pointerImage.rectTransform;
            pointerRt.anchorMin = new Vector2(0.47f, 0.92f);
            pointerRt.anchorMax = new Vector2(0.53f, 1.0f);
            pointerRt.offsetMin = Vector2.zero;
            pointerRt.offsetMax = Vector2.zero;

            // --- Right side panel: controls and info ---
            var controlPanelRt = UIHelper.CreatePanel(parent, "ControlPanel",
                new Color(0.10f, 0.10f, 0.15f, 1f),
                new Vector2(0.77f, 0.10f), new Vector2(0.97f, 0.82f));
            UIHelper.AddVerticalLayout(controlPanelRt, 8f, new RectOffset(8, 8, 12, 12));

            // Spins remaining
            _spinsRemainingTextFallback = UIHelper.CreateText(controlPanelRt,
                "SpinsRemainingText", "Spins: 3/3",
                16, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_spinsRemainingTextFallback.gameObject, 28f);

            UIHelper.CreateDivider(controlPanelRt, 1f);

            // Spin result text
            _spinResultTextFallback = UIHelper.CreateText(controlPanelRt,
                "SpinResultText", "",
                18, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_spinResultTextFallback.gameObject, 32f);

            UIHelper.CreateDivider(controlPanelRt, 1f);

            // Currency display
            _currencyDisplayText = UIHelper.CreateText(controlPanelRt,
                "CurrencyDisplay", "Essence: 100",
                14, UIHelper.COLOR_EXP, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_currencyDisplayText.gameObject, 24f);

            // Bet controls
            var betLabel = UIHelper.CreateText(controlPanelRt, "BetLabel", "Bet:",
                13, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(betLabel.gameObject, 20f);

            _betDisplayText = UIHelper.CreateText(controlPanelRt, "BetDisplay", "10",
                16, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_betDisplayText.gameObject, 24f);

            // Bet adjustment buttons
            var betButtonRowRt = UIHelper.CreatePanel(controlPanelRt, "BetButtons",
                UIHelper.COLOR_TRANSPARENT, Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(betButtonRowRt.gameObject, 32f);
            UIHelper.AddHorizontalLayout(betButtonRowRt, 4f,
                new RectOffset(2, 2, 2, 2), true);

            var betDownBtn = UIHelper.CreateButton(betButtonRowRt, "BetDown", "-",
                UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 16);
            // Bet down logic can be added here

            var betUpBtn = UIHelper.CreateButton(betButtonRowRt, "BetUp", "+",
                UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 16);
            // Bet up logic can be added here

            // Spacer
            var spacerGo = new GameObject("Spacer");
            spacerGo.transform.SetParent(controlPanelRt, false);
            spacerGo.AddComponent<RectTransform>();
            var spacerLE = spacerGo.AddComponent<LayoutElement>();
            spacerLE.flexibleHeight = 1f;

            // Spin button (large, at the bottom of control panel)
            _spinButton = UIHelper.CreateButton(controlPanelRt, "SpinButton", "SPIN!",
                new Color(0.15f, 0.50f, 0.15f, 1f), UIHelper.COLOR_TEXT_PRIMARY, 18);
            UIHelper.SetPreferredHeight(_spinButton.gameObject, 50f);
            _spinButton.onClick.AddListener(() =>
            {
                // Delegate to the same OnCraftAction logic
                if (_isActive) OnCraftAction();
            });

            // --- Spin counter (top of wheel area) ---
            var spinCounterText = UIHelper.CreateText(parent, "SpinCounterLabel",
                "Spin the wheel for enchantment power!",
                14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            var spinCounterRt = spinCounterText.rectTransform;
            spinCounterRt.anchorMin = new Vector2(0.10f, 0.85f);
            spinCounterRt.anchorMax = new Vector2(0.75f, 0.95f);
            spinCounterRt.offsetMin = Vector2.zero;
            spinCounterRt.offsetMax = Vector2.zero;
        }

        // ====================================================================
        // Minigame Logic
        // ====================================================================

        protected override void OnStart()
        {
            _wheelAngle = 0f;
            _spinSpeed = 0f;
            _isSpinning = false;
            _spinsRemaining = _totalSpins;
            _accumulatedScore = 0f;

            _generateWheel();
            _updateSliceColors();
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

                // Update spin button text while spinning
                if (_spinButton != null)
                {
                    var label = _spinButton.GetComponentInChildren<Text>();
                    if (label != null) label.text = "STOP!";
                }

                // Stopped spinning
                if (_spinSpeed <= 0f)
                {
                    _isSpinning = false;
                    _evaluateSpin();

                    // Reset button text
                    if (_spinButton != null)
                    {
                        var label = _spinButton.GetComponentInChildren<Text>();
                        if (label != null) label.text = _spinsRemaining > 0 ? "SPIN!" : "Done";
                    }
                }
            }

            _setSpinsRemainingText($"Spins: {_spinsRemaining}/{_totalSpins}");

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

        /// <summary>
        /// Update the programmatically-created slice images to match their types.
        /// </summary>
        private void _updateSliceColors()
        {
            if (_sliceImages == null || _sliceTypes == null) return;

            for (int i = 0; i < _sliceCount && i < _sliceImages.Length; i++)
            {
                if (_sliceImages[i] == null) continue;

                _sliceImages[i].color = _sliceTypes[i] switch
                {
                    1 => new Color(0.2f, 0.75f, 0.2f, 0.9f),  // Bonus: green
                    -1 => new Color(0.75f, 0.2f, 0.2f, 0.9f),  // Penalty: red
                    _ => new Color(0.45f, 0.45f, 0.55f, 0.9f)   // Neutral: gray
                };
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

            _setSpinResultText(result);

            // Check if all spins used
            if (_spinsRemaining <= 0 && !_isSpinning)
            {
                Complete(_accumulatedScore / _totalSpins);
            }
        }

        private void _setSpinResultText(string text)
        {
            if (_spinResultText != null) _spinResultText.text = text;
            else if (_spinResultTextFallback != null) _spinResultTextFallback.text = text;
        }

        private void _setSpinsRemainingText(string text)
        {
            if (_spinsRemainingText != null) _spinsRemainingText.text = text;
            else if (_spinsRemainingTextFallback != null) _spinsRemainingTextFallback.text = text;
        }
    }
}
