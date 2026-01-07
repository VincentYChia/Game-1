"""
Interactive Crafting UI Renderer

Renders 5 discipline-specific interactive crafting UIs:
- Smithing: Grid-based placement
- Refining: Hub-and-spoke model
- Alchemy: Sequential slots
- Engineering: Slot-type system
- Adornments: Grid-based pattern placement

Layout: Material Palette (left) | Placement Grid/Slots (right) | Recipe Status + Buttons (bottom)
"""

import pygame
from typing import Tuple, List, Dict, Optional, Any
from core.config import Config
from data.databases import MaterialDatabase


class InteractiveCraftingRenderer:
    """Renders interactive crafting UIs for all disciplines"""

    def __init__(self, renderer_instance):
        """Initialize with reference to main renderer"""
        self.renderer = renderer_instance
        self.screen = renderer_instance.screen
        self.font = renderer_instance.font
        self.small_font = renderer_instance.small_font

    def render(self, character, interactive_ui, mouse_pos: Tuple[int, int]):
        """
        Main render method - routes to discipline-specific rendering.

        Returns: (window_rect, material_palette_rects, grid_rects, button_rects, recipe_matched)
        """
        if not interactive_ui or not character.crafting_ui_open or not character.active_station:
            return None

        s = Config.scale
        discipline = interactive_ui.discipline

        # Window dimensions
        ww, wh = Config.MENU_LARGE_W, Config.MENU_MEDIUM_H
        wx = max(0, (Config.VIEWPORT_WIDTH - ww) // 2)
        wy = max(0, (Config.VIEWPORT_HEIGHT - wh) // 2)

        # Create main surface
        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 245))

        # Header
        station = character.active_station
        header = f"Interactive: {station.station_type.value.upper()} (T{station.tier})"
        color = station.get_color()
        surf.blit(self.font.render(header, True, color), (s(20), s(15)))
        help_text = "[ESC] Close | Place materials to match recipe"
        surf.blit(self.small_font.render(help_text, True, (150, 150, 180)), (s(20), s(42)))

        # Layout dimensions
        palette_w = s(200)
        grid_w = ww - palette_w - s(60)
        palette_x = s(20)
        grid_x = palette_x + palette_w + s(30)
        content_y = s(70)
        content_h = wh - content_y - s(90)  # Leave room for buttons

        # Render material palette
        palette_rects = self._render_palette(surf, interactive_ui, palette_x, content_y, palette_w, content_h, mouse_pos)

        # Render discipline-specific grid/slots
        grid_rects = self._render_placement_area(surf, interactive_ui, grid_x, content_y, grid_w, content_h, mouse_pos, discipline)

        # Recipe status
        status_y = content_y + content_h + s(10)
        recipe_matched = interactive_ui.matched_recipe is not None

        if recipe_matched:
            recipe = interactive_ui.matched_recipe
            status_color = (100, 255, 100)
            status_text = f"✓ {recipe.output_id}"
        else:
            status_color = (150, 150, 150)
            status_text = "No recipe matched"

        surf.blit(self.small_font.render(status_text, True, status_color), (grid_x, status_y))

        # Always-visible buttons (Minigame + Instant)
        button_y = status_y + s(25)
        button_rects = self._render_buttons(surf, interactive_ui, grid_x, button_y, mouse_pos)

        # Blit to screen
        self.screen.blit(surf, (wx, wy))

        # Convert rects to screen coordinates
        palette_rects_screen = [(r[0] + wx, r[1] + wy, r[2], r[3], mat_id) for r, mat_id in palette_rects]
        grid_rects_screen = [(r[0] + wx, r[1] + wy, r[2], r[3], pos) for r, pos in grid_rects]
        button_rects_screen = {k: pygame.Rect(v.x + wx, v.y + wy, v.w, v.h) for k, v in button_rects.items()}

        return (
            pygame.Rect(wx, wy, ww, wh),
            palette_rects_screen,
            grid_rects_screen,
            button_rects_screen,
            recipe_matched
        )

    def _render_palette(self, surf, interactive_ui, x, y, w, h, mouse_pos):
        """Render material palette (left side)"""
        s = Config.scale
        palette_rects = []

        # Background
        pygame.draw.rect(surf, (15, 15, 25), pygame.Rect(x, y, w, h))
        pygame.draw.rect(surf, (60, 80, 100), pygame.Rect(x, y, w, h), s(1))

        # Title
        title = self.small_font.render("Inventory", True, (150, 200, 150))
        surf.blit(title, (x + s(5), y + s(5)))

        # Get materials
        materials = interactive_ui.get_available_materials()

        # Display materials
        item_y = y + s(25)
        item_x_start = x + s(5)
        item_w = w - s(10)
        item_h = s(35)
        max_visible = int((h - s(30)) / (item_h + s(3)))

        for i, item_stack in enumerate(materials):
            if i >= max_visible:
                more_text = self.small_font.render(f"+{len(materials) - i} more", True, (150, 150, 150))
                surf.blit(more_text, (item_x_start, item_y))
                break

            item_rect = pygame.Rect(item_x_start, item_y, item_w, item_h)
            is_hover = item_rect.collidepoint(mouse_pos)
            bg_color = (50, 70, 100) if is_hover else (30, 40, 60)

            pygame.draw.rect(surf, bg_color, item_rect, border_radius=s(2))
            pygame.draw.rect(surf, (70, 100, 150), item_rect, s(1), border_radius=s(2))

            # Material info
            mat = interactive_ui.mat_db.get_material(item_stack.item_id)
            if mat:
                mat_name = f"{mat.name} x{item_stack.quantity}"
                tier_color = self._get_tier_color(mat.tier)
                name_text = self.small_font.render(mat_name, True, tier_color)
                surf.blit(name_text, (item_x_start + s(8), item_y + s(5)))

                # Tier badge
                tier_text = self.small_font.render(f"T{mat.tier}", True, (200, 200, 200))
                tier_x = item_x_start + item_w - s(20)
                surf.blit(tier_text, (tier_x, item_y + s(5)))

            palette_rects.append((item_rect, item_stack.item_id))
            item_y += item_h + s(3)

        return palette_rects

    def _render_placement_area(self, surf, interactive_ui, x, y, w, h, mouse_pos, discipline):
        """Render discipline-specific placement area (right side)"""
        s = Config.scale
        grid_rects = []

        # Background
        pygame.draw.rect(surf, (15, 15, 25), pygame.Rect(x, y, w, h))
        pygame.draw.rect(surf, (60, 100, 80), pygame.Rect(x, y, w, h), s(1))

        # Title
        title = self.small_font.render("Placement", True, (150, 200, 150))
        surf.blit(title, (x + s(5), y + s(5)))

        content_y = y + s(25)
        content_h = h - s(35)

        # Route to discipline-specific rendering
        if discipline in ["smithing", "adornments"]:
            grid = interactive_ui.get_grid_contents()
            self._render_grid(surf, interactive_ui, x, content_y, w, content_h, grid, grid_rects)
        elif discipline == "refining":
            placement = interactive_ui.get_placement()
            self._render_hub_spoke(surf, interactive_ui, x, content_y, w, content_h, placement, grid_rects)
        elif discipline == "alchemy":
            placement = interactive_ui.get_placement()
            self._render_sequential_slots(surf, interactive_ui, x, content_y, w, content_h, placement, grid_rects)
        elif discipline == "engineering":
            placement = interactive_ui.get_placement()
            self._render_slot_types(surf, interactive_ui, x, content_y, w, content_h, placement, grid_rects)

        return grid_rects

    def _render_grid(self, surf, ui, x, y, w, h, grid, grid_rects):
        """Render grid-based placement (smithing, adornments)"""
        s = Config.scale
        grid_size = ui.grid_size

        # Calculate cell size
        max_w = (w - s(10)) / grid_size
        max_h = (h - s(10)) / grid_size
        cell_size = min(int(max_w), int(max_h), s(45))

        grid_w = cell_size * grid_size + s(2)
        grid_h = cell_size * grid_size + s(2)

        # Center grid
        grid_x = x + (w - grid_w) // 2
        grid_y = y + (h - grid_h) // 2

        # Draw grid background
        pygame.draw.rect(surf, (10, 10, 20), pygame.Rect(grid_x, grid_y, grid_w, grid_h))
        pygame.draw.rect(surf, (80, 120, 100), pygame.Rect(grid_x, grid_y, grid_w, grid_h), s(1))

        # Draw cells
        for gx in range(grid_size):
            for gy in range(grid_size):
                cell_x = grid_x + gx * cell_size
                cell_y = grid_y + gy * cell_size
                cell_rect = pygame.Rect(cell_x, cell_y, cell_size, cell_size)

                filled = (gx, gy) in grid
                mat_id = grid.get((gx, gy)) if filled else None

                cell_color = (40, 60, 80) if filled else (20, 30, 50)
                border_color = (100, 150, 120) if filled else (60, 80, 100)

                pygame.draw.rect(surf, cell_color, cell_rect)
                pygame.draw.rect(surf, border_color, cell_rect, s(1))

                if filled and mat_id:
                    mat = ui.mat_db.get_material(mat_id)
                    if mat:
                        abbrev = mat.name[:3].upper()
                        mat_text = self.small_font.render(abbrev, True, (200, 200, 200))
                        text_rect = mat_text.get_rect(center=cell_rect.center)
                        surf.blit(mat_text, (text_rect.x, text_rect.y))

                grid_rects.append((cell_rect, (gx, gy)))

    def _render_hub_spoke(self, surf, ui, x, y, w, h, placement, grid_rects):
        """Render hub-and-spoke for refining"""
        s = Config.scale
        center_x = x + w // 2
        center_y = y + h // 2
        slot_size = s(35)
        radius = s(70)

        cores = placement.get("cores", [])
        core_positions = []

        if len(cores) == 1:
            core_rect = pygame.Rect(center_x - slot_size // 2, center_y - slot_size // 2, slot_size, slot_size)
            core_positions.append((core_rect, 0))
        elif len(cores) == 2:
            core_rect1 = pygame.Rect(center_x - slot_size // 2, center_y - radius // 2 - slot_size // 2, slot_size, slot_size)
            core_rect2 = pygame.Rect(center_x - slot_size // 2, center_y + radius // 2 - slot_size // 2, slot_size, slot_size)
            core_positions.append((core_rect1, 0))
            core_positions.append((core_rect2, 1))
        elif len(cores) == 3:
            for i in range(3):
                angle = (i * 120 + 90) * 3.14159 / 180
                core_x = center_x + radius * 0.7 * int(pygame.math.Vector2(1, 0).rotate(i * 120).x)
                core_y = center_y + radius * 0.7 * int(pygame.math.Vector2(0, 1).rotate(i * 120).y)
                core_rect = pygame.Rect(core_x - slot_size // 2, core_y - slot_size // 2, slot_size, slot_size)
                core_positions.append((core_rect, i))

        # Draw core slots
        for core_rect, idx in core_positions:
            core_mat = cores[idx] if idx < len(cores) else None
            core_color = (60, 100, 80) if core_mat else (30, 40, 60)
            pygame.draw.rect(surf, core_color, core_rect, border_radius=s(2))
            pygame.draw.rect(surf, (100, 150, 120), core_rect, s(1), border_radius=s(2))

            if core_mat:
                mat = ui.mat_db.get_material(core_mat)
                if mat:
                    label = self.small_font.render(mat.name[:2], True, (200, 200, 200))
                    surf.blit(label, (core_rect.x + s(5), core_rect.y + s(8)))

            grid_rects.append((core_rect, ('core', idx)))

        # Surrounding slots (6 positions)
        surrounding = placement.get("surrounding", [])
        for i in range(6):
            surr_x = center_x + radius * int(pygame.math.Vector2(1, 0).rotate(i * 60).x)
            surr_y = center_y + radius * int(pygame.math.Vector2(0, 1).rotate(i * 60).y)

            surr_rect = pygame.Rect(surr_x - slot_size // 2, surr_y - slot_size // 2, slot_size, slot_size)
            surr_mat = surrounding[i] if i < len(surrounding) else None
            surr_color = (60, 100, 80) if surr_mat else (30, 40, 60)

            pygame.draw.rect(surf, surr_color, surr_rect, border_radius=s(2))
            pygame.draw.rect(surf, (100, 150, 120), surr_rect, s(1), border_radius=s(2))

            if surr_mat:
                mat = ui.mat_db.get_material(surr_mat)
                if mat:
                    label = self.small_font.render(mat.name[:2], True, (200, 200, 200))
                    surf.blit(label, (surr_rect.x + s(5), surr_rect.y + s(8)))

            grid_rects.append((surr_rect, ('surrounding', i)))

    def _render_sequential_slots(self, surf, ui, x, y, w, h, placement, grid_rects):
        """Render sequential slots for alchemy"""
        s = Config.scale
        slot_h = s(40)
        num_slots = len(placement)
        slot_w = (w - s(20)) // num_slots if num_slots > 0 else w

        for i, mat_id in enumerate(placement):
            slot_x = x + s(10) + i * (slot_w + s(2))
            slot_y = y + s(20)
            slot_rect = pygame.Rect(slot_x, slot_y, slot_w - s(2), slot_h)

            slot_color = (60, 100, 80) if mat_id else (30, 40, 60)
            pygame.draw.rect(surf, slot_color, slot_rect, border_radius=s(2))
            pygame.draw.rect(surf, (100, 150, 120), slot_rect, s(1), border_radius=s(2))

            # Slot number
            num_text = self.small_font.render(str(i + 1), True, (150, 150, 150))
            surf.blit(num_text, (slot_x + s(2), slot_y + s(2)))

            # Material
            if mat_id:
                mat = ui.mat_db.get_material(mat_id)
                if mat:
                    label = self.small_font.render(mat.name[:4], True, (200, 200, 200))
                    text_rect = label.get_rect(center=slot_rect.center)
                    surf.blit(label, (text_rect.x, text_rect.y + s(5)))

            grid_rects.append((slot_rect, i))

    def _render_slot_types(self, surf, ui, x, y, w, h, placement, grid_rects):
        """Render slot-types for engineering"""
        s = Config.scale
        slot_types = list(placement.keys())[:4]  # Show max 4 types
        slot_h = s(35)
        slot_w = (w - s(20)) // len(slot_types) if len(slot_types) > 0 else w

        for i, slot_type in enumerate(slot_types):
            slot_x = x + s(10) + i * (slot_w + s(2))
            slot_y = y + s(20)
            slot_rect = pygame.Rect(slot_x, slot_y, slot_w - s(2), slot_h)

            materials = placement.get(slot_type, [])
            slot_color = (60, 100, 80) if materials else (30, 40, 60)

            pygame.draw.rect(surf, slot_color, slot_rect, border_radius=s(2))
            pygame.draw.rect(surf, (100, 150, 120), slot_rect, s(1), border_radius=s(2))

            # Type label + count
            label = f"{slot_type}({len(materials)})"
            label_text = self.small_font.render(label, True, (150, 200, 150))
            text_rect = label_text.get_rect(center=slot_rect.center)
            surf.blit(label_text, (text_rect.x, text_rect.y))

            grid_rects.append((slot_rect, (slot_type, 0)))

    def _render_buttons(self, surf, interactive_ui, x, y, mouse_pos) -> Dict[str, pygame.Rect]:
        """Render always-visible craft buttons"""
        s = Config.scale
        button_rects = {}

        # Minigame button
        btn_minigame = pygame.Rect(x, y, s(110), s(30))
        btn_color = (80, 120, 180) if btn_minigame.collidepoint(mouse_pos) else (60, 100, 160)
        pygame.draw.rect(surf, btn_color, btn_minigame, border_radius=s(3))
        pygame.draw.rect(surf, (100, 150, 200), btn_minigame, s(2), border_radius=s(3))
        btn_text = self.small_font.render("Minigame", True, (200, 200, 200))
        text_rect = btn_text.get_rect(center=btn_minigame.center)
        surf.blit(btn_text, (text_rect.x, text_rect.y))
        button_rects['minigame'] = btn_minigame

        # Instant button
        btn_instant = pygame.Rect(x + s(125), y, s(110), s(30))
        btn_color = (120, 100, 80) if btn_instant.collidepoint(mouse_pos) else (100, 80, 60)
        pygame.draw.rect(surf, btn_color, btn_instant, border_radius=s(3))
        pygame.draw.rect(surf, (150, 130, 100), btn_instant, s(2), border_radius=s(3))
        btn_text = self.small_font.render("Instant", True, (200, 200, 200))
        text_rect = btn_text.get_rect(center=btn_instant.center)
        surf.blit(btn_text, (text_rect.x, text_rect.y))
        button_rects['instant'] = btn_instant

        return button_rects

    def _get_tier_color(self, tier: int) -> Tuple[int, int, int]:
        """Get color for material tier"""
        tier_colors = {
            1: (180, 180, 180),  # Gray
            2: (100, 200, 100),  # Green
            3: (100, 150, 255),  # Blue
            4: (255, 180, 50),   # Gold
        }
        return tier_colors.get(tier, (180, 180, 180))
