// ============================================================================
// Game1.Unity.Core.PlayerController
// Migrated from: core/game_engine.py (movement + interaction handling)
// Migration phase: 6 (reworked for first-person 2026-02-26)
//
// First-person player controller. WASD movement relative to camera forward.
// Reads InputManager.MoveInput directly each frame (no event dependency).
// Collision via WorldSystem bounds check.
// ============================================================================

using System;
using UnityEngine;
using Game1.Core;
using Game1.Data.Models;
using Game1.Entities;
using Game1.Systems.World;
using Game1.Unity.Utilities;
using Game1.Unity.World;

namespace Game1.Unity.Core
{
    public class PlayerController : MonoBehaviour
    {
        // ====================================================================
        // References
        // ====================================================================

        private GameManager _gameManager;
        private InputManager _inputManager;
        private GameStateManager _stateManager;
        private CameraController _cameraController;

        // ====================================================================
        // Configuration
        // ====================================================================

        [Header("Movement")]
        [SerializeField] private float _moveSpeed = 5.0f;
        [SerializeField] private float _sprintMultiplier = 1.5f;

        [Header("Physics")]
        [SerializeField] private float _gravity = -20f;
        [SerializeField] private float _jumpForce = 8f;
        [SerializeField] private float _groundCheckDistance = 0.2f;
        [SerializeField] private float _playerHeight = 1.8f;

        [Header("Interaction")]
        [SerializeField] private float _interactionRange = 3.5f;

        // ====================================================================
        // State
        // ====================================================================

        private float _verticalVelocity;
        private float _jumpOffset;  // Height above terrain surface
        private bool _isGrounded;
        private Character _character;
        private bool _loggedMovement; // DBG
        private float _dbgTimer; // DBG
        private int _dbgMoveFrames; // DBG
        private bool _refsLogged; // DBG

        public bool MovementEnabled { get; set; } = true;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Awake()
        {
            Debug.Log($"[DBG:PLAYER:AWAKE] PlayerController.Awake() on '{gameObject.name}', " + // DBG
                $"parent={transform.parent?.name ?? "NULL"}, " + // DBG
                $"childCount={transform.childCount}, " + // DBG
                $"scene={gameObject.scene.name}"); // DBG
        }

        private void Start()
        {
            Debug.Log("[DBG:PLAYER:START:01] PlayerController.Start() BEGIN"); // DBG

            // Find GameManager — it's in DontDestroyOnLoad
            _gameManager = GameManager.Instance;
            Debug.Log($"[DBG:PLAYER:START:02] GameManager.Instance = {(_gameManager != null ? "FOUND" : "NULL")}"); // DBG

            // Find GameStateManager
            _stateManager = FindFirstObjectByType<GameStateManager>();
            Debug.Log($"[DBG:PLAYER:START:03] GameStateManager = {(_stateManager != null ? "FOUND" : "NULL")}"); // DBG

            // Find CameraController — should be on a child
            _cameraController = GetComponentInChildren<CameraController>();
            Debug.Log($"[DBG:PLAYER:START:04] GetComponentInChildren<CameraController> = {(_cameraController != null ? "FOUND" : "NULL")}"); // DBG

            // [DBG] If not found in children, search globally as fallback
            if (_cameraController == null) // DBG
            { // DBG
                Debug.LogWarning("[DBG:PLAYER:START:04b] CameraController NOT in children! Searching globally..."); // DBG
                _cameraController = FindFirstObjectByType<CameraController>(); // DBG
                if (_cameraController != null) // DBG
                { // DBG
                    Debug.LogWarning($"[DBG:PLAYER:START:04c] Found CameraController globally on '{_cameraController.gameObject.name}', " + // DBG
                        $"parent={_cameraController.transform.parent?.name ?? "NULL"}"); // DBG
                } // DBG
            } // DBG

            // Find InputManager
            _inputManager = FindFirstObjectByType<InputManager>();
            Debug.Log($"[DBG:PLAYER:START:05] InputManager = {(_inputManager != null ? "FOUND on " + _inputManager.gameObject.name : "NULL")}"); // DBG

            if (_inputManager != null)
            {
                _inputManager.OnInteract += _onInteract;
                _inputManager.OnJump += _onJump;
                Debug.Log("[DBG:PLAYER:START:06] Subscribed to OnInteract, OnJump"); // DBG
            }
            else
            {
                Debug.LogError("[PlayerController] InputManager NOT FOUND! Movement will not work.");
            }

            // [DBG] Dump hierarchy from our perspective
            Debug.Log($"[DBG:PLAYER:START:07] My GO: '{gameObject.name}', active={gameObject.activeInHierarchy}, " + // DBG
                $"childCount={transform.childCount}"); // DBG
            for (int i = 0; i < transform.childCount; i++) // DBG
            { // DBG
                var child = transform.GetChild(i); // DBG
                Debug.Log($"[DBG:PLAYER:START:08] Child[{i}]: '{child.name}', " + // DBG
                    $"components=[{_getComponentNames(child.gameObject)}]"); // DBG
            } // DBG

            Debug.Log($"[PlayerController] Start() complete. " +
                $"GameManager={_gameManager != null}, " +
                $"StateManager={_stateManager != null}, " +
                $"CameraController={_cameraController != null}, " +
                $"InputManager={_inputManager != null}");
        }

