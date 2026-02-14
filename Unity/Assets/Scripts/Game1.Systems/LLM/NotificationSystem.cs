// ============================================================================
// Game1.Systems.LLM.NotificationSystem
// Migrated from: core/game_engine.py (notification system) + Phase 7 design
// Migration phase: 7
// Date: 2026-02-14
//
// Pure C# notification system that manages a queue of notifications.
// The existing NotificationUI MonoBehaviour (Phase 6) handles rendering.
// This class provides the typed notification API that Phase 7 systems use.
//
// During migration: debug notifications mark stubs and unimplemented features.
// Post-migration: gameplay notifications (item acquired, level up, etc.).
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Systems.LLM
{
    /// <summary>
    /// Notification type determines color and filtering behavior.
    /// Debug notifications are filtered out in release builds.
    /// </summary>
    public enum NotificationType
    {
        /// <summary>General information (white).</summary>
        Info,

        /// <summary>Positive feedback (green).</summary>
        Success,

        /// <summary>Caution (yellow).</summary>
        Warning,

        /// <summary>Failure (red).</summary>
        Error,

        /// <summary>Stub/migration markers (cyan). Debug/dev builds only.</summary>
        Debug
    }

    /// <summary>
    /// A single notification entry with message, type, and lifetime tracking.
    /// </summary>
    public class Notification
    {
        public string Message { get; set; }
        public NotificationType Type { get; set; }
        public float Duration { get; set; }
        public float TimeRemaining { get; set; }
        public float Alpha { get; set; } = 1.0f;
    }

    /// <summary>
    /// Queue-based notification manager (pure C#, no Unity dependency).
    /// Manages active and pending notifications with overflow queuing.
    ///
    /// The Phase 6 NotificationUI MonoBehaviour reads from this system
    /// to render notifications on screen. This separation follows
    /// MACRO-3 (UI State Separation) from IMPROVEMENTS.md.
    ///
    /// Thread-safe: Show() can be called from any thread.
    /// </summary>
    public class NotificationSystem
    {
        // ====================================================================
        // Constants
        // ====================================================================

        public const int MaxVisibleNotifications = 5;
        public const float FadeOutDuration = 0.5f;
        public const float DefaultDuration = 3.0f;
        public const int MaxPendingQueue = 20;

        // ====================================================================
        // Singleton
        // ====================================================================

        private static NotificationSystem _instance;
        private static readonly object _singletonLock = new object();

        public static NotificationSystem Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_singletonLock)
                    {
                        if (_instance == null)
                            _instance = new NotificationSystem();
                    }
                }
                return _instance;
            }
        }

        private NotificationSystem() { }

        /// <summary>Reset singleton for testing only.</summary>
        public static void ResetInstance()
        {
            lock (_singletonLock) { _instance = null; }
        }

        // ====================================================================
        // State
        // ====================================================================

        private readonly object _lock = new object();
        private readonly Queue<Notification> _pendingQueue = new();
        private readonly List<Notification> _activeNotifications = new();

        /// <summary>
        /// Callback invoked when a notification should be displayed.
        /// The Phase 6 NotificationUI subscribes to this to render notifications.
        /// Args: message, color (R, G, B), duration.
        /// </summary>
        public event Action<string, NotificationType, float> OnNotificationShow;

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>
        /// Show a notification message.
        /// Thread-safe. Can be called from background threads.
        /// </summary>
        /// <param name="message">Text to display.</param>
        /// <param name="type">Notification type (determines color and filtering).</param>
        /// <param name="duration">Display duration in seconds.</param>
        public void Show(string message, NotificationType type = NotificationType.Info,
                         float duration = DefaultDuration)
        {
            // Filter Debug notifications in release builds
            #if !DEBUG && !UNITY_EDITOR
            if (type == NotificationType.Debug)
                return;
            #endif

            lock (_lock)
            {
                var notification = new Notification
                {
                    Message = message,
                    Type = type,
                    Duration = duration,
                    TimeRemaining = duration
                };

                if (_activeNotifications.Count < MaxVisibleNotifications)
                {
                    _activeNotifications.Add(notification);
                }
                else
                {
                    // Cap pending queue to prevent memory pressure
                    if (_pendingQueue.Count >= MaxPendingQueue)
                    {
                        _pendingQueue.Dequeue(); // Drop oldest pending
                    }
                    _pendingQueue.Enqueue(notification);
                }
            }

            // Raise event for UI layer (outside lock to avoid deadlocks)
            OnNotificationShow?.Invoke(message, type, duration);
        }

        /// <summary>
        /// Update notification timers. Call from main thread Update().
        /// </summary>
        /// <param name="deltaTime">Time elapsed since last frame.</param>
        public void Update(float deltaTime)
        {
            lock (_lock)
            {
                for (int i = _activeNotifications.Count - 1; i >= 0; i--)
                {
                    var n = _activeNotifications[i];
                    n.TimeRemaining -= deltaTime;

                    // Fade out in final FadeOutDuration seconds
                    if (n.TimeRemaining <= FadeOutDuration)
                    {
                        n.Alpha = Math.Max(0f, n.TimeRemaining / FadeOutDuration);
                    }

                    // Remove expired
                    if (n.TimeRemaining <= 0f)
                    {
                        _activeNotifications.RemoveAt(i);

                        // Promote from pending queue
                        if (_pendingQueue.Count > 0)
                        {
                            _activeNotifications.Add(_pendingQueue.Dequeue());
                        }
                    }
                }
            }
        }

        /// <summary>
        /// Get a snapshot of currently active notifications.
        /// Used by UI layer for rendering.
        /// </summary>
        public List<Notification> GetActiveNotifications()
        {
            lock (_lock)
            {
                return new List<Notification>(_activeNotifications);
            }
        }

        /// <summary>Number of currently active (visible) notifications.</summary>
        public int ActiveCount
        {
            get { lock (_lock) { return _activeNotifications.Count; } }
        }

        /// <summary>Number of notifications waiting in the pending queue.</summary>
        public int PendingCount
        {
            get { lock (_lock) { return _pendingQueue.Count; } }
        }

        /// <summary>Clear all active and pending notifications.</summary>
        public void Clear()
        {
            lock (_lock)
            {
                _activeNotifications.Clear();
                _pendingQueue.Clear();
            }
        }

        // ====================================================================
        // Color mapping
        // ====================================================================

        /// <summary>
        /// Get RGBA color for a notification type.
        /// Matches the Phase 7 spec exactly.
        /// </summary>
        public static (float R, float G, float B) GetColor(NotificationType type)
        {
            return type switch
            {
                NotificationType.Info    => (1.0f, 1.0f, 1.0f),       // White
                NotificationType.Success => (0.2f, 0.8f, 0.2f),       // Green
                NotificationType.Warning => (1.0f, 0.8f, 0.0f),       // Yellow
                NotificationType.Error   => (1.0f, 0.3f, 0.3f),       // Red
                NotificationType.Debug   => (0.0f, 0.8f, 0.8f),       // Cyan
                _                        => (1.0f, 1.0f, 1.0f),       // White fallback
            };
        }
    }
}
