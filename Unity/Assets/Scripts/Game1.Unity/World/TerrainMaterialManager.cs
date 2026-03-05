// ============================================================================
// Game1.Unity.World.TerrainMaterialManager
// Created: 2026-02-18
//
// Manages materials and shaders for 3D terrain rendering.
// Creates runtime materials for terrain chunks (vertex-colored),
// water surfaces (animated), and cliff edges (darkened).
// ============================================================================

using UnityEngine;

namespace Game1.Unity.World
{
    /// <summary>
    /// Centralized terrain material management.
    /// Provides shared materials for terrain chunks, water overlay, and edges.
    /// All materials use vertex colors by default so no texture atlas is required
    /// to get a good-looking result — textures are an optional enhancement.
    /// </summary>
    public class TerrainMaterialManager : MonoBehaviour
    {
        // ====================================================================
        // Inspector References (optional — auto-created if null)
        // ====================================================================

        [Header("Custom Materials (optional — leave null for auto-generated)")]
        [SerializeField] private Material _terrainMaterial;
        [SerializeField] private Material _waterMaterial;
        [SerializeField] private Material _edgeMaterial;

        [Header("Water Settings")]
        [SerializeField] private Color _waterColorShallow = new Color(0.12f, 0.45f, 0.82f, 0.85f);
        [SerializeField] private Color _waterColorDeep = new Color(0.05f, 0.25f, 0.55f, 0.9f);
        [SerializeField] private float _waterWaveSpeed = 0.8f;
        [SerializeField] private float _waterWaveScale = 0.3f;
        [SerializeField] private float _waterWaveHeight = 0.04f;

        // ====================================================================
        // Singleton (scene-level)
        // ====================================================================

        private static TerrainMaterialManager _instance;
        public static TerrainMaterialManager Instance => _instance;

        // ====================================================================
        // Properties
        // ====================================================================

        /// <summary>Material for solid terrain chunks (vertex-colored).</summary>
        public Material TerrainMaterial => _terrainMaterial;

        /// <summary>Material for water surface overlay.</summary>
        public Material WaterMaterial => _waterMaterial;

        /// <summary>Material for cliff edge faces (slightly darker).</summary>
        public Material EdgeMaterial => _edgeMaterial;

        // ====================================================================
        // Lifecycle
        // ====================================================================

        private void Awake()
        {
            _instance = this;
            _ensureMaterials();
        }

        private void Update()
        {
            // Animate water material
            if (_waterMaterial != null && _waterMaterial.HasProperty("_WaveOffset"))
            {
                float offset = Time.time * _waterWaveSpeed;
                _waterMaterial.SetFloat("_WaveOffset", offset);
                _waterMaterial.SetFloat("_WaveScale", _waterWaveScale);
                _waterMaterial.SetFloat("_WaveHeight", _waterWaveHeight);
            }
        }

        // ====================================================================
        // Material Creation
        // ====================================================================

        private void _ensureMaterials()
        {
            if (_terrainMaterial == null)
                _terrainMaterial = _createTerrainMaterial();

            if (_waterMaterial == null)
                _waterMaterial = _createWaterMaterial();

            if (_edgeMaterial == null)
                _edgeMaterial = _createEdgeMaterial();
        }

        /// <summary>
        /// Creates a terrain material that renders vertex colors with lighting.
        /// Shader priority:
        ///   1. Game1/VertexColorLit (custom Surface Shader, works in Built-in + URP compat)
        ///   2. Universal Render Pipeline/Particles/Lit (URP — natively reads vertex colors)
        ///   3. Particles/Standard Surface (Built-in — natively reads vertex colors)
        ///   4. Standard (last resort — will NOT show vertex colors)
        /// </summary>
        private Material _createTerrainMaterial()
        {
            Shader shader = _findVertexColorShader();

            var mat = new Material(shader);
            mat.name = "Game1_Terrain";
            mat.enableInstancing = true;
            mat.SetFloat("_Smoothness", 0.1f);
            mat.SetFloat("_Metallic", 0f);
            mat.color = Color.white;

            return mat;
        }

        /// <summary>
        /// Creates a semi-transparent water material.
        /// Uses the custom transparent shader, or falls back to particle shaders
        /// which handle transparency natively.
        /// </summary>
        private Material _createWaterMaterial()
        {
            Shader shader = Shader.Find("Game1/VertexColorTransparent");
            if (shader == null) shader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            if (shader == null) shader = Shader.Find("Particles/Standard Unlit");
            if (shader == null) shader = Shader.Find("Standard");

            var mat = new Material(shader);
            mat.name = "Game1_Water";

            // Configure transparency for Standard/URP fallbacks
            mat.SetFloat("_Surface", 1f); // Transparent (URP)
            mat.SetOverrideTag("RenderType", "Transparent");
            mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            mat.SetInt("_ZWrite", 0);
            mat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            mat.EnableKeyword("_ALPHABLEND_ON");
            mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");

            mat.color = _waterColorShallow;
            mat.SetFloat("_Smoothness", 0.85f);
            mat.SetFloat("_Metallic", 0.1f);

            return mat;
        }

