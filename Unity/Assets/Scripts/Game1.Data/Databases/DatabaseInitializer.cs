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
                UnityEngine.Debug.Log("[DatabaseInitializer] Starting database initialization...");

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

                UnityEngine.Debug.Log("[DatabaseInitializer] All databases initialized successfully.");
                UnityEngine.Debug.Log($"  Materials: {MaterialDatabase.Instance.Count}");
                UnityEngine.Debug.Log($"  Equipment: {EquipmentDatabase.Instance.Count}");
                UnityEngine.Debug.Log($"  Skills: {SkillDatabase.Instance.Count}");
                UnityEngine.Debug.Log($"  Recipes: {RecipeDatabase.Instance.Count}");
                UnityEngine.Debug.Log($"  Placements: {PlacementDatabase.Instance.Count}");
                UnityEngine.Debug.Log($"  Titles: {TitleDatabase.Instance.Count}");
                UnityEngine.Debug.Log($"  Classes: {ClassDatabase.Instance.Count}");
                UnityEngine.Debug.Log($"  NPCs: {NPCDatabase.Instance.NPCCount}");
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.Log($"[DatabaseInitializer] CRITICAL: Initialization failed: {ex.Message}");
                UnityEngine.Debug.Log(ex.StackTrace);
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
