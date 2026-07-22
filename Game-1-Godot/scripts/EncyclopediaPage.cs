using System.Text.Json.Nodes;
using Game1.Core.Data;
using Game1.Core.Progression;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Encyclopedia book page ([L]) — faithful simplified port of the Python
/// encyclopedia overlay (contracts/encyclopedia.json). Four tabs: Guide
/// (static help, keybinds adapted to THIS port), Skills (every SkillDb entry
/// with tier colors + KNOWN/AVAILABLE annotations — no unlock gating, all
/// listed), Titles (every TitleDb entry grouped novice→master with contract
/// tier colors, EARNED flag, random-drop odds table), Stats (level/EXP/HP
/// plus every ActivityTracker counter with value-band colors).
/// Design note: ONE shared ScrollContainer whose content is rebuilt per tab —
/// this preserves the contract quirk that scroll_offset is SHARED across
/// tabs and reset only when the book page opens (Godot clamps overscroll to
/// content height, so the infinite-overscroll quirk is softened, documented
/// deviation).
/// </summary>
public partial class EncyclopediaPage : MenuPage
{
    public override string Title => "Encyclopedia";
    public override Key Keybind => Key.L;

    private const int TabGuide = 0;
    private const int TabSkills = 1;
    private const int TabTitles = 2;
    private const int TabStats = 3;

    private readonly CombatWorld _combat;
    private TabBar _tabs = null!;
    private ScrollContainer _scroll = null!;
    private VBoxContainer _content = null!;
    private int _currentTab = TabGuide;
    private int _sharedScroll;   // contract: scroll_offset shared across tabs
    private double _refresh;

    private static readonly Color Gold = new(1f, 215 / 255f, 0f);
    private static readonly Color HeaderBlue = new(0.6f, 0.8f, 1f);
    private static readonly Color BodyGray = new(0.78f, 0.78f, 0.78f);
    private static readonly Color DimGray = new(0.6f, 0.6f, 0.6f);
    private static readonly Color KnownGreen = new(100 / 255f, 1f, 100 / 255f);
    private static readonly Color AvailableYellow = new(1f, 1f, 0.4f);
    private static readonly Color BonusGreen = new(100 / 255f, 200 / 255f, 100 / 255f);
    private static readonly Color EffectBlue = new(0.55f, 0.65f, 0.8f);

    // Contract: skill tier colors (renderer.py:4519)
    private static readonly Dictionary<int, Color> SkillTierColors = new()
    {
        [1] = new Color(150 / 255f, 150 / 255f, 150 / 255f),
        [2] = new Color(100 / 255f, 200 / 255f, 100 / 255f),
        [3] = new Color(200 / 255f, 100 / 255f, 200 / 255f),
        [4] = new Color(255 / 255f, 200 / 255f, 50 / 255f),
    };

    // Contract: title tier order + colors (renderer.py:4596-4603)
    private static readonly (string Tier, Color Color)[] TitleTiers =
    {
        ("novice", new Color(150 / 255f, 150 / 255f, 150 / 255f)),
        ("apprentice", new Color(100 / 255f, 200 / 255f, 100 / 255f)),
        ("journeyman", new Color(100 / 255f, 150 / 255f, 255 / 255f)),
        ("expert", new Color(200 / 255f, 100 / 255f, 255 / 255f)),
        ("master", new Color(255 / 255f, 200 / 255f, 50 / 255f)),
    };

    // Contract: random_drop display-only chance table (renderer.py:4656)
    private static readonly Dictionary<string, int> RandomDropChance = new()
    {
        ["apprentice"] = 20, ["journeyman"] = 10, ["expert"] = 5, ["master"] = 2,
    };

    // Guide text adapted to THIS port's controls (contract hazard: the
    // original hardcoded Python keybinds would lie here).
    private static readonly string[] GuideLines =
    {
        "=== CONTROLS ===",
        "Movement:",
        "• WASD — move   • Shift — sprint   • Space — jump",
        "Actions:",
        "• Left-click — attack / gather / talk to NPCs",
        "• Click a crafting station to open crafting",
        "Menus:",
        "• [C] Stats   • [K] Skills   • [L] Encyclopedia",
        "• [M] Map   • [J] Quests   • [I] Inventory   • [Esc] close",
        "",
        "=== PROGRESSION ===",
        "• Gain EXP from gathering, crafting, and combat",
        "• EXP to next level: 200 x 1.75^(level-1), max level 30",
        "• Each level grants 1 stat point (STR/DEF/VIT/LCK/AGI/INT)",
        "",
        "=== CRAFTING ===",
        "• Stations: forge, alchemy table, refinery, workbench, enchanting table",
        "• Minigame crafting grants 1.5x XP versus instant crafting",
        "• Higher-tier materials raise difficulty and rewards",
        "",
        "=== SKILLS ===",
        "• 5 hotbar slots; skills level up to 10 through use",
        "• Skills cost mana and have cooldowns",
        "",
        "=== TITLES ===",
        "• Earned from activity milestones (mining, combat, crafting...)",
        "• Higher tiers can be rare random drops past their threshold",
    };