        private string _getComponentNames(GameObject go) // DBG
        { // DBG
            var comps = go.GetComponents<Component>(); // DBG
            var names = new System.Text.StringBuilder(); // DBG
            foreach (var c in comps) // DBG
            { // DBG
                if (c is Transform) continue; // DBG
                if (names.Length > 0) names.Append(", "); // DBG
                names.Append(c.GetType().Name); // DBG
            } // DBG
            return names.ToString(); // DBG
        } // DBG

        private void OnDestroy()
        {
            if (_inputManager != null)
            {
                _inputManager.OnInteract -= _onInteract;
                _inputManager.OnJump -= _onJump;
            }
        }

        private void Update()
        {
            // [DBG] Log refs once, after first full frame
            if (!_refsLogged && Time.frameCount > 5) // DBG
            { // DBG
                _refsLogged = true; // DBG
                Debug.Log($"[DBG:PLAYER:UPDATE:REFS] GM={_gameManager != null}, " + // DBG
                    $"Player={_gameManager?.Player != null}, " + // DBG
                    $"State={(_stateManager != null ? _stateManager.CurrentState.ToString() : "NULL")}, " + // DBG
                    $"MovementEnabled={MovementEnabled}, " + // DBG
                    $"InputMgr={_inputManager != null}"); // DBG
            } // DBG

            if (_gameManager == null || _gameManager.Player == null)
            {
                if (Time.frameCount % 120 == 0) // DBG
                    Debug.Log($"[DBG:PLAYER:SKIP] GM={_gameManager != null}, Player={_gameManager?.Player != null}"); // DBG
                return;
            }
            if (_stateManager != null && _stateManager.CurrentState != GameState.Playing)
            {
                if (Time.frameCount % 120 == 0) // DBG
                    Debug.Log($"[DBG:PLAYER:SKIP] State={_stateManager.CurrentState} (not Playing)"); // DBG
                return;
            }
            if (!MovementEnabled) return;

            _character = _gameManager.Player;

            _processMovement();
            _syncTransform();

            // [DBG] Periodic position log every 2 seconds
            _dbgTimer += Time.deltaTime; // DBG
            if (_dbgTimer >= 2.0f) // DBG
            { // DBG
                _dbgTimer = 0f; // DBG
                Debug.Log($"[DBG:PLAYER:POS] pos={_character.Position} " + // DBG
                    $"transform={transform.position} " + // DBG
                    $"moveInput={(_inputManager != null ? _inputManager.MoveInput.ToString() : "no_input_mgr")} " + // DBG
                    $"moveFrames={_dbgMoveFrames}"); // DBG
                _dbgMoveFrames = 0; // DBG
            } // DBG
        }

        // ====================================================================
        // Input Handlers (events — for discrete actions only)
        // ====================================================================

        private void _onInteract()
        {
            if (_character == null) return;
            Debug.Log("[DBG:PLAYER:INTERACT] Interact triggered"); // DBG
            GameEvents.RaisePlayerInteracted(_character.Position, _character.Facing);
        }

        private void _onJump()
        {
            if (_character == null) return;
            if (!_isGrounded) return;
            _verticalVelocity = _jumpForce;
            _isGrounded = false;
        }

        // ====================================================================
        // Movement — Direct polling from InputManager
        // ====================================================================