        /// <summary>
        /// Creates a material for cliff edge faces that renders vertex colors.
        /// Uses the same shader chain as terrain (vertex-color-aware).
        /// </summary>
        private Material _createEdgeMaterial()
        {
            Shader shader = _findVertexColorShader();

            var mat = new Material(shader);
            mat.name = "Game1_TerrainEdge";
            mat.enableInstancing = true;
            mat.SetFloat("_Smoothness", 0.05f);
            mat.SetFloat("_Metallic", 0f);
            mat.color = Color.white;

            return mat;
        }

        /// <summary>
        /// Find a shader that correctly renders vertex colors with lighting.
        /// Tries our custom shader first, then particle shaders (which natively
        /// support vertex colors), then Standard as last resort.
        /// </summary>
        private static Shader _findVertexColorShader()
        {
            // Best: our custom vertex-color surface shader
            Shader shader = Shader.Find("Game1/VertexColorLit");
            if (shader != null) return shader;

            // URP fallback: particle shaders read vertex colors natively
            shader = Shader.Find("Universal Render Pipeline/Particles/Lit");
            if (shader != null) return shader;

            // Built-in fallback: particle surface shader reads vertex colors
            shader = Shader.Find("Particles/Standard Surface");
            if (shader != null) return shader;

            // Unlit fallback (vertex colors work but no lighting)
            shader = Shader.Find("Particles/Standard Unlit");
            if (shader != null) return shader;

            // Last resort (will NOT show vertex colors, but renders)
            shader = Shader.Find("Standard");
            if (shader != null) return shader;

            return Shader.Find("Diffuse");
        }

        // ====================================================================
        // Water Mesh Generation
        // ====================================================================

        /// <summary>
        /// Generate a water surface overlay mesh for water tiles in a chunk.
        /// The water mesh sits slightly above the water tile depression, creating
        /// a visible water surface plane.
        /// </summary>
        /// <param name="chunkSize">Tiles per side.</param>
        /// <param name="tileTypes">2D tile type array.</param>
        /// <param name="tileScale">World units per tile.</param>
        /// <returns>Mesh for water tiles only, or null if no water in chunk.</returns>
        public static Mesh GenerateWaterMesh(int chunkSize, string[,] tileTypes, float tileScale = 1f)
        {
            var vertices = new System.Collections.Generic.List<Vector3>();
            var normals = new System.Collections.Generic.List<Vector3>();
            var uvs = new System.Collections.Generic.List<Vector2>();
            var triangles = new System.Collections.Generic.List<int>();

            const float waterSurfaceY = -0.08f; // Just above the water tile depth

            for (int x = 0; x < chunkSize; x++)
            {
                for (int z = 0; z < chunkSize; z++)
                {
                    string tileType = (tileTypes != null && tileTypes[x, z] != null)
                        ? tileTypes[x, z].ToLowerInvariant()
                        : "grass";

                    if (tileType != "water") continue;

                    float x0 = x * tileScale;
                    float x1 = (x + 1) * tileScale;
                    float z0 = z * tileScale;
                    float z1 = (z + 1) * tileScale;

                    int baseIndex = vertices.Count;

                    vertices.Add(new Vector3(x0, waterSurfaceY, z0));
                    vertices.Add(new Vector3(x1, waterSurfaceY, z1));
                    vertices.Add(new Vector3(x1, waterSurfaceY, z0));
                    vertices.Add(new Vector3(x0, waterSurfaceY, z1));

                    normals.Add(Vector3.up);
                    normals.Add(Vector3.up);
                    normals.Add(Vector3.up);
                    normals.Add(Vector3.up);

                    // UVs for wave animation (world-space tiling)
                    uvs.Add(new Vector2(x0, z0));
                    uvs.Add(new Vector2(x1, z1));
                    uvs.Add(new Vector2(x1, z0));
                    uvs.Add(new Vector2(x0, z1));

                    triangles.Add(baseIndex + 0);
                    triangles.Add(baseIndex + 1);
                    triangles.Add(baseIndex + 2);
                    triangles.Add(baseIndex + 0);
                    triangles.Add(baseIndex + 3);
                    triangles.Add(baseIndex + 1);
                }
            }

            if (vertices.Count == 0) return null;

            var mesh = new Mesh();
            mesh.name = "ChunkWaterMesh";
            mesh.SetVertices(vertices);
            mesh.SetNormals(normals);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(triangles, 0);
            mesh.RecalculateBounds();
            return mesh;
        }
    }
}
