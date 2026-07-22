using System.Text.Json.Nodes;
using Game1.Core.Data;
using Game1.Core.Progression;
using Godot;

namespace Game1.Godot;

/// <summary>
/// NPC dialogue popup (renderer.py:4161-4272 + game_engine.py:1563-1653).
/// Canonical NPCs speak their speechbank (fresh greeting per conversation,
/// idle barks rotating across conversations) and show the quest section:
/// a green 'Turn In Quest' button first when a completable quest exists,
/// then up to 3 available quests (title + 60-char description). Accepting
/// speaks speechbank.quest_offer; turn-in shows one line per reward then
/// the completion-dialogue priority chain (quest_def.completion_dialogue →
/// speechbank.quest_complete → cycling fallback). Village-template NPCs
/// keep simple flavor lines. [F]/[Esc]/click-advance close; opens via
/// click or [F].
/// </summary>
public partial class DialogueScreen : CanvasLayer
{
    private readonly CombatWorld _combat;
    private Control _root = null!;
    private Label _name = null!;
    private Label _text = null!;
    private VBoxContainer _questBox = null!;
    private bool _open;
    private LiveNpc? _npc;
    private List<string> _pendingLines = new();
    private int _lineIdx;

    public DialogueScreen(CombatWorld combat) => _combat = combat;

    public override void _Ready()
    {
        Layer = 11;
        _root = new Control { Visible = false };
        _root.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        AddChild(_root);

        var panel = new PanelContainer
        {
            AnchorLeft = 0.2f, AnchorRight = 0.8f,
            AnchorTop = 0.66f, AnchorBottom = 0.94f,
        };
        _root.AddChild(panel);

        var margin = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" })
            margin.AddThemeConstantOverride($"margin_{side}", 14);
        panel.AddChild(margin);

        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", 6);
        margin.AddChild(box);

        _name = new Label { Text = "" };
        _name.AddThemeFontSizeOverride("font_size", 22);
        _name.Modulate = new Color(1f, 0.9f, 0.6f);
        box.AddChild(_name);

        _text = new Label
        { Text = "", AutowrapMode = TextServer.AutowrapMode.WordSmart };
        _text.AddThemeFontSizeOverride("font_size", 18);
        box.AddChild(_text);

        _questBox = new VBoxContainer();
        _questBox.AddThemeConstantOverride("separation", 4);
        box.AddChild(_questBox);

        var hint = new Label { Text = "click: continue  ·  [F]/[Esc] leave" };
        hint.AddThemeFontSizeOverride("font_size", 12);
        hint.Modulate = new Color(1, 1, 1, 0.5f);
        box.AddChild(hint);
    }

    public void Open(LiveNpc npc)
    {
        if (_open) return;
        _open = true;
        _root.Visible = true;
        UiHub.OpenScreens++;
        _npc = npc;
        _pendingLines.Clear();
        _lineIdx = 0;

        if (npc.Def is { } def)
        {
            // Fresh greeting each conversation; indices persist (parity)
            npc.Dialogue.ResetConversation();
            _name.Text = def.Title.Length > 0
                ? $"{def.Name} — {def.Title}" : def.Name;
            _text.Text = npc.Dialogue.GetNextLine(def.Speechbank.AsObject());
        }
        else
        {
            _name.Text = $"{npc.Name} — {npc.VillageName}";
            _pendingLines = new List<string>
            {
                $"Welcome to {npc.VillageName}, traveler.",
                $"These are {npc.NationName} lands — mind the wilds.",
                "Safe travels out there.",
            };
            _text.Text = _pendingLines[0];
        }
        RefreshQuestSection();
    }

