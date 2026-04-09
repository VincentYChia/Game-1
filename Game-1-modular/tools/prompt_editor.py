"""Prompt Fragment Editor — Visual tool for editing and previewing
Layer 2 LLM prompt fragments.

Tkinter UI with three panels:
  Left:   Fragment browser (grouped by category, searchable)
  Center: Fragment text editor with live token count
  Right:  Prompt assembly preview (simulates what the LLM would receive)

Run: python tools/prompt_editor.py
"""

import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from world_system.world_memory.prompt_assembler import (
    PromptAssembler, FRAGMENT_CATEGORIES, estimate_tokens,
)

# ── Paths ───────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_DIR = PROJECT_DIR / "world_system" / "config"
FRAGMENTS_PATH = CONFIG_DIR / "prompt_fragments.json"
MANIFEST_PATH = CONFIG_DIR / "stat-key-manifest.json"
HOSTILES_PATH = PROJECT_DIR / "Definitions.JSON" / "hostiles-1.JSON"
MATERIALS_PATH = PROJECT_DIR / "items.JSON" / "items-materials-1.JSON"

# Fragment categories that get matched from trigger tags
FRAGMENT_CATEGORIES = {
    "species", "material_category", "discipline",
    "tier", "element", "rank", "status_effect",
}

# Colors for each category in the browser
CATEGORY_COLORS = {
    "_core": "#4A90D9",
    "_output": "#4A90D9",
    "domain": "#2ECC71",
    "species": "#E67E22",
    "material_category": "#8B4513",
    "discipline": "#9B59B6",
    "tier": "#F39C12",
    "element": "#E74C3C",
    "rank": "#C0392B",
    "status_effect": "#1ABC9C",
}


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


def load_fragments() -> dict:
    """Load prompt fragments from JSON."""
    if FRAGMENTS_PATH.exists():
        with open(FRAGMENTS_PATH) as f:
            return json.load(f)
    return {"_meta": {"version": "1.0", "total_fragments": 0}}


