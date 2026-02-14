// ============================================================================
// Game1.Core.MigrationLogger
// Migrated from: N/A (new architecture — MIGRATION_META_PLAN.md section 4.2)
// Migration phase: 7
// Date: 2026-02-14
//
// Structured logging utility for migration validation.
// Uses [Conditional] attribute for zero-cost in release builds.
// Replaces Python's LLMDebugLogger with unified approach.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Diagnostics;

namespace Game1.Core
{
    /// <summary>
    /// Structured logging for migration validation and debugging.
    /// All Log methods compile out in release builds via [Conditional("DEBUG")].
    /// Warning and Error methods are always active.
    ///
    /// Usage:
    ///   MigrationLogger.Log("LLM_STUB", "Stub generation invoked", data);
    ///   MigrationLogger.LogWarning("SAVE", "Missing field in save data");
    ///   MigrationLogger.LogError("COMBAT", "Damage calculation mismatch");
    /// </summary>
    public static class MigrationLogger
    {
        /// <summary>
        /// Log a debug message with component tag. Compiled out in release builds.
        /// </summary>
        [Conditional("DEBUG")]
        [Conditional("MIGRATION_VALIDATION")]
        public static void Log(string component, string message)
        {
            System.Diagnostics.Debug.WriteLine(
                $"[MIGRATION] [{component}] {message}");
        }

        /// <summary>
        /// Log a debug message with component tag and structured data.
        /// Compiled out in release builds.
        /// </summary>
        [Conditional("DEBUG")]
        [Conditional("MIGRATION_VALIDATION")]
        public static void Log(string component, string message,
                               Dictionary<string, object> data)
        {
            var dataStr = "";
            if (data != null && data.Count > 0)
            {
                var parts = new List<string>();
                foreach (var kvp in data)
                {
                    parts.Add($"{kvp.Key}={kvp.Value}");
                }
                dataStr = " {" + string.Join(", ", parts) + "}";
            }

            System.Diagnostics.Debug.WriteLine(
                $"[MIGRATION] [{component}] {message}{dataStr}");
        }

        /// <summary>
        /// Log a warning. Always active (not conditional).
        /// </summary>
        public static void LogWarning(string component, string message)
        {
            System.Diagnostics.Debug.WriteLine(
                $"[MIGRATION WARNING] [{component}] {message}");
        }

        /// <summary>
        /// Log an error. Always active (not conditional).
        /// </summary>
        public static void LogError(string component, string message)
        {
            System.Diagnostics.Debug.WriteLine(
                $"[MIGRATION ERROR] [{component}] {message}");
        }
    }
}
