using Game1.Core.Progression;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Skills book page ([K]) over the ported SkillManager. Python semantics
/// (game_engine.py:3155-3193): click a learned skill → equip into the FIRST
/// empty hotbar slot; click an occupied hotbar slot → unequip; click an
/// available skill → learn it (grayed with the reason when requirements
/// aren't met).
///
/// Visual: a top row of five big icon Slot widgets (the live hotbar), then two
/// filled, scrolling columns — Learned skill cards (icon + name + Lv + MP/cd)
/// and Available skill cards (icon + name, disabled with reason when locked).
/// </summary>
public partial class SkillsPage : MenuPage
{
    public override string Title => "Skills";
    public override Key Keybind => Key.K;

    private const int HotbarPx = 96;
    private const int CardIconPx = 52;

    private static readonly string[] TierName =
        { "novice", "novice", "apprentice", "journeyman", "expert", "master" };

    private readonly CombatWorld _combat;
    private readonly List<(TextureRect Icon, Label Qty, Button Btn)> _hotbar = new();
    private VBoxContainer _learnedList = null!;
    private VBoxContainer _availableList = null!;
    private Label _status = null!;

    public SkillsPage(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 14);
        box.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(box);

        box.AddChild(UiTheme.Header("Skills"));

        // -- hotbar row: five big icon slots --
        box.AddChild(UiTheme.Section("Hotbar  (click a slot to unequip)"));
        var hotbarRow = new HBoxContainer();
        hotbarRow.AddThemeConstantOverride("separation", 12);
        box.AddChild(hotbarRow);
        for (var i = 0; i < SkillManager.HotbarSlots; i++)
        {
            var slot = i;
            var cell = new VBoxContainer();
            cell.AddThemeConstantOverride("separation", 4);

            var key = new Label
            {
                Text = $"[{i + 1}]",
                HorizontalAlignment = HorizontalAlignment.Center,
            };
            key.AddThemeFontSizeOverride("font_size", 16);
            key.AddThemeColorOverride("font_color", UiTheme.Accent);
            cell.AddChild(key);

            var btn = UiTheme.Slot(HotbarPx, out var icon, out var qty);
            btn.AddThemeFontSizeOverride("font_size", 13);
            btn.Pressed += () =>
            {
                _combat.SkillMgr?.Unequip(slot);
                Refresh();
            };
            cell.AddChild(btn);
            hotbarRow.AddChild(cell);
            _hotbar.Add((icon, qty, btn));
        }

        // -- two filled, scrolling columns --
        var columns = new HBoxContainer
        { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        columns.AddThemeConstantOverride("separation", 24);
        box.AddChild(columns);

        _learnedList = MakeColumn(columns, "Learned  (click to equip)");
        _availableList = MakeColumn(columns, "Available  (click to learn)");

        _status = new Label { Text = "" };
        _status.AddThemeFontSizeOverride("font_size", 17);
        _status.Modulate = UiTheme.Accent;
        box.AddChild(_status);
    }

