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

using System.Text;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Data.Databases;
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
        private Text[] _tabTexts;
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
            // Root panel — centered on screen, 600 x 550
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "EncyclopediaPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(600, 550), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);
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
            _tabTexts = new Text[6];

            // Guide
            var (guideScroll, guideContent) = UIHelper.CreateScrollView(contentAreaRt, "GuideScroll");
            _guideContent = guideScroll.gameObject;
            _tabScrollRects[0] = guideScroll;
            _tabTexts[0] = UIHelper.CreateText(guideContent, "GuideText",
                "Welcome to the Game Encyclopedia!\n\nUse tabs to browse.",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_tabTexts[0].gameObject, 400);

            // Quests
            var (questsScroll, questsContent) = UIHelper.CreateScrollView(contentAreaRt, "QuestsScroll");
            _questsContent = questsScroll.gameObject;
            _tabScrollRects[1] = questsScroll;
            _tabTexts[1] = UIHelper.CreateText(questsContent, "QuestsText",
                "Active Quests:\n(No active quests)",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_tabTexts[1].gameObject, 400);

            // Skills
            var (skillsScroll, skillsContent) = UIHelper.CreateScrollView(contentAreaRt, "SkillsScroll");
            _skillsContent = skillsScroll.gameObject;
            _tabScrollRects[2] = skillsScroll;
            _tabTexts[2] = UIHelper.CreateText(skillsContent, "SkillsText",
                "Learned Skills: 0",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_tabTexts[2].gameObject, 400);

            // Titles
            var (titlesScroll, titlesContent) = UIHelper.CreateScrollView(contentAreaRt, "TitlesScroll");
            _titlesContent = titlesScroll.gameObject;
            _tabScrollRects[3] = titlesScroll;
            _tabTexts[3] = UIHelper.CreateText(titlesContent, "TitlesText",
                "Titles:\n(Browse earned titles)",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_tabTexts[3].gameObject, 400);

            // Stats
            var (statsScroll, statsContent) = UIHelper.CreateScrollView(contentAreaRt, "StatsScroll");
            _statsContent = statsScroll.gameObject;
            _tabScrollRects[4] = statsScroll;
            _tabTexts[4] = UIHelper.CreateText(statsContent, "StatsText",
                "Level: 1\nClass: None",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_tabTexts[4].gameObject, 400);

            // Recipes
            var (recipesScroll, recipesContentTr) = UIHelper.CreateScrollView(contentAreaRt, "RecipesScroll");
            _recipesContent = recipesScroll.gameObject;
            _tabScrollRects[5] = recipesScroll;
            _tabTexts[5] = UIHelper.CreateText(recipesContentTr, "RecipesText",
                "Recipes:\n(Browse crafting recipes)",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_tabTexts[5].gameObject, 400);

            // Store the guide content text as fallback for _refreshContent
            _contentTextFallback = _tabTexts[0];

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

            int tabIndex = _activeTab switch
            {
                "guide" => 0, "quests" => 1, "skills" => 2,
                "titles" => 3, "stats" => 4, "recipes" => 5, _ => 0
            };

            string text = _activeTab switch
            {
                "guide" => _buildGuideText(),
                "quests" => "Active Quests:\n(No active quests)",
                "skills" => _buildSkillsText(gm),
                "titles" => _buildTitlesText(gm),
                "stats" => _buildStatsText(gm),
                "recipes" => _buildRecipesText(),
                _ => ""
            };

            if (_contentText != null) { _contentText.text = text; return; }
            if (_tabTexts != null && tabIndex < _tabTexts.Length && _tabTexts[tabIndex] != null)
                _tabTexts[tabIndex].text = text;
        }

        private string _buildGuideText()
        {
            return "=== GAME ENCYCLOPEDIA ===\n\n" +
                "Controls:\n" +
                "  WASD - Move\n  Mouse - Look\n  Tab - Inventory\n  I - Equipment\n" +
                "  C - Stats\n  K - Skills\n  M - Map\n  J - Encyclopedia\n" +
                "  E - Interact\n  ESC - Close menu\n  1-5 - Skill hotbar\n\n" +
                "Debug Keys:\n" +
                "  F1 - Debug Mode (infinite resources + materials)\n" +
                "  F2 - Learn All Skills\n" +
                "  F3 - Show All Titles\n  F4 - Max Level + Stats\n" +
                "  F7 - Infinite Durability\n\n" +
                "Crafting:\n" +
                "  Interact (E) with a crafting station to begin\n" +
                "  5 disciplines: Smithing, Alchemy, Refining, Engineering, Enchanting\n\n" +
                "Progression:\n" +
                "  Gather resources to gain materials and XP\n" +
                "  Level up to earn stat points (STR/DEF/VIT/LCK/AGI/INT)\n" +
                "  Learn skills, earn titles, craft equipment\n\n" +
                "Tier System:\n" +
                "  T1 (1.0x) - Common\n  T2 (2.0x) - Uncommon\n" +
                "  T3 (4.0x) - Rare\n  T4 (8.0x) - Legendary";
        }

        private string _buildSkillsText(GameManager gm)
        {
            var sb = new StringBuilder();
            var skillDb = SkillDatabase.Instance;
            if (skillDb == null || !skillDb.Loaded)
            {
                sb.AppendLine("Skills: (database not loaded)");
                return sb.ToString();
            }

            var known = gm?.Player?.Skills?.KnownSkills;
            int knownCount = known?.Count ?? 0;
            sb.AppendLine($"=== SKILLS REFERENCE ({skillDb.Skills.Count} total, {knownCount} learned) ===");
            sb.AppendLine();

            // Group by tier (matches Python renderer.py _render_skills_content)
            for (int tier = 1; tier <= 4; tier++)
            {
                bool headerShown = false;
                foreach (var kvp in skillDb.Skills)
                {
                    var def = kvp.Value;
                    if (def == null || def.Tier != tier) continue;

                    if (!headerShown)
                    {
                        sb.AppendLine($"--- TIER {tier} ---");
                        headerShown = true;
                    }

                    bool isKnown = known != null && known.ContainsKey(kvp.Key);
                    string status = isKnown ? "[KNOWN]" : "";
                    string tags = def.Tags != null ? string.Join(", ", def.Tags) : "";
                    string mana = def.Cost?.ManaCostRaw?.ToString() ?? "?";
                    sb.AppendLine($"  {def.Name} {status} (Mana: {mana}) [{tags}]");
                    if (!string.IsNullOrEmpty(def.Description))
                        sb.AppendLine($"    {def.Description}");
                }
                if (headerShown) sb.AppendLine();
            }

            return sb.ToString();
        }

        private string _buildTitlesText(GameManager gm)
        {
            var sb = new StringBuilder();
            var titleDb = TitleDatabase.Instance;
            if (titleDb == null || !titleDb.Loaded)
            {
                sb.AppendLine("Titles: (none loaded)");
                return sb.ToString();
            }

            int total = titleDb.Titles.Count;
            sb.AppendLine($"Titles Database: {total} titles\n");

            foreach (var kvp in titleDb.Titles)
            {
                var t = kvp.Value;
                string bonusDesc = !string.IsNullOrEmpty(t.BonusDescription) ? $" - {t.BonusDescription}" : "";
                sb.AppendLine($"  [{t.Tier}] {t.Name}{bonusDesc}");
            }

            return sb.ToString();
        }

        private string _buildStatsText(GameManager gm)
        {
            var sb = new StringBuilder();
            if (gm?.Player == null)
            {
                sb.AppendLine("Level: 1\nClass: None");
                return sb.ToString();
            }

            var p = gm.Player;
            var s = p.Stats;
            var l = p.Leveling;

            sb.AppendLine($"Level: {l.Level} | Class: {p.ClassId ?? "None"}");
            sb.AppendLine($"HP: {s.CurrentHealth:F0}/{s.MaxHealth:F0}");
            sb.AppendLine($"Mana: {s.CurrentMana:F0}/{s.MaxMana:F0}");
            sb.AppendLine($"Unallocated Points: {l.UnallocatedStatPoints}");
            sb.AppendLine();
            sb.AppendLine($"STR: {s.Strength}  (+{s.Strength * GameConfig.StrDamagePerPoint * 100:F0}% dmg)");
            sb.AppendLine($"DEF: {s.Defense}  (+{s.Defense * GameConfig.DefReductionPerPoint * 100:F0}% red)");
            sb.AppendLine($"VIT: {s.Vitality}  (+{s.Vitality * GameConfig.VitHpPerPoint} HP)");
            sb.AppendLine($"LCK: {s.Luck}  (+{s.Luck * GameConfig.LckCritPerPoint * 100:F0}% crit)");
            sb.AppendLine($"AGI: {s.Agility}  (+{s.Agility * GameConfig.AgiForestryPerPoint * 100:F0}% forestry)");
            sb.AppendLine($"INT: {s.Intelligence}  (-{s.Intelligence * GameConfig.IntDifficultyPerPoint * 100:F0}% diff)");

            return sb.ToString();
        }

        private string _buildRecipesText()
        {
            var sb = new StringBuilder();
            var recipeDb = RecipeDatabase.Instance;
            if (recipeDb == null)
            {
                sb.AppendLine("Recipes: (none loaded)");
                return sb.ToString();
            }

            string[] disciplines = { "smithing", "alchemy", "refining", "engineering", "enchanting" };
            foreach (string disc in disciplines)
            {
                sb.AppendLine($"\n=== {disc.ToUpper()} ===");
                for (int tier = 1; tier <= 4; tier++)
                {
                    var recipes = recipeDb.GetRecipesForStation(disc, tier);
                    if (recipes == null || recipes.Count == 0) continue;
                    foreach (var r in recipes)
                    {
                        string inputStr = "";
                        if (r.Inputs != null)
                        {
                            var parts = new System.Collections.Generic.List<string>();
                            foreach (var inp in r.Inputs)
                                parts.Add($"{inp.MaterialId} x{inp.Quantity}");
                            inputStr = string.Join(", ", parts);
                        }
                        sb.AppendLine($"  T{tier}: {r.OutputId} x{r.OutputQty} [{inputStr}]");
                    }
                }
            }

            return sb.ToString();
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
