// ============================================================================
// Game1.Unity.UI.InventoryUI
// Migrated from: rendering/renderer.py (lines 3977-4238: render_inventory_panel)
//              + game_engine.py (lines 6544-7000: drop logic)
// Migration phase: 6
// Date: 2026-02-13
//
// 30-slot inventory grid with drag-and-drop, tooltips, and quantity display.
// Self-building: if _panel is null at startup, _buildUI() constructs the
// entire hierarchy from code using UIHelper (no prefab/scene setup needed).
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using TMPro;
using Game1.Core;
using Game1.Data.Databases;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Inventory panel — 30-slot grid with item icons, quantities, and drag-and-drop.
    /// Opens/closes via Tab key.
    /// </summary>
    public class InventoryUI : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private int _columns = 6;

        [Header("Slot Prefab")]
        [SerializeField] private GameObject _slotPrefab;
        [SerializeField] private Transform _slotContainer;

        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        private InventorySlot[] _slots;
        private GameStateManager _stateManager;
        private InputManager _inputManager;

        // References populated by _buildUI()
        private ScrollRect _scrollRect;
        private RectTransform _scrollContent;
        private GridLayoutGroup _gridLayout;

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
            _inputManager = InputManager.Instance ?? FindFirstObjectByType<InputManager>();

            if (_inputManager != null)
                _inputManager.OnToggleInventory += _onToggle;

            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            // Subscribe to drag-drop completions for inventory slot swaps
            if (DragDropManager.Instance != null)
                DragDropManager.Instance.OnDropCompleted += _onDropCompleted;

            _createSlots();
            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_inputManager != null)
                _inputManager.OnToggleInventory -= _onToggle;
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onStateChanged;
            if (DragDropManager.Instance != null)
                DragDropManager.Instance.OnDropCompleted -= _onDropCompleted;
        }

        /// <summary>Handle drag-drop completions: swap inventory slots or equip from inventory.</summary>
        private void _onDropCompleted(DragDropManager.DragSource source, int sourceSlot,
            DragDropManager.DragSource target, int targetSlot)
        {
            var gm = GameManager.Instance;
            if (gm?.Player == null) return;

            // Inventory-to-Inventory swap
            if (source == DragDropManager.DragSource.Inventory && target == DragDropManager.DragSource.Inventory)
            {
                gm.Player.Inventory.SwapSlots(sourceSlot, targetSlot);
                Refresh();
            }
            // Inventory-to-Equipment (drag to equip)
            else if (source == DragDropManager.DragSource.Inventory && target == DragDropManager.DragSource.Equipment)
            {
                var slot = gm.Player.Inventory.GetSlot(sourceSlot);
                if (slot == null) return;
                var eqDb = EquipmentDatabase.Instance;
                if (eqDb != null && eqDb.IsEquipment(slot.ItemId))
                {
                    var eq = eqDb.CreateEquipmentFromId(slot.ItemId);
                    if (eq != null)
                    {
                        var (oldItem, status) = gm.Player.Equipment.Equip(eq);
                        if (status == "OK")
                        {
                            gm.Player.Inventory.RemoveItem(slot.ItemId, 1);
                            if (oldItem != null) gm.Player.Inventory.AddItem(oldItem.ItemId, 1);
                            Refresh();
                            FindFirstObjectByType<EquipmentUI>()?.Refresh();
                        }
                    }
                }
            }
            // Drop to world (remove from inventory)
            else if (source == DragDropManager.DragSource.Inventory && target == DragDropManager.DragSource.World)
            {
                var slot = gm.Player.Inventory.GetSlot(sourceSlot);
                if (slot != null)
                {
                    gm.Player.Inventory.RemoveItem(slot.ItemId, slot.Quantity);
                    NotificationUI.Instance?.Show($"Dropped {slot.ItemId.Replace("_", " ")}", Color.yellow);
                    Refresh();
                }
            }
        }

        private void OnEnable()
        {
            Refresh();
        }

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        /// <summary>
        /// Construct the entire inventory panel hierarchy from code.
        /// Right-side panel: header, scrollable 6x5 grid of 64x64 item slots.
        /// </summary>
        private void _buildUI()
        {
            // -- Root panel: centered on screen, 420 x 600
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "InventoryPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(420, 600), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);

            _panel = panelRt.gameObject;

            // Vertical layout for header + grid area
            UIHelper.AddVerticalLayout(panelRt, spacing: 4f,
                padding: new RectOffset(6, 6, 6, 6));

            // -- Header row
            UIHelper.CreateHeaderRow(panelRt, "INVENTORY", "[Tab / ESC]", height: 38f);

            // -- Divider
            UIHelper.CreateDivider(panelRt, 2f);

            // -- Scroll view wrapping the slot grid
            var scrollPanel = UIHelper.CreatePanel(
                panelRt, "ScrollArea", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            // Let the layout group size this to fill remaining space
            var scrollLE = scrollPanel.gameObject.AddComponent<LayoutElement>();
            scrollLE.flexibleHeight = 1f;

            var (scrollRect, content) = UIHelper.CreateScrollView(
                scrollPanel, "SlotScroll", UIHelper.COLOR_TRANSPARENT);
            _scrollRect = scrollRect;
            _scrollContent = content;

            // Replace default VerticalLayoutGroup on content with a GridLayoutGroup.
            // Must use DestroyImmediate — Object.Destroy is deferred to end of frame,
            // so AddComponent<GridLayoutGroup> would fail ("already has LayoutGroup").
            var existingVLG = content.GetComponent<VerticalLayoutGroup>();
            if (existingVLG != null) Object.DestroyImmediate(existingVLG);

            _gridLayout = content.gameObject.AddComponent<GridLayoutGroup>();
            _gridLayout.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            _gridLayout.constraintCount = _columns;
            _gridLayout.cellSize = new Vector2(64, 64);
            _gridLayout.spacing = new Vector2(4, 4);
            _gridLayout.padding = new RectOffset(4, 4, 4, 4);
            _gridLayout.childAlignment = TextAnchor.UpperCenter;

            // Store the content transform as the slot container
            _slotContainer = content;
        }

        /// <summary>Refresh all slots from Character inventory.</summary>
        public void Refresh()
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null || _slots == null) return;

            var inventory = gm.Player.Inventory;
            var allSlots = inventory.GetAllSlots();

            for (int i = 0; i < _slots.Length; i++)
            {
                if (i < allSlots.Length && allSlots[i] != null)
                {
                    _slots[i].SetItem(allSlots[i].ItemId, allSlots[i].Quantity);
                }
                else
                {
                    _slots[i].Clear();
                }
            }
        }

        private void _createSlots()
        {
            int totalSlots = GameConfig.DefaultInventorySlots;
            _slots = new InventorySlot[totalSlots];

            for (int i = 0; i < totalSlots; i++)
            {
                GameObject slotGo;
                if (_slotPrefab != null)
                {
                    slotGo = Instantiate(_slotPrefab, _slotContainer ?? transform);
                }
                else
                {
                    // Use UIHelper.CreateItemSlot for programmatic slot creation
                    var (root, bg, icon, qty, border) = UIHelper.CreateItemSlot(
                        _slotContainer ?? transform, $"Slot_{i}", 64f);
                    slotGo = root.gameObject;
                }

                var slot = slotGo.GetComponent<InventorySlot>();
                if (slot == null) slot = slotGo.AddComponent<InventorySlot>();
                slot.Initialize(i, DragDropManager.DragSource.Inventory);
                _slots[i] = slot;
            }
        }

        private void _onToggle()
        {
            _stateManager?.TogglePanel(GameState.InventoryOpen);
        }

        private void _onStateChanged(GameState oldState, GameState newState)
        {
            _setVisible(newState == GameState.InventoryOpen);
            if (newState == GameState.InventoryOpen)
                Refresh();
        }

        private void _setVisible(bool visible)
        {
            if (_panel != null) _panel.SetActive(visible);
            else gameObject.SetActive(visible);
        }
    }

    /// <summary>
    /// Single inventory slot — icon, quantity, drag/drop source and target.
    /// </summary>
    public class InventorySlot : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler,
        IBeginDragHandler, IDragHandler, IEndDragHandler, IDropHandler, IPointerClickHandler
    {
        [SerializeField] private Image _iconImage;
        [SerializeField] private TextMeshProUGUI _quantityText;
        [SerializeField] private Image _backgroundImage;

        private int _slotIndex;
        private string _itemId;
        private int _quantity;
        private DragDropManager.DragSource _sourceType;

        public void Initialize(int index, DragDropManager.DragSource sourceType)
        {
            _slotIndex = index;
            _sourceType = sourceType;

            if (_iconImage == null) _iconImage = GetComponentInChildren<Image>();
            if (_quantityText == null) _quantityText = GetComponentInChildren<TextMeshProUGUI>();
        }

        public void SetItem(string itemId, int quantity)
        {
            _itemId = itemId;
            _quantity = quantity;

            if (_iconImage != null)
            {
                if (SpriteDatabase.Instance != null)
                    _iconImage.sprite = SpriteDatabase.Instance.GetItemSprite(itemId);
                _iconImage.enabled = true;
            }

            if (_quantityText != null)
            {
                _quantityText.text = quantity > 1 ? quantity.ToString() : "";
                _quantityText.enabled = quantity > 1;
            }
        }

        public void Clear()
        {
            _itemId = null;
            _quantity = 0;
            if (_iconImage != null) _iconImage.enabled = false;
            if (_quantityText != null) _quantityText.enabled = false;
        }

        // Drag & Drop
        public void OnBeginDrag(PointerEventData eventData)
        {
            if (string.IsNullOrEmpty(_itemId)) return;
            DragDropManager.Instance?.BeginDrag(
                _sourceType, _slotIndex, _itemId, _quantity,
                _iconImage?.sprite
            );
        }

        public void OnDrag(PointerEventData eventData) { } // Handled by DragDropManager

        public void OnEndDrag(PointerEventData eventData)
        {
            if (DragDropManager.Instance != null && DragDropManager.Instance.IsDragging)
                DragDropManager.Instance.CancelDrag();
        }

        public void OnDrop(PointerEventData eventData)
        {
            DragDropManager.Instance?.CompleteDrop(_sourceType, _slotIndex);
        }

        // Tooltips
        public void OnPointerEnter(PointerEventData eventData)
        {
            if (string.IsNullOrEmpty(_itemId)) return;

            // Build detailed tooltip text
            string displayName = _itemId.Replace("_", " ");
            string details = "";

            // Check if it's a material
            var matDb = MaterialDatabase.Instance;
            if (matDb != null)
            {
                var mat = matDb.GetMaterial(_itemId);
                if (mat != null)
                {
                    details = $"T{mat.Tier} {mat.Category ?? "material"}\n";
                    if (!string.IsNullOrEmpty(mat.Rarity))
                        details += $"Rarity: {mat.Rarity}\n";
                }
            }

            // Check if it's equipment
            var eqDb = EquipmentDatabase.Instance;
            if (eqDb != null && eqDb.IsEquipment(_itemId))
            {
                var eq = eqDb.CreateEquipmentFromId(_itemId);
                if (eq != null)
                {
                    if (eq.DamageMax > 0)
                        details += $"Damage: {eq.DamageMin}-{eq.DamageMax}\n";
                    if (eq.Defense > 0)
                        details += $"Defense: {eq.Defense}\n";
                    if (eq.DurabilityMax > 0)
                        details += $"Dur: {eq.DurabilityCurrent}/{eq.DurabilityMax}\n";
                }
            }

            if (_quantity > 1) details += $"Qty: {_quantity}";

            TooltipRenderer.Instance?.Show(displayName, details.TrimEnd('\n'), eventData.position);
        }

        public void OnPointerExit(PointerEventData eventData)
        {
            TooltipRenderer.Instance?.Hide();
        }

        public void OnPointerClick(PointerEventData eventData)
        {
            // Right-click to use/equip
            if (eventData.button == PointerEventData.InputButton.Right && !string.IsNullOrEmpty(_itemId))
            {
                var gm = GameManager.Instance;
                if (gm?.Player == null) return;

                // Try to equip if it's equipment
                var eqDb = EquipmentDatabase.Instance;
                if (eqDb != null && eqDb.IsEquipment(_itemId))
                {
                    var eq = eqDb.CreateEquipmentFromId(_itemId);
                    if (eq != null)
                    {
                        var (oldItem, status) = gm.Player.Equipment.Equip(eq);
                        if (status == "OK")
                        {
                            gm.Player.Inventory.RemoveItem(_itemId, 1);
                            if (oldItem != null)
                                gm.Player.Inventory.AddItem(oldItem.ItemId, 1);
                            NotificationUI.Instance?.Show($"Equipped {_itemId.Replace("_", " ")}", Color.green);

                            // Refresh both inventory and equipment UIs
                            var invUI = FindFirstObjectByType<InventoryUI>();
                            invUI?.Refresh();
                            var eqUI = FindFirstObjectByType<EquipmentUI>();
                            eqUI?.Refresh();
                        }
                        else
                        {
                            NotificationUI.Instance?.Show(status, Color.yellow);
                        }
                        return;
                    }
                }

                // Otherwise try to use as consumable
                NotificationUI.Instance?.Show($"Used {_itemId.Replace("_", " ")}", Color.white);
            }
        }
    }
}
