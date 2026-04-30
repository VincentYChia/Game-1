"""Prompt Studio main application — themed Tkinter UI with six panels.

Demo-grade tool for designing and validating every LLM prompt the game
uses. Each LLMSystem entry in :mod:`registry` becomes selectable in the
left tree; the right notebook then exposes:

  Editor    — raw JSON fragment-file editor (Ctrl-S saves).
  Assembly  — input-vars form + live assembled system+user prompt.
  Simulator — fixture / mock / real-LLM run with response panel and
              JSON-parse / schema-shape validation.
  Schema    — output schema description + canonical example.
  Coverage  — health checks: unresolved placeholders, missing fixtures,
              orphaned cross-refs, fragment-file structure.
  About     — quick reference for navigation + WES_VERBOSE / F12 hooks.

Look-and-feel lives in :mod:`tools.prompt_studio.theme`.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

# Project root on path so we can import live game modules.
_PROJECT_DIR = Path(__file__).parent.parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from tools.prompt_studio.registry import (  # noqa: E402
    AssemblerStyle,
    LLMSystem,
    OutputFormat,
    SystemRegistry,
    SystemTier,
)
from tools.prompt_studio.sample_inputs import SampleInput, build_sample  # noqa: E402
from tools.prompt_studio import theme  # noqa: E402
from tools.prompt_studio.theme import (  # noqa: E402
    ACCENT_ERROR,
    ACCENT_PRIMARY,
    ACCENT_SUCCESS,
    ACCENT_WARNING,
    BG_DEEP,
    BG_ELEVATED,
    BG_INPUT,
    BG_SURFACE,
    BORDER_SOFT,
    CODE_COMMENT,
    CODE_HEADING,
    CODE_KEYWORD,
    CODE_STRING,
    CODE_WARN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    apply_theme,
    make_text_widget,
    tier_color,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _read_fragment_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _estimate_tokens(text: str) -> int:
    """Cheap token estimator (chars/4)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


_PLACEHOLDER_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _safe_substitute(template: str, variables: Dict[str, Any]) -> str:
    if not template:
        return ""

    def repl(m: "re.Match[str]") -> str:
        key = m.group(1)
        if key in variables:
            val = variables[key]
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False)
            return str(val)
        return m.group(0)

    return _PLACEHOLDER_RE.sub(repl, template)


def _find_unresolved_placeholders(template: str, variables: Dict[str, Any]) -> List[str]:
    found = _PLACEHOLDER_RE.findall(template or "")
    return sorted({name for name in found if name not in variables})


def _try_get_fixture(task_id: str) -> Optional[str]:
    try:
        from world_system.living_world.infra.llm_fixtures.registry import (
            LLMFixtureRegistry,
        )
        from world_system.living_world.infra import llm_fixtures  # noqa: F401
        from world_system.living_world.infra.llm_fixtures import builtin  # noqa: F401
        registry = LLMFixtureRegistry.get_instance()
        fixture = registry.get(task_id)
        if fixture is None:
            return None
        return getattr(fixture, "canonical_response", None)
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════
# Header banner — runs across the top of the window
# ════════════════════════════════════════════════════════════════════════

class HeaderBanner:
    """Top-of-window banner: title, system count, tier legend."""

    def __init__(self, parent: tk.Widget):
        outer = tk.Frame(parent, bg=BG_DEEP, padx=18, pady=12)
        outer.pack(fill=tk.X, side=tk.TOP)

        # Left column — title stack.
        left = tk.Frame(outer, bg=BG_DEEP)
        left.pack(side=tk.LEFT)

        ttk.Label(
            left, text="Prompt Studio", style="Display.TLabel",
            background=BG_DEEP,
        ).pack(anchor=tk.W)
        ttk.Label(
            left,
            text="Design & validate every LLM prompt in Game-1",
            style="Caption.TLabel",
            background=BG_DEEP,
        ).pack(anchor=tk.W)

        # Right column — tier legend chips + counts.
        right = tk.Frame(outer, bg=BG_DEEP)
        right.pack(side=tk.RIGHT)

        all_systems = SystemRegistry.all()
        ttk.Label(
            right, text=f"{len(all_systems)} LLM tasks",
            style="Heading.TLabel", background=BG_DEEP,
        ).pack(anchor=tk.E)

        chips = tk.Frame(right, bg=BG_DEEP)
        chips.pack(anchor=tk.E, pady=(4, 0))

        grouped = SystemRegistry.grouped_by_tier()
        for tier in (SystemTier.WMS, SystemTier.WNS,
                     SystemTier.WES, SystemTier.NPC):
            count = len(grouped.get(tier, []))
            chip = tk.Label(
                chips,
                text=f"  {tier.name} · {count}  ",
                bg=BG_ELEVATED,
                fg=tier_color(tier.name),
                font=theme.FONTS.body_b,
                bd=0,
                padx=6,
                pady=3,
            )
            chip.pack(side=tk.LEFT, padx=4)


# ════════════════════════════════════════════════════════════════════════
# Browser panel (left)
# ════════════════════════════════════════════════════════════════════════

