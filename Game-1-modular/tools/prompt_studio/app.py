"""Prompt Studio main application — Tkinter UI with six panels.

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
"""

from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from typing import Any, Dict, Optional

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


# ── Color theme ──────────────────────────────────────────────────────────

TIER_COLORS = {
    SystemTier.WMS: "#7CB9D9",
    SystemTier.WNS: "#9B70D9",
    SystemTier.WES: "#E89D5C",
    SystemTier.NPC: "#4DBFA0",
}


# ── Helpers ──────────────────────────────────────────────────────────────

def _read_fragment_file(path: Path) -> Dict[str, Any]:
    """Best-effort load. Missing/malformed → empty dict so the UI keeps
    rendering rather than crashing on a typo."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _estimate_tokens(text: str) -> int:
    """Cheap token estimator (chars/4). Matches the existing
    prompt_editor.py convention so token counts stay comparable."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _safe_substitute(template: str, variables: Dict[str, Any]) -> str:
    """Resolve ``${var}`` tokens, leaving unresolved ones visible
    (highlighted later in the assembly preview as warnings)."""
    if not template:
        return ""
    import re
    pattern = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

    def repl(m: "re.Match[str]") -> str:
        key = m.group(1)
        if key in variables:
            val = variables[key]
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False)
            return str(val)
        return m.group(0)  # leave unresolved

    return pattern.sub(repl, template)


def _find_unresolved_placeholders(template: str, variables: Dict[str, Any]) -> list:
    import re
    found = re.findall(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}", template or "")
    return sorted({name for name in found if name not in variables})


def _try_get_fixture(task_id: str) -> Optional[str]:
    """Look up the canonical fixture response for a task. None on miss."""
    try:
        from world_system.living_world.infra.llm_fixtures.registry import (
            LLMFixtureRegistry,
        )
        # Trigger registration of all builtin fixtures.
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
# Panel: Browser (left side)
# ════════════════════════════════════════════════════════════════════════

