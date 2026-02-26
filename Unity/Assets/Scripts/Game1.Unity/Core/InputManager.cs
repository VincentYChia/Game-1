// ============================================================================
// Game1.Unity.Core.InputManager
// Migrated from: core/game_engine.py (lines 488-1165: handle_events)
// Migration phase: 6 (reworked for first-person controls 2026-02-25)
//
// Replaces Python's pygame event polling with direct device polling.
// Uses Keyboard.current / Mouse.current (New Input System) as primary,
// with legacy UnityEngine.Input fallback when the old backend is active.
// NO InputAction objects — direct polling is the most reliable approach.
// ============================================================================

using System;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace Game1.Unity.Core
{
    /// <summary>
    /// Central input manager. Polls keyboard/mouse every frame and fires events.
    ///
    /// Input backend strategy (handles ALL Player Settings configurations):
    ///   1. Primary:  Keyboard.current / Mouse.current  (New Input System direct device API)
    ///   2. Fallback: UnityEngine.Input.GetKey/GetAxis   (Legacy Input Manager)
    ///   3. Both backends are tried — first one that's available wins each frame.
    ///
    /// Click-to-lock cursor pattern: left-click during gameplay locks the cursor.
    /// Escape unlocks. State transitions also manage cursor lock.
    /// </summary>
    public class InputManager : MonoBehaviour
    {
        // ====================================================================
        // Inspector References
        // ====================================================================

        [SerializeField] private GameStateManager _stateManager;

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
        // Backend Detection
        // ====================================================================

        private bool _hasNewInputSystem;
        private bool _hasLegacyInput;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Awake()
        {
            if (_stateManager == null)
                _stateManager = FindFirstObjectByType<GameStateManager>();

            _detectInputBackends();
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

        private void _detectInputBackends()
        {
            // Detect which input backends are available at runtime
#if ENABLE_INPUT_SYSTEM
            try
            {
                // Check if New Input System devices are available
                _hasNewInputSystem = Keyboard.current != null || Mouse.current != null;
            }
            catch
            {
                _hasNewInputSystem = false;
            }
#else
            _hasNewInputSystem = false;
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            _hasLegacyInput = true;
#else
            _hasLegacyInput = false;
#endif

            Debug.Log($"[InputManager] Backends: NewInputSystem={_hasNewInputSystem}, LegacyInput={_hasLegacyInput}");

            if (!_hasNewInputSystem && !_hasLegacyInput)
            {
                Debug.LogError("[InputManager] NO INPUT BACKEND AVAILABLE! " +
                    "Check Player Settings → Active Input Handling. " +
                    "Set to 'Both' or 'Input System Package (New)'.");
            }
        }

        // ====================================================================
        // Frame Update — All Input Polling
        // ====================================================================

        private void Update()
        {
            // Re-check backends each frame (devices can appear after Awake)
#if ENABLE_INPUT_SYSTEM
            if (!_hasNewInputSystem)
            {
                _hasNewInputSystem = Keyboard.current != null || Mouse.current != null;
                if (_hasNewInputSystem)
                    Debug.Log("[InputManager] New Input System devices now available");
            }
#endif

            bool isPlaying = _stateManager == null || _stateManager.IsPlaying;

            // === 1. Mouse Position (always, for UI) ===
            _pollMousePosition();

            // === 2. Movement (continuous, every frame) ===
            Vector2 moveInput = _pollMovement();
            if (isPlaying && moveInput.sqrMagnitude > 0.01f)
            {
                OnMoveInput?.Invoke(moveInput.normalized);
            }

            // === 3. Mouse Look (when cursor locked in gameplay) ===
            Vector2 mouseDelta = _pollMouseDelta();
            if (IsCursorLocked && isPlaying && mouseDelta.sqrMagnitude > 0.001f)
            {
                float deltaX = mouseDelta.x * _mouseSensitivity;
                float deltaY = mouseDelta.y * _mouseSensitivity * (_invertY ? 1f : -1f);
                OnMouseLook?.Invoke(new Vector2(deltaX, deltaY));
            }

            // === 4. Click-to-Lock Cursor ===
            if (!IsCursorLocked && isPlaying && _wasLeftClickPressed())
            {
                LockCursor();
            }

            // === 5. Button Presses (single-frame) ===
            _pollButtons(isPlaying);

            // === 6. Scroll Wheel ===
            float scroll = _pollScroll();
            if (Mathf.Abs(scroll) > 0.01f)
            {
                OnScroll?.Invoke(scroll);
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
            Debug.Log("[InputManager] Cursor LOCKED");
        }

        /// <summary>Unlock the cursor for UI interaction.</summary>
        public void UnlockCursor()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            IsCursorLocked = false;
            Debug.Log("[InputManager] Cursor UNLOCKED");
        }

        // ====================================================================
        // Input Polling — Movement (WASD)
        // ====================================================================

        private Vector2 _pollMovement()
        {
            Vector2 move = Vector2.zero;

#if ENABLE_INPUT_SYSTEM
            var keyboard = Keyboard.current;
            if (keyboard != null)
            {
                if (keyboard.wKey.isPressed) move.y += 1f;
                if (keyboard.sKey.isPressed) move.y -= 1f;
                if (keyboard.aKey.isPressed) move.x -= 1f;
                if (keyboard.dKey.isPressed) move.x += 1f;
                return move;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            move.x = Input.GetAxisRaw("Horizontal");
            move.y = Input.GetAxisRaw("Vertical");
#endif

            return move;
        }

        // ====================================================================
        // Input Polling — Mouse Delta
        // ====================================================================

        private Vector2 _pollMouseDelta()
        {
#if ENABLE_INPUT_SYSTEM
            var mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.delta.ReadValue();
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            return new Vector2(
                Input.GetAxisRaw("Mouse X") * 10f,  // Scale to match New Input System range
                Input.GetAxisRaw("Mouse Y") * 10f
            );
#endif

#pragma warning disable CS0162
            return Vector2.zero;
#pragma warning restore CS0162
        }

        // ====================================================================
        // Input Polling — Mouse Position
        // ====================================================================

        private void _pollMousePosition()
        {
#if ENABLE_INPUT_SYSTEM
            var mouse = Mouse.current;
            if (mouse != null)
            {
                MousePosition = mouse.position.ReadValue();
                _updateMouseWorldPosition();
                return;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            MousePosition = Input.mousePosition;
            _updateMouseWorldPosition();
#endif
        }

        private void _updateMouseWorldPosition()
        {
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
        // Input Polling — Mouse Clicks
        // ====================================================================

        private bool _wasLeftClickPressed()
        {
#if ENABLE_INPUT_SYSTEM
            var mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.leftButton.wasPressedThisFrame;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetMouseButtonDown(0);
#endif

#pragma warning disable CS0162
            return false;
#pragma warning restore CS0162
        }

        private bool _wasRightClickPressed()
        {
#if ENABLE_INPUT_SYSTEM
            var mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.rightButton.wasPressedThisFrame;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetMouseButtonDown(1);
#endif

#pragma warning disable CS0162
            return false;
#pragma warning restore CS0162
        }

        // ====================================================================
        // Input Polling — Scroll Wheel
        // ====================================================================

        private float _pollScroll()
        {
#if ENABLE_INPUT_SYSTEM
            var mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.scroll.ReadValue().y;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetAxis("Mouse ScrollWheel") * 120f; // Scale to match
#endif

#pragma warning disable CS0162
            return 0f;
#pragma warning restore CS0162
        }

        // ====================================================================
        // Input Polling — Keyboard Buttons (single-frame press detection)
        // ====================================================================

        private void _pollButtons(bool isPlaying)
        {
            // Escape — always active (unlocks cursor, opens pause)
            if (_wasKeyPressed(KeyCode.Escape))
            {
                if (IsCursorLocked)
                    UnlockCursor();
                OnEscape?.Invoke();
                _stateManager?.HandleEscape();
            }

            // --- Gameplay keys (only when playing) ---
            if (!isPlaying) return;

            // Interact
            if (_wasKeyPressed(KeyCode.E))
                OnInteract?.Invoke();

            // Attack (left click while cursor is locked)
            if (IsCursorLocked && _wasLeftClickPressed())
            {
                if (Camera.main != null)
                {
                    var ray = Camera.main.ScreenPointToRay(
                        new Vector3(Screen.width / 2f, Screen.height / 2f, 0));
                    var plane = new Plane(Vector3.up, Vector3.zero);
                    if (plane.Raycast(ray, out float dist))
                    {
                        OnPrimaryAttack?.Invoke(ray.GetPoint(dist));
                    }
                    else
                    {
                        OnPrimaryAttack?.Invoke(MouseWorldPosition);
                    }
                }
            }

            // Secondary action (right click)
            if (_wasRightClickPressed())
                OnSecondaryAction?.Invoke(MouseWorldPosition);

            // Craft action
            if (_wasKeyPressed(KeyCode.Space))
                OnCraftAction?.Invoke();

            // --- Menu toggles ---
            if (_wasKeyPressed(KeyCode.Tab))
                OnToggleInventory?.Invoke();
            if (_wasKeyPressed(KeyCode.I))
                OnToggleEquipment?.Invoke();
            if (_wasKeyPressed(KeyCode.M))
                OnToggleMap?.Invoke();
            if (_wasKeyPressed(KeyCode.J))
                OnToggleEncyclopedia?.Invoke();
            if (_wasKeyPressed(KeyCode.C))
                OnToggleStats?.Invoke();
            if (_wasKeyPressed(KeyCode.K))
                OnToggleSkills?.Invoke();

            // --- Skill bar (1-5) ---
            if (_wasKeyPressed(KeyCode.Alpha1))
                OnSkillActivate?.Invoke(0);
            if (_wasKeyPressed(KeyCode.Alpha2))
                OnSkillActivate?.Invoke(1);
            if (_wasKeyPressed(KeyCode.Alpha3))
                OnSkillActivate?.Invoke(2);
            if (_wasKeyPressed(KeyCode.Alpha4))
                OnSkillActivate?.Invoke(3);
            if (_wasKeyPressed(KeyCode.Alpha5))
                OnSkillActivate?.Invoke(4);

            // --- Debug keys ---
            if (_wasKeyPressed(KeyCode.F1))
                OnDebugKey?.Invoke("F1");
            if (_wasKeyPressed(KeyCode.F2))
                OnDebugKey?.Invoke("F2");
            if (_wasKeyPressed(KeyCode.F3))
                OnDebugKey?.Invoke("F3");
            if (_wasKeyPressed(KeyCode.F4))
                OnDebugKey?.Invoke("F4");
            if (_wasKeyPressed(KeyCode.F5))
                OnDebugKey?.Invoke("F5");
            if (_wasKeyPressed(KeyCode.F7))
                OnDebugKey?.Invoke("F7");
        }

        // ====================================================================
        // Key Press Detection (unified across backends)
        // ====================================================================

        /// <summary>
        /// Check if a key was pressed this frame. Tries New Input System first,
        /// then falls back to legacy Input.GetKeyDown.
        /// </summary>
        private bool _wasKeyPressed(KeyCode keyCode)
        {
#if ENABLE_INPUT_SYSTEM
            var keyboard = Keyboard.current;
            if (keyboard != null)
            {
                Key key = _keyCodeToKey(keyCode);
                if (key != Key.None)
                    return keyboard[key].wasPressedThisFrame;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetKeyDown(keyCode);
#endif

#pragma warning disable CS0162
            return false;
#pragma warning restore CS0162
        }

#if ENABLE_INPUT_SYSTEM
        /// <summary>
        /// Map UnityEngine.KeyCode to UnityEngine.InputSystem.Key.
        /// Only maps keys we actually use.
        /// </summary>
        private static Key _keyCodeToKey(KeyCode keyCode)
        {
            switch (keyCode)
            {
                // Letters
                case KeyCode.A: return Key.A;
                case KeyCode.C: return Key.C;
                case KeyCode.D: return Key.D;
                case KeyCode.E: return Key.E;
                case KeyCode.I: return Key.I;
                case KeyCode.J: return Key.J;
                case KeyCode.K: return Key.K;
                case KeyCode.M: return Key.M;
                case KeyCode.S: return Key.S;
                case KeyCode.W: return Key.W;

                // Numbers
                case KeyCode.Alpha1: return Key.Digit1;
                case KeyCode.Alpha2: return Key.Digit2;
                case KeyCode.Alpha3: return Key.Digit3;
                case KeyCode.Alpha4: return Key.Digit4;
                case KeyCode.Alpha5: return Key.Digit5;

                // Special
                case KeyCode.Space: return Key.Space;
                case KeyCode.Tab: return Key.Tab;
                case KeyCode.Escape: return Key.Escape;

                // Function keys
                case KeyCode.F1: return Key.F1;
                case KeyCode.F2: return Key.F2;
                case KeyCode.F3: return Key.F3;
                case KeyCode.F4: return Key.F4;
                case KeyCode.F5: return Key.F5;
                case KeyCode.F7: return Key.F7;

                default: return Key.None;
            }
        }
#endif

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
