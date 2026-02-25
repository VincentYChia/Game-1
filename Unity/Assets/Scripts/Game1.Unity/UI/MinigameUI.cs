// ============================================================================
// Game1.Unity.UI.MinigameUI
// Migrated from: game_engine.py (lines 3550-5700: minigame orchestration)
// Migration phase: 6
// Date: 2026-02-13
//
// Abstract base for all 5 crafting minigame UIs.
// Provides shared lifecycle: start, update, complete, timer, performance.
// ============================================================================

using System;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Abstract base class for crafting minigame UIs.
    /// Provides shared timer, performance tracking, and lifecycle management.
    /// Concrete implementations handle discipline-specific input and display.
    ///
    /// If [SerializeField] references are not assigned in the inspector,
    /// _buildBaseUI() creates the full shared UI hierarchy at runtime,
    /// and _buildUI() (overridden by subclasses) adds discipline-specific elements.
    /// </summary>
    public abstract class MinigameUI : MonoBehaviour
    {
        // ====================================================================
        // Inspector References (shared by all minigames)
        // ====================================================================

        [Header("Shared UI")]
        [SerializeField] protected GameObject _panel;
        [SerializeField] protected TextMeshProUGUI _titleText;
        [SerializeField] protected TextMeshProUGUI _timerText;
        [SerializeField] protected Image _timerBar;
        [SerializeField] protected TextMeshProUGUI _performanceText;
        [SerializeField] protected Button _cancelButton;

        [Header("Result Display")]
        [SerializeField] protected GameObject _resultPanel;
        [SerializeField] protected TextMeshProUGUI _resultTitleText;
        [SerializeField] protected TextMeshProUGUI _resultQualityText;
        [SerializeField] protected Image _resultItemIcon;
        [SerializeField] protected Button _resultCloseButton;

        // ====================================================================
        // Fallback Text references (used when building UI programmatically,
        // since UIHelper creates legacy Text, not TextMeshProUGUI)
        // ====================================================================

        protected Text _titleTextFallback;
        protected Text _timerTextFallback;
        protected Text _performanceTextFallback;
        protected Text _resultTitleTextFallback;
        protected Text _resultQualityTextFallback;
        protected Text _resultScoreTextFallback;

        // ====================================================================
        // Events
        // ====================================================================

        /// <summary>Raised when minigame completes. Args: (performance 0-1, discipline).</summary>
        public event Action<float, string> OnMinigameComplete;

        /// <summary>Raised when minigame is canceled.</summary>
        public event Action OnMinigameCanceled;

        // ====================================================================
        // State
        // ====================================================================

        protected bool _isActive;
        protected float _timeRemaining;
        protected float _totalTime;
        protected float _performance;
        protected string _discipline;
        protected string _recipeId;

        /// <summary>
        /// The content area within _panel where subclasses add discipline-specific UI.
        /// Set by _buildBaseUI so subclasses can parent their elements here.
        /// </summary>
        protected RectTransform _contentArea;

        private GameStateManager _stateManager;
        private InputManager _inputManager;

        // ====================================================================
        // Initialization
        // ====================================================================

        protected virtual void Awake()
        {
            if (_panel == null)
            {
                _buildBaseUI();
                _buildUI();
            }

            if (_cancelButton != null)
                _cancelButton.onClick.AddListener(Cancel);
            if (_resultCloseButton != null)
                _resultCloseButton.onClick.AddListener(_closeResult);
        }

        protected virtual void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
            _inputManager = FindFirstObjectByType<InputManager>();

            if (_inputManager != null)
            {
                _inputManager.OnCraftAction += _onCraftAction;
                _inputManager.OnEscape += _onEscape;
            }

            _setVisible(false);
        }

        protected virtual void OnDestroy()
        {
            if (_inputManager != null)
            {
                _inputManager.OnCraftAction -= _onCraftAction;
                _inputManager.OnEscape -= _onEscape;
            }
        }

        // ====================================================================
        // Programmatic UI Construction (base shared elements)
        // ====================================================================

        /// <summary>
        /// Build the shared base UI: panel, title, timer, performance bar,
        /// cancel button, and result overlay. Called when _panel is null.
        /// </summary>
        private void _buildBaseUI()
        {
            // --- Main panel: covers most of the screen (10% margin on each side) ---
            var panelRt = UIHelper.CreatePanel(
                transform, "MinigamePanel", UIHelper.COLOR_BG_DARK,
                new Vector2(0.08f, 0.06f), new Vector2(0.92f, 0.94f));
            _panel = panelRt.gameObject;

            var panelLayout = UIHelper.AddVerticalLayout(panelRt, 6f,
                new RectOffset(12, 12, 10, 10));

            // --- Header row: title + cancel button ---
            var headerRt = UIHelper.CreatePanel(panelRt, "Header", UIHelper.COLOR_BG_HEADER,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(headerRt.gameObject, 44f);
            UIHelper.AddHorizontalLayout(headerRt, 8f, new RectOffset(12, 12, 4, 4));

            // Title text (left side of header)
            _titleTextFallback = UIHelper.CreateText(headerRt, "TitleText",
                "Minigame", 22, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredSize(_titleTextFallback.gameObject, -1f, 36f);

            // Cancel button (right side of header)
            _cancelButton = UIHelper.CreateButton(headerRt, "CancelButton", "Cancel",
                new Color(0.6f, 0.15f, 0.15f, 1f), UIHelper.COLOR_TEXT_PRIMARY, 14);
            UIHelper.SetPreferredSize(_cancelButton.gameObject, 80f, 32f);

            // --- Timer row ---
            var timerRowRt = UIHelper.CreatePanel(panelRt, "TimerRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(timerRowRt.gameObject, 32f);

            // Timer text (top, centered)
            _timerTextFallback = UIHelper.CreateText(timerRowRt, "TimerText",
                "30.0s", 18, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleRight);
            var timerTxtRt = _timerTextFallback.rectTransform;
            timerTxtRt.anchorMin = new Vector2(0.85f, 0f);
            timerTxtRt.anchorMax = new Vector2(1f, 1f);
            timerTxtRt.offsetMin = Vector2.zero;
            timerTxtRt.offsetMax = new Vector2(-4f, 0f);

            // Timer bar (progress bar)
            var timerBarBg = UIHelper.CreateImage(timerRowRt, "TimerBarBg",
                new Color(0.15f, 0.15f, 0.20f, 1f));
            var timerBarBgRt = timerBarBg.rectTransform;
            timerBarBgRt.anchorMin = new Vector2(0.02f, 0.2f);
            timerBarBgRt.anchorMax = new Vector2(0.83f, 0.8f);
            timerBarBgRt.offsetMin = Vector2.zero;
            timerBarBgRt.offsetMax = Vector2.zero;

            _timerBar = UIHelper.CreateFilledImage(timerBarBg.rectTransform, "TimerBarFill",
                UIHelper.COLOR_MANA);
            var timerFillRt = _timerBar.rectTransform;
            timerFillRt.anchorMin = Vector2.zero;
            timerFillRt.anchorMax = Vector2.one;
            timerFillRt.offsetMin = new Vector2(2, 2);
            timerFillRt.offsetMax = new Vector2(-2, -2);

            // --- Content area (where subclasses add discipline-specific UI) ---
            _contentArea = UIHelper.CreatePanel(panelRt, "ContentArea", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            // Let it expand to fill remaining space
            var contentLE = _contentArea.gameObject.AddComponent<LayoutElement>();
            contentLE.flexibleHeight = 1f;
            contentLE.flexibleWidth = 1f;

            // --- Performance bar (bottom) ---
            var perfRowRt = UIHelper.CreatePanel(panelRt, "PerformanceRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(perfRowRt.gameObject, 28f);

            _performanceTextFallback = UIHelper.CreateText(perfRowRt, "PerformanceText",
                "Score: 0%", 16, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);

            // --- Result overlay panel (hidden by default) ---
            _buildResultOverlay(panelRt);
        }

        /// <summary>
        /// Build the result overlay: semi-transparent panel with RESULT header,
        /// quality text, score text, and Continue button.
        /// </summary>
        private void _buildResultOverlay(RectTransform parentPanel)
        {
            // Overlay covers the entire minigame panel
            var overlayRt = UIHelper.CreatePanel(
                parentPanel, "ResultOverlay",
                new Color(0.05f, 0.05f, 0.10f, 0.90f),
                new Vector2(0.15f, 0.15f), new Vector2(0.85f, 0.85f));
            _resultPanel = overlayRt.gameObject;

            var overlayLayout = UIHelper.AddVerticalLayout(overlayRt, 12f,
                new RectOffset(24, 24, 24, 24));

            // "RESULT" header
            _resultTitleTextFallback = UIHelper.CreateText(overlayRt, "ResultHeader",
                "RESULT", 28, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_resultTitleTextFallback.gameObject, 44f);

            // Divider
            UIHelper.CreateDivider(overlayRt, 2f);

            // Quality text
            _resultQualityTextFallback = UIHelper.CreateText(overlayRt, "QualityText",
                "Quality: Normal", 22, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_resultQualityTextFallback.gameObject, 36f);

            // Score text
            _resultScoreTextFallback = UIHelper.CreateText(overlayRt, "ScoreText",
                "Score: 0%", 18, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_resultScoreTextFallback.gameObject, 30f);

            // Spacer
            var spacerGo = new GameObject("Spacer");
            spacerGo.transform.SetParent(overlayRt, false);
            spacerGo.AddComponent<RectTransform>();
            var spacerLE = spacerGo.AddComponent<LayoutElement>();
            spacerLE.flexibleHeight = 1f;

            // Continue button
            _resultCloseButton = UIHelper.CreateButton(overlayRt, "ContinueButton", "Continue",
                UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 18);
            UIHelper.SetPreferredHeight(_resultCloseButton.gameObject, 40f);

            _resultPanel.SetActive(false);
        }

        /// <summary>
        /// Override in subclasses to build discipline-specific UI elements.
        /// Called after _buildBaseUI() when inspector references are null.
        /// Use _contentArea as the parent for discipline-specific elements.
        /// </summary>
        protected virtual void _buildUI() { }

        // ====================================================================
        // Text Helpers (write to TMP or fallback Text)
        // ====================================================================

        /// <summary>Set title text on whichever text component is available.</summary>
        protected void _setTitleText(string text)
        {
            if (_titleText != null) _titleText.text = text;
            else if (_titleTextFallback != null) _titleTextFallback.text = text;
        }

        /// <summary>Set timer text on whichever text component is available.</summary>
        protected void _setTimerText(string text)
        {
            if (_timerText != null) _timerText.text = text;
            else if (_timerTextFallback != null) _timerTextFallback.text = text;
        }

        /// <summary>Set performance text on whichever text component is available.</summary>
        protected void _setPerformanceText(string text)
        {
            if (_performanceText != null) _performanceText.text = text;
            else if (_performanceTextFallback != null) _performanceTextFallback.text = text;
        }

        /// <summary>Set result title text on whichever text component is available.</summary>
        protected void _setResultTitleText(string text)
        {
            if (_resultTitleText != null) _resultTitleText.text = text;
            else if (_resultTitleTextFallback != null) _resultTitleTextFallback.text = text;
        }

        /// <summary>Set result quality text on whichever text component is available.</summary>
        protected void _setResultQualityText(string text)
        {
            if (_resultQualityText != null) _resultQualityText.text = text;
            else if (_resultQualityTextFallback != null) _resultQualityTextFallback.text = text;
        }

        // ====================================================================
        // Lifecycle
        // ====================================================================

        /// <summary>Start the minigame for a recipe.</summary>
        public virtual void StartMinigame(string discipline, string recipeId, float duration)
        {
            _discipline = discipline;
            _recipeId = recipeId;
            _totalTime = duration;
            _timeRemaining = duration;
            _performance = 0f;
            _isActive = true;

            _setTitleText($"{discipline} Minigame");

            if (_resultPanel != null)
                _resultPanel.SetActive(false);

            _setVisible(true);
            _stateManager?.TransitionTo(GameState.MinigameActive);

            OnStart();
        }

        /// <summary>Cancel the minigame.</summary>
        public virtual void Cancel()
        {
            _isActive = false;
            OnMinigameCanceled?.Invoke();
            _setVisible(false);
            _stateManager?.TransitionTo(GameState.Playing);
        }

        /// <summary>Complete the minigame with final performance.</summary>
        protected virtual void Complete(float finalPerformance)
        {
            _isActive = false;
            _performance = Mathf.Clamp01(finalPerformance);

            string quality = _performance switch
            {
                >= 0.90f => "Legendary",
                >= 0.75f => "Masterwork",
                >= 0.50f => "Superior",
                >= 0.25f => "Fine",
                _ => "Normal"
            };

            // Show result
            if (_resultPanel != null)
            {
                _resultPanel.SetActive(true);
                _setResultTitleText("Crafting Complete!");
                _setResultQualityText($"Quality: {quality} ({_performance:P0})");

                // Also update score fallback if present
                if (_resultScoreTextFallback != null)
                    _resultScoreTextFallback.text = $"Score: {_performance:P0}";
            }

            OnMinigameComplete?.Invoke(_performance, _discipline);
        }

        // ====================================================================
        // Update Loop
        // ====================================================================

        protected virtual void Update()
        {
            if (!_isActive) return;

            // Timer countdown
            _timeRemaining -= Time.deltaTime;
            if (_timerBar != null)
                _timerBar.fillAmount = _timeRemaining / _totalTime;
            _setTimerText($"{_timeRemaining:F1}s");

            // Update performance display
            _setPerformanceText($"Score: {_performance:P0}");

            // Time's up
            if (_timeRemaining <= 0)
            {
                Complete(_performance);
                return;
            }

            // Discipline-specific update
            OnUpdate(Time.deltaTime);
        }

        // ====================================================================
        // Abstract Methods (implemented by each discipline)
        // ====================================================================

        /// <summary>Called when minigame starts. Set up discipline-specific UI.</summary>
        protected abstract void OnStart();

        /// <summary>Called every frame while minigame is active.</summary>
        protected abstract void OnUpdate(float deltaTime);

        /// <summary>Called when the craft action key (Spacebar) is pressed.</summary>
        protected abstract void OnCraftAction();

        // ====================================================================
        // Input Handlers
        // ====================================================================

        private void _onCraftAction()
        {
            if (_isActive) OnCraftAction();
        }

        private void _onEscape()
        {
            if (_isActive) Cancel();
        }

        private void _closeResult()
        {
            if (_resultPanel != null) _resultPanel.SetActive(false);
            _setVisible(false);
            _stateManager?.TransitionTo(GameState.Playing);
        }

        protected void _setVisible(bool visible)
        {
            if (_panel != null) _panel.SetActive(visible);
        }
    }
}