        private void _processMovement()
        {
            // Read movement input directly from InputManager property
            Vector2 moveInput = Vector2.zero;
            if (_inputManager != null)
            {
                moveInput = _inputManager.MoveInput;
            }

            if (moveInput.sqrMagnitude < 0.01f)
            {
                if (_cameraController != null) _cameraController.NotifyMoving(false);
                return;
            }

            _dbgMoveFrames++; // DBG

            if (!_loggedMovement) // DBG
            { // DBG
                Debug.Log($"[DBG:PLAYER:FIRST_MOVE] input={moveInput} speed={_moveSpeed} " + // DBG
                    $"camCtrl={_cameraController != null} " + // DBG
                    $"charPos={_character?.Position}"); // DBG
                _loggedMovement = true; // DBG
            } // DBG

            // Get camera-relative directions on XZ plane
            Vector3 forward, right;
            if (_cameraController != null)
            {
                forward = _cameraController.ForwardXZ;
                right = _cameraController.RightXZ;
            }
            else
            {
                forward = transform.forward;
                forward.y = 0;
                forward.Normalize();
                right = transform.right;
                right.y = 0;
                right.Normalize();
            }

            Vector3 moveDir = (forward * moveInput.y + right * moveInput.x).normalized;
            float speed = _moveSpeed;
            if (_inputManager != null && _inputManager.IsSprinting)
                speed *= _sprintMultiplier;
            Vector3 movement = moveDir * speed * Time.deltaTime;

            GamePosition currentPos = _character.Position;
            float newX = currentPos.X + movement.x;
            float newZ = currentPos.Z + movement.z;

            // World bounds
            newX = Mathf.Clamp(newX, 0.5f, GameConfig.WorldSizeX - 0.5f);
            newZ = Mathf.Clamp(newZ, 0.5f, GameConfig.WorldSizeZ - 0.5f);

            // Walkability check with wall-sliding (mirrors Python movement)
            var worldSystem = _gameManager.World;
            if (worldSystem != null)
            {
                var targetPos = GamePosition.FromXZ(newX, newZ);
                if (!worldSystem.IsWalkable(targetPos))
                {
                    // Wall-slide: try X-only movement
                    var slideX = GamePosition.FromXZ(newX, currentPos.Z);
                    // Wall-slide: try Z-only movement
                    var slideZ = GamePosition.FromXZ(currentPos.X, newZ);

                    bool canSlideX = worldSystem.IsWalkable(slideX);
                    bool canSlideZ = worldSystem.IsWalkable(slideZ);

                    if (canSlideX)
                    {
                        newZ = currentPos.Z; // Keep Z, slide along X
                    }
                    else if (canSlideZ)
                    {
                        newX = currentPos.X; // Keep X, slide along Z
                    }
                    else
                    {
                        // Completely blocked
                        newX = currentPos.X;
                        newZ = currentPos.Z;
                        if (_dbgMoveFrames % 60 == 0) // DBG — log every ~1 sec when blocked
                        { // DBG
                            string tileInfo = _getTileTypeAtPosition(newX, newZ); // DBG
                            Debug.Log($"[DBG:PLAYER:BLOCKED] at ({newX:F1},{newZ:F1}) tile={tileInfo}"); // DBG
                        } // DBG
                    }
                }
            }

            _character.Position = new GamePosition(newX, currentPos.Y, newZ);

            if (Mathf.Abs(movement.x) > Mathf.Abs(movement.z))
            {
                _character.Facing = movement.x > 0 ? "right" : "left";
            }
            else if (movement.z != 0)
            {
                _character.Facing = movement.z > 0 ? "up" : "down";
            }

            if (_cameraController != null) _cameraController.NotifyMoving(true);
        }

        // ====================================================================
        // Transform Sync (smooth terrain following)
        // ====================================================================

        private float _currentTerrainY; // Smoothed Y position
        private bool _terrainYInitialized;

        private void _syncTransform()
        {
            if (_character == null) return;

            Vector3 pos = PositionConverter.ToVector3(_character.Position);
            string tileType = _getTileTypeAtPosition(pos.x, pos.z);
            float targetY = ChunkMeshGenerator.SampleTerrainHeight(pos.x, pos.z, tileType);

            // Smooth terrain height transitions to avoid jarring camera jumps
            if (!_terrainYInitialized)
            {
                _currentTerrainY = targetY;
                _terrainYInitialized = true;
            }
            else
            {
                float lerpSpeed = 8f * Time.deltaTime;
                _currentTerrainY = Mathf.Lerp(_currentTerrainY, targetY, Mathf.Clamp01(lerpSpeed));
            }

            // Apply gravity and jump physics
            if (_jumpOffset > 0f || _verticalVelocity > 0f)
            {
                _verticalVelocity += _gravity * Time.deltaTime;
                _jumpOffset += _verticalVelocity * Time.deltaTime;

                if (_jumpOffset <= 0f)
                {
                    _jumpOffset = 0f;
                    _verticalVelocity = 0f;
                    _isGrounded = true;
                }
            }
            else
            {
                _isGrounded = true;
            }

            pos.y = _currentTerrainY + _jumpOffset;
            transform.position = pos;
        }

        private string _getTileTypeAtPosition(float x, float z)
        {
            if (_gameManager.World == null) return "grass";
            int tileX = Mathf.FloorToInt(x);
            int tileZ = Mathf.FloorToInt(z);
            var tile = _gameManager.World.GetTile(GamePosition.FromXZ(tileX, tileZ));
            if (tile != null) return tile.TileType.ToString().ToLowerInvariant();
            return "grass";
        }

        // ====================================================================
        // Public API
        // ====================================================================

        public void TeleportTo(GamePosition position)
        {
            if (_character != null)
            {
                _character.Position = position;
                _syncTransform();
            }
        }

        public bool TryGetInteractionTarget(out Vector3 hitPoint, out GameObject hitObject)
        {
            hitPoint = Vector3.zero;
            hitObject = null;
            if (_cameraController == null) return false;
            Ray ray = _cameraController.GetCenterRay();
            if (Physics.Raycast(ray, out RaycastHit hit, _interactionRange))
            {
                hitPoint = hit.point;
                hitObject = hit.collider.gameObject;
                return true;
            }
            return false;
        }
    }
}
