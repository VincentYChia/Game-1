using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// SMITHING placement — the tier-sized anvil GRID (T1 3×3, T2 5×5, T3 7×7, T4 9×9),
/// always shown in full. Select a material, left-click a cell to forge it in,
/// right-click to remove. The arrangement is matched (translation-invariant) against
/// each recipe's placementMap {"row,col": materialId}; a lower-tier recipe still
/// matches on a bigger grid (bounding-box normalization).
/// </summary>
public partial class SmithingBoard : PlacementBoard
{
    private int _n = 3;
    private readonly Dictionary<(int R, int C), string> _cells = new();

    public override void Setup(CombatWorld combat, string discipline, int tier)
    {
        _n = tier switch { 1 => 3, 2 => 5, 3 => 7, 4 => 9, _ => 3 };
        base.Setup(combat, discipline, tier);
    }

    public override void Clear() { _cells.Clear(); QueueRedraw(); }

    private (float Cell, float Ox, float Oy) Layout()
    {
        var size = Size;
        var cell = Mathf.Min((size.X - 28f) / _n, (size.Y - 28f) / _n);
        cell = Mathf.Max(24f, cell);
        var ox = (size.X - _n * cell) * 0.5f;
        var oy = (size.Y - _n * cell) * 0.5f;
        return (cell, ox, oy);
    }

    private Vector2 CellCenter(int r, int c)
    {
        var (cell, ox, oy) = Layout();
        return new Vector2(ox + (c - 1) * cell + cell * 0.5f, oy + (r - 1) * cell + cell * 0.5f);
    }

