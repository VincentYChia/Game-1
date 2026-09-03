using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// REFINING placement — hub-and-spoke: CORE slot(s) in the center + SURROUNDING slots
/// on a ring (tier 1+2 / 1+4 / 2+5 / 3+6). Select a material, left-click a slot to add
/// (same material → qty++, different → replace), right-click to decrement. Matched
/// order-independently: the CORE multiset and the SURROUNDING multiset must each equal
/// the recipe's coreInputs / surroundingInputs.
/// </summary>
public partial class RefiningBoard : PlacementBoard
{
    private int _coreN = 1, _surrN = 2;
    private string?[] _coreMat = System.Array.Empty<string?>();
    private int[] _coreQty = System.Array.Empty<int>();
    private string?[] _surrMat = System.Array.Empty<string?>();
    private int[] _surrQty = System.Array.Empty<int>();

    public override void Setup(CombatWorld combat, string discipline, int tier)
    {
        (_coreN, _surrN) = tier switch
        {
            1 => (1, 2), 2 => (1, 4), 3 => (2, 5), 4 => (3, 6), _ => (1, 2),
        };
        _coreMat = new string?[_coreN]; _coreQty = new int[_coreN];
        _surrMat = new string?[_surrN]; _surrQty = new int[_surrN];
        base.Setup(combat, discipline, tier);
    }

    public override void Clear()
    {
        System.Array.Clear(_coreMat); System.Array.Clear(_coreQty);
        System.Array.Clear(_surrMat); System.Array.Clear(_surrQty);
        QueueRedraw();
    }

    private float SlotSize() => Mathf.Clamp(Mathf.Min(Size.X, Size.Y) * 0.15f, 40f, 86f);

    private List<(Rect2 Rect, bool Core, int Idx)> SlotRects()
    {
        var list = new List<(Rect2, bool, int)>();
        var s = SlotSize();
        var c = Size * 0.5f;
        // core: centered row
        var span = s + 12f;
        for (var i = 0; i < _coreN; i++)
        {
            var x = c.X + (i - (_coreN - 1) / 2f) * span;
            list.Add((Centered(new Vector2(x, c.Y), s), true, i));
        }
        // surrounding: ring
        var r = Mathf.Min(Size.X, Size.Y) * 0.34f;
        for (var i = 0; i < _surrN; i++)
        {
            var a = -Mathf.Pi / 2f + i * Mathf.Tau / _surrN;
            list.Add((Centered(c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r, s), false, i));
        }
        return list;
    }

    private static Rect2 Centered(Vector2 center, float size)
        => new(center - new Vector2(size, size) * 0.5f, new Vector2(size, size));

