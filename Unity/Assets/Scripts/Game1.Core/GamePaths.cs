// ============================================================================
// Game1.Core.GamePaths
// Migrated from: core/paths.py
// Migration phase: 2
// Date: 2026-02-13
// ============================================================================

using System;
using System.IO;

namespace Game1.Core
{
    /// <summary>
    /// Centralized path management for content files and save data.
    /// Supports both Unity (StreamingAssets) and standalone (configurable base path) modes.
    /// </summary>
    public static class GamePaths
    {
        private static string _basePath;
        private static string _savePath;

        /// <summary>
        /// Set the base content path. Call during initialization.
        /// In Unity, this should be Application.streamingAssetsPath + "/Content".
        /// In standalone tests, this can be any directory.
        /// </summary>
        public static void SetBasePath(string path)
        {
            _basePath = path;
        }

        /// <summary>
        /// Set the save data path. Call during initialization.
        /// In Unity, this should be Application.persistentDataPath + "/Saves".
        /// </summary>
        public static void SetSavePath(string path)
        {
            _savePath = path;
        }

        /// <summary>
        /// Get the full path to a content file.
        /// </summary>
        /// <param name="relativePath">Path relative to Content root, e.g., "items.JSON/items-materials-1.JSON"</param>
        /// <returns>Full filesystem path</returns>
        public static string GetContentPath(string relativePath)
        {
            if (string.IsNullOrEmpty(_basePath))
            {
                _basePath = _detectBasePath();
            }

            return Path.Combine(_basePath, relativePath);
        }

        /// <summary>
        /// Get the save data directory path.
        /// </summary>
        public static string GetSavePath()
        {
            if (string.IsNullOrEmpty(_savePath))
            {
                _savePath = _detectSavePath();
            }

            return _savePath;
        }

        /// <summary>
        /// Get the full path for a specific save file.
        /// </summary>
        public static string GetSaveFilePath(string saveName)
        {
            return Path.Combine(GetSavePath(), saveName + ".json");
        }

        /// <summary>
        /// Get the icon path for an item by category and id.
        /// </summary>
        public static string GetIconPath(string category, string itemId)
        {
            return GetContentPath(Path.Combine("icons", category, itemId + ".png"));
        }

        /// <summary>
        /// Check whether the content directory exists and has files.
        /// </summary>
        public static bool ContentPathValid()
        {
            if (string.IsNullOrEmpty(_basePath)) return false;
            return Directory.Exists(_basePath);
        }

        /// <summary>
        /// Ensure the save directory exists, creating it if needed.
        /// </summary>
        public static void EnsureSaveDirectory()
        {
            string savePath = GetSavePath();
            if (!Directory.Exists(savePath))
            {
                Directory.CreateDirectory(savePath);
            }
        }

        // ====================================================================
        // Private Helpers
        // ====================================================================

        private static string _detectBasePath()
        {
            // Try common locations in priority order:
            // 1. StreamingAssets/Content (Unity standard)
            // 2. ../Content (relative to executable)
            // 3. Current directory + Content

            string[] candidates = new[]
            {
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "StreamingAssets", "Content"),
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "StreamingAssets", "Content"),
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Content"),
                Path.Combine(Directory.GetCurrentDirectory(), "Content"),
            };

            foreach (string candidate in candidates)
            {
                if (Directory.Exists(candidate))
                {
                    return Path.GetFullPath(candidate);
                }
            }

            // Fallback: use current directory + Content (will be created or fail gracefully)
            return Path.Combine(Directory.GetCurrentDirectory(), "Content");
        }

        private static string _detectSavePath()
        {
            // Default: user home directory + Game1/Saves
            string userDir = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return Path.Combine(userDir, "Game1", "Saves");
        }
    }
}
