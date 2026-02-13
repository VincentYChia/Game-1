// ============================================================================
// Game1.Unity.UI.StartMenuUI
// Migrated from: rendering/renderer.py (lines 6257-6344: render_start_menu)
//              + game_engine.py (lines 518-530: menu nav)
// Migration phase: 6
// Date: 2026-02-13
//
// Main menu: New World, Load World, Temporary World options.
// ============================================================================

using System.IO;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Unity.Core;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Start menu — New World, Load World, Load Default, Temporary World.
    /// First screen the player sees.
    /// </summary>
    public class StartMenuUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Title")]
        [SerializeField] private TextMeshProUGUI _titleText;

        [Header("Buttons")]
        [SerializeField] private Button _newWorldButton;
        [SerializeField] private Button _loadWorldButton;
        [SerializeField] private Button _tempWorldButton;

        [Header("Load Slots")]
        [SerializeField] private Transform _saveSlotContainer;
        [SerializeField] private GameObject _saveSlotPrefab;
        [SerializeField] private GameObject _loadPanel;

        [Header("New Game")]
        [SerializeField] private TMP_InputField _playerNameInput;
        [SerializeField] private GameObject _namePanel;
        [SerializeField] private Button _confirmNameButton;

        private GameStateManager _stateManager;

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            if (_newWorldButton != null) _newWorldButton.onClick.AddListener(_onNewWorld);
            if (_loadWorldButton != null) _loadWorldButton.onClick.AddListener(_onLoadWorld);
            if (_tempWorldButton != null) _tempWorldButton.onClick.AddListener(_onTempWorld);
            if (_confirmNameButton != null) _confirmNameButton.onClick.AddListener(_onConfirmName);

            if (_titleText != null) _titleText.text = "Game-1";
            if (_namePanel != null) _namePanel.SetActive(false);
            if (_loadPanel != null) _loadPanel.SetActive(false);
        }

        private void OnDestroy()
        {
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onStateChanged;
        }

        private void _onNewWorld()
        {
            // Show name input
            if (_namePanel != null)
            {
                _namePanel.SetActive(true);
                if (_playerNameInput != null)
                {
                    _playerNameInput.text = "Player";
                    _playerNameInput.Select();
                }
            }
        }

        private void _onConfirmName()
        {
            string name = _playerNameInput?.text ?? "Player";
            if (string.IsNullOrWhiteSpace(name)) name = "Player";

            if (_namePanel != null) _namePanel.SetActive(false);

            // Transition to class selection
            _stateManager?.TransitionTo(GameState.ClassSelection);
        }

        private void _onLoadWorld()
        {
            // Show save slot list
            if (_loadPanel != null)
            {
                _loadPanel.SetActive(true);
                _populateSaveSlots();
            }
        }

        private void _onTempWorld()
        {
            // Start with temporary world (no save)
            var gm = GameManager.Instance;
            if (gm != null)
            {
                gm.StartNewGame("Temp Player", "warrior");
            }
        }

        private void _populateSaveSlots()
        {
            if (_saveSlotContainer == null) return;

            foreach (Transform child in _saveSlotContainer)
                Destroy(child.gameObject);

            string savePath = GamePaths.GetSavePath();
            if (!Directory.Exists(savePath)) return;

            string[] saveFiles = Directory.GetFiles(savePath, "*.json");
            foreach (string file in saveFiles)
            {
                if (_saveSlotPrefab == null) continue;

                string saveName = Path.GetFileNameWithoutExtension(file);
                var slot = Instantiate(_saveSlotPrefab, _saveSlotContainer);

                var text = slot.GetComponentInChildren<TextMeshProUGUI>();
                if (text != null) text.text = saveName;

                var button = slot.GetComponent<Button>();
                var capturedName = saveName;
                if (button != null)
                {
                    button.onClick.AddListener(() =>
                    {
                        GameManager.Instance?.LoadGame(capturedName);
                        if (_loadPanel != null) _loadPanel.SetActive(false);
                    });
                }
            }
        }

        private void _onStateChanged(GameState old, GameState next)
        {
            _setVisible(next == GameState.StartMenu);
        }

        private void _setVisible(bool v)
        {
            if (_panel != null) _panel.SetActive(v);
        }
    }
}
