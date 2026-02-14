// ============================================================================
// Phase 7 Unit Tests: StubItemGenerator
// Tests placeholder item generation, schema validation, and notification
// integration.
//
// Uses same test framework pattern as Phase 5 ClassifierPreprocessorTests.
// Simple assert-based (no Unity Test Runner dependency).
// ============================================================================

using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Game1.Core;
using Game1.Systems.LLM;

namespace Game1.Tests.LLM
{
    /// <summary>
    /// Unit tests for Phase 7 StubItemGenerator.
    /// Uses simple assert framework matching Phase 5 test patterns.
    ///
    /// Run: Instantiate and call RunAll() or invoke individual test methods.
    /// All tests return true on pass, throw on failure.
    /// </summary>
    public class StubItemGeneratorTests
    {
        // ====================================================================
        // Test Runner
        // ====================================================================

        public static int RunAll()
        {
            var tests = new StubItemGeneratorTests();
            int passed = 0;
            int failed = 0;
            var testMethods = new List<(string name, Action action)>
            {
                // IItemGenerator interface tests
                ("IsAvailable_AlwaysTrue", tests.IsAvailable_AlwaysTrue),

                // GenerateItemAsync tests
                ("GenerateAsync_NullRequest_ReturnsError", tests.GenerateAsync_NullRequest_ReturnsError),
                ("GenerateAsync_ValidRequest_ReturnsSuccess", tests.GenerateAsync_ValidRequest_ReturnsSuccess),
                ("GenerateAsync_SetsIsStubTrue", tests.GenerateAsync_SetsIsStubTrue),
                ("GenerateAsync_ItemIdContainsDiscipline", tests.GenerateAsync_ItemIdContainsDiscipline),
                ("GenerateAsync_ItemIdContainsHash", tests.GenerateAsync_ItemIdContainsHash),
                ("GenerateAsync_ItemDataHasRequiredFields", tests.GenerateAsync_ItemDataHasRequiredFields),

                // Quality tier tests
                ("QualityTier_LowPoints_Common", tests.QualityTier_LowPoints_Common),
                ("QualityTier_MidPoints_Rare", tests.QualityTier_MidPoints_Rare),
                ("QualityTier_HighPoints_Legendary", tests.QualityTier_HighPoints_Legendary),

                // Discipline-specific tests
                ("Smithing_HasDamageAndDurability", tests.Smithing_HasDamageAndDurability),
                ("Alchemy_HasPotencyAndDuration", tests.Alchemy_HasPotencyAndDuration),
                ("Refining_HasOutputQty", tests.Refining_HasOutputQty),
                ("Engineering_HasAttackDamageAndRange", tests.Engineering_HasAttackDamageAndRange),
                ("Enchanting_HasEnchantmentPower", tests.Enchanting_HasEnchantmentPower),

                // Category mapping tests
                ("Category_Smithing_IsEquipment", tests.Category_Smithing_IsEquipment),
                ("Category_Alchemy_IsConsumable", tests.Category_Alchemy_IsConsumable),
                ("Category_Refining_IsMaterial", tests.Category_Refining_IsMaterial),

                // Recipe inputs tests
                ("RecipeInputs_PreservedInResult", tests.RecipeInputs_PreservedInResult),
                ("StationTier_PreservedInResult", tests.StationTier_PreservedInResult),

                // Notification tests
                ("Notifications_ShowCalledOnGeneration", tests.Notifications_ShowCalledOnGeneration),

                // LoadingState tests
                ("LoadingState_StartedDuringGeneration", tests.LoadingState_StartedDuringGeneration),
                ("LoadingState_FinishedAfterGeneration", tests.LoadingState_FinishedAfterGeneration),

                // GeneratedItem data structure tests
                ("GeneratedItem_CreateSuccess_IsValid", tests.GeneratedItem_CreateSuccess_IsValid),
                ("GeneratedItem_CreateError_IsNotValid", tests.GeneratedItem_CreateError_IsNotValid),
                ("GeneratedItem_DefaultIsStubFalse", tests.GeneratedItem_DefaultIsStubFalse),
            };

            foreach (var (name, action) in testMethods)
            {
                try
                {
                    action();
                    passed++;
                    System.Diagnostics.Debug.WriteLine($"  PASS: {name}");
                }
                catch (Exception ex)
                {
                    failed++;
                    System.Diagnostics.Debug.WriteLine($"  FAIL: {name} — {ex.Message}");
                }
            }

            System.Diagnostics.Debug.WriteLine(
                $"\nStubItemGeneratorTests: {passed} passed, {failed} failed, " +
                $"{passed + failed} total");
            return failed;
        }

