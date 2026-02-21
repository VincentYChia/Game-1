// ============================================================================
// Game1.Unity.UI.SaveLoadUI
// Migrated from: core/game_engine.py (save/load UI sections)
// Migration phase: 6
// Date: 2026-02-21
//
// Save/load file selection UI panel.
// ============================================================================

using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Unity.Core;

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
        private bool _isSaveMode;
        private List<SaveFileInfo> _saveFiles = new();

        private GameManager _gameManager;
        private GameStateManager _stateManager;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            _gameManager = GameManager.Instance;
            _stateManager = FindFirstObjectByType<GameStateManager>();

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
        // Public Methods
        // ====================================================================

        /// <summary>Open the save UI.</summary>
        public void OpenForSave()
        {
            _isSaveMode = true;
            Open();
            if (_saveButton != null) _saveButton.gameObject.SetActive(true);
            if (_loadButton != null) _loadButton.gameObject.SetActive(false);
        }

        /// <summary>Open the load UI.</summary>
        public void OpenForLoad()
        {
            _isSaveMode = false;
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
            }
        }

        private void SelectSlot(string saveName)
        {
            _selectedSaveName = saveName;
            if (_selectedSlotInfo != null)
                _selectedSlotInfo.text = $"Selected: {saveName}";
            if (_saveNameInput != null)
                _saveNameInput.text = saveName;
        }

        private void OnSaveClicked()
        {
            string saveName = _saveNameInput != null ? _saveNameInput.text : _selectedSaveName;
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
