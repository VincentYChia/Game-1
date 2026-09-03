using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Base of the discipline PLACEMENT BOARD — the real 2D crafting interface reborn in
/// 3D: the tier-standard structure (grid / hub-spoke / sequence / typed slots / vertex
/// grid) is ALWAYS shown in full, the player selects a material in the palette then
/// places it into a cell/slot, and the arrangement is matched live against the recipe
/// PLACEMENT TEMPLATES (placements.JSON via Core PlacementDatabase). Placement decides
/// WHICH recipe; the minigame decides quality. The board is pure selection — it never
/// mutates the inventory; the certified CraftRecipe/ConsumeMaterials do that once.
/// </summary>
public abstract partial class PlacementBoard : Control
{
    protected CombatWorld Combat = null!;
    protected string Discipline = "smithing";
    protected int Tier = 1;
    protected DisciplineStyle Style;
    protected string? SelectedMaterialId;   // set by the palette
    public System.Action? OnPlacementChanged;   // workbench re-runs match + availability

    public override void _Ready()
    {
        MouseFilter = MouseFilterEnum.Stop;
        Draw += DrawBoard;
        GuiInput += OnBoardInput;
    }

    public virtual void Setup(CombatWorld combat, string discipline, int tier)
    {
        Combat = combat; Discipline = discipline; Tier = tier;
        Style = CraftStyle.Get(discipline);
        Clear();
        QueueRedraw();
    }

    public void SetSelected(string? id) { SelectedMaterialId = id; QueueRedraw(); }

    /// <summary>Wipe all placements (no inventory effect — nothing was borrowed).</summary>
    public abstract void Clear();

    /// <summary>CLICK-TO-FILL: lay a known recipe's canonical placement onto the board.</summary>
    public abstract void AutoLay(PlacementData data);

    /// <summary>The recipe whose template equals the current placement, or null.</summary>
    public abstract Recipe? TryMatch();

    /// <summary>True if the player has placed anything (gates craft / discovery).</summary>
    public abstract bool HasPlacement();

    /// <summary>A discipline-tagged JSON snapshot of the current placement — the exact
    /// shape the invention sidecar + the invalid-placement cache consume (it mirrors the
    /// per-discipline placements.JSON schema: grid / core+surrounding / ingredients /
    /// slots / shapes+vertices).</summary>
    public abstract JsonObject Signature();

    protected abstract void DrawBoard();
    protected abstract void OnBoardInput(InputEvent e);

    /// <summary>{discipline, stationTier} — the head every Signature() shares.</summary>
    protected JsonObject SigHead() => new() { ["discipline"] = Discipline, ["stationTier"] = Tier };

    /// <summary>A {materialId, quantity} row for a Signature() array.</summary>
    protected static JsonObject Row(string id, int qty) => new() { ["materialId"] = id, ["quantity"] = qty };

    /// <summary>Redraw + notify the workbench that the placement changed.</summary>
    protected void Changed() { QueueRedraw(); OnPlacementChanged?.Invoke(); }

    // ---- shared helpers ----
    protected Texture2D? Icon(string id) => IconCache.Get(Combat.MaterialDb?.GetMaterial(id)?.IconPath);

    protected int InvCount(string id) => Combat.Pc?.Inventory.GetItemCount(id) ?? 0;

    /// <summary>Can this material be placed (owned, or F1 debug infinite)?</summary>
    protected bool CanPlace(string id) =>
        (Combat.Pc?.Inventory.DebugInfiniteMaterials ?? false) || InvCount(id) > 0;

    protected Color RarityColor(string id)
    {
        var rar = Combat.MaterialDb?.GetMaterial(id)?.Rarity ?? "common";
        return UiTheme.Rarity.GetValueOrDefault(rar, UiTheme.Rarity["common"]);
    }

    /// <summary>Tolerant qty read ("quantity" canonical, "qty" fallback).</summary>
    protected static int Qty(JsonObject o)
    {
        if ((o["quantity"] ?? o["qty"]) is JsonValue v)
        {
            if (v.TryGetValue<int>(out var iv)) return iv;
            if (v.TryGetValue<double>(out var dv)) return (int)dv;
        }
        return 1;
    }

    protected static string? MatId(JsonObject o) => o["materialId"]?.GetValue<string>();

    /// <summary>Parse a [{materialId, quantity}] array into a {matId: totalQty} multiset.</summary>
    protected static Dictionary<string, int> Multiset(JsonNode? node)
    {
        var d = new Dictionary<string, int>();
        if (node is JsonArray a)
            foreach (var n in a)
                if (n is JsonObject o && MatId(o) is { } id && !string.IsNullOrEmpty(id))
                    d[id] = d.GetValueOrDefault(id) + Qty(o);
        return d;
    }

    protected static bool DictEq(Dictionary<string, int> a, Dictionary<string, int> b)
    {
        if (a.Count != b.Count) return false;
        foreach (var kv in a)
            if (!b.TryGetValue(kv.Key, out var v) || v != kv.Value) return false;
        return true;
    }

    /// <summary>Draw a material icon (or a lettered fallback) filling a slot rect.</summary>
    protected void DrawOccupant(Rect2 rect, string id, int qty)
    {
        var pad = rect.Size.X * 0.12f;
        var inner = new Rect2(rect.Position + new Vector2(pad, pad), rect.Size - new Vector2(pad * 2, pad * 2));
        var tex = Icon(id);
        if (tex is not null) DrawTextureRect(tex, inner, false);
        else
        {
            var nm = Combat.MaterialDb?.GetMaterial(id)?.Name ?? id;
            DrawString(GetThemeDefaultFont(), rect.Position + new Vector2(6, rect.Size.Y * 0.6f),
                nm[..System.Math.Min(3, nm.Length)], HorizontalAlignment.Left, rect.Size.X, 14, Colors.White);
        }
        if (qty > 1)
            DrawString(GetThemeDefaultFont(), rect.Position + new Vector2(rect.Size.X - 22, rect.Size.Y - 5),
                $"×{qty}", HorizontalAlignment.Left, -1, 13, Colors.White);
    }
}
