// ============================================================================
// Game1.Systems.Save.SaveManager
// Migrated from: systems/save_manager.py (635 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Centralized save/load manager for all game state.
// Serializes character, world, quests, NPCs, dungeons, and map state.
// Uses Newtonsoft.Json for serialization.
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Game1.Core;
using Game1.Data.Models;
using Game1.Systems.World;
using Game1.Systems.Progression;

namespace Game1.Systems.Save
{
    /// <summary>
    /// Centralized save/load manager for all game state.
    /// Handles character, world, quests, NPCs, and optional dungeon/map state.
    ///
    /// Save version history:
    ///   v1.0: Fixed 100x100 world
    ///   v2.0: Added world seed
    ///   v3.0: Infinite world with seed-based generation
    /// </summary>
    public class SaveManager
    {
        public const string SaveVersion = "3.0";

        public SaveManager()
        {
            EnsureSaveDirectory();
        }

        private void EnsureSaveDirectory()
        {
            if (!Directory.Exists(GamePaths.SaveDirectory))
                Directory.CreateDirectory(GamePaths.SaveDirectory);
        }

        // ====================================================================
        // Create Save Data
        // ====================================================================

        /// <summary>
        /// Create a comprehensive save data structure from all game systems.
        /// Matches Python create_save_data().
        /// </summary>
        public Dictionary<string, object> CreateSaveData(
            Dictionary<string, object> characterData,
            WorldSystem world,
            QuestSystem quests,
            List<Dictionary<string, object>> npcStates = null,
            Dictionary<string, object> dungeonState = null,
            float gameTime = 0f,
            Dictionary<string, object> mapState = null)
        {
            var saveData = new Dictionary<string, object>
            {
                ["version"] = SaveVersion,
                ["save_timestamp"] = DateTime.Now.ToString("o"),
                ["player"] = characterData,
                ["world_state"] = SerializeWorldState(world, gameTime),
                ["quest_state"] = quests.ToSaveData(),
                ["npc_state"] = npcStates ?? new List<Dictionary<string, object>>(),
                ["game_settings"] = SerializeGameSettings(),
            };

            if (dungeonState != null)
                saveData["dungeon_state"] = dungeonState;

            if (mapState != null)
                saveData["map_state"] = mapState;

            return saveData;
        }

        // ====================================================================
        // Character Serialization
        // ====================================================================

        /// <summary>
        /// Serialize a character's state. This is a helper that game code can use
        /// to build the character data dictionary. In the Unity migration, the Character
        /// class provides its own ToSaveData(), but this documents the expected format.
        ///
        /// Expected fields: position, facing, stats (6 stats), leveling (level, exp, stat_points),
        /// health, max_health, mana, max_mana, class, inventory, equipment,
        /// equipped_skills, known_skills, titles, activities, stat_tracker,
        /// skill_unlocks, invented_recipes.
        /// </summary>
        public static Dictionary<string, object> SerializeCharacter(
            GamePosition position,
            string facing,
            Dictionary<string, int> stats,
            int level,
            int currentExp,
            int unallocatedStatPoints,
            float health,
            float maxHealth,
            float mana,
            float maxMana,
            string classId,
            List<Dictionary<string, object>> inventory,
            Dictionary<string, Dictionary<string, object>> equipment,
            List<string> equippedSkills,
            Dictionary<string, Dictionary<string, object>> knownSkills,
            List<string> titleIds,
            Dictionary<string, int> activities,
            Dictionary<string, object> statTracker = null,
            HashSet<string> unlockedSkills = null,
            HashSet<string> pendingUnlocks = null,
            List<Dictionary<string, object>> inventedRecipes = null)
        {
            return new Dictionary<string, object>
            {
                ["position"] = new Dictionary<string, object>
                {
                    ["x"] = position.X, ["y"] = position.Y, ["z"] = position.Z
                },
                ["facing"] = facing,
                ["stats"] = stats,
                ["leveling"] = new Dictionary<string, object>
                {
                    ["level"] = level,
                    ["current_exp"] = currentExp,
                    ["unallocated_stat_points"] = unallocatedStatPoints,
                },
                ["health"] = health,
                ["max_health"] = maxHealth,
                ["mana"] = mana,
                ["max_mana"] = maxMana,
                ["class"] = classId,
                ["inventory"] = inventory,
                ["equipment"] = equipment,
                ["equipped_skills"] = equippedSkills,
                ["known_skills"] = knownSkills,
                ["titles"] = titleIds,
                ["activities"] = activities,
                ["stat_tracker"] = statTracker ?? new Dictionary<string, object>(),
                ["skill_unlocks"] = new Dictionary<string, object>
                {
                    ["unlocked_skills"] = unlockedSkills?.ToList() ?? new List<string>(),
                    ["pending_unlocks"] = pendingUnlocks?.ToList() ?? new List<string>(),
                },
                ["invented_recipes"] = inventedRecipes ?? new List<Dictionary<string, object>>(),
            };
        }

        // ====================================================================
        // World Serialization
        // ====================================================================

        private Dictionary<string, object> SerializeWorldState(WorldSystem world, float gameTime)
        {
            var worldData = world.ToSaveData();
            worldData["game_time"] = gameTime;
            return worldData;
        }

        // ====================================================================
        // Game Settings
        // ====================================================================

        private Dictionary<string, object> SerializeGameSettings()
        {
            return new Dictionary<string, object>
            {
                ["keep_inventory"] = true, // Default; override from Config if available
            };
        }

        // ====================================================================
        // Save to File
        // ====================================================================

