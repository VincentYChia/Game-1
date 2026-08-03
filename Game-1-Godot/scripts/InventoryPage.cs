using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Inventory + equipment book page ([I]/[Tab]) — recreating the 2D game's
/// inventory: a 6×5 grid of big icon slots on the left, a paper-doll
/// equipment panel of labeled icon slots on the right. Left-click picks up /
/// places / merges / swaps (certified Core drag semantics); right-click a
/// grid item equips it (requirement + hand-type checks); click an equipment
/// slot to unequip.
/// </summary>
public partial class InventoryPage : MenuPage
{
    public override string Title => "Inventory";
    public override Key Keybind => Key.I;

    private const int SlotPx = 100;
    private const int EquipPx = 112;

    private static readonly (string Slot, string Label)[] EquipLayout =
    {
        ("helmet", "Helmet"), ("mainHand", "Main Hand"), ("offHand", "Off Hand"),
        ("chestplate", "Chest"), ("gauntlets", "Gauntlets"), ("accessory", "Accessory"),
        ("leggings", "Legs"), ("boots", "Boots"), ("axe", "Axe"),
        ("pickaxe", "Pickaxe"),
    };

    private readonly CombatWorld _combat;
    private readonly List<(TextureRect Icon, Label Qty, Button Btn)> _slots = new();
    private readonly Dictionary<string, (TextureRect Icon, Label Sub)> _equip = new();
    private Label _dragLabel = null!;
    private Label _status = null!;
    private Label _summary = null!;
    private double _refresh;

