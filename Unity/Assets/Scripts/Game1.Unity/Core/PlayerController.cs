// ============================================================================
// Game1.Unity.Core.PlayerController
// Migrated from: core/game_engine.py (movement + interaction handling)
// Migration phase: 6 (reworked for first-person 2026-02-25)
//
// First-person player controller. WASD movement relative to camera forward.
// All input routed through InputManager (no legacy Input API).
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
    /// <summary>
    /// First-person player controller. Handles:
    /// - WASD movement relative to camera facing direction
    /// - World bounds collision checking
    /// - E-key interaction with world objects
    /// - Position sync between Character data and Transform
    /// All input comes from InputManager events (no legacy Input API).
    /// </summary>
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
        [SerializeField] private float _groundCheckDistance = 0.2f;
        [SerializeField] private float _playerHeight = 1.8f;

        [Header("Interaction")]
        [SerializeField] private float _interactionRange = 3.5f;

        // ====================================================================
        // State
        // ====================================================================

        private Vector2 _pendingMove;
        private float _verticalVelocity;
        private bool _isGrounded;
        private Character _character;

        /// <summary>Enable/disable player movement (for UI, cutscenes, etc.).</summary>
        public bool MovementEnabled { get; set; } = true;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            _gameManager = GameManager.Instance;
            _inputManager = FindFirstObjectByType<InputManager>();
            _stateManager = FindFirstObjectByType<GameStateManager>();
            _cameraController = GetComponentInChildren<CameraController>();

            if (_inputManager != null)
            {
                _inputManager.OnMoveInput += _onMoveInput;
                _inputManager.OnInteract += _onInteract;
            }
        }

        private void OnDestroy()
        {
            if (_inputManager != null)
            {
                _inputManager.OnMoveInput -= _onMoveInput;
                _inputManager.OnInteract -= _onInteract;
            }
        }

        private void Update()
        {
            if (_gameManager == null || _gameManager.Player == null) return;
            if (_stateManager != null && _stateManager.CurrentState != GameState.Playing) return;
            if (!MovementEnabled) return;

            _character = _gameManager.Player;

            _processMovement();
            _syncTransform();
        }

        // ====================================================================
        // Input Handlers
        // ====================================================================

        private void _onMoveInput(Vector2 input)
        {
            _pendingMove = input;
        }

        private void _onInteract()
        {
            if (_character == null) return;
            GameEvents.RaisePlayerInteracted(_character.Position, _character.Facing);
        }

        // ====================================================================
        // Movement
        // ====================================================================

        private void _processMovement()
        {
            if (_pendingMove.sqrMagnitude < 0.01f)
            {
                _pendingMove = Vector2.zero;
                if (_cameraController != null) _cameraController.NotifyMoving(false);
                return;
            }

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

            // Calculate movement direction relative to camera
            Vector3 moveDir = (forward * _pendingMove.y + right * _pendingMove.x).normalized;

            // Apply speed — use Unity-appropriate speed (not Python pixel-per-frame value)
            // Character.MovementSpeed (0.15) is a Python-era value in pixels/frame.
            // _moveSpeed (5.0) is the correct meters/second for 3D first-person.
            float speed = _moveSpeed;
            Vector3 movement = moveDir * speed * Time.deltaTime;

            // Calculate new position
            GamePosition currentPos = _character.Position;
            float newX = currentPos.X + movement.x;
            float newZ = currentPos.Z + movement.z;

            // World bounds collision check
            var worldSystem = _gameManager.World;
            if (worldSystem != null)
            {
                newX = Mathf.Clamp(newX, 0.5f, GameConfig.WorldSizeX - 0.5f);
                newZ = Mathf.Clamp(newZ, 0.5f, GameConfig.WorldSizeZ - 0.5f);
            }

            // Apply position to character data
            _character.Position = new GamePosition(newX, currentPos.Y, newZ);

            // Update facing based on dominant movement axis
            if (Mathf.Abs(movement.x) > Mathf.Abs(movement.z))
            {
                _character.Facing = movement.x > 0 ? "right" : "left";
            }
            else if (movement.z != 0)
            {
                _character.Facing = movement.z > 0 ? "up" : "down";
            }

            if (_cameraController != null) _cameraController.NotifyMoving(true);

            // Reset pending input (will be refreshed next frame from InputManager)
            _pendingMove = Vector2.zero;
        }

        // ====================================================================
        // Transform Sync
        // ====================================================================

        /// <summary>Sync Unity Transform to Character Position.</summary>
        private void _syncTransform()
        {
            if (_character == null) return;

            Vector3 pos = PositionConverter.ToVector3(_character.Position);

            // Get terrain height at player position with Perlin noise for smooth terrain
            string tileType = _getTileTypeAtPosition(pos.x, pos.z);
            pos.y = ChunkMeshGenerator.SampleTerrainHeight(pos.x, pos.z, tileType);

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

        /// <summary>Teleport the player to a position.</summary>
        public void TeleportTo(GamePosition position)
        {
            if (_character != null)
            {
                _character.Position = position;
                _syncTransform();

                // Snap camera to avoid interpolation lag
                if (_cameraController != null)
                {
                    // Position is synced via parent transform
                }
            }
        }

        /// <summary>Get the interaction raycast from the camera center.</summary>
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
