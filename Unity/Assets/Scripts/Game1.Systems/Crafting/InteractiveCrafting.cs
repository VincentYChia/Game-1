// ============================================================================
// Game1.Systems.Crafting.InteractiveCrafting
// Migrated from: core/interactive_crafting.py (lines 1-1179)
// Migration phase: 4
// Date: 2026-02-21
//
// Dispatch layer connecting CraftingUI → discipline-specific minigames.
// Factory pattern creates the correct minigame based on station type.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Core;
using Game1.Data.Models;
using Game1.Data.Databases;

namespace Game1.Systems.Crafting
{
    /// <summary>
    /// Result of a crafting session containing the minigame reward
    /// and output item information.
    /// </summary>
    public class CraftingSessionResult
    {
        /// <summary>The crafting reward (quality, XP, etc.).</summary>
        public CraftingReward Reward { get; set; }

        /// <summary>Output item ID from the recipe.</summary>
        public string OutputItemId { get; set; }

        /// <summary>Output quantity.</summary>
        public int OutputQuantity { get; set; }

        /// <summary>Whether this was an invention (not a known recipe).</summary>
        public bool IsInvention { get; set; }

        /// <summary>Invented recipe ID (if invention).</summary>
        public string InventedRecipeId { get; set; }

        /// <summary>Whether the crafting succeeded.</summary>
        public bool Success => Reward?.Success ?? false;
    }

    /// <summary>
    /// Interactive crafting dispatch system.
    /// Creates and manages crafting minigames based on station type.
    ///
    /// Usage:
    ///   var session = InteractiveCrafting.Instance;
    ///   session.StartCrafting("smithing", 1, recipe, materials, character);
    ///   // ... update loop calls session.Update(dt) ...
    ///   // ... UI sends input via session.HandleInput(input) ...
    ///   // On completion: var result = session.GetResult();
    /// </summary>
    public class InteractiveCrafting
    {
        private static InteractiveCrafting _instance;
        private static readonly object _lock = new object();

