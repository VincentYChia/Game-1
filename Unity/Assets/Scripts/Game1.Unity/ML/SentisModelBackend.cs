// ============================================================================
// Game1.Unity.ML.SentisModelBackend
// MOCK IMPLEMENTATION — Unity Sentis is not installed for the prototype.
// Returns 85% confidence (always valid) so crafting/invention UI flows work.
// Replace with real Sentis implementation when ONNX models are ready.
// ============================================================================

using System;
using UnityEngine;
using Game1.Systems.Classifiers;

namespace Game1.Unity.ML
{
    /// <summary>
    /// Mock Sentis backend — always returns valid with 85% confidence.
    /// Stands in for real ONNX inference until Unity Sentis is installed.
    /// </summary>
    public class SentisModelBackend : IModelBackend
    {
        private readonly string _classifierType;

        public bool IsLoaded => true;

        public SentisModelBackend(string modelPath, string classifierType)
        {
            _classifierType = classifierType;
            Debug.Log($"[MockSentisBackend] Mock backend created for {classifierType} (model: {modelPath})");
        }

        public (float probability, string error) Predict(float[] inputData)
        {
            // Mock: always returns valid with 85% confidence
            return (0.85f, null);
        }

        public void Dispose()
        {
            // Nothing to dispose in mock
        }
    }
}