    public EncyclopediaPage(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        var outer = new VBoxContainer();
        outer.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        outer.AddThemeConstantOverride("separation", 8);
        AddChild(outer);

        var title = new Label { Text = "ENCYCLOPEDIA" };
        title.AddThemeFontSizeOverride("font_size", 26);
        title.AddThemeColorOverride("font_color", Gold);
        outer.AddChild(title);

        _tabs = new TabBar();
        foreach (var name in new[] { "GAME GUIDE", "SKILLS", "TITLES", "STATS" })
            _tabs.AddTab(name);
        _tabs.TabSelected += OnTabSelected;
        outer.AddChild(_tabs);

        _scroll = new ScrollContainer
        {
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
            HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled,
        };
        outer.AddChild(_scroll);

        _content = new VBoxContainer
        {
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
            SizeFlagsVertical = Control.SizeFlags.ExpandFill,
        };
        _content.AddThemeConstantOverride("separation", 2);
        _scroll.AddChild(_content);

        var hint = new Label
        { Text = "[L or Esc] close  ·  mouse wheel scrolls  ·  scroll is shared across tabs" };
        hint.AddThemeFontSizeOverride("font_size", 13);
        hint.Modulate = new Color(1, 1, 1, 0.5f);
        outer.AddChild(hint);

        Rebuild();
    }

    public override void OnOpened()
    {
        if (_scroll is null) return;
        // Contract: toggle() resets scroll_offset ONLY on open (not on
        // tab switch, not on close).
        _sharedScroll = 0;
        _scroll.ScrollVertical = 0;
        Rebuild();
    }

    public override void Tick(double delta)
    {
        if (_scroll is null || _currentTab != TabStats) return;
        _refresh += delta;
        if (_refresh < 0.5) return;
        _refresh = 0;
        _sharedScroll = _scroll.ScrollVertical;
        Rebuild();   // live counters while playing with the book open
    }

    private void OnTabSelected(long index)
    {
        _sharedScroll = _scroll.ScrollVertical;   // carried across tabs (quirk)
        _currentTab = (int)index;
        Rebuild();
    }

    private void Rebuild()
    {
        while (_content.GetChildCount() > 0)
        {
            var child = _content.GetChild(0);
            _content.RemoveChild(child);
            child.QueueFree();
        }

        switch (_currentTab)
        {
            case TabGuide: BuildGuide(); break;
            case TabSkills: BuildSkills(); break;
            case TabTitles: BuildTitles(); break;
            case TabStats: BuildStats(); break;
        }

        // Restore the shared offset after the new content lays out.
        _scroll.SetDeferred(ScrollContainer.PropertyName.ScrollVertical, _sharedScroll);
    }

    // ── Guide ────────────────────────────────────────────────────────────

    private void BuildGuide()
    {
        // Contract line styling: '===' gold header, ':' light-blue section,
        // '•' bullet, blank = spacer (renderer.py:4288-4311).
        foreach (var line in GuideLines)
        {
            if (line.Length == 0) { AddGap(); continue; }
            if (line.StartsWith("===")) { AddGap(4); AddLine(line, 20, Gold); }
            else if (line.EndsWith(":")) AddLine(line, 16, HeaderBlue);
            else if (line.StartsWith("•")) AddLine(line, 14, BodyGray);
            else AddLine(line, 13, DimGray);
        }
    }

    // ── Skills ───────────────────────────────────────────────────────────

    private void BuildSkills()
    {
        var db = _combat.SkillDb;
        if (db is null || db.Skills.Count == 0)
        {
            AddLine("Skill database not loaded.", 15, DimGray);
            return;
        }

        AddLine($"All Skills ({db.Skills.Count} total)", 20, Gold);
        AddGap();

        var mgr = _combat.SkillMgr;
        for (var tier = 1; tier <= 4; tier++)
        {
            var group = db.Skills.Values
                .Where(s => (int)s.Tier == tier)
                .OrderBy(s => s.Name, StringComparer.Ordinal)
                .ToList();
            if (group.Count == 0) continue;

            AddLine($"-- TIER {tier} --", 17, SkillTierColors[tier]);
            foreach (var s in group)
            {
                var known = mgr?.Known.ContainsKey(s.SkillId) == true;
                var available = !known && (mgr?.CanLearn(s.SkillId).Ok ?? false);
                var suffix = known ? "  [KNOWN]" : available ? "  [AVAILABLE]" : "";
                AddLine($"{s.Name}{suffix}", 15,
                    known ? KnownGreen : available ? AvailableYellow : BodyGray);

                var reqs = $"Requires: Lvl {(int)s.RequiredCharacterLevel}";
                if (s.RequiredStats is JsonObject stats && stats.Count > 0)
                    reqs += ", " + string.Join(", ",
                        stats.Select(kv => $"{kv.Key} {kv.Value}"));
                AddLine($"    {reqs}", 12, DimGray);

                var effect = s.EffectType;
                if (!string.IsNullOrEmpty(s.EffectCategory))
                    effect += $" ({s.EffectCategory})";
                if (!string.IsNullOrEmpty(s.EffectMagnitude))
                    effect += $" — {s.EffectMagnitude}";
                if (!string.IsNullOrEmpty(effect))
                    AddLine($"    {effect}", 12, EffectBlue);
                AddGap(2);
            }
            AddGap();
        }
    }

