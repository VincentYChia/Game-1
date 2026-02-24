// ============================================================================
// Game1.Systems.Classifiers.Preprocessing.AlchemyFeatureExtractor
// Migrated from: systems/crafting_classifier.py (LightGBMFeatureExtractor.extract_alchemy_features, lines 678-763)
// Migration phase: 5
// Date: 2026-02-13
//
// CRITICAL: Feature count (34), order, and computation MUST match training
// script EXACTLY. Any reordering will silently produce wrong predictions.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;
using Game1.Data.Databases;

namespace Game1.Systems.Classifiers.Preprocessing
{
    /// <summary>
    /// Extracts 34 numeric features from alchemy UI state for LightGBM inference.
    ///
    /// Feature layout (EXACT ORDER):
    ///   [0]     num_ingredients
    ///   [1]     total_qty
    ///   [2]     avg_qty
    ///   [3-20]  position features (6 positions × 3: tier, qty, cat_idx)
    ///   [21]    material_diversity
    ///   [22-26] category distribution (elemental, metal, monster_drop, stone, wood)
    ///   [27]    refinement 'basic' count
    ///   [28-30] tier stats (mean, max, std)
    ///   [31-32] sequential patterns (increases, decreases)
    ///   [33]    station_tier
    /// </summary>
    public class AlchemyFeatureExtractor
    {
        public const int FeatureCount = 34;
        private const int MaxPositions = 6;

        private readonly MaterialDatabase _materialsDb;

        public AlchemyFeatureExtractor(MaterialDatabase materialsDb)
        {
            _materialsDb = materialsDb;
        }

        /// <summary>
        /// Extract 34 features from alchemy slot data.
        ///
        /// Each slot is (materialId, quantity) or null for empty.
        /// stationTier is the crafting station tier (1-4).
        /// </summary>
        public float[] Extract(List<(string materialId, int quantity)?> slots, int stationTier)
        {
            float[] features = new float[FeatureCount];
            int idx = 0;

            // Build ingredients list (non-null slots only)
            var ingredients = new List<(string materialId, int quantity, int position)>();
            for (int i = 0; i < slots.Count; i++)
            {
                if (slots[i].HasValue)
                {
                    ingredients.Add((slots[i].Value.materialId, slots[i].Value.quantity, i + 1));
                }
            }

            // Basic counts (3 features)
            int numIngredients = ingredients.Count;
            int totalQty = 0;
            foreach (var ing in ingredients) totalQty += ing.quantity;

            features[idx++] = numIngredients;                            // [0]
            features[idx++] = totalQty;                                  // [1]
            features[idx++] = totalQty / MathF.Max(1, numIngredients);   // [2]

            // Position-based features: 6 positions × 3 = 18 features ([3]-[20])
            for (int pos = 0; pos < MaxPositions; pos++)
            {
                if (pos < ingredients.Count)
                {
                    var ing = ingredients[pos];
                    var mat = GetMaterialInfo(ing.materialId);
                    features[idx++] = mat.tier;                          // tier
                    features[idx++] = ing.quantity;                      // qty
                    features[idx++] = GetCategoryIdx(mat.category);      // cat_idx
                }
                else
                {
                    features[idx++] = 0;  // tier
                    features[idx++] = 0;  // qty
                    features[idx++] = 0;  // cat_idx
                }
            }

            // Material diversity (1 feature) [21]
            var uniqueMats = new HashSet<string>();
            foreach (var ing in ingredients) uniqueMats.Add(ing.materialId);
            features[idx++] = uniqueMats.Count;

            // Category distribution - HARDCODED 5 categories, EXACT order (5 features) [22-26]
            var catCounts = new Dictionary<string, int>();
            foreach (var ing in ingredients)
            {
                string cat = GetMaterialInfo(ing.materialId).category;
                catCounts[cat] = catCounts.GetValueOrDefault(cat, 0) + 1;
            }
            features[idx++] = catCounts.GetValueOrDefault("elemental", 0);
            features[idx++] = catCounts.GetValueOrDefault("metal", 0);
            features[idx++] = catCounts.GetValueOrDefault("monster_drop", 0);
            features[idx++] = catCounts.GetValueOrDefault("stone", 0);
            features[idx++] = catCounts.GetValueOrDefault("wood", 0);

            // Refinement distribution - count of 'basic' (1 feature) [27]
            int basicCount = 0;
            foreach (var ing in ingredients)
            {
                if (GetRefinementLevel(ing.materialId) == "basic")
                    basicCount++;
            }
            features[idx++] = basicCount;

            // Tier statistics (3 features) [28-30]
            var tiers = new List<float>();
            foreach (var ing in ingredients)
                tiers.Add(GetMaterialInfo(ing.materialId).tier);

            features[idx++] = tiers.Count > 0 ? Mean(tiers) : 0;           // mean
            features[idx++] = tiers.Count > 0 ? Max(tiers) : 0;            // max
            features[idx++] = tiers.Count > 1 ? PopulationStdDev(tiers) : 0; // std (population)

            // Sequential patterns (2 features) [31-32]
            if (tiers.Count >= 2)
            {
                int increases = 0, decreases = 0;
                for (int i = 0; i < tiers.Count - 1; i++)
                {
                    if (tiers[i + 1] > tiers[i]) increases++;
                    if (tiers[i + 1] < tiers[i]) decreases++;
                }
                features[idx++] = increases;
                features[idx++] = decreases;
            }
            else
            {
                features[idx++] = 0;
                features[idx++] = 0;
            }

            // Station tier (1 feature) [33]
            features[idx++] = stationTier;

            System.Diagnostics.Debug.Assert(idx == FeatureCount,
                $"[AlchemyFeatureExtractor] Expected {FeatureCount} features, got {idx}");

            return features;
        }

