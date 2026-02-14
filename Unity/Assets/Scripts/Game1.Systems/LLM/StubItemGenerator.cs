// ============================================================================
// Game1.Systems.LLM.StubItemGenerator
// Migrated from: systems/llm_item_generator.py (MockBackend, lines 471-499)
// Migration phase: 7
// Date: 2026-02-14
//
// Placeholder item generator that returns synthetic items without API calls.
// Produces deterministic items based on input materials for reproducibility.
// Marks all generated items with IsStub = true for identification.
//
// Future: Swap for AnthropicItemGenerator with real Claude API calls.
// The IItemGenerator interface ensures no structural changes are needed.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Game1.Core;
using Game1.Data.Databases;

namespace Game1.Systems.LLM
{
    /// <summary>
    /// Placeholder item generator that returns synthetic items without calling any API.
    ///
    /// Behavior:
    /// - Always available (IsAvailable = true)
    /// - Simulates 500ms async delay to mimic network latency
    /// - Generates deterministic placeholder items based on input materials
    /// - Marks all items with IsStub = true
    /// - Logs every invocation via MigrationLogger
    /// - Triggers a debug notification on every call
    /// </summary>
    public class StubItemGenerator : IItemGenerator
    {
        private readonly LoadingState _loadingState;
        private readonly NotificationSystem _notifications;

        /// <summary>Stub is always available.</summary>
        public bool IsAvailable => true;

        /// <summary>
        /// Create a StubItemGenerator with dependencies.
        /// </summary>
        /// <param name="loadingState">Loading state for UI progress. Creates new if null.</param>
        /// <param name="notifications">Notification system. Uses singleton if null.</param>
        public StubItemGenerator(LoadingState loadingState = null,
                                 NotificationSystem notifications = null)
        {
            _loadingState = loadingState ?? new LoadingState();
            _notifications = notifications ?? NotificationSystem.Instance;
        }

        /// <summary>
        /// Generate a placeholder item asynchronously.
        /// Simulates 500ms delay, logs invocation, and produces a deterministic item.
        /// </summary>
        public async Task<GeneratedItem> GenerateItemAsync(ItemGenerationRequest request)
        {
            if (request == null)
            {
                return GeneratedItem.CreateError("unknown", "Request is null");
            }

            // 1. Log the request
            MigrationLogger.Log("LLM_STUB",
                $"Stub generation invoked for {request.Discipline} " +
                $"with {request.Materials?.Count ?? 0} materials",
                new Dictionary<string, object>
                {
                    ["discipline"] = request.Discipline,
                    ["materialCount"] = request.Materials?.Count ?? 0,
                    ["stationTier"] = request.StationTier,
                    ["placementHash"] = request.PlacementHash ?? "none"
                });

            // 2. Show debug notification
            _notifications.Show(
                $"[STUB] Generating {request.Discipline} item...",
                NotificationType.Debug,
                duration: 3.0f);

            // 3. Update loading state
            _loadingState.Start(
                message: "Generating Item (STUB)...",
                overlay: true,
                subtitle: "Using placeholder generator");

            // 4. Simulate async delay (500ms)
            await Task.Delay(500);

            // 5. Generate placeholder item
            GeneratedItem item;
            try
            {
                item = GeneratePlaceholderItem(request);
            }
            catch (Exception ex)
            {
                _loadingState.Finish();
                MigrationLogger.LogError("LLM_STUB", $"Stub generation failed: {ex.Message}");
                return GeneratedItem.CreateError(request.Discipline, $"Stub error: {ex.Message}");
            }

            // 6. Finish loading state
            _loadingState.Finish();

            // 7. Show completion notification
            _notifications.Show(
                $"[STUB] Created: {item.ItemName}",
                NotificationType.Debug,
                duration: 5.0f);

            MigrationLogger.Log("LLM_STUB",
                $"Stub generation complete: {item.ItemId} ({item.ItemName})");

            return item;
        }

