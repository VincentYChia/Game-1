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
using Game1.Entities;
using Game1.Systems.Combat;
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
        [SerializeField] private bool _use3DMesh = true;

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

        // Enemy tracking: maps Enemy instances to their 3D GameObjects for position sync
        private Dictionary<Enemy, GameObject> _enemyGameObjects = new Dictionary<Enemy, GameObject>();

        // ====================================================================
        // Chunk Render Data
        // ====================================================================

        private struct ChunkRenderData
        {
            public GameObject TerrainObject;
            public GameObject WaterObject;
            public GameObject EdgeObject;
            public GameObject ResourceContainer;
            public GameObject EnemyContainer;
        }

        // World furniture: crafting stations, spawn beacon (created once)
        private GameObject _worldFurniture;
        private bool _worldFurnitureSpawned;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Start()
        {
            _chunkSize = GameConfig.ChunkSize;
            _cameraController = FindFirstObjectByType<CameraController>();

            // Force 3D mode — overrides any serialized scene value
            _use3DMesh = true;

            _chunkContainer = new GameObject("ChunkContainer").transform;
            _chunkContainer.SetParent(transform, false);
        }

        // ====================================================================
        // Per-Frame Update
        // ====================================================================

        private void LateUpdate()
        {
            if (GameManager.Instance == null || GameManager.Instance.World == null) return;
            if (GameManager.Instance.Player == null) return;

            // Spawn crafting stations and beacon once
            if (!_worldFurnitureSpawned)
            {
                _spawnWorldFurniture();
                _worldFurnitureSpawned = true;
            }

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

            // Update enemy 3D positions to match AI movement
            _updateEnemyPositions();
        }

        /// <summary>
        /// Sync enemy 3D GameObject positions with their game-logic positions.
        /// Handles death (hide/fade), chase movement, etc.
        /// </summary>
        private void _updateEnemyPositions()
        {
            var toRemove = new List<Enemy>();

            foreach (var kvp in _enemyGameObjects)
            {
                var enemy = kvp.Key;
                var go = kvp.Value;

                if (go == null)
                {
                    toRemove.Add(enemy);
                    continue;
                }

                if (!enemy.IsAlive)
                {
                    // Enemy died — disable its GameObject
                    if (go.activeSelf) go.SetActive(false);
                    continue;
                }

                // Update world position from game logic
                float wx = enemy.Position.X;
                float wz = enemy.Position.Z;
                float terrainY = ChunkMeshGenerator.SampleTerrainHeight(wx, wz, "grass");
                go.transform.position = new Vector3(wx, terrainY, wz);

                // Update health bar if damaged
                var healthBarCanvas = go.GetComponentInChildren<Canvas>(true);
                if (healthBarCanvas != null && enemy.HealthPercent < 1f)
                {
                    healthBarCanvas.gameObject.SetActive(true);
                    var fill = healthBarCanvas.GetComponentInChildren<UnityEngine.UI.Image>();
                    if (fill != null && fill.name == "Fill")
                    {
                        fill.fillAmount = enemy.HealthPercent;
                        fill.color = Color.Lerp(Color.red, Color.green, enemy.HealthPercent);
                    }
                }
            }

            foreach (var dead in toRemove)
                _enemyGameObjects.Remove(dead);
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

            // Generate and assign terrain mesh (pass chunk world pos for Perlin noise continuity)
            Mesh terrainMesh = ChunkMeshGenerator.GenerateChunkMesh(
                _chunkSize, tileTypes, 1f, chunkWorldPos.x, chunkWorldPos.z);
            renderData.TerrainObject = _createMeshObject(
                $"Chunk_{chunkCoord.x}_{chunkCoord.y}_Terrain",
                terrainMesh,
                _getTerrainMaterial(),
                chunkWorldPos
            );

            // Generate cliff edge mesh
            Mesh edgeMesh = ChunkMeshGenerator.GenerateEdgeMesh(
                _chunkSize, tileTypes, 1f, chunkWorldPos.x, chunkWorldPos.z);
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

            // --------------------------------------------------------
            // Spawn resource node objects (trees, ores, stones, etc.)
            // --------------------------------------------------------
            if (chunk.Resources != null && chunk.Resources.Count > 0)
            {
                var resourceContainer = new GameObject(
                    $"Chunk_{chunkCoord.x}_{chunkCoord.y}_Resources");
                resourceContainer.transform.SetParent(_chunkContainer, false);

                foreach (var resource in chunk.Resources)
                {
                    if (resource == null || resource.IsDepleted) continue;

                    try
                    {
                        var resourceGO = PrimitiveShapeFactory.CreateResource(
                            resource.ResourceId, resource.Tier);

                        // Position at resource world coordinates, on terrain surface
                        float wx = resource.Position.X;
                        float wz = resource.Position.Z;
                        string tileAtResource = _getTileTypeAtWorld(
                            wx, wz, tileTypes, chunkCoord);
                        float terrainY = ChunkMeshGenerator.SampleTerrainHeight(
                            wx, wz, tileAtResource);

                        resourceGO.transform.position = new Vector3(wx, terrainY, wz);
                        resourceGO.transform.SetParent(resourceContainer.transform, true);
                    }
                    catch (System.Exception ex)
                    {
                        Debug.LogWarning(
                            $"[WorldRenderer] Failed to create resource {resource.ResourceId}: {ex.Message}");
                    }
                }

                renderData.ResourceContainer = resourceContainer;
            }

            // --------------------------------------------------------
            // Spawn enemy objects (hostile mobs in dangerous/rare chunks)
            // --------------------------------------------------------
            if (chunk.Enemies != null && chunk.Enemies.Count > 0)
            {
                var enemyContainer = new GameObject(
                    $"Chunk_{chunkCoord.x}_{chunkCoord.y}_Enemies");
                enemyContainer.transform.SetParent(_chunkContainer, false);

                var combatManager = GameManager.Instance?.CombatManager;

                foreach (var enemy in chunk.Enemies)
                {
                    if (enemy == null || !enemy.IsAlive) continue;

                    try
                    {
                        bool isBoss = enemy.Definition.Category == "boss";
                        var enemyGO = PrimitiveShapeFactory.CreateEnemy(enemy.Tier, isBoss);
                        enemyGO.name = $"Enemy_{enemy.EnemyId}_{enemy.Name}";

                        // Position at enemy's world coordinates, on terrain surface
                        float wx = enemy.Position.X;
                        float wz = enemy.Position.Z;
                        string tileAtEnemy = _getTileTypeAtWorld(
                            wx, wz, tileTypes, chunkCoord);
                        float terrainY = ChunkMeshGenerator.SampleTerrainHeight(
                            wx, wz, tileAtEnemy);

                        enemyGO.transform.position = new Vector3(wx, terrainY, wz);
                        enemyGO.transform.SetParent(enemyContainer.transform, true);

                        // Add name label
                        string label = $"{enemy.Name} (T{enemy.Tier})";
                        Color labelColor = PrimitiveShapeFactory.GetEnemyTierColor(enemy.Tier);
                        PrimitiveShapeFactory.AddWorldLabel(enemyGO, label, labelColor, 1.8f);

                        // Add health bar
                        PrimitiveShapeFactory.AddWorldHealthBar(enemyGO, 1.5f);

                        // Track enemy-to-GameObject mapping for position updates
                        _enemyGameObjects[enemy] = enemyGO;

                        // Register with CombatManager for AI + combat
                        if (combatManager != null)
                        {
                            var adapter = new EnemyCombatAdapter(enemy);
                            combatManager.AddEnemy(adapter);
                        }
                    }
                    catch (System.Exception ex)
                    {
                        Debug.LogWarning(
                            $"[WorldRenderer] Failed to create enemy {enemy.EnemyId}: {ex.Message}");
                    }
                }

                renderData.EnemyContainer = enemyContainer;
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
                if (data.ResourceContainer != null) Destroy(data.ResourceContainer);

                // Clean up enemy tracking when chunk unloads
                if (data.EnemyContainer != null)
                {
                    // Remove enemy→GO mappings for enemies in this chunk
                    var world = GameManager.Instance?.World;
                    var chunk = world?.GetChunk(chunkCoord.x, chunkCoord.y);
                    if (chunk?.Enemies != null)
                    {
                        foreach (var enemy in chunk.Enemies)
                            _enemyGameObjects.Remove(enemy);
                    }
                    Destroy(data.EnemyContainer);
                }

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

            // Fallback: create a vertex-color material
            if (_cachedTerrainMaterial == null)
            {
                Shader shader = Shader.Find("Game1/VertexColorLit")
                    ?? Shader.Find("Universal Render Pipeline/Particles/Lit")
                    ?? Shader.Find("Particles/Standard Surface")
                    ?? Shader.Find("Standard");
                _cachedTerrainMaterial = new Material(shader);
                _cachedTerrainMaterial.name = "Terrain_Fallback";
                _cachedTerrainMaterial.enableInstancing = true;
                _cachedTerrainMaterial.color = Color.white;
            }
            return _cachedTerrainMaterial;
        }

        private Material _getWaterMaterial()
        {
            if (TerrainMaterialManager.Instance != null)
                return TerrainMaterialManager.Instance.WaterMaterial;

            if (_cachedWaterMaterial == null)
            {
                Shader shader = Shader.Find("Game1/VertexColorTransparent")
                    ?? Shader.Find("Universal Render Pipeline/Particles/Unlit")
                    ?? Shader.Find("Particles/Standard Unlit")
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
                Shader shader = Shader.Find("Game1/VertexColorLit")
                    ?? Shader.Find("Universal Render Pipeline/Particles/Lit")
                    ?? Shader.Find("Particles/Standard Surface")
                    ?? Shader.Find("Standard");
                _cachedEdgeMaterial = new Material(shader);
                _cachedEdgeMaterial.name = "Edge_Fallback";
                _cachedEdgeMaterial.enableInstancing = true;
                _cachedEdgeMaterial.color = Color.white;
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
                    if (kvp.Value.ResourceContainer != null) Destroy(kvp.Value.ResourceContainer);
                    if (kvp.Value.EnemyContainer != null) Destroy(kvp.Value.EnemyContainer);
                }
                _chunkObjects.Clear();
                _enemyGameObjects.Clear();
            }
            else if (_groundTilemap != null)
            {
                _groundTilemap.ClearAllTiles();
            }

            if (_worldFurniture != null)
            {
                Destroy(_worldFurniture);
                _worldFurnitureSpawned = false;
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

        // ====================================================================
        // World Furniture — Stations, Spawn Beacon (created once)
        // ====================================================================

        /// <summary>
        /// Spawns one-time world objects: crafting stations at their fixed positions
        /// and a visible spawn beacon so the player has a landmark.
        /// </summary>
        private void _spawnWorldFurniture()
        {
            _worldFurniture = new GameObject("WorldFurniture");

            _spawnCraftingStations();
            _createSpawnBeacon();

            Debug.Log("[WorldRenderer] World furniture spawned.");
        }

        private void _spawnCraftingStations()
        {
            var world = GameManager.Instance?.World;
            if (world == null || world.CraftingStations == null) return;

            var container = new GameObject("CraftingStations");
            container.transform.SetParent(_worldFurniture.transform, false);

            foreach (var station in world.CraftingStations)
            {
                try
                {
                    string stationType = station.StationType.ToString().ToLowerInvariant();
                    var stationGO = PrimitiveShapeFactory.CreateStation(
                        stationType, station.StationTier);

                    float wx = station.Position.X;
                    float wz = station.Position.Z;
                    float terrainY = ChunkMeshGenerator.SampleTerrainHeight(wx, wz, "grass");

                    stationGO.transform.position = new Vector3(wx, terrainY, wz);
                    stationGO.transform.SetParent(container.transform, true);

                    // Floating label above station
                    string label = $"{station.StationType} T{station.StationTier}";
                    Color labelColor = PrimitiveShapeFactory.GetStationColor(stationType);
                    PrimitiveShapeFactory.AddWorldLabel(stationGO, label, labelColor, 2.0f);
                }
                catch (System.Exception ex)
                {
                    Debug.LogWarning($"[WorldRenderer] Failed to create station: {ex.Message}");
                }
            }
        }

        /// <summary>
        /// Creates a visible beacon at the player spawn point (world center)
        /// so the player has a clear landmark for orientation and movement testing.
        /// </summary>
        private void _createSpawnBeacon()
        {
            float spawnX = 50f;
            float spawnZ = 50f;
            float terrainY = ChunkMeshGenerator.SampleTerrainHeight(spawnX, spawnZ, "grass");

            var beacon = new GameObject("SpawnBeacon");
            beacon.transform.SetParent(_worldFurniture.transform, false);
            beacon.transform.position = new Vector3(spawnX, terrainY, spawnZ);

            // Tall golden pillar
            var pillar = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            pillar.name = "BeaconPillar";
            pillar.transform.SetParent(beacon.transform, false);
            pillar.transform.localPosition = new Vector3(0f, 2.5f, 0f);
            pillar.transform.localScale = new Vector3(0.3f, 2.5f, 0.3f);
            _removeBuiltinCollider(pillar);
            PrimitiveShapeFactory.SetPrimitiveColor(pillar, new Color(1f, 0.84f, 0f)); // gold

            // Glowing sphere on top
            var orb = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            orb.name = "BeaconOrb";
            orb.transform.SetParent(beacon.transform, false);
            orb.transform.localPosition = new Vector3(0f, 5.2f, 0f);
            orb.transform.localScale = new Vector3(0.6f, 0.6f, 0.6f);
            _removeBuiltinCollider(orb);
            PrimitiveShapeFactory.SetPrimitiveColor(orb, new Color(1f, 0.95f, 0.4f)); // bright gold

            // Base ring (flat cylinder on the ground)
            var baseRing = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            baseRing.name = "BeaconBase";
            baseRing.transform.SetParent(beacon.transform, false);
            baseRing.transform.localPosition = new Vector3(0f, 0.05f, 0f);
            baseRing.transform.localScale = new Vector3(2.0f, 0.05f, 2.0f);
            _removeBuiltinCollider(baseRing);
            PrimitiveShapeFactory.SetPrimitiveColor(baseRing, new Color(0.8f, 0.7f, 0.2f, 0.8f));

            // "SPAWN" label floating above
            PrimitiveShapeFactory.AddWorldLabel(beacon, "SPAWN", Color.yellow, 6.5f, 0.012f);
        }

        // ====================================================================
        // Helpers — tile type lookup for resource positioning
        // ====================================================================

        /// <summary>
        /// Get tile type at a world position, using the tileTypes array from
        /// the chunk currently being loaded.
        /// </summary>
        private string _getTileTypeAtWorld(
            float worldX, float worldZ,
            string[,] tileTypes, Vector2Int chunkCoord)
        {
            int localX = Mathf.FloorToInt(worldX) - chunkCoord.x * _chunkSize;
            int localZ = Mathf.FloorToInt(worldZ) - chunkCoord.y * _chunkSize;

            if (localX >= 0 && localX < _chunkSize && localZ >= 0 && localZ < _chunkSize)
                return tileTypes[localX, localZ] ?? "grass";

            return "grass";
        }

        private static void _removeBuiltinCollider(GameObject go)
        {
            var col = go.GetComponent<Collider>();
            if (col != null) Destroy(col);
        }
    }
}
