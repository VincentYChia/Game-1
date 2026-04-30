"""Prompt Studio theme — palette, fonts, and ttk style application.

Dark IDE-style theme for Tk + ttk. Centralized so every panel pulls from
one source of truth. ``apply_theme(root)`` should be called once in
``PromptStudioApp.__init__`` before any widgets are constructed.

Design goals:

- Strong contrast for long-session readability.
- Distinct tier accent colors so designers parse WMS / WNS / WES / NPC
  at a glance.
- Coherent typography hierarchy (display / heading / body / code / small).
- Honest color semantics — green = OK, amber = warn, coral = error.
- Tk widgets and ttk widgets both pick up the look. Where ttk theming
  is too rigid (Treeview row colors, scrollbar troughs), use ``tk.Text``
  + ``tk.Scrollbar`` with explicit color args.

The palette is hand-tuned, not generated. Don't bulk-rotate hues
without checking contrast ratios against the body text color.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from tkinter import ttk
from typing import Tuple


# ── Palette ──────────────────────────────────────────────────────────────

# Surfaces (z-stacked from deepest to most elevated).
BG_DEEP        = "#0E1623"  # window background  # noqa: E221
BG_SURFACE     = "#16213A"  # main panes  # noqa: E221
BG_ELEVATED    = "#1F2D4D"  # cards / fragments  # noqa: E221
BG_INPUT       = "#0A1220"  # text editor / code areas  # noqa: E221
BG_HOVER       = "#2A3A5E"  # buttons hover  # noqa: E221
BG_SELECTED    = "#2F4980"  # selected tree row  # noqa: E221

# Borders / separators.
BORDER_SOFT    = "#283555"  # noqa: E221
BORDER_STRONG  = "#3A4D7A"  # noqa: E221

# Text.
TEXT_PRIMARY   = "#E6EDF7"  # noqa: E221
TEXT_SECONDARY = "#A4B3CC"  # noqa: E221
TEXT_MUTED     = "#6A7B9C"  # noqa: E221
TEXT_INVERSE   = "#0E1623"  # for use on light accent buttons  # noqa: E221

# Accents.
ACCENT_PRIMARY = "#6FB4FF"  # noqa: E221  cyan-blue (default)
ACCENT_SUCCESS = "#7BE49A"  # noqa: E221  spring green
ACCENT_WARNING = "#FFB562"  # noqa: E221  amber
ACCENT_ERROR   = "#FF7A8A"  # noqa: E221  coral

# Tier colors (left-rail rows + filter chips).
TIER_COLOR_WMS = "#7AB8E0"  # cool blue
TIER_COLOR_WNS = "#C490F0"  # lavender
TIER_COLOR_WES = "#FFA763"  # amber
TIER_COLOR_NPC = "#5BD3A8"  # teal

# Code-style highlight tints (for assembled-prompt rendering).
CODE_KEYWORD     = "#FFB562"   # noqa: E221  ${var} placeholders
CODE_STRING      = "#7BE49A"   # noqa: E221  string literal-ish
CODE_COMMENT     = "#6A7B9C"   # noqa: E221  // comments
CODE_HEADING     = "#6FB4FF"   # noqa: E221  ═══ SYSTEM ═══ rules
CODE_WARN        = "#FF7A8A"   # noqa: E221  unresolved placeholders


# ── Typography ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FontStack:
    """Resolved font tuples — populated once on apply_theme."""
    display:  Tuple[str, int, str]   # window header  # noqa: E221
    heading:  Tuple[str, int, str]   # panel headers  # noqa: E221
    subhead:  Tuple[str, int, str]   # tab headings  # noqa: E221
    body:     Tuple[str, int, str]   # default UI text  # noqa: E221
    body_b:   Tuple[str, int, str]   # bold body  # noqa: E221
    code:     Tuple[str, int, str]   # editor / preview  # noqa: E221
    code_b:   Tuple[str, int, str]   # bold code (headings inside text)  # noqa: E221
    small:    Tuple[str, int, str]   # captions, footers  # noqa: E221


def _pick_ui_family() -> str:
    """Choose the best available proportional font. ``tkfont.families()``
    requires a Tk root, so callers must invoke this from inside
    :func:`apply_theme` (which is itself given the root)."""
    try:
        available = set(tkfont.families())
    except RuntimeError:
        return "TkDefaultFont"
    for candidate in ("Segoe UI Variable", "Segoe UI", "SF Pro Text",
                      "Inter", "Helvetica Neue", "Arial"):
        if candidate in available:
            return candidate
    return "TkDefaultFont"


def _pick_code_family() -> str:
    try:
        available = set(tkfont.families())
    except RuntimeError:
        return "TkFixedFont"
    for candidate in ("JetBrains Mono", "Cascadia Code", "Consolas",
                      "Menlo", "DejaVu Sans Mono", "Courier New"):
        if candidate in available:
            return candidate
    return "TkFixedFont"


def _build_fonts() -> FontStack:
    ui = _pick_ui_family()
    code = _pick_code_family()
    return FontStack(
        display=(ui, 16, "bold"),
        heading=(ui, 13, "bold"),
        subhead=(ui, 11, "bold"),
        body=(ui, 10, "normal"),
        body_b=(ui, 10, "bold"),
        code=(code, 11, "normal"),
        code_b=(code, 11, "bold"),
        small=(ui, 9, "normal"),
    )


# ── Apply ────────────────────────────────────────────────────────────────

# Module-level placeholder so other modules can import the symbol before
# ``apply_theme`` runs. Will be re-bound to a real FontStack with
# OS-appropriate families on the first apply_theme call. Until then,
# the tuple values still work as Tk font specs (Tk falls back to system
# defaults when a family is unrecognized).
FONTS: FontStack = FontStack(
    display=("TkDefaultFont", 16, "bold"),
    heading=("TkDefaultFont", 13, "bold"),
    subhead=("TkDefaultFont", 11, "bold"),
    body=("TkDefaultFont", 10, "normal"),
    body_b=("TkDefaultFont", 10, "bold"),
    code=("TkFixedFont", 11, "normal"),
    code_b=("TkFixedFont", 11, "bold"),
    small=("TkDefaultFont", 9, "normal"),
)


def tier_color(tier_name: str) -> str:
    """Map a SystemTier name (``WMS``, ``WNS``, ``WES``, ``NPC``) to its color.

    Accepts the bare 3-letter name OR the full ``SystemTier.WMS`` repr.
    """
    key = tier_name.split(".")[-1].upper()
    return {
        "WMS": TIER_COLOR_WMS,
        "WNS": TIER_COLOR_WNS,
        "WES": TIER_COLOR_WES,
        "NPC": TIER_COLOR_NPC,
    }.get(key, ACCENT_PRIMARY)


def apply_theme(root: tk.Tk) -> FontStack:
    """Configure ttk style + tk option database for the dark theme.

    Returns the resolved :class:`FontStack` (also mutates the module
    ``FONTS`` global so callers can import it directly).
    """
    global FONTS
    FONTS = _build_fonts()

    root.configure(bg=BG_DEEP)
    root.option_add("*Font", FONTS.body)
    root.option_add("*Foreground", TEXT_PRIMARY)
    root.option_add("*Background", BG_SURFACE)
    # Default selectColor + insertBackground so text widgets feel right.
    root.option_add("*selectForeground", TEXT_PRIMARY)
    root.option_add("*selectBackground", BG_SELECTED)
    root.option_add("*insertBackground", TEXT_PRIMARY)

    style = ttk.Style(root)
    # On Windows, the default "vista" theme heavily resists color overrides.
    # Switch to "clam" which respects ttk.Style.configure() much better.
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # ── Frames + label frames ───────────────────────────────────────────
    style.configure("TFrame", background=BG_SURFACE)
    style.configure("Surface.TFrame", background=BG_SURFACE)
    style.configure("Elevated.TFrame", background=BG_ELEVATED)
    style.configure("Deep.TFrame", background=BG_DEEP)

    style.configure(
        "TLabelframe",
        background=BG_SURFACE,
        bordercolor=BORDER_SOFT,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=BG_SURFACE,
        foreground=TEXT_SECONDARY,
        font=FONTS.subhead,
    )
    style.configure(
        "Elevated.TLabelframe",
        background=BG_ELEVATED,
        bordercolor=BORDER_SOFT,
    )
    style.configure(
        "Elevated.TLabelframe.Label",
        background=BG_ELEVATED,
        foreground=TEXT_SECONDARY,
        font=FONTS.subhead,
    )

    # ── Labels ──────────────────────────────────────────────────────────
    style.configure(
        "TLabel",
        background=BG_SURFACE,
        foreground=TEXT_PRIMARY,
        font=FONTS.body,
    )
    style.configure("Display.TLabel", font=FONTS.display, foreground=TEXT_PRIMARY)
    style.configure("Heading.TLabel", font=FONTS.heading, foreground=TEXT_PRIMARY)
    style.configure("Subhead.TLabel", font=FONTS.subhead, foreground=TEXT_PRIMARY)
    style.configure("Body.TLabel", font=FONTS.body, foreground=TEXT_PRIMARY)
    style.configure("Muted.TLabel", font=FONTS.body, foreground=TEXT_MUTED)
    style.configure("Caption.TLabel", font=FONTS.small, foreground=TEXT_MUTED)
    style.configure(
        "Status.TLabel",
        background=BG_DEEP,
        foreground=TEXT_SECONDARY,
        font=FONTS.small,
        padding=(8, 4),
    )

    # Pill-style status badges (padded labels with explicit bg).
    style.configure(
        "OkPill.TLabel",
        background=BG_ELEVATED,
        foreground=ACCENT_SUCCESS,
        font=FONTS.body_b,
        padding=(8, 2),
    )
    style.configure(
        "WarnPill.TLabel",
        background=BG_ELEVATED,
        foreground=ACCENT_WARNING,
        font=FONTS.body_b,
        padding=(8, 2),
    )
    style.configure(
        "ErrorPill.TLabel",
        background=BG_ELEVATED,
        foreground=ACCENT_ERROR,
        font=FONTS.body_b,
        padding=(8, 2),
    )
    style.configure(
        "AccentPill.TLabel",
        background=BG_ELEVATED,
        foreground=ACCENT_PRIMARY,
        font=FONTS.body_b,
        padding=(8, 2),
    )

    # ── Buttons ─────────────────────────────────────────────────────────
    style.configure(
        "TButton",
        background=BG_ELEVATED,
        foreground=TEXT_PRIMARY,
        font=FONTS.body,
        bordercolor=BORDER_STRONG,
        focuscolor=ACCENT_PRIMARY,
        relief="flat",
        padding=(10, 6),
    )
    style.map(
        "TButton",
        background=[("active", BG_HOVER), ("pressed", BG_SELECTED)],
        bordercolor=[("focus", ACCENT_PRIMARY)],
    )

    style.configure(
        "Primary.TButton",
        background=ACCENT_PRIMARY,
        foreground=TEXT_INVERSE,
        font=FONTS.body_b,
    )
    style.map(
        "Primary.TButton",
        background=[("active", "#8BC4FF"), ("pressed", "#5AA0E5")],
    )

    style.configure(
        "Success.TButton",
        background=ACCENT_SUCCESS,
        foreground=TEXT_INVERSE,
        font=FONTS.body_b,
    )
    style.map(
        "Success.TButton",
        background=[("active", "#92ECAC"), ("pressed", "#5DCC7E")],
    )

    style.configure(
        "Warning.TButton",
        background=ACCENT_WARNING,
        foreground=TEXT_INVERSE,
        font=FONTS.body_b,
    )

    style.configure(
        "Ghost.TButton",
        background=BG_SURFACE,
        foreground=TEXT_SECONDARY,
        font=FONTS.body,
        bordercolor=BORDER_SOFT,
    )
    style.map(
        "Ghost.TButton",
        background=[("active", BG_ELEVATED)],
        foreground=[("active", TEXT_PRIMARY)],
    )

    # ── Entry ───────────────────────────────────────────────────────────
    style.configure(
        "TEntry",
        fieldbackground=BG_INPUT,
        background=BG_INPUT,
        foreground=TEXT_PRIMARY,
        bordercolor=BORDER_STRONG,
        insertcolor=TEXT_PRIMARY,
        padding=6,
    )
    style.map(
        "TEntry",
        fieldbackground=[("focus", BG_INPUT)],
        bordercolor=[("focus", ACCENT_PRIMARY)],
    )

    # ── Combobox ────────────────────────────────────────────────────────
    style.configure(
        "TCombobox",
        fieldbackground=BG_INPUT,
        background=BG_ELEVATED,
        foreground=TEXT_PRIMARY,
        arrowcolor=TEXT_SECONDARY,
        bordercolor=BORDER_STRONG,
        padding=4,
    )
    root.option_add("*TCombobox*Listbox.background", BG_ELEVATED)
    root.option_add("*TCombobox*Listbox.foreground", TEXT_PRIMARY)
    root.option_add("*TCombobox*Listbox.selectBackground", BG_SELECTED)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT_PRIMARY)

    # ── Treeview ────────────────────────────────────────────────────────
    style.configure(
        "Treeview",
        background=BG_INPUT,
        fieldbackground=BG_INPUT,
        foreground=TEXT_PRIMARY,
        bordercolor=BORDER_SOFT,
        relief="flat",
        rowheight=26,
        font=FONTS.body,
    )
    style.map(
        "Treeview",
        background=[("selected", BG_SELECTED)],
        foreground=[("selected", TEXT_PRIMARY)],
    )
    style.configure(
        "Treeview.Heading",
        background=BG_ELEVATED,
        foreground=TEXT_SECONDARY,
        font=FONTS.subhead,
        relief="flat",
    )

    # ── Notebook (tabs) ─────────────────────────────────────────────────
    style.configure(
        "TNotebook",
        background=BG_DEEP,
        bordercolor=BORDER_SOFT,
        tabmargins=(4, 6, 4, 0),
    )
    style.configure(
        "TNotebook.Tab",
        background=BG_SURFACE,
        foreground=TEXT_SECONDARY,
        bordercolor=BORDER_SOFT,
        padding=(18, 8),
        font=FONTS.body_b,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", BG_ELEVATED), ("active", BG_HOVER)],
        foreground=[("selected", TEXT_PRIMARY), ("active", TEXT_PRIMARY)],
        bordercolor=[("selected", ACCENT_PRIMARY)],
    )

    # ── PanedWindow ─────────────────────────────────────────────────────
    style.configure("TPanedwindow", background=BG_DEEP)

    # ── Scrollbar (clam respects these) ─────────────────────────────────
    style.configure(
        "Vertical.TScrollbar",
        background=BG_ELEVATED,
        troughcolor=BG_DEEP,
        bordercolor=BG_DEEP,
        arrowcolor=TEXT_SECONDARY,
        gripcount=0,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", BG_HOVER)],
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=BG_ELEVATED,
        troughcolor=BG_DEEP,
        bordercolor=BG_DEEP,
        arrowcolor=TEXT_SECONDARY,
        gripcount=0,
    )

    # ── Separator ───────────────────────────────────────────────────────
    style.configure("TSeparator", background=BORDER_SOFT)

    return FONTS


# ── Themed Text widget helpers ──────────────────────────────────────────

def make_text_widget(
    parent: tk.Widget,
    *,
    code: bool = True,
    wrap: str = "word",
    height: int = 10,
    state: str = "normal",
) -> Tuple[tk.Frame, tk.Text]:
    """Build a themed Text widget (with custom Scrollbar) inside a Frame.

    Returns ``(container_frame, text_widget)``. Pack the container into
    your parent. We deliberately use ``tk.Text`` instead of
    :class:`scrolledtext.ScrolledText` because the latter doesn't
    respect our color args on Windows.
    """
    font = FONTS.code if code else FONTS.body
    container = tk.Frame(parent, bg=BG_INPUT, bd=1, highlightthickness=0)
    text = tk.Text(
        container,
        font=font,
        wrap=wrap,
        bg=BG_INPUT,
        fg=TEXT_PRIMARY,
        insertbackground=TEXT_PRIMARY,
        selectbackground=BG_SELECTED,
        selectforeground=TEXT_PRIMARY,
        relief="flat",
        bd=0,
        padx=12,
        pady=10,
        height=height,
        state=state,
        undo=True,
    )
    sb = ttk.Scrollbar(container, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=sb.set)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    return container, text


__all__ = [
    "apply_theme",
    "tier_color",
    "make_text_widget",
    "FONTS",
    "FontStack",
    # Palette
    "BG_DEEP", "BG_SURFACE", "BG_ELEVATED", "BG_INPUT",
    "BG_HOVER", "BG_SELECTED",
    "BORDER_SOFT", "BORDER_STRONG",
    "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED", "TEXT_INVERSE",
    "ACCENT_PRIMARY", "ACCENT_SUCCESS", "ACCENT_WARNING", "ACCENT_ERROR",
    "TIER_COLOR_WMS", "TIER_COLOR_WNS", "TIER_COLOR_WES", "TIER_COLOR_NPC",
    "CODE_KEYWORD", "CODE_STRING", "CODE_COMMENT",
    "CODE_HEADING", "CODE_WARN",
]
