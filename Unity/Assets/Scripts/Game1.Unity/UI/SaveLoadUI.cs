// ============================================================================
// Game1.Unity.UI.SaveLoadUI
// Migrated from: core/game_engine.py (save/load UI sections)
// Migration phase: 6
// Date: 2026-02-21
//
// Save/load file selection UI panel.
// Self-building: if _panel is null at Start, _buildUI() constructs the full
// UI hierarchy programmatically via UIHelper.
// ============================================================================

using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Save/Load UI panel — displays save files and allows save/load/delete.
    /// </summary>
    public class SaveLoadUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Save Slots")]
        [SerializeField] private Transform _slotContainer;
        [SerializeField] private GameObject _saveSlotPrefab;

        [Header("Buttons")]
        [SerializeField] private Button _saveButton;
        [SerializeField] private Button _loadButton;
        [SerializeField] private Button _deleteButton;
        [SerializeField] private Button _closeButton;

        [Header("Input")]
        [SerializeField] private TMP_InputField _saveNameInput;

        [Header("Info")]
        [SerializeField] private TextMeshProUGUI _selectedSlotInfo;

        // ====================================================================
        // State
        // ====================================================================

        private string _selectedSaveName;
        private List<SaveFileInfo> _saveFiles = new();

        private GameManager _gameManager;
        private GameStateManager _stateManager;

        // Fallback UI references populated by _buildUI()
        private InputField _saveNameInputFallback;
        private Text _selectedSlotInfoFallback;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            if (_panel == null) _buildUI();

            _gameManager = GameManager.Instance;
            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();

            if (_saveButton != null)
                _saveButton.onClick.AddListener(OnSaveClicked);
            if (_loadButton != null)
                _loadButton.onClick.AddListener(OnLoadClicked);
            if (_deleteButton != null)
                _deleteButton.onClick.AddListener(OnDeleteClicked);
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
            // Root panel — centered, dark background
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "SaveLoadPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(520, 560), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);
            _panel = panelRt.gameObject;

            // Main vertical layout
            var vlg = UIHelper.AddVerticalLayout(panelRt, spacing: 10f,
                padding: new RectOffset(16, 16, 16, 16));
            vlg.childAlignment = TextAnchor.UpperCenter;

            // Header row: title + close button
            var (headerRow, headerTitle, headerHint) = UIHelper.CreateHeaderRow(
                panelRt, "SAVE / LOAD", "[X] Close", 44f);

            // Wire close button from header hint area
            _closeButton = headerHint.gameObject.AddComponent<Button>();
            _closeButton.targetGraphic = headerRow.GetComponent<Image>();

            // Divider
            UIHelper.CreateDivider(panelRt);

            // Player name input field at top
            var inputRow = UIHelper.CreatePanel(panelRt, "InputRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(inputRow.gameObject, 40);
            var inputHlg = UIHelper.AddHorizontalLayout(inputRow, spacing: 8f,
                padding: new RectOffset(4, 4, 4, 4));

            var inputLabel = UIHelper.CreateText(inputRow, "InputLabel",
                "Save Name:", 15, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredSize(inputLabel.gameObject, 100, 32);

            _saveNameInputFallback = UIHelper.CreateInputField(inputRow, "SaveNameInput",
                "Enter save name...", new Vector2(280, 32), Vector2.zero, 15);
            var inputFieldRt = _saveNameInputFallback.GetComponent<RectTransform>();
            inputFieldRt.anchorMin = Vector2.zero;
            inputFieldRt.anchorMax = Vector2.one;
            UIHelper.SetPreferredSize(inputFieldRt.gameObject, 280, 32);

            // Divider
            UIHelper.CreateDivider(panelRt);

            // Scrollable save file list
            var (scrollRect, scrollContent) = UIHelper.CreateScrollView(panelRt, "SaveFileScroll",
                UIHelper.COLOR_BG_PANEL);
            UIHelper.SetPreferredHeight(scrollRect.gameObject, 300);
            _slotContainer = scrollContent;

            // Selected slot info text
            _selectedSlotInfoFallback = UIHelper.CreateText(panelRt, "SelectedInfo",
                "No save selected", 14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_selectedSlotInfoFallback.gameObject, 24);

            // Divider
            UIHelper.CreateDivider(panelRt);

            // Bottom buttons row: Save, Load, Delete
            var btnRow = UIHelper.CreatePanel(panelRt, "ButtonRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(btnRow.gameObject, 50);
            var btnHlg = UIHelper.AddHorizontalLayout(btnRow, spacing: 10f,
                padding: new RectOffset(8, 8, 4, 4), childForceExpand: true);

            _saveButton = UIHelper.CreateButton(btnRow, "SaveButton",
                "Save", UIHelper.COLOR_BG_BUTTON, Color.white, 16);
            UIHelper.SetPreferredSize(_saveButton.gameObject, 130, 42);

            _loadButton = UIHelper.CreateButton(btnRow, "LoadButton",
                "Load", UIHelper.COLOR_BG_BUTTON, Color.white, 16);
            UIHelper.SetPreferredSize(_loadButton.gameObject, 130, 42);

            _deleteButton = UIHelper.CreateButton(btnRow, "DeleteButton",
                "Delete", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_RED, 16);
            UIHelper.SetPreferredSize(_deleteButton.gameObject, 130, 42);
        }

        // ====================================================================
        // Public Methods
        // ====================================================================

        /// <summary>Open the save UI.</summary>
        public void OpenForSave()
        {
            Open();
            if (_saveButton != null) _saveButton.gameObject.SetActive(true);
            if (_loadButton != null) _loadButton.gameObject.SetActive(false);
        }

        /// <summary>Open the load UI.</summary>
        public void OpenForLoad()
        {
            Open();
            if (_saveButton != null) _saveButton.gameObject.SetActive(false);
            if (_loadButton != null) _loadButton.gameObject.SetActive(true);
        }

        /// <summary>Close the panel.</summary>
        public void Close()
        {
            if (_panel != null) _panel.SetActive(false);
            _stateManager?.TransitionTo(
                _gameManager?.Player != null ? GameState.Playing : GameState.StartMenu);
        }

        // ====================================================================
        // Private Methods
        // ====================================================================

        private void Open()
        {
            if (_panel != null) _panel.SetActive(true);
            _selectedSaveName = null;
            RefreshSaveFiles();
        }

        private void RefreshSaveFiles()
        {
            _saveFiles.Clear();

            string savePath = GamePaths.GetSavePath();
            if (Directory.Exists(savePath))
            {
                var files = Directory.GetFiles(savePath, "*.json");
                foreach (var file in files)
                {
                    var info = new FileInfo(file);
                    _saveFiles.Add(new SaveFileInfo
                    {
                        FileName = Path.GetFileNameWithoutExtension(file),
                        LastModified = info.LastWriteTime,
                        FileSize = info.Length,
                    });
                }

                // Sort by most recent first
                _saveFiles.Sort((a, b) => b.LastModified.CompareTo(a.LastModified));
            }

            RebuildSlotList();
        }

        private void RebuildSlotList()
        {
            // Clear existing entries
            if (_slotContainer != null)
            {
                for (int i = _slotContainer.childCount - 1; i >= 0; i--)
                    Destroy(_slotContainer.GetChild(i).gameObject);
            }

            // Create slot entries
            foreach (var save in _saveFiles)
            {
                if (_saveSlotPrefab != null && _slotContainer != null)
                {
                    // Inspector-assigned prefab path
                    var go = Instantiate(_saveSlotPrefab, _slotContainer);
                    var text = go.GetComponentInChildren<TextMeshProUGUI>();
                    if (text != null)
                    {
                        text.text = $"{save.FileName}\n{save.LastModified:yyyy-MM-dd HH:mm}";
                    }

                    var button = go.GetComponent<Button>();
                    if (button != null)
                    {
                        string saveName = save.FileName;
                        button.onClick.AddListener(() => SelectSlot(saveName));
                    }
                }
                else if (_slotContainer != null)
                {
                    // Code-built fallback: create save entry via UIHelper
                    string sizeStr = _formatFileSize(save.FileSize);
                    string label = $"{save.FileName}  |  {save.LastModified:yyyy-MM-dd HH:mm}  |  {sizeStr}";

                    var slotBtn = UIHelper.CreateButton(_slotContainer, "Slot_" + save.FileName,
                        label, UIHelper.COLOR_BG_SLOT, UIHelper.COLOR_TEXT_PRIMARY, 13);
                    UIHelper.SetPreferredHeight(slotBtn.gameObject, 40);

                    string saveName = save.FileName;
                    slotBtn.onClick.AddListener(() => SelectSlot(saveName));
                }
            }
        }

        private string _formatFileSize(long bytes)
        {
            if (bytes < 1024) return $"{bytes} B";
            if (bytes < 1024 * 1024) return $"{bytes / 1024.0:F1} KB";
            return $"{bytes / (1024.0 * 1024.0):F1} MB";
        }

        private void SelectSlot(string saveName)
        {
            _selectedSaveName = saveName;

            if (_selectedSlotInfo != null)
                _selectedSlotInfo.text = $"Selected: {saveName}";
            else if (_selectedSlotInfoFallback != null)
                _selectedSlotInfoFallback.text = $"Selected: {saveName}";

            if (_saveNameInput != null)
                _saveNameInput.text = saveName;
            else if (_saveNameInputFallback != null)
                _saveNameInputFallback.text = saveName;
        }

        private void OnSaveClicked()
        {
            string saveName = null;
            if (_saveNameInput != null)
                saveName = _saveNameInput.text;
            else if (_saveNameInputFallback != null)
                saveName = _saveNameInputFallback.text;

            if (string.IsNullOrEmpty(saveName))
                saveName = _selectedSaveName;
            if (string.IsNullOrEmpty(saveName)) return;

            _gameManager?.SaveGame(saveName);
            RefreshSaveFiles();
        }

        private void OnLoadClicked()
        {
            if (string.IsNullOrEmpty(_selectedSaveName)) return;
            _gameManager?.LoadGame(_selectedSaveName);
            Close();
        }

        private void OnDeleteClicked()
        {
            if (string.IsNullOrEmpty(_selectedSaveName)) return;

            string path = Path.Combine(GamePaths.GetSavePath(), _selectedSaveName + ".json");
            if (File.Exists(path))
            {
                File.Delete(path);
                RefreshSaveFiles();
            }
        }
    }

    /// <summary>Info about a save file.</summary>
    internal class SaveFileInfo
    {
        public string FileName { get; set; }
        public DateTime LastModified { get; set; }
        public long FileSize { get; set; }
    }
}
