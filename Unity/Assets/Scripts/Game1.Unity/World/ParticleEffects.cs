// ============================================================================
// Game1.Unity.World.ParticleEffects
// Migrated from: core/minigame_effects.py (1,522 lines of custom particles)
// Migration phase: 6
// Date: 2026-02-13
//
// Replaces Python's custom pixel-based particles with Unity Particle System.
// Provides pre-configured effects for crafting, combat, and world events.
// ============================================================================

using UnityEngine;

namespace Game1.Unity.World
{
    /// <summary>
    /// Centralized particle effect spawner.
    /// Replaces Python's minigame_effects.py with Unity ParticleSystem.
    /// </summary>
    public class ParticleEffects : MonoBehaviour
    {
        public static ParticleEffects Instance { get; private set; }

        [Header("Prefabs")]
        [SerializeField] private ParticleSystem _sparksPrefab;
        [SerializeField] private ParticleSystem _embersPrefab;
        [SerializeField] private ParticleSystem _bubblesPrefab;
        [SerializeField] private ParticleSystem _steamPrefab;
        [SerializeField] private ParticleSystem _gearsPrefab;
        [SerializeField] private ParticleSystem _runeGlowPrefab;
        [SerializeField] private ParticleSystem _levelUpPrefab;
        [SerializeField] private ParticleSystem _craftSuccessPrefab;
        [SerializeField] private ParticleSystem _hitImpactPrefab;

        private void Awake()
        {
            Instance = this;
        }

        /// <summary>Spawn smithing sparks at position.</summary>
        public void PlaySparks(Vector3 position, int count = 20)
        {
            _playEffect(_sparksPrefab, position, count);
        }

        /// <summary>Spawn alchemy bubbles at position.</summary>
        public void PlayBubbles(Vector3 position, int count = 15)
        {
            _playEffect(_bubblesPrefab, position, count);
        }

        /// <summary>Spawn refining embers at position.</summary>
        public void PlayEmbers(Vector3 position, int count = 25)
        {
            _playEffect(_embersPrefab, position, count);
        }

        /// <summary>Spawn steam particles at position.</summary>
        public void PlaySteam(Vector3 position, int count = 10)
        {
            _playEffect(_steamPrefab, position, count);
        }

        /// <summary>Spawn engineering gear particles at position.</summary>
        public void PlayGears(Vector3 position, int count = 8)
        {
            _playEffect(_gearsPrefab, position, count);
        }

        /// <summary>Spawn enchanting rune glow at position.</summary>
        public void PlayRuneGlow(Vector3 position, int count = 12)
        {
            _playEffect(_runeGlowPrefab, position, count);
        }

        /// <summary>Spawn level-up celebration effect.</summary>
        public void PlayLevelUp(Vector3 position)
        {
            _playEffect(_levelUpPrefab, position, 50);
        }

        /// <summary>Spawn craft success effect.</summary>
        public void PlayCraftSuccess(Vector3 position)
        {
            _playEffect(_craftSuccessPrefab, position, 30);
        }

        /// <summary>Spawn hit impact at position.</summary>
        public void PlayHitImpact(Vector3 position, Color color)
        {
            if (_hitImpactPrefab == null) return;
            var ps = Instantiate(_hitImpactPrefab, position, Quaternion.identity, transform);
            var main = ps.main;
            main.startColor = color;
            ps.Emit(10);
            Destroy(ps.gameObject, main.duration + main.startLifetime.constantMax);
        }

        private void _playEffect(ParticleSystem prefab, Vector3 position, int count)
        {
            if (prefab == null) return;
            var ps = Instantiate(prefab, position, Quaternion.identity, transform);
            ps.Emit(count);
            var main = ps.main;
            Destroy(ps.gameObject, main.duration + main.startLifetime.constantMax);
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }
    }
}
