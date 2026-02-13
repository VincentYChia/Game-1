// ============================================================================
// Game1.Unity.UI.ChestUI
// Migrated from: rendering/renderer.py (lines 1637-2022: chest UIs)
// Migration phase: 6
// Date: 2026-02-13
//
// Shared chest display for dungeon, spawn, and death chests.
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
    /// Shared chest UI for dungeon, spawn, and death chests.
    /// Displays item grid with take-all and take-one buttons.
    /// </summary>
    public class ChestUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;
        [SerializeField] private TextMeshProUGUI _titleText;

        [Header("Item Grid")]
        [SerializeField] private Transform _itemContainer;
        [SerializeField] private GameObject _itemSlotPrefab;

        [Header("Buttons")]
        [SerializeField] private Button _takeAllButton;
        [SerializeField] private Button _closeButton;

        private GameStateManager _stateManager;
        private GameState _chestType;
        private List<ChestItemEntry> _items = new List<ChestItemEntry>();

        private struct ChestItemEntry
        {
            public string ItemId;
            public int Quantity;
        }

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            if (_takeAllButton != null) _takeAllButton.onClick.AddListener(_onTakeAll);
            if (_closeButton != null) _closeButton.onClick.AddListener(_onClose);

            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onStateChanged;
        }

        /// <summary>Open the chest UI with items.</summary>
        public void Open(GameState chestType, string title, List<(string itemId, int qty)> items)
        {
            _chestType = chestType;
            _items.Clear();
            foreach (var item in items)
                _items.Add(new ChestItemEntry { ItemId = item.itemId, Quantity = item.qty });

            if (_titleText != null)
                _titleText.text = title;

            _populateItems();
            _stateManager?.TransitionTo(chestType);
        }

        private void _populateItems()
        {
            if (_itemContainer == null) return;

            foreach (Transform child in _itemContainer)
                Destroy(child.gameObject);

            foreach (var item in _items)
            {
                if (_itemSlotPrefab == null) continue;
                var slot = Instantiate(_itemSlotPrefab, _itemContainer);

                var icon = slot.GetComponentInChildren<Image>();
                if (icon != null && SpriteDatabase.Instance != null)
                    icon.sprite = SpriteDatabase.Instance.GetItemSprite(item.ItemId);

                var text = slot.GetComponentInChildren<TextMeshProUGUI>();
                if (text != null)
                    text.text = item.Quantity > 1 ? item.Quantity.ToString() : "";
            }
        }

        private void _onTakeAll()
        {
            var gm = GameManager.Instance;
            if (gm?.Player == null) return;

            foreach (var item in _items)
                gm.Player.Inventory.AddItem(item.ItemId, item.Quantity);

            _items.Clear();
            _populateItems();
            NotificationUI.Instance?.Show("All items taken!", Color.green);
            _onClose();
        }

        private void _onClose()
        {
            _stateManager?.TransitionTo(GameState.Playing);
        }

        private void _onStateChanged(GameState old, GameState next)
        {
            bool visible = next == GameState.DungeonChestOpen
                        || next == GameState.SpawnChestOpen
                        || next == GameState.DeathChestOpen;
            _setVisible(visible);
        }

        private void _setVisible(bool v)
        {
            if (_panel != null) _panel.SetActive(v);
        }
    }
}