    // ── Titles ───────────────────────────────────────────────────────────

    private void BuildTitles()
    {
        var db = _combat.TitleDb;
        if (db is null || db.Titles.Count == 0)
        {
            AddLine("Title database not loaded.", 15, DimGray);
            return;
        }

        AddLine($"All Titles ({db.Titles.Count} total)", 20, Gold);
        AddGap();

        var titles = _combat.Pc?.Titles;
        var rendered = new HashSet<string>();

        void Entry(TitleDefinition t)
        {
            var earned = titles?.HasTitle(t.TitleId) == true;
            AddLine(earned ? $"{t.Name}  [EARNED]" : t.Name, 15,
                earned ? Gold : BodyGray);

            var req = $"Requires: {t.AcquisitionThreshold} {t.ActivityType}";
            if (t.AcquisitionMethod == "random_drop"
                && RandomDropChance.TryGetValue(t.Tier, out var pct))
                req += $" ({pct}% chance)";
            AddLine($"    {req}", 12, DimGray);
            AddLine($"    {t.BonusDescription}", 12, BonusGreen);
            AddGap(2);
        }

        foreach (var (tierName, tierColor) in TitleTiers)
        {
            var ids = db.TitleOrder
                .Where(id => db.Titles[id].Tier == tierName)
                .ToList();
            if (ids.Count == 0) continue;

            AddLine($"-- {tierName.ToUpperInvariant()} --", 17, tierColor);
            foreach (var id in ids)
            {
                rendered.Add(id);
                Entry(db.Titles[id]);
            }
            AddGap();
        }

        var leftovers = db.TitleOrder.Where(id => !rendered.Contains(id)).ToList();
        if (leftovers.Count > 0)
        {
            AddLine("-- OTHER --", 17, DimGray);
            foreach (var id in leftovers) Entry(db.Titles[id]);
        }
    }

    // ── Stats ────────────────────────────────────────────────────────────

    private void BuildStats()
    {
        var pc = _combat.Pc;
        if (pc is null)
        {
            AddLine("No player character.", 15, DimGray);
            return;
        }

        AddLine("Player Statistics", 20, Gold);
        AddGap();

        AddLine("Character:", 16, HeaderBlue);
        AddLine($"    Level: {pc.Leveling.Level} / {LevelingSystem.MaxLevel}",
            14, BodyGray);
        var next = pc.Leveling.GetExpForNextLevel();
        AddLine(next > 0
                ? $"    EXP: {pc.Leveling.CurrentExp:N0} / {next:N0} to next level"
                : $"    EXP: {pc.Leveling.CurrentExp:N0} (max level)",
            14, BodyGray);
        AddLine($"    HP: {pc.Health:F0} / {pc.MaxHealthValue:F0}", 14, BodyGray);
        AddLine($"    Mana: {pc.Mana:F0} / {pc.MaxMana:F0}", 14, BodyGray);
        AddLine($"    Unspent stat points: {pc.Leveling.UnallocatedStatPoints}",
            14, BodyGray);
        AddGap();

        AddLine($"Activity Counts ({pc.Activities.ActivityCounts.Count} tracked):",
            16, HeaderBlue);
        // Contract: sorted by (-value, name); value-band colors.
        foreach (var kv in pc.Activities.ActivityCounts
                     .OrderByDescending(kv => kv.Value)
                     .ThenBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var name = char.ToUpperInvariant(kv.Key[0]) + kv.Key[1..];
            AddLine($"    {name}: {kv.Value:N0}", 14, BandColor(kv.Value));
        }
    }

    // Contract stats color bands (renderer.py:4753-4780)
    private static Color BandColor(long value) =>
        value <= 0 ? new Color(100 / 255f, 100 / 255f, 100 / 255f)
        : value < 10 ? new Color(150 / 255f, 150 / 255f, 150 / 255f)
        : value < 100 ? new Color(180 / 255f, 180 / 255f, 200 / 255f)
        : value < 1000 ? new Color(200 / 255f, 200 / 255f, 220 / 255f)
        : new Color(220 / 255f, 220 / 255f, 255 / 255f);

    // ── Helpers ──────────────────────────────────────────────────────────

    private void AddLine(string text, int fontSize, Color color)
    {
        var label = new Label
        {
            Text = text,
            AutowrapMode = TextServer.AutowrapMode.WordSmart,
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
        };
        label.AddThemeFontSizeOverride("font_size", fontSize);
        label.AddThemeColorOverride("font_color", color);
        _content.AddChild(label);
    }

    private void AddGap(int pixels = 6) =>
        _content.AddChild(new Control
        { CustomMinimumSize = new Vector2(0, pixels) });
}
