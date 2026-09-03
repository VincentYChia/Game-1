using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// PLACEMENT — the "mise en place" ritual before the minigame. You lay the recipe's
/// materials onto the discipline's bench (smithing grid · refining hub-and-spoke ·
/// alchemy sequence · engineering rail · enchanting rune circle), then begin the craft.
///
/// PURELY THEMATIC: the actual craft is decided downstream (recipe filters + the craft
/// system), so arrangement has ZERO effect on quality — it never touches the performance
/// score or Core. It is immersion only: a satisfying, discipline-flavored moment of
/// preparation. Cancelling is a free back-out (nothing is consumed until after the
/// minigame). Shares CraftStyle/CraftFx with the minigame stage for one coherent look.
/// </summary>
public partial class PlacementStage : CanvasLayer
{
    private const float BoardW = 540f, BoardH = 380f;

    private sealed class Token
    {
        public string Name = "";
        public int Qty = 1;
        public Texture2D? Icon;
        public Color Rarity = UiTheme.Rarity["common"];
        public int Slot = -1;   // index into _slotPos, or -1 if in the tray
    }

    private Control _root = null!;
    private ColorRect _backdrop = null!;
    private Control _board = null!;
    private Label _glyph = null!;
    private Label _title = null!;
    private Label _subtitle = null!;
    private HBoxContainer _tray = null!;
    private Label _hint = null!;

    private string _discipline = "smithing";
    private DisciplineStyle _style;
    private readonly List<Token> _tokens = new();
    private Vector2[] _slotPos = System.Array.Empty<Vector2>();
    private string[] _slotLabels = System.Array.Empty<string>();
    private float _slotSize = 64f;
    private int _selected = -1;
    private double _anim;
    private bool _open;
    private System.Action? _onConfirm;
    private System.Action? _onCancel;