def save_fragments(data: dict):
    """Save prompt fragments to JSON."""
    # Update meta counts
    cats = {}
    for key in data:
        if key.startswith("_meta"):
            continue
        if key.startswith("_"):
            cats[key] = 1
        else:
            cat = key.split(":")[0] if ":" in key else key
            cats[cat] = cats.get(cat, 0) + 1
    data["_meta"]["total_fragments"] = sum(cats.values())
    data["_meta"]["categories"] = cats

    with open(FRAGMENTS_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def get_category(key: str) -> str:
    """Get the display category for a fragment key."""
    if key.startswith("_"):
        return key
    return key.split(":")[0] if ":" in key else "other"


def select_fragments_for_tags(tags: list, library: dict) -> list:
    """Simulate the fragment selection logic for a given tag set."""
    selected = []

    # Core (always)
    if "_core" in library:
        selected.append(("_core", library["_core"]))

    # Domain (first matching)
    for tag in tags:
        if tag.startswith("domain:") and tag in library:
            selected.append((tag, library[tag]))
            break

    # Entity/context fragments
    for tag in tags:
        cat = tag.split(":")[0] if ":" in tag else ""
        if cat in FRAGMENT_CATEGORIES and tag in library:
            selected.append((tag, library[tag]))

    # Output (always)
    if "_output" in library:
        selected.append(("_output", library["_output"]))

    return selected


def load_stat_patterns() -> dict:
    """Load stat manifest patterns for the simulator."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            data = json.load(f)
        return data.get("patterns", {})
    return {}


def load_game_entities() -> dict:
    """Load enemies and materials for dropdown population."""
    entities = {"enemies": [], "materials": [], "disciplines": []}

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

    entities["disciplines"] = [
        "smithing", "alchemy", "refining",
        "engineering", "enchanting", "fishing",
    ]

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

        self.fragments = load_fragments()
        self.game_entities = load_game_entities()
        self.stat_patterns = load_stat_patterns()
        self.selected_key = None
        self.unsaved_changes = False

        self._build_menu()
        self._build_ui()
        self._populate_browser()
        self._populate_simulator_dropdowns()

    # ── Menu Bar ────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save All", command=self._save_all,
                              accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Validate Coverage",
                              command=self._validate_coverage)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        self.root.config(menu=menubar)
        self.root.bind("<Control-s>", lambda e: self._save_all())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Main Layout ─────────────────────────────────────────────────

    def _build_ui(self):
        # Main paned window (horizontal split)
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel: Fragment Browser
        left_frame = ttk.LabelFrame(main_pane, text="Fragment Browser",
                                     padding=5)
        main_pane.add(left_frame, weight=1)
        self._build_browser(left_frame)

        # Center panel: Fragment Editor
        center_frame = ttk.LabelFrame(main_pane, text="Fragment Editor",
                                       padding=5)
        main_pane.add(center_frame, weight=2)
        self._build_editor(center_frame)

        # Right panel: Prompt Preview / Simulator
        right_frame = ttk.LabelFrame(main_pane, text="Prompt Assembly Preview",
                                      padding=5)
        main_pane.add(right_frame, weight=2)
        self._build_simulator(right_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                                relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, padx=5, pady=(0, 5))

    # ── Left Panel: Browser ─────────────────────────────────────────

    def _build_browser(self, parent):
        # Search bar
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_browser())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Treeview
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, selectmode="browse",
                                  columns=("tokens",), show="tree headings")
        self.tree.heading("#0", text="Fragment", anchor=tk.W)
        self.tree.heading("tokens", text="Tokens", anchor=tk.E)
        self.tree.column("#0", width=220, minwidth=150)
        self.tree.column("tokens", width=50, minwidth=40, anchor=tk.E)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                   command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Fragment count label
        self.count_label = ttk.Label(parent, text="")
        self.count_label.pack(fill=tk.X, pady=(5, 0))

    def _populate_browser(self):
        """Fill the treeview with fragments grouped by category."""
        self.tree.delete(*self.tree.get_children())

        # Group fragments by category
        groups = {}
        for key in sorted(self.fragments.keys()):
            if key == "_meta":
                continue
            cat = get_category(key)
            groups.setdefault(cat, []).append(key)

        # Category display order
        order = ["_core", "_output", "domain", "species",
                 "material_category", "discipline", "tier",
                 "element", "rank", "status_effect"]
        for cat in order:
            if cat not in groups:
                continue
            color = CATEGORY_COLORS.get(cat, "#666666")
            parent_id = self.tree.insert(
                "", "end", text=f"  {cat} ({len(groups[cat])})",
                open=(cat in ("_core", "_output", "domain")),
                tags=(cat,),
            )
            self.tree.tag_configure(cat, foreground=color)

            for key in groups[cat]:
                text = self.fragments[key]
                tokens = estimate_tokens(text) if isinstance(text, str) else 0
                display = key.split(":")[-1] if ":" in key else key
                self.tree.insert(parent_id, "end", text=f"  {display}",
                                 values=(tokens,), tags=("leaf",))

        # Any uncategorized
        for cat, keys in groups.items():
            if cat not in order:
                parent_id = self.tree.insert(
                    "", "end", text=f"  {cat} ({len(keys)})", tags=("other",))
                for key in keys:
                    text = self.fragments[key]
                    tokens = estimate_tokens(text) if isinstance(text, str) else 0
                    display = key.split(":")[-1] if ":" in key else key
                    self.tree.insert(parent_id, "end", text=f"  {display}",
                                     values=(tokens,), tags=("leaf",))

        total = self.fragments.get("_meta", {}).get("total_fragments", 0)
        self.count_label.config(text=f"{total} fragments total")

    def _filter_browser(self):
        """Filter browser by search text."""
        query = self.search_var.get().lower().strip()
        if not query:
            self._populate_browser()
            return

        self.tree.delete(*self.tree.get_children())
        for key in sorted(self.fragments.keys()):
            if key == "_meta":
                continue
            text = self.fragments[key] if isinstance(self.fragments[key], str) else ""
            if query in key.lower() or query in text.lower():
                cat = get_category(key)
                color = CATEGORY_COLORS.get(cat, "#666666")
                tokens = estimate_tokens(text)
                self.tree.insert("", "end", text=f"  {key}",
                                 values=(tokens,), tags=(cat,))
                self.tree.tag_configure(cat, foreground=color)

    def _on_tree_select(self, event):
        """Handle treeview selection — load fragment into editor."""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        display_text = item["text"].strip()

        # Find the actual key
        key = None
        for k in self.fragments:
            if k == "_meta":
                continue
            short = k.split(":")[-1] if ":" in k else k
            if short == display_text or k == display_text:
                key = k
                break

        if key and key in self.fragments:
            self._load_fragment(key)

    # ── Center Panel: Editor ────────────────────────────────────────

    def _build_editor(self, parent):
        # Key display
        key_frame = ttk.Frame(parent)
        key_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(key_frame, text="Key:").pack(side=tk.LEFT)
        self.key_var = tk.StringVar(value="(select a fragment)")
        ttk.Label(key_frame, textvariable=self.key_var,
                   font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT, padx=5)

        # Category / tag info
        self.tag_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.tag_var,
                   foreground="gray").pack(fill=tk.X)

        # Text editor
        self.editor = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, font=("Consolas", 11),
            height=10, padx=8, pady=8,
        )
        self.editor.pack(fill=tk.BOTH, expand=True, pady=5)
        self.editor.bind("<KeyRelease>", self._on_editor_change)

        # Token count + save button
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.X)

        self.token_var = tk.StringVar(value="0 tokens")
        ttk.Label(bottom_frame, textvariable=self.token_var).pack(side=tk.LEFT)

        self.save_btn = ttk.Button(bottom_frame, text="Save Fragment",
                                    command=self._save_fragment)
        self.save_btn.pack(side=tk.RIGHT)

        self.change_indicator = ttk.Label(bottom_frame, text="",
                                           foreground="orange")
        self.change_indicator.pack(side=tk.RIGHT, padx=10)

    def _load_fragment(self, key: str):
        """Load a fragment into the editor."""
        self.selected_key = key
        self.key_var.set(key)

        cat = get_category(key)
        color = CATEGORY_COLORS.get(cat, "#666666")
        self.tag_var.set(f"Category: {cat}")

        text = self.fragments.get(key, "")
        if not isinstance(text, str):
            text = str(text)

        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", text)
        self._update_token_count()
        self.change_indicator.config(text="")

        self.status_var.set(f"Editing: {key}")

    def _on_editor_change(self, event=None):
        """Track changes in the editor."""
        self._update_token_count()
        if self.selected_key:
            current = self.editor.get("1.0", tk.END).strip()
            original = self.fragments.get(self.selected_key, "")
            if current != original:
                self.change_indicator.config(text="● unsaved")
                self.unsaved_changes = True
            else:
                self.change_indicator.config(text="")

    def _update_token_count(self):
        text = self.editor.get("1.0", tk.END).strip()
        tokens = estimate_tokens(text)
        self.token_var.set(f"~{tokens} tokens")

    def _save_fragment(self):
        """Save the current fragment back to the library."""
        if not self.selected_key:
            return
        text = self.editor.get("1.0", tk.END).strip()
        self.fragments[self.selected_key] = text
        self.change_indicator.config(text="✓ saved", foreground="green")
        self.status_var.set(f"Saved: {self.selected_key}")
        self.root.after(2000,
                         lambda: self.change_indicator.config(text=""))

    # ── Right Panel: Simulator ──────────────────────────────────────

    def _build_simulator(self, parent):
        # Trigger configuration
        config_frame = ttk.LabelFrame(parent, text="Trigger Configuration",
                                       padding=5)
        config_frame.pack(fill=tk.X, pady=(0, 5))

        # Row 1: Event type
        r1 = ttk.Frame(config_frame)
        r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="Event:", width=10).pack(side=tk.LEFT)
        self.event_type_var = tk.StringVar(value="enemy_killed")
        event_combo = ttk.Combobox(r1, textvariable=self.event_type_var,
                                    width=25, state="readonly")
        event_combo["values"] = [
            "enemy_killed", "resource_gathered", "craft_attempted",
            "attack_performed", "damage_taken", "level_up",
            "skill_used", "chunk_entered", "npc_interaction",
            "quest_completed", "item_acquired", "node_depleted",
        ]
        event_combo.pack(side=tk.LEFT, padx=5)
        event_combo.bind("<<ComboboxSelected>>",
                          lambda e: self._update_subtype_options())

        # Row 2: Subtype (entity)
        r2 = ttk.Frame(config_frame)
        r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text="Entity:", width=10).pack(side=tk.LEFT)
        self.subtype_var = tk.StringVar(value="wolf_grey")
        self.subtype_combo = ttk.Combobox(r2, textvariable=self.subtype_var,
                                           width=25)
        self.subtype_combo.pack(side=tk.LEFT, padx=5)

        # Row 3: Location
        r3 = ttk.Frame(config_frame)
        r3.pack(fill=tk.X, pady=2)
        ttk.Label(r3, text="Location:", width=10).pack(side=tk.LEFT)
        self.location_var = tk.StringVar(value="whispering_woods")
        loc_combo = ttk.Combobox(r3, textvariable=self.location_var, width=25)
        loc_combo["values"] = [
            "whispering_woods", "iron_hills", "dark_cave",
            "spawn_crossroads", "elder_grove", "traders_corner",
        ]
        loc_combo.pack(side=tk.LEFT, padx=5)

        # Row 4: Counts
        r4 = ttk.Frame(config_frame)
        r4.pack(fill=tk.X, pady=2)
        ttk.Label(r4, text="Count:", width=10).pack(side=tk.LEFT)
        self.count_var = tk.StringVar(value="10")
        ttk.Entry(r4, textvariable=self.count_var, width=8).pack(
            side=tk.LEFT, padx=5)
        ttk.Label(r4, text="All-time:").pack(side=tk.LEFT, padx=(15, 0))
        self.alltime_var = tk.StringVar(value="47")
        ttk.Entry(r4, textvariable=self.alltime_var, width=8).pack(
            side=tk.LEFT, padx=5)
        ttk.Label(r4, text="Month avg/day:").pack(side=tk.LEFT, padx=(15, 0))
        self.avg_var = tk.StringVar(value="4.2")
        ttk.Entry(r4, textvariable=self.avg_var, width=8).pack(
            side=tk.LEFT, padx=5)

        # Assemble button
        ttk.Button(config_frame, text="Assemble Prompt",
                    command=self._assemble_prompt).pack(pady=(5, 0))

        # Preview area
        preview_frame = ttk.LabelFrame(parent, text="Assembled Prompt",
                                        padding=5)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        self.preview = scrolledtext.ScrolledText(
            preview_frame, wrap=tk.WORD, font=("Consolas", 10),
            state=tk.DISABLED, padx=8, pady=8,
        )
        self.preview.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for coloring
        self.preview.tag_configure("header", foreground="#4A90D9",
                                    font=("Consolas", 10, "bold"))
        self.preview.tag_configure("fragment_key", foreground="#E67E22",
                                    font=("Consolas", 10, "bold"))
        self.preview.tag_configure("data", foreground="#2ECC71")
        self.preview.tag_configure("token_count", foreground="#888888")

        # Total tokens label
        self.preview_tokens_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.preview_tokens_var).pack(
            fill=tk.X, pady=(5, 0))

    def _populate_simulator_dropdowns(self):
        """Fill entity dropdown based on available game data."""
        self._update_subtype_options()

    def _update_subtype_options(self):
        """Update the entity dropdown based on selected event type."""
        event_type = self.event_type_var.get()

        if event_type == "enemy_killed":
            values = [e["id"] for e in self.game_entities["enemies"]]
        elif event_type == "resource_gathered":
            values = list({m["id"] for m in self.game_entities["materials"]})[:30]
        elif event_type == "craft_attempted":
            values = self.game_entities["disciplines"]
        else:
            values = ["general"]

        self.subtype_combo["values"] = sorted(values)
        if values and self.subtype_var.get() not in values:
            self.subtype_var.set(values[0])

    def _get_trigger_tags(self) -> list:
        """Build a tag list from the simulator configuration."""
        event_type = self.event_type_var.get()
        entity = self.subtype_var.get()
        tags = []

        # Domain tag
        domain_map = {
            "enemy_killed": "combat", "attack_performed": "combat",
            "damage_taken": "combat", "resource_gathered": "gathering",
            "node_depleted": "gathering", "craft_attempted": "crafting",
            "level_up": "progression", "skill_used": "skills",
            "chunk_entered": "exploration", "npc_interaction": "social",
            "quest_completed": "social", "item_acquired": "items",
        }
        domain = domain_map.get(event_type, "combat")
        tags.append(f"domain:{domain}")

        # Entity-specific tags
        if event_type == "enemy_killed":
            tags.append(f"species:{entity}")
            # Find tier
            for e in self.game_entities["enemies"]:
                if e["id"] == entity:
                    tags.append(f"tier:{e['tier']}")
                    break
            tags.append("rank:normal")

        elif event_type == "resource_gathered":
            for m in self.game_entities["materials"]:
                if m["id"] == entity:
                    if m.get("category"):
                        tags.append(f"material_category:{m['category']}")
                    tags.append(f"tier:{m['tier']}")
                    break

        elif event_type == "craft_attempted":
            tags.append(f"discipline:{entity}")

        return tags

    def _assemble_prompt(self):
        """Assemble and display the full prompt from fragments + data."""
        tags = self._get_trigger_tags()
        selected = select_fragments_for_tags(tags, self.fragments)

        # Build data block
        event_type = self.event_type_var.get()
        entity = self.subtype_var.get()
        location = self.location_var.get()
        count = self.count_var.get()
        alltime = self.alltime_var.get()
        avg = self.avg_var.get()

        try:
            count_f = float(count)
            alltime_f = float(alltime)
            avg_f = float(avg)
        except ValueError:
            count_f = alltime_f = avg_f = 0.0

        recency = f"{count_f / alltime_f:.0%}" if alltime_f > 0 else "N/A"
        vs_avg = f"{count_f / avg_f:.1f}x" if avg_f > 0 else "N/A"

        # Display in preview
        self.preview.config(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)

        # Tags line
        self.preview.insert(tk.END, "TRIGGER TAGS: ", "header")
        self.preview.insert(tk.END, ", ".join(tags) + "\n\n")

        # Fragments selected
        self.preview.insert(tk.END, "FRAGMENTS SELECTED:\n", "header")
        total_tokens = 0
        for key, text in selected:
            tokens = estimate_tokens(text)
            total_tokens += tokens
            self.preview.insert(tk.END, f"  [{key}] ", "fragment_key")
            self.preview.insert(tk.END, f"(~{tokens} tokens)\n")

        self.preview.insert(tk.END, "\n")
        self.preview.insert(tk.END, "═" * 60 + "\n", "header")
        self.preview.insert(tk.END, "SYSTEM PROMPT:\n", "header")
        self.preview.insert(tk.END, "═" * 60 + "\n\n")

        for key, text in selected:
            if key == "_output":
                continue
            self.preview.insert(tk.END, text + "\n\n")

        self.preview.insert(tk.END, "═" * 60 + "\n", "header")
        self.preview.insert(tk.END, "USER PROMPT:\n", "header")
        self.preview.insert(tk.END, "═" * 60 + "\n\n")

        # Data block
        self.preview.insert(tk.END,
            f"Trigger: {event_type} ({entity}) in {location}\n", "data")
        self.preview.insert(tk.END, f"Count today: {count}\n", "data")
        self.preview.insert(tk.END, f"All-time: {alltime}\n", "data")
        self.preview.insert(tk.END,
            f"Month average per day: {avg}\n", "data")
        self.preview.insert(tk.END,
            f"Recency: {recency} of all-time happened today\n", "data")
        self.preview.insert(tk.END,
            f"vs average: {vs_avg}\n\n", "data")

        # Output instruction
        for key, text in selected:
            if key == "_output":
                self.preview.insert(tk.END, text + "\n")

        # Token summary
        data_tokens = estimate_tokens(
            f"Trigger: {event_type} ({entity}) in {location}\n"
            f"Count: {count}\nAll-time: {alltime}\nAvg: {avg}\n"
            f"Recency: {recency}\nvs average: {vs_avg}\n"
        )
        total_tokens += data_tokens
        self.preview_tokens_var.set(
            f"Total: ~{total_tokens} tokens "
            f"(system: ~{total_tokens - data_tokens}, "
            f"data: ~{data_tokens})"
        )

        self.preview.config(state=tk.DISABLED)
        self.status_var.set(
            f"Assembled prompt with {len(selected)} fragments, "
            f"~{total_tokens} tokens"
        )

    # ── File Operations ─────────────────────────────────────────────

    def _save_all(self):
        """Save all fragments to disk."""
        # Save current editor content first
        if self.selected_key:
            text = self.editor.get("1.0", tk.END).strip()
            self.fragments[self.selected_key] = text

        save_fragments(self.fragments)
        self.unsaved_changes = False
        self.change_indicator.config(text="✓ all saved", foreground="green")
        self.status_var.set("All fragments saved to prompt_fragments.json")
        self._populate_browser()

    def _validate_coverage(self):
        """Check for game entities without matching fragments."""
        missing = []

        # Check species coverage
        for e in self.game_entities["enemies"]:
            key = f"species:{e['id']}"
            if key not in self.fragments:
                missing.append(f"  {key} ({e['name']}, T{e['tier']})")

        # Check discipline coverage
        for d in self.game_entities["disciplines"]:
            key = f"discipline:{d}"
            if key not in self.fragments:
                missing.append(f"  {key}")

        # Check tier coverage
        for t in range(1, 5):
            key = f"tier:{t}"
            if key not in self.fragments:
                missing.append(f"  {key}")

        if missing:
            msg = f"Missing fragments ({len(missing)}):\n\n" + "\n".join(missing)
        else:
            msg = "Full coverage! All game entities have matching fragments."

        messagebox.showinfo("Coverage Validation", msg)

    def _on_close(self):
        if self.unsaved_changes:
            if messagebox.askyesno("Unsaved Changes",
                                    "Save changes before closing?"):
                self._save_all()
        self.root.destroy()


# ═══════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    app = PromptEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
