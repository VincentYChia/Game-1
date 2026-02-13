// ============================================================================
// Game1.Systems.Classifiers.ClassifierManager
// Migrated from: systems/crafting_classifier.py (CraftingClassifierManager, lines 1019-1419)
// Migration phase: 5
// Date: 2026-02-13
//
// Orchestrator singleton for all 5 discipline classifiers.
// Pure C# per AC-002 — no UnityEngine dependency.
//
// ONNX inference is abstracted behind IModelBackend interface.
// Phase 6 provides the Sentis implementation; this phase provides
// the preprocessing pipeline and orchestration logic.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Diagnostics;
using Game1.Data.Databases;
using Game1.Systems.Classifiers.Preprocessing;

namespace Game1.Systems.Classifiers
{
    // ========================================================================
    // Model backend abstraction (Phase 6 provides Sentis implementation)
    // ========================================================================

    /// <summary>
    /// Abstract interface for classifier model backends.
    /// Phase 6 implements this with Unity Sentis Workers.
    /// Testing can provide mock implementations.
    /// </summary>
    public interface IModelBackend : IDisposable
    {
        /// <summary>
        /// Run inference on input data.
        /// Returns (probability, error_or_null).
        /// CNN: inputData is float[H*W*3] row-major channel-last.
        /// LightGBM: inputData is float[numFeatures].
        /// </summary>
        (float probability, string error) Predict(float[] inputData);

        /// <summary>Whether the model is loaded and ready for inference.</summary>
        bool IsLoaded { get; }
    }

    /// <summary>
    /// Factory interface for creating model backends.
    /// Allows Phase 6 to inject Sentis-based implementations.
    /// </summary>
    public interface IModelBackendFactory
    {
        /// <summary>
        /// Create a backend for the given model path and type.
        /// modelPath: path to .onnx file.
        /// classifierType: "cnn" or "lightgbm".
        /// </summary>
        IModelBackend Create(string modelPath, string classifierType);
    }

    // ========================================================================
    // ClassifierManager
    // ========================================================================

    /// <summary>
    /// Main entry point for recipe validation using ML classifiers.
    ///
    /// Manages all 5 discipline classifiers with:
    /// - Lazy loading (models loaded on first use)
    /// - Graceful fallbacks (returns error result if model unavailable)
    /// - Pure C# preprocessing pipeline
    /// - Abstracted model inference via IModelBackend
    ///
    /// Singleton pattern per CONVENTIONS.md section 3.
    /// </summary>
    public class ClassifierManager
    {
        // ====================================================================
        // Singleton
        // ====================================================================

        private static ClassifierManager _instance;
        private static readonly object _lock = new object();

