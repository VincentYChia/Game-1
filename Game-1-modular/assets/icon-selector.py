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
CATALOG_PATH = SCRIPT_DIR.parent.parent / "Scaled JSON Development" / "ITEM_CATALOG_FOR_ICONS.md"
DEFERRED_DECISIONS_FILE = SCRIPT_DIR / "deferred_icon_decisions.json"

# Placeholder directories
PLACEHOLDER_BASE = SCRIPT_DIR

# Generation cycle directories to scan
GENERATION_CYCLES = []
for cycle_dir in SCRIPT_DIR.glob("icons-generation-cycle-*"):
    GENERATION_CYCLES.append(cycle_dir)

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
# GUI APPLICATION
# ============================================================================

class IconSelectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Icon Selection Tool")
        self.root.geometry("1400x900")

        # Load catalog
        print("Loading catalog...")
        self.catalog = parse_catalog(CATALOG_PATH)
        self.items = list(self.catalog.keys())
        self.current_index = 0

        # Load deferred decisions
        self.deferred = load_deferred_decisions()

        # Track selections
        self.selected_versions = []

        # Build UI
        self.build_ui()

        # Load first item
        if self.items:
            self.load_item(0)

    def build_ui(self):
        """Build the user interface"""
        # Top frame: Item info
        info_frame = ttk.Frame(self.root, padding="10")
        info_frame.pack(fill=tk.X)

        self.item_name_label = ttk.Label(info_frame, text="", font=("Arial", 16, "bold"))
        self.item_name_label.pack(anchor=tk.W)

        self.item_info_label = ttk.Label(info_frame, text="", font=("Arial", 10))
        self.item_info_label.pack(anchor=tk.W, pady=(5, 0))

        self.narrative_label = ttk.Label(info_frame, text="", font=("Arial", 10), wraplength=1350)
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

        self.defer_btn = ttk.Button(action_frame, text="⏸ Save for Later",
                                    command=self.defer_decision, state=tk.DISABLED)
        self.defer_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = ttk.Button(action_frame, text="✗ Clear Selection",
                                    command=self.clear_selection, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(action_frame, text="📋 View Deferred",
                  command=self.view_deferred).pack(side=tk.LEFT, padx=5)

    def load_item(self, index):
        """Load and display an item's icons"""
        if index < 0 or index >= len(self.items):
            return

        self.current_index = index
        item_name = self.items[index]
        item_data = self.catalog[item_name]

        # Update info labels
        self.item_name_label.config(text=item_name)
        self.item_info_label.config(
            text=f"Category: {item_data['category']}  |  Type: {item_data['type']}  |  Subtype: {item_data['subtype']}"
        )
        self.narrative_label.config(text=f"Narrative: {item_data['narrative']}")

        # Update progress
        self.progress_label.config(text=f"{index + 1}/{len(self.items)}")

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
            tile_frame.config(relief=tk.RAISED, borderwidth=2)
        else:
            # Select
            self.selected_versions.append(version_info)
            tile_frame.config(relief=tk.SOLID, borderwidth=4)

        self.update_buttons()

    def update_buttons(self):
        """Update button states based on selection"""
        num_selected = len(self.selected_versions)

        if num_selected == 0:
            self.replace_btn.config(state=tk.DISABLED)
            self.defer_btn.config(state=tk.DISABLED)
            self.clear_btn.config(state=tk.DISABLED)
        elif num_selected == 1:
            self.replace_btn.config(state=tk.NORMAL)
            self.defer_btn.config(state=tk.DISABLED)
            self.clear_btn.config(state=tk.NORMAL)
        else:
            self.replace_btn.config(state=tk.DISABLED)
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

        item_name = self.items[self.current_index]
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

    def defer_decision(self):
        """Save multiple selections for later decision"""
        if len(self.selected_versions) < 2:
            messagebox.showerror("Error", "Please select at least 2 images to defer decision.")
            return

        item_name = self.items[self.current_index]

        # Store paths as strings (relative to SCRIPT_DIR)
        self.deferred[item_name] = {
            'item_data': self.catalog[item_name],
            'options': [
                {
                    'path': str(v['path'].relative_to(SCRIPT_DIR)),
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
                index = self.items.index(item_name)
                self.load_item(index)
                deferred_window.destroy()

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
        if self.current_index < len(self.items) - 1:
            self.load_item(self.current_index + 1)

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
