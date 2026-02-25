// ============================================================================
// Game1.Unity.World.PlayerRenderer
// Migrated from: rendering/renderer.py (player drawing within render_world)
// Migration phase: 6 (upgraded for first-person 3D mode)
// Date: 2026-02-25
//
// In first-person mode, the player model is invisible (camera is the player's
// eyes). This script syncs the character's facing direction based on camera
// orientation. Movement is handled by PlayerController.
// In third-person mode (if re-enabled), shows a billboard sprite.
// ============================================================================

using UnityEngine;
using Game1.Core;
using Game1.Data.Models;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Player visual representation. In first-person mode, hides the player
    /// model and syncs the Character facing from camera direction.
    /// Movement is delegated to PlayerController.
    /// </summary>
    public class PlayerRenderer : MonoBehaviour
    {
        // ====================================================================
        // Inspector References
        // ====================================================================

        [Header("Components")]
        [SerializeField] private SpriteRenderer _spriteRenderer;

        [Header("Sprites (Third-Person only)")]
        [SerializeField] private Sprite _spriteDown;
        [SerializeField] private Sprite _spriteUp;
        [SerializeField] private Sprite _spriteLeft;
        [SerializeField] private Sprite _spriteRight;

        [Header("Mode")]
        [SerializeField] private bool _firstPerson = true;

        // ====================================================================
        // State
        // ====================================================================

        private CameraController _cameraController;
        private BillboardSprite _billboard;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Start()
        {
            _cameraController = FindFirstObjectByType<CameraController>();

            if (_firstPerson)
            {
                // Hide all visual components — player is the camera
                if (_spriteRenderer != null)
                    _spriteRenderer.enabled = false;

                _billboard = GetComponent<BillboardSprite>();
                if (_billboard != null)
                    _billboard.enabled = false;

                // Hide any child renderers (primitive shapes, etc.)
                foreach (var r in GetComponentsInChildren<Renderer>())
                    r.enabled = false;
            }
            else
            {
                // Third-person: ensure billboard sprite exists
                if (_spriteRenderer == null)
                    _spriteRenderer = GetComponent<SpriteRenderer>();

                _billboard = GetComponent<BillboardSprite>();
                if (_billboard == null)
                    _billboard = gameObject.AddComponent<BillboardSprite>();
            }
        }

        // ====================================================================
        // Update
        // ====================================================================

        private void LateUpdate()
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null) return;

            // Sync character facing direction from camera orientation
            if (_firstPerson && _cameraController != null)
            {
                Vector3 forward = _cameraController.ForwardXZ;
                string facing;

                if (Mathf.Abs(forward.x) > Mathf.Abs(forward.z))
                    facing = forward.x > 0 ? "right" : "left";
                else
                    facing = forward.z > 0 ? "up" : "down";

                gm.Player.Facing = facing;
            }
            else if (!_firstPerson)
            {
                // Third-person: sync transform to character position
                Vector3 worldPos = PositionConverter.ToVector3(gm.Player.Position);
                worldPos.y = 0.5f;
                transform.position = worldPos;

                _updateFacingSprite(gm.Player.Facing ?? "down");
            }
        }

        private void _updateFacingSprite(string facing)
        {
            if (_spriteRenderer == null) return;

            Sprite targetSprite = facing switch
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
                _spriteRenderer.flipX = facing == "left";
            }
        }

        /// <summary>Switch between first-person and third-person rendering.</summary>
        public void SetFirstPerson(bool firstPerson)
        {
            _firstPerson = firstPerson;

            if (_spriteRenderer != null)
                _spriteRenderer.enabled = !firstPerson;

            if (_billboard != null)
                _billboard.enabled = !firstPerson;

            foreach (var r in GetComponentsInChildren<Renderer>())
                r.enabled = !firstPerson;
        }
    }
}
