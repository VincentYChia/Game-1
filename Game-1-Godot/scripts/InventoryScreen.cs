using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Inventory + equipment popup ([I] or [Tab]; [Esc] closes). Renders the
/// CERTIFIED Inventory (30 slots) and EquipmentManager — presentation only.
/// Left-click a slot to pick up / place / merge / swap (Core StartDrag/
/// EndDrag semantics). Right-click an equipment item to EQUIP it through the
/// certified Equip path (requirement checks, hand-type matrix). Click an
/// equipped row to unequip back to the inventory.
/// </summary>
public partial class InventoryScreen : CanvasLayer
{
    private readonly CombatWorld _combat;
    private Control _root = null!;
    private readonly List<Button> _slotButtons = new();
    private readonly Dictionary<string, Button> _equipButtons = new();
    private Label _dragLabel = null!;
    private Label _status = null!;
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

        var outer = new VBoxContainer();
        outer.AddThemeConstantOverride("separation", 8);
        margin.AddChild(outer);

        var columns = new HBoxContainer();
        columns.AddThemeConstantOverride("separation", 24);
        outer.AddChild(columns);

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
            btn.GuiInput += ev =>
            {
                if (ev is InputEventMouseButton
                    { ButtonIndex: MouseButton.Right, Pressed: true })
                    OnSlotRightClicked(idx);
            };
            grid.AddChild(btn);
            _slotButtons.Add(btn);
        }

        var hint = new Label
        {
            Text = "left-click: pick up / place / merge / swap   ·   "
                   + "right-click: equip   ·   [I] close",
        };
        hint.AddThemeFontSizeOverride("font_size", 14);
        hint.Modulate = new Color(1, 1, 1, 0.6f);
        invBox.AddChild(hint);

        // -- equipment column: one button per certified slot --
        var eqBox = new VBoxContainer { CustomMinimumSize = new Vector2(320, 0) };
        columns.AddChild(eqBox);
        var eqTitle = new Label { Text = "Equipment  (click to unequip)" };
        eqTitle.AddThemeFontSizeOverride("font_size", 26);
        eqBox.AddChild(eqTitle);

        if (_combat.Pc is { } pc)
        {
            foreach (var slot in pc.Equipment.Slots.Keys)
            {
                var captured = slot;
                var btn = new Button
                {
                    Text = $"{slot}: —",
                    Alignment = HorizontalAlignment.Left,
                    ClipText = true,
                };
                btn.AddThemeFontSizeOverride("font_size", 15);
                btn.Pressed += () => OnUnequip(captured);
                eqBox.AddChild(btn);
                _equipButtons[slot] = btn;
            }
        }

        _status = new Label { Text = "" };
        _status.AddThemeFontSizeOverride("font_size", 15);
        _status.Modulate = new Color(1f, 0.9f, 0.6f);
        outer.AddChild(_status);

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
        _status.Text = "";
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

    private void OnSlotRightClicked(int index)
    {
        var pc = _combat.Pc;
        if (pc is null || pc.Inventory.DraggingStack is not null) return;
        var stack = pc.Inventory.Slots[index];
        if (stack?.EquipmentData is not { } item)
        {
            if (stack is not null) _status.Text = $"{DisplayName(stack)}: not equippable";
            return;
        }

        // The certified path: requirement checks + hand-type matrix
        var (oldItem, reason) = pc.Equipment.Equip(item, pc);
        if (reason != "OK")
        {
            _status.Text = reason;
            return;
        }
        pc.Inventory.Slots[index] = null;
        if (oldItem is not null)
            pc.Inventory.AddItem(oldItem.ItemId, 1, equipmentInstance: oldItem);
        _status.Text = $"equipped {item.Name} → {item.Slot}";
        Refresh();
    }

    private void OnUnequip(string slot)
    {
        var pc = _combat.Pc;
        if (pc is null) return;
        var item = pc.Equipment.Unequip(slot);
        if (item is null) return;
        if (!pc.Inventory.AddItem(item.ItemId, 1, equipmentInstance: item))
        {
            pc.Equipment.Equip(item, pc);   // inventory full → revert
            _status.Text = "inventory full";
            return;
        }
        _status.Text = $"unequipped {item.Name}";
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

        foreach (var (slot, btn) in _equipButtons)
        {
            var item = pc.Equipment.Slots.GetValueOrDefault(slot);
            btn.Text = item is null
                ? $"{slot}: —"
                : $"{slot}: {item.Name}  ({item.DurabilityCurrent:F0}/{item.DurabilityMax})";
        }
    }

    private string DisplayName(ItemStack stack) =>
        stack.EquipmentData?.Name
        ?? _combat.MaterialDb?.GetMaterial(stack.ItemId)?.Name
        ?? stack.ItemId;
}
