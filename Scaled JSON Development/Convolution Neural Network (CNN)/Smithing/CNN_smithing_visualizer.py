"""
CNN Smithing Dataset Visualizer — Tkinter GUI Edition

Interactive visualization of smithing CNN training data with:
  • Original recipe placements
  • Valid/Invalid augmented samples
  • Side-by-side comparison
  • Category/tier legend with interactive tabs

Usage:
  python CNN_smithing_visualizer.py
"""

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk, simpledialog, filedialog
from pathlib import Path
import json
from colorsys import hsv_to_rgb
import random


class SmithingDatasetVisualizer:
    """Data model for smithing CNN dataset."""

    CATEGORY_SHAPES = {
        'metal': np.array([[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]], dtype=np.float32),
        'wood':  np.array([[1,1,1,1],[0,0,0,0],[1,1,1,1],[0,0,0,0]], dtype=np.float32),
        'stone': np.array([[1,0,0,1],[0,1,1,0],[0,1,1,0],[1,0,0,1]], dtype=np.float32),
        'monster_drop': np.array([[0,1,1,0],[1,1,1,1],[1,1,1,1],[0,1,1,0]], dtype=np.float32),
        'elemental':    np.array([[0,1,1,0],[1,1,1,1],[1,1,1,1],[0,1,1,0]], dtype=np.float32),
    }
    DEFAULT_SHAPE = np.ones((4, 4), dtype=np.float32)
    TIER_FILL_SIZES = {1: 1, 2: 2, 3: 3, 4: 4}

    def __init__(self, dataset_path, materials_path, placements_path, use_shapes=True):
        self.use_shapes = use_shapes
        print("Loading dataset...")

        data = np.load(dataset_path)
        self.X_train = data['X_train']
        self.y_train = data['y_train']
        self.X_val = data['X_val']
        self.y_val = data['y_val']

        self.X_all = np.concatenate([self.X_train, self.X_val])
        self.y_all = np.concatenate([self.y_train, self.y_val])
        self.valid_indices = np.where(self.y_all == 1)[0]
        self.invalid_indices = np.where(self.y_all == 0)[0]

        with open(materials_path) as f:
            materials_data = json.load(f)
        self.materials_dict = {m['materialId']: m for m in materials_data['materials']}

        with open(placements_path) as f:
            placements_data = json.load(f)
        self.original_recipes = [
            p for p in placements_data['placements']
            if not any(p['recipeId'].endswith(f'_t{i}') for i in range(1, 5))
        ]

        print("Rendering original recipes...")
        self.original_images = [self._render_recipe(r) for r in self.original_recipes]

        print(f"✓ Loaded: original={len(self.original_recipes)}, "
              f"valid={len(self.valid_indices)}, invalid={len(self.invalid_indices)}, "
              f"total={len(self.X_all)}, shape={self.X_all.shape[1:]}")

    def _material_to_color(self, material_id):
        if material_id is None:
            return np.zeros(3)
        if material_id not in self.materials_dict:
            return np.full(3, 0.3)

        mat = self.materials_dict[material_id]
        cat = mat.get('category', 'unknown')
        tier = mat.get('tier', 1)
        tags = mat.get('metadata', {}).get('tags', [])

        if cat == 'elemental':
            hues = {'fire':0, 'water':210, 'earth':120, 'air':60, 'lightning':270, 'ice':180, 'light':45, 'dark':280, 'void':290, 'chaos':330}
            hue = next((hues[t] for t in tags if t in hues), 280)
        else:
            hue = {'metal':210, 'wood':30, 'stone':0, 'monster_drop':300, 'gem':280, 'herb':120, 'fabric':45}.get(cat, 0)

        value = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}.get(tier, 0.5)
        sat = 0.2 if cat == 'stone' else 0.6
        if any(t in tags for t in ['legendary', 'mythical']):
            sat = min(1.0, sat + 0.2)
        elif any(t in tags for t in ['magical', 'ancient']):
            sat = min(1.0, sat + 0.1)

        return np.array(hsv_to_rgb(hue / 360.0, sat, value))

    def _get_shape_mask(self, material_id):
        if material_id is None or material_id not in self.materials_dict:
            return self.DEFAULT_SHAPE
        cat = self.materials_dict[material_id].get('category', 'unknown')
        return self.CATEGORY_SHAPES.get(cat, self.DEFAULT_SHAPE)

    def _get_tier_fill_mask(self, material_id, cell_size=4):
        if material_id is None or material_id not in self.materials_dict:
            return np.zeros((cell_size, cell_size), dtype=np.float32)
        tier = self.materials_dict[material_id].get('tier', 1)
        fill_size = self.TIER_FILL_SIZES.get(tier, 4)
        mask = np.zeros((cell_size, cell_size), dtype=np.float32)
        off = (cell_size - fill_size) // 2
        mask[off:off+fill_size, off:off+fill_size] = 1.0
        return mask

    def _placement_to_grid(self, placement):
        grid = [[None]*9 for _ in range(9)]
        positions = [tuple(map(int, k.split(','))) for k in placement['placementMap']]
        if not positions:
            return grid
        min_y, max_y = min(p[0] for p in positions), max(p[0] for p in positions)
        min_x, max_x = min(p[1] for p in positions), max(p[1] for p in positions)
        off_y = (9 - (max_y - min_y + 1)) // 2
        off_x = (9 - (max_x - min_x + 1)) // 2
        for pos_str, mat_id in placement['placementMap'].items():
            y, x = map(int, pos_str.split(','))
            fy, fx = off_y + (y - min_y), off_x + (x - min_x)
            if 0 <= fy < 9 and 0 <= fx < 9:
                grid[fy][fx] = mat_id
        return grid

    def _grid_to_image(self, grid, cell_size=4):
        sz = 9 * cell_size
        img = np.zeros((sz, sz, 3), dtype=np.float32)
        for i in range(9):
            for j in range(9):
                mat = grid[i][j]
                if mat is None:
                    continue
                color = self._material_to_color(mat)
                if self.use_shapes:
                    combined = self._get_shape_mask(mat) * self._get_tier_fill_mask(mat, cell_size)
                    for c in range(3):
                        img[i*cell_size:(i+1)*cell_size, j*cell_size:(j+1)*cell_size, c] = color[c] * combined
                else:
                    img[i*cell_size:(i+1)*cell_size, j*cell_size:(j+1)*cell_size] = color
        return img

    def _render_recipe(self, recipe):
        return self._grid_to_image(self._placement_to_grid(recipe))

    def get_materials_for_recipe(self, recipe):
        result = []
        for mat_id in set(recipe['placementMap'].values()):
            if mat_id in self.materials_dict:
                m = self.materials_dict[mat_id]
                result.append((m.get('name', mat_id), m.get('category','?'), m.get('tier',1)))
        return result

    def add_cell_borders(self, img, cell_size=4, border_boost=0.25):
        """Add 1px borders between cells with boosted brightness.

        Args:
            img: 36x36x3 float image
            cell_size: pixels per cell (4 for 9x9 grid)
            border_boost: brightness boost for borders (0.0-1.0)

        Returns:
            Modified image with cell borders
        """
        img_bordered = img.copy()

        # Draw vertical grid lines
        for x in range(cell_size, 36, cell_size):
            for y in range(36):
                # Boost the brightness of border pixels
                current = img_bordered[y, x]
                if np.any(current > 0):
                    # Brighten existing colors
                    img_bordered[y, x] = np.clip(current + border_boost, 0, 1)
                else:
                    # Draw light gray on empty cells
                    img_bordered[y, x] = np.full(3, 0.15)

        # Draw horizontal grid lines
        for y in range(cell_size, 36, cell_size):
            for x in range(36):
                current = img_bordered[y, x]
                if np.any(current > 0):
                    img_bordered[y, x] = np.clip(current + border_boost, 0, 1)
                else:
                    img_bordered[y, x] = np.full(3, 0.15)

        return img_bordered

    def set_white_background(self, img):
        """Convert black background to white, keeping material colors.

        Args:
            img: 36x36x3 float image with black (0,0,0) background

        Returns:
            Image with white (1,1,1) background
        """
        img_white = img.copy()
        # Detect black/near-black pixels (all channels < 0.05)
        black_mask = np.all(img < 0.05, axis=2)
        img_white[black_mask] = 1.0  # Replace with white
        return img_white


