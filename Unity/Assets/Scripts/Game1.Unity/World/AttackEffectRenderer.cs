// ============================================================================
// Game1.Unity.World.AttackEffectRenderer
// Migrated from: rendering/renderer.py (lines 6587-6657: _render_attack_effects)
// Migration phase: 6
// Date: 2026-02-13
//
// Renders attack visual effects: melee lines, ranged lines, AoE circles, beams.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;

namespace Game1.Unity.World
{
    /// <summary>
    /// Renders attack visual effects using LineRenderers.
    /// Effects are temporary and fade over their duration.
    /// </summary>
    public class AttackEffectRenderer : MonoBehaviour
    {
        public static AttackEffectRenderer Instance { get; private set; }

        [Header("Settings")]
        [SerializeField] private Material _lineMaterial;
        [SerializeField] private float _defaultDuration = 0.3f;
        [SerializeField] private int _circleSegments = 32;

        private List<ActiveEffect> _activeEffects = new List<ActiveEffect>();

        private class ActiveEffect
        {
            public GameObject GameObject;
            public LineRenderer LineRenderer;
            public float Duration;
            public float Elapsed;
            public Color StartColor;
        }

        private void Awake()
        {
            Instance = this;
        }

        /// <summary>Draw an attack line from attacker to target.</summary>
        public void DrawAttackLine(Vector3 from, Vector3 to, Color color, float width = 0.1f, float duration = -1f)
        {
            if (duration < 0) duration = _defaultDuration;

            var go = new GameObject("AttackLine");
            go.transform.SetParent(transform);

            var lr = go.AddComponent<LineRenderer>();
            lr.positionCount = 2;
            lr.SetPosition(0, from + Vector3.up * 0.1f);
            lr.SetPosition(1, to + Vector3.up * 0.1f);
            lr.startWidth = width;
            lr.endWidth = width * 0.5f;
            lr.startColor = color;
            lr.endColor = color;
            if (_lineMaterial != null) lr.material = _lineMaterial;
            lr.useWorldSpace = true;

            _activeEffects.Add(new ActiveEffect
            {
                GameObject = go,
                LineRenderer = lr,
                Duration = duration,
                Elapsed = 0f,
                StartColor = color
            });
        }

        /// <summary>Draw an AoE circle at a position.</summary>
        public void DrawAoECircle(Vector3 center, float radius, Color color, float width = 0.1f, float duration = -1f)
        {
            if (duration < 0) duration = _defaultDuration;

            var go = new GameObject("AoECircle");
            go.transform.SetParent(transform);

            var lr = go.AddComponent<LineRenderer>();
            lr.positionCount = _circleSegments + 1;
            lr.loop = true;
            lr.startWidth = width;
            lr.endWidth = width;
            lr.startColor = color;
            lr.endColor = color;
            if (_lineMaterial != null) lr.material = _lineMaterial;
            lr.useWorldSpace = true;

            for (int i = 0; i <= _circleSegments; i++)
            {
                float angle = (float)i / _circleSegments * Mathf.PI * 2f;
                Vector3 pos = center + new Vector3(Mathf.Cos(angle) * radius, 0.1f, Mathf.Sin(angle) * radius);
                lr.SetPosition(i % (lr.positionCount), pos);
            }

            _activeEffects.Add(new ActiveEffect
            {
                GameObject = go,
                LineRenderer = lr,
                Duration = duration,
                Elapsed = 0f,
                StartColor = color
            });
        }

        /// <summary>Draw a beam effect from source to target.</summary>
        public void DrawBeam(Vector3 from, Vector3 to, Color color, float width = 0.15f, float duration = 0.5f)
        {
            DrawAttackLine(from, to, color, width, duration);
        }

        private void Update()
        {
            // Update and clean up active effects
            for (int i = _activeEffects.Count - 1; i >= 0; i--)
            {
                var effect = _activeEffects[i];
                effect.Elapsed += Time.deltaTime;

                float progress = effect.Elapsed / effect.Duration;
                if (progress >= 1f)
                {
                    Destroy(effect.GameObject);
                    _activeEffects.RemoveAt(i);
                    continue;
                }

                // Fade out
                float alpha = 1f - progress;
                var fadeColor = new Color(effect.StartColor.r, effect.StartColor.g, effect.StartColor.b, alpha);
                if (effect.LineRenderer != null)
                {
                    effect.LineRenderer.startColor = fadeColor;
                    effect.LineRenderer.endColor = fadeColor;
                }
            }
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
            foreach (var effect in _activeEffects)
            {
                if (effect.GameObject != null)
                    Destroy(effect.GameObject);
            }
            _activeEffects.Clear();
        }
    }
}
