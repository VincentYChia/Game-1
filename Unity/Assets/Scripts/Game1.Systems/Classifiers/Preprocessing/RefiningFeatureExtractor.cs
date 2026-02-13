// ============================================================================
// Game1.Systems.Classifiers.Preprocessing.RefiningFeatureExtractor
// Migrated from: systems/crafting_classifier.py (LightGBMFeatureExtractor.extract_refining_features, lines 588-676)
// Migration phase: 5
// Date: 2026-02-13
//
// CRITICAL: Feature count (19), order, and computation MUST match training
// script EXACTLY. Category distribution uses CORE materials only.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;
using Game1.Data.Databases;

namespace Game1.Systems.Classifiers.Preprocessing
{
    /// <summary>
    /// Extracts 19 numeric features from refining UI state for LightGBM inference.
    ///
    /// Feature layout (EXACT ORDER):
    ///   [0-1]   num_cores, num_spokes
    ///   [2-3]   core_qty, spoke_qty
    ///   [4-5]   spoke/core ratio, qty ratio
    ///   [6]     material_diversity
    ///   [7-11]  category distribution (CORE only: elemental, metal, monster_drop, stone, wood)
    ///   [12]    refinement 'basic' count (core only)
    ///   [13-14] core tier stats (mean, max)
    ///   [15-16] spoke tier stats (mean, max)
    ///   [17]    tier_mismatch (abs difference of means)
    ///   [18]    station_tier
    /// </summary>
    public class RefiningFeatureExtractor
    {
        public const int FeatureCount = 19;

        private readonly MaterialDatabase _materialsDb;

        public RefiningFeatureExtractor(MaterialDatabase materialsDb)
        {
            _materialsDb = materialsDb;
        }

        /// <summary>
        /// Extract 19 features from refining slot data.
        ///
        /// coreSlots: list of (materialId, quantity) or null for empty.
        /// surroundingSlots: list of (materialId, quantity) or null for empty.
        /// stationTier: crafting station tier (1-4).
        /// </summary>
        public float[] Extract(List<(string materialId, int quantity)?> coreSlots,
                               List<(string materialId, int quantity)?> surroundingSlots,
                               int stationTier)
        {
            float[] features = new float[FeatureCount];
            int idx = 0;

            // Build non-null input lists
            var coreInputs = new List<(string materialId, int quantity)>();
            foreach (var slot in coreSlots)
            {
                if (slot.HasValue)
                    coreInputs.Add(slot.Value);
            }

            var spokeInputs = new List<(string materialId, int quantity)>();
            foreach (var slot in surroundingSlots)
            {
                if (slot.HasValue)
                    spokeInputs.Add(slot.Value);
            }

            // Basic counts (2 features) [0-1]
            int numCores = coreInputs.Count;
            int numSpokes = spokeInputs.Count;
            features[idx++] = numCores;
            features[idx++] = numSpokes;

            // Total quantities (2 features) [2-3]
            int coreQty = 0;
            foreach (var c in coreInputs) coreQty += c.quantity;
            int spokeQty = 0;
            foreach (var s in spokeInputs) spokeQty += s.quantity;
            features[idx++] = coreQty;
            features[idx++] = spokeQty;

            // Ratio features (2 features) [4-5]
            features[idx++] = numSpokes / MathF.Max(1, numCores);
            features[idx++] = spokeQty / MathF.Max(1, coreQty);

            // Material diversity across ALL slots (1 feature) [6]
            var allMats = new HashSet<string>();
            foreach (var c in coreInputs) allMats.Add(c.materialId);
            foreach (var s in spokeInputs) allMats.Add(s.materialId);
            features[idx++] = allMats.Count;

            // Category distribution - CORE materials only (5 features) [7-11]
            var catCounts = new Dictionary<string, int>();
            foreach (var c in coreInputs)
            {
                string cat = GetCategory(c.materialId);
                catCounts[cat] = catCounts.GetValueOrDefault(cat, 0) + 1;
            }
            features[idx++] = catCounts.GetValueOrDefault("elemental", 0);
            features[idx++] = catCounts.GetValueOrDefault("metal", 0);
            features[idx++] = catCounts.GetValueOrDefault("monster_drop", 0);
            features[idx++] = catCounts.GetValueOrDefault("stone", 0);
            features[idx++] = catCounts.GetValueOrDefault("wood", 0);

            // Refinement distribution - core only (1 feature) [12]
            int basicCount = 0;
            foreach (var c in coreInputs)
            {
                if (GetRefinementLevel(c.materialId) == "basic")
                    basicCount++;
            }
            features[idx++] = basicCount;

            // Tier statistics (5 features) [13-17]
            var coreTiers = new List<float>();
            foreach (var c in coreInputs)
                coreTiers.Add(GetTier(c.materialId));

            var spokeTiers = new List<float>();
            foreach (var s in spokeInputs)
                spokeTiers.Add(GetTier(s.materialId));

            float coreMean = coreTiers.Count > 0 ? AlchemyFeatureExtractor.Mean(coreTiers) : 0;
            float coreMax = coreTiers.Count > 0 ? AlchemyFeatureExtractor.Max(coreTiers) : 0;
            float spokeMean = spokeTiers.Count > 0 ? AlchemyFeatureExtractor.Mean(spokeTiers) : 0;
            float spokeMax = spokeTiers.Count > 0 ? AlchemyFeatureExtractor.Max(spokeTiers) : 0;

            features[idx++] = coreMean;   // [13]
            features[idx++] = coreMax;    // [14]
            features[idx++] = spokeMean;  // [15]
            features[idx++] = spokeMax;   // [16]

            // Tier mismatch [17]
            if (coreTiers.Count > 0 && spokeTiers.Count > 0)
                features[idx++] = MathF.Abs(coreMean - spokeMean);
            else
                features[idx++] = 0;

            // Station tier (1 feature) [18]
            features[idx++] = stationTier;

            System.Diagnostics.Debug.Assert(idx == FeatureCount,
                $"[RefiningFeatureExtractor] Expected {FeatureCount} features, got {idx}");

            return features;
        }

        // ====================================================================
        // Private helpers
        // ====================================================================

        private string GetCategory(string materialId)
        {
            var mat = _materialsDb?.GetMaterial(materialId);
            return mat?.MaterialCategory ?? "unknown";
        }

        private float GetTier(string materialId)
        {
            var mat = _materialsDb?.GetMaterial(materialId);
            return mat?.Tier ?? 1;
        }

        private string GetRefinementLevel(string materialId)
        {
            var mat = _materialsDb?.GetMaterial(materialId);
            if (mat == null) return "basic";

            // Check Properties dict for tags
            if (mat.Properties?.ContainsKey("tags") == true)
            {
                var tags = mat.Properties["tags"];
                if (tags is Newtonsoft.Json.Linq.JArray jArr)
                {
                    foreach (var t in jArr)
                    {
                        string tag = t.ToString();
                        if (tag == "basic" || tag == "refined" || tag == "raw" || tag == "processed")
                            return tag;
                    }
                }
            }

            // Check Tags list
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
    }
}
