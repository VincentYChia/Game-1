// Game1.Data.Databases.DatabaseInitializer
// Phase: 2 - Data Layer
// Orchestrates loading all databases in dependency order.
// 16-step initialization sequence matching Python game_engine.py startup.

using System;
using Game1.Core;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Centralized database initialization.
    /// Loads all databases in the correct dependency order.
    /// Call DatabaseInitializer.InitializeAll() once at game startup.
    /// </summary>
    public static class DatabaseInitializer
    {
        public static bool Initialized { get; private set; }

        /// <summary>
        /// Initialize all databases in dependency order.
        /// This is the main entry point for game startup.
        /// </summary>
        public static void InitializeAll()
        {
            if (Initialized)
            {
                JsonLoader.LogWarning("DatabaseInitializer.InitializeAll() called twice - skipping");
                return;
            }

            JsonLoader.Log("Starting database initialization...");

            // Step 1: GameConfig (static, no loading needed - already initialized)
            // GameConfig.InitScreenSettings() is called by Unity MonoBehaviour in Phase 6

            // Step 2: GamePaths (singleton, auto-initializes on first access)
            var paths = GamePaths.GetInstance();
            JsonLoader.Log($"GamePaths initialized. BasePath: {paths.BasePath}");

            // Step 3: TranslationDatabase (no dependencies)
            var translationDb = TranslationDatabase.GetInstance();
            translationDb.LoadFromFiles();

            // Step 4: WorldGenerationConfig (no dependencies)
            var worldGenConfig = WorldGenerationConfig.GetInstance();

            // Step 5: MapWaypointConfig (no dependencies)
            var mapWpConfig = MapWaypointConfig.GetInstance();

            // Step 6: ClassDatabase (no dependencies)
            var classDb = ClassDatabase.GetInstance();
            classDb.LoadFromFile(JsonLoader.GetContentPath("progression/classes-1.JSON"));

            // Step 7: ResourceNodeDatabase (no dependencies)
            var resourceDb = ResourceNodeDatabase.GetInstance();
            resourceDb.LoadFromFile(JsonLoader.GetContentPath("Definitions.JSON/Resource-node-1.JSON"));

            // Step 8: MaterialDatabase (multi-file, 3 separate loads)
            var materialDb = MaterialDatabase.GetInstance();
            materialDb.LoadFromFile(JsonLoader.GetContentPath("items.JSON/items-materials-1.JSON"));
            materialDb.LoadRefiningItems(JsonLoader.GetContentPath("items.JSON/items-refining-1.JSON"));
            materialDb.LoadStackableItems(
                JsonLoader.GetContentPath("items.JSON/items-alchemy-1.JSON"),
                new() { "consumable" });
            materialDb.LoadStackableItems(
                JsonLoader.GetContentPath("items.JSON/items-engineering-1.JSON"),
                new() { "device" });
            materialDb.LoadStackableItems(
                JsonLoader.GetContentPath("items.JSON/items-tools-1.JSON"),
                new() { "station" });

            // Step 9: EquipmentDatabase (multi-file, accumulative)
            var equipmentDb = EquipmentDatabase.GetInstance();
            equipmentDb.LoadFromFile(JsonLoader.GetContentPath("items.JSON/items-smithing-2.JSON"));
            equipmentDb.LoadFromFile(JsonLoader.GetContentPath("items.JSON/items-tools-1.JSON"));

            // Step 10: SkillDatabase (single file)
            var skillDb = SkillDatabase.GetInstance();
            skillDb.LoadFromFile(JsonLoader.GetContentPath("Skills/skills-skills-1.JSON"));

            // Step 11: RecipeDatabase (5 files, one per discipline)
            var recipeDb = RecipeDatabase.GetInstance();
            recipeDb.LoadFromFiles();

            // Step 12: PlacementDatabase (5 files, one per discipline)
            var placementDb = PlacementDatabase.GetInstance();
            placementDb.LoadFromFiles();

            // Step 13: TitleDatabase (single file)
            var titleDb = TitleDatabase.GetInstance();
            titleDb.LoadFromFile(JsonLoader.GetContentPath("progression/titles-1.JSON"));

            // Step 14: SkillUnlockDatabase (single file)
            var skillUnlockDb = SkillUnlockDatabase.GetInstance();
            skillUnlockDb.LoadFromFile(JsonLoader.GetContentPath("progression/skill-unlocks.JSON"));

            // Step 15: NPCDatabase (tries enhanced, falls back to v1.0)
            var npcDb = NPCDatabase.GetInstance();
            npcDb.LoadFromFiles();

            // Step 16: UpdateLoader (post-init, loads Update-N packages)
            UpdateLoader.LoadAllUpdates();

            Initialized = true;
            JsonLoader.Log("Database initialization complete.");
        }

        /// <summary>
        /// Reset all database singletons. Used for testing.
        /// </summary>
        public static void ResetAll()
        {
            TranslationDatabase.ResetInstance();
            WorldGenerationConfig.ResetInstance();
            MapWaypointConfig.ResetInstance();
            ClassDatabase.ResetInstance();
            ResourceNodeDatabase.ResetInstance();
            MaterialDatabase.ResetInstance();
            EquipmentDatabase.ResetInstance();
            SkillDatabase.ResetInstance();
            RecipeDatabase.ResetInstance();
            PlacementDatabase.ResetInstance();
            TitleDatabase.ResetInstance();
            SkillUnlockDatabase.ResetInstance();
            NPCDatabase.ResetInstance();
            GamePaths.ResetInstance();
            Initialized = false;
        }
    }
}
