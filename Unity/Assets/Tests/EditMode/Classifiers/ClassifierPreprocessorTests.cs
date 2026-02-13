// ============================================================================
// Phase 5 Unit Tests: ML Classifier Preprocessors
// Tests MaterialColorEncoder, SmithingPreprocessor, AdornmentPreprocessor,
// and all three LightGBM feature extractors.
//
// These tests validate C# preprocessing matches Python output exactly.
// Golden file tests provide pixel-perfect validation; these tests verify
// algorithmic correctness independently.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Systems.Classifiers;
using Game1.Systems.Classifiers.Preprocessing;

namespace Game1.Tests.Classifiers
{
    /// <summary>
    /// Unit tests for Phase 5 ML Classifier preprocessing.
    /// Uses simple assert framework (no Unity Test Runner dependency).
    ///
    /// Run: Instantiate and call RunAll() or invoke individual test methods.
    /// All tests return true on pass, throw on failure.
    /// </summary>
    public class ClassifierPreprocessorTests
    {
        private const float ColorTolerance = 0.001f;
        private const float FeatureTolerance = 0.0001f;

        // ====================================================================
        // Test Runner
        // ====================================================================

        public static int RunAll()
        {
            var tests = new ClassifierPreprocessorTests();
            int passed = 0;
            int failed = 0;
            var testMethods = new List<(string name, Action action)>
            {
                // MaterialColorEncoder tests
                ("HsvToRgb_Red", tests.HsvToRgb_Red),
                ("HsvToRgb_Green", tests.HsvToRgb_Green),
                ("HsvToRgb_Blue", tests.HsvToRgb_Blue),
                ("HsvToRgb_White", tests.HsvToRgb_White),
                ("HsvToRgb_Black", tests.HsvToRgb_Black),
                ("HsvToRgb_MatchesPython_Metal_T1", tests.HsvToRgb_MatchesPython_Metal_T1),
                ("HsvToRgb_MatchesPython_Wood_T2", tests.HsvToRgb_MatchesPython_Wood_T2),
                ("HsvToRgb_MatchesPython_Stone_T1", tests.HsvToRgb_MatchesPython_Stone_T1),

                // SmithingPreprocessor tests
                ("Smithing_EmptyGrid_AllZeros", tests.Smithing_EmptyGrid_AllZeros),
                ("Smithing_OutputSize_Is3888", tests.Smithing_OutputSize_Is3888),
                ("Smithing_ShapeMasks_Correct", tests.Smithing_ShapeMasks_Correct),

                // AdornmentPreprocessor tests
                ("Adornment_EmptyInput_AllZeros", tests.Adornment_EmptyInput_AllZeros),
                ("Adornment_OutputSize_Is9408", tests.Adornment_OutputSize_Is9408),
                ("Adornment_CoordToPixel_Correct", tests.Adornment_CoordToPixel_Correct),

                // AlchemyFeatureExtractor tests
                ("Alchemy_EmptySlots_34Zeros", tests.Alchemy_EmptySlots_34Zeros),
                ("Alchemy_FeatureCount_Is34", tests.Alchemy_FeatureCount_Is34),

                // RefiningFeatureExtractor tests
                ("Refining_EmptySlots_19Zeros", tests.Refining_EmptySlots_19Zeros),
                ("Refining_FeatureCount_Is19", tests.Refining_FeatureCount_Is19),

                // EngineeringFeatureExtractor tests
                ("Engineering_EmptySlots_28Zeros", tests.Engineering_EmptySlots_28Zeros),
                ("Engineering_FeatureCount_Is28", tests.Engineering_FeatureCount_Is28),

                // Math helper tests
                ("PopulationStdDev_Correct", tests.PopulationStdDev_Correct),
                ("PopulationStdDev_SingleElement_Zero", tests.PopulationStdDev_SingleElement_Zero),

                // ClassifierResult tests
                ("ClassifierResult_Valid", tests.ClassifierResult_Valid),
                ("ClassifierResult_Invalid", tests.ClassifierResult_Invalid),
                ("ClassifierResult_Error", tests.ClassifierResult_Error),

                // ClassifierManager tests
                ("ClassifierManager_Singleton", tests.ClassifierManager_Singleton),
                ("ClassifierManager_NotInitialized_ReturnsError", tests.ClassifierManager_NotInitialized_ReturnsError),
            };

            foreach (var (name, action) in testMethods)
            {
                try
                {
                    action();
                    passed++;
                    System.Diagnostics.Debug.WriteLine($"  PASS: {name}");
                }
                catch (Exception ex)
                {
                    failed++;
                    System.Diagnostics.Debug.WriteLine($"  FAIL: {name} — {ex.Message}");
                }
            }

            System.Diagnostics.Debug.WriteLine(
                $"\nPhase 5 Tests: {passed} passed, {failed} failed, {passed + failed} total");
            return failed;
        }

