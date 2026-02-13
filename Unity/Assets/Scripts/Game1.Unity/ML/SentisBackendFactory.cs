// ============================================================================
// Game1.Unity.ML.SentisBackendFactory
// Migrated from: N/A (new — implements Phase 5 IModelBackendFactory)
// Migration phase: 6 (AC-014)
// Date: 2026-02-13
//
// Factory that creates SentisModelBackend instances for each discipline.
// Injected into ClassifierManager at startup by GameManager.
// ============================================================================

using UnityEngine;
using Game1.Systems.Classifiers;

namespace Game1.Unity.ML
{
    /// <summary>
    /// Factory for creating Sentis-based model backends.
    /// Implements IModelBackendFactory from Phase 5.
    /// GameManager injects this into ClassifierManager during initialization.
    /// </summary>
    public class SentisBackendFactory : IModelBackendFactory
    {
        /// <summary>
        /// Create a Sentis model backend for the given model path and type.
        /// </summary>
        /// <param name="modelPath">Path to .onnx file (relative to StreamingAssets/Content/).</param>
        /// <param name="classifierType">"cnn" or "lightgbm".</param>
        /// <returns>A SentisModelBackend instance.</returns>
        public IModelBackend Create(string modelPath, string classifierType)
        {
            // Convert StreamingAssets path to Resources path
            // Phase 5 stores model paths relative to Content/Models/
            // Sentis loads from Resources/Models/
            string resourcePath = modelPath;

            // Strip file extension if present (Resources.Load doesn't use extensions)
            if (resourcePath.EndsWith(".onnx"))
                resourcePath = resourcePath.Substring(0, resourcePath.Length - 5);

            // Ensure Models/ prefix
            if (!resourcePath.StartsWith("Models/"))
                resourcePath = "Models/" + resourcePath;

            Debug.Log($"[SentisFactory] Creating {classifierType} backend: {resourcePath}");

            return new SentisModelBackend(resourcePath, classifierType);
        }
    }
}
