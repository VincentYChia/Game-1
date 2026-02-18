// ============================================================================
// Game1.Unity.World.ParticleEffects
// Migrated from: core/minigame_effects.py (1,522 lines of custom particles)
// Migration phase: 6 (upgraded for 3D with runtime particle creation)
// Date: 2026-02-18
//
// Replaces Python's custom pixel-based particles with Unity Particle System.
// Creates particle systems at runtime if prefabs are not assigned, matching
// the visual characteristics from the Python source:
//   - SparkParticle: 2-5px, 0.3-0.8s, yellow/orange, gravity=200, upward bias
//   - EmberParticle: 3-8px, 1.5-3.0s, orange glow, floats upward
//   - BubbleParticle: larger, translucent, floats upward with sway
//   - SteamParticle: large soft particles, fade quickly, expand outward
//   - GearParticle: metallic, spinning, short duration
//   - RuneGlow: blue-white, spiraling, magical feel
//   - LevelUp: multi-color burst, celebratory
//   - CraftSuccess: green/gold stars
//   - HitImpact: damage-colored splash, very short
// ============================================================================

using UnityEngine;

namespace Game1.Unity.World
{
    /// <summary>
    /// Centralized particle effect spawner for crafting, combat, and world events.
    /// If inspector prefabs are not assigned, auto-creates runtime particle systems
    /// with visual characteristics matching the Python minigame_effects.py source.
    /// All effects work in 3D world space.
    /// </summary>
    public class ParticleEffects : MonoBehaviour
    {
        public static ParticleEffects Instance { get; private set; }

        [Header("Prefabs (optional — auto-created if null)")]
        [SerializeField] private ParticleSystem _sparksPrefab;
        [SerializeField] private ParticleSystem _embersPrefab;
        [SerializeField] private ParticleSystem _bubblesPrefab;
        [SerializeField] private ParticleSystem _steamPrefab;
        [SerializeField] private ParticleSystem _gearsPrefab;
        [SerializeField] private ParticleSystem _runeGlowPrefab;
        [SerializeField] private ParticleSystem _levelUpPrefab;
        [SerializeField] private ParticleSystem _craftSuccessPrefab;
        [SerializeField] private ParticleSystem _hitImpactPrefab;

        private Material _particleMaterial;

        private void Awake()
        {
            Instance = this;
            _ensureParticleMaterial();
            _ensureAllPrefabs();
        }

        // ====================================================================
        // Material Setup
        // ====================================================================

        private void _ensureParticleMaterial()
        {
            if (_particleMaterial != null) return;

            // Use a particle-friendly shader: additive blend for glowing effects
            Shader shader = Shader.Find("Particles/Standard Unlit")
                ?? Shader.Find("Universal Render Pipeline/Particles/Unlit")
                ?? Shader.Find("Sprites/Default");

            if (shader != null)
            {
                _particleMaterial = new Material(shader);
                _particleMaterial.name = "Game1_ParticleDefault";

                // Configure for additive blending (glowing particles)
                _particleMaterial.SetFloat("_Mode", 1f); // Additive
                _particleMaterial.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
                _particleMaterial.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.One);

                // Create a soft circular particle texture
                var tex = _createParticleTexture();
                _particleMaterial.mainTexture = tex;
            }
        }