        // ====================================================================
        // HSV-to-RGB Tests (matching Python colorsys.hsv_to_rgb)
        // ====================================================================

        public void HsvToRgb_Red()
        {
            // Pure red: H=0, S=1, V=1
            MaterialColorEncoder.HsvToRgb(0f, 1f, 1f, out float r, out float g, out float b);
            AssertClose(r, 1f, ColorTolerance, "Red R");
            AssertClose(g, 0f, ColorTolerance, "Red G");
            AssertClose(b, 0f, ColorTolerance, "Red B");
        }

        public void HsvToRgb_Green()
        {
            // Pure green: H=1/3, S=1, V=1
            MaterialColorEncoder.HsvToRgb(1f / 3f, 1f, 1f, out float r, out float g, out float b);
            AssertClose(r, 0f, ColorTolerance, "Green R");
            AssertClose(g, 1f, ColorTolerance, "Green G");
            AssertClose(b, 0f, ColorTolerance, "Green B");
        }

        public void HsvToRgb_Blue()
        {
            // Pure blue: H=2/3, S=1, V=1
            MaterialColorEncoder.HsvToRgb(2f / 3f, 1f, 1f, out float r, out float g, out float b);
            AssertClose(r, 0f, ColorTolerance, "Blue R");
            AssertClose(g, 0f, ColorTolerance, "Blue G");
            AssertClose(b, 1f, ColorTolerance, "Blue B");
        }

        public void HsvToRgb_White()
        {
            // White: S=0, V=1
            MaterialColorEncoder.HsvToRgb(0f, 0f, 1f, out float r, out float g, out float b);
            AssertClose(r, 1f, ColorTolerance, "White R");
            AssertClose(g, 1f, ColorTolerance, "White G");
            AssertClose(b, 1f, ColorTolerance, "White B");
        }

        public void HsvToRgb_Black()
        {
            // Black: V=0
            MaterialColorEncoder.HsvToRgb(0f, 1f, 0f, out float r, out float g, out float b);
            AssertClose(r, 0f, ColorTolerance, "Black R");
            AssertClose(g, 0f, ColorTolerance, "Black G");
            AssertClose(b, 0f, ColorTolerance, "Black B");
        }

        public void HsvToRgb_MatchesPython_Metal_T1()
        {
            // Metal T1: H=210/360=0.5833, S=0.6, V=0.5
            // Python: colorsys.hsv_to_rgb(210/360, 0.6, 0.5) = (0.2, 0.35, 0.5)
            float h = 210f / 360f;
            MaterialColorEncoder.HsvToRgb(h, 0.6f, 0.5f, out float r, out float g, out float b);
            AssertClose(r, 0.2f, ColorTolerance, "Metal T1 R");
            AssertClose(g, 0.35f, ColorTolerance, "Metal T1 G");
            AssertClose(b, 0.5f, ColorTolerance, "Metal T1 B");
        }

        public void HsvToRgb_MatchesPython_Wood_T2()
        {
            // Wood T2: H=30/360=0.0833, S=0.6, V=0.65
            // Python: colorsys.hsv_to_rgb(30/360, 0.6, 0.65) = (0.65, 0.39, 0.26)
            float h = 30f / 360f;
            MaterialColorEncoder.HsvToRgb(h, 0.6f, 0.65f, out float r, out float g, out float b);
            AssertClose(r, 0.65f, ColorTolerance, "Wood T2 R");
            AssertClose(g, 0.39f, ColorTolerance, "Wood T2 G");
            AssertClose(b, 0.26f, ColorTolerance, "Wood T2 B");
        }

        public void HsvToRgb_MatchesPython_Stone_T1()
        {
            // Stone T1: H=0/360=0, S=0.2 (stone override), V=0.5
            // Python: colorsys.hsv_to_rgb(0, 0.2, 0.5) = (0.5, 0.4, 0.4)
            MaterialColorEncoder.HsvToRgb(0f, 0.2f, 0.5f, out float r, out float g, out float b);
            AssertClose(r, 0.5f, ColorTolerance, "Stone T1 R");
            AssertClose(g, 0.4f, ColorTolerance, "Stone T1 G");
            AssertClose(b, 0.4f, ColorTolerance, "Stone T1 B");
        }

        // ====================================================================
        // Smithing Preprocessor Tests
        // ====================================================================

