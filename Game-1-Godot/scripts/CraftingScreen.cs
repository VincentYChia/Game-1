using System.Text.Json.Nodes;
using Game1.Core.Crafting;
using Game1.Core.Data;
using Game1.Core.Progression;
using Godot;

namespace Game1.Godot;

/// <summary>
/// The CRAFTING WORKBENCH — the 2D game's two-step crafting reborn in 3D.
///
/// VIEW 1 · RECIPE BROWSER: opening a station shows the known + discovered recipes for
/// its discipline as large aesthetic CARDS (not a list). Each card offers ⚡ QUICK CRAFT
/// (instant, consumes the materials and yields the plain BASE item — no quality roll,
/// like the 2D instant craft) and ✦ CRAFT (opens the placement bench with that recipe
/// pre-laid). A ✚ EXPERIMENT card opens the bench empty for discovery.
///
/// VIEW 2 · PLACEMENT BENCH: the material menu + the discipline's tier-standard board
/// (smithing grid / refining hub-spoke / alchemy sequence / engineering typed lanes /
/// enchanting shapes+vertices) + Clear · ✦ Minigame · ⚡ Quick · ← Back. The two craft
/// buttons are ALWAYS live (no hint whether the arrangement is valid until pressed). A
/// pressed button on a KNOWN arrangement crafts it; on an UNKNOWN arrangement it runs the
/// DISCOVERY pipeline (invalid-cache → classifier → LLM via the invention sidecar). A
/// discovery becomes a first-class recipe (a new card) and is crafted on the spot.
///
/// Presentation only: the board never touches the inventory — the certified CraftRecipe /
/// ConsumeMaterials do that once.
/// </summary>
public partial class CraftingScreen : CanvasLayer
{
    private readonly CombatWorld _combat;
    private Control _root = null!;
    private Label _title = null!;

    // views
    private Control _browserView = null!;
    private HFlowContainer _cards = null!;
    private Control _placeView = null!;

    // placement bench widgets
    private Label _boardCaption = null!;
    private MaterialPalette _palette = null!;
    private PanelContainer _boardHost = null!;
    private Label _statusLabel = null!;
    private Button _minigameBtn = null!;
    private Button _instantBtn = null!;
    private Control _busy = null!;
    private Label _busyLabel = null!;

    private CraftResultOverlay _result = null!;

    private PlacementBoard? _board;
    private string _boardDiscipline = "";
    private string? _stationType;
    private int _stationTier;
    private bool _open;
    private bool _inPlacement;
    private bool _working;   // a discovery request is in flight

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
        panel.AnchorLeft = 0.05f; panel.AnchorTop = 0.05f;
        panel.AnchorRight = 0.95f; panel.AnchorBottom = 0.95f;
        panel.OffsetLeft = panel.OffsetTop = panel.OffsetRight = panel.OffsetBottom = 0;
        panel.AddThemeStyleboxOverride("panel", UiTheme.Box(UiTheme.PanelBg, UiTheme.Border, 3, 14));
        _root.AddChild(panel);

