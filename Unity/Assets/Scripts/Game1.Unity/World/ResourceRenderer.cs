// ============================================================================
// Game1.Unity.World.ResourceRenderer
// Migrated from: rendering/renderer.py (resource drawing within render_world)
// Migration phase: 6 (upgraded for 3D billboard rendering)
// Date: 2026-02-18
//
// Renders resource nodes (trees, ores, herbs) with HP bars and tool icons.
// In 3D mode, uses BillboardSprite to keep sprites camera-facing.
// Falls back to 3D primitives via PrimitiveShapeFactory when no sprite is available.
// Health bars billboard to camera via world-space Canvas.
// Spawned per chunk by WorldRenderer.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Renders a single resource node — billboard sprite, HP bar, tool requirement icon.
    /// Attached to ResourceNode prefab.
    /// When a sprite is available, ensures BillboardSprite is present for 3D.
    /// When no sprite is available, creates a 3D primitive fallback via PrimitiveShapeFactory.
    /// </summary>
    public class ResourceRenderer : MonoBehaviour
    {
        [Header("Components")]
        [SerializeField] private SpriteRenderer _spriteRenderer;
        [SerializeField] private Canvas _worldCanvas;
        [SerializeField] private Image _healthBarFill;
        [SerializeField] private GameObject _healthBarRoot;
        [SerializeField] private SpriteRenderer _toolIcon;

        [Header("Visual Settings")]
        [SerializeField] private Color _fullColor = new Color(0f, 0.8f, 0f);
        [SerializeField] private Color _depletedColor = new Color(0.4f, 0.4f, 0.4f);

        [Header("3D Settings")]
        [Tooltip("Height offset above terrain surface")]
        [SerializeField] private float _heightAboveTerrain = 0.5f;

        private string _resourceId;
        private float _healthPercent = 1f;
        private bool _isDepleted;
        private bool _usePrimitive;
        private BillboardSprite _billboard;
        private GameObject _primitiveRoot;

        private void Awake()
        {
            // BillboardSprite is added on demand during Initialize —
            // only when we have a sprite (primitives don't need billboarding).
        }

        /// <summary>Initialize for a specific resource node.</summary>
        public void Initialize(string resourceId, string spriteId, int tier = 1, string requiredTool = null)
        {
            _resourceId = resourceId;
            _isDepleted = false;
            _healthPercent = 1f;
            _usePrimitive = false;

            // Try to load resource sprite
            Sprite sprite = null;
            if (SpriteDatabase.Instance != null)
                sprite = SpriteDatabase.Instance.GetItemSprite(spriteId ?? resourceId);

            if (sprite != null)
            {
                // --- Sprite path ---
                if (_spriteRenderer == null)
                    _spriteRenderer = GetComponent<SpriteRenderer>();

                if (_spriteRenderer != null)
                {
                    _spriteRenderer.sprite = sprite;
                    _spriteRenderer.color = Color.white;
                }

                // Ensure BillboardSprite exists for 3D camera compatibility
                _billboard = GetComponent<BillboardSprite>();
                if (_billboard == null)
                    _billboard = gameObject.AddComponent<BillboardSprite>();
            }
            else
            {
                // --- Primitive fallback path ---
                _usePrimitive = true;
                _buildPrimitive(resourceId, tier);

                // Disable SpriteRenderer if one exists (primitive replaces it)
                if (_spriteRenderer != null)
                    _spriteRenderer.enabled = false;
            }

            // Show tool requirement icon if applicable
            if (_toolIcon != null)
            {
                if (!string.IsNullOrEmpty(requiredTool) && SpriteDatabase.Instance != null)
                {
                    _toolIcon.sprite = SpriteDatabase.Instance.GetItemSprite(requiredTool);
                    _toolIcon.gameObject.SetActive(true);
                }
                else
                {
                    _toolIcon.gameObject.SetActive(false);
                }
            }

            if (_healthBarRoot != null)
                _healthBarRoot.SetActive(false);
        }

        /// <summary>Update health bar display.</summary>
        public void UpdateHealth(float currentHP, float maxHP)
        {
            if (maxHP <= 0) return;

            _healthPercent = Mathf.Clamp01(currentHP / maxHP);

            if (_healthBarFill != null)
            {
                _healthBarFill.fillAmount = _healthPercent;
            }

            if (_healthBarRoot != null)
                _healthBarRoot.SetActive(_healthPercent < 1f);
        }

        /// <summary>Mark resource as depleted.</summary>
        public void SetDepleted(bool depleted)
        {
            _isDepleted = depleted;

            if (!_usePrimitive && _spriteRenderer != null)
            {
                _spriteRenderer.color = depleted ? _depletedColor : Color.white;
            }
            else if (_usePrimitive && _primitiveRoot != null)
            {
                // Tint all primitive renderers to show depletion
                var renderers = _primitiveRoot.GetComponentsInChildren<Renderer>();
                foreach (var r in renderers)
                {
                    if (r.material != null)
                        r.material.color = depleted
                            ? r.material.color * 0.5f
                            : r.material.color;
                }
            }

            if (_healthBarRoot != null)
                _healthBarRoot.SetActive(false);
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
        private void _buildPrimitive(string resourceId, int tier)
        {
            // Clean up any existing primitive
            if (_primitiveRoot != null)
                Destroy(_primitiveRoot);

            _primitiveRoot = PrimitiveShapeFactory.CreateResource(resourceId, tier);
            _primitiveRoot.transform.SetParent(transform, false);
            _primitiveRoot.transform.localPosition = Vector3.zero;
        }

        // ====================================================================
        // Update
        // ====================================================================

        private void Update()
        {
            // Billboard health bar to camera (world-space canvas always faces camera)
            if (_worldCanvas != null && Camera.main != null)
            {
                _worldCanvas.transform.rotation = Camera.main.transform.rotation;
            }
        }
    }
}
