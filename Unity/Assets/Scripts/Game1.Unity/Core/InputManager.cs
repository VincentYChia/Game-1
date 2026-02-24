// ============================================================================
// Game1.Unity.Core.InputManager
// Migrated from: core/game_engine.py (lines 488-1165: handle_events)
// Migration phase: 6
// Date: 2026-02-13
//
// Replaces Python's pygame event polling with Unity Input.
// Routes input to appropriate handlers based on current GameState.
// Uses Unity legacy Input API (always available, no package dependency).
// ============================================================================

using System;
using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Central input manager. Routes keyboard/mouse input based on GameState.
    /// Uses Unity's built-in Input API (UnityEngine.Input) for zero-dependency input.
    /// </summary>
    public class InputManager : MonoBehaviour
    {
        // ====================================================================
        // Inspector References
        // ====================================================================

        [SerializeField] private GameStateManager _stateManager;

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
        // Initialization
        // ====================================================================

        private void Awake()
        {
            if (_stateManager == null)
                _stateManager = FindFirstObjectByType<GameStateManager>();
        }

        private void OnEnable()
        {
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onGameStateChanged;
        }

        private void OnDisable()
        {
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onGameStateChanged;
        }

        // ====================================================================
        // Frame Update — Poll all input every frame
        // ====================================================================

        private void Update()
        {
            _updateMousePosition();
            _pollMovement();
            _pollKeyDown();
            _pollMouseButtons();
            _pollScrollWheel();
        }

        // ====================================================================
        // Mouse Tracking
        // ====================================================================

        private void _updateMousePosition()
        {
            MousePosition = Input.mousePosition;

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

        // ====================================================================
        // Movement (continuous, polled every frame)
        // ====================================================================

        private void _pollMovement()
        {
            if (_stateManager == null || !_stateManager.IsPlaying)
                return;

            float h = Input.GetAxisRaw("Horizontal"); // A/D or Left/Right
            float v = Input.GetAxisRaw("Vertical");   // W/S or Up/Down
            var move = new Vector2(h, v);

            if (move.sqrMagnitude > 0.01f)
            {
                OnMoveInput?.Invoke(move);
            }
        }

        // ====================================================================
        // Key Down Events (fired once per press)
        // ====================================================================

        private void _pollKeyDown()
        {
            // Escape — always active
            if (Input.GetKeyDown(KeyCode.Escape))
            {
                OnEscape?.Invoke();
                _stateManager?.HandleEscape();
            }

            // Interact (E)
            if (Input.GetKeyDown(KeyCode.E))
            {
                if (_stateManager != null && _stateManager.IsPlaying)
                    OnInteract?.Invoke();
            }

            // Panel toggles
            if (Input.GetKeyDown(KeyCode.Tab))
                OnToggleInventory?.Invoke();

            if (Input.GetKeyDown(KeyCode.M))
                OnToggleMap?.Invoke();

            if (Input.GetKeyDown(KeyCode.J))
                OnToggleEncyclopedia?.Invoke();

            if (Input.GetKeyDown(KeyCode.C))
                OnToggleStats?.Invoke();

            if (Input.GetKeyDown(KeyCode.K))
                OnToggleSkills?.Invoke();

            // Crafting action (Spacebar)
            if (Input.GetKeyDown(KeyCode.Space))
                OnCraftAction?.Invoke();

            // Skill hotbar (1-5)
            if (Input.GetKeyDown(KeyCode.Alpha1)) OnSkillActivate?.Invoke(0);
            if (Input.GetKeyDown(KeyCode.Alpha2)) OnSkillActivate?.Invoke(1);
            if (Input.GetKeyDown(KeyCode.Alpha3)) OnSkillActivate?.Invoke(2);
            if (Input.GetKeyDown(KeyCode.Alpha4)) OnSkillActivate?.Invoke(3);
            if (Input.GetKeyDown(KeyCode.Alpha5)) OnSkillActivate?.Invoke(4);

            // Debug keys
            if (Input.GetKeyDown(KeyCode.F1)) OnDebugKey?.Invoke("F1");
            if (Input.GetKeyDown(KeyCode.F2)) OnDebugKey?.Invoke("F2");
            if (Input.GetKeyDown(KeyCode.F3)) OnDebugKey?.Invoke("F3");
            if (Input.GetKeyDown(KeyCode.F4)) OnDebugKey?.Invoke("F4");
            if (Input.GetKeyDown(KeyCode.F7)) OnDebugKey?.Invoke("F7");
        }

        // ====================================================================
        // Mouse Button Events
        // ====================================================================

        private void _pollMouseButtons()
        {
            // Left click (button 0)
            if (Input.GetMouseButtonDown(0))
            {
                if (_stateManager == null || _stateManager.IsPlaying)
                    OnPrimaryAttack?.Invoke(MouseWorldPosition);
                else
                    OnUIClick?.Invoke(MousePosition);
            }

            // Right click (button 1)
            if (Input.GetMouseButtonDown(1))
            {
                if (_stateManager == null || _stateManager.IsPlaying)
                    OnSecondaryAction?.Invoke(MouseWorldPosition);
            }
        }

        // ====================================================================
        // Scroll Wheel
        // ====================================================================

        private void _pollScrollWheel()
        {
            float scroll = Input.GetAxis("Mouse ScrollWheel");
            if (Mathf.Abs(scroll) > 0.001f)
                OnScroll?.Invoke(scroll);
        }

        // ====================================================================
        // State Change Handler
        // ====================================================================

        private void _onGameStateChanged(GameState oldState, GameState newState)
        {
            // State-based input filtering happens in the poll methods above
        }
    }
}
