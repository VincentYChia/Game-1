// ============================================================================
// Game1.Unity.UI.NPCDialogueUI
// Migrated from: rendering/renderer.py (lines 3173-3290: render_npc_dialogue_ui)
//              + game_engine.py (lines 1325-1570: NPC interaction)
// Migration phase: 6
// Date: 2026-02-13
//
// NPC dialogue window with quest display, accept/turn-in buttons.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.Core;

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

        private GameStateManager _stateManager;
        private string _currentNpcId;

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
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

        /// <summary>Open dialogue with an NPC.</summary>
        public void Open(string npcId, string npcName, string dialogue, List<string> availableQuests = null)
        {
            _currentNpcId = npcId;

            if (_npcNameText != null) _npcNameText.text = npcName;
            if (_dialogueText != null) _dialogueText.text = dialogue;

            _populateQuests(availableQuests);
            _stateManager?.TransitionTo(GameState.NPCDialogue);
        }

        private void _populateQuests(List<string> questIds)
        {
            if (_questListContainer == null) return;

            foreach (Transform child in _questListContainer)
                Destroy(child.gameObject);

            if (questIds == null) return;

            foreach (string questId in questIds)
            {
                if (_questEntryPrefab == null) continue;
                var entry = Instantiate(_questEntryPrefab, _questListContainer);
                var text = entry.GetComponentInChildren<TextMeshProUGUI>();
                if (text != null) text.text = questId;
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
