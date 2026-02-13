// ============================================================================
// Game1.Systems.Classifiers.Preprocessing.MaterialColorEncoder
// Migrated from: systems/crafting_classifier.py (MaterialColorEncoder, lines 64-213)
// Migration phase: 5
// Date: 2026-02-13
//
// CRITICAL: This encoding MUST match the Python training pipeline EXACTLY.
// DO NOT modify constants without retraining all CNN models.
//
// Uses pure C# HSV-to-RGB (matches Python colorsys.hsv_to_rgb).
// No UnityEngine dependency per AC-002.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;
using Game1.Data.Databases;

namespace Game1.Systems.Classifiers.Preprocessing
{
    /// <summary>
    /// Encodes materials as RGB colors using HSV color space.
    /// Shared between both CNN preprocessors (smithing and adornments).
    ///
    /// Algorithm:
    ///   1. Category -> Hue (0-360 degrees)
    ///   2. Tier -> Value/brightness (0.0-1.0)
    ///   3. Tags -> Saturation (0.0-1.0)
    ///   4. HSV -> RGB conversion
    /// </summary>
    public class MaterialColorEncoder
    {
        // ====================================================================
        // Constants — MUST MATCH crafting_classifier.py lines 73-91 EXACTLY
        // ====================================================================

        /// <summary>Category to Hue mapping (degrees, 0-360).</summary>
        private static readonly Dictionary<string, float> CategoryHues = new()
        {
            { "metal", 210f },
            { "wood", 30f },
            { "stone", 0f },
            { "monster_drop", 300f },
            { "gem", 280f },
            { "herb", 120f },
            { "fabric", 45f },
        };

        /// <summary>Elemental tag to Hue mapping (used when category == "elemental").</summary>
        private static readonly Dictionary<string, float> ElementHues = new()
        {
            { "fire", 0f }, { "water", 210f }, { "earth", 120f }, { "air", 60f },
            { "lightning", 270f }, { "ice", 180f }, { "light", 45f },
            { "dark", 280f }, { "void", 290f }, { "chaos", 330f },
        };

        /// <summary>Tier to Value (brightness) mapping.</summary>
        private static readonly Dictionary<int, float> TierValues = new()
        {
            { 1, 0.50f }, { 2, 0.65f }, { 3, 0.80f }, { 4, 0.95f },
        };

        // ====================================================================
        // Fields
        // ====================================================================

        private readonly MaterialDatabase _materialsDb;

        // ====================================================================
        // Constructor
        // ====================================================================

        public MaterialColorEncoder(MaterialDatabase materialsDb)
        {
            _materialsDb = materialsDb;
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>
        /// Convert material ID to RGB color array.
        /// Returns float[3] with R, G, B values in [0.0, 1.0].
        ///
        /// Special cases:
        ///   - null material_id -> (0, 0, 0) black
        ///   - unknown material -> (0.3, 0.3, 0.3) gray
        /// </summary>
        public float[] Encode(string materialId)
        {
            if (materialId == null)
                return new float[] { 0.0f, 0.0f, 0.0f };

            var matDef = _materialsDb?.GetMaterial(materialId);
            if (matDef == null)
                return new float[] { 0.3f, 0.3f, 0.3f };

            string category = matDef.MaterialCategory ?? "unknown";
            int tier = matDef.Tier;
            var tags = GetTags(matDef);

            // Step 1: Category -> Hue
            float hue;
            if (category == "elemental")
            {
                hue = 280f; // Default for elemental
                foreach (var tag in tags)
                {
                    if (ElementHues.TryGetValue(tag, out float elementHue))
                    {
                        hue = elementHue;
                        break;
                    }
                }
            }
            else
            {
                hue = CategoryHues.GetValueOrDefault(category, 0f);
            }

            // Step 2: Tier -> Value (brightness)
            float value = TierValues.GetValueOrDefault(tier, 0.5f);

            // Step 3: Tags -> Saturation
            float saturation = 0.6f;
            if (category == "stone")
                saturation = 0.2f;

            if (ContainsAny(tags, "legendary", "mythical"))
                saturation = MathF.Min(1.0f, saturation + 0.2f);
            else if (ContainsAny(tags, "magical", "ancient"))
                saturation = MathF.Min(1.0f, saturation + 0.1f);

            // Step 4: HSV -> RGB
            // Matches Python colorsys.hsv_to_rgb(hue/360, saturation, value)
            float hueNormalized = hue / 360.0f;
            HsvToRgb(hueNormalized, saturation, value, out float r, out float g, out float b);

            return new float[] { r, g, b };
        }

        /// <summary>
        /// Get material data needed for shape/tier lookups.
        /// Returns null if material not found.
        /// </summary>
        public MaterialDefinition GetMaterialData(string materialId)
        {
            if (materialId == null) return null;
            return _materialsDb?.GetMaterial(materialId);
        }

        // ====================================================================
        // Private helpers
        // ====================================================================

        /// <summary>
        /// Extract tags from a MaterialDefinition, checking multiple sources
        /// to match Python's get_material_data() fallback chain.
        /// </summary>
        private static List<string> GetTags(MaterialDefinition mat)
        {
            // Try Tags list first (direct JSON field)
            if (mat.Tags != null && mat.Tags.Count > 0)
                return mat.Tags;

            // Try Properties dict for "tags" key
            if (mat.Properties != null && mat.Properties.TryGetValue("tags", out var tagsObj))
            {
                if (tagsObj is Newtonsoft.Json.Linq.JArray jArray)
                {
                    var result = new List<string>();
                    foreach (var item in jArray)
                        result.Add(item.ToString());
                    return result;
                }
            }

            // Try EffectTags
            if (mat.EffectTags != null && mat.EffectTags.Count > 0)
                return mat.EffectTags;

            return new List<string>();
        }

        /// <summary>Check if any of the specified values exist in the list.</summary>
        private static bool ContainsAny(List<string> list, params string[] values)
        {
            foreach (var val in values)
            {
                if (list.Contains(val))
                    return true;
            }
            return false;
        }

        /// <summary>
        /// Convert HSV to RGB. Matches Python's colorsys.hsv_to_rgb exactly.
        ///
        /// Python colorsys.hsv_to_rgb implementation:
        ///   if s == 0.0: return v, v, v
        ///   i = int(h * 6.0)
        ///   f = (h * 6.0) - i
        ///   p = v * (1.0 - s)
        ///   q = v * (1.0 - s * f)
        ///   t = v * (1.0 - s * (1.0 - f))
        ///   i = i % 6
        ///   switch on i: 0->(v,t,p), 1->(q,v,p), 2->(p,v,t),
        ///                3->(p,q,v), 4->(t,p,v), 5->(v,p,q)
        /// </summary>
        public static void HsvToRgb(float h, float s, float v,
                                     out float r, out float g, out float b)
        {
            if (s == 0.0f)
            {
                r = v;
                g = v;
                b = v;
                return;
            }

            int i = (int)(h * 6.0f);
            float f = (h * 6.0f) - i;
            float p = v * (1.0f - s);
            float q = v * (1.0f - s * f);
            float t = v * (1.0f - s * (1.0f - f));
            i = i % 6;

            switch (i)
            {
                case 0: r = v; g = t; b = p; break;
                case 1: r = q; g = v; b = p; break;
                case 2: r = p; g = v; b = t; break;
                case 3: r = p; g = q; b = v; break;
                case 4: r = t; g = p; b = v; break;
                case 5: r = v; g = p; b = q; break;
                default: r = 0; g = 0; b = 0; break;
            }
        }
    }
}
