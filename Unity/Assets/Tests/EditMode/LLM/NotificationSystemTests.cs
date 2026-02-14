// ============================================================================
// Phase 7 Unit Tests: NotificationSystem
// Tests queue behavior, overflow handling, color mapping, and filtering.
//
// Uses same test framework pattern as Phase 5 ClassifierPreprocessorTests.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Systems.LLM;

namespace Game1.Tests.LLM
{
    /// <summary>
    /// Unit tests for Phase 7 NotificationSystem.
    /// </summary>
    public class NotificationSystemTests
    {
        // ====================================================================
        // Test Runner
        // ====================================================================

        public static int RunAll()
        {
            // Reset singleton before tests
            NotificationSystem.ResetInstance();

            var tests = new NotificationSystemTests();
            int passed = 0;
            int failed = 0;
            var testMethods = new List<(string name, Action action)>
            {
                // Basic functionality
                ("Show_AddsToActive", tests.Show_AddsToActive),
                ("Show_MultipleNotifications", tests.Show_MultipleNotifications),
                ("Show_MaxVisible_ExcessGoesToQueue", tests.Show_MaxVisible_ExcessGoesToQueue),

                // Queue behavior
                ("Update_ExpiredNotificationsRemoved", tests.Update_ExpiredNotificationsRemoved),
                ("Update_PendingPromotedOnExpiry", tests.Update_PendingPromotedOnExpiry),
                ("PendingQueue_CappedAt20", tests.PendingQueue_CappedAt20),

                // Fade behavior
                ("Update_FadeOutInFinalHalfSecond", tests.Update_FadeOutInFinalHalfSecond),

                // Color mapping
                ("GetColor_Info_IsWhite", tests.GetColor_Info_IsWhite),
                ("GetColor_Success_IsGreen", tests.GetColor_Success_IsGreen),
                ("GetColor_Warning_IsYellow", tests.GetColor_Warning_IsYellow),
                ("GetColor_Error_IsRed", tests.GetColor_Error_IsRed),
                ("GetColor_Debug_IsCyan", tests.GetColor_Debug_IsCyan),

                // Clear
                ("Clear_RemovesAllNotifications", tests.Clear_RemovesAllNotifications),

                // Event
                ("Show_RaisesEvent", tests.Show_RaisesEvent),

                // Snapshot
                ("GetActive_ReturnsCopy", tests.GetActive_ReturnsCopy),

                // Notification data structure
                ("Notification_DefaultAlphaIsOne", tests.Notification_DefaultAlphaIsOne),
            };

            foreach (var (name, action) in testMethods)
            {
                try
                {
                    // Reset state between tests
                    NotificationSystem.ResetInstance();

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
                $"\nNotificationSystemTests: {passed} passed, {failed} failed, " +
                $"{passed + failed} total");
            return failed;
        }

        // ====================================================================
        // Helpers
        // ====================================================================

        private NotificationSystem CreateSystem()
        {
            // Create a new instance for isolated testing
            return new NotificationSystem();
        }

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

        // ====================================================================
        // Basic functionality tests
        // ====================================================================

        public void Show_AddsToActive()
        {
            var sys = CreateSystem();
            sys.Show("Test notification");
            AssertEqual(1, sys.ActiveCount, "ActiveCount after 1 show");
        }

        public void Show_MultipleNotifications()
        {
            var sys = CreateSystem();
            sys.Show("Notification 1");
            sys.Show("Notification 2");
            sys.Show("Notification 3");
            AssertEqual(3, sys.ActiveCount, "ActiveCount after 3 shows");
        }

        public void Show_MaxVisible_ExcessGoesToQueue()
        {
            var sys = CreateSystem();
            // Show more than MaxVisibleNotifications (5)
            for (int i = 0; i < 7; i++)
            {
                sys.Show($"Notification {i}");
            }
            AssertEqual(5, sys.ActiveCount, "ActiveCount at max visible");
            AssertEqual(2, sys.PendingCount, "PendingCount with overflow");
        }

        // ====================================================================
        // Queue behavior tests
        // ====================================================================

        public void Update_ExpiredNotificationsRemoved()
        {
            var sys = CreateSystem();
            sys.Show("Short notification", duration: 1.0f);
            AssertEqual(1, sys.ActiveCount, "ActiveCount before update");

            // Simulate 2 seconds passing
            sys.Update(2.0f);
            AssertEqual(0, sys.ActiveCount, "ActiveCount after expiry");
        }

        public void Update_PendingPromotedOnExpiry()
        {
            var sys = CreateSystem();
            // Fill active slots
            for (int i = 0; i < 5; i++)
            {
                sys.Show($"Active {i}", duration: 1.0f);
            }
            // Add pending
            sys.Show("Pending 1", duration: 5.0f);
            AssertEqual(5, sys.ActiveCount, "ActiveCount at max");
            AssertEqual(1, sys.PendingCount, "PendingCount before update");

            // Expire all active (they have 1s duration)
            sys.Update(1.5f);

            // Pending should be promoted to active
            AssertEqual(1, sys.ActiveCount, "ActiveCount after promotion");
            AssertEqual(0, sys.PendingCount, "PendingCount after promotion");
        }

        public void PendingQueue_CappedAt20()
        {
            var sys = CreateSystem();
            // Fill active (5) and pending to max (20) + overflow
            for (int i = 0; i < 30; i++)
            {
                sys.Show($"Notification {i}", duration: 100f);
            }
            AssertEqual(5, sys.ActiveCount, "ActiveCount at max");
            AssertEqual(20, sys.PendingCount, "PendingCount capped at 20");
        }

        // ====================================================================
        // Fade behavior tests
        // ====================================================================

        public void Update_FadeOutInFinalHalfSecond()
        {
            var sys = CreateSystem();
            sys.Show("Fading", duration: 1.0f);

            // Update to 0.7s remaining (within fade duration of 0.5s)
            sys.Update(0.3f); // 0.7s remaining

            var notifications = sys.GetActiveNotifications();
            AssertEqual(1, notifications.Count, "Should still have notification");
            AssertApprox(1.0f, notifications[0].Alpha, 0.01f, "Alpha before fade");

            // Update to 0.25s remaining (within fade zone)
            sys.Update(0.45f); // 0.25s remaining

            notifications = sys.GetActiveNotifications();
            AssertEqual(1, notifications.Count, "Should still have notification");
            // Alpha = 0.25 / 0.5 = 0.5
            AssertApprox(0.5f, notifications[0].Alpha, 0.1f, "Alpha during fade");
        }

        // ====================================================================
        // Color mapping tests
        // ====================================================================

        public void GetColor_Info_IsWhite()
        {
            var (r, g, b) = NotificationSystem.GetColor(NotificationType.Info);
            AssertApprox(1.0f, r, 0.01f, "Info.R");
            AssertApprox(1.0f, g, 0.01f, "Info.G");
            AssertApprox(1.0f, b, 0.01f, "Info.B");
        }

        public void GetColor_Success_IsGreen()
        {
            var (r, g, b) = NotificationSystem.GetColor(NotificationType.Success);
            AssertApprox(0.2f, r, 0.01f, "Success.R");
            AssertApprox(0.8f, g, 0.01f, "Success.G");
            AssertApprox(0.2f, b, 0.01f, "Success.B");
        }

        public void GetColor_Warning_IsYellow()
        {
            var (r, g, b) = NotificationSystem.GetColor(NotificationType.Warning);
            AssertApprox(1.0f, r, 0.01f, "Warning.R");
            AssertApprox(0.8f, g, 0.01f, "Warning.G");
            AssertApprox(0.0f, b, 0.01f, "Warning.B");
        }

        public void GetColor_Error_IsRed()
        {
            var (r, g, b) = NotificationSystem.GetColor(NotificationType.Error);
            AssertApprox(1.0f, r, 0.01f, "Error.R");
            AssertApprox(0.3f, g, 0.01f, "Error.G");
            AssertApprox(0.3f, b, 0.01f, "Error.B");
        }

        public void GetColor_Debug_IsCyan()
        {
            var (r, g, b) = NotificationSystem.GetColor(NotificationType.Debug);
            AssertApprox(0.0f, r, 0.01f, "Debug.R");
            AssertApprox(0.8f, g, 0.01f, "Debug.G");
            AssertApprox(0.8f, b, 0.01f, "Debug.B");
        }

        // ====================================================================
        // Clear test
        // ====================================================================

        public void Clear_RemovesAllNotifications()
        {
            var sys = CreateSystem();
            for (int i = 0; i < 8; i++)
                sys.Show($"Notification {i}", duration: 100f);

            sys.Clear();
            AssertEqual(0, sys.ActiveCount, "ActiveCount after clear");
            AssertEqual(0, sys.PendingCount, "PendingCount after clear");
        }

        // ====================================================================
        // Event test
        // ====================================================================

        public void Show_RaisesEvent()
        {
            var sys = CreateSystem();
            string capturedMessage = null;
            NotificationType capturedType = NotificationType.Info;

            sys.OnNotificationShow += (msg, type, dur) =>
            {
                capturedMessage = msg;
                capturedType = type;
            };

            sys.Show("Test Event", NotificationType.Warning, 5f);

            AssertEqual("Test Event", capturedMessage, "Event message");
            AssertEqual(NotificationType.Warning, capturedType, "Event type");
        }

        // ====================================================================
        // Snapshot test
        // ====================================================================

        public void GetActive_ReturnsCopy()
        {
            var sys = CreateSystem();
            sys.Show("Test");

            var snapshot1 = sys.GetActiveNotifications();
            var snapshot2 = sys.GetActiveNotifications();

            Assert(!ReferenceEquals(snapshot1, snapshot2),
                "GetActiveNotifications should return a new list each time");
        }

        // ====================================================================
        // Notification data structure test
        // ====================================================================

        public void Notification_DefaultAlphaIsOne()
        {
            var n = new Notification();
            AssertApprox(1.0f, n.Alpha, 0.001f, "Default Alpha");
        }
    }
}
