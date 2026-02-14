// ============================================================================
// Phase 7 Unit Tests: LoadingState
// Tests thread-safe state transitions, animation formulas, and timing.
//
// Uses same test framework pattern as Phase 5 ClassifierPreprocessorTests.
// Uses injectable time provider for deterministic testing.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Systems.LLM;

namespace Game1.Tests.LLM
{
    /// <summary>
    /// Unit tests for Phase 7 LoadingState.
    /// Uses injectable time provider for deterministic animation testing.
    /// </summary>
    public class LoadingStateTests
    {
        // ====================================================================
        // Test Runner
        // ====================================================================

        public static int RunAll()
        {
            var tests = new LoadingStateTests();
            int passed = 0;
            int failed = 0;
            var testMethods = new List<(string name, Action action)>
            {
                // Initial state
                ("Initial_NotLoading", tests.Initial_NotLoading),
                ("Initial_EmptyMessage", tests.Initial_EmptyMessage),
                ("Initial_ZeroProgress", tests.Initial_ZeroProgress),
                ("Initial_NotComplete", tests.Initial_NotComplete),

                // Start
                ("Start_SetsIsLoading", tests.Start_SetsIsLoading),
                ("Start_SetsMessage", tests.Start_SetsMessage),
                ("Start_SetsOverlayMode", tests.Start_SetsOverlayMode),
                ("Start_SetsSubtitle", tests.Start_SetsSubtitle),
                ("Start_ResetsProgress", tests.Start_ResetsProgress),

                // Update
                ("Update_ChangesMessage", tests.Update_ChangesMessage),
                ("Update_ChangesProgress", tests.Update_ChangesProgress),
                ("Update_NullKeepsCurrent", tests.Update_NullKeepsCurrent),

                // Finish
                ("Finish_SetsComplete", tests.Finish_SetsComplete),
                ("Finish_ProgressIsOne", tests.Finish_ProgressIsOne),
                ("Finish_MessageIsComplete", tests.Finish_MessageIsComplete),
                ("Finish_SubtitleIsEmpty", tests.Finish_SubtitleIsEmpty),

                // Animation formula
                ("Animation_AtZero_IsZero", tests.Animation_AtZero_IsZero),
                ("Animation_AtHalf_MiddleValue", tests.Animation_AtHalf_MiddleValue),
                ("Animation_AtFull_IsMax", tests.Animation_AtFull_IsMax),
                ("Animation_WhenComplete_IsOne", tests.Animation_WhenComplete_IsOne),
                ("Animation_WhenNotLoading_IsZero", tests.Animation_WhenNotLoading_IsZero),
                ("Animation_ExplicitProgress_UsedIfHigher", tests.Animation_ExplicitProgress_UsedIfHigher),

                // Completion delay
                ("CompletionDelay_LoadingDuringDelay", tests.CompletionDelay_LoadingDuringDelay),
                ("CompletionDelay_NotLoadingAfterDelay", tests.CompletionDelay_NotLoadingAfterDelay),

                // Reset
                ("Reset_ClearsAllState", tests.Reset_ClearsAllState),

                // Constants
                ("Constants_MatchPython", tests.Constants_MatchPython),
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
                $"\nLoadingStateTests: {passed} passed, {failed} failed, " +
                $"{passed + failed} total");
            return failed;
        }

        // ====================================================================
        // Helpers
        // ====================================================================

        private static void Assert(bool condition, string message)
        {
            if (!condition) throw new Exception($"Assertion failed: {message}");
        }

        private static void AssertEqual<T>(T expected, T actual, string field)
        {
            if (!EqualityComparer<T>.Default.Equals(expected, actual))
                throw new Exception(
                    $"Expected {field} = {expected}, got {actual}");
        }

        private static void AssertApprox(float expected, float actual, float tolerance, string field)
        {
            if (Math.Abs(expected - actual) > tolerance)
                throw new Exception(
                    $"Expected {field} ≈ {expected} (±{tolerance}), got {actual}");
        }

