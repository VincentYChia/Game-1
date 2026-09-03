using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// ALCHEMY placement — an ORDERED sequence of reagent slots (tier 2 / 3 / 4 / 6). Order
/// matters: base → reagent → catalyst → … Select a material, left-click a slot to add
/// (same → qty++, different → replace), right-click to decrement. Matched by exact
/// position + quantity against the recipe's ingredient sequence.
/// </summary>
public partial class AlchemyBoard : PlacementBoard
{
    // The 2D sequence reads Base → Reagent → Catalyst → … ; beyond three it keeps
    // alternating and closes on a Finisher (interactive_crafting.py:362-366).
    private static readonly string[] Roles = { "Base", "Reagent", "Catalyst", "Reagent", "Catalyst", "Finisher" };
    private int _n = 2;
    private string?[] _mat = System.Array.Empty<string?>();
    private int[] _qty = System.Array.Empty<int>();

    public override void Setup(CombatWorld combat, string discipline, int tier)
    {
        _n = tier switch { 1 => 2, 2 => 3, 3 => 4, 4 => 6, _ => 2 };
        _mat = new string?[_n]; _qty = new int[_n];
        base.Setup(combat, discipline, tier);
    }

    public override void Clear() { System.Array.Clear(_mat); System.Array.Clear(_qty); QueueRedraw(); }

    private float SlotSize() => Mathf.Clamp(Mathf.Min((Size.X - 40f) / _n, Size.Y * 0.4f), 40f, 92f);

    private Rect2 SlotRect(int i)
    {
        var s = SlotSize();
        var span = s + 18f;
        var startX = Size.X * 0.5f - (_n - 1) * span * 0.5f;
        var y = Size.Y * 0.5f;
        return new Rect2(new Vector2(startX + i * span, y) - new Vector2(s, s) * 0.5f, new Vector2(s, s));
    }

