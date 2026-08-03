using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>
/// World map book page ([M]). A SCROLLABLE map of the certified WorldMap
/// (biome palette tinted by nation color) with the full label set — nations,
/// regions, localities, villages — plus a live "you are here" marker and a
/// where-am-I readout, matching the 2D game's map. Pan with the scroll wheel /
/// scrollbars; opens centered on the player. Presentation only (no teleport).
/// </summary>
public partial class MapPage : MenuPage
{
    public override string Title => "Map";
    public override Key Keybind => Key.M;

    private const int PxPerChunk = 3;

    private readonly WorldMap? _map;
    private readonly List<VillageRecord> _villages;
    private readonly PlayerController _player;

    private ScrollContainer _scroll = null!;
    private Control _mapHolder = null!;
    private ColorRect _marker = null!;
    private Label _info = null!;
    private bool _built;

    public MapPage(WorldMap? map, List<VillageRecord> villages,
                   PlayerController player)
    {
        _map = map;
        _villages = villages;
        _player = player;
    }

    public override void _Ready()
    {
        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 10);
        box.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(box);

        box.AddChild(UiTheme.Header("World Map"));
        var hint = new Label { Text = "scroll / drag the bars to pan  ·  opens centered on you" };
        hint.AddThemeFontSizeOverride("font_size", 15);
        hint.Modulate = new Color(1, 1, 1, 0.55f);
        box.AddChild(hint);

        // -- the scrollable map plate --
        var plate = new PanelContainer
        {
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        plate.AddThemeStyleboxOverride("panel",
            UiTheme.Box(UiTheme.PanelInner, UiTheme.Border, 3, 12));
        box.AddChild(plate);

        _scroll = new ScrollContainer();
        plate.AddChild(_scroll);

        var mapSizePx = (_map?.WorldSize ?? 512) * PxPerChunk;
        _mapHolder = new Control
        { CustomMinimumSize = new Vector2(mapSizePx, mapSizePx) };
        _scroll.AddChild(_mapHolder);

        // -- where-am-I readout --
        var infoPanel = new PanelContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
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
        // Defer centering one frame so the ScrollContainer has a real size.
        CallDeferred(nameof(CenterOnPlayer));
    }

    private void CenterOnPlayer()
    {
        if (_map is null) return;
        var half = _map.WorldSize / 2;
        var cx = (int)Math.Floor(_player.Position.X / 16.0);
        var cy = (int)Math.Floor(_player.Position.Z / 16.0);
        var vp = _scroll.Size;
        _scroll.ScrollHorizontal = (int)((cx + half) * PxPerChunk - vp.X / 2);
        _scroll.ScrollVertical = (int)((cy + half) * PxPerChunk - vp.Y / 2);
    }

    public override void Tick(double delta)
    {
        if (_map is null) return;

        var tileX = _player.Position.X;
        var tileZ = _player.Position.Z;
        var cx = (int)Math.Floor(tileX / 16.0);
        var cy = (int)Math.Floor(tileZ / 16.0);
        var half = _map.WorldSize / 2;

        if (_marker is not null)
            _marker.Position = new Vector2(
                (cx + half + 0.5f) * PxPerChunk - 6,
                (cy + half + 0.5f) * PxPerChunk - 6);

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
    }

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

        // base biome image (1 px/chunk), tinted by nation, scaled up in the holder
        var image = Image.CreateEmpty(size, size, false, Image.Format.Rgba8);
        image.Fill(new Color(0.06f, 0.06f, 0.08f));
        foreach (var ((cx, cy), geo) in _map.ChunkData)
        {
            var color = WorldBootstrap.GeoColors.GetValueOrDefault(
                geo.ChunkType, new Color(0.3f, 0.3f, 0.3f));
            if (_map.Nations.TryGetValue(geo.NationId, out var nation))
            {
                var (r, g, b) = nation.Color;
                color = color.Lerp(new Color(r / 255f, g / 255f, b / 255f), 0.30f);
            }
            image.SetPixel(cx + half, cy + half, color);
        }
        var rect = new TextureRect
        {
            Texture = ImageTexture.CreateFromImage(image),
            TextureFilter = CanvasItem.TextureFilterEnum.Nearest,
            StretchMode = TextureRect.StretchModeEnum.Scale,
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            MouseFilter = Control.MouseFilterEnum.Ignore,
        };
        rect.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _mapHolder.AddChild(rect);

        // -- labels (full set: nations, regions, localities, villages) --
        void AddLabel(double cx, double cy, string text, int fontSize, Color color)
        {
            var l = new Label
            {
                Text = text,
                MouseFilter = Control.MouseFilterEnum.Ignore,
                Position = new Vector2((float)((cx + half) * PxPerChunk),
                                       (float)((cy + half) * PxPerChunk)),
            };
            l.AddThemeFontSizeOverride("font_size", fontSize);
            l.AddThemeColorOverride("font_color", color);
            l.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
            l.AddThemeConstantOverride("outline_size", 4);
            _mapHolder.AddChild(l);
        }

        // nations — large, at the centroid of their regions
        foreach (var nation in _map.Nations.Values)
        {
            double sx = 0, sy = 0;
            var n = 0;
            foreach (var rid in nation.RegionIds)
                if (_map.Regions.TryGetValue(rid, out var r))
                {
                    sx += (r.Bounds.MinX + r.Bounds.MaxX) / 2.0;
                    sy += (r.Bounds.MinY + r.Bounds.MaxY) / 2.0;
                    n++;
                }
            if (n > 0)
                AddLabel(sx / n, sy / n, nation.Name.ToUpper(), 22,
                    new Color(1f, 0.9f, 0.65f, 0.85f));
        }
        // regions — medium, at their bounds centre
        foreach (var r in _map.Regions.Values)
            AddLabel((r.Bounds.MinX + r.Bounds.MaxX) / 2.0,
                     (r.Bounds.MinY + r.Bounds.MaxY) / 2.0,
                     r.Name, 15, new Color(0.82f, 0.9f, 1f));
        // localities — small named landmarks
        foreach (var loc in _map.Localities.Values)
            AddLabel(loc.ChunkX, loc.ChunkY, "· " + loc.Name, 12,
                new Color(0.78f, 0.84f, 0.7f));
        // villages — dot + name
        foreach (var v in _villages)
            AddLabel(v.CenterChunk.X, v.CenterChunk.Y, "◊ " + v.Name, 13,
                new Color(1f, 1f, 0.82f));

        _marker = new ColorRect
        {
            Color = new Color(1f, 0.15f, 0.15f),
            Size = new Vector2(12, 12),
            MouseFilter = Control.MouseFilterEnum.Ignore,
        };
        _mapHolder.AddChild(_marker);
    }
}