    protected override void DrawBoard()
    {
        CraftFx.RoundRect(this, new Rect2(0, 0, Size.X, Size.Y), new Color(0.06f, 0.07f, 0.10f, 0.55f),
            new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.35f), 2, 12);
        var c = Size * 0.5f;
        var spokes = new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.35f);
        foreach (var (rect, core, _) in SlotRects())
            if (!core) DrawLine(c, rect.Position + rect.Size * 0.5f, spokes, 2f);

        var font = GetThemeDefaultFont();
        foreach (var (rect, core, idx) in SlotRects())
        {
            var mat = core ? _coreMat[idx] : _surrMat[idx];
            var qty = core ? _coreQty[idx] : _surrQty[idx];
            var has = !string.IsNullOrEmpty(mat);
            if (!has && SelectedMaterialId is not null)
                CraftFx.Glow(this, rect.Position + rect.Size * 0.5f, rect.Size.X * 0.5f,
                    new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.14f), 3);
            CraftFx.RoundRect(this, rect,
                has ? new Color(0.15f, 0.16f, 0.21f) : new Color(0.10f, 0.11f, 0.15f, 0.75f),
                core ? Style.Accent : (has ? RarityColor(mat!) : new Color(0.4f, 0.43f, 0.5f, 0.6f)),
                core ? 3 : (has ? 2 : 1), 8);
            if (has) DrawOccupant(rect, mat!, qty);
            if (core)
                DrawString(font, rect.Position + new Vector2(0, -6), "CORE", HorizontalAlignment.Center,
                    rect.Size.X, 12, new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.9f));
        }
    }

    protected override void OnBoardInput(InputEvent e)
    {
        if (e is not InputEventMouseButton { Pressed: true } mb) return;
        foreach (var (rect, core, idx) in SlotRects())
        {
            if (!rect.HasPoint(mb.Position)) continue;
            var mats = core ? _coreMat : _surrMat;
            var qtys = core ? _coreQty : _surrQty;
            if (mb.ButtonIndex == MouseButton.Right)
            {
                if (!string.IsNullOrEmpty(mats[idx])) { qtys[idx]--; if (qtys[idx] <= 0) { mats[idx] = null; qtys[idx] = 0; } Changed(); }
                return;
            }
            if (mb.ButtonIndex == MouseButton.Left && SelectedMaterialId is { } id && CanPlace(id))
            {
                if (mats[idx] == id) qtys[idx]++;
                else { mats[idx] = id; qtys[idx] = 1; }
                CraftFx.Burst(this, rect.Position + rect.Size * 0.5f, RarityColor(id), 8, 90f, 0.4f, 3f, 120f);
                Changed();
            }
            return;
        }
    }

    public override void AutoLay(PlacementData data)
    {
        Clear();
        Fill(_coreMat, _coreQty, data.CoreInputs);
        Fill(_surrMat, _surrQty, data.SurroundingInputs);
        Changed();
    }

    private static void Fill(string?[] mat, int[] qty, JsonNode node)
    {
        if (node is not JsonArray arr) return;
        var i = 0;
        foreach (var n in arr)
        {
            if (i >= mat.Length) break;
            if (n is not JsonObject o || MatId(o) is not { } id || string.IsNullOrEmpty(id)) continue;
            mat[i] = id; qty[i] = Qty(o); i++;
        }
    }

    public override Recipe? TryMatch()
    {
        var recipeDb = Combat.RecipeDb;
        var placementDb = Combat.PlacementDb;
        if (recipeDb is null || placementDb is null) return null;
        if (!recipeDb.RecipesByStation.TryGetValue("refining", out var list)) return null;

        var core = ZoneMulti(_coreMat, _coreQty);
        var surr = ZoneMulti(_surrMat, _surrQty);
        if (core.Count == 0) return null;   // at least one core required

        foreach (var rec in list.Where(x => x.StationTier <= Tier)
                     .OrderBy(x => x.StationTier).ThenBy(x => x.RecipeId))
        {
            var pd = placementDb.GetPlacement(rec.RecipeId);
            if (pd is null) continue;
            if (DictEq(core, Multiset(pd.CoreInputs)) && DictEq(surr, Multiset(pd.SurroundingInputs)))
                return rec;
        }
        return null;
    }

    public override bool HasPlacement() =>
        _coreMat.Any(m => !string.IsNullOrEmpty(m)) || _surrMat.Any(m => !string.IsNullOrEmpty(m));

    public override JsonObject Signature()
    {
        var sig = SigHead();
        sig["coreInputs"] = ZoneArray(_coreMat, _coreQty);
        sig["surroundingInputs"] = ZoneArray(_surrMat, _surrQty);
        return sig;
    }

    private static JsonArray ZoneArray(string?[] mat, int[] qty)
    {
        var arr = new JsonArray();
        for (var i = 0; i < mat.Length; i++)
            if (!string.IsNullOrEmpty(mat[i]))
                arr.Add(new JsonObject { ["materialId"] = mat[i], ["quantity"] = qty[i] });
        return arr;
    }

    private static Dictionary<string, int> ZoneMulti(string?[] mat, int[] qty)
    {
        var d = new Dictionary<string, int>();
        for (var i = 0; i < mat.Length; i++)
            if (!string.IsNullOrEmpty(mat[i])) d[mat[i]!] = d.GetValueOrDefault(mat[i]!) + qty[i];
        return d;
    }
}
