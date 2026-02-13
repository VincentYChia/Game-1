// ============================================================================
// Game1.Systems.Classifiers.ClassifierConfig
// Migrated from: systems/crafting_classifier.py (ClassifierConfig, lines 48-57)
// Migration phase: 5
// Date: 2026-02-13
// ============================================================================

namespace Game1.Systems.Classifiers
{
    /// <summary>
    /// Configuration for a single discipline classifier.
    /// Matches Python ClassifierConfig dataclass.
    /// </summary>
    public class ClassifierConfig
    {
        /// <summary>Discipline name (smithing, adornments, alchemy, refining, engineering).</summary>
        public string Discipline { get; set; }

        /// <summary>Classifier type: "cnn" or "lightgbm".</summary>
        public string ClassifierType { get; set; }

        /// <summary>Relative path to the ONNX model file from StreamingAssets.</summary>
        public string ModelPath { get; set; }

        /// <summary>Image size for CNN models (36 for smithing, 56 for adornments).</summary>
        public int ImgSize { get; set; } = 36;

        /// <summary>Classification threshold. probability >= threshold means valid.</summary>
        public float Threshold { get; set; } = 0.5f;

        /// <summary>Whether this classifier is enabled.</summary>
        public bool Enabled { get; set; } = true;

        public ClassifierConfig(string discipline, string classifierType, string modelPath,
                                int imgSize = 36, float threshold = 0.5f, bool enabled = true)
        {
            Discipline = discipline;
            ClassifierType = classifierType;
            ModelPath = modelPath;
            ImgSize = imgSize;
            Threshold = threshold;
            Enabled = enabled;
        }
    }
}
