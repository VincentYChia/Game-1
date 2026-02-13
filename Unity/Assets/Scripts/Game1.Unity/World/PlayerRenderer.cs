// ============================================================================
// Game1.Unity.World.PlayerRenderer
// Migrated from: rendering/renderer.py (player drawing within render_world)
// Migration phase: 6
// Date: 2026-02-13
//
// Renders the player sprite, handles facing direction and movement.
// Input handling drives movement via GameManager.Player.Position.
// ============================================================================

using UnityEngine;
using Game1.Core;
using Game1.Data.Models;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Player rendering and movement controller.
    /// Reads input from InputManager and moves the Character (Phase 3).
    /// Updates SpriteRenderer facing direction.
    /// </summary>
    public class PlayerRenderer : MonoBehaviour
    {
        // ====================================================================
        // Inspector References
        // ====================================================================

        [Header("Components")]
        [SerializeField] private SpriteRenderer _spriteRenderer;

        [Header("Sprites")]
        [SerializeField] private Sprite _spriteDown;
        [SerializeField] private Sprite _spriteUp;
        [SerializeField] private Sprite _spriteLeft;
        [SerializeField] private Sprite _spriteRight;

        [Header("Movement")]
        [SerializeField] private float _moveSpeedMultiplier = 5f;

        // ====================================================================
        // State
        // ====================================================================

        private InputManager _inputManager;
        private string _currentFacing = "down";

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Start()
        {
            _inputManager = FindFirstObjectByType<InputManager>();

            if (_spriteRenderer == null)
                _spriteRenderer = GetComponent<SpriteRenderer>();

            if (_inputManager != null)
                _inputManager.OnMoveInput += _onMoveInput;
        }

        private void OnDestroy()
        {
            if (_inputManager != null)
                _inputManager.OnMoveInput -= _onMoveInput;
        }

        // ====================================================================
        // Movement (called from InputManager)
        // ====================================================================

        private void _onMoveInput(Vector2 direction)
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null) return;

            var player = gm.Player;

            // Move character in XZ plane (direction.x → X, direction.y → Z)
            float speed = player.MovementSpeed * _moveSpeedMultiplier * Time.deltaTime;
            float newX = player.Position.X + direction.x * speed;
            float newZ = player.Position.Z + direction.y * speed;

            player.Position = GamePosition.FromXZ(newX, newZ);

            // Update facing direction
            if (Mathf.Abs(direction.x) > Mathf.Abs(direction.y))
            {
                _currentFacing = direction.x > 0 ? "right" : "left";
            }
            else if (direction.y != 0)
            {
                _currentFacing = direction.y > 0 ? "up" : "down";
            }
            player.Facing = _currentFacing;
        }

        // ====================================================================
        // Rendering Update
        // ====================================================================

        private void LateUpdate()
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null) return;

            // Sync transform to character position
            transform.position = PositionConverter.ToVector3(gm.Player.Position);

            // Update sprite facing
            _updateFacingSprite();
        }

        private void _updateFacingSprite()
        {
            if (_spriteRenderer == null) return;

            Sprite targetSprite = _currentFacing switch
            {
                "up" => _spriteUp,
                "down" => _spriteDown,
                "left" => _spriteLeft,
                "right" => _spriteRight,
                _ => _spriteDown
            };

            if (targetSprite != null)
                _spriteRenderer.sprite = targetSprite;

            // Fallback: use flipX for left/right if only one horizontal sprite
            if (_spriteLeft == null && _spriteRight != null)
            {
                _spriteRenderer.flipX = _currentFacing == "left";
            }
        }
    }
}
