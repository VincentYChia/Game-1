// ============================================================================
// Game1.Unity.UI.DragDropManager
// Migrated from: game_engine.py (lines 5700-6544: mouse drag/release)
// Migration phase: 6
// Date: 2026-02-13
//
// Central drag-and-drop state manager.
// Renders ghost icon on overlay Canvas during drag.
// ============================================================================

using System;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Shared drag-and-drop manager for inventory, equipment, and crafting.
    /// Renders a ghost icon following the mouse during drag.
    /// Uses Unity's new Input System and subscribes to InputManager events.
    /// </summary>
    public class DragDropManager : MonoBehaviour
    {
        public static DragDropManager Instance { get; private set; }

        [Header("Ghost Icon")]
        [SerializeField] private Image _ghostIcon;
        [SerializeField] private CanvasGroup _ghostCanvasGroup;
        [SerializeField] private RectTransform _ghostTransform;

        // ====================================================================
        // Drag State
        // ====================================================================

        /// <summary>Whether a drag is currently in progress.</summary>
        public bool IsDragging { get; private set; }

        /// <summary>The source slot type of the current drag.</summary>
        public DragSource Source { get; private set; }

        /// <summary>Source slot index of the dragged item.</summary>
        public int SourceSlotIndex { get; private set; }

        /// <summary>Item ID being dragged.</summary>
        public string DraggedItemId { get; private set; }

        /// <summary>Quantity being dragged.</summary>
        public int DraggedQuantity { get; private set; }

        // ====================================================================
        // Events
        // ====================================================================

        /// <summary>Raised when a drag-and-drop completes. Args: (source, sourceSlot, target, targetSlot).</summary>
        public event Action<DragSource, int, DragSource, int> OnDropCompleted;

        /// <summary>Raised when a drag is canceled.</summary>
        public event Action OnDragCanceled;

        public enum DragSource
        {
            None,
            Inventory,
            Equipment,
            CraftingGrid,
            Chest,
            World
        }

        // ====================================================================
        // InputManager reference
        // ====================================================================

        private InputManager _inputManager;

        private void Awake()
        {
            Instance = this;
            _setGhostVisible(false);
        }

        private void Start()
        {
            _inputManager = FindFirstObjectByType<InputManager>();
            if (_inputManager != null)
            {
                _inputManager.OnEscape += _onEscapePressed;
            }
        }

        /// <summary>Start a drag operation.</summary>
        public void BeginDrag(DragSource source, int slotIndex, string itemId, int quantity, Sprite icon)
        {
            IsDragging = true;
            Source = source;
            SourceSlotIndex = slotIndex;
            DraggedItemId = itemId;
            DraggedQuantity = quantity;

            if (_ghostIcon != null && icon != null)
            {
                _ghostIcon.sprite = icon;
                _setGhostVisible(true);
            }
        }

        /// <summary>Complete a drop on a target.</summary>
        public void CompleteDrop(DragSource target, int targetSlotIndex)
        {
            if (!IsDragging) return;

            OnDropCompleted?.Invoke(Source, SourceSlotIndex, target, targetSlotIndex);
            _endDrag();
        }

        /// <summary>Cancel the current drag operation.</summary>
        public void CancelDrag()
        {
            if (!IsDragging) return;
            OnDragCanceled?.Invoke();
            _endDrag();
        }

        /// <summary>Drop item into the world (remove from inventory).</summary>
        public void DropToWorld()
        {
            if (!IsDragging) return;
            OnDropCompleted?.Invoke(Source, SourceSlotIndex, DragSource.World, -1);
            _endDrag();
        }

        private void _endDrag()
        {
            IsDragging = false;
            Source = DragSource.None;
            SourceSlotIndex = -1;
            DraggedItemId = null;
            DraggedQuantity = 0;
            _setGhostVisible(false);
        }

        // ====================================================================
        // InputManager event handler for Escape
        // ====================================================================

        private void _onEscapePressed()
        {
            if (IsDragging)
            {
                CancelDrag();
            }
        }

        private void Update()
        {
            // Move ghost icon with mouse using new Input System
            if (IsDragging && _ghostTransform != null)
            {
                _ghostTransform.position = Mouse.current?.position.ReadValue() ?? Vector2.zero;
            }

            // Cancel on right-click using new Input System
            if (IsDragging)
            {
                if (Mouse.current?.rightButton.wasPressedThisFrame == true)
                {
                    CancelDrag();
                }
            }
        }

        private void _setGhostVisible(bool visible)
        {
            if (_ghostIcon != null) _ghostIcon.enabled = visible;
            if (_ghostCanvasGroup != null) _ghostCanvasGroup.alpha = visible ? 0.7f : 0f;
        }

        private void OnDestroy()
        {
            // Unsubscribe from InputManager events
            if (_inputManager != null)
            {
                _inputManager.OnEscape -= _onEscapePressed;
            }

            if (Instance == this) Instance = null;
        }
    }
}