        /// <summary>
        /// Create a LoadingState with a controllable clock.
        /// Returns (loadingState, advanceClock) where advanceClock adds seconds.
        /// </summary>
        private static (LoadingState state, Action<float> advanceClock) CreateWithClock()
        {
            float currentTime = 0f;
            var state = new LoadingState(() => currentTime);
            Action<float> advance = (seconds) => currentTime += seconds;
            return (state, advance);
        }

        // ====================================================================
        // Initial state tests
        // ====================================================================

        public void Initial_NotLoading()
        {
            var (state, _) = CreateWithClock();
            Assert(!state.IsLoading, "Initial state should not be loading");
        }

        public void Initial_EmptyMessage()
        {
            var (state, _) = CreateWithClock();
            AssertEqual("", state.Message, "Initial Message");
        }

        public void Initial_ZeroProgress()
        {
            var (state, _) = CreateWithClock();
            AssertApprox(0f, state.Progress, 0.001f, "Initial Progress");
        }

        public void Initial_NotComplete()
        {
            var (state, _) = CreateWithClock();
            Assert(!state.IsComplete, "Initial state should not be complete");
        }

        // ====================================================================
        // Start tests
        // ====================================================================

        public void Start_SetsIsLoading()
        {
            var (state, _) = CreateWithClock();
            state.Start("Loading...");
            Assert(state.IsLoading, "IsLoading after Start");
        }

        public void Start_SetsMessage()
        {
            var (state, _) = CreateWithClock();
            state.Start("Generating item...");
            AssertEqual("Generating item...", state.Message, "Message after Start");
        }

        public void Start_SetsOverlayMode()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test", overlay: true);
            Assert(state.OverlayMode, "OverlayMode after Start with overlay=true");
        }

