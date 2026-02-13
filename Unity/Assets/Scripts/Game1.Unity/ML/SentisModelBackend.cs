// ============================================================================
// Game1.Unity.ML.SentisModelBackend
// Migrated from: N/A (new — implements Phase 5 IModelBackend via Unity Sentis)
// Migration phase: 6 (AC-014, AC-016)
// Date: 2026-02-13
//
// Provides Sentis-based ONNX model inference for Phase 5 classifiers.
// AC-016: Flat float arrays from preprocessors feed directly to Sentis tensors.
// ============================================================================

using System;
using UnityEngine;
using Unity.Sentis;
using Game1.Systems.Classifiers;

namespace Game1.Unity.ML
{
    /// <summary>
    /// Sentis-based implementation of IModelBackend.
    /// Loads ONNX models via Unity Sentis and runs inference.
    /// CNN models expect flat float[H*W*3] arrays (row-major, channel-last).
    /// LightGBM models expect flat float[numFeatures] arrays.
    /// </summary>
    public class SentisModelBackend : IModelBackend
    {
        private Model _model;
        private Worker _worker;
        private readonly string _classifierType; // "cnn" or "lightgbm"
        private readonly int[] _inputShape;

        /// <summary>Whether the model is loaded and ready for inference.</summary>
        public bool IsLoaded => _worker != null;

        /// <summary>
        /// Create a Sentis backend for a model.
        /// </summary>
        /// <param name="modelPath">Path to ONNX model (Resources-relative without extension).</param>
        /// <param name="classifierType">"cnn" or "lightgbm".</param>
        public SentisModelBackend(string modelPath, string classifierType)
        {
            _classifierType = classifierType;

            try
            {
                // Load the model asset from Resources
                var modelAsset = Resources.Load<ModelAsset>(modelPath);
                if (modelAsset == null)
                {
                    Debug.LogWarning($"[SentisBackend] Model not found at Resources/{modelPath}");
                    return;
                }

                _model = ModelLoader.Load(modelAsset);

                // Use CPU backend for compatibility (GPU can be used if available)
                _worker = new Worker(_model, BackendType.CPU);

                // Determine input shape from model metadata
                if (_model.inputs.Count > 0)
                {
                    var inputInfo = _model.inputs[0];
                    _inputShape = new int[inputInfo.shape.rank];
                    for (int i = 0; i < inputInfo.shape.rank; i++)
                    {
                        _inputShape[i] = inputInfo.shape[i].isValue ? inputInfo.shape[i].value : 1;
                    }
                }

                Debug.Log($"[SentisBackend] Loaded {classifierType} model: {modelPath}");
            }
            catch (Exception ex)
            {
                Debug.LogError($"[SentisBackend] Failed to load model {modelPath}: {ex.Message}");
            }
        }

        /// <summary>
        /// Run inference on flat input data.
        /// Returns (probability of valid, error message or null).
        /// </summary>
        public (float probability, string error) Predict(float[] inputData)
        {
            if (_worker == null)
                return (0f, "Model not loaded");

            try
            {
                // Create input tensor based on classifier type
                Tensor<float> inputTensor;

                if (_classifierType == "cnn")
                {
                    // CNN expects [batch, height, width, channels] — NHWC format
                    // Input data is flat float[H*W*3]
                    int totalPixels = inputData.Length / 3;
                    int side = (int)Mathf.Sqrt(totalPixels);

                    inputTensor = new Tensor<float>(new TensorShape(1, side, side, 3));
                    for (int i = 0; i < inputData.Length; i++)
                    {
                        inputTensor[i] = inputData[i];
                    }
                }
                else
                {
                    // LightGBM expects [batch, features]
                    inputTensor = new Tensor<float>(new TensorShape(1, inputData.Length));
                    for (int i = 0; i < inputData.Length; i++)
                    {
                        inputTensor[i] = inputData[i];
                    }
                }

                // Run inference
                _worker.Schedule(inputTensor);

                // Read output
                var outputTensor = _worker.PeekOutput() as Tensor<float>;
                var cpuTensor = outputTensor.ReadbackAndClone();

                // Output format: [batch, 2] with [invalid_prob, valid_prob]
                float probability = cpuTensor.shape.length > 1 ? cpuTensor[0, 1] : cpuTensor[0];

                // Cleanup
                inputTensor.Dispose();
                cpuTensor.Dispose();

                return (probability, null);
            }
            catch (Exception ex)
            {
                return (0f, $"Inference failed: {ex.Message}");
            }
        }

        /// <summary>Dispose the Sentis worker and model resources.</summary>
        public void Dispose()
        {
            _worker?.Dispose();
            _worker = null;
            _model = null;
        }
    }
}