    protected override void DrawBoard()
    {
        CraftFx.RoundRect(this, new Rect2(0, 0, Size.X, Size.Y), new Color(0.06f, 0.07f, 0.10f, 0.55f),
            new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.35f), 2, 12);
        var arrow = new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.4f);
        var font = GetThemeDefaultFont();
        for (var i = 0; i + 1 < _n; i++)
        {
            var a = SlotRect(i); var b = SlotRect(i + 1);
            DrawLine(new Vector2(a.Position.X + a.Size.X, a.Position.Y + a.Size.Y * 0.5f),
                     new Vector2(b.Position.X, b.Position.Y + b.Size.Y * 0.5f), arrow, 2f);
        }
        for (var i = 0; i < _n; i++)
        {
            var rect = SlotRect(i);
            var has = !string.IsNullOrEmpty(_mat[i]);
            if (!has && SelectedMaterialId is not null)
                CraftFx.Glow(this, rect.Position + rect.Size * 0.5f, rect.Size.X * 0.5f,
                    new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.14f), 3);
            CraftFx.RoundRect(this, rect,
                has ? new Color(0.15f, 0.16f, 0.21f) : new Color(0.10f, 0.11f, 0.15f, 0.75f),
                has ? RarityColor(_mat[i]!) : new Color(0.4f, 0.43f, 0.5f, 0.6f), has ? 2 : 1, 8);
            if (has) DrawOccupant(rect, _mat[i]!, _qty[i]);
            // step number + role label under each slot
            DrawString(font, rect.Position + new Vector2(0, -8),
                $"{i + 1}", HorizontalAlignment.Center, rect.Size.X, 13,
                new Color(1, 1, 1, 0.55f));
            DrawString(font, rect.Position + new Vector2(0, rect.Size.Y + 15),
                Roles[System.Math.Min(i, Roles.Length - 1)], HorizontalAlignment.Center, rect.Size.X, 13,
                new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.9f));
        }

        // culminating result flask
        var last = SlotRect(_n - 1);
        var rc = new Vector2(last.Position.X + last.Size.X + 26f, last.Position.Y + last.Size.Y * 0.5f);
        if (rc.X + 20f < Size.X)
        {
            DrawLine(new Vector2(last.Position.X + last.Size.X, rc.Y), new Vector2(rc.X - 16f, rc.Y),
                new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.4f), 2f);
            CraftFx.Glow(this, rc, 18f, new Color(Style.Glow.R, Style.Glow.G, Style.Glow.B, 0.35f), 3);
            DrawCircle(rc, 12f, new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.5f));
            DrawString(font, rc + new Vector2(-20, 30), "Elixir", HorizontalAlignment.Center, 40, 12,
                new Color(1, 1, 1, 0.5f));
        }
    }

    protected override void OnBoardInput(InputEvent e)
    {
        if (e is not InputEventMouseButton { Pressed: true } mb) return;
        for (var i = 0; i < _n; i++)
        {
            if (!SlotRect(i).HasPoint(mb.Position)) continue;
            if (mb.ButtonIndex == MouseButton.Right)
            {
                if (!string.IsNullOrEmpty(_mat[i])) { _qty[i]--; if (_qty[i] <= 0) { _mat[i] = null; _qty[i] = 0; } Changed(); }
                return;
            }
            if (mb.ButtonIndex == MouseButton.Left && SelectedMaterialId is { } id && CanPlace(id))
            {
                if (_mat[i] == id) _qty[i]++;
                else { _mat[i] = id; _qty[i] = 1; }
                CraftFx.Burst(this, SlotRect(i).Position + SlotRect(i).Size * 0.5f, RarityColor(id), 8, 90f, 0.4f, 3f, 120f);
                Changed();
            }
            return;
        }
    }

    public override void AutoLay(PlacementData data)
    {
        Clear();
        if (data.Ingredients is JsonArray arr)
            foreach (var n in arr)
            {
                if (n is not JsonObject o || MatId(o) is not { } id || string.IsNullOrEmpty(id)) continue;
                var slot = (o["slot"] is JsonValue sv && sv.TryGetValue<int>(out var s)) ? s - 1 : 0;
                if (slot >= 0 && slot < _n) { _mat[slot] = id; _qty[slot] = Qty(o); }
            }
        Changed();
    }

    public override Recipe? TryMatch()
    {
        var recipeDb = Combat.RecipeDb;
        var placementDb = Combat.PlacementDb;
        if (recipeDb is null || placementDb is null) return null;
        if (!recipeDb.RecipesByStation.TryGetValue("alchemy", out var list)) return null;
        if (_mat.All(string.IsNullOrEmpty)) return null;

        foreach (var rec in list.Where(x => x.StationTier <= Tier)
                     .OrderBy(x => x.StationTier).ThenBy(x => x.RecipeId))
        {
            var pd = placementDb.GetPlacement(rec.RecipeId);
            if (pd is null) continue;
            if (SequenceMatches(pd.Ingredients)) return rec;
        }
        return null;
    }

    public override bool HasPlacement() => _mat.Any(m => !string.IsNullOrEmpty(m));

    public override JsonObject Signature()
    {
        var sig = SigHead();
        var ing = new JsonArray();
        for (var i = 0; i < _n; i++)
            if (!string.IsNullOrEmpty(_mat[i]))
                ing.Add(new JsonObject { ["slot"] = i + 1, ["materialId"] = _mat[i], ["quantity"] = _qty[i] });
        sig["ingredients"] = ing;
        return sig;
    }

    private bool SequenceMatches(JsonNode ingredients)
    {
        var want = new (string? Mat, int Qty)[_n];
        if (ingredients is JsonArray arr)
            foreach (var n in arr)
            {
                if (n is not JsonObject o || MatId(o) is not { } id || string.IsNullOrEmpty(id)) continue;
                var slot = (o["slot"] is JsonValue sv && sv.TryGetValue<int>(out var s)) ? s - 1 : -1;
                if (slot >= 0 && slot < _n) want[slot] = (id, Qty(o));
            }
        for (var i = 0; i < _n; i++)
        {
            var mine = string.IsNullOrEmpty(_mat[i]) ? ((string?)null, 0) : (_mat[i], _qty[i]);
            if (mine.Item1 != want[i].Mat || (want[i].Mat is not null && mine.Item2 != want[i].Qty)) return false;
        }
        return true;
    }
}
