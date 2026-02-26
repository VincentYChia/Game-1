// ============================================================================
// Game1.Unity.World.ChunkMeshGenerator
// Created: 2026-02-18
// Updated: 2026-02-25 — Smooth Perlin noise terrain (Breath of the Wild style)
//
// Generates a 3D mesh for each world chunk (16x16 tiles).
// Each tile is subdivided into a grid of vertices, with per-vertex Perlin
// noise height sampling for smooth, rolling terrain. Water tiles remain flat
// at their depression level. Vertices at tile boundaries are shared so that
// adjacent tiles and chunks produce seamless terrain.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using Game1.Data.Enums;

namespace Game1.Unity.World
{
    /// <summary>
    /// Generates a 3D mesh for a single chunk (chunkSize x chunkSize tiles).
    /// Uses multi-octave Perlin noise for smooth, rolling terrain heights.
    /// Water tiles stay flat. Vertex normals are properly computed for smooth shading.
    /// </summary>
    public static class ChunkMeshGenerator
    {
        // ====================================================================
        // Noise Parameters
        // ====================================================================

        /// <summary>Base frequency for Perlin noise sampling. Lower = broader hills.</summary>
        private const float NOISE_SCALE = 0.08f;

        /// <summary>Second octave frequency multiplier (detail layer).</summary>
        private const float NOISE_OCTAVE2_FREQ = 2.17f;

        /// <summary>Second octave amplitude multiplier.</summary>
        private const float NOISE_OCTAVE2_AMP = 0.35f;

        /// <summary>Third octave frequency multiplier (fine detail).</summary>
        private const float NOISE_OCTAVE3_FREQ = 4.31f;

        /// <summary>Third octave amplitude multiplier.</summary>
        private const float NOISE_OCTAVE3_AMP = 0.15f;

        /// <summary>
        /// Noise amplitude per tile type. Determines how much vertical displacement
        /// the terrain receives. Water is 0 (flat), mountains are high, etc.
        /// </summary>
        private static readonly Dictionary<string, float> NoiseAmplitude = new Dictionary<string, float>
        {
            { "grass",     0.3f },
            { "water",     0.0f },
            { "stone",     0.4f },
            { "sand",      0.15f },
            { "cave",      0.1f },
            { "snow",      0.35f },
            { "dirt",      0.25f },
            { "dirt_path", 0.1f },
            { "mountain",  0.5f },
            { "forest",    0.3f },
        };

        /// <summary>Number of subdivisions per tile edge. Higher = smoother but more geometry.</summary>
        private const int SUBDIVISIONS = 4;

        // ====================================================================
        // Tile Height Map — base elevation per tile type
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
        // Perlin Noise Sampling
        // ====================================================================

        /// <summary>
        /// Sample multi-octave Perlin noise at a world position.
        /// Returns a value centered roughly around 0 (range approximately -0.5 to +0.5
        /// before amplitude scaling).
        /// </summary>
        private static float SampleNoise(float worldX, float worldZ)
        {
            // Offset to avoid Perlin noise symmetry at origin and integer grid points.
            // Mathf.PerlinNoise returns 0.5 at integer coordinates, so we shift.
            float ox = 1537.31f;
            float oz = 2749.83f;

            float sx = (worldX + ox) * NOISE_SCALE;
            float sz = (worldZ + oz) * NOISE_SCALE;

            // Octave 1: broad rolling hills
            float n = Mathf.PerlinNoise(sx, sz) - 0.5f;

            // Octave 2: medium detail
            float sx2 = (worldX + ox) * NOISE_SCALE * NOISE_OCTAVE2_FREQ;
            float sz2 = (worldZ + oz) * NOISE_SCALE * NOISE_OCTAVE2_FREQ;
            n += (Mathf.PerlinNoise(sx2, sz2) - 0.5f) * NOISE_OCTAVE2_AMP;

            // Octave 3: fine detail
            float sx3 = (worldX + ox) * NOISE_SCALE * NOISE_OCTAVE3_FREQ;
            float sz3 = (worldZ + oz) * NOISE_SCALE * NOISE_OCTAVE3_FREQ;
            n += (Mathf.PerlinNoise(sx3, sz3) - 0.5f) * NOISE_OCTAVE3_AMP;

            return n;
        }

