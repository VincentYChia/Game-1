using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// ENCHANTING placement — the 2D adornments system in full (interactive_crafting.py
/// InteractiveAdornmentsUI). TWO layers on a signed Cartesian lattice (−7..+7):
///   1) SHAPES — pick a tier-gated shape (triangle/square, small→large) from the top
///      palette, set its ROTATION (45° steps), left-click a lattice point to stamp it;
///      right-click a shape to lift it. Placing a shape lights up its VERTICES.
///   2) MATERIALS — deselect the shape, pick a material in the left menu, then left-click
///      a LIT vertex to inscribe it (right-click clears).
/// A recipe matches only when the SHAPES (type + vertex-set + rotation, squares being
/// rotation-agnostic) AND every vertex material equal the template — exactly the 2D rule.
/// </summary>
public partial class EnchantingBoard : PlacementBoard
{
    private const int R = 7;   // coordinate range (fixed across tiers, like the 2D game)

    private static readonly Dictionary<string, (int X, int Y)[]> Templates = new()
    {
        ["triangle_equilateral_small"] = new[] { (0, 0), (-1, -2), (1, -2) },
        ["square_small"] = new[] { (0, 0), (2, 0), (2, -2), (0, -2) },
        ["triangle_isosceles_small"] = new[] { (0, 0), (-1, -3), (1, -3) },
        ["triangle_equilateral_large"] = new[] { (0, 0), (-2, -3), (2, -3) },
        ["square_large"] = new[] { (0, 0), (4, 0), (4, -4), (0, -4) },
        ["triangle_isosceles_large"] = new[] { (0, 0), (-1, -5), (1, -5) },
    };

    private sealed class ShapeInst
    {
        public string Type = "";
        public int Rotation;
        public List<(int X, int Y)> Verts = new();   // absolute, in polygon order
    }

    private readonly List<ShapeInst> _shapes = new();
    private readonly Dictionary<(int X, int Y), string> _verts = new();
    private string? _selShape;
    private int _rot;

    public override void Setup(CombatWorld combat, string discipline, int tier)
    {
        _selShape = null; _rot = 0;
        base.Setup(combat, discipline, tier);
    }

    public override void Clear() { _shapes.Clear(); _verts.Clear(); _selShape = null; QueueRedraw(); }

    public override bool HasPlacement() => _shapes.Count > 0;

    private string[] AvailableShapes()
    {
        var list = new List<string> { "triangle_equilateral_small", "square_small" };
        if (Tier >= 2) list.Add("triangle_isosceles_small");
        if (Tier >= 3) { list.Add("triangle_equilateral_large"); list.Add("square_large"); }
        if (Tier >= 4) list.Add("triangle_isosceles_large");
        return list.ToArray();
    }

    private static (int X, int Y) Rot(int x, int y, int deg)
    {
        var r = deg * System.Math.PI / 180.0;
        var c = System.Math.Cos(r); var s = System.Math.Sin(r);
        return ((int)System.Math.Round(x * c - y * s), (int)System.Math.Round(x * s + y * c));
    }

    private static List<(int X, int Y)> ShapeVerts(string type, int ax, int ay, int rot)
    {
        var outp = new List<(int, int)>();
        if (!Templates.TryGetValue(type, out var tmpl)) return outp;
        foreach (var (dx, dy) in tmpl) { var (rx, ry) = Rot(dx, dy, rot); outp.Add((ax + rx, ay + ry)); }
        return outp;
    }

    private bool VertexIsActive((int X, int Y) v) => _shapes.Any(s => s.Verts.Contains(v));

    // ------------------------------------------------------------- layout ----
    private float ToolTop => 8f;
    private float ToolH => 46f;
    private float ShapeBtn => 46f;
    private Rect2 ShapeRect(int i) => new(10f + i * (ShapeBtn + 6f), ToolTop, ShapeBtn, ToolH);
    private Rect2 RotRect() => new(Size.X - 128f, ToolTop, 118f, ToolH);

    private float LatticeCell()
    {
        var availH = Size.Y - (ToolTop + ToolH + 18f);
        var availW = Size.X - 24f;
        return Mathf.Min(availW, availH) / (2 * R + 2);
    }
    private Vector2 LatticeCenter() => new(Size.X * 0.5f, (ToolTop + ToolH + 14f) + (Size.Y - (ToolTop + ToolH + 18f)) * 0.5f);
    private Vector2 ScreenPos(int x, int y) => LatticeCenter() + new Vector2(x, -y) * LatticeCell();

    protected override void DrawBoard()
    {
        CraftFx.RoundRect(this, new Rect2(0, 0, Size.X, Size.Y), new Color(0.06f, 0.07f, 0.10f, 0.55f),
            new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.35f), 2, 12);
        var font = GetThemeDefaultFont();

