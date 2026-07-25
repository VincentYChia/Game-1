using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Mandatory one-time class selection at game start (game_engine.py:
/// 836-840, 3195-3211): a card grid of the 6 classes; [Esc] refuses to
/// close ("Choose a class to continue"). Selecting applies the class
/// bonuses (ClassBonus seam + affinity tags), learns+equips the starting
/// skill, and refills HP/mana to the new max.
/// </summary>
public partial class ClassSelectScreen : CanvasLayer
{
    private readonly CombatWorld _combat;
    private Control _root = null!;
    private Label _warn = null!;
    private bool _open;

    public ClassSelectScreen(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        Layer = 25;
        _root = new Control();
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        var dim = new ColorRect { Color = new Color(0, 0, 0, 0.78f) };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(dim);

        var panel = new PanelContainer();
        panel.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        panel.AnchorLeft = 0.05f;
        panel.AnchorTop = 0.05f;
        panel.AnchorRight = 0.95f;
        panel.AnchorBottom = 0.95f;
        panel.OffsetLeft = panel.OffsetTop = panel.OffsetRight = panel.OffsetBottom = 0;
        panel.AddThemeStyleboxOverride("panel", UiTheme.Box(UiTheme.PanelBg, UiTheme.Border, 3, 14));
        _root.AddChild(panel);
        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 30);
        panel.AddChild(margin);

        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 16);
        margin.AddChild(box);

        box.AddChild(UiTheme.Header("Choose Your Class", 38));
        box.AddChild(UiTheme.Section("Your starting path shapes bonuses, affinities, and a signature skill.", 20));

        var scroll = UiTheme.VScroll();
        box.AddChild(scroll);

        var grid = new GridContainer
        {
            Columns = 3,
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        grid.AddThemeConstantOverride("h_separation", 18);
        grid.AddThemeConstantOverride("v_separation", 18);
        scroll.AddChild(grid);

        if (_combat.ClassDb is { } db)
        {
            foreach (var def in db.Classes.Values)
                grid.AddChild(BuildCard(def));
        }

        _warn = new Label { Text = "" };
        _warn.AddThemeFontSizeOverride("font_size", 18);
        _warn.Modulate = new Color(1f, 0.55f, 0.45f);
        box.AddChild(_warn);

        _open = true;
        UiHub.OpenScreens++;
    }

    /// <summary>Big vibrant bordered class card: icon + accent name, wrapped
    /// description, starting skill, bonuses list, and a Choose button. The
    /// whole panel highlights on hover; pressing Choose selects the class.</summary>
    private PanelContainer BuildCard(ClassDefinition def)
    {
        var card = new PanelContainer
        {
            CustomMinimumSize = new Vector2(420, 300),
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        card.AddThemeStyleboxOverride("panel",
            UiTheme.Box(UiTheme.PanelInner, UiTheme.Border, 2, 12));

        var inner = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            inner.AddThemeConstantOverride($"margin_{side}", 14);
        card.AddChild(inner);

        var col = new VBoxContainer();
        col.AddThemeConstantOverride("separation", 10);
        inner.AddChild(col);

        // -- header: icon + name --
        var head = new HBoxContainer();
        head.AddThemeConstantOverride("separation", 12);
        col.AddChild(head);

        var icon = new TextureRect
        {
            CustomMinimumSize = new Vector2(64, 64),
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
            Texture = IconCache.Get($"classes/{def.ClassId}.png"),
        };
        head.AddChild(icon);

        var name = new Label
        {
            Text = def.Name,
            VerticalAlignment = VerticalAlignment.Center,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        name.AddThemeFontSizeOverride("font_size", 28);
        name.AddThemeColorOverride("font_color", UiTheme.Accent);
        head.AddChild(name);

        // -- description --
        var desc = new Label
        {
            Text = def.Description,
            AutowrapMode = TextServer.AutowrapMode.WordSmart,
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
        };
        desc.AddThemeFontSizeOverride("font_size", 17);
        desc.AddThemeColorOverride("font_color", UiTheme.Text);
        col.AddChild(desc);

        // -- starting skill --
        if (def.StartingSkill.Length > 0)
        {
            var skillName = _combat.SkillDb?.Skills.GetValueOrDefault(def.StartingSkill)?.Name
                            ?? CombatWorld.Prettify(def.StartingSkill);
            var skillRow = new HBoxContainer();
            skillRow.AddThemeConstantOverride("separation", 8);
            col.AddChild(skillRow);

            var sIcon = new TextureRect
            {
                CustomMinimumSize = new Vector2(28, 28),
                ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
                StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                Texture = IconCache.Get($"skills/{def.StartingSkill}.png"),
            };
            skillRow.AddChild(sIcon);

            var sLabel = new Label
            {
                Text = $"Starting Skill: {skillName}",
                VerticalAlignment = VerticalAlignment.Center,
            };
            sLabel.AddThemeFontSizeOverride("font_size", 16);
            sLabel.AddThemeColorOverride("font_color", new Color(0.55f, 0.9f, 0.55f));
            skillRow.AddChild(sLabel);
        }

        // -- bonuses list --
        var bonusText = string.Join("\n",
            def.Bonuses.Select(kv => $"• {CombatWorld.Prettify(kv.Key)}: {kv.Value}"));
        if (bonusText.Length > 0)
        {
            col.AddChild(UiTheme.Section("Bonuses", 17));
            var bonus = new Label
            {
                Text = bonusText,
                AutowrapMode = TextServer.AutowrapMode.WordSmart,
                SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
                SizeFlagsVertical = Control.SizeFlags.ExpandFill,
            };
            bonus.AddThemeFontSizeOverride("font_size", 16);
            bonus.AddThemeColorOverride("font_color", new Color(0.72f, 0.8f, 0.98f));
            col.AddChild(bonus);
        }

        // -- choose button --
        var choose = UiTheme.TextButton($"Choose {def.Name}", 20);
        choose.SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
        choose.AddThemeStyleboxOverride("normal", UiTheme.Box(UiTheme.SlotBg, UiTheme.Accent, 2, 8));
        choose.AddThemeStyleboxOverride("hover", UiTheme.Box(UiTheme.Border, UiTheme.Accent, 3, 8));
        choose.AddThemeStyleboxOverride("pressed", UiTheme.Box(UiTheme.Accent, UiTheme.Accent, 3, 8));
        choose.AddThemeColorOverride("font_color", UiTheme.Accent);
        var captured = def;
        choose.Pressed += () => Select(captured);
        col.AddChild(choose);

        // whole-card hover highlight
        card.MouseEntered += () => card.AddThemeStyleboxOverride("panel",
            UiTheme.Box(UiTheme.SlotBg, UiTheme.Accent, 3, 12));
        card.MouseExited += () => card.AddThemeStyleboxOverride("panel",
            UiTheme.Box(UiTheme.PanelInner, UiTheme.Border, 2, 12));

        return card;
    }

    private static string Wrap(string text, int width)
    {
        var words = text.Split(' ');
        var lines = new List<string> { "" };
        foreach (var word in words)
        {
            if (lines[^1].Length + word.Length + 1 > width) lines.Add(word);
            else lines[^1] = lines[^1].Length == 0 ? word : lines[^1] + " " + word;
        }
        return string.Join("\n", lines);
    }

    private void Select(ClassDefinition def)
    {
        ApplyClass(_combat, def, refill: true);
        SaveSystem.SelectedClassId = def.ClassId;
        _open = false;
        _root.Visible = false;
        UiHub.OpenScreens--;
        QueueFree();
    }

    /// <summary>Shared with SaveSystem load: wires ClassBonus, affinity
    /// tags, starting skill; optionally refills HP/mana (fresh pick only).</summary>
    public static void ApplyClass(CombatWorld combat, ClassDefinition def,
                                  bool refill)
    {
        var pc = combat.Pc;
        var skills = combat.SkillMgr;
        if (pc is null) return;

        pc.ClassBonus = key =>
            def.Bonuses[key] is JsonValue v && v.TryGetValue<double>(out var d)
                ? d : 0.0;
        if (skills is not null)
        {
            skills.ClassTags = (def.Tags as JsonArray)?
                .Select(t => t?.GetValue<string>() ?? "")
                .Where(t => t.Length > 0).ToList() ?? new List<string>();
            if (def.StartingSkill.Length > 0)
            {
                skills.Learn(def.StartingSkill, skipChecks: true);
                skills.EquipFirstEmpty(def.StartingSkill);
            }
        }

        // recompute max HP with the class bonus; class pick refills to full
        pc.MaxHealthValue = 100 + pc.Stats.Vitality * 15
            + pc.ClassBonus("max_health")
            + pc.Equipment.GetStatBonuses().GetValueOrDefault("max_health", 0);
        if (refill)
        {
            pc.Health = pc.MaxHealthValue;
            pc.Mana = pc.MaxMana;
        }
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (!_open) return;
        if (@event is InputEventKey
            { Pressed: true, Echo: false, PhysicalKeycode: Key.Escape })
        {
            _warn.Text = "Choose a class to continue";   // ESC-proof (parity)
            GetViewport().SetInputAsHandled();
        }
    }
}
