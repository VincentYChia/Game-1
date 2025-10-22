import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from pathlib import Path
from collections import Counter
import math


class EnchantingDesigner:
    def __init__(self, root):
        self.root = root
        self.root.title("Enchanting Pattern Designer")
        self.root.geometry("1600x900")

        # Data storage
        self.recipes = {}
        self.placements = {}
        self.materials_db = {}
        self.current_recipe_id = None
        self.current_recipe_original_inputs = []
        self.current_vertices = {}  # {(x,y): {"materialId": ..., "isKey": ...}}
        self.current_shapes = []  # [{"type": ..., "vertices": [...], "rotation": ...}]
        self.selected_material = None
        self.last_placed_material = None
        self.recipes_file = None
        self.placements_file = None
        self.materials_file = None
        self.selected_shape_idx = None  # Track selected shape for highlighting

        # Shape creation state
        self.shape_templates = self.define_shape_templates()
        self.current_rotation = 0
        self.last_mouse_grid_pos = None  # Track mouse position for preview updates

        # Grid state
        self.grid_size = 8
        self.cell_size = 40  # pixels per grid cell
        self.point_radius = 4

        # Bind keys
        self.root.bind('<space>', self.reselect_last_material)
        self.root.bind('<Shift_L>', self.cycle_rotation)
        self.root.bind('<Shift_R>', self.cycle_rotation)
        self.root.bind('<Return>', self.reselect_last_material)

        # Load files
        self.load_files()

        if not self.recipes:
            messagebox.showerror("Error", "No recipes loaded. Exiting.")
            root.destroy()
            return

        # Build UI
        self.build_ui()

    def define_shape_templates(self):
        """Define standard shape vertex offsets from anchor point"""
        return {
            # SMALL SHAPES (base size, ~2-3 units)
            "triangle_equilateral_small": [
                (0, 0),  # Anchor: top vertex
                (-1, -2),  # Bottom left
                (1, -2)  # Bottom right
                # Width 2, height 2, sides ≈2.2 - approximately equilateral
            ],
            "square_small": [
                (0, 0),  # Anchor: top-left
                (2, 0),  # Top-right
                (2, -2),  # Bottom-right
                (0, -2)  # Bottom-left
                # Side length 2 - proper square
            ],
            "triangle_isosceles_small": [
                (0, 0),  # Anchor: top vertex (apex)
                (-1, -3),  # Bottom left
                (1, -3)  # Bottom right
                # Width 2, height 3 - taller/narrower than equilateral
            ],

            # LARGE SHAPES (double size, ~4-6 units)
            "triangle_equilateral_large": [
                (0, 0),  # Anchor: top vertex
                (-2, -3),  # Bottom left
                (2, -3)  # Bottom right
                # Width 4, height 3, sides ≈3.6 - best equilateral approximation
                # Note: Exact side length 3 impossible on integer grid while staying equilateral
            ],
            "square_large": [
                (0, 0),  # Anchor: top-left
                (4, 0),  # Top-right
                (4, -4),  # Bottom-right
                (0, -4)  # Bottom-left
                # Side length 4 - proper square, double the small square
            ],
            "triangle_isosceles_large": [
                (0, 0),  # Anchor: top vertex (apex)
                (-1, -5),  # Bottom left
                (1, -5)  # Bottom right
                # Width 2, height 5 - tall and narrow, distinctive from equilateral
            ]
        }

    def get_available_shapes_for_tier(self, tier):
        """Get available shape types for a given tier (cumulative)"""
        shapes = []

        # T1: Basic small shapes
        if tier >= 1:
            shapes.extend(["triangle_equilateral_small", "square_small"])

        # T2: Add small isosceles
        if tier >= 2:
            shapes.append("triangle_isosceles_small")

        # T3: Add large equilateral and square
        if tier >= 3:
            shapes.extend(["triangle_equilateral_large", "square_large"])

        # T4: Add large isosceles (all shapes now available)
        if tier >= 4:
            shapes.append("triangle_isosceles_large")

        return shapes

    def rotate_point(self, x, y, degrees):
        """Rotate a point around origin by degrees"""
        rad = math.radians(degrees)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        new_x = round(x * cos_a - y * sin_a)
        new_y = round(x * sin_a + y * cos_a)
        return (new_x, new_y)

    def get_rotated_shape_vertices(self, shape_type, anchor_x, anchor_y, rotation):
        """Get absolute vertices for a shape at anchor position with rotation"""
        template = self.shape_templates[shape_type]
        vertices = []
        for dx, dy in template:
            # Rotate offset around anchor
            rx, ry = self.rotate_point(dx, dy, rotation)
            # Add anchor position
            vertices.append((anchor_x + rx, anchor_y + ry))
        return vertices

    def cycle_rotation(self, event=None):
        """Cycle through common rotation angles (spacebar or shift)"""
        rotations = [0, 45, 90, 135, 180, 225, 270, 315]
        try:
            current_idx = rotations.index(self.current_rotation)
            next_idx = (current_idx + 1) % len(rotations)
            self.current_rotation = rotations[next_idx]
        except ValueError:
            self.current_rotation = 0

        self.rotation_var.set(str(self.current_rotation))
        self.update_shape_preview()

        # Redraw preview at last position if we have one
        if self.last_mouse_grid_pos:
            self.draw_grid()
            self.draw_shape_preview_at(self.last_mouse_grid_pos[0], self.last_mouse_grid_pos[1])

    def on_shape_mode_changed(self):
        """Handle shape mode selection change"""
        self.update_shape_preview()
        self.draw_grid()  # Clear any existing preview

    def reselect_last_material(self, event=None):
        """Reselect the last placed material (Enter key)"""
        if self.last_placed_material:
            self.select_material(self.last_placed_material)
            self.status_label.config(
                text=f"Reselected: {self.last_placed_material} (Enter shortcut)",
                foreground="purple"
            )
        else:
            self.status_label.config(
                text="No material placed yet - select from palette first",
                foreground="orange"
            )

    def get_grid_size_from_tier(self, tier):
        """Get grid size based on tier (doubled from original)"""
        tier_to_size = {1: 8, 2: 10, 3: 12, 4: 14}
        return tier_to_size.get(tier, 8)

    def load_files(self):
        """Load recipes, materials, and optional placements"""
        # Load materials
        self.materials_file = filedialog.askopenfilename(
            title="Select Materials JSON",
            filetypes=[("JSON files", "*.json")]
        )
        if not self.materials_file:
            return

        try:
            with open(self.materials_file, 'r') as f:
                data = json.load(f)
                materials_list = data.get('materials', data if isinstance(data, list) else [])
                for mat in materials_list:
                    mat_id = mat.get('materialId')
                    if mat_id:
                        self.materials_db[mat_id] = {
                            'name': mat.get('name', mat_id),
                            'tier': mat.get('tier', 1),
                            'category': mat.get('category', 'unknown')
                        }
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load materials:\n{e}")
            return

        # Load recipes
        self.recipes_file = filedialog.askopenfilename(
            title="Select Enchanting Recipes JSON",
            filetypes=[("JSON files", "*.json")]
        )
        if not self.recipes_file:
            return

        with open(self.recipes_file, 'r') as f:
            data = json.load(f)
            recipes_list = data.get('recipes', data if isinstance(data, list) else [])
            self.recipes = {r['recipeId']: r for r in recipes_list}

        # Load placements (optional)
        response = messagebox.askyesno(
            "Load Placements?",
            "Do you have an existing placements file to load?\n\nClick 'No' to start fresh."
        )

        if response:
            self.placements_file = filedialog.askopenfilename(
                title="Select Placements JSON (Optional)",
                filetypes=[("JSON files", "*.json")]
            )
            if self.placements_file:
                try:
                    with open(self.placements_file, 'r') as f:
                        data = json.load(f)
                        placements_list = data.get('placements', data if isinstance(data, list) else [])
                        for p in placements_list:
                            self.placements[p['recipeId']] = p.get('placementMap', {})
                except Exception as e:
                    messagebox.showwarning("Warning", f"Failed to load placements:\n{e}")
                    self.placements = {}
        else:
            self.placements_file = filedialog.asksaveasfilename(
                title="Where to save placements?",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            self.placements = {}

    def build_ui(self):
        """Build the main UI"""
        # Top frame
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Recipe:", font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)

        self.recipe_var = tk.StringVar()
        recipe_dropdown = ttk.Combobox(top_frame, textvariable=self.recipe_var,
                                       values=sorted(self.recipes.keys()),
                                       state='readonly', width=50)
        recipe_dropdown.pack(side=tk.LEFT, padx=5)
        recipe_dropdown.bind('<<ComboboxSelected>>', self.on_recipe_selected)

        self.status_label = ttk.Label(top_frame, text="Select a recipe | SHIFT=rotate, SPACE/ENTER=reselect material",
                                      foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=20)

        # Main content
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel
        left_frame = ttk.LabelFrame(main_frame, text="Recipe & Tools", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5)

        # Recipe info
        info_frame = ttk.Frame(left_frame)
        info_frame.pack(fill=tk.X, pady=5)

        self.info_text = tk.Text(info_frame, height=6, width=40, wrap=tk.WORD,
                                 state='disabled', bg='#f0f0f0')
        self.info_text.pack(fill=tk.X)

        # Shape tools
        shape_frame = ttk.LabelFrame(left_frame, text="Shape Tools", padding="10")
        shape_frame.pack(fill=tk.X, pady=10)

        ttk.Label(shape_frame, text="Mode:").pack(anchor=tk.W)

        self.shape_type_var = tk.StringVar(value="place_materials")

        # Container for all mode options
        modes_frame = ttk.Frame(shape_frame)
        modes_frame.pack(anchor=tk.W)

        # Add "Place Materials" option at top
        ttk.Radiobutton(modes_frame, text="Place Materials (No Shape)",
                        variable=self.shape_type_var, value="place_materials",
                        command=self.on_shape_mode_changed).pack(anchor=tk.W)

        ttk.Separator(modes_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        # Shape radio buttons frame (will be populated on recipe selection)
        self.shape_buttons_frame = ttk.Frame(modes_frame)
        self.shape_buttons_frame.pack(anchor=tk.W)

        rotation_frame = ttk.Frame(shape_frame)
        rotation_frame.pack(fill=tk.X, pady=5)
        ttk.Label(rotation_frame, text="Rotation (°):").pack(side=tk.LEFT, padx=5)
        self.rotation_var = tk.StringVar(value="0")
        rotation_entry = ttk.Entry(rotation_frame, textvariable=self.rotation_var, width=8)
        rotation_entry.pack(side=tk.LEFT, padx=5)
        rotation_entry.bind('<Return>', lambda e: self.update_rotation_from_entry())
        rotation_entry.bind('<KP_Enter>', lambda e: self.update_rotation_from_entry())
        ttk.Label(rotation_frame, text="(Shift to rotate)").pack(side=tk.LEFT)

        # Material palette
        palette_label = ttk.Label(left_frame, text="Material Palette", font=('Arial', 11, 'bold'))
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

        # Shape list with delete
        shapes_list_frame = ttk.LabelFrame(left_frame, text="Placed Shapes", padding="5")
        shapes_list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.shapes_listbox = tk.Listbox(shapes_list_frame, height=6)
        self.shapes_listbox.pack(fill=tk.BOTH, expand=True)
        self.shapes_listbox.bind('<<ListboxSelect>>', self.on_shape_selected)

        btn_frame = ttk.Frame(shapes_list_frame)
        btn_frame.pack(fill=tk.X, pady=2)

        ttk.Button(btn_frame, text="❌ Delete Selected",
                   command=self.delete_selected_shape).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        ttk.Button(btn_frame, text="🗑️ Clear All",
                   command=self.clear_all_shapes).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Validation
        self.validation_frame = ttk.LabelFrame(left_frame, text="Validation & Save", padding="10")
        self.validation_frame.pack(fill=tk.X, pady=10)

        self.validation_label = ttk.Label(self.validation_frame, text="No recipe selected", foreground="gray")
        self.validation_label.pack(pady=5)

        self.save_btn = tk.Button(self.validation_frame, text="💾 Save Changes to Recipe",
                                  command=self.save_recipe_changes,
                                  bg='#2196F3', fg='white',
                                  font=('Arial', 11, 'bold'),
                                  height=2,
                                  state='disabled')
        self.save_btn.pack(pady=5, fill=tk.X, ipady=5)

        # Right panel - Grid
        right_frame = ttk.LabelFrame(main_frame, text="Pattern Grid", padding="10")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Canvas for grid
        max_grid_size = 14  # T4 has largest grid
        canvas_size = max_grid_size * self.cell_size + 60
        self.canvas = tk.Canvas(right_frame, width=canvas_size, height=canvas_size,
                                bg='white', highlightthickness=1, highlightbackground='gray')
        self.canvas.pack(pady=10)
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<Button-3>', self.on_canvas_right_click)
        self.canvas.bind('<Motion>', self.on_canvas_motion)

        instructions = ttk.Label(right_frame,
                                 text="1. Select shape mode or 'Place Materials'\n2. If shape: preview follows mouse, SHIFT rotates\n3. Click to place shape at anchor point\n4. Select material (SPACE to reselect), click vertex\n5. Right-click vertex to toggle Key status\n6. Click shape in list to highlight",
                                 foreground="blue", justify=tk.LEFT)
        instructions.pack(pady=10)

        # JSON preview
        json_frame = ttk.LabelFrame(right_frame, text="Placement JSON", padding="5")
        json_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.json_text = tk.Text(json_frame, height=12, width=60, wrap=tk.WORD,
                                 bg='#f0f0f0', font=('Courier', 9))
        self.json_text.pack(fill=tk.BOTH, expand=True)

    def update_shape_radio_buttons(self, tier):
        """Update available shape radio buttons based on tier"""
        # Clear existing buttons
        for widget in self.shape_buttons_frame.winfo_children():
            widget.destroy()

        # Get available shapes for this tier
        available_shapes = self.get_available_shapes_for_tier(tier)

        # Set default if current selection not available
        current_val = self.shape_type_var.get()
        if current_val != "place_materials" and current_val not in available_shapes:
            self.shape_type_var.set(available_shapes[0])

        # Create radio buttons
        for shape in available_shapes:
            display_name = shape.replace('_', ' ').title()
            ttk.Radiobutton(self.shape_buttons_frame, text=display_name,
                            variable=self.shape_type_var, value=shape,
                            command=self.on_shape_mode_changed).pack(anchor=tk.W)

    def grid_to_canvas(self, x, y):
        """Convert grid coordinates to canvas coordinates"""
        half = self.grid_size // 2
        canvas_x = (x + half) * self.cell_size + 30
        canvas_y = (half - y) * self.cell_size + 30
        return canvas_x, canvas_y

    def canvas_to_grid(self, canvas_x, canvas_y):
        """Convert canvas coordinates to grid coordinates"""
        half = self.grid_size // 2
        x = round((canvas_x - 30) / self.cell_size - half)
        y = round(half - (canvas_y - 30) / self.cell_size)
        return x, y

    def draw_grid(self):
        """Draw the grid on canvas"""
        self.canvas.delete('all')

        half = self.grid_size // 2

        # Draw grid lines (light)
        for i in range(self.grid_size + 1):
            x = i * self.cell_size + 30
            y = i * self.cell_size + 30
            # Vertical
            self.canvas.create_line(x, 30, x, self.grid_size * self.cell_size + 30,
                                    fill='#E0E0E0', width=1)
            # Horizontal
            self.canvas.create_line(30, y, self.grid_size * self.cell_size + 30, y,
                                    fill='#E0E0E0', width=1)

        # Draw center axes (darker)
        center = half * self.cell_size + 30
        self.canvas.create_line(center, 30, center, self.grid_size * self.cell_size + 30,
                                fill='#9E9E9E', width=2)
        self.canvas.create_line(30, center, self.grid_size * self.cell_size + 30, center,
                                fill='#9E9E9E', width=2)

        # Draw shape lines (regular shapes)
        for i, shape in enumerate(self.current_shapes):
            if i == self.selected_shape_idx:
                continue  # Draw selected shape last with highlight
            vertices = [eval(v) if isinstance(v, str) else v for v in shape['vertices']]
            for j in range(len(vertices)):
                v1 = vertices[j]
                v2 = vertices[(j + 1) % len(vertices)]
                cx1, cy1 = self.grid_to_canvas(v1[0], v1[1])
                cx2, cy2 = self.grid_to_canvas(v2[0], v2[1])
                self.canvas.create_line(cx1, cy1, cx2, cy2,
                                        fill='#2196F3', width=2)

        # Draw selected shape with highlight
        if self.selected_shape_idx is not None and self.selected_shape_idx < len(self.current_shapes):
            shape = self.current_shapes[self.selected_shape_idx]
            vertices = [eval(v) if isinstance(v, str) else v for v in shape['vertices']]
            for j in range(len(vertices)):
                v1 = vertices[j]
                v2 = vertices[(j + 1) % len(vertices)]
                cx1, cy1 = self.grid_to_canvas(v1[0], v1[1])
                cx2, cy2 = self.grid_to_canvas(v2[0], v2[1])
                # Draw thick yellow highlight
                self.canvas.create_line(cx1, cy1, cx2, cy2,
                                        fill='#FFD700', width=5)
                # Draw blue line on top
                self.canvas.create_line(cx1, cy1, cx2, cy2,
                                        fill='#2196F3', width=2)

        # Draw all grid points
        for x in range(-half, half + 1):
            for y in range(-half, half + 1):
                cx, cy = self.grid_to_canvas(x, y)

                # Determine point appearance
                coord = (x, y)
                if coord in self.current_vertices:
                    vertex_data = self.current_vertices[coord]
                    has_material = vertex_data.get('materialId')
                    is_key = vertex_data.get('isKey', False)

                    if has_material:
                        # Material assigned
                        color = '#FF6B6B' if is_key else '#4ECDC4'
                        radius = 8
                        # Draw material label
                        mat_info = self.materials_db.get(has_material, {"name": has_material})
                        name = mat_info['name'][:6]
                        self.canvas.create_text(cx, cy - 15, text=name, font=('Arial', 8))
                    else:
                        # Empty vertex (part of shape)
                        color = '#FFE66D'
                        radius = 6
                else:
                    # Regular grid point
                    color = '#CCCCCC'
                    radius = 3

                self.canvas.create_oval(cx - radius, cy - radius,
                                        cx + radius, cy + radius,
                                        fill=color, outline='black', width=1,
                                        tags=f'point_{x}_{y}')

    def on_shape_selected(self, event=None):
        """Handle shape selection in listbox"""
        selection = self.shapes_listbox.curselection()
        if selection:
            self.selected_shape_idx = selection[0]
            self.draw_grid()
            self.status_label.config(
                text=f"Shape {self.selected_shape_idx + 1} highlighted",
                foreground="purple"
            )
        else:
            self.selected_shape_idx = None
            self.draw_grid()

    def draw_shape_preview_at(self, x, y):
        """Draw shape preview at given grid coordinates"""
        shape_type = self.shape_type_var.get()

        # Don't preview if in "place materials" mode
        if shape_type == "place_materials":
            return

        rotation = self.current_rotation
        vertices = self.get_rotated_shape_vertices(shape_type, x, y, rotation)

        # Check if shape fits
        half = self.grid_size // 2
        all_fit = all(abs(vx) <= half and abs(vy) <= half for vx, vy in vertices)
        preview_color = '#00FF00' if all_fit else '#FF0000'  # Green if fits, red if doesn't

        # Draw preview lines
        for i in range(len(vertices)):
            v1 = vertices[i]
            v2 = vertices[(i + 1) % len(vertices)]
            cx1, cy1 = self.grid_to_canvas(v1[0], v1[1])
            cx2, cy2 = self.grid_to_canvas(v2[0], v2[1])
            self.canvas.create_line(cx1, cy1, cx2, cy2,
                                    fill=preview_color, width=2, dash=(4, 4))

        # Draw preview vertices
        for vx, vy in vertices:
            cx, cy = self.grid_to_canvas(vx, vy)
            self.canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6,
                                    fill=preview_color, outline='black', width=1)

    def on_canvas_motion(self, event):
        """Handle mouse motion for shape preview"""
        x, y = self.canvas_to_grid(event.x, event.y)

        # Check bounds
        half = self.grid_size // 2
        if abs(x) > half or abs(y) > half:
            return

        # Store last position
        self.last_mouse_grid_pos = (x, y)

        # Redraw grid to clear old preview
        self.draw_grid()

        # Draw preview
        self.draw_shape_preview_at(x, y)

    def on_canvas_click(self, event):
        """Handle canvas click"""
        x, y = self.canvas_to_grid(event.x, event.y)

        # Check bounds
        half = self.grid_size // 2
        if abs(x) > half or abs(y) > half:
            return

        coord = (x, y)
        shape_type = self.shape_type_var.get()

        # Check if placing shape
        if shape_type != "place_materials":
            self.place_shape_at(coord)
            return

        # Place materials mode - assign material to vertex
        if coord in self.current_vertices:
            if self.selected_material:
                self.current_vertices[coord]['materialId'] = self.selected_material
                self.last_placed_material = self.selected_material
                self.selected_material = None
                self.status_label.config(text="Material assigned", foreground="green")
                self.draw_grid()
                self.rebuild_palette()
                self.update_json_preview()
                self.save_files()
            else:
                # Clear material
                if self.current_vertices[coord].get('materialId'):
                    self.current_vertices[coord] = {'materialId': None, 'isKey': False}
                    self.draw_grid()
                    self.rebuild_palette()
                    self.update_json_preview()
                    self.save_files()
        else:
            self.status_label.config(
                text="No vertex at this location. Place a shape first or click an existing vertex.",
                foreground="orange"
            )

    def on_canvas_right_click(self, event):
        """Handle right-click to toggle key status"""
        x, y = self.canvas_to_grid(event.x, event.y)
        coord = (x, y)

        if coord in self.current_vertices and self.current_vertices[coord].get('materialId'):
            is_key = self.current_vertices[coord].get('isKey', False)
            self.current_vertices[coord]['isKey'] = not is_key
            self.status_label.config(
                text=f"Vertex {'marked as KEY' if not is_key else 'unmarked as key'}",
                foreground="purple"
            )
            self.draw_grid()
            self.update_json_preview()
            self.save_files()

    def update_rotation_from_entry(self, event=None):
        """Update rotation from manual entry"""
        try:
            rotation = int(self.rotation_var.get()) % 360
            self.current_rotation = rotation
            self.rotation_var.set(str(rotation))
            self.update_shape_preview()

            # Redraw preview at last position if we have one
            if self.last_mouse_grid_pos:
                self.draw_grid()
                self.draw_shape_preview_at(self.last_mouse_grid_pos[0], self.last_mouse_grid_pos[1])
        except ValueError:
            self.rotation_var.set(str(self.current_rotation))
        return 'break'  # Prevent event propagation

    def update_shape_preview(self):
        """Update preview text when shape/rotation changes"""
        shape = self.shape_type_var.get()
        rotation = self.current_rotation

        if shape == "place_materials":
            self.status_label.config(
                text="Mode: Place Materials - Click vertices to assign materials",
                foreground="blue"
            )
        else:
            self.status_label.config(
                text=f"Shape: {shape.replace('_', ' ').title()}, Rotation: {rotation}° - Move mouse to preview",
                foreground="purple"
            )

    def place_shape_at(self, anchor):
        """Place the currently selected shape at the clicked anchor position"""
        shape_type = self.shape_type_var.get()

        if shape_type == "place_materials":
            return

        rotation = self.current_rotation

        # Get vertices
        vertices = self.get_rotated_shape_vertices(shape_type, anchor[0], anchor[1], rotation)

        # Validate all vertices fit in grid
        half = self.grid_size // 2
        for vx, vy in vertices:
            if abs(vx) > half or abs(vy) > half:
                messagebox.showerror("Error", f"Shape doesn't fit! Vertex ({vx},{vy}) is outside grid.")
                self.status_label.config(text="Shape placement cancelled", foreground="red")
                return

        # Add shape to list
        shape_data = {
            "type": shape_type,
            "vertices": [f"{v[0]},{v[1]}" for v in vertices],
            "rotation": rotation
        }
        self.current_shapes.append(shape_data)

        # Activate vertices
        for v in vertices:
            if v not in self.current_vertices:
                self.current_vertices[v] = {"materialId": None, "isKey": False}

        self.draw_grid()
        self.update_shapes_list()
        self.update_json_preview()
        self.save_files()
        self.status_label.config(text="Shape placed! Assign materials to vertices.", foreground="green")

    def on_recipe_selected(self, event=None):
        """Handle recipe selection"""
        recipe_id = self.recipe_var.get()
        if not recipe_id:
            return

        self.current_recipe_id = recipe_id
        recipe = self.recipes[recipe_id]

        # Store original inputs
        self.current_recipe_original_inputs = [
            {"materialId": inp["materialId"], "quantity": inp["quantity"]}
            for inp in recipe.get('inputs', [])
        ]

        # Load existing placement
        placement = self.placements.get(recipe_id, {})
        self.current_vertices = placement.get('vertices', {})
        # Convert string keys to tuples
        self.current_vertices = {eval(k) if isinstance(k, str) else k: v
                                 for k, v in self.current_vertices.items()}
        self.current_shapes = placement.get('shapes', [])
        self.selected_shape_idx = None

        # Update grid size
        station_tier = recipe.get('stationTier', 1)
        self.grid_size = self.get_grid_size_from_tier(station_tier)

        # Update available shapes for this tier
        self.update_shape_radio_buttons(station_tier)

        # Update UI
        self.update_recipe_info(recipe)
        self.rebuild_palette()
        self.draw_grid()
        self.update_shapes_list()
        self.update_json_preview()
        self.save_btn.config(state='normal')
        self.status_label.config(text=f"Loaded: {recipe_id}", foreground="green")

    def update_recipe_info(self, recipe):
        """Update recipe info display"""
        self.info_text.config(state='normal')
        self.info_text.delete('1.0', tk.END)

        station_tier = recipe.get('stationTier', 1)
        grid_size = self.get_grid_size_from_tier(station_tier)

        info = f"Recipe ID: {recipe['recipeId']}\n"
        info += f"Enchantment: {recipe.get('enchantmentName', 'N/A')}\n"
        info += f"Station Tier: T{station_tier} ({grid_size}x{grid_size} grid)\n"
        info += f"Applies To: {', '.join(recipe.get('applicableTo', []))}\n"
        info += f"Narrative: {recipe.get('metadata', {}).get('narrative', 'N/A')}"

        self.info_text.insert('1.0', info)
        self.info_text.config(state='disabled')

    def rebuild_palette(self):
        """Rebuild material palette"""
        for widget in self.palette_frame.winfo_children():
            widget.destroy()

        if not self.current_recipe_id:
            return

        # Get materials from original recipe
        recipe_materials = {}
        for inp in self.current_recipe_original_inputs:
            recipe_materials[inp['materialId']] = inp['quantity']

        # Count materials in vertices
        vertex_counts = Counter(v.get('materialId') for v in self.current_vertices.values() if v.get('materialId'))

        # Combine
        all_materials = set(recipe_materials.keys()) | set(vertex_counts.keys())

        for material_id in sorted(all_materials):
            required = recipe_materials.get(material_id, 0)
            used = vertex_counts.get(material_id, 0)

            mat_info = self.materials_db.get(material_id, {"name": material_id, "tier": "?"})
            tier_str = f"T{mat_info['tier']}" if mat_info['tier'] != "?" else "T?"

            # Color coding
            if required > 0 and used == required:
                color = '#4CAF50'
            elif required > 0 and used < required:
                color = '#f44336'
            elif required > 0 and used > required:
                color = '#FFC107'
            else:
                color = '#9C27B0'

            frame = ttk.Frame(self.palette_frame)
            frame.pack(fill=tk.X, pady=2)

            label_text = f"[{tier_str}] {mat_info['name']} ({used}/{required})" if required > 0 else f"[{tier_str}] {mat_info['name']} ({used}/NEW)"

            btn = tk.Button(frame, text=label_text, width=35,
                            command=lambda m=material_id: self.select_material(m),
                            bg=color, fg='white', relief=tk.RAISED)
            btn.pack(side=tk.LEFT, padx=2)

        self.update_validation_status()

    def select_material(self, material_id):
        """Select material for placement"""
        self.selected_material = material_id
        self.status_label.config(text=f"Selected: {material_id} - Click vertex to assign",
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

    def update_shapes_list(self):
        """Update the shapes listbox"""
        self.shapes_listbox.delete(0, tk.END)
        for i, shape in enumerate(self.current_shapes):
            display = f"{i + 1}. {shape['type'].replace('_', ' ').title()} @ {shape['rotation']}°"
            self.shapes_listbox.insert(tk.END, display)

    def delete_selected_shape(self):
        """Delete the selected shape"""
        selection = self.shapes_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "No shape selected")
            return

        idx = selection[0]
        shape = self.current_shapes[idx]

        # Remove vertices that belong only to this shape
        shape_vertices = set(eval(v) if isinstance(v, str) else v for v in shape['vertices'])

        # Check if any other shape uses these vertices
        other_shapes_vertices = set()
        for i, s in enumerate(self.current_shapes):
            if i != idx:
                other_shapes_vertices.update(eval(v) if isinstance(v, str) else v for v in s['vertices'])

        # Remove vertices not used by other shapes
        vertices_to_remove = shape_vertices - other_shapes_vertices
        for v in vertices_to_remove:
            if v in self.current_vertices:
                del self.current_vertices[v]

        # Remove shape
        self.current_shapes.pop(idx)
        self.selected_shape_idx = None

        self.draw_grid()
        self.rebuild_palette()
        self.update_shapes_list()
        self.update_json_preview()
        self.save_files()
        self.status_label.config(text="Shape deleted", foreground="blue")

    def clear_all_shapes(self):
        """Clear all shapes and vertices"""
        if not self.current_shapes:
            return

        response = messagebox.askyesno("Confirm", "Clear all shapes and start over?")
        if response:
            self.current_shapes = []
            self.current_vertices = {}
            self.selected_shape_idx = None
            self.draw_grid()
            self.rebuild_palette()
            self.update_shapes_list()
            self.update_json_preview()
            self.save_files()
            self.status_label.config(text="All shapes cleared", foreground="blue")

    def update_json_preview(self):
        """Update JSON preview"""
        self.json_text.delete('1.0', tk.END)

        if not self.current_recipe_id:
            return

        placement = {
            "gridType": f"square_{self.grid_size}x{self.grid_size}",
            "vertices": {f"{k[0]},{k[1]}": v for k, v in self.current_vertices.items()},
            "shapes": self.current_shapes
        }

        json_str = json.dumps(placement, indent=2)
        self.json_text.insert('1.0', json_str)

    def update_validation_status(self):
        """Update validation status"""
        if not self.current_recipe_id:
            self.validation_label.config(text="No recipe selected", foreground="gray")
            return

        # Check if all shapes have at least one material
        shapes_valid = True
        for shape in self.current_shapes:
            shape_vertices = [eval(v) if isinstance(v, str) else v for v in shape['vertices']]
            has_material = any(self.current_vertices.get(v, {}).get('materialId') for v in shape_vertices)
            if not has_material:
                shapes_valid = False
                break

        vertex_count = sum(1 for v in self.current_vertices.values() if v.get('materialId'))

        if not self.current_shapes:
            msg = "⚠ No shapes placed"
            color = "orange"
        elif not shapes_valid:
            msg = "⚠ All shapes must have at least 1 material"
            color = "orange"
        else:
            msg = f"✓ {len(self.current_shapes)} shapes, {vertex_count} materials assigned"
            color = "green"

        self.validation_label.config(text=msg, foreground=color)

    def save_recipe_changes(self):
        """Save pattern and update recipe inputs"""
        if not self.current_recipe_id:
            messagebox.showwarning("No Recipe", "Please select a recipe first")
            return

        # Count materials in vertices
        material_counts = Counter(v.get('materialId') for v in self.current_vertices.values()
                                  if v.get('materialId'))

        # Update recipe inputs
        new_inputs = [{"materialId": mat_id, "quantity": count}
                      for mat_id, count in sorted(material_counts.items())]

        self.recipes[self.current_recipe_id]['inputs'] = new_inputs
        self.current_recipe_original_inputs = new_inputs.copy()

        self.rebuild_palette()

        # Actually save the files
        success = self.save_files()

        if success:
            self.status_label.config(text="✅ Recipe and placements saved successfully!", foreground="green")
            messagebox.showinfo("Saved",
                                "Files saved successfully!\n\nCheck the same folder as your input files for:\n- [filename]-modified.json files")
        else:
            self.status_label.config(text="❌ Save failed - check console", foreground="red")

    def save_files(self):
        """Save both recipes and placements"""
        if not self.recipes_file or not self.placements_file:
            self.status_label.config(text="❌ Cannot save - file paths not set", foreground="red")
            messagebox.showerror("Save Error", "File paths not set. Please reload the application.")
            return False

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

            print(f"✓ Saved recipes to: {recipes_output}")

            # Save placements
            placements_output = Path(self.placements_file).parent / f"{Path(self.placements_file).stem}-modified.json"

            if self.current_recipe_id:
                self.placements[self.current_recipe_id] = {
                    "gridType": f"square_{self.grid_size}x{self.grid_size}",
                    "vertices": {f"{k[0]},{k[1]}": v for k, v in self.current_vertices.items()},
                    "shapes": self.current_shapes
                }

            placements_list = [
                {
                    "recipeId": recipe_id,
                    "placementMap": placement_map
                }
                for recipe_id, placement_map in self.placements.items()
                if placement_map.get('shapes')
            ]

            with open(placements_output, 'w') as f:
                json.dump({
                    "metadata": {
                        "version": "1.0",
                        "totalPlacements": len(placements_list)
                    },
                    "placements": placements_list
                }, f, indent=2)

            print(f"✓ Saved placements to: {placements_output}")
            return True

        except Exception as e:
            error_msg = f"❌ Save failed: {e}"
            self.status_label.config(text=error_msg, foreground="red")
            messagebox.showerror("Save Error", f"Failed to save files:\n\n{e}")
            print(error_msg)
            import traceback
            traceback.print_exc()
            return False


def main():
    root = tk.Tk()
    app = EnchantingDesigner(root)
    root.mainloop()


if __name__ == "__main__":
    main()
