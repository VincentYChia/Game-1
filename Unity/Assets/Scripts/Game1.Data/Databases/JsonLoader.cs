// Game1.Data.Databases.JsonLoader
// Phase: 2 - Data Layer
// Static helper for loading JSON from StreamingAssets/Content/.
// Uses Newtonsoft.Json for deserialization (not Unity's JsonUtility).

using System;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Game1.Core;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Centralized JSON loading utility.
    /// All database singletons use this for consistent file access.
    /// Files are loaded from StreamingAssets/Content/ via GamePaths.
    /// </summary>
    public static class JsonLoader
    {
        /// <summary>
        /// Get absolute path for a content file relative to StreamingAssets/Content/.
        /// </summary>
        public static string GetContentPath(string relativePath)
        {
            return GamePaths.GetInstance().GetResourcePath(relativePath);
        }

        /// <summary>
        /// Load and deserialize a JSON file to a typed object.
        /// Returns default(T) if file not found.
        /// </summary>
        public static T LoadJson<T>(string relativePath)
        {
            string fullPath = GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                LogWarning($"JSON file not found: {fullPath}");
                return default;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                return JsonConvert.DeserializeObject<T>(json);
            }
            catch (Exception ex)
            {
                LogWarning($"Failed to parse JSON file {fullPath}: {ex.Message}");
                return default;
            }
        }

        /// <summary>
        /// Load a JSON file as a raw JObject for manual parsing.
        /// Returns null if file not found or parse error.
        /// </summary>
        public static JObject LoadRawJson(string relativePath)
        {
            string fullPath = GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                LogWarning($"JSON file not found: {fullPath}");
                return null;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                return JObject.Parse(json);
            }
            catch (Exception ex)
            {
                LogWarning($"Failed to parse JSON file {fullPath}: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Load a JSON file as a raw JArray for array-based files.
        /// Returns null if file not found or parse error.
        /// </summary>
        public static JArray LoadRawJsonArray(string relativePath)
        {
            string fullPath = GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                LogWarning($"JSON file not found: {fullPath}");
                return null;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                return JArray.Parse(json);
            }
            catch (Exception ex)
            {
                LogWarning($"Failed to parse JSON array {fullPath}: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Load a JSON file from an absolute path (for UpdateLoader and testing).
        /// </summary>
        public static JObject LoadRawJsonAbsolute(string absolutePath)
        {
            if (!File.Exists(absolutePath))
                return null;

            try
            {
                string json = File.ReadAllText(absolutePath);
                return JObject.Parse(json);
            }
            catch (Exception ex)
            {
                LogWarning($"Failed to parse JSON file {absolutePath}: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Check if a content file exists.
        /// </summary>
        public static bool ContentExists(string relativePath)
        {
            return File.Exists(GetContentPath(relativePath));
        }

        /// <summary>
        /// Logging helper. Uses Unity Debug.Log when available, Console otherwise.
        /// </summary>
        internal static void LogWarning(string message)
        {
            try
            {
                var debugType = Type.GetType("UnityEngine.Debug, UnityEngine.CoreModule");
                if (debugType != null)
                {
                    var method = debugType.GetMethod("LogWarning", new[] { typeof(object) });
                    method?.Invoke(null, new object[] { $"[JsonLoader] {message}" });
                    return;
                }
            }
            catch { }

            Console.WriteLine($"[JsonLoader] WARNING: {message}");
        }

        internal static void Log(string message)
        {
            try
            {
                var debugType = Type.GetType("UnityEngine.Debug, UnityEngine.CoreModule");
                if (debugType != null)
                {
                    var method = debugType.GetMethod("Log", new[] { typeof(object) });
                    method?.Invoke(null, new object[] { $"[JsonLoader] {message}" });
                    return;
                }
            }
            catch { }

            Console.WriteLine($"[JsonLoader] {message}");
        }
    }
}
