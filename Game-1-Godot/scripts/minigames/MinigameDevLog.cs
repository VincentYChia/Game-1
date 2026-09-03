using Godot;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace Game1.Godot;

/// <summary>
/// SHARED PLAYTEST HARNESS for the crafting minigames (extracted from the Alchemy rebuild, where it was ~120 lines
/// of hand-coded F1/F7 plumbing). Composition, not inheritance: an overlay OWNS one of these and forwards to it —
/// the sacred <see cref="MinigameOverlay"/> base stays 0-churn.
///
/// • F1 toggles an on-screen rolling event log (<see cref="ShowLog"/> / <see cref="DrawLog"/>).
/// • F7 opens a notes box (a real <see cref="LineEdit"/>); each entry is timestamped and INTERLEAVED with the event
///   log into <c>res://playtest_logs/&lt;discipline&gt;_playtest.log</c>, so notes land in order/context with a rich
///   discipline-supplied snapshot.
///
/// The discipline supplies the CONTEXT bracket (via <see cref="Context"/>), the session header lines, the note
/// snapshot lines, and the pinned status block — everything discipline-specific — while this owns the log buffer,
/// file IO, notes UI, input routing, and on-screen draw. A dev tool: logging never throws into the game loop.
/// </summary>
public sealed class MinigameDevLog
{
    private static readonly Color Gold = new(0.97f, 0.78f, 0.34f);
    private static readonly Color Sub = new(0.93f, 0.90f, 0.85f, 0.55f);

    private readonly string _discipline;
    private readonly string _fileName;
    private readonly List<string> _log = new();
    private string _logPath = "";
    private int _noteCount;

    private PanelContainer? _notesPanel;
    private LineEdit? _noteEdit;
    private Label? _notesHint;

    /// <summary>Set by the discipline: returns the middle of the log bracket (e.g. <c>"t= 12.3 | Playing |  42%"</c>).
    /// Kept discipline-owned because phase / play-time / best-quality are discipline state.</summary>
    public Func<string>? Context;

    /// <summary>Fires when the player submits an F7 note. The discipline builds its snapshot and calls <see cref="Note"/>.</summary>
    public event Action<string>? NoteSubmitted;

    /// <summary>F1 state — the discipline reads this to size its layout (the log takes a side gutter).</summary>
    public bool ShowLog { get; private set; }
    public bool NotesOpen => _notesPanel?.Visible ?? false;
    public bool NotesEditHasFocus => _noteEdit?.HasFocus() ?? false;

    public MinigameDevLog(string discipline)
    {
        _discipline = string.IsNullOrEmpty(discipline) ? "minigame" : discipline;
        _fileName = $"{_discipline}_playtest.log";
    }

    // ---- notes UI (built once into the discipline's play surface) ------------
    /// <summary>Build the hidden [F7] notes box into <paramref name="parent"/>. Call once from BuildUi.</summary>
    public void BuildNotesPanel(Control parent)
    {
        _notesPanel = new PanelContainer { Visible = false, MouseFilter = Control.MouseFilterEnum.Stop };
        _notesPanel.AddThemeStyleboxOverride("panel", UiTheme.Box(new Color(0.04f, 0.04f, 0.06f, 0.96f), Gold, 2, 10));
        _notesPanel.SetAnchorsPreset(Control.LayoutPreset.CenterBottom);
        _notesPanel.OffsetLeft = -360; _notesPanel.OffsetRight = 360; _notesPanel.OffsetTop = -150; _notesPanel.OffsetBottom = -22;
        parent.AddChild(_notesPanel);

        var pad = new MarginContainer();
        foreach (var side in new[] { "left", "right", "top", "bottom" }) pad.AddThemeConstantOverride($"margin_{side}", 14);
        _notesPanel.AddChild(pad);

        var vb = new VBoxContainer(); vb.AddThemeConstantOverride("separation", 8);
        pad.AddChild(vb);

        var hdr = new Label { Text = "PLAYTEST NOTES  —  type & [Enter] to log (interleaved with the event log)  ·  [F7] close" };
        hdr.AddThemeFontSizeOverride("font_size", 13); hdr.AddThemeColorOverride("font_color", Gold);
        vb.AddChild(hdr);

        _noteEdit = new LineEdit
        {
            PlaceholderText = "what you're seeing / feeling right now",
            SizeFlagsHorizontal = Control.SizeFlags.ExpandFill,
        };
        _noteEdit.AddThemeFontSizeOverride("font_size", 15);
        _noteEdit.TextSubmitted += OnSubmit;
        vb.AddChild(_noteEdit);

        _notesHint = new Label { Text = $"notes are saved to res://playtest_logs/{_fileName}", Modulate = new Color(0.6f, 0.85f, 0.6f) };
        _notesHint.AddThemeFontSizeOverride("font_size", 12);
        vb.AddChild(_notesHint);
    }

    private void OnSubmit(string text)
    {
        text = text.Trim();
        if (text.Length == 0) return;
        NoteSubmitted?.Invoke(text);
        _noteEdit?.Clear();
        _noteEdit?.GrabFocus();
    }

