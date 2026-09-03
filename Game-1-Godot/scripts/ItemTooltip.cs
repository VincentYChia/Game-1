using System.Text;
using System.Text.Json.Nodes;
using Game1.Core.Data;

namespace Game1.Godot;

/// <summary>
/// Builds the hover TOOLTIP text for any item — a basic card by default (name, kind, the
/// headline stat, crafted QUALITY, durability) and a full breakdown when advanced tooltips
/// are on (all stats, requirements, tags, enchantments, narrative). Used everywhere items
/// appear: the backpack, the paper-doll, the crafting recipe cards and material menu.
///
/// Crafted quality is read from the certified item's mutable Bonuses bag
/// (Bonuses["craft_quality"]), which the crafting screen stamps when a minigame craft
/// finishes — so a Masterwork blade reads "Masterwork" wherever you hover it.
/// </summary>
public static class ItemTooltip
{
    /// <summary>The quality a crafted equipment instance was made at (or null).</summary>
    public static string? Quality(EquipmentItem eq)
        => eq.Bonuses is JsonObject b && b["craft_quality"] is { } q ? q.GetValue<string>() : null;

    public static string ForEquipment(EquipmentItem eq)
    {
        var adv = UiPrefs.AdvancedTooltips;
        var sb = new StringBuilder();
        sb.Append(eq.Name);
        var q = Quality(eq);
        if (q is not null) sb.Append($"   ·   {q}");
        sb.Append('\n');
        sb.Append(Cap(eq.Rarity)).Append("  ").Append(Cap(eq.ResolveItemType())).Append($"  ·  T{(int)eq.Tier}");

        if (eq.Damage != (0, 0)) sb.Append($"\nDamage {eq.Damage.Min}–{eq.Damage.Max}");
        if (eq.Defense > 0) sb.Append($"\nDefense {eq.Defense}");
        sb.Append($"\nDurability {eq.DurabilityCurrent:0}/{eq.DurabilityMax}");
        if (eq.Enchantments.Count > 0)
            sb.Append($"\nEnchanted: {string.Join(", ", eq.Enchantments.ConvertAll(e => e["name"]?.GetValue<string>() ?? ""))}");

        if (adv)
        {
            sb.Append($"\n\nAttack speed {eq.AttackSpeed:0.##}   ·   Weight {eq.Weight:0.##}   ·   Range {eq.Range:0.##}");
            if (eq.ItemType == "tool") sb.Append($"\nEfficiency {eq.Efficiency:0.##}");
            var req = ReqLine(eq.Requirements);
            if (req.Length > 0) sb.Append($"\nRequires: {req}");
            if (eq.Tags.Count > 0) sb.Append($"\nTags: {string.Join(", ", eq.Tags)}");
        }
        else sb.Append("\n\n[detailed tooltips: off]");
        return sb.ToString();
    }

    public static string ForMaterial(MaterialDefinition m)
    {
        var adv = UiPrefs.AdvancedTooltips;
        var sb = new StringBuilder();
        sb.Append(m.Name).Append('\n');
        sb.Append(Cap(m.Rarity)).Append("  ").Append(Cap(m.Category)).Append($"  ·  T{(int)m.Tier}");
        if (adv)
        {
            if (!string.IsNullOrWhiteSpace(m.Narrative)) sb.Append($"\n\n{m.Narrative}");
            if (m.Tags is JsonArray ta && ta.Count > 0)
                sb.Append($"\nTags: {string.Join(", ", ta.OfType<JsonValue>().Select(v => v.ToString()))}");
        }
        return sb.ToString();
    }

    public static string ForStack(ItemStack stack, MaterialDatabase? matDb)
    {
        if (stack.EquipmentData is { } eq) return ForEquipment(eq);
        if (matDb?.GetMaterial(stack.ItemId) is { } m) return ForMaterial(m);
        return stack.ItemId;
    }

    private static string ReqLine(JsonObject req)
    {
        var parts = new List<string>();
        if (req["level"] is { } lvl) parts.Add($"Lv {lvl}");
        if (req["stats"] is JsonObject stats)
            foreach (var kv in stats) parts.Add($"{kv.Key.ToUpperInvariant()} {kv.Value}");
        return string.Join(", ", parts);
    }

    private static string Cap(string s)
        => string.IsNullOrEmpty(s) ? s : char.ToUpperInvariant(s[0]) + s[1..];
}
