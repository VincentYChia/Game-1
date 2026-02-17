// ============================================================================
// Game1.Unity.Core.InputManager
// Migrated from: core/game_engine.py (lines 488-1165: handle_events)
// Migration phase: 6
// Date: 2026-02-13
//
// Replaces Python's pygame event polling with Unity Input System.
// Routes input to appropriate handlers based on current GameState.
// ============================================================================

using System;
using UnityEngine;
using UnityEngine.InputSystem;
using Game1.Core;
using Game1.Data.Models;
using Game1.Unity.Utilities;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Central input manager. Routes keyboard/mouse input based on GameState.
    /// Uses Unity's new Input System with action maps for context switching.
    /// </summary>
    public class InputManager : MonoBehaviour
    {
        // ====================================================================
        // Inspector References
        // ====================================================================

        [SerializeField] private GameStateManager _stateManager;
        [SerializeField] private PlayerInput _playerInput;

        // ====================================================================
        // Events — UI components subscribe to receive input
        // ====================================================================

        /// <summary>Movement input (WASD/arrows). Args: Vector2 direction.</summary>
        public event Action<Vector2> OnMoveInput;

        /// <summary>Interact key pressed (E).</summary>
        public event Action OnInteract;

        /// <summary>Primary attack (left click in world).</summary>
        public event Action<Vector3> OnPrimaryAttack;

        /// <summary>Secondary action (right click). Args: world position.</summary>
        public event Action<Vector3> OnSecondaryAction;

        /// <summary>UI click at screen position.</summary>
        public event Action<Vector2> OnUIClick;

        /// <summary>Escape pressed.</summary>
        public event Action OnEscape;

        /// <summary>Inventory toggle (Tab).</summary>
        public event Action OnToggleInventory;

        /// <summary>Equipment toggle.</summary>
        public event Action OnToggleEquipment;

        /// <summary>Map toggle (M).</summary>
        public event Action OnToggleMap;

        /// <summary>Encyclopedia toggle (J).</summary>
        public event Action OnToggleEncyclopedia;

        /// <summary>Stats toggle (C).</summary>
        public event Action OnToggleStats;

        /// <summary>Skills toggle (K).</summary>
        public event Action OnToggleSkills;

        /// <summary>Skill hotbar key pressed (1-5). Args: slot index (0-4).</summary>
        public event Action<int> OnSkillActivate;

        /// <summary>Crafting action key (Spacebar in minigame).</summary>
        public event Action OnCraftAction;

        /// <summary>Debug key pressed. Args: key name (F1-F7).</summary>
        public event Action<string> OnDebugKey;

        /// <summary>Scroll wheel. Args: delta.</summary>
        public event Action<float> OnScroll;

        /// <summary>Mouse position in screen space, updated every frame.</summary>
        public Vector2 MousePosition { get; private set; }

        /// <summary>Mouse position in world space (XZ plane).</summary>
        public Vector3 MouseWorldPosition { get; private set; }

        // ====================================================================
        // Input Actions (bound in Unity Editor or via code)
        // ====================================================================

        private InputAction _moveAction;
        private InputAction _interactAction;
        private InputAction _attackAction;
        private InputAction _secondaryAction;
        private InputAction _escapeAction;
        private InputAction _inventoryAction;
        private InputAction _mapAction;
        private InputAction _encyclopediaAction;
        private InputAction _statsAction;
        private InputAction _skillsAction;
        private InputAction _craftAction;
        private InputAction _scrollAction;
        private InputAction _skill1Action;
        private InputAction _skill2Action;
        private InputAction _skill3Action;
        private InputAction _skill4Action;
        private InputAction _skill5Action;

        // Debug actions
        private InputAction _debugF1;
        private InputAction _debugF2;
        private InputAction _debugF3;
        private InputAction _debugF4;
        private InputAction _debugF7;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Awake()
        {
            if (_stateManager == null)
                _stateManager = FindFirstObjectByType<GameStateManager>();
            _setupInputActions();
        }

        private void OnEnable()
        {
            _bindActions();
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onGameStateChanged;
        }

        private void OnDisable()
        {
            _unbindActions();
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onGameStateChanged;
        }

        // ====================================================================
        // Frame Update — Continuous Input
        // ====================================================================

        private void Update()
        {
            // Track mouse position
            if (Mouse.current != null)
            {
                MousePosition = Mouse.current.position.ReadValue();

                // Convert to world position via camera raycast (XZ plane)
                if (Camera.main != null)
                {
                    var ray = Camera.main.ScreenPointToRay(MousePosition);
                    var plane = new Plane(Vector3.up, Vector3.zero);
                    if (plane.Raycast(ray, out float distance))
                    {
                        MouseWorldPosition = ray.GetPoint(distance);
                    }
                }
            }

            // Continuous movement input (polled every frame)
            if (_moveAction != null && _stateManager != null && _stateManager.IsPlaying)
            {
                var moveValue = _moveAction.ReadValue<Vector2>();
                if (moveValue.sqrMagnitude > 0.01f)
                {
                    OnMoveInput?.Invoke(moveValue);
                }
            }
        }

        // ====================================================================
        // Input Action Setup
        // ====================================================================

        private void _setupInputActions()
        {
            // If PlayerInput component is assigned, use its action map
            if (_playerInput != null && _playerInput.actions != null)
            {
                _moveAction = _playerInput.actions.FindAction("Move");
                _interactAction = _playerInput.actions.FindAction("Interact");
                _attackAction = _playerInput.actions.FindAction("Attack");
                _secondaryAction = _playerInput.actions.FindAction("SecondaryAttack");
                _escapeAction = _playerInput.actions.FindAction("Escape");
                _inventoryAction = _playerInput.actions.FindAction("ToggleInventory");
                _mapAction = _playerInput.actions.FindAction("ToggleMap");
                _encyclopediaAction = _playerInput.actions.FindAction("ToggleEncyclopedia");
                _statsAction = _playerInput.actions.FindAction("ToggleStats");
                _skillsAction = _playerInput.actions.FindAction("ToggleSkills");
                _craftAction = _playerInput.actions.FindAction("CraftAction");
                _scrollAction = _playerInput.actions.FindAction("Zoom");
                _skill1Action = _playerInput.actions.FindAction("Skill1");
                _skill2Action = _playerInput.actions.FindAction("Skill2");
                _skill3Action = _playerInput.actions.FindAction("Skill3");
                _skill4Action = _playerInput.actions.FindAction("Skill4");
                _skill5Action = _playerInput.actions.FindAction("Skill5");
                _debugF1 = _playerInput.actions.FindAction("DebugToggle");
                _debugF2 = _playerInput.actions.FindAction("LearnAllSkills");
                _debugF3 = _playerInput.actions.FindAction("GrantAllTitles");
                _debugF4 = _playerInput.actions.FindAction("MaxLevel");
                _debugF7 = _playerInput.actions.FindAction("InfiniteDurability");
                return;
            }

            // Fallback: create inline actions for testing without InputActionAsset
            _moveAction = new InputAction("Move", InputActionType.Value);
            _moveAction.AddCompositeBinding("2DVector")
                .With("Up", "<Keyboard>/w")
                .With("Down", "<Keyboard>/s")
                .With("Left", "<Keyboard>/a")
                .With("Right", "<Keyboard>/d");

            _interactAction = new InputAction("Interact", InputActionType.Button, "<Keyboard>/e");
            _attackAction = new InputAction("Attack", InputActionType.Button, "<Mouse>/leftButton");
            _secondaryAction = new InputAction("SecondaryAttack", InputActionType.Button, "<Mouse>/rightButton");
            _escapeAction = new InputAction("Escape", InputActionType.Button, "<Keyboard>/escape");
            _inventoryAction = new InputAction("ToggleInventory", InputActionType.Button, "<Keyboard>/tab");
            _mapAction = new InputAction("ToggleMap", InputActionType.Button, "<Keyboard>/m");
            _encyclopediaAction = new InputAction("ToggleEncyclopedia", InputActionType.Button, "<Keyboard>/j");
            _statsAction = new InputAction("ToggleStats", InputActionType.Button, "<Keyboard>/c");
            _skillsAction = new InputAction("ToggleSkills", InputActionType.Button, "<Keyboard>/k");
            _craftAction = new InputAction("CraftAction", InputActionType.Button, "<Keyboard>/space");
            _scrollAction = new InputAction("Scroll", InputActionType.Value, "<Mouse>/scroll/y");

            _skill1Action = new InputAction("Skill1", InputActionType.Button, "<Keyboard>/1");
            _skill2Action = new InputAction("Skill2", InputActionType.Button, "<Keyboard>/2");
            _skill3Action = new InputAction("Skill3", InputActionType.Button, "<Keyboard>/3");
            _skill4Action = new InputAction("Skill4", InputActionType.Button, "<Keyboard>/4");
            _skill5Action = new InputAction("Skill5", InputActionType.Button, "<Keyboard>/5");

            _debugF1 = new InputAction("DebugF1", InputActionType.Button, "<Keyboard>/f1");
            _debugF2 = new InputAction("DebugF2", InputActionType.Button, "<Keyboard>/f2");
            _debugF3 = new InputAction("DebugF3", InputActionType.Button, "<Keyboard>/f3");
            _debugF4 = new InputAction("DebugF4", InputActionType.Button, "<Keyboard>/f4");
            _debugF7 = new InputAction("DebugF7", InputActionType.Button, "<Keyboard>/f7");

            // Enable all actions
            _moveAction.Enable();
            _interactAction.Enable();
            _attackAction.Enable();
            _secondaryAction.Enable();
            _escapeAction.Enable();
            _inventoryAction.Enable();
            _mapAction.Enable();
            _encyclopediaAction.Enable();
            _statsAction.Enable();
            _skillsAction.Enable();
            _craftAction.Enable();
            _scrollAction.Enable();
            _skill1Action.Enable();
            _skill2Action.Enable();
            _skill3Action.Enable();
            _skill4Action.Enable();
            _skill5Action.Enable();
            _debugF1.Enable();
            _debugF2.Enable();
            _debugF3.Enable();
            _debugF4.Enable();
            _debugF7.Enable();
        }

        // ====================================================================
        // Action Bindings
        // ====================================================================

        private void _bindActions()
        {
            if (_interactAction != null) _interactAction.performed += _onInteract;
            if (_attackAction != null) _attackAction.performed += _onAttack;
            if (_secondaryAction != null) _secondaryAction.performed += _onSecondary;
            if (_escapeAction != null) _escapeAction.performed += _onEscape;
            if (_inventoryAction != null) _inventoryAction.performed += _onInventory;
            if (_mapAction != null) _mapAction.performed += _onMap;
            if (_encyclopediaAction != null) _encyclopediaAction.performed += _onEncyclopedia;
            if (_statsAction != null) _statsAction.performed += _onStats;
            if (_skillsAction != null) _skillsAction.performed += _onSkills;
            if (_craftAction != null) _craftAction.performed += _onCraftAction;
            if (_scrollAction != null) _scrollAction.performed += _onScroll;

            if (_skill1Action != null) _skill1Action.performed += ctx => OnSkillActivate?.Invoke(0);
            if (_skill2Action != null) _skill2Action.performed += ctx => OnSkillActivate?.Invoke(1);
            if (_skill3Action != null) _skill3Action.performed += ctx => OnSkillActivate?.Invoke(2);
            if (_skill4Action != null) _skill4Action.performed += ctx => OnSkillActivate?.Invoke(3);
            if (_skill5Action != null) _skill5Action.performed += ctx => OnSkillActivate?.Invoke(4);

            if (_debugF1 != null) _debugF1.performed += ctx => OnDebugKey?.Invoke("F1");
            if (_debugF2 != null) _debugF2.performed += ctx => OnDebugKey?.Invoke("F2");
            if (_debugF3 != null) _debugF3.performed += ctx => OnDebugKey?.Invoke("F3");
            if (_debugF4 != null) _debugF4.performed += ctx => OnDebugKey?.Invoke("F4");
            if (_debugF7 != null) _debugF7.performed += ctx => OnDebugKey?.Invoke("F7");
        }

        private void _unbindActions()
        {
            if (_interactAction != null) _interactAction.performed -= _onInteract;
            if (_attackAction != null) _attackAction.performed -= _onAttack;
            if (_secondaryAction != null) _secondaryAction.performed -= _onSecondary;
            if (_escapeAction != null) _escapeAction.performed -= _onEscape;
            if (_inventoryAction != null) _inventoryAction.performed -= _onInventory;
            if (_mapAction != null) _mapAction.performed -= _onMap;
            if (_encyclopediaAction != null) _encyclopediaAction.performed -= _onEncyclopedia;
            if (_statsAction != null) _statsAction.performed -= _onStats;
            if (_skillsAction != null) _skillsAction.performed -= _onSkills;
            if (_craftAction != null) _craftAction.performed -= _onCraftAction;
            if (_scrollAction != null) _scrollAction.performed -= _onScroll;
        }

        // ====================================================================
        // Input Handlers
        // ====================================================================

        private void _onInteract(InputAction.CallbackContext ctx)
        {
            if (_stateManager != null && _stateManager.IsPlaying)
                OnInteract?.Invoke();
        }

        private void _onAttack(InputAction.CallbackContext ctx)
        {
            if (_stateManager == null || _stateManager.IsPlaying)
                OnPrimaryAttack?.Invoke(MouseWorldPosition);
            else
                OnUIClick?.Invoke(MousePosition);
        }

        private void _onSecondary(InputAction.CallbackContext ctx)
        {
            if (_stateManager == null || _stateManager.IsPlaying)
                OnSecondaryAction?.Invoke(MouseWorldPosition);
        }

        private void _onEscape(InputAction.CallbackContext ctx)
        {
            OnEscape?.Invoke();
            _stateManager?.HandleEscape();
        }

        private void _onInventory(InputAction.CallbackContext ctx) => OnToggleInventory?.Invoke();
        private void _onMap(InputAction.CallbackContext ctx) => OnToggleMap?.Invoke();
        private void _onEncyclopedia(InputAction.CallbackContext ctx) => OnToggleEncyclopedia?.Invoke();
        private void _onStats(InputAction.CallbackContext ctx) => OnToggleStats?.Invoke();
        private void _onSkills(InputAction.CallbackContext ctx) => OnToggleSkills?.Invoke();
        private void _onCraftAction(InputAction.CallbackContext ctx) => OnCraftAction?.Invoke();

        private void _onScroll(InputAction.CallbackContext ctx)
        {
            float scrollValue = ctx.ReadValue<float>();
            if (Mathf.Abs(scrollValue) > 0.01f)
                OnScroll?.Invoke(scrollValue);
        }

        // ====================================================================
        // State Change Handler
        // ====================================================================

        private void _onGameStateChanged(GameState oldState, GameState newState)
        {
            // Could enable/disable action maps here if using InputActionAsset
            // For now, the event handlers check state before dispatching
        }
    }
}
