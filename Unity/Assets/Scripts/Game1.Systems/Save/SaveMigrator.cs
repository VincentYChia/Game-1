// ============================================================================
// Game1.Systems.Save.SaveMigrator
// Migrated from: N/A (new — save version upgrade utility)
// Migration phase: 4
// Date: 2026-02-13
//
// Handles migration of save files between versions:
//   v1.0 -> v2.0: Add world seed
//   v2.0 -> v3.0: Convert fixed world to infinite with seed-based generation
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Systems.Save
{
    /// <summary>
    /// Migrates save data from older versions to the current version.
    /// Each migration step is applied sequentially until the save reaches
    /// the current version (SaveManager.SaveVersion = "3.0").
    /// </summary>
    public static class SaveMigrator
    {
        /// <summary>
        /// Migrate save data to the current version.
        /// Applies all necessary migration steps in order.
        /// </summary>
        public static Dictionary<string, object> Migrate(Dictionary<string, object> saveData)
        {
            if (saveData == null) return saveData;

            string version = saveData.TryGetValue("version", out var v) ? v?.ToString() : "1.0";

            // v1.0 -> v2.0: Add world seed for deterministic generation
            if (version == "1.0")
            {
                saveData = MigrateV1ToV2(saveData);
                version = "2.0";
            }

            // v2.0 -> v3.0: Convert to infinite world with seed-based chunks
            if (version == "2.0")
            {
                saveData = MigrateV2ToV3(saveData);
                version = "3.0";
            }

            saveData["version"] = SaveManager.SaveVersion;
            return saveData;
        }

        /// <summary>
        /// v1.0 -> v2.0: Add world seed.
        /// Old saves had no seed; generate a deterministic one from save timestamp.
        /// </summary>
        private static Dictionary<string, object> MigrateV1ToV2(Dictionary<string, object> saveData)
        {
            Console.WriteLine("Migrating save v1.0 -> v2.0: Adding world seed");

            if (!saveData.ContainsKey("world_state"))
            {
                saveData["world_state"] = new Dictionary<string, object>();
            }

            var worldState = saveData["world_state"] as Dictionary<string, object>;
            if (worldState != null && !worldState.ContainsKey("seed"))
            {
                // Generate seed from save timestamp for reproducibility
                string timestamp = saveData.TryGetValue("save_timestamp", out var ts)
                    ? ts?.ToString() : DateTime.Now.ToString("o");
                int seed = Math.Abs(timestamp.GetHashCode());
                worldState["seed"] = seed;
            }

            saveData["version"] = "2.0";
            return saveData;
        }

        /// <summary>
        /// v2.0 -> v3.0: Convert fixed-size world to infinite world.
        /// - Ensure seed exists in world_state
        /// - Convert old resource/tile data to chunk-based format
        /// - Add game_time if missing
        /// - Add missing fields (death_chests, discovered_dungeons)
        /// </summary>
        private static Dictionary<string, object> MigrateV2ToV3(Dictionary<string, object> saveData)
        {
            Console.WriteLine("Migrating save v2.0 -> v3.0: Converting to infinite world");

            if (!saveData.ContainsKey("world_state"))
            {
                saveData["world_state"] = new Dictionary<string, object>();
            }

            var worldState = saveData["world_state"] as Dictionary<string, object>;
            if (worldState == null) return saveData;

            // Ensure seed exists
            if (!worldState.ContainsKey("seed"))
            {
                worldState["seed"] = new System.Random().Next(0, int.MaxValue);
            }

            // Ensure game_time exists
            if (!worldState.ContainsKey("game_time"))
            {
                worldState["game_time"] = 0.0f;
            }

            // Ensure death_chests list exists
            if (!worldState.ContainsKey("death_chests"))
            {
                worldState["death_chests"] = new List<Dictionary<string, object>>();
            }

            // Ensure discovered_dungeons list exists
            if (!worldState.ContainsKey("discovered_dungeons"))
            {
                worldState["discovered_dungeons"] = new List<Dictionary<string, object>>();
            }

            // Ensure placed_entities exists
            if (!worldState.ContainsKey("placed_entities"))
            {
                worldState["placed_entities"] = new List<Dictionary<string, object>>();
            }

            // Ensure quest_state exists
            if (!saveData.ContainsKey("quest_state"))
            {
                saveData["quest_state"] = new Dictionary<string, object>
                {
                    ["active_quests"] = new Dictionary<string, object>(),
                    ["completed_quests"] = new List<string>(),
                };
            }

            // Ensure game_settings exists
            if (!saveData.ContainsKey("game_settings"))
            {
                saveData["game_settings"] = new Dictionary<string, object>
                {
                    ["keep_inventory"] = true,
                };
            }

            // Migrate player skill_unlocks if missing
            if (saveData.TryGetValue("player", out var playerObj) &&
                playerObj is Dictionary<string, object> player)
            {
                if (!player.ContainsKey("skill_unlocks"))
                {
                    player["skill_unlocks"] = new Dictionary<string, object>
                    {
                        ["unlocked_skills"] = new List<string>(),
                        ["pending_unlocks"] = new List<string>(),
                    };
                }

                if (!player.ContainsKey("invented_recipes"))
                {
                    player["invented_recipes"] = new List<Dictionary<string, object>>();
                }

                if (!player.ContainsKey("stat_tracker"))
                {
                    player["stat_tracker"] = new Dictionary<string, object>();
                }
            }

            saveData["version"] = "3.0";
            return saveData;
        }
    }
}