    private static VBoxContainer MakeColumn(HBoxContainer parent, string heading)
    {
        var col = new VBoxContainer
        {
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        col.AddThemeConstantOverride("separation", 8);
        parent.AddChild(col);

        col.AddChild(UiTheme.Section(heading, 20));

        var scroll = UiTheme.VScroll();
        col.AddChild(scroll);

        var list = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        list.AddThemeConstantOverride("separation", 8);
        scroll.AddChild(list);
        return list;
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

        for (var i = 0; i < _hotbar.Count; i++)
        {
            var (icon, qty, btn) = _hotbar[i];
            var id = mgr.Equipped[i];
            var def = id is not null ? db.Skills.GetValueOrDefault(id) : null;
            if (def is null)
            {
                icon.Texture = null;
                qty.Text = "";
                btn.Text = "—";
                btn.AddThemeColorOverride("font_color", new Color(0.5f, 0.55f, 0.7f));
                btn.AddThemeStyleboxOverride("normal",
                    UiTheme.Box(UiTheme.SlotEmpty, UiTheme.Border, 1, 6));
                continue;
            }
            var tier = TierColor(def.Tier);
            icon.Texture = IconCache.Get(def.IconPath);
            // no icon → short name so the slot is never blank
            btn.Text = icon.Texture is null ? Short(def.Name) : "";
            btn.AddThemeColorOverride("font_color", tier);
            qty.Text = "";
            btn.AddThemeStyleboxOverride("normal", UiTheme.Box(UiTheme.SlotBg, tier, 2, 6));
        }

        foreach (var child in _learnedList.GetChildren()) child.QueueFree();
        foreach (var child in _availableList.GetChildren()) child.QueueFree();

        foreach (var (id, ps) in mgr.Known.OrderBy(k => k.Key, StringComparer.Ordinal))
        {
            var def = db.Skills.GetValueOrDefault(id);
            if (def is null) continue;
            var cost = mgr.ManaCostOf(def);
            var cd = mgr.CooldownOf(def);
            var sub = $"Lv{ps.Level}  ·  {(int)cost} MP  ·  cd {(int)cd}s"
                      + (ps.IsEquipped ? "  ·  [equipped]" : "");

            var captured = id;
            var card = MakeCard(def, sub, TierColor(def.Tier),
                                dim: ps.IsEquipped, enabled: true);
            card.TooltipText = def.Description;
            card.Pressed += () =>
            {
                if (!mgr.EquipFirstEmpty(captured))
                    _status.Text = "All hotbar slots full!";
                Refresh();
            };
            _learnedList.AddChild(card);
        }

        foreach (var (id, def) in db.Skills.OrderBy(
                     k => (k.Value.Tier, k.Key), Comparer<(double, string)>.Default))
        {
            if (mgr.Known.ContainsKey(id)) continue;
            var (ok, reason) = mgr.CanLearn(id);
            var sub = ok
                ? $"T{(int)def.Tier}  ·  ready to learn"
                : $"T{(int)def.Tier}  ·  {reason}";

            var captured = id;
            var card = MakeCard(def, sub, TierColor(def.Tier),
                                dim: !ok, enabled: ok);
            card.TooltipText = def.Description;
            card.Pressed += () =>
            {
                if (mgr.Learn(captured))
                    _status.Text = $"learned {def.Name}!";
                Refresh();
            };
            _availableList.AddChild(card);
        }
    }

    /// <summary>A wide clickable skill card: colored border, icon on the left,
    /// name over a sub-line on the right. The whole card is a Button so all the
    /// existing click wiring stays intact.</summary>
    private static Button MakeCard(
        Game1.Core.Data.SkillDefinition def, string sub, Color tier,
        bool dim, bool enabled)
    {
        var card = new Button
        {
            CustomMinimumSize = new Vector2(0, CardIconPx + 20),
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            Disabled = !enabled,
        };
        card.AddThemeStyleboxOverride("normal",
            UiTheme.Box(UiTheme.SlotBg, tier, 2, 8));
        card.AddThemeStyleboxOverride("hover",
            UiTheme.Box(UiTheme.SlotEmpty, UiTheme.Accent, 2, 8));
        card.AddThemeStyleboxOverride("pressed",
            UiTheme.Box(UiTheme.SlotEmpty, UiTheme.Accent, 3, 8));
        card.AddThemeStyleboxOverride("disabled",
            UiTheme.Box(UiTheme.SlotEmpty, UiTheme.Border, 1, 8));
        if (dim) card.Modulate = new Color(1, 1, 1, 0.6f);

        var row = new HBoxContainer
        {
            MouseFilter = Control.MouseFilterEnum.Ignore,
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
        };
        row.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        row.OffsetLeft = 10; row.OffsetRight = -10;
        row.AddThemeConstantOverride("separation", 12);
        card.AddChild(row);

        var iconTex = IconCache.Get(def.IconPath);
        if (iconTex is not null)
        {
            var icon = new TextureRect
            {
                Texture = iconTex,
                CustomMinimumSize = new Vector2(CardIconPx, CardIconPx),
                ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
                StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                MouseFilter = Control.MouseFilterEnum.Ignore,
                SizeFlagsVertical = Control.SizeFlags.ShrinkCenter,
            };
            row.AddChild(icon);
        }

        var textCol = new VBoxContainer
        {
            MouseFilter = Control.MouseFilterEnum.Ignore,
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ShrinkCenter,
        };
        textCol.AddThemeConstantOverride("separation", 2);
        row.AddChild(textCol);

        var name = new Label { Text = def.Name };
        name.AddThemeFontSizeOverride("font_size", 18);
        name.AddThemeColorOverride("font_color", tier);
        name.MouseFilter = Control.MouseFilterEnum.Ignore;
        textCol.AddChild(name);

        var subLabel = new Label { Text = sub };
        subLabel.AddThemeFontSizeOverride("font_size", 15);
        subLabel.AddThemeColorOverride("font_color", new Color(0.78f, 0.83f, 0.95f));
        subLabel.MouseFilter = Control.MouseFilterEnum.Ignore;
        textCol.AddChild(subLabel);

        return card;
    }

    private static Color TierColor(double tier)
    {
        var idx = Math.Clamp((int)tier, 0, TierName.Length - 1);
        return UiTheme.TierColor.GetValueOrDefault(
            TierName[idx], UiTheme.TierColor["novice"]);
    }

    private static string Short(string name) =>
        name.Length <= 12 ? name : name[..11] + "…";
}