        var margin = new MarginContainer();
        foreach (var s in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{s}", 22);
        panel.AddChild(margin);

        var col = new VBoxContainer();
        col.AddThemeConstantOverride("separation", 10);
        margin.AddChild(col);

        _title = new Label { Text = "Crafting" };
        _title.AddThemeFontSizeOverride("font_size", 34);
        _title.AddThemeColorOverride("font_color", UiTheme.Accent);
        col.AddChild(_title);

        var stack = new Control { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        col.AddChild(stack);
        _browserView = BuildBrowserView();
        _placeView = BuildPlacementView();
        stack.AddChild(_browserView);
        stack.AddChild(_placeView);

        var esc = new Label { Text = "[Esc] back / close", Modulate = new Color(1, 1, 1, 0.5f) };
        esc.AddThemeFontSizeOverride("font_size", 13);
        col.AddChild(esc);

        _result = new CraftResultOverlay { Name = "CraftResult" };
        AddChild(_result);
    }

    // ============================================================ VIEW 1 · browser

    private Control BuildBrowserView()
    {
        var v = new Control { Visible = true };
        v.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        var box = new VBoxContainer();
        box.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        box.AddThemeConstantOverride("separation", 8);
        v.AddChild(box);

        box.AddChild(UiTheme.Section("Recipes — Quick Craft for the base item, or Craft to place & finish", 18));
        var scroll = UiTheme.VScroll();
        box.AddChild(scroll);
        _cards = new HFlowContainer { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        _cards.AddThemeConstantOverride("h_separation", 12);
        _cards.AddThemeConstantOverride("v_separation", 12);
        scroll.AddChild(_cards);
        return v;
    }

    private void BuildBrowser()
    {
        foreach (var c in _cards.GetChildren()) c.QueueFree();
        _cards.AddChild(ExperimentCard());

        var recipeDb = _combat.RecipeDb;
        var placementDb = _combat.PlacementDb;
        if (recipeDb is null || placementDb is null || _stationType is null) return;
        if (!recipeDb.RecipesByStation.TryGetValue(_stationType, out var list)) return;

        foreach (var rec in list
                     .Where(r => r.StationTier <= _stationTier && placementDb.HasPlacement(r.RecipeId))
                     .OrderBy(r => r.RecipeId.StartsWith("invented_") ? 1 : 0)
                     .ThenBy(r => r.StationTier).ThenBy(r => r.OutputId))
            _cards.AddChild(RecipeCard(rec));
    }

    private PanelContainer ExperimentCard()
    {
        var accent = CraftStyle.Get(_stationType ?? "smithing").Accent;
        var card = CardShell(accent);
        var box = CardBody(card);
        var head = new Label { Text = "✚  Experiment", HorizontalAlignment = HorizontalAlignment.Center };
        head.AddThemeFontSizeOverride("font_size", 20);
        head.AddThemeColorOverride("font_color", accent);
        box.AddChild(head);
        var sub = new Label
        {
            Text = "Arrange materials freely on the\nbench to discover new recipes.",
            HorizontalAlignment = HorizontalAlignment.Center,
            AutowrapMode = TextServer.AutowrapMode.WordSmart,
            Modulate = new Color(1, 1, 1, 0.75f),
        };
        sub.AddThemeFontSizeOverride("font_size", 13);
        sub.SizeFlagsVertical = Control.SizeFlags.ExpandFill;
        box.AddChild(sub);
        var open = BenchButton("Open Bench", accent);
        open.Pressed += () => ShowPlacement(null);
        box.AddChild(open);
        return card;
    }

    private PanelContainer RecipeCard(Recipe rec)
    {
        var discovered = rec.RecipeId.StartsWith("invented_");
        var accent = discovered ? UiTheme.Rarity["epic"] : CraftStyle.Get(_stationType ?? "smithing").Accent;
        var card = CardShell(accent);
        var box = CardBody(card);

        // header: icon + name/tier
        var head = new HBoxContainer();
        head.AddThemeConstantOverride("separation", 10);
        box.AddChild(head);
        var icon = new TextureRect
        {
            CustomMinimumSize = new Vector2(52, 52),
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
            Texture = IconCache.Get(OutputIconPath(rec.OutputId)),
        };
        head.AddChild(icon);
        var names = new VBoxContainer { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        head.AddChild(names);
        var nm = new Label { Text = CombatWorld.Prettify(rec.OutputId) };
        nm.AddThemeFontSizeOverride("font_size", 17);
        nm.AutowrapMode = TextServer.AutowrapMode.WordSmart;
        names.AddChild(nm);
        var pts = DifficultyPoints(rec);
        var sub = new Label
        {
            Text = (discovered ? "✦ discovered · " : "") + $"Tier {(int)rec.StationTier} · {DifficultyCalculator.GetDifficultyTier(pts)}",
            Modulate = new Color(0.74f, 0.8f, 0.96f),
        };
        sub.AddThemeFontSizeOverride("font_size", 12);
        names.AddChild(sub);

        // ingredient chips
        box.AddChild(IngredientChips(rec));

        // buttons
        var canCraft = _combat.Pc is not null && RecipeCrafting.CanCraft(rec, _combat.Pc.Inventory);
        var btns = new HBoxContainer { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        btns.AddThemeConstantOverride("separation", 6);
        box.AddChild(btns);
        var quick = BenchButton("⚡ Quick", UiTheme.Accent);
        quick.Disabled = !canCraft;
        quick.SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
        quick.Pressed += () => Present(_combat.CraftRecipe(rec, 0.0), rec);   // base item, no quality
        btns.AddChild(quick);
        var craft = BenchButton("✦ Craft", accent);
        craft.SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
        craft.Pressed += () => ShowPlacement(rec);
        btns.AddChild(craft);
        card.TooltipText = RecipeTip(rec, pts, discovered);
        return card;
    }

    private string RecipeTip(Recipe rec, double pts, bool discovered)
    {
        var tip = new System.Text.StringBuilder();
        tip.Append(CombatWorld.Prettify(rec.OutputId));
        if (discovered) tip.Append("  ·  discovered");
        tip.Append($"\nTier {(int)rec.StationTier} · {DifficultyCalculator.GetDifficultyTier(pts)} craft");
        tip.Append("\nNeeds:");
        if (rec.Inputs is JsonArray arr)
            foreach (var n in arr)
                if (n is JsonObject o && o["materialId"]?.GetValue<string>() is { } id && id.Length > 0)
                {
                    var qty = (o["quantity"] ?? o["qty"]) is JsonValue v && v.TryGetValue<int>(out var q) ? q : 1;
                    tip.Append($"\n  · {CombatWorld.Prettify(id)} ×{qty}");
                }
        if (UiPrefs.AdvancedTooltips)
            tip.Append($"\n\n⚡ Quick = base item · ✦ Craft = minigame (quality)\nstation: {rec.StationType}");
        return tip.ToString();
    }

    private Control IngredientChips(Recipe rec)
    {
        var flow = new HFlowContainer { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        flow.AddThemeConstantOverride("h_separation", 5);
        flow.AddThemeConstantOverride("v_separation", 4);
        if (rec.Inputs is JsonArray arr)
            foreach (var node in arr)
            {
                if (node is not JsonObject o) continue;
                var id = o["materialId"]?.GetValue<string>() ?? "";
                if (id.Length == 0) continue;
                var qty = (o["quantity"] ?? o["qty"]) is JsonValue v && v.TryGetValue<int>(out var q) ? q : 1;
                var chip = new HBoxContainer();
                var ic = new TextureRect
                {
                    CustomMinimumSize = new Vector2(20, 20),
                    ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
                    StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                    Texture = IconCache.Get(_combat.MaterialDb?.GetMaterial(id)?.IconPath),
                };
                chip.AddChild(ic);
                var have = _combat.Pc?.Inventory.GetItemCount(id) ?? 0;
                var enough = (_combat.Pc?.Inventory.DebugInfiniteMaterials ?? false) || have >= qty;
                var l = new Label { Text = $"×{qty}", Modulate = enough ? new Color(0.8f, 0.9f, 0.85f) : new Color(1f, 0.6f, 0.55f) };
                l.AddThemeFontSizeOverride("font_size", 12);
                chip.AddChild(l);
                flow.AddChild(chip);
            }
        return flow;
    }

    private static PanelContainer CardShell(Color accent)
    {
        var card = new PanelContainer { CustomMinimumSize = new Vector2(248, 176) };
        card.AddThemeStyleboxOverride("panel", UiTheme.Box(new Color(0.11f, 0.12f, 0.17f), accent, 2, 10));
        return card;
    }

    private static VBoxContainer CardBody(PanelContainer card)
    {
        var pad = new MarginContainer();
        foreach (var s in new[] { "left", "right", "top", "bottom" }) pad.AddThemeConstantOverride($"margin_{s}", 10);
        card.AddChild(pad);
        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 6);
        pad.AddChild(box);
        return box;
    }

    // ========================================================= VIEW 2 · placement

    private Control BuildPlacementView()
    {
        var v = new Control { Visible = false };
        v.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        var main = new HBoxContainer();
        main.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        main.AddThemeConstantOverride("separation", 16);
        v.AddChild(main);

        // LEFT — material menu
        var left = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill, SizeFlagsStretchRatio = 1.05f };
        left.AddThemeConstantOverride("separation", 6);
        main.AddChild(left);
        left.AddChild(UiTheme.Section("Materials — click to select", 16));
        _palette = new MaterialPalette { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        left.AddChild(_palette);

        // CENTER — board
        var center = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill, SizeFlagsStretchRatio = 2.3f };
        center.AddThemeConstantOverride("separation", 6);
        main.AddChild(center);
        _boardCaption = UiTheme.Section("Placement", 16);
        _boardCaption.HorizontalAlignment = HorizontalAlignment.Center;
        center.AddChild(_boardCaption);
        _boardHost = new PanelContainer { SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        _boardHost.AddThemeStyleboxOverride("panel", UiTheme.Box(new Color(0.07f, 0.08f, 0.11f), UiTheme.Border, 1, 10));
        center.AddChild(_boardHost);
        var hint = new Label
        {
            Text = "left-click to place · right-click to remove",
            HorizontalAlignment = HorizontalAlignment.Center,
            Modulate = new Color(0.7f, 0.82f, 1f),
        };
        hint.AddThemeFontSizeOverride("font_size", 12);
        center.AddChild(hint);

        // RIGHT — status + actions
        var right = new VBoxContainer
        { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill, SizeFlagsStretchRatio = 1.05f };
        right.AddThemeConstantOverride("separation", 10);
        main.AddChild(right);

        _statusLabel = new Label { Text = "", AutowrapMode = TextServer.AutowrapMode.WordSmart };
        _statusLabel.AddThemeFontSizeOverride("font_size", 15);
        _statusLabel.CustomMinimumSize = new Vector2(0, 64);
        right.AddChild(_statusLabel);

        _minigameBtn = BenchButton("✦ Craft (Minigame)", UiTheme.Accent);
        _minigameBtn.Pressed += () => Attempt(minigame: true);
        right.AddChild(_minigameBtn);
        _instantBtn = BenchButton("⚡ Quick Craft", UiTheme.Accent);
        _instantBtn.Pressed += () => Attempt(minigame: false);
        right.AddChild(_instantBtn);
        var clear = BenchButton("Clear", new Color(0.85f, 0.55f, 0.5f));
        clear.Pressed += () => { _board?.Clear(); OnBoardChanged(); };
        right.AddChild(clear);
        var back = BenchButton("← Back to Recipes", new Color(0.6f, 0.66f, 0.8f));
        back.Pressed += ShowBrowser;
        right.AddChild(back);

        var tip = new Label
        {
            Text = "Both buttons are always live. On an unknown arrangement they attempt a DISCOVERY "
                   + "(the classifier + inventor judge it).",
            AutowrapMode = TextServer.AutowrapMode.WordSmart,
            Modulate = new Color(1, 1, 1, 0.55f),
        };
        tip.AddThemeFontSizeOverride("font_size", 12);
        right.AddChild(tip);

        // busy veil (discovery in flight)
        _busy = new Control { Visible = false, MouseFilter = Control.MouseFilterEnum.Stop };
        _busy.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        var veil = new ColorRect { Color = new Color(0, 0, 0, 0.55f) };
        veil.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _busy.AddChild(veil);
        _busyLabel = new Label
        {
            Text = "Consulting the inventor…",
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };
        _busyLabel.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _busyLabel.AddThemeFontSizeOverride("font_size", 22);
        _busyLabel.AddThemeColorOverride("font_color", UiTheme.Accent);
        _busy.AddChild(_busyLabel);
        v.AddChild(_busy);
        return v;
    }

    // =============================================================== transitions

    /// <summary>Station-click entry (CombatWorld ray-pick) — opens the recipe browser.</summary>
    public void OpenAtStation(string stationType, int stationTier)
    {
        _stationType = stationType;
        _stationTier = stationTier;
        var s = CraftStyle.Get(stationType);
        _title.Text = $"{s.Glyph}  {CombatWorld.Prettify(stationType)}  ·  Tier {stationTier}";
        _title.AddThemeColorOverride("font_color", s.Accent);

        EnsureBoard(stationType);
        BuildBrowser();
        ShowBrowser();
        if (!_open) Toggle();
    }

    private void ShowBrowser()
    {
        _inPlacement = false;
        BuildBrowser();   // refresh (materials / discoveries may have changed)
        _browserView.Visible = true;
        _placeView.Visible = false;
    }

    private void ShowPlacement(Recipe? preload)
    {
        _inPlacement = true;
        _browserView.Visible = false;
        _placeView.Visible = true;
        SetBusy(false);

        _boardCaption.Text = BoardCaption(_stationType ?? "", _stationTier);
        EnsureBoard(_stationType ?? "");
        _board?.Setup(_combat, _stationType ?? "", _stationTier);
        _palette.Rebuild(_combat, id => _board?.SetSelected(id));

        if (preload is not null)
        {
            var pd = _combat.PlacementDb?.GetPlacement(preload.RecipeId);
            if (pd is not null) _board?.AutoLay(pd);
        }
        OnBoardChanged();
    }

    private void Toggle()
    {
        _open = !_open;
        _root.Visible = _open;
        UiHub.OpenScreens += _open ? 1 : -1;
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey { Pressed: true, Echo: false, PhysicalKeycode: Key.Escape } || !_open) return;
        if (_working) { GetViewport().SetInputAsHandled(); return; }
        if (_inPlacement) ShowBrowser();
        else Toggle();
        GetViewport().SetInputAsHandled();
    }

    // ================================================================ board glue

    private void EnsureBoard(string discipline)
    {
        if (_board is not null && _boardDiscipline == discipline) return;
        foreach (var c in _boardHost.GetChildren()) c.QueueFree();
        _board = discipline switch
        {
            "smithing" => new SmithingBoard(),
            "refining" => new RefiningBoard(),
            "alchemy" => new AlchemyBoard(),
            "engineering" => new EngineeringBoard(),
            "adornments" => new EnchantingBoard(),
            _ => null,
        };
        _boardDiscipline = discipline;
        if (_board is not null)
        {
            _board.OnPlacementChanged = OnBoardChanged;
            _boardHost.AddChild(_board);
        }
    }

    private void OnBoardChanged()
    {
        var matched = _board?.TryMatch();
        if (matched is not null)
        {
            var canCraft = _combat.Pc is not null && RecipeCrafting.CanCraft(matched, _combat.Pc.Inventory);
            _statusLabel.Text = $"Recipe: {CombatWorld.Prettify(matched.OutputId)} ×{(int)matched.OutputQty}"
                                + (canCraft ? "" : "\n(you're missing materials)");
            _statusLabel.Modulate = canCraft ? new Color(0.6f, 1f, 0.7f) : new Color(1f, 0.75f, 0.6f);
        }
        else if (_board?.HasPlacement() == true)
        {
            _statusLabel.Text = "Unknown arrangement — craft to attempt a discovery.";
            _statusLabel.Modulate = new Color(0.85f, 0.82f, 1f);
        }
        else
        {
            _statusLabel.Text = "Place materials to build a recipe, or lay a new arrangement to discover one.";
            _statusLabel.Modulate = new Color(1, 1, 1, 0.65f);
        }
    }

    // ================================================================== crafting

    /// <summary>Quick / Minigame press. Known arrangement → craft; unknown → discover.</summary>
    private void Attempt(bool minigame)
    {
        if (_working || _board is null) return;
        var matched = _board.TryMatch();
        if (matched is not null)
        {
            if (!(_combat.Pc is not null && RecipeCrafting.CanCraft(matched, _combat.Pc.Inventory)))
            { Toast("You're missing materials for this recipe."); return; }
            if (minigame) StartMinigame(matched);
            else Present(_combat.CraftRecipe(matched, 0.0), matched);   // quick = plain base item
            return;
        }
        if (!_board.HasPlacement()) { Toast("Place some materials on the board first."); return; }
        Discover();
    }

    private void Discover()
    {
        var inv = _combat.Invention;
        if (inv is null || !inv.Available)
        { Toast("Discovery is unavailable — the invention sidecar (Python + models) wasn't found."); return; }

        var sig = _board!.Signature();
        var discipline = _boardDiscipline;
        SetBusy(true);
        System.Threading.Tasks.Task.Run(() =>
        {
            var res = inv.Invent(sig, "");
            Callable.From(() => OnInvented(res, sig, discipline)).CallDeferred();
        });
    }

    private void OnInvented(InventionResult res, JsonObject sig, string discipline)
    {
        SetBusy(false);
        switch (res.Status)
        {
            case InventionStatus.Discovered:
                var recipe = _combat.InventedRecipes?.AddDiscovery(res, sig, discipline, _combat);
                if (recipe is null) { Toast("The invention couldn't be registered."); return; }
                Present(_combat.CraftRecipe(recipe, 0.0), recipe);   // forge the first one
                break;
            case InventionStatus.Invalid:
            case InventionStatus.Unavailable:
                Toast(res.Message);
                break;
        }
    }

    private void StartMinigame(Recipe recipe)
    {
        var overlay = _combat.Minigames.GetValueOrDefault(_stationType ?? "");
        if (overlay is null) { Present(_combat.CraftRecipe(recipe, 0.0), recipe); return; }
        var points = DifficultyPoints(recipe);
        var tier = DifficultyCalculator.GetDifficultyTier(points);
        var ctx = BuildRecipeContext(recipe, points, tier);
        if (_open) Toggle();   // hide the workbench during play
        overlay.Begin(points, tier, ctx,
            perf =>
            {
                if (!_open) Toggle();
                Present(_combat.CraftRecipe(recipe, perf), recipe);
            },
            () =>
            {
                RecipeCrafting.ConsumeMaterials(recipe, _combat.Pc!.Inventory);
                if (!_open) Toggle();
                RefreshAfterCraft();
                Toast("Craft abandoned — materials lost.");
            });
    }

    private void Present(CraftResult? result, Recipe recipe)
    {
        if (result is null) { Toast("Craft failed."); return; }
        if (result.Success) StampQuality(result.OutputId, result.Quality);
        _result.ShowResult(result.Success, result.Quality, CombatWorld.Prettify(result.OutputId),
            result.Quantity, IconCache.Get(OutputIconPath(result.OutputId)), result.Message, RefreshAfterCraft);
    }

    /// <summary>Record the minigame QUALITY onto the freshly-crafted equipment instance
    /// (its mutable Bonuses bag) so it's visible wherever the item is shown.</summary>
    private void StampQuality(string outputId, string quality)
    {
        var inv = _combat.Pc?.Inventory;
        if (inv is null) return;
        for (var i = inv.Slots.Count - 1; i >= 0; i--)
        {
            var eq = inv.Slots[i]?.EquipmentData;
            if (eq is not null && eq.ItemId == outputId && ItemTooltip.Quality(eq) is null)
            {
                if (eq.Bonuses is JsonObject b) b["craft_quality"] = quality;
                return;
            }
        }
    }

    /// <summary>After a craft/abandon: inventory changed → clear the board + relist.</summary>
    private void RefreshAfterCraft()
    {
        _board?.Clear();
        if (_inPlacement)
        {
            _palette.Rebuild(_combat, id => _board?.SetSelected(id));
            OnBoardChanged();
        }
        BuildBrowser();
    }

    // ==================================================================== utils

    private void SetBusy(bool on)
    {
        _working = on;
        _busy.Visible = on;
        _minigameBtn.Disabled = on;
        _instantBtn.Disabled = on;
    }

    private void Toast(string message)
    {
        _statusLabel.Text = message;
        _statusLabel.Modulate = new Color(1f, 0.85f, 0.6f);
    }

    private string? OutputIconPath(string outputId)
        => _combat.EquipDb?.CreateEquipmentFromId(outputId)?.IconPath
           ?? _combat.MaterialDb?.GetMaterial(outputId)?.IconPath;

    private static Button BenchButton(string text, Color accent)
    {
        var b = UiTheme.TextButton(text, 15);
        b.CustomMinimumSize = new Vector2(0, 40);
        b.FocusMode = Control.FocusModeEnum.None;
        b.AddThemeStyleboxOverride("normal", UiTheme.Box(UiTheme.SlotBg, accent, 2, 8));
        b.AddThemeStyleboxOverride("hover", UiTheme.Box(UiTheme.PanelInner, accent, 2, 8));
        b.AddThemeStyleboxOverride("pressed", UiTheme.Box(UiTheme.SlotEmpty, accent, 3, 8));
        b.AddThemeStyleboxOverride("disabled", UiTheme.Box(UiTheme.SlotEmpty, new Color(0.35f, 0.37f, 0.44f), 1, 8));
        return b;
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
                if ((o["quantity"] ?? o["qty"]) is JsonValue v)
                {
                    if (v.TryGetValue<int>(out var iv)) qty = iv;
                    else if (v.TryGetValue<double>(out var dv)) qty = (int)dv;
                }
                var mTier = (int)(_combat.MaterialDb?.GetMaterial(id)?.Tier ?? 1);
                inputs.Add(new MaterialInput(id, qty, mTier));
            }
        return DifficultyCalculator.MaterialPoints(inputs);
    }

    /// <summary>Assemble the tag-driven RecipeContext handed to the minigame (output tags set the
    /// target/character; per-input material tags set per-ingredient behaviour).</summary>
    private RecipeContext BuildRecipeContext(Recipe recipe, double points, string tier)
    {
        var ctx = new RecipeContext
        {
            OutputId = recipe.OutputId, Points = points, Tier = tier,
            OutputTags = TagsOf(recipe.OutputId),
        };
        if (recipe.Inputs is JsonArray arr)
            foreach (var node in arr)
            {
                if (node is not JsonObject o) continue;
                var id = o["materialId"]?.GetValue<string>() ?? "";
                if (id.Length == 0) continue;
                var qty = 1;
                if ((o["quantity"] ?? o["qty"]) is JsonValue v)
                {
                    if (v.TryGetValue<int>(out var iv)) qty = iv;
                    else if (v.TryGetValue<double>(out var dv)) qty = (int)dv;
                }
                var m = _combat.MaterialDb?.GetMaterial(id);
                ctx.Inputs.Add(new RecipeContext.Ingredient
                {
                    Id = id, Name = CombatWorld.Prettify(id), Tags = TagsOf(id, m),
                    Qty = qty, MaterialTier = (int)(m?.Tier ?? 1),
                });
            }
        return ctx;
    }

    /// <summary>Read a material/output's ordered metadata.tags into a plain list (empty if unknown).</summary>
    private List<string> TagsOf(string id, MaterialDefinition? m = null)
    {
        m ??= _combat.MaterialDb?.GetMaterial(id);
        var list = new List<string>();
        if (m?.Tags is JsonArray a)
            foreach (var t in a)
                if (t?.GetValue<string>() is { } s && s.Length > 0) list.Add(s);
        return list;
    }

    private static string BoardCaption(string discipline, int tier) => discipline switch
    {
        "smithing" => $"Anvil Grid · {tier switch { 1 => 3, 2 => 5, 3 => 7, 4 => 9, _ => 3 }}×{tier switch { 1 => 3, 2 => 5, 3 => 7, 4 => 9, _ => 3 }}",
        "refining" => "Refinery · Hub & Spoke",
        "alchemy" => "Alchemy · Reagent Sequence",
        "engineering" => "Workbench · Typed Component Lanes",
        "adornments" => "Enchanter · Shapes & Vertices",
        _ => "Placement",
    };
}
