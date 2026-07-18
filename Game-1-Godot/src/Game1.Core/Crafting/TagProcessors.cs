namespace Game1.Core.Crafting;

/// <summary>
/// Ports of core/crafting_tag_processor.py (the pieces the data layer needs:
/// slot inference + enchant applicability). The remaining processors
/// (alchemy/refining/engineering) port with the crafting phase (P6).
/// </summary>
public static class SmithingTagProcessor
{
    // crafting_tag_processor.py:30-36
    private static readonly Dictionary<string, string?> SlotTags = new()
    {
        ["weapon"] = "mainHand", ["tool"] = null, ["armor"] = null,
        ["shield"] = "offHand", ["accessory"] = "accessory",
    };

    // :39-44
    private static readonly Dictionary<string, string> ToolSlotMap = new()
    {
        ["pickaxe"] = "pickaxe", ["axe"] = "axe", ["shovel"] = "tool", ["hoe"] = "tool",
    };

    // :47-53
    private static readonly Dictionary<string, string> ArmorSlotMap = new()
    {
        ["helmet"] = "helmet", ["chestplate"] = "chestplate",
        ["leggings"] = "leggings", ["boots"] = "boots", ["gauntlets"] = "gauntlets",
    };

    // :56-82 — armor sub-types first, then tools, then generic (null-valued
    // generic tags fall through)
    public static string? GetEquipmentSlot(IReadOnlyList<string> recipeTags)
    {
        foreach (var tag in recipeTags)
            if (ArmorSlotMap.TryGetValue(tag, out var armorSlot))
                return armorSlot;
        foreach (var tag in recipeTags)
            if (ToolSlotMap.TryGetValue(tag, out var toolSlot))
                return toolSlot;
        foreach (var tag in recipeTags)
            if (SlotTags.TryGetValue(tag, out var slot) && slot is not null)
                return slot;
        return null;
    }
}

public static class EnchantingTagProcessor
{
    // crafting_tag_processor.py:190-195
    private static readonly Dictionary<string, string[]> RuleTags = new()
    {
        ["universal"] = new[] { "weapon", "armor", "tool" },
        ["weapon"] = new[] { "weapon" },
        ["armor"] = new[] { "armor" },
        ["tool"] = new[] { "tool" },
    };

    // :197-213 — first rule tag wins; default universal
    public static string[] GetApplicableItemTypes(IReadOnlyList<string> recipeTags)
    {
        foreach (var tag in recipeTags)
            if (RuleTags.TryGetValue(tag, out var types))
                return types;
        return RuleTags["universal"];
    }

    // :215-232
    public static (bool Ok, string Reason) CanApplyToItem(
        IReadOnlyList<string> recipeTags, string itemType) =>
        GetApplicableItemTypes(recipeTags).Contains(itemType)
            ? (true, "OK")
            : (false, $"Enchantment not applicable to {itemType} items");
}
