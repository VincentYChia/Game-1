// ============================================================================
// Game1.Unity.World.BillboardSprite
// Created: 2026-02-18
//
// Component that makes a sprite (or any flat object) always face the camera.
// Used for entities (players, enemies, NPCs, resources) in the 3D world
// to maintain visual readability from any camera angle.
// Supports optional Y-axis-only billboarding for upright entities.
// ============================================================================

using UnityEngine;

namespace Game1.Unity.World
{
    /// <summary>
    /// Billboards a transform to always face the active camera.
    /// Attach to any GameObject with a SpriteRenderer or quad mesh
    /// that should remain facing the camera in 3D space.
    /// </summary>
    public class BillboardSprite : MonoBehaviour
    {
        // ====================================================================
        // Configuration
        // ====================================================================

        [Header("Billboard Settings")]
        [Tooltip("Only rotate around Y axis (keeps sprite upright)")]
        [SerializeField] private bool _yAxisOnly = true;

        [Tooltip("Offset applied after billboarding (e.g., slight tilt)")]
        [SerializeField] private Vector3 _rotationOffset = Vector3.zero;

        [Tooltip("Scale factor applied based on distance from camera (0 = disabled)")]
        [SerializeField] private float _distanceScaling = 0f;

        [Header("Shadow")]
        [Tooltip("Enable ground shadow blob beneath this entity")]
        [SerializeField] private bool _showShadow = true;

        [SerializeField] private float _shadowSize = 0.6f;
        [SerializeField] private float _shadowAlpha = 0.3f;

        // ====================================================================
        // State
        // ====================================================================

        private Transform _cameraTransform;
        private Transform _shadowTransform;
        private float _baseScale = 1f;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            if (Camera.main != null)
                _cameraTransform = Camera.main.transform;

            _baseScale = transform.localScale.x;

            if (_showShadow)
                _createShadow();
        }

        private void LateUpdate()
        {
            if (_cameraTransform == null)
            {
                if (Camera.main != null)
                    _cameraTransform = Camera.main.transform;
                else
                    return;
            }

            // Billboard rotation
            if (_yAxisOnly)
            {
                // Only rotate around Y — keeps sprites upright
                Vector3 lookDir = _cameraTransform.position - transform.position;
                lookDir.y = 0f;
                if (lookDir.sqrMagnitude > 0.001f)
                {
                    Quaternion rotation = Quaternion.LookRotation(-lookDir);
                    transform.rotation = rotation * Quaternion.Euler(_rotationOffset);
                }
            }
            else
            {
                // Full billboard — always perfectly face camera
                transform.rotation = _cameraTransform.rotation * Quaternion.Euler(_rotationOffset);
            }

            // Distance-based scaling (optional)
            if (_distanceScaling > 0f)
            {
                float dist = Vector3.Distance(transform.position, _cameraTransform.position);
                float scale = _baseScale * (1f + dist * _distanceScaling * 0.01f);
                transform.localScale = new Vector3(scale, scale, scale);
            }

            // Update shadow position (project to ground)
            if (_shadowTransform != null)
            {
                _shadowTransform.position = new Vector3(
                    transform.position.x,
                    0.01f, // Just above ground to avoid z-fighting
                    transform.position.z
                );
            }
        }

        // ====================================================================
        // Shadow Creation
        // ====================================================================

        private void _createShadow()
        {
            var shadowGO = new GameObject("Shadow");
            _shadowTransform = shadowGO.transform;
            _shadowTransform.SetParent(transform.parent ?? transform, false);
            _shadowTransform.position = new Vector3(transform.position.x, 0.01f, transform.position.z);
            _shadowTransform.rotation = Quaternion.Euler(90f, 0f, 0f);
            _shadowTransform.localScale = new Vector3(_shadowSize, _shadowSize, 1f);

            // Create shadow sprite (dark ellipse)
            var sr = shadowGO.AddComponent<SpriteRenderer>();
            sr.sprite = _createShadowSprite();
            sr.color = new Color(0f, 0f, 0f, _shadowAlpha);
            sr.sortingOrder = -1;
        }

        private static Sprite _cachedShadowSprite;

        private static Sprite _createShadowSprite()
        {
            if (_cachedShadowSprite != null) return _cachedShadowSprite;

            // Create a circular gradient texture for the shadow
            int size = 32;
            var texture = new Texture2D(size, size, TextureFormat.RGBA32, false);
            float center = size / 2f;

            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x - center) / center;
                    float dy = (y - center) / center;
                    float dist = Mathf.Sqrt(dx * dx + dy * dy);
                    float alpha = Mathf.Clamp01(1f - dist);
                    alpha *= alpha; // Quadratic falloff for soft edge
                    texture.SetPixel(x, y, new Color(0f, 0f, 0f, alpha));
                }
            }

            texture.Apply();
            texture.filterMode = FilterMode.Bilinear;

            _cachedShadowSprite = Sprite.Create(
                texture,
                new Rect(0, 0, size, size),
                new Vector2(0.5f, 0.5f),
                size
            );

            return _cachedShadowSprite;
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>Enable or disable the shadow.</summary>
        public void SetShadowVisible(bool visible)
        {
            if (_shadowTransform != null)
                _shadowTransform.gameObject.SetActive(visible);
        }

        /// <summary>Update shadow size (e.g., for boss enemies).</summary>
        public void SetShadowSize(float size)
        {
            _shadowSize = size;
            if (_shadowTransform != null)
                _shadowTransform.localScale = new Vector3(size, size, 1f);
        }
    }
}
