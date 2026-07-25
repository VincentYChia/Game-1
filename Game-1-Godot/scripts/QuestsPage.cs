using Godot;

namespace Game1.Godot;

/// <summary>
/// Quest log book page ([J], systems/quest_log_overlay.py) — recreating +
/// improving the 2D quest log: a scrolling column of vibrant bordered cards.
/// Each active quest is a solid PanelContainer with an accent title
/// ("READY TO TURN IN" in green when CheckCompletion is true), a wrapped
/// description, a live baseline-delta progress line from Progress(q), and a
/// red Abandon button (no rollback). The header shows Active/Completed counts.
/// </summary>
public partial class QuestsPage : MenuPage
{
    public override string Title => "Quests";
    public override Key Keybind => Key.J;

    private static readonly Color Green = new(0.42f, 0.95f, 0.5f);
    private static readonly Color AbandonRed = new(0.65f, 0.20f, 0.22f);
    private static readonly Color AbandonBorder = new(0.95f, 0.42f, 0.40f);

    private readonly CombatWorld _combat;
    private Label _header = null!;
    private VBoxContainer _list = null!;
    private double _refresh;

    public QuestsPage(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        var outer = new VBoxContainer();
        outer.AddThemeConstantOverride("separation", 14);
        outer.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(outer);

        outer.AddChild(UiTheme.Header("Quest Log"));

        _header = UiTheme.Section("Active: 0    Completed: 0", 21);
        outer.AddChild(_header);

        var scroll = UiTheme.VScroll();
        outer.AddChild(scroll);

        _list = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        _list.AddThemeConstantOverride("separation", 14);
        scroll.AddChild(_list);
    }

    public override void OnOpened() => Refresh();

    public override void Tick(double delta)
    {
        _refresh += delta;
        if (_refresh >= 0.5)
        {
            _refresh = 0;
            Refresh();
        }
    }

    private void Refresh()
    {
        var quests = _combat.QuestMgr;
        if (quests is null) return;

        _header.Text = $"Active: {quests.ActiveQuests.Count}"
                       + $"    Completed: {quests.CompletedQuests.Count}";

        foreach (var child in _list.GetChildren()) child.QueueFree();

        if (quests.ActiveQuests.Count == 0)
        {
            var emptyCard = new PanelContainer
            { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
            emptyCard.AddThemeStyleboxOverride("panel",
                UiTheme.Box(UiTheme.PanelInner, UiTheme.Border, 2, 10));
            var empty = new Label
            {
                Text = "No active quests.\nTalk to an NPC to start one.",
                HorizontalAlignment = HorizontalAlignment.Center,
            };
            empty.AddThemeFontSizeOverride("font_size", 18);
            empty.Modulate = new Color(1, 1, 1, 0.6f);
            emptyCard.AddChild(empty);
            _list.AddChild(emptyCard);
            return;
        }

        foreach (var (id, quest) in quests.ActiveQuests.ToList())
        {
            var ready = quests.CheckCompletion(quest);
            var progress = quests.Progress(quest);
            var progressText = progress.Count == 0
                ? "In progress"
                : string.Join("      ", progress.Select(p =>
                    $"{CombatWorld.Prettify(p.Label)}  {p.Have}/{p.Need}"));

            // -- card shell --
            var card = new PanelContainer
            { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
            card.AddThemeStyleboxOverride("panel", UiTheme.Box(
                UiTheme.PanelInner,
                ready ? Green : UiTheme.Border,
                ready ? 3 : 2, 10));
            _list.AddChild(card);

            var pad = new MarginContainer();
            foreach (var s in new[] { "left", "right", "top", "bottom" })
                pad.AddThemeConstantOverride($"margin_{s}", 14);
            card.AddChild(pad);

            var body = new VBoxContainer();
            body.AddThemeConstantOverride("separation", 8);
            pad.AddChild(body);

            // -- title row: quest title + Abandon button --
            var titleRow = new HBoxContainer();
            titleRow.AddThemeConstantOverride("separation", 12);
            body.AddChild(titleRow);

            var title = new Label
            {
                Text = quest.Def.Title,
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
                SizeFlagsVertical = Control.SizeFlags.ShrinkCenter,
            };
            title.AddThemeFontSizeOverride("font_size", 24);
            title.AddThemeColorOverride("font_color", UiTheme.Accent);
            titleRow.AddChild(title);

            if (ready)
            {
                var badge = new Label
                {
                    Text = "READY TO TURN IN",
                    SizeFlagsVertical = Control.SizeFlags.ShrinkCenter,
                };
                badge.AddThemeFontSizeOverride("font_size", 16);
                badge.AddThemeColorOverride("font_color", Green);
                titleRow.AddChild(badge);
            }

            var abandon = UiTheme.TextButton("Abandon", 16);
            abandon.CustomMinimumSize = new Vector2(110, 40);
            abandon.SizeFlagsVertical = Control.SizeFlags.ShrinkCenter;
            abandon.AddThemeColorOverride("font_color", UiTheme.Text);
            abandon.AddThemeStyleboxOverride("normal",
                UiTheme.Box(AbandonRed, AbandonBorder, 2, 8));
            abandon.AddThemeStyleboxOverride("hover",
                UiTheme.Box(AbandonBorder, AbandonBorder, 2, 8));
            abandon.AddThemeStyleboxOverride("pressed",
                UiTheme.Box(AbandonRed, AbandonBorder, 3, 8));
            var captured = id;
            abandon.Pressed += () =>
            {
                quests.AbandonQuest(captured);
                Refresh();
            };
            titleRow.AddChild(abandon);

            // -- description --
            var desc = new Label
            {
                Text = quest.Def.Description,
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
                AutowrapMode = TextServer.AutowrapMode.WordSmart,
            };
            desc.AddThemeFontSizeOverride("font_size", 17);
            desc.AddThemeColorOverride("font_color", UiTheme.Text);
            body.AddChild(desc);

            // -- progress line --
            var progLabel = new Label
            {
                Text = progressText,
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
                AutowrapMode = TextServer.AutowrapMode.WordSmart,
            };
            progLabel.AddThemeFontSizeOverride("font_size", 18);
            progLabel.AddThemeColorOverride("font_color", ready ? Green : UiTheme.Accent);
            body.AddChild(progLabel);

            // -- return-to footer --
            var footer = new Label
            {
                Text = $"Return to {CombatWorld.Prettify(quest.Def.ReturnTo)}",
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            };
            footer.AddThemeFontSizeOverride("font_size", 15);
            footer.Modulate = new Color(1, 1, 1, 0.55f);
            body.AddChild(footer);
        }
    }
}
