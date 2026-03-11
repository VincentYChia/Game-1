// Game1.Data.Interfaces.IEnchantmentValidator
// Phase: 1 - Foundation
// Interface for enchantment applicability validation. Replaces Python's dynamic import
// of EnchantingTagProcessor.can_apply_to_item(). Full implementation in Phase 4.

using System.Collections.Generic;

namespace Game1.Data.Interfaces
{
    /// <summary>
    /// Validates whether an enchantment can be applied to a specific item type.
    /// Phase 1 provides a stub that always returns (true, "OK").
    /// Phase 4 provides the full tag-based implementation.
    /// </summary>
    public interface IEnchantmentValidator
    {
        (bool CanApply, string Reason) CanApplyToItem(List<string> tags, string itemType);
    }

    /// <summary>
    /// Stub implementation that always allows enchantment application.
    /// Will be replaced by the real EnchantingTagProcessor in Phase 4.
    /// </summary>
    public class StubEnchantmentValidator : IEnchantmentValidator
    {
        public (bool CanApply, string Reason) CanApplyToItem(List<string> tags, string itemType)
        {
            return (true, "OK");
        }
    }
}
