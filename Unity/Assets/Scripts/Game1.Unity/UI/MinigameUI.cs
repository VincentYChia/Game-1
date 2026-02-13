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

namespace Game1.Unity.UI
{
    /// <summary>
    /// Abstract base class for crafting minigame UIs.
    /// Provides shared timer, performance tracking, and lifecycle management.
    /// Concrete implementations handle discipline-specific input and display.
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

        private GameStateManager _stateManager;
        private InputManager _inputManager;

        // ====================================================================
        // Initialization
        // ====================================================================

        protected virtual void Awake()
        {
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

            if (_titleText != null)
                _titleText.text = $"{discipline} Minigame";

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
                if (_resultTitleText != null) _resultTitleText.text = "Crafting Complete!";
                if (_resultQualityText != null) _resultQualityText.text = $"Quality: {quality} ({_performance:P0})";
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
            if (_timerText != null)
                _timerText.text = $"{_timeRemaining:F1}s";

            // Update performance display
            if (_performanceText != null)
                _performanceText.text = $"Score: {_performance:P0}";

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
