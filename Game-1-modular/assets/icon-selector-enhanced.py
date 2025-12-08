"""
Enhanced Icon Selection Tool
Displays all generated icon variations with search and PNG remapping capabilities

New Features:
- Search bar to filter items by ID or name
- PNG remapping: assign any PNG to any entity ID
- Custom icons directory for remapped images
- Real-time refresh of icon display
- Support for ALL entity types (not just items from catalog)

Requirements:
- pip install pillow

Usage:
1. Run script
2. Use search bar to find specific items
3. Browse through items using Next/Previous buttons
4. Click on an image to select it
5. Use "Remap to Different ID" to assign PNG to a different entity
6. Choose "Replace Placeholder" for immediate replacement
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
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
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CATALOG_PATH = PROJECT_ROOT / "Scaled JSON Development" / "ITEM_CATALOG_FOR_ICONS.md"
COMPLETE_CATALOG_PATH = PROJECT_ROOT / "Scaled JSON Development" / "complete_entity_catalog.json"
DEFERRED_DECISIONS_FILE = SCRIPT_DIR / "deferred_icon_decisions.json"
CUSTOM_ICONS_DIR = SCRIPT_DIR / "custom_icons"
REMAP_REGISTRY_FILE = SCRIPT_DIR / "icon_remap_registry.json"

# Ensure custom icons directory exists
CUSTOM_ICONS_DIR.mkdir(exist_ok=True)

# Placeholder directories
PLACEHOLDER_BASE = SCRIPT_DIR

# Generation cycle directories to scan
GENERATION_CYCLES = []
for pattern in ["icons-generation-cycle-*", "icons-generated-cycle-*"]:
    for cycle_dir in SCRIPT_DIR.glob(pattern):
        GENERATION_CYCLES.append(cycle_dir)
GENERATION_CYCLES = sorted(set(GENERATION_CYCLES))

# ============================================================================
# CATALOG PARSING
# ============================================================================

def load_complete_catalog():
    """Load the complete entity catalog (all entities from all JSON files)"""
    if COMPLETE_CATALOG_PATH.exists():
        with open(COMPLETE_CATALOG_PATH, 'r') as f:
            data = json.load(f)
        return data['entities']
    return {}

def parse_old_catalog(filepath):
    """Parse ITEM_CATALOG_FOR_ICONS.md and return item metadata"""
    items = {}

    if not filepath.exists():
        return items

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

def build_unified_catalog():
    """Build a unified catalog from both old and new catalog sources"""
    unified = {}

    # Load complete catalog (from JSON files)
    complete_catalog = load_complete_catalog()

    # Convert complete catalog format to unified format
    for category, entities in complete_catalog.items():
        for entity in entities:
            item_id = entity.get('id', 'UNKNOWN')
            unified[item_id] = {
                'id': item_id,
                'name': entity.get('name', 'Unnamed'),
                'category': entity.get('category', 'unknown'),
                'type': entity.get('type', 'unknown'),
                'subtype': entity.get('subtype', ''),
                'narrative': entity.get('narrative', entity.get('description', '')),
                'source_category': category,
                'icon_path': entity.get('icon_path', 'NOT_SPECIFIED')
            }

    # Also load old catalog for additional info
    old_catalog = parse_old_catalog(CATALOG_PATH)
    for item_id, data in old_catalog.items():
        if item_id not in unified:
            unified[item_id] = {
                'id': item_id,
                'name': data.get('name', item_id),
                'category': data.get('category', 'unknown'),
                'type': data.get('type', 'unknown'),
                'subtype': data.get('subtype', ''),
                'narrative': data.get('narrative', ''),
                'source_category': 'LEGACY',
                'icon_path': 'NOT_SPECIFIED'
            }

    return unified

def categorize_item(item_data):
    """Determine folder structure based on item properties

    Returns tuple: (base_folder, subfolder)
    """
    category = item_data.get('category', '').lower()
    item_type = item_data.get('type', '').lower()
    source_category = item_data.get('source_category', '').upper()

    # Map source categories to folder structure
    if source_category == 'ENEMIES':
        return ('enemies', None)
    elif source_category == 'RESOURCES':
        return ('resources', None)
    elif source_category == 'TITLES':
        return ('titles', None)
    elif source_category == 'SKILLS':
        return ('skills', None)
    elif source_category == 'CLASSES':
        return ('classes', None)
    elif source_category == 'NPCS':
        return ('npcs', None)
    elif source_category == 'QUESTS':
        return ('quests', None)

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

    if category == 'station' or item_type == 'station':
        return ('items', 'stations')
    if category == 'device':
        return ('items', 'devices')
    if category == 'consumable':
        return ('items', 'consumables')

    # Fallback based on category name
    if category == 'enemy':
        return ('enemies', None)
    if category == 'resource':
        return ('resources', None)
    if category == 'title':
        return ('titles', None)
    if category == 'skill':
        return ('skills', None)

    # Default: materials
    return ('items', 'materials')

# ============================================================================
# FILE SCANNING
# ============================================================================

def find_all_icon_versions(item_name, base_folder, subfolder):
    """Find all generated versions of an icon across all generation cycles

    Returns list of dicts with 'path', 'cycle', 'version' keys
    """
    versions = []

    # Check each generation cycle
    for cycle_dir in GENERATION_CYCLES:
        # Check generated_icons, generated_icons-2, generated_icons-3, etc.
        for version_dir in cycle_dir.glob("generated_icons*"):
            # Determine version number from folder name
            if version_dir.name == "generated_icons":
                version_num = 1
                expected_filename = f"{item_name}.png"
            else:
                match = re.search(r'-(\d+)$', version_dir.name)
                if match:
                    version_num = int(match.group(1))
                    expected_filename = f"{item_name}-{version_num}.png"
                else:
                    continue

            # Build path to icon
            if subfolder:
                icon_path = version_dir / base_folder / subfolder / expected_filename
            else:
                icon_path = version_dir / base_folder / expected_filename

            if icon_path.exists():
                versions.append({
                    'path': icon_path,
                    'cycle': cycle_dir.name,
                    'version': version_num,
                    'label': f"{cycle_dir.name}/v{version_num}"
                })

    # Also check custom icons directory
    custom_path = CUSTOM_ICONS_DIR / f"{item_name}.png"
    if custom_path.exists():
        versions.append({
            'path': custom_path,
            'cycle': 'custom',
            'version': 0,
            'label': 'Custom (Remapped)'
        })

    return sorted(versions, key=lambda x: (x['cycle'], x['version']))

def get_placeholder_path(item_name, base_folder, subfolder):
    """Get the path to the current placeholder/existing image"""
    if subfolder:
        placeholder_path = PLACEHOLDER_BASE / base_folder / subfolder / f"{item_name}.png"
    else:
        placeholder_path = PLACEHOLDER_BASE / base_folder / f"{item_name}.png"

    return placeholder_path if placeholder_path.exists() else None

# ============================================================================
# ICON REMAPPING
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

def remap_icon(source_path, target_id, catalog):
    """Remap a PNG to a different entity ID

    Args:
        source_path: Path to the source PNG file
        target_id: The ID of the entity to map this icon to
        catalog: The unified catalog dictionary

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
# GUI APPLICATION
# ============================================================================

class EnhancedIconSelectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Icon Selection Tool")
        self.root.geometry("1500x950")

        # Load catalog
        print("Loading unified catalog...")
        self.catalog = build_unified_catalog()
        self.all_items = sorted(list(self.catalog.keys()))
        self.filtered_items = self.all_items.copy()
        self.current_index = 0

        # Load deferred decisions
        self.deferred = load_deferred_decisions()

        # Track selections
        self.selected_versions = []

        # Search filter
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)

        # Build UI
        self.build_ui()

        # Load first item
        if self.filtered_items:
            self.load_item(0)

    def build_ui(self):
        """Build the user interface"""
        # Search bar at the top
        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)

        ttk.Label(search_frame, text="Search:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=50)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Label(search_frame, text="(Search by ID or name)", font=("Arial", 9, "italic")).pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text="Clear", command=lambda: self.search_var.set("")).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Refresh Catalog", command=self.refresh_catalog).pack(side=tk.LEFT, padx=5)

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

    def refresh_catalog(self):
        """Reload the catalog from disk"""
        self.catalog = build_unified_catalog()
        self.all_items = sorted(list(self.catalog.keys()))
        self.on_search_change()  # Re-apply search filter
        messagebox.showinfo("Refresh Complete", f"Catalog reloaded!\n\nTotal entities: {len(self.all_items)}")

    def load_item(self, index):
        """Load and display an item's icons"""
        if index < 0 or index >= len(self.filtered_items):
            return

        self.current_index = index
        item_id = self.filtered_items[index]
        item_data = self.catalog[item_id]

        # Update labels
        self.item_name_label.config(text=f"{item_id}")
        category_info = f"Category: {item_data.get('source_category', 'UNKNOWN')} | Type: {item_data.get('type', 'unknown')} | Subtype: {item_data.get('subtype', 'N/A')}"
        self.item_info_label.config(text=category_info)
        self.narrative_label.config(text=item_data.get('narrative', 'No description available'))

        # Update progress
        self.progress_label.config(text=f"{index + 1}/{len(self.filtered_items)}")

        # Clear previous images
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Reset selection
        self.selected_versions = []

        # Get folder structure
        base_folder, subfolder = categorize_item(item_data)

        # Find all versions
        versions = find_all_icon_versions(item_id, base_folder, subfolder)

        # Get current placeholder
        placeholder_path = get_placeholder_path(item_id, base_folder, subfolder)

        # Display placeholder if exists
        if placeholder_path:
            self._create_image_tile(placeholder_path, "Current Placeholder", None, 0, is_placeholder=True)

        # Display all versions
        for i, version in enumerate(versions, start=1):
            self._create_image_tile(version['path'], version['label'], version, i)

        # If no images found
        if not versions and not placeholder_path:
            no_img_label = ttk.Label(self.scrollable_frame, text="No icons found for this entity",
                                    font=("Arial", 12), foreground="gray")
            no_img_label.pack(pady=50)

        self.update_buttons()

    def _create_image_tile(self, image_path, label, version_data, column, is_placeholder=False):
        """Create a clickable image tile"""
        tile_frame = ttk.Frame(self.scrollable_frame, relief=tk.RAISED, borderwidth=2)
        tile_frame.grid(row=0, column=column, padx=10, pady=10)

        try:
            # Load and display image
            img = Image.open(image_path)
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            img_label = tk.Label(tile_frame, image=photo)
            img_label.image = photo  # Keep reference
            img_label.pack()

            # Label
            label_widget = ttk.Label(tile_frame, text=label, font=("Arial", 10, "bold" if is_placeholder else "normal"))
            label_widget.pack(pady=5)

            # File size
            size_kb = image_path.stat().st_size / 1024
            size_label = ttk.Label(tile_frame, text=f"{size_kb:.1f} KB", font=("Arial", 8))
            size_label.pack()

            # Make clickable (only for non-placeholder)
            if not is_placeholder and version_data:
                def on_click(event):
                    self.toggle_selection(version_data, tile_frame)

                img_label.bind("<Button-1>", on_click)
                tile_frame.bind("<Button-1>", on_click)
                label_widget.bind("<Button-1>", on_click)

        except Exception as e:
            error_label = ttk.Label(tile_frame, text=f"Error loading image:\n{e}", foreground="red")
            error_label.pack(padx=10, pady=10)

    def toggle_selection(self, version_data, tile_frame):
        """Toggle selection of an image"""
        if version_data in self.selected_versions:
            # Deselect
            self.selected_versions.remove(version_data)
            # Remove highlight
            if hasattr(tile_frame, '_highlight_canvas'):
                tile_frame._highlight_canvas.destroy()
        else:
            # Select
            self.selected_versions.append(version_data)
            self._highlight_tile(tile_frame)

        self.update_buttons()

    def _highlight_tile(self, tile_frame):
        """Add visual highlight to selected tile"""
        highlight_frame = tk.Frame(tile_frame, background="#90EE90", bd=0)
        highlight_frame.place(x=0, y=0, relwidth=1, relheight=1)
        highlight_frame.lower()
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
        self.load_item(self.current_index)

    def replace_placeholder(self):
        """Replace placeholder with selected image"""
        if len(self.selected_versions) != 1:
            messagebox.showerror("Error", "Please select exactly one image to replace the placeholder.")
            return

        item_id = self.filtered_items[self.current_index]
        item_data = self.catalog[item_id]
        base_folder, subfolder = categorize_item(item_data)

        placeholder_path = get_placeholder_path(item_id, base_folder, subfolder)
        selected = self.selected_versions[0]

        # Create target directory if it doesn't exist
        if not placeholder_path:
            # Create the path
            if subfolder:
                target_dir = PLACEHOLDER_BASE / base_folder / subfolder
            else:
                target_dir = PLACEHOLDER_BASE / base_folder
            target_dir.mkdir(parents=True, exist_ok=True)
            placeholder_path = target_dir / f"{item_id}.png"

        # Confirm replacement
        response = messagebox.askyesno(
            "Confirm Replacement",
            f"Replace/create placeholder for {item_id}?\n\n"
            f"Source: {selected['label']}\n"
            f"Target: {placeholder_path.relative_to(SCRIPT_DIR)}"
        )

        if response:
            try:
                # Backup old placeholder if it exists
                if placeholder_path.exists():
                    backup_dir = SCRIPT_DIR / "replaced_placeholders"
                    backup_dir.mkdir(exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = backup_dir / f"{item_id}_{timestamp}.png"
                    shutil.copy2(placeholder_path, backup_path)

                # Replace/create
                shutil.copy2(selected['path'], placeholder_path)

                messagebox.showinfo("Success",
                    f"Icon {'replaced' if placeholder_path.exists() else 'created'}!\n\n"
                    f"Location: {placeholder_path.relative_to(SCRIPT_DIR)}")

                # Refresh display
                self.load_item(self.current_index)

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
                dest_path = remap_icon(source_path, target_id, self.catalog)
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

        item_id = self.filtered_items[self.current_index]

        # Store paths as strings
        self.deferred[item_id] = {
            'item_data': self.catalog[item_id],
            'options': [
                {
                    'path': str(v['path'].relative_to(SCRIPT_DIR)) if v['path'].is_relative_to(SCRIPT_DIR) else str(v['path']),
                    'label': v['label']
                }
                for v in self.selected_versions
            ],
            'deferred_at': datetime.now().isoformat()
        }

        save_deferred_decisions(self.deferred)
        messagebox.showinfo("Saved", f"Deferred decision for {item_id}\n({len(self.selected_versions)} options saved)")

        self.next_item()

    def view_deferred(self):
        """Show list of deferred decisions"""
        if not self.deferred:
            messagebox.showinfo("Deferred Decisions", "No deferred decisions yet!")
            return

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Deferred Decisions")
        dialog.geometry("600x400")

        ttk.Label(dialog, text="Items with Deferred Decisions", font=("Arial", 14, "bold")).pack(pady=10)

        # List
        listbox = tk.Listbox(dialog, font=("Arial", 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for item_id, data in self.deferred.items():
            num_options = len(data.get('options', []))
            listbox.insert(tk.END, f"{item_id} ({num_options} options)")

        def jump_to_item():
            selection = listbox.curselection()
            if selection:
                selected_text = listbox.get(selection[0])
                item_id = selected_text.split(' (')[0]
                if item_id in self.filtered_items:
                    self.current_index = self.filtered_items.index(item_id)
                    self.load_item(self.current_index)
                    dialog.destroy()

        ttk.Button(dialog, text="Jump to Selected Item", command=jump_to_item).pack(pady=10)

    def next_item(self):
        """Navigate to next item"""
        if self.current_index < len(self.filtered_items) - 1:
            self.load_item(self.current_index + 1)

    def prev_item(self):
        """Navigate to previous item"""
        if self.current_index > 0:
            self.load_item(self.current_index - 1)


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
            category = self.catalog[item_id].get('source_category', 'UNKNOWN')
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
    root = tk.Tk()
    app = EnhancedIconSelectorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
