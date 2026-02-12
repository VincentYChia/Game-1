// Game1.Core.GamePaths
// Migrated from: core/paths.py (146 lines) PathManager singleton
// Phase: 2 - Data Layer
// In Unity, uses Application.streamingAssetsPath for content
// and Application.persistentDataPath for saves.

using System.IO;

namespace Game1.Core
{
    /// <summary>
    /// Manages file paths for content and save files.
    /// Unity adaptation of Python PathManager singleton.
    /// Content: StreamingAssets/Content/ (read-only game data, moddable)
    /// Saves: persistentDataPath/saves/ (writable user data)
    /// </summary>
    public class GamePaths
    {
        private static GamePaths _instance;
        private static readonly object _lock = new object();

        public string BasePath { get; private set; }
        public string SavePath { get; private set; }
        public bool IsBundled { get; private set; }

        public static GamePaths GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new GamePaths();
                }
            }
            return _instance;
        }

        private GamePaths()
        {
            SetupPaths();
        }

        private void SetupPaths()
        {
            // In Unity: Application.streamingAssetsPath for content
            // For plain C# testing: use relative path from current directory
            // Phase 6 will override BasePath with Application.streamingAssetsPath
            string streamingAssetsPath = GetStreamingAssetsPath();
            BasePath = Path.Combine(streamingAssetsPath, "Content");

            // Saves in persistent data path
            string persistentDataPath = GetPersistentDataPath();
            SavePath = Path.Combine(persistentDataPath, "saves");

            // Ensure save directory exists
            if (!Directory.Exists(SavePath))
                Directory.CreateDirectory(SavePath);

            IsBundled = false;
        }

        /// <summary>
        /// Get absolute path to a content resource file.
        /// </summary>
        public string GetResourcePath(string relativePath)
        {
            return Path.Combine(BasePath, relativePath);
        }

        /// <summary>
        /// Get path to save directory or specific save file.
        /// </summary>
        public string GetSavePath(string filename = null)
        {
            return filename != null ? Path.Combine(SavePath, filename) : SavePath;
        }

        /// <summary>
        /// Check if a content resource file exists.
        /// </summary>
        public bool ResourceExists(string relativePath)
        {
            return File.Exists(GetResourcePath(relativePath));
        }

        /// <summary>
        /// Override base path for Unity integration (Phase 6).
        /// Called once during startup with Application.streamingAssetsPath.
        /// </summary>
        public void SetBasePath(string streamingAssetsPath)
        {
            BasePath = Path.Combine(streamingAssetsPath, "Content");
        }

        /// <summary>
        /// Override save path for Unity integration (Phase 6).
        /// Called once during startup with Application.persistentDataPath.
        /// </summary>
        public void SetSavePath(string persistentDataPath)
        {
            SavePath = Path.Combine(persistentDataPath, "saves");
            if (!Directory.Exists(SavePath))
                Directory.CreateDirectory(SavePath);
        }

        /// <summary>
        /// Get StreamingAssets path. In plain C# (Phases 1-5), falls back to
        /// current directory. Phase 6 MonoBehaviour sets the real path.
        /// </summary>
        private static string GetStreamingAssetsPath()
        {
            // Try Unity's Application.streamingAssetsPath via reflection
            // to avoid compile-time dependency on UnityEngine
            try
            {
                var appType = System.Type.GetType("UnityEngine.Application, UnityEngine.CoreModule");
                if (appType != null)
                {
                    var prop = appType.GetProperty("streamingAssetsPath");
                    if (prop != null)
                        return prop.GetValue(null)?.ToString() ?? ".";
                }
            }
            catch { }

            // Fallback for plain C# testing
            return ".";
        }

        /// <summary>
        /// Get persistent data path. In plain C# (Phases 1-5), falls back to
        /// current directory. Phase 6 MonoBehaviour sets the real path.
        /// </summary>
        private static string GetPersistentDataPath()
        {
            try
            {
                var appType = System.Type.GetType("UnityEngine.Application, UnityEngine.CoreModule");
                if (appType != null)
                {
                    var prop = appType.GetProperty("persistentDataPath");
                    if (prop != null)
                        return prop.GetValue(null)?.ToString() ?? ".";
                }
            }
            catch { }

            return ".";
        }

        internal static void ResetInstance() => _instance = null;
    }
}
