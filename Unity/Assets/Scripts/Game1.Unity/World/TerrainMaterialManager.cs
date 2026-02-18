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
        /// Creates a terrain material that renders vertex colors with basic lighting.
        /// Uses the Universal Render Pipeline Lit shader if available, otherwise
        /// falls back to Standard shader with vertex color support.
        /// </summary>
        private Material _createTerrainMaterial()
        {
            // Try URP Lit first, then Standard
            Shader shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("Standard");
            if (shader == null) shader = Shader.Find("Diffuse");

            var mat = new Material(shader);
            mat.name = "Game1_Terrain";
            mat.enableInstancing = true;

            // Enable vertex colors
            mat.SetFloat("_Smoothness", 0.1f);
            mat.SetFloat("_Metallic", 0f);

            // For vertex color rendering, we need a white base texture
            // and let vertex colors multiply
            var whiteTex = new Texture2D(1, 1);
            whiteTex.SetPixel(0, 0, Color.white);
            whiteTex.Apply();
            mat.mainTexture = whiteTex;

            return mat;
        }

        /// <summary>
        /// Creates a semi-transparent water material with basic wave animation support.
        /// </summary>
        private Material _createWaterMaterial()
        {
            Shader shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("Standard");
            if (shader == null) shader = Shader.Find("Diffuse");

            var mat = new Material(shader);
            mat.name = "Game1_Water";

            // Configure for transparency
            mat.SetFloat("_Surface", 1f); // Transparent (URP)
            mat.SetFloat("_Blend", 0f);   // Alpha blend
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
        /// Creates a slightly darker material for cliff edge faces.
        /// Uses the same base as terrain but with a slight darkening tint.
        /// </summary>
        private Material _createEdgeMaterial()
        {
            Shader shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("Standard");
            if (shader == null) shader = Shader.Find("Diffuse");

            var mat = new Material(shader);
            mat.name = "Game1_TerrainEdge";
            mat.enableInstancing = true;
            mat.SetFloat("_Smoothness", 0.05f);
            mat.SetFloat("_Metallic", 0f);

            var whiteTex = new Texture2D(1, 1);
            whiteTex.SetPixel(0, 0, Color.white);
            whiteTex.Apply();
            mat.mainTexture = whiteTex;

            return mat;
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
