// ============================================================================
// Game1.Unity.UI.EncyclopediaUI
// Migrated from: rendering/renderer.py (lines 2690-3933: encyclopedia + tabs)
// Migration phase: 6
// Date: 2026-02-13
//
// Tabbed encyclopedia browser: Guide, Quests, Skills, Titles, Stats, Recipes.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.Core;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Encyclopedia panel with 6 tabs: Guide, Quests, Skills, Titles, Stats, Recipes.
    /// </summary>
    public class EncyclopediaUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Tab Buttons")]
        [SerializeField] private Button _guideTab;
        [SerializeField] private Button _questsTab;
        [SerializeField] private Button _skillsTab;
        [SerializeField] private Button _titlesTab;
        [SerializeField] private Button _statsTab;
        [SerializeField] private Button _recipesTab;

        [Header("Content Panels")]
        [SerializeField] private GameObject _guideContent;
        [SerializeField] private GameObject _questsContent;
        [SerializeField] private GameObject _skillsContent;
        [SerializeField] private GameObject _titlesContent;
        [SerializeField] private GameObject _statsContent;
        [SerializeField] private GameObject _recipesContent;

        [Header("Tab Content Text")]
        [SerializeField] private TextMeshProUGUI _contentText;
        [SerializeField] private ScrollRect _contentScroll;

        private string _activeTab = "guide";
        private GameStateManager _stateManager;
        private InputManager _inputManager;
        private GameObject[] _allPanels;

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
            _inputManager = FindFirstObjectByType<InputManager>();

            if (_inputManager != null) _inputManager.OnToggleEncyclopedia += _onToggle;
            if (_stateManager != null) _stateManager.OnStateChanged += _onStateChanged;

            _allPanels = new[] { _guideContent, _questsContent, _skillsContent, _titlesContent, _statsContent, _recipesContent };

            if (_guideTab != null) _guideTab.onClick.AddListener(() => _switchTab("guide"));
            if (_questsTab != null) _questsTab.onClick.AddListener(() => _switchTab("quests"));
            if (_skillsTab != null) _skillsTab.onClick.AddListener(() => _switchTab("skills"));
            if (_titlesTab != null) _titlesTab.onClick.AddListener(() => _switchTab("titles"));
            if (_statsTab != null) _statsTab.onClick.AddListener(() => _switchTab("stats"));
            if (_recipesTab != null) _recipesTab.onClick.AddListener(() => _switchTab("recipes"));

            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_inputManager != null) _inputManager.OnToggleEncyclopedia -= _onToggle;
            if (_stateManager != null) _stateManager.OnStateChanged -= _onStateChanged;
        }

        private void _switchTab(string tabName)
        {
            _activeTab = tabName;

            // Hide all content panels
            foreach (var panel in _allPanels)
                if (panel != null) panel.SetActive(false);

            // Show selected tab
            switch (tabName)
            {
                case "guide": if (_guideContent != null) _guideContent.SetActive(true); break;
                case "quests": if (_questsContent != null) _questsContent.SetActive(true); break;
                case "skills": if (_skillsContent != null) _skillsContent.SetActive(true); break;
                case "titles": if (_titlesContent != null) _titlesContent.SetActive(true); break;
                case "stats": if (_statsContent != null) _statsContent.SetActive(true); break;
                case "recipes": if (_recipesContent != null) _recipesContent.SetActive(true); break;
            }

            _refreshContent();
        }

        private void _refreshContent()
        {
            // Content is populated by sub-components on each tab panel
            // Or a shared content text can be used
            if (_contentText == null) return;

            var gm = GameManager.Instance;
            if (gm?.Player == null) return;

            _contentText.text = _activeTab switch
            {
                "guide" => "Welcome to the Game Encyclopedia!\n\nUse tabs to browse.",
                "quests" => "Active Quests:\n(No active quests)",
                "skills" => $"Learned Skills: {gm.Player.Skills.LearnedSkillCount}",
                "titles" => "Titles:\n(Browse earned titles)",
                "stats" => $"Level: {gm.Player.Leveling.Level}\nClass: {gm.Player.ClassId}",
                "recipes" => "Recipes:\n(Browse crafting recipes)",
                _ => ""
            };
        }

        private void _onToggle() => _stateManager?.TogglePanel(GameState.EncyclopediaOpen);
        private void _onStateChanged(GameState old, GameState next)
        {
            _setVisible(next == GameState.EncyclopediaOpen);
            if (next == GameState.EncyclopediaOpen) _refreshContent();
        }
        private void _setVisible(bool v) { if (_panel != null) _panel.SetActive(v); }
    }
}
