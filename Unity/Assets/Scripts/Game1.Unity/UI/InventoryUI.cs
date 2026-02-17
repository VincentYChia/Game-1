// ============================================================================
// Game1.Unity.UI.InventoryUI
// Migrated from: rendering/renderer.py (lines 3977-4238: render_inventory_panel)
//              + game_engine.py (lines 6544-7000: drop logic)
// Migration phase: 6
// Date: 2026-02-13
//
// 30-slot inventory grid with drag-and-drop, tooltips, and quantity display.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using TMPro;
using Game1.Core;
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
        [SerializeField] private int _rows = 5;

        [Header("Slot Prefab")]
        [SerializeField] private GameObject _slotPrefab;
        [SerializeField] private Transform _slotContainer;

        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        private InventorySlot[] _slots;
        private GameStateManager _stateManager;
        private InputManager _inputManager;

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
            _inputManager = FindFirstObjectByType<InputManager>();

            if (_inputManager != null)
                _inputManager.OnToggleInventory += _onToggle;

            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            _createSlots();
            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_inputManager != null)
                _inputManager.OnToggleInventory -= _onToggle;
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onStateChanged;
        }

        private void OnEnable()
        {
            Refresh();
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
                    slotGo = new GameObject($"Slot_{i}");
                    slotGo.transform.SetParent(_slotContainer ?? transform, false);
                    slotGo.AddComponent<Image>().color = (Color)ColorConverter.UISlotEmpty;
                    var rt = slotGo.GetComponent<RectTransform>();
                    rt.sizeDelta = new Vector2(40, 40);
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
            TooltipRenderer.Instance?.Show(_itemId, $"Quantity: {_quantity}", eventData.position);
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
                // TODO: Use item or open context menu
            }
        }
    }
}
