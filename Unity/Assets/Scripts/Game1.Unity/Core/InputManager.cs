// ============================================================================
// Game1.Unity.Core.InputManager
// Migrated from: core/game_engine.py (lines 488-1165: handle_events)
// Migration phase: 6 (reworked for first-person controls 2026-02-25)
//
// Replaces Python's pygame event polling with Unity Input System.
// Routes input to appropriate handlers based on current GameState.
// Adds mouse look (delta), cursor lock/unlock on UI state transitions.
// ============================================================================

using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Central input manager. Routes keyboard/mouse input based on GameState.
    /// Uses Unity's new Input System package (required in Player Settings).
    /// Manages cursor lock state for first-person camera.
    /// </summary>
    public class InputManager : MonoBehaviour
    {
        // ====================================================================
        // Inspector References
        // ====================================================================

        [SerializeField] private GameStateManager _stateManager;
        [SerializeField] private PlayerInput _playerInput;

        [Header("Mouse Look")]
        [SerializeField] private float _mouseSensitivity = 0.15f;
        [SerializeField] private bool _invertY = false;

        // ====================================================================
        // Events — UI components subscribe to receive input
        // ====================================================================

        public event Action<Vector2> OnMoveInput;
        public event Action<Vector2> OnMouseLook;
        public event Action OnInteract;
        public event Action<Vector3> OnPrimaryAttack;
        public event Action<Vector3> OnSecondaryAction;
        public event Action<Vector2> OnUIClick;
        public event Action OnEscape;
        public event Action OnToggleInventory;
        public event Action OnToggleEquipment;
        public event Action OnToggleMap;
        public event Action OnToggleEncyclopedia;
        public event Action OnToggleStats;
        public event Action OnToggleSkills;
        public event Action<int> OnSkillActivate;
        public event Action OnCraftAction;
        public event Action<string> OnDebugKey;
        public event Action<float> OnScroll;

        /// <summary>Mouse position in screen space, updated every frame.</summary>
        public Vector2 MousePosition { get; private set; }

        /// <summary>Mouse position in world space (XZ plane).</summary>
        public Vector3 MouseWorldPosition { get; private set; }

        /// <summary>Whether the cursor is currently locked (first-person mode).</summary>
        public bool IsCursorLocked { get; private set; }

        /// <summary>Mouse sensitivity for look.</summary>
        public float MouseSensitivity
        {
            get => _mouseSensitivity;
            set => _mouseSensitivity = value;
        }

        /// <summary>Whether Y axis is inverted for look.</summary>
        public bool InvertY
        {
            get => _invertY;
            set => _invertY = value;
        }

        // ====================================================================
        // Input Actions
        // ====================================================================

        private InputAction _moveAction;
        private InputAction _lookAction;
        private InputAction _interactAction;
        private InputAction _attackAction;
        private InputAction _secondaryAction;
        private InputAction _escapeAction;
        private InputAction _inventoryAction;
        private InputAction _equipmentAction;
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
        private InputAction _debugF1;
        private InputAction _debugF2;
        private InputAction _debugF3;
        private InputAction _debugF4;
        private InputAction _debugF5;
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
            _enableAllActions();
            _bindActions();
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onGameStateChanged;
        }

        private void OnDisable()
        {
            _unbindActions();
            _disableAllActions();
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onGameStateChanged;
        }

        // ====================================================================
        // Frame Update — Continuous Input
        // ====================================================================

        private void Update()
        {
            // Track mouse position (always, for UI)
            if (Mouse.current != null)
            {
                MousePosition = Mouse.current.position.ReadValue();

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

            // Mouse look (only when cursor is locked = gameplay mode)
            if (IsCursorLocked && _lookAction != null && _stateManager != null && _stateManager.IsPlaying)
            {
                var lookDelta = _lookAction.ReadValue<Vector2>();
                if (lookDelta.sqrMagnitude > 0.001f)
                {
                    float deltaX = lookDelta.x * _mouseSensitivity;
                    float deltaY = lookDelta.y * _mouseSensitivity * (_invertY ? 1f : -1f);
                    OnMouseLook?.Invoke(new Vector2(deltaX, deltaY));
                }
            }
        }

        // ====================================================================
        // Cursor Lock Management
        // ====================================================================

        /// <summary>Lock the cursor for first-person gameplay.</summary>
        public void LockCursor()
        {
            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
            IsCursorLocked = true;
        }

        /// <summary>Unlock the cursor for UI interaction.</summary>
        public void UnlockCursor()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            IsCursorLocked = false;
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
                _lookAction = _playerInput.actions.FindAction("Look");
                _interactAction = _playerInput.actions.FindAction("Interact");
                _attackAction = _playerInput.actions.FindAction("Attack");
                _secondaryAction = _playerInput.actions.FindAction("SecondaryAttack");
                _escapeAction = _playerInput.actions.FindAction("Escape");
                _inventoryAction = _playerInput.actions.FindAction("ToggleInventory");
                _equipmentAction = _playerInput.actions.FindAction("ToggleEquipment");
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
                _debugF5 = _playerInput.actions.FindAction("ToggleCameraMode");
                _debugF7 = _playerInput.actions.FindAction("InfiniteDurability");
                return;
            }

            // Fallback: create inline actions (works without InputActionAsset)
            _moveAction = new InputAction("Move", InputActionType.Value);
            _moveAction.AddCompositeBinding("2DVector")
                .With("Up", "<Keyboard>/w")
                .With("Down", "<Keyboard>/s")
                .With("Left", "<Keyboard>/a")
                .With("Right", "<Keyboard>/d");

            _lookAction = new InputAction("Look", InputActionType.Value, "<Mouse>/delta");

            _interactAction = new InputAction("Interact", InputActionType.Button, "<Keyboard>/e");
            _attackAction = new InputAction("Attack", InputActionType.Button, "<Mouse>/leftButton");
            _secondaryAction = new InputAction("SecondaryAttack", InputActionType.Button, "<Mouse>/rightButton");
            _escapeAction = new InputAction("Escape", InputActionType.Button, "<Keyboard>/escape");
            _inventoryAction = new InputAction("ToggleInventory", InputActionType.Button, "<Keyboard>/tab");
            _equipmentAction = new InputAction("ToggleEquipment", InputActionType.Button, "<Keyboard>/i");
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
            _debugF5 = new InputAction("DebugF5", InputActionType.Button, "<Keyboard>/f5");
            _debugF7 = new InputAction("DebugF7", InputActionType.Button, "<Keyboard>/f7");
        }

        // ====================================================================
        // Enable / Disable Actions
        // ====================================================================

        private InputAction[] _allActions => new[]
        {
            _moveAction, _lookAction, _interactAction, _attackAction, _secondaryAction,
            _escapeAction, _inventoryAction, _equipmentAction, _mapAction,
            _encyclopediaAction, _statsAction, _skillsAction, _craftAction,
            _scrollAction, _skill1Action, _skill2Action, _skill3Action,
            _skill4Action, _skill5Action, _debugF1, _debugF2, _debugF3,
            _debugF4, _debugF5, _debugF7
        };

        private void _enableAllActions()
        {
            foreach (var action in _allActions)
                action?.Enable();
        }

        private void _disableAllActions()
        {
            foreach (var action in _allActions)
                action?.Disable();
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
            if (_equipmentAction != null) _equipmentAction.performed += _onEquipment;
            if (_mapAction != null) _mapAction.performed += _onMap;
            if (_encyclopediaAction != null) _encyclopediaAction.performed += _onEncyclopedia;
            if (_statsAction != null) _statsAction.performed += _onStats;
            if (_skillsAction != null) _skillsAction.performed += _onSkills;
            if (_craftAction != null) _craftAction.performed += _onCraftAction;
            if (_scrollAction != null) _scrollAction.performed += _onScroll;

            if (_skill1Action != null) _skill1Action.performed += _onSkill1;
            if (_skill2Action != null) _skill2Action.performed += _onSkill2;
            if (_skill3Action != null) _skill3Action.performed += _onSkill3;
            if (_skill4Action != null) _skill4Action.performed += _onSkill4;
            if (_skill5Action != null) _skill5Action.performed += _onSkill5;

            if (_debugF1 != null) _debugF1.performed += _onDebugF1;
            if (_debugF2 != null) _debugF2.performed += _onDebugF2;
            if (_debugF3 != null) _debugF3.performed += _onDebugF3;
            if (_debugF4 != null) _debugF4.performed += _onDebugF4;
            if (_debugF5 != null) _debugF5.performed += _onDebugF5;
            if (_debugF7 != null) _debugF7.performed += _onDebugF7;
        }

        private void _unbindActions()
        {
            if (_interactAction != null) _interactAction.performed -= _onInteract;
            if (_attackAction != null) _attackAction.performed -= _onAttack;
            if (_secondaryAction != null) _secondaryAction.performed -= _onSecondary;
            if (_escapeAction != null) _escapeAction.performed -= _onEscape;
            if (_inventoryAction != null) _inventoryAction.performed -= _onInventory;
            if (_equipmentAction != null) _equipmentAction.performed -= _onEquipment;
            if (_mapAction != null) _mapAction.performed -= _onMap;
            if (_encyclopediaAction != null) _encyclopediaAction.performed -= _onEncyclopedia;
            if (_statsAction != null) _statsAction.performed -= _onStats;
            if (_skillsAction != null) _skillsAction.performed -= _onSkills;
            if (_craftAction != null) _craftAction.performed -= _onCraftAction;
            if (_scrollAction != null) _scrollAction.performed -= _onScroll;

            if (_skill1Action != null) _skill1Action.performed -= _onSkill1;
            if (_skill2Action != null) _skill2Action.performed -= _onSkill2;
            if (_skill3Action != null) _skill3Action.performed -= _onSkill3;
            if (_skill4Action != null) _skill4Action.performed -= _onSkill4;
            if (_skill5Action != null) _skill5Action.performed -= _onSkill5;

            if (_debugF1 != null) _debugF1.performed -= _onDebugF1;
            if (_debugF2 != null) _debugF2.performed -= _onDebugF2;
            if (_debugF3 != null) _debugF3.performed -= _onDebugF3;
            if (_debugF4 != null) _debugF4.performed -= _onDebugF4;
            if (_debugF5 != null) _debugF5.performed -= _onDebugF5;
            if (_debugF7 != null) _debugF7.performed -= _onDebugF7;
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
            {
                // First-person: attack is a forward ray from camera center
                if (Camera.main != null)
                {
                    var ray = Camera.main.ScreenPointToRay(new Vector3(Screen.width / 2f, Screen.height / 2f, 0));
                    var plane = new Plane(Vector3.up, Vector3.zero);
                    if (plane.Raycast(ray, out float dist))
                    {
                        OnPrimaryAttack?.Invoke(ray.GetPoint(dist));
                        return;
                    }
                }
                OnPrimaryAttack?.Invoke(MouseWorldPosition);
            }
            else
            {
                OnUIClick?.Invoke(MousePosition);
            }
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
        private void _onEquipment(InputAction.CallbackContext ctx) => OnToggleEquipment?.Invoke();
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

        private void _onSkill1(InputAction.CallbackContext ctx) => OnSkillActivate?.Invoke(0);
        private void _onSkill2(InputAction.CallbackContext ctx) => OnSkillActivate?.Invoke(1);
        private void _onSkill3(InputAction.CallbackContext ctx) => OnSkillActivate?.Invoke(2);
        private void _onSkill4(InputAction.CallbackContext ctx) => OnSkillActivate?.Invoke(3);
        private void _onSkill5(InputAction.CallbackContext ctx) => OnSkillActivate?.Invoke(4);

        private void _onDebugF1(InputAction.CallbackContext ctx) => OnDebugKey?.Invoke("F1");
        private void _onDebugF2(InputAction.CallbackContext ctx) => OnDebugKey?.Invoke("F2");
        private void _onDebugF3(InputAction.CallbackContext ctx) => OnDebugKey?.Invoke("F3");
        private void _onDebugF4(InputAction.CallbackContext ctx) => OnDebugKey?.Invoke("F4");
        private void _onDebugF5(InputAction.CallbackContext ctx) => OnDebugKey?.Invoke("F5");
        private void _onDebugF7(InputAction.CallbackContext ctx) => OnDebugKey?.Invoke("F7");

        // ====================================================================
        // State Change Handler — Cursor Lock Management
        // ====================================================================

        private void _onGameStateChanged(GameState oldState, GameState newState)
        {
            // Lock cursor during gameplay, unlock for any UI
            if (newState == GameState.Playing)
            {
                LockCursor();
            }
            else
            {
                UnlockCursor();
            }
        }
    }
}