        // ---- shape palette ----
        var shapes = AvailableShapes();
        for (var i = 0; i < shapes.Length; i++)
        {
            var rect = ShapeRect(i);
            var sel = _selShape == shapes[i];
            CraftFx.RoundRect(this, rect, sel ? new Color(0.18f, 0.14f, 0.24f) : new Color(0.10f, 0.11f, 0.15f, 0.8f),
                sel ? Style.Accent : new Color(0.5f, 0.45f, 0.6f, 0.7f), sel ? 2 : 1, 8);
            DrawShapePreview(rect.Grow(-10f), shapes[i], sel ? _rot : 0,
                sel ? Style.Accent : new Color(0.75f, 0.7f, 0.85f));
        }
        // ---- rotation control ----
        var rr = RotRect();
        var canRot = _selShape is not null;
        CraftFx.RoundRect(this, rr, new Color(0.10f, 0.11f, 0.15f, 0.85f),
            canRot ? Style.Accent : new Color(0.4f, 0.42f, 0.5f, 0.6f), canRot ? 2 : 1, 8);
        DrawString(font, rr.Position + new Vector2(0, rr.Size.Y * 0.62f), $"⟳  {_rot}°",
            HorizontalAlignment.Center, rr.Size.X, 18,
            canRot ? new Color(1, 1, 1, 0.92f) : new Color(1, 1, 1, 0.4f));

