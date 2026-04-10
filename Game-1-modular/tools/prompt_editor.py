"""Prompt Fragment Editor — Visual tool for editing and previewing
Layer 2 LLM prompt fragments.

Tkinter UI with three panels:
  Left:   Fragment browser (grouped by category, searchable)
  Center: Fragment text editor with live token count
  Right:  Prompt assembly preview (simulates what the LLM would receive)

Run from Game-1-modular/:  python tools/prompt_editor.py
"""

import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from pathlib import Path

# Add project root to path
_PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_DIR))

from world_system.world_memory.prompt_assembler import (
    PromptAssembler, FRAGMENT_CATEGORIES, EVENT_TO_DOMAIN, estimate_tokens,
)

# ── Paths ───────────────────────────────────────────────────────────

HOSTILES_PATH = _PROJECT_DIR / "Definitions.JSON" / "hostiles-1.JSON"
MATERIALS_PATH = _PROJECT_DIR / "items.JSON" / "items-materials-1.JSON"

# Colors per category
CATEGORY_COLORS = {
    "_core": "#4A90D9", "_output": "#4A90D9",
    "domain": "#2ECC71", "species": "#E67E22",
    "material_category": "#8B4513", "discipline": "#9B59B6",
    "tier": "#F39C12", "element": "#E74C3C",
    "rank": "#C0392B", "status_effect": "#1ABC9C",
    "action": "#3498DB", "result": "#16A085",
}

CATEGORY_ORDER = [
    "_core", "_output", "domain", "species", "material_category",
    "discipline", "tier", "element", "rank", "status_effect",
    "action", "result",
]


def _load_game_entities() -> dict:
    """Load enemies and materials for the simulator dropdowns."""
    entities = {"enemies": [], "materials": [], "disciplines": [
        "smithing", "alchemy", "refining", "engineering", "enchanting", "fishing",
    ]}

    if HOSTILES_PATH.exists():
        with open(HOSTILES_PATH) as f:
            data = json.load(f)
        for e in data.get("enemies", []):
            entities["enemies"].append({
                "id": e.get("enemyId", ""),
                "name": e.get("name", ""),
                "tier": e.get("tier", 1),
            })

    if MATERIALS_PATH.exists():
        with open(MATERIALS_PATH) as f:
            data = json.load(f)
        mats = data if isinstance(data, list) else data.get("materials", [])
        for m in mats:
            entities["materials"].append({
                "id": m.get("materialId", ""),
                "name": m.get("name", ""),
                "tier": m.get("tier", 1),
                "category": m.get("category", ""),
            })

    return entities


# ═══════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════

class PromptEditorApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WMS Prompt Fragment Editor")
        self.root.geometry("1500x900")
        self.root.minsize(1200, 700)

        # Core data
        self.assembler = PromptAssembler()
        self.assembler.load()
        self.game_entities = _load_game_entities()
        self.selected_key: str | None = None
        self.unsaved_changes = False

        # Map treeview item IDs → fragment keys
        self._tree_key_map: dict[str, str] = {}

        self._build_menu()
        self._build_ui()
        self._populate_browser()

    # ── Menu ────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save All (Ctrl+S)", command=self._save_all)
        file_menu.add_separator()
        file_menu.add_command(label="New Fragment...", command=self._new_fragment)
        file_menu.add_command(label="Delete Fragment", command=self._delete_fragment)
        file_menu.add_separator()
        file_menu.add_command(label="Validate Coverage", command=self._validate)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        self.root.config(menu=menubar)
        self.root.bind("<Control-s>", lambda e: self._save_all())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Layout ──────────────────────────────────────────────────────

    def _build_ui(self):
        pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left = ttk.LabelFrame(pane, text="Fragments", padding=5)
        pane.add(left, weight=1)
        self._build_browser(left)

        center = ttk.LabelFrame(pane, text="Editor", padding=5)
        pane.add(center, weight=2)
        self._build_editor(center)

        right = ttk.LabelFrame(pane, text="Prompt Preview", padding=5)
        pane.add(right, weight=2)
        self._build_simulator(right)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var,
                  relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, padx=5, pady=(0, 5))

    # ── Left: Browser ───────────────────────────────────────────────

    def _build_browser(self, parent):
        # Search
        sf = ttk.Frame(parent)
        sf.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(sf, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_browser())
        ttk.Entry(sf, textvariable=self.search_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Tree
        tf = ttk.Frame(parent)
        tf.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tf, selectmode="browse",
                                  columns=("tokens",), show="tree headings")
        self.tree.heading("#0", text="Fragment", anchor=tk.W)
        self.tree.heading("tokens", text="Tok", anchor=tk.E)
        self.tree.column("#0", width=230, minwidth=150)
        self.tree.column("tokens", width=40, minwidth=35, anchor=tk.E)

        sb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.count_label = ttk.Label(parent, text="")
        self.count_label.pack(fill=tk.X, pady=(5, 0))

    def _populate_browser(self):
        self.tree.delete(*self.tree.get_children())
        self._tree_key_map.clear()

        groups: dict[str, list[str]] = {}
        for key in self.assembler.list_keys():
            cat = key if key.startswith("_") else (
                key.split(":")[0] if ":" in key else "other")
            groups.setdefault(cat, []).append(key)

        for cat in CATEGORY_ORDER:
            if cat not in groups:
                continue
            keys = groups.pop(cat)
            color = CATEGORY_COLORS.get(cat, "#666")
            pid = self.tree.insert("", "end",
                                    text=f"  {cat} ({len(keys)})",
                                    open=(cat in ("_core", "_output", "domain")))
            self.tree.tag_configure(cat, foreground=color)
            self.tree.item(pid, tags=(cat,))

            for key in sorted(keys):
                text = self.assembler.get_fragment(key)
                tok = estimate_tokens(text)
                iid = self.tree.insert(pid, "end", text=f"  {key}",
                                        values=(tok,), tags=(cat,))
                self._tree_key_map[iid] = key

        # Remaining
        for cat, keys in groups.items():
            pid = self.tree.insert("", "end", text=f"  {cat} ({len(keys)})")
            for key in sorted(keys):
                text = self.assembler.get_fragment(key)
                tok = estimate_tokens(text)
                iid = self.tree.insert(pid, "end", text=f"  {key}",
                                        values=(tok,))
                self._tree_key_map[iid] = key

        self.count_label.config(
            text=f"{self.assembler.fragment_count} fragments")

    def _filter_browser(self):
        q = self.search_var.get().lower().strip()
        if not q:
            self._populate_browser()
            return
        self.tree.delete(*self.tree.get_children())
        self._tree_key_map.clear()
        for key in self.assembler.list_keys():
            text = self.assembler.get_fragment(key)
            if q in key.lower() or q in text.lower():
                cat = key.split(":")[0] if ":" in key else key
                color = CATEGORY_COLORS.get(cat, "#666")
                self.tree.tag_configure(cat, foreground=color)
                iid = self.tree.insert("", "end", text=f"  {key}",
                                        values=(estimate_tokens(text),),
                                        tags=(cat,))
                self._tree_key_map[iid] = key

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        key = self._tree_key_map.get(sel[0])
        if key:
            self._load_fragment(key)

    # ── Center: Editor ──────────────────────────────────────────────

    def _build_editor(self, parent):
        # Key label
        kf = ttk.Frame(parent)
        kf.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(kf, text="Key:").pack(side=tk.LEFT)
        self.key_var = tk.StringVar(value="(select a fragment)")
        ttk.Label(kf, textvariable=self.key_var,
                  font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT, padx=5)

        self.cat_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.cat_var,
                  foreground="gray").pack(fill=tk.X)

        # Text editor
        self.editor = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, font=("Consolas", 11),
            height=10, padx=8, pady=8)
        self.editor.pack(fill=tk.BOTH, expand=True, pady=5)
        self.editor.bind("<KeyRelease>", self._on_edit)

        bf = ttk.Frame(parent)
        bf.pack(fill=tk.X)
        self.tok_var = tk.StringVar(value="0 tokens")
        ttk.Label(bf, textvariable=self.tok_var).pack(side=tk.LEFT)
        ttk.Button(bf, text="Save Fragment",
                   command=self._save_fragment).pack(side=tk.RIGHT)
        self.change_lbl = ttk.Label(bf, text="", foreground="orange")
        self.change_lbl.pack(side=tk.RIGHT, padx=10)

    def _load_fragment(self, key: str):
        self.selected_key = key
        self.key_var.set(key)
        cat = key if key.startswith("_") else key.split(":")[0]
        self.cat_var.set(f"Category: {cat}")

        text = self.assembler.get_fragment(key)
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", text)
        self._update_tok()
        self.change_lbl.config(text="")
        self.status_var.set(f"Editing: {key}")

    def _on_edit(self, event=None):
        self._update_tok()
        if self.selected_key:
            cur = self.editor.get("1.0", tk.END).strip()
            orig = self.assembler.get_fragment(self.selected_key)
            if cur != orig:
                self.change_lbl.config(text="● unsaved", foreground="orange")
                self.unsaved_changes = True
            else:
                self.change_lbl.config(text="")

    def _update_tok(self):
        text = self.editor.get("1.0", tk.END).strip()
        self.tok_var.set(f"~{estimate_tokens(text)} tokens")

    def _save_fragment(self):
        if not self.selected_key:
            return
        text = self.editor.get("1.0", tk.END).strip()
        self.assembler.set_fragment(self.selected_key, text)
        self.change_lbl.config(text="✓ saved", foreground="green")
        self.status_var.set(f"Saved: {self.selected_key}")

    # ── Right: Simulator ────────────────────────────────────────────

    def _build_simulator(self, parent):
        cfg = ttk.LabelFrame(parent, text="Trigger Configuration", padding=5)
        cfg.pack(fill=tk.X, pady=(0, 5))

        # Event type
        r1 = ttk.Frame(cfg)
        r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="Event:", width=12).pack(side=tk.LEFT)
        self.evt_var = tk.StringVar(value="enemy_killed")
        cb = ttk.Combobox(r1, textvariable=self.evt_var, width=25,
                          state="readonly")
        cb["values"] = sorted(EVENT_TO_DOMAIN.keys())
        cb.pack(side=tk.LEFT, padx=5)
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_entity_opts())

        # Entity
        r2 = ttk.Frame(cfg)
        r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text="Entity:", width=12).pack(side=tk.LEFT)
        self.ent_var = tk.StringVar(value="wolf_grey")
        self.ent_cb = ttk.Combobox(r2, textvariable=self.ent_var, width=25)
        self.ent_cb.pack(side=tk.LEFT, padx=5)
        self._update_entity_opts()

        # Location
        r3 = ttk.Frame(cfg)
        r3.pack(fill=tk.X, pady=2)
        ttk.Label(r3, text="Location:", width=12).pack(side=tk.LEFT)
        self.loc_var = tk.StringVar(value="whispering_woods")
        ttk.Combobox(r3, textvariable=self.loc_var, width=25,
                      values=["whispering_woods", "iron_hills", "dark_cave",
                              "spawn_crossroads", "elder_grove", "traders_corner"]
                      ).pack(side=tk.LEFT, padx=5)

        # Numeric inputs
        r4 = ttk.Frame(cfg)
        r4.pack(fill=tk.X, pady=2)
        for label, var_name, default in [
            ("Today:", "cnt_var", "8"),
            ("All-time:", "all_var", "47"),
            ("Month avg:", "avg_var", "4.2"),
        ]:
            ttk.Label(r4, text=label).pack(side=tk.LEFT, padx=(10, 0))
            v = tk.StringVar(value=default)
            setattr(self, var_name, v)
            ttk.Entry(r4, textvariable=v, width=7).pack(side=tk.LEFT, padx=2)

        # Extra tags
        r5 = ttk.Frame(cfg)
        r5.pack(fill=tk.X, pady=2)
        ttk.Label(r5, text="Extra tags:", width=12).pack(side=tk.LEFT)
        self.extra_tags_var = tk.StringVar(value="")
        ttk.Entry(r5, textvariable=self.extra_tags_var, width=40).pack(
            side=tk.LEFT, padx=5)
        ttk.Label(r5, text="(comma-separated, e.g. action:deplete,result:first)",
                  foreground="gray").pack(side=tk.LEFT)

        ttk.Button(cfg, text="⟳ Assemble Prompt",
                   command=self._assemble).pack(pady=(5, 0))

        # Preview
        pf = ttk.LabelFrame(parent, text="Assembled Prompt", padding=5)
        pf.pack(fill=tk.BOTH, expand=True)

        self.preview = scrolledtext.ScrolledText(
            pf, wrap=tk.WORD, font=("Consolas", 10),
            state=tk.DISABLED, padx=8, pady=8)
        self.preview.pack(fill=tk.BOTH, expand=True)

        self.preview.tag_configure("h", foreground="#4A90D9",
                                    font=("Consolas", 10, "bold"))
        self.preview.tag_configure("fk", foreground="#E67E22",
                                    font=("Consolas", 10, "bold"))
        self.preview.tag_configure("d", foreground="#2ECC71")

        self.ptok_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.ptok_var).pack(fill=tk.X, pady=(5, 0))

    def _update_entity_opts(self):
        evt = self.evt_var.get()
        if evt == "enemy_killed":
            vals = [e["id"] for e in self.game_entities["enemies"]]
        elif evt in ("resource_gathered", "node_depleted"):
            vals = sorted({m["id"] for m in self.game_entities["materials"]})
        elif evt == "craft_attempted":
            vals = self.game_entities["disciplines"]
        elif evt in ("skill_used",):
            vals = ["combat_strike", "fireball", "heal", "chain_harvest"]
        else:
            vals = ["general"]
        self.ent_cb["values"] = vals
        if vals and self.ent_var.get() not in vals:
            self.ent_var.set(vals[0])

    def _build_tags(self) -> list[str]:
        evt = self.evt_var.get()
        entity = self.ent_var.get()

        # Start with assembler's tag derivation
        tier = None
        if evt == "enemy_killed":
            subtype = f"killed_{entity}"
            for e in self.game_entities["enemies"]:
                if e["id"] == entity:
                    tier = e["tier"]
                    break
        elif evt in ("resource_gathered", "node_depleted"):
            subtype = f"gathered_{entity}"
            for m in self.game_entities["materials"]:
                if m["id"] == entity:
                    tier = m["tier"]
                    break
        elif evt == "craft_attempted":
            subtype = f"crafted_{entity}"
        else:
            subtype = entity

        extra = []
        # Material category
        if evt in ("resource_gathered", "node_depleted"):
            for m in self.game_entities["materials"]:
                if m["id"] == entity and m.get("category"):
                    extra.append(f"material_category:{m['category']}")
                    break
        # Manual extra tags
        manual = self.extra_tags_var.get().strip()
        if manual:
            extra.extend(t.strip() for t in manual.split(",") if t.strip())

        tags = self.assembler.tags_from_event(evt, subtype, tier, extra)
        return tags

    def _assemble(self):
        tags = self._build_tags()

        # Build data block
        try:
            cnt = float(self.cnt_var.get())
            all_ = float(self.all_var.get())
            avg = float(self.avg_var.get())
        except ValueError:
            cnt = all_ = avg = 0.0

        recency = f"{cnt / all_:.0%}" if all_ > 0 else "N/A"
        vs_avg = f"{cnt / avg:.1f}x" if avg > 0 else "N/A"

        entity = self.ent_var.get()
        loc = self.loc_var.get()
        evt = self.evt_var.get()

        data_block = (
            f"Trigger: {evt} ({entity}) in {loc}\n"
            f"Count today: {self.cnt_var.get()}\n"
            f"All-time: {self.all_var.get()}\n"
            f"Month average per day: {self.avg_var.get()}\n"
            f"Recency: {recency} of all-time happened today\n"
            f"vs average: {vs_avg}"
        )

        prompt = self.assembler.assemble(tags, data_block)

        # Render
        self.preview.config(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)

        self.preview.insert(tk.END, "TAGS: ", "h")
        self.preview.insert(tk.END, ", ".join(tags) + "\n\n")

        self.preview.insert(tk.END, "FRAGMENTS SELECTED:\n", "h")
        for key, text in prompt.fragments_used:
            self.preview.insert(tk.END, f"  [{key}] ", "fk")
            self.preview.insert(tk.END, f"~{estimate_tokens(text)} tok\n")

        self.preview.insert(tk.END, f"\n{'═' * 55}\n", "h")
        self.preview.insert(tk.END, "SYSTEM:\n", "h")
        self.preview.insert(tk.END, f"{'═' * 55}\n\n")
        self.preview.insert(tk.END, prompt.system + "\n")

        self.preview.insert(tk.END, f"\n{'═' * 55}\n", "h")
        self.preview.insert(tk.END, "USER:\n", "h")
        self.preview.insert(tk.END, f"{'═' * 55}\n\n")
        self.preview.insert(tk.END, prompt.user + "\n")

        self.preview.config(state=tk.DISABLED)
        self.ptok_var.set(f"~{prompt.token_estimate} total tokens")
        self.status_var.set(
            f"Assembled: {len(prompt.fragments_used)} fragments, "
            f"~{prompt.token_estimate} tokens")

    # ── File operations ─────────────────────────────────────────────

    def _save_all(self):
        if self.selected_key:
            text = self.editor.get("1.0", tk.END).strip()
            self.assembler.set_fragment(self.selected_key, text)
        self.assembler.save()
        self.unsaved_changes = False
        self.change_lbl.config(text="✓ all saved", foreground="green")
        self.status_var.set("Saved to prompt_fragments.json")
        self._populate_browser()

    def _new_fragment(self):
        key = simpledialog.askstring(
            "New Fragment",
            "Enter fragment key (e.g. species:new_enemy, action:trade):",
            parent=self.root)
        if not key:
            return
        if key in self.assembler.fragments:
            messagebox.showwarning("Exists", f"Fragment '{key}' already exists.")
            return
        self.assembler.set_fragment(key, "")
        self._populate_browser()
        self._load_fragment(key)
        self.status_var.set(f"Created: {key}")

    def _delete_fragment(self):
        if not self.selected_key:
            return
        if self.selected_key.startswith("_"):
            messagebox.showwarning("Protected", "Cannot delete core fragments.")
            return
        if messagebox.askyesno("Delete", f"Delete '{self.selected_key}'?"):
            del self.assembler.fragments[self.selected_key]
            self.selected_key = None
            self.editor.delete("1.0", tk.END)
            self.key_var.set("(deleted)")
            self._populate_browser()

    def _validate(self):
        result = self.assembler.validate_coverage(self.game_entities)
        missing = result["missing"]
        if missing:
            msg = f"Missing {len(missing)} fragments:\n\n" + "\n".join(missing)
        else:
            msg = f"Full coverage! {len(result['covered'])} entities covered."
        messagebox.showinfo("Coverage", msg)

    def _on_close(self):
        if self.unsaved_changes:
            if messagebox.askyesno("Unsaved", "Save before closing?"):
                self._save_all()
        self.root.destroy()


# ═══════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    PromptEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
