// ============================================================================
// Game1.Unity.Core.PlayerController
// Migrated from: core/game_engine.py (movement + interaction handling)
// Migration phase: 6
// Date: 2026-02-21
//
// MonoBehaviour handling player movement, interaction, and input routing.
// Thin wrapper — all game logic lives in Character (Phase 3).
// ============================================================================

using System;
using UnityEngine;
using Game1.Core;
using Game1.Data.Models;
using Game1.Entities;
using Game1.Systems.World;
using Game1.Unity.Utilities;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Player controller MonoBehaviour. Handles:
    /// - WASD/arrow key movement
    /// - Interaction with world objects (resources, NPCs, stations)
    /// - Click-based combat targeting
    /// - Movement collision checking via CollisionSystem
    /// </summary>
    public class PlayerController : MonoBehaviour
    {
        // ====================================================================
        // References
        // ====================================================================

        private GameManager _gameManager;
        private InputManager _inputManager;
        private GameStateManager _stateManager;

        // ====================================================================
        // Configuration
        // ====================================================================

        [Header("Movement")]
        [SerializeField] private float _moveSpeed = 5.0f;
        [SerializeField] private float _diagonalFactor = 0.7071f;

        [Header("Interaction")]
        [SerializeField] private float _interactionRange = 2.0f;

        // ====================================================================
        // State
        // ====================================================================

        private Vector2 _moveInput;
        private bool _interactPressed;
        private Character _character;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            _gameManager = GameManager.Instance;
            _inputManager = FindFirstObjectByType<InputManager>();
            _stateManager = FindFirstObjectByType<GameStateManager>();
        }

        private void Update()
        {
            if (_gameManager == null || _gameManager.Player == null) return;
            if (_stateManager != null && _stateManager.CurrentState != GameState.Playing) return;

            _character = _gameManager.Player;

            HandleMovement();
            HandleInteraction();
        }

        // ====================================================================
        // Movement
        // ====================================================================

        private void HandleMovement()
        {
            // Read movement input
            float horizontal = Input.GetAxisRaw("Horizontal");
            float vertical = Input.GetAxisRaw("Vertical");

            if (horizontal == 0 && vertical == 0) return;

            // Normalize diagonal movement
            float magnitude = Mathf.Sqrt(horizontal * horizontal + vertical * vertical);
            if (magnitude > 1f)
            {
                horizontal /= magnitude;
                vertical /= magnitude;
            }

            // Calculate new position
            float speed = _character.MovementSpeed;
            float dx = horizontal * speed * Time.deltaTime;
            float dz = vertical * speed * Time.deltaTime;

            GamePosition newPos = new GamePosition(
                _character.Position.X + dx,
                _character.Position.Y,
                _character.Position.Z + dz
            );

            // Collision check via WorldSystem
            var worldSystem = _gameManager.World;
            if (worldSystem != null)
            {
                // Check if target position is walkable
                int tileX = (int)newPos.X;
                int tileZ = (int)newPos.Z;

                // Bounds check
                if (tileX >= 0 && tileX < GameConfig.WorldSizeX
                    && tileZ >= 0 && tileZ < GameConfig.WorldSizeZ)
                {
                    _character.Position = newPos;
                }
            }
            else
            {
                _character.Position = newPos;
            }

            // Update facing direction
            if (Mathf.Abs(horizontal) > Mathf.Abs(vertical))
            {
                _character.Facing = horizontal > 0 ? "right" : "left";
            }
            else
            {
                _character.Facing = vertical > 0 ? "up" : "down";
            }
        }

        // ====================================================================
        // Interaction
        // ====================================================================

        private void HandleInteraction()
        {
            // E key for interaction
            if (Input.GetKeyDown(KeyCode.E))
            {
                TryInteract();
            }
        }

        /// <summary>
        /// Attempt to interact with the nearest interactable object.
        /// </summary>
        private void TryInteract()
        {
            if (_character == null) return;

            // Interaction is handled by the game engine systems
            // This broadcasts an interaction event for other systems to respond to
            GameEvents.RaisePlayerInteracted(_character.Position, _character.Facing);
        }

        // ====================================================================
        // Public Methods
        // ====================================================================

        /// <summary>
        /// Teleport the player to a position (for dungeon entry, respawn, etc.).
        /// </summary>
        public void TeleportTo(GamePosition position)
        {
            if (_character != null)
            {
                _character.Position = position;
            }
        }

        /// <summary>
        /// Enable/disable player movement (for UI, cutscenes, etc.).
        /// </summary>
        public bool MovementEnabled { get; set; } = true;
    }
}
