// ============================================================================
// Game1.Unity.World.EnemyRenderer
// Migrated from: rendering/renderer.py (enemy drawing within render_world)
// Migration phase: 6 (upgraded for 3D billboard rendering)
// Date: 2026-02-18
//
// Renders individual enemy instances — billboard sprite, health bar, corpse fade.
// In 3D mode, uses BillboardSprite to keep the sprite facing the camera.
// Spawned from prefab by EnemySpawnerManager.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Renders a single enemy — billboard sprite, health bar, aggro indicator, corpse fade.
    /// Attached to Enemy prefab. Drives visual from Phase 3 Enemy data.
    /// Ensures a BillboardSprite is present for 3D camera compatibility.
    /// </summary>
    public class EnemyRenderer : MonoBehaviour
    {
        // ====================================================================
        // Inspector References
        // ====================================================================

        [Header("Components")]
        [SerializeField] private SpriteRenderer _spriteRenderer;
        [SerializeField] private Canvas _worldCanvas;
        [SerializeField] private Image _healthBarFill;
        [SerializeField] private GameObject _healthBarRoot;

        [Header("Visual Settings")]
        [SerializeField] private Color _healthBarFullColor = new Color(0f, 0.8f, 0f);
        [SerializeField] private Color _healthBarLowColor = new Color(0.8f, 0f, 0f);
        [SerializeField] private float _healthBarOffset = 0.8f;
        [SerializeField] private float _corpseFadeDuration = 2f;

        [Header("3D Settings")]
        [Tooltip("Height offset above terrain surface")]
        [SerializeField] private float _heightAboveTerrain = 0.5f;

        // ====================================================================
        // State
        // ====================================================================

        private string _enemyId;
        private float _healthPercent = 1f;
        private bool _isDead;
        private float _deathTimer;
        private bool _isBoss;
        private BillboardSprite _billboard;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Awake()
        {
            // Ensure BillboardSprite exists for 3D camera compatibility
            _billboard = GetComponent<BillboardSprite>();
            if (_billboard == null)
                _billboard = gameObject.AddComponent<BillboardSprite>();
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>Initialize this renderer for a specific enemy.</summary>
        public void Initialize(string enemyId, bool isBoss = false)
        {
            _enemyId = enemyId;
            _isBoss = isBoss;

            // Load enemy sprite
            if (_spriteRenderer == null)
                _spriteRenderer = GetComponent<SpriteRenderer>();

            if (_spriteRenderer != null && SpriteDatabase.Instance != null)
            {
                _spriteRenderer.sprite = SpriteDatabase.Instance.GetEnemySprite(enemyId);
            }

            // Scale boss enemies (and their shadow)
            if (isBoss)
            {
                transform.localScale = Vector3.one * 1.5f;
                if (_billboard != null)
                    _billboard.SetShadowSize(0.9f);
            }

            _isDead = false;
            _deathTimer = 0f;
            _healthPercent = 1f;
            if (_healthBarRoot != null) _healthBarRoot.SetActive(true);
        }

        /// <summary>Update health bar display.</summary>
        public void UpdateHealth(float currentHealth, float maxHealth)
        {
            if (maxHealth <= 0) return;

            _healthPercent = Mathf.Clamp01(currentHealth / maxHealth);

            if (_healthBarFill != null)
            {
                _healthBarFill.fillAmount = _healthPercent;
                _healthBarFill.color = Color.Lerp(_healthBarLowColor, _healthBarFullColor, _healthPercent);
            }

            // Show health bar only when damaged
            if (_healthBarRoot != null)
            {
                _healthBarRoot.SetActive(_healthPercent < 1f);
            }
        }

        /// <summary>Trigger death animation (corpse fade).</summary>
        public void OnDeath()
        {
            _isDead = true;
            _deathTimer = 0f;

            if (_healthBarRoot != null)
                _healthBarRoot.SetActive(false);

            // Hide shadow on death
            if (_billboard != null)
                _billboard.SetShadowVisible(false);
        }

        /// <summary>Update enemy world position.</summary>
        public void SetPosition(Vector3 worldPos)
        {
            worldPos.y = _heightAboveTerrain;
            transform.position = worldPos;
        }

        // ====================================================================
        // Update
        // ====================================================================

        private void Update()
        {
            // Corpse fade
            if (_isDead)
            {
                _deathTimer += Time.deltaTime;
                float alpha = 1f - (_deathTimer / _corpseFadeDuration);

                if (alpha <= 0f)
                {
                    Destroy(gameObject);
                    return;
                }

                if (_spriteRenderer != null)
                {
                    var color = _spriteRenderer.color;
                    color.a = alpha;
                    _spriteRenderer.color = color;
                }
            }

            // Billboard health bar to camera (world-space canvas always faces camera)
            if (_worldCanvas != null && Camera.main != null)
            {
                _worldCanvas.transform.rotation = Camera.main.transform.rotation;
            }
        }
    }
}
