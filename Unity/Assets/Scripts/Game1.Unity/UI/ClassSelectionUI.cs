// ============================================================================
// Game1.Unity.UI.ClassSelectionUI
// Migrated from: rendering/renderer.py (lines 6344-6426: render_class_selection_ui)
// Migration phase: 6
// Date: 2026-02-13
//
// Class selection screen: 6 class cards with tag descriptions.
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

        // Fallback UI references populated by _buildUI()
        private Text _selectedClassNameFallback;
        private Text _selectedClassDescFallback;
        private Text _selectedClassBonusesFallback;

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
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

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        private void _buildUI()
        {
            // Root panel — right-side, dark background
            var panelRt = UIHelper.CreatePanel(
                transform, "ClassSelectionPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(0.55f, 0.05f), new Vector2(0.95f, 0.95f));
            _panel = panelRt.gameObject;

            // Main vertical layout
            var vlg = UIHelper.AddVerticalLayout(panelRt, spacing: 10f,
                padding: new RectOffset(16, 16, 16, 16));
            vlg.childAlignment = TextAnchor.UpperCenter;

            // Title: "SELECT YOUR CLASS" — gold, centered
            var titleText = UIHelper.CreateText(panelRt, "Title",
                "SELECT YOUR CLASS", 24, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(titleText.gameObject, 44);

            // Divider
            UIHelper.CreateDivider(panelRt);

            // Scroll area for class grid
            var (scrollRect, scrollContent) = UIHelper.CreateScrollView(panelRt, "ClassGridScroll");
            UIHelper.SetPreferredHeight(scrollRect.gameObject, 340);

            // Remove the default VLG from scroll content so we can add GridLayoutGroup.
            // Must use DestroyImmediate — Object.Destroy is deferred to end of frame.
            var existingVlg = scrollContent.GetComponent<VerticalLayoutGroup>();
            if (existingVlg != null) Object.DestroyImmediate(existingVlg);

            // Grid layout (2 columns x 3 rows), cell size (200, 140), spacing 10
            var grid = scrollContent.gameObject.AddComponent<GridLayoutGroup>();
            grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            grid.constraintCount = 2;
            grid.cellSize = new Vector2(200, 140);
            grid.spacing = new Vector2(10, 10);
            grid.padding = new RectOffset(8, 8, 8, 8);
            grid.childAlignment = TextAnchor.UpperCenter;

            _classCardContainer = scrollContent;

            // Divider below grid
            UIHelper.CreateDivider(panelRt);

            // Selected class details section
            var detailPanel = UIHelper.CreatePanel(panelRt, "DetailPanel", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(detailPanel.gameObject, 130);
            var detailVlg = UIHelper.AddVerticalLayout(detailPanel, spacing: 4f,
                padding: new RectOffset(12, 12, 8, 8));

            // Selected class name
            _selectedClassNameFallback = UIHelper.CreateText(detailPanel, "SelectedName",
                "-- No class selected --", 20, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_selectedClassNameFallback.gameObject, 30);

            // Selected class description
            _selectedClassDescFallback = UIHelper.CreateText(detailPanel, "SelectedDesc",
                "", 14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.UpperCenter);
            UIHelper.SetPreferredHeight(_selectedClassDescFallback.gameObject, 36);

            // Selected class bonuses
            _selectedClassBonusesFallback = UIHelper.CreateText(detailPanel, "SelectedBonuses",
                "", 14, UIHelper.COLOR_TEXT_GREEN, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_selectedClassBonusesFallback.gameObject, 50);

            // Confirm button
            _confirmButton = UIHelper.CreateButton(panelRt, "ConfirmButton",
                "Confirm Class", UIHelper.COLOR_BG_BUTTON, Color.white, 18);
            UIHelper.SetPreferredHeight(_confirmButton.gameObject, 50);
            _confirmButton.interactable = false;
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>Set the player name (from StartMenuUI).</summary>
        public void SetPlayerName(string name)
        {
            _playerName = name;
        }

        // ====================================================================
        // Private Methods
        // ====================================================================

        private void _populateClasses()
        {
            if (_classCardContainer == null) return;

            foreach (Transform child in _classCardContainer)
                Destroy(child.gameObject);

            var classDb = ClassDatabase.Instance;
            if (classDb == null) return;

            var allClasses = classDb.Classes;
            if (allClasses == null) return;

            foreach (var classDef in allClasses.Values)
            {
                if (_classCardPrefab != null)
                {
                    // Inspector-assigned prefab path
                    var card = Instantiate(_classCardPrefab, _classCardContainer);

                    var nameText = card.GetComponentInChildren<TextMeshProUGUI>();
                    if (nameText != null) nameText.text = classDef.Name;

                    var button = card.GetComponent<Button>();
                    var capturedId = classDef.ClassId;
                    var capturedDef = classDef;
                    if (button != null)
                    {
                        button.onClick.AddListener(() => _selectClass(capturedId, capturedDef));
                    }
                }
                else
                {
                    // Code-built fallback: create class card via UIHelper
                    _createClassCard(classDef);
                }
            }
        }

        private void _createClassCard(ClassDefinition classDef)
        {
            // Card panel — dark background
            var cardRt = UIHelper.CreateSizedPanel(
                _classCardContainer, "Card_" + classDef.ClassId, UIHelper.COLOR_BG_SLOT,
                new Vector2(200, 140), Vector2.zero);

            // Make it clickable
            var btn = cardRt.gameObject.AddComponent<Button>();
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
            colors.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
            btn.colors = colors;

            // Layout inside card
            var cardVlg = UIHelper.AddVerticalLayout(cardRt, spacing: 4f,
                padding: new RectOffset(8, 8, 8, 8));
            cardVlg.childAlignment = TextAnchor.UpperCenter;

            // Class name — gold
            var nameText = UIHelper.CreateText(cardRt, "ClassName",
                classDef.Name, 16, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(nameText.gameObject, 24);

            // Bonus line 1
            string bonus1 = "";
            string bonus2 = "";
            if (classDef.Bonuses != null)
            {
                int idx = 0;
                foreach (var kvp in classDef.Bonuses)
                {
                    string line = $"{kvp.Key}: +{kvp.Value:P0}";
                    if (idx == 0) bonus1 = line;
                    else if (idx == 1) bonus2 = line;
                    else bonus2 += $", {kvp.Key}: +{kvp.Value:P0}";
                    idx++;
                }
            }

            var bonusText1 = UIHelper.CreateText(cardRt, "Bonus1",
                bonus1, 13, UIHelper.COLOR_TEXT_GREEN, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(bonusText1.gameObject, 20);

            var bonusText2 = UIHelper.CreateText(cardRt, "Bonus2",
                bonus2, 13, UIHelper.COLOR_TEXT_GREEN, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(bonusText2.gameObject, 20);

            // Tags (if any)
            if (classDef.Tags != null && classDef.Tags.Count > 0)
            {
                string tags = string.Join(", ", classDef.Tags);
                var tagsText = UIHelper.CreateText(cardRt, "Tags",
                    tags, 11, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
                UIHelper.SetPreferredHeight(tagsText.gameObject, 18);
            }

            var capturedId = classDef.ClassId;
            var capturedDef = classDef;
            btn.onClick.AddListener(() => _selectClass(capturedId, capturedDef));
        }

        private void _selectClass(string classId, ClassDefinition classDef)
        {
            _selectedClassId = classId;

            if (_selectedClassName != null)
                _selectedClassName.text = classDef.Name;
            else if (_selectedClassNameFallback != null)
                _selectedClassNameFallback.text = classDef.Name;

            if (_selectedClassDesc != null)
                _selectedClassDesc.text = classDef.Description ?? "";
            else if (_selectedClassDescFallback != null)
                _selectedClassDescFallback.text = classDef.Description ?? "";

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
            else if (_selectedClassBonusesFallback != null)
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
                _selectedClassBonusesFallback.text = bonuses;
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
