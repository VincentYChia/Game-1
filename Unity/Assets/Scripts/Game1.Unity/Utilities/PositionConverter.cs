// ============================================================================
// Game1.Unity.Utilities.PositionConverter
// Migrated from: N/A (new — bridges GamePosition to Unity Vector3)
// Migration phase: 6
// Date: 2026-02-13
// ============================================================================

using UnityEngine;
using Game1.Data.Models;

namespace Game1.Unity.Utilities
{
    /// <summary>
    /// Converts between Phase 1-5 GamePosition and Unity Vector3.
    /// GamePosition uses (X, Y, Z) where Y is height; Unity uses the same convention.
    /// Python's 2D (x, y) maps to GamePosition(x, 0, y) — the Z axis is north-south.
    /// </summary>
    public static class PositionConverter
    {
        /// <summary>
        /// Convert a GamePosition to Unity Vector3.
        /// GamePosition and Vector3 use the same coordinate convention:
        ///   X = east-west, Y = height, Z = north-south
        /// </summary>
        public static Vector3 ToVector3(GamePosition pos)
        {
            return new Vector3(pos.X, pos.Y, pos.Z);
        }

        /// <summary>
        /// Convert a Unity Vector3 to GamePosition.
        /// </summary>
        public static GamePosition FromVector3(Vector3 v)
        {
            return new GamePosition(v.x, v.y, v.z);
        }

        /// <summary>
        /// Convert tile coordinates to world position.
        /// Tile (x, z) → world position at center of tile.
        /// </summary>
        public static Vector3 TileToWorld(int tileX, int tileZ)
        {
            return new Vector3(tileX + 0.5f, 0f, tileZ + 0.5f);
        }

        /// <summary>
        /// Convert world position to tile coordinates.
        /// </summary>
        public static Vector2Int WorldToTile(Vector3 worldPos)
        {
            return new Vector2Int(Mathf.FloorToInt(worldPos.x), Mathf.FloorToInt(worldPos.z));
        }

        /// <summary>
        /// Convert chunk coordinates to world position (bottom-left corner of chunk).
        /// </summary>
        public static Vector3 ChunkToWorld(int chunkX, int chunkZ, int chunkSize)
        {
            return new Vector3(chunkX * chunkSize, 0f, chunkZ * chunkSize);
        }

        /// <summary>
        /// Convert world position to chunk coordinates.
        /// </summary>
        public static Vector2Int WorldToChunk(Vector3 worldPos, int chunkSize)
        {
            return new Vector2Int(
                Mathf.FloorToInt(worldPos.x / chunkSize),
                Mathf.FloorToInt(worldPos.z / chunkSize)
            );
        }
    }
}