        /// <summary>
        /// Generate a deterministic placeholder item from request materials.
        /// Item stats scale with total material tier points.
        /// </summary>
        private GeneratedItem GeneratePlaceholderItem(ItemGenerationRequest request)
        {
            // Compute deterministic item ID from placement hash
            string placementHash = request.PlacementHash ?? Guid.NewGuid().ToString("N");
            string itemId = $"invented_{request.Discipline}_{placementHash}";

            // Compute stats based on material tiers
            int totalTierPoints = 0;
            string primaryMaterial = "unknown";
            int materialCount = 0;

            if (request.Materials != null)
            {
                foreach (var mat in request.Materials)
                {
                    int tier = 1; // default tier
                    string matName = mat.MaterialId;

                    var matDb = MaterialDatabase.Instance;
                    if (matDb != null && matDb.Loaded)
                    {
                        var matDef = matDb.GetMaterial(mat.MaterialId);
                        if (matDef != null)
                        {
                            tier = matDef.Tier;
                            matName = matDef.Name;
                        }
                    }

                    totalTierPoints += tier * mat.Quantity;
                    materialCount += mat.Quantity;

                    if (primaryMaterial == "unknown")
                        primaryMaterial = matName;
                }
            }

            // Determine quality tier from total points (matches DifficultyCalculator tiers)
            string qualityPrefix = GetQualityPrefix(totalTierPoints);
            string rarity = qualityPrefix.ToLowerInvariant();

            string itemName = $"[STUB] {qualityPrefix} {CapitalizeFirst(request.Discipline)} Item";

            // Compute item tier (1-4) from average material tier
            int itemTier = materialCount > 0
                ? Math.Clamp(totalTierPoints / Math.Max(materialCount, 1), 1, 4)
                : 1;

            // Build item data matching the game's expected JSON schema
            var itemData = new Dictionary<string, object>
            {
                ["itemId"] = itemId,
                ["name"] = itemName,
                ["description"] = $"Placeholder item created from {primaryMaterial}. " +
                                  "This item was generated by the migration stub.",
                ["category"] = GetCategoryForDiscipline(request.Discipline),
                ["tier"] = itemTier,
                ["rarity"] = rarity,
                ["isStub"] = true,
                ["tags"] = new List<string> { "invented", "stub" },
                ["effectTags"] = new List<string>(),
                ["effectParams"] = new Dictionary<string, object>()
            };

            // Add discipline-specific stats
            AddDisciplineStats(itemData, request.Discipline, totalTierPoints);

            // Build recipe inputs for save persistence
            var recipeInputs = new List<Dictionary<string, object>>();
            if (request.Materials != null)
            {
                foreach (var mat in request.Materials)
                {
                    recipeInputs.Add(new Dictionary<string, object>
                    {
                        ["materialId"] = mat.MaterialId,
                        ["qty"] = mat.Quantity
                    });
                }
            }

            return new GeneratedItem
            {
                Success = true,
                ItemData = itemData,
                ItemId = itemId,
                ItemName = itemName,
                Discipline = request.Discipline,
                IsStub = true,
                StationTier = request.StationTier,
                RecipeInputs = recipeInputs,
                Narrative = "This is a placeholder item generated by the migration stub. " +
                            "Full LLM generation will be implemented in a future update."
            };
        }

        /// <summary>
        /// Get quality prefix from total tier points.
        /// Matches DifficultyCalculator tier boundaries exactly.
        /// </summary>
        private static string GetQualityPrefix(int totalTierPoints)
        {
            return totalTierPoints switch
            {
                <= 4 => "Common",
                <= 10 => "Uncommon",
                <= 20 => "Rare",
                <= 40 => "Epic",
                _ => "Legendary"
            };
        }

        /// <summary>
        /// Map discipline to item category.
        /// Matches Python _add_invented_item_to_game logic.
        /// </summary>
        private static string GetCategoryForDiscipline(string discipline)
        {
            return (discipline?.ToLowerInvariant()) switch
            {
                "smithing" => "equipment",
                "alchemy" => "consumable",
                "refining" => "material",
                "engineering" => "equipment",
                "enchanting" => "equipment",
                _ => "equipment"
            };
        }

        /// <summary>
        /// Add discipline-specific stats to the item data dictionary.
        /// Stats scale linearly with material tier points.
        /// </summary>
        private static void AddDisciplineStats(Dictionary<string, object> itemData,
                                                string discipline, int tierPoints)
        {
            float statMultiplier = 1.0f + (tierPoints * 0.1f);

            switch (discipline?.ToLowerInvariant())
            {
                case "smithing":
                    itemData["slot"] = "mainHand";
                    itemData["damage"] = new int[] { (int)(8 * statMultiplier), (int)(12 * statMultiplier) };
                    itemData["durabilityCurrent"] = 100;
                    itemData["durabilityMax"] = 100;
                    itemData["weight"] = 5.0f;
                    itemData["attackSpeed"] = 1.0f;
                    itemData["handType"] = "1H";
                    break;

                case "alchemy":
                    itemData["maxStack"] = 20;
                    itemData["effect"] = "healing";
                    itemData["effectParams"] = new Dictionary<string, object>
                    {
                        ["potency"] = (int)(50 * statMultiplier),
                        ["duration"] = 30.0f
                    };
                    break;

                case "refining":
                    itemData["maxStack"] = 99;
                    itemData["materialCategory"] = "processed";
                    itemData["outputQty"] = Math.Max(1, tierPoints / 2);
                    break;

                case "engineering":
                    itemData["slot"] = "mainHand";
                    itemData["damage"] = new int[] { (int)(6 * statMultiplier), (int)(10 * statMultiplier) };
                    itemData["durabilityCurrent"] = 100;
                    itemData["durabilityMax"] = 100;
                    itemData["attackSpeed"] = 1.0f;
                    itemData["range"] = 5.0f;
                    itemData["weight"] = 8.0f;
                    break;

                case "enchanting":
                    itemData["slot"] = "accessory1";
                    itemData["enchantmentPower"] = (int)(25 * statMultiplier);
                    itemData["durabilityCurrent"] = 100;
                    itemData["durabilityMax"] = 100;
                    itemData["weight"] = 1.0f;
                    break;
            }
        }

        /// <summary>Capitalize first letter of a string.</summary>
        private static string CapitalizeFirst(string s)
        {
            if (string.IsNullOrEmpty(s)) return s;
            return char.ToUpperInvariant(s[0]) + s.Substring(1).ToLowerInvariant();
        }
    }
}
