using System.Text.Json.Nodes;
using Godot;

namespace Game1.Godot;

/// <summary>
/// CHARACTER stats book page ([C] — Python's stats window, renderer.py:
/// 7592-7702). Three columns: STATS with +1 allocation buttons while
/// unallocated points remain (permanent, no respec); TITLES (last 8
/// earned, tier-colored, passive — no equip mechanic exists); PROGRESS
/// (nearest unearned title per activity, max 5 rows, mining/forestry
/// always shown). Display bonus percentages use the JSON per-point
/// values (LCK shows +2%/pt while combat crit uses 0.12 — preserved
/// mismatch per contract).
/// </summary>
public partial class StatsPage : MenuPage
{
    public override string Title => "Character";
    public override Key Keybind => Key.C;

    private readonly CombatWorld _combat;
    private Label _pointsLabel = null!;
    private readonly List<(Label Row, Button Plus, string Stat, double Scale)> _rows = new();
    private Label _titlesLabel = null!;
    private Label _progressLabel = null!;
    private Label _header = null!;

    private static readonly Dictionary<string, Color> TierColors = new()
    {
        ["novice"] = new Color(0.78f, 0.78f, 0.78f),
        ["apprentice"] = new Color(0.4f, 1f, 0.4f),
        ["journeyman"] = new Color(0.4f, 0.6f, 1f),
        ["expert"] = new Color(0.78f, 0.4f, 1f),
        ["master"] = new Color(1f, 0.84f, 0f),
    };

    public StatsPage(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 8);
        box.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(box);

        _header = new Label { Text = "CHARACTER" };
        _header.AddThemeFontSizeOverride("font_size", 26);
        _header.Modulate = new Color(1f, 0.84f, 0f);
        box.AddChild(_header);

