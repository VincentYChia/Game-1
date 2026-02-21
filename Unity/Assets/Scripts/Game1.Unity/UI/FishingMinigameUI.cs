// ============================================================================
// Game1.Unity.UI.FishingMinigameUI
// Migrated from: rendering/renderer.py (fishing render sections)
//              + core/game_engine.py (fishing input handling)
// Migration phase: 6
// Date: 2026-02-21
//
// Unity UI for the fishing minigame: renders pond, ripples, and handles clicks.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Systems.Crafting;
using Game1.Unity.Core;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Fishing minigame UI — renders a pond with expanding ripples.
    /// Player clicks ripples at the right time.
    /// </summary>
    public class FishingMinigameUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Pond Area")]
        [SerializeField] private RectTransform _pondArea;
        [SerializeField] private Image _pondBackground;

        [Header("Ripple Rendering")]
        [SerializeField] private GameObject _ripplePrefab;
        [SerializeField] private Transform _rippleContainer;

        [Header("HUD")]
        [SerializeField] private TextMeshProUGUI _timerText;
        [SerializeField] private TextMeshProUGUI _scoreText;
        [SerializeField] private TextMeshProUGUI _hitCountText;
        [SerializeField] private TextMeshProUGUI _instructionText;
        [SerializeField] private Slider _timerBar;

        [Header("Result")]
        [SerializeField] private GameObject _resultPanel;
        [SerializeField] private TextMeshProUGUI _resultTitle;
        [SerializeField] private TextMeshProUGUI _resultDetails;
        [SerializeField] private Button _resultCloseButton;

        // ====================================================================
        // State
        // ====================================================================

        private FishingMinigame _minigame;
        private List<GameObject> _activeRippleObjects = new();
        private bool _showingResult;

        private GameManager _gameManager;
        private GameStateManager _stateManager;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            _gameManager = GameManager.Instance;
            _stateManager = FindFirstObjectByType<GameStateManager>();

            if (_resultCloseButton != null)
                _resultCloseButton.onClick.AddListener(CloseResult);

            if (_panel != null) _panel.SetActive(false);
            if (_resultPanel != null) _resultPanel.SetActive(false);
        }

        private void Update()
        {
            if (_minigame == null || !_panel.activeSelf) return;

            if (_minigame.IsActive)
            {
                _minigame.Update(Time.deltaTime);
                UpdateDisplay();

                // Handle click input
                if (Input.GetMouseButtonDown(0) && !_showingResult)
                {
                    HandleClick();
                }
            }
            else if (!_showingResult)
            {
                ShowResult();
            }
        }

        // ====================================================================
        // Public Methods
        // ====================================================================

        /// <summary>Open the fishing minigame UI with an active minigame.</summary>
        public void Open(FishingMinigame minigame)
        {
            _minigame = minigame;
            _showingResult = false;

            if (_panel != null) _panel.SetActive(true);
            if (_resultPanel != null) _resultPanel.SetActive(false);
            if (_instructionText != null)
                _instructionText.text = "Click the ripples when they reach the target ring!";

            ClearRippleObjects();
        }

        /// <summary>Close the fishing UI.</summary>
        public void Close()
        {
            _minigame = null;
            _showingResult = false;
            ClearRippleObjects();

            if (_panel != null) _panel.SetActive(false);
            _stateManager?.TransitionTo(GameState.Playing);
        }

        // ====================================================================
        // Private Methods
        // ====================================================================

        private void UpdateDisplay()
        {
            if (_minigame == null) return;

            var state = _minigame.GetState();

            // Update timer
            if (_timerText != null)
                _timerText.text = $"Time: {state.TimeRemaining:F1}s";
            if (_timerBar != null && state.TotalTime > 0)
                _timerBar.value = state.TimeRemaining / state.TotalTime;

            // Update score
            var discState = state.DisciplineState;
            if (_scoreText != null && discState.TryGetValue("totalScore", out var score))
                _scoreText.text = $"Score: {score}";
            if (_hitCountText != null
                && discState.TryGetValue("ripplesHit", out var hits)
                && discState.TryGetValue("requiredRipples", out var total))
                _hitCountText.text = $"Hits: {hits}/{total}";

            // Update ripple visuals
            UpdateRippleVisuals(discState);
        }

        private void UpdateRippleVisuals(Dictionary<string, object> discState)
        {
            // In a full implementation, this would update ripple circle renderers
            // based on the ripple data in discState["ripples"]
            // For now, we track state for future 3D rendering
        }

        private void HandleClick()
        {
            if (_minigame == null || !_minigame.IsActive) return;

            // Convert screen click to pond-local coordinates
            Vector2 clickPos = Input.mousePosition;
            if (_pondArea != null)
            {
                RectTransformUtility.ScreenPointToLocalPointInRectangle(
                    _pondArea, clickPos, null, out var localPos);

                var input = new MinigameInput
                {
                    Type = MinigameInputType.Click,
                    Value = localPos.x + _pondArea.rect.width * 0.5f,
                    Index = (int)(localPos.y + _pondArea.rect.height * 0.5f),
                };

                _minigame.HandleInput(input);
            }
        }

        private void ShowResult()
        {
            _showingResult = true;

            var reward = FishingManager.Instance.ProcessResult();
            if (reward == null) return;

            if (_resultPanel != null) _resultPanel.SetActive(true);

            if (_resultTitle != null)
            {
                _resultTitle.text = reward.Success
                    ? $"Catch! ({reward.QualityTier})"
                    : "The fish got away...";
            }

            if (_resultDetails != null)
            {
                _resultDetails.text = reward.Success
                    ? $"Quality: {reward.QualityTier}\nBonus: {reward.BonusPct}%\nScore: {reward.PerformanceScore:P0}"
                    : "Better luck next time!";
            }
        }

        private void CloseResult()
        {
            if (_resultPanel != null) _resultPanel.SetActive(false);
            Close();
        }

        private void ClearRippleObjects()
        {
            foreach (var obj in _activeRippleObjects)
            {
                if (obj != null) Destroy(obj);
            }
            _activeRippleObjects.Clear();
        }
    }
}
