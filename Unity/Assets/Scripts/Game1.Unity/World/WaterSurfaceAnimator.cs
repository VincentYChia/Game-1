// ============================================================================
// Game1.Unity.World.WaterSurfaceAnimator
// Created: 2026-02-18
//
// CPU-side animated water surface. Modifies water mesh vertices each frame
// to produce a gentle wave effect without requiring custom shaders.
// Works with any render pipeline (URP, Standard, Built-in).
//
// Attach to a GameObject that has water surface meshes as children
// (created by WorldRenderer). The animator finds all MeshFilter children
// tagged as water meshes and animates their vertices.
//
// When custom shaders are available, this can be replaced with GPU-side
// wave animation for better performance.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;

namespace Game1.Unity.World
{
    /// <summary>
    /// Animates water surface meshes by modifying vertex positions on the CPU.
    /// Produces Gerstner-like wave displacement using summed sine waves.
    /// Also scrolls UV coordinates for surface detail animation.
    /// </summary>
    public class WaterSurfaceAnimator : MonoBehaviour
    {
        // ====================================================================
        // Configuration
        // ====================================================================

        [Header("Wave Settings")]
        [Tooltip("Primary wave amplitude (vertical displacement)")]
        [SerializeField] private float _waveHeight = 0.04f;

        [Tooltip("Primary wave frequency (waves per world unit)")]
        [SerializeField] private float _waveFrequency = 1.2f;

        [Tooltip("Primary wave speed (world units per second)")]
        [SerializeField] private float _waveSpeed = 0.8f;

        [Tooltip("Secondary wave amplitude (cross-direction)")]
        [SerializeField] private float _wave2Height = 0.025f;

        [Tooltip("Secondary wave frequency")]
        [SerializeField] private float _wave2Frequency = 2.3f;

        [Tooltip("Secondary wave speed")]
        [SerializeField] private float _wave2Speed = 0.5f;

        [Header("UV Animation")]
        [Tooltip("UV scroll speed for surface detail")]
        [SerializeField] private float _uvScrollSpeed = 0.15f;

        [Header("Color Animation")]
        [Tooltip("Animate color between shallow and deep over time")]
        [SerializeField] private bool _animateColor = true;

        [SerializeField] private Color _shallowColor = new Color(0.12f, 0.45f, 0.82f, 0.85f);
        [SerializeField] private Color _deepColor = new Color(0.05f, 0.25f, 0.55f, 0.9f);

        [Tooltip("Color oscillation speed")]
        [SerializeField] private float _colorPulseSpeed = 0.3f;

        // ====================================================================
        // State
        // ====================================================================

        private struct WaterMeshData
        {
            public MeshFilter Filter;
            public Vector3[] OriginalVertices;
            public Vector2[] OriginalUVs;
            public Vector3[] AnimatedVertices;
            public Vector2[] AnimatedUVs;
        }

        private List<WaterMeshData> _waterMeshes = new List<WaterMeshData>();
        private float _timeAccumulator;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Start()
        {
            _discoverWaterMeshes();
        }

        private void Update()
        {
            _timeAccumulator += Time.deltaTime;

            for (int i = 0; i < _waterMeshes.Count; i++)
            {
                var data = _waterMeshes[i];
                if (data.Filter == null || data.Filter.mesh == null)
                    continue;

                _animateVertices(data);
                _animateUVs(data);

                data.Filter.mesh.vertices = data.AnimatedVertices;
                data.Filter.mesh.uv = data.AnimatedUVs;

                // Recalculate normals for correct lighting on waves
                data.Filter.mesh.RecalculateNormals();
            }

            // Animate water material color
            if (_animateColor)
                _animateMaterialColor();
        }

        // ====================================================================
        // Mesh Discovery
        // ====================================================================

        private void _discoverWaterMeshes()
        {
            _waterMeshes.Clear();

            // Find all water mesh objects (named *_Water by WorldRenderer)
            var meshFilters = GetComponentsInChildren<MeshFilter>(true);
            foreach (var filter in meshFilters)
            {
                if (filter.gameObject.name.Contains("Water") && filter.mesh != null)
                {
                    _registerMesh(filter);
                }
            }
        }

