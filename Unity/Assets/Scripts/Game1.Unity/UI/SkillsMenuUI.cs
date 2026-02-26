// ============================================================================
// Game1.Unity.UI.SkillsMenuUI
// Migrated from: core/game_engine.py (skill browsing/equipping sections)
// Migration phase: 6
// Date: 2026-02-21
//
// Skills browsing and equipping UI panel.
// Self-building: if _panel is null at Start, _buildUI() constructs the full
// UI hierarchy programmatically via UIHelper.
// ============================================================================

using System.Collections.Generic;
using System.Linq;
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
    /// Skills menu UI — browse available skills, equip to skill bar, view details.
    /// Accessible via K key binding.
    /// </summary>
    public class SkillsMenuUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Skill List")]
        [SerializeField] private Transform _skillListContainer;
        [SerializeField] private GameObject _skillEntryPrefab;
        [SerializeField] private ScrollRect _skillScrollRect;

        [Header("Skill Detail")]
        [SerializeField] private TextMeshProUGUI _skillName;
        [SerializeField] private TextMeshProUGUI _skillDescription;
        [SerializeField] private TextMeshProUGUI _skillManaCost;
        [SerializeField] private TextMeshProUGUI _skillCooldown;
        [SerializeField] private TextMeshProUGUI _skillTags;
        [SerializeField] private TextMeshProUGUI _skillRequirements;

        [Header("Actions")]
        [SerializeField] private Button _equipButton;
        [SerializeField] private Button _unequipButton;
        [SerializeField] private Button _closeButton;

        [Header("Skill Bar Slots")]
        [SerializeField] private List<Button> _skillBarSlots;

        [Header("Filters")]
        [SerializeField] private TMP_Dropdown _categoryFilter;

        // ====================================================================
        // Fallback references populated by _buildUI()
        // ====================================================================

        private Text _skillNameFallback;
        private Text _skillDescriptionFallback;
        private Text _skillManaCostFallback;
        private Text _skillCooldownFallback;
        private Text _skillTagsFallback;
        private Text _skillRequirementsFallback;
        private Button[] _filterTabs;

        // ====================================================================
        // State
        // ====================================================================

        private string _selectedSkillId;
        private List<SkillDefinition> _displayedSkills = new();
        private int _selectedBarSlot = -1;
        private string _currentFilter = "all";

        private GameManager _gameManager;
        private GameStateManager _stateManager;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private InputManager _inputManager;

        private void Start()
        {
            if (_panel == null) _buildUI();

            _gameManager = GameManager.Instance;
            _stateManager = FindFirstObjectByType<GameStateManager>();
            _inputManager = FindFirstObjectByType<InputManager>();

            if (_inputManager != null)
                _inputManager.OnToggleSkills += _onToggle;

            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            if (_equipButton != null)
                _equipButton.onClick.AddListener(OnEquipClicked);
            if (_unequipButton != null)
                _unequipButton.onClick.AddListener(OnUnequipClicked);
            if (_closeButton != null)
                _closeButton.onClick.AddListener(Close);
            if (_categoryFilter != null)
                _categoryFilter.onValueChanged.AddListener(OnFilterChanged);

            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_inputManager != null)
                _inputManager.OnToggleSkills -= _onToggle;
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onStateChanged;
        }

        private void _onToggle()
        {
            _stateManager?.TogglePanel(GameState.SkillsOpen);
        }

        private void _onStateChanged(GameState oldState, GameState newState)
        {
            bool show = newState == GameState.SkillsOpen;
            _setVisible(show);
            if (show) RefreshSkillList();
        }

        private void _setVisible(bool visible)
        {
            if (_panel != null) _panel.SetActive(visible);
        }

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        private void _buildUI()
        {
            // Root panel — right side, full height, 420px wide
            var panelRt = UIHelper.CreatePanel(transform, "SkillsPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(1f, 0f), new Vector2(1f, 1f),
                new Vector2(-420, 0), Vector2.zero);
            _panel = panelRt.gameObject;

            UIHelper.AddVerticalLayout(panelRt, spacing: 4f,
                padding: new RectOffset(8, 8, 8, 8));

            // Header: "SKILLS [K/ESC]"
            var (headerRow, headerTitle, headerHint) = UIHelper.CreateHeaderRow(
                panelRt, "SKILLS", "[K/ESC]", 40f);

            // --- Hotbar slots row (5 slots) ---
            var hotbarRowRt = UIHelper.CreatePanel(panelRt, "HotbarRow", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(hotbarRowRt.gameObject, 60);
            UIHelper.AddHorizontalLayout(hotbarRowRt, spacing: 6f,
                padding: new RectOffset(8, 8, 6, 6), childForceExpand: true);

            _skillBarSlots = new List<Button>();
            for (int i = 0; i < 5; i++)
            {
                int slotIndex = i;
                var slotBtn = UIHelper.CreateButton(hotbarRowRt, $"HotbarSlot_{i}",
                    $"{i + 1}", UIHelper.COLOR_BG_SLOT, UIHelper.COLOR_TEXT_SECONDARY, 14,
                    () => { _selectedBarSlot = slotIndex; });
                _skillBarSlots.Add(slotBtn);
            }

            // --- Filter tabs row: All / Combat / Buff / Heal / Utility ---
            var (tabBarRt, tabs) = UIHelper.CreateTabBar(panelRt,
                new[] { "All", "Combat", "Buff", "Heal", "Utility" }, 32f);
            _filterTabs = tabs;

            for (int i = 0; i < tabs.Length; i++)
            {
                int idx = i;
                tabs[i].onClick.AddListener(() => OnFilterChanged(idx));
            }

            // --- Scrollable skill list ---
            var listAreaRt = UIHelper.CreatePanel(panelRt, "ListArea", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(listAreaRt.gameObject, 300);

            var (scrollRect, content) = UIHelper.CreateScrollView(listAreaRt, "SkillScroll");
            _skillScrollRect = scrollRect;
            _skillListContainer = content;

            // --- Divider ---
            UIHelper.CreateDivider(panelRt);

            // --- Skill detail section ---
            var detailRt = UIHelper.CreatePanel(panelRt, "DetailSection", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(detailRt.gameObject, 200);
            UIHelper.AddVerticalLayout(detailRt, spacing: 4f,
                padding: new RectOffset(10, 10, 8, 8));

            _skillNameFallback = UIHelper.CreateText(detailRt, "SkillName", "",
                18, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_skillNameFallback.gameObject, 26);

            _skillDescriptionFallback = UIHelper.CreateText(detailRt, "SkillDesc",
                "Select a skill to view details.", 14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_skillDescriptionFallback.gameObject, 40);

            _skillManaCostFallback = UIHelper.CreateText(detailRt, "ManaCost", "",
                14, UIHelper.COLOR_MANA, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_skillManaCostFallback.gameObject, 20);

            _skillCooldownFallback = UIHelper.CreateText(detailRt, "Cooldown", "",
                14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_skillCooldownFallback.gameObject, 20);

            _skillTagsFallback = UIHelper.CreateText(detailRt, "Tags", "",
                13, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_skillTagsFallback.gameObject, 20);

            _skillRequirementsFallback = UIHelper.CreateText(detailRt, "Requirements", "",
                13, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_skillRequirementsFallback.gameObject, 20);

            // --- Action buttons row ---
            var actionRowRt = UIHelper.CreatePanel(panelRt, "ActionRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(actionRowRt.gameObject, 40);
            UIHelper.AddHorizontalLayout(actionRowRt, spacing: 8f,
                padding: new RectOffset(8, 8, 4, 4), childForceExpand: true);

            _equipButton = UIHelper.CreateButton(actionRowRt, "EquipButton",
                "Equip", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_GREEN, 16);
            _unequipButton = UIHelper.CreateButton(actionRowRt, "UnequipButton",
                "Unequip", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_RED, 16);
            _closeButton = UIHelper.CreateButton(actionRowRt, "CloseButton",
                "Close", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 16);
        }

        // ====================================================================
        // Public Methods
        // ====================================================================

        public void Open()
        {
            if (_panel != null) _panel.SetActive(true);
            _selectedSkillId = null;
            RefreshSkillList();
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

        private void RefreshSkillList()
        {
            _displayedSkills.Clear();

            if (_gameManager?.Player == null) return;

            var skillManager = _gameManager.Player.Skills;
            var skillDb = SkillDatabase.Instance;
            if (!skillDb.Loaded) return;

            // Get learned skills
            var learnedSkillIds = skillManager.KnownSkills.Keys;
            foreach (var skillId in learnedSkillIds)
            {
                var skillDef = skillDb.GetSkill(skillId);
                if (skillDef != null)
                {
                    // Apply filter
                    if (_currentFilter != "all" && !MatchesFilter(skillDef, _currentFilter))
                        continue;

                    _displayedSkills.Add(skillDef);
                }
            }

            RebuildSkillList();
        }

        private void RebuildSkillList()
        {
            if (_skillListContainer == null) return;

            // Clear
            for (int i = _skillListContainer.childCount - 1; i >= 0; i--)
                Destroy(_skillListContainer.GetChild(i).gameObject);

            // Create entries
            foreach (var skill in _displayedSkills)
            {
                if (_skillEntryPrefab != null)
                {
                    var go = Instantiate(_skillEntryPrefab, _skillListContainer);
                    var text = go.GetComponentInChildren<TextMeshProUGUI>();
                    if (text != null)
                    {
                        text.text = skill.Name;
                    }

                    var button = go.GetComponent<Button>();
                    if (button != null)
                    {
                        string id = skill.SkillId;
                        button.onClick.AddListener(() => SelectSkill(id));
                    }
                }
                else
                {
                    // Code-built fallback entry
                    string id = skill.SkillId;
                    var entryBtn = UIHelper.CreateButton(_skillListContainer, "Skill_" + id,
                        skill.Name, UIHelper.COLOR_BG_SLOT, UIHelper.COLOR_TEXT_PRIMARY, 14,
                        () => SelectSkill(id));
                    UIHelper.SetPreferredHeight(entryBtn.gameObject, 32);
                }
            }
        }

        private void SelectSkill(string skillId)
        {
            _selectedSkillId = skillId;
            UpdateSkillDetail();
        }

        private void UpdateSkillDetail()
        {
            if (string.IsNullOrEmpty(_selectedSkillId))
            {
                ClearDetail();
                return;
            }

            var skillDb = SkillDatabase.Instance;
            var skillDef = skillDb.GetSkill(_selectedSkillId);
            if (skillDef == null)
            {
                ClearDetail();
                return;
            }

            string nameText = skillDef.Name;
            string descText = skillDef.Description ?? "";
            string manaText = $"Mana: {skillDef.Cost.ManaCostRaw}";
            string cdText = $"Cooldown: {skillDef.Cost.CooldownRaw}";
            string tagsText = skillDef.Tags != null ? $"Tags: {string.Join(", ", skillDef.Tags)}" : "";

            if (_skillName != null) _skillName.text = nameText;
            else if (_skillNameFallback != null) _skillNameFallback.text = nameText;

            if (_skillDescription != null) _skillDescription.text = descText;
            else if (_skillDescriptionFallback != null) _skillDescriptionFallback.text = descText;

            if (_skillManaCost != null) _skillManaCost.text = manaText;
            else if (_skillManaCostFallback != null) _skillManaCostFallback.text = manaText;

            if (_skillCooldown != null) _skillCooldown.text = cdText;
            else if (_skillCooldownFallback != null) _skillCooldownFallback.text = cdText;

            if (_skillTags != null) _skillTags.text = tagsText;
            else if (_skillTagsFallback != null) _skillTagsFallback.text = tagsText;

            // Show equip/unequip based on current state
            bool isEquipped = _gameManager?.Player?.Skills?.GetKnownSkill(_selectedSkillId)?.IsEquipped ?? false;
            if (_equipButton != null) _equipButton.gameObject.SetActive(!isEquipped);
            if (_unequipButton != null) _unequipButton.gameObject.SetActive(isEquipped);
        }

        private void ClearDetail()
        {
            if (_skillName != null) _skillName.text = "";
            else if (_skillNameFallback != null) _skillNameFallback.text = "";

            string defaultDesc = "Select a skill to view details.";
            if (_skillDescription != null) _skillDescription.text = defaultDesc;
            else if (_skillDescriptionFallback != null) _skillDescriptionFallback.text = defaultDesc;

            if (_skillManaCost != null) _skillManaCost.text = "";
            else if (_skillManaCostFallback != null) _skillManaCostFallback.text = "";

            if (_skillCooldown != null) _skillCooldown.text = "";
            else if (_skillCooldownFallback != null) _skillCooldownFallback.text = "";

            if (_skillTags != null) _skillTags.text = "";
            else if (_skillTagsFallback != null) _skillTagsFallback.text = "";

            if (_skillRequirements != null) _skillRequirements.text = "";
            else if (_skillRequirementsFallback != null) _skillRequirementsFallback.text = "";
        }

        private void OnEquipClicked()
        {
            if (string.IsNullOrEmpty(_selectedSkillId)) return;
            if (_gameManager?.Player == null) return;

            _gameManager.Player.Skills.EquipSkill(_selectedSkillId, _selectedBarSlot >= 0 ? _selectedBarSlot : 0);
            UpdateSkillDetail();
        }

        private void OnUnequipClicked()
        {
            if (string.IsNullOrEmpty(_selectedSkillId)) return;
            if (_gameManager?.Player == null) return;

            _gameManager.Player.Skills.UnequipSkill(_selectedSkillId);
            UpdateSkillDetail();
        }

        private void OnFilterChanged(int index)
        {
            _currentFilter = index switch
            {
                0 => "all",
                1 => "combat",
                2 => "buff",
                3 => "heal",
                4 => "utility",
                _ => "all",
            };
            RefreshSkillList();
        }

        private bool MatchesFilter(SkillDefinition skill, string filter)
        {
            if (skill.Tags == null || skill.Tags.Count == 0) return filter == "utility";

            return filter switch
            {
                "combat" => skill.Tags.Any(t =>
                    t == "melee" || t == "ranged" || t == "fire" || t == "ice"
                    || t == "lightning" || t == "physical"),
                "buff" => skill.Tags.Any(t =>
                    t == "empower" || t == "fortify" || t == "quicken" || t == "buff"),
                "heal" => skill.Tags.Any(t => t == "heal" || t == "restore" || t == "regenerate"),
                "utility" => !skill.Tags.Any(t =>
                    t == "melee" || t == "ranged" || t == "fire" || t == "ice"
                    || t == "heal" || t == "empower"),
                _ => true,
            };
        }
    }
}
