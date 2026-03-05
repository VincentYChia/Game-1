// ============================================================================
// Game1.Unity.UI.EquipmentUI
// Migrated from: rendering/renderer.py (lines 5720-5987: render_equipment_ui)
//              + game_engine.py (lines 1573-1700: equip clicks)
// Migration phase: 6
// Date: 2026-02-13
//
// 8-slot equipment panel with durability display and equip/unequip.
// Self-building: if _panel is null at startup, _buildUI() constructs the
// entire hierarchy from code using UIHelper (no prefab/scene setup needed).
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using TMPro;
using Game1.Core;
using Game1.Data.Enums;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Equipment panel — 8 equipment slots (MainHand, OffHand, Head, Chest, Legs, Feet, Hands, Accessory).
    /// Supports drag-and-drop from inventory.
    /// </summary>
    public class EquipmentUI : MonoBehaviour
    {
        [Header("Slot References")]
        [SerializeField] private EquipmentSlotUI[] _slots;

        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Stats Display")]
        [SerializeField] private TextMeshProUGUI _totalDamageText;
        [SerializeField] private TextMeshProUGUI _totalDefenseText;

        private GameStateManager _stateManager;
        private InputManager _inputManager;

        // Stats summary references populated by _buildUI()
        private Text _totalDamageLabel;
        private Text _totalDefenseLabel;
        private Text _statBonusesLabel;

        [System.Serializable]
        public class EquipmentSlotUI
        {
            public Image IconImage;
            public Image SlotBackground;
            public Image DurabilityBar;
            public TextMeshProUGUI SlotLabel;
            public string SlotName; // "MainHand", "OffHand", etc.

            // Additional references for programmatic construction
            [System.NonSerialized] public Text SlotLabelLegacy;
            [System.NonSerialized] public Image DurabilityBackground;
        }

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
            _inputManager = InputManager.Instance ?? FindFirstObjectByType<InputManager>();

            if (_inputManager != null)
                _inputManager.OnToggleEquipment += _onToggle;
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            // Subscribe to equipment change events
            GameEvents.OnEquipmentChanged += _onEquipmentChanged;
            GameEvents.OnEquipmentRemoved += _onEquipmentRemoved;

            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_inputManager != null)
                _inputManager.OnToggleEquipment -= _onToggle;
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onStateChanged;
            GameEvents.OnEquipmentChanged -= _onEquipmentChanged;
            GameEvents.OnEquipmentRemoved -= _onEquipmentRemoved;
        }

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        /// <summary>
        /// Construct the entire equipment panel hierarchy from code.
        /// Right-side panel with body-like slot layout (72x72 each) and stats summary.
        /// Layout:
        ///   Row 1: Head (centered)
        ///   Row 2: MainHand | Chest | OffHand
        ///   Row 3: Gauntlets | Legs | Accessory
        ///   Row 4: Boots (centered)
        ///   Divider
        ///   Stats summary (total damage, total defense)
        /// </summary>
        private void _buildUI()
        {
            const float slotSize = 72f;
            const float slotSpacing = 8f;
            const float labelHeight = 18f;

            // -- Root panel: centered on screen, 340 x 580
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "EquipmentPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(340, 580), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);

            _panel = panelRt.gameObject;

            var vlg = UIHelper.AddVerticalLayout(panelRt, spacing: 4f,
                padding: new RectOffset(8, 8, 6, 6));

            // -- Header
            UIHelper.CreateHeaderRow(panelRt, "EQUIPMENT", "[I / ESC]", height: 38f);

            // -- Divider
            UIHelper.CreateDivider(panelRt, 2f);

            // -- Slot grid area (free-positioned slots inside a sized container)
            // Total width for 3 columns: 3 * 72 + 2 * 8 = 232
            // Total height for 4 rows:   4 * (72 + 18) + 3 * 8 = 384
            float gridWidth = 3 * slotSize + 2 * slotSpacing;
            float gridHeight = 4 * (slotSize + labelHeight) + 3 * slotSpacing;

            var gridContainer = UIHelper.CreatePanel(
                panelRt, "SlotGrid", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(gridContainer.gameObject, gridHeight + 16f);

            // Disable the image component since we want transparent
            var gridImg = gridContainer.GetComponent<Image>();
            if (gridImg != null) gridImg.raycastTarget = false;

            // Helper: place a single equipment slot at a grid position (col 0-2, row 0-3)
            _slots = new EquipmentSlotUI[8];

            float startX = -(gridWidth * 0.5f);
            float startY = (gridHeight * 0.5f);

            void PlaceSlot(int index, string slotName, string label, int col, int row)
            {
                float cellW = slotSize + slotSpacing;
                float cellH = slotSize + labelHeight + slotSpacing;
                float x = startX + col * cellW + slotSize * 0.5f;
                float y = startY - row * cellH - slotSize * 0.5f;

                // Create the slot visual using UIHelper.CreateItemSlot
                var (root, bg, icon, qty, border) = UIHelper.CreateItemSlot(
                    gridContainer, $"Slot_{slotName}", slotSize);
                root.anchorMin = new Vector2(0.5f, 0.5f);
                root.anchorMax = new Vector2(0.5f, 0.5f);
                root.anchoredPosition = new Vector2(x, y);

                // Durability bar background (below icon, inside slot)
                var durBgImg = UIHelper.CreateImage(root, "DurabilityBg",
                    new Color(0.1f, 0.1f, 0.1f, 0.8f), new Vector2(slotSize - 8, 6));
                var durBgRt = durBgImg.rectTransform;
                durBgRt.anchorMin = new Vector2(0.5f, 0f);
                durBgRt.anchorMax = new Vector2(0.5f, 0f);
                durBgRt.pivot = new Vector2(0.5f, 0f);
                durBgRt.anchoredPosition = new Vector2(0, 2);

                // Durability fill bar
                var durFillImg = UIHelper.CreateImage(durBgImg.transform, "DurabilityFill",
                    Color.green, new Vector2(slotSize - 12, 4));
                durFillImg.type = Image.Type.Filled;
                durFillImg.fillMethod = Image.FillMethod.Horizontal;
                durFillImg.fillAmount = 1f;
                var durFillRt = durFillImg.rectTransform;
                durFillRt.anchorMin = new Vector2(0f, 0.5f);
                durFillRt.anchorMax = new Vector2(0f, 0.5f);
                durFillRt.pivot = new Vector2(0f, 0.5f);
                durFillRt.anchoredPosition = new Vector2(2, 0);

                // Label below slot
                var lblTxt = UIHelper.CreateSizedText(
                    gridContainer, $"Label_{slotName}", label,
                    12, UIHelper.COLOR_TEXT_SECONDARY,
                    new Vector2(slotSize + 10, labelHeight),
                    new Vector2(x, y - slotSize * 0.5f - labelHeight * 0.5f - 2),
                    TextAnchor.UpperCenter);

                // Add click handler for unequipping
                var clickHandler = root.gameObject.AddComponent<EquipmentSlotClickHandler>();
                clickHandler.SlotName = slotName;
                clickHandler.EquipmentUI = this;

                // Build slot data
                var slotUI = new EquipmentSlotUI
                {
                    SlotName = slotName,
                    SlotBackground = bg,
                    IconImage = icon,
                    DurabilityBar = durFillImg,
                    DurabilityBackground = durBgImg,
                    SlotLabelLegacy = lblTxt
                };
                _slots[index] = slotUI;
            }

            // Row 1: Head (centered, col 1)
            PlaceSlot(0, "Helmet",     "Head",      1, 0);
            // Row 2: MainHand, Chest, OffHand
            PlaceSlot(1, "MainHand",   "Main Hand", 0, 1);
            PlaceSlot(2, "Chestplate", "Chest",     1, 1);
            PlaceSlot(3, "OffHand",    "Off Hand",  2, 1);
            // Row 3: Gauntlets, Legs, Accessory
            PlaceSlot(4, "Gauntlets",  "Hands",     0, 2);
            PlaceSlot(5, "Leggings",   "Legs",      1, 2);
            PlaceSlot(6, "Accessory",  "Accessory", 2, 2);
            // Row 4: Boots (centered, col 1)
            PlaceSlot(7, "Boots",      "Feet",      1, 3);

            // -- Divider
            UIHelper.CreateDivider(panelRt, 2f);

            // -- Stats summary section
            var statsPanel = UIHelper.CreatePanel(
                panelRt, "StatsSummary", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(statsPanel.gameObject, 60f);
            UIHelper.AddVerticalLayout(statsPanel, spacing: 2f,
                padding: new RectOffset(12, 12, 6, 6));

            var (dmgLabel, dmgValue) = UIHelper.CreateLabeledRow(
                statsPanel, "Total Damage:", "0", 14);
            _totalDamageLabel = dmgValue;

            var (defLabel, defValue) = UIHelper.CreateLabeledRow(
                statsPanel, "Total Defense:", "0", 14);
            _totalDefenseLabel = defValue;

            _statBonusesLabel = UIHelper.CreateText(statsPanel, "StatBonuses", "",
                12, UIHelper.COLOR_TEXT_GREEN, TextAnchor.UpperLeft);
            UIHelper.SetPreferredHeight(_statBonusesLabel.gameObject, 30f);
        }

        /// <summary>Refresh all slots from Character equipment.</summary>
        public void Refresh()
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null || _slots == null) return;

            var equipment = gm.Player.Equipment;

            foreach (var slot in _slots)
            {
                if (slot == null) continue;

                // Parse slot name string to EquipmentSlot enum
                if (!System.Enum.TryParse<EquipmentSlot>(slot.SlotName, true, out var slotEnum))
                    continue;

                var equipped = equipment.GetEquipped(slotEnum);

                if (equipped != null)
                {
                    if (slot.IconImage != null)
                    {
                        if (SpriteDatabase.Instance != null)
                            slot.IconImage.sprite = SpriteDatabase.Instance.GetItemSprite(equipped.ItemId);
                        slot.IconImage.enabled = true;
                    }

                    if (slot.DurabilityBar != null)
                    {
                        float durPct = equipped.DurabilityMax > 0
                            ? (float)equipped.DurabilityCurrent / equipped.DurabilityMax
                            : 1f;
                        slot.DurabilityBar.fillAmount = durPct;
                        slot.DurabilityBar.color = durPct > 0.5f ? Color.green : (durPct > 0.25f ? Color.yellow : Color.red);
                    }
                }
                else
                {
                    if (slot.IconImage != null)
                        slot.IconImage.enabled = false;
                    if (slot.DurabilityBar != null)
                        slot.DurabilityBar.fillAmount = 0f;
                }
            }

            // Update stats summary
            var (minDmg, maxDmg) = equipment.GetWeaponDamage(EquipmentSlot.MainHand);
            var (offMin, offMax) = equipment.GetWeaponDamage(EquipmentSlot.OffHand);
            string dmgText = offMax > 0 ? $"{minDmg}-{maxDmg} / {offMin}-{offMax}" : $"{minDmg}-{maxDmg}";
            int totalDef = equipment.GetTotalDefense();

            // Programmatic labels
            if (_totalDamageLabel != null) _totalDamageLabel.text = dmgText;
            if (_totalDefenseLabel != null) _totalDefenseLabel.text = totalDef.ToString();

            // TMP labels (inspector path)
            if (_totalDamageText != null) _totalDamageText.text = dmgText;
            if (_totalDefenseText != null) _totalDefenseText.text = totalDef.ToString();

            // Stat bonuses display
            if (_statBonusesLabel != null)
            {
                var bonuses = equipment.GetStatBonuses();
                if (bonuses != null && bonuses.Count > 0)
                {
                    var parts = new System.Collections.Generic.List<string>();
                    foreach (var kvp in bonuses)
                        parts.Add($"+{kvp.Value:F1}% {kvp.Key}");
                    _statBonusesLabel.text = string.Join("  ", parts);
                }
                else
                {
                    _statBonusesLabel.text = "";
                }
            }
        }

        private void _onToggle()
        {
            _stateManager?.TogglePanel(GameState.EquipmentOpen);
        }

        private void _onStateChanged(GameState oldState, GameState newState)
        {
            _setVisible(newState == GameState.EquipmentOpen);
            if (newState == GameState.EquipmentOpen) Refresh();
        }

        private void _onEquipmentChanged(object item, int slot) => Refresh();
        private void _onEquipmentRemoved(object item, int slot) => Refresh();

        /// <summary>Unequip an item from a slot and return it to inventory.</summary>
        public void UnequipSlot(string slotName)
        {
            var gm = GameManager.Instance;
            if (gm?.Player == null) return;

            if (!System.Enum.TryParse<EquipmentSlot>(slotName, true, out var slotEnum)) return;

            var item = gm.Player.Equipment.Unequip(slotEnum);
            if (item != null)
            {
                gm.Player.Inventory.AddItem(item.ItemId, 1);
                NotificationUI.Instance?.Show($"Unequipped {item.ItemId.Replace("_", " ")}", Color.yellow);
                Refresh();
                FindFirstObjectByType<InventoryUI>()?.Refresh();
            }
        }

        private void _setVisible(bool visible)
        {
            if (_panel != null) _panel.SetActive(visible);
            else gameObject.SetActive(visible);
        }
    }

    /// <summary>Click handler for equipment slot — right-click or shift-click to unequip.</summary>
    public class EquipmentSlotClickHandler : MonoBehaviour, IPointerClickHandler
    {
        public string SlotName;
        public EquipmentUI EquipmentUI;

        public void OnPointerClick(PointerEventData eventData)
        {
            bool shiftHeld = Keyboard.current != null && Keyboard.current.leftShiftKey.isPressed;
            if (eventData.button == PointerEventData.InputButton.Right ||
                (eventData.button == PointerEventData.InputButton.Left && shiftHeld))
            {
                EquipmentUI?.UnequipSlot(SlotName);
            }
        }
    }
}
