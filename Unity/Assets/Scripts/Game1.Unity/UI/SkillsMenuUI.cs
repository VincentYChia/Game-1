// ============================================================================
// Game1.Unity.UI.SkillsMenuUI
// Migrated from: core/game_engine.py (skill browsing/equipping sections)
// Migration phase: 6
// Date: 2026-02-21
//
// Skills browsing and equipping UI panel.
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

        private void Start()
        {
            _gameManager = GameManager.Instance;
            _stateManager = FindFirstObjectByType<GameStateManager>();

            if (_equipButton != null)
                _equipButton.onClick.AddListener(OnEquipClicked);
            if (_unequipButton != null)
                _unequipButton.onClick.AddListener(OnUnequipClicked);
            if (_closeButton != null)
                _closeButton.onClick.AddListener(Close);
            if (_categoryFilter != null)
                _categoryFilter.onValueChanged.AddListener(OnFilterChanged);

            if (_panel != null)
                _panel.SetActive(false);
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
                if (_skillEntryPrefab == null) continue;

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

            if (_skillName != null) _skillName.text = skillDef.Name;
            if (_skillDescription != null) _skillDescription.text = skillDef.Description ?? "";
            if (_skillManaCost != null) _skillManaCost.text = $"Mana: {skillDef.Cost.ManaCostRaw}";
            if (_skillCooldown != null) _skillCooldown.text = $"Cooldown: {skillDef.Cost.CooldownRaw}";
            if (_skillTags != null && skillDef.Tags != null)
                _skillTags.text = $"Tags: {string.Join(", ", skillDef.Tags)}";

            // Show equip/unequip based on current state
            bool isEquipped = _gameManager?.Player?.Skills?.GetKnownSkill(_selectedSkillId)?.IsEquipped ?? false;
            if (_equipButton != null) _equipButton.gameObject.SetActive(!isEquipped);
            if (_unequipButton != null) _unequipButton.gameObject.SetActive(isEquipped);
        }

        private void ClearDetail()
        {
            if (_skillName != null) _skillName.text = "";
            if (_skillDescription != null) _skillDescription.text = "Select a skill to view details.";
            if (_skillManaCost != null) _skillManaCost.text = "";
            if (_skillCooldown != null) _skillCooldown.text = "";
            if (_skillTags != null) _skillTags.text = "";
            if (_skillRequirements != null) _skillRequirements.text = "";
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
