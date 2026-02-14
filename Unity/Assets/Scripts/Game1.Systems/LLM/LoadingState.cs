// ============================================================================
// Game1.Systems.LLM.LoadingState
// Migrated from: systems/llm_item_generator.py (LoadingState class, lines 104-244)
// Migration phase: 7
// Date: 2026-02-14
//
// Thread-safe loading state for UI progress indicators.
// Supports both small indicator and full-screen overlay modes.
// Includes smooth ease-out cubic animation for indeterminate progress.
// ============================================================================

using System;

namespace Game1.Systems.LLM
{
    /// <summary>
    /// Thread-safe loading state for UI progress indicators.
    /// Supports both small indicator and full-screen overlay modes.
    /// Includes smooth animation for indeterminate progress.
    ///
    /// All public properties use lock-based synchronization to ensure
    /// safe access from both the main thread (UI reads) and background
    /// threads (generation writes). Maps Python threading.Lock() to C# lock().
    /// </summary>
    public class LoadingState
    {
        // ====================================================================
        // Animation constants (exact match to Python)
        // ====================================================================

        /// <summary>Seconds to animate from 0% to 90% (ease-out cubic).</summary>
        public const float SmoothProgressDuration = 15.0f;

        /// <summary>Maximum animated progress before completion.</summary>
        public const float SmoothProgressMax = 0.90f;

        /// <summary>Seconds to show completion state before marking as done.</summary>
        public const float CompletionDelay = 0.5f;

        // ====================================================================
        // State (all access synchronized via _lock)
        // ====================================================================

        private readonly object _lock = new object();
        private bool _isLoading;
        private string _message = "";
        private float _progress;
        private bool _overlayMode;
        private string _subtitle = "";
        private float _startTime;
        private bool _completeState;
        private float _completeTime;
        private bool _useSmoothAnimation = true;

        /// <summary>
        /// Time provider for testability. Defaults to system clock.
        /// Override in tests to control time progression.
        /// </summary>
        private readonly Func<float> _timeProvider;

        public LoadingState() : this(null) { }

        /// <summary>
        /// Create a LoadingState with an optional custom time provider.
        /// </summary>
        /// <param name="timeProvider">
        /// Function returning current time in seconds.
        /// Defaults to Time.realtimeSinceStartup equivalent via Environment.TickCount.
        /// </param>
        public LoadingState(Func<float> timeProvider)
        {
            _timeProvider = timeProvider ?? (() => Environment.TickCount / 1000f);
        }

        // ====================================================================
        // Properties (thread-safe reads)
        // ====================================================================

        /// <summary>
        /// Whether loading is currently in progress.
        /// Returns false after completion delay has elapsed.
        /// </summary>
        public bool IsLoading
        {
            get
            {
                lock (_lock)
                {
                    if (_completeState)
                    {
                        float elapsed = _timeProvider() - _completeTime;
                        return elapsed < CompletionDelay;
                    }
                    return _isLoading;
                }
            }
        }

        /// <summary>
        /// Current loading message. Shows "Item Generation Complete" when in complete state.
        /// </summary>
        public string Message
        {
            get
            {
                lock (_lock)
                {
                    return _completeState ? "Item Generation Complete" : _message;
                }
            }
        }

        /// <summary>
        /// Current subtitle text. Empty when in complete state.
        /// </summary>
        public string Subtitle
        {
            get
            {
                lock (_lock)
                {
                    return _completeState ? "" : _subtitle;
                }
            }
        }

        /// <summary>
        /// Current progress value (0.0-1.0). Returns 1.0 when in complete state.
        /// </summary>
        public float Progress
        {
            get
            {
                lock (_lock)
                {
                    return _completeState ? 1.0f : _progress;
                }
            }
        }

        /// <summary>Whether displaying as full-screen overlay.</summary>
        public bool OverlayMode
        {
            get { lock (_lock) { return _overlayMode; } }
        }

        /// <summary>Whether generation is in the completion state.</summary>
        public bool IsComplete
        {
            get { lock (_lock) { return _completeState; } }
        }

        // ====================================================================
        // Animation
        // ====================================================================

        /// <summary>
        /// Get animated progress for display.
        /// Ease-out cubic from 0% to 90% over SmoothProgressDuration seconds.
        /// Formula: eased = 1 - (1 - t)^3, scaled by SmoothProgressMax.
        /// Matches Python implementation exactly.
        /// </summary>
        public float GetAnimatedProgress()
        {
            lock (_lock)
            {
                if (_completeState) return 1.0f;
                if (!_isLoading) return 0.0f;

                if (!_useSmoothAnimation) return _progress;

                float elapsed = _timeProvider() - _startTime;
                float t = Math.Min(elapsed / SmoothProgressDuration, 1.0f);

                // Ease-out cubic: 1 - (1 - t)^3
                float oneMinusT = 1.0f - t;
                float eased = 1.0f - (oneMinusT * oneMinusT * oneMinusT);

                // Use whichever is higher: animated or explicitly set progress
                float animatedProgress = eased * SmoothProgressMax;
                return Math.Max(animatedProgress, _progress);
            }
        }

        // ====================================================================
        // State transitions
        // ====================================================================

        /// <summary>
        /// Begin a loading operation.
        /// </summary>
        /// <param name="message">Loading message to display.</param>
        /// <param name="overlay">Whether to use full-screen overlay mode.</param>
        /// <param name="subtitle">Optional subtitle text.</param>
        public void Start(string message = "Loading...", bool overlay = false, string subtitle = "")
        {
            lock (_lock)
            {
                _isLoading = true;
                _message = message;
                _progress = 0.0f;
                _overlayMode = overlay;
                _subtitle = subtitle;
                _startTime = _timeProvider();
                _completeState = false;
                _completeTime = 0f;
                _useSmoothAnimation = true;
            }
        }

        /// <summary>
        /// Update loading state mid-operation.
        /// </summary>
        /// <param name="message">New message, or null to keep current.</param>
        /// <param name="progress">New progress (0.0-1.0), or null to keep current.</param>
        /// <param name="subtitle">New subtitle, or null to keep current.</param>
        public void Update(string message = null, float? progress = null, string subtitle = null)
        {
            lock (_lock)
            {
                if (message != null) _message = message;
                if (progress.HasValue)
                {
                    _progress = progress.Value;
                    _useSmoothAnimation = false;
                }
                if (subtitle != null) _subtitle = subtitle;
            }
        }

        /// <summary>
        /// Transition to completion state.
        /// Loading indicator shows for CompletionDelay more seconds.
        /// </summary>
        public void Finish()
        {
            lock (_lock)
            {
                _completeState = true;
                _completeTime = _timeProvider();
                _progress = 1.0f;
            }
        }

        /// <summary>
        /// Reset to idle state immediately. Used for cleanup.
        /// </summary>
        public void Reset()
        {
            lock (_lock)
            {
                _isLoading = false;
                _message = "";
                _progress = 0.0f;
                _overlayMode = false;
                _subtitle = "";
                _completeState = false;
                _completeTime = 0f;
                _useSmoothAnimation = true;
            }
        }
    }
}
