// ============================================================================
// Game1.Unity.World.EnemyRenderer
// Migrated from: rendering/renderer.py (enemy drawing within render_world)
// Migration phase: 6
// Date: 2026-02-13
//
// Renders individual enemy instances — sprite, health bar, corpse fade.
// Spawned from prefab by EnemySpawnerManager.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Renders a single enemy — sprite, health bar, aggro indicator, corpse fade.
    /// Attached to Enemy prefab. Drives visual from Phase 3 Enemy data.
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

        // ====================================================================
        // State
        // ====================================================================

        private string _enemyId;
        private float _healthPercent = 1f;
        private bool _isDead;
        private float _deathTimer;
        private bool _isBoss;

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>Initialize this renderer for a specific enemy.</summary>
        public void Initialize(string enemyId, bool isBoss = false)
        {
            _enemyId = enemyId;
            _isBoss = isBoss;

            // Load enemy sprite
            if (_spriteRenderer != null && SpriteDatabase.Instance != null)
            {
                _spriteRenderer.sprite = SpriteDatabase.Instance.GetEnemySprite(enemyId);
            }

            // Scale boss enemies
            if (isBoss)
            {
                transform.localScale = Vector3.one * 1.5f;
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
        }

        /// <summary>Update enemy world position.</summary>
        public void SetPosition(Vector3 worldPos)
        {
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

            // Billboard health bar to camera
            if (_worldCanvas != null && Camera.main != null)
            {
                _worldCanvas.transform.rotation = Camera.main.transform.rotation;
            }
        }
    }
}
