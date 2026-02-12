// Game1.Data.Databases.UpdateLoader
// Migrated from: data/databases/update_loader.py (364 lines)
// Phase: 2 - Data Layer
// Auto-discovers and loads content from Update-N directories.
// Called AFTER core database initialization to layer in additional content.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Post-initialization content loader for Update-N packages.
    /// Scans updates_manifest.json for installed update directories
    /// and loads additional items, skills, recipes, etc.
    /// </summary>
    public static class UpdateLoader
    {
        /// <summary>
        /// Load all content from installed Update-N packages.
        /// Call AFTER core database initialization.
        /// </summary>
        public static void LoadAllUpdates(string projectRoot = null)
        {
            if (string.IsNullOrEmpty(projectRoot))
                projectRoot = Core.GamePaths.GetInstance().BasePath;

            var installed = GetInstalledUpdates(projectRoot);
            if (installed.Count == 0)
            {
                JsonLoader.Log("No Update-N packages installed");
                return;
            }

            JsonLoader.Log($"Loading {installed.Count} Update-N package(s): {string.Join(", ", installed)}");

            LoadEquipmentUpdates(projectRoot, installed);
            LoadSkillUpdates(projectRoot, installed);
            LoadMaterialUpdates(projectRoot, installed);
            LoadRecipeUpdates(projectRoot, installed);
            LoadTitleUpdates(projectRoot, installed);
            LoadSkillUnlockUpdates(projectRoot, installed);

            JsonLoader.Log("Update-N packages loaded successfully");
        }

        private static List<string> GetInstalledUpdates(string projectRoot)
        {
            string manifestPath = Path.Combine(projectRoot, "updates_manifest.json");
            if (!File.Exists(manifestPath))
                return new List<string>();

            try
            {
                string json = File.ReadAllText(manifestPath);
                var manifest = JObject.Parse(json);
                var updates = manifest["installed_updates"] as JArray;
                return updates?.Select(u => u.Value<string>()).ToList() ?? new List<string>();
            }
            catch
            {
                return new List<string>();
            }
        }

        private static List<string> ScanUpdateDirectory(string updateDir, string databaseType)
        {
            if (!Directory.Exists(updateDir))
                return new List<string>();

            var patterns = databaseType switch
            {
                "equipment" => new[] { "*items*", "*weapons*", "*armor*", "*tools*" },
                "skills" => new[] { "*skills*" },
                "materials" => new[] { "*materials*", "*consumables*", "*devices*" },
                "titles" => new[] { "*titles*" },
                "skill_unlocks" => new[] { "*skill-unlocks*", "*skill_unlocks*" },
                "recipes" => new[] { "*recipes*" },
                _ => new[] { "*" }
            };

            var files = new HashSet<string>();
            foreach (var pattern in patterns)
            {
                foreach (var ext in new[] { ".JSON", ".json" })
                {
                    foreach (var file in Directory.GetFiles(updateDir, pattern + ext))
                        files.Add(file);
                }
            }

            return files.ToList();
        }

        private static void LoadEquipmentUpdates(string projectRoot, List<string> installed)
        {
            var db = EquipmentDatabase.GetInstance();
            foreach (string updateName in installed)
            {
                string updateDir = Path.Combine(projectRoot, updateName);
                foreach (string file in ScanUpdateDirectory(updateDir, "equipment"))
                {
                    try { db.LoadFromFile(file); }
                    catch (Exception ex) { JsonLoader.LogWarning($"Error loading equipment update {file}: {ex.Message}"); }
                }
            }
        }

        private static void LoadSkillUpdates(string projectRoot, List<string> installed)
        {
            var db = SkillDatabase.GetInstance();
            foreach (string updateName in installed)
            {
                string updateDir = Path.Combine(projectRoot, updateName);
                foreach (string file in ScanUpdateDirectory(updateDir, "skills"))
                {
                    try { db.LoadFromFile(file); }
                    catch (Exception ex) { JsonLoader.LogWarning($"Error loading skill update {file}: {ex.Message}"); }
                }
            }
        }

        private static void LoadMaterialUpdates(string projectRoot, List<string> installed)
        {
            var db = MaterialDatabase.GetInstance();
            foreach (string updateName in installed)
            {
                string updateDir = Path.Combine(projectRoot, updateName);
                foreach (string file in ScanUpdateDirectory(updateDir, "materials"))
                {
                    try
                    {
                        if (file.ToLower().Contains("materials"))
                            db.LoadFromFile(file);
                        else
                            db.LoadStackableItems(file);
                    }
                    catch (Exception ex) { JsonLoader.LogWarning($"Error loading material update {file}: {ex.Message}"); }
                }
            }
        }

        private static void LoadRecipeUpdates(string projectRoot, List<string> installed)
        {
            // RecipeDatabase uses internal LoadFile; we'd need to expose it or use LoadFromFiles
            // For now, skip recipe updates as they require special station-type detection
            // This will be enhanced in Phase 4 when crafting system is complete
        }

        private static void LoadTitleUpdates(string projectRoot, List<string> installed)
        {
            var db = TitleDatabase.GetInstance();
            foreach (string updateName in installed)
            {
                string updateDir = Path.Combine(projectRoot, updateName);
                foreach (string file in ScanUpdateDirectory(updateDir, "titles"))
                {
                    try { db.LoadFromFile(file); }
                    catch (Exception ex) { JsonLoader.LogWarning($"Error loading title update {file}: {ex.Message}"); }
                }
            }
        }

        private static void LoadSkillUnlockUpdates(string projectRoot, List<string> installed)
        {
            var db = SkillUnlockDatabase.GetInstance();
            foreach (string updateName in installed)
            {
                string updateDir = Path.Combine(projectRoot, updateName);
                foreach (string file in ScanUpdateDirectory(updateDir, "skill_unlocks"))
                {
                    try { db.LoadFromFile(file); }
                    catch (Exception ex) { JsonLoader.LogWarning($"Error loading skill unlock update {file}: {ex.Message}"); }
                }
            }
        }
    }
}