class SmithingVisualizerApp:
    """Tkinter GUI for smithing dataset."""

    BG, PANEL, BAR = '#1a1a2e', '#16213e', '#0f3460'
    FG, FG_DIM = '#e0e0e0', '#888888'
    TAB_KEYS = ['original', 'valid', 'invalid', 'compare', 'legend']
    TAB_LABELS = ['Original', 'Valid', 'Invalid', 'Compare', 'Legend']
    TAB_COLORS = {'original':'#4A90D9', 'valid':'#27AE60', 'invalid':'#E74C3C', 'compare':'#8E44AD', 'legend':'#F39C12'}
    GRID_OPTIONS = [1, 4, 9, 16, 25]

    def __init__(self, viz: SmithingDatasetVisualizer):
        self.viz = viz
        self.tab = 'original'
        self.page = 0
        self.per_page = 25
        self.seed = 42
        self._items = []
        self.show_borders = False
        self.white_background = False

        self.root = tk.Tk()
        self.root.title("CNN Smithing Dataset Viewer")
        self.root.geometry("1280x900")
        self.root.configure(bg=self.BG)
        self.root.minsize(900, 650)

        self._apply_style()
        self._build_ui()
        self._switch_tab('original')

    def _apply_style(self):
        s = ttk.Style()
        s.theme_use('clam')

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=self.PANEL, height=55)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        tk.Label(hdr, text="Smithing CNN Dataset", font=('Helvetica', 15, 'bold'),
                 fg=self.FG, bg=self.PANEL).pack(side='left', padx=18, pady=12)

        stats = (f"Original: {len(self.viz.original_recipes)} · Valid: {len(self.viz.valid_indices)} · "
                 f"Invalid: {len(self.viz.invalid_indices)} · Total: {len(self.viz.X_all)}")
        tk.Label(hdr, text=stats, font=('Helvetica', 9),
                 fg=self.FG_DIM, bg=self.PANEL).pack(side='left')

        tab_bar = tk.Frame(self.root, bg=self.BAR, height=38)
        tab_bar.pack(fill='x')
        tab_bar.pack_propagate(False)
        self._tab_btns = {}
        for key, label in zip(self.TAB_KEYS, self.TAB_LABELS):
            btn = tk.Button(tab_bar, text=f"  {label}  ", font=('Helvetica', 10, 'bold'),
                            bg=self.BAR, fg=self.FG_DIM, relief='flat', cursor='hand2', bd=0,
                            command=lambda k=key: self._switch_tab(k))
            btn.pack(side='left', fill='y', ipady=4)
            self._tab_btns[key] = btn

        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill='both', expand=True)

        sb = tk.Frame(body, bg=self.PANEL, width=210)
        sb.pack(side='right', fill='y')
        sb.pack_propagate(False)
        self._build_sidebar(sb)

        self.fig = Figure(facecolor=self.BG)
        self.canvas = FigureCanvasTkAgg(self.fig, master=body)
        self.canvas.get_tk_widget().pack(side='left', fill='both', expand=True)
        self.canvas.mpl_connect('button_press_event', self._on_click)

        ctrl = tk.Frame(self.root, bg=self.BAR, height=46)
        ctrl.pack(fill='x')
        ctrl.pack_propagate(False)
        self._build_controls(ctrl)

        self._status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self._status, font=('Helvetica', 8),
                 fg=self.FG_DIM, bg='#0a0a1a', anchor='w', padx=8).pack(fill='x', side='bottom')

    def _build_sidebar(self, parent):
        tk.Label(parent, text="INFO", font=('Helvetica', 9, 'bold'),
                 fg=self.FG_DIM, bg=self.PANEL).pack(pady=(12, 4), padx=10, anchor='w')
        ttk.Separator(parent, orient='horizontal').pack(fill='x', padx=10)

        self._sb_title = tk.Label(parent, text="Click a recipe", wraplength=190,
                                   font=('Helvetica', 9), fg=self.FG, bg=self.PANEL, justify='left')
        self._sb_title.pack(padx=10, pady=6, anchor='w')

        self._sb_body = tk.Text(parent, font=('Helvetica', 8), fg=self.FG,
                                 bg=self.PANEL, relief='flat', wrap='word', state='disabled',
                                 height=14, width=24)
        self._sb_body.pack(padx=8, pady=4, fill='x')

        ttk.Separator(parent, orient='horizontal').pack(fill='x', padx=10, pady=6)
        tk.Label(parent, text="KEYS", font=('Helvetica', 9, 'bold'),
                 fg=self.FG_DIM, bg=self.PANEL).pack(padx=10, anchor='w')
        for key, desc in [("←/→", "Page"), ("1–5", "Tabs"), ("S", "Shuffle"), ("G", "Grid"), ("J", "Jump"), ("Q", "Quit")]:
            r = tk.Frame(parent, bg=self.PANEL)
            r.pack(fill='x', padx=10, pady=1)
            tk.Label(r, text=key, font=('Courier', 8, 'bold'),
                     fg='#4A90D9', bg=self.PANEL, width=5).pack(side='left')
            tk.Label(r, text=desc, font=('Helvetica', 8),
                     fg=self.FG_DIM, bg=self.PANEL).pack(side='left')

    def _build_controls(self, parent):
        nav = tk.Frame(parent, bg=self.BAR)
        nav.pack(side='left', padx=12, pady=6)

        btn_kw = dict(font=('Helvetica', 10, 'bold'), bg='#1a4080', fg=self.FG,
                      relief='flat', padx=10, pady=4, cursor='hand2')

        tk.Button(nav, text='◀  Prev', command=self._prev_page, **btn_kw).pack(side='left', padx=3)
        self._page_var = tk.StringVar(value="Page 1 / 1")
        tk.Label(nav, textvariable=self._page_var, font=('Helvetica', 10),
                 fg=self.FG, bg=self.BAR, width=14).pack(side='left', padx=6)
        tk.Button(nav, text='Next  ▶', command=self._next_page, **btn_kw).pack(side='left', padx=3)
        tk.Button(nav, text='Jump...', command=self._jump_page, **btn_kw).pack(side='left', padx=8)

        grid_frame = tk.Frame(parent, bg=self.BAR)
        grid_frame.pack(side='left', padx=16)
        tk.Label(grid_frame, text="Grid:", font=('Helvetica', 9),
                 fg=self.FG_DIM, bg=self.BAR).pack(side='left', padx=(0, 4))

        self._grid_btns = {}
        dims = {1:'1×1', 4:'2×2', 9:'3×3', 16:'4×4', 25:'5×5'}
        for n, label in dims.items():
            b = tk.Button(grid_frame, text=label, font=('Helvetica', 9),
                          bg=self.PANEL, fg=self.FG_DIM, relief='flat', padx=6, pady=2,
                          command=lambda v=n: self._set_grid(v))
            b.pack(side='left', padx=2)
            self._grid_btns[n] = b
        self._grid_btns[25].configure(fg=self.FG, bg='#1a4080')

        right = tk.Frame(parent, bg=self.BAR)
        right.pack(side='right', padx=12)
        tk.Button(right, text='⟳  Shuffle', command=self._shuffle, **btn_kw).pack(side='left', padx=4)
        self._border_btn = tk.Button(right, text='🔲  Borders OFF', command=self._toggle_borders,
                                      bg=self.PANEL, fg=self.FG_DIM, font=('Helvetica', 9),
                                      relief='flat', padx=8, pady=4, cursor='hand2')
        self._border_btn.pack(side='left', padx=4)
        self._white_btn = tk.Button(right, text='⬜  BG: Black', command=self._toggle_background,
                                     bg=self.PANEL, fg=self.FG_DIM, font=('Helvetica', 9),
                                     relief='flat', padx=8, pady=4, cursor='hand2')
        self._white_btn.pack(side='left', padx=4)

    def _switch_tab(self, tab):
        self.tab = tab
        self.page = 0
        color = self.TAB_COLORS[tab]
        for k, btn in self._tab_btns.items():
            btn.configure(fg=color if k == tab else self.FG_DIM,
                         bg=self.BG if k == tab else self.BAR)
        self._refresh()

    def _set_grid(self, n):
        self.per_page = n
        self.page = 0
        for k, b in self._grid_btns.items():
            b.configure(bg='#1a4080' if k == n else self.PANEL,
                        fg=self.FG if k == n else self.FG_DIM)
        self._refresh()

    def _next_page(self):
        total = self._total_pages()
        if self.page < total - 1:
            self.page += 1
            self._refresh()

    def _prev_page(self):
        if self.page > 0:
            self.page -= 1
            self._refresh()

    def _jump_page(self):
        total = self._total_pages()
        p = simpledialog.askinteger("Jump to Page", f"Page (1–{total}):", minvalue=1, maxvalue=total, parent=self.root)
        if p:
            self.page = p - 1
            self._refresh()

    def _shuffle(self):
        if self.tab in ('valid', 'invalid', 'compare'):
            self.seed = random.randint(0, 99999)
            self.page = 0
            self._refresh()

    def _toggle_borders(self):
        self.show_borders = not self.show_borders
        self._border_btn.configure(text=f"🔲  Borders {'ON' if self.show_borders else 'OFF'}",
                                   bg='#1a4080' if self.show_borders else self.PANEL,
                                   fg=self.FG if self.show_borders else self.FG_DIM)
        self._refresh()

    def _toggle_background(self):
        self.white_background = not self.white_background
        bg_text = 'White' if self.white_background else 'Black'
        self._white_btn.configure(text=f"⬜  BG: {bg_text}",
                                  bg='#1a4080' if self.white_background else self.PANEL,
                                  fg=self.FG if self.white_background else self.FG_DIM)
        self._refresh()

    def _total_pages(self):
        if self.tab == 'original':
            total = len(self.viz.original_images)
        elif self.tab == 'valid':
            total = len(self.viz.valid_indices)
        elif self.tab == 'invalid':
            total = len(self.viz.invalid_indices)
        elif self.tab == 'compare':
            total = min(len(self.viz.valid_indices), len(self.viz.invalid_indices))
        else:
            total = 1
        return max(1, (total + self.per_page - 1) // self.per_page)

    def _refresh(self):
        self.fig.clear()
        self._items = []
        color = self.TAB_COLORS[self.tab]
        total_pages = self._total_pages()
        self._page_var.set(f"Page {self.page + 1} / {total_pages}")

        if self.tab == 'legend':
            self._draw_legend(color)
        elif self.tab == 'compare':
            self._draw_compare(color)
        else:
            self._draw_grid(color)

        self.canvas.draw()

    def _get_page_items(self):
        start, end = self.page * self.per_page, (self.page + 1) * self.per_page

        if self.tab == 'original':
            imgs = self.viz.original_images[start:end]
            labels = [r['recipeId'] for r in self.viz.original_recipes[start:end]]
            recipes = self.viz.original_recipes[start:end]
            return list(zip(imgs, labels, recipes))

        if self.tab in ('valid', 'invalid'):
            rng = np.random.RandomState(self.seed + self.page)
            pool = self.viz.valid_indices if self.tab == 'valid' else self.viz.invalid_indices
            sample = rng.choice(pool, min(self.per_page, len(pool)), replace=False)
            imgs = [self.viz.X_all[i] for i in sample]
            labels = [f"{'Valid' if self.tab == 'valid' else 'Invalid'} #{i}" for i in sample]
            return [(img, lbl, None) for img, lbl in zip(imgs, labels)]

        return []

    def _draw_grid(self, accent):
        items = self._get_page_items()
        self._items = items
        if not items:
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, "No data", ha='center', va='center',
                    color=self.FG, fontsize=14, transform=ax.transAxes)
            ax.set_facecolor(self.BG)
            return

        # Apply background and borders if enabled
        if self.white_background or self.show_borders:
            processed = []
            for img, label, recipe in items:
                if self.white_background:
                    img = self.viz.set_white_background(img)
                if self.show_borders:
                    img = self.viz.add_cell_borders(img)
                processed.append((img, label, recipe))
            items = processed

        n = len(items)
        cols = max(1, int(np.ceil(np.sqrt(self.per_page))))
        rows = max(1, (self.per_page + cols - 1) // cols)

        self.fig.subplots_adjust(left=0.01, right=0.99, top=0.94, bottom=0.02, wspace=0.05, hspace=0.3)
        tab_name = {'original':'Original', 'valid':'Valid', 'invalid':'Invalid'}.get(self.tab, self.tab)
        self.fig.suptitle(f"{tab_name}  —  Page {self.page+1}/{self._total_pages()}  ({n} shown)",
                         color=accent, fontsize=12, fontweight='bold', y=0.99)

        axes = self.fig.subplots(rows, cols)
        if not hasattr(axes, '__len__'):
            axes = np.array([[axes]])
        elif axes.ndim == 1:
            axes = axes.reshape(1, -1)
        axes_flat = axes.flatten()

        for idx, (img, label, _) in enumerate(items):
            ax = axes_flat[idx]
            ax.imshow(img, interpolation='nearest')
            ax.set_title(label if len(label) <= 22 else label[:19] + '...', fontsize=7, color=accent, pad=2)
            ax.set_facecolor(self.BG)
            ax.axis('off')
            for spine in ax.spines.values():
                spine.set_edgecolor(accent)
                spine.set_linewidth(0.6)

        for idx in range(n, len(axes_flat)):
            axes_flat[idx].axis('off')
            axes_flat[idx].set_facecolor(self.BG)

        total = (len(self.viz.original_images) if self.tab == 'original' else
                 len(self.viz.valid_indices) if self.tab == 'valid' else len(self.viz.invalid_indices))
        self._status.set(f"Tab: {self.tab} | Page {self.page+1}/{self._total_pages()} | {n}/{total} | Seed: {self.seed}")

    def _draw_compare(self, accent):
        rng = np.random.RandomState(self.seed + self.page)
        n = self.per_page // 2
        v_idx = rng.choice(self.viz.valid_indices, min(n, len(self.viz.valid_indices)), replace=False)
        i_idx = rng.choice(self.viz.invalid_indices, min(n, len(self.viz.invalid_indices)), replace=False)

        self.fig.subplots_adjust(left=0.04, right=0.99, top=0.92, bottom=0.02, wspace=0.05, hspace=0.3)
        self.fig.suptitle(f"Compare  —  Valid (top) vs Invalid (bottom)  |  Page {self.page+1}",
                         color=accent, fontsize=12, fontweight='bold', y=0.99)

        self._items = []
        rows, cols = 2, max(1, len(v_idx))
        axes = self.fig.subplots(rows, cols)
        if cols == 1:
            axes = axes.reshape(2, 1)

        for col, idx in enumerate(v_idx):
            img = self.viz.X_all[idx]
            if self.white_background:
                img = self.viz.set_white_background(img)
            if self.show_borders:
                img = self.viz.add_cell_borders(img)
            axes[0, col].imshow(img, interpolation='nearest')
            axes[0, col].set_title(f'V#{idx}', fontsize=7, color=self.TAB_COLORS['valid'], pad=2)
            axes[0, col].axis('off')
            axes[0, col].set_facecolor(self.BG)
            self._items.append((img, f'Valid #{idx}', None))

        for col, idx in enumerate(i_idx):
            img = self.viz.X_all[idx]
            if self.white_background:
                img = self.viz.set_white_background(img)
            if self.show_borders:
                img = self.viz.add_cell_borders(img)
            axes[1, col].imshow(img, interpolation='nearest')
            axes[1, col].set_title(f'X#{idx}', fontsize=7, color=self.TAB_COLORS['invalid'], pad=2)
            axes[1, col].axis('off')
            axes[1, col].set_facecolor(self.BG)
            self._items.append((img, f'Invalid #{idx}', None))

        self.fig.text(0.01, 0.73, 'VALID', color=self.TAB_COLORS['valid'],
                      fontsize=9, fontweight='bold', rotation=90, va='center')
        self.fig.text(0.01, 0.27, 'INVALID', color=self.TAB_COLORS['invalid'],
                      fontsize=9, fontweight='bold', rotation=90, va='center')
        self._status.set(f"Compare | {len(v_idx)} valid vs {len(i_idx)} invalid | Seed: {self.seed}")

    def _draw_legend(self, accent):
        self.fig.suptitle("Category Shapes & Tier Fills", color=accent, fontsize=13, fontweight='bold')
        self.fig.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.08, wspace=0.4, hspace=0.6)

        cats = ['metal', 'wood', 'stone', 'monster_drop', 'elemental']
        colors = [(0.4,0.6,0.8), (0.6,0.4,0.2), (0.5,0.5,0.5), (0.8,0.3,0.8), (0.3,0.8,0.3)]
        axes = self.fig.subplots(3, 5)

        for col, (cat, col_rgb) in enumerate(zip(cats, colors)):
            shape = self.viz.CATEGORY_SHAPES.get(cat, self.viz.DEFAULT_SHAPE)
            img = np.zeros((4, 4, 3))
            for c in range(3):
                img[:, :, c] = shape * col_rgb[c]
            axes[0, col].imshow(img, interpolation='nearest')
            axes[0, col].set_title(cat.replace('_', '\n'), fontsize=8, color=self.FG, pad=3)
            axes[0, col].set_facecolor(self.BG)
            axes[0, col].axis('off')
        axes[0, 0].set_ylabel('Shapes', fontsize=9, color=self.FG_DIM)

        base_shape = self.viz.CATEGORY_SHAPES['metal']
        base_rgb = (0.4, 0.6, 0.8)
        for tier in range(1, 5):
            fs = self.viz.TIER_FILL_SIZES[tier]
            mask = np.zeros((4, 4))
            off = (4 - fs) // 2
            mask[off:off+fs, off:off+fs] = 1.0
            comb = base_shape * mask
            img = np.zeros((4, 4, 3))
            for c in range(3):
                img[:, :, c] = comb * base_rgb[c]
            axes[1, tier-1].imshow(img, interpolation='nearest')
            axes[1, tier-1].set_title(f'T{tier} ({fs}×{fs})', fontsize=8, color=self.FG, pad=3)
            axes[1, tier-1].set_facecolor(self.BG)
            axes[1, tier-1].axis('off')
        axes[1, 4].axis('off')
        axes[1, 0].set_ylabel('Tiers', fontsize=9, color=self.FG_DIM)

        hues = {'metal':210, 'wood':30, 'stone':0, 'monster_drop':300, 'elemental':280}
        for col, (cat, hue) in enumerate(hues.items()):
            rgb = hsv_to_rgb(hue/360, 0.7, 0.75)
            swatch = np.full((4, 8, 3), rgb, dtype=np.float32)
            axes[2, col].imshow(swatch, interpolation='nearest', aspect='auto')
            axes[2, col].set_title(f'{hue}°', fontsize=8, color=self.FG, pad=3)
            axes[2, col].set_facecolor(self.BG)
            axes[2, col].axis('off')
        axes[2, 0].set_ylabel('Hues', fontsize=9, color=self.FG_DIM)

        self.fig.set_facecolor(self.BG)
        self._status.set("Legend view | Category shapes · Tier fills · Color hues")

    def _on_click(self, event):
        if event.inaxes is None:
            return
        all_axes = self.fig.get_axes()
        try:
            idx = all_axes.index(event.inaxes)
        except ValueError:
            return
        if idx < len(self._items):
            img, label, recipe = self._items[idx]
            self._show_detail(img, label, recipe)

    def _show_detail(self, img, label, recipe):
        win = tk.Toplevel(self.root)
        win.title(label[:60])
        win.configure(bg=self.PANEL)
        win.geometry("420x520")

        fig2 = Figure(figsize=(4, 4), facecolor=self.PANEL)
        ax = fig2.add_subplot(111)
        ax.imshow(img, interpolation='nearest')
        ax.set_title(label, fontsize=9, color=self.FG, pad=4)
        ax.set_facecolor(self.PANEL)
        ax.axis('off')
        fig2.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.02)

        c2 = FigureCanvasTkAgg(fig2, master=win)
        c2.get_tk_widget().pack(fill='both', expand=True, padx=8, pady=8)
        c2.draw()

        if recipe:
            mats = self.viz.get_materials_for_recipe(recipe)
            info = tk.Text(win, font=('Courier', 9), fg=self.FG, bg=self.BG,
                          relief='flat', height=6, state='disabled')
            info.pack(fill='x', padx=8, pady=(0, 8))
            info.configure(state='normal')
            info.insert('end', f"Recipe: {recipe['recipeId']}\n\n")
            for name, cat, tier in sorted(mats, key=lambda x: x[2]):
                info.insert('end', f"  T{tier} {cat:<12} {name}\n")
            info.configure(state='disabled')

        tk.Button(win, text="Close", bg='#1a4080', fg=self.FG, relief='flat',
                  font=('Helvetica', 9), padx=10, pady=4, command=win.destroy).pack(pady=(0, 8))

    def _bind_keys(self):
        self.root.bind('<Left>', lambda _: self._prev_page())
        self.root.bind('<Right>', lambda _: self._next_page())
        for i, k in enumerate(self.TAB_KEYS, 1):
            self.root.bind(str(i), lambda _, key=k: self._switch_tab(key))
        for c in ['s', 'S']:
            self.root.bind(c, lambda _: self._shuffle())
        for c in ['j', 'J']:
            self.root.bind(c, lambda _: self._jump_page())
        for c in ['g', 'G']:
            self.root.bind(c, lambda _: self._cycle_grid())
        for c in ['q', 'Q']:
            self.root.bind(c, lambda _: self.root.quit())

    def _cycle_grid(self):
        opts = self.GRID_OPTIONS
        idx = opts.index(self.per_page) if self.per_page in opts else 0
        self._set_grid(opts[(idx + 1) % len(opts)])

    def run(self):
        self._bind_keys()
        self.root.mainloop()


if __name__ == "__main__":
    cnn_dir = Path(__file__).parent

    dataset_v2 = cnn_dir / "recipe_dataset_v2.npz"
    dataset_v1 = cnn_dir / "recipe_dataset.npz"
    materials = cnn_dir / "../../../Game-1-modular/items.JSON/items-materials-1.JSON"
    placements = cnn_dir / "../../../Game-1-modular/placements.JSON/placements-smithing-1.JSON"

    dataset_path = dataset_v2 if dataset_v2.exists() else dataset_v1
    if not dataset_path.exists():
        dataset_path = Path(filedialog.askopenfilename(title="Select dataset .npz file", filetypes=[("NPZ files", "*.npz")]))
    if not materials.exists():
        materials = Path(filedialog.askopenfilename(title="Select materials JSON", filetypes=[("JSON files", "*.JSON")]))
    if not placements.exists():
        placements = Path(filedialog.askopenfilename(title="Select placements JSON", filetypes=[("JSON files", "*.JSON")]))

    viz = SmithingDatasetVisualizer(str(dataset_path), str(materials), str(placements), use_shapes=dataset_v2.exists())
    app = SmithingVisualizerApp(viz)
    app.run()
