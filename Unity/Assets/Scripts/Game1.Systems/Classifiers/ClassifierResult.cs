// ============================================================================
// Game1.Systems.Classifiers.ClassifierResult
// Migrated from: systems/crafting_classifier.py (ClassifierResult, lines 34-46)
// Migration phase: 5
// Date: 2026-02-13
// ============================================================================

namespace Game1.Systems.Classifiers
{
    /// <summary>
    /// Immutable result from a classifier prediction.
    /// Matches Python ClassifierResult dataclass exactly.
    /// </summary>
    public struct ClassifierResult
    {
        /// <summary>Whether the recipe is classified as valid.</summary>
        public bool Valid { get; }

        /// <summary>
        /// Confidence in the classification decision (always >= 0.5 when threshold is 0.5).
        /// = Probability if valid, (1 - Probability) if invalid.
        /// </summary>
        public float Confidence { get; }

        /// <summary>Raw model output probability in [0, 1].</summary>
        public float Probability { get; }

        /// <summary>Discipline name (smithing, adornments, alchemy, refining, engineering).</summary>
        public string Discipline { get; }

        /// <summary>Error message if prediction failed, null otherwise.</summary>
        public string Error { get; }

        /// <summary>True if an error occurred during prediction.</summary>
        public bool IsError => Error != null;

        public ClassifierResult(bool valid, float confidence, float probability,
                                string discipline, string error = null)
        {
            Valid = valid;
            Confidence = confidence;
            Probability = probability;
            Discipline = discipline;
            Error = error;
        }

        /// <summary>Create an error result for a discipline.</summary>
        public static ClassifierResult CreateError(string discipline, string error)
            => new ClassifierResult(false, 0f, 0f, discipline, error);
    }
}
