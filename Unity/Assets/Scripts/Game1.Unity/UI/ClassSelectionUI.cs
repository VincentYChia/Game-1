// ============================================================================
// Game1.Unity.UI.ClassSelectionUI
// Migrated from: rendering/renderer.py (lines 6344-6426: render_class_selection_ui)
// Migration phase: 6
// Date: 2026-02-13
//
// Class selection screen: 6 class cards with tag descriptions.
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
    /// Class selection panel — 6 class cards with descriptions and bonuses.
    /// Shown after entering player name, before gameplay starts.
    /// </summary>
    public class ClassSelectionUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Class Grid")]
        [SerializeField] private Transform _classCardContainer;
        [SerializeField] private GameObject _classCardPrefab;

        [Header("Selected Class Details")]
        [SerializeField] private TextMeshProUGUI _selectedClassName;
        [SerializeField] private TextMeshProUGUI _selectedClassDesc;
        [SerializeField] private TextMeshProUGUI _selectedClassBonuses;
        [SerializeField] private Button _confirmButton;

        private string _selectedClassId;
        private string _playerName = "Player";
        private GameStateManager _stateManager;

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            if (_confirmButton != null)
                _confirmButton.onClick.AddListener(_onConfirm);

            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onStateChanged;
        }

        /// <summary>Set the player name (from StartMenuUI).</summary>
        public void SetPlayerName(string name)
        {
            _playerName = name;
        }

        private void _populateClasses()
        {
            if (_classCardContainer == null) return;

            foreach (Transform child in _classCardContainer)
                Destroy(child.gameObject);

            var classDb = ClassDatabase.Instance;
            if (classDb == null) return;

            var allClasses = classDb.GetAllClasses();
            if (allClasses == null) return;

            foreach (var classDef in allClasses)
            {
                if (_classCardPrefab == null) continue;

                var card = Instantiate(_classCardPrefab, _classCardContainer);

                // Set class name
                var nameText = card.GetComponentInChildren<TextMeshProUGUI>();
                if (nameText != null) nameText.text = classDef.Name;

                // Set click handler
                var button = card.GetComponent<Button>();
                var capturedId = classDef.ClassId;
                var capturedDef = classDef;
                if (button != null)
                {
                    button.onClick.AddListener(() => _selectClass(capturedId, capturedDef));
                }
            }
        }

        private void _selectClass(string classId, ClassDefinition classDef)
        {
            _selectedClassId = classId;

            if (_selectedClassName != null)
                _selectedClassName.text = classDef.Name;

            if (_selectedClassDesc != null)
                _selectedClassDesc.text = classDef.Description ?? "";

            if (_selectedClassBonuses != null)
            {
                string bonuses = "";
                if (classDef.Bonuses != null)
                {
                    foreach (var kvp in classDef.Bonuses)
                        bonuses += $"{kvp.Key}: +{kvp.Value:P0}\n";
                }
                if (classDef.Tags != null)
                {
                    bonuses += "\nTags: " + string.Join(", ", classDef.Tags);
                }
                _selectedClassBonuses.text = bonuses;
            }

            if (_confirmButton != null)
                _confirmButton.interactable = true;
        }

        private void _onConfirm()
        {
            if (string.IsNullOrEmpty(_selectedClassId)) return;

            GameManager.Instance?.StartNewGame(_playerName, _selectedClassId);
        }

        private void _onStateChanged(GameState old, GameState next)
        {
            bool visible = next == GameState.ClassSelection;
            _setVisible(visible);
            if (visible) _populateClasses();
        }

        private void _setVisible(bool v)
        {
            if (_panel != null) _panel.SetActive(v);
        }
    }
}
