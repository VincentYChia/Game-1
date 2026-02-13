// ============================================================================
// Game1.Unity.World.EntityRenderer
// Migrated from: rendering/renderer.py (entity/station drawing)
// Migration phase: 6
// Date: 2026-02-13
//
// Renders placed entities: turrets, traps, bombs, crafting stations.
// ============================================================================

using UnityEngine;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Renders a placed entity (turret, trap, bomb, crafting station).
    /// Attached to entity prefabs.
    /// </summary>
    public class EntityRenderer : MonoBehaviour
    {
        [Header("Components")]
        [SerializeField] private SpriteRenderer _spriteRenderer;
        [SerializeField] private SpriteRenderer _rangeIndicator;

        [Header("Visual Settings")]
        [SerializeField] private Color _activeColor = Color.white;
        [SerializeField] private Color _inactiveColor = new Color(0.5f, 0.5f, 0.5f);

        private string _entityId;
        private string _entityType;
        private bool _isActive = true;

        /// <summary>Initialize for a specific entity type.</summary>
        public void Initialize(string entityId, string entityType, Sprite sprite = null)
        {
            _entityId = entityId;
            _entityType = entityType;

            if (_spriteRenderer != null)
            {
                if (sprite != null)
                    _spriteRenderer.sprite = sprite;
                else if (SpriteDatabase.Instance != null)
                    _spriteRenderer.sprite = SpriteDatabase.Instance.GetItemSprite(entityId);
            }

            SetActive(true);
        }

        /// <summary>Show/hide range indicator (for turrets).</summary>
        public void ShowRange(float radius, Color color)
        {
            if (_rangeIndicator == null) return;

            _rangeIndicator.gameObject.SetActive(true);
            _rangeIndicator.color = color;
            _rangeIndicator.transform.localScale = Vector3.one * radius * 2f;
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
            transform.position = worldPos;
        }
    }
}
