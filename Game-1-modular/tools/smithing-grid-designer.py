import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from pathlib import Path
from collections import Counter

# HARDCODED MATERIALS PATH
MATERIALS_JSON_PATH = r"..\items.JSON\items-materials-1.JSON"


class SmithingDesigner:
    def __init__(self, root):
        self.root = root
        self.root.title("Smithing Recipe Designer")
        self.root.geometry("1400x900")

        # Data storage
        self.recipes = {}
        self.placements = {}
        self.materials_db = {}
        self.current_recipe_id = None
        self.current_recipe_original_inputs = []
        self.current_grid = {}
        self.selected_material = None
        self.last_placed_material = None
        self.recipes_file = None
        self.placements_file = None

        # Bind spacebar for reselecting last placed material
        self.root.bind('<space>', self.reselect_last_material)

        # Load materials first (hardcoded path)
        self.load_materials_from_file()

        # Load recipes and optional placements
        self.load_files()

        if not self.recipes:
            messagebox.showerror("Error", "No recipes loaded. Exiting.")
            root.destroy()
            return

        # Build UI
        self.build_ui()

    def reselect_last_material(self, event=None):
        """Reselect the last placed material (triggered by spacebar)"""
        if self.last_placed_material:
            self.select_material(self.last_placed_material)
            self.status_label.config(
                text=f"Reselected: {self.last_placed_material} (Spacebar shortcut)",
                foreground="purple"
            )
        else:
            self.status_label.config(
                text="No material placed yet - select from palette first",
                foreground="orange"
            )

    def get_grid_size_from_tier(self, tier):
        """Get grid size based on tier: T1->3x3, T2->5x5, T3->7x7, T4->9x9"""
        tier_to_size = {
            1: "3x3",
            2: "5x5",
            3: "7x7",
            4: "9x9"
        }
        return tier_to_size.get(tier, "3x3")

    def load_materials_from_file(self):
        """Load materials from hardcoded JSON path"""
        try:
            with open(MATERIALS_JSON_PATH, 'r') as f:
                data = json.load(f)
                materials_list = self.extract_materials_from_json(data)

                # Convert to dict
                for mat in materials_list:
                    mat_id = mat.get('materialId')
                    if mat_id:
                        self.materials_db[mat_id] = {
                            'name': mat.get('name', mat_id),
                            'tier': mat.get('tier', 1),
                            'category': mat.get('category', 'unknown')
                        }

                print(f"✓ Loaded {len(self.materials_db)} materials from {MATERIALS_JSON_PATH}")
        except FileNotFoundError:
            messagebox.showwarning("Warning",
                                   f"Materials file not found at:\n{MATERIALS_JSON_PATH}\n\nUsing empty materials database.")
            self.materials_db = {}
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load materials:\n{e}")
            self.materials_db = {}

    def extract_materials_from_json(self, data):
        """Extract materials list from various JSON structures"""
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Try common keys
            if 'materials' in data:
                return data['materials'] if isinstance(data['materials'], list) else []
            elif 'items' in data:
                return data['items'] if isinstance(data['items'], list) else []
            # If it's a dict of materials, convert to list
            elif all(isinstance(v, dict) for v in data.values()):
                return list(data.values())
        return []

    def extract_recipes_from_json(self, data):
        """Extract recipes from various JSON structures"""
        recipes = {}

        if isinstance(data, list):
            # Direct list of recipes
            for recipe in data:
                if self.is_valid_recipe(recipe):
                    recipe_id = recipe.get('recipeId')
                    if recipe_id:
                        recipes[recipe_id] = recipe
        elif isinstance(data, dict):
            # Try common keys first
            if 'recipes' in data and isinstance(data['recipes'], list):
                for recipe in data['recipes']:
                    if self.is_valid_recipe(recipe):
                        recipe_id = recipe.get('recipeId')
                        if recipe_id:
                            recipes[recipe_id] = recipe
            else:
                # Check if top-level keys are recipe IDs or categories
                for key, value in data.items():
                    if key in ['metadata', 'version', 'info']:
                        continue  # Skip metadata keys

                    if isinstance(value, dict):
                        # Check if this is a single recipe
                        if self.is_valid_recipe(value):
                            recipe_id = value.get('recipeId', key)
                            recipes[recipe_id] = value
                        # Or a category containing recipes
                        elif 'recipes' in value and isinstance(value['recipes'], list):
                            for recipe in value['recipes']:
                                if self.is_valid_recipe(recipe):
                                    recipe_id = recipe.get('recipeId')
                                    if recipe_id:
                                        recipes[recipe_id] = recipe
                    elif isinstance(value, list):
                        # Category is a list of recipes
                        for recipe in value:
                            if isinstance(recipe, dict) and self.is_valid_recipe(recipe):
                                recipe_id = recipe.get('recipeId')
                                if recipe_id:
                                    recipes[recipe_id] = recipe

        return recipes

    def is_valid_recipe(self, recipe):
        """Check if an object is a valid recipe"""
        if not isinstance(recipe, dict):
            return False

        # Must have at least recipeId and outputId
        required_fields = ['recipeId', 'outputId']
        has_required = all(field in recipe for field in required_fields)

        # Should have inputs (or we can work with it anyway)
        return has_required

    def extract_placements_from_json(self, data):
        """Extract placements from various JSON structures"""
        placements = {}

        if isinstance(data, list):
            # Direct list of placement objects
            for placement in data:
                if isinstance(placement, dict) and 'recipeId' in placement:
                    recipe_id = placement['recipeId']
                    # Try to extract the actual placement map
                    if 'placementMap' in placement:
                        placements[recipe_id] = placement['placementMap']
                    elif 'placements' in placement:
                        placements[recipe_id] = placement['placements']
                    else:
                        # Maybe the whole object is the placement map
                        map_data = {k: v for k, v in placement.items()
                                    if k not in ['recipeId', 'metadata', 'gridSize']}
                        if map_data:
                            placements[recipe_id] = map_data
        elif isinstance(data, dict):
            # Try common structures
            if 'placements' in data:
                placements_data = data['placements']
                if isinstance(placements_data, list):
                    # List of placement objects
                    for placement in placements_data:
                        if isinstance(placement, dict) and 'recipeId' in placement:
                            recipe_id = placement['recipeId']
                            if 'placementMap' in placement:
                                placements[recipe_id] = placement['placementMap']
                            elif 'placements' in placement:
                                placements[recipe_id] = placement['placements']
                elif isinstance(placements_data, dict):
                    # Dict of recipe_id -> placement_map
                    placements = placements_data
            else:
                # Maybe top-level keys are recipe IDs
                for key, value in data.items():
                    if key in ['metadata', 'version', 'info']:
                        continue

                    if isinstance(value, dict):
                        # Check if this looks like a placement map (keys are grid coords)
                        if any(',' in str(k) for k in value.keys()):
                            placements[key] = value

        return placements

    def load_files(self):
        """Load recipes and optional placements JSON files with better error handling"""
        # Load recipes (REQUIRED)
        self.recipes_file = filedialog.askopenfilename(
            title="Select Recipes JSON (REQUIRED)",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not self.recipes_file:
            return

        try:
            with open(self.recipes_file, 'r') as f:
                data = json.load(f)

            # Extract recipes using robust extraction
            self.recipes = self.extract_recipes_from_json(data)

            if not self.recipes:
                # Show what was found to help debug
                keys_found = list(data.keys()) if isinstance(data, dict) else "list structure"
                messagebox.showerror(
                    "No Valid Recipes Found",
                    f"Could not find valid recipes in the JSON file.\n\n"
                    f"Top-level structure: {type(data).__name__}\n"
                    f"Keys found: {keys_found}\n\n"
                    f"Recipes must have 'recipeId' and 'outputId' fields."
                )
                return

            print(f"✓ Loaded {len(self.recipes)} recipes from {Path(self.recipes_file).name}")
            print(f"  Recipe IDs: {list(self.recipes.keys())[:5]}{'...' if len(self.recipes) > 5 else ''}")

        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Failed to parse recipes file:\n{e}")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load recipes:\n{e}")
            return

        # Load placements (OPTIONAL)
        response = messagebox.askyesno(
            "Load Placements?",
            f"Successfully loaded {len(self.recipes)} recipes.\n\n"
            "Do you have an existing placements file to load?\n\n"
            "Click 'No' to start with empty placements."
        )

        if response:
            self.placements_file = filedialog.askopenfilename(
                title="Select Placements JSON (Optional)",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if self.placements_file:
                try:
                    with open(self.placements_file, 'r') as f:
                        data = json.load(f)

                    # Extract placements using robust extraction
                    self.placements = self.extract_placements_from_json(data)

                    print(f"✓ Loaded {len(self.placements)} placements from {Path(self.placements_file).name}")
                    if self.placements:
                        print(
                            f"  Placement IDs: {list(self.placements.keys())[:5]}{'...' if len(self.placements) > 5 else ''}")

                    if not self.placements:
                        messagebox.showinfo(
                            "No Placements Found",
                            "The file was loaded but no valid placements were found.\n"
                            "Starting with empty placements."
                        )
                    else:
                        messagebox.showinfo(
                            "Placements Loaded",
                            f"Successfully loaded {len(self.placements)} placement maps."
                        )

                except json.JSONDecodeError as e:
                    messagebox.showwarning("Invalid JSON",
                                           f"Failed to parse placements file:\n{e}\nStarting with empty placements.")
                    self.placements = {}
                except Exception as e:
                    messagebox.showwarning("Warning",
                                           f"Failed to load placements:\n{e}\nStarting with empty placements.")
                    self.placements = {}
        else:
            # Start fresh - ask where to save placements
            self.placements_file = filedialog.asksaveasfilename(
                title="Where to save placements?",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            self.placements = {}
            print("✓ Starting with empty placements")

    def build_ui(self):
        """Build the main UI"""
        # Top frame - Recipe selector
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Recipe:", font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)

        self.recipe_var = tk.StringVar()
        recipe_dropdown = ttk.Combobox(top_frame, textvariable=self.recipe_var,
                                       values=sorted(self.recipes.keys()),
                                       state='readonly', width=50)
        recipe_dropdown.pack(side=tk.LEFT, padx=5)
        recipe_dropdown.bind('<<ComboboxSelected>>', self.on_recipe_selected)

        # Status label
        self.status_label = ttk.Label(top_frame,
                                      text=f"Loaded {len(self.recipes)} recipes, {len(self.placements)} placements | Press SPACEBAR to reselect last material",
                                      foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=20)

        # Main content frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Recipe info and material palette
        left_frame = ttk.LabelFrame(main_frame, text="Recipe & Materials", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5)

        # Recipe info
        info_frame = ttk.Frame(left_frame)
        info_frame.pack(fill=tk.X, pady=5)

        self.info_text = tk.Text(info_frame, height=8, width=40, wrap=tk.WORD,
                                 state='disabled', bg='#f0f0f0')
        self.info_text.pack(fill=tk.X)

        # Material palette
        palette_label = ttk.Label(left_frame, text="Material Palette",
                                  font=('Arial', 11, 'bold'))
        palette_label.pack(pady=(10, 5))

        self.palette_frame = ttk.Frame(left_frame)
        self.palette_frame.pack(fill=tk.BOTH, expand=True)

        # Add material section
        add_mat_frame = ttk.LabelFrame(left_frame, text="Add Material", padding="5")
        add_mat_frame.pack(fill=tk.X, pady=10)

        # Sort materials by tier
        sorted_materials = sorted(self.materials_db.items(),
                                  key=lambda x: (x[1]['tier'], x[1]['name']))
        material_display = [f"[T{m[1]['tier']}] {m[1]['name']} ({m[0]})"
                            for m in sorted_materials]

        self.add_mat_var = tk.StringVar()
        add_mat_combo = ttk.Combobox(add_mat_frame, textvariable=self.add_mat_var,
                                     values=material_display, state='readonly', width=35)
        add_mat_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(add_mat_frame, text="Add to Palette",
                   command=self.add_material_to_palette).pack(side=tk.LEFT, padx=5)

        # Validation status
        self.validation_frame = ttk.LabelFrame(left_frame, text="Status", padding="10")
        self.validation_frame.pack(fill=tk.X, pady=10)

        self.validation_label = ttk.Label(self.validation_frame,
                                          text="No recipe selected",
                                          foreground="gray")
        self.validation_label.pack()

        # Save Changes button
        self.save_btn = tk.Button(self.validation_frame,
                                  text="💾 Save Changes to Recipe",
                                  command=self.save_recipe_changes,
                                  bg='#2196F3', fg='white',
                                  font=('Arial', 10, 'bold'),
                                  state='disabled')
        self.save_btn.pack(pady=5, fill=tk.X)

        # Right panel - Grid designer
        right_frame = ttk.LabelFrame(main_frame, text="Placement Grid", padding="10")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.grid_frame = ttk.Frame(right_frame)
        self.grid_frame.pack()

        # Instructions
        instructions = ttk.Label(right_frame,
                                 text="Click material from palette, then click grid cell to place.\nClick placed cell to remove.\nPress SPACEBAR to reselect last placed material.",
                                 foreground="blue", justify=tk.CENTER)
        instructions.pack(pady=10)

        # JSON preview
        json_frame = ttk.LabelFrame(right_frame, text="Placement JSON", padding="5")
        json_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.json_text = tk.Text(json_frame, height=10, width=60, wrap=tk.WORD,
                                 bg='#f0f0f0', font=('Courier', 9))
        self.json_text.pack(fill=tk.BOTH, expand=True)

    def on_recipe_selected(self, event=None):
        """Handle recipe selection"""
        recipe_id = self.recipe_var.get()
        if not recipe_id:
            return

        self.current_recipe_id = recipe_id
        recipe = self.recipes[recipe_id]

        # Store original inputs (deep copy to avoid reference issues)
        self.current_recipe_original_inputs = [
            {"materialId": inp["materialId"], "quantity": inp["quantity"]}
            for inp in recipe.get('inputs', [])
        ]

        # Load existing placement if available
        self.current_grid = self.placements.get(recipe_id, {}).copy()

        # Update info display
        self.update_recipe_info(recipe)

        # Rebuild material palette
        self.rebuild_palette()

        # Rebuild grid
        self.rebuild_grid(recipe)

        # Update JSON preview
        self.update_json_preview()

        # Enable save button
        self.save_btn.config(state='normal')

        placement_status = f"(has {len(self.current_grid)} placements)" if self.current_grid else "(no placements)"
        self.status_label.config(text=f"Loaded: {recipe_id} {placement_status}", foreground="green")

    def update_recipe_info(self, recipe):
        """Update recipe info display"""
        self.info_text.config(state='normal')
        self.info_text.delete('1.0', tk.END)

        # Get actual grid size (tier-based override)
        station_tier = recipe.get('stationTier', 1)
        actual_grid_size = self.get_grid_size_from_tier(station_tier)
        original_grid_size = recipe.get('gridSize', '3x3')

        info = f"Recipe ID: {recipe['recipeId']}\n"
        info += f"Output: {recipe.get('outputId', 'N/A')} (x{recipe.get('outputQty', 1)})\n"
        info += f"Station Tier: T{station_tier}\n"
        if original_grid_size != actual_grid_size:
            info += f"Grid Size: {actual_grid_size} (overridden from {original_grid_size})\n\n"
        else:
            info += f"Grid Size: {actual_grid_size}\n\n"

        narrative = recipe.get('metadata', {}).get('narrative', 'N/A') if isinstance(recipe.get('metadata'),
                                                                                     dict) else 'N/A'
        info += f"Narrative:\n{narrative}"

        self.info_text.insert('1.0', info)
        self.info_text.config(state='disabled')

    def rebuild_palette(self):
        """Rebuild material palette based on original recipe inputs and current grid"""
        # Clear existing palette
        for widget in self.palette_frame.winfo_children():
            widget.destroy()

        if not self.current_recipe_id:
            return

        # Get materials from ORIGINAL recipe inputs
        recipe_materials = {}
        for input_item in self.current_recipe_original_inputs:
            mat_id = input_item['materialId']
            recipe_materials[mat_id] = input_item['quantity']

        # Calculate material counts from grid
        grid_counts = Counter(self.current_grid.values())

        # Combine: show all materials from recipe + any extras in grid
        all_materials = set(recipe_materials.keys()) | set(grid_counts.keys())

        # Create buttons for each material
        for material_id in sorted(all_materials):
            required = recipe_materials.get(material_id, 0)
            used = grid_counts.get(material_id, 0)

            mat_info = self.materials_db.get(material_id, {"name": material_id, "tier": "?"})

            # Color coding: green=correct, red=under, yellow=over/new
            if required > 0 and used == required:
                color = '#4CAF50'  # Green - exact match
            elif required > 0 and used < required:
                color = '#f44336'  # Red - under
            elif required > 0 and used > required:
                color = '#FFC107'  # Yellow - over
            else:
                color = '#9C27B0'  # Purple - new material not in original recipe

            frame = ttk.Frame(self.palette_frame)
            frame.pack(fill=tk.X, pady=2)

            if required > 0:
                label_text = f"{mat_info['name']} ({used}/{required})"
            else:
                label_text = f"{mat_info['name']} ({used}/NEW)"

            btn = tk.Button(frame,
                            text=label_text,
                            width=30,
                            command=lambda m=material_id: self.select_material(m),
                            bg=color, fg='white', relief=tk.RAISED)
            btn.pack(side=tk.LEFT, padx=2)

            # Delete button (only if material is in grid)
            if used > 0:
                del_btn = tk.Button(frame, text="❌", width=2,
                                    command=lambda m=material_id: self.remove_material_from_grid(m),
                                    bg='#f44336', fg='white')
                del_btn.pack(side=tk.LEFT)

        # Update validation status
        self.update_validation_status()

    def select_material(self, material_id):
        """Select a material for placement"""
        self.selected_material = material_id
        mat_name = self.materials_db.get(material_id, {"name": material_id})['name']
        self.status_label.config(text=f"Selected: {mat_name} - Click grid to place",
                                 foreground="orange")

    def add_material_to_palette(self):
        """Add a new material to palette from dropdown"""
        selection = self.add_mat_var.get()
        if not selection:
            return

        # Extract material_id from display string (last part in parentheses)
        material_id = selection.split('(')[-1].strip(')')

        # Just select it - user will place it on grid
        self.select_material(material_id)
        self.add_mat_var.set('')

    def remove_material_from_grid(self, material_id):
        """Remove all instances of a material from grid"""
        self.current_grid = {k: v for k, v in self.current_grid.items()
                             if v != material_id}
        self.rebuild_palette()
        self.update_grid_display()
        self.update_json_preview()
        self.save_files()  # Auto-save placements only

    def rebuild_grid(self, recipe):
        """Rebuild the placement grid"""
        # Clear existing grid
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        # Get grid dimensions - use tier-based size
        station_tier = recipe.get('stationTier', 1)
        grid_size = self.get_grid_size_from_tier(station_tier)
        rows, cols = map(int, grid_size.split('x'))

        # Create grid with labels
        # Top row - column labels
        tk.Label(self.grid_frame, text="", width=3).grid(row=0, column=0)
        for col in range(cols):
            tk.Label(self.grid_frame, text=str(col + 1), width=8,
                     font=('Arial', 10, 'bold')).grid(row=0, column=col + 1)

        # Grid cells with row labels
        self.grid_buttons = {}
        for row in range(rows):
            # Row label
            tk.Label(self.grid_frame, text=str(row + 1), width=3,
                     font=('Arial', 10, 'bold')).grid(row=row + 1, column=0)

            for col in range(cols):
                key = f"{row + 1},{col + 1}"
                material = self.current_grid.get(key, None)

                btn = tk.Button(self.grid_frame,
                                text=self.get_material_display(material),
                                width=10, height=3,
                                command=lambda k=key: self.on_grid_click(k),
                                bg='#90CAF9' if material else '#EEEEEE',
                                relief=tk.RAISED)
                btn.grid(row=row + 1, column=col + 1, padx=2, pady=2)
                self.grid_buttons[key] = btn

    def get_material_display(self, material_id):
        """Get display text for material"""
        if not material_id:
            return ""
        mat_info = self.materials_db.get(material_id, {"name": material_id})
        return mat_info['name']

    def on_grid_click(self, grid_key):
        """Handle grid cell click"""
        if self.selected_material:
            # Place material
            self.current_grid[grid_key] = self.selected_material
            self.last_placed_material = self.selected_material  # Remember for spacebar reselect
            self.selected_material = None
            self.status_label.config(text="Material placed - Press SPACEBAR to reselect", foreground="green")
        else:
            # Remove material
            if grid_key in self.current_grid:
                del self.current_grid[grid_key]
                self.status_label.config(text="Material removed", foreground="blue")

        self.update_grid_display()
        self.rebuild_palette()
        self.update_json_preview()
        self.save_files()  # Auto-save placements only

    def update_grid_display(self):
        """Update grid button displays without rebuilding"""
        for key, btn in self.grid_buttons.items():
            material = self.current_grid.get(key, None)
            btn.config(text=self.get_material_display(material),
                       bg='#90CAF9' if material else '#EEEEEE')

    def update_json_preview(self):
        """Update JSON preview"""
        self.json_text.delete('1.0', tk.END)
        json_str = json.dumps(self.current_grid, indent=2)
        self.json_text.insert('1.0', json_str)

    def update_validation_status(self):
        """Update validation status display"""
        if not self.current_recipe_id:
            self.validation_label.config(text="No recipe selected", foreground="gray")
            return

        # Count materials in grid
        material_counts = Counter(self.current_grid.values())

        if not material_counts:
            self.validation_label.config(text="⚠ Grid is empty", foreground="orange")
        else:
            total_materials = len(material_counts)
            self.validation_label.config(
                text=f"📊 {total_materials} material types in grid\nClick 'Save Changes' to update recipe",
                foreground="blue"
            )

    def save_recipe_changes(self):
        """Save grid contents to recipe inputs"""
        if not self.current_recipe_id:
            return

        # Count materials in grid
        material_counts = Counter(self.current_grid.values())

        # Update recipe inputs from grid
        new_inputs = [{"materialId": mat_id, "quantity": count}
                      for mat_id, count in sorted(material_counts.items())]

        self.recipes[self.current_recipe_id]['inputs'] = new_inputs

        # Update original inputs to match (so palette doesn't show red/yellow anymore)
        self.current_recipe_original_inputs = [
            {"materialId": inp["materialId"], "quantity": inp["quantity"]}
            for inp in new_inputs
        ]

        # Rebuild palette to show new "correct" state
        self.rebuild_palette()

        # Save both files
        self.save_files()

        self.status_label.config(text="✅ Recipe updated and saved!", foreground="green")

    def save_files(self):
        """Save both recipes and placements files immediately"""
        if not self.recipes_file or not self.placements_file:
            return

        try:
            # Save recipes
            recipes_output = Path(self.recipes_file).parent / f"{Path(self.recipes_file).stem}-modified.json"
            with open(recipes_output, 'w') as f:
                json.dump({
                    "metadata": {
                        "version": "1.0",
                        "modified": True,
                        "totalRecipes": len(self.recipes)
                    },
                    "recipes": list(self.recipes.values())
                }, f, indent=2)

            # Save placements
            placements_output = Path(self.placements_file).parent / f"{Path(self.placements_file).stem}-modified.json"

            # Update placements with current recipe
            if self.current_recipe_id:
                self.placements[self.current_recipe_id] = self.current_grid.copy()

            placements_list = [
                {
                    "recipeId": recipe_id,
                    "placementMap": placement_map,
                    "metadata": {
                        "gridSize": self.recipes.get(recipe_id, {}).get('gridSize', '3x3'),
                        "narrative": self.recipes.get(recipe_id, {}).get('metadata', {}).get('narrative',
                                                                                             '') if isinstance(
                            self.recipes.get(recipe_id, {}).get('metadata'), dict) else ''
                    }
                }
                for recipe_id, placement_map in self.placements.items()
                if placement_map  # Only save non-empty placements
            ]

            with open(placements_output, 'w') as f:
                json.dump({
                    "metadata": {
                        "version": "1.0",
                        "totalPlacements": len(placements_list)
                    },
                    "placements": placements_list
                }, f, indent=2)

            print(f"✓ Saved: {recipes_output.name}")
            print(f"✓ Saved: {placements_output.name}")

        except Exception as e:
            self.status_label.config(text=f"❌ Save failed: {e}", foreground="red")
            messagebox.showerror("Save Error", f"Failed to save files:\n{e}")


def main():
    root = tk.Tk()
    app = SmithingDesigner(root)
    root.mainloop()


if __name__ == "__main__":
    main()