        // ====================================================================
        // Helpers
        // ====================================================================

        private static ItemGenerationRequest CreateTestRequest(
            string discipline = "smithing",
            int stationTier = 1,
            string hash = "testhash123")
        {
            return new ItemGenerationRequest
            {
                Discipline = discipline,
                StationTier = stationTier,
                PlacementHash = hash,
                ClassifierConfidence = 0.85f,
                Materials = new List<MaterialPlacement>
                {
                    new MaterialPlacement
                    {
                        MaterialId = "iron_ingot",
                        Quantity = 3,
                        SlotIndex = 0
                    },
                    new MaterialPlacement
                    {
                        MaterialId = "oak_plank",
                        Quantity = 1,
                        SlotIndex = 1
                    }
                }
            };
        }

        private static GeneratedItem RunGeneration(string discipline = "smithing",
                                                    int stationTier = 1)
        {
            var loadingState = new LoadingState();
            var notifications = new NotificationSystem();
            var generator = new StubItemGenerator(loadingState, notifications);
            var request = CreateTestRequest(discipline, stationTier);
            return generator.GenerateItemAsync(request).GetAwaiter().GetResult();
        }

        private static void Assert(bool condition, string message)
        {
            if (!condition) throw new Exception($"Assertion failed: {message}");
        }

        private static void AssertEqual<T>(T expected, T actual, string field)
        {
            if (!EqualityComparer<T>.Default.Equals(expected, actual))
                throw new Exception(
                    $"Expected {field} = {expected}, got {actual}");
        }

        private static void AssertNotNull(object obj, string field)
        {
            if (obj == null) throw new Exception($"Expected {field} to be non-null");
        }

        private static void AssertContains(string haystack, string needle, string context)
        {
            if (haystack == null || !haystack.Contains(needle))
                throw new Exception(
                    $"Expected '{context}' to contain '{needle}', got '{haystack}'");
        }

        // ====================================================================
        // IItemGenerator interface tests
        // ====================================================================

        public void IsAvailable_AlwaysTrue()
        {
            var generator = new StubItemGenerator();
            Assert(generator.IsAvailable, "StubItemGenerator.IsAvailable should always be true");
        }

        // ====================================================================
        // GenerateItemAsync tests
        // ====================================================================

        public void GenerateAsync_NullRequest_ReturnsError()
        {
            var generator = new StubItemGenerator();
            var result = generator.GenerateItemAsync(null).GetAwaiter().GetResult();
            Assert(!result.Success, "Null request should fail");
            Assert(result.IsError, "Null request should be error");
            AssertNotNull(result.Error, "Error message");
        }

        public void GenerateAsync_ValidRequest_ReturnsSuccess()
        {
            var result = RunGeneration();
            Assert(result.Success, "Valid request should succeed");
            Assert(result.IsValid, "Valid request should produce valid result");
            AssertNotNull(result.ItemData, "ItemData");
            AssertNotNull(result.ItemId, "ItemId");
            AssertNotNull(result.ItemName, "ItemName");
        }

        public void GenerateAsync_SetsIsStubTrue()
        {
            var result = RunGeneration();
            Assert(result.IsStub, "Stub generator should set IsStub = true");
        }

        public void GenerateAsync_ItemIdContainsDiscipline()
        {
            var result = RunGeneration("alchemy");
            AssertContains(result.ItemId, "alchemy", "ItemId");
        }

        public void GenerateAsync_ItemIdContainsHash()
        {
            var result = RunGeneration();
            AssertContains(result.ItemId, "testhash123", "ItemId");
        }

        public void GenerateAsync_ItemDataHasRequiredFields()
        {
            var result = RunGeneration();
            var data = result.ItemData;

            Assert(data.ContainsKey("itemId"), "ItemData must have itemId");
            Assert(data.ContainsKey("name"), "ItemData must have name");
            Assert(data.ContainsKey("category"), "ItemData must have category");
            Assert(data.ContainsKey("tier"), "ItemData must have tier");
            Assert(data.ContainsKey("rarity"), "ItemData must have rarity");
            Assert(data.ContainsKey("isStub"), "ItemData must have isStub");
            Assert(data.ContainsKey("tags"), "ItemData must have tags");
        }