        public static InteractiveCrafting Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new InteractiveCrafting();
                        }
                    }
                }
                return _instance;
            }
        }

        private InteractiveCrafting() { }

        // ====================================================================
        // State
        // ====================================================================

        /// <summary>Currently active minigame (null if none).</summary>
        public BaseCraftingMinigame ActiveMinigame { get; private set; }

        /// <summary>Current discipline being crafted.</summary>
        public string CurrentDiscipline { get; private set; }

        /// <summary>Current recipe being crafted.</summary>
        public Recipe CurrentRecipe { get; private set; }

        /// <summary>Whether a minigame is currently active.</summary>
        public bool IsActive => ActiveMinigame != null && ActiveMinigame.IsActive;

        /// <summary>Whether the minigame has completed (success or failure).</summary>
        public bool IsFinished => ActiveMinigame != null &&
            (ActiveMinigame.IsComplete || ActiveMinigame.IsFailed);

        // ====================================================================
        // Crafting Lifecycle
        // ====================================================================

        /// <summary>
        /// Start a crafting minigame for the given discipline and recipe.
        /// Creates the appropriate minigame subclass.
        /// </summary>
        /// <param name="discipline">Crafting discipline: smithing, alchemy, refining, engineering, enchanting.</param>
        /// <param name="stationTier">Station tier (1-4).</param>
        /// <param name="recipe">Recipe to craft.</param>
        /// <param name="materialInputs">Materials placed by the player.</param>
        /// <param name="buffTimeBonus">Speed buff from skills (0.0-1.0+).</param>
        /// <param name="buffQualityBonus">Quality buff from skills (0.0-1.0+).</param>
        /// <returns>The created minigame, or null if discipline is unknown.</returns>
        public BaseCraftingMinigame StartCrafting(
            string discipline,
            int stationTier,
            Recipe recipe,
            List<RecipeInput> materialInputs,
            float buffTimeBonus = 0f,
            float buffQualityBonus = 0f)
        {
            CurrentDiscipline = discipline?.ToLowerInvariant() ?? "";
            CurrentRecipe = recipe;

            var recipeMeta = new Dictionary<string, object>
            {
                ["stationType"] = CurrentDiscipline,
                ["stationTier"] = stationTier,
                ["recipeId"] = recipe?.RecipeId ?? "",
            };

            ActiveMinigame = CreateMinigame(
                CurrentDiscipline,
                materialInputs ?? new List<RecipeInput>(),
                recipeMeta,
                buffTimeBonus,
                buffQualityBonus);

            if (ActiveMinigame == null)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[InteractiveCrafting] Unknown discipline: {discipline}");
                return null;
            }

            ActiveMinigame.Start();

            System.Diagnostics.Debug.WriteLine(
                $"[InteractiveCrafting] Started {discipline} minigame (T{stationTier})");
            return ActiveMinigame;
        }

        /// <summary>
        /// Update the active minigame. Call every frame.
        /// </summary>
        public void Update(float deltaTime)
        {
            if (ActiveMinigame == null || !ActiveMinigame.IsActive) return;
            ActiveMinigame.Update(deltaTime);
        }

        /// <summary>
        /// Send input to the active minigame.
        /// </summary>
        public bool HandleInput(MinigameInput input)
        {
            if (ActiveMinigame == null || !ActiveMinigame.IsActive) return false;
            return ActiveMinigame.HandleInput(input);
        }

        /// <summary>
        /// Get the result of a completed minigame.
        /// Returns null if no minigame is finished.
        /// </summary>
        public CraftingSessionResult GetResult()
        {
            if (ActiveMinigame == null) return null;
            if (!ActiveMinigame.IsComplete && !ActiveMinigame.IsFailed) return null;

            var reward = ActiveMinigame.GetReward();

            var result = new CraftingSessionResult
            {
                Reward = reward,
                OutputItemId = CurrentRecipe?.OutputId ?? "",
                OutputQuantity = CurrentRecipe?.OutputQty ?? 1,
            };

            return result;
        }

        /// <summary>
        /// Cancel the active minigame and clean up.
        /// </summary>
        public void Cancel()
        {
            ActiveMinigame = null;
            CurrentDiscipline = null;
            CurrentRecipe = null;

            System.Diagnostics.Debug.WriteLine("[InteractiveCrafting] Cancelled active minigame");
        }

        /// <summary>
        /// Clean up after getting the result.
        /// </summary>
        public void EndSession()
        {
            ActiveMinigame = null;
            CurrentDiscipline = null;
            CurrentRecipe = null;
        }

        /// <summary>
        /// Get the current minigame state for UI rendering.
        /// </summary>
        public MinigameState GetState()
        {
            return ActiveMinigame?.GetState();
        }

        // ====================================================================
        // Minigame Factory
        // ====================================================================

        /// <summary>
        /// Create the appropriate minigame for the discipline.
        /// Matches Python: interactive_crafting.py create_interactive_ui()
        /// </summary>
        private static BaseCraftingMinigame CreateMinigame(
            string discipline,
            List<RecipeInput> inputs,
            Dictionary<string, object> recipeMeta,
            float buffTimeBonus,
            float buffQualityBonus)
        {
            return discipline switch
            {
                "smithing" => new SmithingMinigame(inputs, recipeMeta, buffTimeBonus, buffQualityBonus),
                "alchemy" => new AlchemyMinigame(inputs, recipeMeta, buffTimeBonus, buffQualityBonus),
                "refining" => new RefiningMinigame(inputs, recipeMeta, buffTimeBonus, buffQualityBonus),
                "engineering" => new EngineeringMinigame(inputs, recipeMeta, buffTimeBonus, buffQualityBonus),
                "enchanting" => new EnchantingMinigame(inputs, recipeMeta, buffTimeBonus, buffQualityBonus),
                "adornments" => new EnchantingMinigame(inputs, recipeMeta, buffTimeBonus, buffQualityBonus),
                _ => null,
            };
        }

        // ====================================================================
        // Static Helpers
        // ====================================================================

        /// <summary>
        /// Check if a discipline string is valid.
        /// </summary>
        public static bool IsValidDiscipline(string discipline)
        {
            if (string.IsNullOrEmpty(discipline)) return false;
            return discipline.ToLowerInvariant() switch
            {
                "smithing" or "alchemy" or "refining" or "engineering"
                    or "enchanting" or "adornments" or "fishing" => true,
                _ => false,
            };
        }

        /// <summary>
        /// Get the available recipes for a discipline and station tier.
        /// </summary>
        public static List<Recipe> GetAvailableRecipes(string discipline, int stationTier)
        {
            var recipeDb = RecipeDatabase.Instance;
            if (!recipeDb.Loaded) return new List<Recipe>();

            return recipeDb.GetRecipesForStation(discipline, stationTier);
        }
    }
}
