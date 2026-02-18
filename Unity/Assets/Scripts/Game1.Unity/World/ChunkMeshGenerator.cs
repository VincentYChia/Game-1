// ============================================================================
// Game1.Unity.World.ChunkMeshGenerator
// Created: 2026-02-18
//
// Generates a 3D mesh for each world chunk (16x16 tiles).
// Each tile becomes a quad on the XZ plane with per-tile height variation
// and UV mapping to a terrain texture atlas. Replaces the flat 2D Tilemap
// rendering with proper 3D geometry.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using Game1.Data.Enums;

namespace Game1.Unity.World
{
    /// <summary>
    /// Generates a 3D mesh for a single chunk (chunkSize x chunkSize tiles).
    /// Each tile type has a configurable height and UV coordinates.
    /// Water tiles sit below ground level for natural depth.
    /// </summary>
    public static class ChunkMeshGenerator
    {
        // ====================================================================
        // Tile Height Map — elevation per tile type
        // ====================================================================

        private static readonly Dictionary<string, float> TileHeights = new Dictionary<string, float>
        {
            { "grass",     0.0f },
            { "water",    -0.3f },
            { "stone",     0.15f },
            { "sand",     -0.05f },
            { "cave",     -0.1f },
            { "snow",      0.2f },
            { "dirt",      0.0f },
            { "dirt_path", 0.0f },
            { "mountain",  0.5f },
            { "forest",    0.0f },
        };

        // ====================================================================
        // Tile UV Coordinates — row in a terrain atlas (8 tiles wide)
        // Each tile type maps to a column in the atlas texture.
        // If no atlas is used, the material system applies flat colors.
        // ====================================================================

        private static readonly Dictionary<string, int> TileAtlasIndex = new Dictionary<string, int>
        {
            { "grass",     0 },
            { "water",     1 },
            { "stone",     2 },
            { "sand",      3 },
            { "cave",      4 },
            { "snow",      5 },
            { "dirt",      6 },
            { "dirt_path", 6 },
            { "mountain",  2 },
            { "forest",    0 },
        };

        private const int ATLAS_COLUMNS = 8;

        // ====================================================================
        // Mesh Generation
        // ====================================================================

        /// <summary>
        /// Generate a mesh for a chunk given its tile data.
        /// </summary>
        /// <param name="chunkSize">Number of tiles per side (typically 16).</param>
        /// <param name="tileTypes">2D array [x, z] of tile type strings. Null entries default to "grass".</param>
        /// <param name="tileScale">World-space size of each tile (typically 1.0).</param>
        /// <returns>A Unity Mesh with vertices, normals, UVs, and triangles.</returns>
        public static Mesh GenerateChunkMesh(int chunkSize, string[,] tileTypes, float tileScale = 1f)
        {
            int tileCount = chunkSize * chunkSize;
            int vertexCount = tileCount * 4;   // 4 vertices per quad
            int triangleCount = tileCount * 6;  // 2 triangles per quad, 3 indices each

            var vertices = new Vector3[vertexCount];
            var normals = new Vector3[vertexCount];
            var uvs = new Vector2[vertexCount];
            var uv2s = new Vector2[vertexCount]; // secondary UV for tile type ID (shader use)
            var colors = new Color32[vertexCount];
            var triangles = new int[triangleCount];

            int vi = 0; // vertex index
            int ti = 0; // triangle index

            for (int x = 0; x < chunkSize; x++)
            {
                for (int z = 0; z < chunkSize; z++)
                {
                    string tileType = (tileTypes != null && tileTypes[x, z] != null)
                        ? tileTypes[x, z].ToLowerInvariant()
                        : "grass";

                    float height = GetTileHeight(tileType);
                    Color32 color = GetTileColor(tileType);
                    int atlasIndex = GetTileAtlasIndex(tileType);

                    // Quad corners (XZ plane, Y = height)
                    float x0 = x * tileScale;
                    float x1 = (x + 1) * tileScale;
                    float z0 = z * tileScale;
                    float z1 = (z + 1) * tileScale;

                    // Slight random height variation for natural look (deterministic by position)
                    float variation = _heightNoise(x, z) * 0.04f;
                    float h = height + variation;

                    // Water tiles: smooth, no variation
                    if (tileType == "water") h = height;

                    // 4 vertices per tile quad
                    vertices[vi + 0] = new Vector3(x0, h, z0);
                    vertices[vi + 1] = new Vector3(x1, h, z1);
                    vertices[vi + 2] = new Vector3(x1, h, z0);
                    vertices[vi + 3] = new Vector3(x0, h, z1);

                    // Normals point up
                    normals[vi + 0] = Vector3.up;
                    normals[vi + 1] = Vector3.up;
                    normals[vi + 2] = Vector3.up;
                    normals[vi + 3] = Vector3.up;

                    // UV: tile local (0-1) per quad, for tiling textures
                    uvs[vi + 0] = new Vector2(0f, 0f);
                    uvs[vi + 1] = new Vector2(1f, 1f);
                    uvs[vi + 2] = new Vector2(1f, 0f);
                    uvs[vi + 3] = new Vector2(0f, 1f);

                    // UV2: atlas column for shader-based tile selection
                    float atlasU = (atlasIndex + 0.5f) / ATLAS_COLUMNS;
                    uv2s[vi + 0] = new Vector2(atlasU, 0f);
                    uv2s[vi + 1] = new Vector2(atlasU, 0f);
                    uv2s[vi + 2] = new Vector2(atlasU, 0f);
                    uv2s[vi + 3] = new Vector2(atlasU, 0f);

                    // Vertex colors (fallback when no texture atlas)
                    colors[vi + 0] = color;
                    colors[vi + 1] = color;
                    colors[vi + 2] = color;
                    colors[vi + 3] = color;

                    // Two triangles per quad
                    triangles[ti + 0] = vi + 0;
                    triangles[ti + 1] = vi + 1;
                    triangles[ti + 2] = vi + 2;
                    triangles[ti + 3] = vi + 0;
                    triangles[ti + 4] = vi + 3;
                    triangles[ti + 5] = vi + 1;

                    vi += 4;
                    ti += 6;
                }
            }

            var mesh = new Mesh();
            mesh.name = "ChunkMesh";

            // Use 32-bit indices if needed (>65535 vertices for very large chunks)
            if (vertexCount > 65535)
                mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;

            mesh.vertices = vertices;
            mesh.normals = normals;
            mesh.uv = uvs;
            mesh.uv2 = uv2s;
            mesh.colors32 = colors;
            mesh.triangles = triangles;

            mesh.RecalculateBounds();

            return mesh;
        }