        // ====================================================================
        // Quality tier tests
        // ====================================================================

        public void QualityTier_LowPoints_Common()
        {
            var request = new ItemGenerationRequest
            {
                Discipline = "smithing",
                StationTier = 1,
                PlacementHash = "low",
                Materials = new List<MaterialPlacement>
                {
                    new MaterialPlacement { MaterialId = "test_mat", Quantity = 1 }
                }
            };

            var generator = new StubItemGenerator(new LoadingState(), new NotificationSystem());
            var result = generator.GenerateItemAsync(request).GetAwaiter().GetResult();

            // With 1 material at tier 1 = 1 point → Common
            AssertContains(result.ItemName, "Common", "ItemName for low tier");
        }

        public void QualityTier_MidPoints_Rare()
        {
            var request = new ItemGenerationRequest
            {
                Discipline = "smithing",
                StationTier = 2,
                PlacementHash = "mid",
                Materials = new List<MaterialPlacement>
                {
                    // Without DB, all materials default to tier 1
                    // 15 materials * tier 1 = 15 points → Rare (11-20)
                    new MaterialPlacement { MaterialId = "test_mat", Quantity = 15 }
                }
            };

            var generator = new StubItemGenerator(new LoadingState(), new NotificationSystem());
            var result = generator.GenerateItemAsync(request).GetAwaiter().GetResult();
            AssertContains(result.ItemName, "Rare", "ItemName for mid tier");
        }

        public void QualityTier_HighPoints_Legendary()
        {
            var request = new ItemGenerationRequest
            {
                Discipline = "smithing",
                StationTier = 4,
                PlacementHash = "high",
                Materials = new List<MaterialPlacement>
                {
                    // 50 materials * tier 1 = 50 points → Legendary (41+)
                    new MaterialPlacement { MaterialId = "test_mat", Quantity = 50 }
                }
            };

            var generator = new StubItemGenerator(new LoadingState(), new NotificationSystem());
            var result = generator.GenerateItemAsync(request).GetAwaiter().GetResult();
            AssertContains(result.ItemName, "Legendary", "ItemName for high tier");
        }

        // ====================================================================
        // Discipline-specific stat tests
        // ====================================================================

        public void Smithing_HasDamageAndDurability()
        {
            var result = RunGeneration("smithing");
            var data = result.ItemData;
            Assert(data.ContainsKey("damage"), "Smithing item must have damage");
            Assert(data.ContainsKey("durabilityMax"), "Smithing item must have durabilityMax");
            Assert(data.ContainsKey("weight"), "Smithing item must have weight");
            Assert(data.ContainsKey("slot"), "Smithing item must have slot");
        }

        public void Alchemy_HasPotencyAndDuration()
        {
            var result = RunGeneration("alchemy");
            var data = result.ItemData;
            Assert(data.ContainsKey("effect"), "Alchemy item must have effect");
            Assert(data.ContainsKey("effectParams"), "Alchemy item must have effectParams");
            Assert(data.ContainsKey("maxStack"), "Alchemy item must have maxStack");
        }

        public void Refining_HasOutputQty()
        {
            var result = RunGeneration("refining");
            var data = result.ItemData;
            Assert(data.ContainsKey("outputQty"), "Refining item must have outputQty");
            Assert(data.ContainsKey("maxStack"), "Refining item must have maxStack");
        }

        public void Engineering_HasAttackDamageAndRange()
        {
            var result = RunGeneration("engineering");
            var data = result.ItemData;
            Assert(data.ContainsKey("damage"), "Engineering item must have damage");
            Assert(data.ContainsKey("range"), "Engineering item must have range");
            Assert(data.ContainsKey("attackSpeed"), "Engineering item must have attackSpeed");
        }

        public void Enchanting_HasEnchantmentPower()
        {
            var result = RunGeneration("enchanting");
            var data = result.ItemData;
            Assert(data.ContainsKey("enchantmentPower"), "Enchanting item must have enchantmentPower");
        }

