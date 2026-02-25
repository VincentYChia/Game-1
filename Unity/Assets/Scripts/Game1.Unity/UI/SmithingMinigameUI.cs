// ============================================================================
// Game1.Unity.UI.SmithingMinigameUI
// Migrated from: Crafting-subdisciplines/smithing.py (749 lines)
//              + rendering/renderer.py (lines 106-262: render_smithing)
// Migration phase: 6
// Date: 2026-02-13
//
// Smithing minigame: temperature bar, bellows button, hammer timing.
// Player heats metal to target temp and strikes with good timing.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.World;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Smithing minigame — temperature management + hammer strike timing.
    /// Heat metal with bellows, strike when in the perfect zone.
    /// Performance based on number of perfect strikes.
    /// </summary>
    public class SmithingMinigameUI : MinigameUI
    {
        [Header("Smithing-Specific")]
        [SerializeField] private Image _temperatureBar;
        [SerializeField] private Image _perfectZone;
        [SerializeField] private Image _hammerTimingBar;
        [SerializeField] private Image _hammerCursor;
        [SerializeField] private TextMeshProUGUI _hitsText;
        [SerializeField] private Button _bellowsButton;

        [Header("Temperature Settings")]
        [SerializeField] private float _heatingRate = 0.3f;
        [SerializeField] private float _coolingRate = 0.15f;
        [SerializeField] private float _perfectTempMin = 0.6f;
        [SerializeField] private float _perfectTempMax = 0.8f;

        private float _temperature;
        private float _hammerPosition; // 0-1, oscillates
        private float _hammerSpeed = 2f;
        private float _hammerDirection = 1f;
        private int _hitCount;
        private int _perfectHits;
        private int _totalStrikes;
        private bool _isHeating;

        // Fallback text (used when built programmatically)
        private Text _hitsTextFallback;

        protected override void Awake()
        {
            base.Awake();
            if (_bellowsButton != null)
                _bellowsButton.onClick.AddListener(_onBellows);
        }

        // ====================================================================
        // Programmatic UI Construction
        // ====================================================================

        /// <summary>
        /// Build smithing-specific UI: temperature gauge (left), hammer timing
        /// bar (center), hit counter text, fan/fuel buttons.
        /// </summary>
        protected override void _buildUI()
        {
            var parent = _contentArea != null ? _contentArea : _panel.transform;

            // --- Temperature gauge (vertical bar, left side) ---
            // Container for temperature elements
            var tempContainerRt = UIHelper.CreatePanel(parent, "TemperatureContainer",
                new Color(0.10f, 0.10f, 0.15f, 1f),
                new Vector2(0.02f, 0.05f), new Vector2(0.12f, 0.85f));

            // Temperature bar background (fills the container)
            var tempBarBg = UIHelper.CreateImage(tempContainerRt, "TempBarBg",
                new Color(0.15f, 0.15f, 0.22f, 1f));
            var tempBarBgRt = tempBarBg.rectTransform;
            tempBarBgRt.anchorMin = new Vector2(0.1f, 0.05f);
            tempBarBgRt.anchorMax = new Vector2(0.9f, 0.95f);
            tempBarBgRt.offsetMin = Vector2.zero;
            tempBarBgRt.offsetMax = Vector2.zero;

            // Temperature fill bar (vertical fill: blue cold -> red hot)
            _temperatureBar = UIHelper.CreateFilledImage(tempBarBg.rectTransform,
                "TempBarFill", new Color(0.2f, 0.2f, 0.8f, 1f),
                Image.FillMethod.Vertical);
            var tempFillRt = _temperatureBar.rectTransform;
            tempFillRt.anchorMin = Vector2.zero;
            tempFillRt.anchorMax = Vector2.one;
            tempFillRt.offsetMin = new Vector2(2, 2);
            tempFillRt.offsetMax = new Vector2(-2, -2);

            // Perfect zone overlay (green band on the temperature bar)
            _perfectZone = UIHelper.CreateImage(tempBarBg.rectTransform, "PerfectZone",
                new Color(0f, 0.8f, 0f, 0.35f));
            // Position will be set in OnStart based on _perfectTempMin/_perfectTempMax

            // "HOT" label at top
            var hotLabel = UIHelper.CreateText(tempContainerRt, "HotLabel", "HOT",
                11, UIHelper.COLOR_TEXT_RED, TextAnchor.MiddleCenter);
            var hotLabelRt = hotLabel.rectTransform;
            hotLabelRt.anchorMin = new Vector2(0f, 0.96f);
            hotLabelRt.anchorMax = new Vector2(1f, 1f);
            hotLabelRt.offsetMin = Vector2.zero;
            hotLabelRt.offsetMax = Vector2.zero;

            // "COLD" label at bottom
            var coldLabel = UIHelper.CreateText(tempContainerRt, "ColdLabel", "COLD",
                11, UIHelper.COLOR_MANA, TextAnchor.MiddleCenter);
            var coldLabelRt = coldLabel.rectTransform;
            coldLabelRt.anchorMin = new Vector2(0f, 0f);
            coldLabelRt.anchorMax = new Vector2(1f, 0.04f);
            coldLabelRt.offsetMin = Vector2.zero;
            coldLabelRt.offsetMax = Vector2.zero;

            // --- Hammer timing bar (horizontal, center) ---
            var hammerContainerRt = UIHelper.CreatePanel(parent, "HammerContainer",
                new Color(0.10f, 0.10f, 0.15f, 1f),
                new Vector2(0.18f, 0.38f), new Vector2(0.82f, 0.48f));

            // Hammer bar background
            _hammerTimingBar = UIHelper.CreateImage(hammerContainerRt, "HammerBar",
                new Color(0.20f, 0.20f, 0.28f, 1f));
            var hammerBarRt = _hammerTimingBar.rectTransform;
            hammerBarRt.anchorMin = new Vector2(0.02f, 0.1f);
            hammerBarRt.anchorMax = new Vector2(0.98f, 0.9f);
            hammerBarRt.offsetMin = Vector2.zero;
            hammerBarRt.offsetMax = Vector2.zero;

            // Target zone (center green band on hammer bar)
            var hammerTargetZone = UIHelper.CreateImage(hammerBarRt, "HammerTargetZone",
                new Color(0f, 0.7f, 0f, 0.3f));
            var hammerTargetRt = hammerTargetZone.rectTransform;
            hammerTargetRt.anchorMin = new Vector2(0.4f, 0f);
            hammerTargetRt.anchorMax = new Vector2(0.6f, 1f);
            hammerTargetRt.offsetMin = Vector2.zero;
            hammerTargetRt.offsetMax = Vector2.zero;

            // Moving cursor indicator
            _hammerCursor = UIHelper.CreateImage(hammerBarRt, "HammerCursor",
                new Color(1f, 0.9f, 0.2f, 1f));
            // Position set dynamically in OnUpdate via anchor manipulation

            // "Strike" label above hammer bar
            var strikeLabel = UIHelper.CreateText(parent, "StrikeLabel",
                "Press SPACE to strike when cursor is in the green zone",
                14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            var strikeLabelRt = strikeLabel.rectTransform;
            strikeLabelRt.anchorMin = new Vector2(0.18f, 0.49f);
            strikeLabelRt.anchorMax = new Vector2(0.82f, 0.54f);
            strikeLabelRt.offsetMin = Vector2.zero;
            strikeLabelRt.offsetMax = Vector2.zero;

            // --- Hit counter text (above hammer area) ---
            _hitsTextFallback = UIHelper.CreateText(parent, "HitsText",
                "Hits: 0 (Perfect: 0)", 18, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);
            var hitsTxtRt = _hitsTextFallback.rectTransform;
            hitsTxtRt.anchorMin = new Vector2(0.18f, 0.56f);
            hitsTxtRt.anchorMax = new Vector2(0.82f, 0.64f);
            hitsTxtRt.offsetMin = Vector2.zero;
            hitsTxtRt.offsetMax = Vector2.zero;

            // --- Bellows / Fuel button (bottom center) ---
            _bellowsButton = UIHelper.CreateSizedButton(parent, "BellowsButton",
                "Bellows (Heat)",
                new Color(0.7f, 0.35f, 0.1f, 1f), UIHelper.COLOR_TEXT_PRIMARY,
                new Vector2(180f, 50f), new Vector2(0f, -160f),
                16);
            var bellowsBtnRt = _bellowsButton.GetComponent<RectTransform>();
            bellowsBtnRt.anchorMin = new Vector2(0.5f, 0.5f);
            bellowsBtnRt.anchorMax = new Vector2(0.5f, 0.5f);
            _bellowsButton.onClick.AddListener(_onBellows);

            // --- Fuel button (next to bellows) ---
            var fuelButton = UIHelper.CreateSizedButton(parent, "FuelButton",
                "Add Fuel",
                new Color(0.5f, 0.3f, 0.1f, 1f), UIHelper.COLOR_TEXT_PRIMARY,
                new Vector2(140f, 50f), new Vector2(180f, -160f),
                14);
            var fuelBtnRt = fuelButton.GetComponent<RectTransform>();
            fuelBtnRt.anchorMin = new Vector2(0.5f, 0.5f);
            fuelBtnRt.anchorMax = new Vector2(0.5f, 0.5f);
            fuelButton.onClick.AddListener(() =>
            {
                // Fuel adds a smaller heat boost
                _temperature = Mathf.Min(1f, _temperature + 0.05f);
            });
        }

        // ====================================================================
        // Minigame Logic
        // ====================================================================

        protected override void OnStart()
        {
            _temperature = 0.3f;
            _hammerPosition = 0f;
            _hammerDirection = 1f;
            _hitCount = 0;
            _perfectHits = 0;
            _totalStrikes = 0;
            _isHeating = false;

            if (_perfectZone != null)
            {
                var rt = _perfectZone.rectTransform;
                // Position perfect zone on the temperature bar
                rt.anchorMin = new Vector2(0f, _perfectTempMin);
                rt.anchorMax = new Vector2(1f, _perfectTempMax);
                rt.offsetMin = Vector2.zero;
                rt.offsetMax = Vector2.zero;
            }
        }

        protected override void OnUpdate(float deltaTime)
        {
            // Temperature changes
            if (_isHeating)
            {
                _temperature = Mathf.Min(1f, _temperature + _heatingRate * deltaTime);
                _isHeating = false; // Requires continuous button press
            }
            else
            {
                _temperature = Mathf.Max(0f, _temperature - _coolingRate * deltaTime);
            }

            // Update temperature bar
            if (_temperatureBar != null)
            {
                _temperatureBar.fillAmount = _temperature;
                _temperatureBar.color = Color.Lerp(
                    new Color(0.2f, 0.2f, 0.8f), // cold
                    new Color(1f, 0.3f, 0f),       // hot
                    _temperature
                );
            }

            // Hammer oscillation
            _hammerPosition += _hammerDirection * _hammerSpeed * deltaTime;
            if (_hammerPosition >= 1f) { _hammerPosition = 1f; _hammerDirection = -1f; }
            if (_hammerPosition <= 0f) { _hammerPosition = 0f; _hammerDirection = 1f; }

            if (_hammerCursor != null)
            {
                var rt = _hammerCursor.rectTransform;
                rt.anchorMin = new Vector2(_hammerPosition - 0.02f, 0f);
                rt.anchorMax = new Vector2(_hammerPosition + 0.02f, 1f);
                rt.offsetMin = Vector2.zero;
                rt.offsetMax = Vector2.zero;
            }

            // Update hit counter
            _setHitsText($"Hits: {_hitCount} (Perfect: {_perfectHits})");
        }

        protected override void OnCraftAction()
        {
            // Strike the hammer!
            _totalStrikes++;

            bool inTempRange = _temperature >= _perfectTempMin && _temperature <= _perfectTempMax;
            bool inTimingZone = _hammerPosition >= 0.4f && _hammerPosition <= 0.6f;

            if (inTempRange && inTimingZone)
            {
                _perfectHits++;
                _hitCount++;
                ParticleEffects.Instance?.PlaySparks(Vector3.zero, 30);
            }
            else if (inTempRange || inTimingZone)
            {
                _hitCount++;
                ParticleEffects.Instance?.PlaySparks(Vector3.zero, 10);
            }

            // Performance based on perfect strike ratio
            _performance = _totalStrikes > 0 ? (float)_perfectHits / Mathf.Max(_totalStrikes, 5) : 0f;
        }

        private void _onBellows()
        {
            _isHeating = true;
        }

        private void _setHitsText(string text)
        {
            if (_hitsText != null) _hitsText.text = text;
            else if (_hitsTextFallback != null) _hitsTextFallback.text = text;
        }
    }
}
