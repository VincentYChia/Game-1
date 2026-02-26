// ============================================================================
// Game1.Unity.UI.StartMenuUI
// Migrated from: rendering/renderer.py (lines 6257-6344: render_start_menu)
//              + game_engine.py (lines 518-530: menu nav)
// Migration phase: 6
// Date: 2026-02-13
//
// Main menu: New World, Load World, Temporary World options.
// Self-building: if _panel is null at Start, _buildUI() constructs the full
// UI hierarchy programmatically via UIHelper.
// ============================================================================

using System.IO;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

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

        // Fallback UI references populated by _buildUI()
        private Text _titleTextFallback;
        private InputField _playerNameInputFallback;
        private Button _loadDefaultButton;

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            if (_newWorldButton != null) _newWorldButton.onClick.AddListener(_onNewWorld);
            if (_loadWorldButton != null) _loadWorldButton.onClick.AddListener(_onLoadWorld);
            if (_tempWorldButton != null) _tempWorldButton.onClick.AddListener(_onTempWorld);
            if (_confirmNameButton != null) _confirmNameButton.onClick.AddListener(_onConfirmName);

            if (_titleText != null)
                _titleText.text = "Game-1";
            else if (_titleTextFallback != null)
                _titleTextFallback.text = "WELCOME TO THE GAME";

            if (_namePanel != null) _namePanel.SetActive(false);
            if (_loadPanel != null) _loadPanel.SetActive(false);
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
            // Root panel — centered 500x600, dark background
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "StartMenuPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(500, 600), Vector2.zero);
            // Center anchors
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);
            _panel = panelRt.gameObject;

            // Vertical layout for stacking children
            var vlg = UIHelper.AddVerticalLayout(panelRt, spacing: 12f,
                padding: new RectOffset(50, 50, 30, 30));
            vlg.childAlignment = TextAnchor.UpperCenter;

            // Title: "WELCOME TO THE GAME" — gold, centered
            var titleText = UIHelper.CreateText(panelRt, "Title",
                "WELCOME TO THE GAME", 28, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(titleText.gameObject, 50);
            _titleTextFallback = titleText;

            // Subtitle — secondary color
            var subtitleText = UIHelper.CreateText(panelRt, "Subtitle",
                "A Crafting RPG Adventure", 16, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(subtitleText.gameObject, 30);

            // Spacer
            var spacerRt = UIHelper.CreateContainer(panelRt, "Spacer",
                new Vector2(0, 0.5f), new Vector2(1, 0.5f));
            UIHelper.SetPreferredHeight(spacerRt.gameObject, 20);

            // Button: "New World"
            _newWorldButton = UIHelper.CreateButton(panelRt, "NewWorldButton",
                "New World", UIHelper.COLOR_BG_BUTTON, Color.white, 18);
            var newBtnRt = _newWorldButton.GetComponent<RectTransform>();
            UIHelper.SetPreferredSize(newBtnRt.gameObject, 400, 60);

            // Button: "Load World"
            _loadWorldButton = UIHelper.CreateButton(panelRt, "LoadWorldButton",
                "Load World", UIHelper.COLOR_BG_BUTTON, Color.white, 18);
            var loadBtnRt = _loadWorldButton.GetComponent<RectTransform>();
            UIHelper.SetPreferredSize(loadBtnRt.gameObject, 400, 60);

            // Button: "Load Default Save"
            _loadDefaultButton = UIHelper.CreateButton(panelRt, "LoadDefaultButton",
                "Load Default Save", UIHelper.COLOR_BG_BUTTON, Color.white, 18);
            var defaultBtnRt = _loadDefaultButton.GetComponent<RectTransform>();
            UIHelper.SetPreferredSize(defaultBtnRt.gameObject, 400, 60);
            _loadDefaultButton.onClick.AddListener(_onLoadDefault);

            // Button: "Temporary World"
            _tempWorldButton = UIHelper.CreateButton(panelRt, "TempWorldButton",
                "Temporary World", UIHelper.COLOR_BG_BUTTON, Color.white, 18);
            var tempBtnRt = _tempWorldButton.GetComponent<RectTransform>();
            UIHelper.SetPreferredSize(tempBtnRt.gameObject, 400, 60);

            // ---- Name input sub-panel (hidden by default) ----
            var namePanelRt = UIHelper.CreateSizedPanel(
                panelRt, "NamePanel", UIHelper.COLOR_BG_PANEL,
                new Vector2(420, 120), Vector2.zero);
            UIHelper.SetPreferredSize(namePanelRt.gameObject, 420, 120);
            var nameVlg = UIHelper.AddVerticalLayout(namePanelRt, spacing: 8f,
                padding: new RectOffset(10, 10, 10, 10));
            nameVlg.childAlignment = TextAnchor.MiddleCenter;
            _namePanel = namePanelRt.gameObject;

            var nameLabel = UIHelper.CreateText(namePanelRt, "NameLabel",
                "Enter your name:", 16, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(nameLabel.gameObject, 24);

            _playerNameInputFallback = UIHelper.CreateInputField(namePanelRt, "NameInput",
                "Player", new Vector2(300, 36), Vector2.zero, 16);
            // Override anchoring so layout group controls it
            var inputRt = _playerNameInputFallback.GetComponent<RectTransform>();
            inputRt.anchorMin = Vector2.zero;
            inputRt.anchorMax = Vector2.one;
            UIHelper.SetPreferredSize(inputRt.gameObject, 300, 36);

            _confirmNameButton = UIHelper.CreateButton(namePanelRt, "ConfirmNameButton",
                "Confirm", UIHelper.COLOR_BG_BUTTON, Color.white, 16);
            UIHelper.SetPreferredSize(_confirmNameButton.gameObject, 200, 36);

            _namePanel.SetActive(false);

            // ---- Load panel (hidden by default) ----
            var loadPanelRt = UIHelper.CreateSizedPanel(
                panelRt, "LoadPanel", UIHelper.COLOR_BG_PANEL,
                new Vector2(420, 200), Vector2.zero);
            UIHelper.SetPreferredSize(loadPanelRt.gameObject, 420, 200);
            _loadPanel = loadPanelRt.gameObject;

            var (scrollRect, content) = UIHelper.CreateScrollView(loadPanelRt, "SaveSlotScroll");
            _saveSlotContainer = content;
            // No prefab needed — slots are built dynamically in _populateSaveSlots
            _loadPanel.SetActive(false);
        }

        // ====================================================================
        // Button Handlers
        // ====================================================================

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
                else if (_playerNameInputFallback != null)
                {
                    _playerNameInputFallback.text = "Player";
                    _playerNameInputFallback.Select();
                }
            }
        }

        private void _onConfirmName()
        {
            string name = null;
            if (_playerNameInput != null)
                name = _playerNameInput.text;
            else if (_playerNameInputFallback != null)
                name = _playerNameInputFallback.text;

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

        private void _onLoadDefault()
        {
            // Load the default save file
            GameManager.Instance?.LoadGame("default");
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
                string saveName = Path.GetFileNameWithoutExtension(file);

                if (_saveSlotPrefab != null)
                {
                    // Inspector-assigned prefab path
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
                else
                {
                    // Code-built fallback: create slot button via UIHelper
                    var slotBtn = UIHelper.CreateButton(_saveSlotContainer, "Slot_" + saveName,
                        saveName, UIHelper.COLOR_BG_SLOT, UIHelper.COLOR_TEXT_PRIMARY, 14);
                    UIHelper.SetPreferredHeight(slotBtn.gameObject, 36);

                    var capturedName = saveName;
                    slotBtn.onClick.AddListener(() =>
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
