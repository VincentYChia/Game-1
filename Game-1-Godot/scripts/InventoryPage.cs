using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Inventory + equipment book page ([I]/[Tab]). Renders the CERTIFIED
/// Inventory (30 slots) and EquipmentManager — presentation only.
/// Left-click a slot to pick up / place / merge / swap (Core StartDrag/
/// EndDrag semantics). Right-click an equipment item to EQUIP it through
/// the certified Equip path (requirement checks, hand-type matrix). Click
/// an equipped row to unequip.
/// </summary>
public partial class InventoryPage : MenuPage
{
    public override string Title => "Inventory";
    public override Key Keybind => Key.I;

    private readonly CombatWorld _combat;
    private readonly List<Button> _slotButtons = new();
    private readonly List<Label> _slotQty = new();
    private readonly Dictionary<string, Button> _equipButtons = new();
    private Label _dragLabel = null!;
    private Label _status = null!;
    private double _refresh;

    internal static readonly Dictionary<string, Color> RarityColors = new()
    {
        ["common"] = new Color(0.92f, 0.92f, 0.92f),
        ["uncommon"] = new Color(0.45f, 0.9f, 0.45f),
        ["rare"] = new Color(0.4f, 0.65f, 1f),
        ["epic"] = new Color(0.75f, 0.45f, 0.95f),
        ["legendary"] = new Color(1f, 0.65f, 0.25f),
    };

    public InventoryPage(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        var outer = new VBoxContainer();
        outer.AddThemeConstantOverride("separation", 8);
        outer.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(outer);

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
                CustomMinimumSize = new Vector2(112, 56),
                ClipText = true,
                Text = "",
                ExpandIcon = true,
                IconAlignment = HorizontalAlignment.Center,
            };
            btn.AddThemeFontSizeOverride("font_size", 12);
            btn.Pressed += () => OnSlotClicked(idx);
            btn.GuiInput += ev =>
            {
                if (ev is InputEventMouseButton
                    { ButtonIndex: MouseButton.Right, Pressed: true })
                    OnSlotRightClicked(idx);
            };
            // Qty / durability overlaid bottom-right (click passes through)
            var qty = new Label
            {
                MouseFilter = Control.MouseFilterEnum.Ignore,
                HorizontalAlignment = HorizontalAlignment.Right,
                VerticalAlignment = VerticalAlignment.Bottom,
            };
            qty.AddThemeFontSizeOverride("font_size", 13);
            qty.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
            qty.AddThemeConstantOverride("outline_size", 4);
            qty.SetAnchorsPreset(Control.LayoutPreset.FullRect);
            btn.AddChild(qty);
            grid.AddChild(btn);
            _slotButtons.Add(btn);
            _slotQty.Add(qty);
        }

        var hint = new Label
        {
            Text = "left-click: pick up / place / merge / swap   ·   "
                   + "right-click: equip",
        };
        hint.AddThemeFontSizeOverride("font_size", 14);
        hint.Modulate = new Color(1, 1, 1, 0.6f);
        invBox.AddChild(hint);

        // -- equipment column: one button per certified slot --
        var eqBox = new VBoxContainer { CustomMinimumSize = new Vector2(300, 0) };
        columns.AddChild(eqBox);
        var eqTitle = new Label { Text = "Equipment  (click to unequip)" };
        eqTitle.AddThemeFontSizeOverride("font_size", 22);
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
        AddChild(_dragLabel);
    }

    public override void OnOpened()
    {
        _status.Text = "";
        Refresh();
    }

    public override void Tick(double delta)
    {
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
            _dragLabel.Position = GetLocalMousePosition() + new Vector2(14, -8);
        }
    }

    private void OnSlotClicked(int index)
    {
        var inv = _combat.Pc?.Inventory;
        if (inv is null) return;
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
            var qty = _slotQty[i];
            if (stack is null)
            {
                btn.Text = "";
                btn.Icon = null;
                qty.Text = "";
                btn.RemoveThemeColorOverride("font_color");
                continue;
            }
            var name = DisplayName(stack);
            var rarity = RarityColors.GetValueOrDefault(stack.Rarity, RarityColors["common"]);
            var icon = IconCache.Get(IconFor(stack));
            btn.Icon = icon;
            // Icon present → name goes away, corner shows qty/durability;
            // no icon → fall back to the text layout
            if (icon is not null)
            {
                btn.Text = "";
                qty.Text = stack.EquipmentData is { } de
                    ? $"{de.DurabilityCurrent / Math.Max(1, de.DurabilityMax):P0}"
                    : stack.Quantity > 1 ? $"×{stack.Quantity}" : "";
            }
            else
            {
                btn.Text = stack.EquipmentData is { } eq
                    ? $"{name}\n{eq.DurabilityCurrent / Math.Max(1, eq.DurabilityMax):P0} dur"
                    : $"{name}\n×{stack.Quantity}";
                qty.Text = "";
            }
            qty.Modulate = rarity;
            btn.AddThemeColorOverride("font_color", rarity);
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

    private string? IconFor(ItemStack stack) =>
        stack.EquipmentData?.IconPath
        ?? _combat.MaterialDb?.GetMaterial(stack.ItemId)?.IconPath;
}