        /// <summary>
        /// Get the noise amplitude for a tile type.
        /// </summary>
        private static float GetNoiseAmplitude(string tileType)
        {
            if (tileType != null && NoiseAmplitude.TryGetValue(tileType.ToLowerInvariant(), out float amp))
                return amp;
            return 0.3f; // default to grass amplitude
        }

        /// <summary>
        /// Sample the exact terrain height at any world position, accounting for
        /// the tile type's base height and Perlin noise displacement.
        /// Use this for placing entities, characters, items, etc. on the terrain.
        /// </summary>
        /// <param name="worldX">World-space X coordinate.</param>
        /// <param name="worldZ">World-space Z coordinate.</param>
        /// <param name="tileType">Tile type string (e.g. "grass", "mountain", "water").</param>
        /// <returns>The Y height at the given world position.</returns>
        public static float SampleTerrainHeight(float worldX, float worldZ, string tileType)
        {
            if (tileType == null) tileType = "grass";
            string type = tileType.ToLowerInvariant();

            float baseHeight = GetTileHeight(type);
            float amplitude = GetNoiseAmplitude(type);

            // Water and zero-amplitude tiles are perfectly flat
            if (type == "water" || amplitude <= 0f)
                return baseHeight;

            float noise = SampleNoise(worldX, worldZ);
            return baseHeight + noise * amplitude;
        }

        // ====================================================================
        // Mesh Generation
        // ====================================================================

