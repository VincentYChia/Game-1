using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Inventory + equipment popup ([I] or [Tab]; [Esc] closes). Renders the
/// CERTIFIED Inventory (30 slots) and EquipmentManager — presentation only.
/// Click a slot to pick its stack up, click another to place/merge/swap:
/// all semantics are the Core StartDrag/EndDrag port, not UI logic.
/// </summary>
public partial class InventoryScreen : CanvasLayer
{
    private readonly CombatWorld _combat;
    private Control _root = null!;
    private readonly List<Button> _slotButtons = new();
    private Label _equipList = null!;
    private Label _dragLabel = null!;
    private double _refresh;
    private bool _open;

    private static readonly Dictionary<string, Color> RarityColors = new()
    {
        ["common"] = new Color(0.92f, 0.92f, 0.92f),
        ["uncommon"] = new Color(0.45f, 0.9f, 0.45f),
        ["rare"] = new Color(0.4f, 0.65f, 1f),
        ["epic"] = new Color(0.75f, 0.45f, 0.95f),
        ["legendary"] = new Color(1f, 0.65f, 0.25f),
    };

    public InventoryScreen(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        Layer = 10;
        _root = new Control { Visible = false };
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        var dim = new ColorRect { Color = new Color(0, 0, 0, 0.45f) };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(dim);

        var center = new CenterContainer();
        center.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(center);

        var panel = new PanelContainer();
        center.AddChild(panel);
        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 18);
        panel.AddChild(margin);

        var columns = new HBoxContainer();
        columns.AddThemeConstantOverride("separation", 24);
        margin.AddChild(columns);

        // -- inventory grid --
        var invBox = new VBoxContainer();
        columns.AddChild(invBox);
        var title = new Label { Text = "Inventory" };
        title.AddThemeFontSizeOverride("font_size", 26);
        invBox.AddChild(title);

        var grid = new GridContainer { Columns = 6 };
        grid.AddThemeConstantOverride("h_separation", 6);
        grid.AddThemeConstantOverride("v_separation", 6);
        invBox.AddChild(grid);
        for (var i = 0; i < 30; i++)
        {
            var idx = i;
            var btn = new Button
            {
                CustomMinimumSize = new Vector2(118, 58),
                ClipText = true,
                Text = "",
            };
            btn.AddThemeFontSizeOverride("font_size", 14);
            btn.Pressed += () => OnSlotClicked(idx);
            grid.AddChild(btn);
            _slotButtons.Add(btn);
        }

        var hint = new Label
        { Text = "click: pick up / place / merge / swap   ·   [I] close" };
        hint.AddThemeFontSizeOverride("font_size", 14);
        hint.Modulate = new Color(1, 1, 1, 0.6f);
        invBox.AddChild(hint);

        // -- equipment column --
        var eqBox = new VBoxContainer { CustomMinimumSize = new Vector2(280, 0) };
        columns.AddChild(eqBox);
        var eqTitle = new Label { Text = "Equipment" };
        eqTitle.AddThemeFontSizeOverride("font_size", 26);
        eqBox.AddChild(eqTitle);
        _equipList = new Label { Text = "" };
        _equipList.AddThemeFontSizeOverride("font_size", 16);
        eqBox.AddChild(_equipList);

        // stack-in-hand follows the mouse
        _dragLabel = new Label { Visible = false, ZIndex = 100 };
        _dragLabel.AddThemeFontSizeOverride("font_size", 16);
        _root.AddChild(_dragLabel);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey { Pressed: true, Echo: false } key) return;
        // Open only if no other popup is up; closing always allowed
        if (key.PhysicalKeycode is Key.I or Key.Tab)
        {
            if (_open || !UiHub.ScreenOpen) Toggle();
        }
        else if (key.PhysicalKeycode is Key.Escape && _open) Toggle();
    }

    private void Toggle()
    {
        _open = !_open;
        _root.Visible = _open;
        UiHub.OpenScreens += _open ? 1 : -1;
        if (_open) Refresh();
        else _combat.Pc?.Inventory.CancelDrag();
    }

    public override void _Process(double delta)
    {
        if (!_open) return;
        _refresh += delta;
        if (_refresh >= 0.25)
        {
            _refresh = 0;
            Refresh();
        }

        var dragging = _combat.Pc?.Inventory.DraggingStack;
        _dragLabel.Visible = dragging is not null;
        if (dragging is not null)
        {
            _dragLabel.Text = $"{DisplayName(dragging)} ×{dragging.Quantity}";
            _dragLabel.Position = _root.GetLocalMousePosition() + new Vector2(14, -8);
        }
    }

    private void OnSlotClicked(int index)
    {
        var inv = _combat.Pc?.Inventory;
        if (inv is null) return;
        // Core drag semantics: pick up, then place/merge/swap on next click
        if (inv.DraggingStack is null) inv.StartDrag(index);
        else inv.EndDrag(index);
        Refresh();
    }

    private void Refresh()
    {
        var pc = _combat.Pc;
        if (pc is null) return;

        for (var i = 0; i < _slotButtons.Count && i < pc.Inventory.Slots.Count; i++)
        {
            var stack = pc.Inventory.Slots[i];
            var btn = _slotButtons[i];
            if (stack is null)
            {
                btn.Text = "";
                btn.RemoveThemeColorOverride("font_color");
                continue;
            }
            var name = DisplayName(stack);
            btn.Text = stack.EquipmentData is { } eq
                ? $"{name}\n{eq.DurabilityCurrent / Math.Max(1, eq.DurabilityMax):P0} dur"
                : $"{name}\n×{stack.Quantity}";
            btn.AddThemeColorOverride("font_color",
                RarityColors.GetValueOrDefault(stack.Rarity, RarityColors["common"]));
        }

        var lines = pc.Equipment.Slots
            .Select(kv => kv.Value is { } item
                ? $"{kv.Key,-10}  {item.Name}  ({item.DurabilityCurrent:F0}/{item.DurabilityMax})"
                : $"{kv.Key,-10}  —");
        _equipList.Text = string.Join("\n", lines)
            + $"\n\nHP {pc.Health:F0}/{pc.MaxHealthValue:F0}"
            + $"\nLevel {pc.Leveling.Level}  ·  {pc.Leveling.CurrentExp} exp";
    }

    private string DisplayName(ItemStack stack) =>
        stack.EquipmentData?.Name
        ?? _combat.MaterialDb?.GetMaterial(stack.ItemId)?.Name
        ?? stack.ItemId;
}
