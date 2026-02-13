// ============================================================================
// Game1.Unity.World.WorldRenderer
// Migrated from: rendering/renderer.py (lines 965-1391: render_world)
// Migration phase: 6
// Date: 2026-02-13
//
// Manages Tilemap rendering of world chunks.
// Loads/unloads chunks based on camera position.
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
    /// Renders the game world using Unity Tilemap.
    /// Manages chunk visibility based on camera frustum.
    /// Replaces Python renderer's render_world() method.
    /// </summary>
    public class WorldRenderer : MonoBehaviour
    {
        // ====================================================================
        // Inspector References
        // ====================================================================

        [Header("Tilemaps")]
        [SerializeField] private Tilemap _groundTilemap;
        [SerializeField] private Grid _grid;

        [Header("Tile Assets")]
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
        private CameraController _cameraController;
        private int _chunkSize;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Start()
        {
            _chunkSize = GameConfig.ChunkSize;
            _cameraController = FindFirstObjectByType<CameraController>();

            // Create fallback tiles if not assigned in editor
            if (_grassTile == null) _createFallbackTiles();
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
                        _loadChunk(chunkCoord);
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
                _unloadChunk(coord);
            }
        }

        // ====================================================================
        // Chunk Loading/Unloading
        // ====================================================================

        private void _loadChunk(Vector2Int chunkCoord)
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
                    string tileType = chunk.GetTileType(x, z);
                    TileBase tile = _getTileForType(tileType);

                    // Unity Tilemap uses Vector3Int — XZ plane mapped to XY for Tilemap
                    var tilePos = new Vector3Int(baseX + x, baseZ + z, 0);
                    _groundTilemap.SetTile(tilePos, tile);
                }
            }

            _loadedChunks.Add(chunkCoord);
        }

        private void _unloadChunk(Vector2Int chunkCoord)
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

        /// <summary>Clear all loaded chunks and tiles.</summary>
        public void ClearAll()
        {
            _groundTilemap.ClearAllTiles();
            _loadedChunks.Clear();
        }

        // ====================================================================
        // Tile Mapping
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

        // ====================================================================
        // Fallback Tile Creation
        // ====================================================================

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
            // Create a simple colored tile for testing
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