    protected override void DrawBoard()
    {
        var size = Size;
        CraftFx.RoundRect(this, new Rect2(0, 0, size.X, size.Y), new Color(0.06f, 0.07f, 0.10f, 0.55f),
            new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.35f), 2, 12);
        var (cell, ox, oy) = Layout();
        var showTargets = SelectedMaterialId is not null;
        for (var r = 1; r <= _n; r++)
            for (var c = 1; c <= _n; c++)
            {
                var rect = new Rect2(ox + (c - 1) * cell + 2, oy + (r - 1) * cell + 2, cell - 4, cell - 4);
                var has = _cells.TryGetValue((r, c), out var mid);
                if (!has && showTargets)
                    CraftFx.Glow(this, rect.Position + rect.Size * 0.5f, cell * 0.34f,
                        new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.14f), 3);
                CraftFx.RoundRect(this, rect,
                    has ? new Color(0.15f, 0.16f, 0.21f) : new Color(0.10f, 0.11f, 0.15f, 0.7f),
                    has ? RarityColor(mid!) : new Color(0.4f, 0.43f, 0.5f, 0.55f), has ? 2 : 1, 6);
                if (has) DrawOccupant(rect, mid!, 1);
            }
    }

    protected override void OnBoardInput(InputEvent e)
    {
        if (e is not InputEventMouseButton { Pressed: true } mb) return;
        var (cell, ox, oy) = Layout();
        var c = (int)Mathf.Floor((mb.Position.X - ox) / cell) + 1;
        var r = (int)Mathf.Floor((mb.Position.Y - oy) / cell) + 1;
        if (r < 1 || r > _n || c < 1 || c > _n) return;

        if (mb.ButtonIndex == MouseButton.Right)
        {
            if (_cells.Remove((r, c))) Changed();
            return;
        }
        if (mb.ButtonIndex == MouseButton.Left && SelectedMaterialId is { } id && CanPlace(id))
        {
            _cells[(r, c)] = id;
            CraftFx.Burst(this, CellCenter(r, c), RarityColor(id), 8, 90f, 0.4f, 3f, 120f);
            Changed();
        }
    }

    public override void AutoLay(PlacementData data)
    {
        _cells.Clear();
        if (data.PlacementMap is JsonObject map)
        {
            // parse the recipe's raw cells, then CENTER its bounding box in the tier grid
            // (recipes are authored top-left at 1,1; a 3×3 pattern should sit centred on a
            // 9×9 T4 grid, not in the corner). Matching stays translation-invariant.
            var raw = new Dictionary<(int R, int C), string>();
            foreach (var kv in map)
            {
                var cell = ParseCell(kv.Key);
                var mid = kv.Value?.GetValue<string>();
                if (cell is { } rc && !string.IsNullOrEmpty(mid)) raw[rc] = mid!;
            }
            if (raw.Count > 0)
            {
                int minR = raw.Keys.Min(k => k.R), maxR = raw.Keys.Max(k => k.R);
                int minC = raw.Keys.Min(k => k.C), maxC = raw.Keys.Max(k => k.C);
                var rOff = (_n - (maxR - minR + 1)) / 2 + 1 - minR;
                var cOff = (_n - (maxC - minC + 1)) / 2 + 1 - minC;
                foreach (var kv in raw)
                {
                    var r = kv.Key.R + rOff; var c = kv.Key.C + cOff;
                    _cells[r >= 1 && r <= _n && c >= 1 && c <= _n ? (r, c) : kv.Key] = kv.Value;
                }
            }
        }
        Changed();
    }

    public override Recipe? TryMatch()
    {
        if (_cells.Count == 0) return null;
        var recipeDb = Combat.RecipeDb;
        var placementDb = Combat.PlacementDb;
        if (recipeDb is null || placementDb is null) return null;
        if (!recipeDb.RecipesByStation.TryGetValue("smithing", out var list)) return null;

        var mine = Normalize(_cells);
        foreach (var rec in list.Where(x => x.StationTier <= Tier)
                     .OrderBy(x => x.StationTier).ThenBy(x => x.RecipeId))
        {
            var pd = placementDb.GetPlacement(rec.RecipeId);
            if (pd?.PlacementMap is not JsonObject map) continue;
            var theirs = NormalizeJson(map);
            if (theirs.Count == mine.Count && MapsEqual(mine, theirs)) return rec;
        }
        return null;
    }

    public override bool HasPlacement() => _cells.Count > 0;

    public override JsonObject Signature()
    {
        var sig = SigHead();
        var grid = new JsonObject();
        foreach (var kv in _cells) grid[$"{kv.Key.R},{kv.Key.C}"] = kv.Value;
        sig["grid"] = grid;
        return sig;
    }

    // ---- helpers ----
    private static (int R, int C)? ParseCell(string key)
    {
        var p = key.Split(',');
        if (p.Length != 2) return null;
        if (!int.TryParse(p[0].Trim(), out var r) || !int.TryParse(p[1].Trim(), out var c)) return null;
        return (r, c);
    }

    private static Dictionary<(int, int), string> Normalize(Dictionary<(int R, int C), string> cells)
    {
        var minR = cells.Keys.Min(k => k.R);
        var minC = cells.Keys.Min(k => k.C);
        var outp = new Dictionary<(int, int), string>();
        foreach (var kv in cells) outp[(kv.Key.R - minR + 1, kv.Key.C - minC + 1)] = kv.Value;
        return outp;
    }

    private static Dictionary<(int, int), string> NormalizeJson(JsonObject map)
    {
        var raw = new Dictionary<(int R, int C), string>();
        foreach (var kv in map)
        {
            var cell = ParseCell(kv.Key);
            var mid = kv.Value?.GetValue<string>();
            if (cell is { } rc && !string.IsNullOrEmpty(mid)) raw[rc] = mid!;
        }
        return raw.Count == 0 ? new Dictionary<(int, int), string>() : Normalize(raw);
    }

    private static bool MapsEqual(Dictionary<(int, int), string> a, Dictionary<(int, int), string> b)
    {
        foreach (var kv in a)
            if (!b.TryGetValue(kv.Key, out var v) || v != kv.Value) return false;
        return true;
    }
}