        // ---- lattice dots ----
        var cell = LatticeCell();
        var faint = new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.14f);
        for (var y = -R; y <= R; y++)
            for (var x = -R; x <= R; x++)
                DrawCircle(ScreenPos(x, y), 1.8f, faint);
        // axes
        DrawLine(ScreenPos(-R, 0), ScreenPos(R, 0), faint, 1f);
        DrawLine(ScreenPos(0, -R), ScreenPos(0, R), faint, 1f);

        // ---- shape outlines + lit vertices ----
        var edge = new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.6f);
        foreach (var s in _shapes)
        {
            for (var i = 0; i < s.Verts.Count; i++)
            {
                var a = ScreenPos(s.Verts[i].X, s.Verts[i].Y);
                var b = ScreenPos(s.Verts[(i + 1) % s.Verts.Count].X, s.Verts[(i + 1) % s.Verts.Count].Y);
                DrawLine(a, b, edge, 2f);
            }
        }
        // active-but-empty vertices glow to invite a material
        foreach (var s in _shapes)
            foreach (var v in s.Verts)
                if (!_verts.ContainsKey(v))
                {
                    var p = ScreenPos(v.X, v.Y);
                    if (_selShape is null && SelectedMaterialId is not null)
                        CraftFx.Glow(this, p, cell * 0.34f, new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.18f), 3);
                    DrawCircle(p, 4f, new Color(Style.Accent.R, Style.Accent.G, Style.Accent.B, 0.7f));
                }

        // ---- inscribed materials ----
        var vs = cell * 0.92f;
        foreach (var kv in _verts)
        {
            var p = ScreenPos(kv.Key.X, kv.Key.Y);
            var rect = new Rect2(p - new Vector2(vs, vs) * 0.5f, new Vector2(vs, vs));
            CraftFx.Glow(this, p, vs * 0.55f, new Color(RarityColor(kv.Value).R, RarityColor(kv.Value).G, RarityColor(kv.Value).B, 0.32f), 3);
            CraftFx.RoundRect(this, rect, new Color(0.15f, 0.16f, 0.21f), RarityColor(kv.Value), 2, 6);
            DrawOccupant(rect, kv.Value, 1);
        }

        // ---- hint ----
        var hint = _selShape is not null
            ? "click the lattice to stamp the shape · right-click a shape to remove"
            : "pick a shape above, or select a material and click a lit vertex";
        DrawString(font, new Vector2(12, Size.Y - 4), hint, HorizontalAlignment.Left, Size.X - 24, 12,
            new Color(1, 1, 1, 0.4f));
    }

    private void DrawShapePreview(Rect2 area, string type, int rot, Color col)
    {
        if (!Templates.TryGetValue(type, out var tmpl)) return;
        var pts = tmpl.Select(t => Rot(t.X, t.Y, rot)).ToArray();
        float minX = pts.Min(p => p.X), maxX = pts.Max(p => p.X);
        float minY = pts.Min(p => p.Y), maxY = pts.Max(p => p.Y);
        var spanX = System.Math.Max(1f, maxX - minX);
        var spanY = System.Math.Max(1f, maxY - minY);
        var scale = Mathf.Min(area.Size.X / spanX, area.Size.Y / spanY) * 0.9f;
        var mid = area.Position + area.Size * 0.5f;
        Vector2 Map((int X, int Y) p) => mid + new Vector2((p.X - (minX + maxX) / 2f), -(p.Y - (minY + maxY) / 2f)) * scale;
        for (var i = 0; i < pts.Length; i++)
            DrawLine(Map(pts[i]), Map(pts[(i + 1) % pts.Length]), col, 1.6f);
    }

    protected override void OnBoardInput(InputEvent e)
    {
        if (e is not InputEventMouseButton { Pressed: true } mb) return;

        // toolbar: shape palette
        var shapes = AvailableShapes();
        for (var i = 0; i < shapes.Length; i++)
            if (ShapeRect(i).HasPoint(mb.Position) && mb.ButtonIndex == MouseButton.Left)
            {
                _selShape = _selShape == shapes[i] ? null : shapes[i];
                QueueRedraw();
                return;
            }
        // toolbar: rotation
        if (RotRect().HasPoint(mb.Position) && mb.ButtonIndex == MouseButton.Left && _selShape is not null)
        {
            _rot = (_rot + 45) % 360;
            QueueRedraw();
            return;
        }

        // lattice: snap to nearest point
        if (!Pick(mb.Position, out var v)) return;

        if (_selShape is { } stype)
        {
            if (mb.ButtonIndex == MouseButton.Right) { RemoveShapeAt(v); return; }
            if (mb.ButtonIndex == MouseButton.Left) PlaceShape(stype, v.X, v.Y, _rot);
            return;
        }
        // material mode — only on lit vertices
        if (!VertexIsActive(v)) return;
        if (mb.ButtonIndex == MouseButton.Right) { if (_verts.Remove(v)) Changed(); return; }
        if (mb.ButtonIndex == MouseButton.Left && SelectedMaterialId is { } id && CanPlace(id))
        {
            _verts[v] = id;
            CraftFx.Burst(this, ScreenPos(v.X, v.Y), RarityColor(id), 8, 90f, 0.4f, 3f, 120f);
            Changed();
        }
    }

    private bool Pick(Vector2 mouse, out (int X, int Y) v)
    {
        var cell = LatticeCell();
        var c = LatticeCenter();
        var x = Mathf.RoundToInt((mouse.X - c.X) / cell);
        var y = Mathf.RoundToInt((c.Y - mouse.Y) / cell);
        v = (x, y);
        return x >= -R && x <= R && y >= -R && y <= R && ScreenPos(x, y).DistanceTo(mouse) <= cell * 0.6f;
    }

    private void PlaceShape(string type, int ax, int ay, int rot)
    {
        var verts = ShapeVerts(type, ax, ay, rot);
        if (verts.Count == 0) return;
        if (verts.Any(p => p.X < -R || p.X > R || p.Y < -R || p.Y > R)) return;   // must fit the lattice
        _shapes.Add(new ShapeInst { Type = type, Rotation = rot, Verts = verts });
        CraftFx.Burst(this, ScreenPos(ax, ay), Style.Accent, 10, 110f, 0.45f, 3f, 120f);
        Changed();
    }

    private void RemoveShapeAt((int X, int Y) v)
    {
        var idx = _shapes.FindLastIndex(s => s.Verts.Contains(v));
        if (idx < 0) return;
        var removed = _shapes[idx];
        _shapes.RemoveAt(idx);
        // drop materials on vertices no longer covered by any shape
        foreach (var vv in removed.Verts)
            if (!VertexIsActive(vv)) _verts.Remove(vv);
        Changed();
    }

    public override void AutoLay(PlacementData data)
    {
        _shapes.Clear(); _verts.Clear();
        if (data.PlacementMap is not JsonObject map) { Changed(); return; }
        if (map["shapes"] is JsonArray sarr)
            foreach (var n in sarr)
            {
                if (n is not JsonObject o) continue;
                var type = o["type"]?.GetValue<string>() ?? "";
                var rot = (o["rotation"] is JsonValue rv && rv.TryGetValue<int>(out var ri)) ? ri : 0;
                var verts = ParseVertList(o["vertices"]);
                if (verts.Count > 0) _shapes.Add(new ShapeInst { Type = type, Rotation = rot, Verts = verts });
            }
        if (map["vertices"] is JsonObject varr)
            foreach (var kv in varr)
            {
                var p = ParseCoord(kv.Key);
                var mid = kv.Value switch
                {
                    JsonObject vo => vo["materialId"]?.GetValue<string>() ?? vo["itemId"]?.GetValue<string>(),
                    JsonValue jv when jv.TryGetValue<string>(out var s) => s,
                    _ => null,
                };
                if (p is { } pt && !string.IsNullOrEmpty(mid)) _verts[pt] = mid!;
            }
        Changed();
    }

    public override Recipe? TryMatch()
    {
        if (_shapes.Count == 0) return null;
        var recipeDb = Combat.RecipeDb;
        var placementDb = Combat.PlacementDb;
        if (recipeDb is null || placementDb is null) return null;
        if (!recipeDb.RecipesByStation.TryGetValue("adornments", out var list)) return null;

        var myVerts = _verts.ToDictionary(kv => Key(kv.Key), kv => kv.Value);
        foreach (var rec in list.Where(x => x.StationTier <= Tier)
                     .OrderBy(x => x.StationTier).ThenBy(x => x.RecipeId))
        {
            var pd = placementDb.GetPlacement(rec.RecipeId);
            if (pd?.PlacementMap is not JsonObject map) continue;
            if (ShapesMatch(map["shapes"] as JsonArray) && MaterialsMatch(map["vertices"] as JsonObject, myVerts))
                return rec;
        }
        return null;
    }

    public override JsonObject Signature()
    {
        var sig = SigHead();
        var shapes = new JsonArray();
        foreach (var s in _shapes)
        {
            var vs = new JsonArray();
            foreach (var v in s.Verts) vs.Add(Key(v));
            shapes.Add(new JsonObject { ["type"] = s.Type, ["rotation"] = s.Rotation, ["vertices"] = vs });
        }
        var verts = new JsonObject();
        foreach (var kv in _verts) verts[Key(kv.Key)] = new JsonObject { ["materialId"] = kv.Value };
        sig["shapes"] = shapes;
        sig["vertices"] = verts;
        return sig;
    }

    // ---- matching helpers (mirror interactive_crafting.py check_recipe_match) ----
    private bool ShapesMatch(JsonArray? required)
    {
        if (required is null || required.Count == 0) return true;   // vertex-only recipe
        if (required.Count != _shapes.Count) return false;
        var used = new HashSet<int>();
        foreach (var mine in _shapes)
        {
            var mineSet = mine.Verts.Select(Key).ToHashSet();
            var ok = false;
            for (var i = 0; i < required.Count; i++)
            {
                if (used.Contains(i) || required[i] is not JsonObject ro) continue;
                var rtype = ro["type"]?.GetValue<string>() ?? "";
                if (rtype != mine.Type) continue;
                var rverts = ParseVertKeySet(ro["vertices"]);
                if (!rverts.SetEquals(mineSet)) continue;
                var rrot = (ro["rotation"] is JsonValue rv && rv.TryGetValue<int>(out var ri)) ? ri : 0;
                var rotOk = mine.Type.Contains("square") || System.Math.Abs(mine.Rotation - rrot) < 1;
                if (!rotOk) continue;
                used.Add(i); ok = true; break;
            }
            if (!ok) return false;
        }
        return true;
    }

    private static bool MaterialsMatch(JsonObject? required, Dictionary<string, string> mine)
    {
        var want = new Dictionary<string, string>();
        if (required is not null)
            foreach (var kv in required)
            {
                var mid = kv.Value switch
                {
                    JsonObject vo => vo["materialId"]?.GetValue<string>() ?? vo["itemId"]?.GetValue<string>(),
                    JsonValue jv when jv.TryGetValue<string>(out var s) => s,
                    _ => null,
                };
                if (!string.IsNullOrEmpty(mid)) want[kv.Key] = mid!;
            }
        if (want.Count != mine.Count) return false;
        foreach (var kv in want)
            if (!mine.TryGetValue(kv.Key, out var v) || v != kv.Value) return false;
        return true;
    }

    private static string Key((int X, int Y) v) => $"{v.X},{v.Y}";

    private static (int X, int Y)? ParseCoord(string key)
    {
        var p = key.Split(',');
        if (p.Length != 2) return null;
        if (!int.TryParse(p[0].Trim(), out var x) || !int.TryParse(p[1].Trim(), out var y)) return null;
        return (x, y);
    }

    private static List<(int X, int Y)> ParseVertList(JsonNode? node)
    {
        var outp = new List<(int, int)>();
        if (node is JsonArray arr)
            foreach (var n in arr)
                if (n is JsonValue jv && jv.TryGetValue<string>(out var s) && ParseCoord(s) is { } c)
                    outp.Add(c);
        return outp;
    }

    private static HashSet<string> ParseVertKeySet(JsonNode? node)
    {
        var set = new HashSet<string>();
        if (node is JsonArray arr)
            foreach (var n in arr)
                if (n is JsonValue jv && jv.TryGetValue<string>(out var s)) set.Add(s);
        return set;
    }
}
