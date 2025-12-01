#!/usr/bin/env python3
"""
Unified JSON Creator - Dynamic Adaptive UI
- Analyzes existing data to build smart dropdowns
- Custom entry buttons for all dropdowns
- Tag management interface for arrays
- Faithful loading of ALL fields
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass
import re
from datetime import datetime


# ============================================================================
# DEBUG LOGGER
# ============================================================================

class DebugLogger:
    def __init__(self):
        self.logs = []
        self.widget = None

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        self.logs.append(log_entry)
        print(log_entry)

        if self.widget:
            self.widget.insert(tk.END, log_entry + "\n")
            self.widget.see(tk.END)

    def error(self, message: str, exc: Exception = None):
        self.log(message, "ERROR")
        if exc:
            import traceback
            self.log(traceback.format_exc(), "TRACE")

    def success(self, message: str):
        self.log(message, "SUCCESS")

    def attach_widget(self, widget):
        self.widget = widget
        for log in self.logs:
            self.widget.insert(tk.END, log + "\n")


DEBUG = DebugLogger()


# ============================================================================
# FIELD ANALYZER - Determines UI type from data
# ============================================================================

@dataclass
class FieldInfo:
    """Information about a field derived from actual data"""
    name: str
    is_array: bool = False
    is_object: bool = False
    is_number: bool = False
    is_boolean: bool = False
    unique_values: Set[str] = None  # For dropdowns
    all_values_short: bool = False  # All values < 20 chars
    sample_value: Any = None

    def __post_init__(self):
        if self.unique_values is None:
            self.unique_values = set()


class FieldAnalyzer:
    """Analyzes existing data to determine optimal UI widgets"""

    @staticmethod
    def analyze_data(items: List[Dict]) -> Dict[str, FieldInfo]:
        """Analyze all items to determine field characteristics"""
        DEBUG.log(f"Analyzing {len(items)} items")

        field_map: Dict[str, FieldInfo] = {}

        for item in items:
            for field_name, value in item.items():
                if field_name not in field_map:
                    field_map[field_name] = FieldInfo(name=field_name)

                field_info = field_map[field_name]

                # Determine type
                if isinstance(value, list):
                    field_info.is_array = True
                    field_info.sample_value = value
                elif isinstance(value, dict):
                    field_info.is_object = True
                    field_info.sample_value = value
                elif isinstance(value, bool):
                    field_info.is_boolean = True
                elif isinstance(value, (int, float)):
                    field_info.is_number = True
                elif isinstance(value, str):
                    # Track unique string values
                    field_info.unique_values.add(value)
                    if not field_info.sample_value:
                        field_info.sample_value = value

        # Determine if fields should be dropdowns (all values < 20 chars)
        for field_name, field_info in field_map.items():
            if field_info.unique_values:
                all_short = all(len(str(v)) < 20 for v in field_info.unique_values)
                field_info.all_values_short = all_short

                DEBUG.log(f"  {field_name}: {len(field_info.unique_values)} unique values, "
                          f"all_short={all_short}")

        return field_map


# ============================================================================
# DATA LOADER
# ============================================================================

class DataLoader:
    def __init__(self, base_path: str = None):
        if base_path is None:
            base_path = Path(__file__).parent.parent / "Game-1-modular"

        self.base_path = Path(base_path)
        DEBUG.log(f"Base path: {self.base_path}")

        self.data_cache: Dict[str, List[Dict]] = {}
        self.field_analysis: Dict[str, Dict[str, FieldInfo]] = {}

    def load_all(self):
        DEBUG.log("=" * 60)
        DEBUG.log("LOADING ALL DATA")
        DEBUG.log("=" * 60)

        try:
            self._load_items()
            self._load_materials()
            self._load_recipes()
            self._load_placements()
            self._load_skills()
            self._load_quests()
            self._load_npcs()
            self._load_titles()
            self._load_classes()
            self._load_enemies()
            self._load_resource_nodes()

            # Analyze all loaded data
            self._analyze_all_fields()

            DEBUG.success("All data loaded and analyzed")
            self._print_summary()
        except Exception as e:
            DEBUG.error("Failed to load data", e)

    def _analyze_all_fields(self):
        """Analyze fields for each JSON type"""
        DEBUG.log("\n--- ANALYZING FIELDS ---")
        for json_type, items in self.data_cache.items():
            if items:
                self.field_analysis[json_type] = FieldAnalyzer.analyze_data(items)
                DEBUG.log(f"{json_type}: {len(self.field_analysis[json_type])} fields analyzed")

    def _print_summary(self):
        DEBUG.log("=" * 60)
        DEBUG.log("LOAD SUMMARY")
        for json_type, items in self.data_cache.items():
            DEBUG.log(f"{json_type}: {len(items)} items")
        DEBUG.log("=" * 60)

    def _is_metadata(self, obj: Dict) -> bool:
        """Check if object is metadata"""
        metadata_keys = {"version", "discipline", "description", "totalItems",
                         "totalRecipes", "note", "tier_limits"}
        id_fields = {"itemId", "materialId", "recipeId", "skillId", "quest_id",
                     "npc_id", "titleId", "classId", "enemyId", "nodeId"}

        obj_keys = set(obj.keys())
        return not bool(obj_keys & id_fields) and bool(obj_keys & metadata_keys)

    def _load_json_file(self, file_path: Path) -> List[Dict]:
        DEBUG.log(f"Loading: {file_path}")

        try:
            if not file_path.exists():
                DEBUG.log(f"  NOT FOUND")
                return []

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            all_items = []

            if isinstance(data, dict):
                for key, value in data.items():
                    if key == "metadata":
                        continue

                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict) and not self._is_metadata(item):
                                all_items.append(item)
                    elif isinstance(value, dict) and not self._is_metadata(value):
                        all_items.append(value)

            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and not self._is_metadata(item):
                        all_items.append(item)

            DEBUG.log(f"  Loaded {len(all_items)} items")
            return all_items

        except Exception as e:
            DEBUG.error(f"  Error loading", e)
            return []

    def _load_items(self):
        DEBUG.log("\n--- ITEMS ---")
        item_files = [
            "items-alchemy-1.JSON",
            "items-materials-1.JSON",
            "items-refining-1.JSON",
            "items-smithing-2.JSON",
            "items-tools-1.JSON"
        ]

        items_dir = self.base_path / "items.JSON"
        all_items = []

        if items_dir.exists():
            for filename in item_files:
                items = self._load_json_file(items_dir / filename)
                all_items.extend(items)

        self.data_cache["items"] = all_items
        DEBUG.log(f"Total items: {len(all_items)}")

    def _load_materials(self):
        DEBUG.log("\n--- MATERIALS ---")

        # Load from specific file
        materials_file = self.base_path / "items.JSON" / "items-materials-1.JSON"
        materials = self._load_json_file(materials_file)

        self.data_cache["materials"] = materials
        DEBUG.log(f"Total materials: {len(materials)}")

    def _load_recipes(self):
        DEBUG.log("\n--- RECIPES ---")
        recipes_dir = self.base_path / "recipes.JSON"
        all_recipes = []

        if recipes_dir.exists():
            for file_path in recipes_dir.glob("recipes-*.JSON"):
                all_recipes.extend(self._load_json_file(file_path))

        self.data_cache["recipes"] = all_recipes
        DEBUG.log(f"Total recipes: {len(all_recipes)}")

    def _load_placements(self):
        DEBUG.log("\n--- PLACEMENTS ---")
        placements_dir = self.base_path / "placements.JSON"
        all_placements = []

        if placements_dir.exists():
            for file_path in placements_dir.glob("placements-*.JSON"):
                all_placements.extend(self._load_json_file(file_path))

        self.data_cache["placements"] = all_placements
        DEBUG.log(f"Total placements: {len(all_placements)}")

    def _load_skills(self):
        DEBUG.log("\n--- SKILLS ---")
        skills_dir = self.base_path / "Skills"
        all_skills = []

        if skills_dir.exists():
            for file_path in skills_dir.glob("*.JSON"):
                all_skills.extend(self._load_json_file(file_path))

        self.data_cache["skills"] = all_skills
        DEBUG.log(f"Total skills: {len(all_skills)}")

    def _load_quests(self):
        DEBUG.log("\n--- QUESTS ---")
        quest_file = self.base_path / "progression" / "quests-1.JSON"
        self.data_cache["quests"] = self._load_json_file(quest_file)

    def _load_npcs(self):
        DEBUG.log("\n--- NPCS ---")
        npc_file = self.base_path / "progression" / "npcs-1.JSON"
        self.data_cache["npcs"] = self._load_json_file(npc_file)

    def _load_titles(self):
        DEBUG.log("\n--- TITLES ---")
        title_file = self.base_path / "progression" / "titles-1.JSON"
        self.data_cache["titles"] = self._load_json_file(title_file)

    def _load_classes(self):
        DEBUG.log("\n--- CLASSES ---")
        class_file = self.base_path / "progression" / "classes-1.JSON"
        self.data_cache["classes"] = self._load_json_file(class_file)

    def _load_enemies(self):
        DEBUG.log("\n--- ENEMIES ---")
        defs_dir = self.base_path / "Definitions.JSON"

        # Try both filenames
        enemy_file = defs_dir / "hostiles-1.JSON"
        enemies = self._load_json_file(enemy_file)

        if not enemies:
            enemy_file = defs_dir / "hostile-entities-1.JSON"
            enemies = self._load_json_file(enemy_file)

        self.data_cache["enemies"] = enemies

    def _load_resource_nodes(self):
        DEBUG.log("\n--- RESOURCE NODES ---")
        node_file = self.base_path / "Definitions.JSON" / "resource-nodes-1.JSON"
        self.data_cache["resource_nodes"] = self._load_json_file(node_file)

    def get_all(self, json_type: str) -> List[Dict]:
        return self.data_cache.get(json_type, [])

    def get_field_info(self, json_type: str) -> Dict[str, FieldInfo]:
        return self.field_analysis.get(json_type, {})


# ============================================================================
# GUI
# ============================================================================

class UnifiedJSONCreatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("JSON Creator - Dynamic Adaptive UI")
        self.root.geometry("1600x1000")

        self.data_loader = DataLoader()
        self.data_loader.load_all()

        self.current_json_type = "items"
        self.current_data = {}
        self.field_widgets = {}
        self.is_editing_existing = False

        self._create_ui()
        self._on_type_changed()

    def _create_ui(self):
        # Top bar
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="JSON Type:", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)

        json_types = ["items", "materials", "recipes", "placements", "skills", "quests",
                      "npcs", "titles", "classes", "enemies", "resource_nodes"]
        self.type_combo = ttk.Combobox(top_frame, values=json_types, state="readonly", width=20)
        self.type_combo.set("items")
        self.type_combo.pack(side=tk.LEFT, padx=5)
        self.type_combo.bind("<<ComboboxSelected>>", lambda e: self._on_type_changed())

        ttk.Button(top_frame, text="New", command=self._new_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Save", command=self._save_json).pack(side=tk.LEFT, padx=5)

        # Main content
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left - Form
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        ttk.Label(left_frame, text="JSON Editor", font=("Arial", 11, "bold")).pack(pady=5)

        form_canvas = tk.Canvas(left_frame)
        form_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=form_canvas.yview)
        self.form_frame = ttk.Frame(form_canvas)

        form_canvas.configure(yscrollcommand=form_scrollbar.set)
        form_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        form_canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        self.form_frame.bind("<Configure>", lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))

        # Middle - Library
        middle_frame = ttk.Frame(main_paned)
        main_paned.add(middle_frame, weight=1)

        ttk.Label(middle_frame, text="Existing JSONs", font=("Arial", 11, "bold")).pack(pady=5)

        search_frame = ttk.Frame(middle_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self._filter_library())
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        library_scroll = ttk.Scrollbar(middle_frame)
        library_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.library_listbox = tk.Listbox(middle_frame, yscrollcommand=library_scroll.set)
        self.library_listbox.pack(fill=tk.BOTH, expand=True, padx=5)
        library_scroll.config(command=self.library_listbox.yview)
        self.library_listbox.bind("<<ListboxSelect>>", self._on_library_select)

        # Right - Preview
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        ttk.Label(right_frame, text="JSON Preview", font=("Arial", 11, "bold")).pack(pady=5)

        self.preview_text = scrolledtext.ScrolledText(right_frame, height=30, wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bottom - Debug Console
        debug_frame = ttk.Frame(self.root)
        debug_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

        ttk.Label(debug_frame, text="Debug Console:", font=("Arial", 10, "bold")).pack(anchor=tk.W)

        self.debug_text = scrolledtext.ScrolledText(debug_frame, height=6, wrap=tk.WORD)
        self.debug_text.pack(fill=tk.BOTH, expand=True)

        DEBUG.attach_widget(self.debug_text)

    def _on_type_changed(self):
        self.current_json_type = self.type_combo.get()
        DEBUG.log(f"Type changed: {self.current_json_type}")
        self._build_dynamic_form()
        self._update_library()
        self._new_json()

    def _build_dynamic_form(self):
        """Build form dynamically based on analyzed data"""
        DEBUG.log("Building dynamic form")

        for widget in self.form_frame.winfo_children():
            widget.destroy()

        self.field_widgets = {}

        # Get field analysis for this type
        field_info_map = self.data_loader.get_field_info(self.current_json_type)

        if not field_info_map:
            DEBUG.log("  No field info available")
            return

        # Sort fields: ID first, then alphabetically
        id_fields = {"itemId", "materialId", "recipeId", "skillId", "quest_id",
                     "npc_id", "titleId", "classId", "enemyId", "nodeId"}

        sorted_fields = []
        for field_name in field_info_map:
            if field_name in id_fields:
                sorted_fields.insert(0, field_name)
            else:
                sorted_fields.append(field_name)

        # Build UI for each field
        row = 0
        for field_name in sorted_fields:
            field_info = field_info_map[field_name]

            # Label
            label = ttk.Label(self.form_frame, text=field_name, font=("Arial", 9, "bold"))
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)

            # Widget based on field type
            widget = self._create_dynamic_widget(field_name, field_info)
            widget.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)

            self.field_widgets[field_name] = widget
            row += 1

        self.form_frame.grid_columnconfigure(1, weight=1)
        DEBUG.log(f"Built {len(self.field_widgets)} dynamic fields")

    def _create_dynamic_widget(self, field_name: str, field_info: FieldInfo) -> tk.Widget:
        """Create appropriate widget based on field analysis"""

        # ARRAY FIELDS - Tag management interface
        if field_info.is_array:
            return self._create_tag_widget(field_name, field_info)

        # OBJECT FIELDS - JSON text editor
        elif field_info.is_object:
            frame = ttk.Frame(self.form_frame)
            text = scrolledtext.ScrolledText(frame, height=4, width=40)
            text.pack(fill=tk.BOTH, expand=True)
            text.bind("<KeyRelease>", lambda e: self._update_preview())
            return frame

        # BOOLEAN FIELDS - Checkbox
        elif field_info.is_boolean:
            var = tk.BooleanVar(value=False)
            widget = ttk.Checkbutton(self.form_frame, variable=var, command=self._update_preview)
            widget.var = var
            return widget

        # NUMBER FIELDS - Entry
        elif field_info.is_number:
            widget = ttk.Entry(self.form_frame, width=40)
            widget.bind("<KeyRelease>", lambda e: self._update_preview())
            return widget

        # STRING FIELDS WITH SHORT VALUES - Dropdown + Custom
        elif field_info.all_values_short and len(field_info.unique_values) > 0:
            return self._create_dropdown_with_custom(field_name, field_info)

        # OTHER STRING FIELDS - Plain entry
        else:
            widget = ttk.Entry(self.form_frame, width=40)
            widget.bind("<KeyRelease>", lambda e: self._update_preview())
            return widget

    def _create_dropdown_with_custom(self, field_name: str, field_info: FieldInfo) -> tk.Widget:
        """Dropdown with custom entry button"""
        frame = ttk.Frame(self.form_frame)

        # Dropdown with sorted values
        values = sorted(list(field_info.unique_values))
        combo = ttk.Combobox(frame, values=values, width=30)
        combo.pack(side=tk.LEFT, padx=(0, 5))
        combo.bind("<<ComboboxSelected>>", lambda e: self._update_preview())

        # Custom button
        def enable_custom():
            combo.config(state="normal")
            combo.delete(0, tk.END)
            combo.focus()

        ttk.Button(frame, text="Custom", command=enable_custom, width=8).pack(side=tk.LEFT)

        # Store combo reference
        frame.combo = combo

        return frame

    def _create_tag_widget(self, field_name: str, field_info: FieldInfo) -> tk.Widget:
        """Tag management widget for arrays"""
        frame = ttk.Frame(self.form_frame)

        # Tags display frame
        tags_frame = ttk.Frame(frame)
        tags_frame.pack(fill=tk.X, pady=(0, 5))

        # Store tags as list
        frame.tags = []
        frame.tag_widgets = []

        def add_tag():
            tag_value = entry.get().strip()
            if tag_value and tag_value not in frame.tags:
                frame.tags.append(tag_value)

                # Create tag button
                tag_btn = ttk.Button(tags_frame, text=tag_value,
                                     command=lambda t=tag_value: remove_tag(t))
                tag_btn.pack(side=tk.LEFT, padx=2, pady=2)
                frame.tag_widgets.append(tag_btn)

                entry.delete(0, tk.END)
                self._update_preview()

        def remove_tag(tag_value):
            if tag_value in frame.tags:
                frame.tags.remove(tag_value)
                # Rebuild tag widgets
                for widget in frame.tag_widgets:
                    widget.destroy()
                frame.tag_widgets.clear()

                for tag in frame.tags:
                    tag_btn = ttk.Button(tags_frame, text=tag,
                                         command=lambda t=tag: remove_tag(t))
                    tag_btn.pack(side=tk.LEFT, padx=2, pady=2)
                    frame.tag_widgets.append(tag_btn)

                self._update_preview()

        # Add tag interface
        add_frame = ttk.Frame(frame)
        add_frame.pack(fill=tk.X)

        entry = ttk.Entry(add_frame, width=30)
        entry.pack(side=tk.LEFT, padx=(0, 5))
        entry.bind("<Return>", lambda e: add_tag())

        ttk.Button(add_frame, text="Add", command=add_tag, width=8).pack(side=tk.LEFT)

        return frame

    def _update_library(self):
        self.library_listbox.delete(0, tk.END)
        items = self.data_loader.get_all(self.current_json_type)

        id_fields = {
            "items": "itemId", "materials": "materialId", "recipes": "recipeId",
            "placements": "recipeId", "skills": "skillId", "quests": "quest_id",
            "npcs": "npc_id", "titles": "titleId", "classes": "classId",
            "enemies": "enemyId", "resource_nodes": "nodeId",
        }
        id_field = id_fields.get(self.current_json_type, "id")

        for item in items:
            item_id = item.get(id_field, "Unknown")
            name = item.get("name", item.get("title", ""))
            display = f"{item_id}" + (f" - {name}" if name else "")
            self.library_listbox.insert(tk.END, display)

    def _filter_library(self):
        search_term = self.search_var.get().lower()
        self.library_listbox.delete(0, tk.END)
        items = self.data_loader.get_all(self.current_json_type)

        id_fields = {
            "items": "itemId", "materials": "materialId", "recipes": "recipeId",
            "placements": "recipeId", "skills": "skillId", "quests": "quest_id",
            "npcs": "npc_id", "titles": "titleId", "classes": "classId",
            "enemies": "enemyId", "resource_nodes": "nodeId",
        }
        id_field = id_fields.get(self.current_json_type, "id")

        for item in items:
            item_id = item.get(id_field, "Unknown")
            name = item.get("name", item.get("title", ""))
            display = f"{item_id}" + (f" - {name}" if name else "")
            if search_term in display.lower():
                self.library_listbox.insert(tk.END, display)

    def _on_library_select(self, event):
        selection = self.library_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        items = self.data_loader.get_all(self.current_json_type)

        # Filter if searching
        search_term = self.search_var.get().lower()
        if search_term:
            id_fields = {
                "items": "itemId", "materials": "materialId", "recipes": "recipeId",
                "placements": "recipeId", "skills": "skillId", "quests": "quest_id",
                "npcs": "npc_id", "titles": "titleId", "classes": "classId",
                "enemies": "enemyId", "resource_nodes": "nodeId",
            }
            id_field = id_fields.get(self.current_json_type, "id")

            filtered = []
            for item in items:
                item_id = item.get(id_field, "Unknown")
                name = item.get("name", item.get("title", ""))
                display = f"{item_id}" + (f" - {name}" if name else "")
                if search_term in display.lower():
                    filtered.append(item)

            if index < len(filtered):
                selected_item = filtered[index]
            else:
                return
        else:
            if index < len(items):
                selected_item = items[index]
            else:
                return

        self._load_json_to_form(selected_item)

    def _load_json_to_form(self, data: Dict):
        """Load ALL fields from JSON"""
        DEBUG.log(f"Loading item")
        self.current_data = data
        self.is_editing_existing = True

        # Clear all widgets
        for widget in self.field_widgets.values():
            self._clear_widget(widget)

        # Populate with data
        for field_name, value in data.items():
            if field_name in self.field_widgets:
                self._set_widget_value(self.field_widgets[field_name], value)

        self._update_preview()

    def _clear_widget(self, widget):
        """Clear a widget"""
        if hasattr(widget, 'combo'):  # Dropdown with custom
            widget.combo.set("")
        elif hasattr(widget, 'tags'):  # Tag widget
            widget.tags.clear()
            for tag_widget in widget.tag_widgets:
                tag_widget.destroy()
            widget.tag_widgets.clear()
        elif isinstance(widget, ttk.Entry):
            widget.delete(0, tk.END)
        elif isinstance(widget, ttk.Checkbutton):
            widget.var.set(False)
        elif isinstance(widget, ttk.Frame):
            # Check for text widget inside
            for child in widget.winfo_children():
                if isinstance(child, scrolledtext.ScrolledText):
                    child.delete("1.0", tk.END)

    def _set_widget_value(self, widget, value):
        """Set widget value"""
        if hasattr(widget, 'combo'):  # Dropdown
            widget.combo.set(str(value))
        elif hasattr(widget, 'tags'):  # Tag widget
            if isinstance(value, list):
                widget.tags = [str(v) for v in value]
                # Recreate tag buttons
                tags_frame = widget.winfo_children()[0]
                for tag in widget.tags:
                    tag_btn = ttk.Button(tags_frame, text=tag,
                                         command=lambda t=tag: self._remove_tag_from_widget(widget, t))
                    tag_btn.pack(side=tk.LEFT, padx=2, pady=2)
                    widget.tag_widgets.append(tag_btn)
        elif isinstance(widget, ttk.Entry):
            widget.insert(0, str(value))
        elif isinstance(widget, ttk.Checkbutton):
            widget.var.set(bool(value))
        elif isinstance(widget, ttk.Frame):
            for child in widget.winfo_children():
                if isinstance(child, scrolledtext.ScrolledText):
                    if isinstance(value, (dict, list)):
                        child.insert("1.0", json.dumps(value, indent=2))
                    else:
                        child.insert("1.0", str(value))

    def _remove_tag_from_widget(self, widget, tag):
        """Helper to remove tag"""
        if tag in widget.tags:
            widget.tags.remove(tag)
            for tag_widget in widget.tag_widgets:
                tag_widget.destroy()
            widget.tag_widgets.clear()

            tags_frame = widget.winfo_children()[0]
            for t in widget.tags:
                tag_btn = ttk.Button(tags_frame, text=t,
                                     command=lambda tt=t: self._remove_tag_from_widget(widget, tt))
                tag_btn.pack(side=tk.LEFT, padx=2, pady=2)
                widget.tag_widgets.append(tag_btn)

            self._update_preview()

    def _new_json(self):
        self.current_data = {}
        self.is_editing_existing = False

        for widget in self.field_widgets.values():
            self._clear_widget(widget)

        self.preview_text.delete("1.0", tk.END)

    def _collect_form_data(self) -> Dict:
        """Collect ALL data from form"""
        if self.is_editing_existing:
            data = dict(self.current_data)
        else:
            data = {}

        for field_name, widget in self.field_widgets.items():
            if hasattr(widget, 'combo'):  # Dropdown
                value = widget.combo.get()
                if value:
                    data[field_name] = value
                elif field_name in data:
                    del data[field_name]

            elif hasattr(widget, 'tags'):  # Tag widget
                if widget.tags:
                    data[field_name] = widget.tags
                elif field_name in data:
                    del data[field_name]

            elif isinstance(widget, ttk.Entry):
                value = widget.get()
                if value:
                    # Try to convert to number
                    try:
                        if '.' in value:
                            data[field_name] = float(value)
                        else:
                            data[field_name] = int(value)
                    except ValueError:
                        data[field_name] = value
                elif field_name in data:
                    del data[field_name]

            elif isinstance(widget, ttk.Checkbutton):
                data[field_name] = widget.var.get()

            elif isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, scrolledtext.ScrolledText):
                        value = child.get("1.0", tk.END).strip()
                        if value:
                            try:
                                data[field_name] = json.loads(value)
                            except json.JSONDecodeError:
                                data[field_name] = value
                        else:
                            # Auto-add empty object/array
                            field_info_map = self.data_loader.get_field_info(self.current_json_type)
                            if field_name in field_info_map:
                                if field_info_map[field_name].is_object:
                                    data[field_name] = {}
                                elif field_info_map[field_name].is_array:
                                    data[field_name] = []

        return data

    def _update_preview(self):
        data = self._collect_form_data()
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", json.dumps(data, indent=2))

    def _save_json(self):
        data = self._collect_form_data()

        # Determine file path (simplified - just use unified file)
        type_files = {
            "items": "items.JSON/items-unified.JSON",
            "materials": "items.JSON/items-materials-1.JSON",
            "recipes": "recipes.JSON/recipes-unified.JSON",
            "placements": "placements.JSON/placements-unified.JSON",
            "skills": "Skills/skills-unified.JSON",
            "quests": "progression/quests-1.JSON",
            "npcs": "progression/npcs-1.JSON",
            "titles": "progression/titles-1.JSON",
            "classes": "progression/classes-1.JSON",
            "enemies": "Definitions.JSON/hostiles-1.JSON",
            "resource_nodes": "Definitions.JSON/resource-nodes-1.JSON",
        }

        file_path = self.data_loader.base_path / type_files.get(self.current_json_type,
                                                                f"{self.current_json_type}.JSON")

        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)

                if isinstance(existing, list):
                    existing.append(data)
                elif isinstance(existing, dict):
                    for key in existing:
                        if key != "metadata" and isinstance(existing[key], list):
                            existing[key].append(data)
                            break
                else:
                    existing = [data]
            else:
                existing = {
                    "metadata": {"version": "1.0"},
                    self.current_json_type: [data]
                }

            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2)

            DEBUG.success(f"Saved!")
            messagebox.showinfo("Success", "Saved!")

            self.data_loader.load_all()
            self._update_library()

        except Exception as e:
            DEBUG.error("Save failed", e)
            messagebox.showerror("Error", f"Failed:\n{str(e)}")


def main():
    root = tk.Tk()
    app = UnifiedJSONCreatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()