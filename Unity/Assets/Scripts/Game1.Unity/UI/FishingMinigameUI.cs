// ============================================================================
// Game1.Unity.UI.FishingMinigameUI
// Migrated from: rendering/renderer.py (fishing render sections)
//              + core/game_engine.py (fishing input handling)
// Migration phase: 6
// Date: 2026-02-21
//
// Unity UI for the fishing minigame: renders pond, ripples, and handles clicks.
// Self-building: if _panel is null at Start, _buildUI() constructs the full
// UI hierarchy programmatically via UIHelper.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Systems.Crafting;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

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
        // Fallback references populated by _buildUI()
        // ====================================================================

        private Text _timerTextFallback;
        private Text _scoreTextFallback;
        private Text _hitCountTextFallback;
        private Text _instructionTextFallback;
        private Image _timerBarFill;
        private Text _resultTitleFallback;
        private Text _resultDetailsFallback;

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
            if (_panel == null) _buildUI();

            _gameManager = GameManager.Instance;
            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();

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
                if (Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame && !_showingResult)
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
        // Self-Building UI
        // ====================================================================

        private void _buildUI()
        {
            // Root panel — centered, 580x520, dark background
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "FishingPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(580, 520), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);
            _panel = panelRt.gameObject;

            // Main vertical layout
            var vlg = UIHelper.AddVerticalLayout(panelRt, spacing: 6f,
                padding: new RectOffset(12, 12, 10, 10));

            // --- Header ---
            var (headerRow, headerTitle, headerHint) = UIHelper.CreateHeaderRow(
                panelRt, "FISHING", "[ESC] Close", 38f);

            // --- HUD row: timer, score, hits ---
            var hudRow = UIHelper.CreatePanel(panelRt, "HUDRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(hudRow.gameObject, 28);
            UIHelper.AddHorizontalLayout(hudRow, spacing: 12f,
                padding: new RectOffset(4, 4, 2, 2), childForceExpand: true);

            _timerTextFallback = UIHelper.CreateText(hudRow, "TimerText", "Time: 30.0s",
                15, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleLeft);
            _scoreTextFallback = UIHelper.CreateText(hudRow, "ScoreText", "Score: 0",
                15, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            _hitCountTextFallback = UIHelper.CreateText(hudRow, "HitCountText", "Hits: 0/0",
                15, UIHelper.COLOR_TEXT_GREEN, TextAnchor.MiddleRight);

            // --- Timer progress bar ---
            var (timerRoot, timerBg, timerFill, timerLabel) = UIHelper.CreateProgressBar(
                panelRt, "TimerBar",
                UIHelper.COLOR_BG_DARK, UIHelper.COLOR_MANA,
                new Vector2(540, 16), Vector2.zero);
            UIHelper.SetPreferredHeight(timerRoot.gameObject, 16);
            timerRoot.anchorMin = Vector2.zero;
            timerRoot.anchorMax = Vector2.one;
            _timerBarFill = timerFill;

            // --- Instruction text ---
            _instructionTextFallback = UIHelper.CreateText(panelRt, "InstructionText",
                "Click the ripples when they reach the target ring!",
                13, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_instructionTextFallback.gameObject, 22);

            // --- Pond area (main gameplay region) ---
            var pondPanelRt = UIHelper.CreatePanel(panelRt, "PondArea",
                new Color(0.05f, 0.15f, 0.30f, 0.90f),
                Vector2.zero, Vector2.one);
            var pondLe = pondPanelRt.gameObject.AddComponent<LayoutElement>();
            pondLe.flexibleHeight = 1f;
            pondLe.preferredHeight = 300;
            _pondArea = pondPanelRt;
            _pondBackground = pondPanelRt.GetComponent<Image>();

            // Ripple container inside the pond
            var rippleContainerRt = UIHelper.CreateContainer(pondPanelRt, "RippleContainer",
                Vector2.zero, Vector2.one);
            _rippleContainer = rippleContainerRt;

            // --- Result overlay panel (hidden by default) ---
            var resultRt = UIHelper.CreateSizedPanel(
                panelRt, "ResultPanel", new Color(0.06f, 0.06f, 0.10f, 0.95f),
                new Vector2(350, 200), Vector2.zero);
            resultRt.anchorMin = new Vector2(0.5f, 0.5f);
            resultRt.anchorMax = new Vector2(0.5f, 0.5f);
            resultRt.pivot = new Vector2(0.5f, 0.5f);
            _resultPanel = resultRt.gameObject;

            var resultVlg = UIHelper.AddVerticalLayout(resultRt, spacing: 8f,
                padding: new RectOffset(16, 16, 16, 16));
            resultVlg.childAlignment = TextAnchor.MiddleCenter;

            _resultTitleFallback = UIHelper.CreateText(resultRt, "ResultTitle", "",
                22, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_resultTitleFallback.gameObject, 36);

            _resultDetailsFallback = UIHelper.CreateText(resultRt, "ResultDetails", "",
                15, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_resultDetailsFallback.gameObject, 80);

            _resultCloseButton = UIHelper.CreateButton(resultRt, "ResultCloseButton",
                "Continue", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 16);
            UIHelper.SetPreferredHeight(_resultCloseButton.gameObject, 40);

            _resultPanel.SetActive(false);
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

            string instruction = "Click the ripples when they reach the target ring!";
            if (_instructionText != null)
                _instructionText.text = instruction;
            else if (_instructionTextFallback != null)
                _instructionTextFallback.text = instruction;

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
            string timerStr = $"Time: {state.TimeRemaining:F1}s";
            if (_timerText != null)
                _timerText.text = timerStr;
            else if (_timerTextFallback != null)
                _timerTextFallback.text = timerStr;

            if (_timerBar != null && state.TotalTime > 0)
                _timerBar.value = state.TimeRemaining / state.TotalTime;
            else if (_timerBarFill != null && state.TotalTime > 0)
                _timerBarFill.fillAmount = state.TimeRemaining / state.TotalTime;

            // Update score
            var discState = state.DisciplineState;
            if (discState.TryGetValue("totalScore", out var score))
            {
                string scoreStr = $"Score: {score}";
                if (_scoreText != null)
                    _scoreText.text = scoreStr;
                else if (_scoreTextFallback != null)
                    _scoreTextFallback.text = scoreStr;
            }

            if (discState.TryGetValue("ripplesHit", out var hits)
                && discState.TryGetValue("requiredRipples", out var total))
            {
                string hitStr = $"Hits: {hits}/{total}";
                if (_hitCountText != null)
                    _hitCountText.text = hitStr;
                else if (_hitCountTextFallback != null)
                    _hitCountTextFallback.text = hitStr;
            }

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
            Vector2 clickPos = Mouse.current != null ? Mouse.current.position.ReadValue() : Vector2.zero;
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

            string titleStr = reward.Success
                ? $"Catch! ({reward.QualityTier})"
                : "The fish got away...";
            if (_resultTitle != null)
                _resultTitle.text = titleStr;
            else if (_resultTitleFallback != null)
                _resultTitleFallback.text = titleStr;

            string detailStr = reward.Success
                ? $"Quality: {reward.QualityTier}\nBonus: {reward.BonusPct}%\nScore: {reward.PerformanceScore:P0}"
                : "Better luck next time!";
            if (_resultDetails != null)
                _resultDetails.text = detailStr;
            else if (_resultDetailsFallback != null)
                _resultDetailsFallback.text = detailStr;
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