    public override void _Ready()
    {
        Layer = 15;   // above the browser (10), below the minigame stage (20)
        _root = new Control { Visible = false };
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        _backdrop = new ColorRect { MouseFilter = Control.MouseFilterEnum.Stop };
        _backdrop.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(_backdrop);

        var center = new CenterContainer();
        center.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(center);

        var card = new PanelContainer();
        card.AddThemeStyleboxOverride("panel", UiTheme.Box(new Color(0.08f, 0.09f, 0.13f, 0.94f), UiTheme.Border, 3, 16));
        center.AddChild(card);
        var pad = new MarginContainer();
        foreach (var s in new[] { "left", "right", "top", "bottom" })
            pad.AddThemeConstantOverride($"margin_{s}", 24);
        card.AddChild(pad);
        var col = new VBoxContainer();
        col.AddThemeConstantOverride("separation", 12);
        pad.AddChild(col);

        // header
        var head = new HBoxContainer();
        head.AddThemeConstantOverride("separation", 14);
        col.AddChild(head);
        _glyph = new Label();
        _glyph.AddThemeFontSizeOverride("font_size", 42);
        head.AddChild(_glyph);
        var titleCol = new VBoxContainer { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill };
        _title = new Label { Text = "Prepare the Materials" };
        _title.AddThemeFontSizeOverride("font_size", 28);
        _title.AddThemeColorOverride("font_color", UiTheme.Text);
        titleCol.AddChild(_title);
        _subtitle = new Label { Modulate = new Color(1, 1, 1, 0.7f) };
        _subtitle.AddThemeFontSizeOverride("font_size", 15);
        titleCol.AddChild(_subtitle);
        head.AddChild(titleCol);

        // board
        _board = new Control
        {
            CustomMinimumSize = new Vector2(BoardW, BoardH),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
        };
        _board.Draw += DrawBoard;
        _board.GuiInput += OnBoardInput;
        col.AddChild(_board);

        _hint = new Label
        {
            Text = "click a material, then a bench slot to place it  ·  arrange it as you like",
            Modulate = new Color(0.7f, 0.82f, 1f),
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        _hint.AddThemeFontSizeOverride("font_size", 13);
        col.AddChild(_hint);

        // material tray
        var trayScroll = new ScrollContainer
        {
            CustomMinimumSize = new Vector2(BoardW, 74),
            VerticalScrollMode = ScrollContainer.ScrollMode.Disabled,
        };
        col.AddChild(trayScroll);
        _tray = new HBoxContainer();
        _tray.AddThemeConstantOverride("separation", 10);
        trayScroll.AddChild(_tray);

        // buttons
        var buttons = new HBoxContainer { Alignment = BoxContainer.AlignmentMode.Center };
        buttons.AddThemeConstantOverride("separation", 14);
        col.AddChild(buttons);
        var auto = MakeBtn("⤢ AUTO-ARRANGE", new Color(0.6f, 0.7f, 0.9f), 200);
        auto.Pressed += AutoArrange;
        buttons.AddChild(auto);
        var cancel = MakeBtn("← BACK", new Color(0.8f, 0.55f, 0.5f), 150);
        cancel.Pressed += Cancel;
        buttons.AddChild(cancel);
        var begin = MakeBtn("BEGIN CRAFT →", UiTheme.Accent, 220);
        begin.Pressed += Confirm;
        buttons.AddChild(begin);
    }

    private Button MakeBtn(string text, Color accent, int minW)
    {
        var b = UiTheme.TextButton(text, 18);
        b.CustomMinimumSize = new Vector2(minW, 46);
        b.FocusMode = Control.FocusModeEnum.None;
        b.AddThemeStyleboxOverride("normal", UiTheme.Box(UiTheme.SlotBg, accent, 2, 8));
        b.AddThemeStyleboxOverride("hover", UiTheme.Box(UiTheme.PanelInner, accent, 2, 8));
        b.AddThemeStyleboxOverride("pressed", UiTheme.Box(UiTheme.SlotEmpty, accent, 3, 8));
        return b;
    }

    /// <summary>Open the ritual for a recipe. onConfirm → proceed to the minigame;
    /// onCancel → return to the browser (nothing consumed).</summary>
    public void Begin(Recipe recipe, CombatWorld combat, System.Action onConfirm, System.Action onCancel)
    {
        _onConfirm = onConfirm;
        _onCancel = onCancel;
        _discipline = recipe.StationType;
        _style = CraftStyle.Get(_discipline);
        _selected = -1;

        _backdrop.Material = CraftFx.Backdrop(_style.Top, _style.Bottom, _style.Glow, new Vector2(0.5f, 0.7f), 0.5f);
        _glyph.Text = _style.Glyph;
        _glyph.AddThemeColorOverride("font_color", _style.Accent);
        _title.AddThemeColorOverride("font_color", UiTheme.Text);
        _subtitle.Text = $"{_style.Name} · {CombatWorld.Prettify(recipe.OutputId)}";

        BuildTokens(recipe, combat);
        LayoutSlots(_discipline, _tokens.Count);
        RebuildTray();

        _open = true;
        _root.Visible = true;
        UiHub.OpenScreens++;
        _board.QueueRedraw();
    }

    private void BuildTokens(Recipe recipe, CombatWorld combat)
    {
        _tokens.Clear();
        if (recipe.Inputs is not JsonArray arr) return;
        foreach (var node in arr)
        {
            if (node is not JsonObject o) continue;
            var id = o["materialId"]?.GetValue<string>() ?? "?";
            var qty = 1;
            if ((o["quantity"] ?? o["qty"]) is JsonValue v)   // canonical JSON uses "quantity"
            {
                if (v.TryGetValue<int>(out var iv)) qty = iv;
                else if (v.TryGetValue<double>(out var dv)) qty = (int)dv;
            }
            var mat = combat.MaterialDb?.GetMaterial(id);
            var iconPath = combat.EquipDb?.CreateEquipmentFromId(id)?.IconPath ?? mat?.IconPath;
            var rarity = mat?.Rarity ?? "common";
            _tokens.Add(new Token
            {
                Name = mat?.Name ?? CombatWorld.Prettify(id),
                Qty = qty,
                Icon = IconCache.Get(iconPath),
                Rarity = UiTheme.Rarity.GetValueOrDefault(rarity, UiTheme.Rarity["common"]),
            });
        }
    }

    private void LayoutSlots(string discipline, int count)
    {
        count = Mathf.Max(1, count);
        var cx = BoardW / 2f;
        var cy = BoardH / 2f;
        var pos = new Vector2[count];
        var labels = new string[count];
        _slotSize = Mathf.Clamp(72f - Mathf.Max(0, count - 5) * 4f, 48f, 72f);

        switch (discipline)
        {
            case "refining":   // hub-and-spoke: first material at the core, rest ring it
            {
                pos[0] = new Vector2(cx, cy);
                labels[0] = "CORE";
                var ring = count - 1;
                var radius = Mathf.Min(150f, 70f + ring * 12f);
                for (var i = 1; i < count; i++)
                {
                    var a = -Mathf.Pi / 2f + (i - 1) * Mathf.Tau / Mathf.Max(1, ring);
                    pos[i] = new Vector2(cx + Mathf.Cos(a) * radius, cy + Mathf.Sin(a) * radius);
                }
                break;
            }
            case "adornments":  // rune circle
            {
                var radius = Mathf.Min(150f, 60f + count * 10f);
                for (var i = 0; i < count; i++)
                {
                    var a = -Mathf.Pi / 2f + i * Mathf.Tau / count;
                    pos[i] = new Vector2(cx + Mathf.Cos(a) * radius, cy + Mathf.Sin(a) * radius);
                }
                break;
            }
            case "alchemy":     // ordered sequence (order matters)
            {
                string[] roles = { "BASE", "REAGENT", "CATALYST" };
                var spacing = Mathf.Min(_slotSize + 26f, (BoardW - 80f) / count);
                var startX = cx - (count - 1) * spacing / 2f;
                for (var i = 0; i < count; i++)
                {
                    pos[i] = new Vector2(startX + i * spacing, cy);
                    labels[i] = i < roles.Length ? roles[i] : $"{i + 1}";
                }
                break;
            }
            case "engineering": // labeled rail
            {
                string[] roles = { "FRAME", "FUNCTION", "POWER", "MODIFIER" };
                var spacing = Mathf.Min(_slotSize + 30f, (BoardW - 80f) / count);
                var startX = cx - (count - 1) * spacing / 2f;
                for (var i = 0; i < count; i++)
                {
                    pos[i] = new Vector2(startX + i * spacing, cy);
                    labels[i] = roles[i % roles.Length];
                }
                break;
            }
            default:            // smithing (and fallback): centered grid
            {
                var cols = Mathf.Max(1, (int)Mathf.Ceil(Mathf.Sqrt(count)));
                var rows = (count + cols - 1) / cols;
                var spacing = _slotSize + 18f;
                var startX = cx - (cols - 1) * spacing / 2f;
                var startY = cy - (rows - 1) * spacing / 2f;
                for (var i = 0; i < count; i++)
                {
                    var r = i / cols; var c = i % cols;
                    pos[i] = new Vector2(startX + c * spacing, startY + r * spacing);
                }
                break;
            }
        }
        _slotPos = pos;
        _slotLabels = labels;
    }

    private void RebuildTray()
    {
        foreach (var ch in _tray.GetChildren()) ch.QueueFree();
        var anyLeft = false;
        for (var i = 0; i < _tokens.Count; i++)
        {
            var tk = _tokens[i];
            if (tk.Slot >= 0) continue;
            anyLeft = true;
            var idx = i;
            var b = new Button
            {
                Text = $" {tk.Qty}× {tk.Name}",
                Icon = tk.Icon,
                ExpandIcon = true,
                FocusMode = Control.FocusModeEnum.None,
                CustomMinimumSize = new Vector2(0, 60),
            };
            b.AddThemeFontSizeOverride("font_size", 16);
            var sel = idx == _selected;
            b.AddThemeStyleboxOverride("normal", UiTheme.Box(sel ? UiTheme.PanelInner : UiTheme.SlotBg, tk.Rarity, sel ? 3 : 2, 8));
            b.AddThemeStyleboxOverride("hover", UiTheme.Box(UiTheme.PanelInner, UiTheme.Accent, 2, 8));
            b.AddThemeStyleboxOverride("pressed", UiTheme.Box(UiTheme.SlotEmpty, UiTheme.Accent, 3, 8));
            b.Pressed += () => SelectToken(idx);
            _tray.AddChild(b);
        }
        if (!anyLeft)
        {
            var done = new Label { Text = "  everything is on the bench — begin when ready  " };
            done.AddThemeFontSizeOverride("font_size", 15);
            done.Modulate = new Color(0.6f, 0.9f, 0.7f);
            _tray.AddChild(done);
        }
    }

    private void SelectToken(int i)
    {
        _selected = _selected == i ? -1 : i;
        RebuildTray();
        _board.QueueRedraw();
    }

    private void OnBoardInput(InputEvent @event)
    {
        if (@event is not InputEventMouseButton { Pressed: true, ButtonIndex: MouseButton.Left } mb) return;
        var best = -1; var bestD = _slotSize * 0.75f;
        for (var i = 0; i < _slotPos.Length; i++)
        {
            var d = _slotPos[i].DistanceTo(mb.Position);
            if (d < bestD) { bestD = d; best = i; }
        }
        if (best < 0) return;

        var occupant = _tokens.FindIndex(t => t.Slot == best);
        if (occupant >= 0)                       // pick the placed token back up
        {
            _tokens[occupant].Slot = -1;
            _selected = occupant;
        }
        else if (_selected >= 0)                 // drop the held token here
        {
            _tokens[_selected].Slot = best;
            CraftFx.Burst(_board, _slotPos[best], _tokens[_selected].Rarity, 12, 140f, 0.5f, 3f, 120f);
            _selected = -1;
        }
        RebuildTray();
        _board.QueueRedraw();
    }

    private void AutoArrange()
    {
        var slot = 0;
        foreach (var tk in _tokens)
        {
            if (tk.Slot >= 0) continue;
            while (slot < _slotPos.Length && _tokens.Exists(t => t.Slot == slot)) slot++;
            if (slot >= _slotPos.Length) break;
            tk.Slot = slot;
            CraftFx.Burst(_board, _slotPos[slot], tk.Rarity, 8, 120f, 0.4f, 3f, 100f);
            slot++;
        }
        _selected = -1;
        RebuildTray();
        _board.QueueRedraw();
    }

    private void Confirm() => Close(_onConfirm);
    private void Cancel() => Close(_onCancel);

    private void Close(System.Action? cb)
    {
        if (!_open) return;
        _open = false;
        _root.Visible = false;
        UiHub.OpenScreens--;
        _onConfirm = null; _onCancel = null;
        cb?.Invoke();
    }

    public override void _Process(double delta)
    {
        if (!_open) return;
        _anim += delta;
        _board.QueueRedraw();
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (_open && @event is InputEventKey { Pressed: true, Echo: false, PhysicalKeycode: Key.Escape })
        {
            Cancel();
            GetViewport().SetInputAsHandled();
        }
    }

    private void DrawBoard()
    {
        // bench panel
        CraftFx.RoundRect(_board, new Rect2(0, 0, BoardW, BoardH), new Color(0.06f, 0.07f, 0.10f, 0.9f),
            new Color(_style.Accent.R, _style.Accent.G, _style.Accent.B, 0.5f), 2, 14);

        // discipline motif connecting the slots
        var acc = new Color(_style.Accent.R, _style.Accent.G, _style.Accent.B, 0.4f);
        switch (_discipline)
        {
            case "refining":   // spokes from the hub
                for (var i = 1; i < _slotPos.Length; i++)
                    _board.DrawLine(_slotPos[0], _slotPos[i], acc, 2f);
                break;
            case "adornments": // constellation ring
                for (var i = 0; i < _slotPos.Length; i++)
                    _board.DrawLine(_slotPos[i], _slotPos[(i + 1) % _slotPos.Length], acc, 2f);
                break;
            case "alchemy":    // flow arrows
            case "engineering":
                for (var i = 0; i + 1 < _slotPos.Length; i++)
                    _board.DrawLine(_slotPos[i] + new Vector2(_slotSize / 2f, 0),
                        _slotPos[i + 1] - new Vector2(_slotSize / 2f, 0), acc, 2f);
                break;
        }

        var font = _board.GetThemeDefaultFont();
        var pulse = 0.5f + 0.5f * Mathf.Sin((float)_anim * 4f);
        for (var i = 0; i < _slotPos.Length; i++)
        {
            var p = _slotPos[i];
            var rect = new Rect2(p - new Vector2(_slotSize / 2f, _slotSize / 2f), new Vector2(_slotSize, _slotSize));
            var occupant = _tokens.FindIndex(t => t.Slot == i);
            var empty = occupant < 0;

            // empty slots glow while a token is held (valid targets)
            if (empty && _selected >= 0)
                CraftFx.Glow(_board, p, _slotSize * 0.6f, new Color(_style.Accent.R, _style.Accent.G, _style.Accent.B, 0.25f * pulse), 4);

            CraftFx.RoundRect(_board, rect, new Color(0.12f, 0.13f, 0.17f, empty ? 0.7f : 0.95f),
                empty ? new Color(0.4f, 0.43f, 0.5f, 0.7f) : _tokens[occupant].Rarity, empty ? 1 : 2, 8);

            if (occupant >= 0 && _tokens[occupant].Icon is { } tex)
            {
                var pad = 8f;
                _board.DrawTextureRect(tex, new Rect2(rect.Position + new Vector2(pad, pad),
                    rect.Size - new Vector2(pad * 2, pad * 2)), false);
                _board.DrawString(font, rect.Position + new Vector2(_slotSize - 22, _slotSize - 6),
                    $"×{_tokens[occupant].Qty}", HorizontalAlignment.Left, -1, 13, Colors.White);
            }

            if (i < _slotLabels.Length && !string.IsNullOrEmpty(_slotLabels[i]))
                _board.DrawString(font, p + new Vector2(-_slotSize / 2f, _slotSize / 2f + 14),
                    _slotLabels[i], HorizontalAlignment.Center, _slotSize, 12,
                    new Color(_style.Accent.R, _style.Accent.G, _style.Accent.B, 0.8f));
        }
    }
}
