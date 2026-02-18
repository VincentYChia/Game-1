// ============================================================================
// Game1.Unity.World.EntityRenderer
// Migrated from: rendering/renderer.py (entity/station drawing)
// Migration phase: 6 (upgraded for 3D billboard rendering)
// Date: 2026-02-18
//
// Renders placed entities: turrets, traps, bombs, crafting stations.
// In 3D mode, uses BillboardSprite to keep sprites camera-facing.
// Range indicators are projected onto the XZ ground plane.
// ============================================================================

using UnityEngine;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Renders a placed entity (turret, trap, bomb, crafting station).
    /// Attached to entity prefabs. Ensures BillboardSprite is present for 3D.
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
        private BillboardSprite _billboard;

        private void Awake()
        {
            // Ensure BillboardSprite exists for 3D camera compatibility
            _billboard = GetComponent<BillboardSprite>();
            if (_billboard == null)
                _billboard = gameObject.AddComponent<BillboardSprite>();
        }

        /// <summary>Initialize for a specific entity type.</summary>
        public void Initialize(string entityId, string entityType, Sprite sprite = null)
        {
            _entityId = entityId;
            _entityType = entityType;

            if (_spriteRenderer == null)
                _spriteRenderer = GetComponent<SpriteRenderer>();

            if (_spriteRenderer != null)
            {
                if (sprite != null)
                    _spriteRenderer.sprite = sprite;
                else if (SpriteDatabase.Instance != null)
                    _spriteRenderer.sprite = SpriteDatabase.Instance.GetItemSprite(entityId);
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
            if (_spriteRenderer != null)
                _spriteRenderer.color = active ? _activeColor : _inactiveColor;
        }

        /// <summary>Set world position.</summary>
        public void SetPosition(Vector3 worldPos)
        {
            worldPos.y = _heightAboveTerrain;
            transform.position = worldPos;
        }
    }
}
