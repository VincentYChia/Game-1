// ============================================================================
// Game1.Systems.Classifiers.Preprocessing.SmithingPreprocessor
// Migrated from: systems/crafting_classifier.py (SmithingImageRenderer, lines 220-387)
// Migration phase: 5
// Date: 2026-02-13
//
// CRITICAL: Shape masks, tier fills, and pixel layout MUST match training data.
// Output: 36x36x3 float32 image in row-major, channel-last order.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;

namespace Game1.Systems.Classifiers.Preprocessing
{
    /// <summary>
    /// Renders a smithing material grid to a 36x36x3 RGB float image for CNN inference.
    /// Grid: 9x9 cells, each cell = 4x4 pixels = 36x36 total.
    ///
    /// Algorithm:
    ///   1. Center station grid in 9x9 canvas
    ///   2. For each cell: color × shape_mask × tier_fill_mask
    ///   3. Place 4x4 cell block in image
    /// </summary>
    public class SmithingPreprocessor
    {
        // ====================================================================
        // Constants — MUST MATCH crafting_classifier.py lines 230-282 EXACTLY
        // ====================================================================

        public const int ImgSize = 36;
        public const int CellSize = 4;
        public const int GridSize = 9;

        // Shape masks by category (4x4, row-major)
        // Each float[16] represents a 4x4 grid read left-to-right, top-to-bottom

        /// <summary>Metal: Full square (solid, industrial).</summary>
        private static readonly float[] ShapeMetal = {
            1, 1, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1,
        };

        /// <summary>Wood: Horizontal lines (grain pattern).</summary>
        private static readonly float[] ShapeWood = {
            1, 1, 1, 1,
            0, 0, 0, 0,
            1, 1, 1, 1,
            0, 0, 0, 0,
        };

        /// <summary>Stone: X pattern (angular, rocky).</summary>
        private static readonly float[] ShapeStone = {
            1, 0, 0, 1,
            0, 1, 1, 0,
            0, 1, 1, 0,
            1, 0, 0, 1,
        };

        /// <summary>Monster drop: Diamond shape (organic).</summary>
        private static readonly float[] ShapeMonsterDrop = {
            0, 1, 1, 0,
            1, 1, 1, 1,
            1, 1, 1, 1,
            0, 1, 1, 0,
        };

        /// <summary>Elemental: Plus/cross pattern (same as monster_drop in current code).</summary>
        private static readonly float[] ShapeElemental = {
            0, 1, 1, 0,
            1, 1, 1, 1,
            1, 1, 1, 1,
            0, 1, 1, 0,
        };

        /// <summary>Default shape for unknown categories: solid square.</summary>
        private static readonly float[] ShapeDefault = {
            1, 1, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1,
        };

        private static readonly Dictionary<string, float[]> CategoryShapes = new()
        {
            { "metal", ShapeMetal },
            { "wood", ShapeWood },
            { "stone", ShapeStone },
            { "monster_drop", ShapeMonsterDrop },
            { "elemental", ShapeElemental },
        };

        /// <summary>Tier fill sizes: T1=1x1, T2=2x2, T3=3x3, T4=full 4x4.</summary>
        private static readonly Dictionary<int, int> TierFillSizes = new()
        {
            { 1, 1 }, { 2, 2 }, { 3, 3 }, { 4, 4 },
        };

        // ====================================================================
        // Fields
        // ====================================================================

        private readonly MaterialColorEncoder _encoder;

        // ====================================================================
        // Constructor
        // ====================================================================

