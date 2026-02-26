// ============================================================================
// Game1.Unity.UI.EncyclopediaUI
// Migrated from: rendering/renderer.py (lines 2690-3933: encyclopedia + tabs)
// Migration phase: 6
// Date: 2026-02-13
//
// Tabbed encyclopedia browser: Guide, Quests, Skills, Titles, Stats, Recipes.
// Self-building: if _panel is null at Start, _buildUI() constructs the full
// UI hierarchy programmatically via UIHelper.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

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

        // ====================================================================
        // Fallback references populated by _buildUI()
        // ====================================================================

        private Text _contentTextFallback;
        private ScrollRect[] _tabScrollRects;

        // ====================================================================
        // State
        // ====================================================================

        private string _activeTab = "guide";
        private GameStateManager _stateManager;
        private InputManager _inputManager;
        private GameObject[] _allPanels;

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
            _inputManager = InputManager.Instance ?? FindFirstObjectByType<InputManager>();

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

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        private void _buildUI()
        {
            // Root panel — right side, full height, 500px wide
            var panelRt = UIHelper.CreatePanel(transform, "EncyclopediaPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(1f, 0f), new Vector2(1f, 1f),
                new Vector2(-500, 0), Vector2.zero);
            _panel = panelRt.gameObject;

            UIHelper.AddVerticalLayout(panelRt, spacing: 4f,
                padding: new RectOffset(8, 8, 8, 8));

            // Header: "ENCYCLOPEDIA"
            var (headerRow, headerTitle, headerHint) = UIHelper.CreateHeaderRow(
                panelRt, "ENCYCLOPEDIA", "[E/ESC]", 40f);

            // --- Tab bar: Guide / Quests / Skills / Titles / Stats / Recipes ---
            var tabNames = new[] { "Guide", "Quests", "Skills", "Titles", "Stats", "Recipes" };
            var (tabBarRt, tabs) = UIHelper.CreateTabBar(panelRt, tabNames, 36f);

            _guideTab = tabs[0];
            _questsTab = tabs[1];
            _skillsTab = tabs[2];
            _titlesTab = tabs[3];
            _statsTab = tabs[4];
            _recipesTab = tabs[5];

            // --- Content area: one scroll view per tab, stacked ---
            var contentAreaRt = UIHelper.CreatePanel(panelRt, "ContentArea", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            // Let layout expand to fill remaining space
            var contentLe = contentAreaRt.gameObject.AddComponent<LayoutElement>();
            contentLe.flexibleHeight = 1f;

            // Create a scrollable content panel for each tab
            _tabScrollRects = new ScrollRect[6];

            // Guide
            var (guideScroll, guideContent) = UIHelper.CreateScrollView(contentAreaRt, "GuideScroll");
            _guideContent = guideScroll.gameObject;
            _tabScrollRects[0] = guideScroll;
            var guideText = UIHelper.CreateText(guideContent, "GuideText",
                "Welcome to the Game Encyclopedia!\n\nUse tabs to browse.",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(guideText.gameObject, 400);

            // Quests
            var (questsScroll, questsContent) = UIHelper.CreateScrollView(contentAreaRt, "QuestsScroll");
            _questsContent = questsScroll.gameObject;
            _tabScrollRects[1] = questsScroll;
            var questsText = UIHelper.CreateText(questsContent, "QuestsText",
                "Active Quests:\n(No active quests)",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(questsText.gameObject, 400);

            // Skills
            var (skillsScroll, skillsContent) = UIHelper.CreateScrollView(contentAreaRt, "SkillsScroll");
            _skillsContent = skillsScroll.gameObject;
            _tabScrollRects[2] = skillsScroll;
            var skillsText = UIHelper.CreateText(skillsContent, "SkillsText",
                "Learned Skills: 0",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(skillsText.gameObject, 400);

            // Titles
            var (titlesScroll, titlesContent) = UIHelper.CreateScrollView(contentAreaRt, "TitlesScroll");
            _titlesContent = titlesScroll.gameObject;
            _tabScrollRects[3] = titlesScroll;
            var titlesText = UIHelper.CreateText(titlesContent, "TitlesText",
                "Titles:\n(Browse earned titles)",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(titlesText.gameObject, 400);

            // Stats
            var (statsScroll, statsContent) = UIHelper.CreateScrollView(contentAreaRt, "StatsScroll");
            _statsContent = statsScroll.gameObject;
            _tabScrollRects[4] = statsScroll;
            var statsText = UIHelper.CreateText(statsContent, "StatsText",
                "Level: 1\nClass: None",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(statsText.gameObject, 400);

            // Recipes
            var (recipesScroll, recipesContentTr) = UIHelper.CreateScrollView(contentAreaRt, "RecipesScroll");
            _recipesContent = recipesScroll.gameObject;
            _tabScrollRects[5] = recipesScroll;
            var recipesText = UIHelper.CreateText(recipesContentTr, "RecipesText",
                "Recipes:\n(Browse crafting recipes)",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(recipesText.gameObject, 400);

            // Store the guide content text as fallback for _refreshContent
            _contentTextFallback = guideText;

            // Initially show guide tab only
            _questsContent.SetActive(false);
            _skillsContent.SetActive(false);
            _titlesContent.SetActive(false);
            _statsContent.SetActive(false);
            _recipesContent.SetActive(false);
        }

        // ====================================================================
        // Tab Switching
        // ====================================================================

        private void _switchTab(string tabName)
        {
            _activeTab = tabName;

            // Hide all content panels
            if (_allPanels != null)
            {
                foreach (var panel in _allPanels)
                    if (panel != null) panel.SetActive(false);
            }

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
            var gm = GameManager.Instance;
            if (gm?.Player == null) return;

            string text = _activeTab switch
            {
                "guide" => "Welcome to the Game Encyclopedia!\n\nUse tabs to browse.",
                "quests" => "Active Quests:\n(No active quests)",
                "skills" => $"Learned Skills: {gm.Player.Skills.KnownSkills.Count}",
                "titles" => "Titles:\n(Browse earned titles)",
                "stats" => $"Level: {gm.Player.Leveling.Level}\nClass: {gm.Player.ClassId}",
                "recipes" => "Recipes:\n(Browse crafting recipes)",
                _ => ""
            };

            // Update whichever text reference is available
            if (_contentText != null)
                _contentText.text = text;
            else if (_contentTextFallback != null)
                _contentTextFallback.text = text;
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