        /// <summary>
        /// Generate edge geometry (vertical faces) between tiles of different heights.
        /// This creates the "cliff" sides visible at height transitions.
        /// </summary>
        public static Mesh GenerateEdgeMesh(int chunkSize, string[,] tileTypes, float tileScale = 1f)
        {
            var vertices = new List<Vector3>();
            var normals = new List<Vector3>();
            var uvs = new List<Vector2>();
            var colors = new List<Color32>();
            var triangles = new List<int>();

            for (int x = 0; x < chunkSize; x++)
            {
                for (int z = 0; z < chunkSize; z++)
                {
                    string type = _getTileType(tileTypes, x, z, chunkSize);
                    float h = GetTileHeight(type);
                    Color32 color = GetTileColor(type);

                    // Check each neighbor — if lower, add a vertical face
                    _tryAddEdge(vertices, normals, uvs, colors, triangles,
                        x, z, x + 1, z, h, tileTypes, chunkSize, tileScale, color, Vector3.right);
                    _tryAddEdge(vertices, normals, uvs, colors, triangles,
                        x, z, x - 1, z, h, tileTypes, chunkSize, tileScale, color, Vector3.left);
                    _tryAddEdge(vertices, normals, uvs, colors, triangles,
                        x, z, x, z + 1, h, tileTypes, chunkSize, tileScale, color, Vector3.forward);
                    _tryAddEdge(vertices, normals, uvs, colors, triangles,
                        x, z, x, z - 1, h, tileTypes, chunkSize, tileScale, color, Vector3.back);
                }
            }

            if (vertices.Count == 0) return null;

            var mesh = new Mesh();
            mesh.name = "ChunkEdgeMesh";
            mesh.SetVertices(vertices);
            mesh.SetNormals(normals);
            mesh.SetUVs(0, uvs);
            mesh.SetColors(colors);
            mesh.SetTriangles(triangles, 0);
            mesh.RecalculateBounds();
            return mesh;
        }

        // ====================================================================
        // Height / Color Lookups
        // ====================================================================

        /// <summary>Get the base height for a tile type.</summary>
        public static float GetTileHeight(string tileType)
        {
            if (tileType != null && TileHeights.TryGetValue(tileType.ToLowerInvariant(), out float h))
                return h;
            return 0f;
        }

