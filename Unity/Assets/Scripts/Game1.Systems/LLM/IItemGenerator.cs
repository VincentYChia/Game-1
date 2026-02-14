// ============================================================================
// Game1.Systems.LLM.IItemGenerator
// Migrated from: systems/llm_item_generator.py (LLMItemGenerator interface)
// Migration phase: 7
// Date: 2026-02-14
//
// Contract for item generation from validated crafting placements.
// The Python implementation uses Claude API via AnthropicBackend.
// During migration, StubItemGenerator provides placeholder items.
// Future implementation will restore full LLM generation.
// ============================================================================

using System.Threading.Tasks;

namespace Game1.Systems.LLM
{
    /// <summary>
    /// Contract for item generation from validated crafting placements.
    ///
    /// Implementations:
    ///   - StubItemGenerator: Placeholder items during migration (Phase 7)
    ///   - Future: AnthropicItemGenerator with real Claude API calls
    ///
    /// Must be safe to call from a background thread.
    /// </summary>
    public interface IItemGenerator
    {
        /// <summary>
        /// Generate a new item definition from a validated crafting placement.
        /// Returns a GeneratedItem with either valid item data or an error.
        /// Must be safe to call from a background thread.
        /// </summary>
        Task<GeneratedItem> GenerateItemAsync(ItemGenerationRequest request);

        /// <summary>
        /// Whether the generator is available and ready to produce items.
        /// StubItemGenerator always returns true.
        /// A real LLM implementation would check API key availability.
        /// </summary>
        bool IsAvailable { get; }
    }
}
