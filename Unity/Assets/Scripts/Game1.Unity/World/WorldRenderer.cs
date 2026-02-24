// ============================================================================
// Game1.Unity.World.WorldRenderer
// Migrated from: rendering/renderer.py (lines 965-1391: render_world)
// Migration phase: 6 (upgraded for 3D terrain rendering)
// Date: 2026-02-18
//
// Manages 3D terrain chunk rendering. Replaces the flat 2D Tilemap with
// procedurally-generated 3D meshes per chunk, including height variation,
// water surfaces, and cliff edges. Falls back to Tilemap if configured.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Tilemaps;
using Game1.Core;
using Game1.Data.Enums;
using Game1.Systems.World;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.World
{
    /// <summary>
    /// Renders the game world using either 3D mesh terrain (default) or
    /// Unity Tilemap (legacy 2D mode). Manages chunk visibility based on
    /// camera position, loading/unloading chunks as the player moves.
    /// </summary>
    public class WorldRenderer : MonoBehaviour
    {
        // ====================================================================
        // Inspector References
        // ====================================================================

        [Header("Rendering Mode")]
        [Tooltip("Use 3D mesh terrain. Disable for legacy 2D Tilemap mode.")]
        [SerializeField] private bool _use3DMesh = false;

        [Header("Tilemap (Legacy 2D Mode)")]
        [SerializeField] private Tilemap _groundTilemap;
        [SerializeField] private Grid _grid;

        [Header("Tile Assets (Legacy 2D Mode)")]
        [SerializeField] private TileBase _grassTile;
        [SerializeField] private TileBase _waterTile;
        [SerializeField] private TileBase _stoneTile;
        [SerializeField] private TileBase _sandTile;
        [SerializeField] private TileBase _caveTile;
        [SerializeField] private TileBase _snowTile;
        [SerializeField] private TileBase _dirtTile;

        [Header("Configuration")]
        [SerializeField] private int _chunkLoadRadius = 4;
        [SerializeField] private int _chunkUnloadRadius = 6;

        // ====================================================================
        // State
        // ====================================================================

        private HashSet<Vector2Int> _loadedChunks = new HashSet<Vector2Int>();
        private Dictionary<Vector2Int, ChunkRenderData> _chunkObjects = new Dictionary<Vector2Int, ChunkRenderData>();
        private CameraController _cameraController;
        private int _chunkSize;

        // Container for chunk GameObjects (keeps hierarchy clean)
        private Transform _chunkContainer;

        // ====================================================================
        // Chunk Render Data
        // ====================================================================

        private struct ChunkRenderData
        {
            public GameObject TerrainObject;
            public GameObject WaterObject;
            public GameObject EdgeObject;
        }

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Start()
        {
            _chunkSize = GameConfig.ChunkSize;
            _cameraController = FindFirstObjectByType<CameraController>();

            if (_use3DMesh)
            {
                _chunkContainer = new GameObject("ChunkContainer").transform;
                _chunkContainer.SetParent(transform, false);

                // Disable tilemap objects if they exist (switching to 3D mode)
                if (_groundTilemap != null) _groundTilemap.gameObject.SetActive(false);
                if (_grid != null) _grid.gameObject.SetActive(false);
            }
            else
            {
                // Legacy 2D mode: create fallback tiles if not assigned
                if (_grassTile == null) _createFallbackTiles();
            }
        }

        // ====================================================================
        // Per-Frame Update
        // ====================================================================

        private void LateUpdate()
        {
            if (GameManager.Instance == null || GameManager.Instance.World == null) return;
            if (GameManager.Instance.Player == null) return;

            var playerPos = GameManager.Instance.Player.Position;
            var playerChunk = new Vector2Int(
                Mathf.FloorToInt(playerPos.X / _chunkSize),
                Mathf.FloorToInt(playerPos.Z / _chunkSize)
            );

            // Load new chunks in radius
            for (int dx = -_chunkLoadRadius; dx <= _chunkLoadRadius; dx++)
            {
                for (int dz = -_chunkLoadRadius; dz <= _chunkLoadRadius; dz++)
                {
                    var chunkCoord = new Vector2Int(playerChunk.x + dx, playerChunk.y + dz);
                    if (!_loadedChunks.Contains(chunkCoord))
                    {
                        if (_use3DMesh)
                            _loadChunk3D(chunkCoord);
                        else
                            _loadChunkTilemap(chunkCoord);
                    }
                }
            }

            // Unload distant chunks
            var toRemove = new List<Vector2Int>();
            foreach (var chunkCoord in _loadedChunks)
            {
                int dist = Mathf.Max(
                    Mathf.Abs(chunkCoord.x - playerChunk.x),
                    Mathf.Abs(chunkCoord.y - playerChunk.y)
                );
                if (dist > _chunkUnloadRadius)
                {
                    toRemove.Add(chunkCoord);
                }
            }

            foreach (var coord in toRemove)
            {
                if (_use3DMesh)
                    _unloadChunk3D(coord);
                else
                    _unloadChunkTilemap(coord);
            }
        }

        // ====================================================================
        // 3D Mesh Chunk Loading
        // ====================================================================

        private void _loadChunk3D(Vector2Int chunkCoord)
        {
            var world = GameManager.Instance.World;
            if (world == null) return;

            var chunk = world.GetChunk(chunkCoord.x, chunkCoord.y);
            if (chunk == null) return;

            // Extract tile types into a 2D array for the mesh generator
            string[,] tileTypes = new string[_chunkSize, _chunkSize];
            for (int x = 0; x < _chunkSize; x++)
            {
                for (int z = 0; z < _chunkSize; z++)
                {
                    string tileKey = $"{x},{z},0";
                    string tileType = "grass";
                    if (chunk.Tiles.TryGetValue(tileKey, out var worldTile))
                        tileType = worldTile.TileType.ToString().ToLowerInvariant();
                    tileTypes[x, z] = tileType;
                }
            }

            Vector3 chunkWorldPos = new Vector3(
                chunkCoord.x * _chunkSize,
                0f,
                chunkCoord.y * _chunkSize
            );

            var renderData = new ChunkRenderData();

            // Generate and assign terrain mesh
            Mesh terrainMesh = ChunkMeshGenerator.GenerateChunkMesh(_chunkSize, tileTypes);
            renderData.TerrainObject = _createMeshObject(
                $"Chunk_{chunkCoord.x}_{chunkCoord.y}_Terrain",
                terrainMesh,
                _getTerrainMaterial(),
                chunkWorldPos
            );

            // Generate cliff edge mesh
            Mesh edgeMesh = ChunkMeshGenerator.GenerateEdgeMesh(_chunkSize, tileTypes);
            if (edgeMesh != null)
            {
                renderData.EdgeObject = _createMeshObject(
                    $"Chunk_{chunkCoord.x}_{chunkCoord.y}_Edges",
                    edgeMesh,
                    _getEdgeMaterial(),
                    chunkWorldPos
                );
            }

            // Generate water surface mesh
            Mesh waterMesh = TerrainMaterialManager.GenerateWaterMesh(_chunkSize, tileTypes);
            if (waterMesh != null)
            {
                renderData.WaterObject = _createMeshObject(
                    $"Chunk_{chunkCoord.x}_{chunkCoord.y}_Water",
                    waterMesh,
                    _getWaterMaterial(),
                    chunkWorldPos
                );
            }

            _chunkObjects[chunkCoord] = renderData;
            _loadedChunks.Add(chunkCoord);
        }

        private void _unloadChunk3D(Vector2Int chunkCoord)
        {
            if (_chunkObjects.TryGetValue(chunkCoord, out var data))
            {
                if (data.TerrainObject != null) Destroy(data.TerrainObject);
                if (data.WaterObject != null) Destroy(data.WaterObject);
                if (data.EdgeObject != null) Destroy(data.EdgeObject);
                _chunkObjects.Remove(chunkCoord);
            }
            _loadedChunks.Remove(chunkCoord);
        }

        private GameObject _createMeshObject(string name, Mesh mesh, Material material, Vector3 position)
        {
            var go = new GameObject(name);
            go.transform.SetParent(_chunkContainer, false);
            go.transform.position = position;

            var meshFilter = go.AddComponent<MeshFilter>();
            meshFilter.mesh = mesh;

            var meshRenderer = go.AddComponent<MeshRenderer>();
            meshRenderer.material = material;
            meshRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            meshRenderer.receiveShadows = true;

            return go;
        }

        // ====================================================================
        // Material Access
        // ====================================================================

        private Material _cachedTerrainMaterial;
        private Material _cachedWaterMaterial;
        private Material _cachedEdgeMaterial;

        private Material _getTerrainMaterial()
        {
            if (TerrainMaterialManager.Instance != null)
                return TerrainMaterialManager.Instance.TerrainMaterial;

            // Fallback: create a simple vertex-color material
            if (_cachedTerrainMaterial == null)
            {
                Shader shader = Shader.Find("Universal Render Pipeline/Lit")
                    ?? Shader.Find("Standard")
                    ?? Shader.Find("Diffuse");
                _cachedTerrainMaterial = new Material(shader);
                _cachedTerrainMaterial.name = "Terrain_Fallback";
                _cachedTerrainMaterial.enableInstancing = true;
            }
            return _cachedTerrainMaterial;
        }

        private Material _getWaterMaterial()
        {
            if (TerrainMaterialManager.Instance != null)
                return TerrainMaterialManager.Instance.WaterMaterial;

            if (_cachedWaterMaterial == null)
            {
                Shader shader = Shader.Find("Universal Render Pipeline/Lit")
                    ?? Shader.Find("Standard");
                _cachedWaterMaterial = new Material(shader);
                _cachedWaterMaterial.name = "Water_Fallback";
                _cachedWaterMaterial.color = new Color(0.12f, 0.45f, 0.82f, 0.8f);
                _cachedWaterMaterial.SetOverrideTag("RenderType", "Transparent");
                _cachedWaterMaterial.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
                _cachedWaterMaterial.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                _cachedWaterMaterial.SetInt("_ZWrite", 0);
                _cachedWaterMaterial.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            }
            return _cachedWaterMaterial;
        }

        private Material _getEdgeMaterial()
        {
            if (TerrainMaterialManager.Instance != null)
                return TerrainMaterialManager.Instance.EdgeMaterial;

            if (_cachedEdgeMaterial == null)
            {
                Shader shader = Shader.Find("Universal Render Pipeline/Lit")
                    ?? Shader.Find("Standard");
                _cachedEdgeMaterial = new Material(shader);
                _cachedEdgeMaterial.name = "Edge_Fallback";
                _cachedEdgeMaterial.enableInstancing = true;
            }
            return _cachedEdgeMaterial;
        }

        // ====================================================================
        // Legacy Tilemap Chunk Loading (2D fallback)
        // ====================================================================

        private void _loadChunkTilemap(Vector2Int chunkCoord)
        {
            var world = GameManager.Instance.World;
            if (world == null) return;

            var chunk = world.GetChunk(chunkCoord.x, chunkCoord.y);
            if (chunk == null) return;

            int baseX = chunkCoord.x * _chunkSize;
            int baseZ = chunkCoord.y * _chunkSize;

            for (int x = 0; x < _chunkSize; x++)
            {
                for (int z = 0; z < _chunkSize; z++)
                {
                    string tileKey = $"{x},{z},0";
                    string tileType = "grass";
                    if (chunk.Tiles.TryGetValue(tileKey, out var worldTile))
                        tileType = worldTile.TileType.ToString().ToLowerInvariant();
                    TileBase tile = _getTileForType(tileType);

                    var tilePos = new Vector3Int(baseX + x, baseZ + z, 0);
                    _groundTilemap.SetTile(tilePos, tile);
                }
            }

            _loadedChunks.Add(chunkCoord);
        }

        private void _unloadChunkTilemap(Vector2Int chunkCoord)
        {
            int baseX = chunkCoord.x * _chunkSize;
            int baseZ = chunkCoord.y * _chunkSize;

            for (int x = 0; x < _chunkSize; x++)
            {
                for (int z = 0; z < _chunkSize; z++)
                {
                    var tilePos = new Vector3Int(baseX + x, baseZ + z, 0);
                    _groundTilemap.SetTile(tilePos, null);
                }
            }

            _loadedChunks.Remove(chunkCoord);
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>Clear all loaded chunks and terrain.</summary>
        public void ClearAll()
        {
            if (_use3DMesh)
            {
                foreach (var kvp in _chunkObjects)
                {
                    if (kvp.Value.TerrainObject != null) Destroy(kvp.Value.TerrainObject);
                    if (kvp.Value.WaterObject != null) Destroy(kvp.Value.WaterObject);
                    if (kvp.Value.EdgeObject != null) Destroy(kvp.Value.EdgeObject);
                }
                _chunkObjects.Clear();
            }
            else if (_groundTilemap != null)
            {
                _groundTilemap.ClearAllTiles();
            }

            _loadedChunks.Clear();
        }

        /// <summary>Force reload a specific chunk (e.g., after world modification).</summary>
        public void ReloadChunk(Vector2Int chunkCoord)
        {
            if (_loadedChunks.Contains(chunkCoord))
            {
                if (_use3DMesh)
                    _unloadChunk3D(chunkCoord);
                else
                    _unloadChunkTilemap(chunkCoord);
            }

            if (_use3DMesh)
                _loadChunk3D(chunkCoord);
            else
                _loadChunkTilemap(chunkCoord);
        }

        /// <summary>Toggle between 3D mesh and 2D tilemap rendering.</summary>
        public void SetRenderMode(bool use3D)
        {
            if (_use3DMesh == use3D) return;

            ClearAll();
            _use3DMesh = use3D;

            if (_use3DMesh)
            {
                if (_chunkContainer == null)
                {
                    _chunkContainer = new GameObject("ChunkContainer").transform;
                    _chunkContainer.SetParent(transform, false);
                }
                if (_groundTilemap != null) _groundTilemap.gameObject.SetActive(false);
            }
            else
            {
                if (_chunkContainer != null) _chunkContainer.gameObject.SetActive(false);
                if (_groundTilemap != null) _groundTilemap.gameObject.SetActive(true);
            }
        }

        // ====================================================================
        // Tilemap Helpers (Legacy)
        // ====================================================================

        private TileBase _getTileForType(string tileType)
        {
            if (string.IsNullOrEmpty(tileType)) return _grassTile;

            return tileType.ToLowerInvariant() switch
            {
                "grass" => _grassTile,
                "water" => _waterTile,
                "stone" => _stoneTile,
                "sand" => _sandTile,
                "cave" => _caveTile,
                "snow" => _snowTile,
                "dirt" or "dirt_path" => _dirtTile,
                _ => _grassTile
            };
        }

        private void _createFallbackTiles()
        {
            _grassTile = _createColorTile(ColorConverter.TileGrass);
            _waterTile = _createColorTile(ColorConverter.TileWater);
            _stoneTile = _createColorTile(ColorConverter.TileStone);
            _sandTile = _createColorTile(ColorConverter.TileSand);
            _caveTile = _createColorTile(ColorConverter.TileCave);
            _snowTile = _createColorTile(ColorConverter.TileSnow);
            _dirtTile = _createColorTile(ColorConverter.TileDirt);
        }

        private TileBase _createColorTile(Color32 color)
        {
            var tile = ScriptableObject.CreateInstance<Tile>();
            var texture = new Texture2D(1, 1);
            texture.SetPixel(0, 0, color);
            texture.Apply();
            tile.sprite = Sprite.Create(texture, new Rect(0, 0, 1, 1), new Vector2(0.5f, 0.5f), 1f);
            tile.color = Color.white;
            return tile;
        }
    }
}
