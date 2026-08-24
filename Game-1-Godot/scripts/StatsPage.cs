using System.Text.Json.Nodes;
using Game1.Core.Progression;
using Godot;

namespace Game1.Godot;

/// <summary>
/// CHARACTER stats book page ([C] — Python's stats window, renderer.py:
/// 7592-7702). Three vibrant panels: STATS with +1 allocation buttons while
/// unallocated points remain (permanent, no respec); TITLES (last 8
/// earned, tier-colored cards, passive — no equip mechanic exists); PROGRESS
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
    private VBoxContainer _titlesList = null!;
    private VBoxContainer _progressList = null!;
    private Label _header = null!;

    // per-stat one-line descriptions of what the point buys
    private static readonly Dictionary<string, string> StatBlurb = new()
    {
        ["strength"] = "mining / melee damage",
        ["defense"] = "damage reduction",
        ["vitality"] = "max health",
        ["luck"] = "resource quality",
        ["agility"] = "forestry / attack speed",
        ["intelligence"] = "mana / elemental",
    };

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
        box.AddThemeConstantOverride("separation", 16);
        box.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(box);

        _header = UiTheme.Header("CHARACTER", 36);
        box.AddChild(_header);

        var columns = new HBoxContainer
        { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        columns.AddThemeConstantOverride("separation", 20);
        box.AddChild(columns);

        // -- panel 1: stats + allocation --
        var statsCol = BuildPanel(320, expand: false, out var statsBody);
        columns.AddChild(statsCol);
        statsBody.AddChild(UiTheme.Section("STATS", 24));

        _pointsLabel = new Label { Text = "" };
        _pointsLabel.AddThemeFontSizeOverride("font_size", 22);
        _pointsLabel.AddThemeColorOverride("font_color", UiTheme.Accent);
        statsBody.AddChild(_pointsLabel);

        // display scaling = the stats-screen JSON values (contract)
        foreach (var (stat, label, scale) in new[]
                 {
                     ("strength", "STR", 0.05), ("defense", "DEF", 0.02),
                     ("vitality", "VIT", 0.01), ("luck", "LCK", 0.02),
                     ("agility", "AGI", 0.05), ("intelligence", "INT", 0.02),
                 })
        {
            var rowPanel = new PanelContainer();
            rowPanel.AddThemeStyleboxOverride("panel",
                UiTheme.Box(UiTheme.SlotBg, UiTheme.Border, 1, 6));
            statsBody.AddChild(rowPanel);

            var row = new HBoxContainer();
            row.AddThemeConstantOverride("separation", 10);
            rowPanel.AddChild(row);

            var textCol = new VBoxContainer
            { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
            textCol.AddThemeConstantOverride("separation", 0);
            row.AddChild(textCol);

            var rowLabel = new Label { Text = $"{label}: 0  (+0%)" };
            rowLabel.AddThemeFontSizeOverride("font_size", 20);
            rowLabel.AddThemeColorOverride("font_color", UiTheme.Text);
            textCol.AddChild(rowLabel);

            var blurb = new Label { Text = StatBlurb[stat] };
            blurb.AddThemeFontSizeOverride("font_size", 14);
            blurb.AddThemeColorOverride("font_color", new Color(0.65f, 0.72f, 0.88f));
            textCol.AddChild(blurb);

            var plus = new Button
            {
                Text = "+1",
                Visible = false,
                CustomMinimumSize = new Vector2(52, 44),
                SizeFlagsVertical = Control.SizeFlags.ShrinkCenter,
            };
            plus.AddThemeFontSizeOverride("font_size", 20);
            plus.AddThemeColorOverride("font_color", new Color(0.1f, 0.14f, 0.1f));
            plus.AddThemeStyleboxOverride("normal",
                UiTheme.Box(new Color(0.35f, 0.82f, 0.38f), new Color(0.5f, 1f, 0.5f), 2, 6));
            plus.AddThemeStyleboxOverride("hover",
                UiTheme.Box(new Color(0.45f, 0.95f, 0.48f), UiTheme.Accent, 2, 6));
            plus.AddThemeStyleboxOverride("pressed",
                UiTheme.Box(new Color(0.30f, 0.70f, 0.33f), UiTheme.Accent, 2, 6));
            var captured = stat;
            plus.Pressed += () =>
            {
                if (_combat.Pc?.AllocateStatPoint(captured) == true) Refresh();
            };
            row.AddChild(plus);
            _rows.Add((rowLabel, plus, stat, scale));
        }

        // -- panel 2: titles --
        var titlesCol = BuildPanel(420, expand: true, out var titlesBody);
        columns.AddChild(titlesCol);
        titlesBody.AddChild(UiTheme.Section("TITLES", 24));
        var titlesScroll = UiTheme.VScroll();
        titlesBody.AddChild(titlesScroll);
        _titlesList = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        _titlesList.AddThemeConstantOverride("separation", 10);
        titlesScroll.AddChild(_titlesList);

        // -- panel 3: progress --
        var progCol = BuildPanel(380, expand: true, out var progBody);
        columns.AddChild(progCol);
        progBody.AddChild(UiTheme.Section("PROGRESS", 24));
        var progScroll = UiTheme.VScroll();
        progBody.AddChild(progScroll);
        _progressList = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        _progressList.AddThemeConstantOverride("separation", 12);
        progScroll.AddChild(_progressList);
    }

    /// <summary>A solid bordered panel with an inner padded VBox body.</summary>
    private static PanelContainer BuildPanel(int minWidth, bool expand,
                                             out VBoxContainer body)
    {
        var panel = new PanelContainer
        {
            CustomMinimumSize = new Vector2(minWidth, 0),
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
            SizeFlagsHorizontal = expand
                ? Control.SizeFlags.ExpandFill
                : Control.SizeFlags.Fill,
        };
        panel.AddThemeStyleboxOverride("panel",
            UiTheme.Box(UiTheme.PanelInner, UiTheme.Border, 2, 10));

        var margin = new MarginContainer();
        foreach (var s in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{s}", 16);
        panel.AddChild(margin);

        body = new VBoxContainer();
        body.AddThemeConstantOverride("separation", 12);
        margin.AddChild(body);
        return panel;
    }

    public override void OnOpened() => Refresh();

    public override void Tick(double delta) { }

    private void Refresh()
    {
        var pc = _combat.Pc;
        if (pc is null) return;

        _header.Text = $"CHARACTER — Level {pc.Leveling.Level}";
        var points = pc.Leveling.UnallocatedStatPoints;
        _pointsLabel.Text = points > 0 ? $"★  {points} Points to Spend" : "All points spent";
        _pointsLabel.AddThemeColorOverride("font_color",
            points > 0 ? UiTheme.Accent : new Color(0.6f, 0.66f, 0.8f));

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

        RefreshTitles(pc);
        RefreshProgress(pc);
    }

    // titles: LAST 8 earned, tier-colored cards (icon + name + bonus)
    private void RefreshTitles(PlayerCharacter pc)
    {
        foreach (var child in _titlesList.GetChildren()) child.QueueFree();

        var earned = pc.Titles.EarnedTitles;
        if (earned.Count == 0)
        {
            var empty = new Label
            {
                Text = "Keep playing to earn titles!",
                AutowrapMode = TextServer.AutowrapMode.WordSmart,
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            };
            empty.AddThemeFontSizeOverride("font_size", 18);
            empty.AddThemeColorOverride("font_color", new Color(0.65f, 0.72f, 0.88f));
            _titlesList.AddChild(empty);
            return;
        }

        var count = new Label { Text = $"Earned: {earned.Count}" };
        count.AddThemeFontSizeOverride("font_size", 17);
        count.AddThemeColorOverride("font_color", UiTheme.Accent);
        _titlesList.AddChild(count);

        foreach (var t in earned.TakeLast(8))
        {
            var tier = (t.Tier ?? "novice").ToLowerInvariant();
            var color = TierColors.GetValueOrDefault(tier, TierColors["novice"]);

            var card = new PanelContainer
            { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
            card.AddThemeStyleboxOverride("panel",
                UiTheme.Box(UiTheme.SlotBg, color, 2, 8));
            _titlesList.AddChild(card);

            var rowH = new HBoxContainer();
            rowH.AddThemeConstantOverride("separation", 12);
            card.AddChild(rowH);

            // icon on the left (titles/{id}.png) — falls back to a colored dot
            var tex = IconCache.Get(t.IconPath);
            if (tex is not null)
            {
                var iconRect = new TextureRect
                {
                    Texture = tex,
                    ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
                    StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                    CustomMinimumSize = new Vector2(52, 52),
                    SizeFlagsVertical = Control.SizeFlags.ShrinkCenter,
                };
                rowH.AddChild(iconRect);
            }
            else
            {
                var dot = new Label
                {
                    Text = "★",
                    CustomMinimumSize = new Vector2(52, 52),
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment = VerticalAlignment.Center,
                };
                dot.AddThemeFontSizeOverride("font_size", 30);
                dot.AddThemeColorOverride("font_color", color);
                rowH.AddChild(dot);
            }

            var textCol = new VBoxContainer
            { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
            textCol.AddThemeConstantOverride("separation", 2);
            rowH.AddChild(textCol);

            var nameLbl = new Label { Text = $"{t.Name}  [{tier}]" };
            nameLbl.AddThemeFontSizeOverride("font_size", 19);
            nameLbl.AddThemeColorOverride("font_color", color);
            textCol.AddChild(nameLbl);

            var bonus = new Label
            {
                Text = t.BonusDescription,
                AutowrapMode = TextServer.AutowrapMode.WordSmart,
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            };
            bonus.AddThemeFontSizeOverride("font_size", 16);
            bonus.AddThemeColorOverride("font_color", UiTheme.Text);
            textCol.AddChild(bonus);
        }
    }

    // progress: nearest unearned title per activity; mining/forestry
    // always shown, others only when count > 0; max 5 rows
    private void RefreshProgress(PlayerCharacter pc)
    {
        foreach (var child in _progressList.GetChildren()) child.QueueFree();

        var titleDb = _combat.TitleDb;
        var rows = new List<(string Activity, string NextName, int Have, int Need)>();
        if (titleDb is not null)
        {
            var shown = new HashSet<string>();
            foreach (var activity in new[]
                     { "mining", "forestry", "smithing", "refining", "alchemy" })
            {
                if (rows.Count >= 5 || shown.Contains(activity)) continue;
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
                    rows.Add((activity, n.Name, count, (int)n.Threshold));
            }
        }

        if (rows.Count == 0)
        {
            var empty = new Label
            {
                Text = "Start gathering and crafting!",
                AutowrapMode = TextServer.AutowrapMode.WordSmart,
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            };
            empty.AddThemeFontSizeOverride("font_size", 18);
            empty.AddThemeColorOverride("font_color", new Color(0.65f, 0.72f, 0.88f));
            _progressList.AddChild(empty);
            return;
        }

        foreach (var (activity, nextName, have, need) in rows)
        {
            var frac = need > 0 ? Math.Clamp((float)have / need, 0f, 1f) : 0f;

            var card = new PanelContainer
            { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
            card.AddThemeStyleboxOverride("panel",
                UiTheme.Box(UiTheme.SlotBg, UiTheme.Border, 1, 8));
            _progressList.AddChild(card);

            var body = new VBoxContainer
            { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
            body.AddThemeConstantOverride("separation", 6);
            card.AddChild(body);

            var head = new HBoxContainer();
            body.AddChild(head);
            var actLbl = new Label
            {
                Text = CombatWorld.Prettify(activity),
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            };
            actLbl.AddThemeFontSizeOverride("font_size", 19);
            actLbl.AddThemeColorOverride("font_color", UiTheme.Text);
            head.AddChild(actLbl);
            var frac2 = new Label { Text = $"{have}/{need}" };
            frac2.AddThemeFontSizeOverride("font_size", 18);
            frac2.AddThemeColorOverride("font_color", UiTheme.Accent);
            head.AddChild(frac2);

            var bar = new ProgressBar
            {
                MinValue = 0,
                MaxValue = 1,
                Value = frac,
                ShowPercentage = false,
                CustomMinimumSize = new Vector2(0, 20),
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            };
            bar.AddThemeStyleboxOverride("background",
                UiTheme.Box(UiTheme.SlotEmpty, UiTheme.Border, 1, 6));
            bar.AddThemeStyleboxOverride("fill",
                UiTheme.Box(new Color(0.4f, 0.85f, 0.45f), null, 0, 6));
            body.AddChild(bar);

            var nextLbl = new Label
            {
                Text = $"Next: {nextName}",
                AutowrapMode = TextServer.AutowrapMode.WordSmart,
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            };
            nextLbl.AddThemeFontSizeOverride("font_size", 15);
            nextLbl.AddThemeColorOverride("font_color", new Color(0.7f, 0.78f, 0.95f));
            body.AddChild(nextLbl);
        }
    }

    private readonly record struct TitleDefBrief(string Name, double Threshold);
}