    private void RefreshQuestSection()
    {
        foreach (var child in _questBox.GetChildren()) child.QueueFree();
        var def = _npc?.Def;
        var quests = _combat.QuestMgr;
        var npcDb = _combat.NpcDb;
        if (def is null || quests is null || npcDb is null) return;

        var npcQuestIds = (def.Quests as JsonArray)?
            .Select(q => q?.GetValue<string>() ?? "")
            .Where(q => q.Length > 0).ToList() ?? new List<string>();

        // Turn-in first: first NPC quest that is active + completable
        var turnIn = npcQuestIds
            .Select(id => quests.ActiveQuests.GetValueOrDefault(id))
            .FirstOrDefault(q => q is not null && quests.CheckCompletion(q));
        if (turnIn is not null)
        {
            var btn = new Button { Text = $"Turn In Quest: {turnIn.Def.Title}" };
            btn.AddThemeFontSizeOverride("font_size", 15);
            btn.Modulate = new Color(0.55f, 1f, 0.55f);
            btn.Pressed += () => DoTurnIn(turnIn);
            _questBox.AddChild(btn);
        }

        // Then up to 3 available quests (not active, not completed)
        var available = npcQuestIds
            .Where(id => !quests.ActiveQuests.ContainsKey(id)
                         && !quests.CompletedQuests.Contains(id))
            .Select(id => npcDb.Quests.GetValueOrDefault(id))
            .Where(q => q is not null)
            .Take(3).ToList();
        foreach (var quest in available)
        {
            var desc = quest!.Description.Length > 60
                ? quest.Description[..60] + "..." : quest.Description;
            var btn = new Button
            {
                Text = $"{quest.Title}\n{desc}",
                Alignment = HorizontalAlignment.Left,
            };
            btn.AddThemeFontSizeOverride("font_size", 14);
            btn.Pressed += () => DoAccept(quest);
            _questBox.AddChild(btn);
        }

        if (turnIn is null && available.Count == 0)
        {
            var none = new Label { Text = "No quests available at this time." };
            none.AddThemeFontSizeOverride("font_size", 13);
            none.Modulate = new Color(1, 1, 1, 0.55f);
            _questBox.AddChild(none);
        }
    }

    private void DoAccept(QuestDefinition quest)
    {
        var quests = _combat.QuestMgr;
        var def = _npc?.Def;
        if (quests is null || def is null) return;
        if (!quests.StartQuest(quest)) return;
        // NPC speaks quest_offer; fallback = next cycling line
        _text.Text = NpcDialogueState.QuestOffer(def.Speechbank.AsObject())
                     ?? _npc!.Dialogue.GetNextLine(def.Speechbank.AsObject());
        _name.Text = $"{def.Name}  ·  Quest accepted: {quest.Title}";
        RefreshQuestSection();
    }

    private void DoTurnIn(ActiveQuest quest)
    {
        var quests = _combat.QuestMgr;
        var def = _npc?.Def;
        if (quests is null || def is null) return;
        var messages = quests.CompleteQuest(quest.Def.QuestId);
        if (messages is null) return;

        // Completion chain: quest completion_dialogue (all lines) →
        // speechbank.quest_complete → cycling fallback
        _pendingLines = (quest.Def.CompletionDialogue as JsonArray)?
            .Select(l => l?.GetValue<string>() ?? "")
            .Where(l => l.Length > 0).ToList() ?? new List<string>();
        if (_pendingLines.Count == 0)
        {
            var line = NpcDialogueState.QuestComplete(def.Speechbank.AsObject())
                       ?? _npc!.Dialogue.GetNextLine(def.Speechbank.AsObject());
            _pendingLines = new List<string> { line };
        }
        _lineIdx = 0;
        _text.Text = _pendingLines[0];
        _name.Text = $"{def.Name}  ·  {string.Join("  ", messages)}";
        RefreshQuestSection();
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (!_open) return;
        var advance =
            @event is InputEventMouseButton
            { ButtonIndex: MouseButton.Left, Pressed: true }
            || @event is InputEventKey
            { Pressed: true, Echo: false, PhysicalKeycode: Key.Space };
        var close = @event is InputEventKey
        { Pressed: true, Echo: false, PhysicalKeycode: Key.Escape or Key.F };

        if (close)
        {
            Close();
            GetViewport().SetInputAsHandled();
            return;
        }
        if (!advance) return;

        // Advance through queued lines; past the end just idles the panel
        if (_pendingLines.Count > 0 && _lineIdx < _pendingLines.Count - 1)
        {
            _lineIdx++;
            _text.Text = _pendingLines[_lineIdx];
        }
        else if (_pendingLines.Count > 0)
        {
            Close();
        }
    }

    private void Close()
    {
        _open = false;
        _root.Visible = false;
        UiHub.OpenScreens--;
        _npc = null;
        _pendingLines.Clear();
    }
}
