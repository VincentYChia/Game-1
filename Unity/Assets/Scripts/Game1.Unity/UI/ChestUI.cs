// ============================================================================
// Game1.Unity.UI.ChestUI
// Migrated from: rendering/renderer.py (lines 1637-2022: chest UIs)
// Migration phase: 6
// Date: 2026-02-13
//
// Shared chest display for dungeon, spawn, and death chests.
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

        // Fallback UI references populated by _buildUI()
        private Text _titleTextFallback;
        private GridLayoutGroup _itemGrid;
        private Text _emptyLabel;

        private void Start()
        {
            if (_panel == null) _buildUI();

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
            else if (_titleTextFallback != null)
                _titleTextFallback.text = title;

            _populateItems();
            _stateManager?.TransitionTo(chestType);
        }

        private void _populateItems()
        {
            if (_itemContainer == null) return;

            foreach (Transform child in _itemContainer)
                Destroy(child.gameObject);

            // Show/hide empty label
            if (_emptyLabel != null)
                _emptyLabel.gameObject.SetActive(_items.Count == 0);

            foreach (var item in _items)
            {
                if (_itemSlotPrefab != null)
                {
                    // Inspector-assigned prefab path
                    var slot = Instantiate(_itemSlotPrefab, _itemContainer);

                    var icon = slot.GetComponentInChildren<Image>();
                    if (icon != null && SpriteDatabase.Instance != null)
                        icon.sprite = SpriteDatabase.Instance.GetItemSprite(item.ItemId);

                    var text = slot.GetComponentInChildren<TextMeshProUGUI>();
                    if (text != null)
                        text.text = item.Quantity > 1 ? item.Quantity.ToString() : "";
                }
                else
                {
                    // Code-built fallback: create item slot via UIHelper
                    var (slotRoot, slotBg, slotIcon, slotQty, slotBorder) =
                        UIHelper.CreateItemSlot(_itemContainer, "Slot_" + item.ItemId, 64f);

                    if (SpriteDatabase.Instance != null)
                    {
                        var sprite = SpriteDatabase.Instance.GetItemSprite(item.ItemId);
                        if (sprite != null)
                        {
                            slotIcon.sprite = sprite;
                            slotIcon.enabled = true;
                        }
                    }

                    if (item.Quantity > 1)
                        slotQty.text = item.Quantity.ToString();
                }
            }
        }

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        private void _buildUI()
        {
            // Root panel — centered, 500px wide, dark background
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "ChestPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(500, 480), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);
            _panel = panelRt.gameObject;

            // Main vertical layout
            var vlg = UIHelper.AddVerticalLayout(panelRt, spacing: 8f,
                padding: new RectOffset(12, 12, 12, 12));
            vlg.childAlignment = TextAnchor.UpperCenter;

            // Header row: title + close hint
            var (headerRow, headerTitle, headerHint) = UIHelper.CreateHeaderRow(
                panelRt, "CHEST", "[ESC] Close", 40f);
            _titleTextFallback = headerTitle;

            // Wire close button from header hint area
            _closeButton = headerHint.gameObject.AddComponent<Button>();
            _closeButton.targetGraphic = headerRow.GetComponent<Image>();

            // Divider
            UIHelper.CreateDivider(panelRt);

            // Scrollable item grid area
            var (scrollRect, scrollContent) = UIHelper.CreateScrollView(panelRt, "ItemScroll",
                UIHelper.COLOR_BG_PANEL);
            UIHelper.SetPreferredHeight(scrollRect.gameObject, 300);

            // Grid layout inside scroll content for item slots
            _itemGrid = UIHelper.CreateGridLayout(scrollContent, "ItemGrid",
                columns: 6,
                cellSize: new Vector2(64, 64),
                spacing: new Vector2(8, 8),
                padding: new RectOffset(8, 8, 8, 8));
            _itemContainer = _itemGrid.transform;

            // Empty label (shown when chest has no items)
            _emptyLabel = UIHelper.CreateText(scrollContent, "EmptyLabel",
                "This chest is empty.", 15, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(_emptyLabel.gameObject, 40);
            _emptyLabel.gameObject.SetActive(false);

            // Divider
            UIHelper.CreateDivider(panelRt);

            // Bottom buttons row: Take All, Close
            var btnRow = UIHelper.CreatePanel(panelRt, "ButtonRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(btnRow.gameObject, 50);
            UIHelper.AddHorizontalLayout(btnRow, spacing: 10f,
                padding: new RectOffset(8, 8, 4, 4), childForceExpand: true);

            _takeAllButton = UIHelper.CreateButton(btnRow, "TakeAllButton",
                "Take All", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_GREEN, 16);
            UIHelper.SetPreferredSize(_takeAllButton.gameObject, 200, 42);

            _closeButton = UIHelper.CreateButton(btnRow, "CloseButton",
                "Close", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 16);
            UIHelper.SetPreferredSize(_closeButton.gameObject, 200, 42);
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