        public SmithingPreprocessor(MaterialColorEncoder encoder)
        {
            _encoder = encoder;
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>
        /// Preprocess a smithing grid into a flat float array for CNN input.
        ///
        /// The grid dictionary maps (col, row) tuples to material IDs.
        /// stationGridSize is the active grid size (3-9), centered in the 9x9 canvas.
        ///
        /// Returns float[36*36*3] in row-major, channel-last order (H, W, C):
        ///   index = (row * 36 + col) * 3 + channel
        /// </summary>
        public float[] Preprocess(Dictionary<(int col, int row), string> grid, int stationGridSize)
        {
            // Build 9x9 material ID grid (centered)
            string[,] fullGrid = new string[GridSize, GridSize]; // [row, col]
            int offset = (GridSize - stationGridSize) / 2;

            foreach (var kvp in grid)
            {
                int gridCol = offset + kvp.Key.col;
                int gridRow = offset + kvp.Key.row;
                if (gridCol >= 0 && gridCol < GridSize && gridRow >= 0 && gridRow < GridSize)
                {
                    fullGrid[gridRow, gridCol] = kvp.Value;
                }
            }

            return GridToImage(fullGrid);
        }

        /// <summary>
        /// Direct preprocessing from a 9x9 string grid (for testing).
        /// grid[row, col] = materialId or null.
        /// </summary>
        public float[] PreprocessGrid(string[,] grid)
        {
            return GridToImage(grid);
        }

        // ====================================================================
        // Private implementation
        // ====================================================================

        /// <summary>
        /// Convert 9x9 material grid to 36x36x3 image.
        /// Matches Python _grid_to_image exactly (lines 347-387).
        /// </summary>
        private float[] GridToImage(string[,] grid)
        {
            float[] img = new float[ImgSize * ImgSize * 3]; // 36*36*3 = 3888

            for (int i = 0; i < GridSize; i++) // row
            {
                for (int j = 0; j < GridSize; j++) // col
                {
                    string materialId = grid[i, j];

                    if (materialId == null)
                        continue; // Empty cell = black (already zeros)

                    // Get base color [R, G, B]
                    float[] color = _encoder.Encode(materialId);

                    // Get shape mask (4x4) based on category
                    float[] shapeMask = GetShapeMask(materialId);

                    // Get tier fill mask (4x4)
                    float[] tierMask = GetTierFillMask(materialId);

                    // Place cell pixels in image
                    int yStart = i * CellSize;
                    int xStart = j * CellSize;

                    for (int py = 0; py < CellSize; py++)
                    {
                        for (int px = 0; px < CellSize; px++)
                        {
                            int maskIdx = py * CellSize + px;
                            float combined = shapeMask[maskIdx] * tierMask[maskIdx];

                            if (combined > 0)
                            {
                                int imgRow = yStart + py;
                                int imgCol = xStart + px;
                                int baseIdx = (imgRow * ImgSize + imgCol) * 3;

                                img[baseIdx] = color[0] * combined;
                                img[baseIdx + 1] = color[1] * combined;
                                img[baseIdx + 2] = color[2] * combined;
                            }
                        }
                    }
                }
            }

            return img;
        }

        /// <summary>
        /// Get the 4x4 shape mask for a material's category.
        /// Unknown materials and null return DEFAULT_SHAPE (all ones).
        /// </summary>
        private float[] GetShapeMask(string materialId)
        {
            if (materialId == null)
                return ShapeDefault;

            var matData = _encoder.GetMaterialData(materialId);
            if (matData == null)
                return ShapeDefault;

            string category = matData.MaterialCategory ?? "unknown";
            return CategoryShapes.GetValueOrDefault(category, ShapeDefault);
        }

        /// <summary>
        /// Get a 4x4 tier fill mask.
        /// Null/unknown materials return all-zeros (nothing rendered).
        /// </summary>
        private float[] GetTierFillMask(string materialId)
        {
            if (materialId == null)
                return new float[CellSize * CellSize]; // all zeros

            var matData = _encoder.GetMaterialData(materialId);
            if (matData == null)
                return new float[CellSize * CellSize]; // all zeros

            int tier = matData.Tier;
            int fillSize = TierFillSizes.GetValueOrDefault(tier, 4);

            float[] mask = new float[CellSize * CellSize];
            int maskOffset = (CellSize - fillSize) / 2;

            for (int r = 0; r < fillSize; r++)
            {
                for (int c = 0; c < fillSize; c++)
                {
                    mask[(maskOffset + r) * CellSize + (maskOffset + c)] = 1.0f;
                }
            }

            return mask;
        }
    }
}
