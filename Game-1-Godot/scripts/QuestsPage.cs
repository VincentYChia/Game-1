using Godot;

namespace Game1.Godot;

/// <summary>
/// Quest log book page ([J], systems/quest_log_overlay.py). Active quests
/// with objective + live baseline-delta progress and a red Abandon button
/// per quest (no rollback); completed count in the header.
/// </summary>
public partial class QuestsPage : MenuPage
{
    public override string Title => "Quests";
    public override Key Keybind => Key.J;

    private readonly CombatWorld _combat;
    private Label _header = null!;
    private VBoxContainer _list = null!;
    private double _refresh;

    public QuestsPage(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 8);
        box.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(box);

        _header = new Label { Text = "Quest Log" };
        _header.AddThemeFontSizeOverride("font_size", 26);
        box.AddChild(_header);

        var scroll = new ScrollContainer
        { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        box.AddChild(scroll);
        _list = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        _list.AddThemeConstantOverride("separation", 6);
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

        _header.Text = $"Quest Log   ·   Active: {quests.ActiveQuests.Count}"
                       + $"   Completed: {quests.CompletedQuests.Count}";

        foreach (var child in _list.GetChildren()) child.QueueFree();

        if (quests.ActiveQuests.Count == 0)
        {
            var empty = new Label
            { Text = "No active quests. Talk to an NPC to start one." };
            empty.AddThemeFontSizeOverride("font_size", 15);
            empty.Modulate = new Color(1, 1, 1, 0.6f);
            _list.AddChild(empty);
            return;
        }

        foreach (var (id, quest) in quests.ActiveQuests.ToList())
        {
            var row = new HBoxContainer();
            row.AddThemeConstantOverride("separation", 12);
            _list.AddChild(row);

            var progress = quests.Progress(quest);
            var progressText = string.Join("   ", progress.Select(p =>
                $"{CombatWorld.Prettify(p.Label)}: {p.Have}/{p.Need}"));
            var ready = quests.CheckCompletion(quest);
            var desc = quest.Def.Description.Length > 80
                ? quest.Def.Description[..80] + "..." : quest.Def.Description;

            var label = new Label
            {
                Text = $"{quest.Def.Title}"
                       + (ready ? "   — READY TO TURN IN" : "") + $"\n{desc}\n"
                       + $"{progressText}   ·   return to {quest.Def.ReturnTo}",
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
                AutowrapMode = TextServer.AutowrapMode.WordSmart,
            };
            label.AddThemeFontSizeOverride("font_size", 15);
            if (ready) label.Modulate = new Color(0.6f, 1f, 0.6f);
            row.AddChild(label);

            var abandon = new Button
            { Text = "Abandon", CustomMinimumSize = new Vector2(90, 0) };
            abandon.AddThemeFontSizeOverride("font_size", 13);
            abandon.Modulate = new Color(1f, 0.5f, 0.45f);
            var captured = id;
            abandon.Pressed += () =>
            {
                quests.AbandonQuest(captured);
                Refresh();
            };
            row.AddChild(abandon);

            _list.AddChild(new HSeparator());
        }
    }
}
