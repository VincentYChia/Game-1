using System;
using System.Collections.Generic;
using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>
/// World map book page ([M]) — a shaded-relief cartographic map on a manual
/// pan/zoom canvas (NOT a ScrollContainer, which left-pinned the map and fought
/// dragging). The map holder is transformed directly, so it always CENTRES when
/// smaller than the view (no lop-sided empty margin) and click-drag pans reliably.
///   • BACKGROUND: a hillshaded elevation map sampled from the real height field.
///   • LABELS: viewport-aware with OVERLAP DE-COLLISION — placed in importance
///     order, any that would collide with a placed name are skipped, so text
///     never overlaps and density scales with zoom.
///   • ROADS: the settlement network beneath the labels, tiered + LOD'd.
///   • NAV: scroll-wheel zooms on the cursor; click-drag pans; bounds keep the
///     view from drifting off the settled world or past useful detail.
/// The bottom bar always names exactly where the player stands (the context layer).
/// </summary>
public partial class MapPage : MenuPage
{
    public override string Title => "Map";
    public override Key Keybind => Key.M;

    private const int PxPerChunk = 3;          // base map pixels per chunk (label/road space)
    private const float ZoomMax = 6.0f, ZoomStep = 1.18f;
    private const int LabelCap = 60;           // hard safety cap on visible labels

    private readonly WorldMap? _map;
    private readonly List<VillageRecord> _villages;
    private readonly PlayerController _player;
    private readonly RoadNetwork? _roads;

    private Control _view = null!;             // the clipped viewport
    private Control _mapHolder = null!;        // transformed directly (Position + Scale)
    private ColorRect _marker = null!;
    private Label _info = null!;
    private RoadOverlay? _roadOverlay;
    private Vector2 _baseSize;
    private float _zoom = 1.2f;
    private float _zoomMin = 0.4f;
    private bool _built, _boundsReady, _openedOnce;

    // settled-world extent in base pixels (for the content-fit zoom-out bound)
    private Vector2 _contentMin, _contentMax;

    private sealed class MapItem
    {
        public Label Label = null!;
        public int Tier;          // 0 nation · 1 region · 2 city/locality · 3 town · 4 hamlet
        public float Importance;  // bigger shows first within a tier
        public float Px, Py;      // base map-pixel position (label anchor)
        public int FontSize;
        public Color BaseColor;
    }
    private readonly List<MapItem> _items = new();
    private readonly List<MapItem> _cands = new();
    private readonly List<Rect2> _placed = new();

    private Vector2 _lastPos = new(-1, -1);
    private float _lastZoom = -1f;

    public MapPage(WorldMap? map, List<VillageRecord> villages,
                   PlayerController player, RoadNetwork? roads = null)
    {
        _map = map;
        _villages = villages;
        _player = player;
        _roads = roads;
    }

    public override void _Ready()
    {
        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 10);
        box.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(box);

        box.AddChild(UiTheme.Header("World Map"));
        var hint = new Label { Text = "scroll to zoom  ·  click-drag to pan  ·  detail unfolds as you zoom in" };
        hint.AddThemeFontSizeOverride("font_size", 15);
        hint.Modulate = new Color(1, 1, 1, 0.55f);
        box.AddChild(hint);

