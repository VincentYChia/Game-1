// ============================================================================
// Game1.Unity.UI.TitleUI
// Migrated from: core/game_engine.py (title display sections)
// Migration phase: 6
// Date: 2026-02-21
//
// Title browsing and selection UI panel.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Data.Databases;
using Game1.Data.Models;
using Game1.Unity.Core;

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
            _gameManager = GameManager.Instance;

            if (_equipButton != null)
                _equipButton.onClick.AddListener(OnEquipClicked);
            if (_closeButton != null)
                _closeButton.onClick.AddListener(Close);

            if (_panel != null)
                _panel.SetActive(false);
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
                if (_titleEntryPrefab == null) continue;

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
                if (_titleName != null) _titleName.text = "";
                if (_titleDescription != null) _titleDescription.text = "Select a title to view details.";
                if (_titleBonuses != null) _titleBonuses.text = "";
                if (_titleTier != null) _titleTier.text = "";
                return;
            }

            var titleDb = TitleDatabase.Instance;
            var title = titleDb.GetTitle(_selectedTitleId);
            if (title == null) return;

            if (_titleName != null) _titleName.text = title.Name;
            if (_titleDescription != null) _titleDescription.text = title.BonusDescription ?? "";
            if (_titleTier != null) _titleTier.text = $"Tier: {title.Tier}";

            // Show bonuses
            if (_titleBonuses != null && title.Bonuses != null)
            {
                var bonusLines = new List<string>();
                foreach (var kvp in title.Bonuses)
                {
                    bonusLines.Add($"{kvp.Key}: +{kvp.Value:P0}");
                }
                _titleBonuses.text = bonusLines.Count > 0
                    ? string.Join("\n", bonusLines)
                    : "No bonuses";
            }
        }

        private void UpdateCurrentTitle()
        {
            if (_currentTitleText != null)
            {
                _currentTitleText.text = "No title equipped";
            }
        }

        private void OnEquipClicked()
        {
            if (string.IsNullOrEmpty(_selectedTitleId)) return;
            GameEvents.RaiseTitleEarned(_gameManager?.Player, _selectedTitleId);
            UpdateCurrentTitle();
        }
    }
}
