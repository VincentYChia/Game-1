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

        protected override void Awake()
        {
            base.Awake();
            if (_bellowsButton != null)
                _bellowsButton.onClick.AddListener(_onBellows);
        }

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
                rt.anchorMin = new Vector2(_perfectTempMin, 0f);
                rt.anchorMax = new Vector2(_perfectTempMax, 1f);
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
            }

            // Update hit counter
            if (_hitsText != null)
                _hitsText.text = $"Hits: {_hitCount} (Perfect: {_perfectHits})";
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
    }
}
