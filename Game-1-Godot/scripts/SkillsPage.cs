using Game1.Core.Progression;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Skills book page ([K]) over the ported SkillManager. Python semantics
/// (game_engine.py:3155-3193): click a learned skill → equip into the FIRST
/// empty hotbar slot; click an occupied hotbar slot → unequip; click an
/// available skill → learn it (grayed with the reason when requirements
/// aren't met).
/// </summary>
public partial class SkillsPage : MenuPage
{
    public override string Title => "Skills";
    public override Key Keybind => Key.K;

    private readonly CombatWorld _combat;
    private readonly List<Button> _hotbarButtons = new();
    private VBoxContainer _learnedList = null!;
    private VBoxContainer _availableList = null!;
    private Label _status = null!;

    public SkillsPage(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 8);
        box.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(box);

        var title = new Label { Text = "Skills" };
        title.AddThemeFontSizeOverride("font_size", 26);
        box.AddChild(title);

        var hotbarTitle = new Label { Text = "Hotbar  (click a slot to unequip)" };
        hotbarTitle.AddThemeFontSizeOverride("font_size", 17);
        box.AddChild(hotbarTitle);
        var hotbarRow = new HBoxContainer();
        hotbarRow.AddThemeConstantOverride("separation", 8);
        box.AddChild(hotbarRow);
        for (var i = 0; i < SkillManager.HotbarSlots; i++)
        {
            var slot = i;
            var btn = new Button
            { Text = $"[{i + 1}] —", CustomMinimumSize = new Vector2(150, 44) };
            btn.AddThemeFontSizeOverride("font_size", 14);
            btn.Pressed += () =>
            {
                _combat.SkillMgr?.Unequip(slot);
                Refresh();
            };
            hotbarRow.AddChild(btn);
            _hotbarButtons.Add(btn);
        }

        var columns = new HBoxContainer
        { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        columns.AddThemeConstantOverride("separation", 20);
        box.AddChild(columns);

        (_learnedList, var learnedScroll) = MakeColumn(columns,
            "Learned  (click to equip)");
        (_availableList, _) = MakeColumn(columns, "Available  (click to learn)");

        _status = new Label { Text = "" };
        _status.AddThemeFontSizeOverride("font_size", 15);
        _status.Modulate = new Color(1f, 0.9f, 0.6f);
        box.AddChild(_status);
    }

    private static (VBoxContainer List, ScrollContainer Scroll) MakeColumn(
        HBoxContainer parent, string heading)
    {
        var col = new VBoxContainer
        {
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        parent.AddChild(col);
        var label = new Label { Text = heading };
        label.AddThemeFontSizeOverride("font_size", 17);
        col.AddChild(label);
        var scroll = new ScrollContainer
        {
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
            CustomMinimumSize = new Vector2(0, 380),
        };
        col.AddChild(scroll);
        var list = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        scroll.AddChild(list);
        return (list, scroll);
    }

    public override void OnOpened()
    {
        _status.Text = "";
        Refresh();
    }

    private void Refresh()
    {
        var mgr = _combat.SkillMgr;
        var db = _combat.SkillDb;
        if (mgr is null || db is null) return;

        for (var i = 0; i < _hotbarButtons.Count; i++)
        {
            var id = mgr.Equipped[i];
            var name = id is not null ? db.Skills.GetValueOrDefault(id)?.Name ?? id : "—";
            _hotbarButtons[i].Text = $"[{i + 1}] {name}";
        }

        foreach (var child in _learnedList.GetChildren()) child.QueueFree();
        foreach (var child in _availableList.GetChildren()) child.QueueFree();

        foreach (var (id, ps) in mgr.Known.OrderBy(k => k.Key, StringComparer.Ordinal))
        {
            var def = db.Skills.GetValueOrDefault(id);
            if (def is null) continue;
            var cost = mgr.ManaCostOf(def);
            var cd = mgr.CooldownOf(def);
            var btn = new Button
            {
                Text = $"{def.Name}  (Lv{ps.Level})  T{(int)def.Tier}  "
                       + $"{(int)cost}MP  cd {(int)cd}s"
                       + (ps.IsEquipped ? "  [equipped]" : ""),
                Alignment = HorizontalAlignment.Left,
                TooltipText = def.Description,
            };
            btn.AddThemeFontSizeOverride("font_size", 14);
            var captured = id;
            btn.Pressed += () =>
            {
                if (!mgr.EquipFirstEmpty(captured))
                    _status.Text = "All hotbar slots full!";
                Refresh();
            };
            _learnedList.AddChild(btn);
        }

        foreach (var (id, def) in db.Skills.OrderBy(
                     k => (k.Value.Tier, k.Key), Comparer<(double, string)>.Default))
        {
            if (mgr.Known.ContainsKey(id)) continue;
            var (ok, reason) = mgr.CanLearn(id);
            var btn = new Button
            {
                Text = $"T{(int)def.Tier}  {def.Name}"
                       + (ok ? "" : $"   — {reason}"),
                Alignment = HorizontalAlignment.Left,
                Disabled = !ok,
                TooltipText = def.Description,
            };
            btn.AddThemeFontSizeOverride("font_size", 14);
            if (!ok) btn.Modulate = new Color(1, 1, 1, 0.55f);
            var captured = id;
            btn.Pressed += () =>
            {
                if (mgr.Learn(captured))
                    _status.Text = $"learned {def.Name}!";
                Refresh();
            };
            _availableList.AddChild(btn);
        }
    }
}
