using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// The MATERIAL MENU — the left panel of the crafting workbench (the "menu to place
/// things" the 2D game has). Lists the player's inventory materials sorted
/// tier → category → name; click one to select it for placement on the board. F1
/// debug (infinite materials) shows the whole catalog.
/// </summary>
public partial class MaterialPalette : Control
{
    private static readonly string[] CatOrder =
        { "metal", "wood", "stone", "elemental", "monster_drop", "fabric", "herb", "gem", "other" };

    private VBoxContainer _list = null!;
    private readonly List<(string Id, Button Btn, Color Rarity)> _rows = new();
    private string? _selected;
    private System.Action<string?>? _onSelect;

    public override void _Ready()
    {
        var scroll = UiTheme.VScroll();
        scroll.SetAnchorsPreset(LayoutPreset.FullRect);
        AddChild(scroll);
        _list = new VBoxContainer { SizeFlagsHorizontal = SizeFlags.ExpandFill };
        _list.AddThemeConstantOverride("separation", 4);
        scroll.AddChild(_list);
    }

    public void Rebuild(CombatWorld combat, System.Action<string?> onSelect)
    {
        _onSelect = onSelect;
        _selected = null;
        _rows.Clear();
        foreach (var c in _list.GetChildren()) c.QueueFree();

        var matDb = combat.MaterialDb;
        var inv = combat.Pc?.Inventory;
        if (matDb is null || inv is null) return;
        var debug = inv.DebugInfiniteMaterials;

        var rows = matDb.Materials.Values
            .Select(m => (Mat: m, Count: inv.GetItemCount(m.MaterialId)))
            .Where(x => debug || x.Count > 0)
            .OrderBy(x => x.Mat.Tier)
            .ThenBy(x => System.Array.IndexOf(CatOrder, x.Mat.Category) is var i && i >= 0 ? i : CatOrder.Length)
            .ThenBy(x => x.Mat.Name)
            .ToList();

        if (rows.Count == 0)
        {
            var empty = new Label { Text = "  no materials — gather some first  ", Modulate = new Color(1, 1, 1, 0.5f) };
            empty.AddThemeFontSizeOverride("font_size", 14);
            _list.AddChild(empty);
            return;
        }

        foreach (var (m, count) in rows)
        {
            var rarity = UiTheme.Rarity.GetValueOrDefault(m.Rarity, UiTheme.Rarity["common"]);
            var have = debug ? "∞" : count.ToString();
            var b = new Button
            {
                Text = $"  {m.Name}   ×{have}  (T{(int)m.Tier})",
                Icon = IconCache.Get(m.IconPath),
                ExpandIcon = true,
                FocusMode = FocusModeEnum.None,
                Alignment = HorizontalAlignment.Left,
                CustomMinimumSize = new Vector2(0, 46),
            };
            b.AddThemeFontSizeOverride("font_size", 15);
            b.TooltipText = ItemTooltip.ForMaterial(m);
            var id = m.MaterialId;
            b.Pressed += () => Select(id);
            _rows.Add((id, b, rarity));
            _list.AddChild(b);
        }
        Restyle();
    }

    private void Select(string id)
    {
        _selected = _selected == id ? null : id;
        Restyle();
        _onSelect?.Invoke(_selected);
    }

    /// <summary>Clear the selection (e.g., after a craft) without re-listing.</summary>
    public void Deselect() { _selected = null; Restyle(); }

    private void Restyle()
    {
        foreach (var (id, btn, rarity) in _rows)
        {
            var sel = id == _selected;
            btn.AddThemeStyleboxOverride("normal", UiTheme.Box(sel ? UiTheme.PanelInner : UiTheme.SlotBg, rarity, sel ? 3 : 1, 6));
            btn.AddThemeStyleboxOverride("hover", UiTheme.Box(UiTheme.PanelInner, UiTheme.Accent, 2, 6));
            btn.AddThemeStyleboxOverride("pressed", UiTheme.Box(UiTheme.SlotEmpty, UiTheme.Accent, 3, 6));
        }
    }
}