    // ---- input routing -------------------------------------------------------
    /// <summary>Route a key press. Returns true if it was an F1/F7 the harness consumed (the discipline should then
    /// call GetViewport().SetInputAsHandled() and redraw). Claim this at the EARLIEST input stage so F1/F7 never
    /// reach the world's global debug handler.</summary>
    public bool HandleKey(Key key)
    {
        if (key == Key.F1) { ShowLog = !ShowLog; return true; }
        if (key == Key.F7) { ToggleNotes(); return true; }
        return false;
    }

    public void ToggleNotes()
    {
        if (_notesPanel == null) return;
        _notesPanel.Visible = !_notesPanel.Visible;
        if (_notesPanel.Visible) _noteEdit?.GrabFocus(); else _noteEdit?.ReleaseFocus();
    }

    // ---- session + logging ---------------------------------------------------
    /// <summary>Open a fresh session in the log file, framed with the discipline's header lines (metadata block).</summary>
    public void BeginSession(IEnumerable<string> headerLines)
    {
        _noteCount = 0; _log.Clear();
        try
        {
            var dir = ProjectSettings.GlobalizePath("res://playtest_logs");
            System.IO.Directory.CreateDirectory(dir);
            _logPath = System.IO.Path.Combine(dir, _fileName);
        }
        catch { _logPath = ""; return; }

        var sb = new StringBuilder();
        sb.Append('\n').Append(new string('=', 72)).Append('\n');
        sb.Append($"= {_discipline.ToUpperInvariant()} PLAYTEST SESSION  {DateTime.Now:yyyy-MM-dd HH:mm:ss}\n");
        if (headerLines != null) foreach (var line in headerLines) sb.Append("= ").Append(line).Append('\n');
        sb.Append("= event line: [wall | <context> ]  message      (NOTE lines are your F7 entries)\n");
        sb.Append(new string('=', 72)).Append('\n');
        Append(sb.ToString());
    }

    /// <summary>Add an event to the rolling on-screen log and the file (bracketed with the discipline context).</summary>
    public void Log(string message)
    {
        _log.Add(message); if (_log.Count > 40) _log.RemoveAt(0);
        Append($"[{DateTime.Now:HH:mm:ss} | {Context?.Invoke() ?? ""}]  {message}\n");
    }

    /// <summary>Write an F7 NOTE: timestamped, then the discipline's rich snapshot (indented), so the dev sees exactly
    /// what state the note describes.</summary>
    public void Note(string note, IEnumerable<string>? snapshotLines = null)
    {
        _noteCount++;
        _log.Add($">> NOTE: {Trim(note, 28)}"); if (_log.Count > 40) _log.RemoveAt(0);
        var sb = new StringBuilder();
        sb.Append($"[{DateTime.Now:HH:mm:ss} | {Context?.Invoke() ?? ""}]  ===== NOTE #{_noteCount}: {note}\n");
        if (snapshotLines != null) foreach (var line in snapshotLines) sb.Append("        ").Append(line).Append('\n');
        Append(sb.ToString());
        if (_notesHint != null) _notesHint.Text = $"logged note #{_noteCount}  →  {_fileName}";
    }

    private void Append(string s)
    { if (_logPath.Length == 0) return; try { System.IO.File.AppendAllText(_logPath, s); } catch { /* dev tool — never let logging break the game */ } }

    // ---- on-screen draw ------------------------------------------------------
    /// <summary>Draw the rolling log panel (only when <see cref="ShowLog"/>). <paramref name="pinned"/> is a
    /// discipline-supplied status block (coloured lines) drawn above the rolling event tail.</summary>
    public void DrawLog(CanvasItem ci, Rect2 rect, Font font, IReadOnlyList<(string Text, Color Col)>? pinned = null)
    {
        CraftFx.RoundRect(ci, rect, new Color(0.03f, 0.03f, 0.04f, 0.82f), new Color(0.4f, 0.4f, 0.4f, 0.5f), 2, 8);
        var x = rect.Position.X + 8; var y = rect.Position.Y + 18;
        ci.DrawString(font, new Vector2(x, y), $"{_discipline.ToUpperInvariant()} LOG  [F1]", HorizontalAlignment.Left, 220, 12, Gold); y += 18;
        if (pinned != null)
            foreach (var (text, col) in pinned) { ci.DrawString(font, new Vector2(x, y), Trim(text, 42), HorizontalAlignment.Left, 240, 11, col); y += 14; }
        y += 6; ci.DrawLine(new Vector2(x, y), new Vector2(x + rect.Size.X - 16, y), new Color(1, 1, 1, 0.12f), 1f); y += 12;
        var maxLines = Math.Max(0, (int)((rect.Position.Y + rect.Size.Y - y) / 13));
        foreach (var line in _log.TakeLast(maxLines)) { ci.DrawString(font, new Vector2(x, y), Trim(line, 34), HorizontalAlignment.Left, 240, 10, Sub); y += 13; }
    }

    private static string Trim(string s, int n) => s.Length <= n ? s : s[..n];
}
