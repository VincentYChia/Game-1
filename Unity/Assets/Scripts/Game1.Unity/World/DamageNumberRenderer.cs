// ============================================================================
// Game1.Unity.World.DamageNumberRenderer
// Migrated from: rendering/renderer.py (damage number drawing)
// Migration phase: 6
// Date: 2026-02-13
//
// Floating damage numbers with upward drift and fade.
// Uses world-space TextMeshPro for camera-facing text.
// ============================================================================

using UnityEngine;
using TMPro;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Manages floating damage number display.
    /// Pool-based spawning for performance.
    /// Numbers float upward and fade over their lifetime.
    /// </summary>
    public class DamageNumberRenderer : MonoBehaviour
    {
        public static DamageNumberRenderer Instance { get; private set; }

        [Header("Prefab")]
        [SerializeField] private GameObject _damageNumberPrefab;

        [Header("Settings")]
        [SerializeField] private float _riseSpeed = 2f;
        [SerializeField] private float _lifetime = 1.5f;
        [SerializeField] private float _critScale = 1.5f;
        [SerializeField] private int _poolSize = 30;

        private GameObject[] _pool;
        private int _poolIndex;

        private void Awake()
        {
            Instance = this;
            _initializePool();
        }

        /// <summary>
        /// Spawn a floating damage number at a world position.
        /// </summary>
        public void SpawnDamageNumber(Vector3 position, float damage, bool isCrit = false, string damageType = "physical")
        {
            var go = _getFromPool();
            if (go == null) return;

            go.transform.position = position + Vector3.up * 0.5f;
            go.SetActive(true);

            var tmp = go.GetComponentInChildren<TextMeshPro>();
            if (tmp != null)
            {
                tmp.text = Mathf.RoundToInt(damage).ToString();
                tmp.color = _getDamageColor(damageType, isCrit);
                tmp.fontSize = isCrit ? 8f : 5f;
            }

            go.transform.localScale = isCrit ? Vector3.one * _critScale : Vector3.one;

            var mover = go.GetComponent<DamageNumberMover>();
            if (mover == null) mover = go.AddComponent<DamageNumberMover>();
            mover.Initialize(_riseSpeed, _lifetime);
        }

        /// <summary>Spawn a healing number (green, upward).</summary>
        public void SpawnHealNumber(Vector3 position, float amount)
        {
            var go = _getFromPool();
            if (go == null) return;

            go.transform.position = position + Vector3.up * 0.5f;
            go.SetActive(true);

            var tmp = go.GetComponentInChildren<TextMeshPro>();
            if (tmp != null)
            {
                tmp.text = "+" + Mathf.RoundToInt(amount);
                tmp.color = (Color)ColorConverter.DamageHeal;
                tmp.fontSize = 5f;
            }

            var mover = go.GetComponent<DamageNumberMover>();
            if (mover == null) mover = go.AddComponent<DamageNumberMover>();
            mover.Initialize(_riseSpeed, _lifetime);
        }

        private Color _getDamageColor(string damageType, bool isCrit)
        {
            if (isCrit) return (Color)ColorConverter.DamageCrit;

            return damageType?.ToLowerInvariant() switch
            {
                "fire" => (Color)ColorConverter.DamageFire,
                "ice" => (Color)ColorConverter.DamageIce,
                "lightning" => (Color)ColorConverter.DamageLightning,
                "poison" => (Color)ColorConverter.DamagePoison,
                _ => (Color)ColorConverter.DamagePhysical
            };
        }

        private void _initializePool()
        {
            _pool = new GameObject[_poolSize];
            for (int i = 0; i < _poolSize; i++)
            {
                if (_damageNumberPrefab != null)
                {
                    _pool[i] = Instantiate(_damageNumberPrefab, transform);
                }
                else
                {
                    // Create simple fallback
                    _pool[i] = new GameObject("DamageNumber");
                    _pool[i].transform.SetParent(transform);
                    var tmp = _pool[i].AddComponent<TextMeshPro>();
                    tmp.alignment = TextAlignmentOptions.Center;
                    tmp.fontSize = 5f;
                }
                _pool[i].SetActive(false);
            }
        }

        private GameObject _getFromPool()
        {
            for (int i = 0; i < _poolSize; i++)
            {
                int idx = (_poolIndex + i) % _poolSize;
                if (!_pool[idx].activeInHierarchy)
                {
                    _poolIndex = (idx + 1) % _poolSize;
                    return _pool[idx];
                }
            }
            // Pool exhausted, recycle oldest
            _poolIndex = (_poolIndex + 1) % _poolSize;
            _pool[_poolIndex].SetActive(false);
            return _pool[_poolIndex];
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }
    }

    /// <summary>
    /// Helper component: moves damage number upward and fades it out.
    /// </summary>
    public class DamageNumberMover : MonoBehaviour
    {
        private float _riseSpeed;
        private float _lifetime;
        private float _elapsed;
        private TextMeshPro _tmp;
        private Color _startColor;

        public void Initialize(float riseSpeed, float lifetime)
        {
            _riseSpeed = riseSpeed;
            _lifetime = lifetime;
            _elapsed = 0f;

            _tmp = GetComponentInChildren<TextMeshPro>();
            if (_tmp != null) _startColor = _tmp.color;
        }

        private void Update()
        {
            _elapsed += Time.deltaTime;

            // Rise upward
            transform.position += Vector3.up * _riseSpeed * Time.deltaTime;

            // Fade out
            if (_tmp != null)
            {
                float alpha = 1f - (_elapsed / _lifetime);
                _tmp.color = new Color(_startColor.r, _startColor.g, _startColor.b, Mathf.Max(0f, alpha));
            }

            // Billboard to camera
            if (Camera.main != null)
                transform.rotation = Camera.main.transform.rotation;

            // Deactivate when done
            if (_elapsed >= _lifetime)
            {
                gameObject.SetActive(false);
            }
        }
    }
}
