using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// ENGINEERING placement — the 2D typed-slot CANVAS (interactive_crafting.py
/// InteractiveEngineeringUI). The available slot TYPES are gated by tier: T1/T2 expose
/// FRAME / FUNCTION / POWER; T3/T4 also unlock MODIFIER / UTILITY. Each type is a LANE
/// that holds a LIST of materials (a device can want several FRAME pieces, or one FRAME
/// + one FUNCTION + one POWER, etc.), and the whole canvas has a per-tier slot budget
/// (T1 3 · T2 5 · T3 5 · T4 7). Select a material, left-click a lane's ＋ to add it (or a
/// chip of the same material to stack), right-click a chip to remove. Matched
/// order-independently as a per-type multiset against the recipe's slots.
/// </summary>
public partial class EngineeringBoard : PlacementBoard
{
    private sealed class Chip { public string Id = ""; public int Qty; }

    private string[] _types = System.Array.Empty<string>();
    private readonly Dictionary<string, List<Chip>> _lanes = new();
    private int _budget = 3;   // total chips allowed across all lanes

    private static string[] TypesFor(int tier) => tier >= 3
        ? new[] { "FRAME", "FUNCTION", "POWER", "MODIFIER", "UTILITY" }
        : new[] { "FRAME", "FUNCTION", "POWER" };

    private static int BudgetFor(int tier) => tier switch { 1 => 3, 2 => 5, 3 => 5, 4 => 7, _ => 3 };

    public override void Setup(CombatWorld combat, string discipline, int tier)
    {
        _types = TypesFor(tier);
        _budget = BudgetFor(tier);
        _lanes.Clear();
        foreach (var t in _types) _lanes[t] = new List<Chip>();
        base.Setup(combat, discipline, tier);
    }

    public override void Clear()
    {
        foreach (var l in _lanes.Values) l.Clear();
        QueueRedraw();
    }

    public override bool HasPlacement() => _lanes.Values.Any(l => l.Count > 0);

    private int TotalChips() => _lanes.Values.Sum(l => l.Count);

    // ---- layout: vertically-centred typed BINS, chips stacked with a trailing ＋ ----
    private const float TopStrip = 60f;   // title + budget pips
    private const float HeaderH = 22f;
    private const float RowGap = 8f;

    private float LaneW() => (Size.X - 24f) / _types.Length;
    private float ChipH() => Mathf.Clamp(LaneW() * 0.56f, 44f, 74f);

    /// <summary>Rows a bin needs to show (existing chips + one add slot if budget remains).</summary>
    private int MaxRows()
    {
        var add = TotalChips() < _budget ? 1 : 0;
        var rows = 1;
        foreach (var t in _types) rows = System.Math.Max(rows, _lanes[t].Count + add);
        return rows;
    }

    private float BlockH() => HeaderH + MaxRows() * (ChipH() + RowGap);
    private float StartY()
    {
        var avail = System.Math.Max(60f, Size.Y - TopStrip);
        return TopStrip + System.Math.Max(6f, (avail - BlockH()) * 0.5f);
    }

    private Rect2 LaneRect(int i)
        => new(12f + i * LaneW() + 4f, StartY(), LaneW() - 8f, BlockH());

    private Rect2 SlotRect(int laneIdx, int chipIdx)
    {
        var lane = LaneRect(laneIdx);
        return new Rect2(lane.Position.X + 4f, lane.Position.Y + HeaderH + chipIdx * (ChipH() + RowGap),
            lane.Size.X - 8f, ChipH());
    }

    protected override void DrawBoard()
    {
        CraftFx.RoundRect(this, new Rect2(0, 0, Size.X, Size.Y), new Color(0.06f, 0.07f, 0.10f, 0.55f),
            new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.35f), 2, 12);
        var font = GetThemeDefaultFont();
        var accent = Style.Accent;
        var accentFaint = new Color(accent.R, accent.G, accent.B, 0.9f);
        var used = TotalChips();
        var full = used >= _budget;

