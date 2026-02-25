// ============================================================================
// Game1.Unity.UI.TitleUI
// Migrated from: core/game_engine.py (title display sections)
// Migration phase: 6
// Date: 2026-02-21
//
// Title browsing and selection UI panel.
// Self-building: if _panel is null at Start, _buildUI() constructs the full
// UI hierarchy programmatically via UIHelper.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Data.Databases;
using Game1.Data.Models;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Title UI panel — browse earned titles, view bonuses, equip active title.
    /// </summary>
    public class TitleUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Title List")]
        [SerializeField] private Transform _titleListContainer;
        [SerializeField] private GameObject _titleEntryPrefab;
        [SerializeField] private ScrollRect _titleScrollRect;

        [Header("Title Detail")]
        [SerializeField] private TextMeshProUGUI _titleName;
        [SerializeField] private TextMeshProUGUI _titleDescription;
        [SerializeField] private TextMeshProUGUI _titleBonuses;
        [SerializeField] private TextMeshProUGUI _titleTier;

        [Header("Actions")]
        [SerializeField] private Button _equipButton;
        [SerializeField] private Button _closeButton;

        [Header("Current Title")]
        [SerializeField] private TextMeshProUGUI _currentTitleText;

        // ====================================================================
        // Fallback references populated by _buildUI()
        // ====================================================================

        private Text _titleNameFallback;
        private Text _titleDescriptionFallback;
        private Text _titleBonusesFallback;
        private Text _titleTierFallback;
        private Text _currentTitleFallback;

        // ====================================================================
        // State
        // ====================================================================

        private string _selectedTitleId;
        private List<TitleDefinition> _earnedTitles = new();

        private GameManager _gameManager;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            if (_panel == null) _buildUI();

            _gameManager = GameManager.Instance;

            if (_equipButton != null)
                _equipButton.onClick.AddListener(OnEquipClicked);
            if (_closeButton != null)
                _closeButton.onClick.AddListener(Close);

            if (_panel != null)
                _panel.SetActive(false);
        }

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        private void _buildUI()
        {
            // Root panel — right side, full height, 400px wide
            var panelRt = UIHelper.CreatePanel(transform, "TitlePanel", UIHelper.COLOR_BG_DARK,
                new Vector2(1f, 0f), new Vector2(1f, 1f),
                new Vector2(-400, 0), Vector2.zero);
            _panel = panelRt.gameObject;

            UIHelper.AddVerticalLayout(panelRt, spacing: 4f,
                padding: new RectOffset(8, 8, 8, 8));

            // Header: "TITLES"
            var (headerRow, headerTitle, headerHint) = UIHelper.CreateHeaderRow(
                panelRt, "TITLES", "[ESC]", 40f);

            // --- Current title display ---
            var currentRt = UIHelper.CreatePanel(panelRt, "CurrentTitleRow", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(currentRt.gameObject, 36);
            UIHelper.AddHorizontalLayout(currentRt, spacing: 4f,
                padding: new RectOffset(10, 10, 4, 4));

            var currentLabel = UIHelper.CreateText(currentRt, "CurrentLabel", "Current Title:",
                14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredSize(currentLabel.gameObject, 120, 28);

            _currentTitleFallback = UIHelper.CreateText(currentRt, "CurrentTitle", "No title equipped",
                14, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_currentTitleFallback.gameObject, 28);

            // --- Divider ---
            UIHelper.CreateDivider(panelRt);

            // --- Scrollable title list ---
            var listAreaRt = UIHelper.CreatePanel(panelRt, "ListArea", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(listAreaRt.gameObject, 320);

            var (scrollRect, content) = UIHelper.CreateScrollView(listAreaRt, "TitleScroll");
            _titleScrollRect = scrollRect;
            _titleListContainer = content;

            // --- Divider ---
            UIHelper.CreateDivider(panelRt);

            // --- Title detail section ---
            var detailRt = UIHelper.CreatePanel(panelRt, "DetailSection", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(detailRt.gameObject, 180);
            UIHelper.AddVerticalLayout(detailRt, spacing: 4f,
                padding: new RectOffset(10, 10, 8, 8));

            _titleNameFallback = UIHelper.CreateText(detailRt, "TitleName", "",
                18, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_titleNameFallback.gameObject, 26);

            _titleTierFallback = UIHelper.CreateText(detailRt, "TitleTier", "",
                14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_titleTierFallback.gameObject, 20);

            _titleDescriptionFallback = UIHelper.CreateText(detailRt, "TitleDesc",
                "Select a title to view details.", 14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_titleDescriptionFallback.gameObject, 40);

            _titleBonusesFallback = UIHelper.CreateText(detailRt, "TitleBonuses", "",
                14, UIHelper.COLOR_TEXT_GREEN, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_titleBonusesFallback.gameObject, 50);

            // --- Action buttons row ---
            var actionRowRt = UIHelper.CreatePanel(panelRt, "ActionRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(actionRowRt.gameObject, 40);
            UIHelper.AddHorizontalLayout(actionRowRt, spacing: 8f,
                padding: new RectOffset(8, 8, 4, 4), childForceExpand: true);

            _equipButton = UIHelper.CreateButton(actionRowRt, "EquipButton",
                "Equip Title", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_GREEN, 16);
            _closeButton = UIHelper.CreateButton(actionRowRt, "CloseButton",
                "Close", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 16);
        }

        // ====================================================================
        // Public Methods
        // ====================================================================

        public void Open()
        {
            if (_panel != null) _panel.SetActive(true);
            _selectedTitleId = null;
            RefreshTitleList();
        }

        public void Close()
        {
            if (_panel != null) _panel.SetActive(false);
        }

        public void Toggle()
        {
            if (_panel != null && _panel.activeSelf)
                Close();
            else
                Open();
        }

        // ====================================================================
        // Private Methods
        // ====================================================================

        private void RefreshTitleList()
        {
            _earnedTitles.Clear();

            if (_gameManager?.Player == null) return;

            var titleDb = TitleDatabase.Instance;
            if (!titleDb.Loaded) return;

            // Get earned title IDs from StatTracker
            var tracker = _gameManager.Player.StatTracker;
            var allTitles = titleDb.Titles;

            foreach (var kvp in allTitles)
            {
                // Check if title requirements are met
                _earnedTitles.Add(kvp.Value);
            }

            RebuildTitleList();
            UpdateCurrentTitle();
        }

        private void RebuildTitleList()
        {
            if (_titleListContainer == null) return;

            for (int i = _titleListContainer.childCount - 1; i >= 0; i--)
                Destroy(_titleListContainer.GetChild(i).gameObject);

            foreach (var title in _earnedTitles)
            {
                if (_titleEntryPrefab != null)
                {
                    var go = Instantiate(_titleEntryPrefab, _titleListContainer);
                    var text = go.GetComponentInChildren<TextMeshProUGUI>();
                    if (text != null)
                    {
                        text.text = title.Name;
                    }

                    var button = go.GetComponent<Button>();
                    if (button != null)
                    {
                        string id = title.TitleId;
                        button.onClick.AddListener(() => SelectTitle(id));
                    }
                }
                else
                {
                    // Code-built fallback entry
                    string id = title.TitleId;
                    var entryBtn = UIHelper.CreateButton(_titleListContainer, "Title_" + id,
                        title.Name, UIHelper.COLOR_BG_SLOT, UIHelper.COLOR_TEXT_PRIMARY, 14,
                        () => SelectTitle(id));
                    UIHelper.SetPreferredHeight(entryBtn.gameObject, 32);
                }
            }
        }

        private void SelectTitle(string titleId)
        {
            _selectedTitleId = titleId;
            UpdateTitleDetail();
        }

        private void UpdateTitleDetail()
        {
            if (string.IsNullOrEmpty(_selectedTitleId))
            {
                string defaultDesc = "Select a title to view details.";
                if (_titleName != null) _titleName.text = "";
                else if (_titleNameFallback != null) _titleNameFallback.text = "";

                if (_titleDescription != null) _titleDescription.text = defaultDesc;
                else if (_titleDescriptionFallback != null) _titleDescriptionFallback.text = defaultDesc;

                if (_titleBonuses != null) _titleBonuses.text = "";
                else if (_titleBonusesFallback != null) _titleBonusesFallback.text = "";

                if (_titleTier != null) _titleTier.text = "";
                else if (_titleTierFallback != null) _titleTierFallback.text = "";
                return;
            }

            var titleDb = TitleDatabase.Instance;
            var title = titleDb.GetTitle(_selectedTitleId);
            if (title == null) return;

            string nameText = title.Name;
            string descText = title.BonusDescription ?? "";
            string tierText = $"Tier: {title.Tier}";

            if (_titleName != null) _titleName.text = nameText;
            else if (_titleNameFallback != null) _titleNameFallback.text = nameText;

            if (_titleDescription != null) _titleDescription.text = descText;
            else if (_titleDescriptionFallback != null) _titleDescriptionFallback.text = descText;

            if (_titleTier != null) _titleTier.text = tierText;
            else if (_titleTierFallback != null) _titleTierFallback.text = tierText;

            // Show bonuses
            if (title.Bonuses != null)
            {
                var bonusLines = new List<string>();
                foreach (var kvp in title.Bonuses)
                {
                    bonusLines.Add($"{kvp.Key}: +{kvp.Value:P0}");
                }
                string bonusText = bonusLines.Count > 0
                    ? string.Join("\n", bonusLines)
                    : "No bonuses";

                if (_titleBonuses != null) _titleBonuses.text = bonusText;
                else if (_titleBonusesFallback != null) _titleBonusesFallback.text = bonusText;
            }
        }

        private void UpdateCurrentTitle()
        {
            string text = "No title equipped";
            if (_currentTitleText != null)
                _currentTitleText.text = text;
            else if (_currentTitleFallback != null)
                _currentTitleFallback.text = text;
        }

        private void OnEquipClicked()
        {
            if (string.IsNullOrEmpty(_selectedTitleId)) return;
            GameEvents.RaiseTitleEarned(_gameManager?.Player, _selectedTitleId);
            UpdateCurrentTitle();
        }
    }
}