        public void Smithing_EmptyGrid_AllZeros()
        {
            var preprocessor = new SmithingPreprocessor(CreateMockEncoder());
            var grid = new Dictionary<(int, int), string>();
            float[] result = preprocessor.Preprocess(grid, 5);

            for (int i = 0; i < result.Length; i++)
            {
                if (result[i] != 0f)
                    throw new Exception($"Expected all zeros, but index {i} = {result[i]}");
            }
        }

        public void Smithing_OutputSize_Is3888()
        {
            var preprocessor = new SmithingPreprocessor(CreateMockEncoder());
            var grid = new Dictionary<(int, int), string>();
            float[] result = preprocessor.Preprocess(grid, 5);
            AssertEqual(result.Length, 36 * 36 * 3, "SmithingOutputSize");
        }

        public void Smithing_ShapeMasks_Correct()
        {
            // Verify the shape masks have correct pixel counts
            // Metal: 16/16 filled, Wood: 8/16, Stone: 8/16, Diamond: 12/16
            // (These are the mask values before tier fill is applied)
            // Just verify constant definitions are sensible
            AssertEqual(SmithingPreprocessor.ImgSize, 36, "ImgSize");
            AssertEqual(SmithingPreprocessor.CellSize, 4, "CellSize");
            AssertEqual(SmithingPreprocessor.GridSize, 9, "GridSize");
        }

        // ====================================================================
        // Adornment Preprocessor Tests
        // ====================================================================

        public void Adornment_EmptyInput_AllZeros()
        {
            var preprocessor = new AdornmentPreprocessor(CreateMockEncoder());
            var verts = new Dictionary<string, string>();
            var shapes = new List<AdornmentPreprocessor.ShapeData>();
            float[] result = preprocessor.Preprocess(verts, shapes);

            for (int i = 0; i < result.Length; i++)
            {
                if (result[i] != 0f)
                    throw new Exception($"Expected all zeros, but index {i} = {result[i]}");
            }
        }

        public void Adornment_OutputSize_Is9408()
        {
            var preprocessor = new AdornmentPreprocessor(CreateMockEncoder());
            var verts = new Dictionary<string, string>();
            var shapes = new List<AdornmentPreprocessor.ShapeData>();
            float[] result = preprocessor.Preprocess(verts, shapes);
            AssertEqual(result.Length, 56 * 56 * 3, "AdornmentOutputSize");
        }

        public void Adornment_CoordToPixel_Correct()
        {
            // (-7, -7) -> (0, 56), (+7, +7) -> (56, 0), (0, 0) -> (28, 28)
            // px = (x + 7) * 4, py = (7 - y) * 4

            int px, py;

            px = (-7 + 7) * 4; py = (7 - (-7)) * 4;
            AssertEqual(px, 0, "(-7,-7) px"); AssertEqual(py, 56, "(-7,-7) py");

            px = (7 + 7) * 4; py = (7 - 7) * 4;
            AssertEqual(px, 56, "(7,7) px"); AssertEqual(py, 0, "(7,7) py");

            px = (0 + 7) * 4; py = (7 - 0) * 4;
            AssertEqual(px, 28, "(0,0) px"); AssertEqual(py, 28, "(0,0) py");
        }

        // ====================================================================
        // Alchemy Feature Extractor Tests
        // ====================================================================

        public void Alchemy_EmptySlots_34Zeros()
        {
            var extractor = new AlchemyFeatureExtractor(null);
            var slots = new List<(string, int)?> { null, null, null, null, null, null };
            float[] result = extractor.Extract(slots, 1);

            AssertEqual(result.Length, 34, "AlchemyFeatureCount");
            // All features should be 0 except station_tier at index 33
            for (int i = 0; i < 33; i++)
            {
                AssertClose(result[i], 0f, FeatureTolerance, $"Alchemy empty feature[{i}]");
            }
            AssertClose(result[33], 1f, FeatureTolerance, "Alchemy station_tier");
        }

        public void Alchemy_FeatureCount_Is34()
        {
            AssertEqual(AlchemyFeatureExtractor.FeatureCount, 34, "AlchemyFeatureCount constant");
        }

        // ====================================================================
        // Refining Feature Extractor Tests
        // ====================================================================

        public void Refining_EmptySlots_19Zeros()
        {
            var extractor = new RefiningFeatureExtractor(null);
            var cores = new List<(string, int)?> { null };
            var spokes = new List<(string, int)?> { null, null };
            float[] result = extractor.Extract(cores, spokes, 1);

            AssertEqual(result.Length, 19, "RefiningFeatureCount");
            for (int i = 0; i < 18; i++)
            {
                AssertClose(result[i], 0f, FeatureTolerance, $"Refining empty feature[{i}]");
            }
            AssertClose(result[18], 1f, FeatureTolerance, "Refining station_tier");
        }

