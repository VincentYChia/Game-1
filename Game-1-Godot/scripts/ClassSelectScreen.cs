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

        var dim = new ColorRect { Color = new Color(0, 0, 0, 0.7f) };
        dim.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(dim);

        var center = new CenterContainer();
        center.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _root.AddChild(center);
        var panel = new PanelContainer();
        center.AddChild(panel);
        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 20);
        panel.AddChild(margin);

        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 10);
        margin.AddChild(box);

        var title = new Label { Text = "Choose Your Class" };
        title.AddThemeFontSizeOverride("font_size", 28);
        title.Modulate = new Color(1f, 0.84f, 0f);
        box.AddChild(title);

        var grid = new GridContainer { Columns = 3 };
        grid.AddThemeConstantOverride("h_separation", 10);
        grid.AddThemeConstantOverride("v_separation", 10);
        box.AddChild(grid);

        if (_combat.ClassDb is { } db)
        {
            foreach (var def in db.Classes.Values)
            {
                var bonuses = string.Join(", ",
                    def.Bonuses.Select(kv => $"{kv.Key} {kv.Value}"));
                var card = new Button
                {
                    Text = $"{def.Name}\n{Wrap(def.Description, 38)}\n"
                           + (def.StartingSkill.Length > 0
                               ? $"skill: {def.StartingSkill}\n" : "")
                           + Wrap(bonuses, 38),
                    CustomMinimumSize = new Vector2(300, 150),
                    ClipText = false,
                };
                card.AddThemeFontSizeOverride("font_size", 13);
                var captured = def;
                card.Pressed += () => Select(captured);
                grid.AddChild(card);
            }
        }

        _warn = new Label { Text = "" };
        _warn.AddThemeFontSizeOverride("font_size", 15);
        _warn.Modulate = new Color(1f, 0.55f, 0.45f);
        box.AddChild(_warn);

        _open = true;
        UiHub.OpenScreens++;
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