        var plate = new PanelContainer
        {
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        plate.AddThemeStyleboxOverride("panel",
            UiTheme.Box(UiTheme.PanelInner, UiTheme.Border, 3, 12));
        box.AddChild(plate);

        // manual pan/zoom canvas: a clipped view with a directly-transformed holder
        _view = new Control { ClipContents = true, MouseFilter = Control.MouseFilterEnum.Stop };
        _view.GuiInput += OnMapInput;
        plate.AddChild(_view);

        var mapSizePx = (_map?.WorldSize ?? 512) * PxPerChunk;
        _baseSize = new Vector2(mapSizePx, mapSizePx);
        _mapHolder = new Control { Size = _baseSize, MouseFilter = Control.MouseFilterEnum.Ignore };
        _view.AddChild(_mapHolder);

        var infoPanel = new PanelContainer { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        infoPanel.AddThemeStyleboxOverride("panel",
            UiTheme.Box(UiTheme.SlotBg, UiTheme.Border, 2, 8));
        box.AddChild(infoPanel);
        var infoMargin = new MarginContainer();
        foreach (var s in new[] { "left", "right", "top", "bottom" })
            infoMargin.AddThemeConstantOverride($"margin_{s}", 12);
        infoPanel.AddChild(infoMargin);
        _info = new Label { AutowrapMode = TextServer.AutowrapMode.WordSmart };
        _info.AddThemeFontSizeOverride("font_size", 18);
        _info.AddThemeColorOverride("font_color", UiTheme.Text);
        infoMargin.AddChild(_info);
    }

    public override void OnOpened()
    {
        if (!_built) BuildMap();
        CallDeferred(nameof(FirstFrame));
    }

    /// <summary>Deferred so the view has a real size to fit against.</summary>
    private void FirstFrame()
    {
        EnsureZoomBounds();
        if (!_openedOnce)
        {
            _openedOnce = true;
            _zoom = Mathf.Clamp(1.2f, _zoomMin, ZoomMax);
        }
        CenterOnPlayer();
    }

    private void EnsureZoomBounds()
    {
        if (_boundsReady || _map is null) return;
        var vp = _view.Size;
        if (vp.X < 8 || vp.Y < 8) return;   // not laid out yet
        var w = Mathf.Max(1f, _contentMax.X - _contentMin.X);
        var h = Mathf.Max(1f, _contentMax.Y - _contentMin.Y);
        // at min zoom the settled world FITS the view (its limiting dimension
        // fills; the map centres on the other axis — no lop-sided empty margin).
        _zoomMin = Mathf.Clamp(Mathf.Min(vp.X / w, vp.Y / h), 0.12f, 1.2f);
        _boundsReady = true;
    }

    private bool _dragging;

    private void OnMapInput(InputEvent @event)
    {
        if (@event is InputEventMouseButton mb)
        {
            if (mb.ButtonIndex is MouseButton.WheelUp or MouseButton.WheelDown)
            {
                if (mb.Pressed) ZoomAt(mb.ButtonIndex == MouseButton.WheelUp, mb.Position);
                _view.AcceptEvent();
            }
            else if (mb.ButtonIndex == MouseButton.Left)
            {
                _dragging = mb.Pressed;            // click + drag to pan
                _view.AcceptEvent();
            }
            return;
        }
        if (@event is InputEventMouseMotion mm && _dragging)
        {
            _mapHolder.Position += mm.Relative;    // direct pan — always works
            ClampPan();
            _view.AcceptEvent();
        }
    }

    private void ZoomAt(bool zoomIn, Vector2 mouse)
    {
        EnsureZoomBounds();
        var old = _zoom;
        _zoom = Mathf.Clamp(_zoom * (zoomIn ? ZoomStep : 1f / ZoomStep), _zoomMin, ZoomMax);
        if (Mathf.Abs(_zoom - old) < 1e-4f) return;
        // keep the base point under the cursor fixed
        var b = (mouse - _mapHolder.Position) / old;
        _mapHolder.Position = mouse - b * _zoom;
        Apply();
    }

    private void Apply()
    {
        _mapHolder.Scale = new Vector2(_zoom, _zoom);
        ClampPan();
    }

    /// <summary>Centre the map when it is smaller than the view (symmetric
    /// margins), else keep it filling the view (can't drag past an edge).</summary>
    private void ClampPan()
    {
        var view = _view.Size;
        float mapW = _baseSize.X * _zoom, mapH = _baseSize.Y * _zoom;
        var p = _mapHolder.Position;
        p.X = mapW <= view.X ? (view.X - mapW) * 0.5f : Mathf.Clamp(p.X, view.X - mapW, 0);
        p.Y = mapH <= view.Y ? (view.Y - mapH) * 0.5f : Mathf.Clamp(p.Y, view.Y - mapH, 0);
        _mapHolder.Position = p;
    }

    private void CenterOnPlayer()
    {
        if (_map is null) return;
        var half = _map.WorldSize / 2;
        var cx = (int)Math.Floor(_player.Position.X / 16.0);
        var cy = (int)Math.Floor(_player.Position.Z / 16.0);
        var pp = new Vector2((cx + half + 0.5f) * PxPerChunk, (cy + half + 0.5f) * PxPerChunk);
        _mapHolder.Position = _view.Size * 0.5f - pp * _zoom;
        Apply();
        UpdateVisibleLabels();
    }

    public override void Tick(double delta)
    {
        if (_map is null) return;
        if (!_boundsReady) EnsureZoomBounds();

        var tileX = _player.Position.X;
        var tileZ = _player.Position.Z;
        var cx = (int)Math.Floor(tileX / 16.0);
        var cy = (int)Math.Floor(tileZ / 16.0);
        var half = _map.WorldSize / 2;

        if (_marker is not null)
        {
            _marker.Position = new Vector2(
                (cx + half + 0.5f) * PxPerChunk - 6, (cy + half + 0.5f) * PxPerChunk - 6);
            _marker.Scale = Vector2.One / _zoom;   // constant on-screen size
        }

        if (_map.ChunkData.TryGetValue((cx, cy), out var geo))
        {
            var region = _map.Regions.GetValueOrDefault(geo.RegionId);
            var province = _map.Provinces.GetValueOrDefault(geo.ProvinceId);
            var nation = _map.Nations.GetValueOrDefault(geo.NationId);
            var locality = geo.LocalityId >= 0
                ? _map.Localities.GetValueOrDefault(geo.LocalityId) : null;
            _info.Text =
                $"tile ({tileX:F0}, {tileZ:F0})  ·  chunk ({cx}, {cy})  ·  "
                + $"{geo.ChunkType}  ·  {geo.DangerLevel.DisplayName()}\n"
                + (locality is not null ? $"{locality.Name}  ·  " : "")
                + $"{province?.Name ?? "?"}, {region?.Name ?? "?"} "
                + (region is not null ? $"({region.Identity})" : "") + ", "
                + $"{nation?.Name ?? "unclaimed"}";
        }
        else
        {
            _info.Text = $"tile ({tileX:F0}, {tileZ:F0})  ·  chunk ({cx}, {cy})  ·  "
                         + "beyond the mapped world";
        }

        // recompute the visible label set only when the view actually moved
        if (_built && (_mapHolder.Position != _lastPos || _zoom != _lastZoom))
        {
            _lastPos = _mapHolder.Position;
            _lastZoom = _zoom;
            UpdateVisibleLabels();
        }
    }

    // ---- viewport LOD with overlap de-collision ---------------------------
    private static int MaxTier(float z) => z >= 2.2f ? 4 : z >= 1.4f ? 3 : 2;

    private void UpdateVisibleLabels()
    {
        if (_map is null) return;
        var z = _zoom;
        var pos = _mapHolder.Position;
        var view = _view.Size;
        var maxTier = MaxTier(z);

        // base-pixel viewport (+ a margin so labels near the edge still resolve)
        float vMinX = -pos.X / z, vMinY = -pos.Y / z;
        float vMaxX = (view.X - pos.X) / z, vMaxY = (view.Y - pos.Y) / z;
        float padX = (vMaxX - vMinX) * 0.06f, padY = (vMaxY - vMinY) * 0.06f;

        foreach (var it in _items) it.Label.Visible = false;

        _cands.Clear();
        foreach (var it in _items)
            if (it.Tier <= maxTier
                && it.Px >= vMinX - padX && it.Px <= vMaxX + padX
                && it.Py >= vMinY - padY && it.Py <= vMaxY + padY)
                _cands.Add(it);
        // importance order: lower tier first (nation→hamlet), bigger first within
        _cands.Sort((a, b) => a.Tier != b.Tier
            ? a.Tier.CompareTo(b.Tier) : b.Importance.CompareTo(a.Importance));

        _placed.Clear();
        foreach (var it in _cands)
        {
            // screen rect (labels hold a constant on-screen size → screen metrics)
            var sx = it.Px * z + pos.X;
            var sy = it.Py * z + pos.Y;
            var w = it.Label.Text.Length * it.FontSize * 0.52f + 4f;
            var hgt = it.FontSize * 1.15f + 3f;
            var rect = new Rect2(sx - 2, sy - 2, w, hgt);
            var clash = false;
            foreach (var r in _placed)
                if (r.Intersects(rect)) { clash = true; break; }
            if (clash) continue;
            _placed.Add(rect);

            // faintly dim the finest tier currently shown (the "preview" layer)
            var alpha = it.Tier == maxTier && maxTier >= 3 ? 0.72f : 1.0f;
            it.Label.Visible = true;
            it.Label.Scale = Vector2.One / z;
            it.Label.Modulate = new Color(it.BaseColor.R, it.BaseColor.G, it.BaseColor.B, alpha);
            if (_placed.Count >= LabelCap) break;
        }

        _roadOverlay?.QueueRedraw();
    }

    // ---- build (once) ----------------------------------------------------
    private void BuildMap()
    {
        _built = true;
        if (_map is null)
        {
            _info.Text = "no geographic map (UseGeographic off)";
            return;
        }

        var size = _map.WorldSize;
        var half = size / 2;

        BuildReliefBackground(size, half);

        if (_roads is not null)
        {
            _roadOverlay = new RoadOverlay(_roads, half, PxPerChunk, () => _zoom)
            { MouseFilter = Control.MouseFilterEnum.Ignore };
            _roadOverlay.SetAnchorsPreset(Control.LayoutPreset.FullRect);
            _mapHolder.AddChild(_roadOverlay);
        }

        _contentMin = new Vector2(float.MaxValue, float.MaxValue);
        _contentMax = new Vector2(float.MinValue, float.MinValue);

        MapItem Add(double cx, double cy, string text, int font, Color color,
                    int tier, float importance)
        {
            var l = new Label
            {
                Text = text,
                Visible = false,
                MouseFilter = Control.MouseFilterEnum.Ignore,
                Position = new Vector2((float)((cx + half) * PxPerChunk),
                                       (float)((cy + half) * PxPerChunk)),
            };
            l.AddThemeFontSizeOverride("font_size", font);
            l.AddThemeColorOverride("font_color", new Color(1, 1, 1));
            l.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
            l.AddThemeConstantOverride("outline_size", 5);
            _mapHolder.AddChild(l);
            var item = new MapItem
            {
                Label = l, Tier = tier, Importance = importance,
                Px = l.Position.X, Py = l.Position.Y, FontSize = font, BaseColor = color,
            };
            _items.Add(item);
            return item;
        }

        // nations (tier 0)
        foreach (var nation in _map.Nations.Values)
        {
            double sx = 0, sy = 0;
            var nn = 0;
            foreach (var rid in nation.RegionIds)
                if (_map.Regions.TryGetValue(rid, out var r))
                {
                    sx += (r.Bounds.MinX + r.Bounds.MaxX) / 2.0;
                    sy += (r.Bounds.MinY + r.Bounds.MaxY) / 2.0;
                    nn++;
                }
            if (nn > 0)
                Add(sx / nn, sy / nn, nation.Name.ToUpper(), 23,
                    new Color(1f, 0.9f, 0.62f), 0, 1e9f);
        }
        // regions (tier 1)
        foreach (var r in _map.Regions.Values)
            Add((r.Bounds.MinX + r.Bounds.MaxX) / 2.0, (r.Bounds.MinY + r.Bounds.MaxY) / 2.0,
                r.Name, 17, new Color(0.85f, 0.91f, 1f), 1, r.ChunkCount);
        // localities (tier 2, below cities)
        foreach (var loc in _map.Localities.Values)
            Add(loc.ChunkX, loc.ChunkY, "· " + loc.Name, 12,
                new Color(0.80f, 0.86f, 0.72f), 2, 500);
        // settlements — tier + importance by size
        foreach (var v in _villages)
        {
            var npc = v.NpcPositions.Count;
            var (glyph, font, col, tier, imp) = v.Tier switch
            {
                "fortress" => ("★ ", 16, new Color(1f, 0.85f, 0.55f), 2, 5000f + npc),
                "large" => ("◆ ", 15, new Color(1f, 0.92f, 0.7f), 2, 4000f + npc),
                "medium" => ("◆ ", 13, new Color(1f, 1f, 0.82f), 3, 3000f + npc),
                "small" => ("· ", 12, new Color(0.95f, 0.95f, 0.8f), 4, 2000f + npc),
                _ => ("· ", 11, new Color(0.9f, 0.9f, 0.78f), 4, 1000f + npc),
            };
            var item = Add(v.CenterChunk.X, v.CenterChunk.Y, glyph + v.Name, font, col, tier, imp);
            _contentMin = new Vector2(Mathf.Min(_contentMin.X, item.Px), Mathf.Min(_contentMin.Y, item.Py));
            _contentMax = new Vector2(Mathf.Max(_contentMax.X, item.Px), Mathf.Max(_contentMax.Y, item.Py));
        }
        if (_contentMin.X > _contentMax.X)   // no villages → whole map
        {
            _contentMin = Vector2.Zero;
            _contentMax = _baseSize;
        }
        else   // pad the settled extent a little
        {
            var m = new Vector2(6 * PxPerChunk, 6 * PxPerChunk);
            _contentMin -= m; _contentMax += m;
        }

        _marker = new ColorRect
        {
            Color = new Color(1f, 0.15f, 0.15f),
            Size = new Vector2(12, 12),
            MouseFilter = Control.MouseFilterEnum.Ignore,
        };
        _mapHolder.AddChild(_marker);
    }

    /// <summary>A hillshaded elevation map sampled from the real height field.
    /// Per-chunk height + relief-colour grids are computed once, then the image
    /// bilinearly samples colour and derives a hillshade from the height gradient
    /// so ranges cast light/shadow and water is depth-tinted — a real relief map.</summary>
    private void BuildReliefBackground(int size, int half)
    {
        const float OceanH = TerrainHeightField.WaterLevel - 4f;   // unmapped = deep sea

        var heights = new float[size * size];
        var cols = new Color[size * size];
        Array.Fill(heights, OceanH);

        var deepSea = new Color(0.10f, 0.19f, 0.42f);
        var shallow = new Color(0.34f, 0.55f, 0.74f);
        var sand = new Color(0.80f, 0.74f, 0.54f);
        var meadow = new Color(0.34f, 0.49f, 0.26f);
        var forest = new Color(0.20f, 0.36f, 0.19f);
        var stone = new Color(0.47f, 0.44f, 0.40f);
        var scree = new Color(0.60f, 0.58f, 0.54f);
        var snow = new Color(0.94f, 0.96f, 0.99f);

        Color Relief(float h)
        {
            if (h < TerrainHeightField.WaterLevel)
            {
                var dep = Mathf.Clamp((TerrainHeightField.WaterLevel - h) / 9f, 0f, 1f);
                return shallow.Lerp(deepSea, dep);
            }
            var c = meadow;
            c = c.Lerp(forest, Mathf.Clamp((h - 6f) / 16f, 0f, 1f) * 0.7f);
            c = c.Lerp(stone, Mathf.Clamp((h - 22f) / 20f, 0f, 1f) * 0.85f);
            c = c.Lerp(scree, Mathf.Clamp((h - 46f) / 16f, 0f, 1f) * 0.8f);
            c = c.Lerp(snow, Mathf.Clamp((h - 66f) / 14f, 0f, 1f));
            if (h < TerrainHeightField.WaterLevel + 1.0f) c = c.Lerp(sand, 0.55f);
            return c;
        }

        // sample the field once per chunk centre + fold in a faint nation tint
        foreach (var ((cx, cy), geo) in _map!.ChunkData)
        {
            if (cx < -half || cx >= half || cy < -half || cy >= half) continue;
            var i = (cy + half) * size + (cx + half);
            var h = TerrainHeightField.H(cx * 16 + 8, cy * 16 + 8);
            heights[i] = h;
            var c = Relief(h);
            if (_map.Nations.TryGetValue(geo.NationId, out var nation))
            {
                var (nr, ng, nb) = nation.Color;
                c = c.Lerp(new Color(nr / 255f, ng / 255f, nb / 255f), 0.14f);
            }
            cols[i] = c;
        }
        for (var i = 0; i < cols.Length; i++)
            if (cols[i].A == 0f && heights[i] <= OceanH) cols[i] = deepSea;

        float SampleH(float cxf, float cyf)
        {
            cxf = Mathf.Clamp(cxf, -half, half - 1.001f);
            cyf = Mathf.Clamp(cyf, -half, half - 1.001f);
            int x0 = (int)Mathf.Floor(cxf), y0 = (int)Mathf.Floor(cyf);
            float tx = cxf - x0, ty = cyf - y0;
            int ix = x0 + half, iy = y0 + half;
            float h00 = heights[iy * size + ix], h10 = heights[iy * size + ix + 1];
            float h01 = heights[(iy + 1) * size + ix], h11 = heights[(iy + 1) * size + ix + 1];
            return (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty;
        }
        Color SampleC(float cxf, float cyf)
        {
            cxf = Mathf.Clamp(cxf, -half, half - 1.001f);
            cyf = Mathf.Clamp(cyf, -half, half - 1.001f);
            int x0 = (int)Mathf.Floor(cxf), y0 = (int)Mathf.Floor(cyf);
            float tx = cxf - x0, ty = cyf - y0;
            int ix = x0 + half, iy = y0 + half;
            var c00 = cols[iy * size + ix]; var c10 = cols[iy * size + ix + 1];
            var c01 = cols[(iy + 1) * size + ix]; var c11 = cols[(iy + 1) * size + ix + 1];
            return c00.Lerp(c10, tx).Lerp(c01.Lerp(c11, tx), ty);
        }

        var res = size * PxPerChunk;                 // 1 image texel per base pixel
        var data = new byte[res * res * 4];
        var light = new Vector3(-0.5f, 0.86f, -0.42f).Normalized();   // sun from the NW
        const float d = 0.62f;                       // gradient reach (chunks)
        for (var py = 0; py < res; py++)
        {
            var cyf = (float)py / PxPerChunk - half;
            for (var px = 0; px < res; px++)
            {
                var cxf = (float)px / PxPerChunk - half;
                var col = SampleC(cxf, cyf);

                float hl = SampleH(cxf - d, cyf), hr = SampleH(cxf + d, cyf);
                float hu = SampleH(cxf, cyf - d), hdn = SampleH(cxf, cyf + d);
                var nrm = new Vector3(hl - hr, 9f, hu - hdn).Normalized();
                var shade = Mathf.Clamp(0.74f + nrm.Dot(light) * 0.5f, 0.5f, 1.28f);

                var o = (py * res + px) * 4;
                data[o] = (byte)(Mathf.Clamp(col.R * shade, 0f, 1f) * 255f);
                data[o + 1] = (byte)(Mathf.Clamp(col.G * shade, 0f, 1f) * 255f);
                data[o + 2] = (byte)(Mathf.Clamp(col.B * shade, 0f, 1f) * 255f);
                data[o + 3] = 255;
            }
        }

        var image = Image.CreateFromData(res, res, false, Image.Format.Rgba8, data);
        var rect = new TextureRect
        {
            Texture = ImageTexture.CreateFromImage(image),
            TextureFilter = CanvasItem.TextureFilterEnum.Linear,   // smooth when magnified
            Size = _baseSize,
            MouseFilter = Control.MouseFilterEnum.Ignore,
        };
        _mapHolder.AddChild(rect);
    }

    /// <summary>The settlement road network beneath the labels: schematic tiered
    /// lines (grand artery → thin feeder), each with a dark casing for a road
    /// read, LOD'd so only the highways show when zoomed out.</summary>
    private sealed partial class RoadOverlay : Control
    {
        private readonly RoadNetwork _net;
        private readonly int _half, _px;
        private readonly Func<float> _zoom;

        private static readonly Color[] Cols =
        {
            new(0.52f, 0.42f, 0.30f),  // feeder — dirt
            new(0.60f, 0.51f, 0.39f),  // branch — packed earth
            new(0.70f, 0.64f, 0.54f),  // secondary — gravel
            new(0.86f, 0.80f, 0.66f),  // artery — grand pale stone
        };
        private static readonly Color Casing = new(0.18f, 0.13f, 0.09f, 0.85f);
        private static readonly float[] Widths = { 0.8f, 1.4f, 2.4f, 3.6f };
        // feeders only appear zoomed-in; arteries always show the highway skeleton
        private static readonly float[] MinZoom = { 2.0f, 1.2f, 0.55f, 0f };

        public RoadOverlay(RoadNetwork net, int half, int px, Func<float> zoom)
        { _net = net; _half = half; _px = px; _zoom = zoom; }

        public override void _Draw()
        {
            var z = _zoom();
            Vector2 ToPx(Vector2 w) => new((w.X / 16f + _half) * _px, (w.Y / 16f + _half) * _px);

            // two passes: all casings first, then all surfaces, so crossings read cleanly
            for (var pass = 0; pass < 2; pass++)
                foreach (var e in _net.Edges)
                {
                    if (z < MinZoom[e.Tier]) continue;
                    var col = pass == 0 ? Casing : Cols[e.Tier];
                    var wd = Widths[e.Tier] + (pass == 0 ? 1.4f : 0f);
                    if (e.Path is { Length: >= 2 } path)
                        for (var i = 0; i < path.Length - 1; i++)
                            DrawLine(ToPx(path[i]), ToPx(path[i + 1]), col, wd);
                    else
                        DrawLine(ToPx(e.A), ToPx(e.B), col, wd);
                }
        }
    }
}