        /// <summary>
        /// Save the game state to a JSON file.
        /// Matches Python save_game().
        /// </summary>
        public bool SaveToFile(string filename, Dictionary<string, object> saveData)
        {
            try
            {
                string filepath = GetSavePath(filename);
                string json = JsonConvert.SerializeObject(saveData, Formatting.Indented);
                File.WriteAllText(filepath, json);
                return true;
            }
            catch (Exception e)
            {
                Console.WriteLine($"Error saving game: {e.Message}");
                return false;
            }
        }

        // ====================================================================
        // Load from File
        // ====================================================================

        /// <summary>
        /// Load game state from a JSON file.
        /// Applies save migration if version mismatch.
        /// Matches Python load_game().
        /// </summary>
        public Dictionary<string, object> LoadFromFile(string filename)
        {
            try
            {
                string filepath = GetSavePath(filename);

                if (!File.Exists(filepath))
                {
                    Console.WriteLine($"Save file not found: {filepath}");
                    return null;
                }

                string json = File.ReadAllText(filepath);
                var saveData = JsonConvert.DeserializeObject<Dictionary<string, object>>(json);

                // Check version and migrate if needed
                string version = saveData.TryGetValue("version", out var v) ? v?.ToString() : "1.0";
                if (version != SaveVersion)
                {
                    Console.WriteLine($"Warning: Save version {version}, migrating to {SaveVersion}");
                    saveData = SaveMigrator.Migrate(saveData);
                }

                return saveData;
            }
            catch (Exception e)
            {
                Console.WriteLine($"Error loading game: {e.Message}");
                return null;
            }
        }

        // ====================================================================
        // Load Helpers
        // ====================================================================

        /// <summary>
        /// Restore world system state from loaded save data.
        /// </summary>
        public void LoadWorldState(WorldSystem world, Dictionary<string, object> saveData)
        {
            if (saveData.TryGetValue("world_state", out var wsObj) && wsObj is Dictionary<string, object> worldState)
            {
                world.FromSaveData(worldState);
            }
        }

        /// <summary>
        /// Restore quest state from loaded save data.
        /// </summary>
        public void LoadQuestState(QuestSystem quests, Dictionary<string, object> saveData)
        {
            if (saveData.TryGetValue("quest_state", out var qsObj) && qsObj is Dictionary<string, object> questState)
            {
                quests.FromSaveData(questState);
            }
        }

        /// <summary>
        /// Extract player position from save data.
        /// </summary>
        public static GamePosition GetPlayerPosition(Dictionary<string, object> saveData)
        {
            if (saveData.TryGetValue("player", out var playerObj) &&
                playerObj is Dictionary<string, object> player &&
                player.TryGetValue("position", out var posObj) &&
                posObj is Dictionary<string, object> pos)
            {
                return new GamePosition(
                    Convert.ToSingle(pos["x"]),
                    Convert.ToSingle(pos["y"]),
                    Convert.ToSingle(pos["z"]));
            }
            return GamePosition.Zero;
        }

        // ====================================================================
        // File Management
        // ====================================================================

        /// <summary>
        /// Get list of all save files with metadata.
        /// Matches Python get_save_files().
        /// </summary>
        public List<Dictionary<string, object>> GetSaveFiles()
        {
            var saveFiles = new List<Dictionary<string, object>>();

            if (!Directory.Exists(GamePaths.SaveDirectory))
                return saveFiles;

            foreach (var filepath in Directory.GetFiles(GamePaths.SaveDirectory, "*.json"))
            {
                try
                {
                    string filename = Path.GetFileName(filepath);
                    var fileInfo = new FileInfo(filepath);

                    string json = File.ReadAllText(filepath);
                    var data = JsonConvert.DeserializeObject<Dictionary<string, object>>(json);

                    string timestamp = data.TryGetValue("save_timestamp", out var ts)
                        ? ts?.ToString() : fileInfo.LastWriteTime.ToString("o");
                    string version = data.TryGetValue("version", out var ver) ? ver?.ToString() : "1.0";

                    int level = 1;
                    if (data.TryGetValue("player", out var pObj) &&
                        pObj is Dictionary<string, object> p &&
                        p.TryGetValue("leveling", out var lObj) &&
                        lObj is Dictionary<string, object> lev)
                    {
                        level = lev.TryGetValue("level", out var lvl) ? Convert.ToInt32(lvl) : 1;
                    }

                    saveFiles.Add(new Dictionary<string, object>
                    {
                        ["filename"] = filename,
                        ["filepath"] = filepath,
                        ["save_timestamp"] = timestamp,
                        ["modified_time"] = fileInfo.LastWriteTime.ToString("o"),
                        ["version"] = version,
                        ["level"] = level,
                    });
                }
                catch (Exception e)
                {
                    Console.WriteLine($"Error reading save file {filepath}: {e.Message}");
                }
            }

            // Sort newest first
            saveFiles.Sort((a, b) =>
                string.Compare(b["modified_time"]?.ToString(), a["modified_time"]?.ToString(), StringComparison.Ordinal));

            return saveFiles;
        }

        /// <summary>
        /// Delete a save file.
        /// </summary>
        public bool DeleteSaveFile(string filename)
        {
            try
            {
                string filepath = GetSavePath(filename);
                if (File.Exists(filepath))
                {
                    File.Delete(filepath);
                    return true;
                }
                return false;
            }
            catch (Exception e)
            {
                Console.WriteLine($"Error deleting save file: {e.Message}");
                return false;
            }
        }

        private string GetSavePath(string filename)
        {
            return Path.Combine(GamePaths.SaveDirectory, filename);
        }
    }
}