        /// <summary>Get the flat color for a tile type (used as vertex color fallback).</summary>
        public static Color32 GetTileColor(string tileType)
        {
            if (tileType == null) tileType = "grass";

            return tileType.ToLowerInvariant() switch
            {
                "grass"     => new Color32(34, 139, 34, 255),
                "water"     => new Color32(30, 100, 200, 255),
                "stone"     => new Color32(128, 128, 128, 255),
                "sand"      => new Color32(238, 214, 175, 255),
                "cave"      => new Color32(64, 64, 64, 255),
                "snow"      => new Color32(240, 240, 255, 255),
                "dirt" or
                "dirt_path" => new Color32(139, 90, 43, 255),
                "mountain"  => new Color32(100, 100, 110, 255),
                "forest"    => new Color32(20, 100, 20, 255),
                _           => new Color32(34, 139, 34, 255),
            };
        }

        private static int GetTileAtlasIndex(string tileType)
        {
            if (tileType != null && TileAtlasIndex.TryGetValue(tileType.ToLowerInvariant(), out int idx))
                return idx;
            return 0;
        }

        // ====================================================================
        // Private Helpers
        // ====================================================================

        /// <summary>Deterministic pseudo-random height noise based on tile position.</summary>
        private static float _heightNoise(int x, int z)
        {
            // Simple hash for deterministic variation
            int hash = x * 73856093 ^ z * 19349663;
            return ((hash & 0x7FFFFFFF) % 1000) / 1000f - 0.5f;
        }

        private static string _getTileType(string[,] tileTypes, int x, int z, int chunkSize)
        {
            if (x < 0 || x >= chunkSize || z < 0 || z >= chunkSize) return "grass";
            if (tileTypes == null) return "grass";
            return tileTypes[x, z] ?? "grass";
        }

        private static void _tryAddEdge(
            List<Vector3> vertices, List<Vector3> normals, List<Vector2> uvs,
            List<Color32> colors, List<int> triangles,
            int x, int z, int nx, int nz, float myHeight,
            string[,] tileTypes, int chunkSize, float tileScale,
            Color32 color, Vector3 faceNormal)
        {
            string neighborType = _getTileType(tileTypes, nx, nz, chunkSize);
            float neighborHeight = GetTileHeight(neighborType);

            if (neighborHeight >= myHeight) return; // no cliff face needed

            float heightDiff = myHeight - neighborHeight;

            // Determine edge vertices based on face direction
            float x0 = x * tileScale;
            float x1 = (x + 1) * tileScale;
            float z0 = z * tileScale;
            float z1 = (z + 1) * tileScale;

            Vector3 v0, v1, v2, v3;

            if (faceNormal == Vector3.right)
            {
                v0 = new Vector3(x1, myHeight, z0);
                v1 = new Vector3(x1, myHeight, z1);
                v2 = new Vector3(x1, neighborHeight, z1);
                v3 = new Vector3(x1, neighborHeight, z0);
            }
            else if (faceNormal == Vector3.left)
            {
                v0 = new Vector3(x0, myHeight, z1);
                v1 = new Vector3(x0, myHeight, z0);
                v2 = new Vector3(x0, neighborHeight, z0);
                v3 = new Vector3(x0, neighborHeight, z1);
            }
            else if (faceNormal == Vector3.forward)
            {
                v0 = new Vector3(x1, myHeight, z1);
                v1 = new Vector3(x0, myHeight, z1);
                v2 = new Vector3(x0, neighborHeight, z1);
                v3 = new Vector3(x1, neighborHeight, z1);
            }
            else // Vector3.back
            {
                v0 = new Vector3(x0, myHeight, z0);
                v1 = new Vector3(x1, myHeight, z0);
                v2 = new Vector3(x1, neighborHeight, z0);
                v3 = new Vector3(x0, neighborHeight, z0);
            }

            // Darken cliff faces slightly
            byte darken = 30;
            Color32 edgeColor = new Color32(
                (byte)Mathf.Max(0, color.r - darken),
                (byte)Mathf.Max(0, color.g - darken),
                (byte)Mathf.Max(0, color.b - darken),
                255
            );

            int baseIndex = vertices.Count;
            vertices.Add(v0); vertices.Add(v1); vertices.Add(v2); vertices.Add(v3);
            normals.Add(faceNormal); normals.Add(faceNormal);
            normals.Add(faceNormal); normals.Add(faceNormal);
            uvs.Add(new Vector2(0, 1)); uvs.Add(new Vector2(1, 1));
            uvs.Add(new Vector2(1, 0)); uvs.Add(new Vector2(0, 0));
            colors.Add(edgeColor); colors.Add(edgeColor);
            colors.Add(edgeColor); colors.Add(edgeColor);

            triangles.Add(baseIndex + 0);
            triangles.Add(baseIndex + 1);
            triangles.Add(baseIndex + 2);
            triangles.Add(baseIndex + 0);
            triangles.Add(baseIndex + 2);
            triangles.Add(baseIndex + 3);
        }
    }
}
