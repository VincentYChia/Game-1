// ============================================================================
// Game1.Unity.UI.NotificationUI
// Migrated from: rendering/renderer.py (lines 3933-3948: render_notifications)
// Migration phase: 6
// Date: 2026-02-13
//
// Toast notification system with fade and stacking.
// Notifications appear at top-right and auto-dismiss.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using TMPro;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Toast notification manager. Shows stacking messages that auto-dismiss.
    /// Used by Phase 7's NotificationSystem.Show() interface.
    /// </summary>
    public class NotificationUI : MonoBehaviour
    {
        public static NotificationUI Instance { get; private set; }

        [Header("Configuration")]
        [SerializeField] private Transform _notificationContainer;
        [SerializeField] private GameObject _notificationPrefab;
        [SerializeField] private float _defaultDuration = 3f;
        [SerializeField] private float _fadeDuration = 0.5f;
        [SerializeField] private int _maxNotifications = 5;
        [SerializeField] private float _verticalSpacing = 35f;

        private List<NotificationEntry> _activeNotifications = new List<NotificationEntry>();

        private class NotificationEntry
        {
            public GameObject GameObject;
            public TextMeshProUGUI Text;
            public CanvasGroup CanvasGroup;
            public float TimeRemaining;
            public float FadeTime;
        }

        private void Awake()
        {
            Instance = this;
        }

        private void Start()
        {
            // Bridge Phase 7 NotificationSystem (pure C#) to this MonoBehaviour UI
            try
            {
                Game1.Systems.LLM.NotificationSystem.Instance.OnNotificationShow += _onNotificationFromSystem;
            }
            catch (System.Exception) { /* NotificationSystem may not be initialized */ }
        }

        private void _onNotificationFromSystem(string message, Game1.Systems.LLM.NotificationType type, float duration)
        {
            var (r, g, b) = Game1.Systems.LLM.NotificationSystem.GetColor(type);
            Show(message, new Color(r, g, b), duration);
        }

        /// <summary>Show a notification message.</summary>
        public void Show(string message, float duration = -1f)
        {
            Show(message, Color.white, duration);
        }

        /// <summary>Show a notification with custom color.</summary>
        public void Show(string message, Color color, float duration = -1f)
        {
            if (duration < 0) duration = _defaultDuration;

            // Remove oldest if at max
            while (_activeNotifications.Count >= _maxNotifications)
            {
                _removeNotification(0);
            }

            // Create notification
            GameObject go;
            if (_notificationPrefab != null)
            {
                go = Instantiate(_notificationPrefab, _notificationContainer ?? transform);
            }
            else
            {
                go = new GameObject("Notification");
                go.transform.SetParent(_notificationContainer ?? transform, false);
                var tmp = go.AddComponent<TextMeshProUGUI>();
                tmp.fontSize = 16;
                tmp.alignment = TextAlignmentOptions.Right;
                var rt = go.GetComponent<RectTransform>();
                rt.sizeDelta = new Vector2(400, 30);
            }

            var text = go.GetComponentInChildren<TextMeshProUGUI>();
            if (text != null)
            {
                text.text = message;
                text.color = color;
            }

            var cg = go.GetComponent<CanvasGroup>();
            if (cg == null) cg = go.AddComponent<CanvasGroup>();

            _activeNotifications.Add(new NotificationEntry
            {
                GameObject = go,
                Text = text,
                CanvasGroup = cg,
                TimeRemaining = duration,
                FadeTime = _fadeDuration
            });

            _repositionNotifications();
        }

        /// <summary>Show a debug notification (yellow text).</summary>
        public void ShowDebug(string message)
        {
            Show("[DEBUG] " + message, Color.yellow, 5f);
        }

        private void Update()
        {
            for (int i = _activeNotifications.Count - 1; i >= 0; i--)
            {
                var entry = _activeNotifications[i];
                entry.TimeRemaining -= Time.deltaTime;

                // Fade out
                if (entry.TimeRemaining <= entry.FadeTime && entry.CanvasGroup != null)
                {
                    entry.CanvasGroup.alpha = Mathf.Max(0, entry.TimeRemaining / entry.FadeTime);
                }

                // Remove expired
                if (entry.TimeRemaining <= 0)
                {
                    _removeNotification(i);
                }
            }
        }

        private void _removeNotification(int index)
        {
            if (index < 0 || index >= _activeNotifications.Count) return;
            Destroy(_activeNotifications[index].GameObject);
            _activeNotifications.RemoveAt(index);
            _repositionNotifications();
        }

        private void _repositionNotifications()
        {
            for (int i = 0; i < _activeNotifications.Count; i++)
            {
                var rt = _activeNotifications[i].GameObject.GetComponent<RectTransform>();
                if (rt != null)
                {
                    rt.anchoredPosition = new Vector2(0, -i * _verticalSpacing);
                }
            }
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
            try
            {
                Game1.Systems.LLM.NotificationSystem.Instance.OnNotificationShow -= _onNotificationFromSystem;
            }
            catch (System.Exception) { }
        }
    }
}
