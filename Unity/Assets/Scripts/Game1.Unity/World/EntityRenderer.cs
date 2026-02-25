// ============================================================================
// Game1.Unity.World.EntityRenderer
// Migrated from: rendering/renderer.py (entity/station drawing)
// Migration phase: 6 (upgraded for 3D billboard rendering)
// Date: 2026-02-18
//
// Renders placed entities: turrets, traps, bombs, crafting stations.
// In 3D mode, uses BillboardSprite to keep sprites camera-facing.
// Falls back to 3D primitives via PrimitiveShapeFactory when no sprite is available.
// Range indicators are projected onto the XZ ground plane.
// ============================================================================

using UnityEngine;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Renders a placed entity (turret, trap, bomb, crafting station).
    /// Attached to entity prefabs.
    /// When a sprite is available, ensures BillboardSprite is present for 3D.
    /// When no sprite is available, creates a 3D primitive fallback via PrimitiveShapeFactory.
    /// </summary>
    public class EntityRenderer : MonoBehaviour
    {
        [Header("Components")]
        [SerializeField] private SpriteRenderer _spriteRenderer;
        [SerializeField] private SpriteRenderer _rangeIndicator;

        [Header("Visual Settings")]
        [SerializeField] private Color _activeColor = Color.white;
        [SerializeField] private Color _inactiveColor = new Color(0.5f, 0.5f, 0.5f);

        [Header("3D Settings")]
        [Tooltip("Height offset above terrain surface")]
        [SerializeField] private float _heightAboveTerrain = 0.5f;

        private string _entityId;
        private string _entityType;
        private bool _isActive = true;
        private bool _usePrimitive;
        private BillboardSprite _billboard;
        private GameObject _primitiveRoot;

        private void Awake()
        {
            // BillboardSprite is added on demand during Initialize —
            // only when we have a sprite (primitives don't need billboarding).
        }

        /// <summary>Initialize for a specific entity type.</summary>
        public void Initialize(string entityId, string entityType, Sprite sprite = null)
        {
            _entityId = entityId;
            _entityType = entityType;
            _usePrimitive = false;

            // Resolve sprite: use provided sprite, or look up from SpriteDatabase
            Sprite resolvedSprite = sprite;
            if (resolvedSprite == null && SpriteDatabase.Instance != null)
                resolvedSprite = SpriteDatabase.Instance.GetItemSprite(entityId);

            if (resolvedSprite != null)
            {
                // --- Sprite path ---
                if (_spriteRenderer == null)
                    _spriteRenderer = GetComponent<SpriteRenderer>();

                if (_spriteRenderer != null)
                    _spriteRenderer.sprite = resolvedSprite;

                // Ensure BillboardSprite exists for 3D camera compatibility
                _billboard = GetComponent<BillboardSprite>();
                if (_billboard == null)
                    _billboard = gameObject.AddComponent<BillboardSprite>();
            }
            else
            {
                // --- Primitive fallback path ---
                _usePrimitive = true;
                _buildPrimitive();

                // Disable SpriteRenderer if one exists (primitive replaces it)
                if (_spriteRenderer != null)
                    _spriteRenderer.enabled = false;
            }

            SetActive(true);
        }

        /// <summary>Show/hide range indicator (for turrets). Projects circle on ground plane.</summary>
        public void ShowRange(float radius, Color color)
        {
            if (_rangeIndicator == null) return;

            _rangeIndicator.gameObject.SetActive(true);
            _rangeIndicator.color = color;
            _rangeIndicator.transform.localScale = Vector3.one * radius * 2f;

            // Project range indicator flat on ground (XZ plane)
            _rangeIndicator.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            _rangeIndicator.transform.localPosition = new Vector3(0f, -_heightAboveTerrain + 0.02f, 0f);
        }

        /// <summary>Hide range indicator.</summary>
        public void HideRange()
        {
            if (_rangeIndicator != null)
                _rangeIndicator.gameObject.SetActive(false);
        }

        /// <summary>Set active/inactive visual state.</summary>
        public void SetActive(bool active)
        {
            _isActive = active;

            if (!_usePrimitive && _spriteRenderer != null)
            {
                _spriteRenderer.color = active ? _activeColor : _inactiveColor;
            }
            else if (_usePrimitive && _primitiveRoot != null)
            {
                // Tint primitive renderers to show inactive state
                var renderers = _primitiveRoot.GetComponentsInChildren<Renderer>();
                foreach (var r in renderers)
                {
                    if (r.material != null)
                    {
                        Color baseColor = r.material.color;
                        // Desaturate when inactive
                        r.material.color = active
                            ? baseColor
                            : new Color(
                                baseColor.r * 0.6f,
                                baseColor.g * 0.6f,
                                baseColor.b * 0.6f,
                                baseColor.a);
                    }
                }
            }
        }

        /// <summary>Set world position.</summary>
        public void SetPosition(Vector3 worldPos)
        {
            worldPos.y = _heightAboveTerrain;
            transform.position = worldPos;
        }

        // ====================================================================
        // Primitive Fallback
        // ====================================================================

        /// <summary>
        /// Creates a 3D primitive shape via PrimitiveShapeFactory and parents it
        /// under this transform. Used when no sprite is available.
        /// </summary>
        private void _buildPrimitive()
        {
            // Clean up any existing primitive
            if (_primitiveRoot != null)
                Destroy(_primitiveRoot);

            _primitiveRoot = PrimitiveShapeFactory.CreateStation(_entityType, 1);
            _primitiveRoot.transform.SetParent(transform, false);
            _primitiveRoot.transform.localPosition = Vector3.zero;
        }
    }
}
