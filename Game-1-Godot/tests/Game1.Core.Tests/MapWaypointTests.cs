using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Content;
using Game1.Core.Data;
using Xunit;

namespace Game1.Core.Tests;

public class MapWaypointTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/map_waypoint.json");

    private static MapWaypointConfig Load()
    {
        var cfg = new MapWaypointConfig();
        cfg.Load(ContentPaths.TryGetContentRoot()!);
        return cfg;
    }

    private static JsonArray Rgb((int, int, int) c) => new(c.Item1, c.Item2, c.Item3);

    [Fact]
    public void ResolvedConfig_MatchesPython()
    {
        var cfg = Load();
        Assert.Equal(G.GetProperty("loaded").GetBoolean(), cfg.Loaded);

        var actual = new JsonObject
        {
            ["map_display"] = new JsonObject
            {
                ["default_zoom"] = cfg.MapDisplay.DefaultZoom,
                ["min_zoom"] = cfg.MapDisplay.MinZoom,
                ["max_zoom"] = cfg.MapDisplay.MaxZoom,
                ["zoom_step"] = cfg.MapDisplay.ZoomStep,
                ["chunk_render_size"] = cfg.MapDisplay.ChunkRenderSize,
                ["show_grid"] = cfg.MapDisplay.ShowGrid,
                ["show_coordinates"] = cfg.MapDisplay.ShowCoordinates,
                ["show_player_marker"] = cfg.MapDisplay.ShowPlayerMarker,
                ["show_waypoint_markers"] = cfg.MapDisplay.ShowWaypointMarkers,
                ["center_on_player"] = cfg.MapDisplay.CenterOnPlayer,
            },
            ["player_marker"] = Marker(cfg.PlayerMarker),
            ["waypoint_marker"] = Marker(cfg.WaypointMarker),
            ["dungeon_marker"] = Marker(cfg.DungeonMarker),
            ["waypoint"] = new JsonObject
            {
                ["enabled"] = cfg.Waypoint.Enabled,
                ["spawn_always_available"] = cfg.Waypoint.SpawnAlwaysAvailable,
                ["spawn_default_name"] = cfg.Waypoint.SpawnDefaultName,
                ["spawn_position"] = cfg.Waypoint.SpawnPosition.DeepClone(),
                ["unlock_levels"] = cfg.Waypoint.UnlockLevels.DeepClone(),
                ["max_waypoints"] = cfg.Waypoint.MaxWaypoints,
                ["teleport_cooldown"] = cfg.Waypoint.TeleportCooldown,
                ["teleport_mana_cost"] = cfg.Waypoint.TeleportManaCost,
                ["require_solid_ground"] = cfg.Waypoint.RequireSolidGround,
                ["min_distance_between_waypoints"] = cfg.Waypoint.MinDistanceBetweenWaypoints,
                ["blocked_in_dungeons"] = cfg.Waypoint.BlockedInDungeons,
                ["blocked_in_combat"] = cfg.Waypoint.BlockedInCombat,
                ["max_name_length"] = cfg.Waypoint.MaxNameLength,
                ["default_name_format"] = cfg.Waypoint.DefaultNameFormat,
            },
            ["ui"] = new JsonObject
            {
                ["map_window_size"] = cfg.UiMapWindowSize.DeepClone(),
                ["waypoint_panel_width"] = cfg.UiWaypointPanelWidth,
                ["background_color"] = cfg.UiBackgroundColor.DeepClone(),
                ["border_color"] = cfg.UiBorderColor.DeepClone(),
                ["font_color"] = cfg.UiFontColor.DeepClone(),
            },
        };
        foreach (var key in new[]
                 { "map_display", "player_marker", "waypoint_marker", "dungeon_marker", "waypoint", "ui" })
        {
            var diffs = JsonTreeComparer.Diff(G.GetProperty(key), actual[key]);
            Assert.True(diffs.Count == 0, $"{key}: " + string.Join("; ", diffs.Take(10)));
        }

        var biome = new JsonObject();
        foreach (var kv in cfg.BiomeColors)
            biome[kv.Key] = Rgb(kv.Value);
        var biomeDiffs = JsonTreeComparer.Diff(G.GetProperty("biome_colors"), biome);
        Assert.True(biomeDiffs.Count == 0, "biome_colors: " + string.Join("; ", biomeDiffs.Take(10)));
        return;

        static JsonObject Marker(MarkerConfig m) => new()
        {
            ["color"] = new JsonArray(m.Color.Item1, m.Color.Item2, m.Color.Item3),
            ["size"] = m.Size,
            ["shape"] = m.Shape,
            ["show_label"] = m.ShowLabel,
        };
    }

    [Fact]
    public void Lookups_MatchPythonExecution()
    {
        var cfg = Load();
        foreach (var e in G.GetProperty("biome_color_lookup").EnumerateObject())
        {
            var diffs = JsonTreeComparer.Diff(e.Value, Rgb(cfg.GetBiomeColor(e.Name)));
            Assert.True(diffs.Count == 0, $"biome_lookup[{e.Name}]: " + string.Join("; ", diffs));
        }
        foreach (var e in G.GetProperty("max_waypoints_by_level").EnumerateObject())
            Assert.Equal(e.Value.GetInt32(), cfg.GetMaxWaypointsForLevel(int.Parse(e.Name)));
    }
}