        private static Texture2D _createParticleTexture()
        {
            int size = 32;
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
            float center = size * 0.5f;

            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x - center) / center;
                    float dy = (y - center) / center;
                    float dist = Mathf.Sqrt(dx * dx + dy * dy);
                    float alpha = Mathf.Clamp01(1f - dist);
                    alpha *= alpha; // Quadratic falloff for soft edge
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, alpha));
                }
            }

            tex.Apply();
            tex.filterMode = FilterMode.Bilinear;
            tex.wrapMode = TextureWrapMode.Clamp;
            return tex;
        }

        // ====================================================================
        // Prefab Auto-Creation
        // ====================================================================

        private void _ensureAllPrefabs()
        {
            if (_sparksPrefab == null)
                _sparksPrefab = _createPrefab("Sparks",
                    new Color(1f, 0.85f, 0.2f), new Color(1f, 0.5f, 0.1f),
                    lifetime: 0.5f, speed: 4f, size: 0.12f, gravity: 2f,
                    shape: ParticleSystemShapeType.Cone, shapeAngle: 35f);

            if (_embersPrefab == null)
                _embersPrefab = _createPrefab("Embers",
                    new Color(1f, 0.6f, 0.1f), new Color(0.8f, 0.2f, 0f),
                    lifetime: 2f, speed: 0.8f, size: 0.18f, gravity: -0.1f,
                    shape: ParticleSystemShapeType.Cone, shapeAngle: 15f);

            if (_bubblesPrefab == null)
                _bubblesPrefab = _createPrefab("Bubbles",
                    new Color(0.3f, 0.7f, 1f, 0.6f), new Color(0.5f, 0.9f, 1f, 0.3f),
                    lifetime: 1.5f, speed: 0.6f, size: 0.2f, gravity: -0.3f,
                    shape: ParticleSystemShapeType.Sphere, shapeAngle: 0f);

            if (_steamPrefab == null)
                _steamPrefab = _createPrefab("Steam",
                    new Color(0.9f, 0.9f, 0.95f, 0.5f), new Color(0.8f, 0.8f, 0.85f, 0f),
                    lifetime: 1.2f, speed: 1f, size: 0.4f, gravity: -0.5f,
                    shape: ParticleSystemShapeType.Cone, shapeAngle: 20f);

            if (_gearsPrefab == null)
                _gearsPrefab = _createPrefab("Gears",
                    new Color(0.7f, 0.7f, 0.75f), new Color(0.5f, 0.5f, 0.55f),
                    lifetime: 0.8f, speed: 2f, size: 0.15f, gravity: 1f,
                    shape: ParticleSystemShapeType.Cone, shapeAngle: 45f);

            if (_runeGlowPrefab == null)
                _runeGlowPrefab = _createPrefab("RuneGlow",
                    new Color(0.4f, 0.6f, 1f), new Color(0.8f, 0.9f, 1f),
                    lifetime: 1.5f, speed: 1.5f, size: 0.15f, gravity: -0.2f,
                    shape: ParticleSystemShapeType.Sphere, shapeAngle: 0f);

            if (_levelUpPrefab == null)
                _levelUpPrefab = _createPrefab("LevelUp",
                    new Color(1f, 0.9f, 0.3f), new Color(1f, 1f, 1f),
                    lifetime: 2f, speed: 3f, size: 0.2f, gravity: -0.5f,
                    shape: ParticleSystemShapeType.Sphere, shapeAngle: 0f);

            if (_craftSuccessPrefab == null)
                _craftSuccessPrefab = _createPrefab("CraftSuccess",
                    new Color(0.3f, 1f, 0.3f), new Color(1f, 0.9f, 0.3f),
                    lifetime: 1.5f, speed: 2.5f, size: 0.15f, gravity: -0.3f,
                    shape: ParticleSystemShapeType.Sphere, shapeAngle: 0f);

            if (_hitImpactPrefab == null)
                _hitImpactPrefab = _createPrefab("HitImpact",
                    new Color(1f, 0.3f, 0.2f), new Color(1f, 0.6f, 0.3f),
                    lifetime: 0.3f, speed: 5f, size: 0.1f, gravity: 3f,
                    shape: ParticleSystemShapeType.Hemisphere, shapeAngle: 0f);
        }

        private ParticleSystem _createPrefab(string name,
            Color startColor, Color endColor,
            float lifetime, float speed, float size, float gravity,
            ParticleSystemShapeType shape, float shapeAngle)
        {
            var go = new GameObject($"PS_{name}");
            go.transform.SetParent(transform, false);
            go.SetActive(false); // Template — not active

            var ps = go.AddComponent<ParticleSystem>();

            // Main module
            var main = ps.main;
            main.duration = lifetime;
            main.startLifetime = new ParticleSystem.MinMaxCurve(lifetime * 0.6f, lifetime);
            main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.5f, speed);
            main.startSize = new ParticleSystem.MinMaxCurve(size * 0.5f, size);
            main.startColor = new ParticleSystem.MinMaxGradient(startColor, endColor);
            main.gravityModifier = gravity;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.playOnAwake = false;
            main.maxParticles = 100;

            // Emission module (off — we use manual Emit calls)
            var emission = ps.emission;
            emission.enabled = false;

            // Shape module
            var shapeModule = ps.shape;
            shapeModule.enabled = true;
            shapeModule.shapeType = shape;
            if (shape == ParticleSystemShapeType.Cone)
                shapeModule.angle = shapeAngle;
            shapeModule.radius = 0.2f;

            // Size over lifetime (shrink)
            var sol = ps.sizeOverLifetime;
            sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(
                new Keyframe(0f, 1f),
                new Keyframe(0.7f, 0.6f),
                new Keyframe(1f, 0f)
            ));

            // Color over lifetime (fade out)
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var gradient = new Gradient();
            gradient.SetKeys(
                new GradientColorKey[] {
                    new GradientColorKey(startColor, 0f),
                    new GradientColorKey(endColor, 1f)
                },
                new GradientAlphaKey[] {
                    new GradientAlphaKey(startColor.a > 0 ? startColor.a : 1f, 0f),
                    new GradientAlphaKey(0.8f, 0.5f),
                    new GradientAlphaKey(0f, 1f)
                }
            );
            col.color = gradient;

            // Renderer
            var renderer = go.GetComponent<ParticleSystemRenderer>();
            if (renderer != null && _particleMaterial != null)
            {
                renderer.material = _particleMaterial;
                renderer.renderMode = ParticleSystemRenderMode.Billboard;
            }

            return ps;
        }

        // ====================================================================
        // Public API — Spawning Effects
        // ====================================================================

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

        /// <summary>Spawn hit impact at position with custom color.</summary>
        public void PlayHitImpact(Vector3 position, Color color)
        {
            if (_hitImpactPrefab == null) return;
            var ps = Instantiate(_hitImpactPrefab, position, Quaternion.identity, transform);
            ps.gameObject.SetActive(true);
            var main = ps.main;
            main.startColor = color;
            ps.Emit(10);
            Destroy(ps.gameObject, main.duration + main.startLifetime.constantMax);
        }

        private void _playEffect(ParticleSystem prefab, Vector3 position, int count)
        {
            if (prefab == null) return;
            var ps = Instantiate(prefab, position, Quaternion.identity, transform);
            ps.gameObject.SetActive(true);
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