        // ====================================================================
        // Category mapping tests
        // ====================================================================

        public void Category_Smithing_IsEquipment()
        {
            var result = RunGeneration("smithing");
            AssertEqual("equipment", result.ItemData["category"].ToString(), "category");
        }

        public void Category_Alchemy_IsConsumable()
        {
            var result = RunGeneration("alchemy");
            AssertEqual("consumable", result.ItemData["category"].ToString(), "category");
        }

        public void Category_Refining_IsMaterial()
        {
            var result = RunGeneration("refining");
            AssertEqual("material", result.ItemData["category"].ToString(), "category");
        }

        // ====================================================================
        // Recipe input persistence tests
        // ====================================================================

        public void RecipeInputs_PreservedInResult()
        {
            var result = RunGeneration();
            AssertNotNull(result.RecipeInputs, "RecipeInputs");
            AssertEqual(2, result.RecipeInputs.Count, "RecipeInputs.Count");

            var first = result.RecipeInputs[0];
            AssertEqual("iron_ingot", first["materialId"].ToString(), "first.materialId");
            AssertEqual(3, Convert.ToInt32(first["qty"]), "first.qty");
        }

        public void StationTier_PreservedInResult()
        {
            var request = CreateTestRequest(stationTier: 3);
            var generator = new StubItemGenerator(new LoadingState(), new NotificationSystem());
            var result = generator.GenerateItemAsync(request).GetAwaiter().GetResult();
            AssertEqual(3, result.StationTier, "StationTier");
        }

        // ====================================================================
        // Notification integration tests
        // ====================================================================

        public void Notifications_ShowCalledOnGeneration()
        {
            var notifications = new NotificationSystem();
            var generator = new StubItemGenerator(new LoadingState(), notifications);
            var request = CreateTestRequest();

            int callCount = 0;
            notifications.OnNotificationShow += (msg, type, dur) => callCount++;

            generator.GenerateItemAsync(request).GetAwaiter().GetResult();

            // Should get at least 2 notifications: "Generating..." and "Created: ..."
            Assert(callCount >= 2,
                $"Expected at least 2 notification calls, got {callCount}");
        }

        // ====================================================================
        // LoadingState integration tests
        // ====================================================================

        public void LoadingState_StartedDuringGeneration()
        {
            var loadingState = new LoadingState();
            var generator = new StubItemGenerator(loadingState, new NotificationSystem());
            var request = CreateTestRequest();

            // After generation completes, loading state should have been started
            // (IsComplete will be true because Finish() was called)
            generator.GenerateItemAsync(request).GetAwaiter().GetResult();
            Assert(loadingState.IsComplete, "LoadingState should be in complete state after generation");
        }

        public void LoadingState_FinishedAfterGeneration()
        {
            var loadingState = new LoadingState();
            var generator = new StubItemGenerator(loadingState, new NotificationSystem());
            var request = CreateTestRequest();

            generator.GenerateItemAsync(request).GetAwaiter().GetResult();
            Assert(loadingState.IsComplete, "LoadingState.IsComplete should be true after generation");
            AssertEqual(1.0f, loadingState.Progress, "LoadingState.Progress");
        }

        // ====================================================================
        // GeneratedItem data structure tests
        // ====================================================================

        public void GeneratedItem_CreateSuccess_IsValid()
        {
            var item = GeneratedItem.CreateSuccess(
                new Dictionary<string, object> { ["itemId"] = "test" },
                "test_id", "Test Item", "smithing");
            Assert(item.IsValid, "CreateSuccess should produce valid item");
            Assert(item.Success, "CreateSuccess should have Success = true");
            Assert(!item.IsError, "CreateSuccess should not be error");
        }

        public void GeneratedItem_CreateError_IsNotValid()
        {
            var item = GeneratedItem.CreateError("smithing", "test error");
            Assert(!item.IsValid, "CreateError should produce invalid item");
            Assert(!item.Success, "CreateError should have Success = false");
            Assert(item.IsError, "CreateError should be error");
            AssertEqual("test error", item.Error, "Error message");
        }

        public void GeneratedItem_DefaultIsStubFalse()
        {
            var item = new GeneratedItem();
            Assert(!item.IsStub, "Default IsStub should be false");
        }
    }
}