        public static ClassifierManager Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                            _instance = new ClassifierManager();
                    }
                }
                return _instance;
            }
        }

        private ClassifierManager() { }

        /// <summary>Reset singleton for testing only.</summary>
        public static void ResetInstance()
        {
            lock (_lock)
            {
                _instance?.DisposeAll();
                _instance = null;
            }
        }

        // ====================================================================
        // Default configurations
        // ====================================================================

        /// <summary>
        /// Default model configurations matching Python DEFAULT_CONFIGS (lines 1031-1067).
        /// Model paths are relative to StreamingAssets/Content/Models/.
        /// </summary>
        private static readonly Dictionary<string, ClassifierConfig> DefaultConfigs = new()
        {
            {
                "smithing", new ClassifierConfig(
                    discipline: "smithing",
                    classifierType: "cnn",
                    modelPath: "Models/smithing.onnx",
                    imgSize: 36,
                    threshold: 0.5f)
            },
            {
                "adornments", new ClassifierConfig(
                    discipline: "adornments",
                    classifierType: "cnn",
                    modelPath: "Models/adornments.onnx",
                    imgSize: 56,
                    threshold: 0.5f)
            },
            {
                "alchemy", new ClassifierConfig(
                    discipline: "alchemy",
                    classifierType: "lightgbm",
                    modelPath: "Models/alchemy.onnx",
                    threshold: 0.5f)
            },
            {
                "refining", new ClassifierConfig(
                    discipline: "refining",
                    classifierType: "lightgbm",
                    modelPath: "Models/refining.onnx",
                    threshold: 0.5f)
            },
            {
                "engineering", new ClassifierConfig(
                    discipline: "engineering",
                    classifierType: "lightgbm",
                    modelPath: "Models/engineering.onnx",
                    threshold: 0.5f)
            },
        };

        // ====================================================================
        // State
        // ====================================================================

        private Dictionary<string, ClassifierConfig> _configs;
        private IModelBackendFactory _backendFactory;
        private readonly Dictionary<string, IModelBackend> _backends = new();

        // Preprocessors (lazy initialized)
        private MaterialColorEncoder _colorEncoder;
        private SmithingPreprocessor _smithingPreprocessor;
        private AdornmentPreprocessor _adornmentPreprocessor;
        private AlchemyFeatureExtractor _alchemyExtractor;
        private RefiningFeatureExtractor _refiningExtractor;
        private EngineeringFeatureExtractor _engineeringExtractor;

        public bool Initialized { get; private set; }

        // ====================================================================
        // Initialization
        // ====================================================================

        /// <summary>
        /// Initialize the classifier manager with dependencies.
        /// Must be called before Validate().
        ///
        /// backendFactory: creates model backends (Phase 6 provides Sentis impl).
        ///                 Pass null to run without inference (preprocessing only).
        /// configs: optional custom configs, defaults used if null.
        /// </summary>
        public void Initialize(IModelBackendFactory backendFactory = null,
                               Dictionary<string, ClassifierConfig> configs = null)
        {
            _backendFactory = backendFactory;
            _configs = configs ?? new Dictionary<string, ClassifierConfig>(DefaultConfigs);

            var materialsDb = MaterialDatabase.Instance;

            // Initialize preprocessors
            _colorEncoder = new MaterialColorEncoder(materialsDb);
            _smithingPreprocessor = new SmithingPreprocessor(_colorEncoder);
            _adornmentPreprocessor = new AdornmentPreprocessor(_colorEncoder);
            _alchemyExtractor = new AlchemyFeatureExtractor(materialsDb);
            _refiningExtractor = new RefiningFeatureExtractor(materialsDb);
            _engineeringExtractor = new EngineeringFeatureExtractor(materialsDb);

            Initialized = true;

            System.Diagnostics.Debug.WriteLine(
                $"[ClassifierManager] Initialized with {_configs.Count} disciplines" +
                $", backend factory: {(_backendFactory != null ? "provided" : "null")}");
        }

        // ====================================================================
        // Validation — main entry point
        // ====================================================================

        /// <summary>
        /// Validate a smithing recipe from grid state.
        /// </summary>
        public ClassifierResult ValidateSmithing(
            Dictionary<(int col, int row), string> grid, int stationGridSize)
        {
            if (!Initialized)
                return ClassifierResult.CreateError("smithing", "ClassifierManager not initialized");

            float[] input = _smithingPreprocessor.Preprocess(grid, stationGridSize);
            return RunInference("smithing", input);
        }

        /// <summary>
        /// Validate an adornment (enchanting) recipe from vertex/shape state.
        /// </summary>
        public ClassifierResult ValidateAdornments(
            Dictionary<string, string> vertices,
            List<AdornmentPreprocessor.ShapeData> shapes)
        {
            if (!Initialized)
                return ClassifierResult.CreateError("adornments", "ClassifierManager not initialized");

            float[] input = _adornmentPreprocessor.Preprocess(vertices, shapes);
            return RunInference("adornments", input);
        }

        /// <summary>
        /// Validate an alchemy recipe from slot data.
        /// </summary>
        public ClassifierResult ValidateAlchemy(
            List<(string materialId, int quantity)?> slots, int stationTier)
        {
            if (!Initialized)
                return ClassifierResult.CreateError("alchemy", "ClassifierManager not initialized");

            float[] input = _alchemyExtractor.Extract(slots, stationTier);
            return RunInference("alchemy", input);
        }

        /// <summary>
        /// Validate a refining recipe from core/spoke slot data.
        /// </summary>
        public ClassifierResult ValidateRefining(
            List<(string materialId, int quantity)?> coreSlots,
            List<(string materialId, int quantity)?> surroundingSlots,
            int stationTier)
        {
            if (!Initialized)
                return ClassifierResult.CreateError("refining", "ClassifierManager not initialized");

            float[] input = _refiningExtractor.Extract(coreSlots, surroundingSlots, stationTier);
            return RunInference("refining", input);
        }

        /// <summary>
        /// Validate an engineering recipe from typed slot data.
        /// </summary>
        public ClassifierResult ValidateEngineering(
            Dictionary<string, List<(string materialId, int quantity)>> slots,
            int stationTier)
        {
            if (!Initialized)
                return ClassifierResult.CreateError("engineering", "ClassifierManager not initialized");

            float[] input = _engineeringExtractor.Extract(slots, stationTier);
            return RunInference("engineering", input);
        }

        /// <summary>
        /// Generic validation by discipline name (matches Python's validate() signature).
        /// Requires preprocessed input data.
        /// </summary>
        public ClassifierResult Validate(string discipline, float[] preprocessedInput)
        {
            if (!Initialized)
                return ClassifierResult.CreateError(discipline, "ClassifierManager not initialized");

            return RunInference(discipline, preprocessedInput);
        }

        // ====================================================================
        // Preprocessing — exposed for testing and golden file generation
        // ====================================================================

        /// <summary>Get the color encoder for direct access (testing).</summary>
        public MaterialColorEncoder ColorEncoder => _colorEncoder;

        /// <summary>Get the smithing preprocessor for direct access (testing).</summary>
        public SmithingPreprocessor SmithingPreprocessor => _smithingPreprocessor;

        /// <summary>Get the adornment preprocessor for direct access (testing).</summary>
        public AdornmentPreprocessor AdornmentPreprocessor => _adornmentPreprocessor;

        /// <summary>Get the alchemy extractor for direct access (testing).</summary>
        public AlchemyFeatureExtractor AlchemyExtractor => _alchemyExtractor;

        /// <summary>Get the refining extractor for direct access (testing).</summary>
        public RefiningFeatureExtractor RefiningExtractor => _refiningExtractor;

        /// <summary>Get the engineering extractor for direct access (testing).</summary>
        public EngineeringFeatureExtractor EngineeringExtractor => _engineeringExtractor;

        // ====================================================================
        // Model lifecycle
        // ====================================================================

        /// <summary>
        /// Preload models to avoid delay on first validation.
        /// Call when crafting UI opens.
        /// </summary>
        public void Preload(string discipline = null)
        {
            if (_backendFactory == null) return;

            var disciplines = discipline != null
                ? new List<string> { discipline }
                : new List<string>(_configs.Keys);

            foreach (var disc in disciplines)
            {
                if (!_configs.TryGetValue(disc, out var config) || !config.Enabled)
                    continue;

                try
                {
                    var backend = GetOrCreateBackend(disc);
                    if (backend == null) continue;

                    // For CNN models, run warmup prediction
                    if (config.ClassifierType == "cnn" && backend.IsLoaded)
                    {
                        int size = config.ImgSize;
                        float[] dummy = new float[size * size * 3];
                        backend.Predict(dummy); // Warmup — result discarded
                        System.Diagnostics.Debug.WriteLine(
                            $"[ClassifierManager] Warmup complete for {disc}");
                    }
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine(
                        $"[ClassifierManager] Preload failed for {disc}: {ex.Message}");
                }
            }
        }

        /// <summary>
        /// Unload models to free memory.
        /// Call when crafting UI closes.
        /// </summary>
        public void Unload(string discipline = null)
        {
            if (discipline != null)
            {
                if (_backends.TryGetValue(discipline, out var backend))
                {
                    backend.Dispose();
                    _backends.Remove(discipline);
                }
            }
            else
            {
                DisposeAll();
            }
        }

        /// <summary>
        /// Get status of all classifiers.
        /// </summary>
        public Dictionary<string, Dictionary<string, object>> GetStatus()
        {
            var status = new Dictionary<string, Dictionary<string, object>>();

            foreach (var kvp in _configs)
            {
                var config = kvp.Value;
                _backends.TryGetValue(kvp.Key, out var backend);

                status[kvp.Key] = new Dictionary<string, object>
                {
                    ["enabled"] = config.Enabled,
                    ["type"] = config.ClassifierType,
                    ["model_path"] = config.ModelPath,
                    ["loaded"] = backend?.IsLoaded ?? false,
                    ["threshold"] = config.Threshold,
                };
            }

            return status;
        }

        /// <summary>
        /// Update configuration for a discipline.
        /// </summary>
        public void UpdateConfig(string discipline, float? threshold = null, bool? enabled = null,
                                 string modelPath = null)
        {
            if (!_configs.TryGetValue(discipline, out var config))
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[ClassifierManager] Unknown discipline: {discipline}");
                return;
            }

            if (threshold.HasValue) config.Threshold = threshold.Value;
            if (enabled.HasValue) config.Enabled = enabled.Value;

            if (modelPath != null)
            {
                config.ModelPath = modelPath;
                // Clear cached backend since model path changed
                if (_backends.TryGetValue(discipline, out var backend))
                {
                    backend.Dispose();
                    _backends.Remove(discipline);
                }
            }
        }

        // ====================================================================
        // Private implementation
        // ====================================================================

        /// <summary>
        /// Run inference on preprocessed input data.
        /// </summary>
        private ClassifierResult RunInference(string discipline, float[] inputData)
        {
            if (!_configs.TryGetValue(discipline, out var config))
                return ClassifierResult.CreateError(discipline,
                    $"No classifier configured for discipline: {discipline}");

            if (!config.Enabled)
                return ClassifierResult.CreateError(discipline,
                    $"Classifier disabled for discipline: {discipline}");

            // Get or create backend
            var backend = GetOrCreateBackend(discipline);
            if (backend == null)
                return ClassifierResult.CreateError(discipline,
                    $"No backend available for discipline: {discipline}" +
                    (_backendFactory == null ? " (no backend factory configured)" : ""));

            // Run prediction
            var (prob, error) = backend.Predict(inputData);

            if (error != null)
                return ClassifierResult.CreateError(discipline, error);

            // Interpret result — matches Python lines 1230-1240
            bool isValid = prob >= config.Threshold;
            float confidence = isValid ? prob : (1.0f - prob);

            return new ClassifierResult(isValid, confidence, prob, discipline);
        }

        /// <summary>Get or create a model backend for a discipline.</summary>
        private IModelBackend GetOrCreateBackend(string discipline)
        {
            if (_backends.TryGetValue(discipline, out var existing))
                return existing;

            if (_backendFactory == null || !_configs.TryGetValue(discipline, out var config))
                return null;

            try
            {
                var backend = _backendFactory.Create(config.ModelPath, config.ClassifierType);
                if (backend != null)
                    _backends[discipline] = backend;
                return backend;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[ClassifierManager] Failed to create backend for {discipline}: {ex.Message}");
                return null;
            }
        }

        /// <summary>Dispose all backends.</summary>
        private void DisposeAll()
        {
            foreach (var backend in _backends.Values)
            {
                try { backend.Dispose(); }
                catch { /* ignore disposal errors */ }
            }
            _backends.Clear();
        }
    }
}
