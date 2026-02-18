// ============================================================================
// Game1.Unity.World.ResourceRenderer
// Migrated from: rendering/renderer.py (resource drawing within render_world)
// Migration phase: 6 (upgraded for 3D billboard rendering)
// Date: 2026-02-18
//
// Renders resource nodes (trees, ores, herbs) with HP bars and tool icons.
// In 3D mode, uses BillboardSprite to keep sprites camera-facing.
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
    /// Attached to ResourceNode prefab. Ensures BillboardSprite is present for 3D.
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
        private BillboardSprite _billboard;

        private void Awake()
        {
            // Ensure BillboardSprite exists for 3D camera compatibility
            _billboard = GetComponent<BillboardSprite>();
            if (_billboard == null)
                _billboard = gameObject.AddComponent<BillboardSprite>();
        }

        /// <summary>Initialize for a specific resource node.</summary>
        public void Initialize(string resourceId, string spriteId, string requiredTool = null)
        {
            _resourceId = resourceId;
            _isDepleted = false;
            _healthPercent = 1f;

            if (_spriteRenderer == null)
                _spriteRenderer = GetComponent<SpriteRenderer>();

            if (_spriteRenderer != null && SpriteDatabase.Instance != null)
            {
                _spriteRenderer.sprite = SpriteDatabase.Instance.GetItemSprite(spriteId ?? resourceId);
                _spriteRenderer.color = Color.white;
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

            if (_spriteRenderer != null)
            {
                _spriteRenderer.color = depleted ? _depletedColor : Color.white;
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
