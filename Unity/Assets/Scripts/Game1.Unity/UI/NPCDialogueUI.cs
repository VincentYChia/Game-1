// ============================================================================
// Game1.Unity.UI.NPCDialogueUI
// Migrated from: rendering/renderer.py (lines 3173-3290: render_npc_dialogue_ui)
//              + game_engine.py (lines 1325-1570: NPC interaction)
// Migration phase: 6
// Date: 2026-02-13
//
// NPC dialogue window with quest display, accept/turn-in buttons.
// Self-building: if _panel is null at Start, _buildUI() constructs the full
// UI hierarchy programmatically via UIHelper.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// NPC dialogue window — conversation text, quest list, accept/turn-in.
    /// </summary>
    public class NPCDialogueUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("NPC Info")]
        [SerializeField] private TextMeshProUGUI _npcNameText;
        [SerializeField] private Image _npcPortrait;

        [Header("Dialogue")]
        [SerializeField] private TextMeshProUGUI _dialogueText;

        [Header("Quest List")]
        [SerializeField] private Transform _questListContainer;
        [SerializeField] private GameObject _questEntryPrefab;

        [Header("Buttons")]
        [SerializeField] private Button _acceptButton;
        [SerializeField] private Button _turnInButton;
        [SerializeField] private Button _closeButton;

        // ====================================================================
        // Fallback references populated by _buildUI()
        // ====================================================================

        private Text _npcNameFallback;
        private Text _dialogueTextFallback;
        private ScrollRect _dialogueScrollRect;

        // ====================================================================
        // State
        // ====================================================================

        private GameStateManager _stateManager;
        private string _currentNpcId;

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            if (_closeButton != null) _closeButton.onClick.AddListener(_onClose);
            if (_acceptButton != null) _acceptButton.onClick.AddListener(_onAcceptQuest);
            if (_turnInButton != null) _turnInButton.onClick.AddListener(_onTurnInQuest);

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
            // Root panel — centered, 600x500
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "DialoguePanel", UIHelper.COLOR_BG_DARK,
                new Vector2(600, 500), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);
            _panel = panelRt.gameObject;

            UIHelper.AddVerticalLayout(panelRt, spacing: 6f,
                padding: new RectOffset(12, 12, 10, 10));

            // --- NPC name header ---
            var headerRt = UIHelper.CreatePanel(panelRt, "NPCHeader", UIHelper.COLOR_BG_HEADER,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(headerRt.gameObject, 44);
            UIHelper.AddHorizontalLayout(headerRt, spacing: 10f,
                padding: new RectOffset(12, 12, 6, 6));

            // NPC portrait placeholder
            var portraitImg = UIHelper.CreateImage(headerRt, "Portrait",
                UIHelper.COLOR_BG_SLOT, new Vector2(32, 32));
            var portraitLe = portraitImg.gameObject.AddComponent<LayoutElement>();
            portraitLe.preferredWidth = 32;
            portraitLe.preferredHeight = 32;
            _npcPortrait = portraitImg;

            // NPC name
            _npcNameFallback = UIHelper.CreateText(headerRt, "NPCName", "NPC",
                20, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleLeft);

            // --- Dialogue text area (scrollable) ---
            var dialogueAreaRt = UIHelper.CreatePanel(panelRt, "DialogueArea", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            var dialogueLe = dialogueAreaRt.gameObject.AddComponent<LayoutElement>();
            dialogueLe.flexibleHeight = 1f;
            dialogueLe.preferredHeight = 200;

            var (dialogueScroll, dialogueContent) = UIHelper.CreateScrollView(
                dialogueAreaRt, "DialogueScroll");
            _dialogueScrollRect = dialogueScroll;

            _dialogueTextFallback = UIHelper.CreateText(dialogueContent, "DialogueText", "",
                15, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_dialogueTextFallback.gameObject, 180);

            // --- Quest list section ---
            var questLabel = UIHelper.CreateText(panelRt, "QuestLabel", "Available Quests:",
                14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(questLabel.gameObject, 22);

            var questAreaRt = UIHelper.CreatePanel(panelRt, "QuestArea", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(questAreaRt.gameObject, 100);

            var (questScroll, questContent) = UIHelper.CreateScrollView(questAreaRt, "QuestScroll");
            _questListContainer = questContent;

            // --- Response buttons at bottom ---
            var buttonRowRt = UIHelper.CreatePanel(panelRt, "ButtonRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(buttonRowRt.gameObject, 44);
            UIHelper.AddHorizontalLayout(buttonRowRt, spacing: 10f,
                padding: new RectOffset(8, 8, 4, 4), childForceExpand: true);

            _acceptButton = UIHelper.CreateButton(buttonRowRt, "AcceptButton",
                "Accept Quest", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_GREEN, 15);
            _turnInButton = UIHelper.CreateButton(buttonRowRt, "TurnInButton",
                "Turn In", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_GOLD, 15);
            _closeButton = UIHelper.CreateButton(buttonRowRt, "CloseButton",
                "Close", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 15);
        }

        // ====================================================================
        // Public Methods
        // ====================================================================

        /// <summary>Open dialogue with an NPC.</summary>
        public void Open(string npcId, string npcName, string dialogue, List<string> availableQuests = null)
        {
            _currentNpcId = npcId;

            if (_npcNameText != null) _npcNameText.text = npcName;
            else if (_npcNameFallback != null) _npcNameFallback.text = npcName;

            if (_dialogueText != null) _dialogueText.text = dialogue;
            else if (_dialogueTextFallback != null) _dialogueTextFallback.text = dialogue;

            _populateQuests(availableQuests);
            _stateManager?.TransitionTo(GameState.NPCDialogue);
        }

        // ====================================================================
        // Private Methods
        // ====================================================================

        private void _populateQuests(List<string> questIds)
        {
            if (_questListContainer == null) return;

            foreach (Transform child in _questListContainer)
                Destroy(child.gameObject);

            if (questIds == null) return;

            foreach (string questId in questIds)
            {
                if (_questEntryPrefab != null)
                {
                    var entry = Instantiate(_questEntryPrefab, _questListContainer);
                    var text = entry.GetComponentInChildren<TextMeshProUGUI>();
                    if (text != null) text.text = questId;
                }
                else
                {
                    // Code-built fallback entry
                    var questBtn = UIHelper.CreateButton(_questListContainer, "Quest_" + questId,
                        questId, UIHelper.COLOR_BG_SLOT, UIHelper.COLOR_TEXT_PRIMARY, 13);
                    UIHelper.SetPreferredHeight(questBtn.gameObject, 28);
                }
            }
        }

        private void _onAcceptQuest()
        {
            NotificationUI.Instance?.Show("Quest accepted!", Color.green);
        }

        private void _onTurnInQuest()
        {
            NotificationUI.Instance?.Show("Quest completed!", Color.yellow);
        }

        private void _onClose()
        {
            _stateManager?.TransitionTo(GameState.Playing);
        }

        private void _onStateChanged(GameState old, GameState next)
        {
            _setVisible(next == GameState.NPCDialogue);
        }

        private void _setVisible(bool v)
        {
            if (_panel != null) _panel.SetActive(v);
        }
    }
}
