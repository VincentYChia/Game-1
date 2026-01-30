"""
Icon Selection Tool
Displays all generated icon variations and allows selection for replacement or deferred decision

Requirements:
- pip install pillow

Usage:
1. Run script
2. Browse through items using Next/Previous buttons
3. Click on an image to select it (1 for immediate replacement, multiple for deferred)
4. Choose "Replace Placeholder" for immediate replacement or "Save for Later" for deferred decision
"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from pathlib import Path
import re
import json
import shutil
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
# Catalog is now co-located with the icon generator in assets/icons/
CATALOG_PATH = SCRIPT_DIR / "icons" / "ITEM_CATALOG_FOR_ICONS.md"
DEFERRED_DECISIONS_FILE = SCRIPT_DIR / "deferred_icon_decisions.json"
CUSTOM_ICONS_DIR = SCRIPT_DIR / "custom_icons"
REMAP_REGISTRY_FILE = SCRIPT_DIR / "icon_remap_registry.json"

# Ensure custom icons directory exists
CUSTOM_ICONS_DIR.mkdir(exist_ok=True)

# Resource name mapping (catalog name -> file name)
# Some resources were generated with different file names
RESOURCE_NAME_MAP = {
    'copper_vein': 'copper_ore_node',
    'iron_deposit': 'iron_ore_node',
    'limestone_outcrop': 'limestone_node',
    'granite_formation': 'granite_node',
    'mithril_cache': 'mithril_ore_node',
    'obsidian_flow': 'obsidian_node',
    'steel_node': 'steel_ore_node',
}

# Placeholder directories
PLACEHOLDER_BASE = SCRIPT_DIR

# Generation cycle directories to scan
# Scan for ALL generation cycle patterns
GENERATION_CYCLES = []
for pattern in ["icons-generation-cycle-*", "icons-generated-cycle-*"]:
    for cycle_dir in SCRIPT_DIR.glob(pattern):
        GENERATION_CYCLES.append(cycle_dir)
GENERATION_CYCLES = sorted(set(GENERATION_CYCLES))  # Remove duplicates and sort

# ============================================================================
# CATALOG PARSING
# ============================================================================

def parse_catalog(filepath):
    """Parse ITEM_CATALOG_FOR_ICONS.md and return item metadata"""
    items = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    sections = re.split(r'\n### ', content)

    for section in sections[1:]:
        lines = section.strip().split('\n')
        if not lines:
            continue

        item_name = lines[0].strip()
        item_data = {
            'name': item_name,
            'category': '',
            'type': '',
            'subtype': '',
            'narrative': ''
        }

        for line in lines[1:]:
            line = line.strip()
            if line.startswith('- **Category**:'):
                item_data['category'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Type**:'):
                item_data['type'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Subtype**:'):
                item_data['subtype'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Narrative**:'):
                item_data['narrative'] = line.split(':', 1)[1].strip()

        items[item_name] = item_data

    return items

def categorize_item(item_data):
    """Determine folder structure based on item properties

    Returns tuple: (base_folder, subfolder)
    """
    category = item_data.get('category', '').lower()
    item_type = item_data.get('type', '').lower()

    # Non-item entities
    if category == 'enemy':
        return ('enemies', None)
    if category == 'resource':
        return ('resources', None)
    if category == 'title':
        return ('titles', None)
    if category == 'skill':
        return ('skills', None)
    if category == 'npc':
        return ('npcs', None)
    if category == 'quest':
        return ('quests', None)
    if category == 'class':
        return ('classes', None)

    # Item entities - all go under 'items' base folder
    if category == 'equipment':
        if item_type in ['weapon', 'sword', 'axe', 'mace', 'dagger', 'spear', 'bow', 'staff', 'shield']:
            return ('items', 'weapons')
        elif item_type in ['armor']:
            return ('items', 'armor')
        elif item_type in ['tool']:
            return ('items', 'tools')
        elif item_type in ['accessory']:
            return ('items', 'accessories')
        else:
            return ('items', 'weapons')

    if category == 'station':
        return ('items', 'stations')
    if category == 'device':
        return ('items', 'devices')
    if category == 'consumable':
        return ('items', 'consumables')

    # Default: materials
    return ('items', 'materials')

# ============================================================================
# FILE SCANNING
# ============================================================================

def find_all_icon_versions(item_name, base_folder, subfolder):
    """Find all generated versions of an icon across all generation cycles

    Checks both the original catalog name and any mapped file names from RESOURCE_NAME_MAP.
    This ensures icons generated with alternate names are still found.

    Returns list of dicts with 'path', 'cycle', 'version' keys
    """
    versions = []

    # Build list of names to check: original + mapped (if exists)
    names_to_check = [item_name]
    if item_name in RESOURCE_NAME_MAP:
        names_to_check.append(RESOURCE_NAME_MAP[item_name])

    # Check each generation cycle
    for cycle_dir in GENERATION_CYCLES:
        # Check generated_icons, generated_icons-2, generated_icons-3, etc.
        for version_dir in cycle_dir.glob("generated_icons*"):
            # Determine version number from folder name
            if version_dir.name == "generated_icons":
                version_num = 1
            else:
                match = re.search(r'-(\d+)$', version_dir.name)
                if match:
                    version_num = int(match.group(1))
                else:
                    continue

            # Try each possible name
            for check_name in names_to_check:
                if version_num == 1 and version_dir.name == "generated_icons":
                    expected_filename = f"{check_name}.png"
                else:
                    expected_filename = f"{check_name}-{version_num}.png"

                # Build path to icon
                if subfolder:
                    icon_path = version_dir / base_folder / subfolder / expected_filename
                else:
                    icon_path = version_dir / base_folder / expected_filename

                if icon_path.exists():
                    # Add label indicating if this used a mapped name
                    label = f"{cycle_dir.name}/v{version_num}"
                    if check_name != item_name:
                        label += f" ({check_name})"

                    versions.append({
                        'path': icon_path,
                        'cycle': cycle_dir.name,
                        'version': version_num,
                        'label': label,
                        'actual_name': check_name  # Track which name was found
                    })
                    break  # Found for this version, no need to check other names

    # Also check custom icons directory (for remapped PNGs)
    custom_path = CUSTOM_ICONS_DIR / f"{item_name}.png"
    if custom_path.exists():
        versions.append({
            'path': custom_path,
            'cycle': 'custom',
            'version': 0,
            'label': 'Custom (Remapped)',
            'actual_name': item_name
        })

    return sorted(versions, key=lambda x: (x['cycle'], x['version']))

def get_placeholder_path(item_name, base_folder, subfolder):
    """Get the path to the current placeholder image"""
    if subfolder:
        placeholder_path = PLACEHOLDER_BASE / base_folder / subfolder / f"{item_name}.png"
    else:
        placeholder_path = PLACEHOLDER_BASE / base_folder / f"{item_name}.png"

    return placeholder_path if placeholder_path.exists() else None

# ============================================================================
# DEFERRED DECISIONS
# ============================================================================

def load_deferred_decisions():
    """Load previously deferred decisions from JSON file"""
    if DEFERRED_DECISIONS_FILE.exists():
        with open(DEFERRED_DECISIONS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_deferred_decisions(decisions):
    """Save deferred decisions to JSON file"""
    with open(DEFERRED_DECISIONS_FILE, 'w') as f:
        json.dump(decisions, f, indent=2)

# ============================================================================
# PNG REMAPPING
# ============================================================================

def load_remap_registry():
    """Load the icon remap registry"""
    if REMAP_REGISTRY_FILE.exists():
        with open(REMAP_REGISTRY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_remap_registry(registry):
    """Save the icon remap registry"""
    with open(REMAP_REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2)

def remap_icon(source_path, target_id):
    """Remap a PNG to a different entity ID

    Args:
        source_path: Path to the source PNG file
        target_id: The ID of the entity to map this icon to

    Returns:
        Path to the remapped icon in custom_icons directory
    """
    # Ensure custom icons directory exists
    CUSTOM_ICONS_DIR.mkdir(exist_ok=True)

    # Copy and rename the PNG to custom_icons/target_id.png
    dest_path = CUSTOM_ICONS_DIR / f"{target_id}.png"
    shutil.copy2(source_path, dest_path)

    # Update registry
    registry = load_remap_registry()
    registry[target_id] = {
        'source_path': str(source_path),
        'remapped_at': datetime.now().isoformat(),
        'target_id': target_id
    }
    save_remap_registry(registry)

    return dest_path

# ============================================================================
# GUI APPLICATION
# ============================================================================

class IconSelectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Icon Selection Tool (Enhanced)")
        self.root.geometry("1500x950")

        # Load catalog
        print("Loading catalog...")
        self.catalog = parse_catalog(CATALOG_PATH)
        self.all_items = list(self.catalog.keys())
        self.filtered_items = self.all_items.copy()  # For search filtering
        self.current_index = 0

        # Load deferred decisions
        self.deferred = load_deferred_decisions()

        # Track selections
        self.selected_versions = []

        # Search variable
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)

        # Build UI
        self.build_ui()

        # Load first item
        if self.filtered_items:
            self.load_item(0)

    def build_ui(self):
        """Build the user interface"""
        # Search bar at the very top
        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)

        ttk.Label(search_frame, text="Search:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=50)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Label(search_frame, text="(Filter by ID or name)", font=("Arial", 9, "italic")).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Clear", command=lambda: self.search_var.set("")).pack(side=tk.LEFT, padx=5)

        # Top frame: Item info
        info_frame = ttk.Frame(self.root, padding="10")
        info_frame.pack(fill=tk.X)

        self.item_name_label = ttk.Label(info_frame, text="", font=("Arial", 16, "bold"))
        self.item_name_label.pack(anchor=tk.W)

        self.item_info_label = ttk.Label(info_frame, text="", font=("Arial", 10))
        self.item_info_label.pack(anchor=tk.W, pady=(5, 0))

        self.narrative_label = ttk.Label(info_frame, text="", font=("Arial", 10), wraplength=1450)
        self.narrative_label.pack(anchor=tk.W, pady=(5, 0))

        # Separator
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Middle frame: Images
        self.images_frame = ttk.Frame(self.root, padding="10")
        self.images_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbar for images
        canvas = tk.Canvas(self.images_frame)
        scrollbar = ttk.Scrollbar(self.images_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar.set)

        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Bottom frame: Controls
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(fill=tk.X)

        # Navigation
        nav_frame = ttk.Frame(control_frame)
        nav_frame.pack(side=tk.LEFT)

        ttk.Button(nav_frame, text="◀ Previous", command=self.prev_item).pack(side=tk.LEFT, padx=5)

        self.progress_label = ttk.Label(nav_frame, text="0/0")
        self.progress_label.pack(side=tk.LEFT, padx=10)

        ttk.Button(nav_frame, text="Next ▶", command=self.next_item).pack(side=tk.LEFT, padx=5)

        # Actions
        action_frame = ttk.Frame(control_frame)
        action_frame.pack(side=tk.RIGHT)

        self.replace_btn = ttk.Button(action_frame, text="✓ Replace Placeholder",
                                      command=self.replace_placeholder, state=tk.DISABLED)
        self.replace_btn.pack(side=tk.LEFT, padx=5)

        self.remap_btn = ttk.Button(action_frame, text="🔄 Remap to Different ID",
                                    command=self.remap_to_different_id, state=tk.DISABLED)
        self.remap_btn.pack(side=tk.LEFT, padx=5)

        self.defer_btn = ttk.Button(action_frame, text="⏸ Save for Later",
                                    command=self.defer_decision, state=tk.DISABLED)
        self.defer_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = ttk.Button(action_frame, text="✗ Clear Selection",
                                    command=self.clear_selection, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(action_frame, text="📋 View Deferred",
                  command=self.view_deferred).pack(side=tk.LEFT, padx=5)

    def on_search_change(self, *args):
        """Handle search input changes"""
        search_text = self.search_var.get().lower()

        if not search_text:
            self.filtered_items = self.all_items.copy()
        else:
            self.filtered_items = [
                item_id for item_id in self.all_items
                if search_text in item_id.lower() or
                   search_text in self.catalog[item_id].get('name', '').lower()
            ]

        # Reset to first item in filtered list
        self.current_index = 0
        if self.filtered_items:
            self.load_item(0)
        else:
            # Clear display if no matches
            self.item_name_label.config(text="No matches found")
            self.item_info_label.config(text="")
            self.narrative_label.config(text="")
            self.progress_label.config(text="0/0")
            # Clear images
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()

    def load_item(self, index):
        """Load and display an item's icons"""
        if index < 0 or index >= len(self.filtered_items):
            return

        self.current_index = index
        item_name = self.filtered_items[index]
        item_data = self.catalog[item_name]

        # Update info labels
        self.item_name_label.config(text=item_name)
        self.item_info_label.config(
            text=f"Category: {item_data['category']}  |  Type: {item_data['type']}  |  Subtype: {item_data['subtype']}"
        )
        self.narrative_label.config(text=f"Narrative: {item_data['narrative']}")

        # Update progress
        self.progress_label.config(text=f"{index + 1}/{len(self.filtered_items)}")

        # Clear previous selections
        self.selected_versions = []
        self.update_buttons()

        # Get folder structure
        base_folder, subfolder = categorize_item(item_data)

        # Find all versions
        versions = find_all_icon_versions(item_name, base_folder, subfolder)
        placeholder_path = get_placeholder_path(item_name, base_folder, subfolder)

        # Clear images frame
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Add placeholder if exists
        if placeholder_path:
            self.add_image_tile(placeholder_path, "Current Placeholder", is_placeholder=True)

        # Add all versions
        if versions:
            for version_info in versions:
                self.add_image_tile(version_info['path'], version_info['label'], version_info=version_info)
        else:
            no_versions_label = ttk.Label(self.scrollable_frame,
                                         text="No generated versions found",
                                         font=("Arial", 12))
            no_versions_label.pack(pady=50)

    def add_image_tile(self, image_path, label, is_placeholder=False, version_info=None):
        """Add an image tile to the scrollable frame"""
        tile_frame = ttk.Frame(self.scrollable_frame, relief=tk.RAISED, borderwidth=2)
        tile_frame.pack(side=tk.LEFT, padx=10, pady=10)

        # Load and display image
        try:
            img = Image.open(image_path)

            # Resize to fit (max 300x300)
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            img_label = ttk.Label(tile_frame, image=photo)
            img_label.image = photo  # Keep reference
            img_label.pack()

            # Label
            text_label = ttk.Label(tile_frame, text=label, font=("Arial", 10, "bold"))
            text_label.pack(pady=(5, 0))

            # File size
            size_kb = image_path.stat().st_size / 1024
            size_label = ttk.Label(tile_frame, text=f"{size_kb:.1f} KB", font=("Arial", 8))
            size_label.pack()

            # Make clickable (if not placeholder)
            if not is_placeholder and version_info:
                tile_frame.config(cursor="hand2")
                tile_frame.bind("<Button-1>", lambda e: self.toggle_selection(tile_frame, version_info))
                img_label.bind("<Button-1>", lambda e: self.toggle_selection(tile_frame, version_info))
                text_label.bind("<Button-1>", lambda e: self.toggle_selection(tile_frame, version_info))
                size_label.bind("<Button-1>", lambda e: self.toggle_selection(tile_frame, version_info))

        except Exception as e:
            error_label = ttk.Label(tile_frame, text=f"Error loading\n{image_path.name}",
                                   font=("Arial", 10), foreground="red")
            error_label.pack(pady=20)

    def toggle_selection(self, tile_frame, version_info):
        """Toggle selection of an image"""
        if version_info in self.selected_versions:
            # Deselect
            self.selected_versions.remove(version_info)
            # Reset to default styling
            tile_frame.config(relief=tk.RAISED, borderwidth=2)
            # Remove highlight canvas if it exists
            if hasattr(tile_frame, '_highlight_canvas'):
                tile_frame._highlight_canvas.destroy()
                delattr(tile_frame, '_highlight_canvas')
        else:
            # Select
            self.selected_versions.append(version_info)
            # Make selection VERY visible
            tile_frame.config(relief=tk.SOLID, borderwidth=6)
            # Add bright background using a Canvas overlay
            self._highlight_tile(tile_frame)

        self.update_buttons()

    def _highlight_tile(self, tile_frame):
        """Add visual highlight to selected tile"""
        # Create a bright background frame
        highlight_frame = tk.Frame(tile_frame, background="#90EE90", bd=0)
        highlight_frame.place(x=0, y=0, relwidth=1, relheight=1)

        # Send to back so images show on top
        highlight_frame.lower()

        # Store reference so we can remove it later
        tile_frame._highlight_canvas = highlight_frame

    def update_buttons(self):
        """Update button states based on selection"""
        num_selected = len(self.selected_versions)

        if num_selected == 0:
            self.replace_btn.config(state=tk.DISABLED)
            self.remap_btn.config(state=tk.DISABLED)
            self.defer_btn.config(state=tk.DISABLED)
            self.clear_btn.config(state=tk.DISABLED)
        elif num_selected == 1:
            self.replace_btn.config(state=tk.NORMAL)
            self.remap_btn.config(state=tk.NORMAL)
            self.defer_btn.config(state=tk.DISABLED)
            self.clear_btn.config(state=tk.NORMAL)
        else:
            self.replace_btn.config(state=tk.DISABLED)
            self.remap_btn.config(state=tk.DISABLED)
            self.defer_btn.config(state=tk.NORMAL)
            self.clear_btn.config(state=tk.NORMAL)

    def clear_selection(self):
        """Clear all selections"""
        self.selected_versions = []
        self.load_item(self.current_index)  # Reload to reset visual state

    def replace_placeholder(self):
        """Replace placeholder with selected image"""
        if len(self.selected_versions) != 1:
            messagebox.showerror("Error", "Please select exactly one image to replace the placeholder.")
            return

        item_name = self.filtered_items[self.current_index]
        item_data = self.catalog[item_name]
        base_folder, subfolder = categorize_item(item_data)

        placeholder_path = get_placeholder_path(item_name, base_folder, subfolder)
        selected = self.selected_versions[0]

        if not placeholder_path:
            messagebox.showerror("Error", f"Placeholder not found for {item_name}")
            return

        # Confirm replacement
        response = messagebox.askyesno(
            "Confirm Replacement",
            f"Replace placeholder for {item_name}?\n\n"
            f"Source: {selected['label']}\n"
            f"Target: {placeholder_path.relative_to(SCRIPT_DIR)}"
        )

        if response:
            try:
                # Backup old placeholder (optional)
                backup_dir = SCRIPT_DIR / "replaced_placeholders"
                backup_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"{item_name}_{timestamp}.png"
                shutil.copy2(placeholder_path, backup_path)

                # Replace
                shutil.copy2(selected['path'], placeholder_path)

                messagebox.showinfo("Success", f"Placeholder replaced!\n\nBackup saved to:\n{backup_path.relative_to(SCRIPT_DIR)}")

                # Move to next item
                self.next_item()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to replace placeholder:\n{e}")

    def remap_to_different_id(self):
        """Remap the selected PNG to a different entity ID"""
        if len(self.selected_versions) != 1:
            messagebox.showerror("Error", "Please select exactly one image to remap.")
            return

        selected = self.selected_versions[0]
        source_path = selected['path']

        # Create search dialog for target ID
        search_dialog = RemapSearchDialog(self.root, self.all_items, self.catalog)
        target_id = search_dialog.result

        if not target_id:
            return  # User cancelled

        # Confirm remap
        response = messagebox.askyesno(
            "Confirm Remap",
            f"Remap this icon to a different entity?\n\n"
            f"From: {self.filtered_items[self.current_index]}\n"
            f"To: {target_id}\n\n"
            f"The image will be copied to: custom_icons/{target_id}.png"
        )

        if response:
            try:
                dest_path = remap_icon(source_path, target_id)
                messagebox.showinfo("Success",
                    f"Icon remapped successfully!\n\n"
                    f"New location: {dest_path.relative_to(SCRIPT_DIR)}\n\n"
                    f"This icon will now appear when viewing '{target_id}'")

                # Refresh display
                self.load_item(self.current_index)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to remap icon:\n{e}")

    def defer_decision(self):
        """Save multiple selections for later decision"""
        if len(self.selected_versions) < 2:
            messagebox.showerror("Error", "Please select at least 2 images to defer decision.")
            return

        item_name = self.filtered_items[self.current_index]

        # Store paths as strings (relative to SCRIPT_DIR)
        self.deferred[item_name] = {
            'item_data': self.catalog[item_name],
            'options': [
                {
                    'path': str(v['path'].relative_to(SCRIPT_DIR)) if v['path'].is_relative_to(SCRIPT_DIR) else str(v['path']),
                    'label': v['label']
                }
                for v in self.selected_versions
            ],
            'timestamp': datetime.now().isoformat()
        }

        save_deferred_decisions(self.deferred)

        messagebox.showinfo("Saved", f"Deferred decision for {item_name}\n{len(self.selected_versions)} options saved.")

        # Move to next item
        self.next_item()

    def view_deferred(self):
        """Show window with all deferred decisions"""
        if not self.deferred:
            messagebox.showinfo("No Deferred Decisions", "No deferred decisions saved yet.")
            return

        # Create new window
        deferred_window = tk.Toplevel(self.root)
        deferred_window.title("Deferred Decisions")
        deferred_window.geometry("600x400")

        # Listbox
        listbox = tk.Listbox(deferred_window, font=("Arial", 12))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for item_name, data in self.deferred.items():
            num_options = len(data['options'])
            listbox.insert(tk.END, f"{item_name} ({num_options} options)")

        # Buttons
        btn_frame = ttk.Frame(deferred_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def go_to_item():
            selection = listbox.curselection()
            if selection:
                item_name = list(self.deferred.keys())[selection[0]]
                if item_name in self.filtered_items:
                    index = self.filtered_items.index(item_name)
                    self.load_item(index)
                    deferred_window.destroy()
                else:
                    messagebox.showwarning("Not in Current Filter",
                        f"'{item_name}' is not in the current search results. Clear the search to see it.")

        def clear_deferred():
            selection = listbox.curselection()
            if selection:
                item_name = list(self.deferred.keys())[selection[0]]
                del self.deferred[item_name]
                save_deferred_decisions(self.deferred)
                listbox.delete(selection[0])

        ttk.Button(btn_frame, text="Go to Item", command=go_to_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear from List", command=clear_deferred).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=deferred_window.destroy).pack(side=tk.RIGHT, padx=5)

    def prev_item(self):
        """Go to previous item"""
        if self.current_index > 0:
            self.load_item(self.current_index - 1)

    def next_item(self):
        """Go to next item"""
        if self.current_index < len(self.filtered_items) - 1:
            self.load_item(self.current_index + 1)


# ============================================================================
# REMAP SEARCH DIALOG
# ============================================================================

class RemapSearchDialog:
    """Dialog for searching and selecting a target ID for remapping"""

    def __init__(self, parent, all_ids, catalog):
        self.result = None
        self.all_ids = all_ids
        self.catalog = catalog

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Target Entity ID")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Search frame
        search_frame = ttk.Frame(self.dialog, padding="10")
        search_frame.pack(fill=tk.X)

        ttk.Label(search_frame, text="Search for target ID:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search)

        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.focus()

        # Results frame
        results_frame = ttk.Frame(self.dialog, padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(results_frame, text="Matching entities:", font=("Arial", 10)).pack(anchor=tk.W)

        # Scrollable listbox
        scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(results_frame, font=("Arial", 10), yscrollcommand=scroll.set)
        scroll.config(command=self.listbox.yview)

        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Initially show all
        self.filtered_ids = all_ids.copy()
        self.update_listbox()

        # Buttons
        button_frame = ttk.Frame(self.dialog, padding="10")
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Select", command=self.on_select).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.RIGHT, padx=5)

        # Bind double-click
        self.listbox.bind('<Double-Button-1>', lambda e: self.on_select())

        # Wait for dialog to close
        self.dialog.wait_window()

    def on_search(self, *args):
        """Filter IDs based on search text"""
        search_text = self.search_var.get().lower()

        if not search_text:
            self.filtered_ids = self.all_ids.copy()
        else:
            self.filtered_ids = [
                item_id for item_id in self.all_ids
                if search_text in item_id.lower() or
                   search_text in self.catalog[item_id].get('name', '').lower()
            ]

        self.update_listbox()

    def update_listbox(self):
        """Update the listbox with filtered results"""
        self.listbox.delete(0, tk.END)
        for item_id in self.filtered_ids[:100]:  # Limit to 100 for performance
            name = self.catalog[item_id].get('name', 'Unnamed')
            category = self.catalog[item_id].get('category', 'unknown')
            self.listbox.insert(tk.END, f"{item_id} - {name} ({category})")

        if len(self.filtered_ids) > 100:
            self.listbox.insert(tk.END, f"... and {len(self.filtered_ids) - 100} more (refine search)")

    def on_select(self):
        """Handle selection"""
        selection = self.listbox.curselection()
        if selection:
            selected_text = self.listbox.get(selection[0])
            if not selected_text.startswith('...'):
                self.result = selected_text.split(' - ')[0]
                self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel"""
        self.result = None
        self.dialog.destroy()

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*70)
    print("ICON SELECTOR TOOL")
    print("="*70)

    print(f"\n📁 Assets: {SCRIPT_DIR}")
    print(f"📄 Catalog: {CATALOG_PATH}")

    # Check catalog exists
    if not CATALOG_PATH.exists():
        print(f"\n⚠ Error: Catalog not found at {CATALOG_PATH}")
        input("Press Enter to exit...")
        return

    # Find generation cycles
    print(f"\n🔍 Scanning for generation cycles...")
    if not GENERATION_CYCLES:
        print("⚠ Warning: No generation cycles found")
        print("   Looking for: icons-generation-cycle-*/generated_icons*")
    else:
        print(f"✓ Found {len(GENERATION_CYCLES)} generation cycle(s):")
        for cycle in GENERATION_CYCLES:
            version_dirs = list(cycle.glob("generated_icons*"))
            print(f"  - {cycle.name}: {len(version_dirs)} version folder(s)")

    print("\n🚀 Starting GUI...")

    root = tk.Tk()
    app = IconSelectorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