class BrowserPanel:
    def __init__(self, parent: tk.Widget, on_select):
        self._on_select = on_select
        self._iid_to_id: Dict[str, str] = {}

        wrapper = tk.Frame(parent, bg=BG_SURFACE, padx=10, pady=10)
        wrapper.pack(fill=tk.BOTH, expand=True)

        # Section heading.
        ttk.Label(
            wrapper, text="LLM Systems", style="Heading.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            wrapper,
            text="Filter by id, label, or tier name",
            style="Caption.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        # Filter row.
        filter_row = tk.Frame(wrapper, bg=BG_SURFACE)
        filter_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(filter_row, text="🔎", style="Body.TLabel").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._populate())
        entry = ttk.Entry(filter_row, textvariable=self._filter_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Tree.
        tree_frame = tk.Frame(wrapper, bg=BG_INPUT, highlightthickness=0)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_frame, selectmode="browse", show="tree",
        )
        sb = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview,
        )
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Configure tier color tags (foreground).
        for tier in SystemTier:
            self.tree.tag_configure(
                tier.name, foreground=tier_color(tier.name)
            )
        self.tree.tag_configure(
            "tier_header", foreground=TEXT_SECONDARY,
            font=theme.FONTS.subhead,
        )

        self._populate()

    def _populate(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._iid_to_id.clear()
        flt = self._filter_var.get().lower().strip()

        for tier, systems in SystemRegistry.grouped_by_tier().items():
            visible = [
                s for s in systems
                if not flt or flt in s.id.lower()
                or flt in s.label.lower()
                or flt in tier.name.lower()
            ]
            if not visible:
                continue
            tier_iid = self.tree.insert(
                "", "end",
                text=f"  {tier.value}  ·  {len(visible)}",
                open=True,
                tags=("tier_header",),
            )
            for sys_obj in visible:
                iid = self.tree.insert(
                    tier_iid, "end",
                    text=f"     {sys_obj.label}",
                    tags=(tier.name,),
                )
                self._iid_to_id[iid] = sys_obj.id

    def _on_tree_select(self, event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        sys_id = self._iid_to_id.get(sel[0])
        if sys_id is not None:
            self._on_select(sys_id)


# ════════════════════════════════════════════════════════════════════════
# Panel header — common header inside every right-side tab
# ════════════════════════════════════════════════════════════════════════

class PanelHeader:
    """A consistent header at the top of each right-side panel.

    Shows the selected system's tier-colored badge, label, id, and a
    one-line description. Other panels embed their own action buttons
    on the same row to keep the visual rhythm tight.
    """

    def __init__(self, parent: tk.Widget):
        self._tier_badge = tk.Label(
            parent, text="  ?  ", bg=BG_ELEVATED,
            fg=TEXT_MUTED, font=theme.FONTS.body_b,
            padx=6, pady=2,
        )
        self._title_var = tk.StringVar(value="Select a system from the left")
        self._desc_var = tk.StringVar(value="")
        self._id_var = tk.StringVar(value="")

        outer = tk.Frame(parent, bg=BG_SURFACE)
        outer.pack(fill=tk.X, padx=12, pady=(12, 8))

        # Badge column.
        self._tier_badge = tk.Label(
            outer, text="  —  ", bg=BG_ELEVATED, fg=TEXT_MUTED,
            font=theme.FONTS.body_b, padx=8, pady=4,
        )
        self._tier_badge.pack(side=tk.LEFT, padx=(0, 12))

        # Title + meta column.
        info = tk.Frame(outer, bg=BG_SURFACE)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(info, textvariable=self._title_var,
                  style="Heading.TLabel").pack(anchor=tk.W)
        meta_row = tk.Frame(info, bg=BG_SURFACE)
        meta_row.pack(anchor=tk.W, fill=tk.X, pady=(2, 0))
        ttk.Label(meta_row, textvariable=self._id_var,
                  style="Caption.TLabel").pack(side=tk.LEFT)
        ttk.Label(meta_row, textvariable=self._desc_var,
                  style="Caption.TLabel").pack(side=tk.LEFT, padx=(12, 0))

        # Action area (children of the panel grab .action_frame).
        self.action_frame = tk.Frame(outer, bg=BG_SURFACE)
        self.action_frame.pack(side=tk.RIGHT)

    def show_system(self, system: LLMSystem) -> None:
        self._tier_badge.config(
            text=f"  {system.tier.name}  ",
            fg=tier_color(system.tier.name),
        )
        self._title_var.set(system.label)
        self._id_var.set(f"id: {system.id}")
        self._desc_var.set(f" · {system.description}")


# ════════════════════════════════════════════════════════════════════════
# Editor panel
# ════════════════════════════════════════════════════════════════════════

class EditorPanel:
    def __init__(self, parent: tk.Widget, status_callback):
        self._status = status_callback
        self._current_path: Optional[Path] = None
        self._current_system: Optional[LLMSystem] = None

        outer = tk.Frame(parent, bg=BG_SURFACE)
        outer.pack(fill=tk.BOTH, expand=True)

        # Header row.
        self.header = PanelHeader(outer)
        ttk.Button(
            self.header.action_frame, text="↻  Reload",
            style="Ghost.TButton",
            command=self.reload_from_disk,
        ).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(
            self.header.action_frame, text="💾  Save  (Ctrl-S)",
            style="Primary.TButton",
            command=self.save_to_disk,
        ).pack(side=tk.RIGHT)

        # Path label.
        self._path_var = tk.StringVar(value="")
        ttk.Label(
            outer, textvariable=self._path_var, style="Muted.TLabel",
        ).pack(anchor=tk.W, padx=12, pady=(0, 8))

        # Editor.
        text_container, self.editor = make_text_widget(
            outer, code=True, wrap="none", height=20,
        )
        text_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self.editor.bind("<<Modified>>", self._on_modified)

        # Footer pill row.
        footer = tk.Frame(outer, bg=BG_SURFACE)
        footer.pack(fill=tk.X, padx=12, pady=(0, 12))

        self._tok_var = tk.StringVar(value="0 tokens")
        ttk.Label(
            footer, textvariable=self._tok_var, style="AccentPill.TLabel",
        ).pack(side=tk.LEFT)

        self._dirty_var = tk.StringVar(value="")
        self._dirty_label = ttk.Label(
            footer, textvariable=self._dirty_var, style="WarnPill.TLabel",
        )
        # Don't pack until dirty.

    def show_system(self, system: LLMSystem) -> None:
        self._current_system = system
        self._current_path = system.fragment_path
        self.header.show_system(system)
        self._path_var.set(f"📄  {system.fragment_relpath}")
        self.reload_from_disk()

    def reload_from_disk(self) -> None:
        if self._current_path is None:
            return
        if self._current_path.exists():
            try:
                with open(self._current_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                text = f"// failed to read {self._current_path}: {e}"
        else:
            text = "// (file does not exist on disk)"

        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", text)
        self._tok_var.set(f"~{_estimate_tokens(text)} tokens")
        self.editor.edit_modified(False)
        self._set_dirty(False)

    def save_to_disk(self) -> None:
        if self._current_path is None:
            return
        text = self.editor.get("1.0", tk.END).rstrip("\n") + "\n"
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            messagebox.showerror(
                "Invalid JSON",
                f"Refusing to save — JSON parse error:\n\n{e}",
            )
            return
        try:
            self._current_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._current_path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self._set_dirty(False)
        self._status(f"✓ Saved {self._current_path.name}")

    def _on_modified(self, event=None) -> None:
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        text = self.editor.get("1.0", tk.END)
        self._tok_var.set(f"~{_estimate_tokens(text)} tokens")
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        if dirty:
            self._dirty_var.set("●  unsaved changes")
            if not self._dirty_label.winfo_ismapped():
                self._dirty_label.pack(side=tk.LEFT, padx=8)
        else:
            self._dirty_var.set("")
            if self._dirty_label.winfo_ismapped():
                self._dirty_label.pack_forget()


# ════════════════════════════════════════════════════════════════════════
# Assembly panel
# ════════════════════════════════════════════════════════════════════════

class AssemblyPanel:
    def __init__(self, parent: tk.Widget, status_callback):
        self._status = status_callback
        self._current_system: Optional[LLMSystem] = None
        self._current_sample: Optional[SampleInput] = None

        outer = tk.Frame(parent, bg=BG_SURFACE)
        outer.pack(fill=tk.BOTH, expand=True)

        self.header = PanelHeader(outer)
        ttk.Button(
            self.header.action_frame, text="↻  Resample",
            style="Ghost.TButton",
            command=self.regenerate_sample,
        ).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(
            self.header.action_frame, text="⟳  Reassemble",
            style="Primary.TButton",
            command=self.reassemble,
        ).pack(side=tk.RIGHT)

        # Sample label.
        self._sample_label_var = tk.StringVar(value="")
        ttk.Label(
            outer, textvariable=self._sample_label_var, style="Muted.TLabel",
        ).pack(anchor=tk.W, padx=12, pady=(0, 8))

        # Two-pane: vars (left), prompt preview (right).
        pane = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        # Vars frame.
        vars_frame = tk.Frame(pane, bg=BG_SURFACE)
        pane.add(vars_frame, weight=1)
        ttk.Label(
            vars_frame, text="Input variables", style="Subhead.TLabel",
        ).pack(anchor=tk.W, padx=2, pady=(0, 4))
        vars_container, self._vars_text = make_text_widget(
            vars_frame, code=True, wrap="word", height=20,
        )
        vars_container.pack(fill=tk.BOTH, expand=True)
        # Color tags inside the vars view.
        self._vars_text.tag_configure("k", foreground=ACCENT_PRIMARY)
        self._vars_text.tag_configure("c", foreground=CODE_COMMENT)
        self._vars_text.tag_configure("v", foreground=CODE_STRING)

        # Preview frame.
        preview_frame = tk.Frame(pane, bg=BG_SURFACE)
        pane.add(preview_frame, weight=2)
        ttk.Label(
            preview_frame, text="Assembled prompt", style="Subhead.TLabel",
        ).pack(anchor=tk.W, padx=2, pady=(0, 4))
        preview_container, self._preview = make_text_widget(
            preview_frame, code=True, wrap="word", height=20,
            state=tk.DISABLED,
        )
        preview_container.pack(fill=tk.BOTH, expand=True)
        self._preview.tag_configure(
            "h", foreground=CODE_HEADING, font=theme.FONTS.code_b,
        )
        self._preview.tag_configure(
            "warn", foreground=CODE_WARN, font=theme.FONTS.code_b,
        )
        self._preview.tag_configure("dim", foreground=TEXT_MUTED)
        self._preview.tag_configure("placeholder", foreground=CODE_KEYWORD)

        # Footer.
        footer = tk.Frame(outer, bg=BG_SURFACE)
        footer.pack(fill=tk.X, padx=12, pady=(0, 12))

        self._tok_var = tk.StringVar(value="0 tokens")
        ttk.Label(
            footer, textvariable=self._tok_var, style="AccentPill.TLabel",
        ).pack(side=tk.LEFT)

        self._unresolved_var = tk.StringVar(value="")
        self._unresolved_label = ttk.Label(
            footer, textvariable=self._unresolved_var, style="OkPill.TLabel",
        )
        self._unresolved_label.pack(side=tk.RIGHT)

    def show_system(self, system: LLMSystem) -> None:
        self._current_system = system
        self.header.show_system(system)
        self.regenerate_sample()

    def regenerate_sample(self) -> None:
        if self._current_system is None:
            return
        self._current_sample = build_sample(self._current_system.sample_input_key)
        self._sample_label_var.set(
            f"📦  sample: {self._current_sample.label}    "
            f"(builder: {self._current_system.sample_input_key or '—'})"
        )
        self._render_vars()
        self.reassemble()

    def _render_vars(self) -> None:
        self._vars_text.config(state=tk.NORMAL)
        self._vars_text.delete("1.0", tk.END)
        if self._current_sample is None:
            self._vars_text.config(state=tk.DISABLED)
            return
        if self._current_sample.variables:
            self._vars_text.insert(tk.END, "// ${var} substitutions\n", "c")
            for k, v in self._current_sample.variables.items():
                self._vars_text.insert(tk.END, f"{k}", "k")
                self._vars_text.insert(tk.END, ": ")
                self._vars_text.insert(tk.END, f"{v!r}\n", "v")
        if self._current_sample.tags:
            self._vars_text.insert(tk.END, "\n// WMS-style tags\n", "c")
            for t in self._current_sample.tags:
                self._vars_text.insert(tk.END, f"  • {t}\n")
        if self._current_sample.data_block:
            self._vars_text.insert(tk.END, "\n// data block\n", "c")
            self._vars_text.insert(tk.END, self._current_sample.data_block)
        self._vars_text.config(state=tk.DISABLED)

    def reassemble(self) -> None:
        if self._current_system is None:
            return
        sample = self._current_sample or build_sample(None)
        system = self._current_system

        fragments = _read_fragment_file(system.fragment_path)
        core = fragments.get("_core", {}) if isinstance(fragments, dict) else {}
        out_block = fragments.get("_output", {}) if isinstance(fragments, dict) else {}
        if not isinstance(core, dict):
            core = {}
        if not isinstance(out_block, dict):
            out_block = {}

        sys_template = core.get("system", "")
        usr_template = core.get("user_template", "")

        if system.assembler_style == AssemblerStyle.WES:
            sys_resolved = _safe_substitute(sys_template, sample.variables)
            usr_resolved = _safe_substitute(usr_template, sample.variables)
            unresolved = _find_unresolved_placeholders(
                sys_template + "\n" + usr_template, sample.variables,
            )
        else:
            sys_resolved = sys_template or "(no _core.system in this WMS file)"
            usr_resolved = (
                "// WMS-style: tag-indexed assembly. Selected tags drive\n"
                "// fragment picks at runtime — see Assembler\n\n"
                + (sample.data_block or "(no data block)")
            )
            unresolved = []

        # Render.
        self._preview.config(state=tk.NORMAL)
        self._preview.delete("1.0", tk.END)
        self._preview.insert(tk.END, "═══ SYSTEM\n", "h")
        self._insert_with_placeholder_highlights(sys_resolved)
        self._preview.insert(tk.END, "\n\n")
        self._preview.insert(tk.END, "═══ USER\n", "h")
        self._insert_with_placeholder_highlights(usr_resolved)
        self._preview.insert(tk.END, "\n")

        if out_block:
            self._preview.insert(tk.END, "\n═══ OUTPUT GUIDE\n", "h")
            schema_desc = out_block.get("schema_description", "")
            example = out_block.get("example", "")
            if schema_desc:
                self._preview.insert(tk.END, "schema: ", "dim")
                self._preview.insert(tk.END, str(schema_desc) + "\n")
            if example:
                self._preview.insert(tk.END, "example: ", "dim")
                self._preview.insert(tk.END, str(example) + "\n")
        if unresolved:
            self._preview.insert(tk.END, "\n⚠  UNRESOLVED PLACEHOLDERS\n", "warn")
            for name in unresolved:
                self._preview.insert(tk.END, f"  ${{{name}}}\n", "warn")
        self._preview.config(state=tk.DISABLED)

        total_chars = len(sys_resolved) + len(usr_resolved)
        self._tok_var.set(
            f"~{_estimate_tokens(sys_resolved + usr_resolved)} tokens  "
            f"·  {total_chars:,} chars"
        )

        if unresolved:
            self._unresolved_var.set(f"⚠  {len(unresolved)} unresolved")
            self._unresolved_label.configure(style="ErrorPill.TLabel")
        else:
            self._unresolved_var.set("✓  all vars resolved")
            self._unresolved_label.configure(style="OkPill.TLabel")

    def _insert_with_placeholder_highlights(self, text: str) -> None:
        """Insert text into the preview widget; tint any unresolved
        ``${var}`` tokens so they're easy to spot."""
        if not text:
            return
        last = 0
        for m in _PLACEHOLDER_RE.finditer(text):
            if m.start() > last:
                self._preview.insert(tk.END, text[last : m.start()])
            self._preview.insert(tk.END, m.group(0), "placeholder")
            last = m.end()
        if last < len(text):
            self._preview.insert(tk.END, text[last:])


# ════════════════════════════════════════════════════════════════════════
# Simulator panel
# ════════════════════════════════════════════════════════════════════════

class SimulatorPanel:
    def __init__(self, parent: tk.Widget, status_callback):
        self._status = status_callback
        self._current_system: Optional[LLMSystem] = None
        self._last_response: str = ""

        outer = tk.Frame(parent, bg=BG_SURFACE)
        outer.pack(fill=tk.BOTH, expand=True)

        self.header = PanelHeader(outer)
        ttk.Button(
            self.header.action_frame, text="📋  Copy",
            style="Ghost.TButton",
            command=self.copy_response,
        ).pack(side=tk.RIGHT)

        # Run-mode buttons row.
        bar = tk.Frame(outer, bg=BG_SURFACE)
        bar.pack(fill=tk.X, padx=12, pady=(0, 8))
        ttk.Button(
            bar, text="▶  FIXTURE",
            style="Success.TButton",
            command=self.run_fixture,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            bar, text="▶  MOCK BACKEND",
            style="Primary.TButton",
            command=self.run_mock,
        ).pack(side=tk.LEFT, padx=6)
        ttk.Button(
            bar, text="▶  REAL LLM",
            style="Warning.TButton",
            command=self.run_real,
        ).pack(side=tk.LEFT, padx=6)
        ttk.Label(
            bar, text="(real LLM gated on WES_DISABLE_FIXTURES=1 env)",
            style="Caption.TLabel",
        ).pack(side=tk.LEFT, padx=(12, 0))

        # Status pill.
        self._sim_status_var = tk.StringVar(value="")
        self._sim_status_label = ttk.Label(
            outer, textvariable=self._sim_status_var, style="Muted.TLabel",
        )
        self._sim_status_label.pack(anchor=tk.W, padx=12, pady=(0, 8))

        # Response panel.
        resp_container, self._resp = make_text_widget(
            outer, code=True, wrap="word", height=20, state=tk.DISABLED,
        )
        resp_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

    def show_system(self, system: LLMSystem) -> None:
        self._current_system = system
        self.header.show_system(system)
        self._sim_status_var.set("")
        self._set_response("")

    def _set_response(self, text: str, status: str = "") -> None:
        self._last_response = text
        self._resp.config(state=tk.NORMAL)
        self._resp.delete("1.0", tk.END)
        self._resp.insert(tk.END, text)
        self._resp.config(state=tk.DISABLED)
        if status:
            self._sim_status_var.set(status)

    def _validate_response(self, text: str) -> str:
        if not text or not self._current_system:
            return ""
        if self._current_system.output_format == OutputFormat.JSON:
            try:
                json.loads(text)
                return "✓  valid JSON"
            except json.JSONDecodeError as e:
                return f"⚠  JSON parse error: {e}"
        elif self._current_system.output_format == OutputFormat.XML:
            if "<specs>" in text and "</specs>" in text:
                return "✓  XML <specs> wrapper found"
            return "⚠  no <specs> wrapper found"
        return ""

    def run_fixture(self) -> None:
        if self._current_system is None:
            return
        response = _try_get_fixture(self._current_system.id)
        if response is None:
            self._set_response(
                "(no fixture registered for this task — register one in "
                "world_system/living_world/infra/llm_fixtures/builtin.py "
                "to see a canonical response here)",
                status="⚠  no fixture available",
            )
            return
        check = self._validate_response(response)
        self._set_response(response, status=f"📦  fixture loaded  ·  {check}")

    def run_mock(self) -> None:
        if self._current_system is None:
            return
        try:
            from world_system.living_world.backends.backend_manager import (
                BackendManager,
            )
            from world_system.living_world.infra.llm_fixtures import builtin  # noqa: F401
            mgr = BackendManager.get_instance()
        except Exception as e:
            self._set_response(
                f"(failed to import BackendManager: {e})",
                status="⚠  mock unavailable",
            )
            return

        try:
            response = mgr.generate(
                task=self._current_system.id,
                system_prompt="(prompt assembled in Assembly tab)",
                user_prompt="(user prompt)",
            )
            check = self._validate_response(response or "")
            self._set_response(
                response or "(empty response)",
                status=f"🤖  mock backend  ·  {check}",
            )
        except Exception as e:
            self._set_response(
                f"(mock backend failed: {type(e).__name__}: {e})",
                status="⚠  mock backend error",
            )

    def run_real(self) -> None:
        if self._current_system is None:
            return
        if not os.environ.get("WES_DISABLE_FIXTURES"):
            ans = messagebox.askyesno(
                "Confirm real LLM call",
                "WES_DISABLE_FIXTURES is not set — the BackendManager "
                "will return the canonical fixture instead of calling "
                "the real LLM.\n\n"
                "Set WES_DISABLE_FIXTURES=1 in the environment first to "
                "issue an actual API call.\n\n"
                "Run anyway (will use fixture)?",
            )
            if not ans:
                return
        ans = messagebox.askyesno(
            "Real LLM call",
            f"This may issue a billable LLM call for task "
            f"'{self._current_system.id}'. Proceed?",
        )
        if not ans:
            return
        self.run_mock()

    def copy_response(self) -> None:
        if not self._last_response:
            return
        try:
            self._resp.clipboard_clear()
            self._resp.clipboard_append(self._last_response)
            self._status("✓  Response copied to clipboard")
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════
# Schema panel
# ════════════════════════════════════════════════════════════════════════

class SchemaPanel:
    def __init__(self, parent: tk.Widget):
        self._current_system: Optional[LLMSystem] = None

        outer = tk.Frame(parent, bg=BG_SURFACE)
        outer.pack(fill=tk.BOTH, expand=True)

        self.header = PanelHeader(outer)

        # Output format pill row.
        bar = tk.Frame(outer, bg=BG_SURFACE)
        bar.pack(fill=tk.X, padx=12, pady=(0, 8))
        self._format_var = tk.StringVar(value="")
        ttk.Label(
            bar, textvariable=self._format_var, style="AccentPill.TLabel",
        ).pack(side=tk.LEFT)
        self._parse_var = tk.StringVar(value="")
        self._parse_label = ttk.Label(
            bar, textvariable=self._parse_var, style="OkPill.TLabel",
        )
        self._parse_label.pack(side=tk.RIGHT)

        # Schema vs example pane.
        pane = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        schema_frame = tk.Frame(pane, bg=BG_SURFACE)
        pane.add(schema_frame, weight=1)
        ttk.Label(
            schema_frame, text="Schema description", style="Subhead.TLabel",
        ).pack(anchor=tk.W, padx=2, pady=(0, 4))
        sc, self._schema_text = make_text_widget(
            schema_frame, code=True, wrap="word", height=20,
            state=tk.DISABLED,
        )
        sc.pack(fill=tk.BOTH, expand=True)

        example_frame = tk.Frame(pane, bg=BG_SURFACE)
        pane.add(example_frame, weight=1)
        ttk.Label(
            example_frame, text="Canonical example", style="Subhead.TLabel",
        ).pack(anchor=tk.W, padx=2, pady=(0, 4))
        ec, self._example_text = make_text_widget(
            example_frame, code=True, wrap="word", height=20,
            state=tk.DISABLED,
        )
        ec.pack(fill=tk.BOTH, expand=True)

    def show_system(self, system: LLMSystem) -> None:
        self._current_system = system
        self.header.show_system(system)
        self._format_var.set(
            f"output: {system.output_format.value.upper()}  ·  "
            f"{system.fragment_relpath}"
        )

        fragments = _read_fragment_file(system.fragment_path)
        out_block = fragments.get("_output", {}) if isinstance(fragments, dict) else {}
        if not isinstance(out_block, dict):
            out_block = {}

        schema_desc = out_block.get("schema_description", "")
        example = out_block.get("example", "")

        self._schema_text.config(state=tk.NORMAL)
        self._schema_text.delete("1.0", tk.END)
        self._schema_text.insert(
            tk.END, schema_desc or "(no _output.schema_description in file)"
        )
        self._schema_text.config(state=tk.DISABLED)

        rendered_example = example
        parse_status = ""
        parse_style = "OkPill.TLabel"
        if system.output_format == OutputFormat.JSON and example:
            try:
                rendered_example = json.dumps(json.loads(example), indent=2)
                parse_status = "✓  example parses as valid JSON"
            except json.JSONDecodeError as e:
                parse_status = f"⚠  JSON parse error: {e}"
                parse_style = "ErrorPill.TLabel"
        elif system.output_format == OutputFormat.XML:
            if example and "<specs>" in str(example):
                parse_status = "✓  <specs> wrapper present"
            elif example:
                parse_status = "⚠  no <specs> wrapper"
                parse_style = "WarnPill.TLabel"

        self._parse_var.set(parse_status)
        self._parse_label.configure(style=parse_style)

        self._example_text.config(state=tk.NORMAL)
        self._example_text.delete("1.0", tk.END)
        self._example_text.insert(
            tk.END, str(rendered_example) or "(no _output.example in file)"
        )
        self._example_text.config(state=tk.DISABLED)


# ════════════════════════════════════════════════════════════════════════
# Coverage panel
# ════════════════════════════════════════════════════════════════════════

class CoveragePanel:
    def __init__(self, parent: tk.Widget):
        outer = tk.Frame(parent, bg=BG_SURFACE)
        outer.pack(fill=tk.BOTH, expand=True)

        # Header row.
        head_row = tk.Frame(outer, bg=BG_SURFACE)
        head_row.pack(fill=tk.X, padx=12, pady=(12, 8))
        ttk.Label(
            head_row, text="Coverage Report", style="Heading.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Button(
            head_row, text="↻  Recompute",
            style="Primary.TButton",
            command=self.recompute,
        ).pack(side=tk.RIGHT)

        ttk.Label(
            outer,
            text=("Cross-task health: missing fragments, fixture coverage, "
                  "placeholder leakage, _core/_output structure."),
            style="Caption.TLabel",
        ).pack(anchor=tk.W, padx=12, pady=(0, 8))

        # Stat tiles row.
        self._stats_row = tk.Frame(outer, bg=BG_SURFACE)
        self._stats_row.pack(fill=tk.X, padx=12, pady=(0, 12))

        # Detail report.
        rc, self._report_text = make_text_widget(
            outer, code=True, wrap="word", height=18, state=tk.DISABLED,
        )
        rc.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self._report_text.tag_configure(
            "h", foreground=CODE_HEADING, font=theme.FONTS.code_b,
        )
        self._report_text.tag_configure("ok", foreground=ACCENT_SUCCESS)
        self._report_text.tag_configure("warn", foreground=ACCENT_WARNING)
        self._report_text.tag_configure("err", foreground=ACCENT_ERROR)

        self.recompute()

    def _make_stat_tile(
        self, parent: tk.Widget, label: str, value: str, color: str,
    ) -> tk.Frame:
        tile = tk.Frame(
            parent, bg=BG_ELEVATED, highlightbackground=BORDER_SOFT,
            highlightthickness=1, padx=14, pady=10,
        )
        tk.Label(
            tile, text=value, bg=BG_ELEVATED, fg=color,
            font=theme.FONTS.display,
        ).pack(anchor=tk.W)
        tk.Label(
            tile, text=label, bg=BG_ELEVATED, fg=TEXT_SECONDARY,
            font=theme.FONTS.small,
        ).pack(anchor=tk.W)
        return tile

    def recompute(self) -> None:
        # Compute health stats.
        missing: List[LLMSystem] = []
        no_core: List[LLMSystem] = []
        no_output: List[LLMSystem] = []
        unresolved_total = 0
        for system in SystemRegistry.all():
            if not system.fragment_path.exists():
                missing.append(system)
                continue
            fragments = _read_fragment_file(system.fragment_path)
            core_field = fragments.get("_core")
            output_field = fragments.get("_output")
            if not isinstance(core_field, dict):
                no_core.append(system)
            if (
                not isinstance(output_field, dict)
                and system.assembler_style == AssemblerStyle.WES
            ):
                no_output.append(system)
            sample = build_sample(system.sample_input_key)
            if isinstance(core_field, dict):
                tmpl = (core_field.get("system") or "") + "\n" + (core_field.get("user_template") or "")
                unresolved_total += len(_find_unresolved_placeholders(tmpl, sample.variables))

        fixtures_missing: List[LLMSystem] = []
        for system in SystemRegistry.all():
            if _try_get_fixture(system.id) is None:
                fixtures_missing.append(system)

        total = len(SystemRegistry.all())

        # Refresh stat tiles.
        for child in self._stats_row.winfo_children():
            child.destroy()
        self._make_stat_tile(
            self._stats_row, "TOTAL TASKS", str(total), TEXT_PRIMARY,
        ).pack(side=tk.LEFT, padx=(0, 10))
        self._make_stat_tile(
            self._stats_row,
            "MISSING FRAGMENTS",
            str(len(missing)),
            ACCENT_ERROR if missing else ACCENT_SUCCESS,
        ).pack(side=tk.LEFT, padx=10)
        self._make_stat_tile(
            self._stats_row,
            "MISSING FIXTURES",
            str(len(fixtures_missing)),
            ACCENT_WARNING if fixtures_missing else ACCENT_SUCCESS,
        ).pack(side=tk.LEFT, padx=10)
        self._make_stat_tile(
            self._stats_row,
            "UNRESOLVED PLACEHOLDERS",
            str(unresolved_total),
            ACCENT_WARNING if unresolved_total else ACCENT_SUCCESS,
        ).pack(side=tk.LEFT, padx=10)

        # Refresh detail report.
        self._report_text.config(state=tk.NORMAL)
        self._report_text.delete("1.0", tk.END)

        self._report_text.insert(tk.END, "── Fragment files ──\n", "h")
        if missing:
            self._report_text.insert(
                tk.END,
                f"  ⚠  {len(missing)} systems with missing fragment file\n", "err",
            )
            for s in missing:
                self._report_text.insert(
                    tk.END, f"    • {s.id}: {s.fragment_relpath}\n", "err",
                )
        else:
            self._report_text.insert(
                tk.END, "  ✓  all fragment files present\n", "ok",
            )

        if no_core:
            self._report_text.insert(
                tk.END,
                f"  ⚠  {len(no_core)} fragment files without _core block\n",
                "warn",
            )
            for s in no_core:
                self._report_text.insert(tk.END, f"    • {s.id}\n", "warn")
        if no_output:
            self._report_text.insert(
                tk.END,
                f"  ⚠  {len(no_output)} WES-style files without _output block\n",
                "warn",
            )
            for s in no_output:
                self._report_text.insert(tk.END, f"    • {s.id}\n", "warn")

        self._report_text.insert(tk.END, "\n── Fixture coverage ──\n", "h")
        if fixtures_missing:
            self._report_text.insert(
                tk.END,
                f"  ⚠  {len(fixtures_missing)} systems without registered fixture\n",
                "warn",
            )
            for s in fixtures_missing:
                self._report_text.insert(tk.END, f"    • {s.id}\n", "warn")
        else:
            self._report_text.insert(
                tk.END, "  ✓  every system has a fixture\n", "ok",
            )

        self._report_text.insert(tk.END, "\n── Per-tier breakdown ──\n", "h")
        for tier, systems in SystemRegistry.grouped_by_tier().items():
            self._report_text.insert(
                tk.END, f"  {tier.value}: {len(systems)} systems\n",
            )

        self._report_text.config(state=tk.DISABLED)


# ════════════════════════════════════════════════════════════════════════
# About panel
# ════════════════════════════════════════════════════════════════════════

class AboutPanel:
    def __init__(self, parent: tk.Widget):
        outer = tk.Frame(parent, bg=BG_SURFACE)
        outer.pack(fill=tk.BOTH, expand=True)

        head = tk.Frame(outer, bg=BG_SURFACE)
        head.pack(fill=tk.X, padx=18, pady=(18, 8))
        ttk.Label(
            head, text="Prompt Studio  ·  quick reference",
            style="Heading.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            head,
            text="Centralized tool for designing every LLM prompt the game uses.",
            style="Caption.TLabel",
        ).pack(anchor=tk.W)

        body = (
            "PANELS\n"
            "  Editor      Raw JSON fragment file. Ctrl-S saves; refuses\n"
            "              malformed JSON.\n"
            "  Assembly    Live ${var}-substituted system+user prompt with\n"
            "              unresolved-placeholder warnings.\n"
            "  Simulator   Run with FIXTURE / MOCK / REAL LLM. Real-LLM is\n"
            "              gated on WES_DISABLE_FIXTURES=1 + confirm.\n"
            "              Auto JSON / <specs> XML shape validation.\n"
            "  Schema      _output.schema_description + canonical example,\n"
            "              JSON pretty-printed and parse-checked.\n"
            "  Coverage    Cross-task health: missing fragments, fixtures,\n"
            "              placeholder leakage, structure issues.\n"
            "\n"
            "RUNTIME OBSERVABILITY (related)\n"
            "  WES_VERBOSE=1   in env when running the game prints a tagged\n"
            "                  tail of every WMS→WNS→WES→Registry→Reload event.\n"
            "  F12 in-game     toggles a translucent overlay showing the last\n"
            "                  15 events + counter summary.\n"
            "\n"
            "ADDING A NEW LLM TASK\n"
            "  1. Add the task code to BackendManager's routing table.\n"
            "  2. Drop a fragment file into world_system/config/.\n"
            "  3. Register a fixture in llm_fixtures/builtin.py.\n"
            "  4. Add a row to tools/prompt_studio/registry.py.\n"
            "  5. (Optional) Add a sample-input builder in sample_inputs.py.\n"
        )
        bc, body_widget = make_text_widget(
            outer, code=True, wrap="word", height=20,
        )
        bc.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))
        body_widget.insert("1.0", body)
        body_widget.config(state=tk.DISABLED)


# ════════════════════════════════════════════════════════════════════════
# Main app
# ════════════════════════════════════════════════════════════════════════

class PromptStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Prompt Studio  —  Game-1 LLM design & simulator")
        self.root.geometry("1640x980")
        self.root.minsize(1280, 760)

        # Apply theme before any widgets are constructed.
        apply_theme(root)

        # Header banner.
        HeaderBanner(self.root)

        # Subtle separator under banner.
        ttk.Separator(self.root, orient="horizontal").pack(fill=tk.X)

        # Status bar (bottom).
        self._status_var = tk.StringVar(value="Ready")
        status_bar = tk.Frame(self.root, bg=BG_DEEP)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(
            status_bar, textvariable=self._status_var,
            style="Status.TLabel",
        ).pack(side=tk.LEFT, padx=12, pady=4)

        # Main pane.
        body = tk.Frame(self.root, bg=BG_DEEP)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 4))
        pane = ttk.PanedWindow(body, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)

        # Left: browser.
        left_frame = tk.Frame(pane, bg=BG_SURFACE)
        pane.add(left_frame, weight=1)
        self._browser = BrowserPanel(left_frame, on_select=self._on_select_system)

        # Right: tabbed notebook.
        right_frame = tk.Frame(pane, bg=BG_DEEP)
        pane.add(right_frame, weight=4)
        self._notebook = ttk.Notebook(right_frame)
        self._notebook.pack(fill=tk.BOTH, expand=True)

        # Tabs.
        editor_frame = tk.Frame(self._notebook, bg=BG_SURFACE)
        self._editor = EditorPanel(editor_frame, self.set_status)
        self._notebook.add(editor_frame, text="  Editor  ")

        assembly_frame = tk.Frame(self._notebook, bg=BG_SURFACE)
        self._assembly = AssemblyPanel(assembly_frame, self.set_status)
        self._notebook.add(assembly_frame, text="  Assembly  ")

        sim_frame = tk.Frame(self._notebook, bg=BG_SURFACE)
        self._simulator = SimulatorPanel(sim_frame, self.set_status)
        self._notebook.add(sim_frame, text="  Simulator  ")

        schema_frame = tk.Frame(self._notebook, bg=BG_SURFACE)
        self._schema = SchemaPanel(schema_frame)
        self._notebook.add(schema_frame, text="  Schema  ")

        coverage_frame = tk.Frame(self._notebook, bg=BG_SURFACE)
        self._coverage = CoveragePanel(coverage_frame)
        self._notebook.add(coverage_frame, text="  Coverage  ")

        about_frame = tk.Frame(self._notebook, bg=BG_SURFACE)
        self._about = AboutPanel(about_frame)
        self._notebook.add(about_frame, text="  About  ")

        self.root.bind("<Control-s>", lambda e: self._editor.save_to_disk())

    def _on_select_system(self, system_id: str) -> None:
        system = SystemRegistry.by_id(system_id)
        if system is None:
            return
        self.set_status(f"Selected: {system.label}  ·  {system.id}")
        self._editor.show_system(system)
        self._assembly.show_system(system)
        self._simulator.show_system(system)
        self._schema.show_system(system)

    def set_status(self, msg: str) -> None:
        self._status_var.set(msg)


def main() -> None:
    root = tk.Tk()
    PromptStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
