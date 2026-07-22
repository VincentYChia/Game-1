using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Crafting popup ([C]; [Esc] closes). Lists every recipe from the CERTIFIED
/// RecipeDatabase with its station, inputs, and have/need counts — craftable
/// recipes first with a Craft button, the rest grayed out. Crafting runs the
/// certified CraftingSystem path (consume → quality → output → XP → titles);
/// performance is still the rolled minigame seam (ADR-7 overlays pending).
/// </summary>
public partial class CraftingScreen : CanvasLayer
{
    private readonly CombatWorld _combat;
    private Control _root = null!;
    private VBoxContainer _list = null!;
    private Label _status = null!;
    private bool _open;

    public CraftingScreen(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        Layer = 10;
        _root = new Control { Visible = false };
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        var dim = new ColorRect { Color = new Color(0, 0, 0, 0.5f) };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(dim);

        var center = new CenterContainer();
        center.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(center);

        var panel = new PanelContainer();
        center.AddChild(panel);
        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 16);
        panel.AddChild(margin);

        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 8);
        margin.AddChild(box);

        var title = new Label { Text = "Crafting" };
        title.AddThemeFontSizeOverride("font_size", 26);
        box.AddChild(title);

        _status = new Label { Text = "" };
        _status.AddThemeFontSizeOverride("font_size", 15);
        _status.Modulate = new Color(1, 1, 1, 0.75f);
        box.AddChild(_status);

        var scroll = new ScrollContainer
        { CustomMinimumSize = new Vector2(760, 520) };
        box.AddChild(scroll);
        _list = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        _list.AddThemeConstantOverride("separation", 4);
        scroll.AddChild(_list);

        var hint = new Label
        { Text = "performance is rolled until the minigames arrive   ·   [C] close" };
        hint.AddThemeFontSizeOverride("font_size", 13);
        hint.Modulate = new Color(1, 1, 1, 0.55f);
        box.AddChild(hint);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey { Pressed: true, Echo: false } key) return;
        if (key.PhysicalKeycode is Key.C)
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
    }

    private void Refresh()
    {
        foreach (var child in _list.GetChildren()) child.QueueFree();

        var recipeDb = _combat.RecipeDb;
        var pc = _combat.Pc;
        if (recipeDb is null || pc is null) return;

        var rows = recipeDb.Recipes.Values
            .Select(r => (Recipe: r, Craftable: RecipeCrafting.CanCraft(r, pc.Inventory)))
            .OrderByDescending(x => x.Craftable)
            .ThenBy(x => x.Recipe.StationType, StringComparer.Ordinal)
            .ThenBy(x => x.Recipe.RecipeId, StringComparer.Ordinal)
            .ToList();

        var craftableCount = rows.Count(x => x.Craftable);
        _status.Text = $"{craftableCount} of {rows.Count} recipes craftable "
                       + "with your materials";

        foreach (var (recipe, craftable) in rows)
        {
            var row = new HBoxContainer();
            row.AddThemeConstantOverride("separation", 10);
            _list.AddChild(row);

            var inputs = DescribeInputs(recipe, pc);
            var label = new Label
            {
                Text = $"{CombatWorld.Prettify(recipe.OutputId)} ×{(int)recipe.OutputQty}"
                       + $"   [{recipe.StationType} T{(int)recipe.StationTier}]\n"
                       + inputs,
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
                AutowrapMode = TextServer.AutowrapMode.WordSmart,
            };
            label.AddThemeFontSizeOverride("font_size", 15);
            label.Modulate = craftable
                ? new Color(0.75f, 1f, 0.75f)
                : new Color(1, 1, 1, 0.45f);
            row.AddChild(label);

            var btn = new Button
            {
                Text = "Craft",
                Disabled = !craftable,
                CustomMinimumSize = new Vector2(90, 0),
            };
            var captured = recipe;
            btn.Pressed += () =>
            {
                var result = _combat.CraftRecipe(captured);
                _status.Text = result?.Message ?? "craft failed";
                Refresh();
            };
            row.AddChild(btn);

            _list.AddChild(new HSeparator());
        }
    }

    private string DescribeInputs(Recipe recipe, Game1.Core.Progression.PlayerCharacter pc)
    {
        if (recipe.Inputs is not JsonArray arr || arr.Count == 0) return "no inputs";
        var parts = new List<string>();
        foreach (var node in arr)
        {
            if (node is not JsonObject o) continue;
            var id = o["materialId"]?.GetValue<string>() ?? "?";
            var qty = 1;
            if (o["qty"] is JsonValue v)
            {
                if (v.TryGetValue<int>(out var iv)) qty = iv;
                else if (v.TryGetValue<double>(out var dv)) qty = (int)dv;
            }
            var have = pc.Inventory.GetItemCount(id);
            var name = _combat.MaterialDb?.GetMaterial(id)?.Name
                       ?? CombatWorld.Prettify(id);
            parts.Add($"{qty}× {name} ({have})");
        }
        return string.Join("  ·  ", parts);
    }
}
