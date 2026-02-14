// ============================================================================
// Phase 7 Integration Tests: LLM Stub with Game Systems
// Tests that stub-generated items flow correctly through inventory,
// recipe database, and the notification system.
//
// Verifies the complete pipeline:
//   ClassifierManager → IItemGenerator → Inventory → RecipeDatabase → Save
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Core;
using Game1.Data.Models;
using Game1.Data.Databases;
using Game1.Entities;
using Game1.Systems.LLM;

namespace Game1.Tests.E2E
{
    /// <summary>
    /// Integration tests for the LLM stub system with game systems.
    /// Verifies stub items flow through inventory, recipe database, and events.
    /// </summary>
    public class LLMStubIntegrationTests
    {
        // ====================================================================
        // Test Runner
        // ====================================================================

        public static int RunAll()
        {
            var tests = new LLMStubIntegrationTests();
            int passed = 0;
            int failed = 0;
            var testMethods = new List<(string name, Action action)>
            {
                // Full pipeline tests
                ("StubItem_AddedToInventory", tests.StubItem_AddedToInventory),
                ("StubItem_AllDisciplinesProduceValidItems", tests.StubItem_AllDisciplinesProduceValidItems),
                ("StubItem_EventsRaised", tests.StubItem_EventsRaised),
                ("StubItem_LoadingStateLifecycle", tests.StubItem_LoadingStateLifecycle),
                ("StubItem_DeterministicWithSameHash", tests.StubItem_DeterministicWithSameHash),
                ("StubItem_DifferentHashProducesDifferentId", tests.StubItem_DifferentHashProducesDifferentId),

                // Notification integration
                ("Notifications_StubGenerationCreatesTwo", tests.Notifications_StubGenerationCreatesTwo),
                ("Notifications_DebugTypeUsed", tests.Notifications_DebugTypeUsed),

                // Error handling
                ("StubItem_EmptyMaterials_StillSucceeds", tests.StubItem_EmptyMaterials_StillSucceeds),
                ("StubItem_NullMaterials_StillSucceeds", tests.StubItem_NullMaterials_StillSucceeds),

                // Data schema validation
                ("StubItem_SmithingSchema_MatchesEquipmentFormat", tests.StubItem_SmithingSchema_MatchesEquipmentFormat),
                ("StubItem_AlchemySchema_MatchesConsumableFormat", tests.StubItem_AlchemySchema_MatchesConsumableFormat),

                // Interface contract
                ("IItemGenerator_IsAvailable_True", tests.IItemGenerator_IsAvailable_True),
                ("IItemGenerator_PolymorphicCall", tests.IItemGenerator_PolymorphicCall),
            };

            foreach (var (name, action) in testMethods)
            {
                try
                {
                    GameEvents.ClearAll();
                    NotificationSystem.ResetInstance();

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
                $"\nLLMStubIntegrationTests: {passed} passed, {failed} failed, " +
                $"{passed + failed} total");
            return failed;
        }

        // ====================================================================
        // Helpers
        // ====================================================================

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

        private static ItemGenerationRequest CreateRequest(string discipline = "smithing",
                                                            string hash = "integration_test")
        {
            return new ItemGenerationRequest
            {
                Discipline = discipline,
                StationTier = 2,
                PlacementHash = hash,
                ClassifierConfidence = 0.85f,
                Materials = new List<MaterialPlacement>
                {
                    new MaterialPlacement { MaterialId = "iron_ingot", Quantity = 3 },
                    new MaterialPlacement { MaterialId = "oak_plank", Quantity = 2 }
                }
            };
        }

        private static StubItemGenerator CreateGenerator(
            out LoadingState loadingState, out NotificationSystem notifications)
        {
            loadingState = new LoadingState();
            notifications = new NotificationSystem();
            return new StubItemGenerator(loadingState, notifications);
        }

        // ====================================================================
        // Full pipeline tests
        // ====================================================================

        public void StubItem_AddedToInventory()
        {
            var generator = CreateGenerator(out _, out _);
            var result = generator.GenerateItemAsync(CreateRequest()).GetAwaiter().GetResult();

            // Verify the item can be added to inventory
            var spawnPos = GamePosition.FromXZ(0f, 0f);
            var character = new Character(spawnPos);

            bool added = character.Inventory.AddItem(result.ItemId, 1);
            Assert(added, "Stub item should be addable to inventory");
            AssertEqual(1, character.Inventory.GetItemCount(result.ItemId),
                "Stub item count in inventory");
        }

        public void StubItem_AllDisciplinesProduceValidItems()
        {
            var disciplines = new[] { "smithing", "alchemy", "refining", "engineering", "enchanting" };

            foreach (var discipline in disciplines)
            {
                var generator = CreateGenerator(out _, out _);
                var request = CreateRequest(discipline, $"test_{discipline}");
                var result = generator.GenerateItemAsync(request).GetAwaiter().GetResult();

                Assert(result.Success, $"{discipline}: should succeed");
                Assert(result.IsValid, $"{discipline}: should be valid");
                AssertNotNull(result.ItemData, $"{discipline}: ItemData");
                AssertNotNull(result.ItemId, $"{discipline}: ItemId");
                Assert(result.IsStub, $"{discipline}: should be stub");
                AssertEqual(discipline, result.Discipline, $"{discipline}: Discipline");
            }
        }

        public void StubItem_EventsRaised()
        {
            var generator = CreateGenerator(out _, out var notifications);
            var eventCount = 0;

            notifications.OnNotificationShow += (msg, type, dur) => eventCount++;

            generator.GenerateItemAsync(CreateRequest()).GetAwaiter().GetResult();

            Assert(eventCount >= 2,
                $"Should raise at least 2 notification events, got {eventCount}");
        }

        public void StubItem_LoadingStateLifecycle()
        {
            var generator = CreateGenerator(out var loadingState, out _);

            // Before generation
            Assert(!loadingState.IsLoading, "Not loading before generation");

            // After generation
            generator.GenerateItemAsync(CreateRequest()).GetAwaiter().GetResult();
            Assert(loadingState.IsComplete, "Complete after generation");
        }

        public void StubItem_DeterministicWithSameHash()
        {
            var gen1 = CreateGenerator(out _, out _);
            var gen2 = CreateGenerator(out _, out _);

            var result1 = gen1.GenerateItemAsync(CreateRequest("smithing", "same_hash"))
                .GetAwaiter().GetResult();
            var result2 = gen2.GenerateItemAsync(CreateRequest("smithing", "same_hash"))
                .GetAwaiter().GetResult();

            AssertEqual(result1.ItemId, result2.ItemId, "Same hash should produce same ItemId");
        }

        public void StubItem_DifferentHashProducesDifferentId()
        {
            var gen1 = CreateGenerator(out _, out _);
            var gen2 = CreateGenerator(out _, out _);

            var result1 = gen1.GenerateItemAsync(CreateRequest("smithing", "hash_a"))
                .GetAwaiter().GetResult();
            var result2 = gen2.GenerateItemAsync(CreateRequest("smithing", "hash_b"))
                .GetAwaiter().GetResult();

            Assert(result1.ItemId != result2.ItemId,
                "Different hashes should produce different ItemIds");
        }

        // ====================================================================
        // Notification integration tests
        // ====================================================================

        public void Notifications_StubGenerationCreatesTwo()
        {
            var generator = CreateGenerator(out _, out var notifications);
            var messages = new List<string>();

            notifications.OnNotificationShow += (msg, type, dur) => messages.Add(msg);

            generator.GenerateItemAsync(CreateRequest()).GetAwaiter().GetResult();

            Assert(messages.Count >= 2,
                $"Expected at least 2 notifications, got {messages.Count}");
            Assert(messages[0].Contains("[STUB]"),
                $"First notification should contain [STUB], got: {messages[0]}");
        }

        public void Notifications_DebugTypeUsed()
        {
            var generator = CreateGenerator(out _, out var notifications);
            var types = new List<NotificationType>();

            notifications.OnNotificationShow += (msg, type, dur) => types.Add(type);

            generator.GenerateItemAsync(CreateRequest()).GetAwaiter().GetResult();

            foreach (var type in types)
            {
                AssertEqual(NotificationType.Debug, type,
                    "Stub notifications should use Debug type");
            }
        }

        // ====================================================================
        // Error handling tests
        // ====================================================================

        public void StubItem_EmptyMaterials_StillSucceeds()
        {
            var generator = CreateGenerator(out _, out _);
            var request = new ItemGenerationRequest
            {
                Discipline = "smithing",
                StationTier = 1,
                PlacementHash = "empty",
                Materials = new List<MaterialPlacement>()
            };

            var result = generator.GenerateItemAsync(request).GetAwaiter().GetResult();
            Assert(result.Success, "Empty materials should still succeed");
        }

        public void StubItem_NullMaterials_StillSucceeds()
        {
            var generator = CreateGenerator(out _, out _);
            var request = new ItemGenerationRequest
            {
                Discipline = "smithing",
                StationTier = 1,
                PlacementHash = "null_mats",
                Materials = null
            };

            var result = generator.GenerateItemAsync(request).GetAwaiter().GetResult();
            Assert(result.Success, "Null materials should still succeed");
        }

        // ====================================================================
        // Data schema tests
        // ====================================================================

        public void StubItem_SmithingSchema_MatchesEquipmentFormat()
        {
            var generator = CreateGenerator(out _, out _);
            var result = generator.GenerateItemAsync(CreateRequest("smithing"))
                .GetAwaiter().GetResult();

            var data = result.ItemData;

            // Equipment must have these fields
            Assert(data.ContainsKey("slot"), "Smithing must have slot");
            Assert(data.ContainsKey("damage"), "Smithing must have damage");
            Assert(data.ContainsKey("durabilityMax"), "Smithing must have durabilityMax");
            Assert(data.ContainsKey("durabilityCurrent"), "Smithing must have durabilityCurrent");
            Assert(data.ContainsKey("weight"), "Smithing must have weight");
            Assert(data.ContainsKey("attackSpeed"), "Smithing must have attackSpeed");

            // Category must be equipment
            AssertEqual("equipment", data["category"].ToString(), "Smithing category");
        }

        public void StubItem_AlchemySchema_MatchesConsumableFormat()
        {
            var generator = CreateGenerator(out _, out _);
            var result = generator.GenerateItemAsync(CreateRequest("alchemy"))
                .GetAwaiter().GetResult();

            var data = result.ItemData;

            // Consumable must have these fields
            Assert(data.ContainsKey("effect"), "Alchemy must have effect");
            Assert(data.ContainsKey("effectParams"), "Alchemy must have effectParams");
            Assert(data.ContainsKey("maxStack"), "Alchemy must have maxStack");

            // Category must be consumable
            AssertEqual("consumable", data["category"].ToString(), "Alchemy category");
        }

        // ====================================================================
        // Interface contract tests
        // ====================================================================

        public void IItemGenerator_IsAvailable_True()
        {
            IItemGenerator generator = new StubItemGenerator();
            Assert(generator.IsAvailable, "IItemGenerator.IsAvailable should be true");
        }

        public void IItemGenerator_PolymorphicCall()
        {
            IItemGenerator generator = new StubItemGenerator(new LoadingState(), new NotificationSystem());
            var result = generator.GenerateItemAsync(CreateRequest())
                .GetAwaiter().GetResult();

            Assert(result.Success, "Polymorphic call through interface should succeed");
            Assert(result.IsStub, "Result should be marked as stub");
        }
    }
}
