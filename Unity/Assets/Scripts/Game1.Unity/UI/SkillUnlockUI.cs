// ============================================================================
// Game1.Unity.UI.SkillUnlockUI
// Migrated from: core/game_engine.py (skill unlock display sections)
// Migration phase: 6
// Date: 2026-02-21
//
// Displays skill unlock requirements and allows unlocking.
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
        // State
        // ====================================================================

        private string _skillId;
        private GameManager _gameManager;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            _gameManager = GameManager.Instance;

            if (_unlockButton != null)
                _unlockButton.onClick.AddListener(OnUnlockClicked);
            if (_closeButton != null)
                _closeButton.onClick.AddListener(Close);

            if (_panel != null)
                _panel.SetActive(false);
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

            if (_skillName != null) _skillName.text = skill.Name;
            if (_skillDescription != null) _skillDescription.text = skill.Description ?? "";

            // Check if requirements are met
            bool canUnlock = CheckRequirements(skill);
            if (_unlockButton != null) _unlockButton.interactable = canUnlock;

            if (_statusText != null)
            {
                _statusText.text = canUnlock
                    ? "Requirements met! Click to unlock."
                    : "Requirements not met.";
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
            if (_skillDescription != null) _skillDescription.text = "";
            if (_statusText != null) _statusText.text = "";
        }

        private void OnUnlockClicked()
        {
            if (string.IsNullOrEmpty(_skillId)) return;
            if (_gameManager?.Player == null) return;

            _gameManager.Player.Skills.LearnSkill(_skillId);
            GameEvents.RaiseSkillLearned(_skillId);

            if (_statusText != null) _statusText.text = "Skill unlocked!";
            if (_unlockButton != null) _unlockButton.interactable = false;
        }
    }
}