        // ---- top strip: what's unlocked + how much budget is left ----
        DrawString(font, new Vector2(14, 24), $"Tier {Tier} · unlocked component lanes — use any mix",
            HorizontalAlignment.Left, Size.X - 28, 14, new Color(1, 1, 1, 0.72f));
        DrawString(font, new Vector2(14, 48), $"{used} / {_budget} components", HorizontalAlignment.Left,
            220, 13, accentFaint);
        var pipGap = 15f; var pipY = 44f;
        var pipX = Size.X - 16f - _budget * pipGap;
        for (var i = 0; i < _budget; i++)
        {
            var cp = new Vector2(pipX + i * pipGap + 5f, pipY);
            if (i < used) DrawCircle(cp, 5f, accent);
            else
            {
                DrawCircle(cp, 5f, new Color(accent.R, accent.G, accent.B, 0.16f));
                DrawArc(cp, 5f, 0, Mathf.Tau, 16, new Color(accent.R, accent.G, accent.B, 0.5f), 1f);
            }
        }

        // ---- the typed bins ----
        for (var i = 0; i < _types.Length; i++)
        {
            var lane = LaneRect(i);
            CraftFx.RoundRect(this, lane, new Color(0.09f, 0.10f, 0.14f, 0.55f),
                new Color(accent.R, accent.G, accent.B, 0.20f), 1, 8);
            DrawString(font, lane.Position + new Vector2(0, -6), _types[i],
                HorizontalAlignment.Center, lane.Size.X, 14, accentFaint);

            var chips = _lanes[_types[i]];
            for (var c = 0; c < chips.Count; c++)
            {
                var rect = SlotRect(i, c);
                CraftFx.RoundRect(this, rect, new Color(0.15f, 0.16f, 0.21f), RarityColor(chips[c].Id), 2, 8);
                DrawOccupant(rect, chips[c].Id, chips[c].Qty);
            }
            if (!full)
            {
                var add = SlotRect(i, chips.Count);
                var armed = SelectedMaterialId is not null;
                if (armed) CraftFx.Glow(this, add.Position + add.Size * 0.5f, add.Size.X * 0.4f,
                    new Color(accent.R, accent.G, accent.B, 0.12f), 3);
                CraftFx.RoundRect(this, add, new Color(0.10f, 0.11f, 0.15f, 0.5f),
                    new Color(0.5f, 0.55f, 0.7f, 0.6f), 1, 8);
                DrawString(font, add.Position + new Vector2(0, add.Size.Y * 0.6f),
                    armed ? "＋" : (chips.Count == 0 ? "optional" : "＋ add"),
                    HorizontalAlignment.Center, add.Size.X, armed ? 22 : 12, new Color(1, 1, 1, 0.45f));
            }
        }
        DrawString(font, new Vector2(14, Size.Y - 8),
            "select a material, then click a lane's ＋ · right-click a chip to remove",
            HorizontalAlignment.Left, Size.X - 28, 12, new Color(1, 1, 1, 0.4f));
    }

    protected override void OnBoardInput(InputEvent e)
    {
        if (e is not InputEventMouseButton { Pressed: true } mb) return;
        for (var i = 0; i < _types.Length; i++)
        {
            var chips = _lanes[_types[i]];
            // hit an existing chip?
            for (var c = 0; c < chips.Count; c++)
            {
                if (!SlotRect(i, c).HasPoint(mb.Position)) continue;
                if (mb.ButtonIndex == MouseButton.Right)
                {
                    chips[c].Qty--;
                    if (chips[c].Qty <= 0) chips.RemoveAt(c);
                    Changed();
                    return;
                }
                if (mb.ButtonIndex == MouseButton.Left && SelectedMaterialId is { } sid && CanPlace(sid))
                {
                    if (chips[c].Id == sid) chips[c].Qty++;   // stack
                    Changed();
                    return;
                }
                return;
            }
            // hit the trailing add slot?
            if (mb.ButtonIndex == MouseButton.Left && SelectedMaterialId is { } id && CanPlace(id)
                && TotalChips() < _budget && SlotRect(i, chips.Count).HasPoint(mb.Position))
            {
                chips.Add(new Chip { Id = id, Qty = 1 });
                CraftFx.Burst(this, SlotRect(i, chips.Count - 1).Position + SlotRect(i, chips.Count - 1).Size * 0.5f,
                    RarityColor(id), 8, 90f, 0.4f, 3f, 120f);
                Changed();
                return;
            }
        }
    }

    public override void AutoLay(PlacementData data)
    {
        Clear();
        if (data.Slots is JsonArray arr)
            foreach (var n in arr)
            {
                if (n is not JsonObject o || MatId(o) is not { } id || string.IsNullOrEmpty(id)) continue;
                var type = o["type"]?.GetValue<string>() ?? "";
                if (!_lanes.TryGetValue(type, out var lane)) continue;
                var existing = lane.FirstOrDefault(ch => ch.Id == id);
                if (existing is not null) existing.Qty += Qty(o);
                else lane.Add(new Chip { Id = id, Qty = Qty(o) });
            }
        Changed();
    }

    public override Recipe? TryMatch()
    {
        var recipeDb = Combat.RecipeDb;
        var placementDb = Combat.PlacementDb;
        if (recipeDb is null || placementDb is null) return null;
        if (!recipeDb.RecipesByStation.TryGetValue("engineering", out var list)) return null;
        var mine = LaneMap();
        if (mine.Count == 0) return null;

        foreach (var rec in list.Where(x => x.StationTier <= Tier)
                     .OrderBy(x => x.StationTier).ThenBy(x => x.RecipeId))
        {
            var pd = placementDb.GetPlacement(rec.RecipeId);
            if (pd is null) continue;
            if (TypeMapEquals(mine, RecipeTypeMap(pd.Slots))) return rec;
        }
        return null;
    }

    public override JsonObject Signature()
    {
        var sig = SigHead();
        var slots = new JsonArray();
        foreach (var t in _types)
            foreach (var ch in _lanes[t])
                slots.Add(new JsonObject { ["type"] = t, ["materialId"] = ch.Id, ["quantity"] = ch.Qty });
        sig["slots"] = slots;
        return sig;
    }

    // ---- per-type multiset (same material within a lane merges) ----
    private Dictionary<string, Dictionary<string, int>> LaneMap()
    {
        var d = new Dictionary<string, Dictionary<string, int>>();
        foreach (var t in _types)
        {
            if (_lanes[t].Count == 0) continue;
            var inner = new Dictionary<string, int>();
            foreach (var ch in _lanes[t]) inner[ch.Id] = inner.GetValueOrDefault(ch.Id) + ch.Qty;
            d[t] = inner;
        }
        return d;
    }

    private static Dictionary<string, Dictionary<string, int>> RecipeTypeMap(JsonNode slots)
    {
        var d = new Dictionary<string, Dictionary<string, int>>();
        if (slots is JsonArray arr)
            foreach (var n in arr)
            {
                if (n is not JsonObject o || MatId(o) is not { } id || string.IsNullOrEmpty(id)) continue;
                var type = o["type"]?.GetValue<string>() ?? "";
                if (!d.TryGetValue(type, out var inner)) d[type] = inner = new Dictionary<string, int>();
                inner[id] = inner.GetValueOrDefault(id) + Qty(o);
            }
        return d;
    }

    private static bool TypeMapEquals(Dictionary<string, Dictionary<string, int>> a,
                                      Dictionary<string, Dictionary<string, int>> b)
    {
        if (a.Count != b.Count) return false;
        foreach (var kv in a)
            if (!b.TryGetValue(kv.Key, out var inner) || !DictEq(kv.Value, inner)) return false;
        return true;
    }
}