        /// <summary>
        /// Generate a mesh for a chunk given its tile data, with smooth Perlin noise terrain.
        /// </summary>
        /// <param name="chunkSize">Number of tiles per side (typically 16).</param>
        /// <param name="tileTypes">2D array [x, z] of tile type strings. Null entries default to "grass".</param>
        /// <param name="tileScale">World-space size of each tile (typically 1.0).</param>
        /// <param name="chunkWorldX">World-space X origin of this chunk (for noise sampling). Defaults to 0.</param>
        /// <param name="chunkWorldZ">World-space Z origin of this chunk (for noise sampling). Defaults to 0.</param>
        /// <returns>A Unity Mesh with vertices, normals, UVs, vertex colors, and triangles.</returns>
        public static Mesh GenerateChunkMesh(
            int chunkSize,
            string[,] tileTypes,
            float tileScale = 1f,
            float chunkWorldX = 0f,
            float chunkWorldZ = 0f)
        {
            // Each tile is subdivided into SUBDIVISIONS x SUBDIVISIONS quads.
            // Vertex grid per tile: (SUBDIVISIONS+1) x (SUBDIVISIONS+1).
            // Total vertex grid for the whole chunk: (chunkSize*SUBDIVISIONS+1) x (chunkSize*SUBDIVISIONS+1).
            int vertsPerSide = chunkSize * SUBDIVISIONS + 1;
            int vertexCount = vertsPerSide * vertsPerSide;
            int quadCount = chunkSize * SUBDIVISIONS * chunkSize * SUBDIVISIONS;
            int triangleCount = quadCount * 6;

            var vertices = new Vector3[vertexCount];
            var uvs = new Vector2[vertexCount];
            var uv2s = new Vector2[vertexCount];
            var colors = new Color32[vertexCount];
            var triangles = new int[triangleCount];

            float subStep = tileScale / SUBDIVISIONS;

            // ------------------------------------------------------------------
            // Pass 1: Generate vertex positions and attributes
            // ------------------------------------------------------------------
            for (int vx = 0; vx < vertsPerSide; vx++)
            {
                for (int vz = 0; vz < vertsPerSide; vz++)
                {
                    int idx = vx * vertsPerSide + vz;

                    // Local position within the chunk mesh
                    float localX = vx * subStep;
                    float localZ = vz * subStep;

                    // World position for noise sampling
                    float worldX = chunkWorldX + localX;
                    float worldZ = chunkWorldZ + localZ;

                    // Determine which tile this vertex belongs to.
                    // Vertices on the right/top boundary of the chunk clamp to the last tile.
                    int tileX = Mathf.Min(vx / SUBDIVISIONS, chunkSize - 1);
                    int tileZ = Mathf.Min(vz / SUBDIVISIONS, chunkSize - 1);

                    string tileType = _getTileType(tileTypes, tileX, tileZ, chunkSize);
                    float baseHeight = GetTileHeight(tileType);
                    float amplitude = GetNoiseAmplitude(tileType);

                    // For vertices on tile boundaries, we need to handle transitions.
                    // If a vertex sits exactly on a boundary between two tiles, we blend
                    // the height contributions from both tiles for seamless transitions.
                    float height;
                    Color32 color;
                    int atlasIndex;

                    bool isOnTileBoundaryX = (vx % SUBDIVISIONS == 0) && (vx > 0) && (vx < chunkSize * SUBDIVISIONS);
                    bool isOnTileBoundaryZ = (vz % SUBDIVISIONS == 0) && (vz > 0) && (vz < chunkSize * SUBDIVISIONS);

                    if (isOnTileBoundaryX || isOnTileBoundaryZ)
                    {
                        // Boundary vertex: blend between adjacent tiles
                        height = _blendBoundaryHeight(
                            tileTypes, chunkSize, vx, vz, worldX, worldZ);
                        color = _blendBoundaryColor(tileTypes, chunkSize, vx, vz);
                        color = _varyVertexColor(color, worldX, worldZ);
                        atlasIndex = GetTileAtlasIndex(tileType);
                    }
                    else
                    {
                        // Interior vertex: use the tile's own properties
                        if (tileType == "water" || amplitude <= 0f)
                        {
                            height = baseHeight;
                        }
                        else
                        {
                            float noise = SampleNoise(worldX, worldZ);
                            height = baseHeight + noise * amplitude;
                        }

                        color = GetTileColor(tileType);
                        color = _varyVertexColor(color, worldX, worldZ);
                        atlasIndex = GetTileAtlasIndex(tileType);
                    }

                    vertices[idx] = new Vector3(localX, height, localZ);

                    // UV: normalized position within chunk for potential full-chunk texturing,
                    // but also tile-local UVs tiling within each tile
                    float tileLocalU = (vx % SUBDIVISIONS) / (float)SUBDIVISIONS;
                    float tileLocalV = (vz % SUBDIVISIONS) / (float)SUBDIVISIONS;
                    uvs[idx] = new Vector2(tileLocalU, tileLocalV);

                    // UV2: atlas column for shader-based tile selection
                    float atlasU = (atlasIndex + 0.5f) / ATLAS_COLUMNS;
                    uv2s[idx] = new Vector2(atlasU, 0f);

                    colors[idx] = color;
                }
            }

            // ------------------------------------------------------------------
            // Pass 2: Generate triangle indices
            // ------------------------------------------------------------------
            int ti = 0;
            int quadsPerSide = chunkSize * SUBDIVISIONS;
            for (int qx = 0; qx < quadsPerSide; qx++)
            {
                for (int qz = 0; qz < quadsPerSide; qz++)
                {
                    int bottomLeft = qx * vertsPerSide + qz;
                    int bottomRight = (qx + 1) * vertsPerSide + qz;
                    int topLeft = qx * vertsPerSide + (qz + 1);
                    int topRight = (qx + 1) * vertsPerSide + (qz + 1);

                    // Triangle 1: bottomLeft, topRight, bottomRight
                    triangles[ti + 0] = bottomLeft;
                    triangles[ti + 1] = topRight;
                    triangles[ti + 2] = bottomRight;

                    // Triangle 2: bottomLeft, topLeft, topRight
                    triangles[ti + 3] = bottomLeft;
                    triangles[ti + 4] = topLeft;
                    triangles[ti + 5] = topRight;

                    ti += 6;
                }
            }

            // ------------------------------------------------------------------
            // Pass 3: Compute smooth vertex normals from surrounding geometry
            // ------------------------------------------------------------------
            var normals = _computeSmoothNormals(vertices, triangles, vertexCount);

            // ------------------------------------------------------------------
            // Build Mesh
            // ------------------------------------------------------------------
            var mesh = new Mesh();
            mesh.name = "ChunkMesh";

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
        /// Generate edge geometry (vertical faces) between tiles of different base heights.
        /// This creates the "cliff" sides visible at height transitions (e.g. water edges,
        /// mountain cliffs). Uses averaged Perlin noise heights along the edge for smoother
        /// cliff profiles.
        /// </summary>
        public static Mesh GenerateEdgeMesh(
            int chunkSize,
            string[,] tileTypes,
            float tileScale = 1f,
            float chunkWorldX = 0f,
            float chunkWorldZ = 0f)
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

                    // Check each neighbor -- if the base height is lower, add a vertical face
                    _tryAddEdge(vertices, normals, uvs, colors, triangles,
                        x, z, x + 1, z, h, tileTypes, chunkSize, tileScale, color, Vector3.right,
                        chunkWorldX, chunkWorldZ);
                    _tryAddEdge(vertices, normals, uvs, colors, triangles,
                        x, z, x - 1, z, h, tileTypes, chunkSize, tileScale, color, Vector3.left,
                        chunkWorldX, chunkWorldZ);
                    _tryAddEdge(vertices, normals, uvs, colors, triangles,
                        x, z, x, z + 1, h, tileTypes, chunkSize, tileScale, color, Vector3.forward,
                        chunkWorldX, chunkWorldZ);
                    _tryAddEdge(vertices, normals, uvs, colors, triangles,
                        x, z, x, z - 1, h, tileTypes, chunkSize, tileScale, color, Vector3.back,
                        chunkWorldX, chunkWorldZ);
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
        // Height / Color Lookups (Public)
        // ====================================================================

        /// <summary>Get the base height for a tile type (without noise).</summary>
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
        // Private Helpers — Per-Vertex Color Variation
        // ====================================================================

        /// <summary>
        /// Adds subtle per-vertex color variation based on world position noise.
        /// Prevents the flat, uniform look that makes terrain feel like floating
        /// on a solid color. Variation is ±12% of the base color.
        /// </summary>
        private static Color32 _varyVertexColor(Color32 baseColor, float worldX, float worldZ)
        {
            // Use a different noise frequency/offset than terrain height
            float n = SampleNoise(worldX * 1.7f + 317f, worldZ * 1.7f + 529f);
            // n is roughly -0.5..+0.5, scale to ±12% variation
            float variation = n * 0.24f;

            int r = Mathf.Clamp((int)(baseColor.r + baseColor.r * variation), 0, 255);
            int g = Mathf.Clamp((int)(baseColor.g + baseColor.g * variation), 0, 255);
            int b = Mathf.Clamp((int)(baseColor.b + baseColor.b * variation), 0, 255);
            return new Color32((byte)r, (byte)g, (byte)b, baseColor.a);
        }

        // ====================================================================
        // Private Helpers — Tile Lookups
        // ====================================================================

        private static string _getTileType(string[,] tileTypes, int x, int z, int chunkSize)
        {
            if (x < 0 || x >= chunkSize || z < 0 || z >= chunkSize) return "grass";
            if (tileTypes == null) return "grass";
            return tileTypes[x, z] ?? "grass";
        }

        // ====================================================================
        // Private Helpers — Boundary Blending
        // ====================================================================

        /// <summary>
        /// Compute height at a vertex that lies on a tile boundary by averaging
        /// the height contributions from all adjacent tiles. This produces seamless
        /// transitions between different tile types.
        /// </summary>
        private static float _blendBoundaryHeight(
            string[,] tileTypes, int chunkSize,
            int vx, int vz, float worldX, float worldZ)
        {
            // Gather all tiles that touch this vertex
            var adjacentTiles = _getAdjacentTiles(tileTypes, chunkSize, vx, vz);

            if (adjacentTiles.Count == 0)
            {
                // Fallback: treat as grass
                float noise = SampleNoise(worldX, worldZ);
                return noise * 0.3f;
            }

            float totalHeight = 0f;
            int count = adjacentTiles.Count;

            for (int i = 0; i < count; i++)
            {
                string type = adjacentTiles[i];
                float baseH = GetTileHeight(type);
                float amp = GetNoiseAmplitude(type);

                if (type == "water" || amp <= 0f)
                {
                    totalHeight += baseH;
                }
                else
                {
                    float noise = SampleNoise(worldX, worldZ);
                    totalHeight += baseH + noise * amp;
                }
            }

            return totalHeight / count;
        }

        /// <summary>
        /// Blend vertex colors at tile boundaries by averaging neighboring tile colors.
        /// </summary>
        private static Color32 _blendBoundaryColor(
            string[,] tileTypes, int chunkSize, int vx, int vz)
        {
            var adjacentTiles = _getAdjacentTiles(tileTypes, chunkSize, vx, vz);

            if (adjacentTiles.Count == 0)
                return GetTileColor("grass");

            float r = 0f, g = 0f, b = 0f;
            int count = adjacentTiles.Count;

            for (int i = 0; i < count; i++)
            {
                Color32 c = GetTileColor(adjacentTiles[i]);
                r += c.r;
                g += c.g;
                b += c.b;
            }

            return new Color32(
                (byte)(r / count),
                (byte)(g / count),
                (byte)(b / count),
                255);
        }

        /// <summary>
        /// Get the list of tile types adjacent to a vertex at sub-grid position (vx, vz).
        /// A vertex on a tile boundary can touch up to 4 tiles (at a corner) or 2 tiles
        /// (on an edge).
        /// </summary>
        private static List<string> _getAdjacentTiles(
            string[,] tileTypes, int chunkSize, int vx, int vz)
        {
            var tiles = new List<string>(4);

            // The vertex at (vx, vz) in the sub-vertex grid.
            // Tile indices that could touch this vertex:
            //   tile (vx/SUB - 1, vz/SUB - 1) through tile (vx/SUB, vz/SUB)
            // but only if the vertex is exactly on the boundary.

            // Which tile columns/rows does this vertex border?
            int tileX0 = vx / SUBDIVISIONS - 1;
            int tileX1 = vx / SUBDIVISIONS;
            int tileZ0 = vz / SUBDIVISIONS - 1;
            int tileZ1 = vz / SUBDIVISIONS;

            // If the vertex is not on a boundary in a given axis, both tile indices
            // are the same tile, so we only need the one it's inside.
            bool boundaryX = (vx % SUBDIVISIONS == 0) && (vx > 0);
            bool boundaryZ = (vz % SUBDIVISIONS == 0) && (vz > 0);

            if (boundaryX && boundaryZ)
            {
                // Corner: up to 4 tiles
                _addTileIfValid(tiles, tileTypes, tileX0, tileZ0, chunkSize);
                _addTileIfValid(tiles, tileTypes, tileX0, tileZ1, chunkSize);
                _addTileIfValid(tiles, tileTypes, tileX1, tileZ0, chunkSize);
                _addTileIfValid(tiles, tileTypes, tileX1, tileZ1, chunkSize);
            }
            else if (boundaryX)
            {
                // Edge along X: 2 tiles
                int tz = Mathf.Min(vz / SUBDIVISIONS, chunkSize - 1);
                _addTileIfValid(tiles, tileTypes, tileX0, tz, chunkSize);
                _addTileIfValid(tiles, tileTypes, tileX1, tz, chunkSize);
            }
            else if (boundaryZ)
            {
                // Edge along Z: 2 tiles
                int tx = Mathf.Min(vx / SUBDIVISIONS, chunkSize - 1);
                _addTileIfValid(tiles, tileTypes, tx, tileZ0, chunkSize);
                _addTileIfValid(tiles, tileTypes, tx, tileZ1, chunkSize);
            }
            else
            {
                // Interior vertex: single tile
                int tx = Mathf.Min(vx / SUBDIVISIONS, chunkSize - 1);
                int tz = Mathf.Min(vz / SUBDIVISIONS, chunkSize - 1);
                _addTileIfValid(tiles, tileTypes, tx, tz, chunkSize);
            }

            return tiles;
        }

        private static void _addTileIfValid(
            List<string> tiles, string[,] tileTypes, int tx, int tz, int chunkSize)
        {
            if (tx >= 0 && tx < chunkSize && tz >= 0 && tz < chunkSize)
            {
                string t = (tileTypes != null && tileTypes[tx, tz] != null)
                    ? tileTypes[tx, tz].ToLowerInvariant()
                    : "grass";
                tiles.Add(t);
            }
        }

        // ====================================================================
        // Private Helpers — Normal Computation
        // ====================================================================

        /// <summary>
        /// Compute smooth vertex normals by accumulating face normals from all
        /// triangles that share each vertex, then normalizing. This gives proper
        /// shading across the undulating terrain.
        /// </summary>
        private static Vector3[] _computeSmoothNormals(
            Vector3[] vertices, int[] triangles, int vertexCount)
        {
            var normals = new Vector3[vertexCount];

            // Accumulate face normals into each vertex
            for (int i = 0; i < triangles.Length; i += 3)
            {
                int i0 = triangles[i];
                int i1 = triangles[i + 1];
                int i2 = triangles[i + 2];

                Vector3 v0 = vertices[i0];
                Vector3 v1 = vertices[i1];
                Vector3 v2 = vertices[i2];

                // Cross product for face normal (area-weighted)
                Vector3 edge1 = v1 - v0;
                Vector3 edge2 = v2 - v0;
                Vector3 faceNormal = Vector3.Cross(edge1, edge2);

                // Accumulate (area-weighted by cross product magnitude)
                normals[i0] += faceNormal;
                normals[i1] += faceNormal;
                normals[i2] += faceNormal;
            }

            // Normalize all vertex normals
            for (int i = 0; i < vertexCount; i++)
            {
                if (normals[i].sqrMagnitude > 0.0001f)
                    normals[i] = normals[i].normalized;
                else
                    normals[i] = Vector3.up; // fallback for degenerate geometry
            }

            return normals;
        }

        // ====================================================================
        // Private Helpers — Edge Mesh Generation
        // ====================================================================

        private static void _tryAddEdge(
            List<Vector3> vertices, List<Vector3> normals, List<Vector2> uvs,
            List<Color32> colors, List<int> triangles,
            int x, int z, int nx, int nz, float myBaseHeight,
            string[,] tileTypes, int chunkSize, float tileScale,
            Color32 color, Vector3 faceNormal,
            float chunkWorldX, float chunkWorldZ)
        {
            string neighborType = _getTileType(tileTypes, nx, nz, chunkSize);
            float neighborBaseHeight = GetTileHeight(neighborType);

            if (neighborBaseHeight >= myBaseHeight) return; // no cliff face needed

            string myType = _getTileType(tileTypes, x, z, chunkSize);
            float myAmplitude = GetNoiseAmplitude(myType);
            float neighborAmplitude = GetNoiseAmplitude(neighborType);

            // Determine the two edge endpoints in local chunk space
            float x0 = x * tileScale;
            float x1 = (x + 1) * tileScale;
            float z0 = z * tileScale;
            float z1 = (z + 1) * tileScale;

            // We subdivide the edge into SUBDIVISIONS segments for smoother cliff profiles
            int edgeSegments = SUBDIVISIONS;

            for (int seg = 0; seg < edgeSegments; seg++)
            {
                float t0 = seg / (float)edgeSegments;
                float t1 = (seg + 1) / (float)edgeSegments;

                // Compute the two local positions along this edge segment
                float lx0, lz0, lx1, lz1;

                if (faceNormal == Vector3.right)
                {
                    lx0 = x1; lz0 = Mathf.Lerp(z0, z1, t0);
                    lx1 = x1; lz1 = Mathf.Lerp(z0, z1, t1);
                }
                else if (faceNormal == Vector3.left)
                {
                    lx0 = x0; lz0 = Mathf.Lerp(z1, z0, t0);
                    lx1 = x0; lz1 = Mathf.Lerp(z1, z0, t1);
                }
                else if (faceNormal == Vector3.forward)
                {
                    lx0 = Mathf.Lerp(x1, x0, t0); lz0 = z1;
                    lx1 = Mathf.Lerp(x1, x0, t1); lz1 = z1;
                }
                else // Vector3.back
                {
                    lx0 = Mathf.Lerp(x0, x1, t0); lz0 = z0;
                    lx1 = Mathf.Lerp(x0, x1, t1); lz1 = z0;
                }

                // World positions for noise sampling
                float wx0 = chunkWorldX + lx0;
                float wz0 = chunkWorldZ + lz0;
                float wx1 = chunkWorldX + lx1;
                float wz1 = chunkWorldZ + lz1;

                // Top heights (from my tile)
                float topH0, topH1;
                if (myType == "water" || myAmplitude <= 0f)
                {
                    topH0 = myBaseHeight;
                    topH1 = myBaseHeight;
                }
                else
                {
                    topH0 = myBaseHeight + SampleNoise(wx0, wz0) * myAmplitude;
                    topH1 = myBaseHeight + SampleNoise(wx1, wz1) * myAmplitude;
                }

                // Bottom heights (from neighbor tile)
                float bottomH0, bottomH1;
                if (neighborType == "water" || neighborAmplitude <= 0f)
                {
                    bottomH0 = neighborBaseHeight;
                    bottomH1 = neighborBaseHeight;
                }
                else
                {
                    bottomH0 = neighborBaseHeight + SampleNoise(wx0, wz0) * neighborAmplitude;
                    bottomH1 = neighborBaseHeight + SampleNoise(wx1, wz1) * neighborAmplitude;
                }

                // Skip if no actual height difference at these points
                if (topH0 <= bottomH0 && topH1 <= bottomH1) continue;

                // Clamp bottom to not exceed top
                bottomH0 = Mathf.Min(bottomH0, topH0);
                bottomH1 = Mathf.Min(bottomH1, topH1);

                Vector3 v0 = new Vector3(lx0, topH0, lz0);
                Vector3 v1 = new Vector3(lx1, topH1, lz1);
                Vector3 v2 = new Vector3(lx1, bottomH1, lz1);
                Vector3 v3 = new Vector3(lx0, bottomH0, lz0);

                // Darken cliff faces slightly
                byte darken = 30;
                Color32 edgeColor = new Color32(
                    (byte)Mathf.Max(0, color.r - darken),
                    (byte)Mathf.Max(0, color.g - darken),
                    (byte)Mathf.Max(0, color.b - darken),
                    255);

                int baseIndex = vertices.Count;
                vertices.Add(v0);
                vertices.Add(v1);
                vertices.Add(v2);
                vertices.Add(v3);
                normals.Add(faceNormal);
                normals.Add(faceNormal);
                normals.Add(faceNormal);
                normals.Add(faceNormal);
                uvs.Add(new Vector2(t0, 1));
                uvs.Add(new Vector2(t1, 1));
                uvs.Add(new Vector2(t1, 0));
                uvs.Add(new Vector2(t0, 0));
                colors.Add(edgeColor);
                colors.Add(edgeColor);
                colors.Add(edgeColor);
                colors.Add(edgeColor);

                triangles.Add(baseIndex + 0);
                triangles.Add(baseIndex + 1);
                triangles.Add(baseIndex + 2);
                triangles.Add(baseIndex + 0);
                triangles.Add(baseIndex + 2);
                triangles.Add(baseIndex + 3);
            }
        }
    }
}
