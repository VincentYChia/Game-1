using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>
/// World map popup ([M]; [Esc] closes). Renders the CERTIFIED WorldMap —
/// 1 pixel per chunk, biome palette tinted 30% by nation color, village
/// dots, live player marker — plus a where-am-I readout (chunk type, danger,
/// district/province/region/nation) from the same geographic data the
/// Python game uses. Presentation only.
/// </summary>
public partial class MapScreen : CanvasLayer
{
    private const int MapPx = 640;

    private readonly WorldMap? _map;
    private readonly List<VillageRecord> _villages;
    private readonly PlayerController _player;

    private Control _root = null!;
    private Control _mapHolder = null!;
    private ColorRect _marker = null!;
    private Label _info = null!;
    private bool _open;
    private bool _built;

    public MapScreen(WorldMap? map, List<VillageRecord> villages,
                     PlayerController player)
    {
        _map = map;
        _villages = villages;
        _player = player;
    }

    public override void _Ready()
    {
        Layer = 10;
        _root = new Control { Visible = false };
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        var dim = new ColorRect { Color = new Color(0, 0, 0, 0.55f) };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(dim);

        var center = new CenterContainer();
        center.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(center);

        var panel = new PanelContainer();
        center.AddChild(panel);
        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 16);
        panel.AddChild(margin);

        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 8);
        margin.AddChild(box);

        var title = new Label { Text = "World Map" };
        title.AddThemeFontSizeOverride("font_size", 26);
        box.AddChild(title);

        _mapHolder = new Control { CustomMinimumSize = new Vector2(MapPx, MapPx) };
        box.AddChild(_mapHolder);

        _info = new Label { Text = "" };
        _info.AddThemeFontSizeOverride("font_size", 15);
        box.AddChild(_info);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey { Pressed: true, Echo: false } key) return;
        // Open only if no other popup is up; closing always allowed
        if (key.PhysicalKeycode is Key.M)
        {
            if (_open || !UiHub.ScreenOpen) Toggle();
        }
        else if (key.PhysicalKeycode is Key.Escape && _open) Toggle();
    }

    private void Toggle()
    {
        _open = !_open;
        _root.Visible = _open;
        UiHub.OpenScreens += _open ? 1 : -1;
        if (_open && !_built) BuildMapTexture();
    }

    public override void _Process(double delta)
    {
        if (!_open || _map is null) return;

        var tileX = _player.Position.X;
        var tileZ = _player.Position.Z;
        var cx = (int)Math.Floor(tileX / 16.0);
        var cy = (int)Math.Floor(tileZ / 16.0);

        var half = _map.WorldSize / 2;
        _marker.Position = new Vector2(
            (cx + half + 0.5f) / _map.WorldSize * MapPx - 4,
            (cy + half + 0.5f) / _map.WorldSize * MapPx - 4);

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
                + $"{province?.Name ?? "?"}, {region?.Name ?? "?"}, "
                + $"{nation?.Name ?? "unclaimed"}";
        }
        else
        {
            _info.Text = $"tile ({tileX:F0}, {tileZ:F0})  ·  chunk ({cx}, {cy})  ·  "
                         + "beyond the mapped world";
        }
    }

    private void BuildMapTexture()
    {
        _built = true;
        if (_map is null)
        {
            _info.Text = "no geographic map (UseGeographic off)";
            return;
        }

        var size = _map.WorldSize;
        var half = size / 2;
        var image = Image.CreateEmpty(size, size, false, Image.Format.Rgba8);
        image.Fill(new Color(0.08f, 0.08f, 0.1f));

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

        var white = new Color(1, 1, 1);
        foreach (var v in _villages)
        {
            var px = v.CenterChunk.X + half;
            var py = v.CenterChunk.Y + half;
            for (var dy = -1; dy <= 1; dy++)
                for (var dx = -1; dx <= 1; dx++)
                {
                    var x = px + dx;
                    var y = py + dy;
                    if (x >= 0 && x < size && y >= 0 && y < size)
                        image.SetPixel(x, y, white);
                }
        }

        var rect = new TextureRect
        {
            Texture = ImageTexture.CreateFromImage(image),
            TextureFilter = CanvasItem.TextureFilterEnum.Nearest,
            StretchMode = TextureRect.StretchModeEnum.Scale,
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
        };
        rect.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _mapHolder.AddChild(rect);

        _marker = new ColorRect
        {
            Color = new Color(1f, 0.15f, 0.15f),
            Size = new Vector2(8, 8),
        };
        _mapHolder.AddChild(_marker);
    }
}