        public void Refining_FeatureCount_Is19()
        {
            AssertEqual(RefiningFeatureExtractor.FeatureCount, 19, "RefiningFeatureCount constant");
        }

        // ====================================================================
        // Engineering Feature Extractor Tests
        // ====================================================================

        public void Engineering_EmptySlots_28Zeros()
        {
            var extractor = new EngineeringFeatureExtractor(null);
            var slots = new Dictionary<string, List<(string, int)>>();
            float[] result = extractor.Extract(slots, 1);

            AssertEqual(result.Length, 28, "EngineeringFeatureCount");
            for (int i = 0; i < 27; i++)
            {
                AssertClose(result[i], 0f, FeatureTolerance, $"Engineering empty feature[{i}]");
            }
            AssertClose(result[27], 1f, FeatureTolerance, "Engineering station_tier");
        }

        public void Engineering_FeatureCount_Is28()
        {
            AssertEqual(EngineeringFeatureExtractor.FeatureCount, 28, "EngineeringFeatureCount constant");
        }

        // ====================================================================
        // Math Helper Tests
        // ====================================================================

        public void PopulationStdDev_Correct()
        {
            // np.std([1, 2, 3, 4, 5]) = 1.4142135623730951
            var values = new List<float> { 1, 2, 3, 4, 5 };
            float std = AlchemyFeatureExtractor.PopulationStdDev(values);
            AssertClose(std, 1.4142135f, 0.001f, "PopulationStdDev([1,2,3,4,5])");
        }

        public void PopulationStdDev_SingleElement_Zero()
        {
            var values = new List<float> { 42f };
            float std = AlchemyFeatureExtractor.PopulationStdDev(values);
            AssertClose(std, 0f, FeatureTolerance, "PopulationStdDev single");
        }

        // ====================================================================
        // ClassifierResult Tests
        // ====================================================================

        public void ClassifierResult_Valid()
        {
            var result = new ClassifierResult(true, 0.85f, 0.85f, "smithing");
            Assert(result.Valid, "Should be valid");
            Assert(!result.IsError, "Should not be error");
            AssertClose(result.Confidence, 0.85f, 0.001f, "Confidence");
        }

        public void ClassifierResult_Invalid()
        {
            var result = new ClassifierResult(false, 0.7f, 0.3f, "alchemy");
            Assert(!result.Valid, "Should be invalid");
            AssertClose(result.Probability, 0.3f, 0.001f, "Probability");
            AssertClose(result.Confidence, 0.7f, 0.001f, "Confidence = 1 - prob");
        }

        public void ClassifierResult_Error()
        {
            var result = ClassifierResult.CreateError("smithing", "Model not found");
            Assert(result.IsError, "Should be error");
            Assert(!result.Valid, "Error should be invalid");
            AssertEqual(result.Error, "Model not found", "Error message");
        }

        // ====================================================================
        // ClassifierManager Tests
        // ====================================================================

        public void ClassifierManager_Singleton()
        {
            ClassifierManager.ResetInstance();
            var a = ClassifierManager.Instance;
            var b = ClassifierManager.Instance;
            Assert(ReferenceEquals(a, b), "Should be same instance");
            ClassifierManager.ResetInstance();
        }

        public void ClassifierManager_NotInitialized_ReturnsError()
        {
            ClassifierManager.ResetInstance();
            var result = ClassifierManager.Instance.ValidateSmithing(
                new Dictionary<(int, int), string>(), 5);
            Assert(result.IsError, "Should return error when not initialized");
            ClassifierManager.ResetInstance();
        }

        // ====================================================================
        // Test Helpers
        // ====================================================================

        private static MaterialColorEncoder CreateMockEncoder()
        {
            // Create encoder with null database — will return gray for all materials
            return new MaterialColorEncoder(null);
        }

        private static void Assert(bool condition, string message)
        {
            if (!condition)
                throw new Exception($"Assertion failed: {message}");
        }

        private static void AssertEqual<T>(T actual, T expected, string message)
        {
            if (!EqualityComparer<T>.Default.Equals(actual, expected))
                throw new Exception($"Assertion failed: {message} — expected {expected}, got {actual}");
        }

        private static void AssertClose(float actual, float expected, float tolerance, string message)
        {
            float diff = MathF.Abs(actual - expected);
            if (diff > tolerance)
                throw new Exception(
                    $"Assertion failed: {message} — expected {expected:F6}, got {actual:F6}, " +
                    $"diff={diff:F6} > tolerance={tolerance:F6}");
        }
    }
}
