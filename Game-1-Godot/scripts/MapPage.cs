using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>
/// World map book page ([M]). Renders the CERTIFIED WorldMap — 1 pixel per
/// chunk, biome palette tinted 30% by nation color, village dots, live
/// player marker — plus a where-am-I readout from the same geographic data
/// the Python game uses. Presentation only.
/// </summary>
public partial class MapPage : MenuPage
{
    public override string Title => "Map";
    public override Key Keybind => Key.M;

    private const int MapPx = 680;

    private readonly WorldMap? _map;
    private readonly List<VillageRecord> _villages;
    private readonly PlayerController _player;

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
        box.AddThemeConstantOverride("separation", 14);
        box.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(box);

        box.AddChild(UiTheme.Header("World Map"));

        // -- centered, framed map plate --
        var centerRow = new CenterContainer
        { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        box.AddChild(centerRow);

        var plate = new PanelContainer();
        plate.AddThemeStyleboxOverride("panel", UiTheme.Box(UiTheme.PanelInner, UiTheme.Border, 3, 12));
        centerRow.AddChild(plate);

        var plateMargin = new MarginContainer();
        foreach (var s in new[] { "left", "right", "top", "bottom" })
            plateMargin.AddThemeConstantOverride($"margin_{s}", 10);
        plate.AddChild(plateMargin);

        _mapHolder = new Control { CustomMinimumSize = new Vector2(MapPx, MapPx) };
        plateMargin.AddChild(_mapHolder);

        // -- where-am-I readout on a solid panel --
        var infoPanel = new PanelContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        infoPanel.AddThemeStyleboxOverride("panel", UiTheme.Box(UiTheme.SlotBg, UiTheme.Border, 2, 8));
        box.AddChild(infoPanel);

        var infoMargin = new MarginContainer();
        foreach (var s in new[] { "left", "right", "top", "bottom" })
            infoMargin.AddThemeConstantOverride($"margin_{s}", 14);
        infoPanel.AddChild(infoMargin);

        _info = new Label
        {
            Text = "",
            AutowrapMode = TextServer.AutowrapMode.WordSmart,
        };
        _info.AddThemeFontSizeOverride("font_size", 18);
        _info.AddThemeColorOverride("font_color", UiTheme.Text);
        infoMargin.AddChild(_info);
    }

    public override void OnOpened()
    {
        if (!_built) BuildMapTexture();
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
