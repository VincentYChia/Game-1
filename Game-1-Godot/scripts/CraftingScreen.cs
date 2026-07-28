using System.Text.Json.Nodes;
using Game1.Core.Crafting;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Crafting popup ([C]; [Esc] closes). Lists every recipe from the CERTIFIED
/// RecipeDatabase as a vibrant bordered card — big output icon, station/tier,
/// per-input have/need counts, and a large Craft button. Craftable recipes
/// surface first; the rest are dimmed. Crafting runs the certified
/// CraftingSystem path (consume → quality → output → XP → titles);
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

        var dim = new ColorRect { Color = UiTheme.Dim };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(dim);

        var panel = new PanelContainer();
        panel.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        panel.AnchorLeft = 0.08f;
        panel.AnchorTop = 0.05f;
        panel.AnchorRight = 0.92f;
        panel.AnchorBottom = 0.95f;
        panel.OffsetLeft = panel.OffsetTop = panel.OffsetRight = panel.OffsetBottom = 0;
        panel.AddThemeStyleboxOverride("panel", UiTheme.Box(UiTheme.PanelBg, UiTheme.Border, 3, 12));
        _root.AddChild(panel);

        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 26);
        panel.AddChild(margin);

        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 12);
        margin.AddChild(box);

        box.AddChild(UiTheme.Header("Crafting", 36));

        _status = new Label { Text = "" };
        _status.AddThemeFontSizeOverride("font_size", 20);
        _status.AddThemeColorOverride("font_color", UiTheme.Accent);
        box.AddChild(_status);

        var scroll = UiTheme.VScroll();
        box.AddChild(scroll);
        _list = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        _list.AddThemeConstantOverride("separation", 12);
        scroll.AddChild(_list);

        var hint = new Label
        { Text = "double-Esc during a minigame abandons (materials lost)   ·   [Esc] close" };
        hint.AddThemeFontSizeOverride("font_size", 16);
        hint.Modulate = new Color(1, 1, 1, 0.55f);
        box.AddChild(hint);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        // No keybind: like the Python game, crafting opens by CLICKING a
        // station in range (game_engine.py:3032); [Esc] closes.
        if (@event is InputEventKey
            { Pressed: true, Echo: false, PhysicalKeycode: Key.Escape } && _open)
        {
            Toggle();
            // Consume so this Esc doesn't also open the pause menu
            GetViewport().SetInputAsHandled();
        }
    }

    /// <summary>Station-click entry (CombatWorld ray-pick).</summary>
    public void OpenAtStation(string stationType, int stationTier)
    {
        _stationType = stationType;
        _stationTier = stationTier;
        if (!_open) Toggle();
        else Refresh();
    }

    private string? _stationType;
    private int _stationTier;

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

        // Station gating (recipe_db.py:149-150): exact type match, recipe
        // tier <= station tier. No station = no recipes (crafting is 100%
        // station-gated in the Python game).
        // Order by station tier, then the recipe database's definition order
        // (JSON order) — NOT alphabetically. OrderBy is stable so equal tiers
        // keep insertion order. Craftable recipes are distinguished by color,
        // not by reordering.
        var rows = recipeDb.Recipes.Values
            .Where(r => _stationType is null
                        || (r.StationType == _stationType
                            && r.StationTier <= _stationTier))
            .OrderBy(r => r.StationTier)
            .Select(r => (Recipe: r, Craftable: RecipeCrafting.CanCraft(r, pc.Inventory)))
            .ToList();

        var craftableCount = rows.Count(x => x.Craftable);
        _status.Text =
            (_stationType is not null
                ? $"{CombatWorld.Prettify(_stationType)} station T{_stationTier}  ·  "
                : "")
            + $"{craftableCount} of {rows.Count} recipes craftable";

        foreach (var (recipe, craftable) in rows)
            _list.AddChild(BuildCard(recipe, craftable, pc));
    }

    /// <summary>One recipe as a bordered card: big output icon, name +
    /// station/tier, per-input have/need, and a large Craft button.</summary>
    private PanelContainer BuildCard(Recipe recipe, bool craftable,
                                     Game1.Core.Progression.PlayerCharacter pc)
    {
        var accent = craftable ? new Color(0.45f, 0.9f, 0.45f) : UiTheme.Border;
        var card = new PanelContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        card.AddThemeStyleboxOverride("panel",
            UiTheme.Box(craftable ? UiTheme.PanelInner : UiTheme.SlotEmpty, accent, 2, 10));

        var inner = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            inner.AddThemeConstantOverride($"margin_{side}", 12);
        card.AddChild(inner);

        var row = new HBoxContainer();
        row.AddThemeConstantOverride("separation", 16);
        inner.AddChild(row);

        // -- output icon --
        var iconPath = _combat.EquipDb?.CreateEquipmentFromId(recipe.OutputId)?.IconPath
                       ?? _combat.MaterialDb?.GetMaterial(recipe.OutputId)?.IconPath;
        var iconWrap = new PanelContainer
        { CustomMinimumSize = new Vector2(72, 72) };
        iconWrap.AddThemeStyleboxOverride("panel",
            UiTheme.Box(UiTheme.SlotBg, accent, 1, 8));
        var icon = new TextureRect
        {
            Texture = IconCache.Get(iconPath),
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
            CustomMinimumSize = new Vector2(64, 64),
            Modulate = craftable ? Colors.White : new Color(1, 1, 1, 0.45f),
        };
        iconWrap.AddChild(icon);
        row.AddChild(iconWrap);

        // -- name + station/tier + inputs --
        var textCol = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        textCol.AddThemeConstantOverride("separation", 4);
        row.AddChild(textCol);

        var title = new Label
        {
            Text = $"{CombatWorld.Prettify(recipe.OutputId)} ×{(int)recipe.OutputQty}",
        };
        title.AddThemeFontSizeOverride("font_size", 22);
        title.AddThemeColorOverride("font_color",
            craftable ? UiTheme.Text : new Color(0.7f, 0.72f, 0.8f, 0.7f));
        textCol.AddChild(title);

        var station = new Label
        { Text = $"{CombatWorld.Prettify(recipe.StationType)} · Tier {(int)recipe.StationTier}" };
        station.AddThemeFontSizeOverride("font_size", 16);
        station.AddThemeColorOverride("font_color", new Color(0.7f, 0.78f, 0.95f));
        textCol.AddChild(station);

        var inputs = new Label
        {
            Text = DescribeInputs(recipe, pc),
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            AutowrapMode = TextServer.AutowrapMode.WordSmart,
        };
        inputs.AddThemeFontSizeOverride("font_size", 17);
        inputs.Modulate = craftable
            ? new Color(0.82f, 0.95f, 0.82f)
            : new Color(1, 1, 1, 0.5f);
        textCol.AddChild(inputs);

        // -- craft button --
        var btn = UiTheme.TextButton(craftable ? "Craft" : "Missing", 20);
        btn.Disabled = !craftable;
        btn.CustomMinimumSize = new Vector2(150, 64);
        btn.SizeFlagsVertical = Control.SizeFlags.ShrinkCenter;
        if (craftable)
        {
            btn.AddThemeStyleboxOverride("normal", UiTheme.Box(UiTheme.SlotBg, accent, 2, 8));
            btn.AddThemeStyleboxOverride("hover", UiTheme.Box(UiTheme.PanelInner, UiTheme.Accent, 2, 8));
            btn.AddThemeStyleboxOverride("pressed", UiTheme.Box(UiTheme.SlotEmpty, UiTheme.Accent, 3, 8));
        }
        var captured = recipe;
        btn.Pressed += () => StartCraft(captured);
        row.AddChild(btn);

        return card;
    }

    /// <summary>Launch the discipline's minigame; performance flows into
    /// the certified craft. Abandoning consumes the materials with no
    /// output (Python double-Esc idiom). No minigame registered → rolled
    /// performance fallback (the pre-minigame seam).</summary>
    private void StartCraft(Recipe recipe)
    {
        var overlay = _combat.Minigames.GetValueOrDefault(recipe.StationType);
        if (overlay is null)
        {
            var result = _combat.CraftRecipe(recipe);
            _status.Text = result?.Message ?? "craft failed";
            Refresh();
            return;
        }

        var points = DifficultyPoints(recipe);
        var tier = DifficultyCalculator.GetDifficultyTier(points);
        // Hide the recipe browser while playing (station stays "open")
        if (_open) Toggle();
        overlay.Begin(points, tier,
            performance =>
            {
                var result = _combat.CraftRecipe(recipe, performance);
                _status.Text = result?.Message ?? "craft failed";
                if (!_open) Toggle();
                Refresh();
            },
            () =>
            {
                RecipeCrafting.ConsumeMaterials(recipe, _combat.Pc!.Inventory);
                _status.Text = "craft abandoned — materials lost";
                if (!_open) Toggle();
                Refresh();
            });
    }

    private double DifficultyPoints(Recipe recipe)
    {
        var inputs = new List<MaterialInput>();
        if (recipe.Inputs is JsonArray arr)
            foreach (var node in arr)
            {
                if (node is not JsonObject o) continue;
                var id = o["materialId"]?.GetValue<string>() ?? "";
                var qty = 1;
                if (o["qty"] is JsonValue v)
                {
                    if (v.TryGetValue<int>(out var iv)) qty = iv;
                    else if (v.TryGetValue<double>(out var dv)) qty = (int)dv;
                }
                var mTier = (int)(_combat.MaterialDb?.GetMaterial(id)?.Tier ?? 1);
                inputs.Add(new MaterialInput(id, qty, mTier));
            }
        return DifficultyCalculator.MaterialPoints(inputs);
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
            parts.Add($"{qty}× {name} ({(have >= 999_999 ? "∞" : have.ToString())})");
        }
        return string.Join("  ·  ", parts);
    }
}