        public void Start_SetsSubtitle()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test", subtitle: "Please wait...");
            AssertEqual("Please wait...", state.Subtitle, "Subtitle after Start");
        }

        public void Start_ResetsProgress()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test");
            state.Update(progress: 0.5f);
            state.Start("Reset");
            AssertApprox(0f, state.Progress, 0.001f, "Progress after re-Start");
        }

        // ====================================================================
        // Update tests
        // ====================================================================

        public void Update_ChangesMessage()
        {
            var (state, _) = CreateWithClock();
            state.Start("Initial");
            state.Update(message: "Updated");
            AssertEqual("Updated", state.Message, "Message after Update");
        }

        public void Update_ChangesProgress()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test");
            state.Update(progress: 0.75f);
            AssertApprox(0.75f, state.Progress, 0.001f, "Progress after Update");
        }

        public void Update_NullKeepsCurrent()
        {
            var (state, _) = CreateWithClock();
            state.Start("Initial", subtitle: "Sub");
            state.Update(); // all null
            AssertEqual("Initial", state.Message, "Message unchanged");
            AssertEqual("Sub", state.Subtitle, "Subtitle unchanged");
        }

        // ====================================================================
        // Finish tests
        // ====================================================================

        public void Finish_SetsComplete()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test");
            state.Finish();
            Assert(state.IsComplete, "IsComplete after Finish");
        }

        public void Finish_ProgressIsOne()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test");
            state.Finish();
            AssertApprox(1.0f, state.Progress, 0.001f, "Progress after Finish");
        }

        public void Finish_MessageIsComplete()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test");
            state.Finish();
            AssertEqual("Item Generation Complete", state.Message, "Message after Finish");
        }

        public void Finish_SubtitleIsEmpty()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test", subtitle: "Sub");
            state.Finish();
            AssertEqual("", state.Subtitle, "Subtitle after Finish");
        }

        // ====================================================================
        // Animation formula tests
        // ====================================================================

        public void Animation_AtZero_IsZero()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test");
            // At time 0, animation should be at or near 0
            AssertApprox(0f, state.GetAnimatedProgress(), 0.01f, "Animation at t=0");
        }

        public void Animation_AtHalf_MiddleValue()
        {
            var (state, advance) = CreateWithClock();
            state.Start("Test");
            advance(LoadingState.SmoothProgressDuration / 2f); // Half duration

            float progress = state.GetAnimatedProgress();

            // At t=0.5 of duration: eased = 1 - (1-0.5)^3 = 1 - 0.125 = 0.875
            // Scaled by SmoothProgressMax (0.9): 0.875 * 0.9 = 0.7875
            AssertApprox(0.7875f, progress, 0.02f, "Animation at t=half");
        }

        public void Animation_AtFull_IsMax()
        {
            var (state, advance) = CreateWithClock();
            state.Start("Test");
            advance(LoadingState.SmoothProgressDuration); // Full duration

            float progress = state.GetAnimatedProgress();

            // At t=1.0: eased = 1 - (1-1)^3 = 1.0
            // Scaled by SmoothProgressMax (0.9): 1.0 * 0.9 = 0.9
            AssertApprox(LoadingState.SmoothProgressMax, progress, 0.01f,
                "Animation at t=full");
        }

        public void Animation_WhenComplete_IsOne()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test");
            state.Finish();
            AssertApprox(1.0f, state.GetAnimatedProgress(), 0.001f,
                "Animation when complete");
        }

        public void Animation_WhenNotLoading_IsZero()
        {
            var (state, _) = CreateWithClock();
            AssertApprox(0f, state.GetAnimatedProgress(), 0.001f,
                "Animation when not loading");
        }

        public void Animation_ExplicitProgress_UsedIfHigher()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test");
            // Set explicit progress higher than animation would produce at t=0
            state.Update(progress: 0.95f);
            // When explicit progress is set, smooth animation is disabled
            // and explicit progress is used directly
            AssertApprox(0.95f, state.GetAnimatedProgress(), 0.01f,
                "Explicit progress overrides animation");
        }

        // ====================================================================
        // Completion delay tests
        // ====================================================================

        public void CompletionDelay_LoadingDuringDelay()
        {
            var (state, advance) = CreateWithClock();
            state.Start("Test");
            state.Finish();
            // Immediately after finish, IsLoading should still be true
            // (within CompletionDelay)
            Assert(state.IsLoading, "IsLoading during completion delay");
        }

        public void CompletionDelay_NotLoadingAfterDelay()
        {
            var (state, advance) = CreateWithClock();
            state.Start("Test");
            state.Finish();
            advance(LoadingState.CompletionDelay + 0.1f);
            Assert(!state.IsLoading, "IsLoading after completion delay");
        }

        // ====================================================================
        // Reset tests
        // ====================================================================

        public void Reset_ClearsAllState()
        {
            var (state, _) = CreateWithClock();
            state.Start("Test", overlay: true, subtitle: "Sub");
            state.Update(progress: 0.5f);
            state.Finish();

            state.Reset();

            Assert(!state.IsLoading, "IsLoading after Reset");
            Assert(!state.IsComplete, "IsComplete after Reset");
            Assert(!state.OverlayMode, "OverlayMode after Reset");
            AssertEqual("", state.Message, "Message after Reset");
            AssertEqual("", state.Subtitle, "Subtitle after Reset");
            AssertApprox(0f, state.Progress, 0.001f, "Progress after Reset");
        }

        // ====================================================================
        // Constants tests
        // ====================================================================

        public void Constants_MatchPython()
        {
            // Verify constants match Python llm_item_generator.py exactly
            AssertApprox(15.0f, LoadingState.SmoothProgressDuration, 0.001f,
                "SmoothProgressDuration");
            AssertApprox(0.90f, LoadingState.SmoothProgressMax, 0.001f,
                "SmoothProgressMax");
            AssertApprox(0.5f, LoadingState.CompletionDelay, 0.001f,
                "CompletionDelay");
        }
    }
}