    public InventoryPage(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        var outer = new VBoxContainer();
        outer.AddThemeConstantOverride("separation", 12);
        outer.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(outer);
        outer.AddChild(UiTheme.Header("Inventory"));

        // Center the content block in the (large) page so it's balanced
        // rather than pinned to a corner.
        var center = new CenterContainer
        {
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        outer.AddChild(center);

        var columns = new HBoxContainer();
        columns.AddThemeConstantOverride("separation", 48);
        center.AddChild(columns);

        // -- left: item grid (scrollable — the inventory is 96 slots) --
        var slotCount = _combat.Pc?.Inventory.MaxSlots ?? 30;
        const int cols = 6;
        var invBox = new VBoxContainer();
        invBox.AddThemeConstantOverride("separation", 10);
        columns.AddChild(invBox);
        invBox.AddChild(UiTheme.Section("Backpack"));

        var scroll = new ScrollContainer
        {
            CustomMinimumSize = new Vector2(cols * SlotPx + (cols - 1) * 8 + 24, 720),
            HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled,
        };
        invBox.AddChild(scroll);
        var grid = new GridContainer { Columns = cols };
        grid.AddThemeConstantOverride("h_separation", 8);
        grid.AddThemeConstantOverride("v_separation", 8);
        scroll.AddChild(grid);
        for (var i = 0; i < slotCount; i++)
        {
            var idx = i;
            var btn = UiTheme.Slot(SlotPx, out var icon, out var qty);
            btn.Pressed += () => OnSlotClicked(idx);
            btn.GuiInput += ev =>
            {
                if (ev is InputEventMouseButton
                    { ButtonIndex: MouseButton.Right, Pressed: true })
                    OnSlotRightClicked(idx);
            };
            grid.AddChild(btn);
            _slots.Add((icon, qty, btn));
        }

        var hint = new Label
        {
            Text = "left-click: pick up / place / merge / swap      "
                   + "right-click: equip",
        };
        hint.AddThemeFontSizeOverride("font_size", 15);
        hint.Modulate = new Color(1, 1, 1, 0.55f);
        invBox.AddChild(hint);

        // -- right: paper-doll equipment --
        var eqBox = new VBoxContainer { CustomMinimumSize = new Vector2(360, 0) };
        eqBox.AddThemeConstantOverride("separation", 10);
        columns.AddChild(eqBox);
        eqBox.AddChild(UiTheme.Section("Equipment  (click a slot to unequip)"));

        var eqGrid = new GridContainer { Columns = 3 };
        eqGrid.AddThemeConstantOverride("h_separation", 14);
        eqGrid.AddThemeConstantOverride("v_separation", 12);
        eqBox.AddChild(eqGrid);
        foreach (var (slot, label) in EquipLayout)
        {
            var cell = new VBoxContainer();
            cell.AddThemeConstantOverride("separation", 3);
            var name = new Label
            { Text = label, HorizontalAlignment = HorizontalAlignment.Center };
            name.AddThemeFontSizeOverride("font_size", 14);
            name.Modulate = new Color(0.75f, 0.8f, 0.95f);
            cell.AddChild(name);
            var captured = slot;
            var btn = UiTheme.Slot(EquipPx, out var icon, out var sub);
            btn.Pressed += () => OnUnequip(captured);
            cell.AddChild(btn);
            eqGrid.AddChild(cell);
            _equip[slot] = (icon, sub);
        }

        _summary = new Label();
        _summary.AddThemeFontSizeOverride("font_size", 17);
        eqBox.AddChild(_summary);

        _status = new Label { Text = "" };
        _status.AddThemeFontSizeOverride("font_size", 16);
        _status.Modulate = UiTheme.Accent;
        eqBox.AddChild(_status);

        // stack-in-hand follows the mouse
        _dragLabel = new Label { Visible = false, ZIndex = 100 };
        _dragLabel.AddThemeFontSizeOverride("font_size", 16);
        _dragLabel.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
        _dragLabel.AddThemeConstantOverride("outline_size", 5);
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
            _dragLabel.Position = GetLocalMousePosition() + new Vector2(16, -10);
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
            pc.Equipment.Equip(item, pc);
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

        for (var i = 0; i < _slots.Count && i < pc.Inventory.Slots.Count; i++)
        {
            var stack = pc.Inventory.Slots[i];
            var (icon, qty, btn) = _slots[i];
            if (stack is null)
            {
                icon.Texture = null;
                qty.Text = "";
                btn.AddThemeStyleboxOverride("normal",
                    UiTheme.Box(UiTheme.SlotEmpty, UiTheme.Border, 1, 6));
                continue;
            }
            var rarity = UiTheme.Rarity.GetValueOrDefault(stack.Rarity, UiTheme.Rarity["common"]);
            icon.Texture = IconCache.Get(IconFor(stack));
            qty.Text = stack.EquipmentData is { } de
                ? $"{de.DurabilityCurrent / Math.Max(1, de.DurabilityMax):P0}"
                : stack.Quantity > 1 ? $"{stack.Quantity}" : "";
            qty.Modulate = rarity;
            // no icon → show a short name so it's not blank
            btn.Text = icon.Texture is null ? Short(DisplayName(stack)) : "";
            btn.AddThemeFontSizeOverride("font_size", 12);
            btn.AddThemeColorOverride("font_color", rarity);
            btn.AddThemeStyleboxOverride("normal",
                UiTheme.Box(UiTheme.SlotBg, rarity, 2, 6));
        }

        foreach (var (slot, (icon, sub)) in _equip)
        {
            var item = pc.Equipment.Slots.GetValueOrDefault(slot);
            icon.Texture = item is null ? null : IconCache.Get(item.IconPath);
            sub.Text = item is null ? ""
                : icon.Texture is null ? Short(item.Name)
                : $"{item.DurabilityCurrent:F0}/{item.DurabilityMax}";
        }

        _summary.Text = $"HP {pc.Health:F0}/{pc.MaxHealthValue:F0}      "
                        + $"MP {pc.Mana:F0}/{pc.MaxMana:F0}\n"
                        + $"Level {pc.Leveling.Level}   ·   {pc.Leveling.CurrentExp} exp";
    }

    private static string Short(string name) =>
        name.Length <= 12 ? name : name[..11] + "…";

    private string DisplayName(ItemStack stack) =>
        stack.EquipmentData?.Name
        ?? _combat.MaterialDb?.GetMaterial(stack.ItemId)?.Name
        ?? stack.ItemId;

    private string? IconFor(ItemStack stack) =>
        stack.EquipmentData?.IconPath
        ?? _combat.MaterialDb?.GetMaterial(stack.ItemId)?.IconPath;
}