        // ====================================================================
        // Shared helpers (used by all three extractors via static methods)
        // ====================================================================

        /// <summary>Get material category and tier. Returns defaults for unknown.</summary>
        private (string category, int tier) GetMaterialInfo(string materialId)
        {
            var mat = _materialsDb?.GetMaterial(materialId);
            if (mat != null)
                return (mat.MaterialCategory ?? "unknown", mat.Tier);
            return ("unknown", 1);
        }

        /// <summary>
        /// Get refinement level from material tags.
        /// Scans for 'basic', 'refined', 'raw', 'processed'; defaults to 'basic'.
        /// </summary>
        private string GetRefinementLevel(string materialId)
        {
            var mat = _materialsDb?.GetMaterial(materialId);
            if (mat == null) return "basic";

            var tags = mat.Properties?.ContainsKey("tags") == true
                ? mat.Properties["tags"]
                : null;

            if (tags is Newtonsoft.Json.Linq.JArray jArr)
            {
                foreach (var t in jArr)
                {
                    string tag = t.ToString();
                    if (tag == "basic" || tag == "refined" || tag == "raw" || tag == "processed")
                        return tag;
                }
            }

            // Also check Tags list
            if (mat.Tags != null)
            {
                foreach (var tag in mat.Tags)
                {
                    if (tag == "basic" || tag == "refined" || tag == "raw" || tag == "processed")
                        return tag;
                }
            }

            return "basic";
        }

        // ====================================================================
        // Category index mapping — HARDCODED alphabetical order
        // MUST MATCH crafting_classifier.py CATEGORY_TO_IDX (lines 532-538)
        // ====================================================================

        private static readonly Dictionary<string, int> CategoryToIdx = new()
        {
            { "elemental", 0 }, { "metal", 1 }, { "monster_drop", 2 },
            { "stone", 3 }, { "wood", 4 },
        };

        internal static int GetCategoryIdx(string category)
        {
            return CategoryToIdx.GetValueOrDefault(category, 0);
        }

        // ====================================================================
        // Math helpers — match numpy behavior exactly
        // ====================================================================

        internal static float Mean(List<float> values)
        {
            float sum = 0;
            foreach (var v in values) sum += v;
            return sum / values.Count;
        }

        internal static float Max(List<float> values)
        {
            float max = float.MinValue;
            foreach (var v in values)
                if (v > max) max = v;
            return max;
        }

        /// <summary>
        /// Population standard deviation (numpy.std default, divides by N not N-1).
        /// CRITICAL: np.std uses population std, NOT sample std.
        /// </summary>
        public static float PopulationStdDev(List<float> values)
        {
            if (values.Count <= 1) return 0f;

            float mean = Mean(values);
            float sumSqDiff = 0;
            foreach (var v in values)
            {
                float diff = v - mean;
                sumSqDiff += diff * diff;
            }
            return MathF.Sqrt(sumSqDiff / values.Count); // N, not N-1
        }
    }
}