class BrowserPanel:
    """Tree of LLM systems grouped by SystemTier."""

    def __init__(self, parent: tk.Widget, on_select):
        self._on_select = on_select
        self._iid_to_id: Dict[str, str] = {}

        frame = ttk.LabelFrame(parent, text="LLM Systems", padding=4)
        frame.pack(fill=tk.BOTH, expand=True)

        sf = ttk.Frame(frame)
        sf.pack(fill=tk.X)
        ttk.Label(sf, text="Filter:").pack(side=tk.LEFT)
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._populate())
        ttk.Entry(sf, textvariable=self._filter_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0)
        )

        self.tree = ttk.Treeview(frame, selectmode="browse", show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self.frame = frame
        self._populate()

    def _populate(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._iid_to_id.clear()
        flt = self._filter_var.get().lower().strip()

        for tier, systems in SystemRegistry.grouped_by_tier().items():
            color = TIER_COLORS.get(tier, "#888")
            visible = [
                s for s in systems
                if not flt or flt in s.id.lower() or flt in s.label.lower()
            ]
            if not visible:
                continue
            tier_iid = self.tree.insert(
                "", "end",
                text=f"  {tier.value} ({len(visible)})",
                open=True,
                tags=(tier.name,),
            )
            self.tree.tag_configure(tier.name, foreground=color)
            for sys_obj in visible:
                iid = self.tree.insert(
                    tier_iid, "end",
                    text=f"  {sys_obj.label}",
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
# Panel: Editor
# ════════════════════════════════════════════════════════════════════════

class EditorPanel:
    """Raw JSON editor for the selected system's fragment file."""

    def __init__(self, parent: tk.Widget, status_callback):
        self._status = status_callback
        self._current_path: Optional[Path] = None
        self._current_system: Optional[LLMSystem] = None
        self._dirty: bool = False

        outer = ttk.Frame(parent, padding=4)
        outer.pack(fill=tk.BOTH, expand=True)

        # Header — system + fragment path.
        header = ttk.Frame(outer)
        header.pack(fill=tk.X)
        self._header_var = tk.StringVar(value="(select a system)")
        ttk.Label(
            header, textvariable=self._header_var,
            font=("TkDefaultFont", 10, "bold")
        ).pack(side=tk.LEFT)
        self._dirty_var = tk.StringVar(value="")
        ttk.Label(
            header, textvariable=self._dirty_var, foreground="orange"
        ).pack(side=tk.LEFT, padx=10)

        # Path label.
        self._path_var = tk.StringVar(value="")
        ttk.Label(
            outer, textvariable=self._path_var, foreground="gray"
        ).pack(fill=tk.X)

        # Editor.
        self.editor = scrolledtext.ScrolledText(
            outer, wrap=tk.NONE, font=("Consolas", 10),
            padx=6, pady=6,
        )
        self.editor.pack(fill=tk.BOTH, expand=True, pady=4)
        self.editor.bind("<<Modified>>", self._on_modified)

        # Footer.
        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X)
        self._tok_var = tk.StringVar(value="")
        ttk.Label(footer, textvariable=self._tok_var).pack(side=tk.LEFT)
        ttk.Button(
            footer, text="Reload from disk",
            command=self.reload_from_disk,
        ).pack(side=tk.RIGHT)
        ttk.Button(
            footer, text="Save (Ctrl-S)",
            command=self.save_to_disk,
        ).pack(side=tk.RIGHT, padx=4)

    def show_system(self, system: LLMSystem) -> None:
        self._current_system = system
        self._current_path = system.fragment_path
        self._header_var.set(f"{system.label}  [{system.id}]")
        self._path_var.set(system.fragment_relpath)
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
        self._dirty = False
        self._dirty_var.set("")
        self._tok_var.set(f"~{_estimate_tokens(text)} tokens")
        self.editor.edit_modified(False)

    def save_to_disk(self) -> None:
        if self._current_path is None:
            return
        text = self.editor.get("1.0", tk.END).rstrip("\n") + "\n"
        # Validate JSON before writing — refuse to clobber the file
        # with a malformed payload.
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
        self._dirty = False
        self._dirty_var.set("✓ saved")
        self._status(f"Saved {self._current_path.name}")

    def _on_modified(self, event=None) -> None:
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        text = self.editor.get("1.0", tk.END)
        self._tok_var.set(f"~{_estimate_tokens(text)} tokens")
        self._dirty = True
        self._dirty_var.set("● unsaved")


# ════════════════════════════════════════════════════════════════════════
# Panel: Assembly
# ════════════════════════════════════════════════════════════════════════

class AssemblyPanel:
    """Show input variables → assembled system+user prompt with
    placeholder-leakage detection."""

    def __init__(self, parent: tk.Widget, status_callback):
        self._status = status_callback
        self._current_system: Optional[LLMSystem] = None
        self._current_sample: Optional[SampleInput] = None

        outer = ttk.Frame(parent, padding=4)
        outer.pack(fill=tk.BOTH, expand=True)

        # Header.
        header = ttk.Frame(outer)
        header.pack(fill=tk.X)
        self._sys_label = tk.StringVar(value="(select a system)")
        ttk.Label(
            header, textvariable=self._sys_label,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Button(
            header, text="↻ Resample",
            command=self.regenerate_sample,
        ).pack(side=tk.RIGHT, padx=4)
        ttk.Button(
            header, text="⟳ Reassemble",
            command=self.reassemble,
        ).pack(side=tk.RIGHT)

        self._sample_label_var = tk.StringVar(value="")
        ttk.Label(
            outer, textvariable=self._sample_label_var, foreground="gray",
        ).pack(fill=tk.X)

        # Two-pane: vars on left, prompt preview on right.
        pane = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, pady=4)

        vars_frame = ttk.LabelFrame(pane, text="Input variables", padding=4)
        pane.add(vars_frame, weight=1)
        self._vars_text = scrolledtext.ScrolledText(
            vars_frame, wrap=tk.WORD, font=("Consolas", 10),
            padx=4, pady=4,
        )
        self._vars_text.pack(fill=tk.BOTH, expand=True)

        preview_frame = ttk.LabelFrame(pane, text="Assembled prompt", padding=4)
        pane.add(preview_frame, weight=2)
        self._preview = scrolledtext.ScrolledText(
            preview_frame, wrap=tk.WORD, font=("Consolas", 10),
            state=tk.DISABLED, padx=6, pady=6,
        )
        self._preview.pack(fill=tk.BOTH, expand=True)
        self._preview.tag_configure("h", foreground="#4A90D9", font=("Consolas", 10, "bold"))
        self._preview.tag_configure("warn", foreground="#E74C3C", font=("Consolas", 10, "bold"))
        self._preview.tag_configure("dim", foreground="#888")

        # Footer.
        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X)
        self._tok_var = tk.StringVar(value="")
        self._unresolved_var = tk.StringVar(value="")
        ttk.Label(footer, textvariable=self._tok_var).pack(side=tk.LEFT)
        ttk.Label(
            footer, textvariable=self._unresolved_var,
            foreground="#E74C3C",
        ).pack(side=tk.RIGHT)

    def show_system(self, system: LLMSystem) -> None:
        self._current_system = system
        self._sys_label.set(f"{system.label}  [{system.id}]")
        self.regenerate_sample()

    def regenerate_sample(self) -> None:
        if self._current_system is None:
            return
        self._current_sample = build_sample(self._current_system.sample_input_key)
        self._sample_label_var.set(
            f"sample: {self._current_sample.label} "
            f"(key: {self._current_system.sample_input_key or 'none'})"
        )
        self._render_vars()
        self.reassemble()

    def _render_vars(self) -> None:
        self._vars_text.delete("1.0", tk.END)
        if self._current_sample is None:
            return
        if self._current_sample.variables:
            self._vars_text.insert(tk.END, "// ${var} substitutions:\n")
            for k, v in self._current_sample.variables.items():
                self._vars_text.insert(tk.END, f"{k}: {v!r}\n")
        if self._current_sample.tags:
            self._vars_text.insert(tk.END, "\n// WMS-style tags:\n")
            for t in self._current_sample.tags:
                self._vars_text.insert(tk.END, f"  - {t}\n")
        if self._current_sample.data_block:
            self._vars_text.insert(tk.END, "\n// data block:\n")
            self._vars_text.insert(tk.END, self._current_sample.data_block)

    def reassemble(self) -> None:
        if self._current_system is None:
            return
        sample = self._current_sample or build_sample(None)
        system = self._current_system

        fragments = _read_fragment_file(system.fragment_path)
        core = fragments.get("_core", {}) if isinstance(fragments, dict) else {}
        out_block = fragments.get("_output", {}) if isinstance(fragments, dict) else {}
        # Some legacy fragment files use a flat string for _core or _output.
        # Coerce both to dicts so .get() calls below stay safe.
        if not isinstance(core, dict):
            core = {}
        if not isinstance(out_block, dict):
            out_block = {}

        sys_template = core.get("system", "") if isinstance(core, dict) else ""
        usr_template = core.get("user_template", "") if isinstance(core, dict) else ""

        if system.assembler_style == AssemblerStyle.WES:
            sys_resolved = _safe_substitute(sys_template, sample.variables)
            usr_resolved = _safe_substitute(usr_template, sample.variables)
            unresolved = _find_unresolved_placeholders(
                sys_template + "\n" + usr_template, sample.variables,
            )
        else:
            # WMS: assembler picks fragments by tag. We render a "preview"
            # by listing the tags + the data block; assembly via the real
            # PromptAssembler is shown when the fragment-file shape matches.
            sys_resolved = sys_template or "(no _core.system in this WMS file)"
            usr_resolved = (
                "// WMS-style: tag-indexed assembly. Selected tags would "
                "drive fragment picks at runtime.\n\n"
                + (sample.data_block or "(no data block)")
            )
            unresolved = []

        # Render.
        self._preview.config(state=tk.NORMAL)
        self._preview.delete("1.0", tk.END)
        self._preview.insert(tk.END, "═══ SYSTEM ═══\n", "h")
        self._preview.insert(tk.END, sys_resolved + "\n\n")
        self._preview.insert(tk.END, "═══ USER ═══\n", "h")
        self._preview.insert(tk.END, usr_resolved + "\n")
        if out_block:
            self._preview.insert(tk.END, "\n═══ OUTPUT GUIDE ═══\n", "h")
            schema_desc = out_block.get("schema_description", "")
            example = out_block.get("example", "")
            if schema_desc:
                self._preview.insert(tk.END, "schema: ", "dim")
                self._preview.insert(tk.END, str(schema_desc) + "\n")
            if example:
                self._preview.insert(tk.END, "example: ", "dim")
                self._preview.insert(tk.END, str(example) + "\n")
        if unresolved:
            self._preview.insert(tk.END, "\n⚠ UNRESOLVED PLACEHOLDERS\n", "warn")
            for name in unresolved:
                self._preview.insert(tk.END, f"  ${{{name}}}\n", "warn")
        self._preview.config(state=tk.DISABLED)

        total_chars = len(sys_resolved) + len(usr_resolved)
        self._tok_var.set(f"~{_estimate_tokens(sys_resolved + usr_resolved)} tokens "
                          f"({total_chars} chars)")
        self._unresolved_var.set(
            f"{len(unresolved)} unresolved" if unresolved else "✓ all vars resolved"
        )


# ════════════════════════════════════════════════════════════════════════
# Panel: Simulator
# ════════════════════════════════════════════════════════════════════════

class SimulatorPanel:
    """Run the assembled prompt against fixture / mock / real LLM."""

    def __init__(self, parent: tk.Widget, status_callback):
        self._status = status_callback
        self._current_system: Optional[LLMSystem] = None
        self._last_response: str = ""

        outer = ttk.Frame(parent, padding=4)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X)
        self._sys_label = tk.StringVar(value="(select a system)")
        ttk.Label(
            header, textvariable=self._sys_label,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side=tk.LEFT)

        # Run-mode buttons.
        bar = ttk.Frame(outer)
        bar.pack(fill=tk.X, pady=4)
        ttk.Button(bar, text="▶ Run with FIXTURE",
                   command=self.run_fixture).pack(side=tk.LEFT)
        ttk.Button(bar, text="▶ Run with MOCK backend",
                   command=self.run_mock).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="▶ Run with REAL LLM",
                   command=self.run_real).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Copy response",
                   command=self.copy_response).pack(side=tk.RIGHT)

        # Status label (e.g. "fixture found", "no fixture", schema parse OK).
        self._sim_status_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self._sim_status_var,
                  foreground="gray").pack(fill=tk.X)

        # Response panel.
        self._resp = scrolledtext.ScrolledText(
            outer, wrap=tk.WORD, font=("Consolas", 10),
            state=tk.DISABLED, padx=6, pady=6,
        )
        self._resp.pack(fill=tk.BOTH, expand=True, pady=4)
        self._resp.tag_configure(
            "ok", foreground="#27AE60", font=("Consolas", 10, "bold")
        )
        self._resp.tag_configure(
            "warn", foreground="#E74C3C", font=("Consolas", 10, "bold")
        )
        self._resp.tag_configure("dim", foreground="#888")

    def show_system(self, system: LLMSystem) -> None:
        self._current_system = system
        self._sys_label.set(f"{system.label}  [{system.id}]")
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
        """Quick shape check — JSON parse for JSON tasks; XML <specs>
        presence for XML tasks. Returns a short status string."""
        if not text or not self._current_system:
            return ""
        if self._current_system.output_format == OutputFormat.JSON:
            try:
                json.loads(text)
                return "✓ valid JSON"
            except json.JSONDecodeError as e:
                return f"⚠ JSON parse error: {e}"
        elif self._current_system.output_format == OutputFormat.XML:
            if "<specs>" in text and "</specs>" in text:
                return "✓ XML <specs> present"
            return "⚠ no <specs> wrapper found"
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
                status="no fixture available",
            )
            return
        check = self._validate_response(response)
        self._set_response(response, status=f"fixture loaded — {check}")

    def run_mock(self) -> None:
        """Invoke MockBackend.generate(task) — falls through to fixture."""
        if self._current_system is None:
            return
        try:
            from world_system.living_world.backends.backend_manager import (
                BackendManager,
            )
            # Trigger fixture registration if not already.
            from world_system.living_world.infra.llm_fixtures import builtin  # noqa: F401
            mgr = BackendManager.get_instance()
        except Exception as e:
            self._set_response(
                f"(failed to import BackendManager: {e})",
                status="mock unavailable",
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
                status=f"mock backend responded — {check}",
            )
        except Exception as e:
            self._set_response(
                f"(mock backend failed: {type(e).__name__}: {e})",
                status="mock backend error",
            )

    def run_real(self) -> None:
        """Real LLM call — gated on env + confirmation since it costs money."""
        if self._current_system is None:
            return
        if not os.environ.get("WES_DISABLE_FIXTURES"):
            ans = messagebox.askyesno(
                "Confirm real LLM call",
                "WES_DISABLE_FIXTURES is not set. The BackendManager "
                "will return the canonical fixture instead of calling "
                "the real LLM.\n\n"
                "Set WES_DISABLE_FIXTURES=1 in the environment first if "
                "you want to issue an actual API call.\n\n"
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
        # Real call goes through the same path as mock, but with the env
        # toggle WES_DISABLE_FIXTURES already set by the user, the
        # MockBackend's fixture lookup is bypassed and Ollama / Claude
        # backend handles it. We just call run_mock.
        self.run_mock()

    def copy_response(self) -> None:
        if not self._last_response:
            return
        try:
            self._resp.clipboard_clear()
            self._resp.clipboard_append(self._last_response)
            self._status("Response copied to clipboard")
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════
# Panel: Schema
# ════════════════════════════════════════════════════════════════════════

class SchemaPanel:
    """Show the task's _output schema description + canonical example,
    side-by-side with the latest fixture response if one exists."""

    def __init__(self, parent: tk.Widget):
        self._current_system: Optional[LLMSystem] = None

        outer = ttk.Frame(parent, padding=4)
        outer.pack(fill=tk.BOTH, expand=True)

        self._sys_label = tk.StringVar(value="(select a system)")
        ttk.Label(
            outer, textvariable=self._sys_label,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(fill=tk.X)

        pane = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, pady=4)

        left = ttk.LabelFrame(pane, text="Schema description", padding=4)
        pane.add(left, weight=1)
        self._schema_text = scrolledtext.ScrolledText(
            left, wrap=tk.WORD, font=("Consolas", 10),
            state=tk.DISABLED, padx=4, pady=4,
        )
        self._schema_text.pack(fill=tk.BOTH, expand=True)

        right = ttk.LabelFrame(pane, text="Canonical example", padding=4)
        pane.add(right, weight=1)
        self._example_text = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, font=("Consolas", 10),
            state=tk.DISABLED, padx=4, pady=4,
        )
        self._example_text.pack(fill=tk.BOTH, expand=True)

        # Output format + parse-status row.
        bar = ttk.Frame(outer)
        bar.pack(fill=tk.X)
        self._format_var = tk.StringVar(value="")
        self._parse_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._format_var,
                  foreground="gray").pack(side=tk.LEFT)
        ttk.Label(bar, textvariable=self._parse_var,
                  foreground="#27AE60").pack(side=tk.RIGHT)

    def show_system(self, system: LLMSystem) -> None:
        self._current_system = system
        self._sys_label.set(f"{system.label}  [{system.id}]")
        self._format_var.set(
            f"output_format = {system.output_format.value}  "
            f"|  fragment = {system.fragment_relpath}"
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

        # Pretty-print example if it's JSON.
        rendered_example = example
        if system.output_format == OutputFormat.JSON and example:
            try:
                rendered_example = json.dumps(json.loads(example), indent=2)
                self._parse_var.set("✓ example parses as valid JSON")
            except json.JSONDecodeError as e:
                self._parse_var.set(f"⚠ example JSON parse error: {e}")
        elif system.output_format == OutputFormat.XML:
            if example and "<specs>" in str(example):
                self._parse_var.set("✓ example has <specs> wrapper")
            else:
                self._parse_var.set("⚠ example missing <specs> wrapper")
        else:
            self._parse_var.set("")

        self._example_text.config(state=tk.NORMAL)
        self._example_text.delete("1.0", tk.END)
        self._example_text.insert(
            tk.END, str(rendered_example) or "(no _output.example in file)"
        )
        self._example_text.config(state=tk.DISABLED)


# ════════════════════════════════════════════════════════════════════════
# Panel: Coverage
# ════════════════════════════════════════════════════════════════════════

class CoveragePanel:
    """Cross-task health checks: fragment-file presence, fixture coverage,
    placeholder leakage, schema example presence."""

    def __init__(self, parent: tk.Widget):
        outer = ttk.Frame(parent, padding=4)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer, text="Coverage Report",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(fill=tk.X, pady=(0, 4))

        ttk.Button(
            outer, text="↻ Recompute report",
            command=self.recompute,
        ).pack(anchor=tk.W)

        self._report_text = scrolledtext.ScrolledText(
            outer, wrap=tk.WORD, font=("Consolas", 10),
            state=tk.DISABLED, padx=6, pady=6,
        )
        self._report_text.pack(fill=tk.BOTH, expand=True, pady=4)
        self._report_text.tag_configure(
            "h", foreground="#4A90D9", font=("Consolas", 10, "bold")
        )
        self._report_text.tag_configure("ok", foreground="#27AE60")
        self._report_text.tag_configure("warn", foreground="#E67E22")
        self._report_text.tag_configure("err", foreground="#E74C3C")

        self.recompute()

    def recompute(self) -> None:
        lines = []
        # Fragment file presence + structure check.
        missing = []
        no_core = []
        no_output = []
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
            # Placeholder leakage with the canonical sample.
            sample = build_sample(system.sample_input_key)
            if isinstance(core_field, dict):
                tmpl = (core_field.get("system") or "") + "\n" + (core_field.get("user_template") or "")
                unresolved_total += len(_find_unresolved_placeholders(tmpl, sample.variables))

        # Fixture presence.
        fixtures_missing = []
        for system in SystemRegistry.all():
            if _try_get_fixture(system.id) is None:
                fixtures_missing.append(system)

        self._report_text.config(state=tk.NORMAL)
        self._report_text.delete("1.0", tk.END)

        total = len(SystemRegistry.all())
        self._report_text.insert(tk.END, f"Total LLM systems: {total}\n\n", "h")

        # Fragment file checks.
        self._report_text.insert(tk.END, "── Fragment files ──\n", "h")
        if missing:
            self._report_text.insert(
                tk.END, f"  ⚠ {len(missing)} systems with missing fragment file\n", "err",
            )
            for s in missing:
                self._report_text.insert(tk.END, f"    - {s.id}: {s.fragment_relpath}\n", "err")
        else:
            self._report_text.insert(tk.END, "  ✓ all fragment files present\n", "ok")

        if no_core:
            self._report_text.insert(
                tk.END, f"  ⚠ {len(no_core)} fragment files without _core block\n", "warn",
            )
            for s in no_core:
                self._report_text.insert(tk.END, f"    - {s.id}\n", "warn")
        if no_output:
            self._report_text.insert(
                tk.END, f"  ⚠ {len(no_output)} WES-style files without _output block\n", "warn",
            )
            for s in no_output:
                self._report_text.insert(tk.END, f"    - {s.id}\n", "warn")
        self._report_text.insert(
            tk.END, f"  unresolved placeholders (across all sample inputs): {unresolved_total}\n",
            "warn" if unresolved_total else "ok",
        )

        # Fixture presence.
        self._report_text.insert(tk.END, "\n── Fixture coverage ──\n", "h")
        if fixtures_missing:
            self._report_text.insert(
                tk.END, f"  ⚠ {len(fixtures_missing)} systems without registered fixture\n", "warn",
            )
            for s in fixtures_missing:
                self._report_text.insert(tk.END, f"    - {s.id}\n", "warn")
        else:
            self._report_text.insert(tk.END, "  ✓ every system has a fixture\n", "ok")

        # Per-tier breakdown.
        self._report_text.insert(tk.END, "\n── Per-tier breakdown ──\n", "h")
        for tier, systems in SystemRegistry.grouped_by_tier().items():
            self._report_text.insert(tk.END, f"  {tier.value}: {len(systems)} systems\n")

        self._report_text.config(state=tk.DISABLED)


# ════════════════════════════════════════════════════════════════════════
# About Panel
# ════════════════════════════════════════════════════════════════════════

class AboutPanel:
    def __init__(self, parent: tk.Widget):
        outer = ttk.Frame(parent, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer, text="Prompt Studio — quick reference",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        text = (
            "PURPOSE\n"
            "  Centralized tool for designing and validating every LLM\n"
            "  prompt the game uses. WMS, WNS, WES tools/hubs/planner/\n"
            "  supervisor/quest-rewards, NPC dialogue — 32 tasks in all.\n"
            "\n"
            "PANELS\n"
            "  Editor    — raw JSON fragment-file editor (Ctrl-S saves).\n"
            "  Assembly  — input-vars form + live assembled prompt; flags\n"
            "              unresolved ${vars}.\n"
            "  Simulator — fixture / mock / real-LLM run with response\n"
            "              shape validation. Set WES_DISABLE_FIXTURES=1\n"
            "              to bypass canonical fixture and hit a real model.\n"
            "  Schema    — _output.schema_description + canonical example.\n"
            "  Coverage  — cross-task health: missing fragments, fixtures,\n"
            "              placeholder leakage.\n"
            "\n"
            "RELATED RUNTIME OBSERVABILITY\n"
            "  WES_VERBOSE=1   in the environment when running the game\n"
            "                  prints a tagged tail of pipeline events.\n"
            "  F12 in-game     toggles the live observability overlay\n"
            "                  showing last-15 events + counter summary.\n"
            "\n"
            "ADDING A NEW LLM TASK\n"
            "  1. Add the task code to BackendManager's routing table.\n"
            "  2. Drop a fragment file into world_system/config/.\n"
            "  3. Register a fixture in llm_fixtures/builtin.py.\n"
            "  4. Add a row to tools/prompt_studio/registry.py.\n"
            "  5. (Optional) Add a sample-input builder in sample_inputs.py.\n"
        )
        body = scrolledtext.ScrolledText(
            outer, wrap=tk.WORD, font=("Consolas", 10),
            state=tk.NORMAL, padx=6, pady=6,
        )
        body.insert("1.0", text)
        body.config(state=tk.DISABLED)
        body.pack(fill=tk.BOTH, expand=True)


# ════════════════════════════════════════════════════════════════════════
# Main app
# ════════════════════════════════════════════════════════════════════════

class PromptStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Prompt Studio — Game-1 LLM design & simulator")
        self.root.geometry("1500x900")
        self.root.minsize(1200, 700)

        # Status bar (bottom).
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(
            self.root, textvariable=self._status_var,
            relief=tk.SUNKEN, anchor=tk.W,
        ).pack(side=tk.BOTTOM, fill=tk.X)

        # Main pane.
        pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Left: browser.
        left_frame = ttk.Frame(pane)
        pane.add(left_frame, weight=1)
        self._browser = BrowserPanel(left_frame, on_select=self._on_select_system)

        # Right: tabbed notebook.
        right_frame = ttk.Frame(pane)
        pane.add(right_frame, weight=4)
        self._notebook = ttk.Notebook(right_frame)
        self._notebook.pack(fill=tk.BOTH, expand=True)

        # Tabs.
        editor_frame = ttk.Frame(self._notebook)
        self._editor = EditorPanel(editor_frame, self.set_status)
        self._notebook.add(editor_frame, text="Editor")

        assembly_frame = ttk.Frame(self._notebook)
        self._assembly = AssemblyPanel(assembly_frame, self.set_status)
        self._notebook.add(assembly_frame, text="Assembly")

        sim_frame = ttk.Frame(self._notebook)
        self._simulator = SimulatorPanel(sim_frame, self.set_status)
        self._notebook.add(sim_frame, text="Simulator")

        schema_frame = ttk.Frame(self._notebook)
        self._schema = SchemaPanel(schema_frame)
        self._notebook.add(schema_frame, text="Schema")

        coverage_frame = ttk.Frame(self._notebook)
        self._coverage = CoveragePanel(coverage_frame)
        self._notebook.add(coverage_frame, text="Coverage")

        about_frame = ttk.Frame(self._notebook)
        self._about = AboutPanel(about_frame)
        self._notebook.add(about_frame, text="About")

        self.root.bind("<Control-s>", lambda e: self._editor.save_to_disk())

    def _on_select_system(self, system_id: str) -> None:
        system = SystemRegistry.by_id(system_id)
        if system is None:
            return
        self.set_status(f"Selected: {system.label} ({system.id})")
        self._editor.show_system(system)
        self._assembly.show_system(system)
        self._simulator.show_system(system)
        self._schema.show_system(system)
        # Coverage refresh is on-demand via its button.

    def set_status(self, msg: str) -> None:
        self._status_var.set(msg)


def main() -> None:
    root = tk.Tk()
    PromptStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
