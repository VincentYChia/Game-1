using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/map_waypoint_db.py. Waypoint RULES (unlock levels,
/// cooldown, placement constraints, slot calculation) are gameplay logic;
/// the biome color table and UI pixel config are kept as data so Godot
/// themes can consume them (contract doc 03 "decompose" disposition).
/// </summary>
public sealed record MapDisplayConfig(
    double DefaultZoom = 0.5, double MinZoom = 0.08, double MaxZoom = 4.0,
    double ZoomStep = 0.25, double ChunkRenderSize = 12, bool ShowGrid = true,
    bool ShowCoordinates = true, bool ShowPlayerMarker = true,
    bool ShowWaypointMarkers = true, bool CenterOnPlayer = true);

public sealed record MarkerConfig(
    (int, int, int) Color, double Size, string Shape, bool ShowLabel);

public sealed record WaypointSystemConfig(
    bool Enabled, bool SpawnAlwaysAvailable, string SpawnDefaultName,
    JsonArray SpawnPosition, JsonArray UnlockLevels, double MaxWaypoints,
    double TeleportCooldown, double TeleportManaCost, bool RequireSolidGround,
    double MinDistanceBetweenWaypoints, bool BlockedInDungeons,
    bool BlockedInCombat, double MaxNameLength, string DefaultNameFormat);

public sealed class MapWaypointConfig
{
    // map_waypoint_db.py:152-193 — default biome colors (verbatim)
    private static readonly Dictionary<string, (int, int, int)> DefaultBiomeColors = new()
    {
        ["peaceful_forest"] = (34, 139, 34), ["dangerous_forest"] = (0, 100, 0),
        ["rare_hidden_forest"] = (50, 205, 50), ["peaceful_cave"] = (105, 105, 105),
        ["dangerous_cave"] = (64, 64, 64), ["rare_deep_cave"] = (138, 43, 226),
        ["peaceful_quarry"] = (160, 82, 45), ["dangerous_quarry"] = (139, 69, 19),
        ["rare_ancient_quarry"] = (255, 140, 0), ["water_lake"] = (65, 105, 225),
        ["water_river"] = (70, 130, 180), ["water_cursed_swamp"] = (75, 0, 130),
        ["forest"] = (46, 139, 50), ["dense_thicket"] = (22, 100, 30),
        ["cave"] = (95, 95, 100), ["deep_cave"] = (60, 55, 80),
        ["quarry"] = (155, 120, 85), ["rocky_highlands"] = (130, 130, 120),
        ["wetland"] = (60, 110, 90), ["lake"] = (55, 100, 200),
        ["river"] = (65, 120, 185), ["flooded_cave"] = (70, 85, 130),
        ["rocky_forest"] = (75, 115, 65), ["crystal_cavern"] = (120, 80, 180),
        ["overgrown_ruins"] = (100, 110, 75), ["barren_waste"] = (140, 130, 110),
        ["cursed_marsh"] = (55, 70, 55), ["dense_forest"] = (22, 100, 30),
        ["rocky_forest_quarry"] = (75, 115, 65), ["crystal_cave"] = (120, 80, 180),
        ["rocky_quarry"] = (130, 130, 120), ["ruins_quarry"] = (100, 110, 75),
        ["barren_quarry"] = (140, 130, 110), ["unexplored"] = (30, 30, 40),
        ["spawn_area"] = (255, 215, 0),
    };

    public MapDisplayConfig MapDisplay { get; private set; } = new();
    public Dictionary<string, (int, int, int)> BiomeColors { get; } = new();
    public MarkerConfig PlayerMarker { get; private set; } =
        new((255, 255, 255), 8, "triangle", false);
    public MarkerConfig WaypointMarker { get; private set; } =
        new((255, 215, 0), 10, "diamond", true);
    public MarkerConfig DungeonMarker { get; private set; } =
        new((220, 20, 60), 8, "skull", false);
    public WaypointSystemConfig Waypoint { get; private set; } = Defaults();
    public JsonArray UiMapWindowSize { get; private set; } = new(700, 600);
    public double UiWaypointPanelWidth { get; private set; } = 200;
    public JsonArray UiBackgroundColor { get; private set; } = new(20, 20, 30, 240);
    public JsonArray UiBorderColor { get; private set; } = new(100, 100, 120);
    public JsonArray UiFontColor { get; private set; } = new(220, 220, 220);
    public bool Loaded { get; private set; }

    private static WaypointSystemConfig Defaults() => new(
        true, true, "Spawn", new JsonArray(0, 0),
        new JsonArray(5, 10, 15, 20, 25, 30), 7, 30.0, 0, true, 32, true, true,
        24, "Waypoint {number}");

    public void Load(string contentRoot)
    {
        var path = Path.Combine(contentRoot, "Definitions.JSON", "map-waypoint-config.JSON");
        if (!File.Exists(path))
        {
            ParseBiomeColors(new JsonObject());
            Loaded = true;  // _set_defaults marks loaded (py :278)
            return;
        }
        JsonObject data;
        try
        {
            data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
        }
        catch
        {
            ParseBiomeColors(new JsonObject());
            Loaded = true;
            return;
        }

        JsonObject Sect(string key) =>
            data.TryGetPropertyValue(key, out var n) && n is JsonObject o ? o : new JsonObject();

        var md = Sect("map_display");
        MapDisplay = new MapDisplayConfig(
            J.Num(md, "default_zoom", 0.5), J.Num(md, "min_zoom", 0.08),
            J.Num(md, "max_zoom", 4.0), J.Num(md, "zoom_step", 0.25),
            J.Num(md, "chunk_render_size", 12), J.Bool(md, "show_grid", true),
            J.Bool(md, "show_coordinates", true), J.Bool(md, "show_player_marker", true),
            J.Bool(md, "show_waypoint_markers", true), J.Bool(md, "center_on_player", true));

        ParseBiomeColors(Sect("biome_colors"));
        ParseMarkers(Sect("marker_icons"));
        ParseWaypointSystem(Sect("waypoint_system"));
        ParseUi(Sect("ui_settings"));
        Loaded = true;
    }

    private static (int, int, int) Color3(JsonObject o, string key, (int, int, int) def)
    {
        if (o.TryGetPropertyValue(key, out var n) && n is JsonArray a && a.Count >= 3)
            return ((int)a[0]!.GetValue<double>(), (int)a[1]!.GetValue<double>(),
                    (int)a[2]!.GetValue<double>());
        return def;
    }

    private void ParseBiomeColors(JsonObject data)
    {
        BiomeColors.Clear();
        foreach (var kv in DefaultBiomeColors)
            BiomeColors[kv.Key] = Color3(data, kv.Key, kv.Value);
    }

    private void ParseMarkers(JsonObject data)
    {
        JsonObject Sect(string key) =>
            data.TryGetPropertyValue(key, out var n) && n is JsonObject o ? o : new JsonObject();

        var player = Sect("player");
        PlayerMarker = new MarkerConfig(
            Color3(player, "color", (255, 255, 255)), J.Num(player, "size", 8),
            J.Str(player, "shape", "triangle"), false);

        var waypoint = Sect("waypoint");
        WaypointMarker = new MarkerConfig(
            Color3(waypoint, "color", (255, 215, 0)), J.Num(waypoint, "size", 10),
            J.Str(waypoint, "shape", "diamond"), J.Bool(waypoint, "show_label", true));

        var dungeon = Sect("dungeon");
        DungeonMarker = new MarkerConfig(
            Color3(dungeon, "color", (220, 20, 60)), J.Num(dungeon, "size", 8),
            J.Str(dungeon, "shape", "skull"), false);
    }

    private void ParseWaypointSystem(JsonObject data)
    {
        JsonObject Sect(string key) =>
            data.TryGetPropertyValue(key, out var n) && n is JsonObject o ? o : new JsonObject();

        var spawn = Sect("spawn_waypoint");
        var unlock = Sect("unlock_schedule");
        var placement = Sect("placement_rules");
        var naming = Sect("waypoint_naming");
        var cost = Sect("teleport_cost");

        var spawnPos = spawn.TryGetPropertyValue("position", out var sp) && sp is JsonArray spa
            ? (JsonArray)spa.DeepClone() : new JsonArray(0, 0);
        var unlockLevels = unlock.TryGetPropertyValue("levels", out var ul) && ul is JsonArray ula
            ? (JsonArray)ula.DeepClone() : new JsonArray(5, 10, 15, 20, 25, 30);

        // py :245 — mana cost only applies when teleport_cost.enabled
        var manaCost = J.Bool(cost, "enabled", false) ? J.Num(cost, "mana_cost", 0) : 0;

        Waypoint = new WaypointSystemConfig(
            J.Bool(data, "enabled", true),
            J.Bool(spawn, "always_available", true),
            J.Str(spawn, "default_name", "Spawn"),
            spawnPos, unlockLevels,
            J.Num(data, "max_waypoints", 7),
            J.Num(data, "teleport_cooldown", 30.0),
            manaCost,
            J.Bool(placement, "require_solid_ground", true),
            J.Num(placement, "min_distance_between_waypoints", 32),
            J.Bool(placement, "blocked_in_dungeons", true),
            J.Bool(placement, "blocked_in_combat", true),
            J.Num(naming, "max_name_length", 24),
            J.Str(naming, "default_name_format", "Waypoint {number}"));
    }

    private void ParseUi(JsonObject data)
    {
        UiMapWindowSize = data.TryGetPropertyValue("map_window_size", out var s)
                          && s is JsonArray sa && sa.Count >= 2
            ? new JsonArray(sa[0]!.DeepClone(), sa[1]!.DeepClone())
            : new JsonArray(700, 600);
        UiWaypointPanelWidth = J.Num(data, "waypoint_panel_width", 200);

        // py :264 — 4-component background, pad alpha 240 when only RGB given
        if (data.TryGetPropertyValue("background_color", out var bg) && bg is JsonArray bga)
            UiBackgroundColor = bga.Count >= 4
                ? new JsonArray(bga[0]!.DeepClone(), bga[1]!.DeepClone(),
                                bga[2]!.DeepClone(), bga[3]!.DeepClone())
                : new JsonArray(bga[0]!.DeepClone(), bga[1]!.DeepClone(),
                                bga[2]!.DeepClone(), 240);
        var border = Color3(data, "border_color", (100, 100, 120));
        UiBorderColor = new JsonArray(border.Item1, border.Item2, border.Item3);
        var font = Color3(data, "font_color", (220, 220, 220));
        UiFontColor = new JsonArray(font.Item1, font.Item2, font.Item3);
    }

    // py :280-289
    public (int, int, int) GetBiomeColor(string chunkType) =>
        BiomeColors.TryGetValue(chunkType.ToLowerInvariant(), out var c)
            ? c
            : BiomeColors.GetValueOrDefault("unexplored", (30, 30, 40));

    // py :291-311
    public int GetMaxWaypointsForLevel(int level)
    {
        if (!Waypoint.Enabled) return 0;
        var slots = Waypoint.SpawnAlwaysAvailable ? 1 : 0;
        foreach (var unlockLevel in Waypoint.UnlockLevels)
            if (unlockLevel is JsonValue v && v.TryGetValue<double>(out var ul) && level >= ul)
                slots += 1;
        return Math.Min(slots, (int)Waypoint.MaxWaypoints);
    }
}
