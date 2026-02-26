// ============================================================================
// Game1.Unity.UI.SkillUnlockUI
// Migrated from: core/game_engine.py (skill unlock display sections)
// Migration phase: 6
// Date: 2026-02-21
//
// Displays skill unlock requirements and allows unlocking.
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
    /// Skill unlock UI — shows requirements for locked skills and allows unlocking
    /// when requirements are met.
    /// </summary>
    public class SkillUnlockUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Skill Info")]
        [SerializeField] private TextMeshProUGUI _skillName;
        [SerializeField] private TextMeshProUGUI _skillDescription;

        [Header("Requirements")]
        [SerializeField] private Transform _requirementsContainer;
        [SerializeField] private GameObject _requirementEntryPrefab;

        [Header("Actions")]
        [SerializeField] private Button _unlockButton;
        [SerializeField] private Button _closeButton;

        [Header("Status")]
        [SerializeField] private TextMeshProUGUI _statusText;

        // ====================================================================
        // Fallback references populated by _buildUI()
        // ====================================================================

        private Text _skillNameFallback;
        private Text _skillDescriptionFallback;
        private Text _statusTextFallback;

        // ====================================================================
        // State
        // ====================================================================

        private string _skillId;
        private GameManager _gameManager;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            if (_panel == null) _buildUI();

            _gameManager = GameManager.Instance;

            if (_unlockButton != null)
                _unlockButton.onClick.AddListener(OnUnlockClicked);
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
            // Root panel — centered on screen, 400 x 480
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "SkillUnlockPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(400, 480), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);
            _panel = panelRt.gameObject;

            UIHelper.AddVerticalLayout(panelRt, spacing: 6f,
                padding: new RectOffset(10, 10, 10, 10));

            // Header: "SKILL UNLOCK"
            var (headerRow, headerTitle, headerHint) = UIHelper.CreateHeaderRow(
                panelRt, "SKILL UNLOCK", "[ESC]", 40f);

            // --- Skill name ---
            _skillNameFallback = UIHelper.CreateText(panelRt, "SkillName", "",
                20, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_skillNameFallback.gameObject, 32);

            // --- Skill description ---
            _skillDescriptionFallback = UIHelper.CreateText(panelRt, "SkillDesc", "",
                14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_skillDescriptionFallback.gameObject, 50);

            // --- Divider ---
            UIHelper.CreateDivider(panelRt);

            // --- Requirements header ---
            var reqHeaderText = UIHelper.CreateText(panelRt, "ReqHeader", "Requirements:",
                16, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(reqHeaderText.gameObject, 24);

            // --- Scrollable requirements list ---
            var reqAreaRt = UIHelper.CreatePanel(panelRt, "ReqArea", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(reqAreaRt.gameObject, 200);

            var (scrollRect, content) = UIHelper.CreateScrollView(reqAreaRt, "ReqScroll");
            _requirementsContainer = content;

            // --- Divider ---
            UIHelper.CreateDivider(panelRt);

            // --- Status text ---
            _statusTextFallback = UIHelper.CreateText(panelRt, "StatusText", "",
                15, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_statusTextFallback.gameObject, 28);

            // --- Action buttons row ---
            var actionRowRt = UIHelper.CreatePanel(panelRt, "ActionRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(actionRowRt.gameObject, 44);
            UIHelper.AddHorizontalLayout(actionRowRt, spacing: 8f,
                padding: new RectOffset(8, 8, 4, 4), childForceExpand: true);

            _unlockButton = UIHelper.CreateButton(actionRowRt, "UnlockButton",
                "Unlock Skill", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_GREEN, 16);
            _closeButton = UIHelper.CreateButton(actionRowRt, "CloseButton",
                "Close", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 16);
        }

        // ====================================================================
        // Public Methods
        // ====================================================================

        /// <summary>Open the unlock UI for a specific skill.</summary>
        public void Open(string skillId)
        {
            _skillId = skillId;
            if (_panel != null) _panel.SetActive(true);
            UpdateDisplay();
        }

        public void Close()
        {
            if (_panel != null) _panel.SetActive(false);
        }

        // ====================================================================
        // Private Methods
        // ====================================================================

        private void UpdateDisplay()
        {
            if (string.IsNullOrEmpty(_skillId))
            {
                ClearDisplay();
                return;
            }

            var skillDb = SkillDatabase.Instance;
            var skill = skillDb.GetSkill(_skillId);
            if (skill == null)
            {
                ClearDisplay();
                return;
            }

            string nameText = skill.Name;
            string descText = skill.Description ?? "";

            if (_skillName != null) _skillName.text = nameText;
            else if (_skillNameFallback != null) _skillNameFallback.text = nameText;

            if (_skillDescription != null) _skillDescription.text = descText;
            else if (_skillDescriptionFallback != null) _skillDescriptionFallback.text = descText;

            // Build requirements list
            BuildRequirementsList(skill);

            // Check if requirements are met
            bool canUnlock = CheckRequirements(skill);
            if (_unlockButton != null) _unlockButton.interactable = canUnlock;

            string statusMsg = canUnlock
                ? "Requirements met! Click to unlock."
                : "Requirements not met.";

            if (_statusText != null) _statusText.text = statusMsg;
            else if (_statusTextFallback != null) _statusTextFallback.text = statusMsg;
        }

        private void BuildRequirementsList(SkillDefinition skill)
        {
            if (_requirementsContainer == null) return;

            // Clear existing entries
            for (int i = _requirementsContainer.childCount - 1; i >= 0; i--)
                Destroy(_requirementsContainer.GetChild(i).gameObject);

            var player = _gameManager?.Player;
            if (player == null) return;

            // Level requirement
            if (skill.Requirements.CharacterLevel > 0)
            {
                bool met = player.Leveling.Level >= skill.Requirements.CharacterLevel;
                Color color = met ? UIHelper.COLOR_TEXT_GREEN : UIHelper.COLOR_TEXT_RED;

                if (_requirementEntryPrefab != null)
                {
                    var go = Instantiate(_requirementEntryPrefab, _requirementsContainer);
                    var text = go.GetComponentInChildren<TextMeshProUGUI>();
                    if (text != null)
                    {
                        text.text = $"Level {skill.Requirements.CharacterLevel}";
                        text.color = met ? Color.green : Color.red;
                    }
                }
                else
                {
                    string prefix = met ? "[MET]" : "[X]";
                    var reqText = UIHelper.CreateText(_requirementsContainer, "ReqLevel",
                        $"{prefix} Level {skill.Requirements.CharacterLevel} (Current: {player.Leveling.Level})",
                        14, color, TextAnchor.MiddleLeft);
                    UIHelper.SetPreferredHeight(reqText.gameObject, 24);
                }
            }
        }

        private bool CheckRequirements(SkillDefinition skill)
        {
            if (_gameManager?.Player == null) return false;

            var player = _gameManager.Player;

            // Check level requirement
            if (skill.Requirements.CharacterLevel > 0 && player.Leveling.Level < skill.Requirements.CharacterLevel)
                return false;

            return true;
        }

        private void ClearDisplay()
        {
            if (_skillName != null) _skillName.text = "";
            else if (_skillNameFallback != null) _skillNameFallback.text = "";

            if (_skillDescription != null) _skillDescription.text = "";
            else if (_skillDescriptionFallback != null) _skillDescriptionFallback.text = "";

            string emptyStatus = "";
            if (_statusText != null) _statusText.text = emptyStatus;
            else if (_statusTextFallback != null) _statusTextFallback.text = emptyStatus;
        }

        private void OnUnlockClicked()
        {
            if (string.IsNullOrEmpty(_skillId)) return;
            if (_gameManager?.Player == null) return;

            _gameManager.Player.Skills.LearnSkill(_skillId);
            GameEvents.RaiseSkillLearned(_skillId);

            string unlockMsg = "Skill unlocked!";
            if (_statusText != null) _statusText.text = unlockMsg;
            else if (_statusTextFallback != null) _statusTextFallback.text = unlockMsg;

            if (_unlockButton != null) _unlockButton.interactable = false;
        }
    }
}
