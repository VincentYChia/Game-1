// ============================================================================
// Game1.Unity.UI.TooltipRenderer
// Migrated from: rendering/renderer.py (lines 6063-6179: tooltip rendering)
// Migration phase: 6
// Date: 2026-02-13
//
// Deferred tooltip rendering — always on top of all UI.
// Fixes existing Python bug where tooltips could be covered by equipment menu.
// Lives on highest-sort-order Canvas.
// Self-building: if _tooltipPanel is null at Awake, _buildUI() constructs
// the full tooltip hierarchy programmatically via UIHelper.
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
        [SerializeField] private float _maxWidth = 320f;
        [SerializeField] private int _padding = 8;

        private bool _shouldShow;
        private string _pendingTitle;
        private string _pendingBody;
        private string _pendingStats;
        private string _pendingRarity;
        private Sprite _pendingIcon;
        private Vector2 _pendingPosition;

        // Fallback UI references populated by _buildUI()
        private Text _titleTextFallback;
        private Text _bodyTextFallback;
        private Text _statsTextFallback;

        private void Awake()
        {
            if (_tooltipPanel == null) _buildUI();

            Instance = this;
            Hide();
        }

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        private void _buildUI()
        {
            // Create a dedicated highest-sort-order canvas for the tooltip
            var tooltipCanvas = UIHelper.CreateCanvas("TooltipCanvas", 9999, transform);
            // Ensure the canvas doesn't block raycasts on empty areas
            var raycaster = tooltipCanvas.GetComponent<GraphicRaycaster>();
            if (raycaster != null) Object.Destroy(raycaster);

            // Tooltip panel — floating, semi-transparent dark background (0.95 alpha)
            var panelGo = new GameObject("TooltipPanel");
            panelGo.transform.SetParent(tooltipCanvas.transform, false);

            _tooltipPanel = panelGo.AddComponent<RectTransform>();
            _tooltipPanel.pivot = new Vector2(0f, 1f); // top-left pivot for mouse-follow
            _tooltipPanel.anchorMin = Vector2.zero;
            _tooltipPanel.anchorMax = Vector2.zero;
            _tooltipPanel.sizeDelta = new Vector2(_maxWidth, 0); // width capped, height auto

            // Background image — semi-transparent dark (0.95 alpha)
            var bgImg = panelGo.AddComponent<Image>();
            bgImg.color = new Color(0.08f, 0.08f, 0.12f, 0.95f);
            bgImg.raycastTarget = false;

            // ContentSizeFitter for vertical auto-sizing
            var csf = panelGo.AddComponent<ContentSizeFitter>();
            csf.horizontalFit = ContentSizeFitter.FitMode.PreferredSize;
            csf.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            // Vertical layout for stacking title / body / stats
            var vlg = panelGo.AddComponent<VerticalLayoutGroup>();
            vlg.padding = new RectOffset(_padding, _padding, _padding, _padding);
            vlg.spacing = 4f;
            vlg.childForceExpandWidth = true;
            vlg.childForceExpandHeight = false;
            vlg.childControlWidth = true;
            vlg.childControlHeight = true;

            // Constrain max width via LayoutElement
            var panelLe = panelGo.AddComponent<LayoutElement>();
            panelLe.preferredWidth = _maxWidth;

            // Rarity border (outline on panel, initially disabled)
            var borderOutline = panelGo.AddComponent<Outline>();
            borderOutline.effectColor = UIHelper.COLOR_TRANSPARENT;
            borderOutline.effectDistance = new Vector2(2, 2);

            // Icon image (optional, hidden by default)
            var iconGo = new GameObject("Icon");
            iconGo.transform.SetParent(panelGo.transform, false);
            var iconRt = iconGo.AddComponent<RectTransform>();
            var iconLe = iconGo.AddComponent<LayoutElement>();
            iconLe.preferredWidth = 32;
            iconLe.preferredHeight = 32;
            _iconImage = iconGo.AddComponent<Image>();
            _iconImage.preserveAspect = true;
            _iconImage.raycastTarget = false;
            _iconImage.enabled = false;

            // Title text — gold, 16pt
            _titleTextFallback = UIHelper.CreateText(panelGo.transform, "TitleText",
                "", 16, UIHelper.COLOR_TEXT_GOLD, TextAnchor.UpperLeft);
            _titleTextFallback.raycastTarget = false;
            _titleTextFallback.horizontalOverflow = HorizontalWrapMode.Wrap;
            _titleTextFallback.verticalOverflow = VerticalWrapMode.Overflow;
            var titleLe = _titleTextFallback.gameObject.AddComponent<LayoutElement>();
            titleLe.preferredWidth = _maxWidth - _padding * 2;

            // Body text — white, 13pt
            _bodyTextFallback = UIHelper.CreateText(panelGo.transform, "BodyText",
                "", 13, Color.white, TextAnchor.UpperLeft);
            _bodyTextFallback.raycastTarget = false;
            _bodyTextFallback.horizontalOverflow = HorizontalWrapMode.Wrap;
            _bodyTextFallback.verticalOverflow = VerticalWrapMode.Overflow;
            var bodyLe = _bodyTextFallback.gameObject.AddComponent<LayoutElement>();
            bodyLe.preferredWidth = _maxWidth - _padding * 2;

            // Stats text — secondary color, 13pt (hidden by default)
            _statsTextFallback = UIHelper.CreateText(panelGo.transform, "StatsText",
                "", 13, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.UpperLeft);
            _statsTextFallback.raycastTarget = false;
            _statsTextFallback.horizontalOverflow = HorizontalWrapMode.Wrap;
            _statsTextFallback.verticalOverflow = VerticalWrapMode.Overflow;
            var statsLe = _statsTextFallback.gameObject.AddComponent<LayoutElement>();
            statsLe.preferredWidth = _maxWidth - _padding * 2;
            _statsTextFallback.gameObject.SetActive(false);

            // Cache border reference for rarity coloring
            _rarityBorder = bgImg; // Reuse bg image for rarity tinting via outline
            // We'll use the Outline component for rarity border color
            _rarityBorder = null; // Handled via outline in code-built path

            // Hidden by default
            panelGo.SetActive(false);
        }

        // ====================================================================
        // Public API
        // ====================================================================

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

        // ====================================================================
        // Rendering
        // ====================================================================

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

            // Update content — use TMPro fields if assigned, otherwise fallback Text
            _updateTitle();
            _updateBody();
            _updateStats();
            _updateRarityBorder();
            _updateIcon();

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

        private void _updateTitle()
        {
            if (_titleText != null)
            {
                _titleText.text = _pendingTitle ?? "";
                if (!string.IsNullOrEmpty(_pendingRarity))
                    _titleText.color = ColorConverter.GetRarityColor(_pendingRarity);
                else
                    _titleText.color = Color.white;
            }
            else if (_titleTextFallback != null)
            {
                _titleTextFallback.text = _pendingTitle ?? "";
                if (!string.IsNullOrEmpty(_pendingRarity))
                    _titleTextFallback.color = ColorConverter.GetRarityColor(_pendingRarity);
                else
                    _titleTextFallback.color = UIHelper.COLOR_TEXT_GOLD;
            }
        }

        private void _updateBody()
        {
            if (_bodyText != null)
                _bodyText.text = _pendingBody ?? "";
            else if (_bodyTextFallback != null)
                _bodyTextFallback.text = _pendingBody ?? "";
        }

        private void _updateStats()
        {
            bool hasStats = !string.IsNullOrEmpty(_pendingStats);

            if (_statsText != null)
            {
                _statsText.text = _pendingStats ?? "";
                _statsText.gameObject.SetActive(hasStats);
            }
            else if (_statsTextFallback != null)
            {
                _statsTextFallback.text = _pendingStats ?? "";
                _statsTextFallback.gameObject.SetActive(hasStats);
            }
        }

        private void _updateRarityBorder()
        {
            if (_rarityBorder != null && !string.IsNullOrEmpty(_pendingRarity))
            {
                _rarityBorder.color = ColorConverter.GetRarityColor(_pendingRarity);
                _rarityBorder.enabled = true;
            }
            else if (_rarityBorder != null)
            {
                _rarityBorder.enabled = false;
            }

            // Code-built path: update outline color for rarity border
            if (_tooltipPanel != null && _rarityBorder == null)
            {
                var outline = _tooltipPanel.GetComponent<Outline>();
                if (outline != null)
                {
                    if (!string.IsNullOrEmpty(_pendingRarity))
                        outline.effectColor = ColorConverter.GetRarityColor(_pendingRarity);
                    else
                        outline.effectColor = UIHelper.COLOR_TRANSPARENT;
                }
            }
        }

        private void _updateIcon()
        {
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
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }
    }
}
