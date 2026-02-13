// ============================================================================
// Game1.Systems.Classifiers.Preprocessing.AdornmentPreprocessor
// Migrated from: systems/crafting_classifier.py (AdornmentImageRenderer, lines 390-511)
// Migration phase: 5
// Date: 2026-02-13
//
// CRITICAL: Bresenham line drawing, circle rendering, and blending logic
// MUST match the Python implementation pixel-for-pixel.
// Output: 56x56x3 float32 image in row-major, channel-last order.
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Systems.Classifiers.Preprocessing
{
    /// <summary>
    /// Renders adornment (enchanting) vertices and shapes to a 56x56x3 RGB float image
    /// for CNN inference.
    ///
    /// Coordinate space: [-7, +7] x [-7, +7] (Cartesian)
    /// Pixel mapping: px = (x+7)*4, py = (7-y)*4
    ///
    /// Draw order (CRITICAL): edges first, then vertices on top.
    /// Edge blending: average with existing if non-zero.
    /// Vertex circles: overwrite (no blending).
    /// </summary>
    public class AdornmentPreprocessor
    {
        // ====================================================================
        // Constants — MUST MATCH crafting_classifier.py lines 398-399 EXACTLY
        // ====================================================================

        public const int ImgSize = 56;
        public const int CoordRange = 7;
        private const int LineThickness = 2;
        private const int VertexRadius = 3;

        // ====================================================================
        // Fields
        // ====================================================================

        private readonly MaterialColorEncoder _encoder;

        // ====================================================================
        // Constructor
        // ====================================================================

        public AdornmentPreprocessor(MaterialColorEncoder encoder)
        {
            _encoder = encoder;
        }

        // ====================================================================
        // Data structures for input
        // ====================================================================

        /// <summary>A vertex in the adornment graph with coordinate key and optional material.</summary>
        public struct VertexData
        {
            public string CoordKey;   // e.g., "3,4"
            public string MaterialId; // null if no material placed
        }

        /// <summary>A shape connecting multiple vertices.</summary>
        public struct ShapeData
        {
            public string Type;            // Shape type
            public List<string> Vertices;  // List of coord keys (e.g., ["3,4", "5,2", ...])
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>
        /// Preprocess adornment UI state into a flat float array for CNN input.
        ///
        /// Returns float[56*56*3] in row-major, channel-last order (H, W, C):
        ///   index = (row * 56 + col) * 3 + channel
        /// </summary>
        public float[] Preprocess(Dictionary<string, string> vertices, List<ShapeData> shapes)
        {
            float[] img = new float[ImgSize * ImgSize * 3]; // 56*56*3 = 9408

            // Step 1: Draw edges (lines between shape vertices)
            foreach (var shape in shapes)
            {
                var shapeVerts = shape.Vertices;
                int n = shapeVerts.Count;

                for (int i = 0; i < n; i++)
                {
                    string v1Str = shapeVerts[i];
                    string v2Str = shapeVerts[(i + 1) % n];

                    ParseCoord(v1Str, out int x1, out int y1);
                    ParseCoord(v2Str, out int x2, out int y2);

                    CoordToPixel(x1, y1, out int px1, out int py1);
                    CoordToPixel(x2, y2, out int px2, out int py2);

                    // Determine line color from endpoint materials
                    vertices.TryGetValue(v1Str, out string mat1);
                    vertices.TryGetValue(v2Str, out string mat2);

                    float[] color;
                    bool hasMat1 = mat1 != null;
                    bool hasMat2 = mat2 != null;

                    if (hasMat1 && hasMat2)
                    {
                        float[] c1 = _encoder.Encode(mat1);
                        float[] c2 = _encoder.Encode(mat2);
                        color = new float[] {
                            (c1[0] + c2[0]) / 2f,
                            (c1[1] + c2[1]) / 2f,
                            (c1[2] + c2[2]) / 2f
                        };
                    }
                    else if (hasMat1)
                    {
                        color = _encoder.Encode(mat1);
                    }
                    else if (hasMat2)
                    {
                        color = _encoder.Encode(mat2);
                    }
                    else
                    {
                        color = new float[] { 0.3f, 0.3f, 0.3f };
                    }

                    DrawLine(img, px1, py1, px2, py2, color, LineThickness);
                }
            }

            // Step 2: Draw vertices (filled circles) — AFTER edges so they overwrite
            foreach (var kvp in vertices)
            {
                ParseCoord(kvp.Key, out int x, out int y);
                CoordToPixel(x, y, out int px, out int py);
                float[] color = _encoder.Encode(kvp.Value);
                DrawCircle(img, px, py, VertexRadius, color);
            }

            return img;
        }

        // ====================================================================
        // Private helpers
        // ====================================================================

        /// <summary>
        /// Parse "x,y" coordinate string to integers.
        /// </summary>
        private static void ParseCoord(string coordStr, out int x, out int y)
        {
            int commaIdx = coordStr.IndexOf(',');
            x = int.Parse(coordStr.Substring(0, commaIdx));
            y = int.Parse(coordStr.Substring(commaIdx + 1));
        }

        /// <summary>
        /// Convert Cartesian coordinates to pixel coordinates.
        /// Matches Python: px = int((x+7)*4), py = int((7-y)*4)
        /// </summary>
        private static void CoordToPixel(int x, int y, out int px, out int py)
        {
            px = (x + CoordRange) * 4;
            py = (CoordRange - y) * 4;
        }

        /// <summary>
        /// Draw line using Bresenham's algorithm with thickness and blending.
        /// Matches Python implementation lines 475-503 EXACTLY.
        ///
        /// Blending rule: if existing pixel has any non-zero channel,
        /// average (existing + new) / 2. Otherwise overwrite.
        ///
        /// Thickness: for each point on the line, draw a square brush
        /// from -thickness//2 to thickness//2 (inclusive on both sides).
        /// With thickness=2: range is {-1, 0, 1} — effectively 3 pixels wide.
        /// </summary>
        private static void DrawLine(float[] img, int x0, int y0, int x1, int y1,
                                     float[] color, int thickness)
        {
            int dx = Math.Abs(x1 - x0);
            int dy = Math.Abs(y1 - y0);
            int sx = x0 < x1 ? 1 : -1;
            int sy = y0 < y1 ? 1 : -1;
            int err = dx - dy;

            int halfThick = thickness / 2;

            while (true)
            {
                // Draw thick point
                for (int ty = -halfThick; ty <= halfThick; ty++)
                {
                    for (int tx = -halfThick; tx <= halfThick; tx++)
                    {
                        int px = x0 + tx;
                        int py = y0 + ty;

                        if (px >= 0 && px < ImgSize && py >= 0 && py < ImgSize)
                        {
                            int baseIdx = (py * ImgSize + px) * 3;

                            // Check if existing pixel is non-zero
                            bool hasExisting = img[baseIdx] > 0 ||
                                               img[baseIdx + 1] > 0 ||
                                               img[baseIdx + 2] > 0;

                            if (hasExisting)
                            {
                                // Blend: average existing and new
                                img[baseIdx] = (img[baseIdx] + color[0]) / 2f;
                                img[baseIdx + 1] = (img[baseIdx + 1] + color[1]) / 2f;
                                img[baseIdx + 2] = (img[baseIdx + 2] + color[2]) / 2f;
                            }
                            else
                            {
                                img[baseIdx] = color[0];
                                img[baseIdx + 1] = color[1];
                                img[baseIdx + 2] = color[2];
                            }
                        }
                    }
                }

                if (x0 == x1 && y0 == y1)
                    break;

                int e2 = 2 * err;
                if (e2 > -dy)
                {
                    err -= dy;
                    x0 += sx;
                }
                if (e2 < dx)
                {
                    err += dx;
                    y0 += sy;
                }
            }
        }

        /// <summary>
        /// Draw a filled circle at (cx, cy) with given radius and color.
        /// Matches Python implementation lines 505-511.
        ///
        /// Overwrites pixels directly (no blending).
        /// Circle test: (x-cx)^2 + (y-cy)^2 &lt;= radius^2 (inclusive).
        /// </summary>
        private static void DrawCircle(float[] img, int cx, int cy, int radius, float[] color)
        {
            int rSq = radius * radius;

            for (int y = Math.Max(0, cy - radius); y <= Math.Min(ImgSize - 1, cy + radius); y++)
            {
                for (int x = Math.Max(0, cx - radius); x <= Math.Min(ImgSize - 1, cx + radius); x++)
                {
                    if ((x - cx) * (x - cx) + (y - cy) * (y - cy) <= rSq)
                    {
                        int baseIdx = (y * ImgSize + x) * 3;
                        img[baseIdx] = color[0];
                        img[baseIdx + 1] = color[1];
                        img[baseIdx + 2] = color[2];
                    }
                }
            }
        }
    }
}
