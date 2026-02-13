// ============================================================================
// Game1.Systems.Classifiers.Preprocessing.EngineeringFeatureExtractor
// Migrated from: systems/crafting_classifier.py (LightGBMFeatureExtractor.extract_engineering_features, lines 765-850)
// Migration phase: 5
// Date: 2026-02-13
//
// CRITICAL: Feature count (28), order, slot type iteration order, and
// computation MUST match training script EXACTLY.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;
using Game1.Data.Databases;

namespace Game1.Systems.Classifiers.Preprocessing
{
    /// <summary>
    /// Extracts 28 numeric features from engineering UI state for LightGBM inference.
    ///
    /// Feature layout (EXACT ORDER):
    ///   [0]     num_slots (total filled across all types)
    ///   [1]     total_qty
    ///   [2-9]   slot type distribution (8 types in fixed order)
    ///   [10]    unique_slot_types
    ///   [11-13] critical slot flags (has_FRAME, has_FUNCTION, has_POWER)
    ///   [14]    material_diversity
    ///   [15-19] category distribution (elemental, metal, monster_drop, stone, wood)
    ///   [20]    refinement 'basic' count
    ///   [21-23] tier stats (mean, max, std)
    ///   [24-26] qty by slot type (frame_qty, power_qty, function_qty)
    ///   [27]    station_tier
    /// </summary>
    public class EngineeringFeatureExtractor
    {
        public const int FeatureCount = 28;

        /// <summary>
        /// Slot type iteration order — MUST BE EXACT.
        /// Matches Python line 804-805.
        /// </summary>
        private static readonly string[] SlotTypeOrder = {
            "FRAME", "FUNCTION", "POWER", "MODIFIER",
            "UTILITY", "ENHANCEMENT", "CORE", "CATALYST"
        };

        private readonly MaterialDatabase _materialsDb;

        public EngineeringFeatureExtractor(MaterialDatabase materialsDb)
        {
            _materialsDb = materialsDb;
        }

        /// <summary>
        /// A placed material in a typed engineering slot.
        /// </summary>
        public struct EngineeringSlot
        {
            public string SlotType;    // FRAME, FUNCTION, POWER, etc.
            public string MaterialId;
            public int Quantity;
        }

        /// <summary>
        /// Extract 28 features from engineering slot data.
        ///
        /// slotsDict maps slot type (e.g., "FRAME") to list of (materialId, quantity).
        /// stationTier is the crafting station tier (1-4).
        /// </summary>
        public float[] Extract(Dictionary<string, List<(string materialId, int quantity)>> slotsDict,
                               int stationTier)
        {
            float[] features = new float[FeatureCount];
            int idx = 0;

            // Flatten into single list with type info (matches Python lines 784-791)
            var slots = new List<EngineeringSlot>();
            foreach (var kvp in slotsDict)
            {
                foreach (var mat in kvp.Value)
                {
                    slots.Add(new EngineeringSlot
                    {
                        SlotType = kvp.Key,
                        MaterialId = mat.materialId,
                        Quantity = mat.quantity
                    });
                }
            }

            // Basic counts (2 features) [0-1]
            int numSlots = slots.Count;
            int totalQty = 0;
            foreach (var s in slots) totalQty += s.Quantity;
            features[idx++] = numSlots;
            features[idx++] = totalQty;

            // Slot type distribution - 8 features in EXACT order [2-9]
            var slotTypeCounts = new Dictionary<string, int>();
            var slotTypeSet = new HashSet<string>();
            foreach (var s in slots)
            {
                slotTypeCounts[s.SlotType] = slotTypeCounts.GetValueOrDefault(s.SlotType, 0) + 1;
                slotTypeSet.Add(s.SlotType);
            }
            foreach (var sType in SlotTypeOrder)
            {
                features[idx++] = slotTypeCounts.GetValueOrDefault(sType, 0);
            }

            // Unique slot types (1 feature) [10]
            features[idx++] = slotTypeSet.Count;

            // Critical slots present - binary (3 features) [11-13]
            features[idx++] = slotTypeSet.Contains("FRAME") ? 1 : 0;
            features[idx++] = slotTypeSet.Contains("FUNCTION") ? 1 : 0;
            features[idx++] = slotTypeSet.Contains("POWER") ? 1 : 0;

            // Material diversity (1 feature) [14]
            var uniqueMats = new HashSet<string>();
            foreach (var s in slots) uniqueMats.Add(s.MaterialId);
            features[idx++] = uniqueMats.Count;

            // Category distribution - ALL materials (5 features) [15-19]
            var catCounts = new Dictionary<string, int>();
            foreach (var s in slots)
            {
                string cat = GetCategory(s.MaterialId);
                catCounts[cat] = catCounts.GetValueOrDefault(cat, 0) + 1;
            }
            features[idx++] = catCounts.GetValueOrDefault("elemental", 0);
            features[idx++] = catCounts.GetValueOrDefault("metal", 0);
            features[idx++] = catCounts.GetValueOrDefault("monster_drop", 0);
            features[idx++] = catCounts.GetValueOrDefault("stone", 0);
            features[idx++] = catCounts.GetValueOrDefault("wood", 0);

            // Refinement distribution (1 feature) [20]
            int basicCount = 0;
            foreach (var s in slots)
            {
                if (GetRefinementLevel(s.MaterialId) == "basic")
                    basicCount++;
            }
            features[idx++] = basicCount;

            // Tier statistics (3 features) [21-23]
            var tiers = new List<float>();
            foreach (var s in slots)
                tiers.Add(GetTier(s.MaterialId));

            features[idx++] = tiers.Count > 0 ? AlchemyFeatureExtractor.Mean(tiers) : 0;
            features[idx++] = tiers.Count > 0 ? AlchemyFeatureExtractor.Max(tiers) : 0;
            features[idx++] = tiers.Count > 1 ? AlchemyFeatureExtractor.PopulationStdDev(tiers) : 0;

            // Quantity by slot type (3 features) [24-26]
            int frameQty = 0, powerQty = 0, functionQty = 0;
            foreach (var s in slots)
            {
                if (s.SlotType == "FRAME") frameQty += s.Quantity;
                else if (s.SlotType == "POWER") powerQty += s.Quantity;
                else if (s.SlotType == "FUNCTION") functionQty += s.Quantity;
            }
            features[idx++] = frameQty;
            features[idx++] = powerQty;
            features[idx++] = functionQty;

            // Station tier (1 feature) [27]
            features[idx++] = stationTier;

            System.Diagnostics.Debug.Assert(idx == FeatureCount,
                $"[EngineeringFeatureExtractor] Expected {FeatureCount} features, got {idx}");

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