        var columns = new HBoxContainer
        { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        columns.AddThemeConstantOverride("separation", 28);
        box.AddChild(columns);

        // -- column 1: stats + allocation --
        var statsCol = new VBoxContainer { CustomMinimumSize = new Vector2(280, 0) };
        statsCol.AddThemeConstantOverride("separation", 6);
        columns.AddChild(statsCol);
        var statsTitle = new Label { Text = "STATS" };
        statsTitle.AddThemeFontSizeOverride("font_size", 19);
        statsCol.AddChild(statsTitle);
        _pointsLabel = new Label { Text = "", Modulate = new Color(0.4f, 1f, 0.4f) };
        _pointsLabel.AddThemeFontSizeOverride("font_size", 16);
        statsCol.AddChild(_pointsLabel);

        // display scaling = the stats-screen JSON values (contract)
        foreach (var (stat, label, scale) in new[]
                 {
                     ("strength", "STR", 0.05), ("defense", "DEF", 0.02),
                     ("vitality", "VIT", 0.01), ("luck", "LCK", 0.02),
                     ("agility", "AGI", 0.05), ("intelligence", "INT", 0.02),
                 })
        {
            var row = new HBoxContainer();
            row.AddThemeConstantOverride("separation", 10);
            statsCol.AddChild(row);
            var rowLabel = new Label
            { Text = $"{label}: 0", CustomMinimumSize = new Vector2(170, 0) };
            rowLabel.AddThemeFontSizeOverride("font_size", 16);
            row.AddChild(rowLabel);
            var plus = new Button { Text = "+1", Visible = false };
            plus.AddThemeFontSizeOverride("font_size", 14);
            var captured = stat;
            plus.Pressed += () =>
            {
                if (_combat.Pc?.AllocateStatPoint(captured) == true) Refresh();
            };
            row.AddChild(plus);
            _rows.Add((rowLabel, plus, stat, scale));
        }

        // -- column 2: titles --
        var titlesCol = new VBoxContainer
        {
            CustomMinimumSize = new Vector2(420, 0),
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        columns.AddChild(titlesCol);
        var titlesTitle = new Label { Text = "TITLES" };
        titlesTitle.AddThemeFontSizeOverride("font_size", 22);
        titlesCol.AddChild(titlesTitle);
        var titlesScroll = new ScrollContainer
        {
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
            // Vertical-only: without this the label collapses to 0 width and
            // wraps one character per line
            HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled,
        };
        titlesCol.AddChild(titlesScroll);
        _titlesLabel = new Label
        {
            Text = "",
            AutowrapMode = TextServer.AutowrapMode.WordSmart,
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
        };
        _titlesLabel.AddThemeFontSizeOverride("font_size", 16);
        titlesScroll.AddChild(_titlesLabel);

        // -- column 3: progress --
        var progCol = new VBoxContainer
        {
            CustomMinimumSize = new Vector2(360, 0),
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
        };
        columns.AddChild(progCol);
        var progTitle = new Label { Text = "PROGRESS" };
        progTitle.AddThemeFontSizeOverride("font_size", 22);
        progCol.AddChild(progTitle);
        _progressLabel = new Label
        {
            Text = "",
            AutowrapMode = TextServer.AutowrapMode.WordSmart,
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
        };
        _progressLabel.AddThemeFontSizeOverride("font_size", 16);
        progCol.AddChild(_progressLabel);
    }

    public override void OnOpened() => Refresh();

    public override void Tick(double delta) { }

    private void Refresh()
    {
        var pc = _combat.Pc;
        if (pc is null) return;

        _header.Text = $"CHARACTER — Level {pc.Leveling.Level}";
        var points = pc.Leveling.UnallocatedStatPoints;
        _pointsLabel.Text = points > 0 ? $"Points: {points}" : "";

        foreach (var (row, plus, stat, scale) in _rows)
        {
            var value = stat switch
            {
                "strength" => pc.Stats.Strength,
                "defense" => pc.Stats.Defense,
                "vitality" => pc.Stats.Vitality,
                "luck" => pc.Stats.Luck,
                "agility" => pc.Stats.Agility,
                _ => pc.Stats.Intelligence,
            };
            var label = stat switch
            {
                "strength" => "STR", "defense" => "DEF", "vitality" => "VIT",
                "luck" => "LCK", "agility" => "AGI", _ => "INT",
            };
            row.Text = $"{label}: {value}  (+{value * scale * 100:F0}%)";
            plus.Visible = points > 0;
        }

        // titles: LAST 8 earned, tier-colored via BBCode-less plain text
        var earned = pc.Titles.EarnedTitles;
        if (earned.Count == 0)
        {
            _titlesLabel.Text = "Keep playing to earn titles!";
        }
        else
        {
            var lines = new List<string> { $"Earned: {earned.Count}" };
            foreach (var t in earned.TakeLast(8))
                lines.Add($"• {t.Name}  [{t.Tier}]\n   {t.BonusDescription}");
            _titlesLabel.Text = string.Join("\n", lines);
        }

        // progress: nearest unearned title per activity; mining/forestry
        // always shown, others only when count > 0; max 5 rows
        var titleDb = _combat.TitleDb;
        var lines2 = new List<string>();
        if (titleDb is not null)
        {
            var shown = new HashSet<string>();
            foreach (var activity in new[]
                     { "mining", "forestry", "smithing", "refining", "alchemy" })
            {
                if (lines2.Count >= 5 || shown.Contains(activity)) continue;
                var count = pc.Activities.GetCount(activity);
                if (count == 0 && activity is not ("mining" or "forestry")) continue;
                shown.Add(activity);

                TitleDefBrief? next = null;
                foreach (var t in titleDb.Titles.Values)
                {
                    if (t.ActivityType != activity) continue;
                    if (pc.Titles.EarnedTitles.Any(e => e.TitleId == t.TitleId)) continue;
                    var threshold = t.AcquisitionThreshold is JsonValue v
                                    && v.TryGetValue<double>(out var d) ? d : 0;
                    if (threshold <= count) continue;
                    if (next is null || threshold < next.Value.Threshold)
                        next = new TitleDefBrief(t.Name, threshold);
                }
                if (next is { } n)
                {
                    var frac = Math.Clamp(count / n.Threshold, 0, 1);
                    var bar = new string('█', (int)(frac * 14))
                              .PadRight(14, '░');
                    lines2.Add($"{activity}: {bar}  {count}/{(int)n.Threshold}"
                               + $"\n   Next: {n.Name}");
                }
            }
        }
        _progressLabel.Text = lines2.Count > 0
            ? string.Join("\n", lines2)
            : "Start gathering and crafting!";
    }

    private readonly record struct TitleDefBrief(string Name, double Threshold);
}
