// ============================================================================
// Game1.Unity.UI.EquipmentUI
// Migrated from: rendering/renderer.py (lines 5720-5987: render_equipment_ui)
//              + game_engine.py (lines 1573-1700: equip clicks)
// Migration phase: 6
// Date: 2026-02-13
//
// 8-slot equipment panel with durability display and equip/unequip.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
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

        [System.Serializable]
        public class EquipmentSlotUI
        {
            public Image IconImage;
            public Image SlotBackground;
            public Image DurabilityBar;
            public TextMeshProUGUI SlotLabel;
            public string SlotName; // "MainHand", "OffHand", etc.
        }

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
            _inputManager = FindFirstObjectByType<InputManager>();

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

        /// <summary>Refresh all slots from Character equipment.</summary>
        public void Refresh()
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null || _slots == null) return;

            var equipment = gm.Player.Equipment;

            foreach (var slot in _slots)
            {
                if (slot == null) continue;

                var equipped = equipment.GetEquipped(slot.SlotName);

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
                        float durPct = equipped.MaxDurability > 0
                            ? (float)equipped.Durability / equipped.MaxDurability
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

        private void _setVisible(bool visible)
        {
            if (_panel != null) _panel.SetActive(visible);
            else gameObject.SetActive(visible);
        }
    }
}
