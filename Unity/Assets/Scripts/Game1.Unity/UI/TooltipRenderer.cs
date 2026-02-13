// ============================================================================
// Game1.Unity.UI.TooltipRenderer
// Migrated from: rendering/renderer.py (lines 6063-6179: tooltip rendering)
// Migration phase: 6
// Date: 2026-02-13
//
// Deferred tooltip rendering — always on top of all UI.
// Fixes existing Python bug where tooltips could be covered by equipment menu.
// Lives on highest-sort-order Canvas.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Deferred tooltip renderer — always renders on top of all other UI.
    /// UI components call Show() to request a tooltip; it renders in LateUpdate.
    /// This fixes the Python bug where tooltips were covered by equipment menu.
    /// </summary>
    public class TooltipRenderer : MonoBehaviour
    {
        public static TooltipRenderer Instance { get; private set; }

        [Header("Components")]
        [SerializeField] private RectTransform _tooltipPanel;
        [SerializeField] private TextMeshProUGUI _titleText;
        [SerializeField] private TextMeshProUGUI _bodyText;
        [SerializeField] private TextMeshProUGUI _statsText;
        [SerializeField] private Image _rarityBorder;
        [SerializeField] private Image _iconImage;

        [Header("Settings")]
        [SerializeField] private Vector2 _offset = new Vector2(15f, -15f);
        [SerializeField] private float _maxWidth = 300f;
        [SerializeField] private int _padding = 8;

        private bool _shouldShow;
        private string _pendingTitle;
        private string _pendingBody;
        private string _pendingStats;
        private string _pendingRarity;
        private Sprite _pendingIcon;
        private Vector2 _pendingPosition;

        private void Awake()
        {
            Instance = this;
            Hide();
        }

        /// <summary>Show a simple text tooltip at mouse position.</summary>
        public void Show(string title, string body, Vector2 screenPosition)
        {
            _pendingTitle = title;
            _pendingBody = body;
            _pendingStats = null;
            _pendingRarity = null;
            _pendingIcon = null;
            _pendingPosition = screenPosition;
            _shouldShow = true;
        }

        /// <summary>Show an item tooltip with stats and rarity.</summary>
        public void ShowItem(string title, string body, string stats, string rarity, Sprite icon, Vector2 screenPosition)
        {
            _pendingTitle = title;
            _pendingBody = body;
            _pendingStats = stats;
            _pendingRarity = rarity;
            _pendingIcon = icon;
            _pendingPosition = screenPosition;
            _shouldShow = true;
        }

        /// <summary>Hide the tooltip.</summary>
        public void Hide()
        {
            _shouldShow = false;
            if (_tooltipPanel != null)
                _tooltipPanel.gameObject.SetActive(false);
        }

        private void LateUpdate()
        {
            if (!_shouldShow)
            {
                if (_tooltipPanel != null && _tooltipPanel.gameObject.activeSelf)
                    _tooltipPanel.gameObject.SetActive(false);
                return;
            }

            if (_tooltipPanel == null) return;

            _tooltipPanel.gameObject.SetActive(true);

            // Update content
            if (_titleText != null)
            {
                _titleText.text = _pendingTitle ?? "";
                if (!string.IsNullOrEmpty(_pendingRarity))
                    _titleText.color = ColorConverter.GetRarityColor(_pendingRarity);
                else
                    _titleText.color = Color.white;
            }

            if (_bodyText != null)
                _bodyText.text = _pendingBody ?? "";

            if (_statsText != null)
            {
                _statsText.text = _pendingStats ?? "";
                _statsText.gameObject.SetActive(!string.IsNullOrEmpty(_pendingStats));
            }

            if (_rarityBorder != null && !string.IsNullOrEmpty(_pendingRarity))
            {
                _rarityBorder.color = ColorConverter.GetRarityColor(_pendingRarity);
                _rarityBorder.enabled = true;
            }
            else if (_rarityBorder != null)
            {
                _rarityBorder.enabled = false;
            }

            if (_iconImage != null)
            {
                if (_pendingIcon != null)
                {
                    _iconImage.sprite = _pendingIcon;
                    _iconImage.enabled = true;
                }
                else
                {
                    _iconImage.enabled = false;
                }
            }

            // Position tooltip, keeping it on screen
            Vector2 position = _pendingPosition + _offset;

            // Clamp to screen bounds
            float screenWidth = Screen.width;
            float screenHeight = Screen.height;
            Vector2 size = _tooltipPanel.sizeDelta;

            if (position.x + size.x > screenWidth)
                position.x = _pendingPosition.x - size.x - _offset.x;
            if (position.y - size.y < 0)
                position.y = _pendingPosition.y + size.y + Mathf.Abs(_offset.y);

            _tooltipPanel.position = position;

            // Reset for next frame
            _shouldShow = false;
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }
    }
}