        private void _registerMesh(MeshFilter filter)
        {
            var mesh = filter.mesh;
            var data = new WaterMeshData
            {
                Filter = filter,
                OriginalVertices = (Vector3[])mesh.vertices.Clone(),
                OriginalUVs = mesh.uv != null ? (Vector2[])mesh.uv.Clone() : null,
                AnimatedVertices = new Vector3[mesh.vertexCount],
                AnimatedUVs = mesh.uv != null ? new Vector2[mesh.uv.Length] : null
            };
            _waterMeshes.Add(data);
        }

        /// <summary>
        /// Register a new water mesh for animation (called by WorldRenderer when
        /// new water chunks are loaded).
        /// </summary>
        public void RegisterWaterMesh(MeshFilter filter)
        {
            if (filter == null || filter.mesh == null) return;

            // Avoid duplicate registration
            for (int i = 0; i < _waterMeshes.Count; i++)
            {
                if (_waterMeshes[i].Filter == filter) return;
            }

            _registerMesh(filter);
        }

        /// <summary>
        /// Unregister a water mesh (called when chunk is unloaded).
        /// </summary>
        public void UnregisterWaterMesh(MeshFilter filter)
        {
            for (int i = _waterMeshes.Count - 1; i >= 0; i--)
            {
                if (_waterMeshes[i].Filter == filter)
                {
                    _waterMeshes.RemoveAt(i);
                    return;
                }
            }
        }

        /// <summary>Re-scan children for new water meshes.</summary>
        public void RefreshMeshes()
        {
            _discoverWaterMeshes();
        }

        // ====================================================================
        // Vertex Animation (Gerstner-like summed sine waves)
        // ====================================================================

        private void _animateVertices(WaterMeshData data)
        {
            float time = _timeAccumulator;

            for (int v = 0; v < data.OriginalVertices.Length; v++)
            {
                Vector3 original = data.OriginalVertices[v];

                // Get world position of vertex for consistent wave phase across chunks
                Vector3 worldPos = data.Filter.transform.TransformPoint(original);

                // Primary wave: along X axis
                float wave1 = Mathf.Sin(worldPos.x * _waveFrequency + time * _waveSpeed * Mathf.PI * 2f)
                            * _waveHeight;

                // Secondary wave: along Z axis (cross-direction for variety)
                float wave2 = Mathf.Sin(worldPos.z * _wave2Frequency + time * _wave2Speed * Mathf.PI * 2f)
                            * _wave2Height;

                // Tertiary subtle wave: diagonal for natural appearance
                float wave3 = Mathf.Sin((worldPos.x + worldPos.z) * 0.7f + time * 0.6f * Mathf.PI * 2f)
                            * _waveHeight * 0.3f;

                data.AnimatedVertices[v] = new Vector3(
                    original.x,
                    original.y + wave1 + wave2 + wave3,
                    original.z
                );
            }
        }

        // ====================================================================
        // UV Animation (scrolling for surface detail)
        // ====================================================================

        private void _animateUVs(WaterMeshData data)
        {
            if (data.OriginalUVs == null || data.AnimatedUVs == null) return;

            float scrollOffset = _timeAccumulator * _uvScrollSpeed;

            for (int v = 0; v < data.OriginalUVs.Length; v++)
            {
                data.AnimatedUVs[v] = new Vector2(
                    data.OriginalUVs[v].x + scrollOffset,
                    data.OriginalUVs[v].y + scrollOffset * 0.7f
                );
            }
        }

        // ====================================================================
        // Color Animation
        // ====================================================================

        private void _animateMaterialColor()
        {
            if (TerrainMaterialManager.Instance == null) return;
            var waterMat = TerrainMaterialManager.Instance.WaterMaterial;
            if (waterMat == null) return;

            float t = (Mathf.Sin(_timeAccumulator * _colorPulseSpeed * Mathf.PI * 2f) + 1f) * 0.5f;
            waterMat.color = Color.Lerp(_shallowColor, _deepColor, t);
        }

        // ====================================================================
        // Cleanup
        // ====================================================================

        private void OnDestroy()
        {
            _waterMeshes.Clear();
        }
    }
}
