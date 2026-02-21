// ============================================================================
// Game1.Data.Databases.DatabaseInitializer
// Migrated from: N/A (consolidates database initialization order)
// Migration phase: 2
// Date: 2026-02-13
// ============================================================================

using System;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Initializes all databases in the correct dependency order.
    /// Call InitializeAll() once during game startup.
    ///
    /// Order from PHASE_CONTRACTS.md:
    /// Group 1: No dependencies
    /// Group 2: Standalone loaders
    /// Group 3: Equipment (may use tag processors)
    /// Group 4: Content databases
    /// Group 5: Update packages
    /// </summary>
    public static class DatabaseInitializer
    {
        /// <summary>
        /// Load all databases in the correct order.
        /// Call once during startup. Idempotent (safe to call multiple times).
        /// </summary>
        public static void InitializeAll()
        {
            try
            {
                System.Diagnostics.Debug.WriteLine("[DatabaseInitializer] Starting database initialization...");

                // Group 1: No dependencies
                var worldConfig = WorldGenerationConfig.Instance; // loads in constructor
                ClassDatabase.Instance.LoadFromFile("progression/classes-1.JSON");
                ResourceNodeDatabase.Instance.LoadFromFile("Definitions.JSON/resource-node-1.JSON");

                // Group 2: Standalone material loaders
                MaterialDatabase.Instance.LoadFromFile("items.JSON/items-materials-1.JSON");
                MaterialDatabase.Instance.LoadRefiningItems("items.JSON/items-refining-1.JSON");
                MaterialDatabase.Instance.LoadStackableItems("items.JSON/items-alchemy-1.JSON");
                MaterialDatabase.Instance.LoadStackableItems("items.JSON/items-engineering-1.JSON");
                MaterialDatabase.Instance.LoadStackableItems("items.JSON/items-tools-1.JSON");

                // Group 3: Equipment
                EquipmentDatabase.Instance.LoadFromFile("items.JSON/items-smithing-2.JSON");
                EquipmentDatabase.Instance.LoadFromFile("items.JSON/items-tools-1.JSON");

                // Group 4: Content databases
                SkillDatabase.Instance.LoadFromFile("Skills/skills-skills-1.JSON");
                RecipeDatabase.Instance.LoadFromFiles();
                PlacementDatabase.Instance.LoadFromFiles();
                TitleDatabase.Instance.LoadFromFile("progression/titles-1.JSON");

                // Group 5: Additional databases
                NPCDatabase.Instance.LoadFromFile("progression/npcs-1.JSON");
                NPCDatabase.Instance.LoadQuestsFromFile("progression/quests-1.JSON");
                TranslationDatabase.Instance.LoadFromFile("Definitions.JSON/translations-1.JSON");
                var mapConfig = MapWaypointConfig.Instance; // loads defaults
                // Note: EnemyDatabaseAdapter is loaded by GameManager (Phase 6)
                // because it lives in Game1.Systems.Combat to avoid circular dependencies.

                System.Diagnostics.Debug.WriteLine("[DatabaseInitializer] All databases initialized successfully.");
                System.Diagnostics.Debug.WriteLine($"  Materials: {MaterialDatabase.Instance.Count}");
                System.Diagnostics.Debug.WriteLine($"  Equipment: {EquipmentDatabase.Instance.Count}");
                System.Diagnostics.Debug.WriteLine($"  Skills: {SkillDatabase.Instance.Count}");
                System.Diagnostics.Debug.WriteLine($"  Recipes: {RecipeDatabase.Instance.Count}");
                System.Diagnostics.Debug.WriteLine($"  Placements: {PlacementDatabase.Instance.Count}");
                System.Diagnostics.Debug.WriteLine($"  Titles: {TitleDatabase.Instance.Count}");
                System.Diagnostics.Debug.WriteLine($"  Classes: {ClassDatabase.Instance.Count}");
                System.Diagnostics.Debug.WriteLine($"  NPCs: {NPCDatabase.Instance.NPCCount}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[DatabaseInitializer] CRITICAL: Initialization failed: {ex.Message}");
                System.Diagnostics.Debug.WriteLine(ex.StackTrace);
            }
        }

        /// <summary>
        /// Reset all singletons for testing.
        /// NEVER call in production.
        /// </summary>
        public static void ResetAll()
        {
            MaterialDatabase.ResetInstance();
            EquipmentDatabase.ResetInstance();
            RecipeDatabase.ResetInstance();
            SkillDatabase.ResetInstance();
            PlacementDatabase.ResetInstance();
            TitleDatabase.ResetInstance();
            ClassDatabase.ResetInstance();
            ResourceNodeDatabase.ResetInstance();
            WorldGenerationConfig.ResetInstance();
            NPCDatabase.ResetInstance();
            TranslationDatabase.ResetInstance();
            MapWaypointConfig.ResetInstance();
        }
    }
}
